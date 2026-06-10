"""
GLO Finance AS-IS Process Map — PDF Report Generator
Source: GLO_Finance_ASIS_Final.docx
"""
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
import os, datetime

OUTPUT = os.path.join(os.path.dirname(__file__), "GLO_Finance_ASIS_Report.pdf")

# ── Colour palette ────────────────────────────────────────────
C_DARK   = colors.HexColor("#03060F")
C_TEAL   = colors.HexColor("#00E5C0")
C_BLUE   = colors.HexColor("#4FB3FF")
C_PURPLE = colors.HexColor("#A78BFA")
C_AMBER  = colors.HexColor("#FFD04A")
C_RED    = colors.HexColor("#FF6B6B")
C_VIOLET = colors.HexColor("#C57BFF")
C_GREEN  = colors.HexColor("#52E67A")
C_GREY   = colors.HexColor("#4E6280")
C_WHITE  = colors.HexColor("#EEF4FF")
C_BG     = colors.HexColor("#0D1117")
C_PANEL  = colors.HexColor("#111827")

W, H = A4

def make_styles():
    s = getSampleStyleSheet()
    styles = {}
    styles['cover_title'] = ParagraphStyle('cover_title', fontName='Helvetica-Bold',
        fontSize=22, textColor=C_WHITE, spaceAfter=6, leading=28)
    styles['cover_sub'] = ParagraphStyle('cover_sub', fontName='Helvetica',
        fontSize=11, textColor=C_GREY, spaceAfter=4, leading=16)
    styles['cover_meta'] = ParagraphStyle('cover_meta', fontName='Helvetica',
        fontSize=9, textColor=C_GREY, spaceAfter=2)
    styles['section_h'] = ParagraphStyle('section_h', fontName='Helvetica-Bold',
        fontSize=14, textColor=C_TEAL, spaceBefore=16, spaceAfter=6)
    styles['sub_h'] = ParagraphStyle('sub_h', fontName='Helvetica-Bold',
        fontSize=11, textColor=C_BLUE, spaceBefore=10, spaceAfter=4)
    styles['body'] = ParagraphStyle('body', fontName='Helvetica',
        fontSize=9, textColor=C_WHITE, spaceAfter=4, leading=14, alignment=TA_JUSTIFY)
    styles['bullet'] = ParagraphStyle('bullet', fontName='Helvetica',
        fontSize=9, textColor=C_WHITE, spaceAfter=3, leading=13,
        leftIndent=12, bulletIndent=0)
    styles['risk'] = ParagraphStyle('risk', fontName='Helvetica',
        fontSize=9, textColor=colors.HexColor("#FCA5A5"), spaceAfter=3,
        leading=13, leftIndent=12)
    styles['caption'] = ParagraphStyle('caption', fontName='Helvetica',
        fontSize=8, textColor=C_GREY, spaceAfter=4, leading=11, alignment=TA_CENTER)
    return styles

def hr(color=C_GREY, thickness=0.5):
    return HRFlowable(width="100%", thickness=thickness, color=color, spaceAfter=6, spaceBefore=2)

