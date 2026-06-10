"""
Generate GLO_Finance_P2_Interactive.html
  — Fully interactive P2 system-lane diagram with click-to-reveal detail panels.

Also writes GLO_Finance_P2_Voiceover.txt — professional client presentation script.
"""

import json
from pathlib import Path

BASE = Path(r"c:\Users\prabhakargupta\Downloads\dream\test")
OUT_HTML  = BASE / "GLO_Finance_P2_Interactive.html"
OUT_VOICE = BASE / "GLO_Finance_P2_Voiceover.txt"

# ══════════════════════════════════════════════════════════════════════════════
#  ELEMENT DATA  (same geometry as P2, + full 'detail' + 'connections' fields)
# ══════════════════════════════════════════════════════════════════════════════
LANES = [
    {'id':'ssup',      'label':'SSUP Portal\n/ NeoGrid',         'fn':'Supplier Onboarding Team',  'color':'#00E5C0','y_top':80, 'y_bot':210},
    {'id':'eqos',      'label':'EQOS',                           'fn':'Master Data Management',    'color':'#1AE0BE','y_top':210,'y_bot':340},
    {'id':'lm',        'label':'LM / MM\nSystem',                'fn':'Buyers (PO Creation)',      'color':'#4FB3FF','y_top':340,'y_bot':470},
    {'id':'isos',      'label':'ISOS',                           'fn':'Finance & PO Validation Hub','color':'#7B9FFF','y_top':470,'y_bot':600},
    {'id':'otm',       'label':'Oracle TM\n(OTM)',               'fn':'Logistics & Planning',      'color':'#A78BFA','y_top':600,'y_bot':730},
    {'id':'biztalk',   'label':'BizTalk / EDI',                  'fn':'Integration Layer (IT)',    'color':'#C4B5FD','y_top':730,'y_bot':860},
    {'id':'documentum','label':'Documentum',                     'fn':'Document Management (AP)',  'color':'#FFD04A','y_top':860,'y_bot':990},
    {'id':'msaccess',  'label':'MS Access DB\n(Self-Billing)',   'fn':'TBS Billing Analyst',       'color':'#FF6B6B','y_top':990,'y_bot':1120},
    {'id':'ofi',       'label':'Oracle\nFinancials 11i',         'fn':'AP / AR Finance',           'color':'#FF9E5E','y_top':1120,'y_bot':1250},
    {'id':'fusion',    'label':'Oracle Fusion\n(Procurement/AR)','fn':'Finance / Procurement',     'color':'#C57BFF','y_top':1250,'y_bot':1380},
    {'id':'tungsten',  'label':'Tungsten Network',               'fn':'eInvoicing Portal',         'color':'#52E67A','y_top':1380,'y_bot':1510},
    {'id':'wta',       'label':'WTA Portal\n/ HMRC',            'fn':'Customs Clearance Agent',   'color':'#38C6FF','y_top':1510,'y_bot':1640},
    {'id':'nbs',       'label':'NBS / DDA',                     'fn':'Duty Management (Finance)', 'color':'#5DDDAA','y_top':1640,'y_bot':1770},
]

PHASES = [
    {'label':'Supplier\nSetup',          'x_start':240, 'x_end':620,  'color':'rgba(0,229,192,.07)'},
    {'label':'PO &\nCompliance',         'x_start':620, 'x_end':1040, 'color':'rgba(79,179,255,.07)'},
    {'label':'Shipment\n& Booking',      'x_start':1040,'x_end':1430, 'color':'rgba(167,139,250,.07)'},
    {'label':'Invoice\nReceipt & Prep',  'x_start':1430,'x_end':1850, 'color':'rgba(255,208,74,.06)'},
    {'label':'Cost\nValidation',         'x_start':1850,'x_end':2260, 'color':'rgba(255,107,107,.06)'},
    {'label':'Billing &\nPO Raise',      'x_start':2260,'x_end':2670, 'color':'rgba(197,123,255,.06)'},
    {'label':'AR &\nSettlement',         'x_start':2670,'x_end':3050, 'color':'rgba(82,230,122,.06)'},
    {'label':'Customs\n& Duty',          'x_start':3050,'x_end':3530, 'color':'rgba(56,198,255,.06)'},
]

