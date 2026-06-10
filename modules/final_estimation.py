# ═══════════════════════════════════════════════════════════════════════
#  FINAL ESTIMATION GENERATOR
#  Produces a multi-sheet Excel workbook matching the Charter House
#  estimation format:
#    Summary | Development | DevOps & Cloud | Infra Cost | Version History
#
#  Usage:
#    from modules.final_estimation import generate_final_estimation
#    xlsx_bytes = generate_final_estimation(results, project_name="Acme Corp")
# ═══════════════════════════════════════════════════════════════════════
import io
from datetime import datetime

try:
    from openpyxl import Workbook
    from openpyxl.styles import (
        Font, PatternFill, Alignment, Border, Side
    )
    from openpyxl.utils import get_column_letter
    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False


# ─── Colour constants ────────────────────────────────────────────────────────
C_NAVY      = "1F3864"   # dark navy  — title bar
C_BLUE      = "2E74B5"   # medium blue — section headers
C_COL_HEAD  = "4472C4"   # column header blue
C_PHASE     = "D6DCE4"   # phase row (light blue-grey)
C_SUBTOTAL  = "E2EFDA"   # subtotal row (light green)
C_TOTAL     = "FFE699"   # grand total (amber)
C_WHITE     = "FFFFFF"
C_LGRAY     = "F5F5F5"   # alternating row
C_GRAY      = "D9D9D9"   # border
C_NOTE      = "FFF2CC"   # note / assumption row bg
C_RED_LIGHT = "FCE4D6"   # risk row
C_DONE      = "E2EFDA"   # definition of done
C_PREREQ    = "DEEAF1"   # pre-req row


# ─── Style helpers ───────────────────────────────────────────────────────────
def _font(bold=False, size=10, color="000000", name="Calibri"):
    return Font(bold=bold, size=size, color=color, name=name)

def _fill(hex_color):
    return PatternFill("solid", fgColor=hex_color)

def _border(thin=True):
    s = Side(style="thin" if thin else "medium", color=C_GRAY)
    return Border(left=s, right=s, top=s, bottom=s)

def _align(h="left", v="center", wrap=False):
    return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

def _set(ws, cell_ref, value,
         bold=False, size=10, fc=None, font_color="000000",
         h="left", v="center", wrap=False, border=True,
         num_format=None):
    c = ws[cell_ref]
    c.value = value
    c.font  = _font(bold=bold, size=size, color=font_color)
    if fc:
        c.fill = _fill(fc)
    c.alignment = _align(h=h, v=v, wrap=wrap)
    if border:
        c.border = _border()
    if num_format:
        c.number_format = num_format
    return c

def _header_row(ws, row, cols_vals, fc=C_COL_HEAD, font_color=C_WHITE, size=10):
    """Write a header row with dark background."""
    for col, val in cols_vals:
        c = ws.cell(row=row, column=col, value=val)
        c.font      = _font(bold=True, size=size, color=font_color)
        c.fill      = _fill(fc)
        c.alignment = _align(h="center", v="center", wrap=True)
        c.border    = _border()

def _title_row(ws, cell_ref, text, col_span, fc=C_NAVY, size=12):
    """Merge cells and write a big title."""
    row = int(''.join(filter(str.isdigit, cell_ref)))
    col_start = ''.join(filter(str.isalpha, cell_ref))
    ws.merge_cells(f"{col_start}{row}:{get_column_letter(col_span)}{row}")
    c = ws[cell_ref]
    c.value     = text
    c.font      = _font(bold=True, size=size, color=C_WHITE)
    c.fill      = _fill(fc)
    c.alignment = _align(h="center", v="center")

def _section_label(ws, row, col, text, span_col, fc=C_BLUE):
    ws.merge_cells(f"{get_column_letter(col)}{row}:{get_column_letter(span_col)}{row}")
    c = ws.cell(row=row, column=col, value=text)
    c.font      = _font(bold=True, size=10, color=C_WHITE)
    c.fill      = _fill(fc)
    c.alignment = _align(h="left", v="center")

def _phase_row(ws, row, col_start, col_end, text, sum_col_d=None, sum_col_e=None, sum_col_f=None):
    """Write a phase/section header row with SUM formula placeholders."""
    ws.merge_cells(f"{get_column_letter(col_start)}{row}:{get_column_letter(col_start+1)}{row}")
    c = ws.cell(row=row, column=col_start, value=text)
    c.font      = _font(bold=True, size=10, color="000000")
    c.fill      = _fill(C_PHASE)
    c.alignment = _align(h="left", v="center")
    for col in range(col_start+2, col_end+1):
        ws.cell(row=row, column=col).fill = _fill(C_PHASE)
        ws.cell(row=row, column=col).border = _border()

def _data_row(ws, row, values_by_col, fc=None):
    """Write a data row. values_by_col = {col_num: value}."""
    bg = fc or (C_LGRAY if row % 2 == 0 else C_WHITE)
    for col, val in values_by_col.items():
        c = ws.cell(row=row, column=col, value=val)
        c.fill = _fill(bg)
        c.border = _border()
        c.alignment = _align(v="center", wrap=(col > 6))
        if isinstance(val, (int, float)):
            c.alignment = _align(h="center", v="center")

def _col_widths(ws, widths):
    """widths = list of (col_letter, width)."""
    for col, w in widths:
        ws.column_dimensions[col].width = w


# ═══════════════════════════════════════════════════════════════════════
#  DATA EXTRACTION HELPERS
# ═══════════════════════════════════════════════════════════════════════

def _safe(d, *keys, default=""):
    v = d
    for k in keys:
        if isinstance(v, dict):
            v = v.get(k, default)
        else:
            return default
    return v if v is not None else default

def _int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default

def _float(v, default=0.0):
    try:
        return float(v)
    except Exception:
        return default

def _split_phases(phases):
    """Separate dev phases from devops/cloud phases."""
    DEVOPS_KEYWORDS = {"devops", "cloud", "infrastructure", "deployment",
                       "environment", "setup", "provisioning", "ci/cd", "iac"}
    dev_phases, ops_phases = [], []
    for ph in (phases or []):
        name_lower = ph.get("name", "").lower()
        if any(kw in name_lower for kw in DEVOPS_KEYWORDS):
            ops_phases.append(ph)
        else:
            dev_phases.append(ph)
    return dev_phases, ops_phases

def _ensure_devops_phase(ops_phases, tech_stack):
    """If no devops phases exist, generate a standard one."""
    if ops_phases:
        return ops_phases

    standard = [
        {"name": "Azure Environment Setup", "tasks": [
            {"name": "Resource Group & naming convention", "low_hours": 2,  "high_hours": 3,  "role": "DevOps Engineer", "justification": "Isolated network foundation"},
            {"name": "Private endpoints & Private Link config", "low_hours": 6,  "high_hours": 10, "role": "DevOps Engineer", "justification": "All services off public internet"},
            {"name": "Azure AI / OpenAI service provisioning", "low_hours": 3,  "high_hours": 5,  "role": "Cloud Architect", "justification": "Model deployment & quota"},
            {"name": "Azure AI Search index schema setup",     "low_hours": 3,  "high_hours": 4,  "role": "Cloud Architect", "justification": "Vector search indexes"},
            {"name": "Azure App Service / Functions setup",    "low_hours": 2,  "high_hours": 3,  "role": "DevOps Engineer", "justification": "Backend API hosting"},
            {"name": "Azure Key Vault & Managed Identity RBAC","low_hours": 2,  "high_hours": 4,  "role": "DevOps Engineer", "justification": "No hardcoded secrets"},
            {"name": "Azure Blob Storage containers & lifecycle","low_hours": 1, "high_hours": 2,  "role": "DevOps Engineer", "justification": "Source files & outputs"},
            {"name": "Azure Monitor + Log Analytics workspace", "low_hours": 2,  "high_hours": 3,  "role": "DevOps Engineer", "justification": "Logging & observability"},
            {"name": "Microsoft Entra ID — app registrations", "low_hours": 3,  "high_hours": 4,  "role": "Cloud Architect", "justification": "Service-to-service auth"},
        ]},
        {"name": "Security Baseline & Testing", "tasks": [
            {"name": "NSG rules & Conditional Access policies",  "low_hours": 4,  "high_hours": 6,  "role": "DevOps Engineer", "justification": "Security hardening"},
            {"name": "UAT staging environment deployment",       "low_hours": 2,  "high_hours": 3,  "role": "DevOps Engineer", "justification": "Mirror of production"},
        ]},
    ]
    return standard


