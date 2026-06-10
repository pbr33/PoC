"""
ECI Business Estimation Tool — Stakeholder Pitch PDF
Stunning 10-page A4 boardroom-quality pitch document.

Run:  python marketing/generate_pitch_pdf.py
Out:  marketing/ECI_Presale_AI_Pitch.pdf
"""

import os, math
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color, white, black

W, H = A4  # 595.28 × 841.89 pts
OUT = os.path.join(os.path.dirname(__file__), "ECI_Presale_AI_Pitch.pdf")

# ── Brand palette ─────────────────────────────────────────────────────────
IND   = HexColor("#1D1B4B")
IND2  = HexColor("#2D2A6E")
IND3  = HexColor("#3C397C")
TEA   = HexColor("#00B0A0")
LIM   = HexColor("#94C11C")
ORG   = HexColor("#EA752A")
PUR   = HexColor("#7B61FF")
GRN   = HexColor("#22B373")
CYN   = HexColor("#00D4AA")
BLU   = HexColor("#00B4D8")
GLD   = HexColor("#FFD166")
PNK   = HexColor("#F72585")
RED   = HexColor("#EF4444")

TXT   = HexColor("#E2E8F0")
DIM   = HexColor("#94A3B8")
MUT   = HexColor("#64748B")
BDR   = HexColor("#1E293B")
CARD  = HexColor("#0F172A")
CARD2 = HexColor("#111827")
BG    = HexColor("#020817")


# ══════════════════════════════════════════════════════════════════════════
#  DRAWING PRIMITIVES
# ══════════════════════════════════════════════════════════════════════════

def bg(c, col=None):
    c.setFillColor(col or BG)
    c.rect(0, 0, W, H, fill=1, stroke=0)


def grad_h(c, x, y, w, h, c1, c2):
    """Horizontal gradient (left→right)."""
    steps = max(int(w), 1)
    for i in range(steps):
        t = i / steps
        r = c1.red   + t*(c2.red   - c1.red)
        g = c1.green + t*(c2.green - c1.green)
        b = c1.blue  + t*(c2.blue  - c1.blue)
        c.setFillColor(Color(r, g, b))
        c.rect(x+i, y, 1, h, fill=1, stroke=0)


def grad_v(c, x, y, w, h, c1, c2):
    """Vertical gradient (top→bottom)."""
    steps = max(int(h), 1)
    for i in range(steps):
        t = i / steps
        r = c1.red   + t*(c2.red   - c1.red)
        g = c1.green + t*(c2.green - c1.green)
        b = c1.blue  + t*(c2.blue  - c1.blue)
        c.setFillColor(Color(r, g, b))
        c.rect(x, y+h-i-1, w, 1, fill=1, stroke=0)


def rrect(c, x, y, w, h, r=6, fill=None, stroke=None, sw=0.5):
    if fill:
        c.setFillColor(fill)
    if stroke:
        c.setStrokeColor(stroke)
        c.setLineWidth(sw)
    p = c.beginPath()
    p.moveTo(x+r, y)
    p.lineTo(x+w-r, y)
    p.arcTo(x+w-2*r, y, x+w, y+2*r, 270, 90)
    p.lineTo(x+w, y+h-r)
    p.arcTo(x+w-2*r, y+h-2*r, x+w, y+h, 0, 90)
    p.lineTo(x+r, y+h)
    p.arcTo(x, y+h-2*r, x+2*r, y+h, 90, 90)
    p.lineTo(x, y+r)
    p.arcTo(x, y, x+2*r, y+2*r, 180, 90)
    p.close()
    c.drawPath(p, fill=1 if fill else 0, stroke=1 if stroke else 0)


def glow(c, cx, cy, r, col, alpha=0.05, layers=5):
    for i in range(layers, 0, -1):
        c.setFillColor(col)
        c.setFillAlpha(alpha*(i/layers))
        c.circle(cx, cy, r*i*0.55, fill=1, stroke=0)
    c.setFillAlpha(1)


def txt(c, text, x, y, font="Helvetica", size=10, col=TXT):
    c.setFont(font, size)
    c.setFillColor(col)
    c.drawString(x, y, text)


def txc(c, text, cx, y, font="Helvetica", size=10, col=TXT):
    c.setFont(font, size)
    c.setFillColor(col)
    c.drawCentredString(cx, y, text)


def txr(c, text, rx, y, font="Helvetica", size=10, col=TXT):
    c.setFont(font, size)
    c.setFillColor(col)
    c.drawRightString(rx, y, text)


def top_bar(c, col1=BLU, col2=PUR):
    grad_h(c, 0, H-4, W, 4, col1, col2)


def bot_bar(c, col1=PUR, col2=PNK):
    grad_h(c, 0, 0, W, 4, col1, col2)


def logo_strip(c):
    txt(c, "ECI+  Business Estimation Tool", 42, H-32, "Helvetica-Bold", 10, CYN)


def eyebrow(c, text, cy=None, col=PUR):
    txc(c, text, W/2, cy or H-68, "Helvetica-Bold", 8, col)


def page_footer(c, pg, total=10):
    c.setFillColor(HexColor("#0f172a"))
    c.rect(0, 0, W, 38, fill=1, stroke=0)
    txt(c, "ECI Business Estimation Tool  ·  Confidential  ·  2026", 42, 14, "Helvetica", 8, MUT)
    txr(c, f"{pg} / {total}", W-42, 14, "Helvetica-Bold", 8, DIM)


def section_pill(c, label, col, cy, cx=None):
    pill_w = min(len(label)*7 + 32, 280)
    px = (cx or W/2) - pill_w/2
    rrect(c, px, cy-4, pill_w, 22, r=11,
          fill=Color(col.red, col.green, col.blue, 0.12),
          stroke=Color(col.red, col.green, col.blue, 0.4), sw=0.8)
    txc(c, label, cx or W/2, cy+2, "Helvetica-Bold", 8, col)


def badge(c, label, col, bx, by):
    bw = len(label)*5.5 + 18
    rrect(c, bx, by, bw, 16, r=8,
          fill=Color(col.red, col.green, col.blue, 0.18),
          stroke=Color(col.red, col.green, col.blue, 0.5), sw=0.6)
    txc(c, label, bx+bw/2, by+4, "Helvetica-Bold", 7, col)
    return bw


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 1  —  COVER
# ══════════════════════════════════════════════════════════════════════════

