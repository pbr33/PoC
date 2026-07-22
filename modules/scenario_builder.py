# ═══════════════════════════════════════════════════════════════════════
#  SCENARIO MODELLING — What-If Analysis Engine
#  Fragment-isolated • Scope ledger (Full/Modified/Deferred) • Phase control
#  Smart insights • Clone • Notes • Real-time KPI updates
# ═══════════════════════════════════════════════════════════════════════
from __future__ import annotations
import re
import io
from typing import Any

import streamlit as st

from .utils import safe_int, safe_str, safe_list, safe_dict, sc_text


# ── Palette ──────────────────────────────────────────────────────────
_PALETTE = {
    "baseline": {"bg": "#1e293b", "border": "#334155", "accent": "#94a3b8", "label": "Baseline"},
    0:          {"bg": "#0f2744", "border": "#1d4ed8", "accent": "#60a5fa", "label": "Scenario A"},
    1:          {"bg": "#14291a", "border": "#16a34a", "accent": "#4ade80", "label": "Scenario B"},
    2:          {"bg": "#2d1a00", "border": "#d97706", "accent": "#fbbf24", "label": "Scenario C"},
}
_SCENARIO_NAMES = ["Scenario A", "Scenario B", "Scenario C"]
_MAX_SCENARIOS  = 3


# ── Pure helpers ──────────────────────────────────────────────────────
def _parse_weeks(s: Any) -> float:
    s = str(s or "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*month", s, re.I)
    if m:
        return float(m.group(1)) * 4.33
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    return float(m.group(1)) if m else 12.0


def _infer_base_team(time_est: dict) -> int:
    roles: set = set()
    for ph in safe_list(time_est.get("phases")):
        for task in safe_list(ph.get("tasks")):
            r = safe_str(task.get("role"))
            if r:
                roles.add(r)
    return max(3, min(len(roles), 12))


def _risk_level(score: float) -> str:
    if score <= 3:  return "Low"
    if score <= 6:  return "Medium"
    if score <= 8:  return "High"
    return "Critical"


_RISK_COLORS = {
    "Low":      "#4ade80",
    "Medium":   "#facc15",
    "High":     "#f97316",
    "Critical": "#ef4444",
}

_HEAVY_KWS  = ["migrat", "integrat", "pipeline", "platform", "security", "auth",
               "api", "core", "engine", "data", "infrastructure", "architect"]
_MEDIUM_KWS = ["dashboard", "report", "workflow", "notification", "mobile", "portal",
               "monitor", "analyt", "search", "user management", "permission"]
_LIGHT_KWS  = ["document", "train", "export", "audit", "log", "support",
               "deploy", "test", "hypercare", "knowledge transfer", "handover"]


def _scope_weights(items: list) -> dict:
    """Return {label: fraction} where fractions sum to 1.0."""
    raw: dict = {}
    for item in items:
        label = (
            item.get("title") or item.get("description") or str(item)
            if isinstance(item, dict) else str(item)
        )
        low = label.lower()
        if any(k in low for k in _HEAVY_KWS):
            raw[label] = 3.0
        elif any(k in low for k in _MEDIUM_KWS):
            raw[label] = 2.0
        elif any(k in low for k in _LIGHT_KWS):
            raw[label] = 0.8
        else:
            raw[label] = 1.5
    total = sum(raw.values()) or 1
    return {k: v / total for k, v in raw.items()}


# ── Core computation ──────────────────────────────────────────────────
def _compute(results: dict, params: dict) -> dict:
    """
    Compute scenario KPIs from baseline results + params.

    Scope resolution priority (highest first):
      1. scope_ledger  — item-level Full/Modified/Deferred with effort %
      2. removed_items — simple deferral list (legacy)
      3. feature_scope — abstract percentage
    """
    time_est  = safe_dict(results.get("time_estimate"))
    cost_est  = safe_dict(results.get("cost_estimate"))
    risk_res  = safe_dict(results.get("risk_assessment"))

    base_hours    = safe_int(time_est.get("total_hours"), 500)
    base_risk     = float(risk_res.get("overall_score") or 5)
    base_team     = _infer_base_team(time_est)

    # Aggregate cloud costs from whichever provider key(s) are populated
    _cloud_svc_all = []
    for _ck in ("azure_costs", "aws_costs", "gcp_costs", "cloud_costs"):
        _cloud_svc_all.extend(safe_list(cost_est.get(_ck)))
    infra_monthly = sum(safe_int(safe_dict(s).get("monthly_cost", 0)) for s in _cloud_svc_all)
    third_monthly = sum(
        safe_int(safe_dict(t).get("monthly_cost", 0))
        for t in safe_list(cost_est.get("third_party_costs"))
    )
    base_infra_mo = infra_monthly + third_monthly

    # ── Scope ────────────────────────────────────────────────────────
    complexity    = float(params.get("complexity", 1.0))
    feature_scope = int(params.get("feature_scope", 100)) / 100
    engineers     = int(params.get("engineers", base_team))
    architects    = int(params.get("architects", 1))
    seniority     = params.get("seniority", "Mixed")
    contract_type = params.get("contract_type", "T&M")
    discount_pct  = int(params.get("discount", 0)) / 100
    buffer_pct    = int(params.get("buffer", 15)) / 100

    # Priority 1: scope_ledger (Full/Modified/Deferred per item)
    scope_ledger  = params.get("scope_ledger", {})
    removed_items = params.get("removed_items", [])

    if scope_ledger:
        in_scope_raw = safe_list(safe_dict(results.get("scope")).get("in_scope"))
        if in_scope_raw:
            in_scope_strs = [sc_text(x, "in_scope") for x in in_scope_raw]
            weights       = _scope_weights(in_scope_raw)
            total_eff     = sum(
                weights.get(item, 1.0 / len(in_scope_strs)) *
                scope_ledger.get(item, {"effort": 100}).get("effort", 100) / 100
                for item in in_scope_strs
            )
            feature_scope = max(0.15, total_eff)
    elif removed_items:
        # Priority 2: legacy removed_items
        in_scope_raw = safe_list(safe_dict(results.get("scope")).get("in_scope"))
        if in_scope_raw:
            weights     = _scope_weights(in_scope_raw)
            removed_pct = sum(weights.get(it, 1.0 / len(in_scope_raw)) for it in removed_items)
            feature_scope = max(0.20, 1.0 - removed_pct)

    # ── Phase factor ─────────────────────────────────────────────────
    phases_active = params.get("phases_active")
    if phases_active is not None:
        all_phases_list = safe_list(time_est.get("phases"))
        phases_removed  = max(0, len(all_phases_list) - len(phases_active))
    else:
        phases_removed = int(params.get("phases_removed", 0))
    phase_factor = max(0.3, 1.0 - phases_removed * 0.10)

    infra_discount_pct = int(params.get("infra_discount", 0)) / 100
    client_rate        = int(params.get("client_rate", 0))    # $/day per engineer

    # ── Hours ─────────────────────────────────────────────────────────
    scope_mult    = complexity * feature_scope * phase_factor
    senior_factor = {"Junior": 1.35, "Mixed": 1.00, "Senior": 0.82}[seniority]
    adj_hours     = max(40, int(base_hours * scope_mult * senior_factor))

    # ── Duration (Brooks' law) ────────────────────────────────────────
    eng_efficiency = 0.75
    effective_eng  = (
        base_team + (engineers - base_team) * 0.65
        if engineers > base_team else engineers
    )
    hours_per_week = max(1, effective_eng * 40 * eng_efficiency)
    duration_weeks = max(1.0, round(adj_hours / hours_per_week, 1))

    # ── Cost ──────────────────────────────────────────────────────────
    dev_daily  = {"Junior": 380, "Mixed": 580, "Senior": 850}[seniority]
    arch_daily = 950
    arch_bonus = 1.0 - min(0.15, architects * 0.04)

    dev_cost    = adj_hours * arch_bonus * (dev_daily / 8)
    arch_cost   = architects * duration_weeks * 5 * arch_daily
    infra_total = base_infra_mo * (duration_weeks / 4.33) * (1 - infra_discount_pct)

    with_buffer = (dev_cost + arch_cost + infra_total) * (1 + buffer_pct)
    if contract_type == "Fixed":
        with_buffer *= 1.12
    elif contract_type == "Hybrid":
        with_buffer *= 1.05
    final_cost = max(0, with_buffer * (1 - discount_pct))

    # ── Margin & Revenue ──────────────────────────────────────────────
    duration_months = duration_weeks / 4.33
    if client_rate > 0:
        revenue     = client_rate * engineers * duration_weeks * 5
        margin_pct  = round((revenue - final_cost) / revenue * 100, 1) if revenue > 0 else 0.0
        gross_profit = int(revenue - final_cost)
    else:
        revenue      = 0
        margin_pct   = 0.0
        gross_profit = 0

    monthly_burn = int(final_cost / max(1.0, duration_months))

    # ── Risk ──────────────────────────────────────────────────────────
    # Compressed timeline inflates risk further
    compression_risk = max(0.0, (12.0 - duration_weeks) * 0.08) if duration_weeks < 12 else 0.0
    new_risk = min(10.0, max(1.0,
        base_risk
        + (complexity - 1.0) * 2.5
        + {"Junior": +2.0, "Mixed": 0.0, "Senior": -1.2}[seniority]
        + max(0.0, (engineers - 10) * 0.25)
        + (feature_scope - 1.0) * 1.5
        + compression_risk
    ))

    return {
        "hours":          adj_hours,
        "duration_weeks": duration_weeks,
        "total_cost":     int(final_cost),
        "dev_cost":       int(dev_cost + arch_cost),
        "infra_cost":     int(infra_total),
        "monthly_burn":   monthly_burn,
        "risk_score":     round(new_risk, 1),
        "risk_level":     _risk_level(new_risk),
        "team_size":      engineers + architects,
        "engineers":      engineers,
        "architects":     architects,
        "seniority":      seniority,
        "contract_type":  contract_type,
        "discount":       int(params.get("discount", 0)),
        "buffer":         int(params.get("buffer", 15)),
        "revenue":        int(revenue),
        "margin_pct":     margin_pct,
        "gross_profit":   gross_profit,
        "infra_discount": int(params.get("infra_discount", 0)),
    }


