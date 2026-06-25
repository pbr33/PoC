# ═══════════════════════════════════════════════════════════════════════
#  DIAGRAM RENDERERS (Mermaid, Graphviz, 3D Fly-Through)
# ═══════════════════════════════════════════════════════════════════════
import re
import json
import io
import streamlit as st
from .utils import safe_int, safe_str, safe_list, safe_dict

try:
    import graphviz as gv_lib
    HAS_GRAPHVIZ = True
except ImportError:
    gv_lib = None
    HAS_GRAPHVIZ = False


# ═══════════════════════════════════════════════════════════════════════
#  DRAW.IO XML EXPORT  (File > Import > From diagrams.net in Lucidchart)
# ═══════════════════════════════════════════════════════════════════════

def generate_drawio_xml(ar: dict, se: dict = None) -> str:
    """Generate a draw.io (.drawio) XML file from architecture data.

    Layout mirrors the HTML diagram: horizontal flow tiers (Presentation →
    Application → AI → Data) with Security and Operations as full-width
    bands at the bottom.  Import into Lucidchart via File > Import > diagrams.net.
    """
    se = se or {}

    # ── reuse the same helpers from generate_arch_html_svg ──────────────
    def _safe_str(v): return str(v) if v else ""
    def _safe_list(v): return list(v) if isinstance(v, list) else []
    def _safe_dict(v): return dict(v) if isinstance(v, dict) else {}

    def _esc(s):
        return (_safe_str(s).replace("&", "&amp;").replace("<", "&lt;")
                             .replace(">", "&gt;").replace('"', "&quot;"))

    def _html_attr(html: str) -> str:
        """XML-encode an HTML string for safe use as an mxCell value attribute.
        Draw.io stores HTML labels XML-encoded inside the value attribute."""
        return (html.replace("&", "&amp;").replace("<", "&lt;")
                    .replace(">", "&gt;").replace('"', "&quot;"))

    comps = _safe_list(ar.get("components"))

    # provider detection (lightweight copy)
    def _provider(se_d):
        tech = " ".join(_safe_str(t) for t in _safe_list(se_d.get("technology_stack", []))).lower()
        proj = _safe_str(se_d.get("project_type", "")).lower()
        txt  = tech + " " + proj
        aws_score = sum(1 for kw in ["aws","amazon","s3","ec2","lambda","rds","sqs","sns","eks","ecs","dynamodb","bedrock","cloudfront"] if kw in txt)
        gcp_score = sum(1 for kw in ["gcp","google cloud","bigquery","cloud run","pub/sub","firebase","vertex","cloud sql"] if kw in txt)
        az_score  = sum(1 for kw in ["azure","cosmos","entra","azure sql","app service","azure openai","service bus"] if kw in txt)
        best = max([("aws", aws_score), ("gcp", gcp_score), ("azure", az_score)], key=lambda x: x[1])
        return best[0] if best[1] >= 1 else "azure"

    def _has_ai(se_d, ar_d):
        txt = (" ".join(_safe_str(t) for t in _safe_list(se_d.get("technology_stack", [])))
               + " " + _safe_str(se_d.get("project_type", ""))
               + " " + " ".join(_safe_str(c.get("name","")) + " " + _safe_str(c.get("azure_service",""))
                                 for c in _safe_list(ar_d.get("components", [])))).lower()
        return any(kw in txt for kw in ["openai","gpt","llm","ai search","machine learning","sagemaker","bedrock","vertex","cognitive"])

    provider = _provider(se)
    has_ai   = _has_ai(se, ar)

    TIER_COLORS = {
        "azure":        {"stroke": "#0078D4", "fill": "#EBF5FB", "comp_fill": "#DBEEFF"},
        "aws":          {"stroke": "#FF9900", "fill": "#FFF8EE", "comp_fill": "#FFE8C0"},
        "gcp":          {"stroke": "#4285F4", "fill": "#E8F0FE", "comp_fill": "#C8DCFF"},
        "application":  {"stroke": "#00B294", "fill": "#E6FFF9", "comp_fill": "#C0F5EB"},
        "ai":           {"stroke": "#5C2D91", "fill": "#F5F0FF", "comp_fill": "#DDD0F8"},
        "data":         {"stroke": "#107C10", "fill": "#E8F5E9", "comp_fill": "#C8EAC8"},
        "security":     {"stroke": "#D83B01", "fill": "#FFF3ED", "comp_fill": "#FFD5BB"},
        "operations":   {"stroke": "#E6A800", "fill": "#FFFBF0", "comp_fill": "#FFE98A"},
    }
    pres_colors  = TIER_COLORS.get(provider, TIER_COLORS["azure"])
    app_colors   = TIER_COLORS["application"]
    ai_colors    = TIER_COLORS["ai"]
    data_colors  = TIER_COLORS["data"]
    sec_colors   = TIER_COLORS["security"]
    ops_colors   = TIER_COLORS["operations"]

    TYPE_MAP = {
        "front door":"presentation","cdn":"presentation","web app":"presentation","react":"presentation",
        "angular":"presentation","spa":"presentation","api management":"presentation",
        "app service":"presentation","cloudfront":"presentation","alb":"presentation",
        "api gateway":"presentation","load balancer":"presentation","cloud cdn":"presentation",
        "cloud endpoints":"presentation","cloud load":"presentation","static web":"presentation",
        "function":"application","functions":"application","service bus":"application",
        "event hub":"application","logic app":"application","backend":"application",
        "container":"application","kubernetes":"application","aks":"application",
        "lambda":"application","ecs":"application","eks":"application",
        "sqs":"application","sns":"application","cloud run":"application",
        "cloud functions":"application","pub/sub":"application","fargate":"application",
        "openai":"ai","cognitive":"ai","search":"ai","ai search":"ai",
        "machine learning":"ai","ml":"ai","bedrock":"ai","sagemaker":"ai",
        "vertex":"ai","document ai":"ai","vision":"ai","speech":"ai","language":"ai",
        "sql":"data","cosmos":"data","blob":"data","storage":"data","redis":"data",
        "data lake":"data","synapse":"data","s3":"data","rds":"data","dynamodb":"data",
        "bigquery":"data","cloud storage":"data","cloud sql":"data","aurora":"data",
        "key vault":"security","active directory":"security","entra":"security",
        "firewall":"security","defender":"security","iam":"security","waf":"security",
        "cognito":"security","shield":"security","secrets manager":"security","kms":"security",
        "cloud armor":"security","identity platform":"security",
        "monitor":"operations","insights":"operations","devops":"operations",
        "cloudwatch":"operations","cloudtrail":"operations","codepipeline":"operations",
        "cloud logging":"operations","cloud monitoring":"operations","cloud build":"operations",
    }

    def get_tier(comp):
        txt = (_safe_str(comp.get("name","")) + " " + _safe_str(comp.get("type",""))
               + " " + _safe_str(comp.get("azure_service",""))).lower()
        for kw, tier in TYPE_MAP.items():
            if kw in txt:
                return tier
        return "application"

    FLOW_TIERS = ["presentation", "application", "data"]
    if has_ai:
        FLOW_TIERS = ["presentation", "application", "ai", "data"]
    INFRA_TIERS = ["security", "operations"]

    tier_labels = {
        "presentation": "📱 Presentation & API",
        "application":  "⚙️ Application Services",
        "ai":           "🤖 AI & Cognitive",
        "data":         "💾 Data & Storage",
        "security":     "🔑 Security & Identity",
        "operations":   "📊 Monitoring & Operations",
    }
    tier_color_map = {
        "presentation": pres_colors,
        "application":  app_colors,
        "ai":           ai_colors,
        "data":         data_colors,
        "security":     sec_colors,
        "operations":   ops_colors,
    }

    # classify
    tier_comps: dict = {k: [] for k in FLOW_TIERS + INFRA_TIERS}
    for c in comps:
        c = _safe_dict(c)
        t = get_tier(c)
        if t in tier_comps:
            tier_comps[t].append(c)
        else:
            tier_comps["application"].append(c)

    # ── layout constants ─────────────────────────────────────────────────
    PAGE_W       = 1600
    MARGIN       = 40
    HEADER_H     = 60        # title banner
    COMP_W       = 200
    COMP_H       = 70
    COMP_GAP     = 14
    SWIMLANE_HDR = 38
    SWIMLANE_PAD = 16
    FLOW_Y       = MARGIN + HEADER_H + 20
    n_flow       = len(FLOW_TIERS)
    TIER_W       = (PAGE_W - 2 * MARGIN - (n_flow - 1) * 20) // n_flow
    ARROW_GAP    = 14        # gap between swimlane right edge and arrow

    # compute swimlane heights per tier
    def swimlane_h(tier_key):
        n = max(len(tier_comps[tier_key]), 1)
        return SWIMLANE_HDR + SWIMLANE_PAD + n * (COMP_H + COMP_GAP) + SWIMLANE_PAD

    max_flow_h  = max(swimlane_h(t) for t in FLOW_TIERS)
    INFRA_Y     = FLOW_Y + max_flow_h + 30
    INFRA_W     = PAGE_W - 2 * MARGIN
    INFRA_H     = 40 + 3 * (COMP_H + COMP_GAP)
    PAGE_H      = INFRA_Y + len(INFRA_TIERS) * (INFRA_H + 16) + MARGIN

    cells = []
    cell_id = 2

    # ── title banner ─────────────────────────────────────────────────────
    client_name  = (_safe_str(se.get("client_name","")) or
                    _safe_str(st.session_state.get("client_name","")) or "")
    project_type = _safe_str(se.get("project_type","")) or "Solution Architecture"
    title_text   = _esc((client_name + "  —  " if client_name else "") + project_type)
    cells.append(
        f'<mxCell id="{cell_id}" value="{title_text}" '
        f'style="text;html=1;strokeColor=none;fillColor=#1a1a2e;fontColor=#ffffff;'
        f'align=center;verticalAlign=middle;fontSize=16;fontStyle=1;" '
        f'vertex="1" parent="1">'
        f'<mxGeometry x="{MARGIN}" y="{MARGIN}" width="{PAGE_W - 2*MARGIN}" height="{HEADER_H}" as="geometry"/>'
        f'</mxCell>'
    )
    cell_id += 1

    # ── flow tier swimlanes ───────────────────────────────────────────────
    tier_cell_ids: dict = {}
    comp_cell_ids: dict = {}   # comp index → cell id

    for i, tier_key in enumerate(FLOW_TIERS):
        tc = tier_color_map[tier_key]
        sx = MARGIN + i * (TIER_W + 20)
        sy = FLOW_Y
        sh = max_flow_h
        label = _esc(tier_labels[tier_key])
        sw_id = f"sw_{tier_key}"
        tier_cell_ids[tier_key] = sw_id
        cells.append(
            f'<mxCell id="{sw_id}" value="{label}" '
            f'style="swimlane;startSize={SWIMLANE_HDR};fillColor={tc["fill"]};'
            f'strokeColor={tc["stroke"]};fontColor={tc["stroke"]};fontStyle=1;fontSize=11;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{sx}" y="{sy}" width="{TIER_W}" height="{sh}" as="geometry"/>'
            f'</mxCell>'
        )
        # components inside swimlane
        cx = (TIER_W - COMP_W) // 2
        cy = SWIMLANE_HDR + SWIMLANE_PAD
        for comp in tier_comps[tier_key]:
            comp = _safe_dict(comp)
            raw_name = _safe_str(comp.get("name",  "Component"))[:30]
            raw_svc  = _safe_str(comp.get("azure_service",""))[:35]
            raw_svcs = " · ".join(_safe_str(s) for s in _safe_list(comp.get("services",[])))[:60]
            # Build HTML label then XML-encode it for the attribute (Draw.io format)
            _n = _esc(raw_name); _s = _esc(raw_svc); _ss = _esc(raw_svcs)
            html_inner = f'<b>{_n}</b>'
            if _s:
                html_inner += f'<br/><i>{_s}</i>'
            if _ss:
                html_inner += f'<br/><font style="font-size:8px;">{_ss}</font>'
            label = _html_attr(html_inner)
            cells.append(
                f'<mxCell id="{cell_id}" value="{label}" '
                f'style="rounded=1;whiteSpace=wrap;html=1;arcSize=12;'
                f'fillColor={tc["comp_fill"]};strokeColor={tc["stroke"]};fontColor=#1a1a2e;fontSize=10;" '
                f'vertex="1" parent="{sw_id}">'
                f'<mxGeometry x="{cx}" y="{cy}" width="{COMP_W}" height="{COMP_H}" as="geometry"/>'
                f'</mxCell>'
            )
            comp_cell_ids[cell_id] = sw_id
            cell_id += 1
            cy += COMP_H + COMP_GAP

    # ── arrows between flow tiers ─────────────────────────────────────────
    for i in range(len(FLOW_TIERS) - 1):
        src = tier_cell_ids[FLOW_TIERS[i]]
        tgt = tier_cell_ids[FLOW_TIERS[i + 1]]
        cells.append(
            f'<mxCell id="{cell_id}" value="" '
            f'style="endArrow=block;endFill=1;strokeColor=#555555;strokeWidth=2;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;" '
            f'edge="1" source="{src}" target="{tgt}" parent="1">'
            f'<mxGeometry relative="1" as="geometry"/>'
            f'</mxCell>'
        )
        cell_id += 1

    # ── infra tier full-width bands ───────────────────────────────────────
    for j, tier_key in enumerate(INFRA_TIERS):
        tc  = tier_color_map[tier_key]
        iy  = INFRA_Y + j * (INFRA_H + 16)
        iw  = INFRA_W
        label = _esc(tier_labels[tier_key])
        sw_id = f"sw_{tier_key}"
        tier_cell_ids[tier_key] = sw_id
        cells.append(
            f'<mxCell id="{sw_id}" value="{label}" '
            f'style="swimlane;startSize={SWIMLANE_HDR};horizontal=1;fillColor={tc["fill"]};'
            f'strokeColor={tc["stroke"]};fontColor={tc["stroke"]};fontStyle=1;fontSize=11;" '
            f'vertex="1" parent="1">'
            f'<mxGeometry x="{MARGIN}" y="{iy}" width="{iw}" height="{INFRA_H}" as="geometry"/>'
            f'</mxCell>'
        )
        n_comps = len(tier_comps[tier_key])
        if n_comps:
            gap     = 20
            cw      = min(COMP_W + 20, (iw - gap * 2) // max(n_comps, 1) - gap)
            total_w = n_comps * cw + (n_comps - 1) * gap
            start_x = (iw - total_w) // 2
            for k, comp in enumerate(tier_comps[tier_key]):
                comp  = _safe_dict(comp)
                raw_name = _safe_str(comp.get("name","Component"))[:30]
                raw_svc  = _safe_str(comp.get("azure_service",""))[:35]
                _n = _esc(raw_name); _s = _esc(raw_svc)
                html_inner = f'<b>{_n}</b>' + (f'<br/><i>{_s}</i>' if _s else "")
                label = _html_attr(html_inner)
                cx    = start_x + k * (cw + gap)
                cells.append(
                    f'<mxCell id="{cell_id}" value="{label}" '
                    f'style="rounded=1;whiteSpace=wrap;html=1;arcSize=12;'
                    f'fillColor={tc["comp_fill"]};strokeColor={tc["stroke"]};fontColor=#1a1a2e;fontSize=10;" '
                    f'vertex="1" parent="{sw_id}">'
                    f'<mxGeometry x="{cx}" y="{SWIMLANE_HDR + 14}" width="{cw}" height="{COMP_H}" as="geometry"/>'
                    f'</mxCell>'
                )
                cell_id += 1

    # ── assemble XML (.drawio format requires <mxfile> wrapper) ──────────
    cells_xml = "\n          ".join(cells)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<mxfile host="app.diagrams.net" agent="ECI Presales BELLA" version="21.0.0" type="device">\n'
        '  <diagram id="eci_arch_1" name="Solution Architecture">\n'
        f'    <mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1" '
        f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        f'pageWidth="{PAGE_W}" pageHeight="{PAGE_H}" math="0" shadow="0">\n'
        '      <root>\n'
        '        <mxCell id="0" />\n'
        '        <mxCell id="1" parent="0" />\n'
        f'        {cells_xml}\n'
        '      </root>\n'
        '    </mxGraphModel>\n'
        '  </diagram>\n'
        '</mxfile>'
    )


# ═══════════════════════════════════════════════════════════════════════
#  AI VISION ARCHITECTURE — DRAW.IO EXPORT (Lucidchart-compatible)
#  Rules that guarantee Lucidchart accepts the file:
#    1. All cell ids are plain integers (no string ids)
#    2. No emoji anywhere in the XML
#    3. HTML labels use only <b>, <br/>, <i>, <font> — no inline style=""
#    4. HTML label text is XML-attribute-escaped once (never double-encoded)
#    5. No background="" on mxGraphModel (Lucidchart ignores / rejects it)
#    6. mxGeometry always has explicit x/y/width/height (no relative-only)
# ═══════════════════════════════════════════════════════════════════════