def page_cover(c):
    bg(c)

    # Deep gradient top half
    grad_v(c, 0, H//2, W, H//2,
           Color(0.035, 0.055, 0.14, 0.97),
           Color(0.008, 0.031, 0.09, 0))

    # Glow orbs
    c.saveState()
    glow(c, W*0.82, H*0.72, 220, PUR, 0.04, 7)
    glow(c, W*0.18, H*0.32, 190, BLU, 0.05, 7)
    glow(c, W*0.5,  H*0.08, 170, PNK, 0.04, 6)
    glow(c, W*0.5,  H*0.55, 260, IND2, 0.06, 8)
    c.restoreState()

    top_bar(c, BLU, PNK)
    bot_bar(c, PUR, PNK)

    # Logo top-left
    txt(c, "ECI+", 42, H-40, "Helvetica-Bold", 18, TXT)
    txt(c, "  Business Estimation Tool", 42+39, H-36, "Helvetica-Bold", 10, CYN)

    # "Powered by" badges top-right
    ai_providers = ["Azure OpenAI", "Claude", "Gemini", "Qwen"]
    pbx = W - 42
    for p in reversed(ai_providers):
        pw = len(p)*5.5 + 16
        pbx -= pw + 6
        rrect(c, pbx, H-46, pw, 18, r=9,
              fill=HexColor("#ffffff08"), stroke=HexColor("#ffffff18"), sw=0.5)
        txc(c, p, pbx+pw/2, H-41, "Helvetica", 6.5, DIM)

    # Centre — main headline
    pill_y = H - 152
    section_pill(c, "AI-POWERED PRESALES INTELLIGENCE PLATFORM", CYN, pill_y)

    c.setFont("Helvetica-Bold", 50)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-210, "From Scope to")
    c.setFillColor(CYN)
    c.drawCentredString(W/2, H-268, "Boardroom-Ready")
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-326, "Proposal")
    c.setFont("Helvetica-Bold", 34)
    c.setFillColor(PUR)
    c.drawCentredString(W/2, H-372, "in Under 90 Seconds.")

    c.setFont("Helvetica", 12)
    c.setFillColor(DIM)
    c.drawCentredString(W/2, H-410, "11 specialist AI agents · 9 professional deliverables · 5 AI providers")
    c.drawCentredString(W/2, H-428, "One upload. One click. Every document your client expects.")

    # ── KPI boxes ─────────────────────────────────────────────────────────
    kpis = [
        ("<90s", "End-to-End",     CYN),
        ("11",   "AI Agents",      PUR),
        ("9",    "Deliverables",   GLD),
        ("£<1",  "Per Run",        GRN),
        ("5",    "AI Providers",   PNK),
        ("99%",  "Time Saved",     ORG),
    ]
    kw, kg = 82, 9
    total_w = len(kpis)*kw + (len(kpis)-1)*kg
    kx0 = (W - total_w)/2
    ky  = H - 520

    for i, (num, lbl, col) in enumerate(kpis):
        bx = kx0 + i*(kw+kg)
        # Card
        rrect(c, bx, ky-56, kw, 56, r=8,
              fill=HexColor("#ffffff07"), stroke=HexColor("#ffffff10"), sw=0.5)
        # Accent bottom bar
        grad_h(c, bx+1, ky-56, kw-2, 2, col, Color(col.red*.6, col.green*.6, col.blue*.6))
        # Glow dot top
        c.saveState()
        c.setFillColor(col); c.setFillAlpha(0.18)
        c.circle(bx+kw/2, ky-12, 22, fill=1, stroke=0)
        c.setFillAlpha(1)
        c.restoreState()
        # Number
        c.setFont("Helvetica-Bold", 19)
        c.setFillColor(col)
        c.drawCentredString(bx+kw/2, ky-22, num)
        # Label
        c.setFont("Helvetica", 7)
        c.setFillColor(MUT)
        c.drawCentredString(bx+kw/2, ky-38, lbl.upper())

    # ── Visual pipeline preview ────────────────────────────────────────────
    pipe_y = ky - 100
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(MUT)
    c.drawCentredString(W/2, pipe_y+10, "THE PIPELINE  ·  EVERY RUN  ·  FULLY AUTOMATED")

    dots = 11
    dot_r = 6
    spacing = (W - 100) / (dots - 1)
    for i in range(dots):
        dx = 50 + i*spacing
        dy = pipe_y - 18
        cols = [PUR,BLU,PUR,GLD,RED,CYN,BLU,PUR,GRN,GLD,PNK]
        c.saveState()
        c.setFillColor(cols[i]); c.setFillAlpha(0.25)
        c.circle(dx, dy, dot_r+3, fill=1, stroke=0)
        c.setFillAlpha(1)
        c.restoreState()
        c.setFillColor(cols[i])
        c.circle(dx, dy, dot_r, fill=1, stroke=0)
        if i < dots-1:
            c.setStrokeColor(HexColor("#334155"))
            c.setLineWidth(0.8)
            c.setDash(4, 3)
            c.line(dx+dot_r, dy, dx+spacing-dot_r, dy)
            c.setDash()

    c.setStrokeColor(HexColor("#1e293b"))
    c.setLineWidth(0.5)
    c.line(50, 110, W-50, 110)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(CYN)
    c.drawCentredString(W/2, 82, "ECI Business Estimation Tool  ·  Internal Product  ·  2026")
    c.setFont("Helvetica", 8)
    c.setFillColor(MUT)
    c.drawCentredString(W/2, 64, "Transforming presales — one proposal at a time")


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 2  —  THE PROBLEM
# ══════════════════════════════════════════════════════════════════════════