def build_pdf():
    doc = SimpleDocTemplate(OUTPUT, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm, topMargin=2.2*cm, bottomMargin=2*cm)
    S = make_styles()
    story = []

    # ════════════════════════════════════════════════════════
    # PAGE 1 — COVER
    # ════════════════════════════════════════════════════════
    story.append(Spacer(1, 1.5*cm))
    story.append(Paragraph("GLO Finance — AS-IS Process Documentation", S['cover_title']))
    story.append(Paragraph("Global Logistics (Finance) Workstream · End-to-End Process Flow", S['cover_sub']))
    story.append(hr(C_TEAL, 1))
    story.append(Spacer(1, 0.4*cm))

    meta = [
        ["Source Document:", "GLO_Finance_ASIS_Final.docx"],
        ["Authors:", "Krishna Moda / Kirti Gupta"],
        ["Report Generated:", datetime.datetime.now().strftime("%d %B %Y")],
        ["Sections Covered:", "§3.1 Supplier MDM · §3.2 PO Creation · §3.3 Shipment · §3.4 Invoice Processing · §3.5 AR Billing · §3.6 Customs & Duty"],
        ["Process Lanes:", "7 (MDM / PO / Shipment / Product Invoice / Freight Self-Billing / AR / Customs)"],
        ["Systems Mapped:", "EQOS, NeoGrid, LM/MM, ISOS, OTM, Documentum, EDI, OFI, MS Access, Oracle Fusion, Tungsten, NBS, CM-UK, WTA/DDA"],
    ]
    t = Table(meta, colWidths=[4.5*cm, 12.5*cm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0,0),(-1,-1), 'Helvetica'),
        ('FONTNAME', (0,0),(0,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0),(-1,-1), 9),
        ('TEXTCOLOR',(0,0),(0,-1), C_TEAL),
        ('TEXTCOLOR',(1,0),(1,-1), C_WHITE),
        ('VALIGN',   (0,0),(-1,-1), 'TOP'),
        ('TOPPADDING',(0,0),(-1,-1), 4),
        ('BOTTOMPADDING',(0,0),(-1,-1), 4),
        ('ROWBACKGROUNDS',(0,0),(-1,-1),[C_PANEL, C_BG]),
        ('BOX',(0,0),(-1,-1),0.5,C_GREY),
        ('LINEBELOW',(0,0),(-1,-2),0.3,C_GREY),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.6*cm))

    story.append(Paragraph("Executive Summary", S['section_h']))
    story.append(Paragraph(
        "This document summarises the AS-IS end-to-end finance process for Tesco Global Logistics, "
        "based on walkthrough sessions and discussions with Finance and Technology stakeholders. "
        "The process spans seven distinct functional areas — from supplier and factory master data management "
        "through to customs duty payment — and involves fourteen interconnected systems. "
        "The current state is characterised by significant manual intervention, particularly in freight "
        "self-billing (Excel Rolling Files, MS Access database), invoice processing (Documentum manual indexing, "
        "MS Access 3-way matching), and Central Europe AR billing (manual RIMS keying). "
        "Several critical process gaps have been identified including bulk freight PO creation, "
        "late freight cost accruals, and a single-point-of-failure MS Access database.", S['body']))
    story.append(Spacer(1, 0.3*cm))

    # System landscape table
    story.append(Paragraph("System Landscape Overview (§2)", S['section_h']))
    sys_data = [
        ["System", "Purpose", "Key Integration"],
        ["LM",          "Purchase Order creation (Home/CE ranges)",        "→ ISOS via BizTalk/XCOM"],
        ["MM System",   "Clothing PO origin; passes to LM",                "LM → ISOS"],
        ["ISOS",        "PO validation, enrichment, FF assignment, invoice extract (78-col)", "↔ LM, OTM, EQOS, EDI"],
        ["OTM",         "Shipment execution, booking, status, cost exceptions, CSS reports", "↔ ISOS, BizTalk, DW"],
        ["EQOS",        "Supplier & factory master data",                   "Weekly batch → OFI; 15-min → ISOS"],
        ["NeoGrid",     "Supplier set-up workflow (SSUP→MDM task routing)", "SSUP portal"],
        ["Documentum",  "Storage of supplier PDF invoices & customs docs",  "Manual indexing; Excel extract"],
        ["EDI",         "78-col ISOS extract → 69-col OFI-compatible CSV", "ISOS → OFI"],
        ["OFI (Oracle 11i)", "AP/AR invoice posting & payment processing", "EDI input; HSBC output"],
        ["MS Access DB","Self-billing tool: rate card storage, weekly file extraction", "OTM → manual upload"],
        ["Rolling File (Excel)","Master payment tracker for all carrier/FF charges","Manual; no system backup"],
        ["Oracle Fusion","PO & procurement for freight; AP payables for carrier invoices","→ Tungsten"],
        ["Tungsten",    "Carrier/FF e-invoicing portal; auto-feeds Fusion Payables","→ Oracle Fusion AP"],
        ["NBS",         "Duty rate master from OTM HS codes",              "OTM → NBS → QL accrual"],
        ["CM-UK",       "Customs processing — Home category imports (SCDP)","WMS Denver → CSG → CM-UK"],
        ["RIMS",        "CE AR invoice manual entry; pushes to Oracle R12", "OFI output → RIMS → R12"],
        ["Transporeon", "Merchant Haulage payments; TICB commission calcs","Weekly finance reports"],
        ["BizTalk/RTA", "Integration layer for ALL message flows between systems","LM↔ISOS↔OTM↔LSPs"],
    ]
    st = Table(sys_data, colWidths=[3.5*cm, 7.5*cm, 6*cm])
    st.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),8),
        ('TEXTCOLOR',(0,0),(-1,0),C_DARK),
        ('BACKGROUND',(0,0),(-1,0),C_TEAL),
        ('TEXTCOLOR',(0,1),(-1,-1),C_WHITE),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[C_PANEL, C_BG]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),3),
        ('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('BOX',(0,0),(-1,-1),0.5,C_GREY),
        ('LINEBELOW',(0,0),(-1,-2),0.25,C_GREY),
        ('TEXTCOLOR',(0,1),(0,-1),C_TEAL),
        ('FONTNAME',(0,1),(0,-1),'Helvetica-Bold'),
    ]))
    story.append(st)
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════
    # PAGE 2 — PROCESS MAP DESCRIPTION
    # ════════════════════════════════════════════════════════
    story.append(Paragraph("Process Flow Map — Description", S['section_h']))
    story.append(Paragraph(
        "The interactive process map (GLO_Finance_ASIS_ProcessMap_v3.html) visualises the complete end-to-end "
        "AS-IS flow across 7 horizontal swim lanes and 8 phase columns. Each lane represents a functional "
        "process area with the systems used shown in the left panel. Arrows show process sequence: "
        "<b>green</b> = YES/proceed path; <b>orange</b> = NO/exception with loop-back; "
        "<b>grey dashed</b> = cross-lane data handoff. Hover any box for the full document-sourced detail.", S['body']))
    story.append(Spacer(1, 0.2*cm))

    # Diagram reference table
    lanes_desc = [
        ["Lane", "Colour", "Systems", "Phases Active", "Key Elements"],
        ["Supplier &\nFactory MDM",
         "Teal",
         "EQOS · NeoGrid · SSUP",
         "1–2",
         "SSUP doc collection → MDM validation → EQOS creation → OFI + ISOS feeds"],
        ["Purchase Order\nCreation",
         "Blue",
         "LM · MM · ISOS · OTM",
         "2–3",
         "Buyer PO in LM → ISOS validates (factory compliance) → enriches + assigns FF → OTM + Supplier"],
        ["Shipment\nExecution",
         "Purple",
         "OTM · BizTalk · FF Systems",
         "3–4",
         "FOB handover → SM1 → ISOS → SM2 → OTM → Daily Inbound All File"],
        ["Product Invoice\nProcessing",
         "Amber",
         "ISOS · Documentum · EDI · OFI · MS Access",
         "4–7",
         "IV0 → ISOS cost match → 78-col extract → EDI 69-col → MS Access 3-way match → OFI AP invoice → HSBC payment"],
        ["Freight\nSelf-Billing",
         "Red",
         "MS Access DB · Rolling File · Oracle Fusion · Tungsten",
         "4–7",
         "OTM All File → MS Access → Mon extract → Rolling File → carrier email → agree costs → Fusion PO → Tungsten invoice → AP pay"],
        ["AR &\nIntercompany",
         "Violet",
         "OFI · RIMS · Oracle R12",
         "7–8",
         "OFI AP → AR auto-created (TISL) → Commission invoice → UK/ROI (Fusion) or CE (RIMS → R12)"],
        ["Customs &\nDuty",
         "Green",
         "OTM CSS · IMS · NBS · WTA · CM-UK · DDA",
         "6–8",
         "OTM CSS → WTA · IMS from AP → completeness check → SFD at border → HS codes → NBS duty rates → accrual → DDA payment"],
    ]
    lt = Table(lanes_desc, colWidths=[2.5*cm, 1.5*cm, 3.5*cm, 1.8*cm, 7.7*cm])
    lt.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),8),
        ('TEXTCOLOR',(0,0),(-1,0),C_DARK),
        ('BACKGROUND',(0,0),(-1,0),C_TEAL),
        ('TEXTCOLOR',(0,1),(-1,-1),C_WHITE),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[C_PANEL, C_BG]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),4),
        ('BOTTOMPADDING',(0,0),(-1,-1),4),
        ('BOX',(0,0),(-1,-1),0.5,C_GREY),
        ('LINEBELOW',(0,0),(-1,-2),0.25,C_GREY),
    ]))
    story.append(lt)
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════
    # PAGE 3 — DETAILED PROCESS NARRATIVES
    # ════════════════════════════════════════════════════════
    processes = [
        {
            "title": "§3.1 Supplier & Factory Master Data (MDM)",
            "color": C_TEAL,
            "systems": "EQOS · NeoGrid · SSUP Portal",
            "steps": [
                ("SSUP Doc Collection", "SSUP team collects: set-up form, business rationale, bank documents (sort code, account, currency), company letterhead, contact details. Uploaded to NeoGrid; tasks assigned to MDM."),
                ("MDM Validation", "Existing supplier: validate EQOS ID vs address/bank/contacts. New supplier: validate bank docs, letterhead, sort code, currency. Lead/manager approval required. Gaps flagged back to SSUP."),
                ("EQOS Creation", "Supplier/factory record created in EQOS. One record per supplier-factory combination. Factory attributes cannot be edited post-creation — changes require new factory ID. Multiple EQOS records collapse to one OFI vendor if same tax registration number."),
                ("System Feeds", "EQOS → OFI weekly batch (vendor master — prerequisite for AP payment). EQOS → ISOS 15-minute push (supplier compliance validation before PO processing)."),
            ],
        },
        {
            "title": "§3.2 Purchase Order Creation",
            "color": C_BLUE,
            "systems": "LM · MM System · ISOS · OTM · BizTalk",
            "steps": [
                ("PO Creation in LM/MM", "Buyer creates PO in LM. Clothing POs originate in MM → passed to LM → ISOS. Transmission via BizTalk or XCOM. PO types: PO1 (UK inbound), PO3 (outbound to OTM), PO5 (UK home range), PO6 (CE clothing + home)."),
                ("ISOS Validation", "ISOS validates: supplier active status (EQOS), factory approval (EQOS), cost price non-zero, delivery date validity. If factory non-compliant → ISOS sets PO to Cancelled; LM does NOT receive this status."),
                ("ISOS Enrichment", "ISOS enriches PO with: freight forwarder assignment, LSP selection (based on transport lane tables), mapping data. ISOS maintains PO amendment history — LM does not."),
                ("OTM & Supplier", "PO flows ISOS → BizTalk → OTM → Supplier (PDF email) + back to ISOS. OTM enhances PO. PO PDF excludes FF name; shows only transport mode and port details."),
            ],
        },
        {
            "title": "§3.3 Shipment Execution",
            "color": C_PURPLE,
            "systems": "OTM · BizTalk · RTA · FF Systems",
            "steps": [
                ("FOB Handover & SM1", "At FOB, origin FF enters shipment details in their systems. FF sends SM1 (Shipment Milestone 1) to ISOS via BizTalk. Multiple SM1 versions may arrive; ISOS processes only the highest version number."),
                ("SM2 to OTM", "ISOS → SM2 → OTM. OTM records: bookings, container numbers, BL details, shipment dates, milestone timestamps. OTM is the system of record for planned vs actual shipment tracking."),
                ("SM3/SM4 Returns", "OTM → SM3 → Data Warehouse / MM / LM (system-to-system update). OTM → SM4 via BizTalk → FF. Tesco does not separately send shipment details to suppliers."),
                ("Daily Inbound All File", "OTM auto-generates the Daily Inbound All File every day. Delivered to Self-Billing Team via shared mailbox (~12:50 PM) and shared folder. This is the PRIMARY input for all freight billing activities."),
            ],
        },
        {
            "title": "§3.4.1 Product Supplier Invoice Processing",
            "color": C_AMBER,
            "systems": "ISOS · OTM BM · Documentum · EDI · OFI (Oracle 11i) · MS Access",
            "steps": [
                ("IV0 & Documentum", "FF triggers IV0 message → BizTalk → ISOS. Supplier sends PDF invoice separately → Documentum (manual indexing of 6-7 fields: PO number, currency, supplier number, quantity, total amount, invoice number). Packing list cross-check done during indexing."),
                ("ISOS Cost Validation", "ISOS performs automatic 2-way match: PO cost (LM) vs IV0 cost (supplier). If mismatch → cost exception in OTM Business Monitor. Buyer selects: 'Use Supplier Cost', 'Use PO Cost', or 'Alternate Cost'. ISOS does not generate extract until BM is approved."),
                ("78-col Extract & EDI", "ISOS generates 78-column extract (approved POs only): merges PO data, EQOS master, OTM shipment data, IV0 values. EDI converts 78-col → 69-col OFI-compatible CSV (removes 8-9 unused fields)."),
                ("MS Access 3-Way Match", "AP team compares 69-col EDI output vs Documentum Excel extract in MS Access. Validates: Price, Quantity, Invoice number, Supplier number, Currency, Shipment details. Mismatches → DQ exception; FF/supplier corrects; resubmit."),
                ("OFI & Payment", "Matched 69-col CSV uploaded to OFI → AP invoice auto-created (no approval workflow). Payment via HSBC: (1) Standard 90-day, (2) Vendor Financing (~30-day to supplier, Tesco pays HSBC at 90-day), (3) Letter of Credit (Bangladesh). IMS data shared with Customs team daily."),
            ],
        },
        {
            "title": "§3.4.2 Freight Carrier Self-Billing (Sub-Process A)",
            "color": C_RED,
            "systems": "MS Access DB · Rolling File (Excel) · Oracle Fusion · Tungsten Network",
            "steps": [
                ("OTM File → MS Access (Steps A1-A2)", "Daily OTM Inbound All File received via shared mailbox and folder. Analyst manually uploads to MS Access Database. Minor format adjustments + A&A data upload. No automated OTM→MS Access integration."),
                ("Monday Extraction (Step A3)", "Every Monday: Analyst runs extraction query in MS Access per carrier (CMA, MSC, Maersk, LMN, HMN). File contains: container numbers, departure dates, CBM, container type, charge codes, computed amounts (Freight, BAF, Origin THC, Haulage, Dest THC, SCG, GOH, ancillaries)."),
                ("Rolling File (Step A4)", "Cleaned weekly data pasted into Excel Rolling File — single source of truth for all payment tracking. Tracks: container numbers, departure dates, carrier, charges per currency, Carrier Confirmation Status (default: No), Payment Status (default: No). No system backup."),
                ("Carrier Validation (Steps A5-A6)", "Analyst emails invoicing file to carrier. Carrier validates against own records (~80% match first time). Discrepancies resolved against Rate Card (quarterly Excel). Once agreed, Rolling File updated: Cost Agreed = YES."),
                ("Friday PO Raise (Step A7)", "Every Friday: filter Rolling File (Cost Agreed=YES + arrived this week + unpaid). Grouped by currency: USD (origin), GBP (UK dest), EUR (CE dest). ALL POs under Tesco Stores Ltd (TSL) entity 1002. Purchase Requisition → Cost Centre Owner approves → Oracle Fusion auto-generates PO (P1002-XXXXXX)."),
                ("Tungsten & Payment (Steps A9-A11)", "Carrier submits invoice via Tungsten portal against PO. Tungsten validates (PO exists, currency match, value ≤ PO). Invoice auto-flows to Oracle Fusion Payables after ~24 hours. AP Invoice Team pays on agreed terms: 30, 40, or 60 days. Rolling File updated when payment confirmed."),
            ],
        },
        {
            "title": "§3.5 AR & Intercompany Billing",
            "color": C_VIOLET,
            "systems": "Oracle Financials 11i · RIMS · Oracle R12",
            "steps": [
                ("AR Auto-Creation", "Once AP invoice created in OFI, system immediately creates AR invoice from TISL to destination entity: TS UK (UK), Tesco ROI (Ireland), or TICB (Central Europe). One AR invoice per AP invoice header, same multi-line structure."),
                ("Commission Invoice", "TISL generates Commission Invoice per shipment: 1.5% (third-way suppliers), 3.5% (standard via Tesco FF), 4.25% (specific categories). Product AR Invoice + Commission Invoice = complete AR billing pack."),
                ("UK/ROI Routing", "Oracle Fusion AR (automated). Invoice data flows via outbound EDI to UK/ROI financial systems. AR settlement via standard Fusion flows. No workflow approval (receivables)."),
                ("CE (TICB) Routing", "AR invoices manually keyed into RIMS (Retail Invoice Management System) from Oracle output file. RIMS pushes to Oracle R12. Settlement via R12 and CE banking. TICB AR invoices prefix '26...' IMS/ISI customs documentation transmitted daily."),
            ],
        },
        {
            "title": "§3.6 Customs & Duty",
            "color": C_GREEN,
            "systems": "OTM (CSS) · ISOS (IMS) · NBS · WTA · CM-UK · DDA",
            "steps": [
                ("CSS from OTM → WTA", "OTM auto-generates Customs Summary Sheet (CSS) per active shipment: container numbers, PO refs, transport mode, vessel/voyage, ETA, carton count/weight. CSS auto-sent to clearing agent WTA days before arrival. Without CSS, WTA cannot begin SFD preparation."),
                ("IMS from AP → Customs", "IMS (Invoice Matching Status) generated from ISOS + OTM after invoice processing (~7 days post departure). AP sends daily IMS packs to Customs team: IMS Excel extract + AP + AR invoice copies. Shared before overnight batch."),
                ("SFD at UK Border", "WTA uses CSS + IMS to prepare Simplified Frontier Declaration (SFD). Both inputs mandatory. Missing IMS → container held at port (demurrage risk). Tesco AEO/SCDP authorisation → near-automatic HMRC clearance. SDI deadline: 10th of following month."),
                ("F&F Clothing — CW", "Customs Warehousing: goods enter bonded warehouse duty-free. Duty paid only when stock leaves warehouse to stores. WMS (Denver) → CSG → CM-UK updates stock. SFD still required for clothing."),
                ("Duty Rates & Accrual", "OTM sends weekly HS code extracts to NBS. NBS provides duty rates, origin rules, preference rules per product. Accrual = Duty Rate × Customs Value × Quantity → posted to GL."),
                ("DDA Payment", "TISL pays customs duty monthly via Duty Deferment Account (DDA). Payment on 16th of month after import (Home) or after store delivery (F&F). Documentation retained 7 years."),
            ],
        },
    ]

    for proc in processes:
        story.append(Paragraph(proc['title'], S['section_h']))
        story.append(Paragraph(f"<b>Systems:</b> {proc['systems']}", S['caption']))
        story.append(hr(proc['color'], 0.5))
        for step_name, step_desc in proc['steps']:
            story.append(Paragraph(f"<b>▸ {step_name}</b>", S['sub_h']))
            story.append(Paragraph(step_desc, S['body']))

    story.append(PageBreak())

    # ════════════════════════════════════════════════════════
    # PAGE — RISKS & PAIN POINTS
    # ════════════════════════════════════════════════════════
    story.append(Paragraph("Key Risks & Pain Points (Document-Identified)", S['section_h']))
    story.append(hr(colors.HexColor("#FCA5A5"), 0.5))

    risks = [
        ("RISK 1 — MS Access Database (Single Point of Failure)",
         "MS Access is not a supported Tesco technology. No current employee knows how to maintain or modify it "
         "(originally built by a predecessor 5+ years ago). It is the core computation engine for the entire "
         "weekly freight self-billing cycle. No replacement plan exists."),
        ("RISK 2 — No Freight Audit Process",
         "Despite complexity and variability of freight charges, there is effectively no formal freight audit. "
         "POs are raised and paid without verifying container arrival (no goods receipt check). "
         "Payments made for unverified deliveries. No 3-way match for freight invoices."),
        ("RISK 3 — Late Freight Cost Accruals",
         "Freight costs are accrued only when containers arrive at the DC — not at shipment departure. "
         "For Far East origins, transit is 30+ days, resulting in financial under-reporting during transit. "
         "Accrual vs actual variance not tracked per container or BL. "
         "Quote (Mathew Butcher): 'The current process is broken. We should be accruing at the point of shipment.'"),
        ("RISK 4 — Manual Rate Card Distribution",
         "Rate cards distributed via email (Excel). No version-controlled system of record. "
         "Self-Billing team may work from outdated rate cards if email updates are missed. "
         "Rate card version mismatch is a documented source of incorrect freight charge calculations. "
         "Approx. 10-15 rate card updates per carrier per year."),
        ("RISK 5 — Bulk PO Granularity",
         "One consolidated PO raised for all containers arriving in a week. Carriers invoice per Bill of Lading. "
         "PO-to-invoice reconciliation at bulk level — no visibility at container or BL level. "
         "Cannot accrue freight costs at point of shipment (best practice)."),
        ("RISK 6 — Customs Data Accuracy",
         "Incorrect freight charges (rate card mismatches, unapproved surcharges) affect the freight costs "
         "declared to HMRC for duty valuation. Under- or over-declaration of freight costs has legal and "
         "financial consequences for Tesco. IMS errors directly affect duty calculation."),
        ("RISK 7 — ISOS Cancellation Invisible to LM",
         "When ISOS cancels a PO due to factory non-compliance, LM does NOT receive the cancellation status. "
         "Buyers remain unaware their PO has been blocked, creating process gaps and potential supply chain disruption."),
        ("RISK 8 — Rolling File Key-Person Dependency",
         "The Excel Rolling File is the operational master record for all freight payment tracking. "
         "No system backup. ISOS access by Self-Billing team limited to one person (one weekly download). "
         "Key-person dependency risk throughout the freight billing process."),
    ]

    for risk_title, risk_desc in risks:
        story.append(Paragraph(f"⚠ {risk_title}", ParagraphStyle('risk_t', fontName='Helvetica-Bold',
            fontSize=9.5, textColor=colors.HexColor("#FCA5A5"), spaceBefore=8, spaceAfter=2)))
        story.append(Paragraph(risk_desc, S['body']))
    story.append(Spacer(1, 0.4*cm))

    # ════════════════════════════════════════════════════════
    # PAGE — STAKEHOLDERS
    # ════════════════════════════════════════════════════════
    story.append(PageBreak())
    story.append(Paragraph("Stakeholders & Responsibilities (§4)", S['section_h']))
    story.append(hr(C_TEAL, 0.5))

    stakeholders = [
        ["Stakeholder / Team", "Responsibilities"],
        ["SSUP Team", "Supplier Set-Up Support: due diligence, document collection, NeoGrid task management, supplier lifecycle management."],
        ["MDM Team", "Master Data Management: EQOS supplier/factory creation and amendment via NeoGrid."],
        ["Self-Billing Analyst (TISL)", "End-to-end carrier/FF self-billing: OTM file upload, MS Access extraction, Rolling File maintenance, carrier email validation, Oracle Fusion PO raising, Transportin TICB extraction, ISOS Master Supplier download."],
        ["Self-Billing Finance Lead", "Process oversight for TISL self-billing; Oracle Fusion PO and intercompany query escalation."],
        ["Finance AP Team", "Invoice matching (3-way match via MS Access), cost validation, OFI AP posting, DQ report distribution, IMS sharing with Customs."],
        ["Finance AR Team", "Intercompany AR billing from OFI; CE manual RIMS keying."],
        ["Customs & Tax Team", "Duty calculation, SFD/SDI management, WTA liaison, duty deferment account management."],
        ["Procurement Team (Mathew Butcher / Samit Bera)", "Freight rate tender, carrier negotiation, rate card management and distribution."],
        ["Operations Team (John Finch)", "Books shipment space against agreed rate cards; OTM data population."],
        ["Ocean Carriers (CMA, MSC, Maersk, LMN, HMN)", "Validate self-billing invoicing file; confirm charges; submit formal invoices via Tungsten."],
        ["Freight Forwarders (DHL + others)", "Send IV0 to ISOS; trigger shipment milestones SM1; validate freight forwarder fees."],
        ["WTA (Clearing Agent)", "Receives CSS from OTM + IMS from Customs team; prepares and files Simplified Frontier Declarations."],
        ["Finance Controller, Intercompany", "Intercompany freight cost recharge between TSL (Oracle Fusion) and CE (Oracle R12)."],
        ["Global Logistics Team", "Commercial PO prioritisation decisions; sends ~3-4 prioritisation requests/week to Self-Billing."],
    ]

    skt = Table(stakeholders, colWidths=[5*cm, 12*cm])
    skt.setStyle(TableStyle([
        ('FONTNAME',(0,0),(-1,-1),'Helvetica'),
        ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
        ('FONTSIZE',(0,0),(-1,-1),8),
        ('TEXTCOLOR',(0,0),(-1,0),C_DARK),
        ('BACKGROUND',(0,0),(-1,0),C_TEAL),
        ('TEXTCOLOR',(0,1),(-1,-1),C_WHITE),
        ('TEXTCOLOR',(0,1),(0,-1),C_TEAL),
        ('FONTNAME',(0,1),(0,-1),'Helvetica-Bold'),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[C_PANEL, C_BG]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),3),
        ('BOTTOMPADDING',(0,0),(-1,-1),3),
        ('BOX',(0,0),(-1,-1),0.5,C_GREY),
        ('LINEBELOW',(0,0),(-1,-2),0.25,C_GREY),
    ]))
    story.append(skt)

    story.append(Spacer(1, 0.6*cm))
    story.append(hr(C_GREY))
    story.append(Paragraph(
        f"Report generated: {datetime.datetime.now().strftime('%d %B %Y %H:%M')} · "
        "Source: GLO_Finance_ASIS_Final.docx · "
        "Interactive diagram: GLO_Finance_ASIS_ProcessMap_v3.html",
        S['caption']))

    doc.build(story)
    print("PDF saved: " + str(OUTPUT))

if __name__ == '__main__':
    build_pdf()