def _ensure_infra_services(cost_estimate, project_type):
    """Return normalised azure services list from the pipeline cost_estimate.

    The pipeline stores services under 'azure_costs' with fields:
        service, tier, monthly_cost, description
    Legacy / fallback stores them under 'azure_services' with fields:
        name, monthly_cost, pricing_model, notes
    We normalise both to: name, monthly_cost, pricing_model, notes
    and also include third_party_costs.
    """
    def _normalise(raw_list, name_key="name", pricing_key="pricing_model", notes_key="notes"):
        out = []
        for s in (raw_list or []):
            if not isinstance(s, dict):
                continue
            out.append({
                "name":          s.get(name_key) or s.get("name") or s.get("service") or "",
                "monthly_cost":  _float(s.get("monthly_cost", s.get("cost", 0))),
                "pricing_model": s.get(pricing_key) or s.get("tier") or s.get("pricing_model") or "",
                "notes":         s.get(notes_key) or s.get("description") or s.get("notes") or "",
            })
        return out

    # Try pipeline key first ("azure_costs"), then legacy key ("azure_services")
    azure_raw = cost_estimate.get("azure_costs") or cost_estimate.get("azure_services") or []
    services = _normalise(azure_raw, name_key="service", pricing_key="tier", notes_key="description")

    # Append third-party costs if present
    tp_raw = cost_estimate.get("third_party_costs") or []
    services += _normalise(tp_raw, name_key="name", pricing_key="pricing_model", notes_key="description")

    if services:
        return services

    # Absolute fallback — East US Pay-As-You-Go, April 2026
    # Source: https://prices.azure.com/api/retail/prices
    return [
        {"name": "Azure OpenAI — GPT-4o",              "monthly_cost": 75,  "pricing_model": "Pay-per-token",   "notes": "~15M input + 5M output tokens/mo; $2.50/$10 per 1M tokens"},
        {"name": "Azure AI Search — Standard S1",       "monthly_cost": 245, "pricing_model": "Fixed monthly",   "notes": "$0.336/hr × 730 hrs; 1 replica, 1 partition, East US"},
        {"name": "Azure App Service — P1v3 Linux",      "monthly_cost": 97,  "pricing_model": "Fixed monthly",   "notes": "2 vCPU 8 GB RAM; $0.133/hr × 730 hrs, East US"},
        {"name": "Azure Functions",                     "monthly_cost": 5,   "pricing_model": "Consumption",     "notes": "First 1M executions/mo free; ~500K executions typical"},
        {"name": "Azure Blob Storage — Hot LRS",        "monthly_cost": 9,   "pricing_model": "Pay-per-GB",      "notes": "$0.018/GB/mo; 500 GB estimate, Locally Redundant Storage"},
        {"name": "Azure Key Vault — Standard",          "monthly_cost": 1,   "pricing_model": "Operations-based","notes": "$0.03 per 10K operations; secrets + managed identities"},
        {"name": "Azure Monitor / Log Analytics",       "monthly_cost": 23,  "pricing_model": "Per GB ingested", "notes": "$2.30/GB; 10 GB/mo ingestion, 30-day retention"},
        {"name": "Microsoft Entra ID",                  "monthly_cost": 0,   "pricing_model": "Included M365",   "notes": "Managed Identity — included in Microsoft 365 E3/E5"},
    ]


# ═══════════════════════════════════════════════════════════════════════
#  SHEET BUILDERS
# ═══════════════════════════════════════════════════════════════════════