def page_problem(c):
    bg(c)
    top_bar(c, RED, ORG)
    bot_bar(c, RED, ORG)
    logo_strip(c)

    eyebrow(c, "THE PRESALES PROBLEM", H-68, RED)
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-108, "Your Best Engineers Spend")
    c.setFillColor(RED)
    c.drawCentredString(W/2, H-148, "40 Hours Per Proposal.")

    c.setFont("Helvetica", 12)
    c.setFillColor(DIM)
    c.drawCentredString(W/2, H-176, "And the result is still inconsistent, rushed, and not reusable.")

    # Pain points grid
    pains = [
        ("⏰", "40+ Hours",      "Each proposal takes 1–5 days of senior engineer time.",      RED),
        ("🔄", "No Reuse",       "Every estimate starts from scratch. Past project data sits in emails.",  ORG),
        ("🤔", "Inconsistency",  "Two consultants produce wildly different estimates for the same scope.",  GLD),
        ("❌", "Missed Scope",   "Critical assumptions and risks buried in emails, found too late.",        PNK),
        ("💸", "£3,000/Proposal","Fully-loaded cost per manual proposal. 10×/month = £360K/year.",         RED),
        ("🏃", "Lost Deals",     "Competitor submits in 2 hours. You take 2 days. Client moved on.",       ORG),
    ]

    cols = 2
    cw = (W - 80 - 12) / 2
    ch = 82
    sy = H - 232

    for i, (icon, title, desc, col) in enumerate(pains):
        row = i // cols
        ci  = i % cols
        bx  = 40 + ci*(cw+12)
        by  = sy - row*(ch+10) - ch

        rrect(c, bx, by, cw, ch, r=8,
              fill=HexColor("#0f172a"), stroke=Color(col.red,col.green,col.blue,0.3), sw=0.8)
        # Left accent bar
        grad_v(c, bx, by, 3, ch, col, Color(col.red,col.green,col.blue,0.2))

        c.setFont("Helvetica", 18)
        c.drawString(bx+14, by+ch-30, icon)
        c.setFont("Helvetica-Bold", 11)
        c.setFillColor(col)
        c.drawString(bx+46, by+ch-24, title)
        c.setFont("Helvetica", 8)
        c.setFillColor(DIM)
        # Wrap desc at ~50 chars
        words = desc.split()
        lines_, cur = [], ""
        for w in words:
            if len(cur)+len(w)+1 <= 58:
                cur = (cur+" "+w).strip()
            else:
                lines_.append(cur); cur = w
        if cur: lines_.append(cur)
        for j, l in enumerate(lines_[:2]):
            c.drawString(bx+46, by+ch-40-j*12, l)

    # Arrow bridge
    bridge_y = sy - 3*(ch+10) - ch - 26
    c.setStrokeColor(HexColor("#334155"))
    c.setLineWidth(1.5)
    c.setDash(6, 4)
    c.line(W/2, bridge_y, W/2, bridge_y-20)
    c.setDash()
    c.setFillColor(GRN)
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(W/2, bridge_y-30, "↓")

    # Solution teaser
    teaser_y = bridge_y - 60
    rrect(c, 40, teaser_y-46, W-80, 56, r=10,
          fill=Color(0,0.7,0.6,0.06), stroke=Color(0,0.7,0.6,0.3), sw=1)
    grad_h(c, 40, teaser_y-46, 3, 56, GRN, Color(GRN.red,GRN.green,GRN.blue,0.1))
    c.setFont("Helvetica-Bold", 13)
    c.setFillColor(GRN)
    c.drawCentredString(W/2, teaser_y-4, "ECI Estimation Tool solves every one of these — simultaneously.")
    c.setFont("Helvetica", 9)
    c.setFillColor(DIM)
    c.drawCentredString(W/2, teaser_y-22, "Same scope document. Under 90 seconds. All 9 deliverables. Every time.")

    page_footer(c, 2)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 3  —  SOLUTION OVERVIEW
# ══════════════════════════════════════════════════════════════════════════

def page_solution(c):
    bg(c)
    top_bar(c, CYN, GRN)
    bot_bar(c, CYN, GRN)
    logo_strip(c)

    eyebrow(c, "THE SOLUTION", H-68, CYN)
    c.setFont("Helvetica-Bold", 36)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-108, "One Button.")
    c.setFillColor(CYN)
    c.drawCentredString(W/2, H-148, "Every Deliverable. Instantly.")

    c.setFont("Helvetica", 11)
    c.setFillColor(DIM)
    c.drawCentredString(W/2, H-174, "Upload any scope document → click Analyse → 11 AI agents run in parallel")
    c.drawCentredString(W/2, H-190, "producing a complete commercial package in under 90 seconds.")

    # Flow diagram: Input → Pipeline → 9 Outputs
    fx = 42
    fy = H - 255
    fw = W - 84

    # Input box
    iw = 110
    rrect(c, fx, fy-50, iw, 50, r=8, fill=IND2, stroke=CYN, sw=1)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(CYN)
    c.drawCentredString(fx+iw/2, fy-16, "SCOPE")
    c.drawCentredString(fx+iw/2, fy-29, "DOCUMENT")
    c.setFont("Helvetica", 7)
    c.setFillColor(DIM)
    c.drawCentredString(fx+iw/2, fy-42, "PDF · DOCX · TXT · XLSX")

    # Arrow
    ax1 = fx+iw+4
    c.setFillColor(GLD)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(ax1+2, fy-30, "→")

    # Pipeline block
    pw_blk = fw - iw - 130 - 40
    px = ax1 + 22
    rrect(c, px, fy-50, pw_blk, 50, r=8,
          fill=Color(PUR.red, PUR.green, PUR.blue, 0.12), stroke=PUR, sw=1)
    grad_h(c, px, fy-50, pw_blk, 2, PUR, BLU)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(TXT)
    c.drawCentredString(px+pw_blk/2, fy-14, "11 AI AGENTS — PARALLEL PIPELINE")
    # Mini agent dots
    dot_n = 11
    dot_sp = (pw_blk - 24) / (dot_n - 1)
    dot_cols = [PUR,BLU,PUR,GLD,RED,CYN,BLU,PUR,GRN,GLD,PNK]
    for i in range(dot_n):
        dx = px+12+i*dot_sp
        c.setFillColor(dot_cols[i])
        c.circle(dx, fy-36, 4, fill=1, stroke=0)
        if i < dot_n-1:
            c.setStrokeColor(HexColor("#334155"))
            c.setLineWidth(0.5)
            c.setDash(2,2)
            c.line(dx+4, fy-36, dx+dot_sp-4, fy-36)
            c.setDash()

    # Arrow
    ax2 = px+pw_blk+4
    c.setFillColor(GLD)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(ax2+2, fy-30, "→")

    # Output block
    ow = 120
    ox = ax2+22
    rrect(c, ox, fy-50, ow, 50, r=8, fill=IND2, stroke=GRN, sw=1)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(GRN)
    c.drawCentredString(ox+ow/2, fy-14, "9 DELIVERABLES")
    c.setFont("Helvetica", 7)
    c.setFillColor(DIM)
    fmts = ["Excel", "PDF", "PPTX", "SOW", "JSON", "+4 more"]
    for i, f in enumerate(fmts):
        c.drawCentredString(ox+ow/2, fy-26-i*6, f)

    # ── Output formats grid ────────────────────────────────────────────────
    out_y = fy - 76
    outputs = [
        ("📊", "Excel Estimate",  "Multi-tab workbook with time,\ncost, risks, team, scenarios.",     GLD),
        ("📄", "PDF Proposal",    "Executive-quality 20+ page PDF\nwith ECI branding.",               BLU),
        ("🖥",  "PowerPoint",     "Premium indigo 20-slide deck.\nDark enterprise design.",            PUR),
        ("📝", "SOW Document",    "Full Statement of Work with\ndeliverables & acceptance criteria.",  CYN),
        ("🔀", "Scenario Report", "3-scenario Excel: conservative,\nrealistic, aggressive.",           GRN),
        ("❓", "Discovery Q&A",   "Clarification questions for\npre-sales workshops.",                 PNK),
        ("🌐", "3D Architecture", "Interactive Three.js diagram\nviewable in-browser.",               ORG),
        ("🎬", "AI Video",        "MP4 narrator video via HeyGen\nor ElevenLabs TTS.",                RED),
        ("🔗", "ZIP Bundle",      "All formats in one download.\nReady for the client email.",         TEA),
    ]

    oc = 3
    ocw = (W - 80 - (oc-1)*10) / oc
    och = 86
    osy = out_y - 20

    for i, (icon, title, desc, col) in enumerate(outputs):
        row = i // oc
        ci  = i % oc
        bx  = 40 + ci*(ocw+10)
        by  = osy - row*(och+8) - och

        rrect(c, bx, by, ocw, och, r=7,
              fill=HexColor("#0f172a"), stroke=Color(col.red,col.green,col.blue,0.25), sw=0.6)
        # Top accent
        grad_h(c, bx, by+och-2, ocw, 2, col, Color(col.red*.5,col.green*.5,col.blue*.5))

        # Icon circle
        c.saveState()
        c.setFillColor(col); c.setFillAlpha(0.15)
        c.circle(bx+18, by+och-22, 12, fill=1, stroke=0)
        c.setFillAlpha(1)
        c.restoreState()
        c.setFont("Helvetica", 13)
        c.drawString(bx+11, by+och-28, icon)

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(TXT)
        c.drawString(bx+36, by+och-18, title)

        lines = desc.strip().split("\n")
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUT)
        for j, l in enumerate(lines):
            c.drawString(bx+10, by+och-38-j*11, l.strip())

    page_footer(c, 3)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 4  —  11 AGENTS DEEP DIVE
