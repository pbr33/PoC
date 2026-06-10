"""
ECI Business Estimation Tool — Marketing PDF Generator
Generates a stunning marketing brochure PDF using reportlab.

Install: pip install reportlab
Run:     python marketing/generate_pdf.py
Output:  marketing/ECI_Marketing_Brochure.pdf
"""

import os
import math
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import (
    HexColor, Color, white, black
)
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

W, H = A4  # 595.28 x 841.89 pts

# ── Colour palette ──────────────────────────────────────────────────────
C_BG       = HexColor("#020817")
C_CARD     = HexColor("#0f172a")
C_CARD2    = HexColor("#111827")
C_CYAN     = HexColor("#00d4aa")
C_BLUE     = HexColor("#00b4d8")
C_PURPLE   = HexColor("#8b5cf6")
C_PINK     = HexColor("#f72585")
C_GOLD     = HexColor("#ffd166")
C_GREEN    = HexColor("#06d6a0")
C_RED      = HexColor("#ef4444")
C_TEXT     = HexColor("#e2e8f0")
C_DIM      = HexColor("#94a3b8")
C_MUTED    = HexColor("#64748b")
C_BORDER   = HexColor("#1e293b")

OUT = os.path.join(os.path.dirname(__file__), "ECI_Marketing_Brochure.pdf")


# ══════════════════════════════════════════════════════════════════════════
#  DIRECT CANVAS DRAWING HELPERS
# ══════════════════════════════════════════════════════════════════════════

def grad_rect(c, x, y, w, h, col1, col2, vertical=True):
    """Draw a gradient rectangle by stacking thin strips."""
    steps = max(int(h if vertical else w), 1)
    for i in range(steps):
        t = i / steps
        r = col1.red   + t * (col2.red   - col1.red)
        g = col1.green + t * (col2.green - col1.green)
        b = col1.blue  + t * (col2.blue  - col1.blue)
        c.setFillColor(Color(r, g, b))
        if vertical:
            c.rect(x, y + h - i - 1, w, 1, fill=1, stroke=0)
        else:
            c.rect(x + i, y, 1, h, fill=1, stroke=0)


def rounded_rect(c, x, y, w, h, r=6, fill=None, stroke=None, stroke_width=0.5):
    """Draw a rounded rectangle."""
    if fill:
        c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(stroke_width)
    p = c.beginPath()
    p.moveTo(x + r, y)
    p.lineTo(x + w - r, y)
    p.arcTo(x + w - 2*r, y, x + w, y + 2*r, 270, 90)
    p.lineTo(x + w, y + h - r)
    p.arcTo(x + w - 2*r, y + h - 2*r, x + w, y + h, 0, 90)
    p.lineTo(x + r, y + h)
    p.arcTo(x, y + h - 2*r, x + 2*r, y + h, 90, 90)
    p.lineTo(x, y + r)
    p.arcTo(x, y, x + 2*r, y + 2*r, 180, 90)
    p.close()
    c.drawPath(p, fill=1 if fill else 0, stroke=1 if stroke else 0)


def hex_stripe(c, x, y, w, h, color, alpha=0.06):
    """Fill area with a subtle hex pattern overlay."""
    c.saveState()
    c.setFillColor(color)
    c.setFillAlpha(alpha)
    size = 14
    cols = int(w / size) + 2
    rows = int(h / size) + 2
    for row in range(rows):
        for col in range(cols):
            cx = x + col * size + (size * 0.5 if row % 2 else 0)
            cy = y + row * size * 0.87
            c.circle(cx, cy, 2, fill=1, stroke=0)
    c.restoreState()


def glow_circle(c, cx, cy, r, color, alpha=0.06, layers=4):
    """Draw a soft glow effect."""
    for i in range(layers, 0, -1):
        a = alpha * (i / layers)
        c.setFillColor(color)
        c.setFillAlpha(a)
        c.circle(cx, cy, r * i * 0.6, fill=1, stroke=0)
    c.setFillAlpha(1)


def draw_text_centered(c, text, cx, y, font, size, color):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawCentredString(cx, y, text)


