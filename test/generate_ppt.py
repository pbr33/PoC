"""
Generate GLO_Finance_ASIS_ProcessMap.pptx
- Captures the full v3 HTML diagram via Playwright (headless Chromium)
- Slices into 4 wide-format slides (2 phases per slide)
- Adds a title slide and a phase-legend slide
- Output: test/GLO_Finance_ASIS_ProcessMap.pptx
"""

import asyncio, os, sys
from pathlib import Path
from io import BytesIO

# ── paths ────────────────────────────────────────────────────────────────────
BASE   = Path(__file__).parent
HTML   = BASE / "GLO_Finance_ASIS_ProcessMap_v3.html"
OUTPUT = BASE / "GLO_Finance_ASIS_ProcessMap.pptx"

# ── diagram geometry (must match the HTML constants) ─────────────────────────
CANVAS_W = 3540
CANVAS_H = 1300
LABEL_W  = 210        # left swim-lane label panel width

# Phase boundaries  (x_start, x_end, label)
PHASES = [
    (210,  590,  "Supplier Onboarding"),
    (590,  960,  "Purchase Order Creation"),
    (960,  1310, "Shipment Execution"),
    (1310, 1680, "Invoice Preparation"),
    (1680, 2060, "Cost Validation & Agreement"),
    (2060, 2460, "PO Raise & Submission"),
    (2460, 2850, "Payment & AR Billing"),
    (2850, 3520, "Customs Clearance & Duty"),
]

# Group phases into 4 slides (2 phases each)
# Each slide shows the left label panel + 2 phases
SLIDE_GROUPS = [
    (0, 1),   # Slide 1: Supplier Onboarding + PO Creation
    (2, 3),   # Slide 2: Shipment + Invoice Preparation
    (4, 5),   # Slide 3: Cost Validation + PO Raise
    (6, 7),   # Slide 4: Payment & AR + Customs
]

# ── slide spec helpers ────────────────────────────────────────────────────────
def slide_crop(group):
    """Return (x, y, w, h) in diagram pixels for a phase group."""
    ph_a = PHASES[group[0]]
    ph_b = PHASES[group[1]]
    x = 0                          # include left label panel
    y = 0
    w = ph_b[1]                    # right edge of last phase in group
    h = CANVAS_H
    return x, y, w, h

# ── screenshot via Playwright ─────────────────────────────────────────────────
async def capture_screenshots():
    """Render the HTML at full resolution, return 4 PNG bytes objects."""
    from playwright.async_api import async_playwright
    shots = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page    = await browser.new_page()
        # Set viewport larger than the full canvas so nothing clips
        await page.set_viewport_size({"width": CANVAS_W + 40, "height": CANVAS_H + 40})
        await page.goto(HTML.as_uri())
        await page.wait_for_timeout(800)   # let JS render

        for gi, group in enumerate(SLIDE_GROUPS):
            x, y, w, h = slide_crop(group)
            img = await page.screenshot(
                clip={"x": x, "y": y, "width": w, "height": h},
                type="png"
            )
            shots[gi] = img
            print(f"  Captured slide {gi+1}: phases {group[0]+1}-{group[1]+1}  ({w}x{h}px)")

        await browser.close()
    return shots