# ══════════════════════════════════════════════════════════════════════════

def page_agents(c):
    bg(c)
    top_bar(c, PUR, BLU)
    bot_bar(c, PUR, BLU)
    logo_strip(c)

    eyebrow(c, "THE INTELLIGENCE ENGINE", H-68, PUR)
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-104, "11 Specialist Agents.")
    c.setFillColor(PUR)
    c.drawCentredString(W/2, H-138, "Purpose-Built. Always Parallel.")

    c.setFont("Helvetica", 10)
    c.setFillColor(DIM)
    c.drawCentredString(W/2, H-162, "Each agent is an expert in its domain. They run simultaneously and cross-validate each other's outputs.")

    agents = [
        ("0", "Completeness Checker",    "Audits scope gaps before the pipeline starts.\nGenerates pre-qualification questions.",           PUR, "PRE-FLIGHT"),
        ("1", "Requirements Analyst",    "Extracts functional + non-functional requirements.\nTags complexity, ambiguity and risk flags.",    BLU, "ANALYSIS"),
        ("2", "Cost Estimator",          "Calculates delivery costs per role & phase.\nApplies contract type, seniority, and region premiums.", PUR, "FINANCIALS"),
        ("3", "Time Planner",            "Builds phased timeline with buffer zones.\nApplies Brooks' Law and capacity constraints.",         GLD, "SCHEDULE"),
        ("4", "Risk Analyst",            "Identifies, scores and mitigates 10–20 risks.\nRAG status, probability × impact matrix.",          RED, "RISK"),
        ("5", "Architecture Designer",   "Proposes solution architecture with components,\ndata flows, security, and scalability patterns.",  CYN, "TECHNICAL"),
        ("6", "Team Composer",           "Defines optimal team structure and roles.\nBalances seniority mix and utilisation.",               BLU, "RESOURCING"),
        ("7", "SOW Generator",           "Writes complete Statement of Work.\nDeliverables, acceptance criteria, exclusions.",              PUR, "LEGAL"),
        ("8", "Discovery Engine",        "Generates intelligent clarification Q&A.\nStructured for client workshops.",                       GRN, "DISCOVERY"),
        ("9", "Azure Pricer",            "Queries Azure Retail Prices API live.\nMaps architecture to real infra costs.",                    GLD, "CLOUD"),
        ("10","Proposal Writer",         "Synthesises all outputs into executive narrative.\nFull proposal document — human-quality prose.",  PNK, "NARRATIVE"),
    ]

    cols = 2
    aw = (W - 80 - 12) / cols
    ah = 68
    sy = H - 196

    for i, (num, title, desc, col, tag) in enumerate(agents):
        row = i // cols
        ci  = i % cols
        if i == 10:  # last card centred
            bx = W/2 - aw/2
        else:
            bx = 40 + ci*(aw+12)
        by = sy - row*(ah+8) - ah

        rrect(c, bx, by, aw, ah, r=8,
              fill=HexColor("#0f172a"), stroke=Color(col.red,col.green,col.blue,0.3), sw=0.6)
        # Left bar
        grad_v(c, bx, by, 3, ah, col, Color(col.red,col.green,col.blue,0.1))

        # Badge number
        c.saveState()
        c.setFillColor(col); c.setFillAlpha(0.15)
        c.circle(bx+16, by+ah-18, 11, fill=1, stroke=0)
        c.setFillAlpha(1)
        c.restoreState()
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(col)
        c.drawCentredString(bx+16, by+ah-21, num)

        # Title
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(TXT)
        c.drawString(bx+32, by+ah-14, title)

        # Tag badge
        bw_ = badge(c, tag, col, bx+aw-len(tag)*5-26, by+ah-20)

        # Desc
        lines = desc.strip().split("\n")
        c.setFont("Helvetica", 7.5)
        c.setFillColor(DIM)
        for j, l in enumerate(lines):
            c.drawString(bx+32, by+ah-28-j*12, l.strip())

    page_footer(c, 4)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 5  —  15 RESULT TABS
# ══════════════════════════════════════════════════════════════════════════