ELEMS = [
    # ── SSUP Portal / NeoGrid ────────────────────────────────────────────────
    {'id':'ssup_coll','lane':'ssup','cx':420,'type':'box','mode':'manual',
     'label':'Collect & Upload\nSupplier Documents','sys':'SSUP Portal / NeoGrid',
     'detail':'The SSUP (Supplier Set-Up Support) team is the entry point for all new supplier and factory onboarding. They collect a mandatory document pack: set-up form, business rationale, bank details (sort code, account number, currency), company letterhead, and contact information. All tasks and documents are uploaded and tracked in the NeoGrid portal, which assigns tasks to the MDM team for validation. Until documents are complete in NeoGrid, no EQOS record can be created and no POs can be raised against that supplier.',
     'connections':['→ EQOS (creates supplier record)']},

    # ── EQOS ─────────────────────────────────────────────────────────────────
    {'id':'eqos_create','lane':'eqos','cx':500,'type':'out','mode':'mixed',
     'label':'Validate & Create\nSupplier/Factory Record','sys':'EQOS',
     'detail':'EQOS is Tesco\'s master data system for supplier and factory management. MDM performs two validation types: for existing suppliers — EQOS ID, address, bank details and contacts are verified; for new suppliers — bank documents, company letterhead, sort code, account number, currency and contacts are all validated before creation. Lead and manager approvals are required. Critically, factory addresses cannot be edited once created — a new factory ID is required for address changes. One EQOS record per supplier-factory combination. A single factory can be linked to multiple suppliers.',
     'connections':['← SSUP Portal (document upload)','→ ISOS (15-min compliance feed)','→ Oracle 11i OFI (weekly vendor master batch)']},

    {'id':'eqos_feed','lane':'eqos','cx':820,'type':'box','mode':'auto',
     'label':'Real-time Compliance\nFeed to ISOS (15-min)','sys':'EQOS → ISOS',
     'detail':'EQOS pushes supplier compliance and factory approval status to ISOS every 15 minutes via an automated interface. ISOS treats this feed as the master source of truth for supplier compliance during PO validation. If a factory\'s compliance flag changes in EQOS, ISOS reflects this within 15 minutes — meaning a PO that was valid at 9:00 AM could become blocked by 9:15 AM if a factory audit fails. Separately, EQOS sends a weekly batch interface to Oracle Financials 11i (OFI) to create or update vendor master records in the AP module.',
     'connections':['→ ISOS (PO compliance validation)','→ Oracle 11i OFI (weekly batch)']},

    # ── LM / MM System ───────────────────────────────────────────────────────
    {'id':'lm_po','lane':'lm','cx':720,'type':'box','mode':'manual',
     'label':'Buyer Creates\nPurchase Order','sys':'LM / MM System',
     'detail':'Buyers create product Purchase Orders in LM (the PO Creation System). Clothing POs originate in MM (Merchandise Management) and are passed to LM before transmission to ISOS. PO types vary by route: PO1 (UK inbound), PO3 (outbound to OTM), PO5 (LM UK home range), PO6 (LM CE clothing and CE home). Transmission from LM/MM to ISOS occurs via BizTalk or XCOM depending on PO type. Critically, LM does NOT receive cancellation status back from ISOS — so buyers are unaware when a PO is blocked due to compliance failure.',
     'connections':['→ ISOS (PO transmitted via BizTalk)','→ BizTalk (integration middleware)']},

    # ── ISOS ─────────────────────────────────────────────────────────────────
    {'id':'isos_valid','lane':'isos','cx':860,'type':'box','mode':'auto',
     'label':'Validate PO:\nCompliance & Cost','sys':'ISOS',
     'detail':'ISOS is the central finance and PO validation hub. Upon receiving a PO from LM/MM, ISOS performs four automatic validations: (1) Is the supplier active in EQOS? (2) Is the factory approved in EQOS? (3) Is the cost price non-zero? (4) Is the delivery date valid? If a factory is non-compliant, ISOS silently sets the PO status to "Cancelled" — this is NOT communicated back to LM or the buyer. ISOS is the only system that retains the full PO amendment history; LM does not store this.',
     'connections':['← LM/MM (PO received)','← EQOS (compliance status)','→ ISOS Enrich (next step)']},

    {'id':'isos_enrich','lane':'isos','cx':1060,'type':'box','mode':'auto',
     'label':'Enrich PO &\nAssign FF/LSP','sys':'ISOS',
     'detail':'Once validated, ISOS enriches the PO with freight and logistics mapping data. It assigns a Freight Forwarder (FF) and Logistics Service Provider (LSP) based on ISOS internal transport lane mapping tables. ISOS determines the transport mode (sea/air/road). Only the latest approved version of a PO is processed — older versions arriving late are automatically rejected. The enriched PO is then transmitted to OTM.',
     'connections':['→ OTM (enriched PO for distribution)','→ ISOS SM processing (next stage)']},

    {'id':'isos_sm','lane':'isos','cx':1240,'type':'box','mode':'auto',
     'label':'SM1/SM2 Processing\n& Version Filtering','sys':'ISOS',
     'detail':'Shipment Milestone 1 (SM1) is sent by the Freight Forwarder when goods are handed over (FOB). ISOS receives SM1 via BizTalk and applies version filtering — only the highest version number is processed; out-of-sequence updates are rejected. ISOS stores booking, container, and Bill of Lading details. It then generates SM2 and sends it to OTM, which becomes the system of record for planned vs actual shipment tracking. If SM data fails validation, the logistics team coordinates with FF to resolve.',
     'connections':['← BizTalk (SM1 from Freight Forwarder)','→ OTM (SM2 shipment confirmation)']},

    {'id':'isos_78col','lane':'isos','cx':1640,'type':'out','mode':'auto',
     'label':'Generate 78-Column\nExtract (Approved POs)','sys':'ISOS',
     'detail':'The 78-column extract is the pivotal data output that drives the entire invoice matching and payment process. ISOS merges four data sources into this extract: PO data (from LM/OTM), Supplier Master (from EQOS), Shipment Data (from OTM), and FF invoice values (from IV0). ONLY POs that have passed the OTM Business Monitor cost validation appear in this extract. If 100 invoice PDFs have been received but ISOS produces only 80 lines, the remaining 20 are either in price mismatch in Business Monitor, or missing IV0/shipment data.',
     'connections':['← BizTalk/IV0 (FF invoice values needed)','→ BizTalk/EDI (78→69 column conversion)']},

    {'id':'isos_cost','lane':'isos','cx':2050,'type':'box','mode':'auto',
     'label':'2-Way Cost Check:\nPO vs IV0 Value','sys':'ISOS / OTM BM',
     'detail':'ISOS performs an automatic 2-way cost validation: it compares the PO cost (from LM) against the Supplier Invoice cost (from IV0, routed via BizTalk). This validation is fully automated — no manual intervention. If PO cost is less than the supplier invoice cost, a Cost Exception appears in the OTM Business Monitor. ISOS will NOT generate the 78-column extract for that PO until the Business Monitor exception is resolved by the buyer. This creates a dependency: delayed buyer resolution = delayed AP invoice = delayed payment.',
     'connections':['← ISOS 78-col (blocked until resolved)','→ OTM Business Monitor (exception raised)','→ BizTalk/EDI (approved → 78-col export)']},

    # ── OTM ──────────────────────────────────────────────────────────────────
    {'id':'otm_po','lane':'otm','cx':930,'type':'box','mode':'auto',
     'label':'Enrich & Distribute\nPO to Supplier (PDF)','sys':'OTM',
     'detail':'OTM (Oracle Transportation Management) receives the enriched PO from ISOS and further enhances it. OTM issues a PDF copy of the PO to the supplier via email. Importantly, the PO PDF sent from OTM does NOT explicitly include the Freight Forwarder name — only transport mode and port details are shown. OTM also sends the enhanced PO back to ISOS. This bidirectional flow ensures both systems are aligned on PO versions.',
     'connections':['← ISOS (enriched PO)','→ Supplier (PDF via email)','→ BizTalk (PO transmission)']},

    {'id':'otm_sm','lane':'otm','cx':1230,'type':'out','mode':'auto',
     'label':'Shipment Booking\n& Milestone Tracking','sys':'OTM',
     'detail':'OTM becomes the system of record for all shipment tracking. It receives SM2 from ISOS (shipment confirmed) and stores: booking details, container numbers, Bill of Lading data, shipment dates, and milestone timestamps. OTM then sends SM3 (system-to-system update) to Data Warehouse, MM and LM, and SM4 via BizTalk back to the Freight Forwarder. OTM also publishes ETD/ETA information used by the Customs team to predict arrival windows.',
     'connections':['← ISOS (SM2 shipment confirmation)','→ BizTalk (SM4 to Freight Forwarder)','→ OTM Daily File (next)']},

    {'id':'otm_file','lane':'otm','cx':1500,'type':'out','mode':'auto',
     'label':'Daily Inbound\nAll File Generated','sys':'OTM',
     'detail':'OTM automatically generates the Daily Inbound All File (also called the Inbound Report) every day. It is delivered to the TBS Self-Billing Team in Bangalore via shared mailbox (~12:50 PM) and shared folder. Contents: shipment details, carrier name, container type (20ft/40ft/40HC/45ft), origin and destination ports, ETA, ETD, and container counts. This is the PRIMARY and ONLY system-generated input into the freight self-billing process. Without it, the Self-Billing team cannot begin weekly invoice extraction.',
     'connections':['→ MS Access DB (manual upload by TBS team)','→ OTM CSS (triggers pre-arrival data)']},

    {'id':'otm_css','lane':'otm','cx':3100,'type':'out','mode':'auto',
     'label':'CSS Auto-sent\nto WTA (Pre-Arrival)','sys':'OTM → WTA Portal',
     'detail':'OTM automatically generates a Customs Summary Sheet (CSS) for every active shipment. The CSS contains: container number, PO numbers linked to the container, mode of transport, vessel and voyage details, estimated arrival dates, and carton count/weight. CSS is automatically sent to Tesco\'s clearing agent (WTA) several days before vessel arrival, giving WTA time to prepare the Simplified Frontier Declaration (SFD). Without CSS, WTA cannot begin clearance preparation — this is a hard dependency.',
     'connections':['→ WTA Portal (CSS enables SFD preparation)']},

    {'id':'otm_nbs','lane':'otm','cx':3360,'type':'box','mode':'auto',
     'label':'HS Code Extract\nto NBS (weekly)','sys':'OTM → NBS',
     'detail':'OTM contains the Commodity Code (HS code/Tariff code) for every product in a shipment. OTM sends weekly commodity code extracts to NBS (New Buying System). NBS uses these to assign the correct duty rate, origin rules, and preference rules for each HS code. NBS then becomes the duty rate master for Finance. Incorrect HS codes in OTM directly and immediately affect duty calculation accuracy — a 1% error in HS code assignment can represent significant financial liability given Tesco\'s import volumes.',
     'connections':['→ NBS/DDA (duty rate assignment)']},

    # ── BizTalk / EDI ────────────────────────────────────────────────────────
    {'id':'bt_po','lane':'biztalk','cx':820,'type':'box','mode':'auto',
     'label':'Transmit PO to OTM\n& Supplier (BizTalk)','sys':'BizTalk / XCOM',
     'detail':'BizTalk is the primary enterprise integration middleware at Tesco. For PO transmission, BizTalk routes POs from LM/MM → ISOS → OTM and from OTM → Supplier. Different PO types use different transmission protocols: BizTalk for most routes, XCOM for specific clothing routes. BizTalk handles message transformation, routing rules, and retry logic. It maintains an audit trail of all transmitted messages, though support teams must intervene manually for technical failures.',
     'connections':['← LM/MM (PO received for routing)','→ OTM (PO distributed)','→ Supplier (via OTM)']},

    {'id':'bt_sm','lane':'biztalk','cx':1230,'type':'box','mode':'auto',
     'label':'Route Shipment\nMilestones (SM1-SM4)','sys':'BizTalk',
     'detail':'BizTalk is the backbone for all Shipment Milestone messaging. SM1 (FOB handover) is received from the Freight Forwarder\'s system via BizTalk and routed to ISOS. SM2 (shipment confirmed) flows from ISOS to OTM via BizTalk. SM3 (system update) is sent to Data Warehouse/MM/LM. SM4 (carrier acknowledgment) is sent back to the Freight Forwarder via BizTalk. A single shipment may have multiple SM1 versions — ISOS filters by version number and only processes the latest, rejecting earlier out-of-sequence updates.',
     'connections':['← Freight Forwarder (SM1)','→ ISOS (SM milestone data)','→ OTM (SM routing)']},

    {'id':'bt_iv0','lane':'biztalk','cx':1570,'type':'box','mode':'auto',
     'label':'Route IV0 e-Invoice\nfrom FF to ISOS','sys':'BizTalk',
     'detail':'IV0 is an electronic invoice message that Freight Forwarders send to ISOS via BizTalk. The IV0 contains supplier invoice values, shipment references, and booking data that ISOS uses to populate the 78-column extract and perform the 2-way cost check. If IV0 is missing for a shipment, the corresponding ISOS 78-column line will not be generated, and the AP team flags it as missing data. The AP team shares a Business Monitor fallout report with FF each morning specifically tracking missing IV0s.',
     'connections':['← Freight Forwarder (IV0 electronic invoice)','→ ISOS (enables 78-col extract)']},

    {'id':'bt_edi','lane':'biztalk','cx':2050,'type':'out','mode':'auto',
     'label':'EDI: 78-col → 69-col\nFormat Conversion','sys':'EDI',
     'detail':'The EDI module (Electronic Data Interchange) within the BizTalk/integration layer automatically converts the 78-column ISOS extract into a 69-column OFI-compatible CSV format. The 8-9 removed fields are not used by Oracle Financials 11i (OFI). This conversion is fully automated and format-deterministic. The resulting 69-column CSV is what the AP team uses in MS Access for the 3-way match before uploading to OFI. Any field mapping errors at this stage propagate directly into the AP invoice.',
     'connections':['← ISOS (78-col extract)','→ MS Access (69-col for 3-way match)']},

    # ── Documentum ───────────────────────────────────────────────────────────
    {'id':'doc_index','lane':'documentum','cx':1640,'type':'box','mode':'manual',
     'label':'Manually Index PDF\nInvoice (6-7 Fields)','sys':'Documentum',
     'detail':'Suppliers send PDF invoices separately from the IV0 electronic message — these two channels are completely independent. The PDF is stored in Documentum (Tesco\'s document management system), but none of the fields are auto-extracted. The AP team manually keys in 6-7 mandatory fields: PO number, Currency, Supplier number, Quantity, Total Invoice Amount, Invoice number. The team also manually cross-checks the Invoice against the Packing List (quantity check) during indexing. Documentum then produces an Excel extract with the indexed fields, which is used in the MS Access 3-way match. This is one of the highest-volume manual activities in the AP process.',
     'connections':['→ MS Access (indexed invoice fields for 3-way match)']},

    # ── MS Access DB ─────────────────────────────────────────────────────────
    {'id':'ms_upload','lane':'msaccess','cx':2100,'type':'box','mode':'manual',
     'label':'Upload OTM File &\nRun Weekly Extract','sys':'MS Access DB',
     'detail':'The Self-Billing Analyst manually uploads the OTM Daily Inbound All File into the MS Access Database — the local self-billing tool. There is NO automated integration between OTM and MS Access. Every Monday, the analyst runs the extraction query to produce the weekly invoicing file, with separate extraction per carrier: CMA, MSC, Maersk, LMN, HMN. Two additional carriers require fully manual invoicing not driven by the database at all. This weekly manual upload is a critical single point of failure — if the analyst is absent, the entire freight billing cycle stalls.',
     'connections':['← OTM (Daily All File via shared mailbox)','→ Rolling File (cleaned data)']},

    {'id':'ms_roll','lane':'msaccess','cx':2460,'type':'box','mode':'manual',
     'label':'Rolling File: Track\nCharges & Agreements','sys':'MS Access DB',
     'detail':'The Rolling File is a master Excel workbook maintained as the single source of truth for all weekly freight invoicing data. It tracks: container numbers, departure dates, carrier name, charge amounts per currency (USD origin, GBP UK, EUR CE), Carrier Confirmation Status (default: No), and Payment Status (default: No). Every Friday, the analyst filters the Rolling File by: Cost Agreed = YES, Payment Status = No, Container arrived this week. This filtered dataset drives the Oracle Fusion PO creation. CRITICAL RISK: No system backup exists for this file. Loss of the Rolling File = loss of the entire freight billing history.',
     'connections':['→ Oracle Fusion (PO requisition for agreed costs)','→ Oracle 11i OFI (matched data → AP invoice via EDI)']},

    # ── Oracle Financials 11i (OFI) ──────────────────────────────────────────
    {'id':'ofi_ap','lane':'ofi','cx':2810,'type':'out','mode':'auto',
     'label':'AP Invoice\nAuto-Created','sys':'Oracle Financials 11i',
     'detail':'Once the AP team completes the 3-way match in MS Access (69-column EDI output vs Documentum indexed invoice fields), the matched 69-column CSV is uploaded to Oracle Financials 11i (OFI). OFI automatically generates the AP invoice — no workflow approval is required for product invoices. Three payment mechanisms are then available: (1) Standard 90-day payment — invoices selected in batch, Manager + 2nd-level approval, released to HSBC. (2) Vendor Financing — supplier receives ~30-day payment from HSBC; Tesco pays HSBC at 90 days. (3) Letter of Credit — common for Bangladesh suppliers, raised within 7 days.',
     'connections':['← MS Access / EDI (69-col matched data)','→ Oracle 11i AR (triggers AR auto-creation)','→ WTA (IMS data sent for customs)']},

    {'id':'ofi_ar','lane':'ofi','cx':3010,'type':'out','mode':'auto',
     'label':'AR Invoice\nAuto-Created (TISL)',
     'sys':'Oracle Financials 11i',
     'detail':'When an AP invoice is created in OFI, the system immediately and automatically creates a corresponding AR invoice from TISL (Tesco International Sourcing Ltd) to the destination entity. The destination is determined by PO and shipment details: TS UK, Tesco ROI, or TICB (Central Europe). Each AP invoice header produces exactly one corresponding AR invoice with the same multi-line structure. Additionally, TISL generates a Commission Invoice for every cycle — commission percentage depends on supplier type: 1.5% (third-way suppliers), 3.5% (standard), or 4.25% (specific categories). The AR invoice package (product AR + commission) is then routed based on destination.',
     'connections':['← OFI AP (AP invoice auto-triggers AR)','→ Oracle Fusion AR (UK/ROI route)','→ WTA Portal (IMS customs data)']},

    # ── Oracle Fusion ────────────────────────────────────────────────────────
    {'id':'fusion_po','lane':'fusion','cx':2460,'type':'out','mode':'auto',
     'label':'Freight PO Raised\n(P1002-XXXXXX)','sys':'Oracle Fusion Procurement',
     'detail':'Every Friday, the Self-Billing Analyst creates a Purchase Requisition in Oracle Fusion for all freight costs where Cost Agreed = YES and Payment Status = No. All POs are raised under Tesco Stores Limited entity code 1002 (P1002-XXXXXX). Costs are grouped by currency: USD (origin charges), GBP (UK destination), EUR (CE destination). The Cost Centre Owner approves the requisition, and Oracle Fusion automatically generates the PO and emails it to the carrier. This is the carrier\'s authorisation to submit a formal invoice via Tungsten.',
     'connections':['← MS Access Rolling File (PO requisition data)','→ Tungsten Network (PO sent to carrier)']},

    {'id':'fusion_ar','lane':'fusion','cx':2870,'type':'box','mode':'auto',
     'label':'UK/ROI AR Automation\n& EDI to Financials','sys':'Oracle Fusion AR',
     'detail':'For UK and Tesco ROI destinations, AR invoice generation and settlement is fully automated in Oracle Fusion. Invoice data flows automatically from OFI through outbound EDI interfaces to UK and ROI financial systems. AR settlement follows standard AR flows in Oracle Fusion. AR invoices do not undergo workflow approvals as they represent receivables. Separately, Oracle Fusion Payables receives validated Tungsten freight invoices (~24 hours after submission) via a custom-built interface. Freight invoices appear with status "Validated" and are paid on due date per agreed payment terms (30, 40, or 60 days).',
     'connections':['← OFI AR (AR invoice for UK/ROI)','← Tungsten (validated freight invoice)','→ UK/ROI Financial Systems (EDI)']},

    # ── Tungsten Network ─────────────────────────────────────────────────────
    {'id':'tung_inv','lane':'tungsten','cx':2460,'type':'box','mode':'manual',
     'label':'Carrier Creates\nFormal eInvoice vs PO','sys':'Tungsten Network',
     'detail':'The carrier logs into the Tungsten Network portal using their credentials and creates a formal invoice referencing the Tesco Oracle Fusion PO number. The invoice amount must not exceed the PO value. Tungsten automatically validates three conditions: (1) PO number exists in Oracle Fusion, (2) invoice currency matches PO currency, (3) invoice value does not exceed PO value. In practice, 95%+ of submissions are 1 invoice to 1 PO — Tungsten charges per invoice submission, which financially incentivises carriers to consolidate. After ~24 hours, validated invoices automatically flow into Oracle Fusion Payables via a custom-built interface.',
     'connections':['← Oracle Fusion (PO reference for invoice creation)','→ Oracle Fusion Payables (validated invoice auto-received)']},

    # ── WTA Portal / HMRC ────────────────────────────────────────────────────
    {'id':'wta_sfd','lane':'wta','cx':3160,'type':'out','mode':'mixed',
     'label':'Prepare CSS+IMS &\nFile SFD at UK Border','sys':'WTA / HMRC (CHIEF/CDS)',
     'detail':'WTA (Tesco\'s UK clearing agent) requires BOTH CSS and IMS data to prepare the Simplified Frontier Declaration (SFD). CSS provides shipment/container level data from OTM. IMS (Invoice Matching Status) provides invoice-level value data from OFI/ISOS. Both are mandatory — if IMS is missing, WTA holds the container. For Home imports: Tesco operates under SCDP (Simplified Customs Declaration Procedure) — near-automatic HMRC clearance because Tesco is AEO (Authorised Economic Operator) authorised. For F&F Clothing: Customs Warehousing (CW) — goods enter bonded warehouse duty-free; duty is only paid when stock leaves warehouse to stores. Supplementary Declaration (SDI) is filed inland by the 10th of the following month.',
     'connections':['← OTM (CSS: shipment container data)','← OFI AR (IMS: invoice value data)','→ HMRC (CHIEF/CDS customs filing)']},

    # ── NBS / DDA ────────────────────────────────────────────────────────────
    {'id':'nbs_duty','lane':'nbs','cx':3240,'type':'box','mode':'auto',
     'label':'NBS: Duty Rates;\nAccrual Posted to GL','sys':'NBS / OFI GL',
     'detail':'NBS (New Buying System) receives the weekly HS code extract from OTM and fetches the correct duty rate, origin rules, and preference rules for each commodity code. NBS sends duty rate information into the QL (Quantity Ledger) Accrual process. The duty accrual formula is: Accrual = Duty Rate × Customs Value × Quantity. For Home imports, duty is accrued at import. For F&F Clothing (Customs Warehousing), duty is accrued when goods leave the warehouse to stores. WMS (Denver) → CSG (third party) → CM-UK updates customs warehouse stock the day after arrival. The accrual is posted to the General Ledger in OFI.',
     'connections':['← OTM (HS code extract)','→ OFI GL (duty accrual posting)','→ DDA (monthly duty payment)']},

    {'id':'dda_pay','lane':'nbs','cx':3440,'type':'out','mode':'auto',
     'label':'TISL Monthly Duty\nPayment via DDA','sys':'DDA / TISL',
     'detail':'TISL (Tesco International Sourcing Ltd) pays Customs Duty monthly through the Duty Deferment Account (DDA) — a HMRC-approved mechanism that allows duty to be deferred and paid once a month rather than at each import. Payment is made on the 16th of the month following import for Home goods, or the 16th after store delivery for F&F Clothing. Tesco is legally required to retain all customs documentation for 6 years (Tesco retains 7 years). The commission invoice from TISL is NOT part of Customs Value — TISL is classified as a buying agent, and commission is treated as a separate, non-dutiable invoice.',
     'connections':['← NBS (duty accrual calculated)','→ HMRC (DDA payment on 16th)']},
]

