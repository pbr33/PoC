# ═══════════════════════════════════════════════════════════════════════
#  ANIMATED EXPLAINER  —  cinematic, AI-narrated proposal walkthrough
#  • Voice-sync: slide never advances until narration finishes
#  • 7 fully animated scenes driven by live proposal data
#  • Pure HTML / CSS / JS — no external deps, runs in st.components.v1.html
# ═══════════════════════════════════════════════════════════════════════
import json
import math
import streamlit as st
import streamlit.components.v1 as components

from .utils import safe_dict, safe_str, safe_list, safe_int


# ── Tier classifier ───────────────────────────────────────────────────
_PRES_KW = {"front","ui","web","mobile","client","spa","pwa","portal","browser","react","angular","vue","next","blazor","flutter"}
_DATA_KW = {"data","db","database","sql","cosmos","storage","blob","redis","cache","queue","bus","event","search","lake","warehouse","mongo","postgres","mysql"}
_EXT_KW  = {"external","third","saas","monitor","log","insight","email","sms","payment","stripe","twilio","sendgrid","analytics","crm","erp"}

def _tier(comp_type: str, comp_name: str) -> int:
    t = (comp_type + " " + comp_name).lower()
    if any(k in t for k in _PRES_KW): return 0
    if any(k in t for k in _DATA_KW): return 2
    if any(k in t for k in _EXT_KW):  return 3
    return 1