def page_results(c):
    bg(c)
    top_bar(c, GRN, CYN)
    bot_bar(c, GRN, CYN)
    logo_strip(c)

    eyebrow(c, "RESULTS DASHBOARD", H-68, GRN)
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-104, "15 Intelligence Panels.")
    c.setFillColor(GRN)
    c.drawCentredString(W/2, H-138, "Every Answer. Instantly.")

    c.setFont("Helvetica", 10)
    c.setFillColor(DIM)
    c.drawCentredString(W/2, H-160, "Results are organised into 15 tabs — no raw JSON, no prompts — clean, decision-ready intelligence.")

    tabs = [
        ("📋", "Overview",           "Executive summary with project name,\nclient, type, key metrics.",           CYN),
        ("💰", "Cost Estimate",       "Fully itemised cost breakdown by role,\nphase and contract type.",            GLD),
        ("⏱",  "Time Estimate",       "Phase-by-phase timeline with milestones,\nbuffers and total duration.",       BLU),
        ("⚠",  "Risk Register",       "10–20 scored risks, RAG status,\nmitigations and ownership.",               RED),
        ("🏗",  "Architecture",        "Solution components, data flows,\nsecurity and scalability design.",         CYN),
        ("👥", "Team Plan",           "Roles, headcount, utilisation and\noptimal seniority mix.",                  BLU),
        ("📝", "Scope of Work",       "In-scope items, exclusions,\nassumptions and prerequisites.",                GRN),
        ("🔀", "Scenarios",           "3 commercial scenarios with side-by-side\ncost and time comparison.",         PUR),
        ("❓", "Discovery Q&A",       "Structured pre-sales questions\nfor client workshops.",                      PNK),
        ("☁",  "Azure Pricing",       "Live Azure cost map: per service,\nmonthly and annual run costs.",           BLU),
        ("🌐", "AI Architecture",     "AI-generated cinematic diagram\nwith Three.js 3D viewer.",                   PUR),
        ("📄", "Proposal Text",       "Full executive proposal narrative\nready to send.",                          TEA),
        ("📊", "Presentation",        "20-slide premium PPTX viewer\nwith inline download.",                        GLD),
        ("🎬", "Video Narration",     "AI presenter video via HeyGen\nor ElevenLabs. MP4 output.",                 PNK),
        ("💬", "AI Chat",             "Proposal-aware chat assistant.\nAnswers rooted in your specific data.",      CYN),
    ]

    cols = 3
    tw = (W - 80 - (cols-1)*10) / cols
    th = 74
    sy = H - 188

    for i, (icon, title, desc, col) in enumerate(tabs):
        row = i // cols
        ci  = i % cols
        bx  = 40 + ci*(tw+10)
        by  = sy - row*(th+8) - th

        rrect(c, bx, by, tw, th, r=7,
              fill=HexColor("#0f172a"), stroke=Color(col.red,col.green,col.blue,0.2), sw=0.5)
        grad_h(c, bx, by+th-2, tw, 2, col, Color(col.red*.4,col.green*.4,col.blue*.4))

        # Tab number chip
        c.saveState()
        c.setFillColor(col); c.setFillAlpha(0.12)
        c.roundRect(bx+8, by+th-20, 20, 14, 7, fill=1, stroke=0)
        c.setFillAlpha(1)
        c.restoreState()
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(col)
        c.drawCentredString(bx+18, by+th-14, str(i+1))

        c.setFont("Helvetica", 13)
        c.drawString(bx+32, by+th-18, icon)

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(TXT)
        c.drawString(bx+50, by+th-14, title)

        lines = desc.strip().split("\n")
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUT)
        for j, l in enumerate(lines):
            c.drawString(bx+10, by+th-30-j*11, l.strip())

    page_footer(c, 5)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 6  —  STANDOUT FEATURES
# ══════════════════════════════════════════════════════════════════════════

def page_features(c):
    bg(c)

    c.saveState()
    glow(c, W*0.88, H*0.55, 260, PUR, 0.03, 6)
    glow(c, W*0.12, H*0.55, 220, BLU, 0.03, 6)
    c.restoreState()

    top_bar(c, PUR, PNK)
    bot_bar(c, PNK, PUR)
    logo_strip(c)

    eyebrow(c, "STANDOUT CAPABILITIES", H-68, PUR)
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-104, "Features Your Competitors")
    c.setFillColor(PNK)
    c.drawCentredString(W/2, H-140, "Simply Don't Have")

    features = [
        ("🌐", "3D Architecture Viewer",      PUR,
         "Interactive Three.js fly-through of your proposed solution.\n"
         "Rotate, zoom, click nodes. Impress clients in the room — live.\n"
         "Export as PNG. Auto-generated from architecture output."),
        ("🎬", "AI Video Narration",           PNK,
         "Generates a full presenter video via HeyGen, D-ID or ElevenLabs.\n"
         "Your proposal presents itself before the meeting starts.\n"
         "Voice, avatar, slides — MP4 downloadable in one click."),
        ("🧠", "Continuous Learning Engine",   GRN,
         "Records actual vs estimated hours. Derives correction factors\n"
         "per technology category. Each proposal makes the next one smarter.\n"
         "Institutional memory that compounds over time."),
        ("🔀", "Live Scenario Modelling",      CYN,
         "3 simultaneous what-if scenarios with Brooks' Law scaling.\n"
         "Seniority factors, contract type premiums, scope variance.\n"
         "Answer any commercial question in the room — instantly."),
        ("☁",  "Real-Time Azure Pricing",      BLU,
         "Queries the Azure Retail Prices API in real time.\n"
         "Every infrastructure estimate backed by actual 2026 data.\n"
         "Monthly and annual breakdown per service type."),
        ("💬", "Proposal-Aware AI Chat",       GLD,
         "Chat assistant loaded with your specific proposal context.\n"
         "Not generic — every answer is grounded in your actual scope,\n"
         "costs, risks, and architecture. Like having a domain expert on call."),
        ("🗂",  "Persistent Run Library",       ORG,
         "All estimations saved to local SQLite with full history.\n"
         "Client name auto-extracted. Architect review gate. Restore any run.\n"
         "Your estimation library grows every day."),
        ("⌨",  "Command Palette",              TEA,
         "Press Ctrl+K. Navigate tabs, trigger downloads, test connections —\n"
         "all keyboard-driven. Built for consultants who run 10+ proposals/week.\n"
         "Zero mouse required for power operations."),
        ("🔍", "Scope Completeness Checker",   RED,
         "Agent 0 audits your scope document before the pipeline fires.\n"
         "Detects missing NFRs, ambiguous language, and open assumptions.\n"
         "Generates a gap checklist to resolve before client submission."),
    ]

    cols = 3
    fw = (W - 80 - (cols-1)*10) / cols
    fh = 96
    sy = H - 184

    for i, (icon, title, col, desc) in enumerate(features):
        row = i // cols
        ci  = i % cols
        bx  = 40 + ci*(fw+10)
        by  = sy - row*(fh+8) - fh

        rrect(c, bx, by, fw, fh, r=8,
              fill=HexColor("#0f172a"), stroke=Color(col.red,col.green,col.blue,0.25), sw=0.6)
        grad_h(c, bx, by+fh-2, fw, 2, col, Color(col.red*.5,col.green*.5,col.blue*.5))

        # Icon box
        c.saveState()
        c.setFillColor(col); c.setFillAlpha(0.14)
        c.roundRect(bx+10, by+fh-40, 28, 28, 4, fill=1, stroke=0)
        c.setFillAlpha(1)
        c.restoreState()
        c.setFont("Helvetica", 14)
        c.drawString(bx+14, by+fh-26, icon)

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(TXT)
        c.drawString(bx+44, by+fh-20, title)
        c.setFillColor(col)
        c.roundRect(bx+44, by+fh-24, c.stringWidth(title,"Helvetica-Bold",9), 1, 0, fill=1, stroke=0)

        lines = desc.strip().split("\n")
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUT)
        for j, l in enumerate(lines):
            c.drawString(bx+10, by+fh-46-j*11, l.strip())

    page_footer(c, 6)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 7  —  AI PROVIDERS & TECH STACK
# ══════════════════════════════════════════════════════════════════════════