def _build_task_sheet(wb, sheet_name, title_text, phases, meetings_pct=0.10):
    """
    Build a Development or DevOps sheet.
    Returns (ws, total_hours_cell) e.g. ('Development', 'F52')
    """
    ws = wb.create_sheet(sheet_name)

    # Column widths
    _col_widths(ws, [
        ("A", 5), ("B", 28), ("C", 38), ("D", 12), ("E", 12), ("F", 12), ("G", 42)
    ])
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[3].height = 18

    # Title
    _title_row(ws, "A1", title_text, 7)

    # Column headers row 3
    _header_row(ws, 3, [
        (1, "#"), (2, "Task / Phase"), (3, "Sub-task"),
        (4, "Dev Low (hrs)"), (5, "Dev High (hrs)"), (6, "Avg (hrs)"), (7, "Comments")
    ])

    current_row = 4
    phase_total_rows = []   # list of (d_formula_cell, e_formula_cell, f_formula_cell)
    phase_ranges    = []    # list of (phase_label_row, first_task_row, last_task_row)

    for ph_idx, phase in enumerate(phases):
        phase_name  = phase.get("name", f"Phase {ph_idx+1}")
        tasks       = phase.get("tasks", [])
        if not tasks:
            continue

        phase_row  = current_row
        first_task = current_row + 1
        current_row += 1

        # Phase header with placeholder (will set formula after tasks)
        _phase_row(ws, phase_row, 1, 7, phase_name)
        ws.row_dimensions[phase_row].height = 16

        task_d_rows, task_e_rows = [], []

        for t_idx, task in enumerate(tasks):
            row = current_row
            name     = task.get("name", "")
            low      = _int(task.get("low_hours", task.get("hours", 0)))
            high     = _int(task.get("high_hours", task.get("hours", 0)))
            if high < low:
                high = int(low * 1.35)
            role     = task.get("role", "")
            comment  = task.get("justification", task.get("comment", ""))

            bg = C_WHITE if t_idx % 2 == 0 else C_LGRAY

            ws.cell(row=row, column=1, value=t_idx+1).fill  = _fill(bg)
            ws.cell(row=row, column=1).border = _border()
            ws.cell(row=row, column=1).alignment = _align(h="center")
            ws.cell(row=row, column=2, value=role).fill    = _fill(bg); ws.cell(row=row, column=2).border = _border(); ws.cell(row=row, column=2).alignment = _align(wrap=True)
            ws.cell(row=row, column=3, value=name).fill    = _fill(bg); ws.cell(row=row, column=3).border = _border(); ws.cell(row=row, column=3).alignment = _align(wrap=True)
            ws.cell(row=row, column=4, value=low).fill     = _fill(bg); ws.cell(row=row, column=4).border = _border(); ws.cell(row=row, column=4).alignment = _align(h="center")
            ws.cell(row=row, column=5, value=high).fill    = _fill(bg); ws.cell(row=row, column=5).border = _border(); ws.cell(row=row, column=5).alignment = _align(h="center")
            f_avg = f"=(D{row}+E{row})/2"
            ws.cell(row=row, column=6, value=f_avg).fill   = _fill(bg); ws.cell(row=row, column=6).border = _border(); ws.cell(row=row, column=6).alignment = _align(h="center")
            ws.cell(row=row, column=6).number_format = "0.0"
            ws.cell(row=row, column=7, value=comment).fill = _fill(bg); ws.cell(row=row, column=7).border = _border(); ws.cell(row=row, column=7).alignment = _align(wrap=True, v="top")
            ws.row_dimensions[row].height = 15

            task_d_rows.append(row)
            task_e_rows.append(row)
            current_row += 1

        last_task = current_row - 1

        # Now fill phase row SUM formulas
        d_rng = f"D{first_task}:D{last_task}"
        e_rng = f"E{first_task}:E{last_task}"
        ws.cell(row=phase_row, column=4, value=f"=SUM({d_rng})").font = _font(bold=True); ws.cell(row=phase_row, column=4).fill = _fill(C_PHASE); ws.cell(row=phase_row, column=4).border = _border(); ws.cell(row=phase_row, column=4).alignment = _align(h="center")
        ws.cell(row=phase_row, column=5, value=f"=SUM({e_rng})").font = _font(bold=True); ws.cell(row=phase_row, column=5).fill = _fill(C_PHASE); ws.cell(row=phase_row, column=5).border = _border(); ws.cell(row=phase_row, column=5).alignment = _align(h="center")
        ws.cell(row=phase_row, column=6, value=f"=(D{phase_row}+E{phase_row})/2").font = _font(bold=True); ws.cell(row=phase_row, column=6).fill = _fill(C_PHASE); ws.cell(row=phase_row, column=6).border = _border(); ws.cell(row=phase_row, column=6).alignment = _align(h="center")
        ws.cell(row=phase_row, column=6).number_format = "0.0"

        phase_total_rows.append(phase_row)
        phase_ranges.append((phase_row, first_task, last_task))
        current_row += 1  # gap between phases

    # Meetings & Sync row
    mtg_row = current_row
    ws.merge_cells(f"A{mtg_row}:B{mtg_row}")
    ws.cell(row=mtg_row, column=1, value="Meetings & Sync (10% of dev hours)").font = _font(bold=True)
    ws.cell(row=mtg_row, column=1).fill = _fill(C_NOTE); ws.cell(row=mtg_row, column=1).border = _border()
    ws.cell(row=mtg_row, column=1).alignment = _align()
    ws.cell(row=mtg_row, column=2).fill = _fill(C_NOTE); ws.cell(row=mtg_row, column=2).border = _border()
    ws.cell(row=mtg_row, column=3, value="Standups, client syncs, internal reviews").fill = _fill(C_NOTE); ws.cell(row=mtg_row, column=3).border = _border()
    d_sum = "+".join([f"D{r}" for r in phase_total_rows]) if phase_total_rows else "0"
    e_sum = "+".join([f"E{r}" for r in phase_total_rows]) if phase_total_rows else "0"
    ws.cell(row=mtg_row, column=4, value=f"=({d_sum})*{meetings_pct}").fill = _fill(C_NOTE); ws.cell(row=mtg_row, column=4).border = _border(); ws.cell(row=mtg_row, column=4).alignment = _align(h="center"); ws.cell(row=mtg_row, column=4).font = _font(bold=True)
    ws.cell(row=mtg_row, column=5, value=f"=({e_sum})*{meetings_pct}").fill = _fill(C_NOTE); ws.cell(row=mtg_row, column=5).border = _border(); ws.cell(row=mtg_row, column=5).alignment = _align(h="center"); ws.cell(row=mtg_row, column=5).font = _font(bold=True)
    ws.cell(row=mtg_row, column=6, value=f"=(D{mtg_row}+E{mtg_row})/2").fill = _fill(C_NOTE); ws.cell(row=mtg_row, column=6).border = _border(); ws.cell(row=mtg_row, column=6).alignment = _align(h="center"); ws.cell(row=mtg_row, column=6).font = _font(bold=True)
    ws.cell(row=mtg_row, column=6).number_format = "0.0"
    for col in [7]:
        ws.cell(row=mtg_row, column=col).fill = _fill(C_NOTE); ws.cell(row=mtg_row, column=col).border = _border()
    ws.row_dimensions[mtg_row].height = 15

    # TOTAL row
    total_row = mtg_row + 2
    ws.merge_cells(f"A{total_row}:C{total_row}")
    ws.cell(row=total_row, column=1, value=f"TOTAL {sheet_name.upper()} HOURS").font = _font(bold=True, size=11, color=C_WHITE)
    ws.cell(row=total_row, column=1).fill = _fill(C_NAVY); ws.cell(row=total_row, column=1).border = _border()
    ws.cell(row=total_row, column=1).alignment = _align(h="center", v="center")
    ws.cell(row=total_row, column=2).fill = _fill(C_NAVY); ws.cell(row=total_row, column=2).border = _border()
    ws.cell(row=total_row, column=3).fill = _fill(C_NAVY); ws.cell(row=total_row, column=3).border = _border()

    all_phase_and_mtg_d = "+".join([f"D{r}" for r in phase_total_rows] + [f"D{mtg_row}"]) if phase_total_rows else "0"
    all_phase_and_mtg_e = "+".join([f"E{r}" for r in phase_total_rows] + [f"E{mtg_row}"]) if phase_total_rows else "0"
    ws.cell(row=total_row, column=4, value=f"={all_phase_and_mtg_d}").font = _font(bold=True, size=11, color=C_WHITE)
    ws.cell(row=total_row, column=4).fill = _fill(C_NAVY); ws.cell(row=total_row, column=4).border = _border(); ws.cell(row=total_row, column=4).alignment = _align(h="center")
    ws.cell(row=total_row, column=5, value=f"={all_phase_and_mtg_e}").font = _font(bold=True, size=11, color=C_WHITE)
    ws.cell(row=total_row, column=5).fill = _fill(C_NAVY); ws.cell(row=total_row, column=5).border = _border(); ws.cell(row=total_row, column=5).alignment = _align(h="center")
    ws.cell(row=total_row, column=6, value=f"=(D{total_row}+E{total_row})/2").font = _font(bold=True, size=11, color=C_WHITE)
    ws.cell(row=total_row, column=6).fill = _fill(C_NAVY); ws.cell(row=total_row, column=6).border = _border(); ws.cell(row=total_row, column=6).alignment = _align(h="center")
    ws.cell(row=total_row, column=6).number_format = "0.0"
    ws.cell(row=total_row, column=7).fill = _fill(C_NAVY); ws.cell(row=total_row, column=7).border = _border()
    ws.row_dimensions[total_row].height = 20

    # Freeze pane below headers
    ws.freeze_panes = "A4"

    return ws, total_row   # caller uses F{total_row} for cross-sheet ref


