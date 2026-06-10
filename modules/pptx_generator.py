# ═══════════════════════════════════════════════════════════════════════
#  PPTX GENERATOR — ECI Masterpiece Proposal Deck
# ═══════════════════════════════════════════════════════════════════════

import io
from datetime import datetime

import streamlit as st

from .utils import safe_int, safe_str, safe_list, safe_dict, sc_text

HAS_PPTX = False
try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN
    from pptx.enum.shapes import MSO_SHAPE
    HAS_PPTX = True
except ImportError:
    pass

# ── Brand palette ──────────────────────────────────────────────────────────
_C = {
    "indigo": (29,  27,  75),   # #1D1B4B deep indigo — dark slide bg
    "ind2":   (45,  42, 110),   # #2D2A6E medium indigo — offset squares / card-on-dark
    "ind3":   (60,  57, 140),   # #3C397C lighter indigo — accent on dark
    "teal":   ( 0, 176, 160),   # #00B0A0 teal
    "lime":   (148, 193,  28),  # #94C11C lime
    "orange": (234, 117,  42),  # #EA752A warm orange
    "green":  ( 34, 179, 115),  # #22B373 success green
    "purple": (123,  97, 255),  # #7B61FF purple
    "white":  (255, 255, 255),
    "nearw":  (220, 222, 248),  # near-white for text on dark
    "mid":    (100,  98, 130),  # mid-gray purple
    "card":   (244, 245, 255),  # light card bg
    "red":    (239,  68,  68),
    "amber":  (245, 158,  11),
    "rowalt": (248, 249, 255),  # alternate table row
}

def _rgb(name): return RGBColor(*_C[name]) if HAS_PPTX else None
def _rgbt(r,g,b): return RGBColor(r,g,b) if HAS_PPTX else None


# ═══════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════

def generate_proposal_pptx(results):
    """Masterpiece ECI PPTX — Claude-powered content when available."""
    if not HAS_PPTX:
        return None
    slide_content = _try_claude_content(results)
    if slide_content and slide_content.get("slides"):
        return generate_claude_pptx(slide_content, results)
    return _render_premium_pptx(results)


def _try_claude_content(results):
    try:
        key = st.session_state.get("anthropic_api_key", "")
        if not key or st.session_state.get("_claude_blocked"):
            return None
        from .ai_clients import AnthropicAI
        ai = AnthropicAI.from_session()
        if not ai.is_live:
            return None
        return ai.generate_premium_pptx_content(results)
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
#  DATA-DRIVEN PREMIUM RENDERER
# ═══════════════════════════════════════════════════════════════════════

