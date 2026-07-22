# ═══════════════════════════════════════════════════════════════════════
#  REVIEW & FEEDBACK  —  Production-Ready Presales Intelligence Loop
#  Full-cascade recalibration · KPI delta tracking · Version control
#  Version-aware delivery · Rich history · Accept / Reject workflow
# ═══════════════════════════════════════════════════════════════════════
import copy as _copy
import json
import sqlite3
from datetime import datetime

import streamlit as st

from .database import _DB_PATH
from .utils import safe_dict, safe_list, safe_str, safe_int

# ── Section registry ─────────────────────────────────────────────────────────
_SECTIONS = [
    ("requirements",  "📋 Requirements",   "#14A0B9"),
    ("time",          "⏱️ Time Estimate",   "#00b4d8"),
    ("cost",          "💰 Infra Cost",      "#00d4aa"),
    ("risk",          "⚠️ Risk",           "#ffd166"),
    ("architecture",  "🏗️ Architecture",   "#7b61ff"),
    ("scope",         "📌 Scope",           "#94a3b8"),
    ("proposal",      "📄 Proposal",        "#f87171"),
    ("diagrams",      "📐 Diagrams",        "#a78bfa"),
    ("team",          "👥 Team & Roles",    "#06d6a0"),
]
_SEC_LABEL = {s[0]: s[1] for s in _SECTIONS}
_SEC_COLOR = {s[0]: s[2] for s in _SECTIONS}

_FEEDBACK_TYPES = [
    "Missing Feature / Requirement",
    "Wrong Estimate (Too High)",
    "Wrong Estimate (Too Low)",
    "Scope Issue",
    "Risk Missed",
    "Architecture Gap",
    "Pricing Concern",
    "Wording / Clarity",
    "Other",
]
_PRIORITIES = ["Critical", "High", "Medium", "Low"]

# Full cascade map — scope/requirements trigger complete recalibration of everything
_DOWNSTREAM = {
    "requirements": ["time", "cost", "risk", "architecture", "scope", "proposal", "diagrams"],
    "time":         ["cost", "risk", "scope", "proposal"],
    "cost":         ["risk", "proposal"],
    "risk":         ["proposal"],
    "architecture": ["diagrams", "proposal"],
    "scope":        ["time", "cost", "risk", "architecture", "diagrams", "proposal"],
    "proposal":     [],
    "diagrams":     [],
    "team":         [],
}

_DOWNSTREAM_REASON = {
    ("scope",        "time"):         "Scope change resets the hour estimate",
    ("scope",        "cost"):         "Different scope = different Azure services",
    ("scope",        "risk"):         "Scope affects risk profile and exposure",
    ("scope",        "architecture"): "Architecture reflects the functional scope",
    ("scope",        "diagrams"):     "Diagrams reflect the updated architecture",
    ("scope",        "proposal"):     "Proposal sections rewritten to match scope",
    ("requirements", "time"):         "More/fewer requirements changes estimate",
    ("requirements", "cost"):         "Requirements drive service selection",
    ("requirements", "risk"):         "Requirements complexity affects risk",
    ("requirements", "architecture"): "Components match the requirement list",
    ("requirements", "scope"):        "Scope derived from requirements",
    ("requirements", "proposal"):     "Proposal reflects updated requirements",
    ("requirements", "diagrams"):     "Diagrams show new component landscape",
    ("time",         "cost"):         "Hours drive infrastructure sizing",
    ("time",         "risk"):         "Timeline affects delivery risk",
    ("time",         "scope"):        "Phase boundaries affect scope",
    ("time",         "proposal"):     "Timeline shown in proposal",
    ("cost",         "risk"):         "Budget constraints affect risk mitigation",
    ("cost",         "proposal"):     "Cost table updated in proposal",
    ("risk",         "proposal"):     "Risk section updated in proposal",
    ("architecture", "diagrams"):     "Diagrams regenerated from new architecture",
    ("architecture", "proposal"):     "Architecture section updated in proposal",
}

_STATUS_META = {
    "pending":    {"label": "Pending",    "color": "#ffd166", "bg": "rgba(255,209,102,.12)", "icon": "⏳"},
    "processing": {"label": "Processing", "color": "#00b4d8", "bg": "rgba(0,180,216,.12)",   "icon": "⚙️"},
    "applied":    {"label": "Applied",    "color": "#00d4aa", "bg": "rgba(0,212,170,.12)",   "icon": "✅"},
    "dismissed":  {"label": "Dismissed",  "color": "#64748b", "bg": "rgba(100,116,139,.12)", "icon": "🚫"},
}
_PRIORITY_META = {
    "Critical": {"color": "#f87171", "bg": "rgba(248,113,113,.12)"},
    "High":     {"color": "#ffd166", "bg": "rgba(255,209,102,.12)"},
    "Medium":   {"color": "#00b4d8", "bg": "rgba(0,180,216,.12)"},
    "Low":      {"color": "#94a3b8", "bg": "rgba(148,163,184,.12)"},
}

_QUICK_ACTIONS = [
    ("⬆️ Hours +20%",    "time",         "Wrong Estimate (Too Low)",  "Increase total hours by 20% — estimate seems conservative for this scope complexity."),
    ("⬇️ Hours −20%",    "time",         "Wrong Estimate (Too High)", "Decrease total hours by 20% — estimate appears high relative to the defined scope."),
    ("💰 Upgrade Tiers", "cost",         "Pricing Concern",           "Upgrade Azure service tiers by one level — current tiers may be insufficient for production workloads."),
    ("⚠️ Add Risk Gap",  "risk",         "Risk Missed",               "Add integration complexity and data migration risks — these appear underweighted in the current assessment."),
    ("🏗️ Simplify Arch", "architecture", "Architecture Gap",          "Simplify the architecture — remove components that seem over-engineered for the defined project scope."),
    ("✏️ Adjust Tone",   "proposal",     "Wording / Clarity",         "Adjust proposal tone to be more consultative and business-focused — current version is too technical."),
]

_KEY_FIELDS = {
    "time_estimate":     [("total_hours","Total Hours"),("duration_weeks","Duration"),("confidence","Confidence")],
    "cost_estimate":     [("total_monthly_cost","Monthly Cost ($)"),("total_annual_cost","Annual Cost ($)")],
    "risk_assessment":   [("overall_score","Risk Score"),("overall_level","Risk Level")],
    "architecture":      [("pattern","Pattern"),("components","Components (count)")],
    "scope":             [("in_scope","In-Scope"),("out_of_scope","Out-of-Scope")],
    "proposal":          [("sections","Sections")],
    "semantic_analysis": [("project_type","Project Type"),("complexity_score","Complexity"),("requirements","Requirements")],
    "mermaid_diagrams":  [],
}
_RESULT_KEY = {
    "requirements":"semantic_analysis","time":"time_estimate",
    "cost":"cost_estimate","risk":"risk_assessment",
    "architecture":"architecture","scope":"scope",
    "proposal":"proposal","diagrams":"mermaid_diagrams",
}


# ═══════════════════════════════════════════════════════════════════════
#  KPI HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _get_kpi_snapshot(results: dict) -> dict:
    se     = safe_dict(results.get("semantic_analysis", {}))
    te     = safe_dict(results.get("time_estimate",     {}))
    ri     = safe_dict(results.get("risk_assessment",   {}))
    ce     = safe_dict(results.get("cost_estimate",     {}))
    # Prefer phase-sum for hours so it always matches what the Time tab displays
    phases    = safe_list(te.get("phases", []))
    phase_sum = sum(safe_int(safe_dict(p).get("hours", 0)) for p in phases if isinstance(p, dict))
    hours     = phase_sum if phase_sum > 0 else safe_int(te.get("total_hours", 0))
    # Read monthly cost from any key the AI may have used (azure_costs, aws_costs, services, …)
    monthly = 0
    for _ck in ("azure_costs", "aws_costs", "gcp_costs", "cloud_costs",
                "services", "infrastructure_costs", "cost_breakdown",
                "monthly_breakdown", "cloud_services"):
        for _svc in safe_list(ce.get(_ck, [])):
            monthly += safe_int(safe_dict(_svc).get("monthly_cost", 0))
    monthly += sum(safe_int(safe_dict(t).get("monthly_cost", 0))
                   for t in safe_list(ce.get("third_party_costs", [])))
    if monthly == 0:
        monthly = safe_int(ce.get("total_monthly_cost", 0))
    return {
        "hours":      hours,
        "cost":       monthly,
        "risk":       safe_int(ri.get("overall_score", 0)),
        "risk_level": safe_str(ri.get("overall_level", "")),
        "reqs":       len(safe_list(se.get("requirements", []))),
        "complexity": safe_int(se.get("complexity_score", 0)),
        "duration":   safe_str(te.get("duration_weeks", "")),
        "confidence": safe_str(te.get("confidence", "")),
    }

def _kpi_delta(snap_before: dict, snap_after: dict) -> dict:
    delta = {}
    for k in ("hours", "cost", "risk", "reqs", "complexity"):
        b = snap_before.get(k, 0) or 0
        a = snap_after.get(k, 0)  or 0
        diff = a - b
        pct  = round(diff / b * 100, 1) if b else 0
        delta[k] = {"before": b, "after": a, "diff": diff, "pct": pct}
    return delta

def _delta_badge(diff, pct, unit="", reverse_good=False) -> str:
    if diff == 0:
        return '<span style="color:#475569">→</span>'
    up = diff > 0
    good = (up and not reverse_good) or (not up and reverse_good)
    clr  = "#00d4aa" if good else "#f87171"
    sign = "+" if up else ""
    return (
        f'<span style="color:{clr};font-weight:700;font-size:.78rem">'
        f'{sign}{diff:,}{unit}'
        + (f' ({sign}{pct:.0f}%)' if pct else '')
        + '</span>'
    )