def _build_infra_cost_sheet(wb, project_name, azure_services, region="East US"):
    ws = wb.create_sheet("Infra Cost")

    _col_widths(ws, [("A", 5), ("B", 40), ("C", 14), ("D", 22), ("E", 50)])
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 18

    today = datetime.now().strftime("%B %Y")
    _title_row(ws, "A1",
               f"{project_name.upper()}  |  AZURE INFRASTRUCTURE COST ESTIMATE  "
               f"|  {today}  |  Pay-As-You-Go",
               5, fc=C_NAVY)

    # Row 2: Region + pricing source info
    ws.merge_cells("A2:E2")
    c2 = ws["A2"]
    c2.value = (f"  Region: {region} (United States)  |  Pricing: Azure Pay-As-You-Go (Retail)  "
                f"|  Source: prices.azure.com/api/retail/prices  |  All prices in USD  |  Updated: {today}")
    c2.font      = _font(bold=False, size=9, color="1F3864")
    c2.fill      = _fill("DEEAF1")
    c2.alignment = _align(h="left", v="center")
    c2.border    = _border()
    for col in range(2, 6):
        ws.cell(row=2, column=col).fill   = _fill("DEEAF1")
        ws.cell(row=2, column=col).border = _border()

    # Headers on row 3
    _header_row(ws, 3, [(1,"#"),(2,"Service / Resource"),(3,"$/mo"),(4,"Pricing Model"),(5,"Notes / Assumptions")])

    # Group services
    GROUPS = [
        ("AI Services — Azure OpenAI / AI Foundry", ["openai","foundry","ai service","azure ai","embedding","llm","gpt","claude","gemini"]),
        ("Vector Storage — Azure AI Search",        ["search","vector","index"]),
        ("Compute — App Service & Functions",       ["app service","function","container","kubernetes","compute","web app","api"]),
        ("Database & Storage",                      ["sql","cosmos","blob","storage","redis","database"]),
        ("Security & Identity",                     ["key vault","entra","identity","managed identity","ad","aad"]),
        ("Monitoring & Observability",              ["monitor","log analytics","insights","alert","observability"]),
        ("Integration & Messaging",                 ["service bus","logic app","event hub","teams","copilot studio","integration"]),
    ]

    def _group_for(name):
        name_l = name.lower()
        for grp, kws in GROUPS:
            if any(k in name_l for k in kws):
                return grp
        return "Other Services"

    grouped = {}
    for svc in azure_services:
        g = _group_for(svc.get("name",""))
        grouped.setdefault(g, []).append(svc)

    current_row = 4
    subtotal_rows = []

    sno = 1
    for grp_name, svcs in grouped.items():
        if not svcs:
            continue

        # Group section header
        ws.merge_cells(f"A{current_row}:E{current_row}")
        c = ws.cell(row=current_row, column=1, value=f"  {grp_name}")
        c.font = _font(bold=True, size=10, color=C_WHITE)
        c.fill = _fill(C_BLUE)
        c.alignment = _align()
        c.border = _border()
        for col in range(2, 6):
            ws.cell(row=current_row, column=col).fill = _fill(C_BLUE)
            ws.cell(row=current_row, column=col).border = _border()
        current_row += 1
        svc_start_row = current_row

        for svc in svcs:
            name  = svc.get("name", "")
            cost  = _float(svc.get("monthly_cost", svc.get("cost", 0)))
            model = svc.get("pricing_model", svc.get("model", ""))
            notes = svc.get("notes", svc.get("description", ""))
            bg    = C_WHITE if sno % 2 == 0 else C_LGRAY
            ws.cell(row=current_row, column=1, value=sno).fill = _fill(bg); ws.cell(row=current_row,column=1).border=_border(); ws.cell(row=current_row,column=1).alignment=_align(h="center")
            ws.cell(row=current_row, column=2, value=name).fill = _fill(bg); ws.cell(row=current_row,column=2).border=_border(); ws.cell(row=current_row,column=2).alignment=_align(wrap=True)
            ws.cell(row=current_row, column=3, value=cost).fill = _fill(bg); ws.cell(row=current_row,column=3).border=_border(); ws.cell(row=current_row,column=3).alignment=_align(h="center"); ws.cell(row=current_row,column=3).number_format='"$"#,##0.00'
            ws.cell(row=current_row, column=4, value=model).fill = _fill(bg); ws.cell(row=current_row,column=4).border=_border(); ws.cell(row=current_row,column=4).alignment=_align(wrap=True)
            ws.cell(row=current_row, column=5, value=notes).fill = _fill(bg); ws.cell(row=current_row,column=5).border=_border(); ws.cell(row=current_row,column=5).alignment=_align(wrap=True, v="top")
            ws.row_dimensions[current_row].height = 18
            sno += 1
            current_row += 1

        # Subtotal row
        svc_end_row = current_row - 1
        sub_row = current_row
        ws.merge_cells(f"A{sub_row}:B{sub_row}")
        ws.cell(row=sub_row, column=1, value=f"Subtotal — {grp_name.split('—')[-1].strip()}").font = _font(bold=True, size=9)
        ws.cell(row=sub_row, column=1).fill = _fill(C_SUBTOTAL); ws.cell(row=sub_row,column=1).border=_border()
        ws.cell(row=sub_row, column=2).fill = _fill(C_SUBTOTAL); ws.cell(row=sub_row,column=2).border=_border()
        f_sub = f"=SUM(C{svc_start_row}:C{svc_end_row})"
        ws.cell(row=sub_row, column=3, value=f_sub).fill = _fill(C_SUBTOTAL)
        ws.cell(row=sub_row, column=3).border=_border(); ws.cell(row=sub_row,column=3).alignment=_align(h="center")
        ws.cell(row=sub_row, column=3).number_format = '"$"#,##0.00'
        ws.cell(row=sub_row, column=3).font = _font(bold=True)
        for col in [4,5]:
            ws.cell(row=sub_row, column=col).fill = _fill(C_SUBTOTAL); ws.cell(row=sub_row,column=col).border=_border()
        subtotal_rows.append(sub_row)
        current_row += 2  # gap

    # TOTAL row
    total_row = current_row
    ws.merge_cells(f"A{total_row}:B{total_row}")
    ws.cell(row=total_row, column=1, value="TOTAL ESTIMATED MONTHLY INFRASTRUCTURE COST").font = _font(bold=True, size=11, color=C_WHITE)
    ws.cell(row=total_row, column=1).fill = _fill(C_NAVY); ws.cell(row=total_row,column=1).border=_border(); ws.cell(row=total_row,column=1).alignment=_align(h="center",v="center")
    ws.cell(row=total_row, column=2).fill = _fill(C_NAVY); ws.cell(row=total_row,column=2).border=_border()
    sub_refs = "+".join([f"C{r}" for r in subtotal_rows]) if subtotal_rows else "0"
    ws.cell(row=total_row, column=3, value=f"={sub_refs}").font = _font(bold=True, size=11, color=C_WHITE)
    ws.cell(row=total_row, column=3).fill = _fill(C_NAVY); ws.cell(row=total_row,column=3).border=_border(); ws.cell(row=total_row,column=3).alignment=_align(h="center",v="center")
    ws.cell(row=total_row, column=3).number_format = '"$"#,##0.00'
    ws.cell(row=total_row, column=4, value="POC / Initial Phase — excludes one-time setup costs").font = _font(size=9, color=C_WHITE)
    ws.cell(row=total_row, column=4).fill = _fill(C_NAVY); ws.cell(row=total_row,column=4).border=_border()
    ws.cell(row=total_row, column=5).fill = _fill(C_NAVY); ws.cell(row=total_row,column=5).border=_border()
    ws.row_dimensions[total_row].height = 22

    # Footer disclaimer
    disc_row = total_row + 2
    ws.merge_cells(f"A{disc_row}:E{disc_row}")
    disc = ws.cell(row=disc_row, column=1,
                   value=("  ⚠  Estimates are based on Azure Pay-As-You-Go retail prices for the East US region. "
                          "Actual costs vary with usage volume, reserved instance discounts (up to 36%), "
                          "Azure Hybrid Benefit, and M365 license inclusions. "
                          "Verify latest pricing at: https://azure.microsoft.com/pricing/calculator"))
    disc.font      = _font(bold=False, size=8, color="595959")
    disc.fill      = _fill(C_NOTE)
    disc.alignment = _align(h="left", v="center", wrap=True)
    disc.border    = _border()
    for col in range(2, 6):
        ws.cell(row=disc_row, column=col).fill   = _fill(C_NOTE)
        ws.cell(row=disc_row, column=col).border = _border()
    ws.row_dimensions[disc_row].height = 30

    ws.freeze_panes = "A4"
    return ws, total_row   # caller uses C{total_row}


