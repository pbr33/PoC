"""
Generate TWO editable process-map PPT files + two PNG full-diagram exports.

Prompt 1 → GLO_Finance_P1_HighLevel_Editable.pptx + GLO_Finance_P1_HighLevel.png
  7 business-function swim lanes, 5 simplified phases, M/A badges on every step.

Prompt 2 → GLO_Finance_P2_SystemLanes_Editable.pptx + GLO_Finance_P2_SystemLanes.png
  13 system swim lanes (one ERP/system each), 8 L3 activity columns, data-flow arrows.
"""

import asyncio, json
from pathlib import Path
from io import BytesIO
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree

BASE = Path(r"c:\Users\prabhakargupta\Downloads\dream\test")

# ══════════════════════════════════════════════════════════════════════════════
#  PROMPT 1  —  HIGH-LEVEL BUSINESS-FUNCTION LANES
# ══════════════════════════════════════════════════════════════════════════════
P1 = {
  'title': 'GLO Finance AS-IS Process Map — High Level',
  'subtitle': 'Business-Function View  |  7 Swim Lanes  |  5 Phases',
  'canvas_w': 3540,
  'canvas_h': 1240,
  'label_w': 220,
  'bw': 148, 'bh': 46, 'dw': 68,

  'lanes': [
    {'id':'mdm',    'label':'Supplier &\nMDM',         'fn':'MDM / SSUP Team',         'color':'#00E5C0','y_top':80, 'y_bot':230},
    {'id':'po',     'label':'Procurement\n& Buying',   'fn':'Buyers / Merchandisers',  'color':'#4FB3FF','y_top':230,'y_bot':395},
    {'id':'ship',   'label':'Logistics\n& Shipping',   'fn':'Logistics / FF',          'color':'#A78BFA','y_top':395,'y_bot':545},
    {'id':'inv',    'label':'Invoice\nProcessing',     'fn':'AP Finance Team',         'color':'#FFD04A','y_top':545,'y_bot':755},
    {'id':'freight','label':'Freight\nSelf-Billing',   'fn':'TBS Self-Billing Team',   'color':'#FF6B6B','y_top':755,'y_bot':935},
    {'id':'ar',     'label':'AR & Finance\nSettlement','fn':'Finance / Treasury',      'color':'#C57BFF','y_top':935,'y_bot':1085},
    {'id':'customs','label':'Customs\n& Duty',         'fn':'Customs Team / WTA',      'color':'#52E67A','y_top':1085,'y_bot':1240},
  ],

  'phases': [
    {'label':'Supplier\nOnboarding',     'x_start':220, 'x_end':700,  'color':'rgba(0,229,192,.08)'},
    {'label':'Order\nManagement',        'x_start':700, 'x_end':1360, 'color':'rgba(79,179,255,.07)'},
    {'label':'Shipment &\nLogistics',    'x_start':1360,'x_end':1980, 'color':'rgba(167,139,250,.07)'},
    {'label':'Invoice &\nPayment',       'x_start':1980,'x_end':2760, 'color':'rgba(255,208,74,.06)'},
    {'label':'Finance &\nCompliance',    'x_start':2760,'x_end':3500, 'color':'rgba(82,230,122,.06)'},
  ],

  'elems': [
    # MDM lane  (cy = (80+230)/2 = 155)
    {'id':'mdm_collect','lane':'mdm','cx':420, 'type':'box','mode':'manual',
     'label':'Collect & Submit\nSupplier Documents','sys':'SSUP Portal / NeoGrid'},
    {'id':'mdm_val',    'lane':'mdm','cx':620, 'type':'dia','mode':'mixed',
     'label':'MDM Validation\nOK?','sys':'EQOS · NeoGrid'},
    {'id':'mdm_gap',    'lane':'mdm','cx':620, 'cy_off':52,'type':'exc','mode':'manual',
     'label':'Resolve Gaps\n↑ SSUP Resolves','sys':'NeoGrid'},
    {'id':'mdm_eqos',   'lane':'mdm','cx':820, 'type':'out','mode':'auto',
     'label':'Supplier Record\nCreated in EQOS','sys':'EQOS'},
    {'id':'mdm_feed',   'lane':'mdm','cx':1040,'type':'box','mode':'auto',
     'label':'Auto Data Feed\nto OFI & ISOS','sys':'EQOS → OFI / ISOS'},

    # PO lane  (cy = (230+395)/2 = 312)
    {'id':'po_create',  'lane':'po','cx':960, 'type':'box','mode':'manual',
     'label':'Buyer Creates\nPurchase Order','sys':'LM / MM System'},
    {'id':'po_valid',   'lane':'po','cx':1160,'type':'dia','mode':'auto',
     'label':'Factory Compliant\n& Valid?','sys':'ISOS · EQOS'},
    {'id':'po_block',   'lane':'po','cx':1160,'cy_off':55,'type':'exc','mode':'auto',
     'label':'PO Blocked\n(Non-Compliant)','sys':'ISOS'},
    {'id':'po_enrich',  'lane':'po','cx':1370,'type':'box','mode':'auto',
     'label':'Enrich PO &\nAssign Forwarder','sys':'ISOS'},
    {'id':'po_issue',   'lane':'po','cx':1580,'type':'out','mode':'auto',
     'label':'PO Distributed to\nSupplier via OTM','sys':'OTM'},

    # Ship lane  (cy = (395+545)/2 = 470)
    {'id':'sh_fob',     'lane':'ship','cx':1420,'type':'box','mode':'manual',
     'label':'FOB: Goods Handed\nto Freight Forwarder','sys':'FF System'},
    {'id':'sh_proc',    'lane':'ship','cx':1630,'type':'box','mode':'auto',
     'label':'Shipment Milestones\nProcessed','sys':'ISOS / OTM'},
    {'id':'sh_confirm', 'lane':'ship','cx':1830,'type':'out','mode':'auto',
     'label':'Shipment Confirmed\n& Tracked (SM2)','sys':'OTM'},
    {'id':'sh_file',    'lane':'ship','cx':2030,'type':'box','mode':'auto',
     'label':'Daily Inbound\nFreight File Generated','sys':'OTM'},

    # Invoice lane  (cy = (545+755)/2 = 650)
    {'id':'inv_recv',   'lane':'inv','cx':2060,'type':'box','mode':'mixed',
     'label':'Receive Invoices\n(IV0 + PDF Indexed)','sys':'BizTalk / Documentum'},
    {'id':'inv_cost',   'lane':'inv','cx':2280,'type':'dia','mode':'auto',
     'label':'Cost & PO\nMatch OK?','sys':'ISOS / OTM BM'},
    {'id':'inv_bm',     'lane':'inv','cx':2280,'cy_off':76,'type':'exc','mode':'manual',
     'label':'Buyer Resolves\nCost Exception','sys':'OTM Business Monitor'},
    {'id':'inv_match',  'lane':'inv','cx':2500,'type':'dia','mode':'manual',
     'label':'3-Way Match\nOK?','sys':'MS Access'},
    {'id':'inv_dq',     'lane':'inv','cx':2500,'cy_off':76,'type':'exc','mode':'manual',
     'label':'DQ Exception\nRaised & Resolved','sys':'MS Access / DQ'},
    {'id':'inv_ap',     'lane':'inv','cx':2720,'type':'out','mode':'auto',
     'label':'AP Invoice Created\n(Oracle 11i OFI)','sys':'Oracle Financials 11i'},
    {'id':'inv_pay',    'lane':'inv','cx':2950,'type':'out','mode':'auto',
     'label':'Payment Released\n(90-day / LC / VF)','sys':'OFI / HSBC'},

    # Freight lane  (cy = (755+935)/2 = 845)
    {'id':'fr_upload',  'lane':'freight','cx':2060,'type':'box','mode':'manual',
     'label':'Upload OTM File\nto Self-Billing Tool','sys':'MS Access DB'},
    {'id':'fr_extract', 'lane':'freight','cx':2280,'type':'box','mode':'manual',
     'label':'Weekly Carrier\nInvoice Extract','sys':'MS Access DB'},
    {'id':'fr_review',  'lane':'freight','cx':2500,'type':'box','mode':'manual',
     'label':'Send to Carrier\nfor Cost Agreement','sys':'Excel / Email'},
    {'id':'fr_agree',   'lane':'freight','cx':2720,'type':'dia','mode':'mixed',
     'label':'Carrier Agrees\non Costs?','sys':'Excel · Email'},
    {'id':'fr_disc',    'lane':'freight','cx':2720,'cy_off':68,'type':'exc','mode':'manual',
     'label':'Resolve Discrepancy\n(Rate Card)','sys':'Rate Card / Email'},
    {'id':'fr_po',      'lane':'freight','cx':2950,'type':'out','mode':'auto',
     'label':'PO Raised & Carrier\neInvoice (Tungsten)','sys':'Oracle Fusion / Tungsten'},
    {'id':'fr_pay',     'lane':'freight','cx':3170,'type':'out','mode':'auto',
     'label':'Auto-Payment\n(30-60 days)','sys':'Oracle Fusion AP'},

    # AR lane  (cy = (935+1085)/2 = 1010)
    {'id':'ar_create',  'lane':'ar','cx':2850,'type':'box','mode':'auto',
     'label':'AR Invoice &\nCommission Created','sys':'Oracle Financials 11i'},
    {'id':'ar_route',   'lane':'ar','cx':3070,'type':'dia','mode':'auto',
     'label':'UK / ROI\nor CE?','sys':'OFI / RIMS'},
    {'id':'ar_uk',      'lane':'ar','cx':3290,'cy_off':-42,'type':'box','mode':'auto',
     'label':'Oracle Fusion AR\n(UK / ROI)','sys':'Oracle Fusion AR'},
    {'id':'ar_ce',      'lane':'ar','cx':3290,'cy_off': 42,'type':'box','mode':'manual',
     'label':'RIMS Manual Entry\n→ Oracle R12 (CE)','sys':'RIMS / Oracle R12'},

    # Customs lane  (cy = (1085+1240)/2 = 1162)
    {'id':'cus_send',   'lane':'customs','cx':2500,'type':'box','mode':'auto',
     'label':'CSS + IMS Data Sent\nto Customs / WTA','sys':'OTM / OFI'},
    {'id':'cus_data',   'lane':'customs','cx':2720,'type':'dia','mode':'mixed',
     'label':'Data\nComplete?','sys':'WTA Clearing Agent'},
    {'id':'cus_hold',   'lane':'customs','cx':2720,'cy_off':56,'type':'exc','mode':'manual',
     'label':'Escalate Missing Data\n(Demurrage Risk)','sys':'WTA / AP Team'},
    {'id':'cus_sfd',    'lane':'customs','cx':2950,'type':'out','mode':'mixed',
     'label':'SFD Filed at\nUK Border (WTA/HMRC)','sys':'WTA / HMRC (CHIEF/CDS)'},
    {'id':'cus_duty',   'lane':'customs','cx':3170,'type':'box','mode':'auto',
     'label':'HS Codes, Duty Rates\n& Accrual to GL','sys':'NBS / OFI GL'},
    {'id':'cus_dda',    'lane':'customs','cx':3390,'type':'out','mode':'auto',
     'label':'Monthly Duty\nPayment (DDA)','sys':'DDA / TISL'},
  ],

  'conns': [
    # MDM
    {'f':'mdm_collect','fp':'r','t':'mdm_val',  'tp':'l','type':'main','label':''},
    {'f':'mdm_val',    'fp':'r','t':'mdm_eqos', 'tp':'l','type':'yes', 'label':'YES'},
    {'f':'mdm_val',    'fp':'b','t':'mdm_gap',  'tp':'t','type':'no',  'label':'NO'},
    {'f':'mdm_gap',    'fp':'l','t':'mdm_val',  'tp':'l','type':'loop','label':'retry'},
    {'f':'mdm_eqos',   'fp':'r','t':'mdm_feed', 'tp':'l','type':'main','label':''},
    {'f':'mdm_feed',   'fp':'b','t':'po_valid', 'tp':'t','type':'hand','label':'EQOS→ISOS'},
    # PO
    {'f':'po_create',  'fp':'r','t':'po_valid',  'tp':'l','type':'main','label':''},
    {'f':'po_valid',   'fp':'r','t':'po_enrich', 'tp':'l','type':'yes', 'label':'YES'},
    {'f':'po_valid',   'fp':'b','t':'po_block',  'tp':'t','type':'no',  'label':'NO'},
    {'f':'po_enrich',  'fp':'r','t':'po_issue',  'tp':'l','type':'main','label':''},
    {'f':'po_issue',   'fp':'b','t':'sh_fob',   'tp':'t','type':'hand','label':'PO→Ship'},
    # Ship
    {'f':'sh_fob',    'fp':'r','t':'sh_proc',   'tp':'l','type':'main','label':''},
    {'f':'sh_proc',   'fp':'r','t':'sh_confirm','tp':'l','type':'main','label':''},
    {'f':'sh_confirm','fp':'r','t':'sh_file',   'tp':'l','type':'main','label':''},
    {'f':'sh_confirm','fp':'b','t':'inv_recv',  'tp':'t','type':'hand','label':'IV0+PDF'},
    {'f':'sh_file',   'fp':'b','t':'fr_upload', 'tp':'t','type':'hand','label':'OTM All File'},
    # Invoice
    {'f':'inv_recv', 'fp':'r','t':'inv_cost',  'tp':'l','type':'main','label':''},
    {'f':'inv_cost', 'fp':'r','t':'inv_match', 'tp':'l','type':'yes', 'label':'YES ✓'},
    {'f':'inv_cost', 'fp':'b','t':'inv_bm',    'tp':'t','type':'no',  'label':'NO ✗'},
    {'f':'inv_bm',   'fp':'l','t':'inv_cost',  'tp':'l','type':'loop','label':'resolved'},
    {'f':'inv_match','fp':'r','t':'inv_ap',    'tp':'l','type':'yes', 'label':'YES ✓ Match'},
    {'f':'inv_match','fp':'b','t':'inv_dq',    'tp':'t','type':'no',  'label':'NO ✗ DQ'},
    {'f':'inv_dq',   'fp':'l','t':'inv_match', 'tp':'l','type':'loop','label':'resubmit'},
    {'f':'inv_ap',   'fp':'r','t':'inv_pay',   'tp':'l','type':'main','label':''},
    {'f':'inv_ap',   'fp':'b','t':'ar_create', 'tp':'t','type':'hand','label':'AP→AR'},
    {'f':'inv_ap',   'fp':'b','t':'cus_send',  'tp':'t','type':'hand','label':'IMS data'},
    # Freight
    {'f':'fr_upload', 'fp':'r','t':'fr_extract','tp':'l','type':'main','label':''},
    {'f':'fr_extract','fp':'r','t':'fr_review', 'tp':'l','type':'main','label':''},
    {'f':'fr_review', 'fp':'r','t':'fr_agree',  'tp':'l','type':'main','label':''},
    {'f':'fr_agree',  'fp':'r','t':'fr_po',     'tp':'l','type':'yes', 'label':'YES ✓'},
    {'f':'fr_agree',  'fp':'b','t':'fr_disc',   'tp':'t','type':'no',  'label':'NO ✗'},
    {'f':'fr_disc',   'fp':'l','t':'fr_agree',  'tp':'l','type':'loop','label':'resolved'},
    {'f':'fr_po',     'fp':'r','t':'fr_pay',    'tp':'l','type':'main','label':''},
    # AR
    {'f':'ar_create','fp':'r','t':'ar_route','tp':'l','type':'main','label':''},
    {'f':'ar_route', 'fp':'r','t':'ar_uk',   'tp':'l','type':'yes', 'label':'UK/ROI'},
    {'f':'ar_route', 'fp':'b','t':'ar_ce',   'tp':'t','type':'no',  'label':'CE'},
    # Customs
    {'f':'cus_send','fp':'r','t':'cus_data', 'tp':'l','type':'main','label':''},
    {'f':'cus_data','fp':'r','t':'cus_sfd',  'tp':'l','type':'yes', 'label':'YES ✓'},
    {'f':'cus_data','fp':'b','t':'cus_hold', 'tp':'t','type':'no',  'label':'NO ✗'},
    {'f':'cus_hold','fp':'l','t':'cus_data', 'tp':'l','type':'loop','label':'escalated'},
    {'f':'cus_sfd', 'fp':'r','t':'cus_duty', 'tp':'l','type':'main','label':''},
    {'f':'cus_duty','fp':'r','t':'cus_dda',  'tp':'l','type':'main','label':''},
  ],

  'slide_groups': [
    {'phases':(0,1),'title':'P1-2: Supplier Onboarding & Order Management'},
    {'phases':(2,3),'title':'P3-4: Shipment / Logistics & Invoice / Payment'},
    {'phases':(4,4),'title':'P5: Finance & Compliance'},
  ],
}