def _default_params(results: dict) -> dict:
    time_est  = safe_dict(results.get("time_estimate"))
    base_team = _infer_base_team(time_est)
    return {
        "complexity":     1.0,
        "feature_scope":  100,
        "phases_removed": 0,
        "phases_active":  None,
        "engineers":      base_team,
        "architects":     1,
        "seniority":      "Mixed",
        "contract_type":  "T&M",
        "discount":       0,
        "buffer":         15,
        "infra_discount": 0,
        "client_rate":    0,
        "removed_items":  [],
        "scope_ledger":   {},
        "notes":          "",
    }


# ── Smart insights ────────────────────────────────────────────────────
def _smart_insights(
    kpi: dict,
    baseline: dict,
    params: dict,
    modified_items: list,
    deferred_items: list,
) -> list[str]:
    tips: list[str] = []

    cost_delta = kpi["total_cost"] - baseline.get("total_cost", 0)
    week_delta = kpi["duration_weeks"] - baseline.get("duration_weeks", 12)
    risk_delta = kpi["risk_score"] - baseline.get("risk_score", 5)

    if cost_delta < -10_000:
        tips.append(f"💰 **${abs(cost_delta):,.0f} saved** vs baseline — great negotiation lever with the client.")
    elif cost_delta > 10_000:
        tips.append(f"⚠️ This scenario costs **${cost_delta:,.0f} more** than baseline. Verify the value justifies it.")

    if week_delta < -2:
        tips.append(f"⚡ Delivers **{abs(week_delta):.1f} weeks faster** — strong if client has a deadline.")
    elif week_delta > 3:
        tips.append(f"⏳ Timeline extends by **{week_delta:.1f} weeks** — flag this to the client early.")

    if risk_delta < -1.0:
        tips.append(f"🛡️ Risk dropped from {baseline.get('risk_score',5):.1f} → {kpi['risk_score']:.1f}. Communicate this confidence to the client.")
    elif risk_delta > 1.5:
        tips.append(f"⚠️ Risk increased to **{kpi['risk_level']}** ({kpi['risk_score']:.1f}/10) — consider adding senior oversight.")

    if modified_items:
        tips.append(
            f"✏️ **{len(modified_items)} item(s) simplified** — confirm replacements with client to avoid scope misalignment later."
        )
    if deferred_items and kpi["risk_score"] > 6:
        tips.append("🔍 Deferring scope while risk is High/Critical — verify deferred items aren't blocking core delivery.")

    if params.get("seniority") == "Junior" and kpi["risk_score"] > 5:
        tips.append("💡 Junior team + elevated risk: consider adding at least one senior architect to de-risk.")

    if params.get("engineers", 5) > 14:
        tips.append("📐 Team > 14 engineers — Brooks' Law kicks in. Coordination cost may offset speed gains.")

    if params.get("discount", 0) >= 20:
        tips.append(f"🏷️ {params['discount']}% discount applied — ensure margin is still acceptable.")

    infra_disc = params.get("infra_discount", 0)
    if infra_disc >= 20:
        tips.append(f"☁️ {infra_disc}% infra discount modelled — validate with reserved instance commitments before committing.")

    if kpi.get("margin_pct", 0) > 0 and kpi["margin_pct"] < 15:
        tips.append(f"⚠️ Margin is thin at {kpi['margin_pct']:.1f}% — consider reducing discount or increasing client rate.")
    elif kpi.get("margin_pct", 0) >= 35:
        tips.append(f"✅ Strong margin at {kpi['margin_pct']:.1f}% — this scenario is commercially compelling.")

    return tips[:4]


# ── Excel export ──────────────────────────────────────────────────────
def generate_scenario_excel(baseline_kpi: dict, scenarios: list[dict]) -> bytes:
    try:
        import openpyxl
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return b""

    wb = openpyxl.Workbook()

    def _fill(h): return PatternFill("solid", fgColor=h.lstrip("#"))
    def _font(bold=False, color="FFFFFF", size=11): return Font(bold=bold, color=color.lstrip("#"), size=size)
    def _border():
        s = Side(style="thin", color="334155")
        return Border(left=s, right=s, top=s, bottom=s)

    ws = wb.active
    ws.title = "Scenario Comparison"
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B3"

    cols         = ["Metric", "Baseline"] + [s["name"] for s in scenarios]
    header_fills = ["1e293b", "1e3a5f", "14291a", "2d1a00", "2d0f1a"]

    for c, (col, hf) in enumerate(zip(cols, header_fills), 1):
        cell = ws.cell(row=1, column=c, value=col)
        cell.fill      = _fill(hf)
        cell.font      = _font(bold=True, size=12)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border    = _border()
        ws.row_dimensions[1].height = 28

    rows = [
        ("Total Hours",       "hours",          "{:,}",     "h"),
        ("Duration (weeks)",  "duration_weeks", "{:.1f}",   "wks"),
        ("Total Cost (USD)",  "total_cost",     "${:,.0f}", ""),
        ("Dev Cost (USD)",    "dev_cost",       "${:,.0f}", ""),
        ("Infra Cost (USD)",  "infra_cost",     "${:,.0f}", ""),
        ("Risk Score (/10)",  "risk_score",     "{:.1f}",   ""),
        ("Risk Level",        "risk_level",     "{}",       ""),
        ("Team Size",         "team_size",      "{}",       "ppl"),
        ("Engineers",         "engineers",      "{}",       ""),
        ("Architects",        "architects",     "{}",       ""),
    ]

    all_kpis  = [baseline_kpi] + [s["kpi"] for s in scenarios]
    lower_b   = {"hours", "duration_weeks", "total_cost", "dev_cost", "infra_cost", "risk_score"}

    for r, (label, key, fmt, unit) in enumerate(rows, 2):
        for c, kpi in enumerate(all_kpis, 1):
            val     = kpi.get(key, "—")
            display = fmt.format(val) + (f" {unit}" if unit else "") if val != "—" else "—"
            cell    = ws.cell(row=r + 1, column=c, value=display)
            cell.alignment = Alignment(horizontal="center")
            cell.border    = _border()
            cell.fill      = _fill("0f172a" if r % 2 == 0 else "1e293b")
            cell.font      = _font(color="e2e8f0")
            if c > 2 and key not in ("risk_level",):
                try:
                    delta = float(val) - float(baseline_kpi.get(key, 0))
                    if delta != 0:
                        good      = (delta < 0) if key in lower_b else (delta > 0)
                        cell.font = _font(color="4ade80" if good else "f87171")
                except Exception:
                    pass
        lc = ws.cell(row=r + 1, column=1, value=label)
        lc.fill      = _fill("0f172a")
        lc.font      = _font(bold=True, color="94a3b8")
        lc.alignment = Alignment(horizontal="left", indent=1)
        lc.border    = _border()

    ws.column_dimensions["A"].width = 22
    for i in range(2, len(cols) + 1):
        ws.column_dimensions[get_column_letter(i)].width = 18

    ws2 = wb.create_sheet("Scenario Parameters")
    ws2.sheet_view.showGridLines = False
    param_rows = [
        ("Complexity Multiplier", "complexity"),
        ("Feature Scope %",       "feature_scope"),
        ("Engineers",             "engineers"),
        ("Architects",            "architects"),
        ("Seniority Mix",         "seniority"),
        ("Contract Type",         "contract_type"),
        ("Discount %",            "discount"),
        ("Contingency Buffer %",  "buffer"),
    ]
    header2 = ["Parameter"] + [s["name"] for s in scenarios]
    for c, col in enumerate(header2, 1):
        cell = ws2.cell(row=1, column=c, value=col)
        cell.fill      = _fill("1e3a5f")
        cell.font      = _font(bold=True)
        cell.alignment = Alignment(horizontal="center")
        cell.border    = _border()
    for r, (label, key) in enumerate(param_rows, 2):
        lc = ws2.cell(row=r, column=1, value=label)
        lc.fill      = _fill("0f172a")
        lc.font      = _font(bold=True, color="94a3b8")
        lc.border    = _border()
        lc.alignment = Alignment(horizontal="left", indent=1)
        for c, sc in enumerate(scenarios, 2):
            cell = ws2.cell(row=r, column=c, value=sc["params"].get(key, "—"))
            cell.fill      = _fill("1e293b" if r % 2 == 0 else "0f172a")
            cell.font      = _font(color="e2e8f0")
            cell.alignment = Alignment(horizontal="center")
            cell.border    = _border()
    ws2.column_dimensions["A"].width = 26
    for i in range(2, len(header2) + 1):
        ws2.column_dimensions[get_column_letter(i)].width = 20

    # Scope ledger sheet
    ws3 = wb.create_sheet("Scope Details")
    ws3.sheet_view.showGridLines = False
    ledger_header = ["Scope Item", "Weight"] + [
        f"{s['name']} — Status" for s in scenarios
    ] + [f"{s['name']} — Replacement" for s in scenarios]
    for c, col in enumerate(ledger_header, 1):
        cell = ws3.cell(row=1, column=c, value=col)
        cell.fill      = _fill("1e3a5f")
        cell.font      = _font(bold=True, size=10)
        cell.alignment = Alignment(horizontal="center")
        cell.border    = _border()

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── Delta helper ──────────────────────────────────────────────────────
def _delta_html(base_val: float, new_val: float, lower_better: bool = True) -> str:
    if base_val == 0:
        return '<span style="color:#475569;font-size:.7rem">— baseline</span>'
    pct  = (new_val - base_val) / abs(base_val) * 100
    if abs(pct) < 0.5:
        return '<span style="color:#475569;font-size:.7rem">— no change</span>'
    good  = (new_val < base_val) if lower_better else (new_val > base_val)
    color = "#4ade80" if good else "#f87171"
    arrow = "▼" if new_val < base_val else "▲"
    label = ("saved" if good else "more") if lower_better else ("up" if good else "down")
    return (
        f'<span style="color:{color};font-size:.72rem;font-weight:700">'
        f'{arrow} {abs(pct):.1f}% {label}</span>'
    )