def _build_summary_sheet(wb, project_name, results,
                         dev_total_row, ops_total_row, infra_total_row):
    # Put Summary first
    ws = wb.worksheets[0]  # already the first blank sheet renamed below
    ws.title = "Summary"

    _col_widths(ws, [
        ("A",  5), ("B", 28), ("C", 12), ("D", 14),
        ("E",  5), ("F", 5),  ("G", 22), ("H", 12), ("I", 12),
        ("J",  3), ("K", 3),  ("L", 5),  ("M", 55),
    ])

    # ── Row 1: Title
    ws.merge_cells("A1:M1")
    ws.row_dimensions[1].height = 30
    ws.row_dimensions[2].height = 8
    _title_row(ws, "A1",
               f"{project_name.upper()}  |  PROJECT ESTIMATION SUMMARY",
               13, fc=C_NAVY, size=13)

    # ── Row 3: Section labels
    ws.row_dimensions[3].height = 18
    _section_label(ws, 3, 1, "Variables", 4, C_BLUE)
    _section_label(ws, 3, 6, "Team Allocation", 9, C_BLUE)
    _section_label(ws, 3, 12, "S.N.  |  Pre-Requisites (Client Responsibility)", 13, C_BLUE)

    # ── Variables block (rows 4-8, cols A-D)
    req  = results.get("requirements", {})
    time = results.get("time_estimate", {})
    # Derive Yes/No flags from actual technology_stack and in_scope items
    _tech_str = " ".join(str(t).lower() for t in (req.get("technology_stack") or []))
    def _scope_text(item, *fields):
        """Convert a scope item (dict or str) to a plain Excel-safe string."""
        if isinstance(item, dict):
            parts = [str(item.get(f, "")).strip() for f in fields if item.get(f)]
            return " | ".join(parts) if parts else str(item)
        return str(item) if item else ""

    _scope_str = " ".join(
        _scope_text(s, "title", "description").lower()
        for s in ((results.get("scope") or {}).get("in_scope") or [])
    )
    _has_frontend = any(k in _tech_str or k in _scope_str for k in
                        ["react", "angular", "vue", "frontend", "ui", "web app", "blazor", "next.js", "html"])
    _has_db = any(k in _tech_str for k in ["sql", "cosmos", "mongodb", "postgres", "mysql", "database", "redis", "blob"])
    _has_integration = any(k in _tech_str or k in _scope_str for k in
                           ["integration", "api", "connector", "sharepoint", "teams", "sap", "salesforce", "erp", "crm"])
    components = [
        ("Front End",             "Yes" if _has_frontend else "No"),
        ("Backend / AI Dev",      "Yes"),
        ("DevOps & Cloud",        "Yes"),
        ("Database / Storage",    "Yes" if _has_db else "No"),
        ("Integration / APIs",    "Yes" if _has_integration else "No"),
    ]
    _header_row(ws, 4, [(1,"SNO"),(2,"Component"),(3,"In Scope"),(4,"")], fc=C_COL_HEAD)
    for i, (comp, yn) in enumerate(components, 1):
        row = 4 + i
        bg = C_WHITE if i % 2 else C_LGRAY
        ws.cell(row=row, column=1, value=i).fill=_fill(bg); ws.cell(row=row,column=1).border=_border(); ws.cell(row=row,column=1).alignment=_align(h="center")
        ws.cell(row=row, column=2, value=comp).fill=_fill(bg); ws.cell(row=row,column=2).border=_border()
        yn_cell = ws.cell(row=row, column=3, value=yn)
        yn_cell.fill = _fill("E2EFDA" if yn=="Yes" else "FCE4D6")
        yn_cell.border=_border(); yn_cell.alignment=_align(h="center"); yn_cell.font=_font(bold=True)
        ws.cell(row=row, column=4).fill=_fill(bg); ws.cell(row=row,column=4).border=_border()

    # ── Team Allocation (rows 4-9, cols F-I)
    _header_row(ws, 4, [(6,"SNO"),(7,"Role"),(8,"Allocation %"),(9,"Est. Days")], fc=C_COL_HEAD)
    roles = [
        ("Project Manager",     "33%", f"=(Development!F{dev_total_row}+'DevOps & Cloud'!F{ops_total_row})/7*0.33"),
        ("AI Architect / Lead", "50%", f"=(Development!F{dev_total_row}+'DevOps & Cloud'!F{ops_total_row})/7*0.5"),
        ("AI / Senior Engineer","100%",f"=(Development!F{dev_total_row}+'DevOps & Cloud'!F{ops_total_row})/7*1"),
        ("QA Engineer",         "50%", f"=(Development!F{dev_total_row}+'DevOps & Cloud'!F{ops_total_row})/7*0.5"),
        ("DevOps / Cloud Eng",  "25%", f"=(Development!F{dev_total_row}+'DevOps & Cloud'!F{ops_total_row})/7*0.25"),
    ]
    for i, (role, alloc, formula) in enumerate(roles, 1):
        row = 4 + i
        bg = C_WHITE if i % 2 else C_LGRAY
        ws.cell(row=row, column=6, value=i).fill=_fill(bg); ws.cell(row=row,column=6).border=_border(); ws.cell(row=row,column=6).alignment=_align(h="center")
        ws.cell(row=row, column=7, value=role).fill=_fill(bg); ws.cell(row=row,column=7).border=_border()
        ws.cell(row=row, column=8, value=alloc).fill=_fill(bg); ws.cell(row=row,column=8).border=_border(); ws.cell(row=row,column=8).alignment=_align(h="center")
        ws.cell(row=row, column=9, value=formula).fill=_fill(bg); ws.cell(row=row,column=9).border=_border(); ws.cell(row=row,column=9).alignment=_align(h="center"); ws.cell(row=row,column=9).number_format="0.0"

    # ── Pre-Requisites (rows 4+, col L-M)
    # Pipeline stores scope under "scope" key (not "scope_assumptions")
    _scope = results.get("scope") or results.get("scope_assumptions") or {}

    # Normalise all scope lists — convert any structured dicts to plain strings
    def _flat(items, *fields):
        out = []
        for x in (items or []):
            if isinstance(x, dict):
                parts = [str(x.get(f, "")).strip() for f in fields if x.get(f)]
                out.append(" | ".join(parts) if parts else str(x))
            elif x:
                out.append(str(x))
        return out

    prereqs = _flat(_scope.get("prerequisites"), "item", "provided_by", "milestone", "consequence_if_delayed")
    if not prereqs:
        prereqs = [
            "Active Azure subscription with Contributor or Owner role on the target subscription.",
            "Microsoft 365 E3 (or higher) licenses for all service and user accounts.",
            "Read-access credentials and API permissions provided to ECI team within Week 1.",
            "Named project sponsor and product owner available throughout the engagement.",
            "Client SMEs available minimum 10 hrs/week for discovery and review sessions.",
            "Source system APIs documented and accessible with test credentials.",
            "Azure AD user accounts provisioned for UAT users prior to UAT phase commencement.",
            "All compliance and data governance requirements documented before project start.",
        ]
    ws.cell(row=4, column=12, value="S.N.").font=_font(bold=True); ws.cell(row=4,column=12).fill=_fill(C_COL_HEAD); ws.cell(row=4,column=12).border=_border(); ws.cell(row=4,column=12).alignment=_align(h="center"); ws.cell(row=4,column=12).font=_font(bold=True,color=C_WHITE)
    ws.cell(row=4, column=13, value="Pre-Requisite").font=_font(bold=True,color=C_WHITE); ws.cell(row=4,column=13).fill=_fill(C_COL_HEAD); ws.cell(row=4,column=13).border=_border()
    for i, pr in enumerate(prereqs, 1):
        row = 4 + i
        bg = C_PREREQ if i % 2 else C_WHITE
        ws.cell(row=row, column=12, value=i).fill=_fill(bg); ws.cell(row=row,column=12).border=_border(); ws.cell(row=row,column=12).alignment=_align(h="center")
        ws.cell(row=row, column=13, value=pr).fill=_fill(bg); ws.cell(row=row,column=13).border=_border(); ws.cell(row=row,column=13).alignment=_align(wrap=True,v="top"); ws.row_dimensions[4+i].height = 28

    # ── Activities block (rows 10-24, cols A-D)
    _section_label(ws, 10, 1, "Activities", 4, C_BLUE)
    _header_row(ws, 11, [(1,"SNO"),(2,"Component"),(3,""),(4,"Dev Time (hrs)")], fc=C_COL_HEAD)
    activities = [
        (1, "Front End",      "0",                                       "0"),
        (2, "Development",    f"=Development!F{dev_total_row}",         f"=Development!F{dev_total_row}"),
        (3, "DevOps & Cloud", f"='DevOps & Cloud'!F{ops_total_row}",   f"='DevOps & Cloud'!F{ops_total_row}"),
    ]
    for sno, comp, _, hrs_f in activities:
        row = 11 + sno
        bg = C_WHITE if sno % 2 else C_LGRAY
        ws.cell(row=row, column=1, value=sno).fill=_fill(bg); ws.cell(row=row,column=1).border=_border(); ws.cell(row=row,column=1).alignment=_align(h="center")
        ws.cell(row=row, column=2, value=comp).fill=_fill(bg); ws.cell(row=row,column=2).border=_border()
        ws.cell(row=row, column=3).fill=_fill(bg); ws.cell(row=row,column=3).border=_border()
        ws.cell(row=row, column=4, value=hrs_f).fill=_fill(bg); ws.cell(row=row,column=4).border=_border(); ws.cell(row=row,column=4).alignment=_align(h="center"); ws.cell(row=row,column=4).number_format="0.0"

    # Monthly infra cost reference
    ws.cell(row=13, column=6, value="Monthly Infra Cost (Est.)").font=_font(bold=True); ws.cell(row=13,column=6).fill=_fill(C_NOTE); ws.cell(row=13,column=6).border=_border(); ws.cell(row=13,column=6).alignment=_align(h="center")
    ws.merge_cells("F13:G13")
    ws.cell(row=13, column=8, value=f"='Infra Cost'!C{infra_total_row}").font=_font(bold=True)
    ws.cell(row=13, column=8).fill=_fill(C_TOTAL); ws.cell(row=13,column=8).border=_border(); ws.cell(row=13,column=8).alignment=_align(h="center")
    ws.cell(row=13, column=8).number_format='"$"#,##0.00'

    # ── Timeline block (rows 15-24, cols B-D)
    _header_row(ws, 15, [(2,"Component"),(3,"Days"),(4,"Weeks")], fc=C_COL_HEAD)
    timing_rows = [
        ("Development",    f"=Development!F{dev_total_row}/7",       f"=Development!F{dev_total_row}/35"),
        ("DevOps & Cloud", f"='DevOps & Cloud'!F{ops_total_row}/7",  f"='DevOps & Cloud'!F{ops_total_row}/35"),
    ]
    for i, (comp, days_f, weeks_f) in enumerate(timing_rows, 1):
        row = 15 + i
        bg = C_WHITE if i % 2 else C_LGRAY
        ws.cell(row=row, column=2, value=comp).fill=_fill(bg); ws.cell(row=row,column=2).border=_border()
        ws.cell(row=row, column=3, value=days_f).fill=_fill(bg); ws.cell(row=row,column=3).border=_border(); ws.cell(row=row,column=3).alignment=_align(h="center"); ws.cell(row=row,column=3).number_format="0.0"
        ws.cell(row=row, column=4, value=weeks_f).fill=_fill(bg); ws.cell(row=row,column=4).border=_border(); ws.cell(row=row,column=4).alignment=_align(h="center"); ws.cell(row=row,column=4).number_format="0.0"

    # Project Duration summary
    dur_labels = [
        (18, "Project Duration without UAT",         f"=Development!F{dev_total_row}/35"),
        (19, "UAT",                                   "2"),
        (20, "Project Duration with UAT",             "=D18+D19"),
        (21, "Leaves & Holidays Buffer",              "1"),
        (22, "Project Duration incl. Buffer (weeks)", "=D20+D21"),
    ]
    for row, label, formula in dur_labels:
        bg = C_TOTAL if "incl." in label else (C_SUBTOTAL if "with UAT" == label or "without" in label else C_WHITE)
        bold = "incl." in label or "with UAT" == label
        ws.cell(row=row, column=2, value=label).fill=_fill(bg); ws.cell(row=row,column=2).border=_border(); ws.cell(row=row,column=2).font=_font(bold=bold)
        ws.cell(row=row, column=3).fill=_fill(bg); ws.cell(row=row,column=3).border=_border()
        ws.cell(row=row, column=4, value=formula).fill=_fill(bg); ws.cell(row=row,column=4).border=_border(); ws.cell(row=row,column=4).alignment=_align(h="center"); ws.cell(row=row,column=4).number_format="0.0"; ws.cell(row=row,column=4).font=_font(bold=bold)

    # ── Out of Scope (col L-M, rows 13-26)
    oos = _flat(_scope.get("out_of_scope"), "exclusion", "rationale", "change_request_condition")
    if not oos:
        oos = [
            "Automated / scheduled data ingestion pipelines from any source.",
            "Custom UI development beyond agreed interface (web / Teams).",
            "CI/CD pipeline or advanced deployment automation.",
            "Long-term AI operations support or enterprise-wide AI platform.",
            "Multi-language support beyond English.",
            "Data classification, sensitivity labelling, or DLP integration.",
            "Penetration testing (recommended as a separate engagement).",
            "Hardware procurement or on-premises infrastructure.",
            "Third-party software license procurement.",
            "Any features not explicitly listed in scope (subject to change request).",
        ]
    _section_label(ws, 13, 12, "S.N.  |  Out of Scope", 13, C_BLUE)
    ws.cell(row=14, column=12, value="S.N.").font=_font(bold=True,color=C_WHITE); ws.cell(row=14,column=12).fill=_fill(C_COL_HEAD); ws.cell(row=14,column=12).border=_border(); ws.cell(row=14,column=12).alignment=_align(h="center")
    ws.cell(row=14, column=13, value="Item").font=_font(bold=True,color=C_WHITE); ws.cell(row=14,column=13).fill=_fill(C_COL_HEAD); ws.cell(row=14,column=13).border=_border()
    for i, item in enumerate(oos, 1):
        row = 14 + i
        bg = C_RED_LIGHT if i % 2 else C_WHITE
        ws.cell(row=row,column=12,value=i).fill=_fill(bg); ws.cell(row=row,column=12).border=_border(); ws.cell(row=row,column=12).alignment=_align(h="center")
        ws.cell(row=row,column=13,value=item).fill=_fill(bg); ws.cell(row=row,column=13).border=_border(); ws.cell(row=row,column=13).alignment=_align(wrap=True,v="top"); ws.row_dimensions[row].height=28

    # ── Assumptions (col L-M, rows 28+)
    assumptions = _flat(_scope.get("assumptions"), "statement", "consequence", "obligation")
    if not assumptions:
        assumptions = [
            "Source files are PDF and Word only; all other formats excluded from initial scope.",
            "50-100 historical files per use case provided within Week 1.",
            "AI accuracy estimated at 80–95% for structured document tasks.",
            "AI responses are advisory — all outputs require human review before use.",
            "Client SMEs available 10 hrs/week minimum throughout the project.",
            "UAT phase follows agreed timeline; client resources available and committed.",
            "All Azure/cloud licensing, infrastructure, and data usage costs are client responsibility.",
            "Client will respond to ECI queries within 24–48 business hours.",
            "No major organisational restructuring during the project.",
            "Standard business hours (9 AM – 6 PM) apply unless agreed otherwise.",
        ]
    asm_start = 26 + len(oos) + 2
    _section_label(ws, asm_start, 12, "S.N.  |  Assumptions", 13, C_BLUE)
    for i, asm in enumerate(assumptions, 1):
        row = asm_start + i
        bg = C_NOTE if i % 2 else C_WHITE
        ws.cell(row=row,column=12,value=i).fill=_fill(bg); ws.cell(row=row,column=12).border=_border(); ws.cell(row=row,column=12).alignment=_align(h="center")
        ws.cell(row=row,column=13,value=asm).fill=_fill(bg); ws.cell(row=row,column=13).border=_border(); ws.cell(row=row,column=13).alignment=_align(wrap=True,v="top"); ws.row_dimensions[row].height=28

    # ── Risks (col L-M, after assumptions)
    risk_start = asm_start + len(assumptions) + 2
    # Pipeline stores risks under "risk_assessment" (not "risk_analysis")
    _risk_result = results.get("risk_assessment") or results.get("risk_analysis") or {}
    risks_raw = _risk_result.get("risks") or []
    _section_label(ws, risk_start, 12, "S.N.  |  Risks", 13, C_BLUE)
    for i, risk in enumerate(risks_raw, 1):
        row = risk_start + i
        title = risk.get("title", "")
        desc  = risk.get("description", "")
        mit   = risk.get("mitigation", "")
        sev   = risk.get("severity", "")
        text  = f"[{sev.upper()}] {title}: {desc}. Mitigation: {mit}"
        bg = C_RED_LIGHT if i % 2 else C_WHITE
        ws.cell(row=row,column=12,value=i).fill=_fill(bg); ws.cell(row=row,column=12).border=_border(); ws.cell(row=row,column=12).alignment=_align(h="center")
        ws.cell(row=row,column=13,value=text).fill=_fill(bg); ws.cell(row=row,column=13).border=_border(); ws.cell(row=row,column=13).alignment=_align(wrap=True,v="top"); ws.row_dimensions[row].height=35

    # ── Definition of Done (col L-M, after risks)
    dod_start = risk_start + len(risks_raw) + 2
    _section_label(ws, dod_start, 12, "S.N.  |  Definition of Done — Project Closure Criteria", 13, C_BLUE)
    dod_items = [
        ("► DISCOVERY & DESIGN",     ""),
        ("1", "Architecture document reviewed and signed off by client."),
        ("2", "KPI metrics and accuracy thresholds defined, documented, and agreed by client."),
        ("3", "Source file formats confirmed; volume confirmed ≥50 files per use case."),
        ("4", "Prompt templates provided and approved. Model selection justified."),
        ("► ENVIRONMENT SETUP",       ""),
        ("1", "All Azure resources provisioned in dedicated Resource Group; private endpoints verified."),
        ("2", "Entra ID Managed Identities configured — no hardcoded secrets; Key Vault policies set."),
        ("► DEVELOPMENT & TESTING",   ""),
        ("1", "All acceptance criteria tested; defect log maintained; critical issues resolved."),
        ("2", "KPI validation report produced — accuracy vs threshold documented."),
        ("► UAT",                      ""),
        ("1", "10-15 users completed UAT across all agents; written sign-off received from named approver."),
        ("2", "All P1/P2 defects resolved before UAT closure."),
        ("► PRODUCTION HANDOVER",     ""),
        ("1", "Technical documentation and user guides finalised and delivered to client."),
        ("2", "Admin + end-user training sessions completed; recordings provided."),
        ("3", "Production deployment verified; go-live confirmed by client sponsor."),
    ]
    for i, (sno_val, text) in enumerate(dod_items):
        row = dod_start + 1 + i
        is_section = sno_val.startswith("►")
        if is_section:
            ws.merge_cells(f"L{row}:M{row}")
            ws.cell(row=row,column=12,value=f"  {sno_val}").font=_font(bold=True,color=C_WHITE)
            ws.cell(row=row,column=12).fill=_fill(C_COL_HEAD); ws.cell(row=row,column=12).border=_border()
            ws.cell(row=row,column=13).fill=_fill(C_COL_HEAD); ws.cell(row=row,column=13).border=_border()
        else:
            bg = C_DONE if i % 2 else C_WHITE
            ws.cell(row=row,column=12,value=sno_val).fill=_fill(bg); ws.cell(row=row,column=12).border=_border(); ws.cell(row=row,column=12).alignment=_align(h="center")
            ws.cell(row=row,column=13,value=text).fill=_fill(bg); ws.cell(row=row,column=13).border=_border(); ws.cell(row=row,column=13).alignment=_align(wrap=True,v="top")
        ws.row_dimensions[row].height=28

    # Note row at bottom of left section
    note_row = 24
    ws.merge_cells(f"A{note_row}:I{note_row}")
    three = time.get("three_point", {})
    opt   = _int(three.get("optimistic",  0))
    likely= _int(three.get("most_likely", 0))
    pess  = _int(three.get("pessimistic", 0))
    note  = (f"Note: Three-point estimate — Optimistic: {opt} hrs  |  Most Likely: {likely} hrs  "
             f"|  Pessimistic: {pess} hrs  |  18% contingency buffer applied.")
    ws.cell(row=note_row,column=1,value=note).font=_font(bold=False,size=9,color="595959")
    ws.cell(row=note_row,column=1).fill=_fill(C_NOTE); ws.cell(row=note_row,column=1).border=_border()
    ws.cell(row=note_row,column=1).alignment=_align(wrap=True)
    ws.row_dimensions[note_row].height=28

    ws.freeze_panes = "A3"
    return ws