CONNS = [
    {'f':'isos_valid','fp':'r','t':'isos_enrich','tp':'l','type':'main','label':''},
    {'f':'isos_enrich','fp':'r','t':'isos_sm','tp':'l','type':'main','label':''},
    {'f':'isos_sm','fp':'r','t':'isos_78col','tp':'l','type':'main','label':''},
    {'f':'isos_78col','fp':'r','t':'isos_cost','tp':'l','type':'main','label':''},
    {'f':'otm_sm','fp':'r','t':'otm_file','tp':'l','type':'main','label':''},
    {'f':'otm_css','fp':'r','t':'otm_nbs','tp':'l','type':'main','label':''},
    {'f':'bt_po','fp':'r','t':'bt_sm','tp':'l','type':'main','label':''},
    {'f':'bt_sm','fp':'r','t':'bt_iv0','tp':'l','type':'main','label':''},
    {'f':'bt_iv0','fp':'r','t':'bt_edi','tp':'l','type':'main','label':''},
    {'f':'ofi_ap','fp':'r','t':'ofi_ar','tp':'l','type':'main','label':''},
    {'f':'nbs_duty','fp':'r','t':'dda_pay','tp':'l','type':'main','label':''},
    {'f':'ssup_coll','fp':'b','t':'eqos_create','tp':'t','type':'hand','label':'Doc upload'},
    {'f':'eqos_create','fp':'b','t':'isos_valid','tp':'t','type':'hand','label':'Compliance feed'},
    {'f':'lm_po','fp':'b','t':'isos_valid','tp':'t','type':'hand','label':'PO via BizTalk'},
    {'f':'isos_enrich','fp':'b','t':'otm_po','tp':'t','type':'hand','label':'PO to OTM'},
    {'f':'otm_po','fp':'b','t':'bt_po','tp':'t','type':'hand','label':'PO distributed'},
    {'f':'bt_sm','fp':'t','t':'isos_sm','tp':'b','type':'hand','label':'SM1 from FF'},
    {'f':'bt_iv0','fp':'t','t':'isos_cost','tp':'b','type':'hand','label':'IV0 to ISOS'},
    {'f':'isos_cost','fp':'b','t':'bt_edi','tp':'t','type':'hand','label':'78-col export'},
    {'f':'bt_edi','fp':'b','t':'ms_upload','tp':'t','type':'hand','label':'69-col CSV'},
    {'f':'doc_index','fp':'b','t':'ms_upload','tp':'t','type':'hand','label':'Indexed fields'},
    {'f':'ms_roll','fp':'b','t':'ofi_ap','tp':'t','type':'hand','label':'Matched data'},
    {'f':'ms_roll','fp':'b','t':'fusion_po','tp':'t','type':'hand','label':'PO requisition'},
    {'f':'fusion_po','fp':'b','t':'tung_inv','tp':'t','type':'hand','label':'PO to carrier'},
    {'f':'tung_inv','fp':'b','t':'fusion_ar','tp':'t','type':'hand','label':'Validated invoice'},
    {'f':'ofi_ar','fp':'b','t':'fusion_ar','tp':'t','type':'hand','label':'AR for UK/ROI'},
    {'f':'otm_file','fp':'t','t':'otm_css','tp':'b','type':'hand','label':'Triggers CSS'},
    {'f':'otm_css','fp':'b','t':'wta_sfd','tp':'t','type':'hand','label':'CSS data'},
    {'f':'ofi_ar','fp':'b','t':'wta_sfd','tp':'t','type':'hand','label':'IMS data'},
    {'f':'otm_nbs','fp':'b','t':'nbs_duty','tp':'t','type':'hand','label':'HS codes'},
]