# ── CSS ───────────────────────────────────────────────────────────────
_CSS = """
<style>
@keyframes kpi-pop {
  0%  { transform: scale(.88) translateY(6px); opacity: 0; }
  100%{ transform: scale(1)   translateY(0);   opacity: 1; }
}
@keyframes slide-up {
  0%  { transform: translateY(14px); opacity: 0; }
  100%{ transform: translateY(0);    opacity: 1; }
}
@keyframes glow-pulse {
  0%,100%{ box-shadow:0 0 0 0 rgba(96,165,250,0); }
  50%     { box-shadow:0 0 0 4px rgba(96,165,250,.18); }
}

.sc-header {
    font-size: 1.55rem; font-weight: 800;
    background: linear-gradient(130deg, #60a5fa 0%, #a78bfa 50%, #34d399 100%);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 2px;
}
.sc-sub { font-size: .84rem; color: #64748b; margin-bottom: 18px; line-height: 1.5; }

/* KPI cards */
.kpi-card {
    background: linear-gradient(150deg, rgba(15,23,42,.97), rgba(30,41,59,.75));
    border: 1px solid rgba(255,255,255,.06);
    border-radius: 16px; padding: 18px 20px 14px;
    text-align: center; position: relative; overflow: hidden;
    animation: kpi-pop .35s cubic-bezier(.34,1.56,.64,1) both;
    transition: transform .15s ease, box-shadow .15s ease;
}
.kpi-card:hover { transform: translateY(-2px); box-shadow: 0 10px 36px rgba(0,0,0,.45); }
.kpi-card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: var(--acc, #60a5fa);
    box-shadow: 0 0 14px var(--acc, #60a5fa);
}
.kpi-num  { font-size: 1.75rem; font-weight: 900; line-height: 1; letter-spacing: -.02em; }
.kpi-unit { font-size: .85rem;  font-weight: 500; color: #475569; margin-left: 2px; }
.kpi-lbl  { font-size: .63rem; color: #64748b; margin-top: 5px; text-transform: uppercase; letter-spacing: .12em; font-weight: 700; }
.kpi-delta{ margin-top: 7px; min-height: 16px; }

/* Section headers */
.sec-hdr {
    font-size: .67rem; font-weight: 800; color: #475569;
    text-transform: uppercase; letter-spacing: .13em;
    margin: 10px 0 10px; padding-bottom: 5px;
    border-bottom: 1px solid rgba(51,65,85,.7);
    display: flex; align-items: center; gap: 6px;
}

/* Scope info bar */
.scope-bar {
    background: rgba(96,165,250,.07);
    border: 1px solid rgba(96,165,250,.18);
    border-radius: 8px; padding: 8px 14px; margin: 8px 0 12px;
    font-size: .76rem; color: #93c5fd;
    display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
}
.s-pill {
    border-radius: 20px; padding: 1px 9px;
    font-size: .68rem; font-weight: 700;
}
.s-full { background: rgba(74,222,128,.12); color: #4ade80; }
.s-mod  { background: rgba(251,191,36,.12);  color: #fbbf24; }
.s-def  { background: rgba(248,113,113,.12); color: #f87171; }

/* Impact card */
.impact-card {
    background: linear-gradient(135deg, rgba(15,23,42,.95), rgba(30,41,59,.8));
    border: 1px solid #1e3a5f; border-left: 3px solid #60a5fa;
    border-radius: 12px; padding: 14px 18px; margin: 14px 0;
    animation: slide-up .3s ease both;
}
.impact-title {
    font-size: .7rem; font-weight: 800; color: #60a5fa;
    text-transform: uppercase; letter-spacing: .1em; margin-bottom: 10px;
}
.impact-grid {
    display: grid; grid-template-columns: repeat(auto-fit, minmax(110px,1fr)); gap: 10px;
}
.impact-stat { background: rgba(15,23,42,.65); border-radius: 9px; padding: 10px; text-align: center; }
.impact-val  { font-size: 1.15rem; font-weight: 800; }
.impact-lbl  { font-size: .62rem; color: #64748b; text-transform: uppercase; letter-spacing: .08em; margin-top: 2px; }
.i-green  { color: #4ade80; }
.i-amber  { color: #f97316; }
.i-blue   { color: #60a5fa; }
.i-yellow { color: #fbbf24; }

/* Insight pills */
.insight-box {
    background: rgba(30,41,59,.6);
    border: 1px solid #1e3a5f; border-radius: 10px;
    padding: 10px 14px; margin-bottom: 10px;
    font-size: .8rem; color: #cbd5e1; line-height: 1.55;
    animation: slide-up .35s ease both;
}

/* Comparison table */
.cmp-table { width: 100%; border-collapse: collapse; font-size: .8rem; }
.cmp-table th {
    background: #080d1a; color: #475569; padding: 10px 14px; text-align: left;
    border-bottom: 2px solid #1e3a5f;
    font-size: .66rem; text-transform: uppercase; letter-spacing: .1em;
}
.cmp-table td {
    padding: 9px 14px; border-bottom: 1px solid rgba(30,41,59,.8);
    color: #e2e8f0; vertical-align: middle;
}
.cmp-table tr:hover td { background: rgba(30,41,59,.35); }
.b-good { background: rgba(74,222,128,.14); color: #4ade80; border-radius: 5px; padding: 2px 8px; font-size: .68rem; font-weight: 700; }
.b-bad  { background: rgba(248,113,113,.14); color: #f87171; border-radius: 5px; padding: 2px 8px; font-size: .68rem; font-weight: 700; }
.b-base { background: rgba(148,163,184,.1);  color: #94a3b8; border-radius: 5px; padding: 2px 8px; font-size: .68rem; }
.r-badge { border-radius: 5px; padding: 2px 9px; font-size: .72rem; font-weight: 700; }

/* Modifier tag */
.mod-tag {
    display: inline-block; font-size: .62rem; color: #fbbf24;
    background: rgba(251,191,36,.1); border-radius: 4px;
    padding: 1px 6px; margin-left: 4px; vertical-align: middle;
}

/* Empty state */
.empty-state {
    text-align: center; padding: 60px 0;
    background: linear-gradient(135deg, rgba(15,23,42,.6), rgba(30,41,59,.4));
    border: 1px dashed #1e3a5f; border-radius: 18px;
    animation: slide-up .4s ease both;
}

/* Best-scenario banner */
.best-banner {
    background: linear-gradient(135deg, rgba(52,211,153,.08), rgba(96,165,250,.06));
    border: 1px solid rgba(52,211,153,.25); border-radius: 10px;
    padding: 10px 16px; margin-bottom: 16px;
    font-size: .8rem; color: #34d399; font-weight: 600;
    display: flex; align-items: center; gap: 10px;
}
</style>
"""