def page_tech(c):
    bg(c)
    top_bar(c, CYN, BLU)
    bot_bar(c, BLU, CYN)
    logo_strip(c)

    eyebrow(c, "TECHNOLOGY STACK", H-68, CYN)
    c.setFont("Helvetica-Bold", 32)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-104, "Best-in-Class AI.")
    c.setFillColor(CYN)
    c.drawCentredString(W/2, H-140, "Best-in-Class Tools.")

    c.setFont("Helvetica", 10)
    c.setFillColor(DIM)
    c.drawCentredString(W/2, H-163, "ECI Estimate is model-agnostic — use whichever AI your organisation already has licensed.")

    # AI Providers row
    section_pill(c, "AI MODEL PROVIDERS", GLD, H-196)

    providers = [
        ("Azure OpenAI",     "GPT-4o / o3-mini\nGPT-4 Turbo",        BLU,  "●"),
        ("Anthropic Claude", "Claude Sonnet 4\nClaude Haiku 4",       PUR,  "●"),
        ("Google Gemini",    "Gemini 1.5 Pro\nGemini 2.0 Flash",      GRN,  "●"),
        ("Qwen Foundry",     "Qwen-Max\nQwen-Plus",                   GLD,  "●"),
        ("Vertex AI",        "Llama 3.3 / 3.1\nMistral Large",        PNK,  "●"),
    ]

    prow_y = H - 234
    pw = (W - 80 - 4*10) / 5
    ph = 68

    for i, (name, models, col, dot) in enumerate(providers):
        bx = 40 + i*(pw+10)
        by = prow_y - ph
        rrect(c, bx, by, pw, ph, r=8,
              fill=Color(col.red,col.green,col.blue,0.08), stroke=col, sw=0.8)
        c.setFillColor(col)
        c.circle(bx+12, by+ph-14, 4, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(TXT)
        c.drawString(bx+22, by+ph-16, name)
        lines = models.split("\n")
        c.setFont("Helvetica", 7)
        c.setFillColor(DIM)
        for j, l in enumerate(lines):
            c.drawString(bx+10, by+ph-32-j*12, l)
        # "LIVE" badge
        badge(c, "LIVE", col, bx+pw-38, by+6)

    # Tech stack grid
    section_pill(c, "PLATFORM STACK", TEA, prow_y - ph - 28)

    stacks = [
        ("Frontend",        ["Python Streamlit", "Three.js 3D", "HTML/CSS/JS", "Components API"],        CYN),
        ("Document I/O",    ["python-pptx", "reportlab", "openpyxl", "PyPDF2", "docx2txt"],              GLD),
        ("AI & Agents",     ["LangChain", "Custom agents", "Multi-model routing", "Parallel execution"], PUR),
        ("Data & Storage",  ["SQLite history", "Milvus vector DB", "SharePoint API", "Azure Blob"],      BLU),
        ("Integrations",    ["Azure Pricing API", "HeyGen video", "ElevenLabs TTS", "Email SMTP"],       GRN),
        ("Infrastructure",  ["Azure App Service", "Azure OpenAI Service", "Azure Functions", "Docker"],  ORG),
    ]

    sw_ = (W - 80 - 2*12) / 3
    sh = 96
    ssy = prow_y - ph - 70

    for i, (cat, items, col) in enumerate(stacks):
        row = i // 3
        ci  = i % 3
        bx  = 40 + ci*(sw_+12)
        by  = ssy - row*(sh+10) - sh

        rrect(c, bx, by, sw_, sh, r=7,
              fill=HexColor("#0f172a"), stroke=Color(col.red,col.green,col.blue,0.25), sw=0.5)
        grad_h(c, bx, by+sh-2, sw_, 2, col, Color(col.red*.4,col.green*.4,col.blue*.4))

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(col)
        c.drawString(bx+12, by+sh-16, cat)

        c.setFont("Helvetica", 7.5)
        c.setFillColor(DIM)
        for j, item in enumerate(items[:4]):
            c.drawString(bx+12, by+sh-30-j*12, "• " + item)

    page_footer(c, 7)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 8  —  COMPARISON & ROI
# ══════════════════════════════════════════════════════════════════════════

def page_roi(c):
    bg(c)
    top_bar(c, GLD, ORG)
    bot_bar(c, GLD, ORG)
    logo_strip(c)

    eyebrow(c, "RETURN ON INVESTMENT", H-68, GLD)
    c.setFont("Helvetica-Bold", 30)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-104, "The Numbers Are")
    c.setFillColor(GLD)
    c.drawCentredString(W/2, H-138, "Arithmetically Certain.")

    # Big ROI numbers
    bigroi = [
        ("99.9%",   "Time Reduction",     "38 hrs → 90 secs",   GRN),
        ("3,000×",  "Cost Efficiency",    "£3,000 → £<1",        GLD),
        ("8×",      "Team Throughput",    "2 → 20 proposals/week", BLU),
        ("100%",    "Brand Consistency",  "Every consultant, every time", PUR),
    ]
    bw_ = (W - 80 - 3*12) / 4
    bh_ = 76
    by_ = H - 190

    for i, (num, label, sub, col) in enumerate(bigroi):
        bx = 40 + i*(bw_+12)
        by_card = by_ - bh_

        rrect(c, bx, by_card, bw_, bh_, r=8,
              fill=Color(col.red,col.green,col.blue,0.08), stroke=col, sw=1)
        grad_h(c, bx, by_card, bw_, 2, col, Color(col.red*.5,col.green*.5,col.blue*.5))

        c.saveState()
        glow(c, bx+bw_/2, by_card+bh_/2+8, 30, col, 0.05, 4)
        c.restoreState()

        c.setFont("Helvetica-Bold", 22)
        c.setFillColor(col)
        c.drawCentredString(bx+bw_/2, by_card+bh_-26, num)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(TXT)
        c.drawCentredString(bx+bw_/2, by_card+bh_-40, label)
        c.setFont("Helvetica", 7)
        c.setFillColor(DIM)
        c.drawCentredString(bx+bw_/2, by_card+bh_-54, sub)

    # Comparison table
    tbl_y = by_card - 24

    headers = ["Capability",            "Manual",         "Generic AI",     "⚡ ECI Estimate"]
    rows_d  = [
        ("Time to first proposal",      "8–40 hours",     "2–4 hours",      "< 90 seconds"),
        ("Cost per proposal",           "£800–£3,000",    "£200+/month",    "Under £1"),
        ("Infrastructure pricing",      "Manual lookup",  "None",           "Azure Retail API"),
        ("Risk register",               "Ad hoc notes",   "Basic list",     "Scored RAG matrix"),
        ("Scenario modelling",          "Hours rework",   "None",           "3 scenarios live"),
        ("Learns from actuals",         "Tribal knowledge","None",          "Auto-corrected"),
        ("3D architecture view",        "Hire designer",  "None",           "Three.js viewer"),
        ("AI video narration",          "Hire presenter", "None",           "HeyGen / D-ID"),
        ("Multi-model support",         "N/A",            "Single vendor",  "5 AI providers"),
        ("SOW document",                "Template + manual","Basic",        "Full legal SOW"),
        ("Consistency across team",     "Variable",       "Prompt-dependent","Structured pipeline"),
    ]

    row_h = 25
    col_widths = [168, 100, 100, 122]
    tbl_x = 30
    tbl_w = sum(col_widths)

    # Header
    c.setFillColor(HexColor("#111827"))
    c.rect(tbl_x, tbl_y - row_h, tbl_w, row_h, fill=1, stroke=0)
    hx = tbl_x
    for i, (hdr, cw) in enumerate(zip(headers, col_widths)):
        fc = GLD if i == 3 else (TXT if i == 0 else MUT)
        c.setFont("Helvetica-Bold", 8)
        c.setFillColor(fc)
        c.drawCentredString(hx+cw/2, tbl_y-row_h+8, hdr)
        hx += cw

    for ri, row_vals in enumerate(rows_d):
        ry = tbl_y - (ri+2)*row_h
        bg_c = HexColor("#0a1628") if ri%2==0 else HexColor("#0f172a")
        c.setFillColor(bg_c)
        c.rect(tbl_x, ry, tbl_w, row_h, fill=1, stroke=0)
        # ECI column tint
        eci_x = tbl_x + col_widths[0] + col_widths[1] + col_widths[2]
        c.setFillColor(HexColor("#ffd16610"))
        c.rect(eci_x, ry, col_widths[3], row_h, fill=1, stroke=0)

        fx = tbl_x
        for ci, (val, cw) in enumerate(zip(row_vals, col_widths)):
            fc = GLD if ci == 3 else (TXT if ci == 0 else MUT)
            fnt = "Helvetica-Bold" if ci in (0,3) else "Helvetica"
            c.setFont(fnt, 7.5)
            c.setFillColor(fc)
            c.drawCentredString(fx+cw/2, ry+7, val)
            fx += cw
        c.setStrokeColor(HexColor("#1e293b"))
        c.setLineWidth(0.3)
        c.line(tbl_x, ry, tbl_x+tbl_w, ry)

    c.setStrokeColor(HexColor("#1e293b"))
    c.setLineWidth(0.5)
    c.roundRect(tbl_x, tbl_y-(len(rows_d)+1)*row_h, tbl_w, (len(rows_d)+1)*row_h, 6, fill=0, stroke=1)

    # Quote
    q_y = tbl_y - (len(rows_d)+1)*row_h - 46
    rrect(c, 40, q_y-28, W-80, 40, r=8,
          fill=HexColor("#0f172a"), stroke=CYN, sw=0.5)
    c.setFillColor(CYN)
    c.rect(40, q_y-28, 3, 40, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, q_y-2, '"ROI is not a projection. It is arithmetically certain."')
    c.setFont("Helvetica", 8)
    c.setFillColor(MUT)
    c.drawCentredString(W/2, q_y-16, "At 10 proposals/month you recover the platform cost in the first week.")

    page_footer(c, 8)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 9  —  USE CASES & INTEGRATIONS