# ── build PPTX ────────────────────────────────────────────────────────────────
def build_pptx(shots: dict):
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    DARK  = RGBColor(0x03, 0x06, 0x0F)
    TEAL  = RGBColor(0x00, 0xE5, 0xC0)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    GREY  = RGBColor(0xAA, 0xAA, 0xBB)

    # Wide-screen 16:9 (13.33 x 7.5 inches)
    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)

    blank_layout = prs.slide_layouts[6]   # completely blank

    # helper: add a text box
    def add_text(slide, text, x, y, w, h, size=18, bold=False,
                 color=WHITE, align=PP_ALIGN.LEFT, italic=False):
        txb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf  = txb.text_frame
        tf.word_wrap = True
        para = tf.paragraphs[0]
        para.alignment = align
        run = para.add_run()
        run.text = text
        run.font.size  = Pt(size)
        run.font.bold  = bold
        run.font.italic = italic
        run.font.color.rgb = color
        return txb

    def fill_bg(slide, color=DARK):
        from pptx.util import Emu
        bg = slide.shapes.add_shape(
            1,  # MSO_SHAPE_TYPE.RECTANGLE
            0, 0, prs.slide_width, prs.slide_height
        )
        bg.fill.solid()
        bg.fill.fore_color.rgb = color
        bg.line.fill.background()
        # push to back
        sp = bg._element
        sp.getparent().remove(sp)
        slide.shapes._spTree.insert(2, sp)

    # ── Slide 0: Title ───────────────────────────────────────────────────────
    s0 = prs.slides.add_slide(blank_layout)
    fill_bg(s0)

    # Teal accent bar
    bar = s0.shapes.add_shape(1, 0, Inches(3.2), Inches(0.06), Inches(13.33))
    bar.fill.solid(); bar.fill.fore_color.rgb = TEAL; bar.line.fill.background()

    add_text(s0, "GLO Finance", 1.0, 1.2, 11.0, 0.8,
             size=44, bold=True, color=TEAL, align=PP_ALIGN.CENTER)
    add_text(s0, "AS-IS Process Map", 1.0, 2.0, 11.0, 0.8,
             size=32, bold=False, color=WHITE, align=PP_ALIGN.CENTER)
    add_text(s0, "End-to-End Finance Operations  |  7 Swim Lanes  |  8 Process Phases",
             1.0, 2.85, 11.0, 0.5, size=14, color=GREY, align=PP_ALIGN.CENTER)

    # Swim-lane legend table  (2 cols x 7 rows)
    lane_data = [
        ("#00E5C0", "Supplier & Factory MDM",      "EQOS · NeoGrid · SSUP Portal"),
        ("#4FB3FF", "Purchase Order Creation",     "LM/MM System · ISOS · OTM/BizTalk"),
        ("#A78BFA", "Shipment Execution",          "OTM · BizTalk/RTA · FF Systems"),
        ("#FFD04A", "Product Invoice Processing",  "ISOS/OTM BM · Documentum · EDI → OFI · MS Access"),
        ("#FF6B6B", "Freight Self-Billing",        "MS Access DB · Rolling File · Oracle Fusion · Tungsten"),
        ("#C57BFF", "AR & Intercompany Billing",   "Oracle Fusion AR · RIMS (CE) · Oracle R12"),
        ("#52E67A", "Customs & Duty",              "OTM CSS/IMS · NBS/CM-UK · WTA Portal · DDA (TISL)"),
    ]
    top = Inches(3.5)
    row_h = Inches(0.48)
    col_x = [Inches(1.0), Inches(5.2), Inches(9.0)]
    col_w = [Inches(4.0), Inches(3.6), Inches(4.0)]

    for i, (hex_c, name, systems) in enumerate(lane_data):
        r, g, b = int(hex_c[1:3],16), int(hex_c[3:5],16), int(hex_c[5:7],16)
        dot = s0.shapes.add_shape(9, col_x[0], top + i*row_h + Inches(0.14),
                                  Inches(0.18), Inches(0.18))
        dot.fill.solid(); dot.fill.fore_color.rgb = RGBColor(r,g,b)
        dot.line.fill.background()
        add_text(s0, name, 1.25, 3.5 + i*0.48, 3.7, 0.44,
                 size=10, bold=True, color=WHITE)
        add_text(s0, systems, 5.1, 3.5 + i*0.48, 8.0, 0.44,
                 size=8.5, color=GREY, italic=True)

    add_text(s0, "Tesco Global Finance  |  Confidential  |  2024",
             0, 7.1, 13.33, 0.4, size=8, color=GREY, align=PP_ALIGN.CENTER)

    # ── Slides 1-4: Diagram sections ─────────────────────────────────────────
    slide_titles = [
        "Phase 1-2: Supplier Onboarding  &  Purchase Order Creation",
        "Phase 3-4: Shipment Execution  &  Invoice Preparation",
        "Phase 5-6: Cost Validation  &  PO Raise / Submission",
        "Phase 7-8: Payment & AR Billing  &  Customs Clearance / Duty",
    ]

    for gi, group in enumerate(SLIDE_GROUPS):
        sl = prs.slides.add_slide(blank_layout)
        fill_bg(sl)

        # title bar
        title_bar = sl.shapes.add_shape(
            1, 0, 0, prs.slide_width, Inches(0.55))
        title_bar.fill.solid()
        title_bar.fill.fore_color.rgb = RGBColor(0x0D, 0x11, 0x17)
        title_bar.line.fill.background()

        add_text(sl, slide_titles[gi], 0.15, 0.07, 10.5, 0.44,
                 size=13, bold=True, color=TEAL)

        ph_a = PHASES[group[0]]
        ph_b = PHASES[group[1]]
        page_note = f"Phases {group[0]+1} & {group[1]+1}  |  {ph_a[2]}  →  {ph_b[2]}"
        add_text(sl, page_note, 0.15, 0.07, 13.0, 0.44,
                 size=9, color=GREY, align=PP_ALIGN.RIGHT)

        # diagram image — fill the remaining height
        img_bytes = shots[gi]
        img_stream = BytesIO(img_bytes)

        # Calculate aspect ratio and fit to slide width keeping diagram readable
        # Available area: full width 13.33", height 6.85" (below title bar)
        AVAIL_W = Inches(13.33)
        AVAIL_H = Inches(6.88)

        _, _, crop_w, crop_h = slide_crop(group)
        aspect = crop_w / crop_h

        if Emu(AVAIL_W) / Emu(AVAIL_H) > aspect:
            # height-limited
            img_h = AVAIL_H
            img_w = int(img_h * aspect)
        else:
            # width-limited
            img_w = AVAIL_W
            img_h = int(img_w / aspect)

        # Center horizontally
        img_x = (prs.slide_width  - img_w) // 2
        img_y = Inches(0.58)

        sl.shapes.add_picture(img_stream, img_x, img_y, img_w, img_h)

        # Phase labels at bottom
        label_text = f"{ph_a[2]}  |  {ph_b[2]}"
        add_text(sl, label_text, 0, 7.2, 13.33, 0.3,
                 size=7, color=GREY, align=PP_ALIGN.CENTER)

    prs.save(OUTPUT)
    print("PPT saved: " + str(OUTPUT))

# ── main ──────────────────────────────────────────────────────────────────────
async def main():
    print("Launching headless browser...")
    shots = await capture_screenshots()
    print("Building PPTX...")
    build_pptx(shots)

if __name__ == "__main__":
    asyncio.run(main())