# ── Best-scenario selector ────────────────────────────────────────────
def _best_scenario_idx(baseline_kpi: dict, scenarios: list[dict]) -> int | None:
    if not scenarios:
        return None
    scored = []
    b_cost = baseline_kpi.get("total_cost", 1) or 1
    b_risk = baseline_kpi.get("risk_score", 5)
    b_wks  = baseline_kpi.get("duration_weeks", 12)
    for i, sc in enumerate(scenarios):
        k = sc["kpi"]
        saving_pct = (b_cost - k["total_cost"]) / b_cost * 100
        risk_delta = k["risk_score"] - b_risk
        week_delta = k["duration_weeks"] - b_wks
        score = saving_pct * 1.0 + (week_delta * -2.0) + (risk_delta * -4.0)
        scored.append((score, i))
    scored.sort(reverse=True)
    if scored[0][0] > 3:
        return scored[0][1]
    return None


# ── Scope data editor ─────────────────────────────────────────────────
def _render_scope_editor(
    tab_i: int,
    in_scope_all: list[str],
    in_scope_raw: list,
    params: dict,
) -> tuple[dict, list, list, int]:
    """
    Renders the scope data editor and returns
    (new_ledger, deferred_items, modified_items, derived_scope_pct).
    """
    if not in_scope_all:
        st.caption("No scope items found — run pipeline first.")
        return {}, [], [], 100

    try:
        import pandas as pd
    except ImportError:
        st.caption("pandas not available — scope editor disabled.")
        return {}, [], [], 100

    scope_ledger = params.get("scope_ledger", {})

    df_data = []
    for item in in_scope_all:
        ld    = scope_ledger.get(item, {})
        state = ld.get("state", "Full")
        if state == "Deferred":
            effort = 0
        elif state == "Modified":
            effort = ld.get("effort", 50)
        else:
            effort = 100
        df_data.append({
            "Scope Item":             item,
            "Status":                 state,
            "Replacement / Simplified As": ld.get("replacement", ""),
            "Effort %":               effort,
        })

    # Bulk action toolbar
    _ba1, _ba2, _ba3, _ = st.columns([1, 1.2, 1.4, 3])
    with _ba1:
        if st.button("✓ All Full", key=f"bulk_full_{tab_i}", help="Reset all items to Full scope"):
            params["scope_ledger"] = {}
            st.session_state.pop(f"sc_editor_{tab_i}", None)
            st.rerun(scope="fragment")
    with _ba2:
        if st.button("✗ Defer All", key=f"bulk_defer_{tab_i}", help="Defer all scope items"):
            params["scope_ledger"] = {
                item: {"state": "Deferred", "replacement": "", "effort": 0}
                for item in in_scope_all
            }
            st.session_state.pop(f"sc_editor_{tab_i}", None)
            st.rerun(scope="fragment")
    with _ba3:
        if st.button("⊘ Defer Non-Core", key=f"bulk_noncore_{tab_i}",
                     help="Defer light/medium items, keep heavy-weight core items"):
            weights = _scope_weights(in_scope_raw)
            new_led = {}
            for item in in_scope_all:
                w = weights.get(item, 0.1)
                if w < 0.08:
                    new_led[item] = {"state": "Deferred", "replacement": "", "effort": 0}
                else:
                    new_led[item] = params.get("scope_ledger", {}).get(
                        item, {"state": "Full", "replacement": "", "effort": 100}
                    )
            params["scope_ledger"] = new_led
            st.session_state.pop(f"sc_editor_{tab_i}", None)
            st.rerun(scope="fragment")

    st.markdown(
        "<div style='font-size:.72rem;color:#475569;margin-bottom:6px'>"
        "Set each item to <b>Full</b> (baseline effort), "
        "<b>Modified</b> (lighter version — set % and describe), or "
        "<b>Deferred</b> (excluded from this scenario)."
        "</div>",
        unsafe_allow_html=True,
    )

    edited = st.data_editor(
        pd.DataFrame(df_data),
        column_config={
            "Scope Item": st.column_config.TextColumn(
                "Scope Item", disabled=True, width="large",
            ),
            "Status": st.column_config.SelectboxColumn(
                "Status",
                options=["Full", "Modified", "Deferred"],
                required=True,
                width="small",
                help="Full = 100% effort | Modified = simplified version | Deferred = excluded",
            ),
            "Replacement / Simplified As": st.column_config.TextColumn(
                "Replacement / Simplified As",
                width="large",
                help="Describe what replaces this item when Status = Modified (e.g. 'Read-only API instead of full sync')",
            ),
            "Effort %": st.column_config.NumberColumn(
                "Effort %",
                min_value=0, max_value=100, step=5, format="%d%%",
                width="small",
                help="Modified items only: effort vs original (5–95%). Full=100, Deferred=0.",
            ),
        },
        key=f"sc_editor_{tab_i}",
        hide_index=True,
        width="stretch",
        num_rows="fixed",
        height=min(65 + len(in_scope_all) * 37, 520),
    )

    # Parse edited df → ledger
    new_ledger:    dict  = {}
    deferred_items: list = []
    modified_items: list = []

    for i_row in range(len(edited)):
        item_name   = in_scope_all[i_row]
        row         = edited.iloc[i_row]
        state       = str(row.get("Status", "Full"))
        replacement = str(row.get("Replacement / Simplified As", "") or "").strip()
        effort_raw  = row.get("Effort %", 100)
        try:
            effort = int(effort_raw or 0)
        except (ValueError, TypeError):
            effort = 100

        if state == "Full":
            effort = 100
        elif state == "Deferred":
            effort = 0
            deferred_items.append(item_name)
        elif state == "Modified":
            effort = max(5, min(95, effort))
            modified_items.append(item_name)

        new_ledger[item_name] = {
            "state":       state,
            "replacement": replacement,
            "effort":      effort,
        }

    # Derived scope %
    weights   = _scope_weights(in_scope_raw)
    total_eff = sum(
        weights.get(item, 1.0 / len(in_scope_all)) *
        new_ledger.get(item, {"effort": 100}).get("effort", 100) / 100
        for item in in_scope_all
    )
    derived_scope_pct = max(10, min(150, int(total_eff * 100)))

    # Summary bar
    n_full = sum(1 for d in new_ledger.values() if d["state"] == "Full")
    n_mod  = sum(1 for d in new_ledger.values() if d["state"] == "Modified")
    n_def  = sum(1 for d in new_ledger.values() if d["state"] == "Deferred")

    pills = ""
    if n_full: pills += f'<span class="s-pill s-full">{n_full} Full</span>'
    if n_mod:  pills += f'<span class="s-pill s-mod">{n_mod} Modified</span>'
    if n_def:  pills += f'<span class="s-pill s-def">{n_def} Deferred</span>'

    st.markdown(
        f'<div class="scope-bar">'
        f'<span>📊</span>'
        f'<span><b>{derived_scope_pct}%</b> effective scope</span>'
        f'<span style="color:#1e3a5f">|</span>'
        f'{pills}'
        f'</div>',
        unsafe_allow_html=True,
    )

    return new_ledger, deferred_items, modified_items, derived_scope_pct