# ══════════════════════════════════════════════════════════════════════════

def page_usecases(c):
    bg(c)
    top_bar(c, TEA, GRN)
    bot_bar(c, GRN, TEA)
    logo_strip(c)

    eyebrow(c, "USE CASES & INTEGRATIONS", H-68, TEA)
    c.setFont("Helvetica-Bold", 30)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-104, "Works Everywhere")
    c.setFillColor(TEA)
    c.drawCentredString(W/2, H-138, "Your Team Works.")

    # Use cases
    section_pill(c, "PRIMARY USE CASES", CYN, H-172)

    ucases = [
        ("🏢", "Enterprise Pre-Sales",
         "Respond to RFPs and Invitations to Tender in hours,\n"
         "not days. Win rate improves when proposals are faster,\n"
         "more complete and visually superior.", CYN),
        ("🤝", "Client Discovery Workshops",
         "Run the Discovery Q&A output as your workshop agenda.\n"
         "Every question is grounded in the actual scope document.\n"
         "Structure conversations that convert.", BLU),
        ("📐", "Architecture Reviews",
         "Architect-gate every proposal with the run history.\n"
         "Review, annotate, approve or reject before client send.\n"
         "Senior oversight without senior bottleneck.", PUR),
        ("📈", "Commercial Negotiations",
         "Pull up the 3-scenario comparison live in the meeting.\n"
         "Show exactly what changes if timeline shrinks or\n"
         "team size grows. Commercial clarity wins trust.", GLD),
        ("🎓", "Graduate Onboarding",
         "Junior consultants immediately produce senior-quality\n"
         "estimates. No tribal knowledge required. Ramp time\n"
         "drops from months to days.", GRN),
        ("🔁", "Continuous Improvement",
         "Feed in actuals at project close. The learning engine\n"
         "recalibrates estimates automatically. Each generation\n"
         "of estimates is more accurate than the last.", ORG),
    ]

    uc_cols = 3
    uw = (W - 80 - (uc_cols-1)*12) / uc_cols
    uh = 82
    usy = H - 208

    for i, (icon, title, desc, col) in enumerate(ucases):
        row = i // uc_cols
        ci  = i % uc_cols
        bx  = 40 + ci*(uw+12)
        by  = usy - row*(uh+10) - uh

        rrect(c, bx, by, uw, uh, r=8,
              fill=HexColor("#0f172a"), stroke=Color(col.red,col.green,col.blue,0.25), sw=0.6)
        grad_h(c, bx, by+uh-2, uw, 2, col, Color(col.red*.5,col.green*.5,col.blue*.5))
        c.setFont("Helvetica", 14)
        c.drawString(bx+12, by+uh-24, icon)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(TXT)
        c.drawString(bx+36, by+uh-19, title)
        lines = desc.strip().split("\n")
        c.setFont("Helvetica", 7.5)
        c.setFillColor(DIM)
        for j, l in enumerate(lines[:3]):
            c.drawString(bx+12, by+uh-34-j*11, l.strip())

    # Integrations strip
    section_pill(c, "INTEGRATIONS & EXPORT TARGETS", TEA, usy-2*(uh+10)-uh-26)

    intgs = [
        ("📧", "Email / SMTP",      "Deliver proposals directly\nto client inbox",         BLU),
        ("🗂",  "SharePoint",        "Auto-publish to SharePoint\ndocument libraries",       GLD),
        ("☁",  "Azure Blob",        "Persist all runs to Azure\nBlob Storage",              BLU),
        ("🎞",  "HeyGen / D-ID",    "AI video generation\nfor MP4 narration",              PNK),
        ("🎤", "ElevenLabs TTS",    "Voice synthesis for\naudio narration",                 PUR),
        ("🔍", "Milvus Vector DB",  "Semantic search across\npast proposals",               CYN),
    ]

    iw = (W - 80 - 5*10) / 6
    ih = 62
    isy = usy - 2*(uh+10) - uh - 60

    for i, (icon, title, desc, col) in enumerate(intgs):
        bx = 40 + i*(iw+10)
        by = isy - ih

        rrect(c, bx, by, iw, ih, r=7,
              fill=HexColor("#0f172a"), stroke=Color(col.red,col.green,col.blue,0.2), sw=0.5)
        c.setFont("Helvetica", 12)
        c.drawCentredString(bx+iw/2, by+ih-18, icon)
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(col)
        c.drawCentredString(bx+iw/2, by+ih-30, title)
        lines = desc.strip().split("\n")
        c.setFont("Helvetica", 6.5)
        c.setFillColor(MUT)
        for j, l in enumerate(lines):
            c.drawCentredString(bx+iw/2, by+ih-42-j*10, l.strip())

    page_footer(c, 9)