# ══════════════════════════════════════════════════════════════════════════════
#  PROMPT 2  —  SYSTEM-PER-LANE  (13 ERP / tool lanes, 8 L3 columns)
# ══════════════════════════════════════════════════════════════════════════════
P2 = {
  'title': 'GLO Finance AS-IS — System / ERP View',
  'subtitle': 'One swim lane per ERP/System  |  8 L3 Activity Phases  |  Data-flow connections',
  'canvas_w': 3570,
  'canvas_h': 1770,
  'label_w': 240,
  'bw': 148, 'bh': 46, 'dw': 55,

  'lanes': [
    {'id':'ssup',      'label':'SSUP Portal\n/ NeoGrid',            'fn':'Supplier Onboarding Team',  'color':'#00E5C0','y_top':80, 'y_bot':210},
    {'id':'eqos',      'label':'EQOS',                              'fn':'Master Data Management',    'color':'#1AE0BE','y_top':210,'y_bot':340},
    {'id':'lm',        'label':'LM / MM\nSystem',                   'fn':'Buyers (PO Creation)',      'color':'#4FB3FF','y_top':340,'y_bot':470},
    {'id':'isos',      'label':'ISOS',                              'fn':'Finance & PO Hub',          'color':'#7B9FFF','y_top':470,'y_bot':600},
    {'id':'otm',       'label':'Oracle TM\n(OTM)',                  'fn':'Logistics & Planning',      'color':'#A78BFA','y_top':600,'y_bot':730},
    {'id':'biztalk',   'label':'BizTalk / EDI',                     'fn':'Integration Layer (IT)',    'color':'#C4B5FD','y_top':730,'y_bot':860},
    {'id':'documentum','label':'Documentum',                        'fn':'Document Management (AP)',  'color':'#FFD04A','y_top':860,'y_bot':990},
    {'id':'msaccess',  'label':'MS Access DB\n(Self-Billing)',      'fn':'TBS Billing Analyst',       'color':'#FF6B6B','y_top':990,'y_bot':1120},
    {'id':'ofi',       'label':'Oracle\nFinancials 11i',            'fn':'AP / AR Finance',           'color':'#FF9E5E','y_top':1120,'y_bot':1250},
    {'id':'fusion',    'label':'Oracle Fusion\n(Procurement/AR)',   'fn':'Finance / Procurement',     'color':'#C57BFF','y_top':1250,'y_bot':1380},
    {'id':'tungsten',  'label':'Tungsten\nNetwork',                 'fn':'eInvoicing Portal',         'color':'#52E67A','y_top':1380,'y_bot':1510},
    {'id':'wta',       'label':'WTA Portal\n/ HMRC',               'fn':'Customs Clearance Agent',   'color':'#38C6FF','y_top':1510,'y_bot':1640},
    {'id':'nbs',       'label':'NBS / DDA',                        'fn':'Duty Management (Finance)', 'color':'#5DDDAA','y_top':1640,'y_bot':1770},
  ],

  'phases': [
    {'label':'Supplier\nSetup',              'x_start':240, 'x_end':620,  'color':'rgba(0,229,192,.07)'},
    {'label':'PO &\nCompliance',             'x_start':620, 'x_end':1040, 'color':'rgba(79,179,255,.07)'},
    {'label':'Shipment\n& Booking',          'x_start':1040,'x_end':1430, 'color':'rgba(167,139,250,.07)'},
    {'label':'Invoice\nReceipt & Prep',      'x_start':1430,'x_end':1850, 'color':'rgba(255,208,74,.06)'},
    {'label':'Cost\nValidation',             'x_start':1850,'x_end':2260, 'color':'rgba(255,107,107,.06)'},
    {'label':'Billing &\nPO Raise',          'x_start':2260,'x_end':2670, 'color':'rgba(197,123,255,.06)'},
    {'label':'AR &\nSettlement',             'x_start':2670,'x_end':3050, 'color':'rgba(82,230,122,.06)'},
    {'label':'Customs\n& Duty',              'x_start':3050,'x_end':3530, 'color':'rgba(56,198,255,.06)'},
  ],

  'elems': [
    # SSUP (cy=145)
    {'id':'ssup_coll','lane':'ssup','cx':420,'type':'box','mode':'manual',
     'label':'Collect & Upload\nSupplier Documents','sys':'SSUP Portal / NeoGrid'},

    # EQOS (cy=275)
    {'id':'eqos_create','lane':'eqos','cx':500,'type':'out','mode':'mixed',
     'label':'Validate & Create\nSupplier/Factory Record','sys':'EQOS'},
    {'id':'eqos_feed',  'lane':'eqos','cx':820,'type':'box','mode':'auto',
     'label':'Real-time Compliance\nFeed to ISOS (15-min)','sys':'EQOS → ISOS'},

    # LM/MM (cy=405)
    {'id':'lm_po','lane':'lm','cx':720,'type':'box','mode':'manual',
     'label':'Buyer Creates\nPurchase Order','sys':'LM / MM System'},

    # ISOS (cy=535)
    {'id':'isos_valid', 'lane':'isos','cx':860,'type':'box','mode':'auto',
     'label':'Validate PO:\nCompliance & Cost','sys':'ISOS'},
    {'id':'isos_enrich','lane':'isos','cx':1060,'type':'box','mode':'auto',
     'label':'Enrich PO &\nAssign FF/LSP','sys':'ISOS'},
    {'id':'isos_sm',    'lane':'isos','cx':1240,'type':'box','mode':'auto',
     'label':'SM1/SM2 Processing\n& Version Filtering','sys':'ISOS'},
    {'id':'isos_78col', 'lane':'isos','cx':1640,'type':'out','mode':'auto',
     'label':'Generate 78-Column\nExtract (Approved POs)','sys':'ISOS'},
    {'id':'isos_cost',  'lane':'isos','cx':2050,'type':'box','mode':'auto',
     'label':'2-Way Cost Check:\nPO vs IV0 Value','sys':'ISOS / OTM BM'},

    # OTM (cy=665)
    {'id':'otm_po',   'lane':'otm','cx':930,'type':'box','mode':'auto',
     'label':'Enrich & Distribute\nPO to Supplier (PDF)','sys':'OTM'},
    {'id':'otm_sm',   'lane':'otm','cx':1230,'type':'out','mode':'auto',
     'label':'Shipment Booking\n& Milestone Tracking','sys':'OTM'},
    {'id':'otm_file', 'lane':'otm','cx':1500,'type':'out','mode':'auto',
     'label':'Daily Inbound\nAll File Generated','sys':'OTM'},
    {'id':'otm_css',  'lane':'otm','cx':3100,'type':'out','mode':'auto',
     'label':'CSS Auto-sent\nto WTA (Pre-Arrival)','sys':'OTM → WTA'},
    {'id':'otm_nbs',  'lane':'otm','cx':3360,'type':'box','mode':'auto',
     'label':'HS Code Extract\nto NBS (weekly)','sys':'OTM → NBS'},

    # BizTalk/EDI (cy=795)
    {'id':'bt_po',  'lane':'biztalk','cx':820, 'type':'box','mode':'auto',
     'label':'Transmit PO to OTM\n& Supplier (BizTalk)','sys':'BizTalk / XCOM'},
    {'id':'bt_sm',  'lane':'biztalk','cx':1230,'type':'box','mode':'auto',
     'label':'Route Shipment\nMilestones (SM1-SM4)','sys':'BizTalk'},
    {'id':'bt_iv0', 'lane':'biztalk','cx':1570,'type':'box','mode':'auto',
     'label':'Route IV0 e-Invoice\nfrom FF to ISOS','sys':'BizTalk'},
    {'id':'bt_edi', 'lane':'biztalk','cx':2050,'type':'out','mode':'auto',
     'label':'EDI: 78-col → 69-col\nFormat Conversion','sys':'EDI'},

    # Documentum (cy=925)
    {'id':'doc_index','lane':'documentum','cx':1640,'type':'box','mode':'manual',
     'label':'Manually Index PDF\nInvoice (6-7 Fields)','sys':'Documentum'},

    # MS Access (cy=1055)
    {'id':'ms_upload','lane':'msaccess','cx':2100,'type':'box','mode':'manual',
     'label':'Upload OTM File &\nRun Weekly Extract','sys':'MS Access DB'},
    {'id':'ms_roll',  'lane':'msaccess','cx':2460,'type':'box','mode':'manual',
     'label':'Rolling File: Track\nCharges & Agreements','sys':'MS Access DB'},

    # OFI (cy=1185)
    {'id':'ofi_ap','lane':'ofi','cx':2810,'type':'out','mode':'auto',
     'label':'AP Invoice\nAuto-Created','sys':'Oracle Financials 11i'},
    {'id':'ofi_ar','lane':'ofi','cx':3010,'type':'out','mode':'auto',
     'label':'AR Invoice\nAuto-Created (TISL)','sys':'Oracle Financials 11i'},

    # Oracle Fusion (cy=1315)
    {'id':'fusion_po','lane':'fusion','cx':2460,'type':'out','mode':'auto',
     'label':'Freight PO Raised\n(P1002-XXXXXX)','sys':'Oracle Fusion Procurement'},
    {'id':'fusion_ar','lane':'fusion','cx':2870,'type':'box','mode':'auto',
     'label':'UK/ROI AR Automation\n& EDI to Financials','sys':'Oracle Fusion AR'},

    # Tungsten (cy=1445)
    {'id':'tung_inv','lane':'tungsten','cx':2460,'type':'box','mode':'manual',
     'label':'Carrier Creates\nFormal eInvoice vs PO','sys':'Tungsten Network'},

    # WTA/HMRC (cy=1575)
    {'id':'wta_sfd','lane':'wta','cx':3160,'type':'out','mode':'mixed',
     'label':'Prepare CSS+IMS &\nFile SFD at UK Border','sys':'WTA / HMRC (CHIEF/CDS)'},

    # NBS/DDA (cy=1705)
    {'id':'nbs_duty','lane':'nbs','cx':3240,'type':'box','mode':'auto',
     'label':'NBS: Duty Rates;\nAccrual Posted to GL','sys':'NBS / OFI GL'},
    {'id':'dda_pay', 'lane':'nbs','cx':3440,'type':'out','mode':'auto',
     'label':'TISL Monthly Duty\nPayment via DDA','sys':'DDA / TISL'},
  ],

  'conns': [
    # Within ISOS row
    {'f':'isos_valid', 'fp':'r','t':'isos_enrich','tp':'l','type':'main','label':''},
    {'f':'isos_enrich','fp':'r','t':'isos_sm',    'tp':'l','type':'main','label':''},
    {'f':'isos_sm',    'fp':'r','t':'isos_78col', 'tp':'l','type':'main','label':''},
    {'f':'isos_78col', 'fp':'r','t':'isos_cost',  'tp':'l','type':'main','label':''},
    # Within OTM row
    {'f':'otm_sm',  'fp':'r','t':'otm_file','tp':'l','type':'main','label':''},
    {'f':'otm_css', 'fp':'r','t':'otm_nbs', 'tp':'l','type':'main','label':''},
    # Within BizTalk row
    {'f':'bt_po','fp':'r','t':'bt_sm', 'tp':'l','type':'main','label':''},
    {'f':'bt_sm','fp':'r','t':'bt_iv0','tp':'l','type':'main','label':''},
    {'f':'bt_iv0','fp':'r','t':'bt_edi','tp':'l','type':'main','label':''},
    # Within OFI row
    {'f':'ofi_ap','fp':'r','t':'ofi_ar','tp':'l','type':'main','label':''},
    # Within NBS row
    {'f':'nbs_duty','fp':'r','t':'dda_pay','tp':'l','type':'main','label':''},

    # Cross-lane data flows (hand type)
    {'f':'ssup_coll',  'fp':'b','t':'eqos_create','tp':'t','type':'hand','label':'Doc upload'},
    {'f':'eqos_create','fp':'b','t':'isos_valid', 'tp':'t','type':'hand','label':'Compliance\nfeed'},
    {'f':'lm_po',      'fp':'b','t':'isos_valid', 'tp':'t','type':'hand','label':'PO transmitted\n(BizTalk)'},
    {'f':'isos_enrich','fp':'b','t':'otm_po',     'tp':'t','type':'hand','label':'PO to OTM'},
    {'f':'otm_po',     'fp':'b','t':'bt_po',      'tp':'t','type':'hand','label':'PO via\nBizTalk'},
    {'f':'bt_sm',      'fp':'t','t':'isos_sm',    'tp':'b','type':'hand','label':'SM1 from FF'},
    {'f':'bt_iv0',     'fp':'t','t':'isos_cost',  'tp':'b','type':'hand','label':'IV0 to ISOS'},
    {'f':'isos_cost',  'fp':'b','t':'bt_edi',     'tp':'t','type':'hand','label':'78-col to EDI'},
    {'f':'bt_edi',     'fp':'b','t':'ms_upload',  'tp':'t','type':'hand','label':'69-col data'},
    {'f':'doc_index',  'fp':'b','t':'ms_upload',  'tp':'t','type':'hand','label':'Indexed\nfields'},
    {'f':'ms_roll',    'fp':'b','t':'ofi_ap',     'tp':'t','type':'hand','label':'Matched\ndata → AP'},
    {'f':'ms_roll',    'fp':'b','t':'fusion_po',  'tp':'t','type':'hand','label':'PO req'},
    {'f':'fusion_po',  'fp':'b','t':'tung_inv',   'tp':'t','type':'hand','label':'PO to carrier'},
    {'f':'tung_inv',   'fp':'b','t':'fusion_ar',  'tp':'t','type':'hand','label':'Invoice\nvalidated'},
    {'f':'ofi_ar',     'fp':'b','t':'fusion_ar',  'tp':'t','type':'hand','label':'AR for UK'},
    {'f':'otm_file',   'fp':'b','t':'otm_css',    'tp':'t','type':'hand','label':'Triggers\nCSS'},
    {'f':'otm_css',    'fp':'b','t':'wta_sfd',    'tp':'t','type':'hand','label':'CSS data'},
    {'f':'ofi_ar',     'fp':'b','t':'wta_sfd',    'tp':'t','type':'hand','label':'IMS data'},
    {'f':'otm_nbs',    'fp':'b','t':'nbs_duty',   'tp':'t','type':'hand','label':'HS codes'},
  ],

  'slide_groups': [
    {'phases':(0,1),'title':'P1-2: Supplier Setup & PO / Compliance'},
    {'phases':(2,3),'title':'P3-4: Shipment / Booking & Invoice Receipt'},
    {'phases':(4,5),'title':'P5-6: Cost Validation & Billing / PO Raise'},
    {'phases':(6,7),'title':'P7-8: AR & Settlement & Customs / Duty'},
  ],
}