# ── Main render (fragment) ────────────────────────────────────────────
@st.fragment
def render_scenario_tab():
    """
    Fully fragment-isolated scenario modelling.
    - Scope data editor: Full / Modified (with replacement + effort %) / Deferred
    - Phase multiselect from actual phase names
    - Scenario notes
    - Clone scenario
    - Smart insights panel
    - Best-scenario recommendation
    - Comparison table with scope details
    - Radar + bar charts
    - Excel export
    """
    results = st.session_state.get("processing_results", {})
    if not results:
        st.info("Run the pipeline first to enable scenario modelling.")
        return

    time_est   = safe_dict(results.get("time_estimate"))
    base_team  = _infer_base_team(time_est)
    phases_all = [
        p.get("name") or p.get("phase") or f"Phase {i + 1}"
        for i, p in enumerate(safe_list(time_est.get("phases")))
    ]

    in_scope_raw = safe_list(safe_dict(results.get("scope")).get("in_scope"))
    in_scope_all = [sc_text(x, "in_scope") for x in in_scope_raw]

    if "scenarios" not in st.session_state:
        st.session_state.scenarios = []
    if "_sc_active" not in st.session_state:
        st.session_state._sc_active = 0

    scenarios: list[dict] = st.session_state.scenarios
    default_p    = _default_params(results)
    baseline_kpi = _compute(results, default_p)

    st.markdown(_CSS, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────
    st.markdown('<div class="sc-header">🔀 Scenario Modelling</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sc-sub">'
        'Edit scope items (Full / Modified / Deferred), move sliders, compare results — '
        'everything updates in real-time. Build up to 3 what-if scenarios.'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Toolbar ───────────────────────────────────────────────────────
    tc1, tc2, tc3, tc4, _ = st.columns([1, 1, 1, 1, 2])

    with tc1:
        if st.button(
            "＋ New Scenario",
            disabled=len(scenarios) >= _MAX_SCENARIOS,
            width="stretch",
            key="sc_add",
            type="primary",
            help=f"Add scenario ({len(scenarios)}/{_MAX_SCENARIOS})",
        ):
            idx = len(scenarios)
            st.session_state.scenarios.append({
                "name":   _SCENARIO_NAMES[idx],
                "params": _default_params(results).copy(),
                "kpi":    baseline_kpi.copy(),
                "notes":  "",
            })
            st.session_state._sc_active = idx
            st.rerun(scope="fragment")

    with tc2:
        if scenarios and st.button("🗑 Remove", width="stretch", key="sc_remove",
                                   help="Delete the active scenario"):
            active = min(st.session_state._sc_active, len(scenarios) - 1)
            # Clear editor widget state
            for k in [f"sc_editor_{active}"]:
                st.session_state.pop(k, None)
            st.session_state.scenarios.pop(active)
            st.session_state._sc_active = max(0, active - 1)
            st.rerun(scope="fragment")

    with tc3:
        if scenarios and st.button("↺ Reset", width="stretch", key="sc_reset",
                                   help="Reset active scenario to baseline params"):
            active = min(st.session_state._sc_active, len(scenarios) - 1)
            st.session_state.scenarios[active]["params"] = _default_params(results).copy()
            st.session_state.scenarios[active]["kpi"]    = baseline_kpi.copy()
            st.session_state.scenarios[active]["notes"]  = ""
            # Clear editor so it re-initialises from clean params
            st.session_state.pop(f"sc_editor_{active}", None)
            st.rerun(scope="fragment")

    with tc4:
        can_clone = scenarios and len(scenarios) < _MAX_SCENARIOS
        if can_clone and st.button("⎘ Clone Active", width="stretch", key="sc_clone",
                                   help="Duplicate active scenario as a new one"):
            active = min(st.session_state._sc_active, len(scenarios) - 1)
            src    = scenarios[active]
            new_idx = len(scenarios)
            import copy
            st.session_state.scenarios.append({
                "name":   src["name"] + " (Copy)",
                "params": copy.deepcopy(src["params"]),
                "kpi":    src["kpi"].copy(),
                "notes":  src.get("notes", ""),
            })
            st.session_state._sc_active = new_idx
            st.rerun(scope="fragment")

    # ── Empty state ───────────────────────────────────────────────────
    if not scenarios:
        st.markdown("""
        <div class="empty-state">
            <div style="font-size:3.4rem;margin-bottom:14px">🔀</div>
            <div style="font-size:1.1rem;font-weight:700;color:#64748b;margin-bottom:6px">
                No scenarios yet
            </div>
            <div style="font-size:.85rem;color:#475569">
                Click <strong style="color:#60a5fa">＋ New Scenario</strong>
                to build your first what-if analysis
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Scenario tabs ─────────────────────────────────────────────────
    chosen_tabs = st.tabs([s["name"] for s in scenarios])

    for tab_i, sc_tab in enumerate(chosen_tabs):
        with sc_tab:
            sc     = scenarios[tab_i]
            params = sc["params"]
            pal    = _PALETTE[tab_i]
            st.session_state._sc_active = tab_i

            # Name editor + quick presets
            _nr, _pr = st.columns([2, 2])
            with _nr:
                new_name = st.text_input(
                    "Scenario name",
                    value=sc["name"],
                    key=f"sc_name_{tab_i}",
                    label_visibility="collapsed",
                    placeholder="Scenario name…",
                )
                if new_name and new_name != sc["name"]:
                    st.session_state.scenarios[tab_i]["name"] = new_name
                    st.rerun(scope="fragment")
            with _pr:
                _PRESETS = {
                    "— Custom —": None,
                    "⚡ Lean MVP": {
                        "complexity": 0.75, "feature_scope": 70, "engineers": max(2, base_team - 1),
                        "architects": 1, "seniority": "Mixed", "contract_type": "T&M",
                        "discount": 0, "buffer": 15, "infra_discount": 15, "client_rate": params.get("client_rate", 0),
                    },
                    "🚀 Fast Track": {
                        "complexity": 1.0, "feature_scope": 100, "engineers": min(20, base_team + 3),
                        "architects": 2, "seniority": "Senior", "contract_type": "T&M",
                        "discount": 0, "buffer": 10, "infra_discount": 0, "client_rate": params.get("client_rate", 0),
                    },
                    "💰 Budget Saver": {
                        "complexity": 0.9, "feature_scope": 80, "engineers": max(2, base_team - 2),
                        "architects": 1, "seniority": "Junior", "contract_type": "T&M",
                        "discount": 15, "buffer": 20, "infra_discount": 25, "client_rate": params.get("client_rate", 0),
                    },
                    "🏢 Enterprise": {
                        "complexity": 1.3, "feature_scope": 100, "engineers": min(20, base_team + 2),
                        "architects": 2, "seniority": "Senior", "contract_type": "Fixed",
                        "discount": 0, "buffer": 25, "infra_discount": 0, "client_rate": params.get("client_rate", 0),
                    },
                }
                chosen_preset = st.selectbox(
                    "Quick preset",
                    options=list(_PRESETS.keys()),
                    key=f"sc_preset_{tab_i}",
                    label_visibility="collapsed",
                )
                if _PRESETS[chosen_preset] is not None:
                    preset_p = _PRESETS[chosen_preset]
                    for _pk, _pv in preset_p.items():
                        params[_pk] = _pv
                    params["scope_ledger"]  = {}
                    params["phases_active"] = None
                    st.session_state.scenarios[tab_i]["params"] = params
                    st.session_state.pop(f"sc_editor_{tab_i}", None)
                    # Reset selectbox to Custom after applying
                    st.session_state[f"sc_preset_{tab_i}"] = "— Custom —"
                    st.rerun(scope="fragment")

            # ── SCOPE MANAGEMENT (full width) ─────────────────────
            st.markdown(
                '<div class="sec-hdr"><span style="font-size:.9rem">📐</span> Scope Management</div>',
                unsafe_allow_html=True,
            )

            new_ledger, deferred_items, modified_items, derived_scope_pct = _render_scope_editor(
                tab_i, in_scope_all, in_scope_raw, params
            )

            # ── 3-column levers ───────────────────────────────────
            lcol, mcol, rcol = st.columns(3, gap="medium")

            with lcol:
                st.markdown(
                    '<div class="sec-hdr"><span style="font-size:.9rem">👥</span> Team Levers</div>',
                    unsafe_allow_html=True,
                )
                engineers = st.slider(
                    "Engineers",
                    min_value=1, max_value=20, step=1,
                    value=int(params.get("engineers", base_team)),
                    key=f"sl_eng_{tab_i}",
                    help="More engineers = shorter timeline (Brooks' law: diminishing returns past ~10).",
                )
                architects = st.slider(
                    "Architects",
                    min_value=0, max_value=4, step=1,
                    value=int(params.get("architects", 1)),
                    key=f"sl_arch_{tab_i}",
                    help="Architects reduce rework hours but add daily cost.",
                )
                seniority = st.select_slider(
                    "Seniority mix",
                    options=["Junior", "Mixed", "Senior"],
                    value=params.get("seniority", "Mixed"),
                    key=f"sl_sen_{tab_i}",
                    help="Senior: faster delivery, higher day rate, lower risk.",
                )
                complexity = st.slider(
                    "Complexity multiplier",
                    min_value=0.5, max_value=2.0, step=0.05,
                    value=float(params.get("complexity", 1.0)),
                    key=f"sl_cplx_{tab_i}",
                    format="%.2fx",
                    help="Technical complexity vs baseline. Affects hours and risk.",
                )

            with mcol:
                st.markdown(
                    '<div class="sec-hdr"><span style="font-size:.9rem">💰</span> Pricing Levers</div>',
                    unsafe_allow_html=True,
                )
                contract_type = st.radio(
                    "Contract type",
                    options=["T&M", "Fixed", "Hybrid"],
                    index=["T&M", "Fixed", "Hybrid"].index(params.get("contract_type", "T&M")),
                    key=f"sl_ctype_{tab_i}",
                    horizontal=True,
                    help="Fixed adds 12% risk premium. Hybrid adds 5%.",
                )
                discount = st.slider(
                    "Discount %",
                    min_value=0, max_value=30, step=1,
                    value=int(params.get("discount", 0)),
                    key=f"sl_disc_{tab_i}",
                    help="Applied after contingency buffer.",
                )
                buffer = st.slider(
                    "Contingency buffer %",
                    min_value=5, max_value=35, step=5,
                    value=int(params.get("buffer", 15)),
                    key=f"sl_buf_{tab_i}",
                    help="Risk buffer added before applying discount.",
                )
                infra_discount = st.slider(
                    "Infra cost reduction %",
                    min_value=0, max_value=40, step=5,
                    value=int(params.get("infra_discount", 0)),
                    key=f"sl_infrd_{tab_i}",
                    help="Simulate reserved instances, right-sizing or negotiated discounts (0–40%).",
                )
                client_rate = st.number_input(
                    "Client rate ($/day/engineer)",
                    min_value=0, max_value=5000, step=50,
                    value=int(params.get("client_rate", 0)),
                    key=f"sl_crate_{tab_i}",
                    help="Set to calculate revenue, margin %, and gross profit. Leave 0 to skip.",
                )

            with rcol:
                st.markdown(
                    '<div class="sec-hdr"><span style="font-size:.9rem">📅</span> Phases &amp; Notes</div>',
                    unsafe_allow_html=True,
                )

                if phases_all:
                    prev_active = params.get("phases_active") or phases_all
                    active_phases = st.multiselect(
                        "Include phases",
                        options=phases_all,
                        default=[p for p in prev_active if p in phases_all],
                        key=f"sc_phases_{tab_i}",
                        placeholder="Select phases to include…",
                        help="Deselect phases to exclude them — reduces hours and duration proportionally.",
                    )
                    phases_removed_count = len(phases_all) - len(active_phases)
                    if phases_removed_count > 0:
                        st.markdown(
                            f'<div style="font-size:.72rem;color:#f97316;margin-top:2px">'
                            f'⚠️ {phases_removed_count} phase{"s" if phases_removed_count > 1 else ""} excluded '
                            f'(−{phases_removed_count * 10}% effort)</div>',
                            unsafe_allow_html=True,
                        )
                else:
                    active_phases = []
                    phases_removed_count = 0

                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

                notes = st.text_area(
                    "Scenario notes",
                    value=sc.get("notes", ""),
                    key=f"sc_notes_{tab_i}",
                    placeholder="Rationale, assumptions, client constraints…",
                    height=90,
                    label_visibility="collapsed",
                )
                if notes != sc.get("notes", ""):
                    st.session_state.scenarios[tab_i]["notes"] = notes

            # ── Compute KPIs ──────────────────────────────────────
            new_params = {
                "complexity":     complexity,
                "feature_scope":  derived_scope_pct,
                "phases_removed": phases_removed_count,
                "phases_active":  active_phases if phases_all else None,
                "engineers":      engineers,
                "architects":     architects,
                "seniority":      seniority,
                "contract_type":  contract_type,
                "discount":       discount,
                "buffer":         buffer,
                "infra_discount": infra_discount,
                "client_rate":    client_rate,
                "removed_items":  deferred_items,
                "scope_ledger":   new_ledger,
            }
            kpi = _compute(results, new_params)
            st.session_state.scenarios[tab_i]["params"] = new_params
            st.session_state.scenarios[tab_i]["kpi"]    = kpi

            # ── Impact banner ─────────────────────────────────────
            if deferred_items or modified_items or phases_removed_count > 0:
                cost_save  = baseline_kpi.get("total_cost", 0) - kpi.get("total_cost", 0)
                week_save  = baseline_kpi.get("duration_weeks", 0) - kpi.get("duration_weeks", 0)
                risk_now   = kpi.get("risk_level", "Medium")
                rc         = _RISK_COLORS.get(risk_now, "#94a3b8")

                cost_cls   = "i-green" if cost_save > 0 else "i-amber"
                week_cls   = "i-green" if week_save > 0 else "i-amber"

                changes = []
                if deferred_items: changes.append(f"{len(deferred_items)} deferred")
                if modified_items:  changes.append(f"{len(modified_items)} modified")
                if phases_removed_count: changes.append(f"{phases_removed_count} phase(s) removed")

                st.markdown(
                    f'<div class="impact-card">'
                    f'<div class="impact-title">💡 Client Impact — {", ".join(changes)}</div>'
                    f'<div class="impact-grid">'
                    f'<div class="impact-stat">'
                    f'  <div class="impact-val {cost_cls}">{"+" if cost_save < 0 else ""}{"−" if cost_save > 0 else ""}${abs(cost_save):,.0f}</div>'
                    f'  <div class="impact-lbl">{"Cost Saving" if cost_save > 0 else "Extra Cost"}</div>'
                    f'</div>'
                    f'<div class="impact-stat">'
                    f'  <div class="impact-val {week_cls}">{abs(week_save):.1f} wks</div>'
                    f'  <div class="impact-lbl">{"Faster" if week_save > 0 else "Longer"}</div>'
                    f'</div>'
                    f'<div class="impact-stat">'
                    f'  <div class="impact-val" style="color:{rc}">{risk_now}</div>'
                    f'  <div class="impact-lbl">Risk Level</div>'
                    f'</div>'
                    f'<div class="impact-stat">'
                    f'  <div class="impact-val i-blue">{derived_scope_pct}%</div>'
                    f'  <div class="impact-lbl">Scope Active</div>'
                    f'</div>'
                    f'</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                # Show modified item details
                if modified_items:
                    mod_lines = ""
                    for it in modified_items:
                        repl = new_ledger.get(it, {}).get("replacement", "")
                        eff  = new_ledger.get(it, {}).get("effort", 50)
                        repl_text = f" → {repl}" if repl else ""
                        mod_lines += (
                            f'<div style="font-size:.72rem;color:#fbbf24;margin-bottom:3px">'
                            f'✏️ <b>{it[:55]}</b>{repl_text} '
                            f'<span style="color:#94a3b8">({eff}% effort)</span>'
                            f'</div>'
                        )
                    st.markdown(
                        f'<div style="background:rgba(251,191,36,.05);border:1px solid rgba(251,191,36,.15);'
                        f'border-radius:8px;padding:10px 14px;margin-top:6px">'
                        f'<div style="font-size:.65rem;font-weight:800;color:#fbbf24;text-transform:uppercase;'
                        f'letter-spacing:.1em;margin-bottom:6px">Modified Scope Items</div>'
                        f'{mod_lines}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # ── Smart insights ─────────────────────────────────────
            insights = _smart_insights(kpi, baseline_kpi, new_params, modified_items, deferred_items)
            if insights:
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                for tip in insights:
                    st.markdown(
                        f'<div class="insight-box">{tip}</div>',
                        unsafe_allow_html=True,
                    )

            # ── KPI cards ─────────────────────────────────────────
            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            kc1, kc2, kc3, kc4, kc5 = st.columns(5)
            kpi_defs = [
                (kc1, "Total Hours",    f"{kpi['hours']:,}",             "hrs", "hours",          True,  "#60a5fa"),
                (kc2, "Duration",       f"{kpi['duration_weeks']:.1f}",  "wks", "duration_weeks", True,  "#a78bfa"),
                (kc3, "Total Cost",     f"${kpi['total_cost']:,.0f}",    "",    "total_cost",      True,  "#34d399"),
                (kc4, "Monthly Burn",   f"${kpi['monthly_burn']:,.0f}",  "/mo", "monthly_burn",   True,  "#f97316"),
                (kc5, "Risk Score",     f"{kpi['risk_score']}/10",       "",    "risk_score",      True,
                 _RISK_COLORS.get(kpi["risk_level"], "#94a3b8")),
            ]
            for col, label, disp, unit, key, lb, color in kpi_defs:
                delta = _delta_html(baseline_kpi.get(key, 0), kpi.get(key, 0), lb)
                with col:
                    st.markdown(
                        f'<div class="kpi-card" style="--acc:{color}">'
                        f'<div class="kpi-num" style="color:{color}">'
                        f'{disp}<span class="kpi-unit">{unit}</span>'
                        f'</div>'
                        f'<div class="kpi-lbl">{label}</div>'
                        f'<div class="kpi-delta">{delta}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # ── Secondary metrics ─────────────────────────────────
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            _sec_cols = st.columns(5)
            with _sec_cols[0]:
                st.metric("Dev Cost", f"${kpi['dev_cost']:,.0f}",
                          delta=f"${kpi['dev_cost']-baseline_kpi['dev_cost']:+,.0f}")
            with _sec_cols[1]:
                st.metric("Infra Cost", f"${kpi['infra_cost']:,.0f}",
                          delta=f"${kpi['infra_cost']-baseline_kpi['infra_cost']:+,.0f}",
                          help=f"After {new_params.get('infra_discount', 0)}% infra discount" if new_params.get('infra_discount') else None)
            with _sec_cols[2]:
                rc = _RISK_COLORS.get(kpi["risk_level"], "#94a3b8")
                st.markdown(
                    f'<div style="padding-top:4px">'
                    f'<div style="font-size:.75rem;color:#64748b;margin-bottom:5px">Risk Level</div>'
                    f'<span class="r-badge" style="background:{rc}22;color:{rc}">'
                    f'{kpi["risk_level"]}</span></div>',
                    unsafe_allow_html=True,
                )
            with _sec_cols[3]:
                delta_team = kpi["team_size"] - baseline_kpi["team_size"]
                st.metric("Team",
                          f"{kpi['engineers']}d + {kpi['architects']}a",
                          delta=f"{delta_team:+d} people" if delta_team != 0 else None)
            with _sec_cols[4]:
                if kpi.get("revenue", 0) > 0:
                    m_color = "#4ade80" if kpi["margin_pct"] > 20 else "#f97316" if kpi["margin_pct"] < 10 else "#fbbf24"
                    st.markdown(
                        f'<div style="padding-top:4px">'
                        f'<div style="font-size:.75rem;color:#64748b;margin-bottom:5px">Gross Margin</div>'
                        f'<span style="font-size:1.1rem;font-weight:800;color:{m_color}">'
                        f'{kpi["margin_pct"]:.1f}%</span>'
                        f'<div style="font-size:.7rem;color:#475569;margin-top:2px">'
                        f'${kpi["gross_profit"]:,.0f} profit</div></div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        '<div style="padding-top:4px">'
                        '<div style="font-size:.75rem;color:#64748b;margin-bottom:5px">Gross Margin</div>'
                        '<span style="font-size:.75rem;color:#334155;font-style:italic">Set client rate →</span>'
                        '</div>',
                        unsafe_allow_html=True,
                    )

            # ── Push to Proposal ──────────────────────────────────
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            _pb1, _pb2, _ = st.columns([1.5, 1.5, 4])
            with _pb1:
                if st.button("📄 Use in Proposal", key=f"sc_to_proposal_{tab_i}",
                             width="stretch",
                             help="Save this scenario's KPIs to session so the Proposal tab can reference them"):
                    st.session_state["proposal_scenario"] = {
                        "name":          sc["name"],
                        "kpi":           kpi,
                        "params":        new_params,
                        "deferred":      deferred_items,
                        "modified":      modified_items,
                    }
                    st.success(f"✅ '{sc['name']}' set as proposal scenario — switch to Proposal tab.")
            with _pb2:
                if st.button("📋 Copy Summary", key=f"sc_copy_{tab_i}",
                             width="stretch",
                             help="Copy a text summary of this scenario to session clipboard"):
                    summary = (
                        f"**{sc['name']}** — {kpi['duration_weeks']:.0f} wks, "
                        f"${kpi['total_cost']:,.0f} total, "
                        f"${kpi['monthly_burn']:,.0f}/mo burn, "
                        f"Risk: {kpi['risk_level']} ({kpi['risk_score']:.1f}/10), "
                        f"Team: {kpi['engineers']}E + {kpi['architects']}A, "
                        f"Scope: {derived_scope_pct}%"
                    )
                    st.session_state["sc_clipboard"] = summary
                    st.info(f"📋 Copied: {summary}")

            # Notes display
            if sc.get("notes"):
                st.markdown(
                    f'<div style="margin-top:12px;padding:10px 14px;background:rgba(30,41,59,.5);'
                    f'border-radius:8px;border-left:2px solid {pal["accent"]};'
                    f'font-size:.78rem;color:#94a3b8;font-style:italic">'
                    f'📝 {sc["notes"]}</div>',
                    unsafe_allow_html=True,
                )

    # ── COMPARISON TABLE ──────────────────────────────────────────────
    st.markdown("<div style='height:26px'></div>", unsafe_allow_html=True)

    # Best-scenario recommendation
    best_idx = _best_scenario_idx(baseline_kpi, scenarios)
    if best_idx is not None:
        best_name = scenarios[best_idx]["name"]
        b_save    = baseline_kpi["total_cost"] - scenarios[best_idx]["kpi"]["total_cost"]
        b_wks     = baseline_kpi["duration_weeks"] - scenarios[best_idx]["kpi"]["duration_weeks"]
        parts = []
        if b_save > 1000:  parts.append(f"saves ${b_save:,.0f}")
        if b_wks > 0.5:    parts.append(f"{b_wks:.1f} wks faster")
        tag = " · ".join(parts) if parts else "best balance of cost, speed, and risk"
        st.markdown(
            f'<div class="best-banner">'
            f'<span style="font-size:1.1rem">🏆</span>'
            f'<span><b>{best_name}</b> is the recommended scenario — {tag}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        '<div style="font-size:1.1rem;font-weight:700;color:#e2e8f0;margin-bottom:14px">'
        '📊 Side-by-Side Comparison</div>',
        unsafe_allow_html=True,
    )

    all_kpis = [{"name": "Baseline", "kpi": baseline_kpi, "color": "#94a3b8"}] + [
        {"name": sc["name"], "kpi": sc["kpi"], "color": _PALETTE[i]["accent"]}
        for i, sc in enumerate(scenarios)
    ]

    metrics = [
        ("Total Hours",      "hours",          lambda v: f"{v:,} hrs",      True),
        ("Duration",         "duration_weeks", lambda v: f"{v:.1f} wks",    True),
        ("Total Cost",       "total_cost",     lambda v: f"${v:,.0f}",      True),
        ("Monthly Burn",     "monthly_burn",   lambda v: f"${v:,.0f}/mo",   True),
        ("Dev Cost",         "dev_cost",       lambda v: f"${v:,.0f}",      True),
        ("Infra Cost",       "infra_cost",     lambda v: f"${v:,.0f}",      True),
        ("Risk Score",       "risk_score",     lambda v: f"{v:.1f}/10",     True),
        ("Risk Level",       "risk_level",     lambda v: v,                 None),
        ("Team Size",        "team_size",      lambda v: f"{v} ppl",        False),
        ("Gross Margin",     "margin_pct",     lambda v: f"{v:.1f}%",       False),
    ]

    hdr = '<table class="cmp-table"><thead><tr><th style="width:130px">Metric</th>'
    for e in all_kpis:
        hdr += f'<th style="color:{e["color"]}">{e["name"]}</th>'
    hdr += "</tr></thead><tbody>"

    body = ""

    # Scope row
    if in_scope_all:
        body += "<tr><td style='color:#64748b;font-weight:700;vertical-align:top'>Scope</td>"
        for i, entry in enumerate(all_kpis):
            if i == 0:
                body += f"<td><span class='b-base'>All {len(in_scope_all)} items</span></td>"
            else:
                sc_p    = scenarios[i - 1]["params"]
                ledger  = sc_p.get("scope_ledger", {})
                removed = sc_p.get("removed_items", [])
                n_def   = sum(1 for d in ledger.values() if d.get("state") == "Deferred") if ledger else len(removed)
                n_mod   = sum(1 for d in ledger.values() if d.get("state") == "Modified") if ledger else 0
                remaining = len(in_scope_all) - n_def

                cell = f"<span class='b-base'>All {len(in_scope_all)}</span>"
                if n_def or n_mod:
                    cell = f"<span class='b-good'>{remaining}/{len(in_scope_all)} active</span>"
                    if n_mod:
                        cell += f' <span class="mod-tag">✏️ {n_mod} mod</span>'
                    if n_def:
                        def_names = "".join(
                            f'<div style="font-size:.63rem;color:#f87171;line-height:1.6">'
                            f'✗ {safe_str(it)[:42]}</div>'
                            for it, d in ledger.items()
                            if d.get("state") == "Deferred"
                        ) if ledger else "".join(
                            f'<div style="font-size:.63rem;color:#f87171">✗ {safe_str(it)[:42]}</div>'
                            for it in removed
                        )
                        cell += f'<div style="margin-top:4px">{def_names}</div>'
                body += f"<td style='vertical-align:top'>{cell}</td>"
        body += "</tr>"

    # Phase row
    if phases_all:
        body += "<tr><td style='color:#64748b;font-weight:700;vertical-align:top'>Phases</td>"
        for i, entry in enumerate(all_kpis):
            if i == 0:
                body += f"<td><span class='b-base'>All {len(phases_all)}</span></td>"
            else:
                sc_p  = scenarios[i - 1]["params"]
                actv  = sc_p.get("phases_active")
                if actv is None:
                    body += f"<td><span class='b-base'>All {len(phases_all)}</span></td>"
                else:
                    n_actv = len(actv)
                    if n_actv == len(phases_all):
                        body += f"<td><span class='b-base'>All {len(phases_all)}</span></td>"
                    else:
                        body += f"<td><span class='b-good'>{n_actv}/{len(phases_all)}</span></td>"
        body += "</tr>"

    for label, key, fmt_fn, lower_better in metrics:
        body += f"<tr><td style='color:#64748b;font-weight:700'>{label}</td>"
        base_val = baseline_kpi.get(key)
        for i, entry in enumerate(all_kpis):
            val     = entry["kpi"].get(key, "—")
            display = fmt_fn(val) if val != "—" else "—"
            if key == "risk_level":
                rc   = _RISK_COLORS.get(str(val), "#94a3b8")
                body += f'<td><span class="r-badge" style="background:{rc}22;color:{rc}">{display}</span></td>'
            elif i == 0:
                body += f"<td><span class='b-base'>{display}</span></td>"
            elif lower_better is None or base_val is None:
                body += f"<td>{display}</td>"
            else:
                try:
                    dp   = (float(val) - float(base_val)) / abs(float(base_val)) * 100
                    if abs(dp) < 0.5:
                        body += f"<td>{display}</td>"
                    else:
                        good  = (dp < 0) if lower_better else (dp > 0)
                        badge = "b-good" if good else "b-bad"
                        arrow = "▼" if dp < 0 else "▲"
                        body += (
                            f'<td><span class="{badge}">{display}</span> '
                            f'<span style="font-size:.62rem;color:#475569">{arrow}{abs(dp):.1f}%</span></td>'
                        )
                except Exception:
                    body += f"<td>{display}</td>"
        body += "</tr>"

    st.markdown(hdr + body + "</tbody></table>", unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────────────
    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots

        st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
        ch1, ch2 = st.columns(2, gap="medium")

        sc_names  = [e["name"]  for e in all_kpis]
        sc_colors = [e["color"] for e in all_kpis]

        _base_layout = dict(
            paper_bgcolor="#080d1a", plot_bgcolor="#080d1a",
            font=dict(color="#94a3b8", size=11),
            legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.25,
                        font=dict(color="#64748b", size=10)),
            height=300, margin=dict(l=10, r=10, t=44, b=50), bargap=0.28,
        )

        # Chart 1 — Hours + Duration line
        with ch1:
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Bar(
                name="Total Hours", x=sc_names,
                y=[e["kpi"]["hours"] for e in all_kpis],
                marker_color=sc_colors, opacity=0.88,
                text=[f"{e['kpi']['hours']:,}h" for e in all_kpis],
                textposition="outside", textfont=dict(size=10),
            ), secondary_y=False)
            fig.add_trace(go.Scatter(
                name="Duration (wks)", x=sc_names,
                y=[e["kpi"]["duration_weeks"] for e in all_kpis],
                mode="lines+markers",
                line=dict(color="#a78bfa", width=2.5, dash="dot"),
                marker=dict(size=9, color="#a78bfa", line=dict(color="#080d1a", width=2)),
            ), secondary_y=True)
            fig.update_layout(
                title=dict(text="Hours &amp; Duration", font=dict(color="#e2e8f0", size=13)),
                **_base_layout,
            )
            fig.update_xaxes(showgrid=False, tickfont=dict(color="#64748b"))
            fig.update_yaxes(showgrid=True, gridcolor="#1e293b", tickfont=dict(color="#64748b"),
                             secondary_y=False)
            fig.update_yaxes(title_text="Weeks", showgrid=False,
                             tickfont=dict(color="#a78bfa"), secondary_y=True)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

        # Chart 2 — Stacked cost
        with ch2:
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                name="Dev Cost", x=sc_names,
                y=[e["kpi"]["dev_cost"] for e in all_kpis],
                marker_color="#3b82f6", marker_opacity=0.9,
                text=[f"${e['kpi']['dev_cost']:,.0f}" for e in all_kpis],
                textposition="inside", textfont=dict(color="white", size=9),
            ))
            fig2.add_trace(go.Bar(
                name="Infra Cost", x=sc_names,
                y=[e["kpi"]["infra_cost"] for e in all_kpis],
                marker_color="#8b5cf6", marker_opacity=0.9,
                text=[f"${e['kpi']['infra_cost']:,.0f}" for e in all_kpis],
                textposition="inside", textfont=dict(color="white", size=9),
            ))
            fig2.update_layout(
                title=dict(text="Cost Breakdown", font=dict(color="#e2e8f0", size=13)),
                barmode="stack", **_base_layout,
            )
            fig2.update_xaxes(showgrid=False, tickfont=dict(color="#64748b"))
            fig2.update_yaxes(showgrid=True, gridcolor="#1e293b",
                              tickprefix="$", tickfont=dict(color="#64748b"))
            st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})

        # Radar
        if len(all_kpis) >= 2:
            st.markdown(
                '<div style="font-size:.82rem;color:#475569;margin:4px 0 10px">'
                '🕸 Multi-dimension radar — normalised 0–1 (lower = better for cost/risk)</div>',
                unsafe_allow_html=True,
            )
            radar_keys   = ["hours", "duration_weeks", "total_cost", "risk_score", "team_size"]
            radar_labels = ["Hours", "Duration", "Cost", "Risk", "Team"]
            maxes = {k: max(e["kpi"].get(k, 0) for e in all_kpis) or 1 for k in radar_keys}

            def _hex_rgba(h: str, a: float = 0.16) -> str:
                h = h.lstrip("#")
                r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
                return f"rgba({r},{g},{b},{a})"

            fig3 = go.Figure()
            for entry in all_kpis:
                vals = [round(entry["kpi"].get(k, 0) / maxes[k], 3) for k in radar_keys]
                vals.append(vals[0])
                lbls = radar_labels + [radar_labels[0]]
                fig3.add_trace(go.Scatterpolar(
                    r=vals, theta=lbls, fill="toself",
                    name=entry["name"],
                    line=dict(color=entry["color"], width=2.5),
                    fillcolor=_hex_rgba(entry["color"], 0.16),
                    opacity=0.95,
                ))
            fig3.update_layout(
                polar=dict(
                    bgcolor="#080d1a",
                    radialaxis=dict(visible=True, range=[0, 1], gridcolor="#1e293b",
                                   tickfont=dict(color="#334155", size=8)),
                    angularaxis=dict(gridcolor="#1e293b", tickfont=dict(color="#94a3b8", size=11)),
                ),
                paper_bgcolor="#080d1a",
                font=dict(color="#94a3b8"),
                legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.07,
                            font=dict(color="#64748b", size=10)),
                height=370, margin=dict(l=30, r=30, t=20, b=50),
            )
            st.plotly_chart(fig3, width="stretch", config={"displayModeBar": False})

    except ImportError:
        st.info("Install plotly for charts: pip install plotly")

    # ── Export ────────────────────────────────────────────────────────
    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
    st.divider()
    exp_col, _ = st.columns([2, 3])
    with exp_col:
        sc_export  = [{"name": s["name"], "params": s["params"], "kpi": s["kpi"]} for s in scenarios]
        excel_data = generate_scenario_excel(baseline_kpi, sc_export)
        if excel_data:
            st.download_button(
                label="📥 Export Comparison (Excel)",
                data=excel_data,
                file_name="scenario_comparison.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        else:
            st.caption("Install openpyxl to enable Excel export.")