def _render_premium_pptx(results):
    """High-quality data-driven PPTX — ECI masterpiece design."""
    if not HAS_PPTX:
        return None
    import os

    prs = Presentation()
    prs.slide_width  = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    INDIGO = _rgb("indigo"); IND2  = _rgb("ind2");  IND3  = _rgb("ind3")
    TEAL   = _rgb("teal");   LIME  = _rgb("lime");  ORG   = _rgb("orange")
    GREEN  = _rgb("green");  PUR   = _rgb("purple")
    WHITE  = _rgb("white");  NEARW = _rgb("nearw"); MID   = _rgb("mid")
    CARD   = _rgb("card");   RED   = _rgb("red");   AMBER = _rgb("amber")
    ROWALT = _rgb("rowalt")

    LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eci_logo.png")
    DATE_STR  = datetime.now().strftime("%B %d, %Y")

    ACCENT_CYCLE = [TEAL, ORG, GREEN, PUR, LIME, AMBER]

    # ── primitive helpers ──────────────────────────────────────────────
    def _r(sld, x, y, w, h, col):
        s = sld.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
        s.fill.solid(); s.fill.fore_color.rgb = col; s.line.fill.background(); return s

    def _t(sld, text, x, y, w, h, size=11, bold=False, col=None,
           align=PP_ALIGN.LEFT, wrap=True, italic=False):
        if col is None: col = _rgb("indigo")
        tb = sld.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame; tf.word_wrap = wrap
        p  = tf.paragraphs[0]; p.alignment = align
        run = p.add_run(); run.text = str(text)[:300]
        run.font.size = Pt(size); run.font.bold = bold
        run.font.color.rgb = col; run.font.italic = italic
        return tb

    def _logo(sld, x=Inches(12.1), y=Inches(0.12), h=Inches(0.42), white=False):
        try:
            if os.path.exists(LOGO_PATH):
                sld.shapes.add_picture(LOGO_PATH, x, y, height=h); return
        except Exception: pass
        _t(sld, "ECI+", x, y, Inches(1.2), h, size=20, bold=True,
           col=WHITE if white else INDIGO)

    def _offset_squares(sld, dark=True):
        """ECI signature two offset squares — top right decoration."""
        base = IND2 if dark else _rgbt(220, 222, 248)
        acc  = IND3 if dark else _rgbt(195, 198, 238)
        _r(sld, Inches(10.55), Inches(0.00), Inches(1.65), Inches(1.65), base)
        _r(sld, Inches(11.35), Inches(0.55), Inches(1.65), Inches(1.65), acc)

    def _top_rule(sld, col=None):
        if col is None: col = TEAL
        _r(sld, Inches(0.00), Inches(0.00), prs.slide_width, Inches(0.05), col)

    def _slide_footer(sld, dark=True):
        txt_col = _rgbt(100, 98, 140) if dark else _rgbt(140, 138, 170)
        _t(sld, "ECI  •  Confidential",
           Inches(0.5), Inches(7.1), Inches(5.0), Inches(0.3),
           size=8, col=txt_col, italic=True)
        _t(sld, DATE_STR,
           Inches(10.0), Inches(7.1), Inches(3.0), Inches(0.3),
           size=8, col=txt_col, align=PP_ALIGN.RIGHT)

    def _bullets_tb(sld, items, x, y, w, h, size=11, bullet="▸  ", col=None, spacing=7):
        if col is None: col = _rgb("indigo")
        tb = sld.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame; tf.word_wrap = True
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run(); run.text = bullet + safe_str(item)[:120]
            run.font.size = Pt(size); run.font.color.rgb = col
            p.space_after = Pt(spacing)
        return tb

    # ── SLIDE TYPE BUILDERS ────────────────────────────────────────────

    def _cover(title):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = INDIGO
        # Left teal accent bar
        _r(sld, Inches(0.00), Inches(0.00), Inches(0.14), Inches(7.5), TEAL)
        # Offset squares top-right
        _offset_squares(sld, dark=True)
        # Logo
        _logo(sld, x=Inches(0.45), y=Inches(0.18), h=Inches(0.45), white=True)
        # Title
        _t(sld, title, Inches(0.45), Inches(1.7), Inches(9.8), Inches(2.6),
           size=52, bold=True, col=WHITE, wrap=True)
        # Teal rule
        _r(sld, Inches(0.45), Inches(4.4), Inches(2.4), Inches(0.07), TEAL)
        # Subtitle line
        _t(sld, "AI Solution Proposal",
           Inches(0.45), Inches(4.6), Inches(9.0), Inches(0.6),
           size=20, bold=True, col=TEAL)
        _t(sld, "PROJECT PROPOSAL",
           Inches(0.45), Inches(5.28), Inches(9.0), Inches(0.45),
           size=14, bold=True, col=LIME)
        _t(sld, DATE_STR,
           Inches(0.45), Inches(5.85), Inches(5.5), Inches(0.4),
           size=12, col=_rgbt(160, 158, 210))
        _t(sld, "Confidential  •  ECI  •  AI Solutions",
           Inches(0.45), Inches(7.1), Inches(9.0), Inches(0.32),
           size=9, col=_rgbt(100, 98, 150), italic=True)
        return sld

    def _agenda(items):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = WHITE
        _top_rule(sld, TEAL)
        _logo(sld)
        # Left panel
        _r(sld, Inches(0.45), Inches(1.1), Inches(4.2), Inches(5.9), INDIGO)
        _t(sld, "Agenda", Inches(0.7), Inches(3.3), Inches(3.7), Inches(1.3),
           size=46, bold=True, col=WHITE, align=PP_ALIGN.CENTER)
        # Numbered list
        tb = sld.shapes.add_textbox(Inches(5.2), Inches(1.3), Inches(7.8), Inches(5.8))
        tf = tb.text_frame; tf.word_wrap = True
        for i, item in enumerate(items[:9]):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            r1 = p.add_run(); r1.text = "%02d  " % (i + 1)
            r1.font.size = Pt(20); r1.font.bold = True; r1.font.color.rgb = TEAL
            r2 = p.add_run(); r2.text = safe_str(item)[:80]
            r2.font.size = Pt(14); r2.font.color.rgb = INDIGO; p.space_after = Pt(9)
        _slide_footer(sld, dark=False)
        return sld

    def _section(title, subtitle=""):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = INDIGO
        _r(sld, Inches(0.00), Inches(0.00), Inches(0.14), Inches(7.5), TEAL)
        _offset_squares(sld, dark=True)
        _logo(sld, x=Inches(0.45), y=Inches(0.18), h=Inches(0.4), white=True)
        _t(sld, "SECTION", Inches(0.45), Inches(1.8), Inches(5.0), Inches(0.38),
           size=11, col=TEAL, italic=False, bold=True)
        _r(sld, Inches(0.45), Inches(2.3), Inches(1.8), Inches(0.06), TEAL)
        _t(sld, title, Inches(0.45), Inches(2.55), Inches(9.5), Inches(2.4),
           size=46, bold=True, col=WHITE, wrap=True)
        if subtitle:
            _t(sld, subtitle, Inches(0.45), Inches(5.2), Inches(9.5), Inches(0.55),
               size=16, col=TEAL)
        _slide_footer(sld, dark=True)
        return sld

    def _cards_slide(title, headline, items, checkmark=False):
        """Clean 2-column card grid — replaces old circle layout."""
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = WHITE
        _top_rule(sld, TEAL)
        _logo(sld)
        # Title
        _t(sld, title, Inches(0.5), Inches(0.25), Inches(11.5), Inches(0.6),
           size=26, bold=True, col=INDIGO)
        if headline:
            _t(sld, headline, Inches(0.5), Inches(0.92), Inches(11.0), Inches(0.38),
               size=12, col=MID, italic=True)
        _r(sld, Inches(0.5), Inches(1.35), Inches(2.0), Inches(0.05), TEAL)
        # 2-column card grid — max 8 items
        col_count = 2
        cw = Inches(6.0); ch = Inches(0.82)
        col_x = [Inches(0.5), Inches(6.85)]
        bullet = "☑  " if checkmark else "▸  "
        for idx, item in enumerate(items[:8]):
            col_i = idx % col_count
            row_i = idx // col_count
            cx = col_x[col_i]
            cy = Inches(1.55) + row_i * (ch + Inches(0.1))
            acc = ACCENT_CYCLE[idx % len(ACCENT_CYCLE)]
            _r(sld, cx, cy, cw, ch, CARD)
            _r(sld, cx, cy, Inches(0.05), ch, acc)
            _t(sld, bullet + safe_str(item)[:90],
               cx + Inches(0.15), cy + Inches(0.1),
               cw - Inches(0.25), ch - Inches(0.18),
               size=11, col=INDIGO, wrap=True)
        _slide_footer(sld, dark=False)
        return sld

    def _what_we_do_slide(services=None):
        """About ECI — What We Do 3×3 service grid matching ECI brand screenshot."""
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = WHITE

        # ── Dot grid decoration top-right (gray tiny squares) ──────────
        DOT = _rgbt(210, 214, 232)
        for gy in range(7):
            for gx in range(12):
                sq = sld.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                    Inches(7.8 + gx * 0.46), Inches(0.0 + gy * 0.46),
                    Inches(0.2), Inches(0.2))
                sq.fill.solid(); sq.fill.fore_color.rgb = DOT
                sq.line.fill.background()

        # ── Logo top-left ───────────────────────────────────────────────
        _logo(sld, x=Inches(0.4), y=Inches(0.15), h=Inches(0.5))

        # ── Title (large, bold) ─────────────────────────────────────────
        _t(sld, "What we do – Driving Transformation",
           Inches(0.4), Inches(0.78), Inches(10.5), Inches(0.85),
           size=44, bold=True, col=INDIGO, wrap=False)
        # Thick underline under "What we do" portion
        _r(sld, Inches(0.4), Inches(1.68), Inches(2.55), Inches(0.1), TEAL)

        # ── Teal full-width banner ──────────────────────────────────────
        _r(sld, Inches(0.0), Inches(1.88), prs.slide_width, Inches(0.58), TEAL)
        _t(sld, "DIGITAL BUSINESS TRANSFORMATION",
           Inches(0.4), Inches(1.92), Inches(12.5), Inches(0.5),
           size=15, bold=True, col=WHITE, align=PP_ALIGN.CENTER)

        # ── 3×3 service grid ────────────────────────────────────────────
        if services is None:
            services = [
                ("DIGITAL EXPERIENCE DESIGN",
                 "Our teams imagine and design new experiences for your customers and teams."),
                ("CLOUD DEPLOYMENT",
                 "Migrate and provision new cloud environments for AWS, Azure & GCP."),
                ("CUSTOM WORKFLOW APPLICATIONS",
                 "Plan and development of products to streamline or reinvent key processes."),
                ("BI & ANALYTICS",
                 "Define and implement BI and Data Analytics strategy from inception to deployment."),
                ("INNOVATION & STRATEGY",
                 "From rapid prototyping to innovation labs, we help you see around the corner."),
                ("DEVOPS & AGILE",
                 "Improve executive flexibility & speed with practices designed to enable engineering teams."),
                ("SYSTEMS INTEGRATION",
                 "Accelerate the deployment and launch of platforms across the organization."),
                ("ROBOTIC PROCESS AUTOMATION & AI/ML",
                 "Implement RPA and other automation practices to drive efficiency and cost savings."),
                ("SECURITY & COMPLIANCE",
                 "Enterprise-grade security and ISO 27001 certified controls across all deployments."),
            ]

        icon_symbols = ["◫", "☁", "⚙", "📊", "💡", "🔄", "⇌", "</>", "🔒"]
        cell_w = Inches(4.28); cell_h = Inches(1.52)
        icon_sz = Inches(0.5)
        for bi, (svc_title, svc_desc) in enumerate(services[:9]):
            row = bi // 3; col_i = bi % 3
            cx = Inches(0.4 + col_i * 4.32)
            cy = Inches(2.6 + row * 1.62)
            acc = ACCENT_CYCLE[bi % len(ACCENT_CYCLE)]

            # Icon box (white bg, colored border)
            icon_box = sld.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                cx, cy + Inches(0.22), icon_sz, icon_sz)
            icon_box.fill.solid(); icon_box.fill.fore_color.rgb = CARD
            icon_box.line.color.rgb = acc
            from pptx.util import Pt as _Pt3
            icon_box.line.width = _Pt3(1.5)
            # Icon letter inside box
            _t(sld, icon_symbols[bi % len(icon_symbols)],
               cx, cy + Inches(0.22), icon_sz, icon_sz,
               size=14, col=acc, align=PP_ALIGN.CENTER)

            # Vertical separator line
            _r(sld, cx + icon_sz + Inches(0.12), cy + Inches(0.08),
               Inches(0.04), cell_h - Inches(0.15), INDIGO)

            # Service title (bold, INDIGO, uppercase already in string)
            _t(sld, svc_title,
               cx + icon_sz + Inches(0.24), cy + Inches(0.08),
               cell_w - icon_sz - Inches(0.34), Inches(0.48),
               size=10, bold=True, col=INDIGO, wrap=True)

            # Description
            _t(sld, svc_desc,
               cx + icon_sz + Inches(0.24), cy + Inches(0.6),
               cell_w - icon_sz - Inches(0.34), Inches(0.85),
               size=9, col=MID, wrap=True)

        return sld

    def _summary_slide(team_items, duration, annual_cost):
        """Team / Duration / Cost overview — 3-column, white bg, ECI watermark, outline circles."""
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = WHITE

        # ECI watermark — large very-light text repeated across slide
        wm_col = _rgbt(235, 236, 248)
        for wy in range(3):
            _t(sld, "ECI      ECI      ECI      ECI",
               Inches(0.0), Inches(1.5 + wy * 2.1), Inches(13.5), Inches(1.8),
               size=90, bold=True, col=wm_col, align=PP_ALIGN.CENTER)

        # Logo top-left (large)
        _logo(sld, x=Inches(0.5), y=Inches(0.15), h=Inches(0.55))

        # Slide title
        _t(sld, "Proposal Summary",
           Inches(0.5), Inches(0.18), Inches(8.0), Inches(0.6),
           size=26, bold=True, col=INDIGO)
        _r(sld, Inches(0.5), Inches(0.82), Inches(2.2), Inches(0.05), TEAL)

        # 3 equal columns — no card backgrounds, just circles, labels, bullets
        col_w   = Inches(4.1)
        col_xs  = [Inches(0.45), Inches(4.62), Inches(8.78)]
        c_cols  = [TEAL, ORG, LIME]
        c_lbls  = ["Team", "Duration", "Cost"]
        c_syms  = ["👥", "⏱", "💰"]

        for ci, (cx, c_col, c_lbl, c_sym) in enumerate(
                zip(col_xs, c_cols, c_lbls, c_syms)):

            # Vertical separator between columns (skip for first)
            if ci > 0:
                _r(sld, cx - Inches(0.04), Inches(1.0), Inches(0.04), Inches(6.2),
                   _rgbt(220, 222, 240))

            # Large outline icon circle — no fill, colored stroke
            circ_sz = Inches(1.5)
            circ_x  = cx + col_w / 2 - circ_sz / 2
            circ = sld.shapes.add_shape(
                MSO_SHAPE.OVAL, circ_x, Inches(1.1), circ_sz, circ_sz)
            circ.fill.solid(); circ.fill.fore_color.rgb = WHITE
            circ.line.color.rgb = c_col
            from pptx.util import Pt as _Pt2
            circ.line.width = _Pt2(3.0)

            # Symbol inside circle
            _t(sld, c_sym, circ_x, Inches(1.2),
               circ_sz, Inches(1.2),
               size=26, col=c_col, align=PP_ALIGN.CENTER)

            # Bold colored label
            _t(sld, c_lbl,
               cx, Inches(2.75), col_w, Inches(0.6),
               size=24, bold=True, col=c_col, align=PP_ALIGN.CENTER)

            # Thin colored rule under label
            _r(sld, cx + Inches(0.6), Inches(3.42), col_w - Inches(1.2), Inches(0.05), c_col)

            # Checkbox bullet items
            if ci == 0:
                items = [safe_str(it.get("role", it)) if isinstance(it, dict) else safe_str(it)
                         for it in team_items[:5]]
                if not items:
                    items = ["Project Manager", "AI Architect", "AI Engineer", "QA Engineer"]
            elif ci == 1:
                items = [("%s weeks" % safe_str(duration)) if duration else "TBD",
                         "Discovery  •  Design",
                         "Implementation  •  QA",
                         "UAT  •  Go-Live"]
            else:
                items = [("Total: $%s" % "{:,}".format(annual_cost)) if annual_cost else "TBD",
                         "Annual investment",
                         "Milestone-based billing",
                         "Includes training & support"]

            tb = sld.shapes.add_textbox(
                cx + Inches(0.2), Inches(3.58), col_w - Inches(0.4), Inches(3.6))
            tf = tb.text_frame; tf.word_wrap = True
            for i, item in enumerate(items):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                r_ = p.add_run(); r_.text = "☐  " + safe_str(item)
                r_.font.size = Pt(12); r_.font.color.rgb = INDIGO
                p.space_after = Pt(9)

        _slide_footer(sld, dark=False)
        return sld

    def _kpi_cards(title, metrics):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = INDIGO
        _offset_squares(sld, dark=True)
        _logo(sld, x=Inches(12.1), y=Inches(0.12), h=Inches(0.42), white=True)
        _t(sld, title, Inches(0.5), Inches(0.75), Inches(12.2), Inches(0.65),
           size=28, bold=True, col=WHITE, align=PP_ALIGN.CENTER)
        _r(sld, Inches(5.4), Inches(1.5), Inches(2.5), Inches(0.06), TEAL)
        acc_list = [TEAL, LIME, ORG]
        for mi, m in enumerate(metrics[:3]):
            mx = Inches(0.75 + mi * 4.15)
            my = Inches(1.85)
            cw = Inches(3.8); ch = Inches(4.5)
            _r(sld, mx, my, cw, ch, IND2)
            # Top colored bar
            _r(sld, mx, my, cw, Inches(0.06), acc_list[mi])
            # Big value
            _t(sld, safe_str(m.get("value", "—")),
               mx + Inches(0.15), my + Inches(0.45), cw - Inches(0.3), Inches(2.2),
               size=60, bold=True, col=WHITE, align=PP_ALIGN.CENTER)
            # Label
            _t(sld, safe_str(m.get("label", "")),
               mx + Inches(0.15), my + Inches(2.75), cw - Inches(0.3), Inches(0.6),
               size=16, bold=True, col=acc_list[mi], align=PP_ALIGN.CENTER)
            # Desc
            _t(sld, safe_str(m.get("desc", "")),
               mx + Inches(0.15), my + Inches(3.45), cw - Inches(0.3), Inches(0.7),
               size=10, col=NEARW, align=PP_ALIGN.CENTER)
        _slide_footer(sld, dark=True)
        return sld

    def _timeline_slide(title, phases):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = WHITE
        _top_rule(sld, TEAL)
        _logo(sld)
        _t(sld, title, Inches(0.5), Inches(0.25), Inches(11.5), Inches(0.6),
           size=26, bold=True, col=INDIGO)
        _r(sld, Inches(0.5), Inches(0.95), Inches(2.0), Inches(0.05), TEAL)
        n = min(len(phases), 6)
        if not n:
            return sld
        total_h = max(sum(safe_int(safe_dict(p).get("hours", 1)) for p in phases[:n]), 1)
        bar_w = Inches(12.3)
        x_cur = Inches(0.5); bar_y = Inches(1.2); bar_h = Inches(0.9)
        ph_cols = [TEAL, ORG, LIME, PUR, GREEN, AMBER]
        for pi, p in enumerate(phases[:n]):
            pd  = safe_dict(p)
            hrs = safe_int(pd.get("hours", total_h // n))
            w   = bar_w * hrs / total_h
            col = ph_cols[pi % len(ph_cols)]
            _r(sld, x_cur, bar_y, w - Inches(0.04), bar_h, col)
            ph_name = safe_str(pd.get("name", "P%d" % (pi + 1)))[:20]
            _t(sld, ph_name, x_cur, bar_y + Inches(0.12), w - Inches(0.06),
               Inches(0.45), size=10, bold=True, col=WHITE, align=PP_ALIGN.CENTER)
            _t(sld, "%dh" % hrs, x_cur, bar_y + Inches(0.57), w - Inches(0.06),
               Inches(0.3), size=9, col=WHITE, align=PP_ALIGN.CENTER)
            x_cur += w
        # Description cards below bars
        desc_y = Inches(2.35)
        for pi, p in enumerate(phases[:min(n, 3)]):
            pd  = safe_dict(p)
            col = ph_cols[pi % len(ph_cols)]
            dx  = Inches(0.5 + pi * 4.2)
            _r(sld, dx, desc_y, Inches(3.9), Inches(2.5), CARD)
            _r(sld, dx, desc_y, Inches(0.05), Inches(2.5), col)
            _t(sld, safe_str(pd.get("name", "")),
               dx + Inches(0.18), desc_y + Inches(0.1), Inches(3.6), Inches(0.45),
               size=12, bold=True, col=INDIGO)
            desc = safe_str(pd.get("description", ""))[:100]
            if desc:
                _t(sld, desc, dx + Inches(0.18), desc_y + Inches(0.6),
                   Inches(3.6), Inches(1.6), size=10, col=MID, wrap=True)
        if n > 3:
            desc_y2 = desc_y + Inches(2.7)
            for pi, p in enumerate(phases[3:min(n, 6)]):
                pd  = safe_dict(p)
                col = ph_cols[(pi + 3) % len(ph_cols)]
                dx  = Inches(0.5 + pi * 4.2)
                _r(sld, dx, desc_y2, Inches(3.9), Inches(2.0), CARD)
                _r(sld, dx, desc_y2, Inches(0.05), Inches(2.0), col)
                _t(sld, safe_str(pd.get("name", "")),
                   dx + Inches(0.18), desc_y2 + Inches(0.1), Inches(3.6), Inches(0.4),
                   size=11, bold=True, col=INDIGO)
                desc2 = safe_str(pd.get("description", ""))[:80]
                if desc2:
                    _t(sld, desc2, dx + Inches(0.18), desc_y2 + Inches(0.55),
                       Inches(3.6), Inches(1.2), size=10, col=MID, wrap=True)
        _slide_footer(sld, dark=False)
        return sld

    def _tech_grid(title, items, headline=""):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = WHITE
        _top_rule(sld, TEAL)
        _logo(sld)
        _t(sld, title, Inches(0.5), Inches(0.25), Inches(11.5), Inches(0.6),
           size=26, bold=True, col=INDIGO)
        if headline:
            _t(sld, headline, Inches(0.5), Inches(0.92), Inches(11.0), Inches(0.38),
               size=12, col=MID, italic=True)
        _r(sld, Inches(0.5), Inches(1.35), Inches(2.0), Inches(0.05), TEAL)
        bw, bh = Inches(3.9), Inches(1.55)
        for bi, comp in enumerate(items[:9]):
            row = bi // 3; col_idx = bi % 3
            bx = Inches(0.5 + col_idx * 4.25)
            by = Inches(1.55 + row * 1.72)
            acc = ACCENT_CYCLE[bi % len(ACCENT_CYCLE)]
            _r(sld, bx, by, bw, bh, CARD)
            _r(sld, bx, by, Inches(0.06), bh, acc)
            _t(sld, safe_str(comp)[:60], bx + Inches(0.18), by + Inches(0.35),
               bw - Inches(0.3), bh - Inches(0.5), size=13, bold=True, col=INDIGO, wrap=True)
        _slide_footer(sld, dark=False)
        return sld

    def _investment_slide(monthly, annual, cost_lines):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = INDIGO
        _offset_squares(sld, dark=True)
        _logo(sld, x=Inches(12.1), y=Inches(0.12), h=Inches(0.42), white=True)
        _t(sld, "INVESTMENT SUMMARY",
           Inches(0.5), Inches(0.7), Inches(8.0), Inches(0.45),
           size=12, col=TEAL, bold=True)
        ann_str = "$%s" % "{:,}".format(annual) if annual > 0 else "TBD"
        _t(sld, ann_str, Inches(0.5), Inches(1.25), Inches(9.5), Inches(2.1),
           size=76, bold=True, col=WHITE, wrap=False)
        _t(sld, "Estimated Total Annual Investment",
           Inches(0.5), Inches(3.45), Inches(9.5), Inches(0.5),
           size=17, col=LIME, bold=True)
        _r(sld, Inches(0.5), Inches(4.1), Inches(2.8), Inches(0.06), TEAL)
        _bullets_tb(sld, cost_lines[:6], Inches(0.5), Inches(4.35),
                    Inches(9.0), Inches(2.5), size=13, bullet="•  ",
                    col=_rgbt(195, 193, 230), spacing=7)
        if monthly > 0:
            _r(sld, Inches(10.0), Inches(1.5), Inches(3.0), Inches(2.2), IND2)
            _r(sld, Inches(10.0), Inches(1.5), Inches(3.0), Inches(0.06), TEAL)
            _t(sld, "$%s" % "{:,}".format(monthly),
               Inches(10.0), Inches(1.75), Inches(3.0), Inches(0.95),
               size=32, bold=True, col=WHITE, align=PP_ALIGN.CENTER)
            _t(sld, "per month",
               Inches(10.0), Inches(2.75), Inches(3.0), Inches(0.42),
               size=13, col=TEAL, align=PP_ALIGN.CENTER)
            _t(sld, "infrastructure",
               Inches(10.0), Inches(3.2), Inches(3.0), Inches(0.35),
               size=10, col=NEARW, align=PP_ALIGN.CENTER)
        _slide_footer(sld, dark=True)
        return sld

    def _risk_register(risks):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = WHITE
        _top_rule(sld, TEAL)
        _logo(sld)
        _t(sld, "Risk Register", Inches(0.5), Inches(0.25), Inches(11.5), Inches(0.6),
           size=26, bold=True, col=INDIGO)
        _r(sld, Inches(0.5), Inches(0.95), Inches(2.0), Inches(0.05), TEAL)
        # Header row
        y_hdr = Inches(1.15)
        _r(sld, Inches(0.5), y_hdr, Inches(12.5), Inches(0.48), INDIGO)
        for hdr, hx, hw in [("Risk", Inches(1.0), Inches(4.5)),
                              ("Severity", Inches(5.75), Inches(1.3)),
                              ("Mitigation", Inches(7.2), Inches(5.7))]:
            _t(sld, hdr, hx, y_hdr + Inches(0.07), hw, Inches(0.35),
               size=10, bold=True, col=WHITE)
        SEV_COL = {"critical": RED, "high": RED, "medium": AMBER, "low": GREEN}
        y_row = y_hdr + Inches(0.52)
        row_h = Inches(0.82)
        for ri_i, rk in enumerate(risks[:6]):
            rd  = safe_dict(rk)
            sev = safe_str(rd.get("severity", "Medium")).lower()
            sc  = SEV_COL.get(sev, AMBER)
            bg  = CARD if ri_i % 2 == 0 else ROWALT
            _r(sld, Inches(0.5), y_row, Inches(12.5), row_h - Inches(0.05), bg)
            _r(sld, Inches(0.5), y_row, Inches(0.06), row_h - Inches(0.05), sc)
            rid = safe_str(rd.get("id", "RK-%03d" % (ri_i + 1)))
            _t(sld, rid, Inches(0.65), y_row + Inches(0.17), Inches(0.7), Inches(0.38),
               size=9, bold=True, col=sc)
            _t(sld, safe_str(rd.get("title", "")),
               Inches(1.05), y_row + Inches(0.07), Inches(4.5), Inches(0.68),
               size=11, bold=True, col=INDIGO, wrap=True)
            # Severity pill
            _r(sld, Inches(5.8), y_row + Inches(0.22), Inches(1.15), Inches(0.37), sc)
            _t(sld, safe_str(rd.get("severity", "Med")),
               Inches(5.8), y_row + Inches(0.22), Inches(1.15), Inches(0.37),
               size=9, bold=True, col=WHITE, align=PP_ALIGN.CENTER)
            _t(sld, safe_str(rd.get("mitigation", ""))[:110],
               Inches(7.2), y_row + Inches(0.08), Inches(5.65), Inches(0.66),
               size=10, col=MID, wrap=True)
            y_row += row_h
        _slide_footer(sld, dark=False)
        return sld

    def _team_slide(team_roles, duration, tl_items):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = WHITE
        _top_rule(sld, TEAL)
        _logo(sld)
        _t(sld, "Team Composition & Timeline",
           Inches(0.5), Inches(0.25), Inches(11.5), Inches(0.6),
           size=26, bold=True, col=INDIGO)
        _r(sld, Inches(0.5), Inches(0.95), Inches(2.5), Inches(0.05), TEAL)
        # Role cards — thin top accent bar
        cw, ch = Inches(2.4), Inches(2.3)
        for ti, role_info in enumerate(team_roles[:5]):
            tx = Inches(0.45 + ti * 2.58)
            ty = Inches(1.18)
            acc = ACCENT_CYCLE[ti % len(ACCENT_CYCLE)]
            _r(sld, tx, ty, cw, ch, CARD)
            _r(sld, tx, ty, cw, Inches(0.07), acc)
            nm  = safe_str(role_info.get("role", "")) if isinstance(role_info, dict) else safe_str(role_info)
            hrs = safe_str(role_info.get("hours", ""))  if isinstance(role_info, dict) else ""
            _t(sld, nm, tx + Inches(0.12), ty + Inches(0.2), cw - Inches(0.24), Inches(0.55),
               size=11, bold=True, col=INDIGO, wrap=True)
            if hrs:
                _t(sld, hrs, tx + Inches(0.12), ty + Inches(0.85), cw - Inches(0.24), Inches(0.75),
                   size=24, bold=True, col=acc, align=PP_ALIGN.CENTER)
                _t(sld, "hours", tx + Inches(0.12), ty + Inches(1.65), cw - Inches(0.24), Inches(0.35),
                   size=9, col=MID, align=PP_ALIGN.CENTER)
        # Timeline section
        _r(sld, Inches(0.5), Inches(3.68), Inches(12.5), Inches(0.04), _rgbt(220, 222, 248))
        _t(sld, "Project Timeline", Inches(0.5), Inches(3.85), Inches(4.0), Inches(0.45),
           size=14, bold=True, col=INDIGO)
        if duration:
            _t(sld, "Total Duration: %s weeks" % safe_str(duration),
               Inches(5.0), Inches(3.85), Inches(5.5), Inches(0.45),
               size=14, bold=True, col=TEAL)
        _bullets_tb(sld, tl_items[:4], Inches(0.5), Inches(4.42),
                    Inches(12.5), Inches(2.0), size=11, bullet="✔  ",
                    col=INDIGO, spacing=6)
        _slide_footer(sld, dark=False)
        return sld

    def _next_steps_slide(steps):
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = INDIGO
        _r(sld, Inches(0.00), Inches(0.00), Inches(0.14), Inches(7.5), TEAL)
        _offset_squares(sld, dark=True)
        _logo(sld, x=Inches(0.45), y=Inches(0.18), h=Inches(0.4), white=True)
        _t(sld, "Next Steps", Inches(0.45), Inches(1.0), Inches(9.5), Inches(0.9),
           size=42, bold=True, col=WHITE)
        _r(sld, Inches(0.45), Inches(2.05), Inches(2.4), Inches(0.07), TEAL)
        for si, step_txt in enumerate(steps[:5]):
            sy  = Inches(2.4 + si * 0.98)
            acc = ACCENT_CYCLE[si % len(ACCENT_CYCLE)]
            # Numbered circle
            circ = sld.shapes.add_shape(MSO_SHAPE.OVAL,
                Inches(0.45), sy, Inches(0.76), Inches(0.76))
            circ.fill.solid(); circ.fill.fore_color.rgb = acc
            circ.line.fill.background()
            _t(sld, str(si + 1), Inches(0.45), sy + Inches(0.06),
               Inches(0.76), Inches(0.68), size=17, bold=True, col=WHITE,
               align=PP_ALIGN.CENTER)
            _t(sld, safe_str(step_txt)[:120],
               Inches(1.42), sy + Inches(0.08), Inches(9.0), Inches(0.72),
               size=14, col=WHITE, wrap=True)
        _slide_footer(sld, dark=True)
        return sld

    def _contact_slide():
        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = INDIGO

        # ── ECI+ logo — top-right, large ───────────────────────────────
        _logo(sld, x=Inches(11.2), y=Inches(0.12), h=Inches(0.62), white=True)

        # ── 2×2 squares bottom-right (checkerboard IND2/IND3) ──────────
        sq = Inches(1.92)
        gap = Inches(0.12)
        sx0 = Inches(7.82); sy0 = Inches(2.05)
        _r(sld, sx0,            sy0,            sq, sq, IND2)   # top-left
        _r(sld, sx0 + sq + gap, sy0,            sq, sq, IND3)   # top-right
        _r(sld, sx0,            sy0 + sq + gap, sq, sq, IND3)   # bottom-left
        _r(sld, sx0 + sq + gap, sy0 + sq + gap, sq, sq, IND2)   # bottom-right

        # ── Vertical separator line ─────────────────────────────────────
        _r(sld, Inches(2.55), Inches(1.55), Inches(0.04), Inches(5.5),
           _rgbt(75, 72, 140))

        # ── Social circles — large white, dark indigo icons ─────────────
        social_labels = ["f", "t", "in"]
        for si, lbl in enumerate(social_labels):
            circ_sz = Inches(1.22)
            cx = Inches(0.6)
            cy = Inches(1.78 + si * 1.58)
            circ = sld.shapes.add_shape(MSO_SHAPE.OVAL, cx, cy, circ_sz, circ_sz)
            circ.fill.solid(); circ.fill.fore_color.rgb = WHITE
            circ.line.fill.background()
            icon_sz = 22 if lbl != "in" else 20
            _t(sld, lbl, cx, cy + Inches(0.18), circ_sz, Inches(0.88),
               size=icon_sz, bold=True, col=INDIGO, align=PP_ALIGN.CENTER)

        # ── Contact info ────────────────────────────────────────────────
        tx = Inches(2.85)
        _t(sld, "Corporate Headquarters",
           tx, Inches(1.62), Inches(6.5), Inches(0.65),
           size=26, bold=True, col=WHITE)
        _t(sld, "529 Fifth Avenue, 7th floor",
           tx, Inches(2.38), Inches(6.5), Inches(0.42), size=13, col=NEARW)
        _t(sld, "New York, New York, 10017",
           tx, Inches(2.82), Inches(6.5), Inches(0.42), size=13, col=NEARW)

        _t(sld, "Global Sales",
           tx, Inches(3.45), Inches(6.5), Inches(0.65),
           size=26, bold=True, col=WHITE)
        _t(sld, "US: +1 800 752 1382",
           tx, Inches(4.22), Inches(6.5), Inches(0.42), size=13, col=NEARW)
        _t(sld, "UK: +44 207 0716802",
           tx, Inches(4.68), Inches(6.5), Inches(0.42), size=13, col=NEARW)
        _t(sld, "Singapore: +65 66222345",
           tx, Inches(5.14), Inches(6.5), Inches(0.42), size=13, col=NEARW)
        _t(sld, "Hong Kong: +852 3189 0101",
           tx, Inches(5.60), Inches(6.5), Inches(0.42), size=13, col=NEARW)

        return sld

    # ════════════════════════════════════════════════════════════════════
    #  EXTRACT DATA
    # ════════════════════════════════════════════════════════════════════
    se   = safe_dict(results.get("semantic_analysis", {}))
    te   = safe_dict(results.get("time_estimate",     {}))
    ce   = safe_dict(results.get("cost_estimate",     {}))
    ri   = safe_dict(results.get("risk_assessment",   {}))
    ar   = safe_dict(results.get("architecture",      {}))
    sc_d = safe_dict(results.get("scope",             {}))

    PROJ_TYPE    = safe_str(se.get("project_type", "Enterprise AI Solution"))
    dur_weeks    = safe_str(te.get("duration_weeks", ""))
    total_hours  = safe_int(te.get("total_hours", 0))
    monthly_cost = safe_int(ce.get("total_monthly_cost", 0))
    annual_cost  = safe_int(ce.get("total_annual_cost", monthly_cost * 12))
    phases       = safe_list(te.get("phases", []))
    risk_list    = safe_list(ri.get("risks", []))
    arch_comps   = safe_list(ar.get("components", []))
    arch_pattern = safe_str(ar.get("pattern", ""))
    svcs         = safe_list(ce.get("azure_costs", []))
    objectives   = safe_list(se.get("business_objectives", []))
    reqs         = safe_list(se.get("requirements", []))
    tech_stack   = [safe_str(t) for t in safe_list(se.get("technology_stack", []))[:9]]

    in_scope    = [sc_text(x, "in_scope")      for x in safe_list(sc_d.get("in_scope",     []))[:8]]
    out_scope   = [sc_text(x, "out_of_scope")  for x in safe_list(sc_d.get("out_of_scope", []))[:5]]
    assumptions = [sc_text(x, "assumptions")   for x in safe_list(sc_d.get("assumptions",  []))[:7]]
    prereqs     = [sc_text(x, "prerequisites") for x in safe_list(sc_d.get("prerequisites",[]))[:6]]

    req_items = []
    for rq in reqs[:6]:
        rd = safe_dict(rq)
        nm = safe_str(rd.get("title", ""))
        ds = safe_str(rd.get("description", ""))[:70]
        req_items.append((nm + " – " + ds) if (ds and ds != nm) else nm)

    comp_names = [safe_str(safe_dict(c).get("name", "")) for c in arch_comps[:9]]
    if not comp_names:
        comp_names = tech_stack or [
            "Azure OpenAI", "Azure App Service", "Azure AI Search",
            "Cosmos DB", "Azure Functions", "Key Vault",
            "Azure AD", "Application Insights", "Azure DevOps",
        ]

    kpi_metrics = [
        {"label": "Timeline",
         "value": (dur_weeks + " wks") if dur_weeks else "TBD",
         "desc": "Discovery to go-live"},
        {"label": "Total Effort",
         "value": ("%dk" % (total_hours // 1000)) if total_hours >= 1000 else (str(total_hours) + "h") if total_hours else "TBD",
         "desc": "Engineering hours"},
        {"label": "Annual Cost",
         "value": "$%s" % "{:,}".format(annual_cost) if annual_cost else "TBD",
         "desc": "Total investment"},
    ]

    cost_lines = []
    for svc in svcs[:5]:
        sd = safe_dict(svc)
        sn = safe_str(sd.get("service", ""))
        sc_ = safe_int(sd.get("monthly_cost", 0))
        if sn:
            cost_lines.append("%s — $%s/mo" % (sn, "{:,}".format(sc_)))
    if not cost_lines:
        cost_lines = ["Azure OpenAI Service", "Azure App Service", "Azure AI Search"]
    cost_lines.append("Milestone-based payment structure")
    cost_lines.append("Includes: documentation, training & warranty support")

    team_roles = []
    for ph in phases[:5]:
        pd = safe_dict(ph)
        nm  = safe_str(pd.get("name", ""))
        hrs = safe_int(pd.get("hours", 0))
        if nm:
            team_roles.append({"role": nm, "hours": str(hrs) if hrs else ""})
    if not team_roles:
        for name in ["Project Manager", "AI Architect", "AI Engineer", "QA Engineer", "DevOps"]:
            team_roles.append({"role": name, "hours": ""})

    tl_items = (
        [safe_str(safe_dict(p).get("name", "")) + " – " + str(safe_int(safe_dict(p).get("hours", 0))) + "h"
         for p in phases[:4]]
        or ["Phase 1-2: Discovery, Architecture & Design",
            "Phase 3-4: Development & Integration",
            "Phase 5: Testing, UAT & Go-live"]
    )

    obj_items = objectives[:6] or req_items[:6] or ["Delivering transformative AI solution"]

    # ════════════════════════════════════════════════════════════════════
    #  BUILD SLIDES
    # ════════════════════════════════════════════════════════════════════

    _cover(PROJ_TYPE or "Enterprise AI Solution")

    _agenda([
        "Introduction & About ECI",
        "What We Do",
        "Business Context & Challenge",
        "Proposed Solution & Architecture",
        "Key Capabilities & Technology",
        "Project Phases & Timeline",
        "Scope of Work",
        "Investment Summary",
        "Risk Management",
        "Next Steps",
    ])

    _section("Introduction", "Understanding Your Business Vision")
    _what_we_do_slide()  # Slide 4 — replaces plain About ECI cards
    _cards_slide(
        "Business Context",
        "Strategic objectives driving this initiative",
        obj_items,
        checkmark=False,
    )

    _section("Proposed Solution", "Innovation Engineered for Your Business")
    arch_bullets = comp_names[:6] or [
        "Azure OpenAI — Language Model Backend",
        "Azure App Service — Scalable API Layer",
        "Azure AI Search — Knowledge Retrieval",
    ]
    _cards_slide(
        "Solution Architecture",
        arch_pattern or "Azure-native cloud-first architecture",
        arch_bullets,
        checkmark=False,
    )
    _tech_grid("Key Technology Components", comp_names,
               arch_pattern or "Microsoft Azure Cloud Platform")
    _kpi_cards("Value at a Glance", kpi_metrics)

    _section("Implementation Plan", "Structured for Certainty & Speed")
    if phases:
        _timeline_slide("Project Phases & Timeline", phases)
    else:
        _cards_slide("Project Timeline", "Phased milestone-driven delivery",
                     tl_items, checkmark=False)

    _section("Scope of Work", "Clarity Drives Successful Delivery")
    if in_scope:
        _cards_slide("Scope of Work", "Committed deliverables", in_scope, checkmark=True)
    if out_scope:
        _cards_slide("Out of Scope", "Exclusions & change-request conditions",
                     out_scope, checkmark=False)

    all_prereqs = (assumptions + prereqs)[:8] or [
        "Azure subscription provisioned with required quotas",
        "Sample data available for training & testing (Week 1)",
        "Stakeholder availability for weekly reviews & UAT",
        "Access to existing systems granted to ECI team",
        "Legal/security review completed before kick-off",
    ]
    _cards_slide("Assumptions & Pre-Requisites",
                 "Foundation commitments for successful delivery",
                 all_prereqs, checkmark=True)

    _section("Investment", "Transparent Pricing, Measurable ROI")
    _team_slide(team_roles, dur_weeks, tl_items)
    _summary_slide(team_roles, dur_weeks, annual_cost)
    _investment_slide(monthly_cost, annual_cost, cost_lines)

    _section("Risk Management", "Proactive Identification & Mitigation")
    if risk_list:
        _risk_register(risk_list)
    else:
        _cards_slide(
            "Risk Management",
            "Key risks — identified, assessed & mitigated",
            [
                "Integration complexity — mitigation: phased rollout",
                "Data quality issues — mitigation: data profiling sprint",
                "Timeline dependencies — mitigation: early environment setup",
                "Change management — mitigation: stakeholder workshops",
            ],
            checkmark=False,
        )

    _next_steps_slide([
        "Review & provide written feedback on this proposal",
        "Schedule technical deep-dive with ECI architects",
        "Finalize and sign Statement of Work (SOW)",
        "Environment access & onboarding completed",
        "Project kick-off — sprint planning & team introductions",
    ])

    _contact_slide()

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════
#  PREMIUM HTML PREVIEW  (data-driven, matches the indigo PPTX design)
# ═══════════════════════════════════════════════════════════════════════

def build_premium_pptx_preview_html(results: dict, pptx_bytes: bytes = None) -> str:
    """Prev/Next HTML viewer that mirrors the _render_premium_pptx design.
    Pass pptx_bytes to embed a zero-rerun download button inside the iframe."""
    from datetime import datetime as _dt
    try:
        import streamlit as _st
        _client = (_st.session_state.get("proposal_client_name", "") or "Client").strip()
    except Exception:
        _client = "Client"

    se   = safe_dict(results.get("semantic_analysis", {}))
    te   = safe_dict(results.get("time_estimate",     {}))
    ce   = safe_dict(results.get("cost_estimate",     {}))
    ri   = safe_dict(results.get("risk_assessment",   {}))
    ar   = safe_dict(results.get("architecture",      {}))
    sc_d = safe_dict(results.get("scope",             {}))

    PROJ_TYPE   = safe_str(se.get("project_type", "Enterprise AI Solution"))
    dur_weeks   = safe_str(te.get("duration_weeks", ""))
    total_hours = safe_int(te.get("total_hours", 0))
    monthly_c   = safe_int(ce.get("total_monthly_cost", 0))
    annual_c    = safe_int(ce.get("total_annual_cost", monthly_c * 12))
    phases      = safe_list(te.get("phases",   []))
    risk_list   = safe_list(ri.get("risks",    []))
    arch_comps  = safe_list(ar.get("components", []))
    arch_pat    = safe_str(ar.get("pattern", ""))
    svcs        = safe_list(ce.get("azure_costs", []))
    objectives  = safe_list(se.get("business_objectives", []))
    reqs        = safe_list(se.get("requirements", []))
    tech_stack  = [safe_str(t) for t in safe_list(se.get("technology_stack", []))[:9]]

    in_scope   = [sc_text(x, "in_scope")      for x in safe_list(sc_d.get("in_scope",    []))[:8]]
    out_scope  = [sc_text(x, "out_of_scope")  for x in safe_list(sc_d.get("out_of_scope",[]))[:5]]
    assumps    = [sc_text(x, "assumptions")   for x in safe_list(sc_d.get("assumptions", []))[:7]]
    prereqs    = [sc_text(x, "prerequisites") for x in safe_list(sc_d.get("prerequisites",[]))[:6]]

    DATE_STR = _dt.now().strftime("%B %d, %Y")
    IND="#1D1B4B"; IND2="#2D2A6E"; IND3="#3C397C"
    TEA="#00B0A0"; LIM="#94C11C"; ORG="#EA752A"
    GRN="#22B373"; PUR="#7B61FF"; AMB="#F59E0B"
    NRW="#DCDCF8"; MID="#64625E"; CRD="#F4F5FF"
    RED="#EF4444"; WHI="#ffffff"
    ACC=[TEA,ORG,GRN,PUR,LIM,AMB]

    def _e(s):
        return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

    def _logo(dark=True, pos="right:1.6%;top:1.5%"):
        c = WHI if dark else IND
        return (f'<div style="position:absolute;{pos};z-index:10;'
                f'font-size:clamp(13px,1.8vw,24px);font-weight:900;color:{c};letter-spacing:.4px">'
                f'ECI<sup style="font-size:48%;color:{TEA}">+</sup></div>')

    def _osq():
        return (f'<div style="position:absolute;right:0;top:0;width:13%;padding-top:24%;background:{IND2};z-index:2"></div>'
                f'<div style="position:absolute;right:0;top:8%;width:13%;padding-top:24%;margin-right:13%;background:{IND3};z-index:2"></div>')

    def _lbar():
        return f'<div style="position:absolute;left:0;top:0;bottom:0;width:1%;background:{TEA};z-index:6"></div>'

    def _trule():
        return f'<div style="position:absolute;left:0;top:0;width:100%;height:.6%;background:{TEA};z-index:4"></div>'

    def _foot(dark=True):
        c = "rgba(140,138,210,.5)" if dark else "rgba(100,98,160,.4)"
        return (f'<div style="position:absolute;bottom:2%;left:3.5%;font-size:clamp(6px,.7vw,9px);'
                f'color:{c};font-style:italic;z-index:5">ECI  •  Confidential</div>'
                f'<div style="position:absolute;bottom:2%;right:2%;font-size:clamp(6px,.7vw,9px);color:{c};z-index:5">{_e(DATE_STR)}</div>')

    def _card(txt, idx, chk=False):
        ac = ACC[idx % 6]; blt = "☑" if chk else "▸"
        return (f'<div style="display:flex;background:{CRD};margin-bottom:5px;border-radius:3px;overflow:hidden">'
                f'<div style="width:4px;background:{ac};flex-shrink:0"></div>'
                f'<div style="padding:5px 7px;font-size:clamp(7px,.82vw,11px);color:{IND};line-height:1.35">'
                f'<span style="color:{ac};margin-right:4px">{blt}</span>{_e(str(txt)[:100])}</div></div>')

    def _sec_slide(title, sub=""):
        return (f'<div style="position:absolute;inset:0;background:{IND};overflow:hidden">'
                f'{_lbar()}{_osq()}{_logo(dark=True)}{_foot(dark=True)}'
                f'<div style="position:absolute;left:3.5%;top:22%;right:20%;z-index:5">'
                f'<div style="font-size:clamp(8px,.85vw,11px);font-weight:700;color:{TEA};letter-spacing:2px;margin-bottom:6px">SECTION</div>'
                f'<div style="width:13%;height:3px;background:{TEA};margin-bottom:11px"></div>'
                f'<div style="font-size:clamp(20px,3.6vw,48px);font-weight:900;color:{WHI};line-height:1.1">{_e(title)}</div>'
                f'{"<div style=font-size:clamp(9px,1vw,14px);color:"+TEA+";margin-top:9px;font-weight:600>"+_e(sub)+"</div>" if sub else ""}'
                f'</div></div>')

    def _light_slide(title, sub, body_html):
        return (f'<div style="position:absolute;inset:0;background:{WHI};overflow:hidden">'
                f'{_trule()}{_logo(dark=False)}{_foot(dark=False)}'
                f'<div style="position:absolute;left:3%;top:8%;right:3%;z-index:5">'
                f'<div style="font-size:clamp(15px,2vw,26px);font-weight:900;color:{IND};margin-bottom:2px">{_e(title)}</div>'
                f'{"<div style=font-size:clamp(7px,.82vw,11px);color:"+MID+";font-style:italic;margin-bottom:4px>"+_e(sub)+"</div>" if sub else ""}'
                f'<div style="width:48px;height:3px;background:{TEA};margin-bottom:8px"></div>'
                f'{body_html}</div></div>')

    def _2col_cards(items, chk=False):
        c1 = "".join(_card(items[i], i, chk) for i in range(0, len(items), 2))
        c2 = "".join(_card(items[i], i, chk) for i in range(1, len(items), 2))
        return f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 12px"><div>{c1}</div><div>{c2}</div></div>'

    # ── accumulate slides ──────────────────────────────────────────────
    SL = []   # (title, inner_html)
    def add(t, h): SL.append((_e(t), h))

    # 1. COVER
    add(PROJ_TYPE or "Enterprise AI Solution",
        f'<div style="position:absolute;inset:0;background:{IND};overflow:hidden">'
        f'{_lbar()}{_osq()}{_logo(dark=True)}'
        f'<div style="position:absolute;left:3.5%;top:17%;width:67%;z-index:5">'
        f'<div style="font-size:clamp(18px,3.5vw,52px);font-weight:900;color:{WHI};line-height:1.08;letter-spacing:-.3px">{_e(PROJ_TYPE or "Enterprise AI Solution")}</div>'
        f'<div style="width:15%;height:4px;background:{TEA};margin:4% 0 2%"></div>'
        f'<div style="font-size:clamp(10px,1.35vw,18px);font-weight:700;color:{TEA};margin-bottom:5px">AI Solution Proposal</div>'
        f'<div style="font-size:clamp(9px,1.05vw,14px);font-weight:700;color:{LIM}">PROJECT PROPOSAL</div>'
        f'<div style="font-size:clamp(8px,.88vw,12px);color:rgba(180,178,230,.8);margin-top:4%">{_e(DATE_STR)}</div>'
        f'</div>'
        f'<div style="position:absolute;left:3.5%;bottom:3.5%;font-size:clamp(7px,.75vw,10px);color:rgba(120,118,180,.6);z-index:5;font-style:italic">Confidential &nbsp;•&nbsp; ECI &nbsp;•&nbsp; AI Solutions</div>'
        f'</div>')

    # 2. AGENDA
    ag_items = ["Introduction & About ECI","What We Do","Business Context & Challenge",
                "Proposed Solution & Architecture","Key Capabilities & Technology",
                "Project Phases & Timeline","Scope of Work","Investment Summary",
                "Risk Management","Next Steps"]
    ag_rows = "".join(
        f'<div style="display:flex;align-items:center;gap:11px;padding:5px 0;border-bottom:1px solid rgba(29,27,75,.06)">'
        f'<span style="font-size:clamp(14px,1.8vw,22px);font-weight:900;color:{TEA};min-width:26px">{i+1:02d}</span>'
        f'<span style="font-size:clamp(9px,1vw,13px);font-weight:600;color:{IND}">{_e(it)}</span></div>'
        for i, it in enumerate(ag_items[:10]))
    add("Agenda",
        f'<div style="position:absolute;inset:0;background:{WHI};overflow:hidden">'
        f'{_trule()}{_logo(dark=False)}{_foot(dark=False)}'
        f'<div style="position:absolute;left:.5%;top:13%;width:33%;height:74%;background:{IND};z-index:3;'
        f'display:flex;align-items:center;justify-content:center">'
        f'<span style="font-size:clamp(22px,3.5vw,48px);font-weight:900;color:{WHI}">Agenda</span></div>'
        f'<div style="position:absolute;left:37%;top:13%;right:2%;z-index:5">{ag_rows}</div>'
        f'</div>')

    # 3–5: section + what we do + business context
    add("Introduction", _sec_slide("Introduction", "Understanding Your Business Vision"))

    svc9 = [("DIGITAL EXPERIENCE DESIGN","Design new experiences for customers & teams."),
            ("CLOUD DEPLOYMENT","Migrate to AWS, Azure & GCP cloud environments."),
            ("CUSTOM WORKFLOW APPLICATIONS","Develop products to streamline key processes."),
            ("BI & ANALYTICS","Implement BI and Data Analytics from inception."),
            ("INNOVATION & STRATEGY","Rapid prototyping and innovation labs."),
            ("DEVOPS & AGILE","Enable engineering teams with speed & flexibility."),
            ("SYSTEMS INTEGRATION","Accelerate platform deployment across the org."),
            ("ROBOTIC PROCESS AUTOMATION & AI/ML","Implement RPA and AI/ML for efficiency."),
            ("SECURITY & COMPLIANCE","Enterprise-grade security, ISO 27001 certified.")]
    wwd_cells = "".join(
        f'<div style="display:flex;gap:6px;align-items:flex-start;padding:5px 3px 5px 0;border-bottom:1px solid rgba(29,27,75,.06)">'
        f'<div style="width:20px;height:20px;background:{CRD};border:1.5px solid {ACC[i%6]};border-radius:3px;'
        f'flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:8px;color:{ACC[i%6]};margin-top:1px">{i+1}</div>'
        f'<div><div style="font-size:clamp(7px,.78vw,10px);font-weight:700;color:{IND}">{_e(t)}</div>'
        f'<div style="font-size:clamp(6px,.7vw,9px);color:{MID};line-height:1.35">{_e(d)}</div></div></div>'
        for i, (t, d) in enumerate(svc9))
    add("What We Do",
        f'<div style="position:absolute;inset:0;background:{WHI};overflow:hidden">'
        f'<div style="position:absolute;right:0;top:0;width:26%;bottom:0;background:rgba(210,214,232,.15)"></div>'
        f'{_logo(dark=False, pos="left:2%;top:1.5%")}'
        f'<div style="position:absolute;left:2%;top:9%;right:2%;z-index:5">'
        f'<div style="font-size:clamp(15px,2.4vw,34px);font-weight:900;color:{IND};margin-bottom:2px">What we do – Driving Transformation</div>'
        f'<div style="width:18%;height:3px;background:{TEA};margin-bottom:4px"></div>'
        f'<div style="background:{TEA};border-radius:3px;padding:3px 10px;font-size:clamp(8px,.82vw,11px);font-weight:700;color:{WHI};display:inline-block;margin-bottom:6px">DIGITAL BUSINESS TRANSFORMATION</div>'
        f'<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:0 10px">{wwd_cells}</div>'
        f'</div>{_foot(dark=False)}</div>')

    obj_items = objectives[:6] or [safe_str(safe_dict(r2).get("title","")) for r2 in reqs[:6]] or ["Delivering transformative AI solution"]
    add("Business Context", _light_slide("Business Context", "Strategic objectives driving this initiative", _2col_cards(obj_items[:8])))

    # 6–8: section + arch + tech grid
    add("Proposed Solution", _sec_slide("Proposed Solution", "Innovation Engineered for Your Business"))

    comp_names = [safe_str(safe_dict(c).get("name","")) for c in arch_comps[:8]]
    if not comp_names:
        comp_names = tech_stack or ["Azure OpenAI","Azure App Service","Azure AI Search","Cosmos DB","Azure Functions","Key Vault","Azure AD","Application Insights"]
    add("Solution Architecture", _light_slide("Solution Architecture", arch_pat or "Azure-native cloud-first architecture", _2col_cards(comp_names[:8])))

    tech_cells = "".join(
        f'<div style="background:{CRD};border-radius:4px;padding:7% 6%;border-left:4px solid {ACC[i%6]}">'
        f'<div style="font-size:clamp(7px,.85vw,11px);font-weight:700;color:{IND};line-height:1.3">{_e(comp_names[i])}</div></div>'
        for i in range(len(comp_names[:9])))
    add("Key Technology Components", _light_slide("Key Technology Components", arch_pat or "Microsoft Azure Cloud Platform",
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:7px">{tech_cells}</div>'))

    # 9. VALUE AT A GLANCE (dark KPI)
    k_dur  = (dur_weeks+" wks") if dur_weeks else "TBD"
    k_hrs  = ("%dk"%(total_hours//1000)) if total_hours>=1000 else (str(total_hours)+"h") if total_hours else "TBD"
    k_cost = ("$%s"%"{:,}".format(annual_c)) if annual_c else "TBD"
    kpi_cells = "".join(
        f'<div style="background:{IND2};border-radius:7px;padding:7% 4%;text-align:center;border-top:4px solid {ACC[i]}">'
        f'<div style="font-size:clamp(20px,3.8vw,52px);font-weight:900;color:{WHI};line-height:1">{_e(v)}</div>'
        f'<div style="font-size:clamp(8px,1.05vw,14px);font-weight:700;color:{ACC[i]};margin:5px 0 3px">{_e(lb)}</div>'
        f'<div style="font-size:clamp(7px,.82vw,11px);color:{NRW};opacity:.8">{_e(ds)}</div></div>'
        for i,(v,lb,ds) in enumerate([(k_dur,"Timeline","Discovery to go-live"),(k_hrs,"Total Effort","Engineering hours"),(k_cost,"Annual Cost","Total investment")]))
    add("Value at a Glance",
        f'<div style="position:absolute;inset:0;background:{IND};overflow:hidden">'
        f'{_osq()}{_logo(dark=True)}{_foot(dark=True)}'
        f'<div style="position:absolute;left:3%;top:6%;right:3%;z-index:5">'
        f'<div style="font-size:clamp(15px,2vw,26px);font-weight:900;color:{WHI};text-align:center;margin-bottom:5px">Value at a Glance</div>'
        f'<div style="width:18%;height:3px;background:{TEA};margin:0 auto 12px"></div>'
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">{kpi_cells}</div>'
        f'</div></div>')

    # 10–11: section + timeline
    add("Implementation Plan", _sec_slide("Implementation Plan", "Structured for Certainty & Speed"))

    if phases:
        total_h = max(sum(safe_int(safe_dict(p).get("hours",1)) for p in phases[:6]), 1)
        ph_bars = "".join(
            f'<div style="flex:{max(safe_int(safe_dict(phases[i]).get("hours",total_h//len(phases))),1)};background:{ACC[i%6]};'
            f'padding:5px 3px;min-width:28px;text-align:center;overflow:hidden">'
            f'<div style="font-size:clamp(6px,.7vw,9px);font-weight:700;color:{WHI};white-space:nowrap;overflow:hidden">{_e(str(safe_dict(phases[i]).get("name","P"+str(i+1)))[:12])}</div>'
            f'<div style="font-size:clamp(5px,.62vw,8px);color:rgba(255,255,255,.8)">{safe_int(safe_dict(phases[i]).get("hours",0))}h</div>'
            f'</div>' for i in range(min(len(phases),6)))
        ph_desc = "".join(
            f'<div style="background:{CRD};border-radius:4px;padding:6px 7px;border-left:3px solid {ACC[i%6]}">'
            f'<div style="font-size:clamp(7px,.82vw,10px);font-weight:700;color:{IND}">{_e(safe_str(safe_dict(phases[i]).get("name","")))}</div>'
            f'<div style="font-size:clamp(6px,.72vw,9px);color:{MID};margin-top:2px">{_e(safe_str(safe_dict(phases[i]).get("description",""))[:60])}</div>'
            f'</div>' for i in range(min(len(phases),6)))
        ph_body = (f'<div style="display:flex;border-radius:4px;overflow:hidden;height:44px;margin-bottom:9px">{ph_bars}</div>'
                   f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:6px">{ph_desc}</div>')
    else:
        ph_body = _2col_cards(["Phase 1-2: Discovery & Architecture","Phase 3-4: Development & Integration","Phase 5: Testing, UAT & Go-live"])
    add("Project Phases & Timeline", _light_slide("Project Phases & Timeline", "", ph_body))

    # 12–15: scope section + scope + out + assumptions
    add("Scope of Work", _sec_slide("Scope of Work", "Clarity Drives Successful Delivery"))
    if in_scope:
        add("Scope of Work — Deliverables", _light_slide("Scope of Work", "Committed deliverables", _2col_cards(in_scope[:8], chk=True)))
    if out_scope:
        add("Out of Scope", _light_slide("Out of Scope", "Exclusions & change-request conditions", _2col_cards(out_scope[:6])))
    all_pre = (assumps + prereqs)[:8] or ["Azure subscription provisioned","Sample data available Week 1","Stakeholder availability for reviews","Access to existing systems granted"]
    add("Assumptions & Pre-Requisites", _light_slide("Assumptions & Pre-Requisites", "Foundation commitments for successful delivery", _2col_cards(all_pre[:8], chk=True)))

    # 16: section investment
    add("Investment", _sec_slide("Investment", "Transparent Pricing, Measurable ROI"))

    # 17. TEAM COMPOSITION
    team_roles = []
    for ph in phases[:5]:
        pd = safe_dict(ph); nm = safe_str(pd.get("name","")); hrs = safe_int(pd.get("hours",0))
        if nm: team_roles.append({"role":nm,"hours":str(hrs) if hrs else ""})
    if not team_roles:
        for nm2 in ["Project Manager","AI Architect","AI Engineer","QA Engineer","DevOps"]:
            team_roles.append({"role":nm2,"hours":""})
    role_cards = "".join(
        f'<div style="background:{CRD};border-radius:4px;padding:7px 6px;border-top:3px solid {ACC[i%6]}">'
        f'<div style="font-size:clamp(7px,.8vw,10px);font-weight:700;color:{IND}">{_e(safe_str(tr.get("role","") if isinstance(tr,dict) else tr))}</div>'
        f'{"<div style=font-size:clamp(11px,1.4vw,18px);font-weight:900;color:"+ACC[i%6]+";text-align:center;margin-top:3px>"+_e(safe_str(tr.get("hours","")))+"h</div>" if isinstance(tr,dict) and tr.get("hours") else ""}'
        f'</div>' for i,tr in enumerate(team_roles[:5]))
    tl_items2 = [safe_str(safe_dict(p).get("name",""))+" – "+str(safe_int(safe_dict(p).get("hours",0)))+"h" for p in phases[:4]] or ["Phase 1-2: Discovery & Architecture","Phase 3-4: Development & Integration","Phase 5: Testing & Go-live"]
    tl_html = "".join(f'<div style="display:flex;gap:7px;align-items:flex-start;margin-bottom:5px"><span style="color:{TEA}">✔</span><span style="font-size:clamp(8px,.88vw,11px);color:{IND}">{_e(t)}</span></div>' for t in tl_items2[:4])
    add("Team Composition & Timeline",
        f'<div style="position:absolute;inset:0;background:{WHI};overflow:hidden">'
        f'{_trule()}{_logo(dark=False)}{_foot(dark=False)}'
        f'<div style="position:absolute;left:3%;top:8%;right:3%;z-index:5">'
        f'<div style="font-size:clamp(15px,2vw,26px);font-weight:900;color:{IND};margin-bottom:2px">Team Composition &amp; Timeline</div>'
        f'<div style="width:48px;height:3px;background:{TEA};margin-bottom:8px"></div>'
        f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:7px;margin-bottom:10px">{role_cards}</div>'
        f'<div style="border-top:1px solid rgba(29,27,75,.1);padding-top:7px">'
        f'<div style="font-size:clamp(10px,1.1vw,14px);font-weight:700;color:{IND};margin-bottom:5px">Project Timeline{"  —  "+dur_weeks+" weeks" if dur_weeks else ""}</div>'
        f'{tl_html}</div></div></div>')

    # 18. PROPOSAL SUMMARY (3 col, outline circles)
    sum_roles = [safe_str(tr.get("role",tr) if isinstance(tr,dict) else tr) for tr in team_roles[:5]]
    dur_items = [(dur_weeks+" weeks") if dur_weeks else "TBD","Discovery • Design","Implementation • QA","UAT • Go-Live"]
    cost_items = [("Total: $%s"%"{:,}".format(annual_c)) if annual_c else "TBD","Annual investment","Milestone-based billing","Includes training & support"]
    def _sum_col(label, items, color):
        bullets = "".join(
            f'<div style="display:flex;gap:5px;margin-bottom:4px">'
            f'<span style="color:{color};flex-shrink:0">☐</span>'
            f'<span style="font-size:clamp(7px,.8vw,11px);color:{IND}">{_e(safe_str(it)[:50])}</span></div>'
            for it in items[:5])
        return (f'<div style="padding:0 6px;text-align:center">'
                f'<div style="width:44px;height:44px;border-radius:50%;border:3px solid {color};'
                f'display:flex;align-items:center;justify-content:center;margin:0 auto 4px;font-size:16px;color:{color}">◉</div>'
                f'<div style="font-size:clamp(11px,1.4vw,18px);font-weight:900;color:{color};margin-bottom:4px">{_e(label)}</div>'
                f'<div style="width:35%;height:2px;background:{color};margin:0 auto 7px"></div>'
                f'<div style="text-align:left">{bullets}</div></div>')
    sum_body = (f'<div style="display:grid;grid-template-columns:1fr 1px 1fr 1px 1fr;gap:0;align-items:start">'
                f'{_sum_col("Team",sum_roles,TEA)}'
                f'<div style="background:rgba(29,27,75,.12);align-self:stretch"></div>'
                f'{_sum_col("Duration",dur_items,ORG)}'
                f'<div style="background:rgba(29,27,75,.12);align-self:stretch"></div>'
                f'{_sum_col("Cost",cost_items,LIM)}'
                f'</div>')
    add("Proposal Summary",
        f'<div style="position:absolute;inset:0;background:{WHI};overflow:hidden">'
        f'{_logo(dark=False, pos="left:2%;top:1.5%")}{_foot(dark=False)}'
        f'<div style="position:absolute;left:3%;top:9%;right:3%;z-index:5">'
        f'<div style="font-size:clamp(15px,2vw,26px);font-weight:900;color:{IND};margin-bottom:2px">Proposal Summary</div>'
        f'<div style="width:48px;height:3px;background:{TEA};margin-bottom:10px"></div>'
        f'{sum_body}</div></div>')

    # 19. INVESTMENT SUMMARY (dark)
    ann_str = ("$%s"%"{:,}".format(annual_c)) if annual_c else "TBD"
    cost_lines = []
    for sv in svcs[:5]:
        sd = safe_dict(sv); sn = safe_str(sd.get("service","")); sc2 = safe_int(sd.get("monthly_cost",0))
        if sn: cost_lines.append("%s — $%s/mo"%(sn,"{:,}".format(sc2)))
    if not cost_lines: cost_lines = ["Azure OpenAI Service","Azure App Service","Azure AI Search"]
    cost_lines.append("Milestone-based payment structure")
    cost_lines.append("Includes: documentation, training & warranty support")
    c_blt = "".join(f'<div style="display:flex;gap:8px;margin-bottom:6px"><span style="color:rgba(195,193,230,.7)">•</span><span style="font-size:clamp(8px,.9vw,13px);color:rgba(195,193,230,.85)">{_e(cl)}</span></div>' for cl in cost_lines[:6])
    add("Investment Summary",
        f'<div style="position:absolute;inset:0;background:{IND};overflow:hidden">'
        f'{_osq()}{_logo(dark=True)}{_foot(dark=True)}'
        f'<div style="position:absolute;left:3.5%;top:8%;right:3%;z-index:5">'
        f'<div style="font-size:clamp(8px,.85vw,12px);font-weight:700;color:{TEA};letter-spacing:1.5px;margin-bottom:5px">INVESTMENT SUMMARY</div>'
        f'<div style="font-size:clamp(28px,6vw,80px);font-weight:900;color:{WHI};line-height:1;margin-bottom:6px">{_e(ann_str)}</div>'
        f'<div style="font-size:clamp(10px,1.2vw,16px);font-weight:700;color:{LIM};margin-bottom:8px">Estimated Total Annual Investment</div>'
        f'<div style="width:22%;height:3px;background:{TEA};margin-bottom:10px"></div>'
        f'{c_blt}</div>'
        f'{"<div style=position:absolute;right:3.5%;top:12%;background:"+IND2+";border-radius:7px;padding:14px 18px;border-top:4px solid "+TEA+";text-align:center;z-index:5><div style=font-size:clamp(16px,2.4vw,32px);font-weight:900;color:"+WHI+">$"+"{:,}".format(monthly_c)+"</div><div style=font-size:clamp(8px,.88vw,12px);color:"+TEA+";margin-top:3px>per month</div></div>" if monthly_c else ""}'
        f'</div>')

    # 20–21: section + risk register
    add("Risk Management", _sec_slide("Risk Management", "Proactive Identification & Mitigation"))

    SEV_C = {"critical":RED,"high":RED,"medium":AMB,"low":GRN}
    if risk_list:
        hdr = (f'<div style="display:grid;grid-template-columns:3fr 80px 3fr;gap:0;background:{IND};border-radius:4px 4px 0 0;padding:4px 8px">'
               f'<div style="font-size:clamp(7px,.78vw,10px);font-weight:700;color:{WHI}">Risk</div>'
               f'<div style="font-size:clamp(7px,.78vw,10px);font-weight:700;color:{WHI}">Severity</div>'
               f'<div style="font-size:clamp(7px,.78vw,10px);font-weight:700;color:{WHI}">Mitigation</div></div>')
        rows2 = "".join(
            f'<div style="display:grid;grid-template-columns:3fr 80px 3fr;gap:0;background:{""+CRD if ri2%2==0 else "#ECEEF8"};padding:5px 8px;border-left:3px solid {SEV_C.get(safe_str(safe_dict(risk_list[ri2]).get("severity","medium")).lower(),AMB)}">'
            f'<div style="font-size:clamp(7px,.82vw,11px);font-weight:700;color:{IND}">{_e(safe_str(safe_dict(risk_list[ri2]).get("title","")))}</div>'
            f'<div><span style="background:{SEV_C.get(safe_str(safe_dict(risk_list[ri2]).get("severity","med")).lower(),AMB)};color:{WHI};font-size:clamp(6px,.7vw,9px);font-weight:700;padding:1px 5px;border-radius:3px">{_e(safe_str(safe_dict(risk_list[ri2]).get("severity","Med")))}</span></div>'
            f'<div style="font-size:clamp(7px,.78vw,10px);color:{MID};line-height:1.35">{_e(safe_str(safe_dict(risk_list[ri2]).get("mitigation",""))[:80])}</div>'
            f'</div>'
            for ri2 in range(min(len(risk_list),6)))
        risk_body = hdr + rows2
    else:
        risk_body = _2col_cards(["Integration complexity — phased rollout","Data quality issues — data profiling sprint","Timeline dependencies — early environment setup","Change management — stakeholder workshops"])
    add("Risk Register", _light_slide("Risk Register","",risk_body))

    # 22. NEXT STEPS (dark)
    ns_items = ["Review & provide written feedback on this proposal","Schedule technical deep-dive with ECI architects","Finalize and sign Statement of Work (SOW)","Environment access & onboarding completed","Project kick-off — sprint planning & team introductions"]
    ns_html = "".join(
        f'<div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:9px">'
        f'<div style="width:28px;height:28px;border-radius:50%;background:{ACC[i%6]};flex-shrink:0;'
        f'display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:900;color:{WHI}">{i+1}</div>'
        f'<span style="font-size:clamp(9px,1.05vw,14px);color:{WHI};padding-top:5px">{_e(s)}</span></div>'
        for i, s in enumerate(ns_items[:5]))
    add("Next Steps",
        f'<div style="position:absolute;inset:0;background:{IND};overflow:hidden">'
        f'{_lbar()}{_osq()}{_logo(dark=True)}{_foot(dark=True)}'
        f'<div style="position:absolute;left:3.5%;top:10%;right:20%;z-index:5">'
        f'<div style="font-size:clamp(20px,3.5vw,44px);font-weight:900;color:{WHI};margin-bottom:4px">Next Steps</div>'
        f'<div style="width:18%;height:4px;background:{TEA};margin-bottom:14px"></div>'
        f'{ns_html}</div></div>')

    # 23. CONTACT (dark, 2×2 squares)
    soc_html = "".join(
        f'<div style="width:48px;height:48px;border-radius:50%;background:{WHI};flex-shrink:0;'
        f'display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:900;color:{IND}">{lbl}</div>'
        for lbl in ["f","t","in"])
    add("Contact",
        f'<div style="position:absolute;inset:0;background:{IND};overflow:hidden">'
        f'{_logo(dark=True, pos="right:1.6%;top:1.4%")}'
        f'<div style="position:absolute;right:0;top:27%;width:30%;height:73%;display:grid;grid-template-columns:1fr 1fr;gap:0">'
        f'<div style="background:{IND2}"></div><div style="background:{IND3}"></div>'
        f'<div style="background:{IND3}"></div><div style="background:{IND2}"></div></div>'
        f'<div style="position:absolute;left:6%;top:22%;width:1px;bottom:5%;background:rgba(75,72,130,.7)"></div>'
        f'<div style="position:absolute;left:1%;top:22%;display:flex;flex-direction:column;gap:16px;z-index:5">{soc_html}</div>'
        f'<div style="position:absolute;left:9%;top:20%;right:32%;z-index:5">'
        f'<div style="font-size:clamp(14px,1.9vw,26px);font-weight:900;color:{WHI};margin-bottom:4%">Corporate Headquarters</div>'
        f'<div style="font-size:clamp(8px,.9vw,13px);color:{NRW};margin-bottom:2%">529 Fifth Avenue, 7th floor</div>'
        f'<div style="font-size:clamp(8px,.9vw,13px);color:{NRW};margin-bottom:5%">New York, New York, 10017</div>'
        f'<div style="font-size:clamp(14px,1.9vw,26px);font-weight:900;color:{WHI};margin-bottom:4%">Global Sales</div>'
        f'<div style="font-size:clamp(8px,.9vw,13px);color:{NRW};margin-bottom:1.5%">US: +1 800 752 1382</div>'
        f'<div style="font-size:clamp(8px,.9vw,13px);color:{NRW};margin-bottom:1.5%">UK: +44 207 0716802</div>'
        f'<div style="font-size:clamp(8px,.9vw,13px);color:{NRW};margin-bottom:1.5%">Singapore: +65 66222345</div>'
        f'<div style="font-size:clamp(8px,.9vw,13px);color:{NRW}">Hong Kong: +852 3189 0101</div>'
        f'</div></div>')

    # ── build embedded download strip (base64 data-URI — zero Streamlit rerun) ──
    import base64 as _b64
    _dl_strip = ""
    if pptx_bytes:
        try:
            _p64 = _b64.b64encode(pptx_bytes).decode("ascii")
            _pptx_mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
            _fname = f"ECI_Proposal_{_dt.now().strftime('%Y%m%d_%H%M%S')}.pptx"
            _dl_strip = (
                f'<div id="dl" style="display:flex;gap:8px;padding:8px 0 4px">'
                f'<a id="dl-pptx" href="data:{_pptx_mime};base64,{_p64}" download="{_fname}" '
                f'style="flex:1;display:block;text-align:center;background:{IND};color:#fff;'
                f'padding:9px 16px;border-radius:6px;text-decoration:none;font-size:13px;'
                f'font-weight:700;border:1px solid {TEA};transition:background .15s;'
                f'font-family:Segoe UI,Arial,sans-serif" '
                f'onmouseover="this.style.background=\'{TEA}\'" '
                f'onmouseout="this.style.background=\'{IND}\'">'
                f'&#128202; Download PowerPoint (.pptx)</a>'
                f'</div>'
            )
        except Exception:
            _dl_strip = ""

    # ── nav wrapper ────────────────────────────────────────────────────
    total = len(SL)
    titles_js = str([t for t, _ in SL])
    slide_divs = "\n".join(
        f'<div class="sl" style="display:{"block" if i==0 else "none"}" data-id="{i+1}">{h}</div>'
        for i, (_, h) in enumerate(SL))
    thumb_html = "".join(
        f'<div class="th{" active" if i==0 else ""}" onclick="jump({i})" id="th{i}" title="Slide {i+1}">'
        f'{i+1}. {t[:18]}</div>'
        for i, (t, _) in enumerate(SL))

    _viewer_h = "100vh" if not pptx_bytes else "auto"

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#06060f;color:#e2e8f0;min-height:100vh;display:flex;flex-direction:column}}
#viewer{{flex:1;display:flex;flex-direction:column;max-width:1000px;margin:0 auto;width:100%;padding:10px}}
#stage{{position:relative;width:100%;padding-top:56.25%;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 16px 56px rgba(0,0,0,.75)}}
.sl{{position:absolute;inset:0;font-family:'Segoe UI',Arial,sans-serif}}
#nav{{display:flex;align-items:center;justify-content:space-between;padding:9px 0;gap:10px;flex-wrap:wrap}}
.nb{{background:{IND};color:#fff;border:none;padding:7px 20px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700;letter-spacing:.3px;transition:background .15s}}
.nb:hover{{background:{TEA}}}
.nb:disabled{{background:#0d0d22;color:#444;cursor:not-allowed}}
#counter{{font-size:13px;color:#7070a0;font-weight:600}}
#progress{{flex:1;height:3px;background:#0d0d22;border-radius:3px;min-width:80px}}
#bar{{height:100%;background:linear-gradient(90deg,{TEA},{LIM});border-radius:3px;transition:width .3s}}
#thumbs{{display:flex;gap:7px;overflow-x:auto;padding:7px 0;scrollbar-width:thin;scrollbar-color:{IND} transparent}}
.th{{flex-shrink:0;width:88px;height:50px;background:#0d0d22;border:2px solid transparent;border-radius:4px;cursor:pointer;font-size:8.5px;color:#444470;display:flex;align-items:center;justify-content:center;text-align:center;padding:3px;overflow:hidden;transition:border-color .15s;line-height:1.3}}
.th:hover{{border-color:{TEA}}}
.th.active{{border-color:{LIM};color:{LIM}}}
#info{{background:{IND};border-radius:7px;padding:7px 13px;font-size:11px;color:#7070a0;margin-top:3px}}
#stitle{{font-weight:700;color:#e2e8f0;margin-bottom:2px}}
</style></head><body>
<div id="viewer">
  <div id="stage">{slide_divs}</div>
  <div id="nav">
    <button class="nb" id="prevBtn" onclick="go(-1)" disabled>&#8249; Prev</button>
    <div id="progress"><div id="bar" style="width:{100//max(total,1)}%"></div></div>
    <span id="counter">1 / {total}</span>
    <button class="nb" id="nextBtn" onclick="go(1)">Next &#8250;</button>
  </div>
  <div id="thumbs">{thumb_html}</div>
  <div id="info">
    <div id="stitle">Slide 1: {SL[0][0] if SL else ""}</div>
    <div>{_e(_client)} &nbsp;·&nbsp; {_e(PROJ_TYPE)} &nbsp;·&nbsp; {_e(DATE_STR)} &nbsp;·&nbsp; {total} slides</div>
  </div>
  {_dl_strip}
</div>
<script>
var cur=0,tot={total};
var titles={titles_js};
function show(n){{
  document.querySelectorAll('.sl').forEach(function(s){{s.style.display='none'}});
  document.querySelectorAll('.th').forEach(function(t,i){{t.className='th'+(i===n?' active':'')}});
  var el=document.querySelector('.sl[data-id="'+(n+1)+'"]');
  if(el)el.style.display='block';
  cur=n;
  document.getElementById('counter').textContent=(n+1)+' / '+tot;
  document.getElementById('bar').style.width=((n+1)/tot*100)+'%';
  document.getElementById('prevBtn').disabled=(n===0);
  document.getElementById('nextBtn').disabled=(n===tot-1);
  document.getElementById('stitle').textContent='Slide '+(n+1)+': '+(titles[n]||'');
  var th=document.getElementById('th'+n);
  if(th)th.scrollIntoView({{block:'nearest',inline:'center',behavior:'smooth'}});
}}
function go(d){{var n=cur+d;if(n>=0&&n<tot)show(n);}}
function jump(n){{show(n);}}
document.addEventListener('keydown',function(e){{
  if(e.key==='ArrowRight'||e.key===' ')go(1);
  else if(e.key==='ArrowLeft')go(-1);
}});
</script></body></html>"""


# ═══════════════════════════════════════════════════════════════════════
#  HTML SLIDE PREVIEW  (Claude-content driven)
# ═══════════════════════════════════════════════════════════════════════

def build_claude_ppt_preview_html(slide_content: dict, results: dict = None) -> str:
    from datetime import datetime as _dt
    slides  = slide_content.get("slides", [])
    client  = slide_content.get("client", "Client")
    title   = slide_content.get("presentation_title", "AI Solution Proposal")
    tagline = slide_content.get("tagline", "Transforming Business with Intelligent Technology")
    date    = slide_content.get("date", _dt.now().strftime("%B %Y"))
    total   = len(slides)

    INDIGO = "#1D1B4B"; IND2   = "#2D2A6E"; IND3 = "#3C397C"
    TEAL   = "#00B0A0"; LIME   = "#94C11C"; ORG  = "#EA752A"
    GREEN  = "#22B373"; PUR    = "#7B61FF"; AMBER= "#F59E0B"
    NEARW  = "#DCDCF8"; MID    = "#64625E"; CARD = "#F4F5FF"

    ACC_LIST = [TEAL, ORG, GREEN, PUR, LIME, AMBER]

    def _e(s):
        return str(s).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"','&quot;')

    def _logo_html(dark=True):
        c = "#fff" if dark else INDIGO
        return (f'<div style="position:absolute;right:1.5%;top:1.5%;z-index:10;'
                f'font-size:clamp(13px,1.8vw,26px);font-weight:900;color:{c};letter-spacing:.5px">'
                f'ECI<sup style="font-size:50%;color:{TEAL}">+</sup></div>')

    def _offset_sq(dark=True):
        b = IND2 if dark else "#DCDEF8"; a = IND3 if dark else "#C4C7EE"
        return (f'<div style="position:absolute;right:0;top:0;width:12.5%;padding-top:22%;background:{b};z-index:2"></div>'
                f'<div style="position:absolute;right:0;top:7%;width:12.5%;padding-top:22%;'
                f'margin-right:12.5%;background:{a};z-index:2"></div>')

    def _left_bar():
        return f'<div style="position:absolute;left:0;top:0;bottom:0;width:1.05%;background:{TEAL};z-index:6"></div>'

    def _top_rule():
        return f'<div style="position:absolute;left:0;top:0;width:100%;height:.65%;background:{TEAL};z-index:4"></div>'

    def _footer(dark=True):
        c = "rgba(140,138,210,.55)" if dark else "rgba(100,98,160,.45)"
        return (f'<div style="position:absolute;bottom:2.5%;left:3.5%;font-size:clamp(7px,.75vw,10px);'
                f'color:{c};font-style:italic;z-index:5">ECI  •  Confidential</div>'
                f'<div style="position:absolute;bottom:2.5%;right:2%;font-size:clamp(7px,.75vw,10px);'
                f'color:{c};z-index:5">{_e(date)}</div>')

    def _card_html(text, idx, checkmark=False):
        acc = ACC_LIST[idx % len(ACC_LIST)]
        bullet = "☑" if checkmark else "▸"
        return (f'<div style="display:flex;gap:0;background:{CARD};margin-bottom:5px;border-radius:4px;overflow:hidden">'
                f'<div style="width:4px;background:{acc};flex-shrink:0"></div>'
                f'<div style="padding:5px 8px;font-size:clamp(8px,.95vw,12px);color:{INDIGO};line-height:1.4">'
                f'<span style="color:{acc};margin-right:5px">{bullet}</span>{_e(text)}</div></div>')

    def _bullet(txt, color=TEAL):
        return (f'<div style="display:flex;gap:8px;align-items:flex-start;margin-bottom:7px">'
                f'<span style="color:{color};font-size:1.1em;flex-shrink:0;margin-top:1px">▸</span>'
                f'<span style="font-size:clamp(9px,1.05vw,14px);color:#1a1a3a;line-height:1.5">{_e(txt)}</span>'
                f'</div>')

    slide_divs = []

    for sl in slides:
        sid    = sl.get("id", 0)
        stype  = sl.get("type", "content")
        stitle = _e(sl.get("title", ""))
        ssub   = _e(sl.get("subtitle", ""))
        bullets = sl.get("bullets", [])
        callout = _e(sl.get("callout", ""))
        headline= _e(sl.get("headline", ""))

        # ── COVER ─────────────────────────────────────────────────────
        if stype == "cover":
            slabel = _e(sl.get("label", "PROJECT PROPOSAL"))
            inner = f"""
            <div style="position:absolute;inset:0;background:{INDIGO};overflow:hidden">
              {_left_bar()}{_offset_sq(dark=True)}{_logo_html(dark=True)}
              <div style="position:absolute;left:3.5%;top:21%;width:65%;z-index:5">
                <div style="font-size:clamp(22px,4.2vw,58px);font-weight:900;color:#fff;line-height:1.08;letter-spacing:-.5px">{stitle}</div>
                <div style="width:18%;height:4px;background:{TEAL};margin:4.5% 0 2%"></div>
                <div style="font-size:clamp(11px,1.45vw,20px);font-weight:700;color:{TEAL};margin-bottom:6px">{ssub or "AI Solution Proposal"}</div>
                <div style="font-size:clamp(10px,1.2vw,16px);font-weight:700;color:{LIME}">{slabel}</div>
                <div style="font-size:clamp(9px,.95vw,13px);color:rgba(180,178,230,.85);margin-top:4.5%">{_e(date)}</div>
              </div>
              <div style="position:absolute;left:3.5%;bottom:3.5%;font-size:clamp(8px,.8vw,11px);color:rgba(120,118,180,.7);z-index:5;font-style:italic">Confidential &nbsp;•&nbsp; ECI &nbsp;•&nbsp; AI Solutions</div>
            </div>"""

        # ── AGENDA ────────────────────────────────────────────────────
        elif stype == "agenda":
            items = sl.get("items", [])
            rows = "".join(
                f'<div style="display:flex;align-items:center;gap:14px;padding:7px 0;border-bottom:1px solid rgba(29,27,75,.07)">'
                f'<span style="font-size:clamp(16px,2vw,26px);font-weight:900;color:{TEAL};min-width:30px">{i+1:02d}</span>'
                f'<span style="font-size:clamp(10px,1.15vw,16px);font-weight:600;color:{INDIGO}">{_e(it)}</span>'
                f'</div>'
                for i, it in enumerate(items[:9])
            )
            inner = f"""
            <div style="position:absolute;inset:0;background:#fff;overflow:hidden">
              {_top_rule()}{_logo_html(dark=False)}{_footer(dark=False)}
              <div style="position:absolute;left:.5%;top:14%;width:33%;height:72%;background:{INDIGO};z-index:3;display:flex;align-items:center;justify-content:center">
                <span style="font-size:clamp(26px,4.2vw,54px);font-weight:900;color:#fff">Agenda</span>
              </div>
              <div style="position:absolute;left:37%;top:14%;right:2%;z-index:5">{rows}</div>
            </div>"""

        # ── SECTION ───────────────────────────────────────────────────
        elif stype == "section":
            inner = f"""
            <div style="position:absolute;inset:0;background:{INDIGO};overflow:hidden">
              {_left_bar()}{_offset_sq(dark=True)}{_logo_html(dark=True)}{_footer(dark=True)}
              <div style="position:absolute;left:3.5%;top:23%;right:20%;z-index:5">
                <div style="font-size:clamp(9px,.95vw,13px);font-weight:700;color:{TEAL};letter-spacing:2px;margin-bottom:8px">SECTION</div>
                <div style="width:14%;height:4px;background:{TEAL};margin-bottom:14px"></div>
                <div style="font-size:clamp(24px,4.2vw,52px);font-weight:900;color:#fff;line-height:1.1">{stitle}</div>
                {'<div style="font-size:clamp(10px,1.15vw,16px);color:'+TEAL+';margin-top:12px;font-weight:600">'+ssub+'</div>' if ssub else ''}
              </div>
            </div>"""

        # ── KPI METRICS ───────────────────────────────────────────────
        elif stype == "metrics":
            metrics = sl.get("metrics", [])
            acc_m = [TEAL, LIME, ORG]
            metric_cards = "".join(
                f'<div style="flex:1;min-width:120px;background:{IND2};border-radius:6px;overflow:hidden">'
                f'<div style="height:5px;background:{acc_m[mi%3]}"></div>'
                f'<div style="padding:18px 12px;text-align:center">'
                f'<div style="font-size:clamp(28px,4.2vw,58px);font-weight:900;color:#fff;line-height:1">{_e(m.get("value",""))}</div>'
                f'<div style="font-size:clamp(10px,1.1vw,15px);font-weight:700;color:{acc_m[mi%3]};margin:8px 0 5px">{_e(m.get("label",""))}</div>'
                f'<div style="font-size:clamp(8px,.85vw,12px);color:{NEARW}">{_e(m.get("desc",""))}</div>'
                f'</div></div>'
                for mi, m in enumerate(metrics[:3])
            )
            inner = f"""
            <div style="position:absolute;inset:0;background:{INDIGO};overflow:hidden">
              {_offset_sq(dark=True)}{_logo_html(dark=True)}{_footer(dark=True)}
              <div style="position:absolute;left:3%;top:12%;right:3%;z-index:5">
                <div style="font-size:clamp(18px,2.4vw,32px);font-weight:900;color:#fff;margin-bottom:4px;text-align:center">{stitle}</div>
                <div style="width:50px;height:4px;background:{TEAL};margin:0 auto 20px"></div>
                <div style="display:flex;gap:16px;flex-wrap:wrap;margin-top:10px">{metric_cards}</div>
              </div>
            </div>"""

        # ── NEXT STEPS ────────────────────────────────────────────────
        elif stype == "next_steps":
            steps = sl.get("steps", [])
            step_html = "".join(
                f'<div style="display:flex;align-items:flex-start;gap:14px;margin-bottom:14px">'
                f'<div style="min-width:36px;height:36px;border-radius:50%;background:{ACC_LIST[i%len(ACC_LIST)]};'
                f'display:flex;align-items:center;justify-content:center;'
                f'font-size:clamp(11px,1.4vw,18px);font-weight:900;color:#fff;flex-shrink:0">{i+1}</div>'
                f'<div style="font-size:clamp(11px,1.25vw,17px);color:#fff;line-height:1.45;font-weight:500;padding-top:5px">{_e(st_)}</div>'
                f'</div>'
                for i, st_ in enumerate(steps[:5])
            )
            inner = f"""
            <div style="position:absolute;inset:0;background:{INDIGO};overflow:hidden">
              {_left_bar()}{_offset_sq(dark=True)}{_logo_html(dark=True)}{_footer(dark=True)}
              <div style="position:absolute;left:3.5%;top:12%;right:18%;z-index:5">
                <div style="font-size:clamp(22px,3.2vw,42px);font-weight:900;color:#fff;margin-bottom:5px">{stitle}</div>
                <div style="width:55px;height:4px;background:{TEAL};margin-bottom:22px"></div>
                {step_html}
              </div>
            </div>"""

        # ── CONTACT ───────────────────────────────────────────────────
        elif stype == "contact":
            inner = f"""
            <div style="position:absolute;inset:0;background:{INDIGO};overflow:hidden">
              {_logo_html(dark=True)}
              <div style="position:absolute;right:0;bottom:0;width:13.3%;padding-top:23.8%;background:{IND2};z-index:2"></div>
              <div style="position:absolute;right:13.3%;bottom:0;width:13.3%;padding-top:23.8%;background:{IND3};z-index:2"></div>
              <div style="position:absolute;right:0;bottom:23.8%;width:13.3%;padding-top:23.8%;background:{IND3};z-index:2"></div>
              <div style="position:absolute;right:13.3%;bottom:23.8%;width:13.3%;padding-top:23.8%;background:{IND2};z-index:2"></div>
              <div style="position:absolute;left:20%;top:18%;bottom:5%;width:.25%;background:rgba(90,87,160,.5);z-index:3"></div>
              <div style="position:absolute;left:2%;top:22%;z-index:5;display:flex;flex-direction:column;gap:8px">
                {''.join(f'<div style="width:36px;height:36px;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:900;color:{c}">{l}</div>' for l,c in [("f","#3B5998"),("t","#1DA1F2"),("in",TEAL)])}
              </div>
              <div style="position:absolute;left:22%;top:19%;right:30%;z-index:5">
                <div style="font-size:clamp(14px,1.9vw,26px);font-weight:900;color:#fff;margin-bottom:6px">Corporate Headquarters</div>
                <div style="font-size:clamp(8px,.85vw,12px);color:rgba(190,188,230,.75);margin-bottom:12px">529 Fifth Avenue, 7th floor &nbsp;•&nbsp; New York, New York, 10017</div>
                <div style="font-size:clamp(14px,1.9vw,26px);font-weight:900;color:#fff;margin-bottom:6px">Global Sales</div>
                <div style="font-size:clamp(8px,.85vw,12px);color:rgba(190,188,230,.75);line-height:1.9">
                  US: +1 800 752 1382<br>UK: +44 207 0716802<br>Singapore: +65 66222345<br>Hong Kong: +852 3189 0101
                </div>
              </div>
            </div>"""

        # ── WHAT WE DO ────────────────────────────────────────────────────
        elif stype == "what_we_do":
            _wwd_default = [
                ("DIGITAL EXPERIENCE DESIGN",       "Customer & team experience innovation"),
                ("CLOUD DEPLOYMENT",                 "Azure, AWS & GCP migration and provisioning"),
                ("CUSTOM WORKFLOW APPLICATIONS",     "Streamline & reinvent key processes"),
                ("BI & ANALYTICS",                   "Data analytics from inception to deployment"),
                ("INNOVATION & STRATEGY",            "From rapid prototyping to innovation labs"),
                ("DEVOPS & AGILE",                   "Engineering team flexibility & speed"),
                ("SYSTEMS INTEGRATION",              "Accelerate platform deployment across org"),
                ("RPA & AI/ML",                      "Automation and AI to drive efficiency"),
                ("SECURITY & COMPLIANCE",            "Enterprise-grade ISO 27001 security"),
            ]
            wwd_svcs = sl.get("services", _wwd_default)
            # normalise to list of (title, desc) tuples
            _pairs = [(s if isinstance(s, (list, tuple)) and len(s) >= 2 else (str(s), ""))
                      for s in wwd_svcs[:9]]
            dot_cols = [_e(f'<div style="position:absolute;left:{58+gx*3.5:.0f}%;'
                           f'top:{gy*3.5:.0f}%;width:1.5%;padding-top:2.6%;'
                           f'background:rgba(180,185,220,.2)"></div>')
                        for gy in range(6) for gx in range(14)]
            dot_html = "".join(d.replace("&lt;", "<").replace("&gt;", ">")
                               .replace("&amp;", "&").replace("&quot;", '"')
                               for d in dot_cols)
            cells = []
            for bi, (t, d_) in enumerate(_pairs):
                ac = ACC_LIST[bi % len(ACC_LIST)]
                cells.append(
                    f'<div style="padding:3px 2px">'
                    f'<div style="display:flex;gap:5px;align-items:flex-start">'
                    f'<div style="min-width:26px;height:26px;border:1.5px solid {ac};border-radius:3px;'
                    f'display:flex;align-items:center;justify-content:center;'
                    f'font-size:10px;color:{ac};flex-shrink:0;margin-top:1px">&#9638;</div>'
                    f'<div style="width:2px;background:{INDIGO};align-self:stretch;margin:0 3px;flex-shrink:0"></div>'
                    f'<div>'
                    f'<div style="font-size:clamp(7px,.78vw,10.5px);font-weight:800;color:{INDIGO};'
                    f'letter-spacing:.2px;line-height:1.2">{_e(str(t))}</div>'
                    f'<div style="font-size:clamp(6px,.68vw,9px);color:{MID};line-height:1.35;margin-top:2px">'
                    f'{_e(str(d_))}</div>'
                    f'</div></div></div>'
                )
            cells_html = "".join(cells)
            inner = f"""
            <div style="position:absolute;inset:0;background:#fff;overflow:hidden">
              <div style="position:absolute;right:0;top:0;width:42%;height:30%;overflow:hidden;z-index:1">{dot_html}</div>
              <div style="position:absolute;left:2.5%;top:2%;z-index:6;font-size:clamp(13px,1.9vw,24px);font-weight:900;color:{INDIGO}">ECI<sup style="font-size:50%;color:{TEAL}">+</sup></div>
              <div style="position:absolute;left:2.5%;top:10%;right:4%;z-index:5">
                <div style="font-size:clamp(20px,3.3vw,44px);font-weight:900;color:{INDIGO};line-height:1.05;letter-spacing:-.5px">What we do – Driving Transformation</div>
                <div style="width:17%;height:5px;background:{TEAL};margin-top:6px"></div>
              </div>
              <div style="position:absolute;left:0;top:30%;right:0;padding:1.5% 0;background:{TEAL};z-index:5;text-align:center">
                <span style="font-size:clamp(10px,1.25vw,16px);font-weight:800;color:#fff;letter-spacing:1.5px">DIGITAL BUSINESS TRANSFORMATION</span>
              </div>
              <div style="position:absolute;left:1%;top:39%;right:1%;bottom:2%;z-index:5;display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5% 1.5%">
                {cells_html}
              </div>
            </div>"""

        # ── CONTENT (default — card grid) ──────────────────────────────
        else:
            col1 = [b for i, b in enumerate(bullets[:8]) if i % 2 == 0]
            col2 = [b for i, b in enumerate(bullets[:8]) if i % 2 == 1]
            cards1 = "".join(_card_html(b, i * 2) for i, b in enumerate(col1))
            cards2 = "".join(_card_html(b, i * 2 + 1) for i, b in enumerate(col2))
            callout_html = (
                f'<div style="margin-top:10px;padding:8px 14px;background:{INDIGO};border-radius:6px;'
                f'font-size:clamp(8px,.9vw,12px);font-weight:700;color:{TEAL}">{callout}</div>'
                if callout else ""
            )
            inner = f"""
            <div style="position:absolute;inset:0;background:#fff;overflow:hidden">
              {_top_rule()}{_logo_html(dark=False)}{_footer(dark=False)}
              <div style="position:absolute;left:3%;top:8%;right:3%;z-index:5">
                <div style="font-size:clamp(16px,2.2vw,28px);font-weight:900;color:{INDIGO};margin-bottom:3px">{stitle}</div>
                {'<div style="font-size:clamp(9px,1vw,13px);color:'+MID+';font-style:italic;margin-bottom:6px">'+headline+'</div>' if headline else ''}
                <div style="width:50px;height:3px;background:{TEAL};margin-bottom:10px"></div>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 16px">
                  <div>{cards1}</div>
                  <div>{cards2}</div>
                </div>
                {callout_html}
              </div>
            </div>"""

        slide_divs.append(
            f'<div class="sl" style="display:{"block" if sid==1 else "none"}" data-id="{sid}">{inner}</div>'
        )

    slides_html = "\n".join(slide_divs)

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#0a0a1e;color:#e2e8f0;min-height:100vh;display:flex;flex-direction:column}}
#viewer{{flex:1;display:flex;flex-direction:column;max-width:1000px;margin:0 auto;width:100%;padding:12px}}
#stage{{position:relative;width:100%;padding-top:56.25%;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 16px 56px rgba(0,0,0,.65)}}
.sl{{position:absolute;inset:0}}
#nav{{display:flex;align-items:center;justify-content:space-between;padding:10px 0;gap:10px;flex-wrap:wrap}}
.nb{{background:{INDIGO};color:#fff;border:none;padding:8px 22px;border-radius:6px;cursor:pointer;font-size:13px;font-weight:700;letter-spacing:.3px;transition:background .15s}}
.nb:hover{{background:{TEAL}}}
.nb:disabled{{background:#111130;color:#444;cursor:not-allowed}}
#counter{{font-size:13px;color:#7070a0;font-weight:600}}
#progress{{flex:1;height:3px;background:#111130;border-radius:3px;min-width:80px}}
#bar{{height:100%;background:linear-gradient(90deg,{TEAL},{LIME});border-radius:3px;transition:width .3s}}
#thumbs{{display:flex;gap:8px;overflow-x:auto;padding:8px 0;scrollbar-width:thin;scrollbar-color:{INDIGO} transparent}}
.th{{flex-shrink:0;width:90px;height:52px;background:#111130;border:2px solid transparent;border-radius:5px;cursor:pointer;font-size:9px;color:#555580;display:flex;align-items:center;justify-content:center;text-align:center;padding:4px;overflow:hidden;transition:border-color .15s}}
.th:hover{{border-color:{TEAL}}}
.th.active{{border-color:{LIME};color:{LIME}}}
#info{{background:{INDIGO};border-radius:8px;padding:8px 14px;font-size:11px;color:#7070a0;margin-top:4px}}
#stitle{{font-weight:700;color:#e2e8f0;margin-bottom:2px}}
</style>
</head>
<body>
<div id="viewer">
  <div id="stage">{slides_html}</div>
  <div id="nav">
    <button class="nb" id="prevBtn" onclick="go(-1)" disabled>&#8249; Prev</button>
    <div id="progress"><div id="bar" style="width:{100//max(total,1)}%"></div></div>
    <span id="counter">1 / {total}</span>
    <button class="nb" id="nextBtn" onclick="go(1)">Next &#8250;</button>
  </div>
  <div id="thumbs">
    {''.join(f'<div class="th{" active" if i==0 else ""}" onclick="jump({i})" id="th{i}" title="Slide {i+1}">{i+1}. {_e(slides[i].get("title",""))[:20]}</div>' for i in range(len(slides)))}
  </div>
  <div id="info">
    <div id="stitle">Slide 1: {_e(slides[0].get("title","") if slides else "")}</div>
    <div>{_e(client)} &nbsp;·&nbsp; {_e(title)} &nbsp;·&nbsp; {_e(date)} &nbsp;·&nbsp; {total} slides</div>
  </div>
</div>
<script>
var cur=0,tot={total};
var titles={str([_e(sl.get("title","")) for sl in slides])};
function show(n){{
  document.querySelectorAll('.sl').forEach(function(s){{s.style.display='none'}});
  document.querySelectorAll('.th').forEach(function(t,i){{t.className='th'+(i===n?' active':'')}});
  var el=document.querySelector('.sl[data-id="'+(n+1)+'"]');
  if(el)el.style.display='block';
  cur=n;
  document.getElementById('counter').textContent=(n+1)+' / '+tot;
  document.getElementById('bar').style.width=((n+1)/tot*100)+'%';
  document.getElementById('prevBtn').disabled=(n===0);
  document.getElementById('nextBtn').disabled=(n===tot-1);
  document.getElementById('stitle').textContent='Slide '+(n+1)+': '+(titles[n]||'');
  var th=document.getElementById('th'+n);
  if(th)th.scrollIntoView({{block:'nearest',inline:'center',behavior:'smooth'}});
}}
function go(d){{var n=cur+d;if(n>=0&&n<tot)show(n);}}
function jump(n){{show(n);}}
document.addEventListener('keydown',function(e){{if(e.key==='ArrowRight'||e.key===' ')go(1);else if(e.key==='ArrowLeft')go(-1);}});
</script>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════
#  CLAUDE CONTENT → PPTX RENDERER
# ═══════════════════════════════════════════════════════════════════════

def generate_claude_pptx(slide_content: dict, results: dict = None) -> "bytes | None":
    """Build an ECI-branded .pptx from Claude-generated slide content."""
    if not HAS_PPTX:
        return None
    if results and (not slide_content or not slide_content.get("slides")):
        return _render_premium_pptx(results)

    import os
    prs = Presentation()
    prs.slide_width  = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    INDIGO = _rgb("indigo"); IND2   = _rgb("ind2");  IND3  = _rgb("ind3")
    TEAL   = _rgb("teal");   LIME   = _rgb("lime");  ORG   = _rgb("orange")
    GREEN  = _rgb("green");  PUR    = _rgb("purple")
    WHITE  = _rgb("white");  NEARW  = _rgb("nearw"); MID   = _rgb("mid")
    CARD   = _rgb("card");   RED    = _rgb("red");   AMBER = _rgb("amber")
    ROWALT = _rgb("rowalt")

    LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "eci_logo.png")
    date_str  = slide_content.get("date", datetime.now().strftime("%B %Y"))
    ACCENT_CYCLE = [TEAL, ORG, GREEN, PUR, LIME, AMBER]

    def _r(sld, x, y, w, h, col):
        s = sld.shapes.add_shape(MSO_SHAPE.RECTANGLE, x, y, w, h)
        s.fill.solid(); s.fill.fore_color.rgb = col; s.line.fill.background(); return s

    def _t(sld, text, x, y, w, h, size=11, bold=False, col=None,
           align=PP_ALIGN.LEFT, wrap=True, italic=False):
        if col is None: col = INDIGO
        tb = sld.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame; tf.word_wrap = wrap
        p  = tf.paragraphs[0]; p.alignment = align
        run = p.add_run(); run.text = str(text)[:300]
        run.font.size = Pt(size); run.font.bold = bold
        run.font.color.rgb = col; run.font.italic = italic
        return tb

    def _logo(sld, x=Inches(12.1), y=Inches(0.12), h=Inches(0.42), white=False):
        try:
            if os.path.exists(LOGO_PATH):
                sld.shapes.add_picture(LOGO_PATH, x, y, height=h); return
        except Exception: pass
        _t(sld, "ECI+", x, y, Inches(1.2), h, size=20, bold=True,
           col=WHITE if white else INDIGO)

    def _offset_squares(sld):
        _r(sld, Inches(10.55), Inches(0.00), Inches(1.65), Inches(1.65), IND2)
        _r(sld, Inches(11.35), Inches(0.55), Inches(1.65), Inches(1.65), IND3)

    def _left_bar(sld):
        _r(sld, Inches(0.00), Inches(0.00), Inches(0.14), Inches(7.5), TEAL)

    def _top_rule(sld):
        _r(sld, Inches(0.00), Inches(0.00), prs.slide_width, Inches(0.05), TEAL)

    def _footer(sld, dark=False):
        fc = _rgbt(100, 98, 140) if dark else _rgbt(140, 138, 170)
        _t(sld, "ECI  •  Confidential",
           Inches(0.5), Inches(7.1), Inches(5.0), Inches(0.3), size=8, col=fc, italic=True)

    def _cards_grid(sld, items, start_y, checkmark=False):
        col_count = 2
        cw = Inches(6.0); ch = Inches(0.82)
        col_x = [Inches(0.5), Inches(6.85)]
        bullet = "☑  " if checkmark else "▸  "
        for idx, item in enumerate(items[:8]):
            ci = idx % col_count; ri = idx // col_count
            cx = col_x[ci]; cy = start_y + ri * (ch + Inches(0.1))
            acc = ACCENT_CYCLE[idx % len(ACCENT_CYCLE)]
            _r(sld, cx, cy, cw, ch, CARD)
            _r(sld, cx, cy, Inches(0.05), ch, acc)
            _t(sld, bullet + str(item)[:90],
               cx + Inches(0.15), cy + Inches(0.1),
               cw - Inches(0.25), ch - Inches(0.18), size=11, col=INDIGO, wrap=True)

    for sl in slide_content.get("slides", []):
        stype       = sl.get("type", "content")
        stitle      = str(sl.get("title", ""))
        ssub        = str(sl.get("subtitle", ""))
        bullets_list = sl.get("bullets", [])
        callout     = str(sl.get("callout", ""))
        headline    = str(sl.get("headline", ""))

        sld = prs.slides.add_slide(blank)
        sld.background.fill.solid(); sld.background.fill.fore_color.rgb = WHITE

        if stype == "cover":
            sld.background.fill.fore_color.rgb = INDIGO
            _left_bar(sld); _offset_squares(sld)
            _logo(sld, x=Inches(0.45), y=Inches(0.18), h=Inches(0.45), white=True)
            _t(sld, stitle, Inches(0.45), Inches(1.7), Inches(9.8), Inches(2.6),
               size=52, bold=True, col=WHITE, wrap=True)
            _r(sld, Inches(0.45), Inches(4.4), Inches(2.4), Inches(0.07), TEAL)
            _t(sld, ssub or "AI Solution Proposal",
               Inches(0.45), Inches(4.6), Inches(9.0), Inches(0.6), size=20, bold=True, col=TEAL)
            _t(sld, date_str, Inches(0.45), Inches(5.6), Inches(5.0), Inches(0.4),
               size=12, col=_rgbt(160, 158, 210))

        elif stype == "agenda":
            _top_rule(sld); _logo(sld); _footer(sld, dark=False)
            _r(sld, Inches(0.45), Inches(1.1), Inches(4.2), Inches(5.9), INDIGO)
            _t(sld, "Agenda", Inches(0.7), Inches(3.3), Inches(3.7), Inches(1.3),
               size=46, bold=True, col=WHITE, align=PP_ALIGN.CENTER)
            tb = sld.shapes.add_textbox(Inches(5.2), Inches(1.3), Inches(7.8), Inches(5.8))
            tf = tb.text_frame; tf.word_wrap = True
            for i, item in enumerate(sl.get("items", [])[:9]):
                p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
                r1 = p.add_run(); r1.text = "%02d  " % (i + 1)
                r1.font.size = Pt(20); r1.font.bold = True; r1.font.color.rgb = TEAL
                r2 = p.add_run(); r2.text = str(item)[:80]
                r2.font.size = Pt(14); r2.font.color.rgb = INDIGO; p.space_after = Pt(9)

        elif stype == "section":
            sld.background.fill.fore_color.rgb = INDIGO
            _left_bar(sld); _offset_squares(sld)
            _logo(sld, x=Inches(0.45), y=Inches(0.18), h=Inches(0.4), white=True)
            _t(sld, "SECTION", Inches(0.45), Inches(1.8), Inches(5.0), Inches(0.38),
               size=11, col=TEAL, bold=True)
            _r(sld, Inches(0.45), Inches(2.3), Inches(1.8), Inches(0.06), TEAL)
            _t(sld, stitle, Inches(0.45), Inches(2.55), Inches(9.5), Inches(2.4),
               size=46, bold=True, col=WHITE, wrap=True)
            if ssub:
                _t(sld, ssub, Inches(0.45), Inches(5.2), Inches(9.5), Inches(0.55),
                   size=16, col=TEAL)

        elif stype == "metrics":
            sld.background.fill.fore_color.rgb = INDIGO
            _offset_squares(sld)
            _logo(sld, x=Inches(12.1), y=Inches(0.12), h=Inches(0.42), white=True)
            _t(sld, stitle, Inches(0.5), Inches(0.75), Inches(12.2), Inches(0.65),
               size=28, bold=True, col=WHITE, align=PP_ALIGN.CENTER)
            _r(sld, Inches(5.4), Inches(1.5), Inches(2.5), Inches(0.06), TEAL)
            acc_m = [TEAL, LIME, ORG]
            for mi, m in enumerate(sl.get("metrics", [])[:3]):
                mx = Inches(0.75 + mi * 4.15); my = Inches(1.85)
                cw = Inches(3.8); ch = Inches(4.5)
                _r(sld, mx, my, cw, ch, IND2)
                _r(sld, mx, my, cw, Inches(0.06), acc_m[mi])
                _t(sld, str(m.get("value", "—")),
                   mx + Inches(0.15), my + Inches(0.45), cw - Inches(0.3), Inches(2.2),
                   size=60, bold=True, col=WHITE, align=PP_ALIGN.CENTER)
                _t(sld, str(m.get("label", "")),
                   mx + Inches(0.15), my + Inches(2.75), cw - Inches(0.3), Inches(0.6),
                   size=16, bold=True, col=acc_m[mi], align=PP_ALIGN.CENTER)
                _t(sld, str(m.get("desc", "")),
                   mx + Inches(0.15), my + Inches(3.45), cw - Inches(0.3), Inches(0.7),
                   size=10, col=NEARW, align=PP_ALIGN.CENTER)

        elif stype == "next_steps":
            sld.background.fill.fore_color.rgb = INDIGO
            _left_bar(sld); _offset_squares(sld)
            _logo(sld, x=Inches(0.45), y=Inches(0.18), h=Inches(0.4), white=True)
            _t(sld, stitle, Inches(0.45), Inches(1.0), Inches(9.5), Inches(0.9),
               size=42, bold=True, col=WHITE)
            _r(sld, Inches(0.45), Inches(2.05), Inches(2.4), Inches(0.07), TEAL)
            for i, st_ in enumerate(sl.get("steps", [])[:5]):
                sy  = Inches(2.4 + i * 0.98)
                acc = ACCENT_CYCLE[i % len(ACCENT_CYCLE)]
                circ = sld.shapes.add_shape(MSO_SHAPE.OVAL,
                    Inches(0.45), sy, Inches(0.76), Inches(0.76))
                circ.fill.solid(); circ.fill.fore_color.rgb = acc
                circ.line.fill.background()
                _t(sld, str(i + 1), Inches(0.45), sy + Inches(0.06),
                   Inches(0.76), Inches(0.68), size=17, bold=True, col=WHITE,
                   align=PP_ALIGN.CENTER)
                _t(sld, str(st_)[:120], Inches(1.42), sy + Inches(0.08),
                   Inches(9.0), Inches(0.72), size=14, col=WHITE, wrap=True)

        elif stype == "contact":
            sld.background.fill.fore_color.rgb = INDIGO
            _logo(sld, x=Inches(12.1), y=Inches(0.14), h=Inches(0.46), white=True)
            sq = Inches(1.78)
            _r(sld, Inches(9.25),  Inches(3.95), sq, sq, IND2)
            _r(sld, Inches(11.03), Inches(3.95), sq, sq, IND3)
            _r(sld, Inches(9.25),  Inches(5.73), sq, sq, IND3)
            _r(sld, Inches(11.03), Inches(5.73), sq, sq, IND2)
            _r(sld, Inches(2.68), Inches(1.5), Inches(0.04), Inches(5.1), _rgbt(65, 62, 130))
            social_data = [("f", _rgbt(59, 89, 152)), ("t", _rgbt(29, 161, 242)), ("in", TEAL)]
            for si, (lbl, s_col) in enumerate(social_data):
                sy = Inches(1.95 + si * 1.28)
                circ2 = sld.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.9), sy, Inches(0.96), Inches(0.96))
                circ2.fill.solid(); circ2.fill.fore_color.rgb = WHITE; circ2.line.fill.background()
                _t(sld, lbl, Inches(0.9), sy + Inches(0.08), Inches(0.96), Inches(0.8),
                   size=17, bold=True, col=s_col, align=PP_ALIGN.CENTER)
            _t(sld, "Corporate Headquarters", Inches(3.0), Inches(1.65), Inches(6.1), Inches(0.58),
               size=20, bold=True, col=WHITE)
            _t(sld, "529 Fifth Avenue, 7th floor", Inches(3.0), Inches(2.32), Inches(6.1), Inches(0.4),
               size=12, col=NEARW)
            _t(sld, "New York, New York, 10017", Inches(3.0), Inches(2.73), Inches(6.1), Inches(0.4),
               size=12, col=NEARW)
            _t(sld, "Global Sales", Inches(3.0), Inches(3.3), Inches(6.1), Inches(0.58),
               size=20, bold=True, col=WHITE)
            _t(sld, "US: +1 800 752 1382", Inches(3.0), Inches(3.97), Inches(6.1), Inches(0.38), size=12, col=NEARW)
            _t(sld, "UK: +44 207 0716802",  Inches(3.0), Inches(4.38), Inches(6.1), Inches(0.38), size=12, col=NEARW)
            _t(sld, "Singapore: +65 66222345", Inches(3.0), Inches(4.79), Inches(6.1), Inches(0.38), size=12, col=NEARW)
            _t(sld, "Hong Kong: +852 3189 0101", Inches(3.0), Inches(5.2), Inches(6.1), Inches(0.38), size=12, col=NEARW)

        else:  # content — card grid layout
            _top_rule(sld); _logo(sld); _footer(sld, dark=False)
            _t(sld, stitle, Inches(0.5), Inches(0.25), Inches(11.5), Inches(0.6),
               size=26, bold=True, col=INDIGO)
            if headline:
                _t(sld, headline, Inches(0.5), Inches(0.92), Inches(11.0), Inches(0.38),
                   size=12, col=MID, italic=True)
            _r(sld, Inches(0.5), Inches(1.35), Inches(2.0), Inches(0.05), TEAL)
            _cards_grid(sld, bullets_list, Inches(1.55))
            if callout:
                _r(sld, Inches(0.5), Inches(6.62), Inches(12.5), Inches(0.65), INDIGO)
                _t(sld, callout, Inches(0.7), Inches(6.66), Inches(12.0), Inches(0.5),
                   size=11, bold=True, col=TEAL)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════
#  DISCOVERY PREP DECK (unchanged)
# ═══════════════════════════════════════════════════════════════════════

def generate_discovery_pptx(discovery_questions: dict):
    """Generate an ECI-branded Discovery Prep Deck PPTX."""
    if not HAS_PPTX:
        return None

    prs = Presentation()
    prs.slide_width  = Inches(13.333)
    prs.slide_height = Inches(7.5)

    ECI_BLUE = _rgbt(27, 58, 92)
    ACCENT   = _rgbt(0, 180, 216)
    GREEN    = _rgbt(0, 212, 170)
    AMBER    = _rgbt(255, 209, 102)
    RED      = _rgbt(255, 107, 107)
    PURPLE   = _rgbt(123, 97, 255)
    WHITE    = _rgb("white")
    MID_GRAY = _rgbt(100, 100, 100)

    _PRI_COLOR = {"High": RED, "Medium": AMBER, "Low": GREEN}
    _CAT_COLOR = {
        "Technical": ACCENT, "Business": GREEN, "Budget": AMBER,
        "Timeline": PURPLE, "Decision Process": RED,
    }

    blank = prs.slide_layouts[6]

    def _bg(slide, color=ECI_BLUE):
        bg = slide.background; bg.fill.solid(); bg.fill.fore_color.rgb = color

    def _box(slide, l, t, w, h, rgb):
        shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
        shp.fill.solid(); shp.fill.fore_color.rgb = rgb; shp.line.fill.background(); return shp

    def _add_text(slide, l, t, w, h, text, size=14, bold=False, color=None,
                  align=PP_ALIGN.LEFT, wrap=True):
        if color is None: color = WHITE
        tf = slide.shapes.add_textbox(l, t, w, h)
        tf.text_frame.word_wrap = wrap
        p = tf.text_frame.paragraphs[0]
        run = p.add_run(); run.text = text
        run.font.size = Pt(size); run.font.bold = bold
        run.font.color.rgb = color; p.alignment = align
        return tf

    project_type = safe_str(discovery_questions.get("project_type", "IT Project"))
    priority_sum = safe_str(discovery_questions.get("priority_summary", ""))
    total_q      = safe_int(discovery_questions.get("total_questions", 0))
    categories   = safe_list(discovery_questions.get("categories"))

    sld = prs.slides.add_slide(blank)
    _bg(sld, ECI_BLUE)
    _box(sld, 0, Inches(2.8), prs.slide_width, Inches(2.0), ACCENT)
    _add_text(sld, Inches(1), Inches(0.8), Inches(11), Inches(1.4),
              "DISCOVERY PREP DECK", 36, True, WHITE, PP_ALIGN.CENTER)
    _add_text(sld, Inches(1), Inches(2.85), Inches(11), Inches(0.8),
              project_type, 24, False, _rgbt(30, 30, 30), PP_ALIGN.CENTER)
    _add_text(sld, Inches(1), Inches(4.5), Inches(11), Inches(1.0),
              priority_sum, 14, False, _rgbt(200, 220, 240), PP_ALIGN.CENTER)
    _add_text(sld, Inches(1), Inches(6.2), Inches(11), Inches(0.6),
              f"{total_q} questions  |  {len(categories)} categories  |  ECI Presales  |  {datetime.now().strftime('%d %b %Y')}",
              11, False, _rgbt(150, 180, 200), PP_ALIGN.CENTER)

    sld = prs.slides.add_slide(blank)
    _bg(sld, _rgbt(15, 25, 45))
    _box(sld, 0, 0, prs.slide_width, Inches(1.1), ECI_BLUE)
    _add_text(sld, Inches(0.4), Inches(0.2), Inches(12), Inches(0.7),
              "Question Summary by Category", 22, True, WHITE, PP_ALIGN.LEFT)
    y_pos = Inches(1.3)
    for cat in categories:
        c_name    = safe_str(cat.get("name", ""))
        c_icon    = safe_str(cat.get("icon", ""))
        questions = safe_list(cat.get("questions"))
        high_c    = sum(1 for q in questions if safe_str(safe_dict(q).get("priority")) == "High")
        c_color   = _CAT_COLOR.get(c_name, ACCENT)
        _box(sld, Inches(0.4), y_pos, Inches(0.06), Inches(0.35), c_color)
        tf = sld.shapes.add_textbox(Inches(0.6), y_pos, Inches(11), Inches(0.38))
        tf.text_frame.word_wrap = False
        p = tf.text_frame.paragraphs[0]
        r1 = p.add_run()
        r1.text = f"{c_icon} {c_name}  "
        r1.font.size = Pt(13); r1.font.bold = True; r1.font.color.rgb = WHITE
        r2 = p.add_run()
        r2.text = f"({len(questions)} questions, {high_c} high priority)"
        r2.font.size = Pt(11); r2.font.color.rgb = _rgbt(180, 200, 220)
        y_pos += Inches(0.45)

    for cat in categories:
        c_name    = safe_str(cat.get("name", ""))
        questions = safe_list(cat.get("questions"))
        c_color   = _CAT_COLOR.get(c_name, ACCENT)
        c_icon    = safe_str(cat.get("icon", ""))

        for chunk_start in range(0, len(questions), 6):
            chunk = questions[chunk_start:chunk_start + 6]
            sld   = prs.slides.add_slide(blank)
            _bg(sld, _rgbt(15, 25, 45))
            _box(sld, 0, 0, prs.slide_width, Inches(1.1), ECI_BLUE)
            _box(sld, 0, 0, Inches(0.12), Inches(7.5), c_color)
            pg = f"  (cont.)" if chunk_start > 0 else ""
            _add_text(sld, Inches(0.4), Inches(0.15), Inches(10), Inches(0.5),
                      f"{c_icon} {c_name}{pg}", 18, True, WHITE, PP_ALIGN.LEFT)
            _add_text(sld, Inches(0.4), Inches(0.65), Inches(10), Inches(0.4),
                      f"{len(questions)} questions  |  ECI Discovery Prep", 11,
                      False, _rgbt(160, 185, 210), PP_ALIGN.LEFT)
            y = Inches(1.2)
            for qi, q in enumerate(chunk):
                qd  = safe_dict(q)
                pri = safe_str(qd.get("priority", "Medium"))
                pc  = _PRI_COLOR.get(pri, AMBER)
                _box(sld, Inches(0.4), y, Inches(12.6), Inches(0.85),
                     _rgbt(20, 35, 60) if qi % 2 == 0 else _rgbt(25, 40, 68))
                _box(sld, Inches(0.4), y, Inches(0.06), Inches(0.85), pc)
                _add_text(sld, Inches(0.6), y + Inches(0.08), Inches(9.8), Inches(0.42),
                          safe_str(qd.get("question", ""))[:120], 12, False, WHITE, PP_ALIGN.LEFT)
                _add_text(sld, Inches(10.6), y + Inches(0.08), Inches(2.2), Inches(0.35),
                          pri, 10, True, pc, PP_ALIGN.RIGHT)
                context = safe_str(qd.get("context", ""))
                if context:
                    _add_text(sld, Inches(0.6), y + Inches(0.5), Inches(11.8), Inches(0.32),
                              context[:100], 9, False, _rgbt(160, 185, 210), PP_ALIGN.LEFT)
                y += Inches(0.95)

    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()