# ══════════════════════════════════════════════════════════════════════════
#  PAGE 10  —  CTA / CLOSING
# ══════════════════════════════════════════════════════════════════════════

def page_cta(c):
    bg(c)

    c.saveState()
    glow(c, W/2, H/2+60, 300, PUR, 0.07, 9)
    glow(c, W/2, H/2+60, 200, BLU, 0.04, 7)
    glow(c, W*0.1, H*0.1, 180, PNK, 0.03, 5)
    glow(c, W*0.9, H*0.1, 180, CYN, 0.03, 5)
    c.restoreState()

    top_bar(c, PNK, PUR)
    bot_bar(c, PUR, PNK)

    # Logo
    txt(c, "ECI+", 42, H-40, "Helvetica-Bold", 18, TXT)
    txt(c, "  Business Estimation Tool", 80, H-36, "Helvetica-Bold", 10, CYN)

    # Main message
    c.setFont("Helvetica-Bold", 54)
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-185, "Your Next")
    c.setFillColor(CYN)
    c.drawCentredString(W/2, H-247, "Proposal")
    c.setFillColor(TXT)
    c.drawCentredString(W/2, H-309, "Writes Itself.")

    c.setFont("Helvetica", 13)
    c.setFillColor(DIM)
    c.drawCentredString(W/2, H-346, "Upload a scope document. Hit Analyse. Walk into the meeting with")
    c.drawCentredString(W/2, H-364, "a 20-slide deck, a 3D architecture, an Excel model, and an AI presenter video.")

    # CTA button (visual)
    btn_w, btn_h = 270, 50
    btn_x = (W-btn_w)/2
    btn_y = H - 450
    grad_h(c, btn_x, btn_y, btn_w, btn_h, BLU, PUR)
    c.roundRect(btn_x, btn_y, btn_w, btn_h, 12, fill=0, stroke=0)
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(white)
    c.drawCentredString(W/2, btn_y+18, "Request a Live Demo  →")

    # Supporting stats
    stats = [
        ("< 90s", "End-to-End",       CYN),
        ("11",    "AI Agents",         PUR),
        ("9",     "Deliverables",      GLD),
        ("£<1",   "Per Run",           GRN),
        ("<8 hrs", "Time Saved Daily", ORG),
    ]

    sw = (W - 80 - 4*12) / 5
    sh = 70
    sy = btn_y - 98

    for i, (num, lbl, col) in enumerate(stats):
        bx = 40 + i*(sw+12)
        rrect(c, bx, sy-sh, sw, sh, r=8,
              fill=HexColor("#0f172a"), stroke=col, sw=0.6)
        grad_h(c, bx, sy-sh, sw, 2, col, Color(col.red*.5,col.green*.5,col.blue*.5))
        c.saveState()
        glow(c, bx+sw/2, sy-sh/2+4, 20, col, 0.06, 4)
        c.restoreState()
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(col)
        c.drawCentredString(bx+sw/2, sy-sh+34, num)
        c.setFont("Helvetica", 7)
        c.setFillColor(MUT)
        c.drawCentredString(bx+sw/2, sy-sh+18, lbl.upper())

    # Feature summary strip
    strip_y = sy - sh - 24
    c.setFillColor(HexColor("#0f172a"))
    c.roundRect(40, strip_y-28, W-80, 36, 8, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#1e293b"))
    c.setLineWidth(0.5)
    c.roundRect(40, strip_y-28, W-80, 36, 8, fill=0, stroke=1)
    bullets = [
        "11 AI Agents", "15 Result Tabs", "9 Output Formats",
        "5 AI Providers", "3D Visualisation", "AI Video", "Scenario Modelling", "Continuous Learning"
    ]
    bul_w = (W-80)/len(bullets)
    for i, b in enumerate(bullets):
        bx = 40 + i*bul_w
        fc = [CYN,PUR,GLD,GRN,BLU,PNK,ORG,TEA][i]
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(fc)
        c.drawCentredString(bx+bul_w/2, strip_y-10, b)
        if i < len(bullets)-1:
            c.setStrokeColor(HexColor("#1e293b"))
            c.setLineWidth(0.3)
            c.line(bx+bul_w, strip_y-28+6, bx+bul_w, strip_y-28+30)

    # Footer
    c.setFillColor(HexColor("#111827"))
    c.rect(0, 0, W, 44, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(CYN)
    c.drawCentredString(W/2, 26, "ECI Business Estimation Tool  ·  Internal Product  ·  2026")
    c.setFont("Helvetica", 8)
    c.setFillColor(MUT)
    c.drawCentredString(W/2, 12, "11 Agents  ·  9 Formats  ·  5 AI Providers  ·  Under 90 Seconds")


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════

def main():
    cv = canvas.Canvas(OUT, pagesize=A4)
    cv.setTitle("ECI Business Estimation Tool — Stakeholder Pitch")
    cv.setAuthor("ECI Presales Intelligence Platform")
    cv.setSubject("AI-Powered Presales — Boardroom Pitch Deck 2026")
    cv.setKeywords("ECI presales AI estimation proposals automation")

    pages = [
        ("Cover",                page_cover),
        ("The Problem",          page_problem),
        ("Solution Overview",    page_solution),
        ("11 Agents Deep Dive",  page_agents),
        ("15 Result Tabs",       page_results),
        ("Standout Features",    page_features),
        ("Tech Stack",           page_tech),
        ("Comparison & ROI",     page_roi),
        ("Use Cases",            page_usecases),
        ("CTA / Closing",        page_cta),
    ]

    for i, (label, fn) in enumerate(pages):
        print(f"  Page {i+1:>2}/{len(pages)}  {label}...")
        fn(cv)
        cv.showPage()

    cv.save()
    print(f"\n" + "-"*58)
    print(f"  DONE  ->  {OUT}")
    print(f"  Pages : {len(pages)}  |  Format : A4  |  Theme : Dark Premium")
    print("-"*58)


if __name__ == "__main__":
    main()
