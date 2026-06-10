"""
BELAL — Business Estimation Leveraging Automated Learning
Top-Class Sales Deck PDF Generator
Output: marketing/BELAL_Sales_Deck.pdf

Run: python marketing/generate_sales_pdf.py
"""

import os, math
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, Color, white, black
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

W, H = A4  # 595 x 842 pts
OUT = os.path.join(os.path.dirname(__file__), "BELAL_Sales_Deck.pdf")
LOGO = os.path.join(os.path.dirname(__file__), "..", "eci_logo.png")

# ── Palette ──────────────────────────────────────────────────────────────────
BG      = HexColor("#020817")
CARD    = HexColor("#0d1829")
CARD2   = HexColor("#111e33")
BORDER  = HexColor("#1e3a5f")
CYAN    = HexColor("#00d4aa")
BLUE    = HexColor("#00b4d8")
PURPLE  = HexColor("#7b61ff")
GOLD    = HexColor("#ffd166")
GREEN   = HexColor("#22c55e")
RED     = HexColor("#ef4444")
ORANGE  = HexColor("#f59e0b")
TEXT    = HexColor("#e2e8f0")
DIM     = HexColor("#94a3b8")
MUTED   = HexColor("#64748b")
WHITE   = white

# ── Helpers ───────────────────────────────────────────────────────────────────

def bg(c):
    c.setFillColor(BG); c.rect(0, 0, W, H, fill=1, stroke=0)

def grad_rect(c, x, y, w, h, c1, c2, steps=None):
    """Vertical gradient from c1 (top) to c2 (bottom)."""
    n = steps or max(int(h), 1)
    for i in range(n):
        t = i / n
        r = c1.red   + t*(c2.red   - c1.red)
        g = c1.green + t*(c2.green - c1.green)
        b = c1.blue  + t*(c2.blue  - c1.blue)
        c.setFillColor(Color(r, g, b))
        yy = y + h - (i+1)*(h/n)
        c.rect(x, yy, w, h/n + 1, fill=1, stroke=0)

def rr(c, x, y, w, h, r=8, fill=None, stroke=None, sw=0.5):
    """Rounded rectangle."""
    if fill:   c.setFillColor(fill)
    if stroke: c.setStrokeColor(stroke); c.setLineWidth(sw)
    p = c.beginPath()
    p.moveTo(x+r, y); p.lineTo(x+w-r, y)
    p.arcTo(x+w-2*r, y, x+w, y+2*r, 270, 90)
    p.lineTo(x+w, y+h-r)
    p.arcTo(x+w-2*r, y+h-2*r, x+w, y+h, 0, 90)
    p.lineTo(x+r, y+h)
    p.arcTo(x, y+h-2*r, x+2*r, y+h, 90, 90)
    p.lineTo(x, y+r)
    p.arcTo(x, y, x+2*r, y+2*r, 180, 90)
    p.close()
    c.drawPath(p, fill=1 if fill else 0, stroke=1 if stroke else 0)

def glow(c, cx, cy, r, col, layers=5, alpha=0.07):
    for i in range(layers, 0, -1):
        c.setFillColor(col); c.setFillAlpha(alpha*(i/layers))
        c.circle(cx, cy, r*i*0.55, fill=1, stroke=0)
    c.setFillAlpha(1)

def dot_grid(c, x, y, w, h):
    c.setFillColor(HexColor("#ffffff")); c.setFillAlpha(0.025)
    sz = 22
    for row in range(int(h/sz)+2):
        for col in range(int(w/sz)+2):
            c.circle(x+col*sz, y+row*sz, 1.2, fill=1, stroke=0)
    c.setFillAlpha(1)

def txt(c, text, x, y, font="Helvetica-Bold", size=12, color=TEXT):
    c.setFont(font, size); c.setFillColor(color); c.drawString(x, y, text)

def txtr(c, text, x, y, font="Helvetica-Bold", size=12, color=TEXT):
    c.setFont(font, size); c.setFillColor(color); c.drawRightString(x, y, text)

def txtc(c, text, cx, y, font="Helvetica-Bold", size=12, color=TEXT):
    c.setFont(font, size); c.setFillColor(color); c.drawCentredString(cx, y, text)

def line(c, x1, y1, x2, y2, color=BORDER, w=0.5):
    c.setStrokeColor(color); c.setLineWidth(w); c.line(x1, y1, x2, y2)

def badge(c, x, y, text, bg_col, fg_col=WHITE, r=4):
    """Small colored pill badge."""
    c.setFont("Helvetica-Bold", 7)
    tw = c.stringWidth(text, "Helvetica-Bold", 7)
    pw, ph = tw + 14, 14
    rr(c, x, y, pw, ph, r=r, fill=bg_col)
    c.setFillColor(fg_col); c.drawString(x+7, y+4, text)

def page_header(c, label="", accent=CYAN):
    """Thin branded top bar."""
    c.setFillColor(CARD); c.rect(0, H-28, W, 28, fill=1, stroke=0)
    c.setFillColor(accent); c.rect(0, H-28, 3, 28, fill=1, stroke=0)
    if label:
        txt(c, "BELAL  ·  " + label, 14, H-18, "Helvetica-Bold", 7.5, MUTED)
    txtr(c, "belal.eci.com", W-14, H-18, "Helvetica", 7, MUTED)

def page_footer(c, num, total):
    c.setFillColor(CARD); c.rect(0, 0, W, 22, fill=1, stroke=0)
    c.setFillColor(CYAN); c.rect(0, 0, W*num/total, 2, fill=1, stroke=0)
    txt(c, "© 2026 ECI  ·  Confidential  ·  Not for distribution", 14, 7, "Helvetica", 7, MUTED)
    txtr(c, f"{num} / {total}", W-14, 7, "Helvetica-Bold", 7, DIM)

def wrap_text(c, text, x, y, max_w, font, size, color, leading=None):
    """Simple word-wrap. Returns final y."""
    lead = leading or size * 1.4
    c.setFont(font, size); c.setFillColor(color)
    words = text.split()
    line_text = ""
    for word in words:
        test = (line_text + " " + word).strip()
        if c.stringWidth(test, font, size) <= max_w:
            line_text = test
        else:
            if line_text:
                c.drawString(x, y, line_text); y -= lead
            line_text = word
    if line_text:
        c.drawString(x, y, line_text); y -= lead
    return y

def section_title(c, text, x, y, accent=CYAN, sub=None):
    """Draws a section header with accent underline."""
    c.setFont("Helvetica-Bold", 18); c.setFillColor(accent)
    c.drawString(x, y, text)
    tw = c.stringWidth(text, "Helvetica-Bold", 18)
    c.setFillColor(accent); c.setFillAlpha(0.35)
    c.rect(x, y-4, tw, 2, fill=1, stroke=0); c.setFillAlpha(1)
    if sub:
        txt(c, sub, x, y-18, "Helvetica", 9, DIM)
        return y - 40
    return y - 28

