# ═══════════════════════════════════════════════════════════════════════
#  AGENT TRAINING — instruction store + feedback loop
#  All data lives in the shared SQLite DB (training_instructions +
#  estimation_feedback tables).  load_training_context() is called
#  at the RAG step of every pipeline run and the returned string is
#  prepended to every agent's system prompt.
# ═══════════════════════════════════════════════════════════════════════
import sqlite3, json, os
from datetime import datetime

from .database import _DB_PATH


# ── Read ──────────────────────────────────────────────────────────────

def load_training_context(project_types: list = None) -> str:
    """
    Load active instructions + recent feedback summaries from SQLite.
    project_types: list of detected types for this run (e.g. ["AI", "Cloud"]).
      Instructions tagged with any of those types are included.
      Instructions tagged [] (general) always load regardless.
    Returns a formatted block ready to prepend to agent system prompts.
    Returns "" if nothing is stored yet.
    """
    try:
        con = sqlite3.connect(_DB_PATH)
        con.row_factory = sqlite3.Row

        all_instrs = con.execute(
            "SELECT instruction, category, project_types FROM training_instructions "
            "WHERE active=1 ORDER BY id ASC"
        ).fetchall()

        # Filter by project type: empty project_types on instruction = applies to all
        instructions = []
        for row in all_instrs:
            try:
                ipt = json.loads(row["project_types"] or "[]")
            except Exception:
                ipt = []
            if not ipt:  # general — always include
                instructions.append(row)
            elif not project_types:  # caller didn't specify type — include everything
                instructions.append(row)
            elif any(pt in ipt for pt in project_types):
                instructions.append(row)

        feedback = con.execute(
            "SELECT client_name, bella_hours, actual_hours, bella_cost, actual_cost, "
            "phase_deltas, notes FROM estimation_feedback "
            "WHERE active=1 ORDER BY id DESC LIMIT 20"
        ).fetchall()
        con.close()
    except Exception:
        return ""

    if not instructions and not feedback:
        return ""

    parts = ["═" * 60,
             "AGENT TRAINING CONTEXT — read and apply before estimating",
             "═" * 60]

    if instructions:
        parts.append("\n📋 INSTRUCTIONS FROM PRESALES LEAD:")
        by_cat: dict = {}
        for row in instructions:
            cat = (row["category"] or "general").title()
            by_cat.setdefault(cat, []).append(row["instruction"])
        for cat, items in by_cat.items():
            parts.append(f"\n[{cat}]")
            for item in items:
                parts.append(f"  • {item}")

    if feedback:
        parts.append("\n\n📊 PAST ESTIMATE vs ACTUAL (learn from these gaps):")
        for fb in feedback:
            h_delta = fb["actual_hours"] - fb["bella_hours"]
            c_delta = fb["actual_cost"]  - fb["bella_cost"]
            direction_h = "over-estimated" if h_delta < 0 else "under-estimated"
            direction_c = "over-estimated" if c_delta < 0 else "under-estimated"
            client = fb["client_name"] or "Client"
            parts.append(
                f"\n  Project: {client}\n"
                f"    Hours  — BELLA: {fb['bella_hours']}h | Actual: {fb['actual_hours']}h "
                f"({direction_h} by {abs(h_delta)}h)\n"
                f"    Cost   — BELLA: ${fb['bella_cost']:,}/mo | Actual: ${fb['actual_cost']:,}/mo "
                f"({direction_c} by ${abs(c_delta):,}/mo)"
            )
            try:
                phases = json.loads(fb["phase_deltas"] or "[]")
                if phases:
                    parts.append("    Phase breakdown:")
                    for p in phases[:8]:
                        d = p.get("actual_hours", 0) - p.get("bella_hours", 0)
                        sign = "+" if d >= 0 else ""
                        parts.append(f"      {p.get('phase','?')}: BELLA {p.get('bella_hours',0)}h → Actual {p.get('actual_hours',0)}h ({sign}{d}h)")
            except Exception:
                pass
            if fb["notes"]:
                parts.append(f"    Note: {fb['notes']}")

        # Compute aggregate bias
        total_h_delta = sum(fb["actual_hours"] - fb["bella_hours"] for fb in feedback)
        avg_h_delta   = round(total_h_delta / len(feedback))
        if abs(avg_h_delta) > 10:
            bias = "tends to UNDER-estimate" if avg_h_delta > 0 else "tends to OVER-estimate"
            parts.append(
                f"\n  ⚠️  SYSTEMATIC BIAS: Based on {len(feedback)} past project(s), BELLA {bias} "
                f"hours by an average of {abs(avg_h_delta)}h. Adjust your estimates accordingly."
            )

    parts.append("\n" + "═" * 60)
    return "\n".join(parts)


# ── Write ─────────────────────────────────────────────────────────────

def add_instruction(instruction: str, category: str = "general",
                    created_by: str = "", project_types: list = None) -> int:
    """Insert a new training instruction. Returns the new row id."""
    con = sqlite3.connect(_DB_PATH)
    cur = con.execute(
        "INSERT INTO training_instructions (created_at, instruction, category, created_by, project_types) "
        "VALUES (?,?,?,?,?)",
        (datetime.utcnow().isoformat(), instruction.strip(), category.lower(), created_by,
         json.dumps(project_types or []))
    )
    con.commit()
    row_id = cur.lastrowid
    con.close()
    return row_id