def _build_version_history(wb, project_name, author="Prabhakar Gupta"):
    ws = wb.create_sheet("Version History")
    _col_widths(ws, [("A",12),("B",60),("C",18),("D",25)])
    ws.row_dimensions[1].height=26

    _title_row(ws,"A1",f"{project_name.upper()}  |  ESTIMATION VERSION HISTORY",4,fc=C_NAVY)
    _header_row(ws,3,[(1,"Version"),(2,"Changes / Notes"),(3,"Date"),(4,"Author")])
    today = datetime.now().strftime("%Y-%m-%d")
    for i, (ver, notes, date, auth) in enumerate([
        ("v1.0", "Initial estimation based on scope document.",  today, author),
    ], 1):
        row = 3 + i
        bg  = C_LGRAY if i % 2 else C_WHITE
        ws.cell(row=row,column=1,value=ver).fill=_fill(bg); ws.cell(row=row,column=1).border=_border(); ws.cell(row=row,column=1).alignment=_align(h="center")
        ws.cell(row=row,column=2,value=notes).fill=_fill(bg); ws.cell(row=row,column=2).border=_border(); ws.cell(row=row,column=2).alignment=_align(wrap=True)
        ws.cell(row=row,column=3,value=date).fill=_fill(bg); ws.cell(row=row,column=3).border=_border(); ws.cell(row=row,column=3).alignment=_align(h="center")
        ws.cell(row=row,column=4,value=auth).fill=_fill(bg); ws.cell(row=row,column=4).border=_border()
        ws.row_dimensions[row].height=18
    return ws