def feature_card(c, x, y, w, h, icon, title, desc, accent=CYAN):
    """Draw a single feature card."""
    rr(c, x, y, w, h, r=8, fill=CARD, stroke=BORDER, sw=0.5)
    c.setFillColor(accent); c.setFillAlpha(0.12)
    rr(c, x, y+h-28, w, 28, r=8, fill=accent)
    c.setFillAlpha(1)
    # top accent strip
    c.setFillColor(accent); c.rect(x, y+h-3, w, 3, fill=1, stroke=0)
    txt(c, icon + "  " + title, x+10, y+h-19, "Helvetica-Bold", 9, WHITE)
    wrap_text(c, desc, x+10, y+h-36, w-20, "Helvetica", 8, DIM, leading=12)

def pricing_card(c, x, y, w, h, tier, price, period, features, accent,
                 popular=False, cta="Get Started"):
    """Draw a pricing tier card."""
    rr(c, x, y, w, h, r=10, fill=CARD, stroke=accent if popular else BORDER, sw=1.5 if popular else 0.5)
    # Top accent gradient
    grad_rect(c, x, y+h-60, w, 60,
              Color(accent.red, accent.green, accent.blue, 1),
              Color(CARD.red, CARD.green, CARD.blue, 1))
    rr(c, x, y+h-60, w, 60, r=10, fill=None, stroke=None)
    if popular:
        badge(c, x + w/2 - 28, y+h+2, "★  MOST POPULAR", GOLD, BG)
    txtr(c, tier, x+w-14, y+h-20, "Helvetica-Bold", 11, WHITE)
    txtr(c, price, x+w-14, y+h-38, "Helvetica-Bold", 18, WHITE)
    txtr(c, period, x+w-14, y+h-52, "Helvetica", 7.5, HexColor("#e2e8f0"))
    # Divider
    line(c, x+10, y+h-65, x+w-10, y+h-65, BORDER, 0.5)
    fy = y+h-80
    for feat in features:
        c.setFillColor(accent); c.circle(x+18, fy+4, 2.5, fill=1, stroke=0)
        txt(c, feat, x+28, fy, "Helvetica", 7.5, TEXT)
        fy -= 14
    # CTA button
    btn_y = y + 18
    rr(c, x+14, btn_y, w-28, 22, r=6, fill=accent)
    txtc(c, cta, x+w/2, btn_y+7, "Helvetica-Bold", 8.5, BG)

# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — COVER
# ═══════════════════════════════════════════════════════════════════════════════