def generate_vision_drawio_xml(ar: dict, se: dict = None, ce: dict = None) -> str:
    """Generate a Lucidchart-compatible draw.io export of the AI Vision Architecture.

    Import into Lucidchart: File → Import → diagrams.net (.drawio)
    """
    se = se or {}
    ce = ce or {}

    # ── XML helpers ──────────────────────────────────────────────────────
    # _x     : full-escape raw text → safe XML attribute text (& < > ")
    # _xa    : escape HTML string for XML attribute (< > " only — NOT &,
    #          because _x() was already applied to all text nodes inside)
    def _x(s):
        return (str(s) if s else "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    def _xa(html: str) -> str:
        """Encode a composed HTML string for use as an XML attribute value.
        Text nodes inside were already _x()-escaped so & is already &amp;.
        We only need to encode the HTML angle-brackets and any stray quotes."""
        return html.replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    # HTML label for a component.
    # Uses ONLY <b>, <br/>, <i>, <font> — NO attributes with quotes inside.
    # All text content already escaped via _x(); then the whole thing goes
    # through _xa() before insertion into value="..." XML attribute.
    def _label(name: str, svc: str, cost: str) -> str:
        parts = [f"<b>{_x(name)}</b>"]
        if svc:
            parts.append(f"<br/><i>{_x(svc)}</i>")
        if cost:
            parts.append(f"<br/><font>{_x(cost)}</font>")
        return "".join(parts)

    # ── provider + AI detection ──────────────────────────────────────────
    def _provider(se_d):
        txt = (" ".join(str(t) for t in (se_d.get("technology_stack") or []))
               + " " + str(se_d.get("project_type", ""))).lower()
        scores = {
            "aws":   sum(1 for k in ["aws","amazon","s3","ec2","lambda","rds","bedrock","eks"] if k in txt),
            "gcp":   sum(1 for k in ["gcp","google","bigquery","cloud run","vertex","firebase"] if k in txt),
            "azure": sum(1 for k in ["azure","cosmos","entra","app service","azure openai"] if k in txt),
        }
        best = max(scores, key=scores.get)
        return best if scores[best] >= 1 else "azure"

    def _has_ai(se_d, ar_d):
        txt = (" ".join(str(t) for t in (se_d.get("technology_stack") or []))
               + " " + str(se_d.get("project_type", ""))
               + " " + " ".join(str(c.get("name","")) + " " + str(c.get("azure_service",""))
                                 for c in (ar_d.get("components") or []) if isinstance(c, dict))).lower()
        return any(k in txt for k in ["openai","gpt","llm","ai search","machine learning",
                                       "sagemaker","bedrock","vertex","cognitive","copilot","rag"])

    comps    = [c for c in (ar.get("components") or []) if isinstance(c, dict)]
    provider = _provider(se)
    has_ai   = _has_ai(se, ar)

    # ── per-tier colors (dark neon — no emoji, no unsafe chars) ─────────
    _pres_stroke = {"aws": "#FF9900", "gcp": "#4285F4", "azure": "#00B4D8"}.get(provider, "#00B4D8")
    DARK = {
        "presentation": {"fill": "#0A1825", "stroke": _pres_stroke,  "font": "#DBEAFE", "comp": "#0F2235"},
        "application":  {"fill": "#0A1A25", "stroke": "#06B6D4",      "font": "#CFFAFE", "comp": "#0F2030"},
        "ai":           {"fill": "#1A0D2E", "stroke": "#7B61FF",      "font": "#EDE9FE", "comp": "#221040"},
        "data":         {"fill": "#091A14", "stroke": "#00D4AA",      "font": "#D1FAE5", "comp": "#0E2A20"},
        "security":     {"fill": "#1A0808", "stroke": "#F87171",      "font": "#FEE2E2", "comp": "#2A0F0F"},
        "operations":   {"fill": "#1A1200", "stroke": "#FFD166",      "font": "#FEF3C7", "comp": "#2A1E00"},
    }

    # ── tier labels — raw text (escaped by _x() when placed in value="") ─
    tier_labels = {
        "presentation": "Presentation & API",
        "application":  "Application Services",
        "ai":           "AI & Cognitive",
        "data":         "Data & Storage",
        "security":     "Security & Identity",
        "operations":   "Monitoring & Operations",
    }

    # ── tier classification ──────────────────────────────────────────────
    TYPE_MAP = {
        "front door":"presentation","cdn":"presentation","web app":"presentation",
        "react":"presentation","angular":"presentation","api management":"presentation",
        "app service":"presentation","cloudfront":"presentation","api gateway":"presentation",
        "load balancer":"presentation","static web":"presentation","alb":"presentation",
        "function":"application","service bus":"application","event hub":"application",
        "logic app":"application","backend":"application","container":"application",
        "kubernetes":"application","aks":"application","lambda":"application",
        "ecs":"application","eks":"application","sqs":"application","sns":"application",
        "cloud run":"application","pub/sub":"application","fargate":"application",
        "openai":"ai","cognitive":"ai","ai search":"ai","machine learning":"ai",
        "bedrock":"ai","sagemaker":"ai","vertex":"ai","speech":"ai","language":"ai",
        "sql":"data","cosmos":"data","blob":"data","storage":"data","redis":"data",
        "data lake":"data","synapse":"data","s3":"data","rds":"data","dynamodb":"data",
        "bigquery":"data","cloud sql":"data","aurora":"data",
        "key vault":"security","active directory":"security","entra":"security",
        "firewall":"security","defender":"security","iam":"security","waf":"security",
        "cognito":"security","shield":"security","secrets manager":"security","kms":"security",
        "monitor":"operations","insights":"operations","devops":"operations",
        "cloudwatch":"operations","cloudtrail":"operations","cloud logging":"operations",
    }

    def get_tier(c):
        txt = (str(c.get("name","")) + " " + str(c.get("type",""))
               + " " + str(c.get("azure_service",""))).lower()
        for kw, tier in TYPE_MAP.items():
            if kw in txt:
                return tier
        return "application"

    FLOW_TIERS  = ["presentation", "application", "ai", "data"] if has_ai else \
                  ["presentation", "application", "data"]
    INFRA_TIERS = ["security", "operations"]
    ALL_TIERS   = FLOW_TIERS + INFRA_TIERS

    tier_comps: dict = {k: [] for k in ALL_TIERS}
    for c in comps:
        t = get_tier(c)
        tier_comps[t if t in tier_comps else "application"].append(c)

    # ── monthly cost lookup ──────────────────────────────────────────────
    _cost_map: dict = {}
    for _ck in ("azure_costs","aws_costs","gcp_costs","cloud_costs","services",
                "infrastructure_costs","cost_breakdown","cloud_services"):
        for _sv in (ce.get(_ck) or []):
            if isinstance(_sv, dict):
                _sn = str(_sv.get("service","") or _sv.get("name","")).lower()
                _mc = int(_sv.get("monthly_cost", 0) or 0)
                if _sn and _mc:
                    _cost_map[_sn] = _mc

    def _cost(name: str) -> str:
        n = name.lower()
        for k, v in _cost_map.items():
            if k[:10] in n or n[:10] in k:
                return f"${v}/mo"
        return ""

    # ── layout ───────────────────────────────────────────────────────────
    PAGE_W       = 1700
    MARGIN       = 44
    HEADER_H     = 60
    COMP_W       = 200
    COMP_H       = 70
    COMP_GAP     = 14
    SWIMLANE_HDR = 38
    SWIMLANE_PAD = 16
    FLOW_Y       = MARGIN + HEADER_H + 20
    n_flow       = len(FLOW_TIERS)
    TIER_W       = (PAGE_W - 2 * MARGIN - (n_flow - 1) * 20) // n_flow

    def _sh(key):
        n = max(len(tier_comps[key]), 1)
        return SWIMLANE_HDR + SWIMLANE_PAD + n * (COMP_H + COMP_GAP) + SWIMLANE_PAD

    max_flow_h = max(_sh(t) for t in FLOW_TIERS)
    INFRA_Y    = FLOW_Y + max_flow_h + 30
    INFRA_W    = PAGE_W - 2 * MARGIN
    INFRA_H    = 40 + 3 * (COMP_H + COMP_GAP)
    PAGE_H     = INFRA_Y + len(INFRA_TIERS) * (INFRA_H + 16) + MARGIN

    # ── assemble cells as raw XML strings ───────────────────────────────
    # All IDs are plain integers starting from 2.
    # Swimlane IDs are integers stored in tier_cell_ids[tier_key].
    cells      = []
    _id        = 2   # monotonic counter
    tier_cell_ids: dict = {}   # tier_key -> integer id

    def _cell(id_, value_attr, style, x, y, w, h, parent, vertex="1"):
        # value_attr must already be fully XML-attribute-safe:
        #   plain text  → call _x(raw_text) before passing here
        #   HTML label  → call _xa(_label(...)) before passing here
        return (
            f'<mxCell id="{id_}" value="{value_attr}" style="{style}" '
            f'vertex="{vertex}" parent="{parent}">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/>'
            f'</mxCell>'
        )

    def _edge(id_, style, src, tgt, parent="1"):
        return (
            f'<mxCell id="{id_}" value="" style="{style}" '
            f'edge="1" source="{src}" target="{tgt}" parent="{parent}">'
            f'<mxGeometry relative="1" as="geometry"/>'
            f'</mxCell>'
        )

    # title banner
    client = str(se.get("client_name", "") or "")
    ptype  = str(se.get("project_type", "") or "AI Vision Architecture")
    title_val = _x((client + " - " if client else "") + ptype + " - AI Vision Architecture")
    cells.append(_cell(
        _id, title_val,
        "text;html=0;strokeColor=#7B61FF;fillColor=#1A0D2E;fontColor=#C4B5FD;"
        "align=center;verticalAlign=middle;fontSize=15;fontStyle=1;",
        MARGIN, MARGIN, PAGE_W - 2 * MARGIN, HEADER_H, parent="1"
    ))
    _id += 1

    # flow tier swimlanes + their components
    for i, tier_key in enumerate(FLOW_TIERS):
        tc   = DARK[tier_key]
        sx   = MARGIN + i * (TIER_W + 20)
        sw_id = _id
        tier_cell_ids[tier_key] = sw_id
        cells.append(_cell(
            sw_id, _x(tier_labels[tier_key]),        # plain text → _x()
            f"swimlane;startSize={SWIMLANE_HDR};fillColor={tc['fill']};"
            f"strokeColor={tc['stroke']};fontColor={tc['font']};fontStyle=1;fontSize=11;",
            sx, FLOW_Y, TIER_W, max_flow_h, parent="1"
        ))
        _id += 1
        cx = (TIER_W - COMP_W) // 2
        cy = SWIMLANE_HDR + SWIMLANE_PAD
        for comp in tier_comps[tier_key]:
            nm  = str(comp.get("name", "Component"))[:34]
            svc = str(comp.get("azure_service", ""))[:40]
            cells.append(_cell(
                _id, _xa(_label(nm, svc, _cost(nm))),  # HTML → _xa()
                f"rounded=1;whiteSpace=wrap;html=1;arcSize=12;"
                f"fillColor={tc['comp']};strokeColor={tc['stroke']};fontColor={tc['font']};fontSize=10;",
                cx, cy, COMP_W, COMP_H, parent=str(sw_id)
            ))
            _id += 1
            cy += COMP_H + COMP_GAP

    # arrows between flow tiers
    for i in range(len(FLOW_TIERS) - 1):
        src = tier_cell_ids[FLOW_TIERS[i]]
        tgt = tier_cell_ids[FLOW_TIERS[i + 1]]
        ac  = DARK[FLOW_TIERS[i]]["stroke"]
        cells.append(_edge(
            _id,
            f"endArrow=block;endFill=1;strokeColor={ac};strokeWidth=2;"
            "exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;",
            str(src), str(tgt)
        ))
        _id += 1

    # infra bands
    for j, tier_key in enumerate(INFRA_TIERS):
        tc    = DARK[tier_key]
        iy    = INFRA_Y + j * (INFRA_H + 16)
        sw_id = _id
        tier_cell_ids[tier_key] = sw_id
        cells.append(_cell(
            sw_id, _x(tier_labels[tier_key]),        # plain text → _x()
            f"swimlane;startSize={SWIMLANE_HDR};fillColor={tc['fill']};"
            f"strokeColor={tc['stroke']};fontColor={tc['font']};fontStyle=1;fontSize=11;",
            MARGIN, iy, INFRA_W, INFRA_H, parent="1"
        ))
        _id += 1
        n_c = len(tier_comps[tier_key])
        if n_c:
            gap     = 20
            cw      = min(COMP_W + 20, max(80, (INFRA_W - gap * 2) // n_c - gap))
            total_w = n_c * cw + (n_c - 1) * gap
            start_x = (INFRA_W - total_w) // 2
            for k, comp in enumerate(tier_comps[tier_key]):
                nm  = str(comp.get("name", "Component"))[:34]
                svc = str(comp.get("azure_service", ""))[:40]
                cx  = start_x + k * (cw + gap)
                cells.append(_cell(
                    _id, _xa(_label(nm, svc, _cost(nm))),  # HTML → _xa()
                    f"rounded=1;whiteSpace=wrap;html=1;arcSize=12;"
                    f"fillColor={tc['comp']};strokeColor={tc['stroke']};fontColor={tc['font']};fontSize=10;",
                    cx, SWIMLANE_HDR + 12, cw, COMP_H, parent=str(sw_id)
                ))
                _id += 1

    # ── assemble final XML ───────────────────────────────────────────────
    cells_xml = "\n        ".join(cells)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<mxfile host="app.diagrams.net" version="21.0.0">'
        '<diagram id="eci_ai_vision" name="AI Vision Architecture">'
        f'<mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1" '
        f'tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" '
        f'pageWidth="{PAGE_W}" pageHeight="{PAGE_H}" math="0" shadow="0">'
        '<root>'
        '<mxCell id="0"/>'
        '<mxCell id="1" parent="0"/>'
        f'{cells_xml}'
        '</root>'
        '</mxGraphModel>'
        '</diagram>'
        '</mxfile>'
    )


# ═══════════════════════════════════════════════════════════════════════
#  DYNAMIC MULTI-CLOUD ARCHITECTURE SVG GENERATOR
#  Detects provider (Azure/AWS/GCP) and AI usage from semantic analysis.
#  No hardcoded Azure defaults — layout adapts to actual scope.
# ═══════════════════════════════════════════════════════════════════════

def generate_arch_html_svg(ar: dict, semantic: dict = None) -> str:
    """Generate a clean, professional architecture diagram as self-contained HTML.

    Layout: LEFT→RIGHT HORIZONTAL FLOW
      [External Sources] ──▶ [Presentation] ──▶ [Application] ──▶ [AI*] ──▶ [Data] ──▶ [Consumers]
      (*AI column only shown when project involves AI/ML)
      Provider-aware: Azure / AWS / GCP branding, colors, and service defaults.
    Returns a full HTML page ready for st.components.v1.html().
    """
    # ═══════════════════════ DATA PREP ════════════════════════════════
    se           = semantic or {}
    pattern      = safe_str(ar.get("pattern",  "Solution Architecture"))
    client_name  = safe_str(se.get("client_name",  ""))
    project_type = safe_str(se.get("project_type", "Cloud Solution"))
    comps        = safe_list(ar.get("components"))
    data_flow    = safe_list(ar.get("data_flow"))
    security_items = safe_list(ar.get("security"))
    tech_stack   = safe_list(se.get("technology_stack", []))
    title = ((client_name + "  —  ") if client_name else "") + pattern

    FONT = "Segoe UI,-apple-system,Roboto,Arial,sans-serif"

    # ═══════════════════════ PROVIDER & AI DETECTION ══════════════════
    def _detect_provider_local(se_d):
        tech = " ".join(str(t) for t in safe_list(se_d.get("technology_stack", []))).lower()
        proj = safe_str(se_d.get("project_type", "")).lower()
        combined = tech + " " + proj
        aws_kw  = ["aws", "amazon web services", "amazon s3", "s3 ", "ec2", "lambda",
                   "eks", "ecs", "rds", "dynamodb", "cloudfront", "sqs", "cognito",
                   "kinesis", "glacier", "redshift", "fargate", "bedrock", "sagemaker"]
        gcp_kw  = ["gcp", "google cloud", "bigquery", "cloud run", "gke", "pub/sub",
                   "firebase", "cloud sql", "vertex ai", "cloud functions", "dataflow",
                   "memorystore", "cloud storage gcp", "alloydb"]
        az_kw   = ["azure", "microsoft azure", "cosmos db", "app service", "azure sql",
                   "entra id", "azure ad", "azure devops", "azure openai", "azure blob",
                   "azure functions", "service bus", "azure storage", "azure monitor"]
        aws_score = sum(1 for kw in aws_kw if kw in combined)
        gcp_score = sum(1 for kw in gcp_kw if kw in combined)
        az_score  = sum(1 for kw in az_kw  if kw in combined)
        scores = sorted([("aws", aws_score), ("gcp", gcp_score), ("azure", az_score)],
                        key=lambda x: x[1], reverse=True)
        if scores[0][1] >= 1:
            return scores[0][0]
        return "azure"

    def _has_ai_local(se_d, ar_d):
        tech = " ".join(str(t) for t in safe_list(se_d.get("technology_stack", []))).lower()
        proj = safe_str(se_d.get("project_type", "")).lower()
        comps_text = " ".join(
            safe_str(c.get("name", "")) + " " + safe_str(c.get("azure_service", ""))
            for c in safe_list(ar_d.get("components", []))
        ).lower()
        combined = tech + " " + proj + " " + comps_text
        ai_kw = ["openai", "gpt", "llm", "genai", "gen ai", "ai search", "cognitive",
                 "machine learning", "ml model", "nlp", "embeddings", "vector search",
                 "azure ai", "bedrock", "vertex ai", "sagemaker", "copilot", "rekognition",
                 "comprehend", "textract", "document ai", "dialogflow", "speech", "vision ai",
                 "neural", "foundation model"]
        return any(kw in combined for kw in ai_kw)

    cloud_provider = _detect_provider_local(se)
    has_ai_tier    = _has_ai_local(se, ar)

    # ═══════════════════════ PROVIDER VISUAL CONFIG ════════════════════
    _PROV_CFG = {
        "azure": {
            "brand":       "Microsoft Azure",
            "sub_label":   "☁  Azure Subscription",
            "sub_color":   "#0078D4",
            "grad_start":  "#003d82",
            "grad_mid":    "#0063B1",
            "grad_end":    "#0091D5",
            "cons_color":  "#0078D4",
            "cons_bg":     "#EBF5FB",
            "sub_bg":      "rgba(235,245,251,.7)",
        },
        "aws": {
            "brand":       "Amazon Web Services",
            "sub_label":   "☁  AWS Account",
            "sub_color":   "#FF9900",
            "grad_start":  "#232F3E",
            "grad_mid":    "#37475A",
            "grad_end":    "#FF9900",
            "cons_color":  "#FF9900",
            "cons_bg":     "#FFF8EE",
            "sub_bg":      "rgba(255,248,238,.7)",
        },
        "gcp": {
            "brand":       "Google Cloud Platform",
            "sub_label":   "☁  GCP Project",
            "sub_color":   "#4285F4",
            "grad_start":  "#1a1a2e",
            "grad_mid":    "#1565C0",
            "grad_end":    "#4285F4",
            "cons_color":  "#4285F4",
            "cons_bg":     "#E8F0FE",
            "sub_bg":      "rgba(232,240,254,.7)",
        },
    }
    pcfg = _PROV_CFG.get(cloud_provider, _PROV_CFG["azure"])

    # ═══════════════════════ DYNAMIC TIER CONFIG ══════════════════════
    # Presentation tier color = provider accent; others fixed
    _PRES_COLOR = pcfg["sub_color"]
    _PRES_BG    = pcfg["cons_bg"]

    _BASE_FLOW_TIERS = [
        ("presentation", "Frontend & API"       if cloud_provider != "azure" else "Presentation & API",
                         "📱", _PRES_COLOR, _PRES_BG),
        ("application",  "Application Services", "⚙️", "#00B294", "#E6FFF9"),
        ("data",         "Data & Storage",        "💾", "#107C10", "#E8F5E9"),
    ]
    _AI_TIER = ("ai", "AI & ML" if cloud_provider in ("aws", "gcp") else "AI & Cognitive",
                "🤖", "#5C2D91", "#F5F0FF")

    if has_ai_tier:
        FLOW_TIERS = [_BASE_FLOW_TIERS[0], _BASE_FLOW_TIERS[1], _AI_TIER, _BASE_FLOW_TIERS[2]]
    else:
        FLOW_TIERS = list(_BASE_FLOW_TIERS)

    # 2 INFRA tiers (full-width bands below)
    INFRA_TIERS = [
        ("security",   "🔑  Security & Identity",     "#D83B01", "#FFF3ED"),
        ("operations", "📊  Monitoring & Operations",  "#E6A800", "#FFFBF0"),
    ]

    # ═══════════════════════ TYPE + ICON MAPS (all providers) ══════════
    TYPE_MAP = {
        # ── Azure Presentation ──
        "front door":"presentation","cdn":"presentation","static web":"presentation",
        "web app":"presentation","portal":"presentation","react":"presentation",
        "angular":"presentation","vue":"presentation","spa":"presentation",
        "api management":"presentation","app service":"presentation",
        "container app":"presentation",
        # ── AWS Presentation ──
        "cloudfront":"presentation","alb":"presentation","api gateway":"presentation",
        "load balancer":"presentation","route 53":"presentation","route53":"presentation",
        "elastic load":"presentation",
        # ── GCP Presentation ──
        "cloud cdn":"presentation","cloud endpoints":"presentation",
        "cloud load":"presentation","cloud armor cdn":"presentation",
        # ── Azure Application ──
        "function":"application","functions":"application","service bus":"application",
        "event hub":"application","logic app":"application","backend":"application",
        "signalr":"application","integration":"application","messaging":"application",
        "container":"application","kubernetes":"application","aks":"application",
        "microservice":"application","compute":"application",
        # ── AWS Application ──
        "lambda":"application","ecs":"application","eks":"application",
        "sqs":"application","sns":"application","kinesis":"application",
        "glue":"application","step functions":"application","fargate":"application",
        "elastic beanstalk":"application",
        # ── GCP Application ──
        "cloud run":"application","cloud functions":"application","pub/sub":"application",
        "dataflow":"application","composer":"application","app engine":"application",
        # ── Azure AI ──
        "openai":"ai","cognitive":"ai","language":"ai","vision":"ai","speech":"ai",
        "form recognizer":"ai","intelligence":"ai","search":"ai",
        "ml":"ai","machine learning":"ai","copilot":"ai",
        # ── AWS AI ──
        "bedrock":"ai","sagemaker":"ai","rekognition":"ai","comprehend":"ai",
        "textract":"ai","polly":"ai","lex":"ai","kendra":"ai","personalize":"ai",
        # ── GCP AI ──
        "vertex":"ai","ai platform":"ai","document ai":"ai","dialogflow":"ai",
        "natural language":"ai","vision ai":"ai","automl":"ai","translation":"ai",
        # ── Azure Data ──
        "sql":"data","cosmos":"data","database":"data","blob":"data","storage":"data",
        "redis":"data","cache":"data","data lake":"data","synapse":"data",
        "databricks":"data","data factory":"data","table storage":"data",
        # ── AWS Data ──
        "s3":"data","rds":"data","dynamodb":"data","aurora":"data","redshift":"data",
        "elasticache":"data","glacier":"data","athena":"data","opensearch":"data",
        "timestream":"data",
        # ── GCP Data ──
        "cloud storage":"data","cloud sql":"data","bigquery":"data","bigtable":"data",
        "firestore":"data","memorystore":"data","spanner":"data","alloydb":"data",
        # ── Security (all) ──
        "key vault":"security","active directory":"security","entra":"security",
        "firewall":"security","defender":"security","sentinel":"security",
        "waf":"security","ddos":"security","identity":"security","auth":"security",
        "iam":"security","cognito":"security","shield":"security",
        "secrets manager":"security","kms":"security","guardduty":"security",
        "cloud armor":"security","secret manager":"security",
        "identity platform":"security",
        # ── Operations (all) ──
        "monitor":"operations","insights":"operations","devops":"operations",
        "log":"operations","pipeline":"operations","ci/cd":"operations",
        "cloudwatch":"operations","cloudtrail":"operations","codepipeline":"operations",
        "x-ray":"operations","xray":"operations","codecommit":"operations",
        "cloud logging":"operations","cloud monitoring":"operations",
        "cloud build":"operations","cloud trace":"operations",
    }

    ICON_MAP = {
        # Azure
        "front door":"🌍","cdn":"📡","api management":"🔌","api gateway":"🔌",
        "function":"⚡","functions":"⚡","service bus":"📨","event hub":"📬",
        "logic app":"🔗","signalr":"📡","app service":"🌐","web app":"🌐",
        "static web":"📄","react":"⚛","container":"📦","kubernetes":"☸","aks":"☸",
        "sql":"🗄","cosmos":"🌀","blob":"💾","storage":"💾","redis":"⚡","cache":"⚡",
        "data lake":"🏞","synapse":"🔬","databricks":"🔥","data factory":"🏭",
        "key vault":"🔑","active directory":"👤","entra":"👤","firewall":"🛡",
        "defender":"🛡","sentinel":"👁","waf":"🛡","ddos":"🛡",
        "monitor":"📊","insights":"📈","devops":"🚀","log analytics":"📋",
        "openai":"🤖","cognitive":"🧠","search":"🔍","form recognizer":"📝",
        "language":"💬","vision":"👁","speech":"🎤","copilot":"🤖",
        "power bi":"📊","teams":"💬","sharepoint":"📁","front":"🌍",
        # AWS
        "cloudfront":"🌍","lambda":"⚡","ecs":"📦","eks":"☸","sqs":"📨","sns":"📢",
        "kinesis":"🌊","glue":"🔧","fargate":"📦","step functions":"🔗",
        "s3":"💾","rds":"🗄","dynamodb":"🌀","aurora":"🗄","redshift":"🔬",
        "elasticache":"⚡","glacier":"🧊","athena":"🔍","opensearch":"🔍",
        "bedrock":"🤖","sagemaker":"🧠","rekognition":"👁","comprehend":"💬",
        "textract":"📝","polly":"🎤","lex":"💬","kendra":"🔍","personalize":"🎯",
        "iam":"👤","cognito":"🔐","shield":"🛡","secrets manager":"🔑",
        "kms":"🔑","guardduty":"🛡","cloudwatch":"📊","cloudtrail":"📋",
        "codepipeline":"🚀","x-ray":"🔬","xray":"🔬","alb":"⚖","route53":"🌐",
        # GCP
        "cloud run":"📦","cloud functions":"⚡","pub/sub":"📨","dataflow":"🌊",
        "cloud storage":"💾","cloud sql":"🗄","bigquery":"🔬","bigtable":"🗃",
        "firestore":"🌀","memorystore":"⚡","spanner":"🌐","alloydb":"🗄",
        "vertex":"🤖","ai platform":"🧠","document ai":"📝","dialogflow":"💬",
        "cloud cdn":"🌍","cloud endpoints":"🔌","cloud load":"⚖",
        "cloud armor":"🛡","secret manager":"🔑","cloud logging":"📋",
        "cloud monitoring":"📊","cloud build":"🚀","cloud trace":"🔬",
        "cloud armor cdn":"🌍","gke":"☸","identity platform":"👤",
    }

    def get_icon(name, svc_label):
        s = (str(name) + " " + str(svc_label)).lower()
        for kw, ic in ICON_MAP.items():
            if kw in s:
                return ic
        return "☁"

    def get_tier(comp):
        n = safe_str(comp.get("name", "")).lower()
        t = safe_str(comp.get("type", "")).lower()
        a = safe_str(comp.get("azure_service", "")).lower()
        combined = n + " " + t + " " + a
        for kw, tier in TYPE_MAP.items():
            if kw in combined:
                return tier
        return "application"

    def esc(s):
        return (str(s).replace("&","&amp;").replace("<","&lt;")
                      .replace(">","&gt;").replace('"',"&quot;"))

    def trunc(s, n):
        s = str(s)
        return s if len(s) <= n else s[:n-1] + "…"

    # ═══════════════════════ CLASSIFY COMPONENTS ══════════════════════
    all_tier_keys = [t[0] for t in FLOW_TIERS] + [t[0] for t in INFRA_TIERS]
    tier_comps = {k: [] for k in all_tier_keys}
    for c in comps:
        c = safe_dict(c)
        t = get_tier(c)
        if t in tier_comps:
            tier_comps[t].append(c)

    # ── Provider-specific defaults (only used when tier has no AI-classified components) ──
    if cloud_provider == "aws":
        FLOW_DEFAULTS = {
            "presentation": [
                {"name":"CloudFront",    "azure_service":"AWS CloudFront CDN",  "services":["CDN","WAF","SSL termination"]},
                {"name":"API Gateway",   "azure_service":"AWS API Gateway",     "services":["REST API","Rate limiting","OAuth"]},
                {"name":"Load Balancer", "azure_service":"AWS ALB",             "services":["Traffic routing","Health checks"]},
            ],
            "application": [
                {"name":"Lambda",        "azure_service":"AWS Lambda",          "services":["Serverless functions","Event processing"]},
                {"name":"ECS / EKS",     "azure_service":"AWS ECS / EKS",       "services":["Container orchestration","Auto-scaling"]},
                {"name":"SQS / SNS",     "azure_service":"AWS SQS / SNS",       "services":["Message queuing","Pub/Sub"]},
            ],
            "ai": [
                {"name":"Amazon Bedrock","azure_service":"Amazon Bedrock",      "services":["Foundation models","Claude / Titan"]},
                {"name":"SageMaker",     "azure_service":"Amazon SageMaker",    "services":["ML training","Model hosting"]},
                {"name":"Rekognition",   "azure_service":"Amazon Rekognition",  "services":["Image AI","Content moderation"]},
            ],
            "data": [
                {"name":"S3 Bucket",     "azure_service":"Amazon S3",           "services":["Object storage","Lifecycle policies"]},
                {"name":"RDS",           "azure_service":"Amazon RDS",          "services":["Relational DB","Multi-AZ failover"]},
                {"name":"DynamoDB",      "azure_service":"Amazon DynamoDB",     "services":["NoSQL","On-demand scaling"]},
            ],
        }
        INFRA_DEFAULTS = {
            "security": [
                {"name":"IAM",             "azure_service":"AWS IAM"},
                {"name":"Cognito",         "azure_service":"Amazon Cognito"},
                {"name":"WAF + Shield",    "azure_service":"AWS WAF + Shield"},
                {"name":"Secrets Manager", "azure_service":"AWS Secrets Manager"},
            ],
            "operations": [
                {"name":"CloudWatch",      "azure_service":"Amazon CloudWatch"},
                {"name":"CloudTrail",      "azure_service":"AWS CloudTrail"},
                {"name":"CodePipeline",    "azure_service":"AWS CodePipeline"},
                {"name":"X-Ray",           "azure_service":"AWS X-Ray"},
            ],
        }
    elif cloud_provider == "gcp":
        FLOW_DEFAULTS = {
            "presentation": [
                {"name":"Cloud CDN",       "azure_service":"Google Cloud CDN",     "services":["CDN","SSL","DDoS protection"]},
                {"name":"API Gateway",     "azure_service":"Cloud Endpoints",      "services":["REST API","Rate limiting"]},
                {"name":"Load Balancer",   "azure_service":"Cloud Load Balancing", "services":["Global traffic","Health checks"]},
            ],
            "application": [
                {"name":"Cloud Run",       "azure_service":"Google Cloud Run",     "services":["Serverless containers","Auto-scaling"]},
                {"name":"Cloud Functions", "azure_service":"Cloud Functions",      "services":["Serverless","Event-driven"]},
                {"name":"Pub/Sub",         "azure_service":"Google Cloud Pub/Sub", "services":["Message broker","Push/pull"]},
            ],
            "ai": [
                {"name":"Vertex AI",       "azure_service":"Google Vertex AI",     "services":["Gemini","Foundation models"]},
                {"name":"AI Platform",     "azure_service":"Google AI Platform",   "services":["ML training","Model registry"]},
                {"name":"Document AI",     "azure_service":"Google Document AI",   "services":["Document processing","OCR"]},
            ],
            "data": [
                {"name":"Cloud Storage",   "azure_service":"Google Cloud Storage", "services":["Object storage","Multi-region"]},
                {"name":"Cloud SQL",       "azure_service":"Google Cloud SQL",     "services":["Managed PostgreSQL","HA"]},
                {"name":"BigQuery",        "azure_service":"Google BigQuery",      "services":["Analytics warehouse","Serverless"]},
            ],
        }
        INFRA_DEFAULTS = {
            "security": [
                {"name":"Cloud IAM",       "azure_service":"Google Cloud IAM"},
                {"name":"Identity Platform","azure_service":"Identity Platform"},
                {"name":"Cloud Armor",     "azure_service":"Google Cloud Armor"},
                {"name":"Secret Manager",  "azure_service":"GCP Secret Manager"},
            ],
            "operations": [
                {"name":"Cloud Logging",   "azure_service":"Google Cloud Logging"},
                {"name":"Cloud Monitoring","azure_service":"Cloud Monitoring"},
                {"name":"Cloud Build",     "azure_service":"Google Cloud Build"},
                {"name":"Cloud Trace",     "azure_service":"Google Cloud Trace"},
            ],
        }
    else:  # azure
        FLOW_DEFAULTS = {
            "presentation": [
                {"name":"Front Door",    "azure_service":"Azure Front Door",    "services":["WAF","CDN","SSL termination"]},
                {"name":"Web App",       "azure_service":"Azure App Service",   "services":["SPA / SSR","Auth integration"]},
                {"name":"API Management","azure_service":"Azure APIM",          "services":["Rate limiting","OAuth 2.0"]},
            ],
            "application": [
                {"name":"Functions",     "azure_service":"Azure Functions",     "services":["Business logic","Event processing"]},
                {"name":"Service Bus",   "azure_service":"Azure Service Bus",   "services":["Async messaging","Dead-letter queue"]},
                {"name":"Logic Apps",    "azure_service":"Azure Logic Apps",    "services":["Workflow automation","Connectors"]},
            ],
            "ai": [
                {"name":"Azure OpenAI",  "azure_service":"Azure OpenAI Service","services":["GPT-4o","Embeddings"]},
                {"name":"AI Search",     "azure_service":"Azure AI Search",     "services":["Vector search","Semantic ranking"]},
                {"name":"Cognitive Svcs","azure_service":"Azure AI Services",   "services":["Vision","Language","Speech"]},
            ],
            "data": [
                {"name":"SQL Database",  "azure_service":"Azure SQL Database",  "services":["Relational data","BCDR"]},
                {"name":"Cosmos DB",     "azure_service":"Azure Cosmos DB",     "services":["NoSQL","Global distribution"]},
                {"name":"Blob Storage",  "azure_service":"Azure Blob Storage",  "services":["Documents","Media files"]},
            ],
        }
        INFRA_DEFAULTS = {
            "security": [
                {"name":"Key Vault",     "azure_service":"Azure Key Vault"},
                {"name":"Entra ID",      "azure_service":"Microsoft Entra ID"},
                {"name":"Firewall / WAF","azure_service":"Azure Firewall"},
                {"name":"Defender",      "azure_service":"Microsoft Defender"},
            ],
            "operations": [
                {"name":"Monitor",       "azure_service":"Azure Monitor"},
                {"name":"App Insights",  "azure_service":"Application Insights"},
                {"name":"DevOps",        "azure_service":"Azure DevOps"},
                {"name":"Log Analytics", "azure_service":"Log Analytics Workspace"},
            ],
        }

    # Use defaults only for tiers that have no classified components
    active_flow_keys = {t[0] for t in FLOW_TIERS}
    for k, defs in {**FLOW_DEFAULTS, **INFRA_DEFAULTS}.items():
        if k in tier_comps and not tier_comps[k] and (k in active_flow_keys or k in ("security", "operations")):
            tier_comps[k] = defs

    # ═══════════════════════ LAYOUT GEOMETRY ══════════════════════════
    SVG_W       = 1500
    TITLE_H     = 64
    CONTENT_Y   = TITLE_H + 20

    # Side panels
    EXT_X       = 18
    EXT_W       = 148
    CONS_W      = 162
    COL_GAP     = 30      # gap between any two adjacent panels (arrow space)

    # Flow columns — dynamic count based on FLOW_TIERS (3 or 4)
    N_FLOW          = len(FLOW_TIERS)
    FLOW_START_X    = EXT_X + EXT_W + COL_GAP
    CONS_X          = SVG_W - 18 - CONS_W
    FLOW_END_X      = CONS_X - COL_GAP
    FLOW_AVAIL      = FLOW_END_X - FLOW_START_X
    FLOW_COL_W      = (FLOW_AVAIL - (N_FLOW - 1) * COL_GAP) // N_FLOW

    # Card geometry inside each column
    CARD_PAD_X  = 12
    CARD_W      = FLOW_COL_W - 2 * CARD_PAD_X
    CARD_H      = 76
    CARD_GAP_Y  = 10

    # Column header
    COL_HDR_H   = 50
    COL_PTOP    = COL_HDR_H + 10
    COL_PBOT    = 14

    MAX_CARDS_PER_COL = 5
    max_flow_cards = max(
        min(len(tier_comps[t[0]]), MAX_CARDS_PER_COL)
        for t in FLOW_TIERS
    )
    max_flow_cards = max(max_flow_cards, 2)
    FLOW_COL_H = COL_PTOP + max_flow_cards * (CARD_H + CARD_GAP_Y) - CARD_GAP_Y + COL_PBOT

    # Provider subscription/account outline
    SUB_PAD     = 14
    SUB_LABEL_H = 38
    SUB_X       = FLOW_START_X - SUB_PAD
    SUB_W       = (FLOW_END_X - FLOW_START_X) + 2 * SUB_PAD
    SUB_Y       = CONTENT_Y
    SUB_H       = SUB_LABEL_H + FLOW_COL_H + 18
    FLOW_Y      = SUB_Y + SUB_LABEL_H + 8

    BAND_X      = SUB_X
    BAND_W      = SUB_W
    BAND_H      = 90
    BAND_GAP    = 10
    BAND_Y0     = SUB_Y + SUB_H + 14

    LEG_Y       = BAND_Y0 + 2 * (BAND_H + BAND_GAP) + 10
    SVG_H       = LEG_Y + 52

    flow_col_xs = [
        FLOW_START_X + i * (FLOW_COL_W + COL_GAP)
        for i in range(N_FLOW)
    ]

    ARROW_Y = FLOW_Y + FLOW_COL_H // 2

    # ═══════════════════════ SVG BUILDERS ═════════════════════════════
    parts = []

    def R(x, y, w, h, **kw):
        attrs = " ".join(f'{k}="{v}"' for k, v in kw.items())
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" {attrs}/>')

    def T(x, y, content, **kw):
        attrs = " ".join(f'{k}="{v}"' for k, v in kw.items())
        parts.append(f'<text x="{x}" y="{y}" {attrs}>{content}</text>')

    def Ci(cx, cy, r, **kw):
        attrs = " ".join(f'{k}="{v}"' for k, v in kw.items())
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" {attrs}/>')

    def P(d, **kw):
        attrs = " ".join(f'{k}="{v}"' for k, v in kw.items())
        parts.append(f'<path d="{d}" {attrs}/>')

    def hdr_path(x, y, w, h, rx=10):
        """Rectangle with rounded TOP corners only (flat bottom)."""
        return (f"M {x+rx} {y} H {x+w-rx} "
                f"Q {x+w} {y} {x+w} {y+rx} "
                f"V {y+h} H {x} V {y+rx} "
                f"Q {x} {y} {x+rx} {y} Z")

    # ═══════════════════════ DEFS ══════════════════════════════════════
    # Provider-aware gradient + arrow markers
    _gs = pcfg["grad_start"]
    _gm = pcfg["grad_mid"]
    _ge = pcfg["grad_end"]
    _ac = pcfg["sub_color"]
    parts.append(
        '<defs>'
        f'<linearGradient id="gTitle" x1="0" y1="0" x2="1" y2="0">'
        f'<stop offset="0" stop-color="{_gs}"/>'
        f'<stop offset="0.5" stop-color="{_gm}"/>'
        f'<stop offset="1" stop-color="{_ge}"/>'
        '</linearGradient>'
        '<linearGradient id="gBg" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#EEF3FA"/>'
        '<stop offset="1" stop-color="#E0E8F4"/>'
        '</linearGradient>'
        '<filter id="fShadow" x="-6%" y="-6%" width="115%" height="130%">'
        f'<feDropShadow dx="0" dy="3" stdDeviation="5" flood-color="{_ac}" flood-opacity="0.12"/>'
        '</filter>'
        '<filter id="fCard" x="-6%" y="-6%" width="115%" height="130%">'
        '<feDropShadow dx="0" dy="1" stdDeviation="2" flood-color="#000" flood-opacity="0.09"/>'
        '</filter>'
        # Arrow markers — one per tier color + gray
        '<marker id="mBlue"   markerWidth="11" markerHeight="8" refX="10" refY="4" orient="auto"><polygon points="0 0,11 4,0 8" fill="#0078D4"/></marker>'
        '<marker id="mGreen"  markerWidth="11" markerHeight="8" refX="10" refY="4" orient="auto"><polygon points="0 0,11 4,0 8" fill="#00B294"/></marker>'
        f'<marker id="mProv"   markerWidth="11" markerHeight="8" refX="10" refY="4" orient="auto"><polygon points="0 0,11 4,0 8" fill="{_ac}"/></marker>'
        '<marker id="mPurple" markerWidth="11" markerHeight="8" refX="10" refY="4" orient="auto"><polygon points="0 0,11 4,0 8" fill="#5C2D91"/></marker>'
        '<marker id="mForest" markerWidth="11" markerHeight="8" refX="10" refY="4" orient="auto"><polygon points="0 0,11 4,0 8" fill="#107C10"/></marker>'
        '<marker id="mGreen"  markerWidth="11" markerHeight="8" refX="10" refY="4" orient="auto"><polygon points="0 0,11 4,0 8" fill="#00B294"/></marker>'
        '<marker id="mGray"   markerWidth="11" markerHeight="8" refX="10" refY="4" orient="auto"><polygon points="0 0,11 4,0 8" fill="#6B7280"/></marker>'
        '</defs>'
    )

    # ═══════════════════════ BACKGROUND ════════════════════════════════
    R(0, 0, SVG_W, SVG_H, fill="url(#gBg)")

    # ═══════════════════════ TITLE BANNER ══════════════════════════════
    R(0, 0, SVG_W, TITLE_H, fill="url(#gTitle)")
    R(SVG_W - 220, 0, 220, TITLE_H, fill="rgba(255,255,255,.05)")
    T(22, 38, esc(trunc(title, 88)),
      fill="white",
      **{"font-size":"19","font-weight":"700","font-family":FONT,"letter-spacing":".3"})
    T(22, 56, esc(project_type),
      fill="rgba(255,255,255,.68)", **{"font-size":"11","font-family":FONT})
    T(SVG_W - 16, 38, esc(pcfg["brand"]),
      fill="rgba(255,255,255,.55)",
      **{"font-size":"13","font-weight":"600","font-family":FONT,"text-anchor":"end"})
    T(SVG_W - 16, 54, "Architecture Diagram",
      fill="rgba(255,255,255,.38)",
      **{"font-size":"9","font-family":FONT,"text-anchor":"end"})

    # ═══════════════════════ PROVIDER ACCOUNT/SUBSCRIPTION BOX ═════════
    R(SUB_X, SUB_Y, SUB_W, SUB_H,
      fill=pcfg["sub_bg"], stroke=pcfg["sub_color"],
      **{"stroke-width":"2","stroke-dasharray":"12,6","rx":"14","filter":"url(#fShadow)"})
    lbl_pill_w = max(220, len(pcfg["sub_label"]) * 9 + 24)
    R(SUB_X + 14, SUB_Y + 8, lbl_pill_w, 28, fill=pcfg["sub_color"], rx="6",
      **{"filter":"url(#fCard)"})
    T(SUB_X + 26, SUB_Y + 27, esc(pcfg["sub_label"]),
      fill="white", **{"font-size":"13","font-weight":"700","font-family":FONT})

    # ═══════════════════════ FLOW COLUMNS ══════════════════════════════
    # Dynamic arrow labels based on which tiers are present
    _tier_keys = [t[0] for t in FLOW_TIERS]
    _ARROW_LABEL_MAP = {
        ("presentation","application"): ("HTTPS / WebSocket", "#00B294", "mGreen"),
        ("application","ai"):           ("REST / Inference",  "#5C2D91", "mPurple"),
        ("ai","data"):                  ("Query / Store",     "#107C10", "mForest"),
        ("application","data"):         ("Query / Store",     "#107C10", "mForest"),
        ("presentation","data"):        ("Direct Read/Write", "#107C10", "mForest"),
    }
    ARROW_LABELS  = []
    ARROW_COLORS  = []
    ARROW_MARKERS = []
    for fi in range(len(_tier_keys) - 1):
        pair = (_tier_keys[fi], _tier_keys[fi + 1])
        lbl, clr, mrk = _ARROW_LABEL_MAP.get(pair, ("→", _ac, "mProv"))
        ARROW_LABELS.append(lbl)
        ARROW_COLORS.append(clr)
        ARROW_MARKERS.append(mrk)

    for fi, (tkey, tlabel, temoji, tcolor, tbg) in enumerate(FLOW_TIERS):
        cx = flow_col_xs[fi]
        cards = tier_comps[tkey][:MAX_CARDS_PER_COL]
        extra = len(tier_comps[tkey]) - len(cards)

        # ── Column background ──────────────────────────────────────────
        R(cx, FLOW_Y, FLOW_COL_W, FLOW_COL_H,
          fill=tbg, stroke=tcolor,
          **{"stroke-width":"1.5","rx":"10","filter":"url(#fShadow)"})

        # ── Column header (rounded-top only via path) ───────────────────
        parts.append(
            f'<path d="{hdr_path(cx, FLOW_Y, FLOW_COL_W, COL_HDR_H)}" '
            f'fill="{tcolor}"/>'
        )
        # Subtle shine on header
        parts.append(
            f'<path d="{hdr_path(cx, FLOW_Y, FLOW_COL_W, COL_HDR_H//2)}" '
            f'fill="rgba(255,255,255,.10)"/>'
        )
        # Emoji + label
        T(cx + FLOW_COL_W // 2, FLOW_Y + 20, temoji,
          **{"text-anchor":"middle","font-size":"16","font-family":FONT})
        T(cx + FLOW_COL_W // 2, FLOW_Y + 38, esc(tlabel),
          fill="white",
          **{"font-size":"10","font-weight":"700","text-anchor":"middle","font-family":FONT,
             "letter-spacing":".3"})

        # ── Service cards ───────────────────────────────────────────────
        for ci, comp in enumerate(cards):
            ccx  = cx + CARD_PAD_X
            ccy  = FLOW_Y + COL_PTOP + ci * (CARD_H + CARD_GAP_Y)
            cn   = safe_str(comp.get("name", ""))
            ca   = safe_str(comp.get("azure_service", ""))
            svcs = safe_list(comp.get("services", []))
            icon = get_icon(cn, ca)

            # Card shadow
            R(ccx + 2, ccy + 2, CARD_W, CARD_H,
              fill="rgba(0,0,0,.07)", rx="8")
            # Card body
            R(ccx, ccy, CARD_W, CARD_H,
              fill="white", stroke=tcolor,
              **{"stroke-width":"1.2","rx":"8"})
            # Top accent (5px color bar)
            parts.append(
                f'<path d="{hdr_path(ccx, ccy, CARD_W, 5, rx=4)}" '
                f'fill="{tcolor}"/>'
            )
            # Icon background circle
            Ci(ccx + 22, ccy + CARD_H // 2 + 4, 16,
               fill=tcolor, **{"opacity":".12"})
            Ci(ccx + 22, ccy + CARD_H // 2 + 4, 14,
               fill="none", stroke=tcolor, **{"stroke-width":"1.5"})
            T(ccx + 22, ccy + CARD_H // 2 + 9, icon,
              **{"text-anchor":"middle","font-size":"13","font-family":FONT})
            # Service name
            T(ccx + 44, ccy + 26, esc(trunc(cn, 22)),
              fill="#111827",
              **{"font-size":"11","font-weight":"700","font-family":FONT})
            # Azure service label
            T(ccx + 44, ccy + 42, esc(trunc(ca, 26)),
              fill=tcolor, **{"font-size":"8.5","font-family":FONT})
            # Sub-detail tag
            if svcs:
                T(ccx + 44, ccy + 57, esc(trunc(str(svcs[0]), 30)),
                  fill="#9CA3AF", **{"font-size":"8","font-family":FONT})

        # "+N more" label
        if extra > 0:
            T(cx + FLOW_COL_W // 2,
              FLOW_Y + COL_PTOP + len(cards) * (CARD_H + CARD_GAP_Y) + 14,
              f"+ {extra} more…",
              fill=tcolor,
              **{"text-anchor":"middle","font-size":"9","font-style":"italic","font-family":FONT})

        # ── Inter-column horizontal arrows ──────────────────────────────
        if fi < N_FLOW - 1:
            ax1 = cx + FLOW_COL_W        # right edge of this column
            ax2 = flow_col_xs[fi + 1]    # left edge of next column
            amid = (ax1 + ax2) // 2
            col  = ARROW_COLORS[fi]
            mrk  = ARROW_MARKERS[fi]
            lbl  = ARROW_LABELS[fi]
            # Arrow line
            P(f"M {ax1} {ARROW_Y} L {ax2} {ARROW_Y}",
              stroke=col,
              **{"stroke-width":"2.5","fill":"none","marker-end":f"url(#{mrk})"})
            # Arrow label pill
            lpw = len(lbl) * 6 + 16
            R(amid - lpw // 2, ARROW_Y - 22, lpw, 16,
              fill="white", stroke=col,
              **{"stroke-width":"1","rx":"8","opacity":".92"})
            T(amid, ARROW_Y - 10, esc(lbl),
              fill=col,
              **{"font-size":"8","font-weight":"700","text-anchor":"middle","font-family":FONT})
            # Step number circle
            Ci(amid, ARROW_Y + 4, 9, fill=col)
            T(amid, ARROW_Y + 8, str(fi + 2),
              fill="white",
              **{"text-anchor":"middle","font-size":"8","font-weight":"700","font-family":FONT})

    # ═══════════════════════ EXTERNAL SOURCES ══════════════════════════
    # Derive labels from tech stack / data flow
    src_labels = []
    for t in tech_stack:
        tl = t.lower()
        if any(k in tl for k in ["user","client","sharepoint","excel","file","external","browser","erp","crm","source"]):
            src_labels.append(safe_str(t))
    if data_flow:
        lbl0 = safe_str(data_flow[0])
        if lbl0 and lbl0 not in src_labels:
            src_labels.insert(0, lbl0)
    if not src_labels:
        src_labels = ["External Users", "Data Sources", "3rd-party APIs"]
    src_labels = src_labels[:4]

    EXT_CARD_H = 70
    ext_total_h = len(src_labels) * (EXT_CARD_H + 12) - 12
    ext_y0 = FLOW_Y + (FLOW_COL_H - ext_total_h) // 2

    # Header label
    T(EXT_X + EXT_W // 2, ext_y0 - 14, "External",
      fill="#4B5563",
      **{"font-size":"10","font-weight":"700","text-anchor":"middle","font-family":FONT})
    T(EXT_X + EXT_W // 2, ext_y0 - 2, "Sources",
      fill="#4B5563",
      **{"font-size":"10","font-weight":"700","text-anchor":"middle","font-family":FONT})

    ext_mid_ys = []
    for i, src in enumerate(src_labels):
        ey = ext_y0 + i * (EXT_CARD_H + 12)
        src_icon = ("👤" if any(k in src.lower() for k in ["user","client","person"])
                    else "📁" if any(k in src.lower() for k in ["share","file","excel","document"])
                    else "🏢" if any(k in src.lower() for k in ["erp","crm","system","3rd","third"])
                    else "🌐")
        R(EXT_X + 2, ey + 2, EXT_W, EXT_CARD_H, fill="rgba(0,0,0,.06)", rx="9")
        R(EXT_X, ey, EXT_W, EXT_CARD_H,
          fill="#F8FAFC", stroke="#9CA3AF",
          **{"stroke-width":"1.5","stroke-dasharray":"5,3","rx":"9"})
        parts.append(
            f'<path d="{hdr_path(EXT_X, ey, EXT_W, 4, rx=4)}" fill="#9CA3AF"/>'
        )
        Ci(EXT_X + 21, ey + EXT_CARD_H // 2 + 2, 14, fill="#E5E7EB", stroke="#9CA3AF",
           **{"stroke-width":"1"})
        T(EXT_X + 21, ey + EXT_CARD_H // 2 + 7, src_icon,
          **{"text-anchor":"middle","font-size":"12","font-family":FONT})
        T(EXT_X + 41, ey + EXT_CARD_H // 2 - 3, esc(trunc(src, 16)),
          fill="#374151",
          **{"font-size":"10","font-weight":"600","font-family":FONT})
        T(EXT_X + 41, ey + EXT_CARD_H // 2 + 11, "External Source",
          fill="#9CA3AF", **{"font-size":"8","font-family":FONT})
        ext_mid_ys.append(ey + EXT_CARD_H // 2 + 2)

    # Arrow: External → first flow column
    ax_ext = EXT_X + EXT_W
    ax_col0 = flow_col_xs[0]
    amid_ext = (ax_ext + ax_col0) // 2
    emy = ext_mid_ys[0] if ext_mid_ys else ARROW_Y
    # Draw a two-segment path: right from EXT → bend to ARROW_Y → right to col
    if abs(emy - ARROW_Y) > 4:
        P(f"M {ax_ext} {emy} C {amid_ext} {emy} {amid_ext} {ARROW_Y} {ax_col0} {ARROW_Y}",
          stroke="#6B7280",
          **{"stroke-width":"2","fill":"none","stroke-dasharray":"6,3",
             "marker-end":"url(#mGray)"})
    else:
        P(f"M {ax_ext} {ARROW_Y} L {ax_col0} {ARROW_Y}",
          stroke="#6B7280",
          **{"stroke-width":"2","fill":"none","stroke-dasharray":"6,3",
             "marker-end":"url(#mGray)"})
    # Step 1 label
    lpw1 = 58
    R(amid_ext - lpw1 // 2, ARROW_Y - 22, lpw1, 16,
      fill="white", stroke="#6B7280",
      **{"stroke-width":"1","rx":"8","opacity":".92"})
    T(amid_ext, ARROW_Y - 10, "Request",
      fill="#6B7280",
      **{"font-size":"8","font-weight":"700","text-anchor":"middle","font-family":FONT})
    Ci(amid_ext, ARROW_Y + 4, 9, fill="#6B7280")
    T(amid_ext, ARROW_Y + 8, "1",
      fill="white",
      **{"text-anchor":"middle","font-size":"8","font-weight":"700","font-family":FONT})

    # ═══════════════════════ CONSUMERS ════════════════════════════════
    cons_labels = []
    for t in tech_stack:
        tl = t.lower()
        if any(k in tl for k in ["teams","copilot","power bi","portal","dashboard","app","mobile","client app"]):
            cons_labels.append(safe_str(t))
    if data_flow and len(data_flow) > 1:
        lblz = safe_str(data_flow[-1])
        if lblz and lblz not in cons_labels:
            cons_labels.insert(0, lblz)
    if not cons_labels:
        cons_labels = ["End Users", "Web Portal", "Mobile App"]
    cons_labels = cons_labels[:4]

    CONS_CARD_H = 70
    cons_total_h = len(cons_labels) * (CONS_CARD_H + 12) - 12
    cons_y0 = FLOW_Y + (FLOW_COL_H - cons_total_h) // 2

    _cc = pcfg["cons_color"]
    _cb = pcfg["cons_bg"]

    T(CONS_X + CONS_W // 2, cons_y0 - 14, "Consumers",
      fill=_cc,
      **{"font-size":"10","font-weight":"700","text-anchor":"middle","font-family":FONT})
    T(CONS_X + CONS_W // 2, cons_y0 - 2, "& Clients",
      fill=_cc,
      **{"font-size":"10","font-weight":"700","text-anchor":"middle","font-family":FONT})

    cons_mid_ys = []
    for i, cons in enumerate(cons_labels):
        cy2 = cons_y0 + i * (CONS_CARD_H + 12)
        c_icon = ("💬" if "teams" in cons.lower()
                  else "🤖" if "copilot" in cons.lower()
                  else "📊" if any(k in cons.lower() for k in ["bi","dashboard","report"])
                  else "📱" if "mobile" in cons.lower()
                  else "🌐")
        R(CONS_X + 2, cy2 + 2, CONS_W, CONS_CARD_H, fill="rgba(0,0,0,.06)", rx="9")
        R(CONS_X, cy2, CONS_W, CONS_CARD_H,
          fill=_cb, stroke=_cc,
          **{"stroke-width":"1.5","rx":"9"})
        parts.append(
            f'<path d="{hdr_path(CONS_X, cy2, CONS_W, 4, rx=4)}" fill="{_cc}"/>'
        )
        Ci(CONS_X + 21, cy2 + CONS_CARD_H // 2 + 2, 14,
           fill=_cc, **{"opacity":".15"})
        Ci(CONS_X + 21, cy2 + CONS_CARD_H // 2 + 2, 13,
           fill="none", stroke=_cc, **{"stroke-width":"1.5"})
        T(CONS_X + 21, cy2 + CONS_CARD_H // 2 + 7, c_icon,
          **{"text-anchor":"middle","font-size":"12","font-family":FONT})
        T(CONS_X + 41, cy2 + CONS_CARD_H // 2 - 3, esc(trunc(cons, 17)),
          fill="#1E3A5F",
          **{"font-size":"10","font-weight":"700","font-family":FONT})
        T(CONS_X + 41, cy2 + CONS_CARD_H // 2 + 11, "Consumer",
          fill=_cc, **{"font-size":"8","font-family":FONT})
        cons_mid_ys.append(cy2 + CONS_CARD_H // 2 + 2)

    # Arrow: last flow column → Consumers (use data tier color)
    _data_color = "#107C10"
    for _tk, _tl, _te, _tc, _tb in FLOW_TIERS:
        if _tk == "data":
            _data_color = _tc
            break
    ax_last = flow_col_xs[-1] + FLOW_COL_W
    amid_cons = (ax_last + CONS_X) // 2
    cmy = cons_mid_ys[0] if cons_mid_ys else ARROW_Y
    if abs(cmy - ARROW_Y) > 4:
        P(f"M {ax_last} {ARROW_Y} C {amid_cons} {ARROW_Y} {amid_cons} {cmy} {CONS_X} {cmy}",
          stroke=_data_color,
          **{"stroke-width":"2.5","fill":"none","marker-end":"url(#mForest)"})
    else:
        P(f"M {ax_last} {ARROW_Y} L {CONS_X} {ARROW_Y}",
          stroke=_data_color,
          **{"stroke-width":"2.5","fill":"none","marker-end":"url(#mForest)"})
    lpw2 = 56
    R(amid_cons - lpw2 // 2, ARROW_Y - 22, lpw2, 16,
      fill="white", stroke=_data_color,
      **{"stroke-width":"1","rx":"8","opacity":".92"})
    T(amid_cons, ARROW_Y - 10, "Results",
      fill=_data_color,
      **{"font-size":"8","font-weight":"700","text-anchor":"middle","font-family":FONT})
    Ci(amid_cons, ARROW_Y + 4, 9, fill=_data_color)
    T(amid_cons, ARROW_Y + 8, str(N_FLOW + 1),
      fill="white",
      **{"text-anchor":"middle","font-size":"8","font-weight":"700","font-family":FONT})

    # ═══════════════════════ INFRA BANDS ══════════════════════════════
    for bi, (tkey, tlabel, tcolor, tbg) in enumerate(INFRA_TIERS):
        by = BAND_Y0 + bi * (BAND_H + BAND_GAP)
        # Band shadow + body
        R(BAND_X + 2, by + 2, BAND_W, BAND_H, fill="rgba(0,0,0,.06)", rx="10")
        R(BAND_X, by, BAND_W, BAND_H,
          fill=tbg, stroke=tcolor,
          **{"stroke-width":"1.5","rx":"10"})
        # Left label pill
        lpw_b = len(tlabel) * 7 + 24
        R(BAND_X + 10, by + BAND_H // 2 - 16, lpw_b, 30, fill=tcolor, rx="6")
        T(BAND_X + 20, by + BAND_H // 2 + 5, esc(tlabel),
          fill="white", **{"font-size":"11","font-weight":"700","font-family":FONT})

        # Service cards inside band
        bcards = tier_comps[tkey]
        card_x = BAND_X + lpw_b + 22
        BCW, BCH = 164, BAND_H - 18
        for ci, comp in enumerate(bcards[:7]):
            ccn  = safe_str(comp.get("name", ""))
            cca  = safe_str(comp.get("azure_service", ""))
            icon = get_icon(ccn, cca)
            bcx  = card_x + ci * (BCW + 10)
            bcy  = by + 9
            if bcx + BCW > BAND_X + BAND_W - 10:
                break
            R(bcx + 2, bcy + 2, BCW, BCH, fill="rgba(0,0,0,.07)", rx="7")
            R(bcx, bcy, BCW, BCH,
              fill="white", stroke=tcolor,
              **{"stroke-width":"1","rx":"7"})
            parts.append(
                f'<path d="{hdr_path(bcx, bcy, BCW, 4, rx=4)}" fill="{tcolor}"/>'
            )
            Ci(bcx + 18, bcy + BCH // 2 + 2, 12,
               fill=tcolor, **{"opacity":".14"})
            Ci(bcx + 18, bcy + BCH // 2 + 2, 11,
               fill="none", stroke=tcolor, **{"stroke-width":"1.2"})
            T(bcx + 18, bcy + BCH // 2 + 6, icon,
              **{"text-anchor":"middle","font-size":"11","font-family":FONT})
            T(bcx + 36, bcy + BCH // 2 - 4, esc(trunc(ccn, 18)),
              fill="#111827", **{"font-size":"10","font-weight":"600","font-family":FONT})
            T(bcx + 36, bcy + BCH // 2 + 10, esc(trunc(cca, 22)),
              fill=tcolor, **{"font-size":"8","font-family":FONT})

    # ═══════════════════════ LEGEND ════════════════════════════════════
    leg_items = [(t[3], t[0], t[1]) for t in FLOW_TIERS] + [(t[2], t[0], t[1]) for t in INFRA_TIERS]
    leg_total_w = min(BAND_W, len(leg_items) * 175 + 80)
    R(BAND_X, LEG_Y, leg_total_w, 30,
      fill="white", stroke="#E5E7EB",
      **{"stroke-width":"1","rx":"6"})
    T(BAND_X + 10, LEG_Y + 19, "Legend:",
      fill="#374151", **{"font-size":"9","font-weight":"700","font-family":FONT})
    for li, (lc, lk, ll) in enumerate(leg_items):
        lx = BAND_X + 72 + li * 173
        R(lx, LEG_Y + 10, 11, 11, fill=lc, rx="3")
        T(lx + 16, LEG_Y + 20, esc(trunc(ll, 22)),
          fill="#6B7280", **{"font-size":"8.5","font-family":FONT})

    # Security / availability note
    notes = []
    if security_items:
        notes.append(f"🔒 {len(security_items)} security controls")
    av = safe_str(ar.get("availability", ""))
    if av:
        notes.append(f"🎯 {av}")
    sc = safe_str(ar.get("scalability", ""))
    if sc:
        notes.append(f"📐 {sc}")
    if notes:
        T(BAND_X, LEG_Y + 44, "  ·  ".join(esc(trunc(n, 60)) for n in notes),
          fill="#6B7280", **{"font-size":"8.5","font-family":FONT})

    # ═══════════════════════ ASSEMBLE SVG + HTML ════════════════════════
    SVG_H_FINAL = max(SVG_H, LEG_Y + 58)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{SVG_W}" height="{SVG_H_FINAL}" '
        f'viewBox="0 0 {SVG_W} {SVG_H_FINAL}">'
        + "".join(parts)
        + "</svg>"
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{background:#D8E2EE;font-family:{FONT};overflow-x:auto}}
#wrap{{padding:0 0 20px 0;overflow:auto;cursor:grab}}
#wrap:active{{cursor:grabbing}}
.dl-bar{{position:fixed;bottom:14px;right:16px;display:flex;gap:8px;z-index:10}}
.dl-btn{{background:#0078D4;color:white;border:none;padding:8px 18px;border-radius:7px;
  font-size:12px;font-weight:600;cursor:pointer;font-family:{FONT};
  box-shadow:0 3px 10px rgba(0,80,160,.3);transition:background .15s}}
.dl-btn:hover{{background:#005A9E}}
</style>
</head><body>
<div id="wrap">{svg}</div>
<div class="dl-bar">
  <button class="dl-btn" onclick="dlSVG()">⬇ SVG</button>
  <button class="dl-btn" onclick="dlPNG()">⬇ PNG</button>
</div>
<script>
const _svg=document.querySelector('svg');
const _wrap=document.getElementById('wrap');
let _drag=false,_sx=0,_sy=0,_sl=0,_st=0;
_wrap.addEventListener('mousedown',e=>{{_drag=true;_sx=e.clientX;_sy=e.clientY;_sl=_wrap.scrollLeft;_st=_wrap.scrollTop;}});
document.addEventListener('mouseup',()=>_drag=false);
document.addEventListener('mousemove',e=>{{if(!_drag)return;_wrap.scrollLeft=_sl-(e.clientX-_sx);_wrap.scrollTop=_st-(e.clientY-_sy);}});
function dlSVG(){{
  const s=new XMLSerializer().serializeToString(_svg);
  const b=new Blob([s],{{type:'image/svg+xml'}});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='ECI_Architecture.svg';a.click();
}}
function dlPNG(){{
  const s=new XMLSerializer().serializeToString(_svg);
  const img=new Image();
  img.onload=function(){{
    const c=document.createElement('canvas');
    c.width=_svg.viewBox.baseVal.width*2;c.height=_svg.viewBox.baseVal.height*2;
    const ctx=c.getContext('2d');ctx.scale(2,2);ctx.drawImage(img,0,0);
    c.toBlob(b=>{{const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='ECI_Architecture.png';a.click();}});
  }};
  img.src='data:image/svg+xml;charset=utf-8,'+encodeURIComponent(s);
}}
</script>
</body></html>"""
    return html


def _sanitize_mermaid(code: str) -> str:
    """
    Clean LLM-generated Mermaid to prevent syntax errors.
      1. Strip code fences and %%{init} blocks
      2. Skip prose before diagram declaration
      3. Remove style/classDef/linkStyle/click directives
      4. Normalize special node shapes → safe rectangular brackets
         (cylinder [(...)], stadium ([...]), subroutine [[...]], asymmetric >...]
         all cause Dagre's "Could not find a suitable point" layout error)
      5. Fix self-loops in sequenceDiagram and graph/flowchart
    """
    c = code.strip()

    # Strip markdown code fences
    if "```" in c:
        c = "\n".join(
            l for l in c.splitlines() if not l.strip().startswith("```")
        ).strip()

    # Strip %%{init: ...}%% blocks
    c = re.sub(r'%%\{.*?\}%%', '', c, flags=re.DOTALL).strip()

    lines = c.splitlines()

    # Skip any prose/text before the actual diagram declaration
    DIAG_STARTS = ("sequenceDiagram", "flowchart", "graph ",
                   "graph\t", "classDiagram", "stateDiagram",
                   "erDiagram", "gantt", "pie", "%%{")
    start_idx = 0
    for i, line in enumerate(lines):
        s = line.strip()
        if any(s.startswith(kw) for kw in DIAG_STARTS):
            start_idx = i
            break
    lines = lines[start_idx:]

    # Detect diagram type
    diagram_type = ""
    for line in lines:
        s = line.strip()
        for kw in ("sequenceDiagram", "flowchart", "graph",
                   "classDiagram", "stateDiagram", "erDiagram", "gantt", "pie"):
            if s.startswith(kw):
                diagram_type = kw
                break
        if diagram_type:
            break

    def _norm_shapes(ln):
        """Convert special node shapes to safe rectangular brackets."""
        # Cylinder/database: NodeId[("label")] or NodeId[('label')] or NodeId[(label)]
        # These ALWAYS cause Dagre "suitable point" errors
        ln = re.sub(
            r'(\b\w[\w\-]*)\s*\[\s*\(\s*"([^"]*)"\s*\)\s*\]',
            lambda m: f'{m.group(1)}["{m.group(2)}"]', ln)
        ln = re.sub(
            r"(\b\w[\w\-]*)\s*\[\s*\(\s*'([^']*)'\s*\)\s*\]",
            lambda m: f'{m.group(1)}["{m.group(2)}"]', ln)
        ln = re.sub(
            r'(\b\w[\w\-]*)\s*\[\s*\(\s*([^)"\'()\]]+?)\s*\)\s*\]',
            lambda m: f'{m.group(1)}["{m.group(2).strip()}"]', ln)
        # Stadium: NodeId(["label"]) or NodeId([label])
        ln = re.sub(
            r'(\b\w[\w\-]*)\s*\(\s*\[\s*"([^"]*)"\s*\]\s*\)',
            lambda m: f'{m.group(1)}["{m.group(2)}"]', ln)
        ln = re.sub(
            r'(\b\w[\w\-]*)\s*\(\s*\[\s*([^\]"]+?)\s*\]\s*\)',
            lambda m: f'{m.group(1)}["{m.group(2).strip()}"]', ln)
        # Subroutine: NodeId[["label"]] or NodeId[[label]]
        ln = re.sub(
            r'(\b\w[\w\-]*)\s*\[\s*\[\s*"([^"]*)"\s*\]\s*\]',
            lambda m: f'{m.group(1)}["{m.group(2)}"]', ln)
        ln = re.sub(
            r'(\b\w[\w\-]*)\s*\[\s*\[\s*([^\]"]+?)\s*\]\s*\]',
            lambda m: f'{m.group(1)}["{m.group(2).strip()}"]', ln)
        # Asymmetric/flag: NodeId>label]
        ln = re.sub(
            r'(\b\w[\w\-]*)\s*>\s*([^"\]\[]+?)\s*\]',
            lambda m: f'{m.group(1)}["{m.group(2).strip()}"]', ln)
        return ln

    out = []
    for line in lines:
        s = line.strip()

        # Remove style directives — LLM-generated CSS is frequently malformed
        if re.match(r'\s*style\s+\S+\s+', line):
            continue
        # Remove classDef lines
        if re.match(r'\s*classDef\s+', line):
            continue
        # Remove linkStyle lines
        if re.match(r'\s*linkStyle\s+', line):
            continue
        # Remove standalone class-assignment lines (class NodeA someClass)
        if re.match(r'\s*class\s+\S+\s+\S+\s*$', line) and ":::" not in line:
            continue
        # Remove click event lines (unsupported in embedded mode)
        if re.match(r'\s*click\s+', line):
            continue

        # Normalize special node shapes for graph/flowchart diagrams
        if diagram_type in ("graph", "flowchart"):
            line = _norm_shapes(line)

        # sequenceDiagram: self-message A->>A: msg  →  Note over A: msg
        if diagram_type == "sequenceDiagram":
            m = re.match(r'^\ *(\w+)\ *(->>|-->>|->|-->)\ *\1\ *:\ *(.+)$', line)
            if m:
                actor, _, msg = m.group(1), m.group(2), m.group(3)
                out.append(f"    Note over {actor}: {msg}")
                continue

        # graph/flowchart: self-loop  A --> A  or  A -->|label| A
        if diagram_type in ("graph", "flowchart"):
            m = re.match(
                r'^\ *(\w[\w\-]*)\ *(?:-->|---|-\.->|===>?)\ *(?:\|[^|]*\|)?\ *\1\s*$',
                line,
            )
            if m:
                out.append(f"    %% removed self-loop: {s}")
                continue

        out.append(line)

    return "\n".join(out)


def render_mermaid(mermaid_code, height=450):
    """Render a Mermaid.js diagram using streamlit HTML component."""
    import json as _json

    clean = _sanitize_mermaid(mermaid_code)
    code_json = _json.dumps(clean)
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"></script>
<style>
  html,body{{margin:0;padding:8px;background:#151c2e;}}
  #out{{text-align:center;}}
  svg{{max-width:100%;height:auto;}}
  #err{{color:#ff6b6b;font-family:monospace;font-size:12px;
        background:#1e1a2e;border:1px solid #ff6b6b55;
        padding:10px;border-radius:6px;white-space:pre-wrap;text-align:left;}}
  #hidden{{position:absolute;left:-9999px;top:-9999px;}}
</style>
</head><body>
<div id="out"></div>
<div id="hidden"></div>
<script>
(async function(){{
  const code = {code_json};
  const delay = ms => new Promise(r => setTimeout(r, ms));
  mermaid.initialize({{
    startOnLoad: false, securityLevel: 'loose', theme: 'dark',
    themeVariables:{{
      primaryColor:'#16274B', primaryTextColor:'#e2e8f0',
      primaryBorderColor:'#00929E', lineColor:'#00b4d8',
      secondaryColor:'#151c2e', tertiaryColor:'#0a0e1a', fontFamily:'sans-serif'
    }}
  }});
  let lastErr;
  for (let attempt = 0; attempt < 4; attempt++) {{
    if (attempt > 0) await delay(300 * attempt);
    try {{
      const el = document.getElementById('hidden');
      const {{ svg }} = await mermaid.render('mg_' + Date.now(), code, el);
      document.getElementById('out').innerHTML = svg;
      return;
    }} catch(e) {{ lastErr = e; }}
  }}
  document.getElementById('out').innerHTML =
    '<div id="err">\u26a0 ' + (lastErr.message || String(lastErr)) + '</div>';
}})();
</script>
</body></html>"""
    st.components.v1.html(html, height=height, scrolling=True)


def render_mermaid_tabs(diagrams):
    """Render all architecture diagrams in a SINGLE iframe with built-in tabs.

    diagrams: list of (key, label, mermaid_code) tuples

    Shows a "Generate Diagrams" button inside the HTML component — clicking it
    renders diagrams purely in JavaScript with NO Python rerun, so the active
    Streamlit tab never resets to tab 0.
    """
    import json as _json

    tabs_data = []
    for key, label, code in diagrams:
        clean = _sanitize_mermaid(code) if code else ""
        tabs_data.append({"key": key, "label": label, "code": clean})

    tabs_json = _json.dumps(tabs_data)

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:#151c2e;font-family:sans-serif;}}
  #genBtn{{
    display:block;margin:18px auto 12px;padding:10px 28px;
    background:linear-gradient(135deg,#00929E,#0077b6);color:#fff;
    border:none;border-radius:8px;font-size:14px;font-weight:600;
    cursor:pointer;letter-spacing:.3px;
  }}
  #genBtn:hover{{background:linear-gradient(135deg,#00b4d8,#0096c7);}}
  #genBtn:disabled{{opacity:.5;cursor:default;}}
  #diagArea{{display:none;}}
  .tabs{{display:flex;gap:4px;padding:10px 10px 0;border-bottom:1px solid #2a3550;flex-wrap:wrap;}}
  .tab{{padding:7px 14px;cursor:pointer;border-radius:6px 6px 0 0;font-size:13px;
        color:#94a3b8;background:#1e2a42;border:1px solid #2a3550;border-bottom:none;}}
  .tab.active{{color:#00b4d8;background:#151c2e;border-color:#00929E;}}
  .panels{{padding:12px;}}
  .panel{{display:none;}}
  .panel.active{{display:block;}}
  .diagram{{text-align:center;min-height:60px;}}
  svg{{max-width:100%;height:auto;}}
  .err{{color:#ff6b6b;font-family:monospace;font-size:12px;background:#1e1a2e;
        border:1px solid #ff6b6b55;padding:10px;border-radius:6px;white-space:pre-wrap;}}
  #hidden{{position:absolute;left:-9999px;top:-9999px;}}
  .spinner{{color:#94a3b8;font-size:13px;padding:20px;}}
</style>
</head><body>
<button id="genBtn" onclick="generateDiagrams()">&#x1F504; Generate Diagrams</button>
<div id="diagArea">
  <div class="tabs" id="tabbar"></div>
  <div class="panels" id="panels"></div>
</div>
<div id="hidden"></div>
<script>
const TABS = {tabs_json};
const delay = ms => new Promise(r => setTimeout(r, ms));

// Build tab/panel DOM immediately (hidden) so clicking a tab after generate works
(function buildDOM(){{
  const tabbar = document.getElementById('tabbar');
  const panels = document.getElementById('panels');
  TABS.forEach((t, i) => {{
    const btn = document.createElement('div');
    btn.className = 'tab' + (i===0 ? ' active' : '');
    btn.textContent = t.label;
    btn.onclick = () => {{
      document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(x=>x.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById('panel_'+i).classList.add('active');
    }};
    tabbar.appendChild(btn);

    const panel = document.createElement('div');
    panel.className = 'panel' + (i===0 ? ' active' : '');
    panel.id = 'panel_' + i;
    panel.innerHTML = '<div class="diagram spinner" id="diag_'+i+'">Ready to render\u2026</div>';
    panels.appendChild(panel);
  }});
}})();

mermaid.initialize({{
  startOnLoad: false, securityLevel: 'loose', theme: 'dark',
  themeVariables:{{
    primaryColor:'#16274B', primaryTextColor:'#e2e8f0',
    primaryBorderColor:'#00929E', lineColor:'#00b4d8',
    secondaryColor:'#151c2e', tertiaryColor:'#0a0e1a', fontFamily:'sans-serif'
  }}
}});

async function generateDiagrams() {{
  const btn = document.getElementById('genBtn');
  btn.disabled = true;
  btn.textContent = '\u23F3 Rendering\u2026';
  document.getElementById('diagArea').style.display = 'block';

  // Mark all panels as "rendering"
  TABS.forEach((t, i) => {{
    document.getElementById('diag_'+i).textContent = 'Rendering\u2026';
    document.getElementById('diag_'+i).className = 'diagram spinner';
  }});

  const el = document.getElementById('hidden');
  for (let i = 0; i < TABS.length; i++) {{
    const t = TABS[i];
    const out = document.getElementById('diag_' + i);
    if (!t.code) {{ out.innerHTML = '<div class="err">No diagram data.</div>'; continue; }}
    let lastErr;
    let rendered = false;
    for (let attempt = 0; attempt < 4; attempt++) {{
      if (attempt > 0) await delay(400 * attempt);
      try {{
        const {{ svg }} = await mermaid.render('mg_'+i+'_'+attempt+'_'+Date.now(), t.code, el);
        out.className = 'diagram';
        out.innerHTML = svg;
        rendered = true;
        break;
      }} catch(e) {{ lastErr = e; }}
    }}
    if (!rendered) {{
      out.innerHTML = '<div class="err">\u26a0 Diagram parse error: '+((lastErr&&lastErr.message)||String(lastErr))+'<br><br><details><summary>Raw code</summary><pre style="font-size:10px;text-align:left;white-space:pre-wrap">'+t.code.replace(/</g,'&lt;')+'</pre></details></div>';
    }}
  }}
  btn.textContent = '\u2705 Diagrams Ready';
  btn.style.background = '#1e3a2e';
}}
</script>
</body></html>"""
    st.components.v1.html(html, height=680, scrolling=True)


# ═══════════════════════════════════════════════════════════════════════
#  AUDIO / VIDEO TRANSCRIPT EXTRACTOR
# ═══════════════════════════════════════════════════════════════════════

def extract_audio_transcript(uploaded_file):
    """Extract transcript from uploaded transcript files. Returns text."""
    name = uploaded_file.name.lower()
    data = uploaded_file.read()
    uploaded_file.seek(0)

    # For text-based transcript files (SRT, VTT, TXT)
    if name.endswith((".txt", ".srt", ".vtt")):
        text = data.decode("utf-8", errors="replace")
        text = re.sub(r'\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[.,]\d{3}', '', text)
        text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'WEBVTT.*?\n', '', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    # For JSON transcript exports (Teams, Zoom, Otter.ai)
    if name.endswith(".json"):
        try:
            transcript_data = json.loads(data.decode("utf-8"))
            parts = []
            if isinstance(transcript_data, list):
                for item in transcript_data:
                    if isinstance(item, dict):
                        speaker = item.get("speaker", item.get("name", "Speaker"))
                        text_val = item.get("text", item.get("content", item.get("transcript", "")))
                        if text_val:
                            parts.append(f"{speaker}: {text_val}")
            elif isinstance(transcript_data, dict):
                for seg in transcript_data.get("segments", transcript_data.get("results", transcript_data.get("transcript", []))):
                    if isinstance(seg, dict):
                        speaker = seg.get("speaker", "Speaker")
                        text_val = seg.get("text", seg.get("content", ""))
                        if text_val:
                            parts.append(f"{speaker}: {text_val}")
            return "\n".join(parts) if parts else data.decode("utf-8", errors="replace")[:50000]
        except Exception:
            return data.decode("utf-8", errors="replace")[:50000]

    # For DOCX transcripts (exported meeting notes)
    if name.endswith(".docx"):
        try:
            from docx import Document
            doc = Document(io.BytesIO(data))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
        except Exception:
            return "[Could not extract DOCX transcript]"

    # For CSV transcript exports
    if name.endswith(".csv"):
        text = data.decode("utf-8", errors="replace")
        lines = text.split("\n")
        parts = []
        for line in lines[1:]:
            cols = line.split(",")
            if len(cols) >= 2:
                parts.append(cols[-1].strip().strip('"'))
        return "\n".join(parts) if parts else text[:50000]

    return "[Unsupported format: " + name.split(".")[-1] + ". Please upload TXT, SRT, VTT, JSON, DOCX, or CSV transcript files.]"


# ═══════════════════════════════════════════════════════════════════════
#  INTERACTIVE ARCHITECTURE TAB — 10+ diagram types, fully dynamic
# ═══════════════════════════════════════════════════════════════════════

def _hex_to_rgba(hex_color: str, alpha: float = 1.0) -> str:
    """Convert a 6-char hex color (#RRGGBB) to rgba() string Plotly always accepts."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"
    return hex_color  # pass-through if already rgba/named


def _plotly_arch_diagram(ar: dict, se: dict) -> None:
    """Interactive Solution Architecture — clickable node cards, animated connections, slide-up detail panel."""
    import json as _jj

    comps  = safe_list(ar.get("components", []))
    flow   = safe_list(ar.get("data_flow", []))
    sec    = safe_list(ar.get("security", []))
    tech   = safe_list(se.get("technology_stack", []))
    proj   = safe_str(se.get("project_type", "Enterprise Solution"))

    TIER_DEF = [
        ("External",       "#06b6d4", "👤", ["client","user","browser","mobile","external","webhook","third-party"]),
        ("Presentation",   "#a78bfa", "🎨", ["ui ","frontend","web app","portal","dashboard","react","angular","spa","teams","copilot studio","power bi"]),
        ("API / Gateway",  "#0078d4", "⚡", ["api management","apim","front door","cdn","gateway","load bal","signalr"]),
        ("Application",    "#00b294", "⚙️",  ["app service","function","container","backend","logic app","service bus","event grid"]),
        ("AI & Cognitive", "#e040fb", "🤖", ["openai","gpt","ai search","cognitive","foundry","claude","ml","embedding","vector","rag"]),
        ("Data & Storage", "#22c55e", "🗄️", ["sql","cosmos","blob","storage","database","redis","cache","sharepoint","data lake"]),
        ("Security",       "#f97316", "🔒", ["key vault","entra","active dir","defender","firewall","mfa","identity","azure ad","policy"]),
        ("Monitoring",     "#facc15", "📊", ["monitor","insights","analytics","devops","logging","observ"]),
    ]

    comp_data = []
    for idx, raw in enumerate(comps):
        c      = safe_dict(raw)
        name   = safe_str(c.get("name", "Component " + str(idx + 1)))
        desc   = safe_str(c.get("description", ""))
        ctype  = safe_str(c.get("type", ""))
        conns  = safe_list(c.get("connections", []))
        ctechs = safe_list(c.get("technology", []))
        search = (name + " " + desc + " " + ctype).lower()
        tier_name = "Application"; tier_color = "#00b294"; tier_icon = "\u2699\ufe0f"
        for tname, tcol, ticon, kws in TIER_DEF:
            if any(kw in search for kw in kws):
                tier_name = tname; tier_color = tcol; tier_icon = ticon; break
        comp_data.append({
            "id": "c" + str(idx), "name": name, "type": ctype or tier_name,
            "desc": desc, "tier": tier_name, "color": tier_color, "icon": tier_icon,
            "conns": [safe_str(x) for x in conns],
            "techs": [safe_str(x) for x in ctechs],
        })

    flow_steps = []
    for fitem in flow[:14]:
        fs = safe_str(fitem) if isinstance(fitem, str) else safe_str(safe_dict(fitem).get("step", safe_str(fitem)))
        flow_steps.append(fs[:85])

    def _clean(s):
        # Remove surrogate code points so UTF-8 encoding never fails
        return s.encode("utf-8", errors="replace").decode("utf-8") if isinstance(s, str) else s

    for cd in comp_data:
        cd["name"]  = _clean(cd["name"])
        cd["desc"]  = _clean(cd["desc"])
        cd["type"]  = _clean(cd["type"])
        cd["conns"] = [_clean(x) for x in cd["conns"]]
        cd["techs"] = [_clean(x) for x in cd["techs"]]

    cj  = _jj.dumps(comp_data,   ensure_ascii=True)
    tj  = _jj.dumps([{"name": t[0], "color": t[1], "icon": t[2]} for t in TIER_DEF], ensure_ascii=False)
    fj  = _jj.dumps([_clean(s) for s in flow_steps], ensure_ascii=True)
    sj  = _jj.dumps([_clean(safe_str(s)) for s in sec[:10]], ensure_ascii=True)
    thj = _jj.dumps([_clean(safe_str(t)) for t in tech[:15]], ensure_ascii=True)
    nc  = str(len(comp_data))
    nf  = str(len(flow_steps))
    ns  = str(len(sec))
    nt  = str(len(tech))
    pe  = _clean(proj).replace("'", "\\'")

    # ── Static CSS ──────────────────────────────────────────────────────────────
    _CSS = """* {margin:0;padding:0;box-sizing:border-box}
:root {--bg:#07101f;--sur:#0d1b2e;--sur2:#101e33;--brd:#1e3654;--txt:#e2e8f0;--mut:#64748b}
body {font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--txt);overflow-x:hidden}
.hdr {background:#0a1628;border-bottom:1px solid #1e3654;padding:11px 16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.htitle {font-size:.95rem;font-weight:800;color:#e2e8f0;display:flex;align-items:center;gap:8px}
.hbadge {font-size:.58rem;background:#0f2a4a;border:1px solid #0078d4;border-radius:20px;padding:2px 9px;color:#60a5fa;font-weight:700}
.stats {display:flex;gap:12px;margin-left:auto}
.stat {font-size:.65rem;color:#64748b;text-align:center}
.stat b {display:block;font-size:.9rem;color:#e2e8f0;font-weight:800}
.srch {background:#101e33;border:1px solid #1e3654;border-radius:8px;padding:4px 11px;display:flex;align-items:center;gap:6px}
.srch input {background:none;border:none;outline:none;color:#e2e8f0;font-size:.76rem;width:130px}
.canvas {overflow-x:auto;padding:12px 16px;min-height:400px}
.tier-row {display:flex;gap:7px;min-width:max-content;align-items:flex-start}
.tier-col {display:flex;flex-direction:column;min-width:148px;max-width:166px}
.tier-hd {font-size:.57rem;font-weight:800;letter-spacing:1px;text-transform:uppercase;padding:5px 8px;text-align:center;border-radius:7px 7px 0 0;margin-bottom:5px}
.cards {display:flex;flex-direction:column;gap:5px}
.card {background:#0d1b2e;border:1px solid #1e3654;border-radius:9px;padding:9px;cursor:pointer;transition:all .2s;position:relative;overflow:hidden}
.card::before {content:'';position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--tc);transition:width .18s}
.card:hover {transform:translateY(-2px);box-shadow:0 6px 28px rgba(0,0,0,.45),0 0 14px var(--gw)}
.card:hover::before {width:5px}
.card.active {border-color:var(--tc);box-shadow:0 0 22px var(--gw)}
.card.dimmed {opacity:.28;pointer-events:none}
.cico {font-size:1.2rem;margin-bottom:3px;display:block}
.cnm {font-size:.73rem;font-weight:700;color:#e2e8f0;line-height:1.2;margin-bottom:2px}
.cty {font-size:.56rem;color:#64748b;text-transform:uppercase;letter-spacing:.3px}
.cbadge {display:inline-block;font-size:.51rem;font-weight:700;padding:1px 6px;border-radius:10px;margin-top:4px}
.arr {display:flex;align-items:center;padding-top:26px;opacity:.5;min-width:22px}
.panel {position:fixed;bottom:0;left:0;right:0;background:linear-gradient(180deg,#0b1829,#071221);border-top:2px solid #1e3654;border-radius:14px 14px 0 0;transform:translateY(100%);transition:transform .32s cubic-bezier(.16,1,.3,1);z-index:999;max-height:54vh;overflow-y:auto}
.panel.open {transform:translateY(0)}
.drag {width:36px;height:4px;background:#1e3654;border-radius:2px;margin:9px auto 0}
.ph {display:flex;align-items:center;gap:10px;padding:11px 16px 8px;border-bottom:1px solid #1e3654;position:sticky;top:0;background:#0b1829;z-index:1}
.phico {font-size:1.8rem}
.phnm {font-size:.95rem;font-weight:800;color:#e2e8f0}
.phsub {font-size:.62rem;color:#64748b;margin-top:1px}
.phtr {font-size:.58rem;font-weight:700;padding:3px 9px;border-radius:12px;border:1px solid}
.phcl {margin-left:auto;cursor:pointer;font-size:1.05rem;color:#64748b;padding:4px 8px;border-radius:6px;background:#101e33;border:1px solid #1e3654;transition:all .15s}
.phcl:hover {color:#e2e8f0;border-color:#60a5fa}
.pb {display:grid;grid-template-columns:2fr 1fr 1fr;gap:10px;padding:11px 16px 16px}
.ps {background:#101e33;border:1px solid #1e3654;border-radius:9px;padding:10px}
.plbl {font-size:.56rem;color:#64748b;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px}
.ptxt {font-size:.76rem;color:#cbd5e1;line-height:1.65}
.trow {display:flex;flex-wrap:wrap;gap:4px}
.tag {font-size:.61rem;padding:2px 7px;border-radius:10px;background:#0f2a4a;border:1px solid #1e4a80;color:#93c5fd}
.ci {font-size:.71rem;color:#93c5fd;padding:2px 0;border-bottom:1px solid #1e3654;display:flex;align-items:center;gap:5px}
.ci::before {content:'→';color:#0078d4}
.fstrip {display:flex;gap:0;overflow-x:auto;padding:7px 16px;border-top:1px solid #1e3654;background:#0d1b2e;scrollbar-width:thin}
.fstep {display:flex;align-items:center;flex-shrink:0}
.fnode {font-size:.62rem;background:#07101f;border:1px solid #1e3654;border-radius:6px;padding:3px 8px;color:#94a3b8;max-width:126px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.farr {font-size:.8rem;color:#1e3654;padding:0 2px;flex-shrink:0}
.lgnd {display:flex;flex-wrap:wrap;gap:6px;padding:6px 16px;border-top:1px solid #1e3654}
.li {display:flex;align-items:center;gap:4px;font-size:.59rem;color:#64748b}
.ld {width:7px;height:7px;border-radius:2px}
@keyframes fa {to {stroke-dashoffset:-20}}
.fl {animation:fa 1s linear infinite}
::-webkit-scrollbar {width:4px;height:4px}
::-webkit-scrollbar-track {background:#07101f}
::-webkit-scrollbar-thumb {background:#1e3654;border-radius:3px}"""

    # ── Static JS ───────────────────────────────────────────────────────────────
    _JS = """let aid=null;

const lg=document.getElementById('lg');
TIERS.forEach(t=>{
  const n=COMPS.filter(c=>c.tier===t.name).length;
  if(!n)return;
  lg.innerHTML+=`<div class='li'><div class='ld' style='background:${t.color}'></div>${t.icon} ${t.name} (${n})</div>`;
});

const fs=document.getElementById('fs');
FLOWS.forEach((s,i)=>{
  const d=document.createElement('div');
  d.className='fstep';
  d.innerHTML=(i>0?'<span class="farr">\u2192</span>':'')+`<div class='fnode' title='${s}'>${i+1}. ${s}</div>`;
  fs.appendChild(d);
});

const tr=document.getElementById('tr');
const used=TIERS.filter(t=>COMPS.some(c=>c.tier===t.name));
used.forEach((tier,ti)=>{
  if(ti>0){
    const a=document.createElement('div');
    a.className='arr';
    a.innerHTML=`<svg width='22' viewBox='0 0 22 60' fill='none'>
      <line x1='11' y1='0' x2='11' y2='44' stroke='${tier.color}' stroke-width='1.5' stroke-dasharray='4 3' class='fl'/>
      <polygon points='5,43 17,43 11,56' fill='${tier.color}' opacity='.7'/>
    </svg>`;
    tr.appendChild(a);
  }
  const tc=COMPS.filter(c=>c.tier===tier.name);
  const col=document.createElement('div');
  col.className='tier-col';
  col.innerHTML=`<div class='tier-hd' style='background:${tier.color}20;color:${tier.color};border:1px solid ${tier.color}50'>${tier.icon} ${tier.name}</div><div class='cards' id='tc${ti}'></div>`;
  tr.appendChild(col);
  const cd=col.querySelector('.cards');
  tc.forEach(comp=>{
    const card=document.createElement('div');
    card.className='card';
    card.id='card-'+comp.id;
    card.style.cssText=`--tc:${comp.color};--gw:${comp.color}44`;
    card.dataset.nm=comp.name.toLowerCase();
    card.innerHTML=`<span class='cico'>${comp.icon}</span><div class='cnm'>${comp.name}</div><div class='cty'>${comp.type}</div><span class='cbadge' style='background:${comp.color}22;color:${comp.color};border:1px solid ${comp.color}55'>${comp.tier}</span>`;
    card.addEventListener('click',()=>openPanel(comp));
    cd.appendChild(card);
  });
});

function openPanel(comp){
  if(aid){const p=document.getElementById('card-'+aid);if(p){p.classList.remove('active');p.style.background='';}}
  aid=comp.id;
  const card=document.getElementById('card-'+comp.id);
  if(card){card.classList.add('active');card.style.background=comp.color+'18';}
  document.getElementById('ph').innerHTML=`
    <span class='phico'>${comp.icon}</span>
    <div><div class='phnm'>${comp.name}</div><div class='phsub'>${comp.type}</div></div>
    <span class='phtr' style='color:${comp.color};border-color:${comp.color};background:${comp.color}20'>${comp.tier}</span>
    <div class='phcl' onclick='closePanel()'>\u2715</div>`;
  const connH=comp.conns.length>0
    ?comp.conns.slice(0,6).map(x=>`<div class='ci'>${x}</div>`).join('')
    :'<div style="color:#64748b;font-size:.73rem">No connections documented</div>';
  const techH=(comp.techs.length>0?comp.techs:[comp.tier,'Azure']).map(t=>`<span class='tag'>${t}</span>`).join('');
  const secH=SEC.slice(0,5).map(s=>`<span class='tag'>${s}</span>`).join('')||'<span style="color:#64748b;font-size:.73rem">\u2014</span>';
  const stackH=TECH.slice(0,8).map(t=>`<span class='tag'>${t}</span>`).join('');
  document.getElementById('pb').innerHTML=`
    <div class='ps' style='grid-column:1/3'>
      <div class='plbl'>&#128203; Description</div>
      <div class='ptxt'>${comp.desc||'Core '+comp.tier+' component providing essential capabilities in the solution architecture.'}</div>
    </div>
    <div class='ps' style='background:${comp.color}10;border-color:${comp.color}40'>
      <div class='plbl' style='color:${comp.color}'>\u2b50 Tier Role</div>
      <div class='ptxt'><strong style='color:${comp.color}'>${comp.tier}</strong> layer \u00b7 ${comp.type||comp.name}<div class='trow' style='margin-top:7px'>${techH}</div></div>
    </div>
    <div class='ps' style='grid-column:1/2'>
      <div class='plbl'>&#128279; Connections (${comp.conns.length})</div>
      <div class='ptxt'>${connH}</div>
    </div>
    <div class='ps' style='grid-column:2/4'>
      <div class='plbl'>&#128274; Security Controls</div>
      <div class='trow'>${secH}</div>
      <div class='plbl' style='margin-top:9px'>&#128736; Tech Stack</div>
      <div class='trow'>${stackH}</div>
    </div>`;
  document.getElementById('pnl').classList.add('open');
}

function closePanel(){
  document.getElementById('pnl').classList.remove('open');
  if(aid){const c=document.getElementById('card-'+aid);if(c){c.classList.remove('active');c.style.background='';};aid=null;}
}

function filterCards(q){
  q=q.toLowerCase().trim();
  document.querySelectorAll('.card').forEach(c=>{
    c.classList.toggle('dimmed',q&&!c.dataset.nm.includes(q));
  });
}

document.addEventListener('keydown',e=>{if(e.key==='Escape')closePanel();});"""

    html = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='UTF-8'>"
        "<style>" + _CSS + "</style></head><body>"
        "<div class='hdr'>"
        "<div class='htitle'>\U0001f3d7\ufe0f Interactive Solution Architecture "
        "<span class='hbadge'>" + pe + "</span></div>"
        "<div class='stats'>"
        "<div class='stat'><b>" + nc + "</b>Services</div>"
        "<div class='stat'><b>" + nf + "</b>Flow Steps</div>"
        "<div class='stat'><b>" + ns + "</b>Security</div>"
        "<div class='stat'><b>" + nt + "</b>Technologies</div>"
        "</div>"
        "<div class='srch'>\U0001f50d "
        "<input id='si' type='text' placeholder='Search\u2026' oninput='filterCards(this.value)'>"
        "</div></div>"
        "<div class='canvas'><div class='tier-row' id='tr'></div></div>"
        "<div class='fstrip' id='fs'></div>"
        "<div class='lgnd' id='lg'></div>"
        "<div class='panel' id='pnl'><div class='drag'></div>"
        "<div class='ph' id='ph'></div>"
        "<div class='pb' id='pb'></div></div>"
        "<script>"
        "const COMPS=" + cj + ";"
        "const TIERS=" + tj + ";"
        "const FLOWS=" + fj + ";"
        "const SEC="   + sj + ";"
        "const TECH="  + thj + ";"
        + _JS +
        "</script></body></html>"
    )
    st.components.v1.html(html, height=820, scrolling=True)

def _plotly_workflow(te: dict) -> None:
    """Project Workflow — layered Gantt bars (optimistic/likely/pessimistic) + milestone cards."""
    try:
        import plotly.graph_objects as _go
    except ImportError:
        st.warning("plotly not installed — run: pip install plotly")
        return

    phases = safe_list(te.get("phases"))
    if not phases:
        st.info("No phase data available. Run the pipeline first.")
        return

    PHASE_COLORS = ["#0078D4","#00B294","#5C2D91","#107C10","#D83B01","#E6A800","#00BCF2","#FF8C00"]
    total    = safe_int(te.get("total_hours", 0))
    dur      = safe_str(te.get("duration_weeks", ""))
    three_pt = safe_dict(te.get("three_point", {}))
    opt_tot  = safe_int(three_pt.get("optimistic",  int(total * 0.80))) or int(total * 0.80)
    pes_tot  = safe_int(three_pt.get("pessimistic", int(total * 1.35))) or int(total * 1.35)

    fig = _go.Figure()

    for i, ph in enumerate(phases):
        ph    = safe_dict(ph)
        name  = safe_str(ph.get("name", f"Phase {i+1}"))[:42]
        hrs   = safe_int(ph.get("hours", 0))
        low   = safe_int(ph.get("low_hours",  int(hrs * 0.82))) or hrs
        high  = safe_int(ph.get("high_hours", int(hrs * 1.35))) or hrs
        mid   = hrs or max(1, (low + high) // 2)
        tasks = safe_list(ph.get("tasks", []))
        color = PHASE_COLORS[i % len(PHASE_COLORS)]
        pct   = safe_str(ph.get("percentage", f"{int(hrs / max(total, 1) * 100)}%"))
        r_, g_, b_ = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        task_html  = "<br>".join(
            f"  ▸ {safe_str(safe_dict(t).get('name',''))[:48]}" for t in tasks[:6]
        )

        fig.add_trace(_go.Bar(
            name="Pessimistic", x=[high], y=[name], orientation="h", base=0,
            marker=dict(color=f"rgba({r_},{g_},{b_},0.10)", line=dict(color=color, width=1)),
            showlegend=(i == 0), legendgroup="pess",
            hovertemplate=f"<b>{name}</b><br>Pessimistic: <b>{high:,} hrs</b><extra></extra>",
        ))
        fig.add_trace(_go.Bar(
            name="Most Likely", x=[mid], y=[name], orientation="h", base=0,
            marker=dict(color=f"rgba({r_},{g_},{b_},0.85)", line=dict(color=color, width=1.5)),
            showlegend=(i == 0), legendgroup="likely",
            hovertemplate=(
                f"<b>{name}</b><br>Most Likely: <b>{mid:,} hrs</b> ({pct})<br>"
                f"Optimistic: {low:,}h  |  Pessimistic: {high:,}h<br>Tasks: {len(tasks)}"
                + (f"<br><br>{task_html}" if task_html else "")
                + "<extra></extra>"
            ),
        ))
        fig.add_trace(_go.Scatter(
            name="Optimistic", x=[low], y=[name], mode="markers",
            marker=dict(size=13, color=color, symbol="diamond",
                        line=dict(color="#0a0f1e", width=2)),
            showlegend=(i == 0), legendgroup="opt",
            hovertemplate=f"<b>{name}</b><br>Optimistic: <b>{low:,} hrs</b><extra></extra>",
        ))
        fig.add_annotation(
            x=mid + max(total * 0.012, 2), y=name,
            text=f"<b>{mid:,}h</b>  <span style='color:#64748b'>{pct}</span>",
            showarrow=False, font=dict(size=10, color="#e2e8f0"), xanchor="left",
        )

    fig.update_layout(
        title=dict(
            text=(f"📋  Project Workflow  <span style='font-size:13px;color:#64748b'>|  "
                  f"Total {total:,} hrs  |  {dur}  |  Range {opt_tot:,}–{pes_tot:,} hrs</span>"),
            font=dict(size=16, color="#e2e8f0"), x=0.02, xanchor="left",
        ),
        template="plotly_dark", paper_bgcolor="#0a0f1e", plot_bgcolor="#0f172a",
        barmode="overlay",
        height=max(440, len(phases) * 72 + 170),
        margin=dict(l=20, r=200, t=88, b=55),
        xaxis=dict(title=dict(text="Hours", font=dict(color="#64748b", size=11)),
                   gridcolor="#1e293b", gridwidth=1, tickfont=dict(color="#64748b"), zeroline=False),
        yaxis=dict(tickfont=dict(color="#e2e8f0", size=11), autorange="reversed", gridcolor="#1e293b"),
        legend=dict(bgcolor="rgba(15,23,42,0.9)", bordercolor="#334155", borderwidth=1,
                    font=dict(color="#94a3b8", size=10),
                    orientation="h", y=1.04, x=0.5, xanchor="center"),
        hoverlabel=dict(bgcolor="#1e293b", font_size=12, bordercolor="#334155"),
    )
    st.plotly_chart(fig, use_container_width=True)

    milestones = safe_list(te.get("milestones", []))
    if milestones:
        MS_COLORS = ["#0078D4","#00B294","#5C2D91","#107C10","#D83B01","#E6A800"]
        ms_html = ""
        for j, m in enumerate(milestones):
            m = safe_dict(m)
            c = MS_COLORS[j % len(MS_COLORS)]
            ms_html += (
                f'<div style="background:linear-gradient(135deg,#1e293b,#0f172a);'
                f'border:1px solid {c}44;border-top:3px solid {c};'
                f'border-radius:10px;padding:10px 14px;min-width:140px;flex:1">'
                f'<div style="font-size:.62rem;color:{c};font-weight:700;letter-spacing:1px">WEEK {safe_int(m.get("week"))}</div>'
                f'<div style="font-size:.82rem;color:#e2e8f0;font-weight:600;margin-top:4px">'
                f'{safe_str(m.get("name",""))[:30]}</div>'
                f'<div style="font-size:.7rem;color:#64748b;margin-top:3px">'
                f'{safe_str(m.get("description",""))[:55]}</div></div>'
            )
        st.markdown(
            f'<div style="margin-top:16px">'
            f'<div style="font-size:.68rem;color:#64748b;font-weight:600;letter-spacing:1px;margin-bottom:8px">MILESTONES</div>'
            f'<div style="display:flex;gap:10px;flex-wrap:wrap">{ms_html}</div></div>',
            unsafe_allow_html=True,
        )


def _plotly_dataflow(ar: dict) -> None:
    """Data Flow — rich Sankey with per-source colored links + numbered step strip."""
    try:
        import plotly.graph_objects as _go
    except ImportError:
        st.warning("plotly not installed")
        return

    data_flow = safe_list(ar.get("data_flow"))
    comps     = safe_list(ar.get("components"))

    TIER_DEFAULTS = [
        (["user","client","browser","external","person"],                        "👤 User / Client"),
        (["front door","cdn","apim","api management","api gateway"],             "🔌 API Gateway"),
        (["function","app service","backend","compute","container","logic app"], "⚙️ Application Layer"),
        (["openai","foundry","ai","search","cognitive","llm","gpt","claude"],    "🤖 AI & Cognitive"),
        (["sql","cosmos","blob","redis","storage","database"],                   "💾 Data & Storage"),
        (["teams","sharepoint","output","report","copilot","consumer"],          "📤 Output / Consumer"),
    ]
    NODE_COLORS = ["#0078D4","#00B294","#5C2D91","#107C10","#D83B01","#E6A800","#00BCF2","#FF8C00"]

    nodes = []
    if len(data_flow) >= 2:
        for item in data_flow:
            s = safe_str(item).strip()
            if s and s not in nodes:
                nodes.append(s)

    if len(nodes) < 3:
        comp_text = " ".join(
            safe_str(safe_dict(c).get("name","")) + " " + safe_str(safe_dict(c).get("azure_service",""))
            for c in comps
        ).lower()
        nodes = [
            lbl for kws, lbl in TIER_DEFAULTS
            if any(k in comp_text for k in kws) or lbl in ("👤 User / Client","📤 Output / Consumer")
        ]

    if len(nodes) < 3:
        nodes = [lbl for _, lbl in TIER_DEFAULTS]

    n = len(nodes)
    node_colors = [NODE_COLORS[i % len(NODE_COLORS)] for i in range(n)]
    links_src, links_tgt, links_val, links_color = [], [], [], []
    for i in range(n - 1):
        links_src.append(i); links_tgt.append(i + 1)
        links_val.append(max(20, 90 - i * 12))
        bc = node_colors[i]
        r_, g_, b_ = int(bc[1:3], 16), int(bc[3:5], 16), int(bc[5:7], 16)
        links_color.append(f"rgba({r_},{g_},{b_},0.35)")

    sec = safe_list(ar.get("security"))
    fig = _go.Figure(_go.Sankey(
        arrangement="snap",
        node=dict(
            pad=35, thickness=30,
            line=dict(color="rgba(255,255,255,0.08)", width=0.5),
            label=nodes, color=node_colors,
            hovertemplate="<b>%{label}</b><extra></extra>",
        ),
        link=dict(
            source=links_src, target=links_tgt, value=links_val, color=links_color,
            hovertemplate="<b>%{source.label}</b> → <b>%{target.label}</b><extra></extra>",
        ),
    ))
    fig.update_layout(
        title=dict(
            text=f"🔄  End-to-End Data Flow  |  {n} layers  |  🔒 {len(sec)} security controls",
            font=dict(size=15, color="#e2e8f0"), x=0.5,
        ),
        template="plotly_dark", paper_bgcolor="#0a0f1e",
        height=560, margin=dict(l=30, r=30, t=80, b=30),
        font=dict(color="#e2e8f0", size=12),
    )
    st.plotly_chart(fig, use_container_width=True)

    if len(data_flow) >= 2:
        step_colors = ["#0078D4","#00B294","#5C2D91","#107C10","#D83B01","#E6A800"]
        steps_html  = ""
        for j, step in enumerate(data_flow[:9]):
            c   = step_colors[j % len(step_colors)]
            arr = f'<span style="color:#334155;margin:0 5px;font-size:.9rem">→</span>' if j < len(data_flow) - 1 else ""
            steps_html += (
                f'<div style="display:flex;align-items:center">'
                f'<div style="background:linear-gradient(135deg,#1e293b,#0f172a);'
                f'border:1px solid {c}55;border-bottom:2px solid {c};'
                f'border-radius:8px;padding:7px 14px;font-size:.75rem;color:#e2e8f0;white-space:nowrap">'
                f'<span style="color:{c};font-weight:700;margin-right:6px">{j+1}.</span>'
                f'{safe_str(step)[:38]}</div>{arr}</div>'
            )
        st.markdown(
            f'<div style="margin-top:16px;padding:12px 14px;background:#0a0f1e;'
            f'border-radius:12px;border:1px solid #1e293b">'
            f'<div style="font-size:.68rem;color:#64748b;font-weight:600;letter-spacing:1px;margin-bottom:10px">FLOW STEPS</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:5px;align-items:center">{steps_html}</div></div>',
            unsafe_allow_html=True,
        )


def _plotly_infra_map(ce: dict) -> None:
    """Infrastructure Map — hero KPIs + sunburst + cost bar chart + breakdown table."""
    try:
        import plotly.graph_objects as _go
        import pandas as _pd
    except ImportError:
        st.warning("plotly not installed")
        return

    azure_costs = safe_list(safe_dict(ce).get("azure_costs"))
    if not azure_costs:
        st.info("No infrastructure cost data found. Run the pipeline first.")
        return

    GROUP_KWS = {
        "AI & Cognitive":      ["openai","foundry","ai","search","cognitive","llm","gpt","claude","embedding"],
        "Compute":             ["app service","function","container","kubernetes","compute","web app","aks"],
        "Data & Storage":      ["sql","cosmos","blob","storage","redis","cache","database","table"],
        "Security & Identity": ["key vault","entra","identity","ad","firewall","defender","sentinel"],
        "Integration":         ["service bus","logic app","event","teams","copilot","sharepoint","signalr","apim","api management"],
        "Monitoring & DevOps": ["monitor","insights","devops","log","pipeline","ci/cd"],
    }
    GRP_HEX = {
        "AI & Cognitive":"#5C2D91","Compute":"#0078D4","Data & Storage":"#107C10",
        "Security & Identity":"#D83B01","Integration":"#00B294",
        "Monitoring & DevOps":"#E6A800","Other":"#475569",
    }

    def get_grp(name):
        nl = safe_str(name).lower()
        for g, kws in GROUP_KWS.items():
            if any(k in nl for k in kws):
                return g
        return "Other"

    total = sum(safe_int(s.get("monthly_cost", s.get("cost", 0))) for s in [safe_dict(x) for x in azure_costs])
    grp_sums = {}
    sb_ids, sb_lbls, sb_pars, sb_vals, sb_cols, sb_hov = (
        ["Infrastructure"], ["Infrastructure"], [""],
        [total], ["rgba(10,15,30,0.95)"], ["<b>Azure Infrastructure</b>"],
    )

    for svc in azure_costs:
        svc  = safe_dict(svc)
        name = safe_str(svc.get("service", svc.get("name", "")))
        cost = max(1, safe_int(svc.get("monthly_cost", svc.get("cost", 0))))
        tier = safe_str(svc.get("tier", ""))
        desc = safe_str(svc.get("description", ""))[:80]
        grp  = get_grp(name)
        ghex = GRP_HEX.get(grp, "#475569")
        r_, g_, b_ = int(ghex[1:3], 16), int(ghex[3:5], 16), int(ghex[5:7], 16)
        if grp not in grp_sums:
            grp_sums[grp] = 0
            sb_ids.append(grp); sb_lbls.append(grp); sb_pars.append("Infrastructure")
            sb_vals.append(0); sb_cols.append(f"rgba({r_},{g_},{b_},1)")
            sb_hov.append(f"<b>{grp}</b>")
        grp_sums[grp] += cost
        sb_ids.append(name); sb_lbls.append(name); sb_pars.append(grp)
        sb_vals.append(cost); sb_cols.append(f"rgba({r_},{g_},{b_},0.72)")
        sb_hov.append(f"<b>{name}</b><br>Tier: {tier}<br><b>${cost:,}/mo</b>  |  ${cost*12:,}/yr<br>{desc}")

    for i, lbl in enumerate(sb_lbls):
        if lbl in grp_sums:
            sb_vals[i] = grp_sums[lbl]

    st.markdown(
        f'<div style="display:flex;gap:12px;margin-bottom:18px">'
        f'<div style="flex:1.2;background:linear-gradient(135deg,#0d2137,#0a0f1e);'
        f'border:1px solid #0078D444;border-radius:14px;padding:18px 22px">'
        f'<div style="font-size:.7rem;color:#64748b;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Monthly Cost — East US</div>'
        f'<div style="font-size:2.4rem;font-weight:800;color:#00d4aa;line-height:1">${total:,}</div>'
        f'<div style="font-size:.72rem;color:#64748b;margin-top:4px">Azure Pay-As-You-Go retail</div></div>'
        f'<div style="flex:1;background:linear-gradient(135deg,#1e293b,#0f172a);'
        f'border:1px solid #334155;border-radius:14px;padding:18px 22px">'
        f'<div style="font-size:.7rem;color:#64748b;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Annual Cost</div>'
        f'<div style="font-size:2.4rem;font-weight:800;color:#7b61ff;line-height:1">${total*12:,}</div>'
        f'<div style="font-size:.72rem;color:#64748b;margin-top:4px">12-month projection</div></div>'
        f'<div style="flex:1;background:linear-gradient(135deg,#1e293b,#0f172a);'
        f'border:1px solid #334155;border-radius:14px;padding:18px 22px">'
        f'<div style="font-size:.7rem;color:#64748b;margin-bottom:4px;text-transform:uppercase;letter-spacing:1px">Services</div>'
        f'<div style="font-size:2.4rem;font-weight:800;color:#e2e8f0;line-height:1">{len(azure_costs)}</div>'
        f'<div style="font-size:.72rem;color:#64748b;margin-top:4px">across {len(grp_sums)} categories</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    col_l, col_r = st.columns([1, 1])

    with col_l:
        fig_sb = _go.Figure(_go.Sunburst(
            ids=sb_ids, labels=sb_lbls, parents=sb_pars, values=sb_vals,
            customdata=sb_hov,
            hovertemplate="%{customdata}<extra></extra>",
            marker=dict(colors=sb_cols, line=dict(color="#0a0f1e", width=1.5)),
            texttemplate="<b>%{label}</b><br>$%{value:,}",
            textfont=dict(size=10, color="#ffffff"),
            branchvalues="total", maxdepth=2,
            insidetextorientation="radial",
        ))
        fig_sb.update_layout(
            title=dict(text="Cost by Category", font=dict(size=13, color="#94a3b8"), x=0.5),
            template="plotly_dark", paper_bgcolor="#0a0f1e",
            height=440, margin=dict(l=10, r=10, t=50, b=10),
        )
        st.plotly_chart(fig_sb, use_container_width=True)

    with col_r:
        rows_s = sorted([safe_dict(s) for s in azure_costs],
                        key=lambda x: safe_int(x.get("monthly_cost", x.get("cost", 0))), reverse=True)[:12]
        bnames = [safe_str(r.get("service", r.get("name", "")))[:30] for r in rows_s]
        bvals  = [safe_int(r.get("monthly_cost", r.get("cost", 0))) for r in rows_s]
        bclrs  = [GRP_HEX.get(get_grp(safe_str(r.get("service", r.get("name", "")))), "#475569") for r in rows_s]
        bhov   = [
            f"<b>{safe_str(r.get('service', r.get('name','')))}</b><br>"
            f"Tier: {safe_str(r.get('tier',''))}<br>"
            f"${safe_int(r.get('monthly_cost', r.get('cost',0))):,}/mo  |  "
            f"${safe_int(r.get('monthly_cost', r.get('cost',0)))*12:,}/yr<br>"
            f"{int(safe_int(r.get('monthly_cost', r.get('cost',0))) / max(total, 1) * 100)}% of budget"
            for r in rows_s
        ]
        fig_bar = _go.Figure(_go.Bar(
            x=bvals, y=bnames, orientation="h",
            marker=dict(color=bclrs, line=dict(color="#0a0f1e", width=1)),
            text=[f"${v:,}" for v in bvals], textposition="outside",
            textfont=dict(size=10, color="#94a3b8"),
            customdata=bhov,
            hovertemplate="%{customdata}<extra></extra>",
        ))
        fig_bar.update_layout(
            title=dict(text="Services by Monthly Cost", font=dict(size=13, color="#94a3b8"), x=0.5),
            template="plotly_dark", paper_bgcolor="#0a0f1e", plot_bgcolor="#0f172a",
            height=440, margin=dict(l=10, r=90, t=50, b=30),
            xaxis=dict(title="$/month", gridcolor="#1e293b", tickfont=dict(color="#64748b"),
                       tickprefix="$", zeroline=False),
            yaxis=dict(tickfont=dict(color="#e2e8f0"), autorange="reversed"),
            bargap=0.25,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with st.expander("📋 Full Service Breakdown — East US Pay-As-You-Go", expanded=False):
        all_rows = sorted([safe_dict(s) for s in azure_costs],
                          key=lambda x: safe_int(x.get("monthly_cost", x.get("cost", 0))), reverse=True)
        df = _pd.DataFrame([{
            "Service":   safe_str(r.get("service", r.get("name", ""))),
            "Category":  get_grp(safe_str(r.get("service", r.get("name", "")))),
            "Tier":      safe_str(r.get("tier", "")),
            "$/month":   f"${safe_int(r.get('monthly_cost', r.get('cost',0))):,}",
            "$/year":    f"${safe_int(r.get('monthly_cost', r.get('cost',0)))*12:,}",
            "% Budget":  f"{safe_int(r.get('monthly_cost', r.get('cost',0))) / max(total,1)*100:.1f}%",
            "Notes":     safe_str(r.get("description", ""))[:65],
        } for r in all_rows])
        st.dataframe(df, use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════════════════════════════
#  AI-POWERED ROI BUILDER & TRANSFORMATION JOURNEY (Claude-exclusive)
# ═══════════════════════════════════════════════════════════════════════

_ROI_TEASER_HTML = """<!DOCTYPE html><html><head><style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#05090f;font-family:'Segoe UI',system-ui,sans-serif;color:#e2e8f0;
  display:flex;align-items:center;justify-content:center;min-height:360px;
  background-image:radial-gradient(circle,rgba(20,160,185,0.1) 1px,transparent 1px);
  background-size:28px 28px}
.wrap{text-align:center;max-width:540px;padding:24px}
.icon{font-size:3.8rem;margin-bottom:18px;filter:drop-shadow(0 0 24px rgba(20,160,185,0.5))}
.title{font-size:1.35rem;font-weight:800;color:#e2e8f0;margin-bottom:10px}
.desc{font-size:.82rem;color:#64748b;line-height:1.75}
.pills{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-top:20px}
.pill{font-size:.7rem;font-weight:600;padding:5px 14px;border-radius:20px;
  border:1px solid rgba(20,160,185,0.3);color:#14A0B9;background:rgba(20,160,185,0.08)}
</style></head><body><div class="wrap">
<div class="icon">💰</div>
<div class="title">ROI &amp; Business Case Builder</div>
<div class="desc">Click "Generate with AI Agent" to create a fully interactive ROI calculator
with live sliders, animated charts, and 3-year financial projections — seeded from your proposal data.</div>
<div class="pills">
  <div class="pill">📊 Live Sliders</div>
  <div class="pill">💹 3-Year Projection</div>
  <div class="pill">⚡ Instant Recalc</div>
  <div class="pill">📥 Downloadable</div>
</div></div></body></html>"""

_JOURNEY_TEASER_HTML = """<!DOCTYPE html><html><head><style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:#05090f;font-family:'Segoe UI',system-ui,sans-serif;color:#e2e8f0;
  display:flex;align-items:center;justify-content:center;min-height:360px;
  background-image:radial-gradient(circle,rgba(148,193,28,0.08) 1px,transparent 1px);
  background-size:28px 28px}
.wrap{text-align:center;max-width:540px;padding:24px}
.icon{font-size:3.8rem;margin-bottom:18px;filter:drop-shadow(0 0 24px rgba(148,193,28,0.45))}
.title{font-size:1.35rem;font-weight:800;color:#e2e8f0;margin-bottom:10px}
.desc{font-size:.82rem;color:#64748b;line-height:1.75}
.pills{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-top:20px}
.pill{font-size:.7rem;font-weight:600;padding:5px 14px;border-radius:20px;
  border:1px solid rgba(148,193,28,0.3);color:#94C11C;background:rgba(148,193,28,0.08)}
</style></head><body><div class="wrap">
<div class="icon">🚀</div>
<div class="title">Client Transformation Journey</div>
<div class="desc">Click "Generate with AI Agent" to create a visual transformation roadmap —
where the client is today vs. Go-Live vs. 1 year post-implementation,
with specific KPI improvements per phase.</div>
<div class="pills">
  <div class="pill">🗓 Phase Timeline</div>
  <div class="pill">📈 KPI Improvements</div>
  <div class="pill">🎯 Before vs After</div>
  <div class="pill">✨ Animated</div>
</div></div></body></html>"""


def _roi_loading_html() -> str:
    return (
        '<div style="background:linear-gradient(135deg,#051a2e,#0a2540);'
        'border:3px solid #14A0B9;border-radius:16px;padding:44px;text-align:center;'
        'font-family:Segoe UI,system-ui,sans-serif;'
        'box-shadow:0 0 50px rgba(20,160,185,.7),0 0 100px rgba(20,160,185,.3),inset 0 0 60px rgba(20,160,185,.05)">'
        '<div style="display:inline-block;width:58px;height:58px;border-radius:50%;'
        'border:4px solid rgba(20,160,185,.3);border-top:4px solid #14A0B9;border-right:4px solid #94C11C;'
        'animation:ldSpin .75s linear infinite;margin-bottom:18px"></div>'
        '<div style="font-size:1.15rem;font-weight:800;color:#ffffff;margin-bottom:8px;'
        'text-shadow:0 0 20px rgba(20,160,185,.8)">💰 Building Your ROI Model...</div>'
        '<div style="font-size:.8rem;color:#7dd3e8;margin-bottom:26px">AI Agent is calculating financial projections &amp; building interactive charts</div>'
        '<div style="display:flex;flex-direction:column;gap:9px;max-width:400px;margin:0 auto">'
        '<div style="padding:10px 15px;background:rgba(20,160,185,.18);border:1px solid #14A0B9;border-radius:8px;text-align:left">'
        '<span style="font-size:.75rem;color:#38bdf8;font-weight:700">● ANALYZING</span>'
        '<span style="font-size:.75rem;color:#bae6fd;margin-left:10px">Project cost &amp; effort data</span></div>'
        '<div style="padding:10px 15px;background:rgba(148,193,28,.15);border:1px solid #94C11C;border-radius:8px;text-align:left">'
        '<span style="font-size:.75rem;color:#a3e635;font-weight:700;animation:ldPulse .9s infinite">● COMPUTING</span>'
        '<span style="font-size:.75rem;color:#d9f99d;margin-left:10px">ROI, payback period &amp; 3-year projections</span></div>'
        '<div style="padding:10px 15px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.25);border-radius:8px;text-align:left">'
        '<span style="font-size:.75rem;color:rgba(255,255,255,.6);font-weight:700">○ BUILDING</span>'
        '<span style="font-size:.75rem;color:rgba(255,255,255,.5);margin-left:10px">Interactive sliders &amp; animated charts</span></div>'
        '</div>'
        '<div style="margin-top:20px;font-size:.72rem;color:#7dd3e8">⏱ Up to 90 seconds · Do not close this tab</div>'
        '<style>@keyframes ldSpin{to{transform:rotate(360deg)}}'
        '@keyframes ldPulse{0%,100%{opacity:.5}50%{opacity:1}}</style></div>'
    )


def _journey_loading_html() -> str:
    return (
        '<div style="background:linear-gradient(135deg,#0d2a05,#0a2010);'
        'border:3px solid #94C11C;border-radius:16px;padding:44px;text-align:center;'
        'font-family:Segoe UI,system-ui,sans-serif;'
        'box-shadow:0 0 50px rgba(148,193,28,.7),0 0 100px rgba(148,193,28,.3),inset 0 0 60px rgba(148,193,28,.05)">'
        '<div style="display:inline-block;width:58px;height:58px;border-radius:50%;'
        'border:4px solid rgba(148,193,28,.3);border-top:4px solid #94C11C;border-right:4px solid #14A0B9;'
        'animation:ldSpin .75s linear infinite;margin-bottom:18px"></div>'
        '<div style="font-size:1.15rem;font-weight:800;color:#ffffff;margin-bottom:8px;'
        'text-shadow:0 0 20px rgba(148,193,28,.8)">🚀 Mapping Transformation Journey...</div>'
        '<div style="font-size:.8rem;color:#bef264;margin-bottom:26px">AI Agent is building your client\'s before/after story with KPI improvements</div>'
        '<div style="display:flex;flex-direction:column;gap:9px;max-width:400px;margin:0 auto">'
        '<div style="padding:10px 15px;background:rgba(148,193,28,.18);border:1px solid #94C11C;border-radius:8px;text-align:left">'
        '<span style="font-size:.75rem;color:#a3e635;font-weight:700">● ANALYZING</span>'
        '<span style="font-size:.75rem;color:#d9f99d;margin-left:10px">Project phases &amp; deliverables</span></div>'
        '<div style="padding:10px 15px;background:rgba(20,160,185,.15);border:1px solid #14A0B9;border-radius:8px;text-align:left">'
        '<span style="font-size:.75rem;color:#38bdf8;font-weight:700;animation:ldPulse .9s infinite">● CRAFTING</span>'
        '<span style="font-size:.75rem;color:#bae6fd;margin-left:10px">Before/after KPI comparisons per phase</span></div>'
        '<div style="padding:10px 15px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.25);border-radius:8px;text-align:left">'
        '<span style="font-size:.75rem;color:rgba(255,255,255,.6);font-weight:700">○ BUILDING</span>'
        '<span style="font-size:.75rem;color:rgba(255,255,255,.5);margin-left:10px">Animated timeline &amp; milestone cards</span></div>'
        '</div>'
        '<div style="margin-top:20px;font-size:.72rem;color:#bef264">⏱ Up to 2 minutes · Do not close this tab</div>'
        '<style>@keyframes ldSpin{to{transform:rotate(360deg)}}'
        '@keyframes ldPulse{0%,100%{opacity:.5}50%{opacity:1}}</style></div>'
    )


def _generate_roi_html(ant, se: dict, te: dict, ce: dict) -> "str | None":
    """Call Claude to generate the interactive ROI & Business Case HTML page."""
    client  = safe_str(se.get("client_name", "Client"))
    project = safe_str(se.get("project_type", "Solution"))
    hours   = safe_int(te.get("total_hours", 1000))
    weeks   = safe_str(te.get("duration_weeks", "16"))
    monthly = safe_int(safe_dict(ce).get("total_monthly_cost", 5000))
    phases  = safe_list(te.get("phases", []))
    tech    = safe_list(se.get("technology_stack", []))
    cplx    = safe_int(se.get("complexity_score", 5))

    phase_s = "; ".join(
        f"{safe_str(safe_dict(p).get('name',''))} ({safe_int(safe_dict(p).get('hours',0))}h)"
        for p in phases[:6]
    )
    def_team  = max(5, min(30, safe_int(se.get("team_size", 12))))
    def_rate  = 140 if cplx >= 7 else 100
    def_saved = 10 if any(k in project.lower() for k in ["ai","automat","ml"]) else 6
    def_lift  = 28 if any(k in project.lower() for k in ["ai","automat","ml"]) else 18

    SYSTEM = (
        "You are a world-class frontend engineer and financial analyst. "
        "Generate a complete, self-contained HTML/CSS/JS page: an interactive ROI & Business Case calculator. "
        "DESIGN: dark background #05090f, glassmorphism cards (rgba(255,255,255,0.04) + backdrop-filter:blur(12px)), "
        "ECI brand colors teal #14A0B9 and lime #94C11C. Dot-grid body background via radial-gradient. "
        "Animated shimmer gradient accent bar. No external URLs. "
        "\n\nPAGE STRUCTURE (all required):\n"
        "1. HEADER: dark gradient bar, project title left, pills right (duration, hours, AI Agent tag).\n"
        "2. HERO METRICS ROW: 4 glassmorphism cards side by side. "
        "   IDs: val-invest (Total Investment), val-savings (Annual Benefit), val-roi (3-Yr ROI %), val-payback (Payback). "
        "   Numbers animate from 0 on DOMContentLoaded with requestAnimationFrame easing.\n"
        "3. TWO-COLUMN GRID: "
        "   LEFT PANEL = 4 range sliders with live labels: Team Size (2-50), Avg Hourly Rate $30-$300, "
        "   Hours Saved/Person/Week (1-30), AI Productivity Lift % (5-60). "
        "   Each slider has custom CSS thumb (teal→lime gradient, glow shadow) and fills track color via --pct CSS var. "
        "   RIGHT PANEL = 3-Year Financial Projection animated bar chart. "
        "   3 groups (Year 1, Year 2, Year 3), each with 3 bars: Cost (red rgba 214,51,1), "
        "   Benefit (lime gradient), Net Value (teal gradient, turns red if negative). "
        "   Bar IDs: bar-c1/bar-b1/bar-n1, bar-c2/bar-b2/bar-n2, bar-c3/bar-b3/bar-n3. "
        "   Net value labels: bv-n1/bv-n2/bv-n3. Bars transition height with cubic-bezier spring.\n"
        "4. INVESTMENT BREAKDOWN GRID (2 cols × 3 rows, 6 cards): "
        "   Dev Investment, Annual Infra Cost, Hours Saved/Year, Productivity Gain Value, 3-Year Net Value, Payback Progress Bar.\n"
        "5. CALCULATIONS (JS): "
        "   investDev = TOTAL_HOURS * S.rate; investInfra = MONTHLY_INFRA * 12; totalInvest = investDev + investInfra; "
        "   annualHrs = S.team * S.saved * 52; hrVal = annualHrs * S.rate; "
        "   prodVal = S.team * 2000 * S.rate * (S.lift/100) * 0.25; annualBenefit = hrVal + prodVal; "
        "   roi3 = ((annualBenefit*3 - totalInvest) / totalInvest) * 100; "
        "   payback = totalInvest / (annualBenefit/12). "
        "   Recalc fires on every slider input. "
        "Return ONLY the complete HTML page, no markdown fences."
    )

    USER = (
        f"PROJECT:\n"
        f"  Client: {client}\n"
        f"  Type: {project}\n"
        f"  Total Dev Hours: {hours:,}\n"
        f"  Duration: {weeks} weeks\n"
        f"  Monthly Azure Cost: ${monthly:,}\n"
        f"  Tech: {', '.join(safe_str(t) for t in tech[:8])}\n"
        f"  Phases: {phase_s}\n\n"
        f"JS CONSTANTS:\n"
        f"  const TOTAL_HOURS = {hours};\n"
        f"  const MONTHLY_INFRA = {monthly};\n\n"
        f"DEFAULT SLIDER VALUES:\n"
        f"  S.team = {def_team}\n"
        f"  S.rate = {def_rate}\n"
        f"  S.saved = {def_saved}\n"
        f"  S.lift = {def_lift}\n\n"
        f"Generate the complete interactive ROI HTML page now. "
        f"Make it beautiful, cinematic, and data-accurate. "
        f"Use '{client}' as project name in the header."
    )

    try:
        raw = ant._make_request(SYSTEM, USER, max_tokens=14000, timeout=300)
        if not raw:
            return None
        html = raw.strip()
        for fence in ["```html", "```"]:
            if fence in html:
                html = html.split(fence, 1)[1].split("```")[0].strip()
                break
        if not html.lower().startswith("<!"):
            for tag in ["<!doctype", "<html"]:
                idx = html.lower().find(tag)
                if idx >= 0:
                    html = html[idx:]
                    break
        return html if len(html) > 800 else None
    except Exception as _e:
        st.error(f"AI Agent error generating ROI model: {_e}")
        return None


def _generate_journey_html(ant, se: dict, te: dict, ar: dict) -> "str | None":
    """Call Claude to generate the Client Transformation Journey HTML page."""
    client  = safe_str(se.get("client_name", "Client"))
    project = safe_str(se.get("project_type", "Solution"))
    weeks   = safe_str(te.get("duration_weeks", "16"))
    hours   = safe_int(te.get("total_hours", 1000))
    phases  = safe_list(te.get("phases", []))
    tech    = safe_list(se.get("technology_stack", []))
    comps   = safe_list(ar.get("components", []))
    pain    = safe_list(se.get("pain_points", []))

    phase_s = "; ".join(
        safe_str(safe_dict(p).get("name", "")) + ": " +
        ", ".join(
            safe_str(safe_dict(t).get("name", t) if isinstance(t, dict) else t)
            for t in safe_list(safe_dict(p).get("tasks", []))[:3]
        )
        for p in phases[:5]
    )
    comp_s  = ", ".join(safe_str(safe_dict(c).get("name", "")) for c in comps[:8])
    pain_s  = "; ".join(safe_str(p) for p in pain[:5]) or "Manual processes, inefficiency, lack of AI capabilities"

    SYSTEM = (
        "You are a world-class frontend engineer and business transformation consultant. "
        "Generate a complete, self-contained HTML/CSS/JS page: a stunning Client Transformation Journey visualization. "
        "DESIGN: background #05090f, glassmorphism cards, teal #14A0B9, lime #94C11C, navy #161E56. "
        "Dot-grid background. Animated shimmer accent bar. No external URLs. "
        "\n\nPAGE STRUCTURE (all required):\n"
        "1. HEADER: gradient bar, client name + project title, duration pill, 'AI Agent' badge.\n"
        "2. ANIMATED ACCENT BAR: shimmer gradient.\n"
        "3. HORIZONTAL TIMELINE: 4 milestone nodes on a horizontal progress line. "
        "   TODAY (gray/slate) → GO-LIVE (teal, ~duration weeks) → 3 MONTHS POST (teal+lime) → 1 YEAR POST (lime). "
        "   Each node: large colored circle with emoji icon, date label below, status badge. "
        "   Connecting line fills from left to right with a gradient. "
        "   Nodes fade in with staggered animation (0ms, 150ms, 300ms, 450ms delays).\n"
        "4. PHASE CARDS GRID below timeline — 4 glassmorphism cards (one per milestone). "
        "   Each card: colored top border, milestone name + icon, 3-4 specific bullet outcomes, "
        "   2-3 KPI chips (before→after format, e.g. '3 days → 4 hrs'). "
        "   Cards slide up with staggered animation. KPI numbers animate on intersection.\n"
        "5. BEFORE vs AFTER COMPARISON SECTION: "
        "   Section title, then 5-6 metric rows in a clean grid. "
        "   Each row: metric name + icon, BEFORE value (red/gray chip), animated progress bar (gray→lime), AFTER value (lime chip). "
        "   Progress bars animate width 0→final on page load with delay. "
        "   Metrics: manual processing time, error/rework rate, report generation time, "
        "   decision speed, user productivity, cost per transaction.\n"
        "6. SUCCESS INDICATORS ROW: 3 glass cards at bottom with big icon, bold headline, short tagline. "
        "   Theme: Efficiency Unlocked, Intelligence Embedded, Growth Enabled.\n"
        "7. ALL ANIMATIONS: use CSS @keyframes + JS setTimeout/IntersectionObserver. "
        "Return ONLY the complete HTML page, no markdown fences."
    )

    USER = (
        f"PROJECT DATA:\n"
        f"  Client: {client}\n"
        f"  Project Type: {project}\n"
        f"  Duration to Go-Live: {weeks} weeks\n"
        f"  Total Dev Hours: {hours:,}\n"
        f"  Technology: {', '.join(safe_str(t) for t in tech[:8])}\n"
        f"  Key Components: {comp_s}\n"
        f"  Current Pain Points: {pain_s}\n"
        f"  Phases: {phase_s}\n\n"
        f"CONTENT REQUIREMENTS:\n"
        f"1. TODAY card: describe {client}'s current painful state — specific to their pain points above.\n"
        f"2. GO-LIVE card: foundation delivered — what the system does on day 1.\n"
        f"3. 3 MONTHS card: team is productive, early ROI visible — specific gains.\n"
        f"4. 1 YEAR card: full transformation realized — quantified outcomes.\n"
        f"5. KPI comparisons must be CONCRETE and credible, not generic "
        f"   (e.g. 'Invoice processing: 3.5 days → 2 hours' not 'Process: slow → fast').\n"
        f"6. Use '{client}' by name in cards and header.\n\n"
        f"Generate the complete, beautiful, animated Transformation Journey HTML page now."
    )

    try:
        raw = ant._make_request(SYSTEM, USER, max_tokens=16000, timeout=330)
        if not raw:
            return None
        html = raw.strip()
        for fence in ["```html", "```"]:
            if fence in html:
                html = html.split(fence, 1)[1].split("```")[0].strip()
                break
        if not html.lower().startswith("<!"):
            for tag in ["<!doctype", "<html"]:
                idx = html.lower().find(tag)
                if idx >= 0:
                    html = html[idx:]
                    break
        return html if len(html) > 800 else None
    except Exception as _e:
        st.error(f"AI Agent error generating Journey map: {_e}")
        return None


def _render_roi_builder(se: dict, te: dict, ce: dict) -> None:
    """Render the AI-powered ROI & Business Case Builder tab."""
    import hashlib as _hl, json as _js
    _key = "roi_builder_" + _hl.md5(
        _js.dumps([se, te, ce], sort_keys=True, default=str).encode()
    ).hexdigest()[:10]
    cached = st.session_state.get(_key)
    client = safe_str(se.get("client_name", "Client"))

    st.markdown(
        f'<div style="background:linear-gradient(135deg,rgba(20,160,185,.10),rgba(148,193,28,.06));'
        f'border:1px solid rgba(20,160,185,.25);border-radius:14px;padding:16px 20px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:12px">'
        f'<span style="font-size:2rem">💰</span>'
        f'<div><div style="font-size:.95rem;font-weight:700;color:#e2e8f0">ROI &amp; Business Case Builder</div>'
        f'<div style="font-size:.76rem;color:#94a3b8;margin-top:2px">Interactive financial model with live sliders '
        f'&amp; 3-year projections for <b style="color:#14A0B9">{client}</b></div></div>'
        f'<span style="margin-left:auto;font-size:.7rem;color:#94C11C;font-weight:700;'
        f'background:rgba(148,193,28,.1);padding:4px 11px;border-radius:20px;white-space:nowrap">⚡ AI Agent</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    if cached:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            from datetime import datetime as _dt
            st.download_button(
                "📥 Download ROI Model (HTML)",
                data=cached.encode("utf-8"),
                file_name=f"ROI_{client.replace(' ', '_')}_{_dt.now().strftime('%Y%m%d')}.html",
                mime="text/html", use_container_width=True, key="dl_roi_html",
            )
        with c2:
            if st.button("🔄 Reset", key="roi_rst", use_container_width=True):
                st.session_state.pop(_key, None)
                st.rerun()
        with c3:
            gen_clicked = st.button("✨ Regen", key="roi_regen", use_container_width=True, type="primary")
        st.components.v1.html(cached, height=990, scrolling=True)
    else:
        gen_clicked = st.button(
            "✨ Generate ROI & Business Case with AI Agent",
            key="roi_gen", type="primary", use_container_width=True,
        )
        st.components.v1.html(_ROI_TEASER_HTML, height=375, scrolling=False)

    if gen_clicked:
        try:
            st.toast("💰 AI Agent is building your ROI model...", icon="📊")
        except Exception:
            pass
        _slot = st.empty()
        _slot.markdown(_roi_loading_html(), unsafe_allow_html=True)
        from .ai_clients import AnthropicAI as _Ant
        _ant = _Ant.from_session()
        if not _ant.is_live:
            _slot.empty()
            st.error("No Anthropic API key configured. Add it in Settings → AI Clients.")
            return
        _html = _generate_roi_html(_ant, se, te, ce)
        _slot.empty()
        if _html:
            st.session_state[_key] = _html
            st.rerun()
        else:
            st.error("AI Agent could not generate the ROI model. Please try again.")


def _render_transformation_journey(se: dict, te: dict, ar: dict) -> None:
    """Render the AI-powered Client Transformation Journey tab."""
    import hashlib as _hl, json as _js
    _key = "journey_" + _hl.md5(
        _js.dumps([se, te, ar], sort_keys=True, default=str).encode()
    ).hexdigest()[:10]
    cached = st.session_state.get(_key)
    client = safe_str(se.get("client_name", "Client"))

    st.markdown(
        f'<div style="background:linear-gradient(135deg,rgba(148,193,28,.10),rgba(20,160,185,.06));'
        f'border:1px solid rgba(148,193,28,.25);border-radius:14px;padding:16px 20px;margin-bottom:12px">'
        f'<div style="display:flex;align-items:center;gap:12px">'
        f'<span style="font-size:2rem">🚀</span>'
        f'<div><div style="font-size:.95rem;font-weight:700;color:#e2e8f0">Client Transformation Journey</div>'
        f'<div style="font-size:.76rem;color:#94a3b8;margin-top:2px">Visual before/after roadmap — where '
        f'<b style="color:#94C11C">{client}</b> is today vs. go-live vs. 1 year post-implementation</div></div>'
        f'<span style="margin-left:auto;font-size:.7rem;color:#94C11C;font-weight:700;'
        f'background:rgba(148,193,28,.1);padding:4px 11px;border-radius:20px;white-space:nowrap">⚡ AI Agent</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    if cached:
        c1, c2, c3 = st.columns([3, 1, 1])
        with c1:
            from datetime import datetime as _dt
            st.download_button(
                "📥 Download Journey Map (HTML)",
                data=cached.encode("utf-8"),
                file_name=f"Journey_{client.replace(' ', '_')}_{_dt.now().strftime('%Y%m%d')}.html",
                mime="text/html", use_container_width=True, key="dl_journey_html",
            )
        with c2:
            if st.button("🔄 Reset", key="jrn_rst", use_container_width=True):
                st.session_state.pop(_key, None)
                st.rerun()
        with c3:
            gen_clicked = st.button("✨ Regen", key="jrn_regen", use_container_width=True, type="primary")
        st.components.v1.html(cached, height=1060, scrolling=True)
    else:
        gen_clicked = st.button(
            "✨ Generate Transformation Journey with AI Agent",
            key="jrn_gen", type="primary", use_container_width=True,
        )
        st.components.v1.html(_JOURNEY_TEASER_HTML, height=375, scrolling=False)

    if gen_clicked:
        try:
            st.toast("🚀 AI Agent is mapping the transformation journey...", icon="✨")
        except Exception:
            pass
        _slot = st.empty()
        _slot.markdown(_journey_loading_html(), unsafe_allow_html=True)
        from .ai_clients import AnthropicAI as _Ant
        _ant = _Ant.from_session()
        if not _ant.is_live:
            _slot.empty()
            st.error("No Anthropic API key configured. Add it in Settings → AI Clients.")
            return
        _html = _generate_journey_html(_ant, se, te, ar)
        _slot.empty()
        if _html:
            st.session_state[_key] = _html
            st.rerun()
        else:
            st.error("AI Agent could not generate the Journey map. Please try again.")


def _plotly_security(ar: dict) -> None:
    """Security Layers — security gauge + domain progress bars + radar + controls grid."""
    try:
        import plotly.graph_objects as _go
    except ImportError:
        st.warning("plotly not installed")
        return

    security_items = safe_list(ar.get("security"))

    DOMAINS = [
        "Identity & Access", "Network Security", "Data Protection",
        "Threat Detection", "Compliance & Audit", "Operational Security",
    ]
    DOMAIN_KWS = {
        "Identity & Access":    ["identity","entra","ad","mfa","sso","rbac","auth","managed identity","conditional access"],
        "Network Security":     ["network","firewall","waf","ddos","private","vnet","nsg","endpoint","front door","tls"],
        "Data Protection":      ["encrypt","key vault","tls","ssl","data","backup","rest","bcdr","cmk"],
        "Threat Detection":     ["sentinel","defender","monitor","alert","threat","siem","detect","scan"],
        "Compliance & Audit":   ["audit","log","compliance","gdpr","soc","policy","governance","logging","diagnostic"],
        "Operational Security": ["devops","pipeline","scan","secret","rotation","patch","update","ci/cd"],
    }
    DOMAIN_ICONS  = {"Identity & Access":"👤","Network Security":"🛡️","Data Protection":"🔐",
                     "Threat Detection":"🔍","Compliance & Audit":"📋","Operational Security":"🚀"}
    DOMAIN_COLORS = {"Identity & Access":"#0078D4","Network Security":"#D83B01",
                     "Data Protection":"#00B294","Threat Detection":"#5C2D91",
                     "Compliance & Audit":"#E6A800","Operational Security":"#107C10"}

    def score(d):
        kws = DOMAIN_KWS.get(d, [])
        return min(5, sum(1 for item in security_items if any(k in safe_str(item).lower() for k in kws)) + 2)

    scores  = [score(d) for d in DOMAINS]
    overall = sum(scores) / (len(DOMAINS) * 5) * 100

    col_left, col_right = st.columns([1, 2])

    with col_left:
        fig_g = _go.Figure(_go.Indicator(
            mode="gauge+number",
            value=overall,
            number=dict(suffix="%", font=dict(size=40, color="#e2e8f0"), valueformat=".0f"),
            title=dict(text="Security Coverage", font=dict(size=13, color="#94a3b8")),
            gauge=dict(
                axis=dict(range=[0,100], tickfont=dict(color="#64748b", size=9), tickcolor="#334155"),
                bar=dict(color="#0078D4", thickness=0.28),
                bgcolor="#0f172a", bordercolor="#334155",
                steps=[
                    dict(range=[0,40],   color="rgba(216,59,1,0.12)"),
                    dict(range=[40,70],  color="rgba(230,168,0,0.12)"),
                    dict(range=[70,100], color="rgba(16,124,16,0.12)"),
                ],
                threshold=dict(line=dict(color="#00d4aa", width=3), thickness=0.8, value=80),
            ),
        ))
        fig_g.update_layout(
            template="plotly_dark", paper_bgcolor="#0a0f1e",
            height=260, margin=dict(l=20, r=20, t=60, b=10),
        )
        st.plotly_chart(fig_g, use_container_width=True)

        for d, s in zip(DOMAINS, scores):
            c    = DOMAIN_COLORS.get(d, "#0078D4")
            icon = DOMAIN_ICONS.get(d, "🔒")
            pct  = int(s / 5 * 100)
            r_, g_, b_ = int(c[1:3],16), int(c[3:5],16), int(c[5:7],16)
            lc   = "#E6A800" if pct < 60 else ("#107C10" if pct >= 80 else c)
            st.markdown(
                f'<div style="margin:5px 0;background:#0f172a;border-radius:8px;padding:7px 10px;">'
                f'<div style="display:flex;justify-content:space-between;margin-bottom:5px">'
                f'<span style="font-size:.72rem;color:#94a3b8">{icon} {d}</span>'
                f'<span style="font-size:.72rem;color:{lc};font-weight:700">{s}/5</span></div>'
                f'<div style="background:#1e293b;border-radius:4px;height:6px">'
                f'<div style="background:linear-gradient(90deg,rgba({r_},{g_},{b_},0.9),rgba({r_},{g_},{b_},0.6));'
                f'width:{pct}%;height:6px;border-radius:4px"></div></div></div>',
                unsafe_allow_html=True,
            )

    with col_right:
        mrkr_colors = [DOMAIN_COLORS.get(d, "#0078D4") for d in DOMAINS + [DOMAINS[0]]]
        fig_r = _go.Figure()
        fig_r.add_trace(_go.Scatterpolar(
            r=[5]*len(DOMAINS)+[5], theta=DOMAINS+[DOMAINS[0]],
            fill="toself", fillcolor="rgba(255,255,255,0.03)",
            line=dict(color="#2d3748", width=1.5, dash="dot"),
            name="Best Practice (5/5)", hoverinfo="skip",
        ))
        fig_r.add_trace(_go.Scatterpolar(
            r=[3]*len(DOMAINS)+[3], theta=DOMAINS+[DOMAINS[0]],
            fill="toself", fillcolor="rgba(230,168,0,0.04)",
            line=dict(color="#E6A800", width=1, dash="dash"),
            name="Minimum Viable (3/5)", hoverinfo="skip",
        ))
        fig_r.add_trace(_go.Scatterpolar(
            r=scores+[scores[0]], theta=DOMAINS+[DOMAINS[0]],
            fill="toself", fillcolor="rgba(0,120,212,0.18)",
            line=dict(color="#0078D4", width=3),
            marker=dict(size=13, color=mrkr_colors, line=dict(color="#0a0f1e", width=2)),
            name="Architecture Coverage",
            hovertemplate="<b>%{theta}</b><br>Score: <b>%{r}/5</b><extra></extra>",
        ))
        fig_r.update_layout(
            title=dict(
                text=f"🔒  Security Domain Coverage  |  Overall: {overall:.0f}%",
                font=dict(size=14, color="#e2e8f0"), x=0.5,
            ),
            polar=dict(
                bgcolor="#0a0f1e",
                radialaxis=dict(
                    visible=True, range=[0,5], tickvals=[1,2,3,4,5],
                    ticktext=["Min","Basic","Fair","Good","Best"],
                    tickfont=dict(color="#64748b", size=8),
                    gridcolor="#1e293b", linecolor="#1e293b",
                ),
                angularaxis=dict(
                    tickfont=dict(color="#e2e8f0", size=11),
                    gridcolor="#1e293b", linecolor="#334155",
                    rotation=90, direction="clockwise",
                ),
            ),
            template="plotly_dark", paper_bgcolor="#0a0f1e",
            height=460, margin=dict(l=80, r=80, t=70, b=30),
            legend=dict(bgcolor="rgba(15,23,42,0.9)", bordercolor="#334155", borderwidth=1,
                        font=dict(color="#94a3b8", size=9),
                        x=0.5, y=-0.08, xanchor="center", orientation="h"),
        )
        st.plotly_chart(fig_r, use_container_width=True)

    if security_items:
        st.markdown(
            '<div style="font-size:.68rem;color:#64748b;font-weight:600;letter-spacing:1px;'
            'margin-top:18px;margin-bottom:10px">SECURITY CONTROLS IN SCOPE</div>',
            unsafe_allow_html=True,
        )
        cols3 = st.columns(3)
        for i, item in enumerate(security_items):
            item_l = safe_str(item).lower()
            ctrl_c = "#0078D4"
            for d, kws in DOMAIN_KWS.items():
                if any(k in item_l for k in kws):
                    ctrl_c = DOMAIN_COLORS.get(d, "#0078D4")
                    break
            with cols3[i % 3]:
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,#1e293b,#0f172a);'
                    f'border:1px solid {ctrl_c}33;border-left:3px solid {ctrl_c};'
                    f'border-radius:0 8px 8px 0;padding:8px 12px;margin:3px 0">'
                    f'<div style="font-size:.78rem;color:#e2e8f0">{safe_str(item)}</div></div>',
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            '<div style="background:#1e293b;border:1px solid #334155;border-radius:10px;'
            'padding:20px;text-align:center;color:#64748b;font-size:.85rem">'
            '⚠️  No explicit security controls found. Recommended: Key Vault, Entra ID, WAF, '
            'Azure Monitor, Defender for Cloud, Private Endpoints.</div>',
            unsafe_allow_html=True,
        )


_VISION_LOADER_HTML = (
    '<!DOCTYPE html><html><head><meta charset="utf-8"><style>'
    '*{margin:0;padding:0;box-sizing:border-box}'
    'body{background:transparent;font-family:"Segoe UI",sans-serif;padding:8px}'
    '@keyframes spin{to{transform:rotate(360deg)}}'
    '@keyframes pulse{0%,100%{opacity:.35;transform:scale(.96)}50%{opacity:1;transform:scale(1.02)}}'
    '@keyframes bar{0%{width:2%}100%{width:96%}}'
    '@keyframes fade{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}'
    '@keyframes dotpulse{0%,80%,100%{opacity:.2;transform:scale(.8)}40%{opacity:1;transform:scale(1)}}'
    '@keyframes shimmer{0%{background-position:-400px 0}100%{background-position:400px 0}}'
    '.wrap{background:linear-gradient(135deg,#0d1435 0%,#0a2040 50%,#0d1435 100%);'
    'border:2px solid #7b61ff;border-radius:18px;padding:36px 32px;text-align:center;'
    'animation:fade .35s ease;box-shadow:0 0 80px rgba(123,97,255,.5),0 0 160px rgba(0,212,170,.12)}'
    '.ring-wrap{position:relative;width:72px;height:72px;margin:0 auto 20px}'
    '.ring{position:absolute;inset:0;border-radius:50%;border:3px solid rgba(123,97,255,.15);'
    'border-top:3px solid #7b61ff;border-right:3px solid #00d4aa;animation:spin .8s linear infinite}'
    '.ring2{position:absolute;inset:8px;border-radius:50%;border:2px solid rgba(0,212,170,.12);'
    'border-bottom:2px solid #00d4aa;animation:spin 1.4s linear infinite reverse}'
    '.title{font-size:1.05rem;font-weight:800;color:#fff;letter-spacing:.6px;margin-bottom:6px;'
    'text-shadow:0 0 24px rgba(123,97,255,.95)}'
    '.badges{margin:8px 0 14px}'
    '.badge{display:inline-block;border-radius:6px;padding:2px 10px;margin:0 3px;'
    'font-size:.6rem;font-weight:700;letter-spacing:.5px}'
    '.b-purple{background:rgba(123,97,255,.2);color:#c4b5fd;border:1px solid rgba(123,97,255,.35)}'
    '.b-teal{background:rgba(0,212,170,.15);color:#00d4aa;border:1px solid rgba(0,212,170,.3)}'
    '.b-amber{background:rgba(245,158,11,.12);color:#fbbf24;border:1px solid rgba(245,158,11,.25)}'
    '.sub{font-size:.76rem;color:#94a3b8;margin-bottom:22px}'
    '.steps{display:flex;flex-direction:column;gap:8px;max-width:420px;margin:0 auto 20px}'
    '.step{display:flex;align-items:center;gap:11px;padding:9px 14px;border-radius:9px;font-size:.73rem;text-align:left}'
    '.done{background:rgba(0,212,170,.1);border:1px solid rgba(0,212,170,.4);color:#a7f3d0}'
    '.active{background:rgba(123,97,255,.14);border:1px solid rgba(123,97,255,.55);color:#ede9fe;'
    'animation:pulse 1.3s ease-in-out infinite}'
    '.wait{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.1);color:rgba(255,255,255,.35)}'
    '.step-icon{font-size:.85rem;flex-shrink:0}'
    '.bar-track{height:5px;background:rgba(255,255,255,.07);border-radius:3px;'
    'max-width:400px;margin:0 auto 14px;overflow:hidden}'
    '.bar{height:5px;border-radius:3px;'
    'background:linear-gradient(90deg,#7b61ff,#00d4aa,#7b61ff);'
    'background-size:300% 100%;animation:bar 110s linear forwards,shimmer 2s linear infinite}'
    '.note{font-size:.67rem;color:#7c6fcd;letter-spacing:.3px}'
    '.dots{display:inline-flex;align-items:center;gap:5px;vertical-align:middle;margin-right:6px}'
    '.dot{width:5px;height:5px;border-radius:50%;animation:dotpulse 1.5s ease-in-out infinite}'
    '.d1{background:#7b61ff;animation-delay:0s}'
    '.d2{background:#00d4aa;animation-delay:.25s}'
    '.d3{background:#7b61ff;animation-delay:.5s}'
    '</style></head><body><div class="wrap">'
    '<div class="ring-wrap"><div class="ring"></div><div class="ring2"></div></div>'
    '<div class="title">&#127775; AI Vision Architecture</div>'
    '<div class="badges">'
    '<span class="badge b-purple">&#9889; AI AGENT</span>'
    '<span class="badge b-teal">LIVE RENDER</span>'
    '<span class="badge b-amber">DARK THEME</span>'
    '</div>'
    '<div class="sub">Crafting your cinematic dark-theme architecture diagram&#8202;&#8212;&#8202;neon tier zones, animated data flows &amp; cost overlays</div>'
    '<div class="steps">'
    '<div class="step done"><span class="step-icon">&#10003;</span> Reading architecture components &amp; tech stack</div>'
    '<div class="step active"><span class="step-icon">&#9679;</span> Designing tier zones, connections &amp; data-flow arrows&#8230;</div>'
    '<div class="step wait"><span class="step-icon">&#9675;</span> Rendering neon effects, cost badges &amp; security layers</div>'
    '<div class="step wait"><span class="step-icon">&#9675;</span> Finalising hover interactions &amp; responsive layout</div>'
    '</div>'
    '<div class="bar-track"><div class="bar"></div></div>'
    '<div class="note"><span class="dots"><span class="dot d1"></span><span class="dot d2"></span><span class="dot d3"></span></span>'
    'Up to 2 minutes &middot; Do not navigate away</div>'
    '</div></body></html>'
)


@st.fragment
def _arch_vision_fragment(ar: dict, se: dict, ce: dict, cv_key: str) -> None:
    """Fragment for the AI Vision Architecture card.

    3-state pattern ensures the loader HTML is shown in its own completed rerun
    BEFORE the blocking API call starts — Streamlit only flushes components.html
    at rerun-end, so splitting into show-loader / do-work reruns guarantees
    the user sees the animation the entire time.
    """
    import json as _j

    _cv_html     = st.session_state.get(cv_key)
    _FLAG_SHOW   = "_arch_vision_show_loader"   # rerun 1: just show the loader
    _FLAG_WORK   = "_arch_vision_doing_work"    # rerun 2: make the API call
    _err_flag    = "_arch_vision_err"

    # ── STATE 1 — show loader (no API call, just render the HTML) ────────
    if st.session_state.get(_FLAG_SHOW):
        st.session_state[_FLAG_SHOW] = False
        st.session_state[_FLAG_WORK] = True
        st.components.v1.html(_VISION_LOADER_HTML, height=330, scrolling=False)
        st.rerun(scope="fragment")
        return

    # ── STATE 2 — do the work; spinner keeps feedback alive during API call
    if st.session_state.get(_FLAG_WORK):
        st.session_state[_FLAG_WORK] = False
        # Show loader HTML again (will be visible once this rerun ends if API is fast)
        st.components.v1.html(_VISION_LOADER_HTML, height=330, scrolling=False)
        _err = None
        _generated = None
        # st.spinner IS streamed mid-rerun — gives native Streamlit feedback
        with st.spinner("🔮 AI Vision Architecture — generating, please wait…"):
            try:
                from .ai_clients import AnthropicAI as _AC, AzureAI as _AZ
                _ant = _AC.from_session()
                if _ant.is_live and not st.session_state.get("_claude_blocked"):
                    _generated = _ant.generate_claude_premium_diagram(ar, se, ce)
                if not _generated:
                    _az = _AZ.from_session()
                    if _az.is_live:
                        _generated = _az.generate_ai_arch_svg(ar, se)
                if not _generated:
                    _err = "No AI provider available. Configure a Claude or Azure OpenAI API key in Settings."
            except Exception as _cv_ex:
                _err = str(_cv_ex)[:280]
        if _generated:
            st.session_state[cv_key] = _generated
        if _err:
            st.session_state[_err_flag] = _err
        st.rerun(scope="fragment")
        return

    # ── Show error from previous generation attempt ───────────────────
    _prev_err = st.session_state.pop(_err_flag, None)
    if _prev_err:
        st.error(f"Generation failed: {_prev_err}", icon="⚠️")

    # ── Diagram available ─────────────────────────────────────────────
    if _cv_html:
        st.components.v1.html(_cv_html, height=1080, scrolling=True)
        from datetime import datetime as _dt2
        _cv1, _cv2, _cv3, _cv4 = st.columns(4)
        with _cv1:
            st.download_button(
                "📥 Download (HTML)",
                data=_cv_html.encode("utf-8"),
                file_name="ECI_Vision_" + _dt2.now().strftime("%Y%m%d_%H%M%S") + ".html",
                mime="text/html",
                use_container_width=True,
                key="dl_cv_html",
            )
        with _cv2:
            # Build draw.io XML on demand and offer as download
            _drawio_key = cv_key + "_drawio"
            if _drawio_key not in st.session_state:
                st.session_state[_drawio_key] = generate_vision_drawio_xml(ar, se, ce).encode("utf-8")
            st.download_button(
                "📐 Export to Lucidchart",
                data=st.session_state[_drawio_key],
                file_name="ECI_Vision_" + _dt2.now().strftime("%Y%m%d_%H%M%S") + ".drawio",
                mime="application/xml",
                use_container_width=True,
                key="dl_cv_drawio",
                help="Download .drawio file → in Lucidchart: File → Import → diagrams.net",
            )
        with _cv3:
            if st.button("🔄 Reset Vision", key="btn_cv_reset", use_container_width=True):
                st.session_state.pop(cv_key, None)
                st.session_state.pop(cv_key + "_drawio", None)
                st.rerun(scope="fragment")
        with _cv4:
            if st.button("✨ Regenerate", key="btn_cv_regen",
                         use_container_width=True, type="primary"):
                st.session_state.pop(cv_key, None)
                st.session_state.pop(cv_key + "_drawio", None)
                st.session_state["_arch_vision_show_loader"] = True
                st.rerun(scope="fragment")
        st.info(
            "**To import into Lucidchart:** Download the `.drawio` file → "
            "in Lucidchart go to **File → Import → diagrams.net** and select the file.",
            icon="💡",
        )

    # ── No diagram yet — auto-trigger on first render, show button on retry ─
    else:
        _auto_key = f"_avis_auto_{cv_key}"
        if not st.session_state.get(_auto_key):
            # First time seeing this key — trigger generation automatically
            st.session_state[_auto_key] = True
            st.session_state["_arch_vision_show_loader"] = True
            st.rerun(scope="fragment")
        else:
            # Generation was attempted (failed/reset) — show retry button
            st.markdown(
                '<div style="background:linear-gradient(135deg,rgba(123,97,255,.07),'
                'rgba(0,180,216,.07)),rgba(8,12,24,.6);border:1px solid rgba(123,97,255,.22);'
                'border-radius:14px;padding:28px 24px;text-align:center;margin:8px 0">'
                '<div style="font-size:3rem;margin-bottom:10px">&#127775;</div>'
                '<div style="font-family:\'Segoe UI\',sans-serif;font-size:1.1rem;font-weight:800;'
                'color:#e2e8f0;letter-spacing:.5px">AI Vision Architecture</div>'
                '<div style="font-size:.83rem;color:#94a3b8;margin-top:8px;max-width:480px;'
                'margin-left:auto;margin-right:auto">AI Agent generates a cinematic dark-theme '
                'diagram&#8202;&#8212;&#8202;neon tier zones, animated data-flow arrows, cost '
                'overlays, tech stack badges and hover effects.</div>'
                '</div>',
                unsafe_allow_html=True,
            )
            if st.button(
                "🚀 Generate AI Vision Architecture",
                key="btn_cv_gen",
                use_container_width=True,
                type="primary",
            ):
                st.session_state["_arch_vision_show_loader"] = True
                st.rerun(scope="fragment")


@st.fragment
def _arch_dl_fragment(drawio_key: str, html_key: str, lucid_url: str) -> None:
    """Download buttons in a fragment so clicking only reruns this section, not the full page."""
    _drawio_b = st.session_state.get(drawio_key, b"")
    _html_s   = st.session_state.get(html_key, "")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "📥 Download (HTML)", data=_html_s,
            file_name="ECI_Architecture.html", mime="text/html",
            use_container_width=True, key="dl_arch_html_frag",
        )
    with c2:
        if _drawio_b:
            st.download_button(
                "📐 Export for Lucidchart", data=_drawio_b,
                file_name="ECI_Architecture.drawio", mime="application/xml",
                use_container_width=True, key="dl_arch_drawio_frag",
            )
    with c3:
        st.link_button("🔗 Open Lucidchart", lucid_url, use_container_width=True)
    st.info(
        "**To import into Lucidchart:** Download the `.drawio` file → "
        "in Lucidchart go to **File → Import → diagrams.net** and select the file.",
        icon="💡",
    )


def render_architecture_tab(ar: dict, te: dict, ce: dict,
                             mermaid_diagrams: dict = None,
                             semantic: dict = None,
                             ai_client=None) -> None:
    """Render the Architecture tab.

    Top section  : AI-generated, full-colour HTML/SVG diagram (Claude / Azure OpenAI).
    Middle section: Interactive JavaScript SVG designer (5 views) — shown in expander.
    Bottom section: Component cards, data-flow strip, security controls.
    """
    import json as _json
    import hashlib as _hashlib

    mmd = mermaid_diagrams or {}
    mmd_clean = {k: _sanitize_mermaid(str(v)) if v else "" for k, v in mmd.items()}
    se = semantic or {}

    # ── Cache key: MD5 of the architecture dict so a new pipeline run auto-invalidates ──
    _cache_key = "arch_ai_html_" + _hashlib.md5(
        _json.dumps(ar, sort_keys=True, default=str).encode()
    ).hexdigest()[:10]
    cached_html = st.session_state.get(_cache_key)

    # ── Pattern / meta banner ──
    pattern = safe_str(ar.get("pattern", "Solution Architecture"))
    st.markdown(f"**Pattern:** _{pattern}_")

    # ── Architecture Diagram header ──
    st.markdown("### 🏗️ Solution Architecture Diagram")

    # ── Display: show diagram + Download HTML + Export to Lucidchart ──
    import hashlib as _hl, json as _jc
    _arch_sig   = _hl.md5(_jc.dumps(ar, sort_keys=True, default=str).encode()).hexdigest()[:12]
    _drawio_key = f"_drawio_v3_{_arch_sig}"   # v3 = mxfile wrapper + XML-escaped labels
    _pyhtml_key = f"_py_html_{_arch_sig}"
    _html_dl_key = f"_html_dl_{_arch_sig}"    # HTML string stored for fragment download

    _LUCID_URL = (
        "https://lucid.app/lucidchart/42269312-503c-4fd3-8e1c-243956ae2cc3/edit"
        "?beaconFlowId=18A335721711BBAD&page=0_0"
        "&invitationId=inv_02446fe5-a04d-4f14-a99c-26694ea0b981#"
    )

    # Generate drawio once per unique architecture (never on button-click reruns)
    if _drawio_key not in st.session_state:
        st.session_state[_drawio_key] = generate_drawio_xml(ar, se).encode("utf-8")

    # ── Render diagram HTML outside the fragment ──────────────────────────
    # (stays on screen unchanged when download buttons are clicked)
    if cached_html:
        st.components.v1.html(cached_html, height=920, scrolling=True)
        st.session_state[_html_dl_key] = cached_html
    else:
        if _pyhtml_key not in st.session_state:
            st.session_state[_pyhtml_key] = generate_arch_html_svg(ar, se)
        _py_html = st.session_state[_pyhtml_key]
        st.components.v1.html(_py_html, height=920, scrolling=True)
        if _html_dl_key not in st.session_state:
            st.session_state[_html_dl_key] = _py_html

    # ── Download buttons in a fragment ────────────────────────────────────
    # Clicking a download button only reruns this fragment, not the full page
    _arch_dl_fragment(_drawio_key, _html_dl_key, _LUCID_URL)

    gen_clicked = False  # Enhance with AI hidden

    # ── AI generation (triggered by button in either branch above) ──
    # Tries all live AI clients in priority order: configured → Claude → GPT → Qwen → DeepSeek
    if gen_clicked:
        # Build candidate list: configured client first, then all others
        _candidates = []
        if ai_client and hasattr(ai_client, "generate_ai_arch_svg"):
            _candidates.append(("configured", ai_client))

        # Lazy-import sibling clients to try as fallbacks
        try:
            from .ai_clients import AnthropicAI, AzureAI, QwenAI, DeepSeekAI
            for _cls_name, _cls in [
                ("Claude", AnthropicAI),
                ("Azure OpenAI", AzureAI),
                ("Qwen", QwenAI),
                ("DeepSeek", DeepSeekAI),
            ]:
                try:
                    _c = _cls.from_session()
                    if _c and _c.is_live and hasattr(_c, "generate_ai_arch_svg"):
                        if not any(_c.__class__ is x.__class__ for _, x in _candidates):
                            _candidates.append((_cls_name, _c))
                except Exception:
                    pass
        except ImportError:
            pass

        if not _candidates:
            st.warning(
                "No AI client configured. Add an Anthropic, Azure OpenAI, Qwen, or DeepSeek key in Settings.",
                icon="🔑",
            )
        else:
            _model_name = _candidates[0][0]
            with st.spinner(f"🤖 Generating AI diagram via {_model_name} — this may take ~30 s…"):
                _html = None
                _last_err = ""
                for _name, _c in _candidates:
                    try:
                        _html = _c.generate_ai_arch_svg(ar, se)
                        if _html:
                            _model_name = _name
                            break
                    except Exception as _ex:
                        _last_err = str(_ex)[:120]
                        continue

            if _html:
                st.session_state[_cache_key] = _html
                st.success(f"✅ AI diagram generated via {_model_name}. Refreshing…")
                st.rerun()
            else:
                st.error(
                    f"AI diagram generation failed across all configured models. "
                    f"Last error: {_last_err or 'No response returned — check API keys in Settings.'}",
                    icon="⚠️",
                )

    # ── Claude AI Vision Architecture — fragment-isolated (no full-page gray-out) ──
    st.markdown("---")
    st.markdown("### 🌟 AI Vision Architecture")

    _cv_key = "claude_vision_arch_" + _hashlib.md5(
        _json.dumps(ar, sort_keys=True, default=str).encode()
    ).hexdigest()[:10]
    _arch_vision_fragment(ar, se, ce, _cv_key)

    # ── Build the interactive SVG HTML (always, so the expander can show it) ──
    arch_json = _json.dumps({
        "components":   safe_list(ar.get("components")),
        "data_flow":    [safe_str(f) for f in safe_list(ar.get("data_flow"))],
        "pattern":      safe_str(ar.get("pattern", "Solution Architecture")),
        "security":     [safe_str(s) for s in safe_list(ar.get("security"))],
        "scalability":  safe_str(ar.get("scalability", "")),
        "availability": safe_str(ar.get("availability", "")),
    })
    time_json = _json.dumps({
        "phases":         [safe_dict(p) for p in safe_list(te.get("phases"))],
        "roles":          [safe_dict(r) for r in safe_list(te.get("roles"))],
        "total_hours":    safe_int(te.get("total_hours", 0)),
        "duration_weeks": safe_str(te.get("duration_weeks", "")),
    })
    cost_json = _json.dumps({
        "azure_costs":   [safe_dict(c) for c in safe_list(safe_dict(ce).get("azure_costs"))],
        "total_monthly": safe_int(safe_dict(ce).get("total_monthly_cost", 0)),
    })
    mermaid_json = _json.dumps(mmd_clean)
    semantic_json = _json.dumps({
        "project_type":     safe_str(se.get("project_type", "")),
        "complexity_score": safe_int(se.get("complexity_score", 5)),
        "technology_stack": [safe_str(t) for t in safe_list(se.get("technology_stack"))],
        "req_count":        len(safe_list(se.get("requirements"))),
    })


    html = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10.6.1/dist/mermaid.min.js" defer></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:#080e1a;color:#e2e8f0;font-family:'Segoe UI',Arial,sans-serif;
  width:100%;overflow-x:hidden}}
/* ── toolbar ── */
#toolbar{{background:#0a1628;border-bottom:1px solid #1e2d4a;padding:10px 14px}}
#hdr{{display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px}}
#titlewrap{{min-width:0}}
#diag-title{{font-size:.85rem;font-weight:800;color:#e2e8f0;letter-spacing:.4px}}
#diag-sub{{font-size:.65rem;color:#64748b;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
#stats{{display:flex;gap:10px;flex-wrap:wrap;margin-top:6px}}
.stat{{background:rgba(0,180,212,.1);border:1px solid rgba(0,180,212,.25);
  border-radius:20px;padding:2px 10px;font-size:.62rem;color:#00bcf2;white-space:nowrap}}
/* ── selector groups ── */
#selwrap{{display:flex;flex-direction:column;gap:5px;margin-top:8px}}
.sel-row{{display:flex;align-items:center;gap:5px;flex-wrap:wrap}}
.sel-lbl{{font-size:.58rem;color:#475569;text-transform:uppercase;letter-spacing:1px;
  white-space:nowrap;min-width:70px}}
.sb{{padding:4px 11px;border:1px solid #1e3050;background:transparent;color:#64748b;
  border-radius:16px;cursor:pointer;font-size:.67rem;font-weight:600;
  letter-spacing:.2px;transition:all .15s;white-space:nowrap}}
.sb:hover{{border-color:#0078d4;color:#93c5fd}}
.sb.on{{background:linear-gradient(135deg,#0f4c8c,#0078d4);border-color:#0078d4;
  color:#fff;box-shadow:0 0 8px rgba(0,120,212,.4)}}
.sb.mmd.on{{background:linear-gradient(135deg,#1a3a1a,#166534);border-color:#22c55e;
  box-shadow:0 0 8px rgba(34,197,94,.35)}}
#exp{{padding:5px 12px;background:#0f2640;border:1px solid #0078d4;
  color:#60a5fa;border-radius:7px;cursor:pointer;font-size:.67rem;font-weight:700;
  transition:all .15s;white-space:nowrap;flex-shrink:0}}
#exp:hover{{background:#0078d4;color:#fff}}
/* ── canvas ── */
#wrap{{width:100%;overflow-x:auto;background:#080e1a}}
svg#asvg{{display:block}}
#mermaid-area{{display:none;padding:16px;background:#080e1a;min-height:550px;overflow:auto}}
#mermaid-area svg{{max-width:100%;height:auto}}
#mmd-spinner{{text-align:center;padding:60px;color:#64748b;font-size:.8rem}}
#mmd-err{{color:#f87171;background:#1a0a0a;border:1px solid #7f1d1d;border-radius:8px;
  padding:12px;font-size:.75rem;white-space:pre-wrap;font-family:monospace}}
/* ── legend ── */
#leg{{display:flex;gap:12px;padding:7px 14px 10px;flex-wrap:wrap;
  border-top:1px solid #1e2d4a;background:#0a1628}}
.li{{display:flex;align-items:center;gap:5px;font-size:.62rem;color:#94a3b8}}
.ld{{width:9px;height:9px;border-radius:2px;flex-shrink:0}}
/* ── tooltip ── */
#tip{{position:fixed;pointer-events:none;display:none;
  background:#0d1a2e;border:1px solid #0078d4;border-radius:8px;
  padding:9px 13px;min-width:170px;max-width:240px;z-index:99;
  font-size:.7rem;line-height:1.55;box-shadow:0 4px 20px rgba(0,0,0,.6)}}
#tip-name{{font-weight:700;color:#e2e8f0;font-size:.78rem}}
#tip-svc{{color:#00bcf2;margin-top:2px;font-size:.68rem}}
#tip-svcs{{color:#94a3b8;margin-top:4px;font-size:.62rem;line-height:1.5}}
</style>
</head><body>
<div id="toolbar">
  <div id="hdr">
    <div id="titlewrap">
      <div id="diag-title">🏗️ Architecture Designer</div>
      <div id="diag-sub"></div>
      <div id="stats"></div>
    </div>
    <div style="display:flex;gap:6px;flex-shrink:0">
      <button id="renderBtn" onclick="forceRender('solution');"
        style="padding:5px 12px;background:#0078d4;border:none;border-radius:7px;color:#fff;font-size:.67rem;font-weight:700;cursor:pointer;letter-spacing:.2px">
        🔄 Render
      </button>
      <button id="exp" onclick="doExport()">⬇ Export</button>
    </div>
  </div>
  <div id="selwrap">
    <div class="sel-row">
      <span class="sel-lbl">⚡ Interactive</span>
      <button class="sb on"  onclick="show('solution',this)">🏗️ Solution Architecture</button>
      <button class="sb"     onclick="show('workflow',this)">🔄 Project Workflow</button>
      <button class="sb"     onclick="show('dataflow',this)">📊 Data Flow</button>
      <button class="sb"     onclick="show('infra',this)">☁️ Infrastructure Map</button>
      <button class="sb"     onclick="show('security',this)">🔒 Security Layers</button>
    </div>
    <div class="sel-row">
      <span class="sel-lbl">🤖 AI Diagrams</span>
      <button class="sb mmd" onclick="show('mmd_infrastructure',this)">🏗️ Infrastructure</button>
      <button class="sb mmd" onclick="show('mmd_data_flow',this)">🔄 Data Flow</button>
      <button class="sb mmd" onclick="show('mmd_sequence',this)">📨 Sequence</button>
      <button class="sb mmd" onclick="show('mmd_deployment',this)">🚀 Deployment</button>
      <button class="sb mmd" onclick="show('mmd_security',this)">🔒 Security</button>
    </div>
  </div>
</div>
<div id="wrap"><svg id="asvg" xmlns="http://www.w3.org/2000/svg"></svg></div>
<div id="mermaid-area">
  <div id="mmd-spinner">Loading diagram…</div>
  <div id="mmd-render"></div>
</div>
<div id="leg"></div>
<div id="tip">
  <div id="tip-name"></div>
  <div id="tip-svc"></div>
  <div id="tip-svcs"></div>
</div>
<script>
const ARCH={arch_json};
const TIME={time_json};
const COST={cost_json};
const MMD={mermaid_json};
const SEM={semantic_json};
const NS='http://www.w3.org/2000/svg';
// svg is resolved lazily in _init() — never cache at parse time
// because Streamlit iframes can execute scripts before layout settles.
let svg=null;

// Mermaid is only needed for AI diagram tabs and is loaded with defer,
// so it may not be available at script-init time.  All checks are lazy.
let _mermaidInitDone=false;
function _ensureMermaid(){{
  if(_mermaidInitDone)return;
  if(typeof mermaid==='undefined'||typeof mermaid.render!=='function')return;
  try{{
    mermaid.initialize({{
      startOnLoad:false,securityLevel:'loose',theme:'dark',
      themeVariables:{{primaryColor:'#16274B',primaryTextColor:'#e2e8f0',
        primaryBorderColor:'#0078d4',lineColor:'#00bcf2',secondaryColor:'#0a1628',
        tertiaryColor:'#080e1a',fontFamily:'Segoe UI,Arial,sans-serif'}}
    }});
    _mermaidInitDone=true;
  }}catch(e){{console.warn('Mermaid init error:',e);}}
}}
function _mermaidOk(){{
  _ensureMermaid();
  return typeof mermaid!=='undefined'&&typeof mermaid.render==='function';
}}

// ── SVG helpers ────────────────────────────────────────────────────────────────────────────
function e(tag,a,txt){{
  const n=document.createElementNS(NS,tag);
  for(const[k,v]of Object.entries(a||{{}}))n.setAttribute(k,v);
  if(txt!==undefined)n.textContent=txt;return n;
}}
function trunc(s,n){{s=String(s||'');return s.length>n?s.slice(0,n-2)+'…':s;}}
function rgb(hex){{
  return parseInt(hex.slice(1,3),16)+','+parseInt(hex.slice(3,5),16)+','+parseInt(hex.slice(5,7),16);
}}
function setSvg(w,h){{
  const cw=document.getElementById('wrap').clientWidth||860;
  const fw=Math.max(w,cw);
  svg.setAttribute('width',fw);svg.setAttribute('height',h);
  svg.setAttribute('viewBox','0 0 '+fw+' '+h);return fw;
}}
function addDefs(){{
  let d=document.getElementById('_defs');if(d)d.remove();
  d=e('defs',{{id:'_defs'}});
  ['arr','#4b5563','arr2','#0078d4','arr3','#00bcf2'].reduce((acc,v,i,a)=>{{
    if(i%2===0){{
      const mk=e('marker',{{id:v,markerWidth:'9',markerHeight:'7',refX:'9',refY:'3.5',orient:'auto'}});
      mk.appendChild(e('polygon',{{points:'0 0,9 3.5,0 7',fill:a[i+1]}}));
      d.appendChild(mk);
    }}return d;
  }},d);
  svg.insertBefore(d,svg.firstChild);
}}

// ── Azure service icons ──────────────────────────────────────────────────────────────────────────────
const ICONS={{
  'front door':'🚪','cdn':'📡','static web':'📄','react':'⚛',
  'api management':'🔌','api gateway':'🔌','functions':'⚡','function':'⚡',
  'service bus':'📨','event hub':'📬','logic app':'🔗','signalr':'📡',
  'app service':'🖥','web app':'🌐','container app':'📦','kubernetes':'☸','aks':'☸',
  'sql':'🗃','cosmos':'🌀','blob':'💾','storage':'💾','redis':'⚡','cache':'⚡',
  'data lake':'🏞','synapse':'🔬','databricks':'🔥','data factory':'🏭',
  'key vault':'🔑','active directory':'👤','entra':'👤','firewall':'🛡',
  'defender':'🛡','sentinel':'👁','waf':'🛡','ddos':'🛡',
  'monitor':'📊','insights':'📈','devops':'🚀','log analytics':'📋',
  'openai':'🤖','cognitive':'🧠','search':'🔍','form recognizer':'📝',
  'power bi':'📊','power platform':'⚡','copilot':'🤖',
}};
function getIcon(comp){{
  const n=(comp.name||'').toLowerCase(),s=(comp.azure_service||'').toLowerCase();
  for(const[kw,ic]of Object.entries(ICONS))if(n.includes(kw)||s.includes(kw))return ic;
  return '⬡';
}}

// ── tier classification ──────────────────────────────────────────────────────────────────────────────
const TMAP={{
  'front door':'presentation','cdn':'presentation','static web':'presentation',
  'web app':'presentation','portal':'presentation','react':'presentation',
  'api':'application','function':'application','app service':'application',
  'service bus':'application','event hub':'application','logic app':'application',
  'container':'application','kubernetes':'application','aks':'application','signalr':'application',
  'sql':'data','cosmos':'data','blob':'data','storage':'data','redis':'data','cache':'data',
  'data lake':'data','synapse':'data','databricks':'data','data factory':'data','search':'data',
  'key vault':'security','active directory':'security','entra':'security',
  'firewall':'security','defender':'security','sentinel':'security','waf':'security',
  'monitor':'operations','insights':'operations','devops':'operations','log':'operations',
  'openai':'ai','cognitive':'ai','ai':'ai','copilot':'ai','form recognizer':'ai',
}};
const ZONES=[
  {{id:'internet',    label:'🌐 Internet',         col:'#6b7280',bg:'rgba(107,114,128,.08)',brd:'#4b5563'}},
  {{id:'presentation',label:'📱 Presentation',      col:'#0078d4',bg:'rgba(0,120,212,.09)', brd:'#0078d4'}},
  {{id:'application', label:'⚙️ Application',       col:'#00bcf2',bg:'rgba(0,188,242,.09)', brd:'#00bcf2'}},
  {{id:'ai',          label:'🤖 AI & Cognitive',    col:'#a855f7',bg:'rgba(168,85,247,.08)',brd:'#a855f7'}},
  {{id:'data',        label:'💾 Data & Storage',    col:'#22c55e',bg:'rgba(34,197,94,.08)', brd:'#22c55e'}},
  {{id:'security',    label:'🔑 Identity & Security',col:'#f59e0b',bg:'rgba(245,158,11,.07)',brd:'#f59e0b'}},
  {{id:'operations',  label:'🔧 Ops & DevOps',      col:'#fb923c',bg:'rgba(251,146,60,.07)',brd:'#fb923c'}},
];
function getTier(c){{
  const n=(c.name||'').toLowerCase(),t=(c.type||'').toLowerCase(),s=(c.azure_service||'').toLowerCase();
  for(const[k,v]of Object.entries(TMAP))if(n.includes(k)||t.includes(k)||s.includes(k))return v;
  return 'application';
}}

// ── tooltip (lazy ref — element may not exist at parse time) ─────────────────────────────────
function _getTip(){{return document.getElementById('tip');}}
document.addEventListener('mousemove',ev=>{{
  const t=_getTip();if(!t)return;
  t.style.left=(ev.clientX+14)+'px';t.style.top=(ev.clientY+10)+'px';
}});
function showTip(comp){{
  const t=_getTip();if(!t)return;
  document.getElementById('tip-name').textContent=comp.name||'';
  document.getElementById('tip-svc').textContent=comp.azure_service||'';
  const svcs=(comp.services||[]).slice(0,4).join('\n• ');
  document.getElementById('tip-svcs').textContent=svcs?'• '+svcs:'';
  t.style.display='block';
}}
function hideTip(){{const t=_getTip();if(t)t.style.display='none';}}

// ── header stats ──────────────────────────────────────────────────────────────────────────────────
function setHeader(sub){{
  document.getElementById('diag-sub').textContent=sub;
  const stats=document.getElementById('stats');stats.innerHTML='';
  const items=[
    ARCH.pattern&&{{t:'Pattern',v:trunc(ARCH.pattern,30)}},
    SEM.project_type&&{{t:'Type',v:SEM.project_type}},
    ARCH.components.length&&{{t:'Components',v:ARCH.components.length}},
    TIME.total_hours&&{{t:'Est. Hours',v:TIME.total_hours+'h'}},
    COST.total_monthly&&{{t:'Infra/mo',v:'$'+COST.total_monthly}},
    SEM.req_count&&{{t:'Requirements',v:SEM.req_count}},
  ].filter(Boolean);
  items.forEach(it=>{{
    const d=document.createElement('div');d.className='stat';
    d.textContent=it.t+': '+it.v;stats.appendChild(d);
  }});
}}

// ══════════════════════════════════════════════════════════════════════════════════
//  1. SOLUTION ARCHITECTURE — Azure subscription zones + data-flow arrows
// ══════════════════════════════════════════════════════════════════════════════════
function drawSolution(){{
  svg.innerHTML='';addDefs();
  const W=setSvg(860,760);
  const PAD=24,ZH=95,GAP=7,CW=150,CH=62;
  const posMap={{}};

  const tiers={{}};ZONES.forEach(z=>tiers[z.id]=[]);
  tiers['internet']=[{{name:'Users',azure_service:'Web Browser / Mobile',services:['End customers','Internal staff']}},
                     {{name:'External APIs',azure_service:'3rd-party Services',services:['Payment gateways','Identity providers']}}];
  (ARCH.components||[]).forEach(c=>{{
    const t=getTier(c);tiers[t]=tiers[t]||[];tiers[t].push(c);
  }});
  const DEFAULTS={{
    presentation:[{{name:'Web Application',azure_service:'Azure App Service',services:['SPA / Server-side rendering','CDN caching']}},
                  {{name:'Front Door',azure_service:'Azure Front Door',services:['Global load balancing','WAF protection']}}],
    application: [{{name:'API Gateway',azure_service:'Azure API Management',services:['Rate limiting','OAuth 2.0','Versioning']}},
                  {{name:'App Services',azure_service:'Azure Functions',services:['Business logic','Event processing']}}],
    data:        [{{name:'SQL Database',azure_service:'Azure SQL Database',services:['Relational data','BCDR']}},
                  {{name:'Blob Storage',azure_service:'Azure Blob Storage',services:['Documents','Media files']}}],
    security:    [{{name:'Key Vault',azure_service:'Azure Key Vault',services:['Secrets management','Certificate rotation']}},
                  {{name:'Azure AD',azure_service:'Microsoft Entra ID',services:['SSO','MFA','RBAC']}}],
    operations:  [{{name:'Monitor',azure_service:'Azure Monitor',services:['Alerts','Log Analytics','Metrics']}},
                  {{name:'DevOps',azure_service:'Azure DevOps',services:['CI/CD','Repos','Boards']}}],
  }};
  ZONES.forEach(z=>{{if(!tiers[z.id].length&&DEFAULTS[z.id])tiers[z.id]=DEFAULTS[z.id];}});
  const visZones=ZONES.filter(z=>tiers[z.id]&&tiers[z.id].length);

  const subH=visZones.length*(ZH+GAP)+GAP*2;
  const totalH=PAD+subH+PAD+22;
  svg.setAttribute('height',totalH);svg.setAttribute('viewBox','0 0 '+W+' '+totalH);

  svg.appendChild(e('rect',{{x:PAD,y:PAD,width:W-PAD*2,height:subH,rx:14,
    fill:'none',stroke:'#0078d4','stroke-width':2,'stroke-dasharray':'12,6'}}));
  svg.appendChild(e('rect',{{x:PAD+20,y:PAD-11,width:196,height:22,rx:5,fill:'#080e1a'}}));
  svg.appendChild(e('text',{{x:PAD+28,y:PAD+6,fill:'#0078d4','font-size':'12',
    'font-weight':'800','letter-spacing':'.5'}},'☁️  Azure Subscription'));

  const ZY0=PAD+GAP+4;
  visZones.forEach((zone,zi)=>{{
    const zy=ZY0+zi*(ZH+GAP);
    const zx=PAD+12,zw=W-PAD*2-24;
    const comps=tiers[zone.id]||[];

    svg.appendChild(e('rect',{{x:zx,y:zy,width:zw,height:ZH,rx:9,
      fill:zone.bg,stroke:zone.brd,'stroke-width':1,'stroke-dasharray':'4,3'}}));
    svg.appendChild(e('rect',{{x:zx+8,y:zy+6,width:160,height:22,rx:11,
      fill:'rgba('+rgb(zone.col)+',.18)'}}));
    svg.appendChild(e('text',{{x:zx+16,y:zy+21,fill:zone.col,'font-size':'11','font-weight':'700'}}
      ,zone.label));
    if(comps.length>0){{
      svg.appendChild(e('text',{{x:zx+zw-10,y:zy+20,fill:zone.col,'font-size':'10',
        'text-anchor':'end',opacity:'.7'}},comps.length+' components'));
    }}

    const avail=zw-178;
    const maxN=Math.max(1,Math.floor(avail/(CW+9)));
    const vis=comps.slice(0,maxN);
    const totalCW=vis.length*(CW+9)-9;
    let cx=zx+176+(avail-totalCW)/2;
    const cy=zy+(ZH-CH)/2;

    vis.forEach((comp,ci)=>{{
      const g=e('g',{{cursor:'pointer'}});
      const fx=cx+ci*(CW+9);
      const ccx=fx+CW/2,ccy=cy+CH/2;
      const keys=[(comp.name||'').toLowerCase(),(comp.azure_service||'').toLowerCase()];
      keys.forEach(k=>{{if(k.trim())posMap[k.trim()]={{cx:ccx,cy:ccy}};}});
      const firstWord=(comp.name||'').split(' ')[0].toLowerCase();
      if(firstWord.length>2)posMap[firstWord]={{cx:ccx,cy:ccy}};

      g.appendChild(e('rect',{{x:fx+2,y:cy+2,width:CW,height:CH,rx:7,fill:'rgba(0,0,0,.4)'}}));
      const card=e('rect',{{x:fx,y:cy,width:CW,height:CH,rx:7,
        fill:'rgba('+rgb(zone.col)+',.13)',stroke:zone.col,'stroke-width':1}});
      g.appendChild(card);
      g.appendChild(e('rect',{{x:fx,y:cy,width:CW,height:3,rx:2,fill:zone.col,opacity:'.9'}}));
      g.appendChild(e('circle',{{cx:fx+18,cy:cy+CH/2,r:12,
        fill:'rgba('+rgb(zone.col)+',.2)',stroke:zone.col,'stroke-width':.8}}));
      g.appendChild(e('text',{{x:fx+18,y:cy+CH/2+4,fill:zone.col,'font-size':'12',
        'text-anchor':'middle'}},getIcon(comp)));
      g.appendChild(e('text',{{x:fx+34,y:cy+22,fill:'#e2e8f0','font-size':'11','font-weight':'700'}}
        ,trunc(comp.name||'',16)));
      g.appendChild(e('text',{{x:fx+34,y:cy+38,fill:zone.col,'font-size':'9',opacity:'.9'}}
        ,trunc(comp.azure_service||'',22)));
      const svcs=comp.services||[];
      if(svcs[0])g.appendChild(e('text',{{x:fx+34,y:cy+52,fill:'#64748b','font-size':'8'}}
        ,trunc(String(svcs[0]),25)));

      g.addEventListener('mouseenter',()=>{{card.setAttribute('fill','rgba('+rgb(zone.col)+',.3)');showTip(comp);}});
      g.addEventListener('mouseleave',()=>{{card.setAttribute('fill','rgba('+rgb(zone.col)+',.13)');hideTip();}});
      svg.appendChild(g);
    }});

    if(comps.length>vis.length){{
      svg.appendChild(e('text',{{x:zx+zw-10,y:zy+ZH-8,fill:zone.col,'font-size':'9',
        'text-anchor':'end',opacity:'.65'}},'+ '+(comps.length-vis.length)+' more…'));
    }}

    if(zi<visZones.length-1){{
      const ax=zx+88,ay1=zy+ZH+1,ay2=zy+ZH+GAP-1;
      svg.appendChild(e('line',{{x1:ax,y1:ay1,x2:ax,y2:ay2,
        stroke:'#374151','stroke-width':1.5,'stroke-dasharray':'3,2','marker-end':'url(#arr)'}}));
    }}
  }});

  const flow=ARCH.data_flow||[];
  function fuzzyPos(name){{
    const k=name.toLowerCase().trim();
    if(posMap[k])return posMap[k];
    for(const[pk,pv]of Object.entries(posMap)){{
      if(pk.includes(k)||k.includes(pk))return pv;
    }}
    const fw=k.split(' ')[0];
    for(const[pk,pv]of Object.entries(posMap))if(pk.includes(fw))return pv;
    return null;
  }}
  const drawnArrows=new Set();
  for(let i=0;i<flow.length-1;i++){{
    const from=fuzzyPos(flow[i]),to=fuzzyPos(flow[i+1]);
    if(!from||!to)continue;
    const key=Math.round(from.cx)+'_'+Math.round(from.cy)+'→'+Math.round(to.cx)+'_'+Math.round(to.cy);
    if(drawnArrows.has(key))continue;
    drawnArrows.add(key);
    const midX=(from.cx+to.cx)/2,midY=(from.cy+to.cy)/2;
    const cp1x=from.cx+(to.cx-from.cx)*.3,cp1y=from.cy+(to.cy-from.cy)*.1;
    const cp2x=from.cx+(to.cx-from.cx)*.7,cp2y=from.cy+(to.cy-from.cy)*.9;
    const path=e('path',{{
      d:'M '+from.cx+' '+from.cy+' C '+cp1x+' '+cp1y+','+cp2x+' '+cp2y+','+to.cx+' '+to.cy,
      fill:'none',stroke:'#00bcf2','stroke-width':'1.5',opacity:'.55',
      'stroke-dasharray':'5,3','marker-end':'url(#arr3)'
    }});
    svg.appendChild(path);
    const lbl=e('text',{{x:midX,y:midY-5,fill:'#00bcf2','font-size':'8',
      'text-anchor':'middle',opacity:'.65','font-style':'italic'}},String(i+1));
    svg.appendChild(lbl);
  }}

  if(flow.length){{
    const fy=PAD+subH+PAD+4;
    svg.appendChild(e('text',{{x:PAD+10,y:fy,fill:'#374151','font-size':'9','font-style':'italic'}}
      ,'📊 Flow: '+flow.slice(0,8).join(' → ')));
  }}

  legend(ZONES.filter(z=>tiers[z.id]&&tiers[z.id].length).map(z=>({{label:z.label,color:z.col}})));
  setHeader(ARCH.pattern||'Azure Solution Architecture');
}}

// ══════════════════════════════════════════════════════════════════════════════════
//  2. PROJECT WORKFLOW — dynamic swim-lane Gantt
// ══════════════════════════════════════════════════════════════════════════════════
function drawWorkflow(){{
  svg.innerHTML='';addDefs();
  const phases=TIME.phases.length?TIME.phases:[
    {{name:'Discovery & Planning',weeks:2,team:'PM, Business Analyst, Client'}},
    {{name:'Architecture & Design',weeks:2,team:'Solution Architect, Lead Dev'}},
    {{name:'Development Sprint 1',weeks:4,team:'Dev Team, DevOps'}},
    {{name:'Development Sprint 2',weeks:4,team:'Dev Team, QA'}},
    {{name:'Integration & Testing',weeks:2,team:'QA, Dev Team'}},
    {{name:'UAT & Training',weeks:2,team:'PM, Client, QA'}},
    {{name:'Deployment & Go-Live',weeks:1,team:'DevOps, PM'}},
    {{name:'Hypercare & Support',weeks:2,team:'Support, PM'}},
  ];
  const LANES=[
    {{id:'client', label:'👤 Client / Stakeholder', col:'#0078d4',
      match:['client','stakeholder','uat','sign-off','accept']}},
    {{id:'pm',     label:'📋 PM & Business Analyst', col:'#00bcf2',
      match:['pm','analyst','ba','planning','discov','require']}},
    {{id:'arch',   label:'🏛️ Architect',             col:'#a78bfa',
      match:['architect','design','solution','tech lead']}},
    {{id:'dev',    label:'💻 Development',            col:'#00d4aa',
      match:['dev','sprint','integrat','build','code','engineer']}},
    {{id:'qa',     label:'🧪 QA & Testing',           col:'#fbbf24',
      match:['qa','test','uat','quality','validation']}},
    {{id:'devops', label:'🚀 DevOps & Cloud',         col:'#fb923c',
      match:['devops','deploy','pipeline','ci','go-live','cloud','infra']}},
    {{id:'support',label:'🛟 Support & Hypercare',    col:'#e879f9',
      match:['support','hypercare','maintenance','monitor']}},
  ];
  const PW=Math.max(88,(820-180)/phases.length-8);
  const LH=72,HEADER_H=46;
  const TW=Math.max(820,180+phases.length*(PW+7)+20);
  const TH=LANES.length*LH+HEADER_H+30;
  setSvg(TW,TH);

  const totalWeeks=phases.reduce((s,p)=>s+(p.weeks||2),0)||16;

  phases.forEach((ph,pi)=>{{
    const px=180+pi*(PW+7);
    const pname=typeof ph==='string'?ph:(ph.name||'Phase '+(pi+1));
    const pweeks=typeof ph==='object'&&ph.weeks?ph.weeks+'w':'';
    const isLast=pi===phases.length-1;
    const col=isLast?'#22c55e':'#0078d4';
    svg.appendChild(e('rect',{{x:px,y:4,width:PW,height:HEADER_H-4,rx:6,
      fill:'rgba('+rgb(col)+',.15)',stroke:col,'stroke-width':1}}));
    svg.appendChild(e('text',{{x:px+PW/2,y:18,fill:'#e2e8f0','font-size':'10','font-weight':'700',
      'text-anchor':'middle','dominant-baseline':'middle'}},trunc(pname,15)));
    if(pweeks)svg.appendChild(e('text',{{x:px+PW/2,y:35,fill:col,'font-size':'9','font-weight':'600',
      'text-anchor':'middle'}},pweeks));
    if(pi<phases.length-1){{
      const ax=px+PW+1;
      svg.appendChild(e('line',{{x1:ax,y1:HEADER_H/2,x2:ax+5,y2:HEADER_H/2,
        stroke:'#374151','stroke-width':1.5,'marker-end':'url(#arr)'}}));
    }}
  }});

  LANES.forEach((lane,li)=>{{
    const ly=HEADER_H+li*LH;
    svg.appendChild(e('rect',{{x:0,y:ly,width:TW,height:LH,
      fill:li%2?'transparent':'rgba(255,255,255,.012)',
      stroke:'rgba(255,255,255,.04)','stroke-width':1}}));
    svg.appendChild(e('rect',{{x:0,y:ly,width:174,height:LH,
      fill:'rgba('+rgb(lane.col)+',.09)',stroke:lane.col,'stroke-width':.8,opacity:.8}}));
    svg.appendChild(e('text',{{x:87,y:ly+LH/2,fill:lane.col,'font-size':'11','font-weight':'700',
      'text-anchor':'middle','dominant-baseline':'middle'}},lane.label));

    phases.forEach((ph,pi)=>{{
      const pname=(typeof ph==='string'?ph:(ph.name||'')).toLowerCase();
      const pteam=(typeof ph==='object'?(ph.team||''):'').toLowerCase();
      const active=lane.match.some(m=>pname.includes(m)||pteam.includes(m));
      if(!active)return;
      const px=180+pi*(PW+7)+4;
      const bh=LH-16;const by=ly+8;
      svg.appendChild(e('rect',{{x:px,y:by,width:PW-8,height:bh,rx:6,
        fill:'rgba('+rgb(lane.col)+',.2)',stroke:lane.col,'stroke-width':1}}));
      svg.appendChild(e('text',{{x:px+(PW-8)/2,y:by+bh/2,fill:lane.col,'font-size':'14',
        'text-anchor':'middle','dominant-baseline':'middle'}},'▣'));
      const teamLabel=(typeof ph==='object'&&ph.team)?trunc(ph.team,12):'';
      if(teamLabel&&PW>100)svg.appendChild(e('text',{{x:px+(PW-8)/2,y:by+bh-6,
        fill:'rgba('+rgb(lane.col)+',.7)','font-size':'7','text-anchor':'middle'}},teamLabel));
    }});
  }});

  const barY=HEADER_H+LANES.length*LH+8;
  svg.appendChild(e('text',{{x:87,y:barY+10,fill:'#475569','font-size':'9','text-anchor':'middle'}}
    ,'Total: '+(TIME.duration_weeks||totalWeeks+'w')));

  legend(LANES.map(l=>({{label:l.label,color:l.col}})));
  setHeader('Project Workflow — '+(TIME.duration_weeks||'')+(TIME.total_hours?' · '+TIME.total_hours+'h':''));
}}

// ══════════════════════════════════════════════════════════════════════════════════
//  3. DATA FLOW — horizontal pipeline with animated flow dots
// ══════════════════════════════════════════════════════════════════════════════════
function drawDataflow(){{
  svg.innerHTML='';addDefs();
  const STAGES=[
    {{id:'src',  label:'📥 Data Sources',   col:'#6b7280',items:[]}},
    {{id:'ing',  label:'🔄 Ingestion',       col:'#0078d4',items:[]}},
    {{id:'proc', label:'⚙️ Processing',      col:'#00bcf2',items:[]}},
    {{id:'ai',   label:'🤖 AI & Analytics', col:'#a855f7',items:[]}},
    {{id:'stor', label:'💾 Storage',         col:'#22c55e',items:[]}},
    {{id:'cons', label:'📊 Consumers',       col:'#fb923c',items:[]}},
  ];
  (ARCH.components||[]).forEach(c=>{{
    const n=(c.name||'').toLowerCase(),s=(c.azure_service||'').toLowerCase();
    if(n.includes('user')||n.includes('client')||n.includes('input')||n.includes('source')||n.includes('upload'))
      STAGES[0].items.push(c);
    else if(n.includes('event')||n.includes('hub')||n.includes('ingest')||n.includes('service bus')||
            s.includes('event hub')||s.includes('service bus'))
      STAGES[1].items.push(c);
    else if(n.includes('process')||n.includes('function')||n.includes('api')||
            s.includes('function')||s.includes('api management')||s.includes('app service'))
      STAGES[2].items.push(c);
    else if(n.includes('ai')||n.includes('openai')||n.includes('cognitive')||n.includes('ml')||
            s.includes('openai')||s.includes('cognitive')||s.includes('search'))
      STAGES[3].items.push(c);
    else if(n.includes('sql')||n.includes('cosmos')||n.includes('blob')||n.includes('storage')||
            n.includes('lake')||n.includes('database')||s.includes('sql')||s.includes('cosmos')||s.includes('storage'))
      STAGES[4].items.push(c);
    else
      STAGES[5].items.push(c);
  }});
  const DEF=[
    [{{name:'Web Users',azure_service:'Browser/Mobile',services:['End customers','Internal users']}},
     {{name:'External Systems',azure_service:'Third-party APIs',services:['Webhooks','File uploads']}}],
    [{{name:'Event Hub',azure_service:'Azure Event Hubs',services:['100K events/sec','Partitioned ingestion']}},
     {{name:'API Gateway',azure_service:'API Management',services:['Rate limiting','Auth','Routing']}}],
    [{{name:'Azure Functions',azure_service:'Serverless Compute',services:['Event-driven logic','Auto-scale']}},
     {{name:'App Service',azure_service:'Azure App Service',services:['Business logic','Background jobs']}}],
    [{{name:'Azure OpenAI',azure_service:'GPT-4o / Embeddings',services:['NLP processing','Vector search']}},
     {{name:'AI Search',azure_service:'Azure AI Search',services:['Hybrid search','RAG pipeline']}}],
    [{{name:'SQL Database',azure_service:'Azure SQL',services:['Relational data','BCDR']}},
     {{name:'Blob Storage',azure_service:'Azure Storage',services:['Documents','Unstructured data']}}],
    [{{name:'Power BI',azure_service:'Analytics',services:['Dashboards','Reports']}},
     {{name:'API Clients',azure_service:'Consumer Apps',services:['Mobile apps','3rd-party integrations']}}],
  ];
  STAGES.forEach((s,i)=>{{if(!s.items.length)s.items=DEF[i];}});
  const W=setSvg(900,560);
  const SW=(W-30)/(STAGES.length)-9;const SH=480;const CH=60;
  svg.setAttribute('height',SH+70);svg.setAttribute('viewBox','0 0 '+W+' '+(SH+70));
  STAGES.forEach((st,si)=>{{
    const sx=15+si*(SW+9);
    svg.appendChild(e('rect',{{x:sx,y:10,width:SW,height:SH,rx:9,
      fill:'rgba('+rgb(st.col)+',.07)',stroke:st.col,'stroke-width':1,'stroke-dasharray':'4,3'}}));
    svg.appendChild(e('rect',{{x:sx,y:10,width:SW,height:40,rx:9,
      fill:'rgba('+rgb(st.col)+',.2)'}}));
    svg.appendChild(e('text',{{x:sx+SW/2,y:34,fill:st.col,'font-size':'10','font-weight':'700',
      'text-anchor':'middle'}},st.label));
    st.items.slice(0,5).forEach((item,ii)=>{{
      const iy=60+ii*(CH+9);
      svg.appendChild(e('rect',{{x:sx+7,y:iy,width:SW-14,height:CH,rx:7,
        fill:'rgba('+rgb(st.col)+',.12)',stroke:st.col,'stroke-width':1}}));
      svg.appendChild(e('text',{{x:sx+18,y:iy+15,fill:st.col,'font-size':'14'}}
        ,getIcon(item)));
      svg.appendChild(e('text',{{x:sx+34,y:iy+17,fill:'#e2e8f0','font-size':'10','font-weight':'600'}}
        ,trunc(item.name||'',14)));
      svg.appendChild(e('text',{{x:sx+34,y:iy+31,fill:st.col,'font-size':'8',opacity:'.9'}}
        ,trunc(item.azure_service||'',19)));
      const s0=(item.services||[])[0];
      if(s0)svg.appendChild(e('text',{{x:sx+34,y:iy+44,fill:'#475569','font-size':'8'}}
        ,trunc(String(s0),22)));
    }});
    if(si<STAGES.length-1){{
      const ax=sx+SW+1,ay=10+SH/2;
      svg.appendChild(e('line',{{x1:ax,y1:ay,x2:ax+7,y2:ay,
        stroke:'#00bcf2','stroke-width':2,'marker-end':'url(#arr2)'}}));
      const circ=e('circle',{{r:4,fill:'#00bcf2',opacity:'.8'}});
      const anim=document.createElementNS(NS,'animateMotion');
      anim.setAttribute('dur',(1.2+si*.2)+'s');anim.setAttribute('repeatCount','indefinite');
      anim.setAttribute('path','M '+ax+' '+ay+' L '+(ax+8)+' '+ay);
      circ.appendChild(anim);svg.appendChild(circ);
    }}
  }});
  const flow=(ARCH.data_flow||[]).slice(0,8);
  if(flow.length)svg.appendChild(e('text',{{x:W/2,y:SH+48,fill:'#374151','font-size':'9',
    'font-style':'italic','text-anchor':'middle'}},trunc('📊 '+flow.join(' → '),120)));
  legend(STAGES.map(s=>({{label:s.label,color:s.col}})));
  setHeader('Data ingestion & processing pipeline');
}}

// ══════════════════════════════════════════════════════════════════════════════════
//  4. INFRASTRUCTURE MAP — component grid with costs
// ══════════════════════════════════════════════════════════════════════════════════
function drawInfra(){{
  svg.innerHTML='';addDefs();
  const costs=COST.azure_costs||[];
  const comps=ARCH.components||[];
  const items=[];
  comps.forEach(c=>{{
    let mo=0;
    const sn=(c.azure_service||'').toLowerCase();
    costs.forEach(cc=>{{const cn=(cc.service||'').toLowerCase();
      if(cn.includes(sn.slice(0,7))||sn.includes(cn.slice(0,7)))mo=cc.monthly_cost||0;}});
    items.push({{...c,monthly:mo}});
  }});
  costs.forEach(cc=>{{
    const cs=(cc.service||'').toLowerCase();
    const dup=items.some(i=>{{const s=(i.azure_service||'').toLowerCase();
      return s.includes(cs.slice(0,7))||cs.includes(s.slice(0,7));}});
    if(!dup&&cc.service)items.push({{name:cc.service,azure_service:cc.service,monthly:cc.monthly_cost||0}});
  }});
  if(!items.length){{
    ['Azure App Service','Azure API Management','Azure SQL Database',
     'Azure Blob Storage','Azure Monitor','Azure Key Vault','Azure DevOps','Azure AD']
     .forEach(s=>items.push({{name:s,azure_service:s,monthly:0}}));
  }}
  const W=setSvg(860,600);
  const CW=170,CH=90,GAP=10;
  const COLS=Math.max(1,Math.floor((W-20)/(CW+GAP)));
  const ROWS=Math.ceil(items.length/COLS);
  const TH=ROWS*(CH+GAP)+80;
  svg.setAttribute('height',TH);svg.setAttribute('viewBox','0 0 '+W+' '+TH);
  svg.appendChild(e('text',{{x:W/2,y:24,fill:'#e2e8f0','font-size':'14','font-weight':'800',
    'text-anchor':'middle'}},'☁️ Azure Infrastructure Map'));
  svg.appendChild(e('text',{{x:W/2,y:42,fill:'#64748b','font-size':'10','text-anchor':'middle'}}
    ,'Est. $'+COST.total_monthly+'/mo total · '+items.length+' services'));
  items.forEach((item,i)=>{{
    const ci=i%COLS,ri=Math.floor(i/COLS);
    const rowItems=Math.min(items.length-ri*COLS,COLS);
    const rowW=rowItems*(CW+GAP)-GAP;
    const rowX=(W-rowW)/2;
    const x=rowX+ci*(CW+GAP),y=54+ri*(CH+GAP);
    const t=getTier(item);
    const zn=ZONES.find(z=>z.id===t)||ZONES[2];
    svg.appendChild(e('rect',{{x:x+2,y:y+2,width:CW,height:CH,rx:9,fill:'rgba(0,0,0,.35)'}}));
    const card=e('rect',{{x,y,width:CW,height:CH,rx:9,
      fill:'rgba('+rgb(zn.col)+',.11)',stroke:zn.col,'stroke-width':1}});
    svg.appendChild(card);
    svg.appendChild(e('rect',{{x,y,width:CW,height:3,rx:2,fill:zn.col,opacity:'.9'}}));
    svg.appendChild(e('text',{{x:x+20,y:y+40,fill:zn.col,'font-size':'18','text-anchor':'middle'}}
      ,getIcon(item)));
    svg.appendChild(e('text',{{x:x+35,y:y+24,fill:'#e2e8f0','font-size':'11','font-weight':'700'}}
      ,trunc(item.name||'',17)));
    svg.appendChild(e('text',{{x:x+35,y:y+38,fill:zn.col,'font-size':'8',opacity:'.9'}}
      ,trunc(item.azure_service||'',22)));
    const svcs=item.services||[];
    if(svcs[0])svg.appendChild(e('text',{{x:x+35,y:y+50,fill:'#475569','font-size':'8'}}
      ,trunc(String(svcs[0]),24)));
    svg.appendChild(e('circle',{{cx:x+12,cy:y+CH-10,r:4,fill:zn.col,opacity:'.7'}}));
    if(item.monthly>0){{
      svg.appendChild(e('rect',{{x:x+CW-62,y:y+CH-20,width:58,height:16,rx:8,
        fill:'rgba(255,209,102,.12)',stroke:'#fbbf24','stroke-width':1}}));
      svg.appendChild(e('text',{{x:x+CW-33,y:y+CH-8,fill:'#fbbf24','font-size':'9','font-weight':'700',
        'text-anchor':'middle'}},'$'+item.monthly+'/mo'));
    }}
  }});
  legend(ZONES.map(z=>({{label:z.label,color:z.col}})));
  setHeader('Azure services · estimated monthly costs · '+items.length+' components');
}}

// ══════════════════════════════════════════════════════════════════════════════════
//  5. SECURITY ARCHITECTURE — defence-in-depth layers
// ══════════════════════════════════════════════════════════════════════════════════
function drawSecurity(){{
  svg.innerHTML='';addDefs();
  const W=setSvg(860,620);const TH=620;
  svg.setAttribute('height',TH);svg.setAttribute('viewBox','0 0 '+W+' '+TH);
  const secItems=ARCH.security||[];
  const comps=ARCH.components||[];
  const LAYERS=[
    {{id:'net',  label:'🌐 Internet / Network Perimeter', col:'#6b7280',y:10,h:72,
      match:c=>{{const n=(c.name||'').toLowerCase(),s=(c.azure_service||'').toLowerCase();
        return n.includes('cdn')||n.includes('front door')||s.includes('front door')||n.includes('user')||n.includes('external');}} }},
    {{id:'dmz',  label:'🛡️ WAF / DDoS / Edge Protection', col:'#ef4444',y:90,h:72,
      match:c=>{{const n=(c.name||'').toLowerCase(),s=(c.azure_service||'').toLowerCase();
        return n.includes('firewall')||n.includes('waf')||n.includes('ddos')||s.includes('ddos')||s.includes('firewall');}} }},
    {{id:'pres', label:'📱 Presentation & API Layer',      col:'#0078d4',y:170,h:80,
      match:c=>getTier(c)==='presentation'&&!((c.name||'').toLowerCase().includes('front door')) }},
    {{id:'app',  label:'⚙️ Application & Business Logic',  col:'#00bcf2',y:258,h:80,
      match:c=>getTier(c)==='application' }},
    {{id:'ai',   label:'🤖 AI & Intelligence Layer',       col:'#a855f7',y:346,h:72,
      match:c=>getTier(c)==='ai' }},
    {{id:'data', label:'💾 Data Zone (Encrypted at Rest)', col:'#22c55e',y:426,h:72,
      match:c=>getTier(c)==='data' }},
    {{id:'iam',  label:'🔑 Identity & Access Management',  col:'#f59e0b',y:506,h:72,
      match:c=>{{const n=(c.name||'').toLowerCase(),t=getTier(c);
        return t==='security'||n.includes('auth')||n.includes('ad')||n.includes('entra');}} }},
  ];
  LAYERS.forEach(layer=>{{
    const lx=18,lw=W-36;
    svg.appendChild(e('rect',{{x:lx,y:layer.y,width:lw,height:layer.h,rx:8,
      fill:'rgba('+rgb(layer.col)+',.07)',stroke:layer.col,'stroke-width':1.5,'stroke-dasharray':'6,4'}}));
    svg.appendChild(e('rect',{{x:lx+8,y:layer.y+4,width:245,height:22,rx:11,
      fill:'rgba('+rgb(layer.col)+',.18)'}}));
    svg.appendChild(e('text',{{x:lx+16,y:layer.y+19,fill:layer.col,'font-size':'11','font-weight':'700'}}
      ,layer.label));
    const lcomps=comps.filter(layer.match);
    const CW2=145,CH2=layer.h-22;
    lcomps.slice(0,4).forEach((c,ci)=>{{
      const cx=lx+260+ci*(CW2+8),cy=layer.y+10;
      svg.appendChild(e('rect',{{x:cx,y:cy,width:CW2,height:CH2,rx:6,
        fill:'rgba('+rgb(layer.col)+',.15)',stroke:layer.col,'stroke-width':1}}));
      svg.appendChild(e('text',{{x:cx+14,y:cy+CH2/2-4,fill:layer.col,'font-size':'16'}}
        ,getIcon(c)));
      svg.appendChild(e('text',{{x:cx+34,y:cy+CH2/2-4,fill:'#e2e8f0','font-size':'10','font-weight':'600'}}
        ,trunc(c.name||'',15)));
      svg.appendChild(e('text',{{x:cx+34,y:cy+CH2/2+10,fill:layer.col,'font-size':'8',opacity:'.9'}}
        ,trunc(c.azure_service||'',18)));
    }});
    if(layer.id==='iam'&&secItems.length){{
      let scY=layer.y+8;
      secItems.slice(0,5).forEach(s=>{{
        svg.appendChild(e('text',{{x:W-28,y:scY,fill:'#f59e0b','font-size':'9',
          'text-anchor':'end'}},'• '+trunc(String(s),30)));
        scY+=14;
      }});
    }}
  }});
  LAYERS.forEach((layer,li)=>{{
    if(li<LAYERS.length-1){{
      const ay1=layer.y+layer.h,ay2=LAYERS[li+1].y;
      if(ay2>ay1)svg.appendChild(e('line',{{x1:90,y1:ay1,x2:90,y2:ay2-2,
        stroke:'#374151','stroke-width':1.5,'stroke-dasharray':'3,2','marker-end':'url(#arr)'}}));
    }}
  }});
  svg.appendChild(e('rect',{{x:W-220,y:12,width:200,height:72,rx:9,
    fill:'rgba(245,158,11,.1)',stroke:'#f59e0b','stroke-width':1}}));
  svg.appendChild(e('text',{{x:W-120,y:32,fill:'#f59e0b','font-size':'11','font-weight':'700',
    'text-anchor':'middle'}},'🛡️ Security Posture'));
  svg.appendChild(e('text',{{x:W-120,y:50,fill:'#94a3b8','font-size':'10','text-anchor':'middle'}}
    ,secItems.length?secItems.length+' controls defined':'Well-Architected'));
  if(ARCH.availability)svg.appendChild(e('text',{{x:W-120,y:66,fill:'#64748b','font-size':'9',
    'text-anchor':'middle'}},trunc(ARCH.availability,32)));
  legend(LAYERS.map(l=>({{label:l.label,color:l.col}})));
  setHeader('Security architecture · defence-in-depth · '+secItems.length+' controls');
}}

// ══════════════════════════════════════════════════════════════════════════════════
//  MERMAID DIAGRAM RENDERING
// ══════════════════════════════════════════════════════════════════════════════════
const mmdRendered={{}};

async function showMermaid(key){{
  document.getElementById('wrap').style.display='none';
  const ma=document.getElementById('mermaid-area');
  ma.style.display='block';
  const spinner=document.getElementById('mmd-spinner');
  const rnd=document.getElementById('mmd-render');

  const code=MMD[key]||'';
  if(!code){{
    spinner.style.display='none';
    rnd.innerHTML='<div id="mmd-err">No AI-generated diagram available for this type.\nRun the pipeline first.</div>';
    return;
  }}
  if(!_mermaidOk()){{
    spinner.style.display='none';
    rnd.innerHTML='<div id="mmd-err">⚠ Mermaid library unavailable (CDN may be blocked).\n\nRaw diagram code:\n\n'+
      '<pre style="font-size:9px;white-space:pre-wrap">'+code.replace(/</g,'&lt;')+'</pre></div>';
    return;
  }}
  if(mmdRendered[key]){{
    spinner.style.display='none';
    rnd.innerHTML=mmdRendered[key];
    return;
  }}
  spinner.style.display='block';
  rnd.innerHTML='';
  let lastErr;
  for(let attempt=0;attempt<4;attempt++){{
    if(attempt>0)await new Promise(r=>setTimeout(r,400*attempt));
    try{{
      const {{svg:svgStr}}=await mermaid.render('mmd_'+key+'_'+attempt+'_'+Date.now(),code);
      mmdRendered[key]=svgStr;
      spinner.style.display='none';
      rnd.innerHTML=svgStr;
      return;
    }}catch(err){{lastErr=err;}}
  }}
  spinner.style.display='none';
  rnd.innerHTML='<div id="mmd-err">⚠ Diagram render error:\n'+
    (lastErr&&lastErr.message?lastErr.message:String(lastErr))+'\n\n'+
    '<details><summary>Raw code</summary><pre style="font-size:9px;white-space:pre-wrap">'+
    code.replace(/</g,'&lt;')+'</pre></details></div>';
}}

// ══════════════════════════════════════════════════════════════════════════════════
//  SELECTOR, LEGEND, EXPORT
// ══════════════════════════════════════════════════════════════════════════════════
let _cur='solution';

function show(type,btn){{
  document.querySelectorAll('.sb').forEach(b=>b.classList.remove('on'));
  if(btn)btn.classList.add('on');
  _cur=type;
  if(type.startsWith('mmd_')){{
    showMermaid(type.replace('mmd_',''));
  }}else{{
    document.getElementById('wrap').style.display='block';
    document.getElementById('mermaid-area').style.display='none';
    hideTip();
    svg=document.getElementById('asvg');   // always refresh reference
    if(!svg)return;
    try{{
      if(type==='solution')drawSolution();
      else if(type==='workflow')drawWorkflow();
      else if(type==='dataflow')drawDataflow();
      else if(type==='infra')drawInfra();
      else if(type==='security')drawSecurity();
    }}catch(err){{
      console.error('[ECI] draw error:',err);
      try{{svg.innerHTML='<text x="50%" y="50%" fill="#ef4444" font-size="13" text-anchor="middle">⚠ '+String(err).slice(0,90)+'</text>';}}catch(e2){{}}
    }}
  }}
}}

function doExport(){{
  if(_cur.startsWith('mmd_')){{
    const svgEl=document.querySelector('#mmd-render svg');
    if(!svgEl)return;
    const blob=new Blob([new XMLSerializer().serializeToString(svgEl)],{{type:'image/svg+xml'}});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download='ECI_'+_cur+'.svg';a.click();
  }}else{{
    const svgEl=document.getElementById('asvg');
    if(!svgEl)return;
    const blob=new Blob([new XMLSerializer().serializeToString(svgEl)],{{type:'image/svg+xml'}});
    const a=document.createElement('a');a.href=URL.createObjectURL(blob);
    a.download='ECI_'+_cur+'_architecture.svg';a.click();
  }}
}}

function legend(items){{
  const lg=document.getElementById('leg');lg.innerHTML='';
  items.forEach(it=>{{
    const d=document.createElement('div');d.className='li';
    d.innerHTML='<div class="ld" style="background:'+it.color+'"></div><span>'+it.label+'</span>';
    lg.appendChild(d);
  }});
}}

// ══════════════════════════════════════════════════════════════════════
//  CORE INIT — resolves svg lazily, retries if DOM isn't ready yet
// ══════════════════════════════════════════════════════════════════════
function _init(){{
  // Re-resolve every call so stale null is never a problem
  svg = document.getElementById('asvg');
  if(!svg){{
    // DOM not ready — retry in 120 ms (happens on first Streamlit render)
    setTimeout(_init, 120);
    return;
  }}
  try{{
    setHeader(ARCH.pattern||'Azure Solution Architecture');
    drawSolution();
  }}catch(err){{
    console.error('[ECI Arch] draw error:', err);
    // Show a human-readable error inside the SVG canvas
    try{{
      const W=880, H=240;
      svg.setAttribute('width',W);
      svg.setAttribute('height',H);
      svg.setAttribute('viewBox','0 0 '+W+' '+H);
      svg.innerHTML=
        '<rect width="'+W+'" height="'+H+'" fill="#0a0e1a"/>'+
        '<rect x="20" y="20" width="'+(W-40)+'" height="'+(H-40)+'" rx="12"'+
        ' fill="rgba(239,68,68,.1)" stroke="#ef4444" stroke-width="1.5"/>'+
        '<text x="'+(W/2)+'" y="76" fill="#ef4444" font-size="15" font-weight="700"'+
        ' text-anchor="middle" font-family="Segoe UI,Arial,sans-serif">⚠\ufe0f Diagram Render Error</text>'+
        '<text x="'+(W/2)+'" y="108" fill="#94a3b8" font-size="11"'+
        ' text-anchor="middle" font-family="Segoe UI,Arial,sans-serif">'+
        String(err).slice(0,110).replace(/[<>&"]/g,c=>({{\'<\':\'&lt;\',\'>\':\'&gt;\',\'&\':\'&amp;\',\'"\':\'&quot;\'}}[c]||c))+
        '</text>'+
        '<text x="'+(W/2)+'" y="140" fill="#64748b" font-size="10"'+
        ' text-anchor="middle" font-family="Segoe UI,Arial,sans-serif">'+
        'Click the Render button above to retry.</text>';
    }}catch(e2){{console.error('[ECI Arch] error-handler crash:',e2);}}
  }}
}}

// ══════════════════════════════════════════════════════════════════════
//  RENDER BUTTON — always force-redraw regardless of prior state
// ══════════════════════════════════════════════════════════════════════
window.forceRender=function(type){{
  svg=document.getElementById('asvg');
  show(type||_cur||'solution', null);
  const btn=document.getElementById('renderBtn');
  if(btn){{btn.textContent='\u2705 Done';setTimeout(()=>{{btn.textContent='\U0001F504 Render';}},2000);}}
}};

// ══════════════════════════════════════════════════════════════════════
//  STARTUP — fire across multiple timing paths
// ══════════════════════════════════════════════════════════════════════
// Path 1: script already at end-of-body, DOM usually ready
setTimeout(_init, 0);
// Path 2: iframe load event (fires after Streamlit injects the srcdoc)
window.addEventListener('load', function(){{ setTimeout(_init, 50); }});
// Path 3: resize fires when Streamlit expander opens — always re-draw
window.addEventListener('resize', function(){{
  if(!_cur.startsWith('mmd_')){{ svg=document.getElementById('asvg'); show(_cur,null); }}
}});
// Path 4: 1 s safety net catches edge cases (slow machines, blocked CDN)
setTimeout(function(){{
  if(svg&&svg.innerHTML.trim()===''){{ _init(); }}
}}, 1000);
</script>
</body></html>"""

    # ── Interactive Diagrams (4 tabs) ────────────────────────────────────
    st.markdown("### 📊 Interactive Diagrams")
    _itabs = st.tabs([
        "🏗️ Solution Architecture",
        "💰 ROI & Business Case",
        "🚀 Transformation Journey",
        "🔒 Security Layers",
    ])
    # Pre-render instant placeholders so clicking any sub-tab never shows blank
    _itp = {}
    for _ii, _ilbl in enumerate(["🏗️ Solution Architecture", "💰 ROI & Business Case",
                                  "🚀 Transformation Journey", "🔒 Security Layers"]):
        with _itabs[_ii]:
            _itp[_ii] = st.empty()
            _itp[_ii].markdown(
                f'<div style="padding:18px 4px 0;color:#475569;font-size:.8rem;font-style:italic">'
                f'⏳ {_ilbl} — loading…</div>',
                unsafe_allow_html=True,
            )
    with _itabs[0]:
        _itp[0].empty()
        _plotly_arch_diagram(ar, se)
    with _itabs[1]:
        _itp[1].empty()
        _render_roi_builder(se, te, ce)
    with _itabs[2]:
        _itp[2].empty()
        _render_transformation_journey(se, te, ar)
    with _itabs[3]:
        _itp[3].empty()
        _plotly_security(ar)

    # ── Component cards ──────────────────────────────────────────────────
    comps = safe_list(ar.get("components"))
    if comps:
        st.markdown("### 🧩 Components")
        arch_cols = st.columns(3)
        for i, c in enumerate(comps):
            c = safe_dict(c)
            with arch_cols[i % 3]:
                svcs = "".join(
                    "<li style='font-size:.78rem;color:#94a3b8;margin:2px 0'>" + safe_str(s) + "</li>"
                    for s in safe_list(c.get("services"))
                )
                st.markdown(
                    '<div class="ac"><div class="acn">' + safe_str(c.get("name")) +
                    '</div><div class="act">' + safe_str(c.get("azure_service")) +
                    '</div><ul class="acs">' + svcs + '</ul></div>',
                    unsafe_allow_html=True,
                )

    # ── Data flow strip ──────────────────────────────────────────────────
    df = safe_list(ar.get("data_flow"))
    if df:
        flow_str = " → ".join(safe_str(x) for x in df)
        st.markdown(
            '<div class="dfv" style="font-size:.8rem;padding:10px 14px;'
            'background:rgba(0,120,212,.08);border-radius:8px;color:#94a3b8;'
            'border-left:3px solid #0078D4;margin:8px 0">' + flow_str + '</div>',
            unsafe_allow_html=True,
        )

    # ── Security controls ────────────────────────────────────────────────
    sec_items = safe_list(ar.get("security"))
    if sec_items:
        with st.expander("🔒 Security Controls (" + str(len(sec_items)) + ")", expanded=False):
            for s in sec_items:
                st.markdown("- " + safe_str(s))

    # ── Architecture metadata ────────────────────────────────────────────
    scalability  = safe_str(ar.get("scalability", ""))
    availability = safe_str(ar.get("availability", ""))
    if scalability or availability:
        with st.expander("📐 Scalability & Availability", expanded=False):
            if scalability:
                st.markdown("**Scalability:** " + scalability)
            if availability:
                st.markdown("**Availability:** " + availability)


# ═══════════════════════════════════════════════════════════════════════
#  GRAPHVIZ DOT DIAGRAM GENERATORS
# ═══════════════════════════════════════════════════════════════════════

def render_dot_to_svg(dot_string):
    """Render a DOT string to SVG bytes using the graphviz library.

    Returns SVG bytes or None if graphviz system binary is not available.
    """
    if not HAS_GRAPHVIZ or not dot_string:
        return None
    try:
        src = gv_lib.Source(dot_string)
        svg_bytes = src.pipe(format="svg")
        return svg_bytes
    except Exception:
        return None


def render_dot_to_png(dot_string):
    """Render a DOT string to PNG bytes using the graphviz library.

    Returns PNG bytes or None if graphviz system binary is not available.
    """
    if not HAS_GRAPHVIZ or not dot_string:
        return None
    try:
        src = gv_lib.Source(dot_string)
        png_bytes = src.pipe(format="png")
        return png_bytes
    except Exception:
        return None


def render_dot_to_html(dot_string):
    """Create a self-contained HTML file that renders DOT using Viz.js.

    This always works — no system graphviz binary needed. The user downloads
    an HTML file they can open in any browser to see the rendered diagram.
    """
    if not dot_string:
        return None
    escaped = dot_string.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    html = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>ECI Architecture Diagram</title>
<style>body{background:#0a0e1a;margin:0;display:flex;justify-content:center;align-items:center;min-height:100vh;font-family:sans-serif}
#msg{color:#94a3b8;font-size:1.2rem}svg{max-width:95vw}
.toolbar{position:fixed;top:10px;right:10px;display:flex;gap:8px;z-index:10}
.toolbar button{background:#1B3A5C;color:white;border:none;padding:8px 16px;border-radius:6px;cursor:pointer;font-size:14px}
.toolbar button:hover{background:#00b4d8}</style>
<script src="https://unpkg.com/@viz-js/viz@3.2.4/lib/viz-standalone.js"></script>
</head><body>
<div class="toolbar"><button onclick="downloadSVG()">Download SVG</button><button onclick="downloadPNG()">Download PNG</button></div>
<div id="graph"><p id="msg">Rendering diagram...</p></div>
<script>
const dot = `""" + escaped + """`;
Viz.instance().then(viz => {
  const svg = viz.renderSVGElement(dot);
  document.getElementById('graph').innerHTML = '';
  document.getElementById('graph').appendChild(svg);
}).catch(e => { document.getElementById('msg').textContent = 'Render error: ' + e; });
function downloadSVG(){
  const svg = document.querySelector('#graph svg');
  if(!svg) return;
  const blob = new Blob([new XMLSerializer().serializeToString(svg)], {type:'image/svg+xml'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
  a.download = 'ECI_Architecture.svg'; a.click();
}
function downloadPNG(){
  const svg = document.querySelector('#graph svg');
  if(!svg) return;
  const svgData = new XMLSerializer().serializeToString(svg);
  const canvas = document.createElement('canvas');
  const ctx = canvas.getContext('2d');
  const img = new Image();
  img.onload = function(){
    canvas.width = img.width * 2; canvas.height = img.height * 2;
    ctx.scale(2, 2); ctx.drawImage(img, 0, 0);
    canvas.toBlob(function(blob){
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
      a.download = 'ECI_Architecture.png'; a.click();
    });
  };
  img.src = 'data:image/svg+xml;base64,' + btoa(unescape(encodeURIComponent(svgData)));
}
</script></body></html>"""
    return html.encode("utf-8")


# ═══════════════════════════════════════════════════════════════════════
#  3D ARCHITECTURE FLY-THROUGH (Three.js)
# ═══════════════════════════════════════════════════════════════════════

def generate_3d_flythrough_html(ar, ce, narration_map=None):
    """Return a self-contained HTML string with an interactive Three.js 3D
    architecture fly-through.  Uses ES-module importmap so OrbitControls loads
    reliably in every modern browser (Chrome 89+, Firefox 108+, Safari 16.4+).
    Accepts an optional narration_map dict {component_name: narration_text}.
    """
    import json as _json

    arch = safe_dict(ar)
    cost = safe_dict(ce)
    components = safe_list(arch.get("components"))
    data_flow  = safe_list(arch.get("data_flow"))
    pattern    = safe_str(arch.get("pattern", "Solution Architecture"))

    _type_to_tier = {
        "web app": "presentation", "frontend": "presentation",
        "ui": "presentation", "cdn": "presentation", "portal": "presentation",
        "integration": "application", "microservices": "application",
        "api": "application", "messaging": "application",
        "backend": "application", "compute": "application",
        "function": "application", "logic": "application",
        "app service": "application",
        "database": "data", "storage": "data", "data": "data",
        "cache": "data", "redis": "data", "cosmos": "data", "sql": "data",
        "identity": "security", "security": "security",
        "auth": "security", "firewall": "security", "keyvault": "security",
        "key vault": "security",
        "operations": "operations", "devops": "operations",
        "monitoring": "operations", "logging": "operations",
        "insights": "operations",
    }

    cost_map = {}
    for ac in safe_list(cost.get("azure_costs")):
        ac = safe_dict(ac)
        svc = safe_str(ac.get("service", "")).lower()
        monthly = safe_int(ac.get("monthly_cost", 0))
        if svc:
            cost_map[svc] = monthly

    tier_y = {"presentation": 9, "application": 4, "data": 0, "security": -4, "operations": -8}

    tier_buckets = {t: [] for t in tier_y}
    for comp in components:
        comp = safe_dict(comp)
        ctype       = safe_str(comp.get("type", "")).lower()
        cname_lower = safe_str(comp.get("name", "")).lower()
        tier = _type_to_tier.get(ctype)
        if tier is None:
            for kw, t in _type_to_tier.items():
                if kw in cname_lower:
                    tier = t
                    break
        tier_buckets[tier or "application"].append(comp)

    components_3d = []
    for tier_name, comps_in_tier in tier_buckets.items():
        n = len(comps_in_tier)
        if n == 0:
            continue
        y = tier_y[tier_name]
        for idx, comp in enumerate(comps_in_tier):
            comp      = safe_dict(comp)
            name      = safe_str(comp.get("name", "Component"))
            azure_svc = safe_str(comp.get("azure_service", ""))
            services  = [safe_str(s) for s in safe_list(comp.get("services", []))[:5]]
            x = (idx - (n - 1) / 2.0) * 5.5
            z = (idx % 2) * 2.5
            monthly = 0
            nl, al = name.lower(), azure_svc.lower()
            for ck, cv in cost_map.items():
                if ck in nl or ck in al or nl in ck or al in ck:
                    monthly = cv
                    break
            components_3d.append({
                "name": name, "azure_service": azure_svc, "services": services,
                "tier": tier_name, "x": round(x, 2), "y": y, "z": round(z, 2),
                "monthly_cost": monthly,
            })

    # Guarantee a non-empty scene even before the AI runs
    if not components_3d:
        _demo = [
            ("Web App",     "Azure App Service",   "presentation", ["Hosting","Auto-scale"]),
            ("API Gateway", "Azure API Mgmt",      "application",  ["Rate-limit","Auth"]),
            ("Database",    "Azure SQL",           "data",         ["Managed DB","Backups"]),
            ("Cache",       "Azure Redis Cache",   "data",         ["In-memory cache"]),
            ("Identity",    "Azure AD B2C",        "security",     ["SSO","MFA"]),
            ("Monitoring",  "Azure Monitor",       "operations",   ["Alerts","Dashboards"]),
        ]
        _tc = {}
        for nm, svc, tier, svcs in _demo:
            i = _tc.get(tier, 0); _tc[tier] = i + 1
            components_3d.append({"name": nm, "azure_service": svc, "services": svcs,
                                   "tier": tier, "x": round((i - 0.5) * 5.5, 2),
                                   "y": tier_y[tier], "z": 0.0, "monthly_cost": 0})

    total_monthly = safe_int(cost.get("total_monthly_cost", 0))
    pattern_js = (pattern
                  .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                  .replace('"', "&quot;").replace("\n", " "))
    comp_json = _json.dumps(components_3d)
    flow_json = _json.dumps([safe_str(f) for f in data_flow])
    narr_json = _json.dumps(narration_map or {})

    # Build component list sidebar HTML
    sidebar_items = ""
    for idx, c in enumerate(components_3d):
        tier_colors_css = {
            "presentation": "#00b4d8", "application": "#1b5c8c",
            "data": "#00d4aa", "security": "#7b61ff", "operations": "#ffd166"
        }
        col = tier_colors_css.get(c.get("tier", ""), "#94a3b8")
        name_esc = (c.get("name", "") or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        svc_esc = (c.get("azure_service", "") or "").replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
        sidebar_items += (
            '<div class="cli" id="cli_' + str(idx) + '" onclick="window._3d.focusComp(' + str(idx) + ')" '
            + 'style="border-left:3px solid ' + col + '">'
            + '<div class="cli-name">' + name_esc + '</div>'
            + '<div class="cli-svc">' + svc_esc + '</div>'
            + '</div>'
        )

    html = (
        """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>ECI 3D Architecture</title>
<script type="importmap">
{"imports":{
  "three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js",
  "three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"
}}
</script>
<style>
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:100%;height:100%;overflow:hidden;background:#040810;
  font-family:'Segoe UI',Arial,sans-serif}
#layout{display:flex;width:100%;height:100%;overflow:hidden}
#sidebar{width:210px;min-width:180px;max-width:240px;background:rgba(4,8,16,.92);
  border-right:1px solid #1e2a4a;display:flex;flex-direction:column;overflow:hidden;flex-shrink:0}
#sidebar-hdr{padding:10px 12px 6px;font-size:.6rem;color:#64748b;
  text-transform:uppercase;letter-spacing:1px;border-bottom:1px solid #1e2a4a;flex-shrink:0}
#sidebar-list{overflow-y:auto;flex:1;padding:6px 6px}
#sidebar-list::-webkit-scrollbar{width:4px}
#sidebar-list::-webkit-scrollbar-track{background:#040810}
#sidebar-list::-webkit-scrollbar-thumb{background:#1e2a4a;border-radius:2px}
.cli{padding:7px 9px;margin-bottom:4px;border-radius:6px;cursor:pointer;
  background:rgba(30,42,74,.3);border-left:3px solid #1e2a4a;
  transition:background .2s,border-color .2s}
.cli:hover{background:rgba(0,212,170,.08)}
.cli.active{background:rgba(0,212,170,.12);border-left-color:#00d4aa!important}
.cli.active .cli-name{color:#00d4aa}
.cli-name{font-size:.7rem;color:#e2e8f0;font-weight:600;line-height:1.3;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.cli-svc{font-size:.58rem;color:#64748b;margin-top:2px;
  white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
#main{flex:1;position:relative;overflow:hidden}
#sw{position:absolute;inset:0}
#sw canvas{width:100%!important;height:100%!important;display:block}
#ov{position:absolute;inset:0;pointer-events:none}
#tb{position:absolute;top:10px;left:50%;transform:translateX(-50%);
  background:rgba(4,8,16,.92);border:1px solid #1e2a4a;
  backdrop-filter:blur(12px);border-radius:20px;
  padding:5px 18px;color:#e2e8f0;font-size:.74rem;white-space:nowrap;text-align:center;z-index:5}
.hl{color:#00d4aa;font-weight:700}
#hud{position:absolute;top:52px;right:12px;background:rgba(4,8,16,.97);
  border:1px solid #1e2a4a;border-radius:12px;padding:14px 16px;
  color:#e2e8f0;min-width:220px;max-width:260px;display:none;
  backdrop-filter:blur(12px);pointer-events:all;z-index:10}
#hx{float:right;cursor:pointer;color:#64748b;font-size:.95rem;line-height:1;margin-left:8px}
#hx:hover{color:#e2e8f0}
#hn{font-size:.88rem;font-weight:700;color:#00d4aa;margin-bottom:3px}
#hs{font-size:.68rem;color:#00b4d8;margin-bottom:8px}
.hl2{font-size:.58rem;color:#64748b;text-transform:uppercase;letter-spacing:1px}
#hc{font-size:1.1rem;font-weight:700;color:#ffd166;margin:2px 0 8px;
  font-family:'Courier New',monospace}
#hv{font-size:.7rem;color:#94a3b8;line-height:1.7;margin-top:3px}
#ht{display:inline-block;font-size:.56rem;padding:2px 7px;border-radius:10px;
  margin-top:7px;text-transform:uppercase;letter-spacing:1px}
#tot{position:absolute;bottom:58px;right:12px;background:rgba(4,8,16,.92);
  border:1px solid #1e2a4a;border-radius:10px;padding:7px 12px;text-align:right;z-index:5}
#totl{font-size:.58rem;color:#64748b;text-transform:uppercase;letter-spacing:1px}
#totv{font-size:.95rem;font-weight:700;color:#ffd166;font-family:'Courier New',monospace}
#hint{position:absolute;bottom:56px;left:50%;transform:translateX(-50%);
  color:#475569;font-size:.6rem;white-space:nowrap;z-index:5}
#progbar-wrap{position:absolute;bottom:44px;left:0;right:0;height:4px;
  background:rgba(30,42,74,.5);display:none;z-index:6}
#progbar{height:4px;width:0%;background:#00d4aa;transition:width .1s linear}
#ctrl{position:absolute;bottom:10px;left:50%;transform:translateX(-50%);
  display:flex;gap:6px;pointer-events:all;z-index:10;align-items:center}
.cb{background:rgba(4,8,16,.94);border:1px solid #1e2a4a;color:#94a3b8;
  padding:5px 12px;border-radius:8px;cursor:pointer;font-size:.7rem;
  transition:all .2s;white-space:nowrap}
.cb:hover{border-color:#00d4aa;color:#00d4aa}
.cb.on{background:rgba(0,212,170,.1);border-color:#00d4aa;color:#00d4aa}
#spin{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
  background:#040810;color:#64748b;font-size:.8rem;flex-direction:column;gap:12px;z-index:20}
.sp{width:28px;height:28px;border:3px solid #1e2a4a;border-top-color:#00d4aa;
  border-radius:50%;animation:rot .8s linear infinite}
@keyframes rot{to{transform:rotate(360deg)}}
#nv{position:absolute;top:-130px;left:50%;transform:translateX(-50%);
  background:rgba(4,8,16,.95);border:1px solid #1e2a4a;
  backdrop-filter:blur(12px);border-radius:14px;
  padding:12px 20px;min-width:280px;max-width:380px;text-align:center;
  transition:top .4s cubic-bezier(.16,1,.3,1),opacity .4s;
  opacity:0;pointer-events:none;z-index:15}
#nv.show{opacity:1}
#nvtier{font-size:.56rem;text-transform:uppercase;letter-spacing:1.5px;
  padding:2px 8px;border-radius:8px;display:inline-block;margin-bottom:6px}
#nvname{font-size:.95rem;font-weight:700;color:#e2e8f0;margin-bottom:3px}
#nvservice{font-size:.7rem;color:#00b4d8;margin-bottom:5px}
#nvdesc{font-size:.65rem;color:#94a3b8;line-height:1.5;max-width:340px}
</style></head><body>
<div id="spin"><div class="sp"></div><span>Loading 3D scene&hellip;</span></div>
<div id="layout">
  <div id="sidebar">
    <div id="sidebar-hdr">&#9654; Components (""" + str(len(components_3d)) + """)</div>
    <div id="sidebar-list">""" + sidebar_items + """</div>
  </div>
  <div id="main">
    <div id="sw"></div>
    <div id="ov">
      <div id="tb"><span class="hl">""" + pattern_js + """</span> &nbsp;&middot;&nbsp; 3D Architecture</div>
      <div id="nv">
        <div id="nvtier">TIER</div>
        <div id="nvname">Component</div>
        <div id="nvservice">Azure Service</div>
        <div id="nvdesc"></div>
      </div>
      <div id="hud">
        <span id="hx" onclick="window._3d.closeHUD()">&#10005;</span>
        <div id="hn"></div><div id="hs"></div>
        <div class="hl2">Monthly Infra Cost</div><div id="hc"></div>
        <div class="hl2">Capabilities</div><div id="hv"></div>
        <div id="ht"></div>
      </div>
      <div id="tot"><div id="totl">Total Monthly</div><div id="totv">$""" + str(total_monthly) + """/mo</div></div>
      <div id="hint">Hover canvas to orbit &nbsp;&middot;&nbsp; Scroll outside 3D to navigate page</div>
      <div id="progbar-wrap"><div id="progbar"></div></div>
      <div id="ctrl">
        <button class="cb" id="bfly" onclick="window._3d.toggleFly()">&#9654; Play Tour</button>
        <button class="cb" onclick="window._3d.resetCam()">&#8635; Reset</button>
        <button class="cb" onclick="window._3d.topCam()">&#8859; Top View</button>
        <button class="cb" id="bvoice" onclick="window._3d.toggleVoice()">&#128266; Voice ON</button>
      </div>
    </div>
  </div>
</div>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const COMPS="""
        + comp_json
        + """;
const FLOW="""
        + flow_json
        + """;
const NARR="""
        + narr_json
        + """;
const THEX={presentation:0x00b4d8,application:0x1b5c8c,data:0x00d4aa,security:0x7b61ff,operations:0xffd166};
const TCSS={presentation:'#00b4d8',application:'#1b5c8c',data:'#00d4aa',security:'#7b61ff',operations:'#ffd166'};
const TBG={presentation:'rgba(0,180,216,.12)',application:'rgba(27,92,140,.12)',
           data:'rgba(0,212,170,.12)',security:'rgba(123,97,255,.12)',operations:'rgba(255,209,102,.12)'};

const wrap=document.getElementById('sw');
const W=()=>wrap.clientWidth||window.innerWidth;
const H=()=>wrap.clientHeight||window.innerHeight;
const renderer=new THREE.WebGLRenderer({antialias:true,alpha:false});
renderer.setPixelRatio(Math.min(devicePixelRatio,2));
renderer.setSize(W(),H());
renderer.setClearColor(0x040810,1);
wrap.appendChild(renderer.domElement);

const scene=new THREE.Scene();
scene.background=new THREE.Color(0x040810);
scene.fog=new THREE.FogExp2(0x040810,0.012);

const camera=new THREE.PerspectiveCamera(55,W()/H(),0.1,1000);
camera.position.set(0,20,38);

const controls=new OrbitControls(camera,renderer.domElement);
controls.enableDamping=true; controls.dampingFactor=0.08;
controls.minDistance=4; controls.maxDistance=100;
controls.target.set(0,0,0); controls.update();

// Mouse enter/leave scroll fix
renderer.domElement.addEventListener('mouseenter',()=>{controls.enableZoom=true;});
renderer.domElement.addEventListener('mouseleave',()=>{controls.enableZoom=false;});
controls.enableZoom=false;

// Lights - ambient + directional + 3 point lights
scene.add(new THREE.AmbientLight(0xffffff,0.45));
const dL=new THREE.DirectionalLight(0x00d4aa,1.6); dL.position.set(10,20,15); scene.add(dL);
const pL1=new THREE.PointLight(0x00b4d8,2.0,90); pL1.position.set(-15,12,0); scene.add(pL1);
const pL2=new THREE.PointLight(0x7b61ff,1.6,90); pL2.position.set(15,-4,10); scene.add(pL2);
const pL3=new THREE.PointLight(0xffd166,1.2,70); pL3.position.set(0,-10,-15); scene.add(pL3);

// Grid
scene.add(new THREE.GridHelper(100,50,0x1e2a4a,0x0d1120));

// Starfield
{const g=new THREE.BufferGeometry(),p=new Float32Array(7200);
 for(let i=0;i<p.length;i++)p[i]=(Math.random()-.5)*220;
 g.setAttribute('position',new THREE.BufferAttribute(p,3));
 scene.add(new THREE.Points(g,new THREE.PointsMaterial({color:0x94a3b8,size:.14,transparent:true,opacity:.45})));}

// Tier floor plates + tier label sprites
const tierLabelY={presentation:9,application:4,data:0,security:-4,operations:-8};
const tierNames={presentation:'PRESENTATION',application:'APPLICATION',data:'DATA',security:'SECURITY',operations:'OPERATIONS'};
[...new Set(COMPS.map(c=>c.tier))].forEach(tier=>{
  const tc=COMPS.filter(c=>c.tier===tier); if(!tc.length)return;
  const ty=tc[0].y-1.5, mx=Math.max(...tc.map(c=>Math.abs(c.x)))+5;
  const geo=new THREE.PlaneGeometry(mx*2+4,12);
  const pl=new THREE.Mesh(geo,new THREE.MeshBasicMaterial({color:THEX[tier]||0x1e2a4a,transparent:true,opacity:.06,side:THREE.DoubleSide}));
  pl.rotation.x=-Math.PI/2; pl.position.set(0,ty,2); scene.add(pl);
  const el=new THREE.LineSegments(new THREE.EdgesGeometry(geo),
    new THREE.LineBasicMaterial({color:THEX[tier]||0x1e2a4a,transparent:true,opacity:.2}));
  el.rotation.x=-Math.PI/2; el.position.set(0,ty,2); scene.add(el);
  // Tier label sprite
  const cv=document.createElement('canvas'); cv.width=512; cv.height=64;
  const ctx2=cv.getContext('2d');
  ctx2.font='bold 20px Segoe UI,Arial'; ctx2.textAlign='left';
  ctx2.fillStyle=TCSS[tier]||'#94a3b8';
  ctx2.globalAlpha=0.5;
  ctx2.fillText(tierNames[tier]||tier.toUpperCase(),10,44);
  const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(cv),transparent:true,depthTest:false}));
  sp.scale.set(14,1.8,1);
  sp.position.set(-(mx+1), tc[0].y+0.5, -3);
  scene.add(sp);
});

// Label sprites
function mkLabel(txt,col,sc){
  const cv=document.createElement('canvas'); cv.width=512; cv.height=64;
  const ctx=cv.getContext('2d');
  ctx.font='bold 24px Segoe UI,Arial'; ctx.textAlign='center';
  ctx.fillStyle='#'+col.toString(16).padStart(6,'0');
  ctx.shadowColor='rgba(0,0,0,.8)'; ctx.shadowBlur=6;
  ctx.fillText(txt.length>28?txt.slice(0,26)+'\u2026':txt,256,44);
  const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(cv),transparent:true,depthTest:false}));
  sp.scale.set(7*sc,.88*sc,1); return sp;
}

// Component boxes
const meshes=[], ray=new THREE.Raycaster(), mouse=new THREE.Vector2();
COMPS.forEach((c,i)=>{
  const col=THEX[c.tier]||0x1e2a4a;
  const geo=new THREE.BoxGeometry(3.8,2.0,2.6);
  const mat=new THREE.MeshPhongMaterial({
    color:col,transparent:true,opacity:.75,shininess:120,specular:0x404040,
    emissive:col,emissiveIntensity:0.08
  });
  const mesh=new THREE.Mesh(geo,mat);
  mesh.position.set(c.x,c.y,c.z); mesh.userData={c,i}; scene.add(mesh);
  mesh.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo),
    new THREE.LineBasicMaterial({color:col,transparent:true,opacity:.85})));
  const nl=mkLabel(c.name,col,.75); nl.position.set(c.x,c.y+2.1,c.z); scene.add(nl);
  if(c.azure_service){const sl=mkLabel(c.azure_service,0xaabbcc,.54);sl.position.set(c.x,c.y+1.3,c.z);scene.add(sl);}
  meshes.push(mesh);
});

// Data-flow arcs + flowing particles
function fc(n){const nl=n.toLowerCase();return COMPS.find(c=>c.name.toLowerCase().includes(nl)||nl.includes(c.name.toLowerCase()));}
const arcCurves=[];
for(let i=0;i<FLOW.length-1;i++){
  const a=fc(FLOW[i]),b=fc(FLOW[i+1]); if(!a||!b)continue;
  const pa=new THREE.Vector3(a.x,a.y,a.z),pb=new THREE.Vector3(b.x,b.y,b.z);
  const pm=pa.clone().add(pb).multiplyScalar(.5); pm.y+=Math.abs(a.y-b.y)*.5+2.5;
  const curve=new THREE.QuadraticBezierCurve3(pa,pm,pb);
  const pts=curve.getPoints(40);
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts),
    new THREE.LineBasicMaterial({color:0x00b4d8,transparent:true,opacity:.4})));
  scene.add(new THREE.ArrowHelper(pb.clone().sub(pa).normalize(),pb,0,0x00b4d8,.6,.35));
  // flowing particles (8 per arc)
  const particles=[];
  for(let p=0;p<8;p++){
    const pg=new THREE.SphereGeometry(0.12,6,6);
    const pm2=new THREE.MeshBasicMaterial({color:0x00d4aa,transparent:true,opacity:0.9});
    const dot=new THREE.Mesh(pg,pm2);
    dot.userData.phase=p/8;
    scene.add(dot);
    particles.push(dot);
  }
  arcCurves.push({curve,particles});
}

// Pulse rings
const ringGeo=new THREE.RingGeometry(1.8,2.0,32);
const rings=[0,0.33,0.66].map(phase=>{
  const m=new THREE.Mesh(ringGeo,new THREE.MeshBasicMaterial({color:0x00d4aa,transparent:true,opacity:0,side:THREE.DoubleSide}));
  m.userData.phase=phase;
  m.rotation.x=-Math.PI/2;
  m.visible=false;
  scene.add(m);
  return m;
});
let ringTarget=null;
function activateRings(c){
  ringTarget=new THREE.Vector3(c.x,c.y-1,c.z);
  rings.forEach(r=>{r.visible=true;r.scale.setScalar(0);r.material.opacity=0.8;});
}

// ── Voice — pre-cached, pre-warmed ──────────────────────────────────
let voiceEnabled = true;
let _cachedVoice = null;

function _pickVoice(){
  if(!window.speechSynthesis) return;
  const voices = window.speechSynthesis.getVoices();
  if(!voices.length) return;
  _cachedVoice =
    voices.find(v=>v.lang.startsWith('en')&&(v.name.toLowerCase().includes('female')||v.name.toLowerCase().includes('zira')||v.name.toLowerCase().includes('susan')||v.name.toLowerCase().includes('samantha')))
    ||voices.find(v=>v.lang.startsWith('en-US')||v.lang.startsWith('en-us'))
    ||voices.find(v=>v.lang.startsWith('en'));
}

if(window.speechSynthesis){
  // Cache voice immediately (works in Chrome); also on voiceschanged (Firefox/Safari)
  _pickVoice();
  window.speechSynthesis.addEventListener('voiceschanged', _pickVoice);
  // Pre-warm TTS engine with a silent utterance so first real speech is instant
  setTimeout(()=>{
    const _wu = new SpeechSynthesisUtterance('​');
    _wu.volume = 0; _wu.rate = 2;
    if(_cachedVoice) _wu.voice = _cachedVoice;
    window.speechSynthesis.speak(_wu);
  }, 800);
}

function speak(text){
  if(!voiceEnabled||!window.speechSynthesis||!text) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.rate = 0.92; u.pitch = 1.05; u.volume = 1.0;
  if(!_cachedVoice) _pickVoice();  // lazy retry if voiceschanged was slow
  if(_cachedVoice) u.voice = _cachedVoice;
  window.speechSynthesis.speak(u);
}

// Estimate how long speech will take (2.5 words/sec at rate 0.92)
function _speechMs(text){
  if(!text||!voiceEnabled||!window.speechSynthesis) return 0;
  return Math.max(2000, Math.ceil(text.trim().split(/\s+/).length / 2.3) * 1000);
}

function buildNarration(c){
  if(NARR[c.name])return NARR[c.name];
  const intros={
    presentation:"In the presentation tier,",application:"At the application layer,",
    data:"In the data tier,",security:"For security and identity,",operations:"For monitoring and operations,"
  };
  let t=(intros[c.tier]||"Next,")+" "+c.name;
  if(c.azure_service)t+=" is powered by "+c.azure_service;
  if(c.services&&c.services.length)t+=". Key capabilities include "+c.services.slice(0,3).join(", ");
  if(c.monthly_cost>0)t+=". Estimated at $"+c.monthly_cost.toLocaleString()+" per month";
  return t+".";
}

// Now Visiting banner
let nvTimer=null;
function showNowVisiting(c){
  const nv=document.getElementById('nv');
  const tc=TCSS[c.tier]||'#94a3b8';
  const tbg=TBG[c.tier]||'transparent';
  document.getElementById('nvtier').textContent=(c.tier||'').toUpperCase();
  document.getElementById('nvtier').style.cssText='background:'+tbg+';color:'+tc+';border:1px solid '+tc;
  document.getElementById('nvname').textContent=c.name;
  document.getElementById('nvservice').textContent=c.azure_service||'';
  const desc=c.services&&c.services.length?c.services.slice(0,2).join(' \u00b7 '):'';
  document.getElementById('nvdesc').textContent=desc;
  nv.style.top='68px'; nv.classList.add('show');
  if(nvTimer)clearTimeout(nvTimer);
  nvTimer=setTimeout(()=>{nv.style.top='-130px';nv.classList.remove('show');},4000);
}
function hideNowVisiting(){
  const nv=document.getElementById('nv');
  nv.style.top='-130px'; nv.classList.remove('show');
  if(nvTimer){clearTimeout(nvTimer);nvTimer=null;}
}

// HUD
let sel=null;
function showHUD(c){
  document.getElementById('hn').textContent=c.name;
  document.getElementById('hs').textContent=c.azure_service||'';
  document.getElementById('hc').textContent=c.monthly_cost>0?'$'+c.monthly_cost.toLocaleString()+'/mo':'Included in estimate';
  document.getElementById('hv').innerHTML=c.services.length?c.services.map(s=>'&#8226; '+s).join('<br>'):'N/A';
  const te=document.getElementById('ht'),tc=TCSS[c.tier]||'#94a3b8';
  te.textContent=(c.tier||'').toUpperCase();
  te.style.cssText='background:'+(TBG[c.tier]||'transparent')+';color:'+tc+';border:1px solid '+tc;
  document.getElementById('hud').style.display='block';
}
function closeHUD(){document.getElementById('hud').style.display='none';}

// Visit component during fly-through
let lastCompIdx=-1;
function visitComp(i){
  const c=COMPS[i]; if(!c)return;
  lastCompIdx=i+1;
  showNowVisiting(c);
  activateRings(c);
  if(voiceEnabled)speak(buildNarration(c));
  document.querySelectorAll('.cli').forEach(el=>el.classList.remove('active'));
  const el=document.getElementById('cli_'+i);
  if(el){el.classList.add('active');el.scrollIntoView({block:'nearest',behavior:'smooth'});}
}

// Click ray-cast
let zT=null,zL=null,doZ=false;
renderer.domElement.addEventListener('click',e=>{
  const r=renderer.domElement.getBoundingClientRect();
  mouse.x=((e.clientX-r.left)/r.width)*2-1;
  mouse.y=-((e.clientY-r.top)/r.height)*2+1;
  ray.setFromCamera(mouse,camera);
  const hits=ray.intersectObjects(meshes);
  if(hits.length){
    const m=hits[0].object;
    if(sel)sel.material.emissive.setIntensity?sel.material.emissiveIntensity=0.08:null;
    sel=m; m.material.emissiveIntensity=0.35;
    showHUD(m.userData.c);
    if(fly)stopFly();
    activateRings(m.userData.c);
    zT=new THREE.Vector3(m.position.x+9,m.position.y+6,m.position.z+14);
    zL=m.position.clone(); doZ=true;
    // highlight sidebar
    document.querySelectorAll('.cli').forEach(el=>el.classList.remove('active'));
    const sEl=document.getElementById('cli_'+m.userData.i);
    if(sEl){sEl.classList.add('active');sEl.scrollIntoView({block:'nearest',behavior:'smooth'});}
  }else{
    if(sel){sel.material.emissiveIntensity=0.08;sel=null;}
    doZ=false;closeHUD();
  }
});

// Focus component from sidebar
function focusComp(i){
  const c=COMPS[i]; if(!c)return;
  if(fly)stopFly();
  zT=new THREE.Vector3(c.x+9,c.y+6,c.z+14);
  zL=new THREE.Vector3(c.x,c.y,c.z); doZ=true;
  showHUD(c);
  activateRings(c);
  if(sel)sel.material.emissiveIntensity=0.08;
  sel=meshes[i]; if(sel)sel.material.emissiveIntensity=0.35;
  document.querySelectorAll('.cli').forEach(el=>el.classList.remove('active'));
  const el=document.getElementById('cli_'+i);
  if(el)el.classList.add('active');
  if(voiceEnabled)speak(buildNarration(c));
}

// Camera presets
const DP=new THREE.Vector3(0,20,38),DT=new THREE.Vector3(0,0,0);
function resetCam(){doZ=false;stopFly();controls.enabled=true;camera.position.copy(DP);controls.target.copy(DT);controls.enableZoom=false;}
function topCam(){doZ=false;stopFly();controls.enabled=true;camera.position.set(0,55,.01);controls.target.set(0,0,0);}

// Speed control
// Speed is now driven by narration completion — no manual speed knob needed
function cycleSpeed(){} // kept for API compat

// Voice toggle
function toggleVoice(){
  voiceEnabled=!voiceEnabled;
  const btn=document.getElementById('bvoice');
  if(voiceEnabled){btn.innerHTML='&#128266; Voice ON';btn.classList.add('on');}
  else{btn.innerHTML='&#128263; Voice OFF';btn.classList.remove('on');window.speechSynthesis&&window.speechSynthesis.cancel();}
}

// ── Fly-Through: pause-at-each-component state machine ──────────────────
// The tour visits each component one-by-one:
//   1) TRAVELING  → camera slowly lerps toward the component's viewpoint
//   2) DWELLING   → camera holds while narration plays (min 5 s)
//   3) After dwell → advance to next component
const WPS = COMPS.length ? [
  {pos:new THREE.Vector3(0,24,48), look:new THREE.Vector3(0,2,0)},   // overview
  ...COMPS.map(c=>({pos:new THREE.Vector3(c.x+10,c.y+7,c.z+18), look:new THREE.Vector3(c.x,c.y,c.z)})),
  {pos:new THREE.Vector3(0,24,48), look:new THREE.Vector3(0,2,0)},   // return overview
] : [
  {pos:new THREE.Vector3(0,24,48),  look:new THREE.Vector3(0,0,0)},
  {pos:new THREE.Vector3(24,10,24), look:new THREE.Vector3(0,0,0)},
  {pos:new THREE.Vector3(-24,10,24),look:new THREE.Vector3(0,0,0)},
  {pos:new THREE.Vector3(0,24,48),  look:new THREE.Vector3(0,0,0)},
];

let fly        = false;
let flyState   = 'idle';     // 'traveling' | 'dwelling'
let flyWPIdx   = 0;          // current waypoint index
let dwellUntil = 0;          // timestamp when minimum dwell expires
const MIN_DWELL_MS  = 4000;  // minimum dwell at component (ms)
const OVERVIEW_DWELL = 1800; // shorter dwell at overview waypoints
let _introSpoken = false;    // guard: speak tour intro only once per play

function toggleFly(){ fly ? stopFly() : startFly(); }

function startFly(){
  fly          = true;
  flyState     = 'traveling';
  flyWPIdx     = 0;
  lastCompIdx  = -1;
  _introSpoken = false;
  controls.enabled    = false;
  controls.enableZoom = false;
  doZ = false;
  closeHUD();
  document.getElementById('bfly').innerHTML = '&#9646;&#9646; Pause';
  document.getElementById('bfly').classList.add('on');
  document.getElementById('progbar-wrap').style.display = 'block';
  document.getElementById('progbar').style.width = '0%';
  // Speak tour intro immediately so narration starts while camera is still travelling
  if(voiceEnabled){
    const n = COMPS.length;
    const intro = 'Welcome to the architecture tour. I will guide you through ' + n + ' component' + (n!==1?'s':'')+'. Let\\'s begin.';
    speak(intro);
    _introSpoken = true;
  }
}

function stopFly(){
  fly      = false;
  flyState = 'idle';
  controls.enabled = true;
  controls.enableZoom = false;
  document.getElementById('bfly').innerHTML = '&#9654; Play Tour';
  document.getElementById('bfly').classList.remove('on');
  document.getElementById('progbar-wrap').style.display = 'none';
  document.getElementById('progbar').style.width = '0%';
  hideNowVisiting();
  if(window.speechSynthesis) window.speechSynthesis.cancel();
}

function _flyAdvance(){
  flyWPIdx++;
  if(flyWPIdx >= WPS.length){
    // Tour complete — restart from beginning
    flyWPIdx = 0;
    lastCompIdx = -1;
  }
  flyState = 'traveling';
}

// Animate
let tick=0;
function animate(){
  requestAnimationFrame(animate); tick+=.012;
  meshes.forEach((m,i)=>{
    m.material.opacity=.72+.07*Math.sin(tick+i*.9);
    m.scale.setScalar(m===sel?1+.02*Math.sin(tick*2.5):1);
  });
  pL1.intensity=1.8+.5*Math.sin(tick*.65);
  pL2.intensity=1.5+.4*Math.sin(tick*.5+1.2);
  pL3.intensity=1.0+.3*Math.sin(tick*.4+2.1);

  // Flowing particles on arcs
  arcCurves.forEach(({curve,particles})=>{
    particles.forEach(dot=>{
      const t=((tick*0.06+dot.userData.phase)%1);
      const pt=curve.getPoint(t);
      dot.position.copy(pt);
      dot.material.opacity=0.5+0.5*Math.sin(t*Math.PI);
    });
  });

  // Pulse rings
  if(ringTarget){
    rings.forEach(r=>{
      const t=((tick*0.4+r.userData.phase)%1);
      r.scale.setScalar(t*4);
      r.material.opacity=(1-t)*0.7;
      r.position.copy(ringTarget);
    });
  }

  if(fly){
    const tgt = WPS[flyWPIdx];
    if(flyState === 'traveling'){
      // Adaptive lerp speed: faster when far, steady close in
      const dist = camera.position.distanceTo(tgt.pos);
      const lerpP = dist > 12 ? 0.028 : 0.020;
      const lerpT = dist > 12 ? 0.048 : 0.035;
      camera.position.lerp(tgt.pos, lerpP);
      controls.target.lerp(tgt.look, lerpT);
      // Arrived
      if(dist < 0.55){
        flyState = 'dwelling';
        const isOverview = (flyWPIdx === 0 || flyWPIdx === WPS.length - 1);
        if(isOverview){
          dwellUntil = Date.now() + OVERVIEW_DWELL;
        } else {
          const c = COMPS[flyWPIdx - 1];
          const narr = c ? (NARR[c.name] || buildNarration(c)) : '';
          dwellUntil = Date.now() + Math.max(MIN_DWELL_MS, _speechMs(narr) + 600);
          visitComp(flyWPIdx - 1);
        }
      }
      const pct = (flyWPIdx / Math.max(WPS.length - 1, 1)) * 100;
      document.getElementById('progbar').style.width = pct.toFixed(1) + '%';
    } else if(flyState === 'dwelling'){
      camera.position.lerp(tgt.pos, 0.06);
      controls.target.lerp(tgt.look, 0.09);
      // Advance when both speech is done AND dwell timer expired
      const speechDone = !window.speechSynthesis || !window.speechSynthesis.speaking;
      const timeDone   = Date.now() >= dwellUntil;
      if(speechDone && timeDone){
        const pct = ((flyWPIdx + 1) / Math.max(WPS.length - 1, 1)) * 100;
        document.getElementById('progbar').style.width = Math.min(pct, 100).toFixed(1) + '%';
        _flyAdvance();
      }
    }
  }
  if(doZ&&zT&&zL){camera.position.lerp(zT,.04);controls.target.lerp(zL,.06);}
  controls.update();
  renderer.render(scene,camera);
}
animate();

// Resize
window.addEventListener('resize',()=>{
  const nw=W(),nh=H();
  camera.aspect=nw/nh; camera.updateProjectionMatrix(); renderer.setSize(nw,nh);
});

// Hide spinner after first frame
setTimeout(()=>{const s=document.getElementById('spin');if(s)s.style.display='none';},500);

// Expose handlers (module scope != global scope)
window._3d={toggleFly,resetCam,topCam,closeHUD,focusComp,toggleVoice,cycleSpeed};
</script>
</body></html>"""
    )
    return html


def generate_architecture_diagram(architecture_data):
    """Generate a Graphviz DOT string for an architecture diagram."""
    data = safe_dict(architecture_data)
    pattern = safe_str(data.get("pattern"), "Solution Architecture")
    components = safe_list(data.get("components"))
    data_flow = safe_list(data.get("data_flow"))
    security_items = safe_list(data.get("security"))

    tier_colors = {
        "presentation": "#00B4D8",
        "application": "#1B3A5C",
        "data": "#00D4AA",
        "security": "#7B61FF",
        "operations": "#FFD166",
    }

    type_to_tier = {
        "web app": "presentation", "frontend": "presentation",
        "ui": "presentation", "cdn": "presentation",
        "integration": "application", "microservices": "application",
        "api": "application", "messaging": "application",
        "backend": "application", "compute": "application",
        "database": "data", "storage": "data",
        "data": "data", "cache": "data",
        "identity": "security", "security": "security",
        "auth": "security",
        "operations": "operations", "devops": "operations",
        "monitoring": "operations",
    }

    tier_labels = {
        "presentation": "Presentation Tier",
        "application": "Application Tier",
        "data": "Data Tier",
        "security": "Security Tier",
        "operations": "Operations Tier",
    }

    tier_components = {t: [] for t in tier_colors}
    for comp in components:
        comp = safe_dict(comp)
        comp_type = safe_str(comp.get("type")).lower()
        comp_name_lower = safe_str(comp.get("name")).lower()
        tier = type_to_tier.get(comp_type)
        if tier is None:
            tier = type_to_tier.get(comp_name_lower, "application")
        tier_components[tier].append(comp)

    def node_id(name):
        nid = safe_str(name).replace(" ", "_").replace("/", "_").replace("-", "_")
        nid = "".join(ch for ch in nid if ch.isalnum() or ch == "_")
        return "n_" + nid

    lines = []
    lines.append("digraph architecture {")
    lines.append('    rankdir=TB;')
    lines.append('    bgcolor="#0a0e1a";')
    lines.append('    fontname="Helvetica";')
    lines.append('    node [fontname="Helvetica", fontsize=10, shape=box, style="rounded,filled", fontcolor=white];')
    lines.append('    edge [fontname="Helvetica", fontsize=9, color="#64748b", fontcolor="#94a3b8"];')
    lines.append('')
    lines.append('    labelloc=t;')
    lines.append('    label=<<FONT FACE="Helvetica" POINT-SIZE="16" COLOR="white">' + safe_str(pattern) + '</FONT>>;')
    lines.append('')

    cluster_idx = 0
    all_node_ids = []
    for tier_key in ["presentation", "application", "data", "operations"]:
        comps_in_tier = tier_components.get(tier_key, [])
        if not comps_in_tier:
            continue
        color = tier_colors[tier_key]
        label = tier_labels[tier_key]
        lines.append('    subgraph cluster_' + str(cluster_idx) + ' {')
        lines.append('        label=<<FONT FACE="Helvetica" POINT-SIZE="12" COLOR="' + color + '">' + label + '</FONT>>;')
        lines.append('        style=dashed;')
        lines.append('        color="' + color + '";')
        lines.append('        bgcolor="#111827";')
        lines.append('')
        for comp in comps_in_tier:
            comp = safe_dict(comp)
            name = safe_str(comp.get("name"))
            azure_svc = safe_str(comp.get("azure_service"))
            nid = node_id(name)
            all_node_ids.append((name, nid))
            node_label = name + "\\n" + azure_svc
            lines.append('        ' + nid + ' [label="' + node_label + '", fillcolor="' + color + '"];')
        lines.append('    }')
        lines.append('')
        cluster_idx += 1

    security_comps = tier_components.get("security", [])
    if security_comps or security_items:
        color = tier_colors["security"]
        label = tier_labels["security"]
        lines.append('    subgraph cluster_' + str(cluster_idx) + ' {')
        lines.append('        label=<<FONT FACE="Helvetica" POINT-SIZE="12" COLOR="' + color + '">' + label + '</FONT>>;')
        lines.append('        style=dashed;')
        lines.append('        color="' + color + '";')
        lines.append('        bgcolor="#111827";')
        lines.append('        rank=max;')
        lines.append('')
        for comp in security_comps:
            comp = safe_dict(comp)
            name = safe_str(comp.get("name"))
            azure_svc = safe_str(comp.get("azure_service"))
            nid = node_id(name)
            all_node_ids.append((name, nid))
            node_label = name + "\\n" + azure_svc
            lines.append('        ' + nid + ' [label="' + node_label + '", fillcolor="' + color + '"];')
        if security_items:
            sec_label = "Security Controls\\n" + "\\n".join(safe_str(s) for s in security_items)
            lines.append('        n_security_controls [label="' + sec_label + '", fillcolor="' + color + '", shape=note];')
        lines.append('    }')
        lines.append('')
        cluster_idx += 1

    name_to_nid = {}
    for name, nid in all_node_ids:
        name_to_nid[name.lower()] = nid

    flow_nids = []
    for item in data_flow:
        item_str = safe_str(item)
        item_lower = item_str.lower()
        matched_nid = name_to_nid.get(item_lower)
        if matched_nid is None:
            for comp_name_lower, comp_nid in name_to_nid.items():
                if item_lower in comp_name_lower or comp_name_lower in item_lower:
                    matched_nid = comp_nid
                    break
        if matched_nid is None:
            ghost_nid = node_id(item_str)
            lines.append('    ' + ghost_nid + ' [label="' + item_str + '", fillcolor="#334155", shape=box, style="rounded,filled"];')
            name_to_nid[item_lower] = ghost_nid
            matched_nid = ghost_nid
        flow_nids.append(matched_nid)

    for i in range(len(flow_nids) - 1):
        lines.append('    ' + flow_nids[i] + ' -> ' + flow_nids[i + 1] + ';')

    lines.append("}")
    return "\n".join(lines)


def generate_flow_diagram(time_est_data):
    """Generate a Graphviz DOT string for a project workflow / timeline diagram."""
    data = safe_dict(time_est_data)
    phases = safe_list(data.get("phases"))
    milestones = safe_list(data.get("milestones"))

    phase_colors = [
        "#1B3A5C", "#0E5E8A", "#007F8C", "#00A07A", "#00B464",
        "#00D44A", "#06d6a0", "#0AD490", "#10D280", "#16D070",
    ]
    milestone_color = "#FFD166"

    lines = []
    lines.append("digraph timeline {")
    lines.append('    rankdir=LR;')
    lines.append('    bgcolor="#0a0e1a";')
    lines.append('    fontname="Helvetica";')
    lines.append('    node [fontname="Helvetica", fontsize=10, style="rounded,filled", fontcolor=white];')
    lines.append('    edge [fontname="Helvetica", fontsize=9, color="#64748b"];')
    lines.append('')
    lines.append('    labelloc=t;')
    lines.append('    label=<<FONT FACE="Helvetica" POINT-SIZE="14" COLOR="white">Project Timeline</FONT>>;')
    lines.append('')

    phase_node_ids = []
    for idx, phase in enumerate(phases):
        phase = safe_dict(phase)
        name = safe_str(phase.get("name"), "Phase " + str(idx + 1))
        hours = safe_int(phase.get("hours"))
        pct = safe_str(phase.get("percentage"), "")
        tasks = safe_list(phase.get("tasks"))

        color = phase_colors[idx % len(phase_colors)]
        nid = "phase_" + str(idx)
        phase_node_ids.append(nid)

        label_parts = [name, str(hours) + " hrs (" + pct + ")"]
        for task in tasks:
            task = safe_dict(task)
            task_name = safe_str(task.get("name"))
            task_hours = safe_int(task.get("hours"))
            task_role = safe_str(task.get("role"))
            if task_name:
                task_line = "- " + task_name
                if task_hours:
                    task_line = task_line + " (" + str(task_hours) + "h"
                    if task_role:
                        task_line = task_line + ", " + task_role
                    task_line = task_line + ")"
                elif task_role:
                    task_line = task_line + " [" + task_role + "]"
                label_parts.append(task_line)

        label = "\\n".join(label_parts)
        lines.append('    ' + nid + ' [label="' + label + '", fillcolor="' + color + '", shape=box];')

    lines.append('')

    for i in range(len(phase_node_ids) - 1):
        lines.append('    ' + phase_node_ids[i] + ' -> ' + phase_node_ids[i + 1] + ';')
    lines.append('')

    total_hours = sum(safe_int(safe_dict(p).get("hours")) for p in phases) or 1
    cumulative_week = 0
    phase_week_ranges = []
    total_weeks_est = safe_int(data.get("duration_weeks")) if safe_str(data.get("duration_weeks")).isdigit() else 0
    if total_weeks_est == 0:
        dur_str = safe_str(data.get("duration_weeks"))
        digits = "".join(ch for ch in dur_str if ch.isdigit())
        total_weeks_est = safe_int(digits) if digits else max(8, total_hours // 160)

    for phase in phases:
        phase = safe_dict(phase)
        ph_hours = safe_int(phase.get("hours"))
        proportion = ph_hours / total_hours if total_hours else 0
        weeks_for_phase = proportion * total_weeks_est
        start_week = cumulative_week
        cumulative_week += weeks_for_phase
        phase_week_ranges.append((start_week, cumulative_week))

    for m_idx, ms in enumerate(milestones):
        ms = safe_dict(ms)
        ms_name = safe_str(ms.get("name"), "Milestone " + str(m_idx + 1))
        ms_week = safe_int(ms.get("week"))
        ms_desc = safe_str(ms.get("description"))
        mid = "ms_" + str(m_idx)

        label = ms_name + "\\nWeek " + str(ms_week)
        if ms_desc:
            label = label + "\\n" + ms_desc
        lines.append('    ' + mid + ' [label="' + label + '", shape=diamond, fillcolor="' + milestone_color + '", fontcolor="#1B3A5C", fontsize=9];')

        best_phase_idx = 0
        for p_idx, (ws, we) in enumerate(phase_week_ranges):
            if ms_week <= we or p_idx == len(phase_week_ranges) - 1:
                best_phase_idx = p_idx
                break

        if phase_node_ids:
            target_phase = phase_node_ids[min(best_phase_idx, len(phase_node_ids) - 1)]
            lines.append('    ' + target_phase + ' -> ' + mid + ' [style=dashed, color="' + milestone_color + '"];')

    lines.append("}")
    return "\n".join(lines)