def _kpi_bar(val, max_val, color) -> str:
    pct = min(100, int(val / max_val * 100)) if max_val else 0
    return (
        f'<div style="background:#1e293b;border-radius:3px;height:4px;margin-top:4px">'
        f'<div style="background:{color};border-radius:3px;height:4px;width:{pct}%"></div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════════════
#  DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════

def _db_init_feedback():
    con = sqlite3.connect(_DB_PATH)
    con.execute("""CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER DEFAULT 0, version_num INTEGER DEFAULT 1,
        submitted_by TEXT DEFAULT '', submitted_at TEXT NOT NULL,
        section TEXT NOT NULL, feedback_type TEXT NOT NULL,
        priority TEXT DEFAULT 'Medium', description TEXT NOT NULL,
        status TEXT DEFAULT 'pending', ai_summary TEXT DEFAULT '')""")
    con.execute("""CREATE TABLE IF NOT EXISTS proposal_versions_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER DEFAULT 0, version_num INTEGER NOT NULL,
        created_at TEXT NOT NULL, label TEXT DEFAULT '',
        feedback_summary TEXT DEFAULT '', feedback_ids TEXT DEFAULT '[]',
        kpi_snapshot TEXT DEFAULT '{}', results_snapshot TEXT DEFAULT '{}')""")
    con.commit(); con.close()

def _db_migrate_feedback():
    con = sqlite3.connect(_DB_PATH)
    fb_cols  = {r[1] for r in con.execute("PRAGMA table_info(feedback)").fetchall()}
    ver_cols = {r[1] for r in con.execute("PRAGMA table_info(proposal_versions_v2)").fetchall()}
    for col, ddl in [("ai_summary","TEXT DEFAULT ''")]:
        if col not in fb_cols: con.execute(f"ALTER TABLE feedback ADD COLUMN {col} {ddl}")
    for col, ddl in [("label","TEXT DEFAULT ''"),("kpi_snapshot","TEXT DEFAULT '{}'")]:
        if col not in ver_cols: con.execute(f"ALTER TABLE proposal_versions_v2 ADD COLUMN {col} {ddl}")
    con.commit(); con.close()

try: _db_init_feedback(); _db_migrate_feedback()
except Exception: pass

def save_feedback(run_id, version_num, submitted_by, section, feedback_type, priority, description) -> int:
    try:
        con = sqlite3.connect(_DB_PATH)
        cur = con.execute(
            "INSERT INTO feedback (run_id,version_num,submitted_by,submitted_at,section,"
            "feedback_type,priority,description,status) VALUES (?,?,?,?,?,?,?,?,'pending')",
            (run_id, version_num, submitted_by or "Anonymous",
             datetime.now().strftime("%Y-%m-%d %H:%M"),
             section, feedback_type, priority, description))
        fid = cur.lastrowid; con.commit(); return fid
    except Exception: return 0
    finally:
        try: con.close()
        except Exception: pass

def update_feedback_status(fb_id: int, status: str, ai_summary: str = ""):
    if not fb_id: return
    try:
        con = sqlite3.connect(_DB_PATH)
        con.execute("UPDATE feedback SET status=?, ai_summary=? WHERE id=?", (status, ai_summary, fb_id))
        con.commit(); con.close()
    except Exception: pass

def get_feedback_for_run(run_id: int) -> list:
    try:
        con = sqlite3.connect(_DB_PATH); con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM feedback WHERE run_id=? ORDER BY id DESC", (run_id,)).fetchall()
        con.close(); return [dict(r) for r in rows]
    except Exception: return []

def get_all_feedback(limit: int = 300) -> list:
    try:
        con = sqlite3.connect(_DB_PATH); con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT f.*,p.project_type,p.client_name FROM feedback f "
            "LEFT JOIN proposals p ON f.run_id=p.id ORDER BY f.id DESC LIMIT ?", (limit,)).fetchall()
        con.close(); return [dict(r) for r in rows]
    except Exception: return []

def save_version_snapshot(run_id, version_num, label, feedback_summary,
                           feedback_ids, kpi_snapshot, results) -> int:
    try:
        con = sqlite3.connect(_DB_PATH)
        cur = con.execute(
            "INSERT INTO proposal_versions_v2 "
            "(run_id,version_num,created_at,label,feedback_summary,feedback_ids,kpi_snapshot,results_snapshot) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (run_id, version_num, datetime.now().strftime("%Y-%m-%d %H:%M"),
             label, feedback_summary, json.dumps(feedback_ids),
             json.dumps(kpi_snapshot, default=str), json.dumps(results, default=str)))
        vid = cur.lastrowid; con.commit(); con.close(); return vid
    except Exception: return 0

def get_versions_for_run(run_id: int) -> list:
    try:
        con = sqlite3.connect(_DB_PATH); con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT id,run_id,version_num,created_at,label,feedback_summary,feedback_ids,kpi_snapshot "
            "FROM proposal_versions_v2 WHERE run_id=? ORDER BY version_num ASC", (run_id,)).fetchall()
        con.close()
        result = []
        for r in rows:
            d = dict(r)
            for field in ("feedback_ids", "kpi_snapshot"):
                try: d[field] = json.loads(d.get(field, "{}"))
                except Exception: d[field] = {}
            result.append(d)
        return result
    except Exception: return []

def load_version_results(run_id: int, version_num: int) -> dict:
    try:
        con = sqlite3.connect(_DB_PATH)
        row = con.execute(
            "SELECT results_snapshot FROM proposal_versions_v2 WHERE run_id=? AND version_num=?",
            (run_id, version_num)).fetchone()
        con.close()
        if row: return json.loads(row[0])
    except Exception: pass
    return {}


# ═══════════════════════════════════════════════════════════════════════
#  SESSION STATE
# ═══════════════════════════════════════════════════════════════════════

def _ensure_rfb_state():
    if "_proposal_version_num" not in st.session_state:
        st.session_state["_proposal_version_num"] = 1
    if "_version_snapshots" not in st.session_state:
        st.session_state["_version_snapshots"] = {}
    if "_version_meta" not in st.session_state:
        st.session_state["_version_meta"] = [{
            "num": 1, "label": "Original",
            "ts": datetime.now().strftime("%H:%M"),
            "feedback_summary": "", "feedback_ids": [],
            "kpi": _get_kpi_snapshot(st.session_state.get("processing_results", {})),
        }]
    if "_rfb_submitted" not in st.session_state:
        st.session_state["_rfb_submitted"] = []

def _current_version() -> int:
    return st.session_state.get("_proposal_version_num", 1)

def _bump_version(feedback_summary: str, feedback_ids: list):
    _ensure_rfb_state()
    prev_v = st.session_state["_proposal_version_num"]
    next_v = prev_v + 1
    results_now = _copy.deepcopy(st.session_state.get("processing_results", {}))
    kpi_now     = _get_kpi_snapshot(results_now)
    st.session_state["_version_snapshots"][next_v] = results_now
    if 1 not in st.session_state["_version_snapshots"]:
        pre = _copy.deepcopy(st.session_state.get("results_before_regen", results_now))
        st.session_state["_version_snapshots"][1] = pre
        if st.session_state["_version_meta"] and "kpi" not in st.session_state["_version_meta"][0]:
            st.session_state["_version_meta"][0]["kpi"] = _get_kpi_snapshot(pre)
    st.session_state["_version_meta"].append({
        "num": next_v, "label": f"Revision {prev_v}",
        "ts": datetime.now().strftime("%H:%M"),
        "feedback_summary": feedback_summary, "feedback_ids": list(feedback_ids),
        "kpi": kpi_now,
    })
    st.session_state["_proposal_version_num"] = next_v
    run_id = st.session_state.get("_last_run_id", 0)
    if run_id:
        save_version_snapshot(
            run_id=run_id, version_num=next_v, label=f"Revision {prev_v}",
            feedback_summary=feedback_summary, feedback_ids=feedback_ids,
            kpi_snapshot=kpi_now, results=results_now,
        )

def _apply_pending_post_rerun():
    # Version bump is intentionally NOT processed here —
    # it must fire AFTER the pipeline runs so the snapshot captures the new state.
    # It is consumed inside _render_rfb_inner after run_pipeline_with_feedback().
    if st.session_state.get("_rfb_pending_status"):
        fb_id, status, ai_sum = st.session_state.pop("_rfb_pending_status")
        update_feedback_status(fb_id, status, ai_sum)
        for item in st.session_state.get("_rfb_submitted", []):
            if item.get("id") == fb_id:
                item["status"] = status; item["ai_summary"] = ai_sum; break


# ═══════════════════════════════════════════════════════════════════════
#  IMPACT PREVIEW
# ═══════════════════════════════════════════════════════════════════════

def _impact_sections(section_key: str, also_sections: list) -> tuple:
    """Return (direct_keys, cascade_keys) that will be recalibrated."""
    direct  = [section_key] + [s for s in also_sections if s != section_key]
    cascade = []
    seen    = set(direct)
    for sec in direct:
        for ds in _DOWNSTREAM.get(sec, []):
            if ds not in seen:
                cascade.append(ds); seen.add(ds)
    return direct, cascade