def page_cover(c):
    bg(c)
    # Gradient overlay
    grad_rect(c, 0, H//2, W, H//2,
              Color(0.02, 0.05, 0.14), Color(0.008, 0.031, 0.09))
    dot_grid(c, 0, 0, W, H)

    # Glowing orbs
    glow(c, -40, H+20, 180, CYAN, layers=6, alpha=0.09)
    glow(c, W+40, H//3, 200, PURPLE, layers=6, alpha=0.07)
    glow(c, W//2, 60, 140, BLUE, layers=5, alpha=0.06)

    # Top brand bar
    c.setFillColor(HexColor("#0a1628")); c.rect(0, H-50, W, 50, fill=1, stroke=0)
    c.setFillColor(CYAN); c.rect(0, H-50, 4, 50, fill=1, stroke=0)

    # ECI Logo
    if os.path.exists(LOGO):
        try:
            c.drawImage(LOGO, 16, H-46, width=80, height=38,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            txt(c, "ECI", 16, H-34, "Helvetica-Bold", 18, CYAN)
    else:
        txt(c, "ECI", 16, H-34, "Helvetica-Bold", 18, CYAN)

    txt(c, "SALES DECK  ·  2026  ·  CONFIDENTIAL", W-14, H-32,
        "Helvetica", 7.5, MUTED)
    c.setFillColor(MUTED)
    c.drawRightString(W-14, H-32, "SALES DECK  ·  2026  ·  CONFIDENTIAL")

    # Central hero
    mid = W / 2

    # Subtitle over-title
    txtc(c, "INTRODUCING", mid, H-115, "Helvetica", 9, MUTED)

    # BELAL big name — letter-spaced simulation
    c.setFont("Helvetica-Bold", 68); c.setFillColor(CYAN)
    c.drawCentredString(mid, H-175, "BELAL")

    # Glow under BELAL
    glow(c, mid, H-170, 140, CYAN, layers=4, alpha=0.05)

    # Tagline
    txtc(c, "Business Estimation Leveraging Automated Learning",
         mid, H-200, "Helvetica", 12.5, TEXT)

    # Cyan divider
    c.setFillColor(CYAN); c.rect(mid-80, H-215, 160, 1.5, fill=1, stroke=0)

    # Sub-tagline
    txtc(c, "AI-Powered Presales Intelligence Platform by ECI",
         mid, H-232, "Helvetica-Bold", 10, BLUE)

    # Hero stat row
    stats = [
        ("90 sec", "Proposal Generated"),
        ("11", "AI Agents in Parallel"),
        ("9", "Professional Formats"),
        ("5+", "AI Providers"),
    ]
    sx = 60; sw = (W - 120) / len(stats)
    for i, (val, lbl) in enumerate(stats):
        cx = sx + i*sw + sw/2
        rr(c, sx+i*sw+8, H-330, sw-16, 72, r=10,
           fill=HexColor("#0d1829"), stroke=BORDER, sw=0.5)
        txtc(c, val, cx, H-280, "Helvetica-Bold", 26, CYAN)
        txtc(c, lbl, cx, H-300, "Helvetica", 7.5, DIM)

    # Quote strip
    c.setFillColor(HexColor("#0a1628")); c.rect(0, H-390, W, 46, fill=1, stroke=0)
    c.setFillColor(CYAN); c.rect(0, H-390, 3, 46, fill=1, stroke=0)
    txtc(c, '"From Scope Document to Boardroom-Ready Proposal — in Under 90 Seconds"',
         mid, H-360, "Helvetica-Bold", 11, TEXT)
    txtc(c, "No more days of manual writing. No more inconsistent estimates. One button. Complete package.",
         mid, H-376, "Helvetica", 8.5, DIM)

    # What's inside list
    txtc(c, "WHAT'S INSIDE THIS DECK", mid, H-430, "Helvetica-Bold", 9, MUTED)
    items = [
        "The Problem We Solve",
        "How BELAL Works",
        "Key Features",
        "Pricing Packages",
        "ROI Proof & Comparison",
        "How to Get Started",
    ]
    col_w = 200
    for i, item in enumerate(items):
        col = i % 2; row = i // 2
        ix = mid - col_w + col*col_w*1.1
        iy = H-452 - row*18
        c.setFillColor(CYAN); c.circle(ix, iy+5, 3, fill=1, stroke=0)
        txt(c, item, ix+12, iy, "Helvetica", 9, TEXT)

    # Bottom
    c.setFillColor(CARD); c.rect(0, 0, W, 38, fill=1, stroke=0)
    c.setFillColor(CYAN); c.rect(0, 36, W, 2, fill=1, stroke=0)
    txtc(c, "belal.eci.com  ·  contact@eci.com  ·  +44 (0) 20 XXXX XXXX",
         mid, 14, "Helvetica", 8, DIM)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — THE PROBLEM
# ═══════════════════════════════════════════════════════════════════════════════

def page_problem(c):
    bg(c); dot_grid(c, 0, 0, W, H)
    page_header(c, "THE PROBLEM", RED)

    glow(c, W, H-100, 160, RED, alpha=0.05)

    cy = H - 65
    cy = section_title(c, "Why Presales Teams Are Struggling", 36, cy,
                        accent=RED,
                        sub="Manual proposal writing is costing your business more than you think")

    # Big pain stat
    txtc(c, "£3,000", W/2, cy-10, "Helvetica-Bold", 42, RED)
    txtc(c, "average senior consultant cost per manually written proposal",
         W/2, cy-32, "Helvetica", 9, DIM)
    txtc(c, "That's before accounting for delays, rework, and deals lost to faster competitors.",
         W/2, cy-48, "Helvetica", 8.5, MUTED)
    cy -= 70

    pain_points = [
        ("⏳", RED,    "15–40 Hours Per Proposal",
         "Your best consultants spend entire working weeks formatting spreadsheets instead of winning deals. "
         "A single enterprise proposal consumes 3–5 days of senior time — every single time."),
        ("📉", ORANGE, "Inconsistent Estimates",
         "Two consultants, same project — 30% different estimates. Clients notice. "
         "Inconsistency destroys credibility and makes negotiation unpredictable."),
        ("🔍", GOLD,   "Generic Templates Clients See Through",
         "Clients receive proposals that feel copy-pasted. No specificity, no insight. "
         "They can tell you didn't read their document carefully — because you couldn't."),
        ("⚡", PURPLE, "Slow Turnaround Loses Deals",
         "Your competitor submits in 24 hours. You take 5 days. In presales, speed signals capability. "
         "Slow proposals lose deals before the meeting even happens."),
        ("🧠", BLUE,   "Tribal Knowledge Is Never Captured",
         "Your most experienced consultant retires and takes all institutional estimation knowledge with them. "
         "Every new hire starts from zero. The same mistakes get repeated."),
    ]

    for icon, accent, title, desc in pain_points:
        rr(c, 36, cy-58, W-72, 62, r=8, fill=CARD, stroke=accent, sw=0.8)
        c.setFillColor(accent); c.setFillAlpha(0.08)
        rr(c, 36, cy-58, W-72, 62, r=8, fill=accent)
        c.setFillAlpha(1)
        c.setFillColor(accent); c.rect(36, cy-58, 4, 62, fill=1, stroke=0)
        txt(c, icon + "  " + title, 52, cy-18, "Helvetica-Bold", 10.5, WHITE)
        wrap_text(c, desc, 52, cy-34, W-100, "Helvetica", 8.5, DIM, leading=12)
        cy -= 74

    page_footer(c, 2, 11)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 3 — THE SOLUTION
# ═══════════════════════════════════════════════════════════════════════════════

def page_solution(c):
    bg(c); dot_grid(c, 0, 0, W, H)
    page_header(c, "THE SOLUTION", CYAN)
    glow(c, 0, H//2, 180, CYAN, alpha=0.06)
    glow(c, W, H//3, 160, PURPLE, alpha=0.05)

    cy = H - 65
    cy = section_title(c, "Introducing BELAL", 36, cy, accent=CYAN,
                        sub="One platform. Eleven AI specialists. Complete proposal in 90 seconds.")

    # Flow diagram: INPUT → INTELLIGENCE → OUTPUT
    box_y = cy - 20
    box_h = 130
    bw = (W - 100) / 3

    boxes = [
        (BLUE,   "📥  INPUT",  ["Upload any document",
                                 "PDF, DOCX, XLSX, TXT",
                                 "Images, CSV, SharePoint",
                                 "Or paste text directly"]),
        (CYAN,   "🧠  INTELLIGENCE", ["11 AI Agents fire in parallel",
                                       "Requirements Analysis",
                                       "Cost & Time Estimation",
                                       "Risk, Architecture, SOW"]),
        (GREEN,  "📦  OUTPUT", ["9 professional formats",
                                  "Excel · PDF · PowerPoint",
                                  "Word · JSON · ZIP",
                                  "In under 90 seconds"]),
    ]
    for i, (accent, title, items) in enumerate(boxes):
        bx = 36 + i * (bw + 14)
        rr(c, bx, box_y - box_h, bw, box_h, r=10,
           fill=CARD, stroke=accent, sw=1)
        c.setFillColor(accent); c.setFillAlpha(0.1)
        rr(c, bx, box_y-box_h, bw, box_h, r=10, fill=accent)
        c.setFillAlpha(1)
        c.setFillColor(accent); c.rect(bx, box_y-box_h, bw, 3, fill=1, stroke=0)
        txt(c, title, bx+12, box_y-18, "Helvetica-Bold", 10, WHITE)
        for j, it in enumerate(items):
            txt(c, "·  " + it, bx+12, box_y-36-j*16, "Helvetica", 8, DIM)
        if i < 2:
            txtc(c, "→", bx+bw+7, box_y-box_h/2-8, "Helvetica-Bold", 18, MUTED)

    cy = box_y - box_h - 24

    # 90 second hero
    c.setFillColor(CARD2); c.rect(36, cy-48, W-72, 52, fill=1, stroke=0)
    c.setFillColor(CYAN); c.rect(36, cy-48, 4, 52, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 28); c.setFillColor(CYAN)
    c.drawString(56, cy-18, "90 Seconds.")
    c.setFont("Helvetica-Bold", 12); c.setFillColor(TEXT)
    c.drawString(218, cy-18, "That's all it takes to go from blank scope to boardroom-ready package.")
    txt(c, "Compare that to 15–40 hours of manual writing. BELAL pays for itself on the very first proposal.", 56, cy-36, "Helvetica", 8.5, DIM)
    cy -= 72

    # 11 agents grid
    cy = section_title(c, "11 Specialised AI Agents", 36, cy, accent=PURPLE,
                        sub="Not one general AI — eleven purpose-built specialists working simultaneously")

    agents = [
        ("01", CYAN,   "Requirements Analyst",    "Structures every requirement from unstructured docs"),
        ("02", BLUE,   "Cost Estimator",           "Phase-by-phase cost models with contingency buffers"),
        ("03", PURPLE, "Time Planner",             "Realistic timelines with milestone dependencies"),
        ("04", RED,    "Risk Analyst",             "Identifies & scores 10–20 risks with mitigations"),
        ("05", GOLD,   "Architecture Designer",    "Recommends tech stack & Azure service specifics"),
        ("06", GREEN,  "Team Composer",            "Optimal team structure and seniority mix"),
        ("07", ORANGE, "SOW Generator",            "Legally-structured Statement of Work"),
        ("08", BLUE,   "Discovery Engine",         "Prioritised question sets per scope gap"),
        ("09", CYAN,   "Infrastructure Pricer",    "Live Azure Retail Prices — real numbers, not guesses"),
        ("10", PURPLE, "Completeness Checker",     "Identifies critical gaps before you submit"),
        ("11", GOLD,   "Proposal Writer",          "Assembles everything into a client-ready narrative"),
    ]

    cols = 2; aw = (W - 90) / cols
    for i, (num, accent, name, desc) in enumerate(agents):
        col = i % cols; row = i // cols
        ax = 36 + col*(aw+18)
        ay = cy - row*30
        c.setFillColor(accent); c.setFillAlpha(0.12)
        rr(c, ax, ay-22, aw, 24, r=5, fill=accent)
        c.setFillAlpha(1)
        c.setFillColor(accent); c.setFont("Helvetica-Bold", 7.5)
        c.drawString(ax+8, ay-12, f"AGENT {num}")
        c.setFont("Helvetica-Bold", 8.5); c.setFillColor(WHITE)
        c.drawString(ax+62, ay-12, name)
        c.setFont("Helvetica", 7.5); c.setFillColor(DIM)
        tw = c.stringWidth(name, "Helvetica-Bold", 8.5) + 70
        c.drawString(ax+tw+8, ay-12, "—  " + desc)

    page_footer(c, 3, 11)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 4 — KEY FEATURES (Part 1)
# ═══════════════════════════════════════════════════════════════════════════════

def page_features_1(c):
    bg(c); dot_grid(c, 0, 0, W, H)
    page_header(c, "KEY FEATURES", CYAN)

    cy = H - 65
    cy = section_title(c, "Everything Your Presales Team Needs", 36, cy, accent=CYAN,
                        sub="Every feature built for one purpose — winning more deals, faster")

    features = [
        (CYAN,   "⚡  Real-Time Scenario Modelling",
         "Client asks 'what if we cut scope by 25%?' Answer it in the room, in real-time. "
         "Drag sliders to adjust scope complexity (0.5×–2.5×), team size, pricing model. "
         "Up to 3 scenarios simultaneously. Export comparison Excel to hand to the client. "
         "Brooks' Law applied automatically — no naive headcount math."),
        (BLUE,   "💰  Live Azure Infrastructure Pricing",
         "Fetches real prices from the Azure Retail Prices API every time you run. "
         "Architecture recommendations automatically feed the pricing engine. "
         "Actual 2025 list prices for every recommended service. "
         "Static fallback catalog if API temporarily unavailable. CFO-defensible numbers."),
        (PURPLE, "🌐  3D Architecture Viewer",
         "Technical diagrams in Word documents are forgettable. A 3D fly-through is not. "
         "Your Azure architecture renders as an interactive 3D graph — rotate, zoom, pan. "
         "Click any service node to see its purpose, SKU, and monthly cost. "
         "Built on Three.js — runs in any browser, no plugins required."),
        (GOLD,   "🎬  AI Video Narrator",
         "Your proposal now comes with its own presenter. Integrate with HeyGen, D-ID, or ElevenLabs "
         "to generate an AI avatar that narrates the executive summary. "
         "Send the video before meetings — clients understand the proposal before you even connect. "
         "Download as MP4 to attach to emails or embed in SharePoint."),
        (GREEN,  "💬  AI Chat — Your Proposal Knows Itself",
         "After generating, ask anything: 'Why is the risk score High?' "
         "'Explain the architecture to a non-technical client.' 'Draft our follow-up email.' "
         "Full context of your specific proposal — not generic answers. "
         "Rooted in your actual scope, team, costs, risks, and requirements."),
        (RED,    "✅  Scope Completeness Checker",
         "Before you see results, the Completeness Checker reviews your scope document "
         "and flags: requirements clearly defined, partially covered, or critically missing. "
         "Prevents the most common proposal failure: submitting a detailed proposal "
         "that misunderstands what the client actually wants."),
    ]

    cw = (W - 90) / 2; ch = 112
    for i, (accent, title, desc) in enumerate(features):
        col = i % 2; row = i // 2
        fx = 36 + col*(cw+18)
        fy = cy - row*(ch+12) - ch
        rr(c, fx, fy, cw, ch, r=8, fill=CARD, stroke=accent, sw=0.6)
        c.setFillColor(accent); c.setFillAlpha(0.07)
        rr(c, fx, fy, cw, ch, r=8, fill=accent)
        c.setFillAlpha(1)
        c.setFillColor(accent); c.rect(fx, fy+ch-3, cw, 3, fill=1, stroke=0)
        txt(c, title, fx+11, fy+ch-19, "Helvetica-Bold", 9.5, WHITE)
        wrap_text(c, desc, fx+11, fy+ch-35, cw-22, "Helvetica", 7.5, DIM, leading=11.5)

    page_footer(c, 4, 11)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 5 — KEY FEATURES (Part 2)
# ═══════════════════════════════════════════════════════════════════════════════

def page_features_2(c):
    bg(c); dot_grid(c, 0, 0, W, H)
    page_header(c, "KEY FEATURES", PURPLE)

    cy = H - 65
    cy = section_title(c, "More Features That Set BELAL Apart", 36, cy, accent=PURPLE,
                        sub="Built for teams that demand efficiency, accuracy, and speed")

    features2 = [
        (PURPLE, "🧠  Continuous Learning Engine",
         "Records actual hours/costs after delivery. Calculates variance per technology. "
         "Derives correction factors automatically. Future estimates improve with every project. "
         "The accuracy improvement is measurable, visible in Admin Dashboard — not a marketing claim."),
        (BLUE,   "🗂️  Run Library — Never Lose an Estimate",
         "Every run auto-saved to persistent database. Full searchable history. "
         "Architect review gate — mark proposals approved before sending. "
         "Compare any two runs side-by-side. Outcome tracking for Won/Lost/Delivered."),
        (CYAN,   "🔗  SharePoint & Email Integration",
         "Publish proposals directly to SharePoint. Email outputs to clients in one click. "
         "Integrates with your existing Microsoft 365 environment via Azure AD app registration. "
         "No copy-paste, no attachment management. Seamless enterprise workflow."),
        (GREEN,  "🤖  Multi-Model AI — No Vendor Lock-In",
         "Works with Azure OpenAI (GPT-4o), Claude (Opus/Sonnet/Haiku), "
         "Google Gemini, Qwen (DashScope + Foundry), and Vertex AI. "
         "Switch with one click. Use your existing Azure agreement. "
         "Your fine-tuned custom model? It works here too."),
        (GOLD,   "⌨️  Command Palette  (Ctrl+K)",
         "Press Ctrl+K and type what you want. Navigate, download, test connections, clear chat — "
         "all without touching the mouse. Built for power users who live in the tool daily. "
         "Every common action is one keystroke away."),
        (ORANGE, "🔔  Smart Notification System",
         "In-app notification bell keeps teams aligned. 'Run #47 saved', 'Reviewed by Prabhakar', "
         "'Export ready', 'Pipeline complete' — know what's happening without pinging colleagues. "
         "Designed for multi-user team environments."),
    ]

    cw = (W - 90) / 2; ch = 110
    for i, (accent, title, desc) in enumerate(features2):
        col = i % 2; row = i // 2
        fx = 36 + col*(cw+18)
        fy = cy - row*(ch+12) - ch
        rr(c, fx, fy, cw, ch, r=8, fill=CARD, stroke=accent, sw=0.6)
        c.setFillColor(accent); c.setFillAlpha(0.07)
        rr(c, fx, fy, cw, ch, r=8, fill=accent)
        c.setFillAlpha(1)
        c.setFillColor(accent); c.rect(fx, fy+ch-3, cw, 3, fill=1, stroke=0)
        txt(c, title, fx+11, fy+ch-19, "Helvetica-Bold", 9.5, WHITE)
        wrap_text(c, desc, fx+11, fy+ch-35, cw-22, "Helvetica", 7.5, DIM, leading=11.5)

    page_footer(c, 5, 11)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 6 — 9 OUTPUT FORMATS
# ═══════════════════════════════════════════════════════════════════════════════

def page_outputs(c):
    bg(c); dot_grid(c, 0, 0, W, H)
    page_header(c, "OUTPUTS", GREEN)

    cy = H - 65
    cy = section_title(c, "9 Professional Formats. One Click.", 36, cy, accent=GREEN,
                        sub="Every run delivers a complete package — ready to share, present, and sign")

    outputs = [
        (CYAN,   "📊", "Excel Workbook",      "5-tab workbook: Cost Breakdown, Timeline, Risk Register, Infrastructure Costs, Summary Dashboard"),
        (RED,    "📄", "Branded PDF Proposal","Cover page + all sections in ECI formatting. Client-ready on delivery."),
        (PURPLE, "📊", "PowerPoint Deck",     "Presentation-ready slides. Drop straight into your client meeting."),
        (BLUE,   "📝", "Statement of Work",   ".docx format. Milestone payments, acceptance criteria, legally structured."),
        (GOLD,   "❓", "Discovery Prep Deck", "Prioritised question sets per scope gap. Never go into a discovery call unprepared."),
        (GREEN,  "🔀", "Scenario Comparison", "What-if analysis side-by-side in Excel. Hand to the client in the negotiation room."),
        (ORANGE, "🔗", "JSON Export",         "API-ready structured data. Feed into your CRM, BI tool, or custom application."),
        (MUTED,  "📦", "ZIP Bundle",          "Everything in one archive. One download, send to anyone."),
        (CYAN,   "🎬", "Video Narration",     "AI avatar narrates your executive summary. MP4 download. Send before the meeting."),
    ]

    ow = (W - 96) / 3; oh = 90
    for i, (accent, icon, title, desc) in enumerate(outputs):
        col = i % 3; row = i // 3
        ox = 36 + col*(ow+12)
        oy = cy - row*(oh+10) - oh
        rr(c, ox, oy, ow, oh, r=8, fill=CARD, stroke=accent, sw=0.5)
        c.setFillColor(accent); c.setFillAlpha(0.08)
        rr(c, ox, oy, ow, oh, r=8, fill=accent); c.setFillAlpha(1)
        c.setFillColor(accent); c.rect(ox, oy+oh-3, ow, 3, fill=1, stroke=0)
        txt(c, icon + "  " + title, ox+10, oy+oh-18, "Helvetica-Bold", 9, WHITE)
        wrap_text(c, desc, ox+10, oy+oh-32, ow-20, "Helvetica", 7.5, DIM, leading=11)

    # Bottom note
    note_y = cy - 3*(oh+10) - oh - 20
    rr(c, 36, note_y-28, W-72, 32, r=6, fill=HexColor("#0a1628"), stroke=CYAN, sw=0.5)
    c.setFillColor(CYAN); c.rect(36, note_y-28, 3, 32, fill=1, stroke=0)
    txt(c, "⚡  All 9 formats generated automatically in a single pipeline run. No additional steps required.", 52, note_y-10, "Helvetica-Bold", 9, TEXT)
    txt(c, "Run time: typically under 90 seconds on GPT-4o or Claude Sonnet with standard document complexity.", 52, note_y-22, "Helvetica", 8, DIM)

    page_footer(c, 6, 11)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 7 — PRICING PACKAGES
# ═══════════════════════════════════════════════════════════════════════════════

def page_pricing(c):
    bg(c)
    glow(c, W/2, H/2, 300, CYAN, layers=6, alpha=0.03)
    dot_grid(c, 0, 0, W, H)
    page_header(c, "PRICING & PACKAGES", GOLD)

    cy = H - 65
    cy = section_title(c, "Choose the Plan That Fits Your Team", 36, cy, accent=GOLD,
                        sub="All plans include core AI pipeline · Cancel any time · Free migration support")

    packages = [
        {
            "tier": "TRIAL",
            "price": "FREE",
            "period": "7 days · no credit card",
            "accent": BLUE,
            "popular": False,
            "cta": "Start Free Trial",
            "features": [
                "10 estimation runs",
                "PDF + Excel outputs",
                "1 AI provider (Azure)",
                "Core pipeline (8 agents)",
                "Run Library (7 days)",
                "Email support",
                "Community onboarding",
            ]
        },
        {
            "tier": "STARTER",
            "price": "£299",
            "period": "per month · billed monthly",
            "accent": CYAN,
            "popular": False,
            "cta": "Get Started",
            "features": [
                "100 runs / month",
                "All 9 output formats",
                "3 AI providers",
                "Scenario modelling",
                "Full Run Library",
                "Completeness Checker",
                "Chat + email support",
                "Up to 3 users",
            ]
        },
        {
            "tier": "PROFESSIONAL",
            "price": "£999",
            "period": "per month · billed monthly",
            "accent": PURPLE,
            "popular": True,
            "cta": "Talk to Sales",
            "features": [
                "Unlimited runs",
                "All 9 output formats",
                "All 5 AI providers",
                "3D Architecture Viewer",
                "Video Narrator (HeyGen/D-ID)",
                "AI Chat (full context)",
                "SharePoint integration",
                "Scenario modelling (3x)",
                "Continuous Learning Engine",
                "Priority support · SLA",
                "Up to 15 users",
            ]
        },
        {
            "tier": "ENTERPRISE",
            "price": "Custom",
            "period": "contact us for pricing",
            "accent": GOLD,
            "popular": False,
            "cta": "Contact Sales",
            "features": [
                "Everything in Professional",
                "On-premises deployment",
                "Azure Container Apps",
                "Microsoft SSO / SAML",
                "Custom AI fine-tuning",
                "White-labelling",
                "Dedicated CSM",
                "Custom SLA",
                "Unlimited users",
                "API access (REST)",
            ]
        },
    ]

    pw = (W - 96) / 4; ph = 310
    card_y = cy - ph - 22
    for i, pkg in enumerate(packages):
        px = 36 + i*(pw+12)
        pricing_card(c, px, card_y, pw, ph,
                     tier=pkg["tier"],
                     price=pkg["price"],
                     period=pkg["period"],
                     features=pkg["features"],
                     accent=pkg["accent"],
                     popular=pkg["popular"],
                     cta=pkg["cta"])

    # API cost note
    note_y = card_y - 24
    rr(c, 36, note_y-28, W-72, 32, r=6, fill=CARD2, stroke=BORDER, sw=0.5)
    c.setFillColor(CYAN); c.rect(36, note_y-28, 3, 32, fill=1, stroke=0)
    txt(c, "💡  AI API Cost Note:", 52, note_y-10, "Helvetica-Bold", 8.5, CYAN)
    txt(c, "Each estimation run costs approximately £0.10–£0.50 in AI API fees (GPT-4o / Claude Sonnet). "
        "For teams with existing Azure OpenAI agreements, the incremental cost is negligible.",
        148, note_y-10, "Helvetica", 8, DIM)
    txt(c, "Compare to: senior consultant time for manual proposal = £800–£3,000. "
        "External proposal tools = £200–£500/user/month. BELAL API cost = under £1 per proposal.",
        52, note_y-22, "Helvetica", 7.5, MUTED)

    page_footer(c, 7, 11)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 8 — ROI & PROOF
# ═══════════════════════════════════════════════════════════════════════════════

def page_roi(c):
    bg(c); dot_grid(c, 0, 0, W, H)
    page_header(c, "ROI & PROOF", GREEN)
    glow(c, 0, H/2, 160, GREEN, alpha=0.05)

    cy = H - 65
    cy = section_title(c, "The Return on Investment Is Arithmetically Certain", 36, cy,
                        accent=GREEN, sub="Not a projection. Not an estimate. Pure arithmetic.")

    # ROI comparison table
    rows = [
        ("Metric",               "Manual Process",    "Generic AI Tool",     "BELAL",          True),
        ("Time per proposal",    "15–40 hours",       "2–4 hours",           "90 seconds",     False),
        ("Cost per proposal",    "£800–£3,000",       "£200–£500/user/mo",   "Under £1",       False),
        ("Consistency",          "Low — varies by consultant", "Medium",     "High — ±8%",     False),
        ("Proposals per day",    "0.3–0.7",           "2–3",                 "50+",            False),
        ("Live pricing",         "Manual lookup",     "None",                "Azure API live", False),
        ("Risk identification",  "Ad hoc",            "Basic",               "Scored register",False),
        ("Scenario modelling",   "Hours of rework",   "None",                "Real-time, 3×",  False),
        ("Formats generated",    "1–2",               "1–2",                 "9 formats",      False),
        ("Learns from outcomes", "Tribal knowledge",  "None",                "Automated",      False),
    ]

    tw = W - 72; tx = 36
    col_w = [tw*0.28, tw*0.22, tw*0.22, tw*0.28]
    row_h = 20

    for ri, row in enumerate(rows):
        ry = cy - ri*row_h - row_h
        is_header = row[4]
        bg_col = HexColor("#0a1628") if is_header else (CARD if ri%2==0 else CARD2)
        c.setFillColor(bg_col); c.rect(tx, ry, tw, row_h, fill=1, stroke=0)
        xo = tx
        for ci, (cell, cw) in enumerate(zip(row[:4], col_w)):
            if is_header:
                txt(c, cell, xo+6, ry+6, "Helvetica-Bold", 8.5, CYAN)
            elif ci == 3:  # BELAL column — highlight
                c.setFillColor(GREEN); c.setFillAlpha(0.08)
                c.rect(xo, ry, cw, row_h, fill=1, stroke=0); c.setFillAlpha(1)
                txt(c, "✓  " + cell, xo+6, ry+6, "Helvetica-Bold", 8, GREEN)
            elif ci == 1:
                txt(c, cell, xo+6, ry+6, "Helvetica", 8, RED)
            else:
                txt(c, cell, xo+6, ry+6, "Helvetica", 8, DIM)
            # Vertical separator
            c.setStrokeColor(BORDER); c.setLineWidth(0.3)
            c.line(xo+cw, ry, xo+cw, ry+row_h)
            xo += cw

    # Bottom ROI cards
    roi_y = cy - len(rows)*row_h - 30
    roi_stats = [
        (GREEN,  "70%",  "Reduction in\npresales effort"),
        (CYAN,   "±8%",  "Estimate consistency\nacross consultants"),
        (GOLD,   "50×",  "More proposals\nper day possible"),
        (PURPLE, "3000×","ROI on day one\nvs manual writing"),
    ]
    rsw = (W - 90) / 4
    for i, (accent, val, lbl) in enumerate(roi_stats):
        rx = 36 + i*(rsw+12)
        rr(c, rx, roi_y-54, rsw, 58, r=8, fill=CARD, stroke=accent, sw=0.6)
        c.setFillColor(accent); c.setFillAlpha(0.1)
        rr(c, rx, roi_y-54, rsw, 58, r=8, fill=accent); c.setFillAlpha(1)
        txtc(c, val, rx+rsw/2, roi_y-22, "Helvetica-Bold", 20, accent)
        for j, part in enumerate(lbl.split("\n")):
            txtc(c, part, rx+rsw/2, roi_y-38-j*12, "Helvetica", 7.5, DIM)

    page_footer(c, 8, 11)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 9 — USE CASES & TESTIMONIALS
# ═══════════════════════════════════════════════════════════════════════════════

def page_usecases(c):
    bg(c); dot_grid(c, 0, 0, W, H)
    page_header(c, "USE CASES & TESTIMONIALS", BLUE)

    cy = H - 65
    cy = section_title(c, "Who Benefits From BELAL", 36, cy, accent=BLUE,
                        sub="Purpose-built for every role in the presales and delivery cycle")

    use_cases = [
        (CYAN,   "👔  Presales Consultants",
         "Stop spending evenings writing proposals. Upload at 5pm Friday. "
         "Complete reviewed package ready for Monday — before you close your laptop."),
        (PURPLE, "📋  Presales Managers",
         "Every consultant produces the same calibre as your best performer. "
         "Architect gate ensures quality. Review pipeline streamlined end-to-end."),
        (BLUE,   "🏗️  Solution Architects",
         "3D architecture viewer and live Azure pricing make recommendations tangible. "
         "Clients understand and trust the numbers — no more hand-waving on costs."),
        (GOLD,   "💼  Commercial Directors",
         "Scenario modelling means 3 options ready before every negotiation. "
         "'What if' questions become your advantage, not your vulnerability."),
        (GREEN,  "📈  Sales Leaders",
         "Collective delivery knowledge captured and applied to every new estimate. "
         "Accuracy improves over time. Win rates improve with it."),
        (RED,    "🏢  Enterprise IT Teams",
         "Deploy on-premises or Azure Container Apps. SSO via Microsoft AD. "
         "Data stays in your network. Compliant with enterprise security requirements."),
    ]

    ucw = (W - 90) / 2; uch = 76
    for i, (accent, title, desc) in enumerate(use_cases):
        col = i % 2; row = i // 2
        ux = 36 + col*(ucw+18)
        uy = cy - row*(uch+10) - uch
        rr(c, ux, uy, ucw, uch, r=7, fill=CARD, stroke=accent, sw=0.5)
        c.setFillColor(accent); c.setFillAlpha(0.07)
        rr(c, ux, uy, ucw, uch, r=7, fill=accent); c.setFillAlpha(1)
        c.setFillColor(accent); c.rect(ux, uy+uch-3, ucw, 3, fill=1, stroke=0)
        txt(c, title, ux+10, uy+uch-18, "Helvetica-Bold", 9.5, WHITE)
        wrap_text(c, desc, ux+10, uy+uch-33, ucw-20, "Helvetica", 8, DIM, leading=11.5)

    # Testimonials
    test_y = cy - 3*(uch+10) - uch - 18
    cy2 = section_title(c, "What Our Users Say", 36, test_y, accent=GOLD, sub=None)

    testimonials = [
        ('"We used to spend two days per proposal. Now the first draft is done before the coffee '
         'is cold. Scenario modelling alone transformed how we handle commercial negotiations."',
         "— Presales Director, Global Systems Integrator"),
        ('"The 3D architecture viewer in client meetings is a genuine showstopper. '
         'First time I\'ve seen a CFO lean forward during a technical section."',
         "— Solution Architect, Enterprise Technology Practice"),
        ('"The completeness checker caught three critical gaps in a scope we would have priced at a loss. '
         'That feature paid for itself in the first week."',
         "— Senior Presales Consultant, Digital Transformation Practice"),
    ]

    tw2 = (W - 90) / 3
    for i, (quote, attr) in enumerate(testimonials):
        tx2 = 36 + i*(tw2+12)
        ty2 = cy2 - 80
        rr(c, tx2, ty2, tw2, 82, r=8, fill=CARD2, stroke=GOLD, sw=0.4)
        c.setFillColor(GOLD); c.setFont("Helvetica-Bold", 18); c.setFillAlpha(0.4)
        c.drawString(tx2+8, ty2+64, "“"); c.setFillAlpha(1)
        wrap_text(c, quote, tx2+10, ty2+56, tw2-20, "Helvetica", 7.5, TEXT, leading=11)
        txt(c, attr, tx2+10, ty2+8, "Helvetica", 7, GOLD)

    page_footer(c, 9, 11)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 10 — ROADMAP & SECURITY
# ═══════════════════════════════════════════════════════════════════════════════

def page_roadmap(c):
    bg(c); dot_grid(c, 0, 0, W, H)
    page_header(c, "ROADMAP & SECURITY", PURPLE)

    cy = H - 65
    cy = section_title(c, "What's Coming Next", 36, cy, accent=PURPLE,
                        sub="We ship continuously — your platform gets more powerful every quarter")

    roadmap = [
        (GREEN,  "Q2 2026 — Shipping Now",    [
            "Editable proposal sections (WYSIWYG in-app)",
            "Interactive ROI calculator (client-facing)",
            "Full Word (.docx) proposal export",
            "Proposal public sharing link",
        ]),
        (CYAN,   "Q3 2026 — Next Quarter",    [
            "Client portal (read-only, branded)",
            "CRM integration (Salesforce / HubSpot)",
            "Real-time multi-user collaboration",
            "Role-based access control (4 roles)",
        ]),
        (PURPLE, "Q4 2026 — Later This Year", [
            "REST API layer (FastAPI) for custom integrations",
            "Microsoft Teams bot integration",
            "Mobile-responsive interface",
            "Advanced analytics dashboard",
        ]),
    ]

    rmw = (W - 90) / 3; rmh = 110
    for i, (accent, title, items) in enumerate(roadmap):
        rx = 36 + i*(rmw+12)
        ry = cy - rmh - 10
        rr(c, rx, ry, rmw, rmh, r=8, fill=CARD, stroke=accent, sw=0.7)
        c.setFillColor(accent); c.setFillAlpha(0.1)
        rr(c, rx, ry, rmw, rmh, r=8, fill=accent); c.setFillAlpha(1)
        c.setFillColor(accent); c.rect(rx, ry+rmh-3, rmw, 3, fill=1, stroke=0)
        txt(c, title, rx+10, ry+rmh-18, "Helvetica-Bold", 8.5, WHITE)
        for j, item in enumerate(items):
            c.setFillColor(accent); c.circle(rx+16, ry+rmh-34-j*17+5, 2.5, fill=1, stroke=0)
            txt(c, item, rx+24, ry+rmh-34-j*17, "Helvetica", 8, DIM)

    # Security section
    sec_y = cy - rmh - 36
    sec_y2 = section_title(c, "Enterprise Security & Compliance", 36, sec_y, accent=RED,
                             sub="Built with enterprise security requirements from day one")

    sec_items = [
        (RED,    "🔐  API Keys in Session Memory Only",
         "Credentials never persisted to disk in plaintext. Compatible with Azure Key Vault injection."),
        (ORANGE, "🛡  Authentication Gate",
         "Admin password or Microsoft SSO (Azure AD). Role-based access in Professional/Enterprise tiers."),
        (BLUE,   "🏠  Data Stays In Your Network",
         "Run data in local SQLite or Azure SQL. No telemetry. No usage data to third parties."),
        (GREEN,  "📋  Audit & Governance Ready",
         "Full run history. Architect review gate. Outcome tracking. Compliant with enterprise audit requirements."),
    ]

    sw2 = (W - 90) / 2; sh2 = 62
    for i, (accent, title, desc) in enumerate(sec_items):
        col = i % 2; row = i // 2
        sx2 = 36 + col*(sw2+18)
        sy2 = sec_y2 - row*(sh2+8) - sh2
        rr(c, sx2, sy2, sw2, sh2, r=7, fill=CARD, stroke=accent, sw=0.5)
        c.setFillColor(accent); c.setFillAlpha(0.07)
        rr(c, sx2, sy2, sw2, sh2, r=7, fill=accent); c.setFillAlpha(1)
        c.setFillColor(accent); c.rect(sx2, sy2+sh2-3, sw2, 3, fill=1, stroke=0)
        txt(c, title, sx2+10, sy2+sh2-18, "Helvetica-Bold", 9, WHITE)
        wrap_text(c, desc, sx2+10, sy2+sh2-32, sw2-20, "Helvetica", 8, DIM, leading=11.5)

    page_footer(c, 10, 11)


# ═══════════════════════════════════════════════════════════════════════════════
#  PAGE 11 — CALL TO ACTION / GET STARTED
# ═══════════════════════════════════════════════════════════════════════════════

def page_cta(c):
    bg(c)
    grad_rect(c, 0, H//3, W, H*2//3,
              Color(0.008, 0.031, 0.09), Color(0.02, 0.05, 0.14))
    dot_grid(c, 0, 0, W, H)
    glow(c, W/2, H/2+60, 260, CYAN, layers=7, alpha=0.06)
    glow(c, 60, H-100, 120, PURPLE, alpha=0.07)
    glow(c, W-60, 100, 120, GOLD, alpha=0.06)

    page_header(c, "GET STARTED", CYAN)

    # Big CTA text
    txtc(c, "Ready to Transform Your Presales?", W/2, H-90, "Helvetica-Bold", 20, TEXT)
    txtc(c, "Start your free 7-day trial today. No credit card required. No commitment.",
         W/2, H-112, "Helvetica", 10, DIM)

    # 3 start options
    opts = [
        (CYAN,   "🚀  Free 7-Day Trial",
         "Start immediately. 10 estimation runs.\nUpload your first scope document today.",
         "belal.eci.com/trial"),
        (PURPLE, "📅  Book a Live Demo",
         "2-hour live session. Bring your most\nchallenging scope doc. See it live.",
         "belal.eci.com/demo"),
        (GOLD,   "💬  Talk to Sales",
         "Custom enterprise pricing.\nDeployment assistance. White-labelling.",
         "sales@eci.com"),
    ]

    ow = (W - 90) / 3; oh = 120
    oy = H - 270
    for i, (accent, title, desc, link) in enumerate(opts):
        ox = 36 + i*(ow+12)
        rr(c, ox, oy-oh, ow, oh, r=10, fill=CARD, stroke=accent, sw=1)
        c.setFillColor(accent); c.setFillAlpha(0.1)
        rr(c, ox, oy-oh, ow, oh, r=10, fill=accent); c.setFillAlpha(1)
        c.setFillColor(accent); c.rect(ox, oy-3, ow, 3, fill=1, stroke=0)
        txt(c, title, ox+12, oy-20, "Helvetica-Bold", 10, WHITE)
        for j, line_ in enumerate(desc.split("\n")):
            txt(c, line_, ox+12, oy-36-j*13, "Helvetica", 8, DIM)
        # Link button
        rr(c, ox+12, oy-oh+14, ow-24, 20, r=5, fill=accent)
        txtc(c, link, ox+ow/2, oy-oh+20, "Helvetica-Bold", 7.5, BG)

    # Package summary strip
    strip_y = oy - oh - 24
    c.setFillColor(CARD2); c.rect(36, strip_y-40, W-72, 44, fill=1, stroke=0)
    pkgs = ["FREE TRIAL  ·  7 days", "STARTER  ·  £299/mo", "PROFESSIONAL  ·  £999/mo", "ENTERPRISE  ·  Custom"]
    colors = [BLUE, CYAN, PURPLE, GOLD]
    pw = (W - 72) / 4
    for i, (pkg, col) in enumerate(zip(pkgs, colors)):
        px = 36 + i*pw
        c.setFillColor(col); c.rect(px, strip_y+2, pw-2, 2, fill=1, stroke=0)
        txtc(c, pkg, px+pw/2, strip_y-22, "Helvetica-Bold", 8, col)

    # Final tagline
    txtc(c, "⚡  11 Agents  ·  9 Formats  ·  90 Seconds  ·  One Platform",
         W/2, strip_y-64, "Helvetica-Bold", 11, CYAN)
    txtc(c, "BELAL  —  Business Estimation Leveraging Automated Learning",
         W/2, strip_y-82, "Helvetica", 9, DIM)
    txtc(c, "An ECI Product  ·  belal.eci.com  ·  contact@eci.com",
         W/2, strip_y-98, "Helvetica", 8, MUTED)

    # ECI logo bottom-center
    if os.path.exists(LOGO):
        try:
            c.drawImage(LOGO, W/2-40, strip_y-140, width=80, height=36,
                        preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # Footer bar
    c.setFillColor(CARD); c.rect(0, 0, W, 28, fill=1, stroke=0)
    c.setFillColor(CYAN); c.rect(0, 26, W, 2, fill=1, stroke=0)
    txtc(c, "© 2026 ECI  ·  BELAL is an ECI proprietary platform  ·  All rights reserved  ·  Confidential",
         W/2, 9, "Helvetica", 7.5, MUTED)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN — Build PDF
# ═══════════════════════════════════════════════════════════════════════════════

def build():
    c = canvas.Canvas(OUT, pagesize=A4)
    c.setTitle("BELAL — Business Estimation Leveraging Automated Learning | Sales Deck")
    c.setAuthor("ECI")
    c.setSubject("AI-Powered Presales Intelligence Platform — Sales & Pricing Deck 2026")

    pages = [
        page_cover,
        page_problem,
        page_solution,
        page_features_1,
        page_features_2,
        page_outputs,
        page_pricing,
        page_roi,
        page_usecases,
        page_roadmap,
        page_cta,
    ]

    for fn in pages:
        fn(c)
        c.showPage()

    c.save()
    size_kb = os.path.getsize(OUT) // 1024
    print(f"[OK] PDF saved: {OUT}")
    print(f"     Pages: {len(pages)}  |  Size: {size_kb} KB  |  Format: A4")


if __name__ == "__main__":
    build()