# ══════════════════════════════════════════════════════════════════════════════
#  SHARED HELPERS
# ══════════════════════════════════════════════════════════════════════════════
def _lane_cy(lane):
    return (lane['y_top'] + lane['y_bot']) / 2

def _resolve(diag):
    lmap = {l['id']: l for l in diag['lanes']}
    emap = {}
    for e in diag['elems']:
        lane = lmap[e['lane']]
        e['_cy']   = _lane_cy(lane) + e.get('cy_off', 0)
        e['_lane'] = lane
        emap[e['id']] = e
    return lmap, emap

def _port(elem, p, diag):
    bw = diag['bw']; bh = diag['bh']; dw = diag['dw']
    cx, cy, t = elem['cx'], elem['_cy'], elem['type']
    if t == 'dia':
        return {'r':(cx+dw,cy),'l':(cx-dw,cy),'t':(cx,cy-dw),'b':(cx,cy+dw)}[p]
    w = 148 if t=='exc' else bw
    h = 36  if t=='exc' else bh
    return {'r':(cx+w/2,cy),'l':(cx-w/2,cy),'t':(cx,cy-h/2),'b':(cx,cy+h/2)}[p]

# ══════════════════════════════════════════════════════════════════════════════
#  HTML GENERATOR  (for PNG export)
# ══════════════════════════════════════════════════════════════════════════════
MODE_COLOR = {'auto':'#4ade80','manual':'#f97316','mixed':'#94A3B8','decision':'#F59E0B'}

