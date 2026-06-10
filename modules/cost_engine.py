# ═══════════════════════════════════════════════════════════════════════
#  DEAL COST ENGINE — Presales Cost Calculator
#  Powered by ECI Rate Card model
# ═══════════════════════════════════════════════════════════════════════
from __future__ import annotations
import uuid
import json
import io
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

import streamlit as st

from .utils import safe_str, safe_int, safe_list, safe_dict

# ───────────────────────────────────────────────────────────────────────
#  RATE CARD  (source: ECI Rate Card)
#  Format: (location, community, role, internal_hourly, bill_hourly)
# ───────────────────────────────────────────────────────────────────────
_RATE_ROWS = [
    # ── IND (India) ─────────────────────────────────────────────────────
    ("IND","Backend","Associate Software Eng",4,20),
    ("IND","Backend","Lead Software Engineer",18,35),
    ("IND","Backend","Senior Software Engineer",11,30),
    ("IND","Backend","Software Engineer",6,25),
    ("IND","Backend","Technical Architect",52,55),
    ("IND","Business Analyst","Associate Business Analyst",4,20),
    ("IND","Business Analyst","Business Analyst",7,25),
    ("IND","Business Analyst","Lead Business Analyst",18,35),
    ("IND","Business Analyst","Senior Business Analyst",12,30),
    ("IND","Data Services","Associate Software Eng",4,30),
    ("IND","Data Services","Database Administrator",27,45),
    ("IND","Data Services","Lead Developer",24,45),
    ("IND","Data Services","Senior Data Analyst",21,35),
    ("IND","Data Services","Data Analyst",11,30),
    ("IND","Data Services","Technical Architect",41,60),
    ("IND","DevOps","Associate Software Eng",4,25),
    ("IND","DevOps","Lead DevOps Engineer",13,45),
    ("IND","DevOps","Senior Software Engineer",13,40),
    ("IND","DevOps","Software Engineer",14,35),
    ("IND","Front-end","Lead Software Engineer",18,30),
    ("IND","Front-end","Senior Software Engineer",10,25),
    ("IND","Front-end","Software Engineer",6,20),
    ("IND","Front-end","Technical Architect",26,40),
    ("IND","Project Management","Lead Project Manager",28,40),
    ("IND","Project Management","Project Manager",21,30),
    ("IND","QA-Automation","Lead QA Engineer",22,30),
    ("IND","QA-Automation","Quality Assurance Eng",5,20),
    ("IND","QA-Manual","Associate Software Eng",4,20),
    ("IND","QA-Manual","Lead QA Engineer",15,32),
    ("IND","QA-Manual","Quality Assurance Eng",7,23),
    ("IND","QA-Manual","Senior QA Engineer",13,28),
    ("IND","RPA","Lead Software Engineer",18,40),
    ("IND","RPA","Senior Software Engineer",12,25),
    ("IND","Salesforce","Senior Software Engineer",9,30),
    ("IND","SharePoint","Senior Software Engineer",13,35),
    ("IND","SharePoint","Software Engineer",11,30),
    ("IND","UX-Design","Senior Designer",10,30),
    ("IND","Consultant","Associate Consultant",25,30),
    ("IND","Consultant","Consultant",30,35),
    ("IND","Consultant","Sr. Consultant",35,40),
    ("IND","Consultant","Consultant-Architect",40,50),
]

# Build lookup: (location, community, role) → (internal, bill)
RATE_LOOKUP: Dict[tuple, tuple] = {
    (loc, com, rol): (irate, brate)
    for loc, com, rol, irate, brate in _RATE_ROWS
}

# Unique locations / communities / roles for dropdowns
LOCATIONS    = ["IND"]
COMMUNITIES: Dict[str, List[str]] = {}
ROLES_BY_LOC_COM: Dict[tuple, List[str]] = {}
for loc, com, rol, _i, _b in _RATE_ROWS:
    COMMUNITIES.setdefault(loc, [])
    if com not in COMMUNITIES[loc]:
        COMMUNITIES[loc].append(com)
    ROLES_BY_LOC_COM.setdefault((loc, com), [])
    if rol not in ROLES_BY_LOC_COM[(loc, com)]:
        ROLES_BY_LOC_COM[(loc, com)].append(rol)

# Planning parameters
PLANNING_PARAMS = {
    "sga":             0.20,   # 20% on revenue
    "util_gap":        0.20,   # 20% on people cost
    "bgr_util_gap":    0.10,   # 10% BGR utilization gap
    "risk_enterprise": 0.02,
    "risk_startup":    0.04,
    "risk_standard":   0.00,
}

RISK_TIERS = ["Enterprise", "Startup", "Standard"]

MARGIN_THRESHOLDS = {
    "green":  45,   # net margin ≥ 45% → healthy
    "yellow": 35,   # 35-44% → caution
    # below 35% → red / management approval needed
}

_LOC_LABELS = {"IND": "🇮🇳 India (IND)"}
_LOC_COLORS = {"IND": "#00d4aa"}

_PRACTICE_ICONS = {
    "Backend": "⚙️", "Data Services": "📊", "DevOps": "🔧", "Front-end": "🖥️",
    "Project Management": "📋", "QA-Automation": "🤖", "QA-Manual": "✅",
    "Business Analyst": "📝", "RPA": "🔄", "Salesforce": "☁️", "SharePoint": "📁",
    "UX-Design": "🎨", "Consultant": "💼", "Product Owner": "🎯",
}


# ───────────────────────────────────────────────────────────────────────
#  CALCULATION ENGINE
# ───────────────────────────────────────────────────────────────────────

def _business_days(start: date, end: date) -> int:
    """Count Mon-Fri days between start and end (inclusive)."""
    if end < start:
        return 0
    days = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days += 1
        cur += timedelta(days=1)
    return days


def calc_member_hours(m: dict) -> float:
    """Return hours directly from the member dict (hours entered at add-time)."""
    return float(m.get("hours", 0.0))


def calc_deal(members: list, approval_gross: float = 50.0) -> dict:
    """Compute deal P&L. Revenue = T&M (hours × bill rate). No risk buffer."""
    per_member = []
    total_people_cost = 0.0
    total_tm_revenue  = 0.0

    for m in members:
        hours  = calc_member_hours(m)
        p_cost = m.get("internal_rate", 0) * hours
        tm_rev = m.get("billed_rate",   0) * hours
        total_people_cost += p_cost
        total_tm_revenue  += tm_rev
        per_member.append({**m, "hours": hours, "people_cost": p_cost, "tm_revenue": tm_rev})

    total_hours    = sum(pm["hours"] for pm in per_member)
    actual_revenue = total_tm_revenue
    sga            = actual_revenue * PLANNING_PARAMS["sga"]

    gross_margin = (actual_revenue - total_people_cost) / actual_revenue if actual_revenue > 0 else 0.0
    net_margin   = (actual_revenue - total_people_cost - sga) / actual_revenue if actual_revenue > 0 else 0.0

    return {
        "total_hours":    total_hours,
        "people_cost":    total_people_cost,
        "actual_revenue": actual_revenue,
        "sga":            sga,
        "gross_margin":   gross_margin,
        "net_margin":     net_margin,
        "per_member":     per_member,
        "needs_approval": gross_margin < (approval_gross / 100.0),
    }


# ───────────────────────────────────────────────────────────────────────
#  EXCEL EXPORT
# ───────────────────────────────────────────────────────────────────────