CANVAS_W = 3570
CANVAS_H = 1770
LABEL_W  = 240
BW, BH, DW = 148, 46, 55

# ══════════════════════════════════════════════════════════════════════════════
#  BUILD HTML
# ══════════════════════════════════════════════════════════════════════════════
def build_interactive_html():
    # Pre-compute _cy for each element
    lmap = {l['id']:l for l in LANES}
    emap = {}
    for e in ELEMS:
        ln = lmap[e['lane']]
        e['_cy'] = (ln['y_top']+ln['y_bot'])/2 + e.get('cy_off',0)
        e['_lane'] = ln
        emap[e['id']] = e

    def get_port(e, p):
        cx,cy,t = e['cx'],e['_cy'],e['type']
        if t=='dia': return {'r':(cx+DW,cy),'l':(cx-DW,cy),'t':(cx,cy-DW),'b':(cx,cy+DW)}[p]
        w=148 if t=='exc' else BW; h=36 if t=='exc' else BH
        return {'r':(cx+w/2,cy),'l':(cx-w/2,cy),'t':(cx,cy-h/2),'b':(cx,cy+h/2)}[p]

    def bpath(fp,tp,typ):
        x1,y1=fp; x2,y2=tp
        if typ=='loop':
            lx=min(x1,x2)-52
            return f'M{x1},{y1} C{lx},{y1} {lx},{y2} {x2},{y2}'
        if typ=='no':
            return f'M{x1},{y1} C{x1},{y1+20} {x2},{y2-20} {x2},{y2}'
        if typ=='hand':
            dx=x2-x1; dy=y2-y1
            if abs(dx)<70:
                c1y=y1+dy*.35; c2y=y2-dy*.35
                return f'M{x1},{y1} C{x1},{c1y} {x2},{c2y} {x2},{y2}'
            c1x=x1+dx*.45; c2x=x2-dx*.45
            return f'M{x1},{y1} C{c1x},{y1} {c2x},{y2} {x2},{y2}'
        mx=(x1+x2)/2
        return f'M{x1},{y1} C{mx},{y1} {mx},{y2} {x2},{y2}'

    def hexrgb(h):
        h=h.lstrip('#'); return int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)

    CONN_C={'main':'rgba(255,255,255,.4)','yes':'#4ade80','no':'#f97316','loop':'#f97316','hand':'rgba(100,116,139,.9)'}
    MODE_C={'auto':'#4ade80','manual':'#f97316','mixed':'#94A3B8'}

    svg_lines = []
    s = svg_lines.append

    s(f'<svg id="mainsvg" xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}">')
    s('<defs>')
    for ct,cc in CONN_C.items():
        s(f'<marker id="arr-{ct}" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">')
        s(f'<path d="M1,1 L7,4 L1,7 Z" fill="{cc}"/></marker>')
    s('</defs>')
    s(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" fill="#03060F"/>')

    # Lane bands
    for ln in LANES:
        r,g,b = hexrgb(ln['color'])
        cy_l = (ln['y_top']+ln['y_bot'])//2
        s(f'<rect x="0" y="{ln["y_top"]}" width="{CANVAS_W}" height="{ln["y_bot"]-ln["y_top"]}" fill="rgba({r},{g},{b},.05)"/>')
        s(f'<line x1="0" y1="{ln["y_bot"]}" x2="{CANVAS_W}" y2="{ln["y_bot"]}" stroke="rgba(255,255,255,.06)"/>')
        s(f'<rect x="0" y="{ln["y_top"]}" width="3" height="{ln["y_bot"]-ln["y_top"]}" fill="{ln["color"]}"/>')
        s(f'<rect x="3" y="{ln["y_top"]}" width="{LABEL_W-3}" height="{ln["y_bot"]-ln["y_top"]}" fill="rgba(3,6,15,.85)"/>')
        lbl_lines = ln['label'].split('\n')
        n=len(lbl_lines)
        start_y = cy_l - (n-1)*9
        for i,ll in enumerate(lbl_lines):
            s(f'<text x="{LABEL_W//2+2}" y="{start_y+i*17}" text-anchor="middle" dominant-baseline="middle" font-size="10" font-weight="700" fill="{ln["color"]}" font-family="Inter,sans-serif">{ll}</text>')
        s(f'<text x="{LABEL_W//2+2}" y="{cy_l+14+(n-1)*9}" text-anchor="middle" dominant-baseline="middle" font-size="7" fill="rgba(255,255,255,.32)" font-family="Inter,sans-serif">{ln["fn"]}</text>')
        s(f'<line x1="{LABEL_W}" y1="{ln["y_top"]}" x2="{LABEL_W}" y2="{ln["y_bot"]}" stroke="rgba(255,255,255,.07)"/>')

    # Header
    s(f'<rect x="0" y="0" width="{CANVAS_W}" height="80" fill="rgba(3,6,15,.97)"/>')
    s(f'<line x1="0" y1="80" x2="{CANVAS_W}" y2="80" stroke="rgba(255,255,255,.08)"/>')
    s(f'<rect x="0" y="0" width="{LABEL_W}" height="80" fill="rgba(3,6,15,.96)"/>')
    s(f'<text x="{LABEL_W//2}" y="28" text-anchor="middle" dominant-baseline="middle" font-size="7.5" font-weight="700" fill="rgba(255,255,255,.4)" font-family="Inter,sans-serif">ERP / SYSTEM</text>')
    s(f'<text x="{LABEL_W//2}" y="44" text-anchor="middle" dominant-baseline="middle" font-size="6.5" fill="rgba(255,255,255,.22)" font-family="Inter,sans-serif">Business Function Below</text>')
    s(f'<text x="{LABEL_W//2}" y="60" text-anchor="middle" dominant-baseline="middle" font-size="6" fill="rgba(255,255,255,.18)" font-family="Inter,sans-serif">[A]=Auto  [M]=Manual</text>')

    phase_colors=['#00E5C0','#4FB3FF','#A78BFA','#FFD04A','#FF6B6B','#C57BFF','#52E67A','#38C6FF']
    for pi,ph in enumerate(PHASES):
        x=ph['x_start']; w=ph['x_end']-ph['x_start']
        s(f'<rect x="{x}" y="0" width="{w}" height="{CANVAS_H}" fill="{ph["color"]}"/>')
        s(f'<line x1="{ph["x_end"]}" y1="0" x2="{ph["x_end"]}" y2="{CANVAS_H}" stroke="rgba(255,255,255,.06)"/>')
        plines=ph['label'].split('\n')
        for i,pl in enumerate(plines):
            s(f'<text x="{x+w//2}" y="{26+i*17}" text-anchor="middle" dominant-baseline="middle" font-size="9" font-weight="700" fill="{phase_colors[pi]}" font-family="Inter,sans-serif">{pl}</text>')

    # Connections
    for cn in CONNS:
        fe=emap.get(cn['f']); te=emap.get(cn['t'])
        if not fe or not te: continue
        fp=get_port(fe,cn['fp']); tp=get_port(te,cn['tp'])
        ct=cn['type']; cc=CONN_C[ct]
        d=bpath(fp,tp,ct)
        s(f'<path d="{d}" fill="none" stroke="{cc}" stroke-width="1.3" marker-end="url(#arr-{ct})"/>')
        lbl=cn.get('label','')
        if lbl:
            mx=(fp[0]+tp[0])//2; my=(fp[1]+tp[1])//2
            s(f'<text x="{mx}" y="{my}" text-anchor="middle" dominant-baseline="middle" font-size="6.5" fill="{cc}" font-family="Inter,sans-serif">{lbl}</text>')

    # Elements (clickable)
    elem_data_js = {}
    for e in ELEMS:
        cx=e['cx']; cy=int(e['_cy']); t=e['type']
        mc=MODE_C.get(e.get('mode','auto'),'#4ade80')
        llines=e['label'].split('\n'); n=len(llines)
        elem_id = e['id']

        s(f'<g class="elem" data-id="{elem_id}" style="cursor:pointer">')
        if t=='dia':
            pts=f'{cx},{cy-DW} {cx+DW},{cy} {cx},{cy+DW} {cx-DW},{cy}'
            s(f'<polygon points="{pts}" fill="rgba(3,6,15,.92)" stroke="#F59E0B" stroke-width="1.4" class="elem-shape" data-id="{elem_id}"/>')
        elif t=='exc':
            s(f'<rect x="{cx-74}" y="{cy-18}" width="148" height="36" rx="4" fill="rgba(3,6,15,.92)" stroke="{mc}" stroke-width="1.4" class="elem-shape" data-id="{elem_id}"/>')
            s(f'<rect x="{cx-74}" y="{cy-18}" width="3" height="36" rx="2" fill="{mc}"/>')
        else:
            bstroke='#00E5C0' if t=='out' else e['_lane']['color']
            bsw='1.6' if t=='out' else '1.0'
            s(f'<rect x="{cx-74}" y="{cy-23}" width="148" height="46" rx="5" fill="rgba(3,6,15,.92)" stroke="{bstroke}" stroke-width="{bsw}" class="elem-shape" data-id="{elem_id}"/>')
            s(f'<rect x="{cx-74}" y="{cy-23}" width="3" height="46" rx="3" fill="{mc}"/>')
            badge='[A]' if e.get('mode')=='auto' else '[M]' if e.get('mode')=='manual' else '[A/M]'
            s(f'<text x="{cx+66}" y="{cy-14}" text-anchor="end" font-size="6" font-weight="700" fill="{mc}" font-family="Inter,sans-serif">{badge}</text>')

        for i,ll in enumerate(llines):
            yy = cy + (i - n/2 + 0.5)*11
            fsize = '7.5' if t!='exc' else '7'
            fw = '600' if t!='exc' else '500'
            fc = mc if t=='exc' else '#eef4ff'
            s(f'<text x="{cx+2}" y="{yy}" text-anchor="middle" dominant-baseline="middle" font-size="{fsize}" font-weight="{fw}" fill="{fc}" font-family="Inter,sans-serif" pointer-events="none">{ll}</text>')

        sys_txt=e.get('sys','')
        if sys_txt and t!='dia':
            sy = cy+23+9 if t!='exc' else cy+18+8
            s(f'<text x="{cx}" y="{sy}" text-anchor="middle" dominant-baseline="middle" font-size="6" fill="rgba(255,255,255,.3)" font-family="Inter,sans-serif" pointer-events="none">{sys_txt}</text>')

        s('</g>')

        # Collect detail for JS
        conns_from = [c['t'] for c in CONNS if c['f']==elem_id]
        conns_to   = [c['f'] for c in CONNS if c['t']==elem_id]
        elem_data_js[elem_id] = {
            'id': elem_id,
            'label': e['label'].replace('\n',' — '),
            'sys': e.get('sys',''),
            'mode': e.get('mode','auto'),
            'fn': e['_lane']['fn'],
            'lane_label': e['_lane']['label'].replace('\n',' / '),
            'lane_color': e['_lane']['color'],
            'detail': e.get('detail',''),
            'connects_to': conns_from,
            'receives_from': conns_to,
            'connections': e.get('connections',[]),
        }

    s('</svg>')

    svg_markup = '\n'.join(svg_lines)
    elem_data_json = json.dumps(elem_data_js, ensure_ascii=False, indent=2)

    # Full HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>GLO Finance AS-IS — System View (Interactive)</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: 100%; height: 100%; overflow: hidden; background: #03060F;
  font-family: 'Inter', sans-serif; color: #EEF4FF; }}

/* ── top bar ── */
#topbar {{
  position: fixed; top: 0; left: 0; right: 0; height: 54px; z-index: 300;
  background: rgba(3,6,15,.97); border-bottom: 1px solid rgba(255,255,255,.09);
  display: flex; align-items: center; padding: 0 18px; gap: 16px;
}}
#topbar .brand {{ font-size: 13px; font-weight: 700; color: #EEF4FF; }}
#topbar .sub   {{ font-size: 9px; color: #4E6280; margin-top: 2px; }}
.badge {{
  display: inline-flex; align-items: center; gap: 5px; padding: 2px 9px;
  border-radius: 20px; font-size: 8px; font-weight: 700; letter-spacing: .6px;
  text-transform: uppercase; white-space: nowrap;
}}
.badge-auto   {{ background: rgba(74,222,128,.12); border: 1px solid rgba(74,222,128,.3); color: #4ade80; }}
.badge-manual {{ background: rgba(249,115,22,.12); border: 1px solid rgba(249,115,22,.3); color: #f97316; }}
.badge-mixed  {{ background: rgba(148,163,184,.1);  border: 1px solid rgba(148,163,184,.25); color: #94A3B8; }}
.ctrl-btn {{
  height: 28px; padding: 0 10px; border-radius: 6px; cursor: pointer;
  border: 1px solid rgba(255,255,255,.1); background: rgba(255,255,255,.04);
  color: #94A3B8; font-size: 10px; font-weight: 600; font-family: 'Inter',sans-serif;
  transition: all .15s;
}}
.ctrl-btn:hover {{ background: rgba(255,255,255,.09); color: #EEF4FF; }}

/* ── diagram viewport ── */
#vp {{
  position: fixed; top: 54px; left: 0; right: 0; bottom: 0;
  overflow: hidden; z-index: 1; cursor: grab; transition: right .35s ease;
}}
#vp.panel-open {{ right: 420px; }}
#vp.drag {{ cursor: grabbing; }}
#diagram-root {{ transform-origin: 0 0; user-select: none; }}

/* ── detail panel ── */
#detail-panel {{
  position: fixed; top: 54px; right: -420px; bottom: 0; width: 420px; z-index: 200;
  background: #08111F; border-left: 1px solid rgba(255,255,255,.1);
  display: flex; flex-direction: column;
  transition: right .35s cubic-bezier(.4,0,.2,1);
  overflow: hidden;
}}
#detail-panel.open {{ right: 0; }}
.dp-header {{
  padding: 18px 18px 14px; border-bottom: 1px solid rgba(255,255,255,.07);
  flex-shrink: 0;
}}
.dp-sys  {{ font-size: 9px; font-weight: 700; letter-spacing: .8px; text-transform: uppercase;
  color: var(--lc); margin-bottom: 6px; }}
.dp-title {{ font-size: 16px; font-weight: 700; color: #EEF4FF; line-height: 1.3; margin-bottom: 8px; }}
.dp-fn    {{ font-size: 10px; color: #4E6280; margin-bottom: 10px; }}
.dp-mode  {{ display: inline-flex; }}
.dp-close {{
  position: absolute; top: 14px; right: 14px; width: 26px; height: 26px;
  border-radius: 6px; border: 1px solid rgba(255,255,255,.1);
  background: rgba(255,255,255,.05); cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; color: #4E6280; transition: all .12s;
}}
.dp-close:hover {{ background: rgba(255,255,255,.12); color: #EEF4FF; }}
.dp-body {{ padding: 16px 18px; overflow-y: auto; flex: 1; }}
.dp-section-title {{
  font-size: 9px; font-weight: 700; letter-spacing: .7px; text-transform: uppercase;
  color: #4E6280; margin-bottom: 8px; padding-bottom: 5px;
  border-bottom: 1px solid rgba(255,255,255,.06);
}}
.dp-detail {{ font-size: 11.5px; color: #94A3B8; line-height: 1.7; margin-bottom: 18px; }}
.dp-connections {{ list-style: none; }}
.dp-connections li {{
  font-size: 10.5px; color: #64748B; padding: 4px 0;
  border-bottom: 1px solid rgba(255,255,255,.04); display: flex; align-items: center; gap: 7px;
}}
.dp-connections li::before {{ content: ''; width: 5px; height: 5px;
  border-radius: 50%; background: var(--lc); flex-shrink: 0; }}
.dp-empty {{
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 100%; color: #1E293B; gap: 10px; padding: 40px;
}}
.dp-empty svg {{ opacity: .3; }}
.dp-empty p {{ font-size: 11px; text-align: center; color: #334155; }}

/* ── zoom controls ── */
#zoom-ctrl {{
  position: fixed; bottom: 40px; right: 14px; display: flex;
  flex-direction: column; gap: 3px; z-index: 200;
  transition: right .35s ease;
}}
#zoom-ctrl.panel-open {{ right: 434px; }}
.zb {{
  width: 30px; height: 30px; border-radius: 6px;
  background: rgba(8,14,28,.95); border: 1px solid rgba(255,255,255,.1);
  color: #94A3B8; cursor: pointer; display: flex; align-items: center;
  justify-content: center; font-size: 15px; font-weight: 700;
  backdrop-filter: blur(8px); transition: all .12s;
}}
.zb:hover {{ background: rgba(20,40,80,.95); color: #EEF4FF; }}
#zoom-label {{ font-size: 8px; color: #4E6280; text-align: center; padding: 2px;
  background: rgba(8,14,28,.85); border: 1px solid rgba(255,255,255,.07);
  border-radius: 5px; font-family: monospace; }}

/* elem hover highlight */
.elem:hover .elem-shape {{ filter: brightness(1.35); transition: filter .15s; }}
.elem.selected .elem-shape {{ filter: brightness(1.5); }}
</style>
</head>
<body>

<!-- Top bar -->
<div id="topbar">
  <div>
    <div class="brand">GLO Finance — AS-IS Process Map (System / ERP View)</div>
    <div class="sub">13 System Swim Lanes  ·  8 L3 Activity Phases  ·  Click any box to see details</div>
  </div>
  <div style="margin-left:auto;display:flex;align-items:center;gap:8px;">
    <span class="badge badge-auto">&#x25CF; Auto</span>
    <span class="badge badge-manual">&#x25CF; Manual</span>
    <span class="badge badge-mixed">&#x25CF; Mixed</span>
    <button class="ctrl-btn" onclick="resetView()">&#x2295; Reset</button>
    <button class="ctrl-btn" onclick="fitScreen()">&#x2922; Fit</button>
  </div>
</div>

<!-- Diagram viewport -->
<div id="vp">
  <div id="diagram-root">
    {svg_markup}
  </div>
</div>

<!-- Detail panel -->
<div id="detail-panel">
  <div class="dp-empty" id="dp-empty">
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
      <rect x="6" y="14" width="36" height="26" rx="4" stroke="#334155" stroke-width="2"/>
      <path d="M16 8 L24 4 L32 8" stroke="#334155" stroke-width="2"/>
      <line x1="14" y1="24" x2="34" y2="24" stroke="#334155" stroke-width="1.5"/>
      <line x1="14" y1="30" x2="28" y2="30" stroke="#334155" stroke-width="1.5"/>
    </svg>
    <p>Click any box on the diagram<br>to see its full description,<br>system details and connections.</p>
  </div>
  <div id="dp-content" style="display:none;height:100%;flex-direction:column;display:none">
    <div class="dp-header" id="dp-header">
      <div class="dp-sys" id="dp-sys"></div>
      <div class="dp-title" id="dp-title"></div>
      <div class="dp-fn" id="dp-fn"></div>
      <div class="dp-mode" id="dp-mode"></div>
      <div class="dp-close" onclick="closePanel()">&#x2715;</div>
    </div>
    <div class="dp-body">
      <div class="dp-section-title">WHAT HAPPENS HERE</div>
      <div class="dp-detail" id="dp-detail"></div>
      <div class="dp-section-title">SYSTEM CONNECTIONS</div>
      <ul class="dp-connections" id="dp-connections"></ul>
    </div>
  </div>
</div>

<!-- Zoom controls -->
<div id="zoom-ctrl">
  <button class="zb" onclick="doZoom(1.15)">+</button>
  <div id="zoom-label">100%</div>
  <button class="zb" onclick="doZoom(1/1.15)">&#x2212;</button>
</div>

<script>
const ELEM_DATA = {elem_data_json};

// ── pan / zoom ────────────────────────────────────────────────────────────────
const vp = document.getElementById('vp');
const root = document.getElementById('diagram-root');
let scale=1, tx=0, ty=0, dragging=false, mx0=0, my0=0, tx0=0, ty0=0;

function applyTransform(){{
  root.style.transform = `translate(${{tx}}px,${{ty}}px) scale(${{scale}})`;
  document.getElementById('zoom-label').textContent = Math.round(scale*100)+'%';
}}
function doZoom(f, cx, cy){{
  cx = cx||vp.clientWidth/2; cy = cy||vp.clientHeight/2;
  const ns = Math.min(3, Math.max(.12, scale*f));
  tx = cx - (cx-tx)*(ns/scale); ty = cy - (cy-ty)*(ns/scale); scale=ns;
  applyTransform();
}}
function resetView(){{ scale=1; tx=0; ty=0; applyTransform(); }}
function fitScreen(){{
  const vw=vp.clientWidth, vh=vp.clientHeight;
  scale = Math.min(vw/{CANVAS_W}, vh/{CANVAS_H})*.9;
  tx=(vw-{CANVAS_W}*scale)/2; ty=(vh-{CANVAS_H}*scale)/2;
  applyTransform();
}}
vp.addEventListener('mousedown', e=>{{ if(e.target.closest('.elem')) return;
  dragging=true; vp.classList.add('drag'); mx0=e.clientX; my0=e.clientY; tx0=tx; ty0=ty; }});
window.addEventListener('mousemove', e=>{{ if(!dragging) return;
  tx=tx0+e.clientX-mx0; ty=ty0+e.clientY-my0; applyTransform(); }});
window.addEventListener('mouseup', ()=>{{ dragging=false; vp.classList.remove('drag'); }});
vp.addEventListener('wheel', e=>{{ e.preventDefault();
  const r=vp.getBoundingClientRect();
  doZoom(e.deltaY<0?1.1:.9, e.clientX-r.left, e.clientY-r.top); }}, {{passive:false}});

// ── detail panel ─────────────────────────────────────────────────────────────
let selectedEl = null;
function openPanel(id){{
  const d = ELEM_DATA[id];
  if(!d) return;
  // deselect old
  if(selectedEl) selectedEl.classList.remove('selected');
  selectedEl = document.querySelector(`.elem[data-id="${{id}}"]`);
  if(selectedEl) selectedEl.classList.add('selected');

  document.getElementById('dp-empty').style.display='none';
  const content = document.getElementById('dp-content');
  content.style.display='flex'; content.style.flexDirection='column'; content.style.height='100%';

  const lc = d.lane_color;
  document.getElementById('dp-header').style.setProperty('--lc', lc);
  document.getElementById('detail-panel').style.setProperty('--lc', lc);
  document.getElementById('dp-sys').textContent  = d.sys;
  document.getElementById('dp-sys').style.color  = lc;
  document.getElementById('dp-title').textContent = d.label;
  document.getElementById('dp-fn').textContent   = 'Business Function: ' + d.fn + '  ·  System: ' + d.lane_label;

  const modeEl = document.getElementById('dp-mode');
  const modeText = d.mode==='auto'? '[A] Automated' : d.mode==='manual'? '[M] Manual' : '[A/M] Mixed';
  const modeClass = d.mode==='auto'? 'badge-auto' : d.mode==='manual'? 'badge-manual' : 'badge-mixed';
  modeEl.innerHTML = `<span class="badge ${{modeClass}}">${{modeText}}</span>`;

  document.getElementById('dp-detail').textContent = d.detail;

  const ul = document.getElementById('dp-connections');
  ul.innerHTML = '';
  const conns = d.connections && d.connections.length ? d.connections :
    [...(d.receives_from||[]).map(x=>'← '+x), ...(d.connects_to||[]).map(x=>'→ '+x)];
  conns.forEach(c=>{{
    const li=document.createElement('li');
    li.style.setProperty('--lc', lc);
    li.textContent=c; ul.appendChild(li);
  }});

  document.getElementById('detail-panel').classList.add('open');
  document.getElementById('vp').classList.add('panel-open');
  document.getElementById('zoom-ctrl').classList.add('panel-open');
}}
function closePanel(){{
  document.getElementById('detail-panel').classList.remove('open');
  document.getElementById('vp').classList.remove('panel-open');
  document.getElementById('zoom-ctrl').classList.remove('panel-open');
  document.getElementById('dp-content').style.display='none';
  document.getElementById('dp-empty').style.display='';
  if(selectedEl){{ selectedEl.classList.remove('selected'); selectedEl=null; }}
}}
document.querySelectorAll('.elem').forEach(g=>{{
  g.addEventListener('click', e=>{{
    e.stopPropagation();
    openPanel(g.dataset.id);
  }});
}});
document.addEventListener('keydown', e=>{{ if(e.key==='Escape') closePanel(); }});

// auto-fit on load
window.addEventListener('load', ()=>{{ setTimeout(fitScreen, 100); }});
</script>
</body>
</html>"""

    OUT_HTML.write_text(html, encoding='utf-8')
    print("Interactive HTML written: " + str(OUT_HTML))


# ══════════════════════════════════════════════════════════════════════════════
#  VOICEOVER SCRIPT
# ══════════════════════════════════════════════════════════════════════════════
VOICEOVER = """
╔══════════════════════════════════════════════════════════════════════════════╗
║   GLO FINANCE AS-IS PROCESS MAP — PROFESSIONAL CLIENT VOICEOVER SCRIPT     ║
║   Prompt 2: System / ERP View  ·  Estimated delivery time: ~6-7 minutes   ║
╚══════════════════════════════════════════════════════════════════════════════╝

[TONE: Confident, authoritative, conversational. Speak at a measured pace.
 Pause at [PAUSE] markers. Click each element as you reference it.]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  OPENING  (0:00 – 0:45)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"What you're looking at is the complete end-to-end finance operations landscape
 for Tesco's Global Logistics — mapped, verified, and documented for the first
 time in one single view.

 Every row you see on the left is a real system or ERP platform that Tesco's
 finance operation runs on today. Every column across the top represents a key
 business activity — from the moment a supplier is first onboarded, all the
 way through to paying customs duty to HMRC. [PAUSE]

 What makes this view powerful is not just what it shows — it's what it reveals.
 Where systems hand off to each other. Where automated processes break down into
 manual workarounds. And where the real operational risk lives.

 Let me walk you through it."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 1 — THE DIAGRAM STRUCTURE  (0:45 – 1:30)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Point to left swim lane labels]

"Thirteen swim lanes. Each one is a distinct ERP system, platform or tool.
 Not a business team — a system. Because in Tesco's finance world, the system
 boundaries are where the complexity lives.

 At the top, we have eight activity phases — the L3 process steps — from
 Supplier Setup all the way to Customs and Duty settlement.

[Point to the green [A] and orange [M] badges on boxes]

 Every activity box carries a badge. Green means it's automated — the system
 handles it without human intervention. Orange means it's manual — a person
 has to do it. You'll notice very quickly where the manual steps cluster. That
 clustering pattern tells its own story. [PAUSE]

 The arrows between rows — those diagonal connections — are the integration
 points. They show where data moves from one system to another. Count them.
 There are over twenty distinct system-to-system integrations in this landscape."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 2 — THE SUPPLIER FOUNDATION  (1:30 – 2:15)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Click SSUP Portal / NeoGrid box, panel opens]

"The process starts here — with a supplier trying to get onto Tesco's books.
 The SSUP team collects a mandatory document pack: company registration, bank
 details, letterhead, contacts. All of this goes into NeoGrid manually. [PAUSE]

[Click EQOS box]

 From NeoGrid, it flows into EQOS — Tesco's master data system for every
 supplier and factory globally. EQOS validates, approves, and creates the
 record. This is a critical gatekeeping step — until a supplier exists in EQOS,
 not a single Purchase Order can be raised against them.

 And here's something important — [Click EQOS feed box] — once a supplier is
 active, EQOS pushes compliance status to ISOS automatically every fifteen
 minutes. That means if a factory fails a compliance audit at 9 AM, by 9:15
 all their in-flight POs are blocked. The system reacts in near real-time."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 3 — THE ORDER MACHINE  (2:15 – 3:00)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Click LM/MM box]

"Buyers create Purchase Orders here — in LM or MM depending on the product
 category. Clothing starts in MM, crosses to LM, then transmits via BizTalk.
 A fully manual step — [M] badge, orange.

[Click ISOS Validate box]

 That PO lands in ISOS — the central finance and validation hub. ISOS runs
 four automatic checks: Is the supplier active? Is the factory approved?
 Is the cost price valid? Is the delivery date correct?

 If anything fails — [point to compliance exception] — ISOS silently cancels
 the PO. The critical word there is 'silently'. LM does not receive a
 cancellation message back. The buyer has no idea. They think their PO is live.
 That is a known, documented gap in the current system landscape. [PAUSE]

[Click OTM box, then BizTalk box]

 If the PO passes — it goes to OTM, which further enriches it and distributes
 it to the supplier as a PDF. BizTalk handles the transmission at every step.
 Think of BizTalk as the nervous system connecting all of these platforms
 together."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 4 — THE INVOICE CHAIN  (3:00 – 4:00)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Click Documentum box]

"Once goods ship and an invoice arrives, look what happens here — Documentum.
 The supplier sends a PDF invoice. It arrives in Documentum, and someone
 manually keys in six or seven fields — PO number, currency, supplier ID,
 quantity, amount. Every. Single. Invoice. [PAUSE]

 This is one of the highest-volume manual activities in the entire finance
 operation. At Tesco's import scale, that represents thousands of manual
 keystrokes per week, with the attendant risk of human error.

[Click BizTalk IV0 box]

 Simultaneously — on a completely separate channel — the Freight Forwarder
 sends an electronic IV0 invoice message via BizTalk to ISOS. Two invoices
 for the same shipment. Two completely separate systems. They need to reconcile.

[Click ISOS 78-column extract box]

 ISOS merges everything — PO data, supplier master, shipment data, IV0
 values — into a 78-column extract. This extract only contains POs that have
 passed cost validation. If a buyer hasn't resolved a cost mismatch in the
 OTM Business Monitor, that invoice simply doesn't appear here.

[Click BizTalk EDI box]

 EDI then automatically trims that to 69 columns in OFI format. Fully
 automated. Clean. This is the input into the 3-way match.

[Click Oracle 11i OFI AP box]

 Once matched — Oracle Financials 11i creates the AP invoice automatically.
 No workflow approval required. Payment goes to HSBC on 90-day terms,
 Vendor Financing, or Letter of Credit depending on the supplier profile."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 5 — THE FREIGHT BILLING STORY  (4:00 – 4:45)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Click MS Access box]

"Now look at this row — MS Access. A self-built Microsoft Access database,
 maintained by a single analyst in Bangalore, is the operational backbone of
 Tesco's entire freight self-billing process. [PAUSE]

 Every Monday, the analyst manually uploads the OTM Daily File. There is no
 automated connection between OTM and MS Access. They extract the weekly
 invoicing data by carrier, clean it, paste it into an Excel Rolling File,
 email it to each carrier for agreement — and then, on Friday, raise a
 Purchase Requisition in Oracle Fusion.

 The Rolling File has no system backup.

[Click Oracle Fusion PO box]

 Oracle Fusion generates the PO automatically and emails it to the carrier.

[Click Tungsten box]

 The carrier then logs into Tungsten Network and submits a formal eInvoice
 against that PO. Tungsten validates it, and within 24 hours it flows
 automatically into Oracle Fusion Payables.

 The contrast here is striking — a state-of-the-art Oracle Fusion and Tungsten
 setup at the end of a process that starts with a manually-maintained,
 single-point-of-failure MS Access database."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SECTION 6 — CUSTOMS & THE FINAL MILE  (4:45 – 5:30)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Click OTM CSS box]

"In the bottom rows, we have customs. OTM automatically generates a Customs
 Summary Sheet for every active shipment and sends it to WTA — Tesco's
 clearing agent — days before the vessel arrives. That's proactive, automated,
 and it works well.

[Click WTA SFD box]

 WTA combines that CSS with IMS invoice data received from OFI, and files
 the Simplified Frontier Declaration at the UK border. Tesco's AEO status
 means this gives near-automatic HMRC clearance.

[Click NBS/DDA box]

 Meanwhile — OTM sends HS codes to NBS weekly. NBS calculates duty rates.
 The accrual is posted to the General Ledger in OFI. And on the 16th of each
 month, TISL pays Customs Duty through the Duty Deferment Account.

 Automated, systematic, and compliant. The customs lane is one of the most
 well-engineered parts of this entire process."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CLOSING — THE OPPORTUNITY  (5:30 – 6:15)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[Pan back to show full diagram]

"So what does this map tell us?

 Thirteen systems. Over twenty integration points. A process that spans from
 a supplier uploading a document in NeoGrid all the way to HMRC receiving
 duty payment — and everything in between touches a different platform.

 Some of this is highly automated and works exceptionally well. OTM's CSS
 generation, ISOS's real-time compliance feed, Oracle Fusion's PO automation,
 Tungsten's eInvoicing — these are modern, scalable, and reliable.

 But there are pressure points. Manual PDF indexing in Documentum at scale.
 A single MS Access database with no backup driving the freight billing cycle.
 A silent PO cancellation in ISOS that buyers never see. Quarterly rate cards
 managed in Excel. [PAUSE]

 This is precisely the kind of visibility that enables intelligent
 transformation. You can't improve what you can't see — and now we can see
 all of it.

 The question isn't whether there's opportunity here. The question is where
 to start, and in what sequence, to unlock maximum value with minimum
 disruption to a finance operation that processes hundreds of thousands of
 transactions every year.

 That's exactly what we'd like to work through with you."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  PRESENTATION TIPS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  • Open the HTML diagram in Chrome full-screen before the meeting.
  • Use Ctrl+Scroll (or pinch) to zoom into specific sections as you narrate.
  • Click each box as you reference it — the detail panel slides in and shows
    the description, reinforcing your narrative with written detail.
  • After the walkthrough, invite the client to click and explore themselves.
  • The diagram scrolls horizontally — use the Fit button to reset the view.
  • Press Escape to close the detail panel at any time.

  KEY PHRASES TO USE:
  — "This is verified against the source documentation"
  — "Every connection you see is a real integration in production"
  — "The orange [M] badges are where transformation conversations begin"
  — "This is what the current state actually looks like — before we design
     what it should look like"
"""

if __name__ == '__main__':
    build_interactive_html()
    OUT_VOICE.write_text(VOICEOVER, encoding='utf-8')
    print("Voiceover script written: " + str(OUT_VOICE))
    print("")
    print("Done:")
    print("  " + str(OUT_HTML))
    print("  " + str(OUT_VOICE))