def add_feedback(client_name: str, bella_hours: int, actual_hours: int,
                 bella_cost: int, actual_cost: int,
                 phase_deltas: list, notes: str = "",
                 proposal_id: str = "", created_by: str = "") -> int:
    """Store one feedback record comparing BELLA estimate vs actual Excel."""
    con = sqlite3.connect(_DB_PATH)
    cur = con.execute(
        "INSERT INTO estimation_feedback "
        "(created_at, proposal_id, client_name, bella_hours, actual_hours, "
        " bella_cost, actual_cost, phase_deltas, notes, created_by) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        (datetime.utcnow().isoformat(), proposal_id, client_name,
         int(bella_hours), int(actual_hours), int(bella_cost), int(actual_cost),
         json.dumps(phase_deltas), notes, created_by)
    )
    con.commit()
    row_id = cur.lastrowid
    con.close()
    return row_id


def list_instructions(active_only: bool = False) -> list:
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    q = "SELECT * FROM training_instructions"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY id DESC"
    rows = [dict(r) for r in con.execute(q).fetchall()]
    con.close()
    return rows


def list_feedback() -> list:
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "SELECT * FROM estimation_feedback ORDER BY id DESC"
    ).fetchall()]
    con.close()
    return rows


def toggle_instruction(row_id: int, active: bool):
    con = sqlite3.connect(_DB_PATH)
    con.execute("UPDATE training_instructions SET active=? WHERE id=?", (int(active), row_id))
    con.commit()
    con.close()


def delete_instruction(row_id: int):
    con = sqlite3.connect(_DB_PATH)
    con.execute("DELETE FROM training_instructions WHERE id=?", (row_id,))
    con.commit()
    con.close()


def delete_feedback(row_id: int):
    con = sqlite3.connect(_DB_PATH)
    con.execute("DELETE FROM estimation_feedback WHERE id=?", (row_id,))
    con.commit()
    con.close()


# ── Excel parser ──────────────────────────────────────────────────────

def parse_excel_estimate(file_bytes: bytes) -> dict:
    """
    Parse an Excel file (the actual estimate sent to client).
    Returns:
      {
        "total_hours": int,
        "total_cost": int,
        "phases": [{"phase": str, "actual_hours": int, "actual_cost": int}]
      }
    Handles common layouts: one column for phase/task, one for hours, one for cost.
    """
    import io
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
        ws = wb.active
    except ImportError:
        # Fall back to xlrd / pandas if openpyxl not available
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(file_bytes))
            return _parse_df(df)
        except Exception:
            return {"total_hours": 0, "total_cost": 0, "phases": []}
    except Exception:
        return {"total_hours": 0, "total_cost": 0, "phases": []}

    # Find header row — look for cells containing "hour", "day", "effort", "cost"
    header_row = None
    hour_col = cost_col = phase_col = None
    for row_idx, row in enumerate(ws.iter_rows(max_row=20), 1):
        for cell in row:
            val = str(cell.value or "").lower().strip()
            if any(k in val for k in ["hour", "days", "effort", "man day"]):
                hour_col = cell.column
                header_row = row_idx
            if any(k in val for k in ["cost", "price", "amount", "budget"]):
                cost_col = cell.column
                header_row = row_idx
            if any(k in val for k in ["phase", "activity", "task", "module", "workstream"]):
                phase_col = cell.column
                header_row = row_idx

    phases = []
    total_hours = 0
    total_cost  = 0

    if header_row and (hour_col or cost_col):
        for row in ws.iter_rows(min_row=header_row + 1):
            phase_name = str(row[phase_col - 1].value or "").strip() if phase_col else f"Row {row[0].row}"
            hours_val  = row[hour_col - 1].value if hour_col else 0
            cost_val   = row[cost_col  - 1].value if cost_col  else 0
            try:
                h = float(hours_val or 0)
                c = float(cost_val  or 0)
            except (ValueError, TypeError):
                continue
            if h == 0 and c == 0:
                continue
            # If "days" column, convert to hours (×8)
            if hour_col:
                hdr_val = str(ws.cell(header_row, hour_col).value or "").lower()
                if "day" in hdr_val:
                    h = h * 8
            phases.append({"phase": phase_name, "actual_hours": int(h), "actual_cost": int(c)})
            total_hours += int(h)
            total_cost  += int(c)
    else:
        # Fallback: sum all numeric cells
        for row in ws.iter_rows():
            for cell in row:
                try:
                    if isinstance(cell.value, (int, float)) and cell.value > 0:
                        total_hours += int(cell.value)
                except Exception:
                    pass

    return {"total_hours": total_hours, "total_cost": total_cost, "phases": phases}


def _parse_df(df) -> dict:
    total_hours = 0
    total_cost  = 0
    phases = []
    hour_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["hour","effort","day"])), None)
    cost_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["cost","price","amount"])), None)
    name_col = next((c for c in df.columns if any(k in str(c).lower() for k in ["phase","task","activity","module"])), None)
    for _, row in df.iterrows():
        h = int(float(row.get(hour_col, 0) or 0)) if hour_col else 0
        c = int(float(row.get(cost_col, 0)  or 0)) if cost_col  else 0
        n = str(row.get(name_col, "")) if name_col else ""
        if h == 0 and c == 0:
            continue
        phases.append({"phase": n, "actual_hours": h, "actual_cost": c})
        total_hours += h
        total_cost  += c
    return {"total_hours": total_hours, "total_cost": total_cost, "phases": phases}