def export_deal_excel(members: list, deal: dict, project_name: str,
                      margin_thresholds: dict | None = None) -> bytes:
    try:
        import openpyxl
        from openpyxl.styles import (Font, PatternFill, Alignment, Border, Side)
        from openpyxl.utils import get_column_letter
    except ImportError:
        return b""

    mt = margin_thresholds or {"green": 45, "yellow": 35, "approval_gross": 50}

    wb = openpyxl.Workbook()

    # openpyxl requires AARRGGBB (8-char) hex — always prefix FF for full opacity
    def _c(h): return "FF" + h.upper().lstrip("#").zfill(6)

    NAVY   = _c("0F172A"); PURPLE = _c("7C3AED"); TEAL   = _c("00D4AA")
    GREY   = _c("1E293B"); WHITE  = _c("FFFFFF"); LGREY  = _c("94A3B8")
    ORANGE = _c("F59E0B"); RED    = _c("EF4444"); GREEN  = _c("22C55E")
    DKRED  = _c("1A0505"); ALTROW = _c("0F1A2E"); BORDER = _c("334155")
    SLATE  = _c("475569")

    def _mg_color(pct):
        if pct >= mt["green"]:  return GREEN
        if pct >= mt["yellow"]: return ORANGE
        return RED

    def _fill(color): return PatternFill("solid", fgColor=color)
    def _font(bold=False, color=WHITE, sz=11):
        return Font(bold=bold, color=color, size=sz, name="Segoe UI")
    def _border():
        s = Side(style="thin", color=BORDER)
        return Border(left=s, right=s, top=s, bottom=s)
    def _align(h="left", v="center", wrap=False):
        return Alignment(horizontal=h, vertical=v, wrap_text=wrap)
    def _hdr(ws, row, col, val, bold=True, bg=GREY, fg=WHITE, sz=11, align="left"):
        c = ws.cell(row=row, column=col, value=val)
        c.font = _font(bold, fg, sz); c.fill = _fill(bg)
        c.alignment = _align(align); c.border = _border()
        return c
    def _cell(ws, row, col, val, bold=False, fg=WHITE, bg=NAVY, fmt=None, align="left"):
        c = ws.cell(row=row, column=col, value=val)
        c.font = _font(bold, fg); c.fill = _fill(bg)
        c.alignment = _align(align); c.border = _border()
        if fmt: c.number_format = fmt
        return c

    # ── Sheet 1: Project Team ──────────────────────────────────────────
    ws = wb.active
    ws.title = "Project Team"
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A4"

    # Title row
    ws.merge_cells("A1:J1")
    t = ws["A1"]; t.value = f"Project Deal Cost Model — {project_name}"
    t.font = Font(bold=True, color=TEAL, size=16, name="Segoe UI")
    t.fill = _fill(NAVY); t.alignment = _align("center")

    ws.merge_cells("A2:H2")
    ws["A2"].value = "** Internal — Finance & Directors Only"
    ws["A2"].font = Font(bold=False, color="475569", size=10, name="Segoe UI")
    ws["A2"].fill = _fill(NAVY); ws["A2"].alignment = _align("right")

    # Column headers row 3
    headers = ["Title (Rate Card)", "Role on SOW", "Hours", "Allocation",
               "Internal Rate\n($/hr)", "People Cost\n(Sub Total)",
               "Billed Rate\n($/hr)", "Revenue\n(Sub Total)"]
    col_widths = [40, 22, 10, 12, 14, 16, 14, 16]
    for ci, (h, w) in enumerate(zip(headers, col_widths), 1):
        ws.column_dimensions[get_column_letter(ci)].width = w
        _hdr(ws, 3, ci, h, bg=PURPLE, sz=10, align="center")

    # Data rows
    row = 4
    for pm in deal["per_member"]:
        title = f"{pm['location']}-{pm['community']}-{pm['role']}"
        _cell(ws, row, 1, title,                    fg=WHITE,  bg=GREY,  align="left")
        _cell(ws, row, 2, pm.get("sow_role",""),    fg=LGREY,  bg=NAVY)
        _cell(ws, row, 3, pm["hours"],              fg=LGREY,  bg=NAVY,  fmt="#,##0", align="right")
        _cell(ws, row, 4, pm.get("allocation",1),   fg=TEAL,   bg=NAVY,  fmt="0%",   align="center")
        _cell(ws, row, 5, pm.get("internal_rate",0),fg=ORANGE, bg=NAVY,  fmt='"$"#,##0', align="right")
        _cell(ws, row, 6, pm["people_cost"],        fg=WHITE,  bg=GREY,  fmt='"$"#,##0.00', align="right")
        _cell(ws, row, 7, pm.get("billed_rate",0),  fg=GREEN,  bg=NAVY,  fmt='"$"#,##0', align="right")
        _cell(ws, row, 8, pm["tm_revenue"],         fg=WHITE,  bg=GREY,  fmt='"$"#,##0.00', align="right")
        row += 1

    # Totals row
    _hdr(ws, row, 1, "TOTALS", bg=PURPLE, align="right")
    for ci in range(2, 4):
        _cell(ws, row, ci, "", bg=PURPLE)
    _cell(ws, row, 3, deal["total_hours"],    bold=True, fg=WHITE,  bg=PURPLE, fmt="#,##0", align="right")
    _cell(ws, row, 4, "", bg=PURPLE)
    _cell(ws, row, 5, "", bg=PURPLE)
    _cell(ws, row, 6, deal["people_cost"],    bold=True, fg=WHITE,  bg=PURPLE, fmt='"$"#,##0.00', align="right")
    _cell(ws, row, 7, "", bg=PURPLE)
    _cell(ws, row, 8, deal["actual_revenue"], bold=True, fg=TEAL,   bg=PURPLE, fmt='"$"#,##0.00', align="right")
    row += 2

    # P&L Summary block
    summary_rows = [
        ("T&M Revenue",              deal["actual_revenue"],  TEAL,   NAVY),
        ("People Cost",              deal["people_cost"],     WHITE,  NAVY),
        ("SG&A (20% of revenue)",    deal["sga"],             LGREY,  NAVY),
        ("",                         "",                      WHITE,  NAVY),
        ("Gross Margin %",           deal["gross_margin"],    _mg_color(deal["gross_margin"]*100), GREY),
        ("Net Margin %",             deal["net_margin"],      _mg_color(deal["net_margin"]*100),   GREY),
    ]
    for label, val, fg, bg in summary_rows:
        if not label:
            row += 1; continue
        c1 = ws.cell(row=row, column=1, value=label)
        c1.font = Font(bold=True, color=fg, size=10, name="Segoe UI")
        c1.fill = _fill(bg); c1.alignment = _align("left"); c1.border = _border()
        fmt = "0.0%" if "%" in label else '"$"#,##0.00'
        c8 = ws.cell(row=row, column=8, value=val)
        c8.font = Font(bold=True, color=fg, size=11, name="Segoe UI")
        c8.fill = _fill(bg); c8.alignment = _align("right", wrap=False)
        c8.number_format = fmt; c8.border = _border()
        for ci in range(2, 8):
            e = ws.cell(row=row, column=ci); e.fill = _fill(bg); e.border = _border()
        row += 1

    # Approval note
    if deal["needs_approval"]:
        ws.merge_cells(f"A{row}:H{row}")
        n = ws[f"A{row}"]
        n.value = "⚠️  Gross Margin < 50% — Management Approval Required"
        n.font = Font(bold=True, color=RED, size=11, name="Segoe UI")
        n.fill = _fill(DKRED); n.alignment = _align("center")

    # Row heights
    ws.row_dimensions[1].height = 28
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 36
    for r in range(4, row): ws.row_dimensions[r].height = 20

    # ── Sheet 2: Rate Card Reference ──────────────────────────────────
    ws2 = wb.create_sheet("Rate Card")
    ws2.sheet_view.showGridLines = False
    ws2.freeze_panes = "A3"

    ws2.merge_cells("A1:F1")
    t2 = ws2["A1"]; t2.value = "ECI Rate Card"
    t2.font = Font(bold=True, color=TEAL, size=14, name="Segoe UI")
    t2.fill = _fill(NAVY); t2.alignment = _align("center")

    rc_hdrs = ["Location", "Community / Practice", "Role", "Internal Rate ($/hr)", "Bill Rate ($/hr)", "Margin %"]
    rc_widths = [12, 24, 34, 20, 18, 12]
    for ci, (h, w) in enumerate(zip(rc_hdrs, rc_widths), 1):
        ws2.column_dimensions[get_column_letter(ci)].width = w
        _hdr(ws2, 2, ci, h, bg=PURPLE, sz=10, align="center")

    _XL_LOC_COLORS = {"IND": _c("00D4AA")}
    prev_loc = None
    for ri, (loc, com, rol, ir, br) in enumerate(_RATE_ROWS, 3):
        bg = ALTROW if ri % 2 == 0 else NAVY
        margin = (br - ir) / br if br > 0 else 0
        loc_disp = loc if loc != prev_loc else ""
        prev_loc = loc
        fg_margin = _mg_color(margin * 100)
        for ci, (val, fg, fmt, al) in enumerate([
            (loc_disp, _XL_LOC_COLORS.get(loc, WHITE), "@", "center"),
            (com,      LGREY, "@", "left"),
            (rol,      WHITE, "@", "left"),
            (ir,       ORANGE,"$#,##0", "right"),
            (br,       GREEN, "$#,##0", "right"),
            (margin,   fg_margin, "0%", "center"),
        ], 1):
            c = ws2.cell(row=ri, column=ci, value=val)
            c.font = Font(color=fg, size=10, name="Segoe UI")
            c.fill = _fill(bg); c.alignment = _align(al); c.border = _border()
            c.number_format = fmt
        ws2.row_dimensions[ri].height = 18

    # ── Sheet 3: Notes ─────────────────────────────────────────────────
    ws3 = wb.create_sheet("Notes")
    ws3.sheet_view.showGridLines = False
    notes = [
        ("ECI Deal Cost Model — Notes", True, TEAL, NAVY, 14),
        ("", False, WHITE, NAVY, 10),
        ("Calculation Method:", True, WHITE, GREY, 11),
        ("  Hours = Allocation × Business Days × 8 hours/day", False, LGREY, NAVY, 10),
        ("  Business Days = Mon-Fri between Start and End dates (inclusive)", False, LGREY, NAVY, 10),
        ("  People Cost = Internal Hourly Rate × Hours", False, LGREY, NAVY, 10),
        ("  T&M Revenue = Billed Hourly Rate × Hours", False, LGREY, NAVY, 10),
        ("", False, WHITE, NAVY, 10),
        ("Planning Parameters:", True, WHITE, GREY, 11),
        (f"  SG&A:              {PLANNING_PARAMS['sga']*100:.0f}% of Actual Revenue", False, LGREY, NAVY, 10),
        (f"  Risk Buffer — Enterprise: {PLANNING_PARAMS['risk_enterprise']*100:.0f}%", False, LGREY, NAVY, 10),
        (f"  Risk Buffer — Startup:    {PLANNING_PARAMS['risk_startup']*100:.0f}%",    False, LGREY, NAVY, 10),
        ("", False, WHITE, NAVY, 10),
        ("Margin Health:", True, WHITE, GREY, 11),
        (f"  ✅ Green:  Net Margin ≥ {mt['green']}%", False, GREEN,  NAVY, 10),
        (f"  🟡 Yellow: Net Margin {mt['yellow']}–{mt['green']-1}%", False, ORANGE, NAVY, 10),
        (f"  🔴 Red:    Net Margin < {mt['yellow']}% — management approval may be required", False, RED, NAVY, 10),
        (f"  ⚠️  Gross Margin < {mt['approval_gross']}% — Seek management approval", False, RED, NAVY, 10),
        ("", False, WHITE, NAVY, 10),
        (f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", False, LGREY, NAVY, 10),
    ]
    ws3.column_dimensions["A"].width = 65
    for ri, (txt, bold, fg, bg, sz) in enumerate(notes, 1):
        c = ws3.cell(row=ri, column=1, value=txt)
        c.font = Font(bold=bold, color=fg, size=sz, name="Segoe UI")
        c.fill = _fill(bg); c.alignment = _align("left")
        ws3.row_dimensions[ri].height = 20

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ───────────────────────────────────────────────────────────────────────
#  AI TEAM SUGGESTION
# ───────────────────────────────────────────────────────────────────────

def _ai_suggest_team(project_summary: str, ai_client) -> list:
    """Ask Claude to suggest an optimal team from the rate card."""
    available_titles = "\n".join(
        f"  {loc}-{com}-{rol} | Internal ${ir}/hr | Bill ${br}/hr"
        for loc, com, rol, ir, br in _RATE_ROWS
    )
    system = (
        "You are an expert ECI presales consultant. Given a project description, "
        "suggest an optimal delivery team from the ECI rate card.\n"
        "Return ONLY valid JSON — a list of objects with these exact keys:\n"
        '  {"listed_role": "IND-Backend-Lead Software Engineer", "sow_role": "Lead Backend Engineer", '
        '"allocation": 1.0, "hours": 240}\n'
        "Rules:\n"
        "• Choose listed_role from the rate card exactly as shown (IND only)\n"
        "• allocation: 0.25, 0.33, 0.5, 0.75, or 1.0\n"
        "• hours: total project hours for this person (e.g. 80-2000)\n"
        "• Include PM (0.33-0.5 allocation), at least one architect, devs, QA\n"
        "• Use IND location for all roles\n"
        "• Return 5-10 team members maximum\n"
        "• Return ONLY the JSON array, no markdown, no explanation"
    )
    user = f"AVAILABLE RATE CARD:\n{available_titles}\n\nPROJECT:\n{project_summary[:2000]}"
    try:
        raw = ai_client.call_raw_text(system, user, max_tokens=2000)
        if not raw:
            return []
        import re, json as _json
        m = re.search(r"\[[\s\S]*\]", raw)
        if m:
            return _json.loads(m.group(0))
    except Exception:
        pass
    return []


# ───────────────────────────────────────────────────────────────────────
#  SENIORITY / PARALLELISM / HEALTH-CHECK HELPERS
# ───────────────────────────────────────────────────────────────────────

_SENIORITY_RULES = [
    (["lead", "principal", "head", "staff"],           "Lead"),
    (["senior", "sr.", "sr "],                         "Senior"),
    (["associate", "junior", "jr.", "entry", "assoc"], "Junior"),
]

def _seniority_level(role: str) -> str:
    rl = role.lower()
    for keywords, level in _SENIORITY_RULES:
        if any(kw in rl for kw in keywords):
            return level
    return "Mid"


_PARALLELIZABLE_COMMUNITIES = {
    "Backend", "Front-end", "Data Services", "QA-Automation", "QA-Manual",
    "RPA", "Salesforce", "SharePoint", "UX-Design", "DevOps",
}
_SEQUENTIAL_COMMUNITIES = {"Project Management", "Business Analyst", "Consultant"}


def _parallelism_calc(team: list, deal: dict, parallel_n: int, parallel_pct: float) -> dict:
    """Compute timeline + cost trade-off when splitting work into `parallel_n` tracks.

    Uses Amdahl's Law: speedup = 1 / (seq_frac + par_frac / n)
    with an 8% coordination overhead penalty per additional stream.
    """
    if not team or deal.get("total_hours", 0) == 0:
        return {}

    hours_per_week = 40
    base_cap   = sum(float(m.get("allocation", 1.0)) * hours_per_week for m in team)
    base_weeks = deal["total_hours"] / base_cap if base_cap > 0 else 0

    seq_frac = 1.0 - parallel_pct / 100.0
    par_frac = parallel_pct / 100.0

    amdahl    = 1.0 / (seq_frac + (par_frac / max(parallel_n, 1)))
    coord_pen = 1.0 + (parallel_n - 1) * 0.08       # 8% per extra stream
    eff_speed = amdahl / coord_pen
    new_weeks = base_weeks / eff_speed if eff_speed > 0 else base_weeks

    # Cost: only parallelizable roles scale; PM/BA/Architect don't duplicate
    extra_cost    = deal["people_cost"] * par_frac * (parallel_n - 1)
    new_cost      = deal["people_cost"] + extra_cost
    extra_revenue = deal["actual_revenue"] * par_frac * (parallel_n - 1)
    new_revenue   = deal["actual_revenue"] + extra_revenue
    new_sga       = new_revenue * PLANNING_PARAMS["sga"]
    new_gross     = (new_revenue - new_cost) / new_revenue if new_revenue > 0 else 0
    new_net       = (new_revenue - new_cost - new_sga) / new_revenue if new_revenue > 0 else 0

    return {
        "base_weeks":           round(base_weeks, 1),
        "new_weeks":            round(new_weeks, 1),
        "weeks_saved":          round(base_weeks - new_weeks, 1),
        "timeline_reduction_pct": round((1 - new_weeks / base_weeks) * 100, 1) if base_weeks > 0 else 0,
        "eff_speedup":          round(eff_speed, 2),
        "amdahl_speedup":       round(amdahl, 2),
        "coord_penalty_pct":    round((coord_pen - 1) * 100, 1),
        "extra_cost":           round(extra_cost),
        "new_cost":             round(new_cost),
        "extra_revenue":        round(extra_revenue),
        "new_revenue":          round(new_revenue),
        "new_gross_mg":         round(new_gross * 100, 1),
        "new_net_mg":           round(new_net * 100, 1),
        "cost_increase_pct":    round(extra_cost / deal["people_cost"] * 100, 1) if deal["people_cost"] > 0 else 0,
    }


def _team_health_issues(team: list, r: dict) -> list:
    """Static rule-based team composition health check. Returns list of (icon, title, detail)."""
    issues = []
    if not team:
        return [("ℹ️", "No team members yet", "Add team members to get a health check.")]

    coms        = {m.get("community", "") for m in team}
    roles_lower = [m.get("role", "").lower() for m in team]
    total_hrs   = sum(float(m.get("hours", 0)) for m in team)
    project_str = str(r).lower() if r else ""

    has_pm      = "Project Management" in coms
    has_arch    = any("architect" in rl for rl in roles_lower)
    has_qa      = "QA-Manual" in coms or "QA-Automation" in coms
    has_devops  = "DevOps" in coms
    has_ba      = "Business Analyst" in coms
    has_ux      = "UX-Design" in coms
    has_fe      = "Front-end" in coms
    has_cloud   = any(kw in project_str for kw in ["azure", "aws", "cloud", "infra", "kubernetes", "docker"])

    if not has_pm:
        issues.append(("🔴", "No Project Manager",
                        "Every delivery needs a PM — governance, client comms, sprint planning."))
    if not has_arch and total_hrs > 400:
        issues.append(("🟡", "No Solution Architect",
                        "Projects >400 hrs need architectural governance and design decisions."))
    if not has_qa and total_hrs > 200:
        issues.append(("🟡", "No QA Resource",
                        "No QA engineer. Recommend adding QA for any production delivery."))
    if has_cloud and not has_devops:
        issues.append(("🟡", "No DevOps Engineer",
                        "Cloud/infra scope detected. Add a DevOps engineer for CI/CD and deployment."))
    if not has_ba and total_hrs > 600:
        issues.append(("🟡", "No Business Analyst",
                        "Large project without a BA — requirements capture risk is high."))
    if has_fe and not has_ux and total_hrs > 300:
        issues.append(("ℹ️", "No UX Designer",
                        "Front-end work without a UX designer. Client-facing experience may suffer."))

    levels      = [_seniority_level(m.get("role", "")) for m in team]
    senior_cnt  = sum(1 for lv in levels if lv in ("Senior", "Lead"))
    if len(team) >= 4 and senior_cnt < 2:
        issues.append(("🟡", f"Low Seniority ({senior_cnt}/{len(team)} senior+lead)",
                        "Consider adding more senior/lead resources for quality and mentoring."))

    if not issues:
        issues.append(("🟢", "Team composition looks great!",
                        "All key roles (PM, Architect, QA, DevOps) are covered."))
    return issues


# ───────────────────────────────────────────────────────────────────────
#  SESSION STATE HELPERS
# ───────────────────────────────────────────────────────────────────────

def _init_state():
    defaults = {
        "deal_team":           [],
        "deal_project_name":   "",
        "deal_scenarios":      [],
        "deal_ai_loading":     False,
        "deal_ai_error":       "",
        # margin thresholds (internal, not exposed in UI)
        "deal_mg_green":          45,
        "deal_mg_yellow":         35,
        "deal_mg_approval_gross": 50,
        # add-member form state
        "_deal_add_loc":       "IND",
        "_deal_add_com":       "Backend",
        "_deal_add_rol":       "Lead Software Engineer",
        "_deal_add_sow":       "",
        "_deal_add_alloc":     1.0,
        "_deal_add_hours":     160.0,
        "_deal_add_brate_ovr": 35.0,
        "_deal_last_role_key": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _get_margin_thresholds() -> dict:
    return {
        "green":          st.session_state.get("deal_mg_green",          45),
        "yellow":         st.session_state.get("deal_mg_yellow",         35),
        "approval_gross": st.session_state.get("deal_mg_approval_gross", 50),
    }


def _member_card_html(pm: dict, idx: int, hours: float, cost: float, rev: float,
                      mt: dict | None = None) -> str:
    mt  = mt or {"green": 45, "yellow": 35}
    loc = pm.get("location", "")
    col = _LOC_COLORS.get(loc, "#7b61ff")
    icon  = _PRACTICE_ICONS.get(pm.get("community", ""), "👤")
    margin = (rev - cost) / rev * 100 if rev > 0 else 0
    mg_col = "#22c55e" if margin >= mt["green"] else ("#f59e0b" if margin >= mt["yellow"] else "#ef4444")
    alloc_pct = int(pm.get("allocation", 1) * 100)
    return f"""
<div style="background:linear-gradient(135deg,#0f172a,#1a1f2e);
     border:1px solid {col}44;border-radius:12px;padding:14px 16px;
     margin-bottom:10px;position:relative;overflow:hidden;">
  <div style="position:absolute;top:0;left:0;width:4px;height:100%;background:{col};border-radius:4px 0 0 4px;"></div>
  <div style="margin-left:8px;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px;">
      <div>
        <span style="font-size:.65rem;color:{col};font-weight:700;letter-spacing:.06em;text-transform:uppercase">{icon} {pm.get('community','')}</span><br>
        <span style="font-size:.9rem;font-weight:700;color:#e2e8f0">{pm.get('role','')}</span>
        <span style="font-size:.7rem;color:#64748b;margin-left:6px">{loc}</span>
      </div>
      <div style="text-align:right">
        <span style="font-size:.72rem;background:{col}22;color:{col};padding:2px 8px;border-radius:20px;font-weight:600">{alloc_pct}% alloc</span><br>
        <span style="font-size:.65rem;color:#475569;margin-top:2px;display:block">{hours:.0f} hrs</span>
      </div>
    </div>
    <div style="display:flex;gap:16px;margin-top:8px;flex-wrap:wrap;">
      <div><span style="font-size:.62rem;color:#475569">SOW Role</span><br>
           <span style="font-size:.75rem;color:#94a3b8">{pm.get('sow_role','') or '—'}</span></div>
      <div><span style="font-size:.62rem;color:#475569">Int. Rate</span><br>
           <span style="font-size:.75rem;color:#f59e0b">${pm.get('internal_rate',0)}/hr</span></div>
      <div><span style="font-size:.62rem;color:#475569">Bill Rate</span><br>
           <span style="font-size:.75rem;color:#22c55e">${pm.get('billed_rate',0)}/hr</span></div>
      <div><span style="font-size:.62rem;color:#475569">People Cost</span><br>
           <span style="font-size:.75rem;color:#e2e8f0">${cost:,.0f}</span></div>
      <div><span style="font-size:.62rem;color:#475569">Revenue</span><br>
           <span style="font-size:.75rem;color:#22c55e">${rev:,.0f}</span></div>
      <div><span style="font-size:.62rem;color:#475569">Margin</span><br>
           <span style="font-size:.75rem;color:{mg_col};font-weight:700">{margin:.1f}%</span></div>
    </div>
  </div>
</div>"""


def _margin_gauge_html(net_margin_pct: float, gross_margin_pct: float,
                       needs_approval: bool, mt: dict | None = None) -> str:
    mt = mt or {"green": 45, "yellow": 35, "approval_gross": 50}
    nm = min(max(net_margin_pct, 0), 100)
    gm = min(max(gross_margin_pct, 0), 100)
    g, y = mt["green"], mt["yellow"]
    nm_col = "#22c55e" if nm >= g else ("#f59e0b" if nm >= y else "#ef4444")
    gm_col = "#22c55e" if gm >= mt["approval_gross"] else ("#f59e0b" if gm >= y else "#ef4444")
    approval_banner = ""
    if needs_approval:
        approval_banner = """
<div style="margin-top:12px;padding:10px 16px;background:#1a0505;border:1px solid #ef444455;
     border-radius:8px;color:#ef4444;font-size:.78rem;font-weight:600;text-align:center;">
  ⚠️  Gross Margin &lt; 50% — Management Approval Required
</div>"""
    return f"""
<div style="background:linear-gradient(135deg,#0f172a,#1e293b);border:1px solid #334155;
     border-radius:16px;padding:24px;text-align:center;">
  <div style="font-size:.72rem;font-weight:700;color:#64748b;letter-spacing:.1em;
       text-transform:uppercase;margin-bottom:16px">DEAL HEALTH</div>

  <div style="margin-bottom:20px;">
    <div style="font-size:.68rem;color:#94a3b8;margin-bottom:4px">NET MARGIN</div>
    <div style="font-size:2.6rem;font-weight:900;color:{nm_col};line-height:1">{nm:.1f}%</div>
    <div style="background:#1e293b;border-radius:20px;height:8px;margin:8px auto;max-width:200px;overflow:hidden;">
      <div style="width:{min(nm,100):.0f}%;height:100%;background:{nm_col};border-radius:20px;
           transition:width .4s ease;"></div>
    </div>
    <div style="font-size:.62rem;color:#475569">
      {'✅ Healthy' if nm>=g else ('⚠️ Caution' if nm>=y else '🔴 Below Target')}
    </div>
  </div>

  <div style="width:1px;height:40px;background:#334155;margin:0 auto 16px;"></div>

  <div>
    <div style="font-size:.68rem;color:#94a3b8;margin-bottom:4px">GROSS MARGIN</div>
    <div style="font-size:1.8rem;font-weight:800;color:{gm_col}">{gm:.1f}%</div>
    <div style="background:#1e293b;border-radius:20px;height:6px;margin:6px auto;max-width:160px;overflow:hidden;">
      <div style="width:{min(gm,100):.0f}%;height:100%;background:{gm_col};border-radius:20px;"></div>
    </div>
  </div>
  {approval_banner}
</div>"""


def _metric_card(label: str, value: str, sub: str = "", color: str = "#00d4aa",
                 icon: str = "") -> str:
    return f"""
<div style="background:linear-gradient(135deg,#0f172a,#1a1f2e);
     border:1px solid {color}33;border-radius:12px;padding:18px 20px;text-align:center;
     box-shadow:0 4px 20px {color}11;">
  <div style="font-size:1rem;margin-bottom:4px">{icon}</div>
  <div style="font-size:1.6rem;font-weight:800;color:{color}">{value}</div>
  <div style="font-size:.72rem;font-weight:600;color:#94a3b8;text-transform:uppercase;
       letter-spacing:.05em;margin-top:4px">{label}</div>
  {f'<div style="font-size:.65rem;color:#475569;margin-top:3px">{sub}</div>' if sub else ''}
</div>"""


# ───────────────────────────────────────────────────────────────────────
#  MAIN RENDER FUNCTION
# ───────────────────────────────────────────────────────────────────────

_ALLOC_OPTIONS = [0.1, 0.25, 0.33, 0.5, 0.75, 1.0]

def _snap_alloc(v) -> float:
    """Clamp any allocation value to the nearest valid slider option."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 1.0
    return min(_ALLOC_OPTIONS, key=lambda x: abs(x - f))


@st.fragment
def render_team_roles_tab(r: dict, se: dict, te: dict, ai_client=None):
    _placeholder = st.empty()
    _placeholder.markdown(
        '<div style="padding:32px 0;display:flex;flex-direction:column;align-items:center;gap:16px;">'
        '<div style="display:flex;align-items:center;gap:12px;">'
        '<div style="width:22px;height:22px;border:3px solid rgba(0,212,170,.15);'
        'border-top-color:#00d4aa;border-radius:50%;'
        'animation:spin 0.8s linear infinite;"></div>'
        '<span style="color:#64748b;font-size:.85rem;font-weight:500">Loading Teams &amp; Roles…</span>'
        '</div>'
        '<style>@keyframes spin{to{transform:rotate(360deg)}}</style>'
        # skeleton rows
        '<div style="width:100%;max-width:680px;display:flex;flex-direction:column;gap:10px;">'
        + "".join(
            f'<div style="height:{h}px;border-radius:8px;'
            f'background:linear-gradient(90deg,#0f172a 25%,#1e293b 50%,#0f172a 75%);'
            f'background-size:200% 100%;animation:shimmer 1.4s infinite;">'
            f'</div>'
            f'<style>@keyframes shimmer{{0%{{background-position:200% 0}}100%{{background-position:-200% 0}}}}</style>'
            for h in [44, 36, 44, 36, 60]
        )
        + '</div></div>',
        unsafe_allow_html=True,
    )
    try:
        _render_team_roles_tab_inner(r, se, te, ai_client)
    except Exception as _frag_exc:
        import traceback
        _placeholder.empty()
        st.error(f"Teams & Roles tab error — {type(_frag_exc).__name__}: {_frag_exc}")
        with st.expander("Details"):
            st.code(traceback.format_exc())
        return
    _placeholder.empty()


def _render_team_roles_tab_inner(r: dict, se: dict, te: dict, ai_client=None):
    _init_state()

    team: List[dict] = st.session_state["deal_team"]

    # ── Page header ────────────────────────────────────────────────────
    st.markdown("""
<div style="background:linear-gradient(135deg,#13072e 0%,#1a0535 50%,#0f172a 100%);
     border:1px solid #7c3aed44;border-radius:16px;padding:24px 28px;margin-bottom:24px;">
  <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
    <span style="font-size:1.5rem">💼</span>
    <span style="font-size:1.4rem;font-weight:800;color:#e2e8f0">Deal Cost Calculator</span>
    <span style="background:rgba(124,58,237,.25);color:#a78bfa;font-size:.65rem;font-weight:700;
         border-radius:20px;padding:3px 10px;border:1px solid #7c3aed44">PRESALES TOOL</span>
  </div>
  <div style="font-size:.82rem;color:#64748b;">
    Build your project team from the ECI rate card · Live cost &amp; margin calculation
  </div>
</div>""", unsafe_allow_html=True)

    # ── Project name bar ────────────────────────────────────────────────
    pname = st.text_input(
        "Project Name", value=st.session_state["deal_project_name"],
        placeholder="e.g. AI Platform Implementation", key="deal_project_name_input",
    )
    st.session_state["deal_project_name"] = pname

    st.divider()

    # ── Resolve thresholds & deal calculation ───────────────────────────
    mt = _get_margin_thresholds()

    deal = calc_deal(team, approval_gross=mt["approval_gross"])

    # ── Client view toggle ──────────────────────────────────────────────
    _cv_col, _disc_col = st.columns([1, 1])
    with _cv_col:
        _client_view = st.toggle(
            "👁️ Client View",
            key="deal_client_view",
            help="Hides internal rates and people cost — safe to show to client",
        )
    with _disc_col:
        _discount_pct = st.slider(
            "💡 Discount on bill rates",
            min_value=0, max_value=30, value=0, step=1, format="%d%%",
            key="deal_discount_pct",
            help="What-if: apply a discount to all bill rates and see margin impact",
        )

    # ── KPI row ─────────────────────────────────────────────────────────
    blended = deal["actual_revenue"] / deal["total_hours"] if deal["total_hours"] > 0 else 0
    disc_rev = deal["actual_revenue"] * (1 - _discount_pct / 100)
    disc_gm  = (disc_rev - deal["people_cost"]) / disc_rev * 100 if disc_rev > 0 else 0
    disc_nm  = (disc_rev - deal["people_cost"] - disc_rev * PLANNING_PARAMS["sga"]) / disc_rev * 100 if disc_rev > 0 else 0

    gm_pct = disc_gm if _discount_pct > 0 else deal["gross_margin"] * 100
    nm_pct = disc_nm if _discount_pct > 0 else deal["net_margin"]   * 100
    gm_col = "#22c55e" if gm_pct >= mt["approval_gross"] else ("#f59e0b" if gm_pct >= mt["yellow"] else "#ef4444")
    nm_col = "#22c55e" if nm_pct >= mt["green"]          else ("#f59e0b" if nm_pct >= mt["yellow"] else "#ef4444")

    kpi_cols = st.columns(6)
    kpis_data = [
        ("Total Hours",   f"{deal['total_hours']:,.0f} h",
         f"{len(team)} members",                                        "#00d4aa", "⏱️"),
        ("Blended Rate",  f"${blended:.0f}/hr",
         "Revenue ÷ total hours",                                       "#00b4d8", "🔢"),
        ("Revenue",       f"${disc_rev:,.0f}" if _discount_pct else f"${deal['actual_revenue']:,.0f}",
         f"Billed to client{f'  (−{_discount_pct}%)' if _discount_pct else ''}",  "#22c55e", "💵"),
        ("Gross Margin",  f"{gm_pct:.1f}%",
         "Before SG&A",                                                 gm_col,   "📈"),
        ("Net Margin",    f"{nm_pct:.1f}%",
         "After SG&A (20%)",                                            nm_col,   "🎯"),
    ]
    if not _client_view:
        kpis_data.insert(2, (
            "People Cost", f"${deal['people_cost']:,.0f}",
            "Internal (do not share)", "#f59e0b", "💰",
        ))

    for col_obj, (lbl, val, sub, clr, ico) in zip(kpi_cols, kpis_data):
        with col_obj:
            st.markdown(_metric_card(lbl, val, sub, clr, ico), unsafe_allow_html=True)

    if _discount_pct > 0:
        st.markdown(
            f'<div style="background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25);'
            f'border-radius:8px;padding:8px 14px;font-size:.75rem;color:#f59e0b;margin-top:8px;">'
            f'⚠️ Discount scenario active: <b>{_discount_pct}%</b> off bill rates → '
            f'Gross {gm_pct:.1f}% | Net {nm_pct:.1f}% '
            f'({"✅ healthy" if nm_pct >= mt["green"] else "⚠️ caution" if nm_pct >= mt["yellow"] else "🔴 below target"})'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Main layout: Team Builder | Summary ────────────────────────────
    left, right = st.columns([3, 2], gap="large")

    # ────────────────────────────────────────────────────────────────
    # LEFT — Team Builder
    # ────────────────────────────────────────────────────────────────
    with left:
        # ── Add Member Panel ─────────────────────────────────────────
        with st.expander("➕ Add Team Member", expanded=len(team) == 0):
            st.markdown('<div style="font-size:.78rem;color:#94a3b8;margin-bottom:12px;">Select role from rate card, set dates and allocation</div>', unsafe_allow_html=True)

            a1, a2, a3 = st.columns(3)
            with a1:
                # Location — when it changes, reset community
                loc = st.selectbox(
                    "Location", LOCATIONS,
                    format_func=lambda x: _LOC_LABELS[x],
                    key="_deal_add_loc",
                )
            with a2:
                coms = COMMUNITIES.get(loc, [])
                cur_com = st.session_state["_deal_add_com"]
                if not coms:
                    coms = ["Consultant"]
                if cur_com not in coms:
                    st.session_state["_deal_add_com"] = coms[0]
                    cur_com = coms[0]
                com = st.selectbox("Practice / Community", coms,
                                   index=coms.index(cur_com), key="_deal_add_com")
            with a3:
                roles_list = ROLES_BY_LOC_COM.get((loc, com), [])
                cur_rol = st.session_state["_deal_add_rol"]
                if cur_rol not in roles_list:
                    st.session_state["_deal_add_rol"] = roles_list[0]
                    cur_rol = roles_list[0]
                rol = st.selectbox("Role", roles_list,
                                   index=roles_list.index(cur_rol), key="_deal_add_rol")

            internal_r, bill_r = RATE_LOOKUP.get((loc, com, rol), (0, 0))

            # Auto-update bill rate when role changes
            role_key = f"{loc}|{com}|{rol}"
            if st.session_state.get("_deal_last_role_key") != role_key:
                st.session_state["_deal_last_role_key"]  = role_key
                st.session_state["_deal_add_brate_ovr"] = float(bill_r)

            b1, b2, b3 = st.columns(3)
            with b1:
                sow_role = st.text_input(
                    "Role on SOW (custom name)",
                    placeholder=f"e.g. Lead {com} Engineer",
                    key="_deal_add_sow",
                )
            with b2:
                alloc = st.select_slider(
                    "Allocation", options=[0.1, 0.25, 0.33, 0.5, 0.75, 1.0],
                    value=st.session_state["_deal_add_alloc"],
                    format_func=lambda x: f"{int(x*100)}%",
                    key="_deal_add_alloc",
                )
            with b3:
                # Bill rate — pre-filled from rate card, user can override
                brate_ovr = st.number_input(
                    f"Bill Rate ($/hr) — card rate: ${bill_r}",
                    min_value=0.0,
                    value=float(st.session_state["_deal_add_brate_ovr"]),
                    step=5.0, format="%.0f", key="_deal_add_brate_ovr",
                )

            # Pre-fill hours from estimate agent if a matching role exists
            _est_hours_hint = 160.0
            if te:
                for _er in safe_list(te.get("roles", [])):
                    _erd = safe_dict(_er)
                    _ern = safe_str(_erd.get("name", "")).lower()
                    if any(kw in rol.lower() or kw in com.lower()
                           for kw in _ern.split() if len(kw) > 3):
                        try:
                            _est_hours_hint = float(_erd.get("hours", 160) or 160)
                        except Exception:
                            pass
                        break
            if st.session_state.get("_deal_last_role_key") != role_key:
                st.session_state["_deal_add_hours"] = _est_hours_hint

            hours_col, _ = st.columns([2, 3])
            with hours_col:
                add_hours = st.number_input(
                    "Hours", min_value=1.0, max_value=20000.0,
                    value=float(st.session_state["_deal_add_hours"]),
                    step=8.0, format="%.0f", key="_deal_add_hours",
                    help="Total hours for this role on the project (pre-filled from estimate when available)",
                )

            # Live preview
            preview_hours  = add_hours
            preview_cost   = internal_r * preview_hours
            preview_rev    = (brate_ovr or bill_r) * preview_hours
            preview_margin = (preview_rev - preview_cost) / preview_rev * 100 if preview_rev > 0 else 0
            mg_c = "#22c55e" if preview_margin >= mt["green"] else ("#f59e0b" if preview_margin >= mt["yellow"] else "#ef4444")
            st.markdown(
                f'<div style="background:#0f1a2e;border:1px solid #1e3a5f;border-radius:8px;'
                f'padding:10px 14px;font-size:.75rem;color:#94a3b8;margin:8px 0;">'
                f'📌 <b style="color:#00d4aa">{loc}-{com}-{rol}</b>&nbsp;&nbsp;|&nbsp;&nbsp;'
                f'Internal: <b style="color:#f59e0b">${internal_r}/hr</b>&nbsp;&nbsp;|&nbsp;&nbsp;'
                f'Bill: <b style="color:#22c55e">${brate_ovr or bill_r}/hr</b>&nbsp;&nbsp;|&nbsp;&nbsp;'
                f'<b>{preview_hours:.0f} hrs</b>&nbsp;&nbsp;|&nbsp;&nbsp;'
                f'Cost: <b>${preview_cost:,.0f}</b>&nbsp;&nbsp;|&nbsp;&nbsp;'
                f'Rev: <b>${preview_rev:,.0f}</b>&nbsp;&nbsp;|&nbsp;&nbsp;'
                f'Margin: <b style="color:{mg_c}">{preview_margin:.1f}%</b>'
                f'</div>', unsafe_allow_html=True,
            )

            add_col, clear_col = st.columns([1, 4])
            with add_col:
                if st.button("➕ Add to Team", type="primary", use_container_width=True, key="deal_add_btn"):
                    member = {
                        "id":            str(uuid.uuid4())[:8],
                        "location":      loc,
                        "community":     com,
                        "role":          rol,
                        "sow_role":      sow_role or f"{rol}",
                        "hours":         add_hours,
                        "allocation":    alloc,
                        "internal_rate": internal_r,
                        "billed_rate":   brate_ovr if brate_ovr > 0 else bill_r,
                    }
                    st.session_state["deal_team"].append(member)
                    st.toast(f"Added {rol} ({loc})", icon="✅")
                    st.rerun(scope="fragment")

        # ── Team list ────────────────────────────────────────────────
        if team:
            st.markdown(f'<div style="font-size:.8rem;font-weight:700;color:#64748b;'
                        f'margin-bottom:10px;text-transform:uppercase;letter-spacing:.06em;">'
                        f'TEAM ({len(team)} members)</div>', unsafe_allow_html=True)
            for i, pm in enumerate(team):
                pm_hours = calc_member_hours(pm)
                pm_cost  = pm.get("internal_rate", 0) * pm_hours
                pm_rev   = pm.get("billed_rate", 0) * pm_hours
                st.markdown(_member_card_html(pm, i, pm_hours, pm_cost, pm_rev, mt=mt), unsafe_allow_html=True)

                # Inline controls
                e1, e2, e3, e4, e5 = st.columns([2, 2, 2, 1, 1])
                with e1:
                    new_alloc = st.select_slider(
                        "Alloc", options=_ALLOC_OPTIONS,
                        value=_snap_alloc(pm.get("allocation", 1.0)),
                        format_func=lambda x: f"{int(x*100)}%",
                        key=f"alloc_{pm['id']}",
                        label_visibility="collapsed",
                    )
                    if new_alloc != pm.get("allocation"):
                        st.session_state["deal_team"][i]["allocation"] = new_alloc
                        st.rerun(scope="fragment")
                with e2:
                    new_hours = st.number_input(
                        "Hours", value=float(pm.get("hours", 0)),
                        min_value=1.0, step=8.0, format="%.0f",
                        key=f"hrs_{pm['id']}", label_visibility="collapsed",
                    )
                    if abs(new_hours - pm.get("hours", 0)) > 0.01:
                        st.session_state["deal_team"][i]["hours"] = new_hours
                        st.rerun(scope="fragment")
                with e3:
                    new_brate = st.number_input(
                        "Bill Rate", value=float(pm.get("billed_rate", 0)),
                        min_value=0.0, step=5.0, format="%.0f",
                        key=f"brate_{pm['id']}", label_visibility="collapsed",
                    )
                    if abs(new_brate - pm.get("billed_rate", 0)) > 0.01:
                        st.session_state["deal_team"][i]["billed_rate"] = new_brate
                        st.rerun(scope="fragment")
                with e4:
                    if st.button("✏️", key=f"dup_{pm['id']}", help="Duplicate member"):
                        dup = {**pm, "id": str(uuid.uuid4())[:8]}
                        st.session_state["deal_team"].insert(i + 1, dup)
                        st.rerun(scope="fragment")
                with e5:
                    if st.button("🗑️", key=f"del_{pm['id']}", help="Remove member"):
                        st.session_state["deal_team"].pop(i)
                        st.rerun(scope="fragment")

            # ── Clear / Import from Estimate ──────────────────────────
            st.markdown("<br>", unsafe_allow_html=True)
            btn1, btn2, btn3 = st.columns(3)
            with btn1:
                if st.button("🗑️ Clear Team", key="deal_clear"):
                    st.session_state["deal_team"] = []
                    st.rerun(scope="fragment")
            with btn2:
                # Import AI estimate roles
                te_roles = safe_list(te.get("roles", []))
                if te_roles and st.button("📥 Import from Estimate", key="deal_import"):
                    imported = 0
                    _ind_rows = _RATE_ROWS
                    for rl in te_roles:
                        rld = safe_dict(rl)
                        role_name = safe_str(rld.get("name", ""))
                        alloc = _snap_alloc(rld.get("allocation_pct", 1.0))
                        try:
                            role_hours = max(1.0, float(rld.get("hours", 160) or 160))
                        except Exception:
                            role_hours = 160.0
                        matched = None
                        for loc2, com2, rol2, ir2, br2 in _ind_rows:
                            if any(kw.lower() in rol2.lower() or kw.lower() in com2.lower()
                                   for kw in role_name.lower().split() if len(kw) > 3):
                                matched = (loc2, com2, rol2, ir2, br2)
                                break
                        if matched:
                            loc2, com2, rol2, ir2, br2 = matched
                            existing_rate = safe_int(rld.get("rate", 0))
                            st.session_state["deal_team"].append({
                                "id":            str(uuid.uuid4())[:8],
                                "location":      loc2,
                                "community":     com2,
                                "role":          rol2,
                                "sow_role":      role_name,
                                "hours":         role_hours,
                                "allocation":    alloc,
                                "internal_rate": ir2,
                                "billed_rate":   existing_rate if existing_rate > 0 else br2,
                            })
                            imported += 1
                    st.toast(f"Imported {imported} roles from estimate", icon="📥")
                    st.rerun(scope="fragment")

            with btn3:
                # Save as scenario
                if team and st.button("💾 Save Scenario", key="deal_save_scen"):
                    scen_name = f"Scenario {len(st.session_state['deal_scenarios'])+1} — {datetime.now().strftime('%H:%M')}"
                    st.session_state["deal_scenarios"].append({
                        "name": scen_name,
                        "team": [m.copy() for m in team],
                        "deal": {k: v for k, v in deal.items() if k != "per_member"},
                        "ts":   datetime.now().strftime("%Y-%m-%d %H:%M"),
                    })
                    st.toast(f"Saved as '{scen_name}'", icon="💾")
                    st.rerun(scope="fragment")

        else:
            st.markdown("""
<div style="border:2px dashed #1e3a5f;border-radius:14px;padding:40px;text-align:center;color:#334155;">
  <div style="font-size:2rem;margin-bottom:8px">👥</div>
  <div style="font-size:.9rem;font-weight:600;color:#475569;margin-bottom:4px">No team members yet</div>
  <div style="font-size:.78rem;color:#1e3a5f">Use "Add Team Member" above or ask AI to suggest a team</div>
</div>""", unsafe_allow_html=True)

        # ── AI Team Suggest ─────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div style="font-size:.8rem;font-weight:700;color:#64748b;text-transform:uppercase;'
                    'letter-spacing:.06em;margin-bottom:10px;">🤖 AI TEAM SUGGESTIONS</div>',
                    unsafe_allow_html=True)

        ai_loading = st.session_state.get("deal_ai_loading", False)
        if ai_loading:
            import streamlit.components.v1 as _stcomp_ai
            _stcomp_ai.html("""
<div style="display:flex;align-items:center;gap:12px;padding:14px;
     background:#0f1020;border:1px solid #7c3aed44;border-radius:10px;">
  <div style="display:flex;gap:6px">
    <div style="width:8px;height:8px;border-radius:50%;background:#7c3aed;
         animation:p 1.2s infinite;animation-delay:0s"></div>
    <div style="width:8px;height:8px;border-radius:50%;background:#a78bfa;
         animation:p 1.2s infinite;animation-delay:.2s"></div>
    <div style="width:8px;height:8px;border-radius:50%;background:#c4b5fd;
         animation:p 1.2s infinite;animation-delay:.4s"></div>
  </div>
  <span style="color:#a78bfa;font-size:.8rem;font-family:Segoe UI,sans-serif">
    AI is building the optimal team…</span>
</div>
<style>@keyframes p{0%,100%{transform:scale(.6);opacity:.3}50%{transform:scale(1.2);opacity:1}}
body{margin:0;background:transparent}</style>""", height=60)

        if st.session_state.get("deal_ai_error"):
            st.error(st.session_state["deal_ai_error"])
            st.session_state["deal_ai_error"] = ""

        # Build a short project summary for AI
        project_summary_parts = []
        if se:
            project_summary_parts.append(f"Project: {se.get('project_type','Unknown')}")
            project_summary_parts.append(f"Tech: {', '.join(safe_list(se.get('technologies',[])))[:200]}")
        if te:
            project_summary_parts.append(f"Duration: {te.get('duration_weeks','?')} weeks, {te.get('total_hours','?')} hours")
        project_summary_for_ai = "\n".join(project_summary_parts) or "Enterprise software project"

        ai_col1, ai_col2 = st.columns(2)
        with ai_col1:
            can_ai = ai_client is not None and getattr(ai_client, "is_live", False)
            if st.button(
                "🤖 Suggest Optimal Team",
                type="primary" if can_ai else "secondary",
                use_container_width=True, key="deal_ai_suggest",
                disabled=ai_loading or not can_ai,
            ):
                st.session_state["deal_ai_loading"] = True
                st.rerun(scope="fragment")

        # AI loading state: do the call and then clear flag
        if st.session_state.get("deal_ai_loading"):
            try:
                suggestions = _ai_suggest_team(project_summary_for_ai, ai_client)
                if suggestions:
                    today_d2 = date.today()
                    for sg in suggestions:
                        sg = safe_dict(sg)
                        listed = safe_str(sg.get("listed_role", ""))
                        parts  = listed.split("-", 2)
                        if len(parts) == 3:
                            sg_loc, sg_com, sg_rol = parts[0].strip(), parts[1].strip(), parts[2].strip()
                        else:
                            continue
                        ir2, br2 = RATE_LOOKUP.get((sg_loc, sg_com, sg_rol), (0, 0))
                        if ir2 == 0:
                            continue
                        alloc2   = _snap_alloc(sg.get("allocation", 1.0))
                        hours2   = max(1.0, float(sg.get("hours", 160)))
                        st.session_state["deal_team"].append({
                            "id":           str(uuid.uuid4())[:8],
                            "location":     sg_loc,
                            "community":    sg_com,
                            "role":         sg_rol,
                            "sow_role":     safe_str(sg.get("sow_role", sg_rol)),
                            "hours":        hours2,
                            "allocation":   alloc2,
                            "internal_rate": ir2,
                            "billed_rate":   br2,
                        })
                    st.toast(f"AI added {len(suggestions)} team members", icon="🤖")
                else:
                    st.session_state["deal_ai_error"] = "AI returned no suggestions. Try with a more detailed project."
            except Exception as ex:
                st.session_state["deal_ai_error"] = f"AI suggestion failed: {str(ex)[:200]}"
            finally:
                st.session_state["deal_ai_loading"] = False
            st.rerun(scope="fragment")

        if not can_ai:
            st.caption("Configure Claude API key in settings to enable AI suggestions")

        # ── Team Health Check ─────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("🩺 Team Health Check", expanded=bool(team)):
            health = _team_health_issues(team, r)
            _ic_bg = {"🟢": "rgba(34,197,94,.08)", "🔴": "rgba(239,68,68,.08)",
                      "🟡": "rgba(245,158,11,.08)", "ℹ️": "rgba(148,163,184,.06)"}
            _ic_bdr = {"🟢": "rgba(34,197,94,.3)",  "🔴": "rgba(239,68,68,.3)",
                       "🟡": "rgba(245,158,11,.3)",  "ℹ️": "rgba(148,163,184,.15)"}
            for icon, title, detail in health:
                bg  = _ic_bg.get(icon,  "rgba(148,163,184,.06)")
                bdr = _ic_bdr.get(icon, "rgba(148,163,184,.15)")
                st.markdown(
                    f'<div style="background:{bg};border:1px solid {bdr};border-radius:8px;'
                    f'padding:9px 13px;margin-bottom:7px;">'
                    f'<div style="font-size:.8rem;font-weight:700;color:#e2e8f0;margin-bottom:2px">'
                    f'{icon} {title}</div>'
                    f'<div style="font-size:.72rem;color:#64748b">{detail}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ────────────────────────────────────────────────────────────────
    # RIGHT — Cost Summary
    # ────────────────────────────────────────────────────────────────
    with right:
        # ── Margin Gauge ──────────────────────────────────────────────
        st.markdown(
            _margin_gauge_html(
                deal["net_margin"]   * 100,
                deal["gross_margin"] * 100,
                deal["needs_approval"],
                mt=mt,
            ),
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        # ── P&L waterfall ─────────────────────────────────────────────
        if team and deal["actual_revenue"] > 0:
            try:
                import plotly.graph_objects as go
                wf_lbls = ["Revenue", "− People Cost", "− SG&A (20%)"]

                fig = go.Figure(go.Waterfall(
                    orientation="v",
                    measure=["absolute", "relative", "relative"],
                    x=wf_lbls,
                    y=[deal["actual_revenue"], -deal["people_cost"], -deal["sga"]],
                    connector={"line": {"color": "#334155", "width": 1}},
                    decreasing={"marker": {"color": "#ef4444"}},
                    increasing={"marker": {"color": "#22c55e"}},
                    totals={"marker": {"color": "#7b61ff"}},
                    text=[f"${v:,.0f}" for v in
                          [deal["actual_revenue"], deal["people_cost"], deal["sga"]]],
                    textposition="outside",
                ))
                fig.update_layout(
                    title=dict(text="Deal P&L Waterfall", font=dict(color="#e2e8f0", size=13)),
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=320,
                    margin=dict(l=0, r=0, t=40, b=0),
                    yaxis=dict(showgrid=True, gridcolor="#1e293b", tickprefix="$", tickformat=",.0f"),
                    xaxis=dict(showgrid=False),
                    showlegend=False,
                )
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            except ImportError:
                pass

        # ── By Practice breakdown ─────────────────────────────────────
        if deal["per_member"]:
            try:
                import plotly.express as px
                import pandas as pd

                prac_data: dict = {}
                for pm in deal["per_member"]:
                    com = pm.get("community", "Other")
                    prac_data.setdefault(com, {"cost": 0, "rev": 0, "hrs": 0})
                    prac_data[com]["cost"] += pm["people_cost"]
                    prac_data[com]["rev"]  += pm["tm_revenue"]
                    prac_data[com]["hrs"]  += pm["hours"]

                df = pd.DataFrame([
                    {"Practice": f"{_PRACTICE_ICONS.get(c,'•')} {c}",
                     "Hours": v["hrs"], "Revenue": v["rev"]}
                    for c, v in prac_data.items()
                ])
                fig2 = px.bar(
                    df, x="Practice", y="Revenue",
                    color="Practice", text_auto=True,
                    title="Revenue by Practice",
                    color_discrete_sequence=[
                        "#00d4aa", "#00b4d8", "#7b61ff", "#f59e0b", "#ef4444",
                        "#22c55e", "#a78bfa", "#fb923c",
                    ],
                )
                fig2.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=280, showlegend=False,
                    margin=dict(l=0, r=0, t=40, b=60),
                    yaxis=dict(tickprefix="$", tickformat=",.0f", showgrid=True, gridcolor="#1e293b"),
                    xaxis=dict(showgrid=False, tickangle=-30),
                )
                fig2.update_traces(texttemplate="$%{y:,.0f}", textposition="outside",
                                   textfont=dict(size=9))
                st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
            except ImportError:
                pass

        # ── Seniority mix ─────────────────────────────────────────────
        if team:
            try:
                import plotly.graph_objects as go
                _lvls = [_seniority_level(m.get("role", "")) for m in team]
                _lv_counts = {}
                for lv in _lvls:
                    _lv_counts[lv] = _lv_counts.get(lv, 0) + 1
                _lv_colors = {"Lead": "#7b61ff", "Senior": "#00d4aa",
                              "Mid": "#00b4d8",  "Junior": "#f59e0b"}
                _fig_s = go.Figure(go.Pie(
                    labels=list(_lv_counts.keys()),
                    values=list(_lv_counts.values()),
                    hole=0.55,
                    marker_colors=[_lv_colors.get(k, "#94a3b8") for k in _lv_counts],
                    textinfo="label+percent",
                    textfont=dict(size=10, color="#e2e8f0"),
                    hovertemplate="%{label}: %{value} member(s)<extra></extra>",
                ))
                _fig_s.update_layout(
                    title=dict(text="Seniority Mix", font=dict(color="#e2e8f0", size=12)),
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)", showlegend=True,
                    height=220, margin=dict(l=0, r=0, t=36, b=0),
                    legend=dict(font=dict(color="#94a3b8", size=9),
                                bgcolor="rgba(0,0,0,0)", orientation="h",
                                yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
                )
                st.plotly_chart(_fig_s, use_container_width=True,
                                config={"displayModeBar": False})
            except ImportError:
                pass

        # ── P&L summary table ─────────────────────────────────────────
        st.markdown("""
<div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;
     padding:16px;font-size:.8rem;font-family:monospace;">""", unsafe_allow_html=True)

        def _pnl_row(label, val, color="#94a3b8", bold=False, fmt="$"):
            v_str = f"${val:,.2f}" if fmt == "$" else f"{val*100:.1f}%"
            b = "font-weight:700;" if bold else ""
            return (f'<div style="display:flex;justify-content:space-between;'
                    f'padding:4px 0;border-bottom:1px solid #1e293b;">'
                    f'<span style="color:#64748b">{label}</span>'
                    f'<span style="color:{color};{b}">{v_str}</span></div>')

        _eff_rev = disc_rev if _discount_pct else deal["actual_revenue"]
        _eff_gm  = disc_gm / 100 if _discount_pct else deal["gross_margin"]
        _eff_nm  = disc_nm / 100 if _discount_pct else deal["net_margin"]

        rows_html = (
            _pnl_row("Revenue (T&M)",  _eff_rev,          "#22c55e", bold=True)
            + ("" if _client_view else
               _pnl_row("People Cost", deal["people_cost"], "#ef4444"))
            + _pnl_row("SG&A (20%)",   _eff_rev * PLANNING_PARAMS["sga"], "#f59e0b")
            + _pnl_row("Gross Margin", _eff_gm,
                       "#22c55e" if _eff_gm * 100 >= mt["approval_gross"]
                       else ("#f59e0b" if _eff_gm * 100 >= mt["yellow"] else "#ef4444"),
                       bold=True, fmt="%")
            + _pnl_row("Net Margin",   _eff_nm,
                       "#22c55e" if _eff_nm * 100 >= mt["green"]
                       else ("#f59e0b" if _eff_nm * 100 >= mt["yellow"] else "#ef4444"),
                       bold=True, fmt="%")
        )
        st.markdown(rows_html + "</div>", unsafe_allow_html=True)

        # ── Export row ─────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        if team:
            xl_bytes = export_deal_excel(
                team, deal,
                st.session_state.get("deal_project_name") or "Deal",
                margin_thresholds=mt,
            )
            if xl_bytes:
                fname = f"ECI_Deal_{(st.session_state.get('deal_project_name') or 'Project').replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                st.download_button(
                    "📥 Export to Excel",
                    data=xl_bytes, file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, type="primary",
                    key="deal_xl_dl",
                )

    # ── Parallelism Analyzer ────────────────────────────────────────────
    st.divider()
    st.markdown(
        '<div style="background:linear-gradient(135deg,rgba(0,180,216,.06),rgba(123,97,255,.06)),'
        'rgba(10,15,26,.8);border:1px solid rgba(0,180,216,.2);border-radius:16px;'
        'padding:20px 24px;margin-bottom:20px;">'
        '<div style="font-size:1.05rem;font-weight:800;color:#e2e8f0;margin-bottom:6px">'
        '⚡ Parallelism Analyzer — Speed vs Cost Trade-off</div>'
        '<div style="font-size:.78rem;color:#64748b;line-height:1.6">'
        'Model what happens when you add parallel delivery streams to compress the timeline. '
        'Based on <b style="color:#00b4d8">Amdahl\'s Law</b> — not all work can be parallelised: '
        'discovery, architecture, and PM coordination must stay sequential. '
        'Adding streams reduces time but increases cost and coordination overhead.'
        '</div></div>',
        unsafe_allow_html=True,
    )

    if not team or deal["total_hours"] == 0:
        st.info("Add team members to run the parallelism analysis.")
    else:
        _pa_c1, _pa_c2 = st.columns(2)
        with _pa_c1:
            _par_n = st.slider(
                "Parallel delivery streams",
                min_value=1, max_value=4, value=1, step=1,
                key="deal_par_n",
                help="1 = baseline sequential. 2 = two parallel teams, etc.",
                format="%d streams",
            )
        with _pa_c2:
            _par_pct = st.slider(
                "Parallelisable work (%)",
                min_value=30, max_value=90, value=65, step=5,
                key="deal_par_pct",
                help="Estimate of how much work CAN run in parallel. "
                     "Dev & QA tasks: ~70-80%. Discovery/Arch: ~20-30%.",
                format="%d%%",
            )

        # Build all 4 scenarios for comparison chart
        _par_scenarios = []
        for _n in range(1, 5):
            _ps = _parallelism_calc(team, deal, _n, _par_pct)
            if _ps:
                _par_scenarios.append({"n": _n, **_ps})

        _sel_ps = _parallelism_calc(team, deal, _par_n, _par_pct)

        if _sel_ps:
            # ── KPI highlight for selected scenario ──────────────────
            _base_weeks = _sel_ps["base_weeks"]
            _pct_saved  = _sel_ps["timeline_reduction_pct"]
            _pct_cost   = _sel_ps["cost_increase_pct"]

            _ph1, _ph2, _ph3, _ph4 = st.columns(4)
            _ph_cards = [
                (_ph1, "Timeline",
                 f"{_sel_ps['new_weeks']:.1f} wks",
                 f"was {_base_weeks} wks",
                 "#00d4aa", "⏱️"),
                (_ph2, "Time Saved",
                 f"−{_sel_ps['weeks_saved']:.1f} wks",
                 f"−{_pct_saved:.0f}% vs baseline",
                 "#7b61ff", "🚀"),
                (_ph3, "Extra Cost",
                 f"+${_sel_ps['extra_cost']:,}",
                 f"+{_pct_cost:.0f}% people cost",
                 "#f59e0b", "💸"),
                (_ph4, "Gross Margin",
                 f"{_sel_ps['new_gross_mg']:.1f}%",
                 f"was {deal['gross_margin']*100:.1f}%",
                 "#22c55e" if _sel_ps["new_gross_mg"] >= mt["approval_gross"] else "#f59e0b", "📈"),
            ]
            for _col, _lbl, _val, _sub, _clr, _ico in _ph_cards:
                with _col:
                    st.markdown(_metric_card(_lbl, _val, _sub, _clr, _ico),
                                unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # ── Breakdown explanation ────────────────────────────────
            if _par_n > 1:
                _seq_pct = 100 - _par_pct
                st.markdown(
                    f'<div style="background:#0f172a;border:1px solid #1e293b;'
                    f'border-radius:10px;padding:14px 18px;font-size:.78rem;'
                    f'display:flex;gap:32px;">'
                    f'<div><div style="color:#475569;font-size:.65rem;'
                    f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">'
                    f'Amdahl Speedup</div>'
                    f'<div style="color:#00b4d8;font-weight:700;font-size:1.1rem">'
                    f'{_sel_ps["amdahl_speedup"]}×</div>'
                    f'<div style="color:#334155;font-size:.67rem">pure parallelism</div></div>'
                    f'<div><div style="color:#475569;font-size:.65rem;'
                    f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">'
                    f'After Coordination Overhead</div>'
                    f'<div style="color:#7b61ff;font-weight:700;font-size:1.1rem">'
                    f'{_sel_ps["eff_speedup"]}×</div>'
                    f'<div style="color:#334155;font-size:.67rem">'
                    f'−{_sel_ps["coord_penalty_pct"]:.0f}% penalty ({(_par_n-1)*8}%)</div></div>'
                    f'<div><div style="color:#475569;font-size:.65rem;'
                    f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">'
                    f'Sequential (must stay serial)</div>'
                    f'<div style="color:#ef4444;font-weight:700;font-size:1.1rem">'
                    f'{_seq_pct}%</div>'
                    f'<div style="color:#334155;font-size:.67rem">'
                    f'arch, discovery, PM, go-live</div></div>'
                    f'<div><div style="color:#475569;font-size:.65rem;'
                    f'text-transform:uppercase;letter-spacing:.05em;margin-bottom:4px">'
                    f'Parallelisable</div>'
                    f'<div style="color:#22c55e;font-weight:700;font-size:1.1rem">'
                    f'{_par_pct}%</div>'
                    f'<div style="color:#334155;font-size:.67rem">'
                    f'dev, QA, FE, data, UX</div></div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            # ── Comparison table ─────────────────────────────────────
            try:
                import plotly.graph_objects as _pgo
                _tab_cols = ["Streams", "Timeline (wks)", "Time Saved", "Extra Cost",
                             "New People Cost", "Gross Margin", "Net Margin"]
                _tab_vals = [
                    [f"{ps['n']} {'(baseline)' if ps['n']==1 else f'parallel'}" for ps in _par_scenarios],
                    [f"{ps['new_weeks']:.1f}" for ps in _par_scenarios],
                    [f"−{ps['weeks_saved']:.1f} wks ({ps['timeline_reduction_pct']:.0f}%)" for ps in _par_scenarios],
                    [f"+${ps['extra_cost']:,} ({ps['cost_increase_pct']:.0f}%)" for ps in _par_scenarios],
                    [f"${ps['new_cost']:,}" for ps in _par_scenarios],
                    [f"{ps['new_gross_mg']:.1f}%" for ps in _par_scenarios],
                    [f"{ps['new_net_mg']:.1f}%" for ps in _par_scenarios],
                ]
                _hl_fill  = ["rgba(0,180,216,.15)" if ps["n"] == _par_n else "rgba(15,23,42,.0)"
                             for ps in _par_scenarios]
                _hl_font  = ["#00b4d8" if ps["n"] == _par_n else "#94a3b8"
                             for ps in _par_scenarios]

                _fig_tbl = _pgo.Figure(_pgo.Table(
                    header=dict(
                        values=[f"<b>{c}</b>" for c in _tab_cols],
                        fill_color="#1e293b", font=dict(color="#cbd5e1", size=11),
                        align="left", height=30,
                    ),
                    cells=dict(
                        values=_tab_vals,
                        fill_color=[_hl_fill] + [["#0f172a"] * len(_par_scenarios)] * (len(_tab_cols) - 1),
                        font=dict(color=[_hl_font] + [["#e2e8f0"] * len(_par_scenarios)] * (len(_tab_cols) - 1), size=11),
                        align="left", height=28,
                    ),
                ))
                _fig_tbl.update_layout(
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                    height=180, margin=dict(l=0, r=0, t=10, b=0),
                )
                st.plotly_chart(_fig_tbl, use_container_width=True,
                                config={"displayModeBar": False})
            except ImportError:
                pass

            # ── Trade-off scatter chart ──────────────────────────────
            try:
                import plotly.graph_objects as _pgo2
                _x_wks   = [ps["new_weeks"]  for ps in _par_scenarios]
                _y_cost  = [ps["new_cost"]   for ps in _par_scenarios]
                _labels  = [f"{ps['n']}× streams" for ps in _par_scenarios]
                _colors  = ["#00b4d8" if ps["n"] == _par_n else "#334155"
                            for ps in _par_scenarios]
                _sizes   = [18 if ps["n"] == _par_n else 10
                            for ps in _par_scenarios]

                _fig_sc = _pgo2.Figure()
                _fig_sc.add_trace(_pgo2.Scatter(
                    x=_x_wks, y=_y_cost,
                    mode="lines+markers+text",
                    text=_labels, textposition="top center",
                    textfont=dict(color="#94a3b8", size=9),
                    line=dict(color="#334155", width=1.5, dash="dot"),
                    marker=dict(color=_colors, size=_sizes,
                                line=dict(color="#00b4d8", width=1.5)),
                    hovertemplate="<b>%{text}</b><br>%{x:.1f} weeks | $%{y:,}<extra></extra>",
                ))
                _fig_sc.add_hline(
                    y=deal["people_cost"], line_dash="dash",
                    line_color="#ef4444", opacity=0.4,
                    annotation_text="baseline cost",
                    annotation_font_color="#ef4444",
                    annotation_font_size=9,
                )
                _fig_sc.update_layout(
                    title=dict(text="Timeline vs Cost Trade-off Curve",
                               font=dict(color="#e2e8f0", size=12)),
                    template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)", height=280,
                    margin=dict(l=0, r=0, t=40, b=0),
                    xaxis=dict(title="Timeline (weeks)", showgrid=True,
                               gridcolor="#1e293b", color="#64748b"),
                    yaxis=dict(title="People Cost ($)", tickprefix="$",
                               tickformat=",.0f", showgrid=True,
                               gridcolor="#1e293b", color="#64748b"),
                )
                st.plotly_chart(_fig_sc, use_container_width=True,
                                config={"displayModeBar": False})
            except ImportError:
                pass

        # ── What can / cannot be parallelised ───────────────────────
        if _par_n > 1:
            _wc1, _wc2 = st.columns(2)
            _par_coms   = [m.get("community","") for m in team if m.get("community","") in _PARALLELIZABLE_COMMUNITIES]
            _seq_coms   = [m.get("community","") for m in team if m.get("community","") in _SEQUENTIAL_COMMUNITIES]
            _par_roles  = sorted({m.get("role","") for m in team if m.get("community","") in _PARALLELIZABLE_COMMUNITIES})
            _seq_roles  = sorted({m.get("role","") for m in team if m.get("community","") in _SEQUENTIAL_COMMUNITIES})
            _unk_roles  = sorted({m.get("role","") for m in team
                                  if m.get("community","") not in _PARALLELIZABLE_COMMUNITIES
                                  and m.get("community","") not in _SEQUENTIAL_COMMUNITIES})

            def _role_pills(roles, color):
                return "".join(
                    f'<span style="background:{color}18;color:{color};border:1px solid {color}33;'
                    f'border-radius:20px;padding:2px 9px;font-size:.68rem;margin:3px 2px;'
                    f'display:inline-block">{r}</span>'
                    for r in roles
                ) or '<span style="color:#334155;font-size:.72rem">none in current team</span>'

            with _wc1:
                st.markdown(
                    f'<div style="background:rgba(34,197,94,.05);border:1px solid rgba(34,197,94,.2);'
                    f'border-radius:10px;padding:14px;">'
                    f'<div style="font-size:.75rem;font-weight:700;color:#22c55e;margin-bottom:8px">'
                    f'✅ CAN be parallelised ({_par_pct}% of work)</div>'
                    f'<div style="font-size:.68rem;color:#64748b;margin-bottom:8px;line-height:1.5">'
                    f'Development tasks, feature sprints, QA testing cycles, '
                    f'UI/UX design, data pipeline work, DevOps automation</div>'
                    f'<div style="margin-top:6px">{_role_pills(_par_roles, "#22c55e")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with _wc2:
                _all_seq = _seq_roles + _unk_roles
                st.markdown(
                    f'<div style="background:rgba(239,68,68,.05);border:1px solid rgba(239,68,68,.2);'
                    f'border-radius:10px;padding:14px;">'
                    f'<div style="font-size:.75rem;font-weight:700;color:#ef4444;margin-bottom:8px">'
                    f'🔒 CANNOT be parallelised ({100-_par_pct}% of work)</div>'
                    f'<div style="font-size:.68rem;color:#64748b;margin-bottom:8px;line-height:1.5">'
                    f'Discovery & requirements, architecture design, '
                    f'integration testing, go-live deployment, PM coordination</div>'
                    f'<div style="margin-top:6px">{_role_pills(_all_seq, "#ef4444")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    # ── Scenarios comparison ────────────────────────────────────────────
    scenarios = st.session_state.get("deal_scenarios", [])
    if scenarios:
        st.divider()
        st.markdown('<div style="font-size:.9rem;font-weight:700;color:#e2e8f0;margin-bottom:14px;">📊 Scenario Comparison</div>', unsafe_allow_html=True)
        try:
            import pandas as pd
            scen_rows = []
            for i, sc in enumerate(scenarios):
                d = safe_dict(sc.get("deal", {}))
                scen_rows.append({
                    "#":            i + 1,
                    "Scenario":     sc.get("name", f"Scenario {i+1}"),
                    "Members":      len(safe_list(sc.get("team", []))),
                    "Hours":        f"{d.get('total_hours',0):,.0f}",
                    "People Cost":  f"${d.get('people_cost',0):,.0f}",
                    "Revenue":      f"${d.get('actual_revenue',0):,.0f}",
                    "Gross Margin": f"{d.get('gross_margin',0)*100:.1f}%",
                    "Net Margin":   f"{d.get('net_margin',0)*100:.1f}%",
                    "Saved":        sc.get("ts", ""),
                })
            st.dataframe(pd.DataFrame(scen_rows), use_container_width=True, hide_index=True)

            # Load scenario back
            sc_names = [s.get("name", f"S{i+1}") for i, s in enumerate(scenarios)]
            sc2c1, sc2c2 = st.columns([3, 1])
            with sc2c1:
                sel_sc = st.selectbox("Load scenario", sc_names, key="deal_load_sc_sel")
            with sc2c2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("▶️ Load", key="deal_load_sc"):
                    idx = sc_names.index(sel_sc)
                    sc_obj = scenarios[idx]
                    st.session_state["deal_team"] = sc_obj.get("team", [])
                    st.toast(f"Loaded '{sel_sc}'", icon="▶️")
                    st.rerun(scope="fragment")
        except ImportError:
            for i, sc in enumerate(scenarios):
                d = safe_dict(sc.get("deal", {}))
                st.write(f"**{sc.get('name','')}** — Rev: ${d.get('actual_revenue',0):,.0f} | Net Margin: {d.get('net_margin',0)*100:.1f}%")

    # ── Rate Card Reference ─────────────────────────────────────────────
    with st.expander("📋 Full Rate Card Reference", expanded=False):
        _search = st.text_input("🔍 Search roles", placeholder="e.g. Backend, Architect, QA…", key="deal_rc_search")
        try:
            import pandas as pd
            rc_df_rows = []
            for loc, com, rol, ir, br in _RATE_ROWS:
                key_str = f"{loc} {com} {rol}".lower()
                if _search and _search.lower() not in key_str:
                    continue
                margin = (br - ir) / br * 100 if br > 0 else 0
                rc_df_rows.append({
                    "Location":   loc,
                    "Practice":   com,
                    "Role":       rol,
                    "Internal $/hr": ir,
                    "Bill $/hr":  br,
                    "Margin %":   f"{margin:.0f}%",
                    "Listed Role": f"{loc}-{com}-{rol}",
                })
            if rc_df_rows:
                st.dataframe(pd.DataFrame(rc_df_rows), use_container_width=True, hide_index=True, height=340)
            else:
                st.info("No roles match your search.")
        except ImportError:
            for loc, com, rol, ir, br in _RATE_ROWS:
                if not _search or _search.lower() in f"{loc} {com} {rol}".lower():
                    st.write(f"`{loc}-{com}-{rol}` — Internal: ${ir}/hr | Bill: ${br}/hr")