def _impact_preview_html(section_key: str, also_sections: list) -> str:
    direct, cascade = _impact_sections(section_key, also_sections)
    all_secs = direct + cascade
    total    = len(all_secs)

    def pill(sk, is_direct):
        lbl = _SEC_LABEL.get(sk, sk.title())
        clr = _SEC_COLOR.get(sk, "#475569")
        bg  = f"{clr}22" if is_direct else f"{clr}0d"
        brd = f"{clr}55" if is_direct else f"{clr}22"
        fw  = "700" if is_direct else "400"
        return (
            f'<span style="display:inline-flex;align-items:center;gap:4px;'
            f'background:{bg};border:1px solid {brd};border-radius:7px;'
            f'padding:4px 10px;font-size:.72rem;font-weight:{fw};color:{clr};'
            f'white-space:nowrap">{lbl}</span>'
        )

    direct_pills  = " ".join(pill(s, True)  for s in direct)
    cascade_pills = " ".join(pill(s, False) for s in cascade) if cascade else ""
    est_time = f"~{15 + total * 8}–{20 + total * 12} seconds"

    return (
        f'<div style="background:linear-gradient(135deg,rgba(123,97,255,.07),rgba(0,180,216,.04));'
        f'border:1px solid rgba(123,97,255,.2);border-radius:12px;padding:14px 16px;margin-top:10px">'
        f'<div style="font-size:.72rem;font-weight:700;color:#a78bfa;margin-bottom:10px">'
        f'📊 Recalibration Impact — {total} section{"s" if total!=1 else ""} will update</div>'

        f'<div style="font-size:.65rem;color:#475569;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Direct</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px">{direct_pills}</div>'

        + (f'<div style="font-size:.65rem;color:#475569;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">Cascade (auto)</div>'
           f'<div style="display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px">{cascade_pills}</div>'
           if cascade_pills else "")

        + f'<div style="font-size:.65rem;color:#334155;margin-top:4px">⏱️ Estimated time: {est_time}</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════════════
#  LOADING SCREEN
# ═══════════════════════════════════════════════════════════════════════

def _render_loading_screen(section_label: str, n_sections: int,
                            description: str, direct: list, cascade: list):
    all_secs = direct + cascade

    def step(sk, is_direct, idx):
        lbl = _SEC_LABEL.get(sk, sk.title())
        clr = _SEC_COLOR.get(sk, "#475569")
        delay = idx * 0.15
        dot_bg = clr if is_direct else f"{clr}66"
        return (
            f'<div style="display:flex;align-items:center;gap:8px;padding:7px 11px;'
            f'background:{clr}0d;border:1px solid {clr}{"33" if is_direct else "18"};border-radius:8px;">'
            f'<div style="width:7px;height:7px;border-radius:50%;background:{dot_bg};flex-shrink:0;'
            f'animation:pulse 1.4s {delay:.2f}s ease-in-out infinite"></div>'
            f'<span style="font-size:.72rem;color:{"#94a3b8" if is_direct else "#475569"}">{lbl}</span>'
            + ('<span style="font-size:.58rem;color:#334155;margin-left:auto">auto</span>' if not is_direct else '')
            + f'</div>'
        )

    steps_html = ""
    for i, sk in enumerate(all_secs[:8]):
        steps_html += step(sk, sk in direct, i)

    est_time = f"~{15 + n_sections * 8}–{20 + n_sections * 12} sec"

    st.markdown(
        f"""
        <style>
        @keyframes pulse{{0%,100%{{opacity:.25;transform:scale(.75)}}50%{{opacity:1;transform:scale(1.2)}}}}
        @keyframes spin{{to{{transform:rotate(360deg)}}}}
        @keyframes shimmer{{0%{{background-position:200% 0}}100%{{background-position:-200% 0}}}}
        @keyframes fadeUp{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:translateY(0)}}}}
        </style>

        <div style="padding:32px 16px 20px;display:flex;flex-direction:column;
                    align-items:center;gap:20px;animation:fadeUp .35s ease;">

          <!-- dual-ring spinner -->
          <div style="position:relative;width:68px;height:68px;">
            <div style="position:absolute;inset:0;border-radius:50%;border:3px solid rgba(0,212,170,.1)"></div>
            <div style="position:absolute;inset:0;border-radius:50%;border:3px solid transparent;
                        border-top-color:#00d4aa;animation:spin .85s linear infinite"></div>
            <div style="position:absolute;inset:8px;border-radius:50%;border:3px solid transparent;
                        border-top-color:#7b61ff;animation:spin 1.3s linear infinite reverse"></div>
            <div style="position:absolute;inset:0;display:flex;align-items:center;
                        justify-content:center;font-size:1.3rem">🔄</div>
          </div>

          <!-- title -->
          <div style="text-align:center;max-width:460px">
            <div style="font-size:1.05rem;font-weight:800;color:#e2e8f0;margin-bottom:6px">
              AI Recalibrating Full Proposal…
            </div>
            <div style="font-size:.8rem;color:#64748b;line-height:1.6">
              Feedback on <strong style="color:#00d4aa">{section_label}</strong> is cascading to
              <strong style="color:#a78bfa">{n_sections} section{"s" if n_sections!=1 else ""}</strong>.
              All estimates, costs, risks, architecture and diagrams will be updated for consistency.
            </div>
            <div style="font-size:.7rem;color:#334155;margin-top:6px;font-style:italic">
              "{description[:90]}{"…" if len(description)>90 else ""}"
            </div>
          </div>

          <!-- section grid -->
          <div style="width:100%;max-width:460px;display:grid;
                      grid-template-columns:repeat(2,1fr);gap:7px">
            {steps_html}
          </div>

          <!-- shimmer bars (replaced by real progress below) -->
          <div style="width:100%;max-width:460px">
            <div style="font-size:.62rem;color:#334155;margin-bottom:5px;text-transform:uppercase;letter-spacing:.5px">
              Live Progress ↓
            </div>
            {"".join(
                f'<div style="height:5px;border-radius:3px;margin-bottom:6px;'
                f'background:linear-gradient(90deg,#0f172a 25%,#1e293b 50%,#0f172a 75%);'
                f'background-size:200% 100%;animation:shimmer 1.5s {i*0.25:.2f}s infinite"></div>'
                for i in range(2)
            )}
          </div>

          <div style="font-size:.68rem;color:#1e293b">
            {est_time} — please keep this tab open
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════
#  ACCEPT / REJECT PANEL
# ═══════════════════════════════════════════════════════════════════════

def _render_accept_reject_panel():
    before   = st.session_state.get("results_before_regen")
    sections = st.session_state.get("regen_sections", [])
    if not before or not sections: return

    r_now = st.session_state.get("processing_results", {})
    # Use the KPI values that were DISPLAYED to the user (saved at last parent render)
    # so "before" always matches what was on screen — not a re-derived value that may drift.
    _saved_kpi = st.session_state.get("_last_rendered_kpi") or {}
    kpi_b = _get_kpi_snapshot(before)
    if _saved_kpi:
        kpi_b["hours"] = _saved_kpi.get("hours", kpi_b["hours"])
        kpi_b["cost"]  = _saved_kpi.get("cost",  kpi_b["cost"])
        kpi_b["risk"]  = _saved_kpi.get("risk",  kpi_b["risk"])
        kpi_b["reqs"]  = _saved_kpi.get("reqs",  kpi_b["reqs"])
    kpi_a = _get_kpi_snapshot(r_now)
    delta = _kpi_delta(kpi_b, kpi_a)

    def kpi_cell(label, b_val, a_val, unit, diff, pct, reverse_good=False):
        changed = diff != 0
        arrow   = _delta_badge(diff, pct, unit, reverse_good) if changed else ""
        return (
            f'<div style="background:#0a0f1a;border:1px solid {"rgba(0,212,170,.2)" if changed else "#1e293b"};'
            f'border-radius:10px;padding:12px 14px;text-align:center">'
            f'<div style="font-size:.62rem;color:#475569;text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px">{label}</div>'
            f'<div style="display:flex;align-items:baseline;justify-content:center;gap:8px;flex-wrap:wrap">'
            f'<span style="font-size:.9rem;color:#475569;text-decoration:{"line-through" if changed else "none"}">{b_val}</span>'
            + (f'<span style="font-size:.85rem;font-weight:800;color:#00d4aa">{a_val}</span>' if changed else "")
            + f'</div>'
            + (f'<div style="margin-top:4px">{arrow}</div>' if changed else
               '<div style="font-size:.65rem;color:#334155;margin-top:4px">no change</div>')
            + f'</div>'
        )

    kpi_grid = "".join([
        kpi_cell("Hours", f"{kpi_b['hours']:,}h", f"{kpi_a['hours']:,}h", "h",
                 delta['hours']['diff'], delta['hours']['pct']),
        kpi_cell("Infra Cost", f"${kpi_b['cost']:,}", f"${kpi_a['cost']:,}", "",
                 delta['cost']['diff'], delta['cost']['pct']),
        kpi_cell("Risk Score", f"{kpi_b['risk']}/10", f"{kpi_a['risk']}/10", "",
                 delta['risk']['diff'], delta['risk']['pct'], reverse_good=True),
        kpi_cell("Requirements", str(kpi_b['reqs']), str(kpi_a['reqs']), "",
                 delta['reqs']['diff'], delta['reqs']['pct']),
    ])

    n = len(sections)
    st.markdown(
        f'<div style="background:linear-gradient(135deg,rgba(0,212,170,.08),rgba(0,180,216,.05));'
        f'border:1.5px solid rgba(0,212,170,.3);border-radius:14px;padding:18px 20px;margin-bottom:18px">'

        f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:14px">'
        f'<span style="font-size:1.4rem">✅</span>'
        f'<div><div style="font-size:1rem;font-weight:800;color:#00d4aa">Recalibration Complete</div>'
        f'<div style="font-size:.75rem;color:#64748b">'
        f'{n} section{"s" if n!=1 else ""} updated — review changes and accept or discard</div></div>'
        f'</div>'

        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:14px">'
        f'{kpi_grid}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Before/after detail table
    any_shown = False
    for sec_key in sections:
        rkey   = _RESULT_KEY.get(sec_key, sec_key)
        fields = _KEY_FIELDS.get(rkey, [])
        if not fields: continue
        old_d  = safe_dict(before.get(rkey, {}))
        new_d  = safe_dict(r_now.get(rkey, {}))
        sec_lbl = _SEC_LABEL.get(sec_key, sec_key.title())
        sec_clr = _SEC_COLOR.get(sec_key, "#94a3b8")
        any_shown = True
        rows_html = ""
        for fkey, flabel in fields:
            v_old = old_d.get(fkey); v_new = new_d.get(fkey)
            d_old = len(v_old) if isinstance(v_old, list) else v_old
            d_new = len(v_new) if isinstance(v_new, list) else v_new
            changed = d_new != d_old
            nc  = "#00d4aa" if changed else "#475569"
            rows_html += (
                f'<tr><td style="padding:5px 10px;font-size:.7rem;color:#475569;width:30%">{flabel}</td>'
                f'<td style="padding:5px 10px;font-size:.7rem;color:#334155'
                f'{";text-decoration:line-through" if changed else ""}">'
                f'<code style="background:#0f172a;padding:1px 5px;border-radius:3px">{d_old}</code></td>'
                f'<td style="padding:5px 10px;font-size:.7rem;color:{nc};font-weight:{"700" if changed else "400"}">'
                f'<code style="background:{"rgba(0,212,170,.07)" if changed else "#0f172a"};'
                f'border:{"1px solid #00d4aa22" if changed else "none"};padding:1px 5px;border-radius:3px">'
                f'{d_new}</code>{"  ◀" if changed else ""}</td></tr>'
            )
        st.markdown(
            f'<div style="font-size:.75rem;font-weight:700;color:{sec_clr};'
            f'border-left:3px solid {sec_clr};padding-left:8px;margin:10px 0 7px">{sec_lbl}</div>'
            f'<table style="width:100%;border-collapse:collapse;background:#080d18;'
            f'border:1px solid #1e293b;border-radius:8px;overflow:hidden;margin-bottom:10px">'
            f'<thead><tr>'
            f'<th style="padding:5px 10px;font-size:.62rem;color:#334155;text-align:left;background:#0f172a;'
            f'border-bottom:1px solid #1e293b;text-transform:uppercase;letter-spacing:.5px">Field</th>'
            f'<th style="padding:5px 10px;font-size:.62rem;color:#334155;text-align:left;background:#0f172a;'
            f'border-bottom:1px solid #1e293b;text-transform:uppercase;letter-spacing:.5px">Before</th>'
            f'<th style="padding:5px 10px;font-size:.62rem;color:#00d4aa;text-align:left;background:#0f172a;'
            f'border-bottom:1px solid #1e293b;text-transform:uppercase;letter-spacing:.5px">After ●</th>'
            f'</tr></thead><tbody>{rows_html}</tbody></table>',
            unsafe_allow_html=True,
        )

    if not any_shown:
        st.info("Proposal / Diagrams regenerated — open those tabs to review the new content.")

    st.markdown("")
    ac1, ac2 = st.columns(2)
    with ac1:
        if st.button("✅  Accept & Keep New Version", type="primary",
                     width="stretch", key="rfb_accept_inline"):
            st.session_state["results_before_regen"] = None
            st.session_state["regen_sections"]       = []
            st.session_state.pop("_last_rendered_kpi", None)
            st.toast(f"✅ Changes accepted — proposal is now at v{_current_version()}!", icon="✅")
            st.rerun()  # full rerun so ALL tabs re-render with the updated results
    with ac2:
        if st.button("↩️  Discard — Restore Previous", width="stretch",
                     key="rfb_discard_inline"):
            st.session_state["processing_results"]   = before
            st.session_state["results_before_regen"] = None
            st.session_state["regen_sections"]       = []
            if st.session_state.get("_proposal_version_num", 1) > 1:
                st.session_state["_proposal_version_num"] -= 1
                vm = st.session_state.get("_version_meta", [])
                if vm: vm.pop()
            st.toast("↩️ Discarded — proposal restored to previous version.", icon="↩️")
            st.rerun()  # full rerun so ALL tabs restore to previous results
            st.rerun(scope="fragment")
    st.markdown("---")


# ═══════════════════════════════════════════════════════════════════════
#  VERSION HTML COMPONENTS
# ═══════════════════════════════════════════════════════════════════════

def _chip(num, label, ts, is_current, is_latest, kpi=None, prev_kpi=None) -> str:
    if is_current:
        bg, brd, tc, sc = ("linear-gradient(135deg,#00d4aa,#00b4d8)","#00d4aa","#0f172a","#0f172a99")
        shd = "box-shadow:0 0 16px #00d4aa44;"
    elif is_latest:
        bg, brd, tc, sc = ("linear-gradient(135deg,rgba(123,97,255,.3),rgba(167,139,250,.2))","#7b61ff","#a78bfa","#64748b")
        shd = "box-shadow:0 0 8px #7b61ff33;"
    else:
        bg, brd, tc, sc = ("#0a0f1a","#1e293b","#475569","#334155")
        shd = ""

    delta_html = ""
    if kpi and prev_kpi and num > 1:
        h_diff = (kpi.get("hours",0) or 0) - (prev_kpi.get("hours",0) or 0)
        c_diff = (kpi.get("cost",0)  or 0) - (prev_kpi.get("cost",0)  or 0)
        if h_diff or c_diff:
            h_str = f"{'+'if h_diff>=0 else ''}{h_diff}h" if h_diff else ""
            c_str = f"{'+'if c_diff>=0 else ''}${c_diff}" if c_diff else ""
            parts = [s for s in [h_str, c_str] if s]
            delta_html = (
                f'<div style="font-size:.52rem;color:{sc};margin-top:3px;opacity:.8">'
                + " · ".join(parts)
                + '</div>'
            )

    badge = (
        '<span style="font-size:.5rem;background:#00d4aa22;color:#00d4aa;'
        'border-radius:3px;padding:1px 4px;margin-left:3px">LATEST</span>'
        if is_latest and not is_current else ""
    )
    return (
        f'<div style="display:inline-flex;flex-direction:column;align-items:center;'
        f'background:{bg};border:2px solid {brd};border-radius:12px;'
        f'padding:9px 14px;min-width:88px;{shd}">'
        f'<div style="font-size:.8rem;font-weight:800;color:{tc}">v{num}{badge}</div>'
        f'<div style="font-size:.6rem;color:{sc};margin-top:2px">{label}</div>'
        f'<div style="font-size:.56rem;color:{sc};margin-top:1px">{ts}</div>'
        f'{delta_html}</div>'
    )

def _arrow() -> str:
    return '<div style="display:inline-flex;align-items:center;padding:0 5px;color:#1e293b;font-size:.95rem;margin-bottom:4px">──▶</div>'

def _fb_card(fb: dict) -> str:
    sec = fb.get("section","")
    slbl = _SEC_LABEL.get(sec, sec.title())
    sclr = _SEC_COLOR.get(sec, "#94a3b8")
    sm   = _STATUS_META.get(fb.get("status","pending"), _STATUS_META["pending"])
    pm   = _PRIORITY_META.get(fb.get("priority","Medium"), _PRIORITY_META["Medium"])
    desc = (fb.get("description","") or "")
    clip = desc[:95] + ("…" if len(desc)>95 else "")
    ai_s = fb.get("ai_summary","") or ""
    ai_b = (
        f'<div style="margin-top:6px;padding:5px 9px;background:rgba(0,212,170,.04);'
        f'border:1px solid rgba(0,212,170,.12);border-radius:5px">'
        f'<span style="font-size:.58rem;color:#00d4aa;font-weight:700">AI · </span>'
        f'<span style="font-size:.68rem;color:#475569">{ai_s[:100]}{"…" if len(ai_s)>100 else ""}</span></div>'
        if ai_s else ""
    )
    return (
        f'<div style="background:#080d18;border:1px solid #1e293b;border-left:3px solid {sclr};'
        f'border-radius:9px;padding:10px 12px;margin-bottom:7px">'
        f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:4px;margin-bottom:4px">'
        f'<span style="font-size:.66rem;font-weight:700;color:{sclr};background:{sclr}1a;'
        f'border:1px solid {sclr}2f;border-radius:6px;padding:2px 7px">{slbl}</span>'
        f'<span style="font-size:.61rem;color:{sm["color"]};background:{sm["bg"]};'
        f'border:1px solid {sm["color"]}2f;border-radius:6px;padding:2px 6px">{sm["icon"]} {sm["label"]}</span>'
        f'<span style="font-size:.59rem;color:{pm["color"]};background:{pm["bg"]};'
        f'border:1px solid {pm["color"]}2f;border-radius:6px;padding:2px 6px">{fb.get("priority","Medium")}</span>'
        f'<span style="font-size:.57rem;color:#334155;margin-left:auto">v{fb.get("version_num",1)} · {(fb.get("submitted_at","") or "")[:10]}</span>'
        f'</div>'
        f'<div style="font-size:.67rem;color:#475569;margin-bottom:3px">{fb.get("feedback_type","")}</div>'
        f'<div style="font-size:.76rem;color:#cbd5e1;line-height:1.5">{clip}</div>'
        f'{ai_b}'
        f'<div style="font-size:.57rem;color:#1e293b;margin-top:5px">by {fb.get("submitted_by","") or "Anonymous"}</div>'
        f'</div>'
    )


# ═══════════════════════════════════════════════════════════════════════
#  SUBMIT QUEUE
# ═══════════════════════════════════════════════════════════════════════

def _queue_submit(run_id, section, fb_type, priority, description,
                  submitted_by, also_sections):
    _ensure_rfb_state()
    fb_id = save_feedback(
        run_id=run_id, version_num=_current_version(),
        submitted_by=submitted_by or "Anonymous",
        section=section, feedback_type=fb_type,
        priority=priority, description=description)

    sec_label        = _SEC_LABEL.get(section, section.title())
    feedback_summary = f"{fb_type} — {sec_label}"
    direct, cascade  = _impact_sections(section, also_sections)
    n_total          = len(direct) + len(cascade)

    st.session_state["_rfb_submitted"].insert(0, {
        "id": fb_id, "run_id": run_id, "version_num": _current_version(),
        "submitted_by": submitted_by or "Anonymous",
        "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "section": section, "feedback_type": fb_type,
        "priority": priority, "description": description,
        "status": "processing", "ai_summary": "",
    })

    st.session_state["_rfb_pending_version_bump"] = {
        "feedback_summary": feedback_summary, "feedback_ids": [fb_id],
    }
    st.session_state["_rfb_pending_status"] = (
        fb_id, "applied",
        f"Recalibrated {n_total} section(s) based on: {description[:80]}",
    )

    feedback_items: dict = {section: description}
    for sec in (also_sections or []):
        if sec != section:
            feedback_items[sec] = f"[context] {section} feedback: {description[:80]}"

    st.session_state["_rfb_is_processing"] = True
    st.session_state["_rfb_pending_feedback"] = {
        "feedback_items": feedback_items,
        "section_label":  sec_label,
        "n_sections":     n_total,
        "description":    description,
        "direct":         direct,
        "cascade":        cascade,
    }
    update_feedback_status(fb_id, "processing")


# ═══════════════════════════════════════════════════════════════════════
#  MAIN RENDER
# ═══════════════════════════════════════════════════════════════════════

@st.fragment
def render_review_feedback_tab(r: dict, se: dict, te: dict, ce: dict,
                                ri: dict, ar: dict, ai_client=None):
    try:
        _render_rfb_inner(r, se, te, ce, ri, ar, ai_client)
    except Exception as _exc:
        import traceback
        st.error(f"Review & Feedback error — {type(_exc).__name__}: {_exc}")
        with st.expander("Debug"):
            st.code(traceback.format_exc())


def _render_rfb_inner(r, se, te, ce, ri, ar, ai_client=None):
    _apply_pending_post_rerun()
    _ensure_rfb_state()

    # ── PROCESSING STATE ─────────────────────────────────────────────────────
    # Uses st.status() which appears INSTANTLY when its with-block is entered —
    # no multi-phase rerun needed.  The status widget transitions to "complete"
    # once the pipeline finishes, then we rerun to show the accept/reject panel.

    if st.session_state.get("_rfb_is_processing"):
        pending = st.session_state.pop("_rfb_pending_feedback", {})
        st.session_state.pop("_rfb_is_processing", None)
        if not pending:
            st.rerun(scope="fragment"); return

        section_label = pending.get("section_label", "section")
        n_sections    = pending.get("n_sections", 1)
        description   = pending.get("description", "")
        direct        = pending.get("direct", [])
        cascade       = pending.get("cascade", [])
        all_secs      = direct + cascade

        # Visual header card
        _render_loading_screen(section_label, n_sections, description, direct, cascade)

        # st.status() is visible IMMEDIATELY and shows live updates while Python runs
        with st.status(
            f"🔄  Recalibrating {n_sections} section{'s' if n_sections != 1 else ''}…",
            expanded=True,
        ) as _sw:
            _sw.write(
                f"Applying **{section_label}** feedback and cascading to "
                + ", ".join(
                    f"**{_SEC_LABEL.get(s, s.title())}**" for s in all_secs[:6]
                )
                + ("…" if len(all_secs) > 6 else "")
            )
            from .pipeline import run_pipeline_with_feedback
            run_pipeline_with_feedback(pending.get("feedback_items", {}))
            # Version bump here — AFTER pipeline — so snapshot captures new processing_results
            _vbump = st.session_state.pop("_rfb_pending_version_bump", None)
            if _vbump:
                _bump_version(_vbump.get("feedback_summary", ""), _vbump.get("feedback_ids", []))
            _sw.update(
                label=f"✅  {n_sections} section{'s' if n_sections != 1 else ''} recalibrated — review changes below",
                state="complete",
                expanded=False,
            )

        # Show success toast using the message stored by run_pipeline_with_feedback.
        _toast_msg = st.session_state.pop("_rfb_pipeline_toast", None)
        if _toast_msg:
            st.toast(_toast_msg, icon="✅")

        # scope="fragment" keeps the rerun scoped to this fragment only —
        # no full-page gray overlay.
        st.rerun(scope="fragment")
        return

    run_id      = st.session_state.get("_last_run_id", 0)
    current_ver = _current_version()
    ver_meta    = st.session_state.get("_version_meta", [])
    snapshots   = st.session_state.get("_version_snapshots", {})
    has_review  = bool(
        st.session_state.get("results_before_regen") and
        st.session_state.get("regen_sections")
    )

    # ── HEADER ────────────────────────────────────────────────────────────────
    n_fb = max(
        len(st.session_state.get("_rfb_submitted",[])),
        len(get_feedback_for_run(run_id)) if run_id else 0,
    )
    fb_badge = (
        f'<span style="font-size:.67rem;background:rgba(0,212,170,.09);color:#00d4aa;'
        f'border:1px solid rgba(0,212,170,.2);border-radius:6px;padding:2px 8px;margin-left:7px">'
        f'{n_fb} item{"s" if n_fb!=1 else ""}</span>'
        if n_fb else ""
    )
    action_badge = (
        '<span style="font-size:.67rem;background:rgba(255,209,102,.1);color:#ffd166;'
        'border:1px solid rgba(255,209,102,.22);border-radius:6px;padding:2px 8px;margin-left:5px;'
        'animation:blink 2s ease-in-out infinite">⚡ Action Required</span>'
        if has_review else ""
    )
    st.markdown(
        f'<style>@keyframes blink{{0%,100%{{opacity:.5}}50%{{opacity:1}}}}</style>'
        f'<div style="background:linear-gradient(135deg,rgba(123,97,255,.07),rgba(0,180,216,.04)),'
        f'rgba(10,15,26,.6);border:1px solid rgba(123,97,255,.16);border-radius:16px;'
        f'padding:16px 20px;margin-bottom:16px">'
        f'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin-bottom:5px">'
        f'<span style="font-size:1.05rem;font-weight:800;color:#e2e8f0">🔄 Review &amp; Feedback</span>'
        f'{fb_badge}{action_badge}</div>'
        f'<div style="font-size:.77rem;color:#475569">Submit feedback on any section — the AI recalibrates '
        f'everything that depends on it and saves a new version with a full audit trail.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── ACCEPT/REJECT (after recalibration) ──────────────────────────────────
    if has_review:
        _render_accept_reject_panel()

    # ── VERSION TIMELINE ─────────────────────────────────────────────────────
    if ver_meta:
        chips = ""
        for i, vm in enumerate(ver_meta):
            prev_kpi = ver_meta[i-1].get("kpi") if i > 0 else None
            chips += _chip(vm["num"], vm["label"], vm.get("ts",""),
                           vm["num"]==current_ver, i==len(ver_meta)-1,
                           vm.get("kpi"), prev_kpi)
            if i < len(ver_meta)-1:
                chips += _arrow()
        st.markdown(
            f'<div style="font-size:.6rem;color:#334155;text-transform:uppercase;'
            f'letter-spacing:.6px;margin-bottom:7px">Version Timeline</div>'
            f'<div style="display:flex;align-items:flex-start;flex-wrap:wrap;gap:2px;'
            f'padding:12px 14px;background:#05080f;border:1px solid #1e293b;border-radius:12px;'
            f'margin-bottom:16px">{chips}</div>',
            unsafe_allow_html=True,
        )

    # ── COMPARE ──────────────────────────────────────────────────────────────
    if len(ver_meta) >= 2 and len(snapshots) >= 2:
        with st.expander("🔍 Compare Any Two Versions", expanded=False):
            ver_nums = [vm["num"] for vm in ver_meta]
            cc1, cc2 = st.columns(2)
            with cc1:
                sel_a = st.selectbox("Version A", ver_nums, index=0, key="rfb_cmp_a",
                    format_func=lambda n: f"v{n} — {next((v['label'] for v in ver_meta if v['num']==n),'')}")
            with cc2:
                sel_b = st.selectbox("Version B", ver_nums, index=len(ver_nums)-1, key="rfb_cmp_b",
                    format_func=lambda n: f"v{n} — {next((v['label'] for v in ver_meta if v['num']==n),'')}")
            snap_a, snap_b = snapshots.get(sel_a,{}), snapshots.get(sel_b,{})
            if snap_a and snap_b:
                import pandas as _pd
                k_a, k_b = _get_kpi_snapshot(snap_a), _get_kpi_snapshot(snap_b)
                d = _kpi_delta(k_a, k_b)
                rows = []
                for lbl, ka_val, kb_val, unit, diff, pct, rev in [
                    ("Total Hours",  f"{k_a['hours']:,}h",  f"{k_b['hours']:,}h",  "h",  d['hours']['diff'],  d['hours']['pct'],  False),
                    ("Monthly Cost", f"${k_a['cost']:,}",   f"${k_b['cost']:,}",   "",   d['cost']['diff'],   d['cost']['pct'],   False),
                    ("Risk Score",   f"{k_a['risk']}/10",   f"{k_b['risk']}/10",   "",   d['risk']['diff'],   d['risk']['pct'],   True),
                    ("Requirements", str(k_a['reqs']),       str(k_b['reqs']),      "",   d['reqs']['diff'],   d['reqs']['pct'],   False),
                    ("Complexity",   str(k_a['complexity']), str(k_b['complexity']), "",  d['complexity']['diff'], d['complexity']['pct'], False),
                ]:
                    changed = diff != 0
                    rows.append({
                        "Metric": lbl,
                        f"v{sel_a}": ka_val, f"v{sel_b}": kb_val,
                        "Delta": (f"{'+'if diff>=0 else ''}{diff:,}{unit} ({'+' if pct>=0 else ''}{pct:.0f}%)" if changed else "—"),
                        "Status": "🔴 Changed" if changed else "✅ Same",
                    })
                st.dataframe(_pd.DataFrame(rows), width="stretch", hide_index=True)
            else:
                st.info("Submit feedback to create v2 — then compare here.")

    st.markdown("")
    col_form, col_hist = st.columns([3, 2], gap="large")

    # ── FORM ─────────────────────────────────────────────────────────────────
    with col_form:
        st.markdown(
            '<div style="font-size:.8rem;font-weight:700;color:#cbd5e1;'
            'border-left:3px solid #7b61ff;padding-left:9px;margin-bottom:12px">'
            '📝 Submit Feedback</div>', unsafe_allow_html=True)

        sec_labels = [s[1] for s in _SECTIONS]
        sec_keys   = [s[0] for s in _SECTIONS]
        sel_sec_lbl = st.selectbox("Section", sec_labels, key="rfb_section")
        sel_sec     = sec_keys[sec_labels.index(sel_sec_lbl)]

        t_col, p_col = st.columns(2)
        with t_col:
            fb_type = st.selectbox("Feedback Type", _FEEDBACK_TYPES, key="rfb_type")
        with p_col:
            priority = st.selectbox("Priority", _PRIORITIES, index=1, key="rfb_priority")

        description = st.text_area(
            "Description",
            placeholder=(
                "Be specific — examples:\n"
                "• 'Data migration phase is low — typically 3× for this scope'\n"
                "• 'Client uses Snowflake, not Azure SQL — update cost items'\n"
                "• 'Vendor lock-in risk missing — client is sensitive to this'"
            ),
            height=115, key="rfb_desc",
        )
        submitted_by = st.text_input("Your Name (optional)", placeholder="e.g. Prabhaker G.", key="rfb_by")

        with st.expander("+ Also recalibrate additional sections", expanded=False):
            other_labels = [s[1] for s in _SECTIONS if s[0] != sel_sec]
            also_labels  = st.multiselect("", other_labels, default=[], key="rfb_also",
                                           label_visibility="collapsed")
            also_sections = [sec_keys[sec_labels.index(lbl)] for lbl in also_labels]

        # ── Impact preview (live, computed from dropdown) ─────────────────────
        st.markdown(_impact_preview_html(sel_sec, also_sections), unsafe_allow_html=True)

        st.markdown("")
        can_submit = bool(description.strip())
        direct_c, cascade_c = _impact_sections(sel_sec, also_sections)
        total_c = len(direct_c) + len(cascade_c)

        if st.button(
            f"🚀  Submit & Recalibrate  {total_c} sections  →  v{current_ver + 1}",
            type="primary", width="stretch", key="rfb_submit", disabled=not can_submit,
        ):
            _queue_submit(run_id=run_id, section=sel_sec, fb_type=fb_type,
                          priority=priority, description=description.strip(),
                          submitted_by=submitted_by.strip(), also_sections=also_sections)
            st.rerun(scope="fragment")

        if not can_submit:
            st.caption("Enter a description to enable submission.")

        # ── Quick actions ──────────────────────────────────────────────────────
        st.markdown("---")
        st.markdown('<div style="font-size:.65rem;color:#334155;text-transform:uppercase;'
                    'letter-spacing:.5px;margin-bottom:8px">⚡ One-Click Adjustments</div>',
                    unsafe_allow_html=True)
        qa_cols = st.columns(3)
        for i, (qa_lbl, qa_sec, qa_type, qa_desc) in enumerate(_QUICK_ACTIONS):
            with qa_cols[i % 3]:
                if st.button(qa_lbl, key=f"rfb_quick_{i}", width="stretch"):
                    _queue_submit(run_id=run_id, section=qa_sec, fb_type=qa_type,
                                  priority="Medium", description=qa_desc,
                                  submitted_by=submitted_by.strip() or "Quick Action",
                                  also_sections=[])
                    st.rerun(scope="fragment")

    # ── HISTORY ──────────────────────────────────────────────────────────────
    with col_hist:
        st.markdown(
            '<div style="font-size:.8rem;font-weight:700;color:#cbd5e1;'
            'border-left:3px solid #00d4aa;padding-left:9px;margin-bottom:12px">'
            '📋 Feedback History</div>', unsafe_allow_html=True)

        session_items = st.session_state.get("_rfb_submitted", [])
        db_items      = get_feedback_for_run(run_id) if run_id else []
        seen_ids      = {f["id"] for f in db_items if f.get("id")}
        merged        = list(db_items) + [i for i in session_items if i.get("id") not in seen_ids]
        merged.sort(key=lambda f: f.get("id",0), reverse=True)

        if not merged:
            st.markdown(
                '<div style="background:#05080f;border:1px dashed #1e293b;border-radius:10px;'
                'padding:28px 18px;text-align:center">'
                '<div style="font-size:1.6rem;margin-bottom:8px">💬</div>'
                '<div style="font-size:.78rem;color:#1e293b;font-weight:600">No feedback yet</div>'
                '<div style="font-size:.69rem;color:#0f172a;margin-top:3px">'
                'Submit feedback on the left to begin.</div></div>',
                unsafe_allow_html=True)
        else:
            total_n   = len(merged)
            applied_n = sum(1 for f in merged if f.get("status")=="applied")
            pending_n = sum(1 for f in merged if f.get("status") in ("pending","processing"))
            sc1, sc2, sc3 = st.columns(3)
            for col, val, lbl, clr, bdr in [
                (sc1, total_n,   "Total",   "#e2e8f0", "#1e293b"),
                (sc2, applied_n, "Applied", "#00d4aa", "rgba(0,212,170,.2)"),
                (sc3, pending_n, "Pending", "#ffd166", "rgba(255,209,102,.2)"),
            ]:
                with col:
                    st.markdown(
                        f'<div style="text-align:center;padding:6px 4px;background:#05080f;'
                        f'border:1px solid {bdr};border-radius:8px">'
                        f'<div style="font-size:1.15rem;font-weight:800;color:{clr}">{val}</div>'
                        f'<div style="font-size:.57rem;color:#334155">{lbl}</div></div>',
                        unsafe_allow_html=True)
            st.markdown("")
            f1, f2 = st.columns(2)
            with f1:
                f_status = st.selectbox("", ["All","pending","processing","applied","dismissed"],
                    key="rfb_f_status", label_visibility="collapsed")
            with f2:
                f_sec_lbl = st.selectbox("", ["All"]+[s[1] for s in _SECTIONS],
                    key="rfb_f_sec", label_visibility="collapsed")
            filtered = merged
            if f_status != "All":
                filtered = [f for f in filtered if f.get("status")==f_status]
            if f_sec_lbl != "All":
                fsk = next((s[0] for s in _SECTIONS if s[1]==f_sec_lbl), None)
                if fsk: filtered = [f for f in filtered if f.get("section")==fsk]
            st.markdown("")
            for fb in filtered[:20]:
                st.markdown(_fb_card(fb), unsafe_allow_html=True)
            if len(filtered) > 20:
                st.caption(f"+{len(filtered)-20} more — Admin → 💬 Feedback")

    # ── VERSION CHANGE LOG ────────────────────────────────────────────────────
    if len(ver_meta) > 1:
        with st.expander("📜 Full Version Change Log", expanded=False):
            for vm in reversed(ver_meta):
                vn, vlbl, vts = vm["num"], vm["label"], vm.get("ts","")
                vs, vids      = vm.get("feedback_summary",""), vm.get("feedback_ids",[])
                is_cur        = vn == current_ver
                brd = "#00d4aa" if is_cur else ("#7b61ff" if vn>1 else "#1e293b")
                lc  = "#00d4aa" if is_cur else ("#a78bfa" if vn>1 else "#475569")
                kpi_now  = vm.get("kpi", {})
                kpi_prev = ver_meta[vn-2].get("kpi",{}) if vn>1 and len(ver_meta)>=(vn-1) else {}
                kpi_html = ""
                if kpi_now and kpi_prev and vn > 1:
                    d = _kpi_delta(kpi_prev, kpi_now)
                    parts = []
                    if d['hours']['diff']: parts.append(f"⏱️ {'+' if d['hours']['diff']>=0 else ''}{d['hours']['diff']:,}h")
                    if d['cost']['diff']:  parts.append(f"💰 {'+' if d['cost']['diff']>=0 else ''}${d['cost']['diff']:,}")
                    if d['risk']['diff']:  parts.append(f"⚠️ {'+' if d['risk']['diff']>=0 else ''}{d['risk']['diff']}")
                    if parts:
                        kpi_html = f'<div style="font-size:.62rem;color:#475569;margin-top:4px">' + " · ".join(parts) + "</div>"
                st.markdown(
                    f'<div style="background:#05080f;border:1px solid #1e293b;'
                    f'border-left:3px solid {brd};border-radius:8px;padding:9px 13px;margin-bottom:6px">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center">'
                    f'<span style="font-weight:700;font-size:.8rem;color:{lc}">v{vn} — {vlbl}'
                    + (' <span style="font-size:.57rem;color:#00d4aa;background:#00d4aa1a;'
                       'border-radius:3px;padding:1px 5px">Current</span>' if is_cur else "")
                    + f'</span><span style="font-size:.6rem;color:#334155">{vts}</span></div>'
                    + (f'<div style="font-size:.72rem;color:#64748b;margin-top:3px">{vs}</div>' if vs else "")
                    + (f'<div style="font-size:.6rem;color:#334155;margin-top:2px">{len(vids)} feedback item(s) applied</div>'
                       if vn>1 else '<div style="font-size:.6rem;color:#334155;margin-top:2px">Original AI output</div>')
                    + kpi_html
                    + '</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════
#  VERSION HISTORY TAB  (called from pipeline History tab)
# ═══════════════════════════════════════════════════════════════════════

def render_version_history_tab(r: dict):
    """Rich per-session version history — replaces the basic History tab content."""
    _apply_pending_post_rerun()  # flush any version bump from the Review tab
    _ensure_rfb_state()
    import json as _json
    from datetime import datetime as _dt

    ver_meta    = st.session_state.get("_version_meta", [])
    snapshots   = st.session_state.get("_version_snapshots", {})
    current_ver = _current_version()
    run_id      = st.session_state.get("_last_run_id", 0)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown(
        '<div style="background:linear-gradient(135deg,rgba(123,97,255,.07),rgba(0,180,216,.04));'
        'border:1px solid rgba(123,97,255,.16);border-radius:14px;padding:16px 20px;margin-bottom:18px">'
        '<div style="font-size:1.05rem;font-weight:800;color:#e2e8f0;margin-bottom:5px">'
        '📚 Proposal Version History</div>'
        '<div style="font-size:.77rem;color:#475569">'
        'Every feedback round creates a new version — full audit trail with KPI deltas, '
        'restore to any version, and download any version\'s deliverables.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if not ver_meta or (len(ver_meta) == 1 and not snapshots):
        st.info("No revision history yet. Submit feedback in the 🔄 Review tab to create versions.")
    else:
        # ── Timeline strip ─────────────────────────────────────────────────
        chips = ""
        for i, vm in enumerate(ver_meta):
            prev_kpi = ver_meta[i-1].get("kpi") if i > 0 else None
            chips += _chip(vm["num"], vm["label"], vm.get("ts",""),
                           vm["num"]==current_ver, i==len(ver_meta)-1,
                           vm.get("kpi"), prev_kpi)
            if i < len(ver_meta)-1:
                chips += _arrow()
        st.markdown(
            f'<div style="display:flex;align-items:flex-start;flex-wrap:wrap;gap:2px;'
            f'padding:12px 14px;background:#05080f;border:1px solid #1e293b;border-radius:12px;'
            f'margin-bottom:20px">{chips}</div>',
            unsafe_allow_html=True,
        )

        # ── Version cards ──────────────────────────────────────────────────
        for vm in reversed(ver_meta):
            vn      = vm["num"]
            vlbl    = vm["label"]
            vts     = vm.get("ts", "")
            vsumm   = vm.get("feedback_summary", "")
            vids    = vm.get("feedback_ids", [])
            vkpi    = vm.get("kpi", {})
            is_cur  = vn == current_ver
            prev_kpi = ver_meta[vn-2].get("kpi",{}) if vn>1 and len(ver_meta)>=(vn-1) else {}
            snap    = snapshots.get(vn, {})

            brd_clr = "#00d4aa" if is_cur else ("#7b61ff" if vn>1 else "#1e293b")
            lbl_clr = "#00d4aa" if is_cur else ("#a78bfa" if vn>1 else "#64748b")

            # KPI delta row
            delta_html = ""
            if vkpi and prev_kpi and vn > 1:
                d = _kpi_delta(prev_kpi, vkpi)
                cells = []
                for k, lbl, unit, rev in [
                    ("hours","Hours","h",False), ("cost","Cost","",False),
                    ("risk","Risk","",True), ("reqs","Reqs","",False)
                ]:
                    b_v = vkpi.get(k,0) or 0
                    diff = d[k]['diff']
                    pct  = d[k]['pct']
                    clr  = ("#00d4aa" if (diff>0 and not rev) or (diff<0 and rev)
                            else "#f87171" if diff!=0 else "#475569")
                    sign = "+" if diff > 0 else ""
                    val_str = f"{b_v:,}h" if k=="hours" else (f"${b_v:,}" if k=="cost" else str(b_v))
                    dlt_str = (f" ({sign}{diff:,}{unit})" if diff else "")
                    cells.append(
                        f'<div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;'
                        f'padding:8px 12px;text-align:center">'
                        f'<div style="font-size:.6rem;color:#334155;margin-bottom:3px;'
                        f'text-transform:uppercase;letter-spacing:.4px">{lbl}</div>'
                        f'<div style="font-size:.82rem;font-weight:700;color:#e2e8f0">{val_str}</div>'
                        f'<div style="font-size:.63rem;color:{clr}">{dlt_str or "—"}</div>'
                        f'</div>'
                    )
                delta_html = (
                    '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin:10px 0">'
                    + "".join(cells) + '</div>'
                )
            elif vkpi and vn == 1:
                cells = []
                for k, lbl, unit in [("hours","Hours","h"),("cost","Cost",""),("risk","Risk",""),("reqs","Reqs","")]:
                    b_v = vkpi.get(k,0) or 0
                    val_str = f"{b_v:,}h" if k=="hours" else (f"${b_v:,}" if k=="cost" else str(b_v))
                    cells.append(
                        f'<div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;'
                        f'padding:8px 12px;text-align:center">'
                        f'<div style="font-size:.6rem;color:#334155;margin-bottom:3px;'
                        f'text-transform:uppercase;letter-spacing:.4px">{lbl}</div>'
                        f'<div style="font-size:.82rem;font-weight:700;color:#e2e8f0">{val_str}</div>'
                        f'</div>'
                    )
                delta_html = (
                    '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin:10px 0">'
                    + "".join(cells) + '</div>'
                )

            cur_badge = (
                '<span style="font-size:.57rem;color:#00d4aa;background:#00d4aa1a;'
                'border:1px solid #00d4aa33;border-radius:4px;padding:1px 6px;margin-left:6px">● CURRENT</span>'
                if is_cur else
                '<span style="font-size:.57rem;color:#475569;background:#1e293b;'
                'border-radius:4px;padding:1px 6px;margin-left:6px">v' + str(vn) + '</span>'
            )

            st.markdown(
                f'<div style="background:#080d18;border:1.5px solid {brd_clr}33;'
                f'border-left:4px solid {brd_clr};border-radius:12px;padding:16px 18px;margin-bottom:12px">'
                f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">'
                f'<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap">'
                f'<span style="font-size:.9rem;font-weight:800;color:{lbl_clr}">v{vn} — {vlbl}</span>'
                f'{cur_badge}'
                f'</div>'
                f'<span style="font-size:.65rem;color:#334155">{vts}</span>'
                f'</div>'
                + (f'<div style="font-size:.75rem;color:#64748b;margin-bottom:6px">'
                   f'💬 {vsumm}</div>' if vsumm else
                   '<div style="font-size:.72rem;color:#334155;margin-bottom:6px">Original AI-generated proposal</div>')
                + delta_html
                + (f'<div style="font-size:.62rem;color:#334155">{len(vids)} feedback item(s) applied</div>' if vids else "")
                + f'</div>',
                unsafe_allow_html=True,
            )

            # Buttons row under each version card
            btn_cols = st.columns([2, 2, 1])
            with btn_cols[0]:
                if snap:
                    st.download_button(
                        f"📥 Download v{vn} (JSON)",
                        data=_json.dumps(snap, indent=2, default=str),
                        file_name=f"ECI_Proposal_v{vn}_{_dt.now().strftime('%Y%m%d')}.json",
                        mime="application/json",
                        key=f"dl_ver_{vn}",
                        width="stretch",
                    )
            with btn_cols[1]:
                if not is_cur and snap:
                    if st.button(f"↩️ Restore v{vn}", key=f"restore_v{vn}",
                                  width="stretch"):
                        st.session_state["processing_results"]   = snap
                        st.session_state["results_before_regen"] = None
                        st.session_state["regen_sections"]       = []
                        st.session_state["_proposal_version_num"] = vn
                        st.toast(f"🔁 Restored to v{vn} — {vlbl}", icon="🔁")
                        st.rerun(scope="fragment")
                elif is_cur:
                    st.caption("← Current version")
            with btn_cols[2]:
                if snap:
                    if st.button(f"🔍 v{vn}", key=f"inspect_v{vn}", width="stretch",
                                  help=f"Inspect v{vn} details"):
                        st.session_state[f"_inspect_v{vn}"] = not st.session_state.get(f"_inspect_v{vn}", False)

            if st.session_state.get(f"_inspect_v{vn}") and snap:
                with st.expander(f"v{vn} Full Details", expanded=True):
                    kpi = _get_kpi_snapshot(snap)
                    st.json({
                        "version": vn, "label": vlbl, "timestamp": vts,
                        "kpi": kpi, "sections_changed": len(vids),
                    })

    st.markdown("---")

    # ── Historical Pipeline Runs (from DB) ───────────────────────────────────
    st.markdown(
        '<div style="font-size:.82rem;font-weight:700;color:#cbd5e1;'
        'border-left:3px solid #14A0B9;padding-left:9px;margin-bottom:12px">'
        '🗄️ Historical Pipeline Runs</div>', unsafe_allow_html=True)

    from .database import db_load_runs
    import pandas as _pd

    pipeline_versions = st.session_state.get("proposal_versions", [])
    if not pipeline_versions:
        st.info("No pipeline runs saved yet. Process a document to create the first run.")
    else:
        ver_rows = []
        for i, v in enumerate(reversed(pipeline_versions)):
            ver_rows.append({
                "#":       len(pipeline_versions) - i,
                "Time":    v.get("ts", ""),
                "Project": v.get("project_type", ""),
                "Hours":   f"{v.get('total_hours',0):,}",
                "$/mo":    f"${v.get('monthly_cost',0):,}",
                "Risk":    v.get("risk_level",""),
                "Reqs":    v.get("req_count",""),
            })
        st.dataframe(_pd.DataFrame(ver_rows), width="stretch", hide_index=True)

        if len(pipeline_versions) >= 2:
            latest, prev = pipeline_versions[-1], pipeline_versions[-2]
            st.markdown("##### Delta — Latest vs Previous Run")
            delta_rows = []
            for field, label, fmt in [
                ("total_hours",  "Total Hours",  lambda v: f"{v:,} h"),
                ("monthly_cost", "Monthly $/mo", lambda v: f"${v:,}"),
                ("req_count",    "Requirements", str),
                ("risk_score",   "Risk Score",   str),
            ]:
                lv = latest.get(field,0) or 0
                pv = prev.get(field,0)   or 0
                diff_val = lv - pv
                diff_str = (f"{'+'if diff_val>=0 else ''}{fmt(diff_val)}" if callable(fmt) else str(diff_val))
                delta_rows.append({
                    "Metric": label, "Previous": fmt(pv) if callable(fmt) else str(pv),
                    "Latest": fmt(lv) if callable(fmt) else str(lv), "Change": diff_str,
                    "▲": "▲" if diff_val>0 else ("▼" if diff_val<0 else "="),
                })
            st.dataframe(_pd.DataFrame(delta_rows), width="stretch", hide_index=True)

        v_idx = st.selectbox(
            "Download run as JSON",
            range(1, len(pipeline_versions)+1),
            format_func=lambda i: f"Run {i} — {pipeline_versions[i-1].get('ts','')} ({pipeline_versions[i-1].get('project_type','')})",
            key="hist_ver_select",
        )
        st.download_button(
            "📥 Download Run JSON",
            data=json.dumps(pipeline_versions[v_idx-1], indent=2, default=str),
            file_name=f"ECI_Run_{v_idx}_{datetime.now().strftime('%Y%m%d')}.json",
            mime="application/json", key="dl_ver_json",
        )


# ═══════════════════════════════════════════════════════════════════════
#  DELIVERY VERSION SELECTOR
# ═══════════════════════════════════════════════════════════════════════

def get_delivery_version_data(r, se, te, ce, ri, ar) -> tuple:
    """Returns (del_r, del_se, del_te, del_ce, del_ri, del_ar, version_num).
    If a historical version is selected, overrides the main data.
    """
    _apply_pending_post_rerun()  # ensure version bump from Review tab is flushed
    _ensure_rfb_state()
    ver_meta    = st.session_state.get("_version_meta", [])
    snapshots   = st.session_state.get("_version_snapshots", {})
    current_ver = _current_version()

    if len(ver_meta) <= 1:
        return r, se, te, ce, ri, ar, current_ver

    ver_nums = [vm["num"] for vm in ver_meta]
    sel_ver  = st.selectbox(
        "Generate deliverables for:",
        ver_nums,
        index=len(ver_nums)-1,
        format_func=lambda n: (
            f"v{n} — {next((v['label'] for v in ver_meta if v['num']==n), '')} "
            + ("● Current" if n == current_ver else "")
        ),
        key="delivery_ver_sel",
        help="Select any version to download its specific deliverables",
    )

    if sel_ver != current_ver:
        snap = snapshots.get(sel_ver, {})
        if snap:
            kpi = _get_kpi_snapshot(snap)
            st.markdown(
                f'<div style="background:rgba(123,97,255,.08);border:1px solid rgba(123,97,255,.2);'
                f'border-radius:10px;padding:10px 14px;margin:8px 0">'
                f'<span style="font-size:.8rem;font-weight:700;color:#a78bfa">📦 v{sel_ver} Deliverables</span>'
                f'<span style="font-size:.75rem;color:#64748b;margin-left:8px">'
                f'{next((v["label"] for v in ver_meta if v["num"]==sel_ver), "")} · '
                f'{kpi.get("hours",0):,}h · ${kpi.get("cost",0):,}/mo · Risk {kpi.get("risk",0)}/10</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            del_r  = snap
            del_se = safe_dict(snap.get("semantic_analysis", {}))
            del_te = safe_dict(snap.get("time_estimate",     {}))
            del_ce = safe_dict(snap.get("cost_estimate",     {}))
            del_ri = safe_dict(snap.get("risk_assessment",   {}))
            del_ar = safe_dict(snap.get("architecture",      {}))
            return del_r, del_se, del_te, del_ce, del_ri, del_ar, sel_ver

    st.markdown(
        f'<div style="background:rgba(0,212,170,.06);border:1px solid rgba(0,212,170,.18);'
        f'border-radius:10px;padding:8px 14px;margin:8px 0">'
        f'<span style="font-size:.75rem;color:#00d4aa">✅ v{current_ver} (Current) — latest recalibrated version</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
    return r, se, te, ce, ri, ar, current_ver


# ═══════════════════════════════════════════════════════════════════════
#  SLIM BANNER  (above tab list — non-intrusive action prompt)
# ═══════════════════════════════════════════════════════════════════════

def render_pending_review_banner():
    if not (st.session_state.get("results_before_regen") and st.session_state.get("regen_sections")):
        return
    n = len(st.session_state.get("regen_sections", []))
    st.markdown(
        f'<div style="background:linear-gradient(90deg,rgba(0,212,170,.07),rgba(0,180,216,.05));'
        f'border:1px solid #00d4aa2a;border-radius:10px;padding:9px 16px;margin-bottom:10px;'
        f'display:flex;align-items:center;gap:12px">'
        f'<span>✅</span>'
        f'<div style="flex:1;font-size:.8rem;color:#64748b">'
        f'<strong style="color:#00d4aa">Recalibration complete</strong> — '
        f'{n} section{"s" if n!=1 else ""} updated. Open the '
        f'<strong>🔄 Review</strong> tab to accept or discard changes.</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ═══════════════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════════════════

def render_feedback_admin_panel():
    st.markdown(
        '<div style="font-size:.8rem;font-weight:700;color:#cbd5e1;'
        'border-left:3px solid #7b61ff;padding-left:9px;margin-bottom:13px">'
        '🔄 Presales Feedback Tracker</div>', unsafe_allow_html=True)
    try:
        all_fb = get_all_feedback(limit=300)
    except Exception as e:
        st.warning(f"Could not load feedback: {e}"); return
    if not all_fb:
        st.info("No feedback submitted yet."); return

    import pandas as _pd
    total_n   = len(all_fb)
    applied_n = sum(1 for f in all_fb if f.get("status")=="applied")
    pending_n = sum(1 for f in all_fb if f.get("status") in ("pending","processing"))
    crit_n    = sum(1 for f in all_fb if f.get("priority")=="Critical")
    kc = st.columns(4)
    kc[0].metric("Total Feedback",   total_n)
    kc[1].metric("Applied",          applied_n, delta=f"{int(applied_n/total_n*100) if total_n else 0}%")
    kc[2].metric("Pending / Active", pending_n)
    kc[3].metric("Critical",         crit_n)
    st.markdown("")
    fc1, fc2, fc3 = st.columns(3)
    with fc1: fa_s   = st.selectbox("Status",  ["All","pending","processing","applied","dismissed"], key="adm_fb_s")
    with fc2: fa_p   = st.selectbox("Priority",["All","Critical","High","Medium","Low"], key="adm_fb_p")
    with fc3: fa_sec = st.selectbox("Section", ["All"]+[s[1] for s in _SECTIONS], key="adm_fb_sec")
    filtered = all_fb
    if fa_s   != "All": filtered = [f for f in filtered if f.get("status")==fa_s]
    if fa_p   != "All": filtered = [f for f in filtered if f.get("priority")==fa_p]
    if fa_sec != "All":
        sk = next((s[0] for s in _SECTIONS if s[1]==fa_sec), None)
        if sk: filtered = [f for f in filtered if f.get("section")==sk]
    if not filtered:
        st.info("No feedback matches."); return
    rows = []
    for fb in filtered:
        sm = _STATUS_META.get(fb.get("status","pending"), _STATUS_META["pending"])
        rows.append({
            "ID": fb.get("id",""), "Run": f"#{fb.get('run_id',0)}", "v": f"v{fb.get('version_num',1)}",
            "Section":  _SEC_LABEL.get(fb.get("section",""), fb.get("section","")),
            "Type": fb.get("feedback_type",""), "Priority": fb.get("priority",""),
            "Status": f"{sm['icon']} {sm['label']}",
            "By": fb.get("submitted_by","") or "Anon", "Date": (fb.get("submitted_at","") or "")[:10],
            "Preview": (fb.get("description","") or "")[:55]+"…",
            "Project": fb.get("client_name","") or fb.get("project_type","") or "—",
        })
    st.dataframe(_pd.DataFrame(rows), width="stretch", hide_index=True)
    with st.expander("⚙️ Manage", expanded=False):
        sel_id = st.number_input("Feedback ID", min_value=1, step=1,
                                  value=filtered[0].get("id",1) if filtered else 1, key="adm_fb_id")
        a1,a2,a3 = st.columns(3)
        with a1:
            if st.button("✅ Mark Applied",  key="adm_apply",   width="stretch"):
                update_feedback_status(int(sel_id), "applied"); st.rerun()
        with a2:
            if st.button("🚫 Dismiss",       key="adm_dismiss", width="stretch"):
                update_feedback_status(int(sel_id), "dismissed"); st.rerun()
        with a3:
            if st.button("⏳ Reset Pending", key="adm_reset",   width="stretch"):
                update_feedback_status(int(sel_id), "pending"); st.rerun()
    try:
        import plotly.graph_objects as _go
        from collections import Counter as _C
        sc = _C(fb.get("section","other") for fb in all_fb)
        fig = _go.Figure(_go.Bar(
            x=[_SEC_LABEL.get(k,k.title()) for k in sc], y=list(sc.values()),
            marker_color=[_SEC_COLOR.get(k,"#475569") for k in sc],
            text=list(sc.values()), textposition="outside"))
        fig.update_layout(
            title=dict(text="Feedback by Section",font=dict(size=12,color="#e2e8f0")),
            template="plotly_dark",paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            height=250,margin=dict(l=0,r=0,t=36,b=20),showlegend=False,
            xaxis=dict(color="#64748b",tickfont=dict(size=9)),
            yaxis=dict(color="#64748b",showgrid=True,gridcolor="#1e293b"))
        st.plotly_chart(fig, width="stretch")
    except Exception: pass