# ── Data extraction ───────────────────────────────────────────────────
def _extract(r, se, te, ce, ri, ar) -> dict:
    sc   = safe_dict(r.get("scope", {}))
    reqs = safe_list(se.get("requirements", []))
    fn_n = len([x for x in reqs if isinstance(x, dict) and x.get("type") == "functional"])
    nf_n = len([x for x in reqs if isinstance(x, dict) and x.get("type") == "non-functional"])
    ig_n = len([x for x in reqs if isinstance(x, dict) and x.get("type") == "integration"])

    phases = [
        {"name": safe_str(p.get("name", f"Phase {i+1}")),
         "hours": safe_int(p.get("hours", 0)),
         "week_label": safe_str(p.get("week_label", ""))}
        for i, p in enumerate(safe_list(te.get("phases", []))) if isinstance(p, dict)
    ][:8]

    milestones = [
        {"name": safe_str(m.get("name", "")), "week": safe_int(m.get("week", 0))}
        for m in safe_list(te.get("milestones", [])) if isinstance(m, dict)
    ][:6]

    azure_costs = [c for c in safe_list(ce.get("azure_costs", []))
                   if isinstance(c, dict) and safe_int(c.get("monthly_cost", 0)) > 0]
    top_costs = sorted(azure_costs, key=lambda x: safe_int(x.get("monthly_cost", 0)), reverse=True)[:6]

    risks_raw = [r2 for r2 in safe_list(ri.get("risks", [])) if isinstance(r2, dict)][:5]

    comps_raw = [c for c in safe_list(ar.get("components", [])) if isinstance(c, dict)][:12]
    comps = [{"name": safe_str(c.get("name","")),
              "type": safe_str(c.get("type","service")).lower(),
              "azure": safe_str(c.get("azure_service","")),
              "tier": _tier(safe_str(c.get("type","")).lower(), safe_str(c.get("name","")))}
             for c in comps_raw]

    in_scope_raw = safe_list(sc.get("in_scope", []))
    in_scope = []
    for item in in_scope_raw[:7]:
        s = safe_str(item.get("title") or item.get("feature") or item.get("name") or "") if isinstance(item, dict) else safe_str(item)
        if s: in_scope.append(s)

    tech = [safe_str(t) for t in safe_list(se.get("technology_stack", []))][:10]
    team = safe_list(st.session_state.get("_ce_team", []))
    team_size = len(team) if team else max(3, fn_n // 5)

    total_monthly = safe_int(ce.get("total_monthly_cost", 0))
    total_annual  = safe_int(ce.get("total_annual_cost", 0)) or total_monthly * 12

    dur_raw = safe_str(te.get("duration_weeks", ""))
    dur_num = 0
    for tok in dur_raw.split():
        try: dur_num = int(tok); break
        except ValueError: pass

    high_r = len([x for x in risks_raw if safe_str(x.get("severity","")).lower() in ("high","critical")])
    med_r  = len([x for x in risks_raw if safe_str(x.get("severity","")).lower() == "medium"])
    low_r  = len([x for x in risks_raw if safe_str(x.get("severity","")).lower() == "low"])

    return {
        "project_name":   safe_str(se.get("project_type","Solution Proposal")) or "Solution Proposal",
        "client_name":    st.session_state.get("proposal_client_name","") or "",
        "date_str":       st.session_state.get("proposal_proposal_date","") or "",
        "fn_n": fn_n, "nf_n": nf_n, "ig_n": ig_n,
        "total_hours":    safe_int(te.get("total_hours", 0)),
        "duration_weeks": dur_raw or "TBD",
        "dur_num":        dur_num,
        "confidence":     safe_str(te.get("confidence","High")),
        "phases":         phases,
        "milestones":     milestones,
        "total_monthly":  total_monthly,
        "total_annual":   total_annual,
        "top_costs":      [{"service": safe_str(c.get("service","")), "cost": safe_int(c.get("monthly_cost",0))} for c in top_costs],
        "risk_score":     safe_int(ri.get("overall_score", 0)),
        "risk_level":     safe_str(ri.get("overall_level","Medium")),
        "high_r": high_r, "med_r": med_r, "low_r": low_r,
        "risks":          [{"title": safe_str(r2.get("title","")),
                            "severity": safe_str(r2.get("severity","Medium")),
                            "mitigation": safe_str(r2.get("mitigation",""))[:100],
                            "category": safe_str(r2.get("category",""))}
                           for r2 in risks_raw],
        "arch_pattern":   safe_str(ar.get("pattern","Microservices")),
        "components":     comps,
        "data_flow":      [safe_str(x) for x in safe_list(ar.get("data_flow",[]))[:6]],
        "in_scope":       in_scope,
        "tech":           tech,
        "team_size":      team_size,
    }


# ── Narration ─────────────────────────────────────────────────────────
def _template_narration(d: dict) -> list:
    client    = d["client_name"] or "the client"
    proj      = d["project_name"]
    dur       = d["duration_weeks"]
    hrs       = f"{d['total_hours']:,}" if d["total_hours"] else "estimated"
    cost_m    = f"${d['total_monthly']:,}" if d["total_monthly"] else "planned"
    scope_str = ", ".join(d["in_scope"][:3]) if d["in_scope"] else "key features"
    top_risk  = d["risks"][0]["title"] if d["risks"] else "delivery timeline"
    top_mit   = d["risks"][0]["mitigation"] if d["risks"] else "proactive monitoring"
    flow      = " to ".join(d["data_flow"][:3]) if d["data_flow"] else "client through services to data"
    phases_str = ", ".join(p["name"] for p in d["phases"][:3]) if d["phases"] else "Discovery, Build, and Launch"
    n_comps   = len(d["components"])
    return [
        f"Welcome to the {proj} proposal{' for ' + client if client != 'the client' else ''}. "
        f"We have designed a complete, production-ready solution. Let me walk you through every layer.",

        f"The project covers {d['fn_n']} functional requirements, {d['nf_n']} non-functional requirements, "
        f"and {d['ig_n']} integrations. Key deliverables include {scope_str}.",

        f"The solution follows a {d['arch_pattern']} architecture with {n_comps} specialised components. "
        f"Data flows from {flow}. Every component is cloud-native on Azure.",

        f"Delivery is structured across {len(d['phases'])} phases — {phases_str} — "
        f"totalling {hrs} hours and completing in {dur}. "
        f"Our confidence level is {d['confidence']}.",

        f"Infrastructure runs entirely on Azure at {cost_m} per month. "
        f"A dedicated team of {d['team_size']} specialists covers the full delivery stack, "
        f"from architecture through to quality assurance.",

        f"Risk analysis identified {len(d['risks'])} items with an overall {d['risk_level']} risk profile. "
        f"The primary concern is {top_risk}. Our mitigation: {top_mit}.",

        f"This is our commitment to delivering {proj}{' for ' + client if client != 'the client' else ''}. "
        f"On time. Within budget. Built to last. We look forward to building this together.",
    ]

def _ai_narration(d: dict, ai_client) -> list:
    if ai_client is None:
        return _template_narration(d)
    try:
        prompt = (
            f"Write 7 professional spoken narration lines for an animated proposal presentation.\n"
            f"Each line is 2-3 natural sentences — confident, clear, no jargon.\n\n"
            f"Project: {d['project_name']}\nClient: {d['client_name']}\n"
            f"Reqs: {d['fn_n']} functional, {d['nf_n']} non-functional, {d['ig_n']} integrations\n"
            f"Architecture: {d['arch_pattern']}, {len(d['components'])} components\n"
            f"Duration: {d['duration_weeks']} / {d['total_hours']} hours\n"
            f"Monthly cost: ${d['total_monthly']:,}\nRisk: {d['risk_level']} ({d['risk_score']}/10)\n"
            f"Key scope: {', '.join(d['in_scope'][:4])}\n\n"
            f"Scenes: 1.Opening  2.Scope  3.Architecture  4.Timeline  5.Cost & Team  6.Risks  7.Closing CTA\n"
            f"Return ONLY a JSON array of exactly 7 strings. No markdown."
        )
        resp = ai_client.complete(prompt, max_tokens=700)
        raw  = resp.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        lines = json.loads(raw)
        if isinstance(lines, list) and len(lines) >= 7:
            return [str(x) for x in lines[:7]]
    except Exception:
        pass
    return _template_narration(d)


# ── SVG donut (Python-side, exact math) ──────────────────────────────
def _donut_svg(top_costs: list, total_monthly: int) -> str:
    COLORS = ["#00d4aa","#0078d4","#7c3aed","#f59e0b","#ef4444","#06b6d4"]
    cx, cy, ro, ri = 75, 75, 62, 38
    shown = [c for c in top_costs if c["cost"] > 0][:6]
    total = sum(c["cost"] for c in shown) or 1
    angle = -math.pi / 2
    paths = ""
    GAP   = 0.03
    for i, c in enumerate(shown):
        sweep = (c["cost"] / total) * (2 * math.pi - len(shown) * GAP)
        x1 = cx + ro * math.cos(angle)
        y1 = cy + ro * math.sin(angle)
        x2 = cx + ro * math.cos(angle + sweep)
        y2 = cy + ro * math.sin(angle + sweep)
        ix1 = cx + ri * math.cos(angle + sweep)
        iy1 = cy + ri * math.sin(angle + sweep)
        ix2 = cx + ri * math.cos(angle)
        iy2 = cy + ri * math.sin(angle)
        lg  = 1 if sweep > math.pi else 0
        clr = COLORS[i % len(COLORS)]
        paths += (
            f'<path class="dseg" style="--di:{i*0.12}s" fill="{clr}" '
            f'd="M{x1:.2f},{y1:.2f} A{ro},{ro} 0 {lg},1 {x2:.2f},{y2:.2f} '
            f'L{ix1:.2f},{iy1:.2f} A{ri},{ri} 0 {lg},0 {ix2:.2f},{iy2:.2f} Z"/>'
        )
        angle += sweep + GAP
    total_lbl = f"${total_monthly:,}" if total_monthly else "$0"
    paths += (
        f'<text x="{cx}" y="{cy-8}" text-anchor="middle" fill="#64748b" font-size="9" letter-spacing="1">MONTHLY</text>'
        f'<text x="{cx}" y="{cy+10}" text-anchor="middle" fill="#e2e8f0" font-size="15" font-weight="800">{total_lbl}</text>'
    )
    legend = ""
    for i, c in enumerate(shown):
        clr = COLORS[i % len(COLORS)]
        legend += (
            f'<div class="cleg" style="--di:{i*0.1}s">'
            f'<span class="cdot" style="background:{clr}"></span>'
            f'<span class="csvc">{c["service"][:24]}</span>'
            f'<span class="cval">${c["cost"]:,}</span></div>'
        )
    return (
        f'<div class="donut-block">'
        f'<svg width="150" height="150" viewBox="0 0 150 150" class="donut-svg">{paths}</svg>'
        f'<div class="cleg-wrap">{legend}</div>'
        f'</div>'
    )


# ── Master HTML builder ───────────────────────────────────────────────
def _build_html(d: dict, narration: list) -> str:
    JS   = json.dumps(d,         ensure_ascii=False)
    NAR  = json.dumps(narration, ensure_ascii=False)
    PCOL = ["#00d4aa","#0078d4","#7c3aed","#f59e0b","#ef4444","#ec4899","#06b6d4","#84cc16"]

    # ── Phase bars ────────────────────────────────────────────────────
    max_h = max((p["hours"] for p in d["phases"]), default=1) or 1
    phase_html = ""
    for i, p in enumerate(d["phases"]):
        clr = PCOL[i % len(PCOL)]
        w   = min(100, round(p["hours"] / max_h * 100))
        wlb = f" · {p['week_label']}" if p["week_label"] else ""
        phase_html += (
            f'<div class="ph-row" data-w="{w}" style="--pi:{i}">'
            f'<div class="ph-lbl">{p["name"]}</div>'
            f'<div class="ph-track"><div class="ph-bar" id="pb{i}" style="background:{clr}"></div></div>'
            f'<div class="ph-meta">{p["hours"]:,}h{wlb}</div></div>'
        )

    # ── Donut + legend ────────────────────────────────────────────────
    donut_block = _donut_svg(d["top_costs"], d["total_monthly"])

    # ── Scope cards ───────────────────────────────────────────────────
    scope_cards = "".join(
        f'<div class="scard" style="--si:{i}">'
        f'<span class="scard-icon">✦</span>{item}</div>'
        for i, item in enumerate(d["in_scope"])
    )
    tech_pills = "".join(
        f'<span class="tpill" style="--ti:{i}">{t}</span>'
        for i, t in enumerate(d["tech"])
    )

    # ── Risk cards ────────────────────────────────────────────────────
    SEV = {"High":"#ef4444","Critical":"#ef4444","Medium":"#f59e0b","Low":"#22c55e"}
    risk_cards = ""
    for i, rk in enumerate(d["risks"]):
        clr = SEV.get(rk["severity"], "#f59e0b")
        risk_cards += (
            f'<div class="rcard" style="--ri:{i};border-left:3px solid {clr}">'
            f'<div class="rtop">'
            f'<span class="rsev" style="color:{clr};background:{clr}18">{rk["severity"]}</span>'
            f'<span class="rcat">{rk["category"]}</span></div>'
            f'<div class="rtitle">{rk["title"]}</div>'
            f'<div class="rmit">{rk["mitigation"]}</div></div>'
        )

    # ── KPI hero boxes ────────────────────────────────────────────────
    kpis = [
        (d["total_monthly"], "Monthly Infra", "$", "/mo"),
        (d["total_hours"],   "Total Hours",   "",  "h"),
        (d["dur_num"] or 0,  d["duration_weeks"], "", " wks"),
        (d["team_size"],     "Team Size",     "",  " people"),
    ]
    kpi_boxes = ""
    for i, (val, lbl, pre, suf) in enumerate(kpis):
        display_val = (pre + f"{val:,}" + suf) if val else "TBD"
        is_counter  = isinstance(val, int) and val > 0
        counter_attrs = (f'data-target="{val}" data-pre="{pre}" data-suf="{suf}"'
                         if is_counter else "")
        kpi_boxes += (
            f'<div class="kbox" style="--ki:{i}">'
            f'<div class="kval" {counter_attrs}>'
            f'{display_val}</div>'
            f'<div class="klbl">{lbl}</div></div>'
        )

    # ── Requirements stat boxes ───────────────────────────────────────
    req_boxes = "".join(
        f'<div class="rqbox" style="--rqi:{i}">'
        f'<div class="rqnum" data-target="{n}">{n}</div>'
        f'<div class="rqlbl">{lbl}</div></div>'
        for i, (n, lbl) in enumerate([
            (d["fn_n"],  "Functional"),
            (d["nf_n"],  "Non-Functional"),
            (d["ig_n"],  "Integrations"),
        ])
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:100%;height:100%;overflow:hidden;background:#020817;
  font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:#e2e8f0}}

/* ══ ANIMATED MESH BG ════════════════════════════════════════════════ */
#mesh{{position:fixed;inset:0;pointer-events:none;z-index:0;
  background:radial-gradient(ellipse 80% 60% at 15% 40%,#00d4aa09,transparent),
             radial-gradient(ellipse 60% 80% at 85% 20%,#0078d409,transparent),
             radial-gradient(ellipse 70% 50% at 50% 90%,#7c3aed07,transparent)}}
.particle{{position:absolute;border-radius:50%;pointer-events:none;
  animation:drift linear infinite}}
@keyframes drift{{
  0%  {{transform:translateY(0) scale(1);  opacity:.6}}
  50% {{transform:translateY(-40px) scale(1.2); opacity:.3}}
  100%{{transform:translateY(0) scale(1);  opacity:.6}}
}}

/* ══ PROGRESS BAR ════════════════════════════════════════════════════ */
#topbar{{position:fixed;top:0;left:0;right:0;height:3px;background:#0f172a;z-index:300}}
#topfill{{height:100%;width:0%;transition:width .7s cubic-bezier(.4,0,.2,1);
  background:linear-gradient(90deg,#00d4aa,#0078d4,#7c3aed)}}

/* ══ SCENE DOTS ══════════════════════════════════════════════════════ */
#scenedots{{position:fixed;top:12px;left:50%;transform:translateX(-50%);
  display:flex;gap:10px;z-index:300;align-items:center}}
.sdot{{width:8px;height:8px;border-radius:50%;background:#1e293b;cursor:pointer;
  transition:all .35s cubic-bezier(.34,1.56,.64,1);border:1px solid #334155}}
.sdot.on{{background:#00d4aa;transform:scale(1.6);border-color:#00d4aa;
  box-shadow:0 0 12px #00d4aa66}}
.sdot:hover:not(.on){{background:#334155;transform:scale(1.2)}}

/* ══ STAGE ═══════════════════════════════════════════════════════════ */
#stage{{position:fixed;top:0;left:0;right:0;bottom:98px;z-index:1;overflow:hidden}}

/* ══ SCENE BASE ══════════════════════════════════════════════════════ */
.sc{{position:absolute;inset:0;display:flex;flex-direction:column;
  align-items:center;justify-content:center;padding:20px 28px 10px;
  opacity:0;pointer-events:none;
  transition:opacity .55s ease,transform .55s cubic-bezier(.4,0,.2,1);
  transform:translateY(24px)}}
.sc.enter{{opacity:1;pointer-events:auto;transform:translateY(0)}}
.sc.exit-up{{opacity:0;transform:translateY(-24px)}}
.sc.exit-dn{{opacity:0;transform:translateY(24px)}}

/* ══ SCENE ACCENT FLASH ══════════════════════════════════════════════ */
#aflash{{position:fixed;inset:0;pointer-events:none;z-index:250;opacity:0;
  transition:opacity .2s ease}}

/* ══ SCENE LABEL OVERLAY ════════════════════════════════════════════ */
#slabel{{position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
  z-index:260;pointer-events:none;text-align:center;
  opacity:0;transition:opacity .3s ease}}
#slabel .sl-icon{{font-size:2.5rem;display:block;margin-bottom:6px}}
#slabel .sl-name{{font-size:1rem;font-weight:700;letter-spacing:3px;
  text-transform:uppercase;color:#fff}}

/* ══ SECTION HEADER ══════════════════════════════════════════════════ */
.sh{{font-size:.58rem;font-weight:800;letter-spacing:3px;text-transform:uppercase;
  margin-bottom:5px;opacity:.85}}
.stitle{{font-size:1.55rem;font-weight:900;line-height:1.2;text-align:center;margin-bottom:6px}}
.ssub{{font-size:.82rem;color:#94a3b8;text-align:center;margin-bottom:14px}}

/* ══ SCENE 0 — HERO ══════════════════════════════════════════════════ */
.hero-tag{{font-size:.58rem;font-weight:800;letter-spacing:3px;text-transform:uppercase;
  color:#00d4aa;border:1px solid #00d4aa33;border-radius:20px;padding:4px 16px;
  margin-bottom:14px;animation:fadeUp .5s ease both}}
.hero-name{{font-size:2.2rem;font-weight:900;text-align:center;margin-bottom:4px;
  background:linear-gradient(130deg,#e2e8f0 30%,#00d4aa 65%,#0078d4);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  animation:fadeUp .6s .1s ease both;line-height:1.15}}
.hero-client{{font-size:.9rem;color:#64748b;text-align:center;margin-bottom:20px;
  animation:fadeUp .6s .18s ease both}}
.krow{{display:flex;gap:12px;flex-wrap:wrap;justify-content:center}}
.kbox{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);
  border-radius:14px;padding:14px 20px;text-align:center;min-width:106px;
  animation:fadeUp .6s calc(.28s + var(--ki)*.09s) ease both;backdrop-filter:blur(4px)}}
.kval{{font-size:1.3rem;font-weight:900;color:#e2e8f0}}
.klbl{{font-size:.62rem;color:#475569;margin-top:3px;letter-spacing:.4px}}

/* ══ SCENE 1 — SCOPE ════════════════════════════════════════════════ */
.sgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));
  gap:9px;width:100%;max-width:800px;margin-bottom:14px}}
.scard{{background:rgba(0,212,170,.06);border:1px solid rgba(0,212,170,.16);
  border-radius:10px;padding:10px 14px;font-size:.82rem;color:#cbd5e1;
  display:flex;align-items:center;gap:10px;
  animation:fadeUp .45s calc(.15s + var(--si)*.08s) ease both}}
.scard-icon{{color:#00d4aa;font-size:.75rem;flex-shrink:0}}
.trow{{display:flex;flex-wrap:wrap;gap:6px;justify-content:center;max-width:700px}}
.tpill{{background:rgba(0,120,212,.1);border:1px solid rgba(0,120,212,.22);
  border-radius:20px;padding:4px 12px;font-size:.71rem;color:#7dd3fc;
  animation:fadeUp .4s calc(.35s + var(--ti)*.07s) ease both}}
.rqrow{{display:flex;gap:16px;justify-content:center;margin-bottom:14px}}
.rqbox{{text-align:center;animation:fadeUp .5s calc(.1s + var(--rqi)*.1s) ease both}}
.rqnum{{font-size:2.2rem;font-weight:900;color:#00d4aa}}
.rqlbl{{font-size:.65rem;color:#64748b;margin-top:2px;letter-spacing:.4px}}

/* ══ SCENE 2 — ARCHITECTURE LIVE DRAW ════════════════════════════════ */
.arch-wrap{{width:100%;max-width:870px;background:rgba(255,255,255,.02);
  border:1px solid #1e293b;border-radius:16px;padding:12px 8px 6px;position:relative}}
#arch-svg{{overflow:visible;max-width:100%;display:block;margin:0 auto}}
.arch-lbadge{{display:flex;gap:10px;justify-content:center;margin-top:7px;flex-wrap:wrap}}
.alb{{font-size:.58rem;font-weight:800;letter-spacing:1.5px;text-transform:uppercase;
  padding:3px 13px;border-radius:20px;opacity:0;transition:opacity .5s ease}}
.alb.show{{opacity:1}}

/* ══ SCENE 3 — TIMELINE ══════════════════════════════════════════════ */
.tlwrap{{width:100%;max-width:720px}}
.ph-row{{display:grid;grid-template-columns:150px 1fr 88px;gap:10px;
  align-items:center;margin-bottom:9px}}
.ph-lbl{{font-size:.77rem;color:#94a3b8;text-align:right;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.ph-track{{background:#0f172a;border:1px solid #1e293b;border-radius:6px;
  height:12px;overflow:hidden}}
.ph-bar{{height:100%;border-radius:6px;width:0%;
  transition:width 1.1s cubic-bezier(.34,1.2,.64,1)}}
.ph-meta{{font-size:.68rem;color:#475569;white-space:nowrap}}

/* ══ SCENE 4 — COST & TEAM ═══════════════════════════════════════════ */
.donut-block{{display:flex;align-items:flex-start;gap:20px;flex-wrap:wrap;
  justify-content:center;width:100%;max-width:720px}}
.donut-svg{{filter:drop-shadow(0 0 18px #00d4aa18)}}
.dseg{{transform-origin:75px 75px;
  animation:popIn .5s calc(.1s + var(--di)) cubic-bezier(.34,1.56,.64,1) both}}
@keyframes popIn{{from{{transform:scale(0)}}to{{transform:scale(1)}}}}
.cleg-wrap{{display:flex;flex-direction:column;gap:8px;padding-top:12px}}
.cleg{{display:flex;align-items:center;gap:8px;
  animation:fadeUp .4s calc(.25s + var(--di)) ease both}}
.cdot{{width:10px;height:10px;border-radius:50%;flex-shrink:0}}
.csvc{{font-size:.76rem;color:#94a3b8;flex:1;min-width:140px}}
.cval{{font-size:.76rem;font-weight:700;color:#e2e8f0;white-space:nowrap}}
.team-row{{display:flex;gap:10px;flex-wrap:wrap;justify-content:center;margin-top:14px}}
.team-stat{{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
  border-radius:10px;padding:10px 18px;text-align:center;min-width:100px;
  animation:fadeUp .5s .5s ease both}}
.tstat-v{{font-size:1.3rem;font-weight:900;color:#e2e8f0}}
.tstat-l{{font-size:.62rem;color:#475569;margin-top:2px}}

/* ══ SCENE 5 — RISKS ════════════════════════════════════════════════ */
.risk-summary{{display:flex;gap:12px;margin-bottom:14px}}
.rs-box{{border-radius:10px;padding:8px 16px;text-align:center;font-size:.78rem}}
.rcard{{background:#0f172a;border-radius:10px;padding:13px 15px;
  animation:slideR .45s calc(.1s + var(--ri)*.12s) ease both}}
@keyframes slideR{{from{{opacity:0;transform:translateX(28px)}}
                   to{{opacity:1;transform:translateX(0)}}}}
.rtop{{display:flex;justify-content:space-between;align-items:center;margin-bottom:5px}}
.rsev{{font-size:.68rem;font-weight:800;letter-spacing:.5px;
  border-radius:20px;padding:2px 9px}}
.rcat{{font-size:.64rem;color:#475569}}
.rtitle{{font-size:.84rem;font-weight:700;color:#cbd5e1;margin-bottom:4px}}
.rmit{{font-size:.73rem;color:#64748b;line-height:1.4}}
.rgrid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
  gap:9px;width:100%;max-width:820px}}

/* ══ SCENE 6 — CLOSE ════════════════════════════════════════════════ */
.close-orb{{width:96px;height:96px;border-radius:50%;
  display:flex;align-items:center;justify-content:center;font-size:2.2rem;
  animation:orbPulse 2.5s ease infinite;margin-bottom:20px}}
@keyframes orbPulse{{
  0%,100%{{box-shadow:0 0 0 0 rgba(0,212,170,.25),0 0 30px rgba(0,212,170,.15)}}
  50%{{box-shadow:0 0 0 18px transparent,0 0 50px rgba(0,212,170,.25)}}
}}
.cta-btn{{background:linear-gradient(135deg,#00d4aa,#0078d4);border:none;
  border-radius:30px;padding:12px 36px;font-size:.95rem;font-weight:800;
  color:#020817;cursor:pointer;letter-spacing:.5px;margin-top:14px;
  animation:fadeUp .6s .4s ease both;transition:transform .2s,box-shadow .2s}}
.cta-btn:hover{{transform:translateY(-2px);box-shadow:0 10px 28px #00d4aa44}}

/* ══ NARRATION BAR ═══════════════════════════════════════════════════ */
#narbar{{position:fixed;bottom:54px;left:0;right:0;
  background:rgba(9,15,32,.95);backdrop-filter:blur(12px);
  border-top:1px solid #1e293b;
  padding:8px 20px;z-index:200;display:flex;align-items:center;gap:12px;
  min-height:44px}}
.wave{{display:flex;gap:3px;align-items:center;flex-shrink:0}}
.wbar{{width:3px;border-radius:3px;background:#00d4aa;
  animation:wv .8s ease-in-out infinite}}
.wbar:nth-child(1){{height:6px; animation-delay:0s}}
.wbar:nth-child(2){{height:14px;animation-delay:.1s}}
.wbar:nth-child(3){{height:9px; animation-delay:.2s}}
.wbar:nth-child(4){{height:16px;animation-delay:.15s}}
.wbar:nth-child(5){{height:6px; animation-delay:.05s}}
@keyframes wv{{0%,100%{{transform:scaleY(.3)}}50%{{transform:scaleY(1)}}}}
.wave.idle .wbar{{animation-play-state:paused;height:4px}}
#nartext{{flex:1;font-size:.8rem;color:#94a3b8;line-height:1.5}}
#narlbl{{font-size:.65rem;color:#475569;white-space:nowrap}}

/* ══ CONTROLS ════════════════════════════════════════════════════════ */
#ctrl{{position:fixed;bottom:0;left:0;right:0;height:54px;
  background:#030712;border-top:1px solid #1e293b;z-index:300;
  display:flex;align-items:center;justify-content:center;gap:8px;padding:0 12px}}
.cb{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);
  border-radius:8px;padding:7px 14px;font-size:.78rem;color:#94a3b8;
  cursor:pointer;transition:all .2s;white-space:nowrap;flex-shrink:0}}
.cb:hover{{background:rgba(255,255,255,.12);color:#e2e8f0;border-color:rgba(255,255,255,.2)}}
.cb.pri{{background:linear-gradient(135deg,#00d4aa22,#0078d422);
  border-color:#00d4aa44;color:#00d4aa}}
.cb.pri:hover{{background:linear-gradient(135deg,#00d4aa33,#0078d433)}}
.cb.on{{background:#00d4aa20;border-color:#00d4aa55;color:#00d4aa}}
.cb.warn{{background:#ef444420;border-color:#ef444455;color:#ef4444}}
#sclbl{{font-size:.7rem;color:#334155;min-width:56px;text-align:center}}
.csep{{width:1px;height:22px;background:#1e293b;flex-shrink:0}}
#kbd-hint{{font-size:.62rem;color:#1e293b;margin-left:4px;white-space:nowrap}}

/* ══ KEYFRAMES ═══════════════════════════════════════════════════════ */
@keyframes fadeUp{{from{{opacity:0;transform:translateY(14px)}}to{{opacity:1;transform:translateY(0)}}}}
@keyframes drawPath{{from{{stroke-dashoffset:600}}to{{stroke-dashoffset:0}}}}
@keyframes fadeIn{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes nodePop{{from{{opacity:0;transform:scale(.6)}}to{{opacity:1;transform:scale(1)}}}}
</style>
</head>
<body>
<div id="mesh"></div>
<div id="topbar"><div id="topfill"></div></div>
<div id="scenedots"></div>
<div id="aflash"></div>
<div id="slabel"><span class="sl-icon" id="sl-icon"></span><span class="sl-name" id="sl-name"></span></div>

<div id="stage">

  <!-- ── S0: HERO ─────────────────────────────────────────────── -->
  <div class="sc" id="s0">
    <div class="hero-tag">PROPOSAL OVERVIEW</div>
    <div class="hero-name" id="h0-name"></div>
    <div class="hero-client" id="h0-client"></div>
    <div class="krow">{kpi_boxes}</div>
  </div>

  <!-- ── S1: SCOPE ────────────────────────────────────────────── -->
  <div class="sc" id="s1">
    <div class="sh" style="color:#0078d4">SCOPE &amp; DELIVERABLES</div>
    <div class="stitle">What We're Building</div>
    <div class="rqrow">{req_boxes}</div>
    <div class="sgrid">{scope_cards}</div>
    <div class="trow">{tech_pills}</div>
  </div>

  <!-- ── S2: ARCHITECTURE ──────────────────────────────────────── -->
  <div class="sc" id="s2">
    <div class="sh" style="color:#7c3aed">SOLUTION ARCHITECTURE</div>
    <div class="stitle" id="h2-pattern"></div>
    <div class="arch-wrap">
      <svg id="arch-svg" width="830" height="440" viewBox="0 0 830 440"></svg>
      <div class="arch-lbadge" id="arch-lbadge"></div>
    </div>
  </div>

  <!-- ── S3: TIMELINE ──────────────────────────────────────────── -->
  <div class="sc" id="s3">
    <div class="sh" style="color:#f59e0b">DELIVERY TIMELINE</div>
    <div class="stitle" id="h3-dur"></div>
    <div class="ssub" id="h3-sub"></div>
    <div class="tlwrap" id="tl-wrap">{phase_html}</div>
  </div>

  <!-- ── S4: COST & TEAM ───────────────────────────────────────── -->
  <div class="sc" id="s4">
    <div class="sh" style="color:#06b6d4">INFRASTRUCTURE &amp; TEAM</div>
    <div class="stitle">Azure-Powered, Expert-Delivered</div>
    {donut_block}
    <div class="team-row" id="team-row"></div>
  </div>

  <!-- ── S5: RISKS ─────────────────────────────────────────────── -->
  <div class="sc" id="s5">
    <div class="sh" style="color:#ef4444">RISK REGISTER</div>
    <div class="stitle" id="h5-title"></div>
    <div class="risk-summary" id="risk-sum"></div>
    <div class="rgrid">{risk_cards}</div>
  </div>

  <!-- ── S6: CLOSE ─────────────────────────────────────────────── -->
  <div class="sc" id="s6">
    <div class="close-orb" id="close-orb"
         style="background:radial-gradient(circle,#00d4aa22,transparent);
                border:1px solid #00d4aa33">🚀</div>
    <div class="sh" style="color:#00d4aa">READY TO BUILD</div>
    <div class="hero-name" id="h6-title" style="animation:fadeUp .6s ease both"></div>
    <div class="hero-client" id="h6-sub" style="animation:fadeUp .6s .1s ease both"></div>
    <button class="cta-btn" onclick="restart()">↺ &nbsp;Replay Presentation</button>
  </div>

</div><!-- /stage -->

<!-- narration bar -->
<div id="narbar">
  <div class="wave idle" id="wave">
    <div class="wbar"></div><div class="wbar"></div><div class="wbar"></div>
    <div class="wbar"></div><div class="wbar"></div>
  </div>
  <span id="nartext">Click ▶ Play to start the animated walkthrough with voice narration…</span>
  <span id="narlbl"></span>
</div>

<!-- controls -->
<div id="ctrl">
  <button class="cb" onclick="prevS()" title="Previous (←)">◀</button>
  <button class="cb pri" id="playbtn" onclick="togglePlay()">▶&nbsp; Play</button>
  <button class="cb" onclick="nextS()" title="Next (→)">▶</button>
  <div class="csep"></div>
  <span id="sclbl">1 / 7</span>
  <div class="csep"></div>
  <button class="cb on" id="voicebtn" onclick="toggleVoice()" title="Toggle voice (V)">🔊&nbsp; Voice On</button>
  <button class="cb" id="fsbtn" onclick="toggleFS()" title="Fullscreen (F)">⛶&nbsp; Fullscreen</button>
  <span id="kbd-hint">Space=play  ←→=prev/next  F=fullscreen  V=voice</span>
</div>

<script>
/* ════════════════════════════════════════════════════════════════════
   DATA
════════════════════════════════════════════════════════════════════ */
const D   = {JS};
const NAR = {NAR};

const SCENE_META = [
  {{icon:'🎯', name:'Introduction',   accent:'#00d4aa', dur:5500}},
  {{icon:'📋', name:'Scope',          accent:'#0078d4', dur:6000}},
  {{icon:'🏗️', name:'Architecture',   accent:'#7c3aed', dur:18000}},
  {{icon:'⏱️', name:'Timeline',       accent:'#f59e0b', dur:6500}},
  {{icon:'💰', name:'Cost & Team',    accent:'#06b6d4', dur:6000}},
  {{icon:'⚠️', name:'Risks',          accent:'#ef4444', dur:6000}},
  {{icon:'🚀', name:'Closing',        accent:'#00d4aa', dur:5000}},
];
const NS = SCENE_META.length;

/* ════════════════════════════════════════════════════════════════════
   STATE
════════════════════════════════════════════════════════════════════ */
let cur       = 0;
let playing   = false;
let voiceOn   = true;
let utter     = null;
let safeT     = null;   // safety timer (fallback if speech hangs)
let durationT = null;   // timer used when voice is off

/* ════════════════════════════════════════════════════════════════════
   INIT
════════════════════════════════════════════════════════════════════ */
window.addEventListener('DOMContentLoaded', () => {{
  buildParticles();
  buildDots();
  fillStatic();
  buildArch();
  showScene(0, false);
}});

function buildParticles() {{
  const mesh = document.getElementById('mesh');
  for(let i=0;i<18;i++) {{
    const p=document.createElement('div');
    p.className='particle';
    const sz=Math.random()*3+1;
    p.style.cssText=[
      `width:${{sz}}px`,`height:${{sz}}px`,
      `left:${{Math.random()*100}}%`,`top:${{Math.random()*100}}%`,
      `background:#00d4aa${{Math.floor(Math.random()*30+10).toString(16)}}`,
      `animation-duration:${{Math.random()*8+6}}s`,
      `animation-delay:-${{Math.random()*8}}s`,
    ].join(';');
    mesh.appendChild(p);
  }}
}}

function buildDots() {{
  const c=document.getElementById('scenedots');
  SCENE_META.forEach((_,i)=>{{
    const d=document.createElement('div');
    d.className='sdot'; d.id='dot'+i;
    d.title=SCENE_META[i].name;
    d.onclick=()=>jumpTo(i);
    c.appendChild(d);
  }});
}}

function fillStatic() {{
  // Hero
  const proj=D.project_name, cl=D.client_name, dt=D.date_str;
  document.getElementById('h0-name').textContent=proj;
  document.getElementById('h0-client').textContent=
    (cl?'For '+cl:'')+((cl&&dt)?' · ':'')+dt;
  // Architecture
  document.getElementById('h2-pattern').textContent=D.arch_pattern+' Architecture';
  // Timeline
  document.getElementById('h3-dur').textContent=
    'Phased Delivery — '+D.duration_weeks;
  document.getElementById('h3-sub').textContent=
    (D.total_hours?D.total_hours.toLocaleString()+' hours  ·  ':'')+D.confidence+' confidence';
  // Risks
  document.getElementById('h5-title').textContent=
    D.risks.length+' Identified Risks  ·  Overall: '+D.risk_level+' ('+D.risk_score+'/10)';
  // Close
  document.getElementById('h6-title').textContent="Let's Build "+proj;
  document.getElementById('h6-sub').textContent=
    cl?'Partnering with '+cl+' to deliver excellence.':'On time. Within budget. Built to last.';
  // Team stats
  const tr=document.getElementById('team-row');
  tr.innerHTML=
    stat(D.team_size,'Team Size')+
    stat('$'+(D.total_annual?D.total_annual.toLocaleString():'0')+'/yr','Annual Cost')+
    stat(D.confidence,'Confidence');
  // Risk summary
  const rs=document.getElementById('risk-sum');
  rs.innerHTML=
    rsbox(D.high_r,'High','#ef4444')+
    rsbox(D.med_r,'Medium','#f59e0b')+
    rsbox(D.low_r,'Low','#22c55e');
}}
function stat(v,l){{return`<div class="team-stat"><div class="tstat-v">${{v}}</div><div class="tstat-l">${{l}}</div></div>`;}}
function rsbox(n,l,c){{return`<div class="rs-box" style="background:${{c}}14;border:1px solid ${{c}}33;color:${{c}}"><strong>${{n}}</strong> ${{l}}</div>`;}}

/* ════════════════════════════════════════════════════════════════════
   ARCHITECTURE — LIVE DRAW ENGINE
   Full enterprise architecture with 6 layers drawn live:
   🔒 Security Banner  →  CLIENT | SERVICES | INTEGRATION | DATA
   →  📊 Monitoring Banner
   Animated connections and data-flow particles between every layer.
════════════════════════════════════════════════════════════════════ */
let _archT=[];
let _archDots=[];

function _aat(ms,fn){{ _archT.push(setTimeout(fn,ms)); }}

function clearArchAnim(){{
  _archT.forEach(t=>clearTimeout(t)); _archT=[];
  _archDots.forEach(el=>{{try{{el.remove();}}catch(_){{}}}}); _archDots=[];
}}

/* ── Layer classifier ── */
function _archLayer(comp){{
  const nm=(comp.name||'').toLowerCase();
  const az=(comp.azure||'').toLowerCase();
  const ty=(comp.type||'').toLowerCase();
  const t=`${{ty}} ${{nm}} ${{az}}`;

  // Security (tight — avoid swallowing generic app components)
  if(/key vault|entra|azure ad\b|b2c\b|waf\b|ddos|front door|firewall|defender|sentinel|oauth|openid|saml|mfa|api management|apim\b/.test(t)) return 's';
  if(/\bauth(?:entication|orization)?\b/.test(t)) return 's';

  // Monitoring
  if(/application insight|app insight|log analytic|azure monitor|alert rule|telemetry|diagnostic/.test(t)) return 'm';
  if(/\bmonitor\b|observabilit/.test(t)) return 'm';

  // CLIENT (presentation layer — must be clearly UI/frontend)
  if(/static web app|power app|power page|spa\b|pwa\b|blazor|flutter|react\b|angular\b|vue\b/.test(t)) return 0;
  if(/\bportal\b|\bdashboard\b|\bfrontend\b|front.?end|mobile app|ios app|android app/.test(t)) return 0;
  if(/web application|web client|user interface|chat.*ui|chat.*interface/.test(t)) return 0;

  // INTEGRATION (messaging, pipelines, orchestration)
  if(/service bus|event hub|event grid|azure queue|message queue|kafka|rabbitmq/.test(t)) return 2;
  if(/logic app|azure function|data factory|synapse pipeline|stream analytic/.test(t)) return 2;
  if(/\betl\b|data pipeline|data ingestion|orchestrat|workflow engine|pubsub/.test(t)) return 2;

  // DATA (storage, persistence, search)
  if(/cosmos db|azure sql|sql database|postgres|mysql|mongodb|cassandra/.test(t)) return 3;
  if(/redis|azure cache|blob storage|azure storage|data lake|synapse analytic/.test(t)) return 3;
  if(/ai search|cognitive search|azure search|table storage|file share|\bwarehouse\b/.test(t)) return 3;

  return 1; // APP SERVICES default
}}

/* ── Smart column defaults — project-type aware ── */
function _colDefaults(idx,D){{
  const ctx=`${{D.project_name||''}} ${{D.client_name||''}} ${{D.arch_pattern||''}} ${{(D.tech||[]).join(' ')}}`.toLowerCase();
  const isFin   =/financ|bank|trading|payment|invest|wealth|account|credit|insurance/.test(ctx);
  const isAI    =/\bai\b|machine.learn|\bml\b|\bllm\b|genai|nlp|intelligence|openai|cognitiv|gpt/.test(ctx);
  const isData  =/data.?engineer|analytic|warehouse|\bbi\b|reporting|insight/.test(ctx);
  const isHealth=/health|medical|clinical|patient|hospital|pharma|ehr|fhir/.test(ctx);
  const isRetail=/retail|ecommerce|e.commerce|shop|commerce|order|product|catalog/.test(ctx);
  const isCloud =/\bcloud\b|devops|platform|infra|kubernetes|container|cicd|deploy/.test(ctx);
  const isMedia =/media|content|stream|video|audio|publish|cms/.test(ctx);

  if(idx===0){{  // CLIENT LAYER
    if(isFin)    return[{{name:'Financial Portal',   azure:'Azure Static Web Apps'}},{{name:'Mobile Banking',      azure:'React Native + CDN'}},{{name:'Trader Dashboard',   azure:'Power BI Embedded'}}];
    if(isAI)     return[{{name:'AI Chat Interface',  azure:'React + Static Web Apps'}},{{name:'Results Dashboard',  azure:'Power BI Embedded'}},{{name:'User Portal',         azure:'Azure AD B2C'}}];
    if(isData)   return[{{name:'Analytics Portal',   azure:'Power BI Embedded'}},{{name:'Self-Service UI',     azure:'Azure Static Web Apps'}},{{name:'Reports Viewer',      azure:'Azure AD B2C'}}];
    if(isHealth) return[{{name:'Patient Portal',     azure:'Azure Static Web Apps'}},{{name:'Clinical Dashboard', azure:'Power Apps'}},{{name:'Telehealth App',     azure:'Azure Communication Svc'}}];
    if(isRetail) return[{{name:'Web Storefront',     azure:'Azure Static Web Apps'}},{{name:'Customer App',       azure:'React Native + CDN'}},{{name:'Seller Portal',       azure:'Azure AD B2C'}}];
    if(isCloud)  return[{{name:'Admin Console',      azure:'Azure Static Web Apps'}},{{name:'Ops Dashboard',      azure:'Azure Monitor Workbooks'}},{{name:'Self-Service Portal',azure:'Power Apps'}}];
    if(isMedia)  return[{{name:'Web Player',         azure:'Azure Static Web Apps'}},{{name:'Content Studio',    azure:'Azure AD B2C'}},{{name:'Mobile App',         azure:'React Native + CDN'}}];
    return       [{{name:'Web Application',      azure:'Azure Static Web Apps'}},{{name:'Mobile App',         azure:'React Native + CDN'}},{{name:'Admin Portal',       azure:'Azure AD B2C'}}];
  }}
  if(idx===2){{  // INTEGRATION LAYER
    if(isFin)    return[{{name:'Transaction Events', azure:'Azure Service Bus'}},{{name:'Payment Gateway',     azure:'Azure API Management'}},{{name:'Market Data Feed',   azure:'Azure Event Hub'}}];
    if(isAI)     return[{{name:'AI Orchestrator',    azure:'Azure Functions'}},{{name:'Model Event Bus',     azure:'Azure Service Bus'}},{{name:'Data Ingestion',       azure:'Azure Data Factory'}}];
    if(isData)   return[{{name:'ETL Pipeline',       azure:'Azure Data Factory'}},{{name:'Stream Processor',   azure:'Azure Stream Analytics'}},{{name:'Ingest Event Hub',   azure:'Azure Event Hub'}}];
    if(isHealth) return[{{name:'HL7/FHIR Bridge',    azure:'Azure Logic Apps'}},{{name:'Appointment Bus',    azure:'Azure Service Bus'}},{{name:'Notification Queue',  azure:'Azure Storage Queue'}}];
    if(isRetail) return[{{name:'Order Events',       azure:'Azure Service Bus'}},{{name:'Inventory Sync',    azure:'Azure Event Grid'}},{{name:'Fulfillment Queue',   azure:'Azure Storage Queue'}}];
    if(isCloud)  return[{{name:'Deployment Pipeline',azure:'Azure DevOps / GitHub'}},{{name:'Config Events',     azure:'Azure Event Grid'}},{{name:'Audit Bus',           azure:'Azure Service Bus'}}];
    if(isMedia)  return[{{name:'Media Pipeline',     azure:'Azure Media Services'}},{{name:'Content Events',   azure:'Azure Event Grid'}},{{name:'CDN Orchestrator',   azure:'Azure Functions'}}];
    return       [{{name:'Message Bus',          azure:'Azure Service Bus'}},{{name:'Event Hub',          azure:'Azure Event Hub'}},{{name:'Workflow Engine',     azure:'Azure Logic Apps'}}];
  }}
  if(idx===1){{  // APP SERVICES (fill if genuinely empty)
    if(isFin)    return[{{name:'Risk Engine',         azure:'Azure App Service'}},{{name:'Pricing Service',   azure:'Azure App Service'}},{{name:'Compliance API',     azure:'Azure App Service'}}];
    if(isAI)     return[{{name:'AI Processing API',   azure:'Azure App Service'}},{{name:'Model Inference',   azure:'Azure ML Online Endpoint'}},{{name:'Enrichment Service',azure:'Azure Functions'}}];
    if(isData)   return[{{name:'Data Processing API', azure:'Azure App Service'}},{{name:'Analytics Engine',  azure:'Azure Databricks'}},{{name:'Query Service',       azure:'Azure App Service'}}];
    if(isHealth) return[{{name:'Clinical Decision',   azure:'Azure App Service'}},{{name:'Patient Matching',  azure:'Azure App Service'}},{{name:'Scheduling Engine',  azure:'Azure App Service'}}];
    if(isRetail) return[{{name:'Cart Service',        azure:'Azure App Service'}},{{name:'Pricing Engine',    azure:'Azure App Service'}},{{name:'Recommendation API', azure:'Azure App Service'}}];
    return       [{{name:'Business Logic API',   azure:'Azure App Service'}},{{name:'Processing Service', azure:'Azure App Service'}},{{name:'Notification Service',azure:'Azure Communication'}}];
  }}
  if(idx===3){{  // DATA LAYER (fill if genuinely empty)
    if(isFin)    return[{{name:'Transaction DB',      azure:'Azure SQL Database'}},{{name:'Market Data Store', azure:'Azure Cosmos DB'}},{{name:'Audit Archive',      azure:'Azure Blob Storage'}}];
    if(isAI)     return[{{name:'Knowledge Base',      azure:'Azure AI Search'}},{{name:'Vector Store',       azure:'Azure Cosmos DB'}},{{name:'Model Artifacts',     azure:'Azure Blob Storage'}}];
    if(isData)   return[{{name:'Data Lake',           azure:'Azure Data Lake Gen2'}},{{name:'Data Warehouse',    azure:'Azure Synapse Analytics'}},{{name:'Serving Cache',     azure:'Azure Redis Cache'}}];
    if(isHealth) return[{{name:'Patient Records',     azure:'Azure Cosmos DB'}},{{name:'Clinical Data',      azure:'Azure SQL Database'}},{{name:'Imaging Store',      azure:'Azure Blob Storage'}}];
    if(isRetail) return[{{name:'Product Catalog',     azure:'Azure Cosmos DB'}},{{name:'Customer DB',        azure:'Azure SQL Database'}},{{name:'Order History',      azure:'Azure Table Storage'}}];
    if(isCloud)  return[{{name:'Config Store',        azure:'Azure App Configuration'}},{{name:'State DB',          azure:'Azure Cosmos DB'}},{{name:'Artifact Registry',  azure:'Azure Container Registry'}}];
    return       [{{name:'Primary Database',     azure:'Azure Cosmos DB'}},{{name:'Cache Layer',        azure:'Azure Redis Cache'}},{{name:'File Storage',       azure:'Azure Blob Storage'}}];
  }}
  return[];
}}

function buildArch(){{
  const svg=document.getElementById('arch-svg');
  const badge=document.getElementById('arch-lbadge');
  const comps=D.components||[];

  // ── Layout constants ──────────────────────────────────────────────
  const W=830, H=440, PAD=12;
  const BAN_H=68;
  const BAN_Y_T=8,  BAN_Y_B=H-8-BAN_H;   // 364
  const GAP_V=14;
  const COL_Y=BAN_Y_T+BAN_H+GAP_V;        // 90
  const COL_BOT=BAN_Y_B-GAP_V;            // 350
  const COL_H=COL_BOT-COL_Y;              // 260
  const COL_W=190;
  const COL_GAP=Math.floor((W-2*PAD-4*COL_W)/3); // ~13
  const COL_X=[PAD, PAD+COL_W+COL_GAP, PAD+2*(COL_W+COL_GAP), PAD+3*(COL_W+COL_GAP)];
  const COL_CX=COL_X.map(x=>Math.round(x+COL_W/2));
  const BAN_W=W-2*PAD; // 806

  // ── Classify components into 6 buckets ───────────────────────────
  const bk={{s:[],0:[],1:[],2:[],3:[],m:[]}};
  comps.forEach(c=>{{
    const l=_archLayer(c);
    (bk[l]=bk[l]||[]).push(c);
  }});

  // Fill any empty main-tier bucket with project-aware smart defaults
  [0,1,2,3].forEach(i=>{{ if(!(bk[i]||[]).length) bk[i]=_colDefaults(i,D); }});

  // Security + Monitoring banners — use real components if ≥2, else fixed defaults
  const SEC_DEF=[
    {{name:'API Gateway',    azure:'Azure API Management'}},
    {{name:'Identity & Auth',azure:'Azure AD / Entra ID'}},
    {{name:'Key Vault',      azure:'Azure Key Vault'}},
    {{name:'WAF & DDoS',     azure:'Front Door + DDoS Protection'}}
  ];
  const MON_DEF=[
    {{name:'App Insights',   azure:'Application Insights'}},
    {{name:'Log Analytics',  azure:'Log Analytics Workspace'}},
    {{name:'Azure Monitor',  azure:'Azure Monitor Metrics'}},
    {{name:'Alert Rules',    azure:'Action Groups & Alerts'}}
  ];
  const secItems=(bk['s']||[]).length>=2?(bk['s']||[]).slice(0,4):SEC_DEF;
  const monItems=(bk['m']||[]).length>=2?(bk['m']||[]).slice(0,4):MON_DEF;

  const TIER_LABEL=['CLIENT LAYER','APP SERVICES','INTEGRATION','DATA LAYER'];
  const TIER_CLR=['#7c3aed','#0078d4','#06b6d4','#10b981'];
  const SEC_CLR='#f59e0b', MON_CLR='#818cf8';

  let out='';

  // ── SVG Defs ──────────────────────────────────────────────────────
  out+='<defs>';
  // Column gradients
  TIER_CLR.forEach((clr,i)=>{{
    out+=`<linearGradient id="tcg${{i}}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${{clr}}" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="${{clr}}" stop-opacity="0.03"/>
    </linearGradient>`;
  }});
  // Banner gradients
  out+=`<linearGradient id="scg" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="${{SEC_CLR}}" stop-opacity="0.14"/>
    <stop offset="50%" stop-color="${{SEC_CLR}}" stop-opacity="0.06"/>
    <stop offset="100%" stop-color="${{SEC_CLR}}" stop-opacity="0.14"/>
  </linearGradient>
  <linearGradient id="mcg" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0%" stop-color="${{MON_CLR}}" stop-opacity="0.14"/>
    <stop offset="50%" stop-color="${{MON_CLR}}" stop-opacity="0.06"/>
    <stop offset="100%" stop-color="${{MON_CLR}}" stop-opacity="0.14"/>
  </linearGradient>`;
  // Arrow markers for each tier + banners
  [...TIER_CLR,SEC_CLR,MON_CLR].forEach((clr,i)=>{{
    out+=`<marker id="am${{i}}" markerWidth="9" markerHeight="9" refX="7" refY="4.5" orient="auto">
      <path d="M0,1 L0,8 L9,4.5 z" fill="${{clr}}" opacity="0.85"/>
    </marker>`;
  }});
  // Down markers (for vertical paths)
  [SEC_CLR,MON_CLR].forEach((clr,i)=>{{
    out+=`<marker id="amd${{i}}" markerWidth="7" markerHeight="7" refX="3.5" refY="6" orient="auto">
      <path d="M0,0 L7,0 L3.5,6 z" fill="${{clr}}" opacity="0.8"/>
    </marker>`;
  }});
  out+='</defs>';

  // ── Ambient column glows ──────────────────────────────────────────
  TIER_CLR.forEach((clr,i)=>{{
    out+=`<ellipse cx="${{COL_CX[i]}}" cy="${{COL_Y+COL_H/2}}"
      rx="96" ry="130" fill="${{clr}}" opacity="0.013"/>`;
  }});

  // ══ SECURITY BANNER ═══════════════════════════════════════════════
  const sBanPerim=2*(BAN_W+BAN_H);
  out+=`<rect id="sec-rect" data-arch x="${{PAD}}" y="${{BAN_Y_T}}" width="${{BAN_W}}" height="${{BAN_H}}"
    rx="12" fill="url(#scg)" stroke="${{SEC_CLR}}" stroke-width="1.5"
    stroke-dasharray="${{sBanPerim}}" stroke-dashoffset="${{sBanPerim}}" opacity="0"/>`;
  out+=`<text id="sec-lbl" data-arch x="${{W/2}}" y="${{BAN_Y_T+15}}" text-anchor="middle"
    font-size="8" font-weight="800" letter-spacing="3" fill="${{SEC_CLR}}" opacity="0">
    🔒  SECURITY, IDENTITY &amp; ACCESS CONTROL</text>`;
  out+=`<line id="sec-line" data-arch x1="${{PAD+14}}" y1="${{BAN_Y_T+20}}"
    x2="${{W-PAD-14}}" y2="${{BAN_Y_T+20}}" stroke="${{SEC_CLR}}" stroke-width="0.5" opacity="0"/>`;

  // Security component boxes
  const SBOX_W=Math.floor((BAN_W-5*8)/4);
  const SBOX_H=36, SBOX_Y=BAN_Y_T+23;
  secItems.forEach((item,si)=>{{
    const sx=PAD+8+si*(SBOX_W+8);
    const snm=item.name.length>22?item.name.substring(0,21)+'…':item.name;
    const saz=(item.azure||'').length>26?item.azure.substring(0,25)+'…':item.azure;
    const sbp=2*(SBOX_W+SBOX_H);
    out+=`<g id="sb${{si}}" data-arch opacity="0">
      <rect id="sbr${{si}}" data-arch x="${{sx}}" y="${{SBOX_Y}}" width="${{SBOX_W}}" height="${{SBOX_H}}"
        rx="6" fill="${{SEC_CLR}}14" stroke="${{SEC_CLR}}" stroke-width="0.9"
        stroke-dasharray="${{sbp}}" stroke-dashoffset="${{sbp}}"/>
      <text x="${{sx+SBOX_W/2}}" y="${{SBOX_Y+14}}" text-anchor="middle"
        font-size="9.5" font-weight="700" fill="#fcd34d"
        data-arch id="sbn${{si}}" opacity="0">${{snm}}</text>
      <text x="${{sx+SBOX_W/2}}" y="${{SBOX_Y+27}}" text-anchor="middle"
        font-size="7" fill="${{SEC_CLR}}99"
        data-arch id="sba${{si}}" opacity="0">${{saz}}</text>
    </g>`;
  }});

  // ══ MONITORING BANNER ═════════════════════════════════════════════
  const mBanPerim=2*(BAN_W+BAN_H);
  out+=`<rect id="mon-rect" data-arch x="${{PAD}}" y="${{BAN_Y_B}}" width="${{BAN_W}}" height="${{BAN_H}}"
    rx="12" fill="url(#mcg)" stroke="${{MON_CLR}}" stroke-width="1.5"
    stroke-dasharray="${{mBanPerim}}" stroke-dashoffset="${{mBanPerim}}" opacity="0"/>`;
  out+=`<text id="mon-lbl" data-arch x="${{W/2}}" y="${{BAN_Y_B+15}}" text-anchor="middle"
    font-size="8" font-weight="800" letter-spacing="3" fill="${{MON_CLR}}" opacity="0">
    📊  MONITORING, OBSERVABILITY &amp; ALERTING</text>`;
  out+=`<line id="mon-line" data-arch x1="${{PAD+14}}" y1="${{BAN_Y_B+20}}"
    x2="${{W-PAD-14}}" y2="${{BAN_Y_B+20}}" stroke="${{MON_CLR}}" stroke-width="0.5" opacity="0"/>`;

  // Monitoring component boxes
  const MBOX_Y=BAN_Y_B+23;
  monItems.forEach((item,mi)=>{{
    const mx=PAD+8+mi*(SBOX_W+8);
    const mnm=item.name.length>22?item.name.substring(0,21)+'…':item.name;
    const maz=(item.azure||'').length>26?item.azure.substring(0,25)+'…':item.azure;
    const mbp=2*(SBOX_W+SBOX_H);
    out+=`<g id="mb${{mi}}" data-arch opacity="0">
      <rect id="mbr${{mi}}" data-arch x="${{mx}}" y="${{MBOX_Y}}" width="${{SBOX_W}}" height="${{SBOX_H}}"
        rx="6" fill="${{MON_CLR}}14" stroke="${{MON_CLR}}" stroke-width="0.9"
        stroke-dasharray="${{mbp}}" stroke-dashoffset="${{mbp}}"/>
      <text x="${{mx+SBOX_W/2}}" y="${{MBOX_Y+14}}" text-anchor="middle"
        font-size="9.5" font-weight="700" fill="#c7d2fe"
        data-arch id="mbn${{mi}}" opacity="0">${{mnm}}</text>
      <text x="${{mx+SBOX_W/2}}" y="${{MBOX_Y+27}}" text-anchor="middle"
        font-size="7" fill="${{MON_CLR}}99"
        data-arch id="mba${{mi}}" opacity="0">${{maz}}</text>
    </g>`;
  }});

  // ══ MAIN TIER COLUMNS ═════════════════════════════════════════════
  for(let i=0;i<4;i++){{
    const cx=COL_X[i], cw=COL_W, cy=COL_Y, ch=COL_H;
    const perim=2*(cw+ch);
    const tc=(bk[i]||[]);
    const maxC=Math.min(tc.length,4);
    const boxH=48, boxW=cw-16, boxX=cx+8;
    const usable=ch-30;
    const sp=maxC>0?Math.min(14,(usable-maxC*boxH)/(maxC+1)):0;
    const clr=TIER_CLR[i];

    // Column border (drawn)
    out+=`<rect id="cb${{i}}" data-arch x="${{cx}}" y="${{cy}}" width="${{cw}}" height="${{ch}}"
      rx="11" fill="url(#tcg${{i}})" stroke="${{clr}}" stroke-width="1.6"
      stroke-dasharray="${{perim}}" stroke-dashoffset="${{perim}}" opacity="0"/>`;
    // Top glow accent
    out+=`<line id="ca${{i}}" data-arch x1="${{cx+14}}" y1="${{cy}}" x2="${{cx+cw-14}}" y2="${{cy}}"
      stroke="${{clr}}" stroke-width="2.8" stroke-linecap="round" opacity="0"/>`;
    // Tier label
    out+=`<text id="ct${{i}}" data-arch x="${{cx+cw/2}}" y="${{cy+16}}" text-anchor="middle"
      font-size="7.5" font-weight="800" letter-spacing="2.5" fill="${{clr}}" opacity="0">
      ${{TIER_LABEL[i]}}</text>`;
    // Separator
    out+=`<line id="cl${{i}}" data-arch x1="${{cx+12}}" y1="${{cy+20}}" x2="${{cx+cw-12}}" y2="${{cy+20}}"
      stroke="${{clr}}" stroke-width="0.6" opacity="0"/>`;

    // Component boxes
    tc.slice(0,4).forEach((comp,ci)=>{{
      const by=cy+26+sp*(ci+1)+ci*boxH;
      const nm=comp.name.length>21?comp.name.substring(0,20)+'…':comp.name;
      const az=(comp.azure||'').length>25?comp.azure.substring(0,24)+'…':(comp.azure||'');
      const bp=2*(boxW+boxH);
      out+=`<g id="bx${{i}}_${{ci}}" data-arch opacity="0">
        <rect id="br${{i}}_${{ci}}" data-arch x="${{boxX}}" y="${{by}}" width="${{boxW}}" height="${{boxH}}"
          rx="7" fill="${{clr}}1c" stroke="${{clr}}" stroke-width="0.9"
          stroke-dasharray="${{bp}}" stroke-dashoffset="${{bp}}"/>
        <circle cx="${{boxX+10}}" cy="${{by+boxH/2}}" r="3.5" fill="${{clr}}"
          data-arch id="bd${{i}}_${{ci}}" opacity="0"/>
        <text x="${{boxX+21}}" y="${{by+18}}" font-size="10" font-weight="700" fill="#e2e8f0"
          data-arch id="bn${{i}}_${{ci}}" opacity="0">${{nm}}</text>
        ${{az?`<text x="${{boxX+21}}" y="${{by+33}}" font-size="8" fill="${{clr}}cc"
          data-arch id="ba${{i}}_${{ci}}" opacity="0">${{az}}</text>`:''}}
      </g>`;
    }});
    if(tc.length>4){{
      out+=`<text id="bm${{i}}" data-arch x="${{cx+cw/2}}" y="${{cy+ch-6}}" text-anchor="middle"
        font-size="7.5" fill="${{clr}}66" opacity="0">+${{tc.length-4}} more</text>`;
    }}
  }}

  // ══ CONNECTIONS ═══════════════════════════════════════════════════
  // Vertical: Security Banner → Columns (amber, downward)
  COL_CX.forEach((cx,i)=>{{
    const y1=BAN_Y_T+BAN_H, y2=COL_Y, pl=y2-y1;
    out+=`<line id="vsc${{i}}" data-arch x1="${{cx}}" y1="${{y1}}" x2="${{cx}}" y2="${{y2}}"
      stroke="${{SEC_CLR}}" stroke-width="1.2"
      stroke-dasharray="${{pl}}" stroke-dashoffset="${{pl}}" opacity="0"
      marker-end="url(#amd0)"/>`;
  }});

  // Horizontal: Tier columns L→R
  for(let i=0;i<3;i++){{
    const x1=COL_X[i]+COL_W, x2=COL_X[i+1], ym=COL_Y+COL_H/2;
    const pl=x2-x1;
    out+=`<path id="hcp${{i}}" data-arch
      d="M${{x1}},${{ym}} C${{x1+pl*.45}},${{ym}} ${{x2-pl*.45}},${{ym}} ${{x2}},${{ym}}"
      fill="none" stroke="${{TIER_CLR[i]}}" stroke-width="2.2"
      stroke-dasharray="400" stroke-dashoffset="400" opacity="0"
      marker-end="url(#am${{i}})"/>`;
    // Echo arc
    out+=`<path id="hcp2${{i}}" data-arch
      d="M${{x1}},${{ym-10}} C${{x1+pl*.35}},${{ym-10}} ${{x2-pl*.35}},${{ym+10}} ${{x2}},${{ym+10}}"
      fill="none" stroke="${{TIER_CLR[i]}}" stroke-width="0.65"
      stroke-dasharray="400" stroke-dashoffset="400" opacity="0"/>`;
  }}

  // Vertical: Columns → Monitoring Banner (indigo, downward)
  COL_CX.forEach((cx,i)=>{{
    const y1=COL_Y+COL_H, y2=BAN_Y_B, pl=y2-y1;
    out+=`<line id="vcm${{i}}" data-arch x1="${{cx}}" y1="${{y1}}" x2="${{cx}}" y2="${{y2}}"
      stroke="${{MON_CLR}}" stroke-width="1.2"
      stroke-dasharray="${{pl}}" stroke-dashoffset="${{pl}}" opacity="0"
      marker-end="url(#amd1)"/>`;
  }});

  // Data-flow label
  if(D.data_flow&&D.data_flow.length){{
    out+=`<text id="dfl" data-arch x="${{W/2}}" y="${{H-1}}" text-anchor="middle"
      font-size="7" fill="#1e293b" letter-spacing="0.5" opacity="0">
      ${{D.data_flow.slice(0,5).join(' → ')}}
    </text>`;
  }}

  svg.innerHTML=out;

  // ── Layer badges ──────────────────────────────────────────────────
  if(badge){{
    const lbls=[
      {{t:'🔒 Security',c:SEC_CLR}},
      ...TIER_LABEL.map((t,i)=>{{return{{t,c:TIER_CLR[i]}};}}),
      {{t:'📊 Monitoring',c:MON_CLR}}
    ];
    badge.innerHTML=lbls.map((x,i)=>
      `<span class="alb" id="alb${{i}}"
        style="background:${{x.c}}18;border:1px solid ${{x.c}}44;color:${{x.c}}">${{x.t}}</span>`
    ).join('');
  }}
}}

/* ──────────────────────────────────────────────────────────────────
   resetArch — snap all [data-arch] elements back to initial state
──────────────────────────────────────────────────────────────────── */
function resetArch(){{
  document.querySelectorAll('[data-arch]').forEach(el=>{{
    el.style.transition='none';
    el.style.opacity='0';
    const da=el.getAttribute('stroke-dasharray');
    if(da) el.style.strokeDashoffset=da;
  }});
  document.querySelectorAll('.alb').forEach(el=>el.classList.remove('show'));
}}

/* ── Animation helpers ───────────────────────────────────────────── */
function _drawBorder(id,dur){{
  const el=document.getElementById(id);
  if(!el)return;
  el.style.opacity='1';
  el.style.transition=`stroke-dashoffset ${{dur}}ms cubic-bezier(.4,0,.2,1)`;
  el.style.strokeDashoffset='0';
}}
function _fadeEl(id,dur){{
  const el=document.getElementById(id);
  if(!el)return;
  el.style.transition=`opacity ${{dur}}ms ease`;
  el.style.opacity='1';
}}
function _drawPath(id,dur){{
  const el=document.getElementById(id);
  if(!el)return;
  const da=el.getAttribute('stroke-dasharray')||'400';
  el.style.transition='none';
  el.style.strokeDashoffset=da;
  el.style.opacity='0';
  void el.getBoundingClientRect();
  el.style.transition=`stroke-dashoffset ${{dur}}ms cubic-bezier(.4,0,.2,1),opacity .3s ease`;
  el.style.opacity='0.9';
  el.style.strokeDashoffset='0';
}}

/* ──────────────────────────────────────────────────────────────────
   animateArch — 7-phase cinematic live-draw sequence
──────────────────────────────────────────────────────────────────── */
function animateArch(){{
  clearArchAnim();
  resetArch();
  void document.getElementById('arch-svg')?.getBoundingClientRect();

  // ── Phase 1 (180ms): Security banner draws ────────────────────────
  _aat(180,()=>_drawBorder('sec-rect',900));
  _aat(600,()=>{{_fadeEl('sec-lbl',350);_fadeEl('sec-line',350);}});
  _aat(700,()=>{{const b=document.getElementById('alb0');if(b)b.classList.add('show');}});
  // Security component cards appear L→R
  for(let si=0;si<4;si++){{
    _aat(750+si*210,()=>{{
      const g=document.getElementById('sb'+si);
      if(g){{g.style.transition='none';g.style.opacity='1';}}
      _aat(15,()=>_drawBorder('sbr'+si,350));
    }});
    _aat(950+si*210,()=>{{_fadeEl('sbn'+si,220);_fadeEl('sba'+si,220);}});
  }}

  // ── Phase 2 (1900ms): Monitoring banner draws ─────────────────────
  _aat(1900,()=>_drawBorder('mon-rect',900));
  _aat(2300,()=>{{_fadeEl('mon-lbl',350);_fadeEl('mon-line',350);}});
  _aat(2400,()=>{{const b=document.getElementById('alb5');if(b)b.classList.add('show');}});
  for(let mi=0;mi<4;mi++){{
    _aat(2450+mi*190,()=>{{
      const g=document.getElementById('mb'+mi);
      if(g){{g.style.transition='none';g.style.opacity='1';}}
      _aat(15,()=>_drawBorder('mbr'+mi,320));
    }});
    _aat(2620+mi*190,()=>{{_fadeEl('mbn'+mi,200);_fadeEl('mba'+mi,200);}});
  }}

  // ── Phase 3 (3300ms): Main tier columns draw L→R ─────────────────
  for(let i=0;i<4;i++){{
    const base=3300+i*680;
    // Draw column border
    _aat(base,()=>{{
      const cb=document.getElementById('cb'+i);
      if(cb){{cb.style.transition='none';cb.style.opacity='1';}}
      _aat(15,()=>_drawBorder('cb'+i,740));
    }});
    _aat(base+500,()=>{{_fadeEl('ca'+i,350);_fadeEl('ct'+i,300);_fadeEl('cl'+i,300);}});
    _aat(base+670,()=>{{const b=document.getElementById('alb'+(i+1));if(b)b.classList.add('show');}});
    // Component cards (try all 4 slots, skip if not present)
    for(let ci=0;ci<4;ci++){{
      const cb2=base+710+ci*260;
      _aat(cb2,()=>{{
        const g=document.getElementById(`bx${{i}}_${{ci}}`);
        if(!g)return;
        g.style.transition='none';g.style.opacity='1';
        _aat(15,()=>_drawBorder(`br${{i}}_${{ci}}`,380));
      }});
      _aat(cb2+310,()=>{{_fadeEl(`bd${{i}}_${{ci}}`,200);}});
      _aat(cb2+370,()=>{{_fadeEl(`bn${{i}}_${{ci}}`,260);}});
      _aat(cb2+450,()=>{{_fadeEl(`ba${{i}}_${{ci}}`,260);}});
    }}
    _aat(base+820,()=>_fadeEl('bm'+i,300));
  }}

  // ── Phase 4 (8400ms): Security → Column vertical arrows ──────────
  for(let i=0;i<4;i++){{
    _aat(8400+i*130,()=>_drawPath('vsc'+i,420));
  }}

  // ── Phase 5 (9000ms): Horizontal tier→tier arrows ─────────────────
  for(let i=0;i<3;i++){{
    _aat(9000+i*380,()=>_drawPath('hcp'+i,760));
    _aat(9000+i*380+200,()=>_drawPath('hcp2'+i,600));
  }}

  // ── Phase 6 (10200ms): Column → Monitoring vertical arrows ───────
  for(let i=0;i<4;i++){{
    _aat(10200+i*120,()=>_drawPath('vcm'+i,400));
  }}

  // ── Phase 7 (11000ms): Flow particles + data-flow label ──────────
  _aat(11000,()=>{{
    spawnArchParticles();
    _aat(200,()=>_fadeEl('dfl',800));
  }});
}}

/* ──────────────────────────────────────────────────────────────────
   spawnArchParticles
   3 particle streams: Security→Columns, Columns→Columns, Columns→Mon
──────────────────────────────────────────────────────────────────── */
function spawnArchParticles(){{
  const svg=document.getElementById('arch-svg');
  if(!svg)return;
  const TCLR=['#7c3aed','#0078d4','#06b6d4','#10b981'];
  const SEC_CLR='#f59e0b', MON_CLR='#818cf8';

  function dot(pathId,clr,dur,begin,r){{
    if(!document.getElementById(pathId))return;
    const c=document.createElementNS('http://www.w3.org/2000/svg','circle');
    c.setAttribute('r',r||'3');
    c.setAttribute('fill',clr);
    const mo=document.createElementNS('http://www.w3.org/2000/svg','animateMotion');
    mo.setAttribute('dur',dur+'s');
    mo.setAttribute('repeatCount','indefinite');
    mo.setAttribute('begin',begin+'s');
    mo.setAttribute('keyPoints','0;1');
    mo.setAttribute('keyTimes','0;1');
    mo.setAttribute('calcMode','linear');
    const mp=document.createElementNS('http://www.w3.org/2000/svg','mpath');
    mp.setAttribute('href','#'+pathId);
    mo.appendChild(mp);
    const ao=document.createElementNS('http://www.w3.org/2000/svg','animate');
    ao.setAttribute('attributeName','opacity');
    ao.setAttribute('values','0;0.95;0.95;0');
    ao.setAttribute('dur',dur+'s');
    ao.setAttribute('repeatCount','indefinite');
    ao.setAttribute('begin',begin+'s');
    c.appendChild(mo); c.appendChild(ao);
    svg.appendChild(c);
    _archDots.push(c);
  }}

  // Security → Columns (amber, 2 dots each)
  for(let i=0;i<4;i++){{
    dot('vsc'+i, SEC_CLR, 1.3, (i*0.28).toFixed(2), 2.5);
    dot('vsc'+i, SEC_CLR, 1.3, (i*0.28+0.65).toFixed(2), 1.8);
  }}
  // Horizontal tier→tier (tier colors, 3 dots each)
  for(let i=0;i<3;i++){{
    for(let p=0;p<3;p++){{
      dot('hcp'+i, TCLR[i], (1.8+p*.3).toFixed(2), (p*.58).toFixed(2), p===1?4.5:2.8);
    }}
  }}
  // Columns → Monitoring (indigo, 2 dots each)
  for(let i=0;i<4;i++){{
    dot('vcm'+i, MON_CLR, 1.3, (i*0.25).toFixed(2), 2.5);
    dot('vcm'+i, MON_CLR, 1.3, (i*0.25+0.65).toFixed(2), 1.8);
  }}
}}

/* ════════════════════════════════════════════════════════════════════
   SCENE ENGINE
════════════════════════════════════════════════════════════════════ */
function showScene(idx, forward) {{
  const prev=cur;
  cur=idx;
  // Exit old scene
  const oldEl=document.getElementById('s'+prev);
  if(oldEl && prev!==idx) {{
    oldEl.classList.remove('enter');
    oldEl.classList.add(forward===false?'exit-dn':'exit-up');
    setTimeout(()=>oldEl.classList.remove('exit-up','exit-dn'),600);
  }}
  // Enter new scene
  const el=document.getElementById('s'+idx);
  if(el){{
    el.classList.remove('exit-up','exit-dn');
    requestAnimationFrame(()=>requestAnimationFrame(()=>el.classList.add('enter')));
  }}
  // Scene-entry side effects
  switch(idx){{
    case 0: animateCounters(); break;
    case 3: animatePhases();   break;
    case 1: animateReqNums();  break;
    case 2: animateArch();     break;
  }}
  // UI
  updateUI();
  // Accent flash
  accentFlash(SCENE_META[idx].accent);
  // Show transition label briefly
  showLabel(SCENE_META[idx].icon, SCENE_META[idx].name);
}}

function updateUI() {{
  // Dots
  document.querySelectorAll('.sdot').forEach((d,i)=>d.classList.toggle('on',i===cur));
  // Progress bar
  document.getElementById('topfill').style.width=
    Math.round((cur/(NS-1))*100)+'%';
  // Scene label
  document.getElementById('sclbl').textContent=(cur+1)+' / '+NS;
  // Narration text
  document.getElementById('nartext').textContent=NAR[cur]||'';
  document.getElementById('narlbl').textContent=SCENE_META[cur].name;
}}

function accentFlash(clr) {{
  const f=document.getElementById('aflash');
  f.style.background=`radial-gradient(ellipse 60% 60% at 50% 50%,${{clr}}12,transparent)`;
  f.style.opacity='1';
  setTimeout(()=>f.style.opacity='0',800);
}}

function showLabel(icon,name) {{
  const sl=document.getElementById('slabel');
  document.getElementById('sl-icon').textContent=icon;
  document.getElementById('sl-name').textContent=name;
  sl.style.opacity='1';
  setTimeout(()=>sl.style.opacity='0',900);
}}

/* ════════════════════════════════════════════════════════════════════
   SCENE-SPECIFIC ANIMATIONS
════════════════════════════════════════════════════════════════════ */
function animateCounters() {{
  document.querySelectorAll('[data-target]').forEach(el=>{{
    const target=+el.dataset.target;
    if(!target) return;
    const pre=el.dataset.pre||'', suf=el.dataset.suf||'';
    const dur=1200, start=performance.now();
    function tick(now){{
      const p=Math.min((now-start)/dur,1);
      const e=1-Math.pow(1-p,3);
      el.textContent=pre+Math.round(e*target).toLocaleString()+suf;
      if(p<1) requestAnimationFrame(tick);
    }}
    requestAnimationFrame(tick);
  }});
}}

function animateReqNums() {{
  document.querySelectorAll('.rqnum[data-target]').forEach(el=>{{
    const target=+el.dataset.target;
    if(!target) return;
    const dur=900, start=performance.now();
    function tick(now){{
      const p=Math.min((now-start)/dur,1);
      el.textContent=Math.round((1-Math.pow(1-p,3))*target);
      if(p<1) requestAnimationFrame(tick);
    }}
    requestAnimationFrame(tick);
  }});
}}

function animatePhases() {{
  D.phases.forEach((p,i)=>{{
    const bar=document.getElementById('pb'+i);
    if(!bar) return;
    const maxH=Math.max(...D.phases.map(x=>x.hours));
    const w=maxH>0?Math.round(p.hours/maxH*100):0;
    bar.style.width='0%';
    setTimeout(()=>{{ bar.style.width=w+'%'; }}, 80+i*160);
  }});
}}

/* ════════════════════════════════════════════════════════════════════
   PLAYBACK — VOICE-SYNCED
   Slides never advance until the current narration finishes.
   Safety timer fires if speechSynthesis never calls onend (Chrome bug).
════════════════════════════════════════════════════════════════════ */
function togglePlay(){{
  if(playing) stopPlay(); else startPlay();
}}

function startPlay(){{
  playing=true;
  document.getElementById('playbtn').innerHTML='⏸&nbsp; Pause';
  document.getElementById('playbtn').classList.add('on');
  startScenePlayback();
}}

function stopPlay(){{
  playing=false;
  clearTimeout(safeT); clearTimeout(durationT);
  stopSpeech();
  setWave(false);
  document.getElementById('playbtn').innerHTML='▶&nbsp; Play';
  document.getElementById('playbtn').classList.remove('on');
}}

function startScenePlayback(){{
  if(!playing) return;
  clearTimeout(safeT); clearTimeout(durationT);
  const txt=(NAR[cur]||'').trim();
  const meta=SCENE_META[cur];

  if(voiceOn && window.speechSynthesis && txt){{
    // ── VOICE-DRIVEN ─────────────────────────────────────────────
    stopSpeech();
    utter=new SpeechSynthesisUtterance(txt);
    utter.rate=0.88; utter.pitch=1.0; utter.volume=0.95;

    // Pick best voice (async safe: voices may not be ready yet)
    const voices=window.speechSynthesis.getVoices();
    const pick=voices.find(v=>v.name.includes('Google UK English Female'))
             ||voices.find(v=>v.name.includes('Google US English'))
             ||voices.find(v=>/english.*female/i.test(v.name))
             ||voices.find(v=>v.lang&&v.lang.startsWith('en-'));
    if(pick) utter.voice=pick;

    utter.onstart =()=> setWave(true);
    utter.onend   =()=>{{
      setWave(false);
      clearTimeout(safeT);
      if(playing) setTimeout(advanceOrStop, 650); // brief pause between scenes
    }};
    utter.onerror =(e)=>{{
      setWave(false);
      clearTimeout(safeT);
      if(playing) setTimeout(advanceOrStop, 300);
    }};
    window.speechSynthesis.speak(utter);

    // Safety: if onend never fires (Chrome bug) advance after duration + 40s buffer
    safeT=setTimeout(()=>{{
      if(playing){{ stopSpeech(); setWave(false); advanceOrStop(); }}
    }}, meta.dur + 40000);

  }} else {{
    // ── TIMER-DRIVEN (voice off) ──────────────────────────────────
    setWave(false);
    durationT=setTimeout(()=>{{ if(playing) advanceOrStop(); }}, meta.dur);
  }}
}}

function advanceOrStop(){{
  clearTimeout(safeT); clearTimeout(durationT);
  if(cur<NS-1){{
    const nxt=cur+1;
    showScene(nxt, true);
    startScenePlayback();
  }} else {{
    stopPlay();
    // Completed — show replay nudge
    document.getElementById('nartext').textContent=
      '✅ Presentation complete! Click ↺ Replay or use the dots to revisit any scene.';
  }}
}}

/* ── Navigation ────────────────────────────────────────────────────── */
function nextS(){{
  stopSpeech(); clearTimeout(safeT); clearTimeout(durationT);
  if(cur<NS-1){{ showScene(cur+1,true); if(playing) startScenePlayback(); }}
}}
function prevS(){{
  stopSpeech(); clearTimeout(safeT); clearTimeout(durationT);
  if(cur>0){{ showScene(cur-1,false); if(playing) startScenePlayback(); }}
}}
function jumpTo(idx){{
  stopSpeech(); clearTimeout(safeT); clearTimeout(durationT);
  showScene(idx, idx>cur);
  if(playing) startScenePlayback();
}}
function restart(){{ stopPlay(); showScene(0,false); setTimeout(startPlay,400); }}

/* ── Voice ─────────────────────────────────────────────────────────── */
function toggleVoice(){{
  voiceOn=!voiceOn;
  const btn=document.getElementById('voicebtn');
  btn.textContent=voiceOn?'🔊 Voice On':'🔇 Voice Off';
  btn.classList.toggle('on',voiceOn);
  btn.classList.toggle('warn',!voiceOn);
  if(!voiceOn){{ stopSpeech(); setWave(false); }}
  // Restart current scene's timer/speech with new setting
  if(playing){{ clearTimeout(safeT); clearTimeout(durationT); startScenePlayback(); }}
}}

function stopSpeech(){{
  if(window.speechSynthesis){{ window.speechSynthesis.cancel(); }}
  utter=null;
}}

function setWave(active){{
  document.getElementById('wave').classList.toggle('idle',!active);
}}

// Chrome: voices load async
if(window.speechSynthesis){{
  window.speechSynthesis.getVoices();
  window.speechSynthesis.addEventListener('voiceschanged',()=>
    window.speechSynthesis.getVoices(), {{once:true}});
}}

// Chrome: resume if tab regains focus while speech was running
document.addEventListener('visibilitychange',()=>{{
  if(!document.hidden && window.speechSynthesis &&
     window.speechSynthesis.paused && playing){{
    window.speechSynthesis.resume();
  }}
}});

/* ── Fullscreen ────────────────────────────────────────────────────── */
function toggleFS(){{
  const btn=document.getElementById('fsbtn');
  if(!document.fullscreenElement){{
    document.documentElement.requestFullscreen&&
      document.documentElement.requestFullscreen();
    btn.textContent='✕ Exit FS';
  }} else {{
    document.exitFullscreen&&document.exitFullscreen();
    btn.textContent='⛶ Fullscreen';
  }}
}}

/* ── Keyboard shortcuts ────────────────────────────────────────────── */
document.addEventListener('keydown',(e)=>{{
  if(['INPUT','TEXTAREA'].includes(e.target.tagName)) return;
  if(e.key===' '){{ e.preventDefault(); togglePlay(); }}
  if(e.key==='ArrowRight') nextS();
  if(e.key==='ArrowLeft')  prevS();
  if(e.key.toLowerCase()==='f') toggleFS();
  if(e.key.toLowerCase()==='v') toggleVoice();
  if(e.key.toLowerCase()==='r') restart();
}});
</script>
</body>
</html>"""


# ── Public render function ────────────────────────────────────────────
def render_animated_explainer_tab(r: dict, se: dict, te: dict, ce: dict,
                                   ri: dict, ar: dict, ai_client=None):
    r  = safe_dict(r);  se = safe_dict(se)
    te = safe_dict(te); ce = safe_dict(ce)
    ri = safe_dict(ri); ar = safe_dict(ar)

    if not se and not te and not ce:
        st.info("Run the pipeline first — the Animated Explainer builds a cinematic, voice-narrated walkthrough of your full proposal.")
        return

    # ── Header ────────────────────────────────────────────────────────
    st.markdown("""
<div style="margin-bottom:14px">
  <div style="font-size:.6rem;font-weight:800;letter-spacing:3px;text-transform:uppercase;
              color:#00d4aa;margin-bottom:4px">🎬 ANIMATED PROPOSAL EXPLAINER</div>
  <div style="font-size:.84rem;color:#64748b">
    Cinematic, voice-narrated walkthrough · Voice stays in sync with each slide ·
    Fullscreen-ready for live client presentations
  </div>
</div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        use_ai = st.toggle("✨ AI-Enhanced Narration", value=True,
                            help="Uses AI to write natural spoken narration per scene")
    with c2:
        regen = st.button("🔄 Regenerate", use_container_width=True,
                           help="Rebuild presentation from latest proposal data")
    with c3:
        st.caption("Chrome recommended for voice")

    # ── Cache ─────────────────────────────────────────────────────────
    cache_key = "_anim_html_cache"
    data_hash = hash(
        safe_str(se.get("project_type","")) +
        str(safe_int(te.get("total_hours",0))) +
        str(safe_int(ce.get("total_monthly_cost",0)))
    )

    if regen or cache_key not in st.session_state or st.session_state.get("_anim_hash") != data_hash:
        with st.spinner("🎬 Building your animated presentation…"):
            d   = _extract(r, se, te, ce, ri, ar)
            nar = _ai_narration(d, ai_client) if use_ai and ai_client else _template_narration(d)
            st.session_state[cache_key]  = _build_html(d, nar)
            st.session_state["_anim_d"]  = d
            st.session_state["_anim_nar"] = nar
            st.session_state["_anim_hash"] = data_hash

    html_src = st.session_state.get(cache_key, "")
    if not html_src:
        st.error("Could not build presentation.")
        return

    st.markdown("---")

    # ── Narration script viewer ───────────────────────────────────────
    with st.expander("📝 Narration Script", expanded=False):
        nar  = st.session_state.get("_anim_nar", [])
        lbls = ["Hero / Opening","Scope & Deliverables","Architecture",
                "Timeline","Cost & Team","Risks","Closing"]
        for i, (lbl, line) in enumerate(zip(lbls, nar)):
            st.markdown(f"**Scene {i+1} — {lbl}**")
            st.caption(line)

    # ── Presentation ──────────────────────────────────────────────────
    components.html(html_src, height=700, scrolling=False)

    # ── Tips ──────────────────────────────────────────────────────────
    st.markdown("""
<div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:10px">
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;
              padding:8px 14px;font-size:.73rem;color:#64748b">
    <strong style="color:#94a3b8">▶ Play</strong> — voice narrates each slide; next slide only opens when narration finishes
  </div>
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;
              padding:8px 14px;font-size:.73rem;color:#64748b">
    <strong style="color:#94a3b8">⛶ Fullscreen</strong> — present directly to client (keyboard: F)
  </div>
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;
              padding:8px 14px;font-size:.73rem;color:#64748b">
    <strong style="color:#94a3b8">Keyboard</strong> — Space=play/pause  ←→=navigate  V=voice  R=restart
  </div>
  <div style="background:#0f172a;border:1px solid #1e293b;border-radius:8px;
              padding:8px 14px;font-size:.73rem;color:#64748b">
    <strong style="color:#94a3b8">● Dots</strong> — click any scene dot to jump to that section instantly
  </div>
</div>""", unsafe_allow_html=True)