def build_html(diag, out_path):
    cw = diag['canvas_w']; ch = diag['canvas_h']
    lw = diag['label_w']
    bw = diag['bw']; bh = diag['bh']; dw = diag['dw']

    lmap, emap = _resolve(diag)

    lines = []
    a = lines.append

    # ─── SVG helpers ───
    def attr(**kw):
        return ' '.join(f'{k.replace("_","-")}="{v}"' for k,v in kw.items())

    def rect(x,y,w,h,fill='none',stroke='none',sw=1,rx=0,**kw):
        a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" '
          f'stroke="{stroke}" stroke-width="{sw}" rx="{rx}" {attr(**kw)}/>')

    def text(x,y,txt,size=10,fill='#fff',weight='normal',anchor='middle',dy='0',**kw):
        a(f'<text x="{x}" y="{y}" dy="{dy}" text-anchor="{anchor}" '
          f'dominant-baseline="middle" font-size="{size}" font-weight="{weight}" '
          f'fill="{fill}" font-family="Inter,sans-serif" {attr(**kw)}>{txt}</text>')

    def line(x1,y1,x2,y2,stroke='rgba(255,255,255,.12)',sw=1):
        a(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
          f'stroke="{stroke}" stroke-width="{sw}"/>')

    def path(d,stroke,sw=1.4,fill='none',marker_end='',dash=''):
        de = f'stroke-dasharray="{dash}"' if dash else ''
        me = f'marker-end="{marker_end}"' if marker_end else ''
        a(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {de} {me}/>')

    # ─── build path ───
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

    # ─── SVG open ───
    a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{cw}" height="{ch}">')
    a(f'<defs>')
    CONN_C={'main':'rgba(255,255,255,.45)','yes':'#4ade80','no':'#f97316','loop':'#f97316','hand':'rgba(100,116,139,.85)'}
    for ct,cc in CONN_C.items():
        a(f'<marker id="arr-{ct}" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">')
        a(f'<path d="M1,1 L7,4 L1,7 Z" fill="{cc}"/></marker>')
    a('</defs>')

    # background
    a(f'<rect width="{cw}" height="{ch}" fill="#03060F"/>')

    def hexrgb(h):
        h=h.lstrip('#')
        return int(h[0:2],16),int(h[2:4],16),int(h[4:6],16)

    # ─── Lane bands ───
    for ln in diag['lanes']:
        r,g,b = hexrgb(ln['color'])
        rect(0,ln['y_top'],cw,ln['y_bot']-ln['y_top'],fill=f'rgba({r},{g},{b},.05)')
        line(0,ln['y_bot'],cw,ln['y_bot'],'rgba(255,255,255,.06)')
        # left accent bar
        rect(0,ln['y_top'],3,ln['y_bot']-ln['y_top'],fill=ln['color'])
        # label panel
        rect(3,ln['y_top'],lw-3,ln['y_bot']-ln['y_top'],fill='rgba(3,6,15,.85)')
        cy=_lane_cy(ln)
        lbl_lines = ln['label'].split('\n')
        fn_line   = ln['fn']
        n = len(lbl_lines)
        start_y = cy - (n-1)*8 - 4
        for i,ll in enumerate(lbl_lines):
            text(lw/2+2,start_y+i*16,ll,size=10,weight='700',fill=ln['color'])
        text(lw/2+2,cy+14+(n-1)*8,fn_line,size=7.5,fill='rgba(255,255,255,.35)',weight='400')
        line(lw,ln['y_top'],lw,ln['y_bot'],'rgba(255,255,255,.08)',sw=1)

    # ─── Header bar ───
    rect(0,0,cw,80,fill='rgba(3,6,15,.97)')
    line(0,80,cw,80,'rgba(255,255,255,.08)')
    rect(0,0,lw,80,fill='rgba(3,6,15,.95)')
    text(lw/2,32,'BUSINESS FUNCTION\n/ SYSTEM',size=8,fill='rgba(255,255,255,.4)',weight='600')
    text(lw/2,50,'[A]=Auto   [M]=Manual',size=7,fill='rgba(255,255,255,.25)')

    # ─── Phase columns ───
    for ph in diag['phases']:
        x=ph['x_start']; w=ph['x_end']-ph['x_start']
        a(f'<rect x="{x}" y="0" width="{w}" height="{ch}" fill="{ph["color"]}"/>')
        line(ph['x_end'],0,ph['x_end'],ch,'rgba(255,255,255,.06)')
        plines=ph['label'].split('\n')
        for i,pl in enumerate(plines):
            text(x+w/2,30+i*16,pl,size=9,fill='rgba(255,255,255,.55)',weight='700')

    # ─── Connections ───
    for cn in diag['conns']:
        fe=emap.get(cn['f']); te=emap.get(cn['t'])
        if not fe or not te: continue
        fp=_port(fe,cn['fp'],diag); tp=_port(te,cn['tp'],diag)
        ct=cn['type']
        cc=CONN_C[ct]
        d=bpath(fp,tp,ct)
        path(d,cc,sw=1.2 if ct=='main' else 1.4,marker_end=f'url(#arr-{ct})')
        lbl=cn.get('label','')
        if lbl:
            mx=(fp[0]+tp[0])/2; my=(fp[1]+tp[1])/2
            for i,ll in enumerate(lbl.split('\n')):
                text(mx,my-6+i*10,ll,size=7,fill=cc)

    # ─── Elements ───
    for e in diag['elems']:
        cx=e['cx']; cy=e['_cy']; t=e['type']
        mode_c=MODE_COLOR.get(e.get('mode','auto'),'#4ade80')
        r2,g2,b2=hexrgb(e['_lane']['color'])

        if t=='dia':
            pts=f'{cx},{cy-dw} {cx+dw},{cy} {cx},{cy+dw} {cx-dw},{cy}'
            a(f'<polygon points="{pts}" fill="rgba(3,6,15,.92)" stroke="{MODE_COLOR["decision"]}" stroke-width="1.4"/>')
            llines=e['label'].split('\n')
            for i,ll in enumerate(llines):
                text(cx,cy+(i-len(llines)/2+0.5)*11,ll,size=8,fill='#fff')
        elif t=='exc':
            w2=148; h2=36
            rect(cx-w2/2,cy-h2/2,w2,h2,fill='rgba(3,6,15,.92)',stroke=mode_c,sw=1.4,rx=4)
            rect(cx-w2/2,cy-h2/2,3,h2,fill=mode_c,rx=2)
            llines=e['label'].split('\n')
            for i,ll in enumerate(llines):
                text(cx+2,cy+(i-len(llines)/2+0.5)*11,ll,size=7.5,fill=mode_c)
        else:
            w2=bw; h2=bh
            bfill='rgba(3,6,15,.92)'
            bstroke=e['_lane']['color'] if t=='box' else ('#00E5C0' if t=='out' else e['_lane']['color'])
            bsw=1.0 if t=='box' else 1.6
            rect(cx-w2/2,cy-h2/2,w2,h2,fill=bfill,stroke=bstroke,sw=bsw,rx=5)
            rect(cx-w2/2,cy-h2/2,3,h2,fill=mode_c,rx=3)
            llines=e['label'].split('\n')
            for i,ll in enumerate(llines):
                text(cx+2,cy+(i-len(llines)/2+0.5)*11,ll,size=8,
                     weight='700' if e.get('bold') else '500',fill='#eef4ff')
            # mode badge
            badge='[A]' if e.get('mode')=='auto' else '[M]' if e.get('mode')=='manual' else '[A/M]'
            bc=mode_c
            text(cx+w2/2-8,cy-h2/2+6,badge,size=6.5,fill=bc,anchor='end',weight='700')
            # sys tag
            sys=e.get('sys','')
            if sys:
                text(cx,cy+h2/2+8,sys,size=6.5,fill='rgba(255,255,255,.32)',anchor='middle')

    a('</svg>')
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>{diag['title']}</title>
<style>body{{margin:0;background:#03060F}}svg{{display:block}}</style>
</head><body>{''.join(lines)}</body></html>"""
    out_path.write_text(html, encoding='utf-8')
    print("HTML written: " + str(out_path))

# ══════════════════════════════════════════════════════════════════════════════
#  PLAYWRIGHT  PNG SCREENSHOT
# ══════════════════════════════════════════════════════════════════════════════
async def screenshot(html_path, png_path, cw, ch):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page    = await browser.new_page()
        await page.set_viewport_size({'width': cw+20, 'height': ch+20})
        await page.goto(html_path.as_uri())
        await page.wait_for_timeout(600)
        await page.screenshot(
            path=str(png_path),
            clip={'x':0,'y':0,'width':cw,'height':ch},
            type='png'
        )
        await browser.close()
    print("PNG saved:  " + str(png_path))

# ══════════════════════════════════════════════════════════════════════════════
#  PPTX BUILDER  (native editable shapes)
# ══════════════════════════════════════════════════════════════════════════════
def _rgb(h):
    h=h.lstrip('#')
    return RGBColor(int(h[0:2],16),int(h[2:4],16),int(h[4:6],16))

C_BG    =_rgb('#03060F')
C_PANEL =_rgb('#0D1117')
C_WHITE =_rgb('#FFFFFF')
C_GREY  =_rgb('#94A3B8')
C_TEAL  =_rgb('#00E5C0')
C_GREEN =_rgb('#4ade80')
C_ORANGE=_rgb('#f97316')
C_AMBER =_rgb('#F59E0B')

MODE_RGB={'auto':C_GREEN,'manual':C_ORANGE,'mixed':C_GREY,'decision':C_AMBER}
CONN_RGB={'main':_rgb('#94A3B8'),'yes':C_GREEN,'no':C_ORANGE,'loop':C_ORANGE,'hand':_rgb('#64748B')}

SLIDE_W=Inches(13.33); SLIDE_H=Inches(7.5); TITLE_H=Inches(0.52)

def _set_fill(sh, color, alpha_pct=100):
    sh.fill.solid(); sh.fill.fore_color.rgb=color
    if alpha_pct<100:
        spPr=sh._element.spPr
        sf=spPr.find('.//' + qn('a:solidFill'))
        if sf is not None:
            sc=sf.find(qn('a:srgbClr'))
            if sc is not None:
                al=etree.SubElement(sc,qn('a:alpha')); al.set('val',str(int(alpha_pct*1000)))

def _no_line(sh):  sh.line.fill.background()

def _set_line(sh,c,w=1.0):
    sh.line.color.rgb=c; sh.line.width=Pt(w)

def _set_arrow(conn,c,w=1.0):
    conn.line.color.rgb=c; conn.line.width=Pt(w)
    spPr=conn._element.spPr
    ln=spPr.find(qn('a:ln'))
    if ln is None: ln=etree.SubElement(spPr,qn('a:ln'))
    tE=ln.find(qn('a:tailEnd'))
    if tE is None: tE=etree.SubElement(ln,qn('a:tailEnd'))
    tE.set('type','arrow'); tE.set('w','med'); tE.set('len','med')
    hE=ln.find(qn('a:headEnd'))
    if hE is None: hE=etree.SubElement(ln,qn('a:headEnd'))
    hE.set('type','none')

def _text(sh, lines, fpt=7, bold=False, color=None, align=PP_ALIGN.CENTER):
    if color is None: color=C_WHITE
    tf=sh.text_frame; tf.word_wrap=False; tf.vertical_anchor=3
    for i,ln in enumerate(lines):
        p=tf.paragraphs[i] if i==0 else tf.add_paragraph()
        p.alignment=align
        r=p.add_run(); r.text=ln
        r.font.size=Pt(fpt); r.font.bold=bold; r.font.color.rgb=color

def _add_bg(slide):
    bg=slide.shapes.add_shape(1,0,0,SLIDE_W,SLIDE_H)
    bg.fill.solid(); bg.fill.fore_color.rgb=C_BG; _no_line(bg)
    sp=bg._element; sp.getparent().remove(sp)
    slide.shapes._spTree.insert(2,sp)

def _T(diag,sg):
    pi,pj=sg['phases']
    xa=diag['phases'][pi]['x_start']; xb=diag['phases'][pj]['x_end']
    lw=diag['label_w']
    vis=lw+(xb-xa)
    sc=SLIDE_W/vis; sy=(SLIDE_H-TITLE_H)/diag['canvas_h']
    return {'xa':xa,'xb':xb,'sc':sc,'sy':sy,'lw':lw}

def _dx(x,T):
    lw=T['lw']
    if x<=lw: return int(x*T['sc'])
    return int((x-T['xa']+lw)*T['sc'])

def _dy(y,T): return int(TITLE_H+y*T['sy'])

def _in_range(e,T): return T['xa']<=e['cx']<=T['xb']

def _draw_lanes(slide,diag,T):
    lw_s=int(T['lw']*T['sc'])
    for ln in diag['lanes']:
        lr=_rgb(ln['color'])
        yt=_dy(ln['y_top'],T); h=_dy(ln['y_bot'],T)-yt
        # band
        bd=slide.shapes.add_shape(1,0,yt,SLIDE_W,h)
        _set_fill(bd,lr,8); _no_line(bd)
        # accent bar
        bar=slide.shapes.add_shape(1,0,yt,Pt(3),h)
        bar.fill.solid(); bar.fill.fore_color.rgb=lr; _no_line(bar)
        # label panel
        panel=slide.shapes.add_shape(1,0,yt,lw_s,h)
        _set_fill(panel,C_BG,90); _no_line(panel)
        # name
        cy_s=_dy(int(_lane_cy(ln)),T)
        tb=slide.shapes.add_textbox(Pt(5),yt,lw_s-Pt(6),h)
        tf=tb.text_frame; tf.word_wrap=True; tf.vertical_anchor=3
        fpt=max(5.5,round(T['sc']/Inches(1)*72*.68,1))
        lbl_lines=ln['label'].split('\n')
        for i,ll in enumerate(lbl_lines):
            p=tf.paragraphs[i] if i==0 else tf.add_paragraph()
            p.alignment=PP_ALIGN.CENTER
            r=p.add_run(); r.text=ll
            r.font.size=Pt(fpt); r.font.bold=True; r.font.color.rgb=lr
        fn=ln['fn']
        ptb=slide.shapes.add_textbox(Pt(3),yt+h*2//3,lw_s-Pt(4),h//3)
        pf=ptb.text_frame; pp=pf.paragraphs[0]; pp.alignment=PP_ALIGN.CENTER
        pr=pp.add_run(); pr.text=fn
        pr.font.size=Pt(max(4.5,fpt-2)); pr.font.color.rgb=C_GREY
        # separator
        sep=slide.shapes.add_shape(1,0,_dy(ln['y_bot'],T)-1,SLIDE_W,Pt(0.7))
        _set_fill(sep,_rgb('#1E293B'),100); _no_line(sep)

def _draw_phases(slide,diag,sg,T):
    pi,pj=sg['phases']
    phase_colors=['#00E5C0','#4FB3FF','#A78BFA','#FFD04A','#FF6B6B','#C57BFF','#52E67A','#38C6FF']
    for phi in range(pi,pj+1):
        ph=diag['phases'][phi]
        x1=_dx(ph['x_start'],T); x2=_dx(ph['x_end'],T); pw=x2-x1
        hdr=slide.shapes.add_shape(1,x1,0,pw,TITLE_H)
        _set_fill(hdr,_rgb(phase_colors[phi%8]),12); _no_line(hdr)
        tb=slide.shapes.add_textbox(x1+Pt(3),0,pw-Pt(6),TITLE_H)
        tf=tb.text_frame; tf.vertical_anchor=3
        for i,ll in enumerate(ph['label'].split('\n')):
            p=tf.paragraphs[i] if i==0 else tf.add_paragraph()
            p.alignment=PP_ALIGN.CENTER
            r=p.add_run(); r.text=ll
            r.font.size=Pt(7); r.font.bold=True; r.font.color.rgb=_rgb(phase_colors[phi%8])
        # vertical sep
        sx=_dx(ph['x_end'],T)
        sv=slide.shapes.add_shape(1,sx-1,0,Pt(0.7),SLIDE_H)
        _set_fill(sv,_rgb('#1E293B'),100); _no_line(sv)
    # lane panel header
    lw_s=int(T['lw']*T['sc'])
    lb=slide.shapes.add_textbox(0,0,lw_s,TITLE_H)
    tf=lb.text_frame; tf.vertical_anchor=3; p=tf.paragraphs[0]
    p.alignment=PP_ALIGN.CENTER; r=p.add_run()
    r.text='SYSTEM / FUNCTION'; r.font.size=Pt(6); r.font.bold=True; r.font.color.rgb=C_GREY

def _draw_conns(slide,diag,T,emap):
    from pptx.enum.shapes import MSO_CONNECTOR_TYPE as CT
    for cn in diag['conns']:
        fe=emap.get(cn['f']); te=emap.get(cn['t'])
        if not fe or not te: continue
        if not _in_range(fe,T): continue
        fp=_port(fe,cn['fp'],diag); tp=_port(te,cn['tp'],diag)
        if not _in_range(te,T):
            xb=T['xb']; tp=(min(tp[0],xb),tp[1])
        x1=_dx(fp[0],T); y1=_dy(fp[1],T)
        x2=_dx(tp[0],T); y2=_dy(tp[1],T)
        if abs(x2-x1)<3 and abs(y2-y1)<3: continue
        ct_e=CT.ELBOW if cn['type'] in ('hand','loop','no') else CT.STRAIGHT
        conn=slide.shapes.add_connector(ct_e,x1,y1,x2,y2)
        _set_arrow(conn,CONN_RGB[cn['type']],0.9)
        lbl=cn.get('label','')
        if lbl:
            mx=(x1+x2)//2; my=(y1+y2)//2
            tb=slide.shapes.add_textbox(mx-Inches(.3),my-Inches(.1),Inches(.6),Inches(.16))
            tf=tb.text_frame; p=tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
            r=p.add_run(); r.text=lbl.replace('\n',' ')
            r.font.size=Pt(5.5); r.font.color.rgb=CONN_RGB[cn['type']]

def _draw_elems(slide,diag,T,emap):
    bw=diag['bw']; bh=diag['bh']; dw=diag['dw']
    fpt=max(5.5,round(T['sc']/Inches(1)*72*.84,1)); fpt=min(fpt,8.0)
    for e in diag['elems']:
        if not _in_range(e,T): continue
        cx_=_dx(e['cx'],T); cy_=_dy(int(e['_cy']),T)
        lr=_rgb(e['_lane']['color'])
        mode_c=MODE_RGB.get(e.get('mode','auto'),C_GREEN)
        lines=e['label'].split('\n')
        t=e['type']

        if t=='dia':
            dw_=int(dw*T['sc']); dh=int(dw*T['sy'])
            sh=slide.shapes.add_shape(4,cx_-dw_,cy_-dh,dw_*2,dh*2)
            _set_fill(sh,C_PANEL,95); _set_line(sh,C_AMBER,1.2)
            _text(sh,lines,fpt)
        elif t=='exc':
            w_=int(148*T['sc']); h_=int(36*T['sy'])
            sh=slide.shapes.add_shape(5,cx_-w_//2,cy_-h_//2,w_,h_)
            _set_fill(sh,C_PANEL,95); _set_line(sh,mode_c,1.2)
            _text(sh,lines,max(fpt-.5,5),color=mode_c)
        else:
            w_=int(bw*T['sc']); h_=int(bh*T['sy'])
            sh=slide.shapes.add_shape(5,cx_-w_//2,cy_-h_//2,w_,h_)
            _set_fill(sh,C_PANEL,95)
            bc=C_TEAL if t=='out' else lr
            _set_line(sh,bc,1.4 if t=='out' else 1.0)
            _text(sh,lines,fpt,bold=e.get('bold',False))
            # Mode badge (small label top-right)
            badge='[A]' if e.get('mode')=='auto' else '[M]' if e.get('mode')=='manual' else '[A/M]'
            btb=slide.shapes.add_textbox(cx_+w_//2-Pt(16),cy_-h_//2,Pt(16),Pt(9))
            bp=btb.text_frame.paragraphs[0]; bp.alignment=PP_ALIGN.RIGHT
            br=bp.add_run(); br.text=badge
            br.font.size=Pt(5.5); br.font.bold=True; br.font.color.rgb=mode_c
        # sys tag
        sys=e.get('sys','')
        if sys and t!='dia':
            tb=slide.shapes.add_textbox(cx_-int(bw*T['sc'])//2,cy_+int(bh*T['sy'])//2+1,
                                         int(bw*T['sc']),Pt(8))
            tf=tb.text_frame; p=tf.paragraphs[0]; p.alignment=PP_ALIGN.CENTER
            r=p.add_run(); r.text=sys
            r.font.size=Pt(max(fpt-1.5,4)); r.font.color.rgb=C_GREY

def _build_title_slide(prs,diag):
    sl=prs.slides.add_slide(prs.slide_layouts[6])
    _add_bg(sl)
    bar=sl.shapes.add_shape(1,0,Inches(3.0),SLIDE_W,Pt(1.5))
    bar.fill.solid(); bar.fill.fore_color.rgb=C_TEAL; _no_line(bar)
    def _t(txt,x,y,w,h,sz,bold=False,c=C_WHITE,al=PP_ALIGN.CENTER):
        tb=sl.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
        tf=tb.text_frame; tf.vertical_anchor=3; tf.word_wrap=True
        p=tf.paragraphs[0]; p.alignment=al; r=p.add_run()
        r.text=txt; r.font.size=Pt(sz); r.font.bold=bold; r.font.color.rgb=c
    _t(diag['title'],0.8,0.9,11.8,0.8,34,True,C_TEAL)
    _t(diag['subtitle'],0.8,1.75,11.8,0.5,14,False,C_WHITE)
    # legend
    legend=[('[A] = Automated Process',C_GREEN),('[M] = Manual Process',C_ORANGE),('[A/M] = Mixed',C_GREY)]
    for i,(lbl,c) in enumerate(legend):
        _t(lbl,1.0+i*3.8,2.5,3.5,0.35,10,True,c)
    # lane summary
    ty=3.4
    for ln in diag['lanes']:
        lr=_rgb(ln['color'])
        dot=sl.shapes.add_shape(9,Inches(1.0),Inches(ty)+Pt(2),Pt(10),Pt(10))
        dot.fill.solid(); dot.fill.fore_color.rgb=lr; _no_line(dot)
        _t(ln['label'].replace('\n',' ') + '  —  ' + ln['fn'],1.25,ty,11,0.38,8,False,C_WHITE,PP_ALIGN.LEFT)
        ty+=0.42
    _t('Tesco Global Finance  |  Confidential  |  2024',0,7.15,13.33,0.3,8,False,C_GREY)

def build_pptx(diag, out_path):
    _,emap = _resolve(diag)
    prs=Presentation()
    prs.slide_width=SLIDE_W; prs.slide_height=SLIDE_H
    _build_title_slide(prs,diag)
    for i,sg in enumerate(diag['slide_groups']):
        sl=prs.slides.add_slide(prs.slide_layouts[6])
        T=_T(diag,sg)
        _add_bg(sl)
        _draw_lanes(sl,diag,T)
        _draw_phases(sl,diag,sg,T)
        # title
        tb=sl.shapes.add_textbox(Pt(6),Pt(4),Inches(11),Pt(16))
        tf=tb.text_frame; p=tf.paragraphs[0]; p.alignment=PP_ALIGN.LEFT
        r=p.add_run(); r.text='Slide '+str(i+2)+'  |  '+sg['title']
        r.font.size=Pt(9); r.font.bold=True; r.font.color.rgb=C_TEAL
        _draw_conns(sl,diag,T,emap)
        _draw_elems(sl,diag,T,emap)
        print("  Slide "+str(i+2)+" built")
    prs.save(out_path)
    print("PPTX saved: " + str(out_path))

# ══════════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════════
async def main():
    p1_html = BASE / 'GLO_Finance_P1_HighLevel.html'
    p2_html = BASE / 'GLO_Finance_P2_SystemLanes.html'
    p1_png  = BASE / 'GLO_Finance_P1_HighLevel.png'
    p2_png  = BASE / 'GLO_Finance_P2_SystemLanes.png'
    p1_pptx = BASE / 'GLO_Finance_P1_HighLevel_Editable.pptx'
    p2_pptx = BASE / 'GLO_Finance_P2_SystemLanes_Editable.pptx'

    print("=== PROMPT 1 — High-Level Business Function View ===")
    _resolve(P1)
    build_html(P1, p1_html)
    await screenshot(p1_html, p1_png, P1['canvas_w'], P1['canvas_h'])
    build_pptx(P1, p1_pptx)

    print("")
    print("=== PROMPT 2 — System-per-Lane View ===")
    _resolve(P2)
    build_html(P2, p2_html)
    await screenshot(p2_html, p2_png, P2['canvas_w'], P2['canvas_h'])
    build_pptx(P2, p2_pptx)

    print("")
    print("Done. Output files:")
    for f in [p1_pptx,p2_pptx,p1_png,p2_png]:
        print("  " + str(f))

if __name__ == '__main__':
    asyncio.run(main())