def draw_text(c, text, x, y, font, size, color):
    c.setFont(font, size)
    c.setFillColor(color)
    c.drawString(x, y, text)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE BUILDERS
# ══════════════════════════════════════════════════════════════════════════

def page_cover(c):
    """Full-bleed cover page."""
    # Background
    c.setFillColor(C_BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Gradient overlay top half
    grad_rect(c, 0, H//2, W, H//2,
              Color(0.035, 0.055, 0.14, 0.95),
              Color(0.008, 0.031, 0.09, 0))

    # Glow orbs
    c.saveState()
    glow_circle(c, W*0.85, H*0.75, 200, C_PURPLE, alpha=0.04, layers=6)
    glow_circle(c, W*0.15, H*0.3,  180, C_BLUE,   alpha=0.05, layers=6)
    glow_circle(c, W*0.5,  H*0.1,  160, C_PINK,   alpha=0.04, layers=5)
    c.restoreState()

    # Top gradient bar
    grad_rect(c, 0, H-6, W, 6, C_BLUE, C_PURPLE, vertical=False)

    # Logo / product name
    c.saveState()
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(C_CYAN)
    c.drawString(50, H - 44, "⚡  ECI Business Estimation Tool")
    c.restoreState()

    # Tag line pill
    pill_w, pill_h = 260, 26
    pill_x = (W - pill_w) / 2
    pill_y = H - 160
    rounded_rect(c, pill_x, pill_y, pill_w, pill_h, r=13,
                 fill=HexColor("#00b4d820"), stroke=HexColor("#00b4d860"))
    draw_text_centered(c, "AI-POWERED PRESALES INTELLIGENCE PLATFORM",
                       W/2, pill_y + 9, "Helvetica-Bold", 8, C_BLUE)

    # Main headline
    c.saveState()
    c.setFont("Helvetica-Bold", 44)
    lines = ["From Scope", "Document to", "Boardroom-Ready", "Proposal"]
    line_h = 52
    start_y = H - 220
    for i, line in enumerate(lines):
        y = start_y - i * line_h
        # Gradient text via clipping
        if i in (1, 2):
            c.setFillColor(C_CYAN)
        else:
            c.setFillColor(C_TEXT)
        c.drawCentredString(W/2, y, line)
    c.restoreState()

    # "In Under 90 Seconds"
    c.saveState()
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(C_PURPLE)
    c.drawCentredString(W/2, H - 220 - 4 * line_h - 20, "in Under 90 Seconds.")
    c.restoreState()

    # Sub text
    c.saveState()
    c.setFont("Helvetica", 12)
    c.setFillColor(C_MUTED)
    sub = "11 specialised AI agents. 9 professional output formats. 5 AI providers."
    c.drawCentredString(W/2, H - 220 - 4*line_h - 60, sub)
    c.restoreState()

    # Stats row
    stats = [
        ("11", "AI Agents"),
        ("<90s", "Per Proposal"),
        ("9", "Output Formats"),
        ("<£1", "Per Run"),
        ("5", "AI Providers"),
    ]
    box_w = 90
    total_w = len(stats) * box_w + (len(stats)-1) * 12
    sx = (W - total_w) / 2
    sy = H - 220 - 4*line_h - 140

    for i, (num, lbl) in enumerate(stats):
        bx = sx + i * (box_w + 12)
        rounded_rect(c, bx, sy, box_w, 64, r=8,
                     fill=HexColor("#ffffff08"), stroke=HexColor("#ffffff12"))
        # Accent bar bottom
        colors = [C_CYAN, C_PURPLE, C_GOLD, C_GREEN, C_PINK]
        c.setFillColor(colors[i])
        c.roundRect(bx, sy, box_w, 2, 1, fill=1, stroke=0)
        # Number
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(colors[i])
        c.drawCentredString(bx + box_w/2, sy + 36, num)
        # Label
        c.setFont("Helvetica", 7)
        c.setFillColor(C_MUTED)
        c.drawCentredString(bx + box_w/2, sy + 20, lbl.upper())

    # Bottom decorative line
    c.saveState()
    c.setStrokeColor(HexColor("#1e293b"))
    c.setLineWidth(1)
    c.line(50, 120, W-50, 120)
    c.restoreState()

    # Footer
    c.setFont("Helvetica", 9)
    c.setFillColor(C_MUTED)
    c.drawCentredString(W/2, 90, "ECI Business Estimation Tool  ·  Internal Product  ·  2026")
    c.drawCentredString(W/2, 74, "Transforming presales from days to seconds — one proposal at a time")

    # Bottom gradient bar
    grad_rect(c, 0, 0, W, 6, C_PURPLE, C_PINK, vertical=False)


def page_agents(c):
    """Page 2: 11 Agents pipeline diagram."""
    c.setFillColor(C_BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Header strip
    grad_rect(c, 0, H-60, W, 60, HexColor("#0f172a"), C_BG)
    c.setFillColor(HexColor("#0f172a"))
    c.rect(0, H-60, W, 60, fill=1, stroke=0)

    # Top bar
    grad_rect(c, 0, H-4, W, 4, C_BLUE, C_PURPLE, vertical=False)

    draw_text(c, "⚡  ECI Business Estimation Tool", 50, H-38, "Helvetica-Bold", 10, C_CYAN)

    # Section eyebrow
    draw_text_centered(c, "THE INTELLIGENCE ENGINE", W/2, H-88, "Helvetica-Bold", 9, C_PURPLE)

    # Title
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(C_TEXT)
    c.drawCentredString(W/2, H-122, "11 Specialist Agents.")
    c.setFillColor(C_CYAN)
    c.drawCentredString(W/2, H-158, "One Button.")

    # Sub
    c.setFont("Helvetica", 11)
    c.setFillColor(C_DIM)
    c.drawCentredString(W/2, H-184,
        "Each agent is purpose-built for its domain. They run in parallel,")
    c.drawCentredString(W/2, H-200,
        "cross-reference outputs, and produce results no single model can match.")

    # Draw agent pipeline grid
    agents = [
        ("0", "🔍", "Completeness", "Checker",   C_PURPLE, "#8b5cf620"),
        ("1", "🔍", "Requirements", "Analyst",    C_BLUE,   "#00b4d820"),
        ("2", "📊", "Cost",         "Estimator",  C_PURPLE, "#8b5cf620"),
        ("3", "⏱", "Time",         "Planner",    C_GOLD,   "#ffd16620"),
        ("4", "⚠", "Risk",         "Analyst",    C_RED,    "#ef444420"),
        ("5", "🏗", "Architecture", "Designer",   C_CYAN,   "#00d4aa20"),
        ("6", "👥", "Team",         "Composer",   C_BLUE,   "#00b4d820"),
        ("7", "📝", "SOW",          "Generator",  C_PURPLE, "#8b5cf620"),
        ("8", "❓", "Discovery",    "Engine",     C_GREEN,  "#06d6a020"),
        ("9", "💰", "Azure",        "Pricer",     C_GOLD,   "#ffd16620"),
        ("10","✍", "Proposal",     "Writer",     C_PINK,   "#f7258520"),
    ]

    # 2 rows: 6 + 5
    rows = [agents[:6], agents[6:]]
    row_y_start = H - 320
    for row_i, row in enumerate(rows):
        row_y = row_y_start - row_i * 160
        n = len(row)
        cell_w = (W - 100) / n
        for col_i, (num, icon, l1, l2, col, bg) in enumerate(row):
            bx = 50 + col_i * cell_w + 4
            by = row_y - 110
            bw = cell_w - 8
            bh = 110

            # Card background
            rounded_rect(c, bx, by, bw, bh, r=8,
                         fill=HexColor(bg), stroke=col)
            # Accent bar top
            c.setFillColor(col)
            c.roundRect(bx, by+bh-3, bw, 3, 1.5, fill=1, stroke=0)
            # Number badge
            c.setFillColor(C_BG)
            c.circle(bx+18, by+bh-16, 11, fill=1, stroke=0)
            c.setStrokeColor(col)
            c.setLineWidth(0.8)
            c.circle(bx+18, by+bh-16, 11, fill=0, stroke=1)
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(col)
            c.drawCentredString(bx+18, by+bh-19, num)
            # Icon
            c.setFont("Helvetica", 20)
            c.drawCentredString(bx+bw/2, by+64, icon)
            # Labels
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(C_TEXT)
            c.drawCentredString(bx+bw/2, by+44, l1)
            c.setFont("Helvetica", 8)
            c.setFillColor(C_DIM)
            c.drawCentredString(bx+bw/2, by+30, l2)
            # Bottom status
            c.setFillColor(col)
            c.setFillAlpha(0.15)
            c.roundRect(bx+8, by+8, bw-16, 16, 8, fill=1, stroke=0)
            c.setFillAlpha(1)
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(col)
            c.drawCentredString(bx+bw/2, by+13, "AGENT " + num)

            # Arrow (not for last in row)
            if col_i < n - 1:
                c.setStrokeColor(HexColor("#334155"))
                c.setLineWidth(1)
                c.setDash(3, 3)
                ax = bx + bw + 4
                ay = by + bh/2
                c.line(ax, ay, ax + 0, ay)
                c.setDash()
                c.setFillColor(HexColor("#334155"))
                c.drawString(ax - 2, ay - 3, "→")

    # Output strip at bottom
    strip_y = 80
    c.setFillColor(HexColor("#0f172a"))
    c.roundRect(30, strip_y, W-60, 64, 8, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#1e293b"))
    c.setLineWidth(0.5)
    c.roundRect(30, strip_y, W-60, 64, 8, fill=0, stroke=1)

    outputs = ["📊 Excel", "📄 PDF", "📊 PPTX", "📝 SOW", "🔀 Scenario", "❓ Discovery", "🎬 Video", "🔗 JSON", "📦 ZIP"]
    out_w = (W - 60) / len(outputs)
    for i, o in enumerate(outputs):
        ox = 30 + i * out_w
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(C_GREEN)
        c.drawCentredString(ox + out_w/2, strip_y + 38, o.split()[0])
        c.setFont("Helvetica", 7)
        c.setFillColor(C_DIM)
        c.drawCentredString(ox + out_w/2, strip_y + 22, o.split()[1] if " " in o else "")
        if i < len(outputs)-1:
            c.setStrokeColor(HexColor("#1e293b"))
            c.setLineWidth(0.5)
            c.line(ox + out_w, strip_y+8, ox + out_w, strip_y+56)

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(C_GREEN)
    c.drawCentredString(W/2, strip_y+10, "9 PROFESSIONAL DELIVERABLES — EVERY RUN — AUTOMATICALLY")

    grad_rect(c, 0, 0, W, 4, C_PURPLE, C_PINK, vertical=False)


def page_features(c):
    """Page 3: Feature showcase."""
    c.setFillColor(C_BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # Glow
    c.saveState()
    glow_circle(c, W*0.9, H*0.5, 250, C_PURPLE, alpha=0.03, layers=5)
    glow_circle(c, W*0.1, H*0.5, 200, C_BLUE, alpha=0.03, layers=5)
    c.restoreState()

    grad_rect(c, 0, H-4, W, 4, C_CYAN, C_GREEN, vertical=False)
    draw_text(c, "⚡  ECI Business Estimation Tool", 50, H-32, "Helvetica-Bold", 10, C_CYAN)

    draw_text_centered(c, "PLATFORM CAPABILITIES", W/2, H-64, "Helvetica-Bold", 9, C_CYAN)
    c.setFont("Helvetica-Bold", 30)
    c.setFillColor(C_TEXT)
    c.drawCentredString(W/2, H-96, "Everything Your Presales Team")
    c.setFillColor(C_CYAN)
    c.drawCentredString(W/2, H-128, "Actually Needs")

    features = [
        ("🔀", "Scenario Modelling", C_CYAN,
         "Run 3 simultaneous what-if scenarios with Brooks' Law\n"
         "team scaling, seniority factors, and contract type\n"
         "premiums. Answer commercial questions in the room."),
        ("💰", "Live Azure Pricing", C_BLUE,
         "Real-time Azure Retail Prices API integration. Every\n"
         "infrastructure estimate backed by actual 2025 market\n"
         "data — not guesses or outdated price lists."),
        ("🌐", "3D Architecture Viewer", C_PURPLE,
         "Interactive Three.js fly-through of your proposed\n"
         "solution. Rotate, zoom, click nodes. The showstopper\n"
         "in every client presentation."),
        ("🎬", "AI Video Narration", C_PINK,
         "Generates a presenter video via HeyGen, D-ID, or\n"
         "ElevenLabs. Your proposal presents itself before the\n"
         "meeting even starts. Download as MP4."),
        ("🧠", "Continuous Learning", C_GREEN,
         "Records actual vs estimated hours/cost. Derives\n"
         "correction factors per tech category. Future estimates\n"
         "automatically get more accurate over time."),
        ("🔍", "Scope Completeness", C_GOLD,
         "Agent 0 analyses your document before the main\n"
         "pipeline — identifying gaps and generating a checklist\n"
         "of questions to ask before submission."),
        ("💬", "Proposal-Aware Chat", C_CYAN,
         "AI chat with full context of your specific proposal.\n"
         "Not generic answers — answers rooted in your actual\n"
         "scope, costs, risks, and architecture."),
        ("🗂️", "Persistent Run Library", C_BLUE,
         "Every estimation auto-saved to SQLite with client name\n"
         "extracted. Architect review gate, searchable history,\n"
         "restore any run. Nothing is ever lost."),
        ("⌨️", "Command Palette", C_PURPLE,
         "Press Ctrl+K. Navigate, download, test connections —\n"
         "all without touching the mouse. Built for power users\n"
         "who live in the tool every day."),
    ]

    cols = 3
    rows_count = math.ceil(len(features) / cols)
    card_w = (W - 80 - (cols-1)*12) / cols
    card_h = (H - 220 - (rows_count-1)*10) / rows_count - 2
    start_y = H - 168

    for i, (icon, title, col, desc) in enumerate(features):
        row = i // cols
        col_i = i % cols
        bx = 40 + col_i * (card_w + 12)
        by = start_y - row * (card_h + 10) - card_h

        rounded_rect(c, bx, by, card_w, card_h, r=8,
                     fill=HexColor("#0f172a"), stroke=HexColor("#1e293b"))
        c.setFillColor(col)
        c.roundRect(bx, by+card_h-3, card_w, 3, 1.5, fill=1, stroke=0)

        # Icon box
        c.setFillColor(Color(col.red, col.green, col.blue, 0.12))
        c.roundRect(bx+12, by+card_h-50, 32, 32, 4, fill=1, stroke=0)
        c.setFont("Helvetica", 16)
        c.drawString(bx+18, by+card_h-36, icon)

        # Title
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(C_TEXT)
        c.drawString(bx+12, by+card_h-64, title)

        # Desc lines
        lines = desc.strip().split("\n")
        c.setFont("Helvetica", 7.5)
        c.setFillColor(C_MUTED)
        for j, line in enumerate(lines):
            c.drawString(bx+12, by+card_h-80 - j*12, line.strip())

    grad_rect(c, 0, 0, W, 4, C_CYAN, C_GREEN, vertical=False)


def page_compare(c):
    """Page 4: Comparison table + ROI."""
    c.setFillColor(C_BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)
    grad_rect(c, 0, H-4, W, 4, C_GOLD, C_PINK, vertical=False)
    draw_text(c, "⚡  ECI Business Estimation Tool", 50, H-32, "Helvetica-Bold", 10, C_CYAN)

    draw_text_centered(c, "WHY ECI ESTIMATE", W/2, H-64, "Helvetica-Bold", 9, C_GOLD)
    c.setFont("Helvetica-Bold", 30)
    c.setFillColor(C_TEXT)
    c.drawCentredString(W/2, H-96, "The Tool Your Competitors")
    c.setFillColor(C_GOLD)
    c.drawCentredString(W/2, H-128, "Don't Have")

    # Table
    headers = ["Capability", "Manual Process", "Generic AI Tool", "⚡ ECI Estimate"]
    rows = [
        ("Time to first proposal",      "8–40 hours",       "2–4 hours",      "< 90 seconds"),
        ("Estimate consistency",         "Low variance",     "Medium",         "±8% across team"),
        ("Live infrastructure pricing",  "Manual lookup",    "None",           "Azure Retail API"),
        ("Risk identification",          "Ad hoc",           "Basic",          "Scored register"),
        ("Scenario modelling",           "Hours of rework",  "None",           "3 scenarios live"),
        ("Learns from past projects",    "Tribal knowledge", "None",           "Auto-corrected"),
        ("3D architecture view",         "Hire a designer",  "None",           "Three.js viewer"),
        ("AI video narration",           "Hire presenter",   "None",           "HeyGen / D-ID"),
        ("Multi-model AI support",       "N/A",              "Single vendor",  "5 providers"),
        ("Cost per proposal",            "£800–£3,000",      "£200+/month",    "Under £1"),
    ]

    tbl_y = H - 175
    row_h = 28
    col_widths = [165, 105, 105, 130]
    tbl_x = 30
    tbl_w = sum(col_widths)

    # Header row
    c.setFillColor(HexColor("#111827"))
    c.rect(tbl_x, tbl_y - row_h, tbl_w, row_h, fill=1, stroke=0)
    hx = tbl_x
    for i, (hdr, cw) in enumerate(zip(headers, col_widths)):
        col = C_CYAN if i == 3 else (C_TEXT if i == 0 else C_MUTED)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(col)
        c.drawCentredString(hx + cw/2, tbl_y - row_h + 10, hdr)
        hx += cw

    # Data rows
    for ri, (cap, manual, generic, eci) in enumerate(rows):
        ry = tbl_y - (ri+2)*row_h
        bg = HexColor("#0a1628") if ri % 2 == 0 else HexColor("#0f172a")
        c.setFillColor(bg)
        c.rect(tbl_x, ry, tbl_w, row_h, fill=1, stroke=0)
        # ECI column highlight
        eci_x = tbl_x + col_widths[0] + col_widths[1] + col_widths[2]
        c.setFillColor(HexColor("#00d4aa10"))
        c.rect(eci_x, ry, col_widths[3], row_h, fill=1, stroke=0)

        vals = [cap, manual, generic, eci]
        fx = tbl_x
        for ci, (val, cw) in enumerate(zip(vals, col_widths)):
            fc = C_CYAN if ci == 3 else (C_TEXT if ci == 0 else C_MUTED)
            fnt = "Helvetica-Bold" if ci in (0, 3) else "Helvetica"
            c.setFont(fnt, 8)
            c.setFillColor(fc)
            c.drawCentredString(fx + cw/2, ry + 9, val)
            fx += cw

        # Row divider
        c.setStrokeColor(HexColor("#1e293b"))
        c.setLineWidth(0.3)
        c.line(tbl_x, ry, tbl_x + tbl_w, ry)

    # Table border
    c.setStrokeColor(HexColor("#1e293b"))
    c.setLineWidth(0.5)
    c.roundRect(tbl_x, tbl_y - (len(rows)+1)*row_h, tbl_w, (len(rows)+1)*row_h, 6, fill=0, stroke=1)

    # ROI section
    roi_y = tbl_y - (len(rows)+1)*row_h - 48
    draw_text_centered(c, "RETURN ON INVESTMENT — THE ARITHMETIC", W/2, roi_y, "Helvetica-Bold", 9, C_GOLD)

    roi_items = [
        ("⏱️", "Time saved",          "38 hours → 90 seconds per proposal",   "99.9% faster",    C_GREEN),
        ("💷", "Cost per proposal",   "Under £1 vs £800–£3,000 manual",       "3000× cheaper",   C_BLUE),
        ("📈", "Throughput increase", "2–3 per week → 20+ per consultant",    "8× more capacity",C_PURPLE),
        ("🎯", "Quality consistency", "Every consultant at senior level",      "Measurable",      C_GOLD),
    ]

    roi_box_h = 46
    roi_box_w = (W - 80 - 3*12) / 4
    roi_start_y = roi_y - 60

    for i, (icon, label, value, badge, col) in enumerate(roi_items):
        rx = 40 + i * (roi_box_w + 12)
        ry = roi_start_y - roi_box_h

        rounded_rect(c, rx, ry, roi_box_w, roi_box_h, r=8,
                     fill=HexColor("#0f172a"), stroke=col)
        c.setFillColor(col)
        c.roundRect(rx, ry+roi_box_h-2, roi_box_w, 2, 1, fill=1, stroke=0)

        c.setFont("Helvetica", 14)
        c.drawString(rx+10, ry+roi_box_h-22, icon)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(col)
        c.drawString(rx+30, ry+roi_box_h-18, label)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(C_DIM)
        c.drawString(rx+10, ry+roi_box_h-32, value)
        # Badge
        badge_w = c.stringWidth(badge, "Helvetica-Bold", 7) + 16
        c.setFillColor(Color(col.red, col.green, col.blue, 0.15))
        c.roundRect(rx+roi_box_w-badge_w-8, ry+6, badge_w, 14, 7, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(col)
        c.drawCentredString(rx+roi_box_w-badge_w/2-8, ry+11, badge)

    # Final quote
    quote_y = roi_start_y - roi_box_h - 60
    c.setFillColor(HexColor("#0f172a"))
    c.roundRect(40, quote_y-36, W-80, 52, 8, fill=1, stroke=0)
    c.setStrokeColor(C_CYAN)
    c.setLineWidth(0.5)
    c.roundRect(40, quote_y-36, W-80, 52, 8, fill=0, stroke=1)
    c.setFillColor(C_CYAN)
    c.rect(40, quote_y-36, 3, 52, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(C_TEXT)
    c.drawCentredString(W/2, quote_y+2, '"ROI is not a projection. It is arithmetically certain."')
    c.setFont("Helvetica", 9)
    c.setFillColor(C_MUTED)
    c.drawCentredString(W/2, quote_y-18, "At 10 proposals/month, you recover the platform cost in the first week.")

    grad_rect(c, 0, 0, W, 4, C_GOLD, C_PINK, vertical=False)


def page_cta(c):
    """Page 5: CTA / closing page."""
    c.setFillColor(C_BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    c.saveState()
    glow_circle(c, W/2, H/2+80, 280, C_PURPLE, alpha=0.06, layers=8)
    glow_circle(c, W/2, H/2+80, 200, C_BLUE, alpha=0.04, layers=6)
    c.restoreState()

    grad_rect(c, 0, H-4, W, 4, C_PINK, C_PURPLE, vertical=False)
    draw_text(c, "⚡  ECI Business Estimation Tool", 50, H-34, "Helvetica-Bold", 10, C_CYAN)

    # Big centre text
    c.saveState()
    c.setFont("Helvetica-Bold", 52)
    c.setFillColor(C_TEXT)
    c.drawCentredString(W/2, H-200, "Your Next")
    c.setFont("Helvetica-Bold", 52)
    c.setFillColor(C_CYAN)
    c.drawCentredString(W/2, H-260, "Proposal")
    c.setFont("Helvetica-Bold", 52)
    c.setFillColor(C_TEXT)
    c.drawCentredString(W/2, H-320, "Writes Itself.")
    c.restoreState()

    c.setFont("Helvetica", 13)
    c.setFillColor(C_DIM)
    c.drawCentredString(W/2, H-360, "Upload a scope document. Hit one button.")
    c.drawCentredString(W/2, H-378, "Walk into the meeting with a complete package.")

    # CTA button (visual only)
    btn_w, btn_h = 260, 46
    btn_x = (W - btn_w) / 2
    btn_y = H - 460
    grad_rect(c, btn_x, btn_y, btn_w, btn_h, C_BLUE, C_PURPLE, vertical=False)
    c.roundRect(btn_x, btn_y, btn_w, btn_h, 10, fill=0, stroke=0)
    # Clip to rounded
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(white)
    c.drawCentredString(W/2, btn_y + 16, "Request a Live Demo  →")

    # 5 AI provider badges
    providers = ["Azure OpenAI", "Claude (Anthropic)", "Google Gemini", "Qwen Foundry", "Vertex AI"]
    badge_colors = [C_BLUE, C_PURPLE, C_GREEN, C_GOLD, C_PINK]
    badge_w = 96
    total = len(providers) * badge_w + (len(providers)-1) * 8
    bx = (W - total) / 2
    py = btn_y - 80

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(C_MUTED)
    c.drawCentredString(W/2, py + 40, "WORKS WITH YOUR EXISTING AI AGREEMENTS")

    for i, (p, col) in enumerate(zip(providers, badge_colors)):
        px = bx + i * (badge_w + 8)
        c.setFillColor(HexColor("#0f172a"))
        c.roundRect(px, py, badge_w, 28, 14, fill=1, stroke=0)
        c.setStrokeColor(col)
        c.setLineWidth(0.6)
        c.roundRect(px, py, badge_w, 28, 14, fill=0, stroke=1)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(col)
        # Dot
        c.circle(px+14, py+14, 3, fill=1, stroke=0)
        c.setFillColor(C_TEXT)
        c.drawString(px+22, py+11, p)

    # Stats row bottom
    stats = [
        ("11", "Specialised AI Agents", C_CYAN),
        ("< 90s", "Per Full Proposal", C_PURPLE),
        ("9", "Output Formats", C_GOLD),
        ("< £1", "Per Run API Cost", C_GREEN),
    ]
    sw = (W - 80 - 3*16) / 4
    sy = py - 120

    for i, (num, lbl, col) in enumerate(stats):
        sx = 40 + i * (sw + 16)
        c.setFillColor(HexColor("#0f172a"))
        c.roundRect(sx, sy, sw, 72, 8, fill=1, stroke=0)
        c.setStrokeColor(col)
        c.setLineWidth(0.5)
        c.roundRect(sx, sy, sw, 72, 8, fill=0, stroke=1)
        c.setFillColor(col)
        c.roundRect(sx, sy, sw, 3, 1.5, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(col)
        c.drawCentredString(sx+sw/2, sy+38, num)
        c.setFont("Helvetica", 8)
        c.setFillColor(C_MUTED)
        c.drawCentredString(sx+sw/2, sy+22, lbl)

    # Footer
    c.setFillColor(HexColor("#1e293b"))
    c.rect(0, 0, W, 50, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(C_CYAN)
    c.drawCentredString(W/2, 30, "ECI Business Estimation Tool  ·  Internal Product  ·  2026")
    c.setFont("Helvetica", 8)
    c.setFillColor(C_MUTED)
    c.drawCentredString(W/2, 14, "11 Agents  ·  9 Formats  ·  5 AI Providers  ·  Under 90 Seconds")
    grad_rect(c, 0, 0, W, 4, C_PINK, C_PURPLE, vertical=False)


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    c = canvas.Canvas(OUT, pagesize=A4)
    c.setTitle("ECI Business Estimation Tool — Marketing Brochure")
    c.setAuthor("ECI Presales Intelligence Platform")
    c.setSubject("AI-Powered Presales Intelligence — Marketing Material 2026")

    print("Generating page 1: Cover...")
    page_cover(c)
    c.showPage()

    print("Generating page 2: 11 Agents Pipeline...")
    page_agents(c)
    c.showPage()

    print("Generating page 3: Feature Showcase...")
    page_features(c)
    c.showPage()

    print("Generating page 4: Comparison + ROI...")
    page_compare(c)
    c.showPage()

    print("Generating page 5: CTA / Closing...")
    page_cta(c)
    c.showPage()

    c.save()
    print(f"\nDONE. PDF saved to: {OUT}")
    print(f"   Pages: 5  |  Format: A4  |  Theme: Dark Enterprise")


if __name__ == "__main__":
    main()