# ═══════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

def generate_final_estimation(results: dict,
                               project_name: str = "Project",
                               author: str = "Prabhakar Gupta",
                               region: str = "East US") -> bytes:
    """
    Generate a Final Estimation Excel workbook.

    Parameters
    ----------
    results       : dict — full pipeline results (time_estimate, cost_estimate,
                    risk_analysis, scope_assumptions, requirements, etc.)
    project_name  : str  — client / project name shown in headers
    author        : str  — name shown in Version History

    Returns
    -------
    bytes — the .xlsx file as a byte string (ready for st.download_button)
    """
    if not HAS_OPENPYXL:
        return b""

    wb = Workbook()
    # Remove default sheet; rebuild in the right order
    default = wb.active
    default.title = "Summary"   # hold the slot; will be populated last

    # ── Separate dev phases from devops phases ──
    phases = _safe(results, "time_estimate", "phases", default=[])
    if isinstance(phases, list) and phases:
        dev_phases, ops_phases = _split_phases(phases)
    else:
        dev_phases, ops_phases = [], []

    tech_stack = _safe(results, "requirements", "technology_stack", default=[])
    ops_phases = _ensure_devops_phase(ops_phases, tech_stack)

    if not dev_phases:
        dev_phases = [{
            "name": "Phase 1: Discovery & Design",
            "tasks": [
                {"name":"Kickoff workshop — scope confirmation & stakeholder alignment","low_hours":8,"high_hours":10,"role":"AI Architect / Lead","justification":"Joint session with client SMEs"},
                {"name":"Data assessment — source file review & volume validation","low_hours":8,"high_hours":12,"role":"AI Architect / Lead","justification":"Validate format, structure, volume"},
                {"name":"Architecture finalisation — services, data flows, security","low_hours":8,"high_hours":12,"role":"AI Architect / Lead","justification":"Azure Well-Architected baseline"},
                {"name":"Agent orchestration logic design","low_hours":8,"high_hours":12,"role":"AI Engineer","justification":"System prompt, tool definitions, output format"},
                {"name":"Evaluation framework — KPI metrics, accuracy thresholds","low_hours":6,"high_hours":8,"role":"AI Architect / Lead","justification":"Model selection, benchmarking criteria"},
                {"name":"Technical documentation v1","low_hours":12,"high_hours":16,"role":"AI Architect / Lead","justification":"Architecture doc, solution design; client sign-off"},
            ]
        },{
            "name": "Phase 2: AI Development & Integration",
            "tasks": [
                {"name":"Document parser — file ingestion & content extraction","low_hours":12,"high_hours":16,"role":"AI Engineer","justification":"PDF/Word/XLSX boundary detection"},
                {"name":"One-time data ingestion — AI Search index","low_hours":8,"high_hours":12,"role":"AI Engineer","justification":"Chunking strategy, metadata tagging, embeddings"},
                {"name":"Core agent logic — prompt engineering & orchestration","low_hours":20,"high_hours":28,"role":"AI Engineer","justification":"System prompt, tool registration, conversation flow"},
                {"name":"Output generation — structured document / report","low_hours":10,"high_hours":14,"role":"AI Engineer","justification":"Word/Excel/PDF output with source traceability"},
                {"name":"Teams / Copilot Studio UI — file upload & response cards","low_hours":8,"high_hours":12,"role":"AI Engineer","justification":"Adaptive card output; file return to user"},
                {"name":"Prompt logging — all interactions to Log Analytics","low_hours":4,"high_hours":6,"role":"AI Engineer","justification":"Per-query logging; audit trail"},
            ]
        },{
            "name": "Phase 3: Testing & UAT",
            "tasks": [
                {"name":"Internal QA — end-to-end testing; test case execution","low_hours":12,"high_hours":16,"role":"QA Engineer","justification":"All acceptance criteria tested; defect log"},
                {"name":"KPI validation — accuracy testing against thresholds","low_hours":8,"high_hours":12,"role":"QA Engineer","justification":"Model comparison report"},
                {"name":"UAT facilitation — client users, queries per agent","low_hours":8,"high_hours":10,"role":"AI Engineer","justification":"Session management, issue logging, user feedback"},
                {"name":"Bug fixes & prompt tuning post-UAT","low_hours":10,"high_hours":16,"role":"AI Engineer","justification":"P1/P2 issues resolved before sign-off"},
            ]
        },{
            "name": "Phase 4: Handover & Knowledge Transfer",
            "tasks": [
                {"name":"Technical documentation — architecture diagrams, API specs","low_hours":8,"high_hours":12,"role":"AI Architect / Lead","justification":"ECI standard format; delivered to client ops team"},
                {"name":"Functional documentation — end-user guides","low_hours":6,"high_hours":8,"role":"AI Engineer","justification":"Per-agent user guide; uploaded to client SharePoint"},
                {"name":"Knowledge transfer — admin + end-user training sessions","low_hours":6,"high_hours":8,"role":"AI Architect / Lead","justification":"1hr each; recorded for future reference"},
            ]
        }]

    # ── Build task sheets ──
    _, dev_total_row = _build_task_sheet(wb, "Development",       f"{project_name.upper()} — DEVELOPMENT & INTEGRATION",  dev_phases)
    _, ops_total_row = _build_task_sheet(wb, "DevOps & Cloud",    f"{project_name.upper()} — DEVOPS & INFRASTRUCTURE",     ops_phases)

    # ── Build Infra Cost sheet ──
    cost_estimate  = results.get("cost_estimate", {})
    azure_services = _ensure_infra_services(cost_estimate, _safe(results,"requirements","project_type",default=""))
    _, infra_total_row = _build_infra_cost_sheet(wb, project_name, azure_services, region=region)

    # ── Build Summary sheet (uses refs to other sheets) ──
    _build_summary_sheet(wb, project_name, results,
                         dev_total_row, ops_total_row, infra_total_row)

    # ── Build Version History ──
    _build_version_history(wb, project_name, author)

    # ── Reorder sheets: Summary first ──
    sheet_order = ["Summary", "Development", "DevOps & Cloud", "Infra Cost", "Version History"]
    for i, name in enumerate(sheet_order):
        if name in wb.sheetnames:
            wb.move_sheet(name, offset=wb.sheetnames.index(name) - i)

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.read()
