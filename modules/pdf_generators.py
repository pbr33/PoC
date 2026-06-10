# ═══════════════════════════════════════════════════════════════════════
#  PDF GENERATORS
# ═══════════════════════════════════════════════════════════════════════

import io
from datetime import datetime

import streamlit as st

from .utils import safe_int, safe_str, safe_list, safe_dict, sc_text

HAS_REPORTLAB = False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm, inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable, Image as RLImage
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
    HAS_REPORTLAB = True
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════════
#  PDF PROPOSAL GENERATOR (ECI Template)
# ═══════════════════════════════════════════════════════════════════════

def _eci_styles():
    """ECI-branded paragraph styles for reportlab."""
    styles = getSampleStyleSheet()
    eci_blue = rl_colors.Color(27/255, 58/255, 92/255)
    eci_accent = rl_colors.Color(0, 180/255, 216/255)
    styles.add(ParagraphStyle("ECITitle", parent=styles["Title"], fontSize=26, textColor=rl_colors.white, alignment=TA_CENTER, spaceAfter=6))
    styles.add(ParagraphStyle("ECISubtitle", parent=styles["Normal"], fontSize=13, textColor=rl_colors.Color(200/255, 220/255, 240/255), alignment=TA_CENTER, spaceAfter=4))
    styles.add(ParagraphStyle("ECIHeading", parent=styles["Heading1"], fontSize=15, textColor=eci_blue, spaceBefore=14, spaceAfter=6, borderWidth=0))
    styles.add(ParagraphStyle("ECIBody", parent=styles["Normal"], fontSize=10, leading=14, textColor=rl_colors.Color(30/255, 30/255, 30/255), spaceAfter=4))
    styles.add(ParagraphStyle("ECIBullet", parent=styles["Normal"], fontSize=10, leading=14, textColor=rl_colors.Color(30/255, 30/255, 30/255), leftIndent=16, bulletIndent=6, spaceAfter=2))
    styles.add(ParagraphStyle("ECISmall", parent=styles["Normal"], fontSize=8, textColor=rl_colors.Color(100/255, 100/255, 100/255), alignment=TA_CENTER))
    styles.add(ParagraphStyle("ECIKPIVal", parent=styles["Normal"], fontSize=16, textColor=eci_blue, alignment=TA_CENTER, leading=20))
    styles.add(ParagraphStyle("ECIKPILabel", parent=styles["Normal"], fontSize=8, textColor=rl_colors.Color(100/255, 100/255, 100/255), alignment=TA_CENTER))
    styles.add(ParagraphStyle("ECITableCell", parent=styles["Normal"], fontSize=8, leading=10, textColor=rl_colors.Color(30/255, 30/255, 30/255)))
    styles.add(ParagraphStyle("ECITableHeader", parent=styles["Normal"], fontSize=8, leading=10, textColor=rl_colors.white, alignment=TA_CENTER))
    return styles


def _eci_table(headers, rows, col_widths=None):
    """Build a styled reportlab Table."""
    eci_blue = rl_colors.Color(27/255, 58/255, 92/255)
    alt_row = rl_colors.Color(245/255, 248/255, 252/255)
    styles = _eci_styles()
    hdr_cells = [Paragraph("<b>" + h + "</b>", styles["ECITableHeader"]) for h in headers]
    data = [hdr_cells]
    for row in rows:
        data.append([Paragraph(str(v), styles["ECITableCell"]) for v in row])
    if not col_widths:
        col_widths = [480 / len(headers)] * len(headers)
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), eci_blue),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.Color(200/255, 200/255, 200/255)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), alt_row))
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def _md_to_para(text, styles):
    """Convert simple markdown text to a list of Paragraph flowables."""
    elements = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            elements.append(Spacer(1, 4))
            continue
        # Bold markers
        cleaned = line.replace("**", "<b>", 1)
        while "**" in cleaned:
            cleaned = cleaned.replace("**", "</b>", 1)
            if "**" in cleaned:
                cleaned = cleaned.replace("**", "<b>", 1)
        # Italic markers
        cleaned = cleaned.replace("_", "<i>", 1)
        while "_" in cleaned:
            cleaned = cleaned.replace("_", "</i>", 1)
            if "_" in cleaned:
                cleaned = cleaned.replace("_", "<i>", 1)
        if line.startswith("- "):
            elements.append(Paragraph(cleaned[2:], styles["ECIBullet"], bulletText="\u2022"))
        else:
            elements.append(Paragraph(cleaned, styles["ECIBody"]))
    return elements


def generate_proposal_pdf(results):
    if not HAS_REPORTLAB:
        return None
    buf = io.BytesIO()
    styles = _eci_styles()
    eci_blue = rl_colors.Color(27/255, 58/255, 92/255)
    eci_light = rl_colors.Color(214/255, 228/255, 240/255)

    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=25*mm, bottomMargin=20*mm, leftMargin=18*mm, rightMargin=18*mm,
                            title="ECI Project Proposal", author="ECI")
    elements = []

    se = safe_dict(results.get("semantic_analysis"))
    te = safe_dict(results.get("time_estimate"))
    ce = safe_dict(results.get("cost_estimate"))
    ri = safe_dict(results.get("risk_assessment"))
    ar = safe_dict(results.get("architecture"))
    sc = safe_dict(results.get("scope"))
    proposal = safe_dict(results.get("proposal"))

    # ── Cover ──
    elements.append(Spacer(1, 40))
    # Blue banner table
    banner_data = [[Paragraph("<b>PROJECT PROPOSAL</b>", styles["ECITitle"]),],
                   [Paragraph(safe_str(se.get("project_type", "Technology Solution")), styles["ECISubtitle"]),],
                   [Paragraph(datetime.now().strftime("%B %d, %Y"), styles["ECISubtitle"]),]]
    banner = Table(banner_data, colWidths=[480])
    banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), eci_blue),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(banner)
    elements.append(Spacer(1, 24))

    # KPI boxes
    kpi_items = [
        ("Requirements", str(len(safe_list(se.get("requirements"))))),
        ("Total Hours", str(safe_int(te.get("total_hours")))),
        ("Infra Cost/mo", "$" + str(safe_int(ce.get("total_monthly_cost")))),
        ("Risk Level", safe_str(ri.get("overall_level", "N/A"))),
    ]
    kpi_cells = []
    for label, val in kpi_items:
        kpi_cells.append([
            Paragraph("<b>" + val + "</b>", styles["ECIKPIVal"]),
            Paragraph(label, styles["ECIKPILabel"]),
        ])
    # Transpose: each kpi is a column of 2 rows
    kpi_data = [[kpi_cells[i][0] for i in range(4)], [kpi_cells[i][1] for i in range(4)]]
    kpi_table = Table(kpi_data, colWidths=[120, 120, 120, 120])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), eci_light),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.white),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("ECI |  CONFIDENTIAL", styles["ECISmall"]))
    elements.append(PageBreak())

    # ── Proposal sections ──
    for sec in safe_list(proposal.get("sections")):
        sec = safe_dict(sec)
        elements.append(Paragraph(safe_str(sec.get("title")), styles["ECIHeading"]))
        elements.append(HRFlowable(width="30%", thickness=2, color=rl_colors.Color(0, 180/255, 216/255), spaceAfter=8))
        elements.extend(_md_to_para(safe_str(sec.get("content")), styles))
        elements.append(Spacer(1, 10))

    elements.append(PageBreak())

    # ── Requirements summary ──
    elements.append(Paragraph("Requirements Summary", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=rl_colors.Color(0, 180/255, 216/255), spaceAfter=8))
    reqs = safe_list(se.get("requirements"))
    fn = [r for r in reqs if isinstance(r, dict) and r.get("type") == "functional"]
    nf = [r for r in reqs if isinstance(r, dict) and r.get("type") == "non-functional"]
    ig = [r for r in reqs if isinstance(r, dict) and r.get("type") == "integration"]
    elements.append(Paragraph("Functional: <b>" + str(len(fn)) + "</b>  |  Non-Functional: <b>" + str(len(nf)) + "</b>  |  Integration: <b>" + str(len(ig)) + "</b>", styles["ECIBody"]))
    elements.append(Spacer(1, 6))
    req_rows = [[safe_str(r.get("title")), safe_str(r.get("type")), safe_str(r.get("complexity")), safe_str(r.get("priority", ""))] for r in reqs if isinstance(r, dict)]
    if req_rows:
        elements.append(_eci_table(["Requirement", "Type", "Complexity", "Priority"], req_rows[:25], [200, 90, 80, 80]))
    elements.append(PageBreak())

    # ── Time estimate ──
    elements.append(Paragraph("Time Estimation", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=rl_colors.Color(0, 180/255, 216/255), spaceAfter=8))
    elements.extend(_md_to_para(
        "- <b>Total Hours:</b> " + str(safe_int(te.get("total_hours")))
        + "\n- <b>Duration:</b> " + safe_str(te.get("duration_weeks"))
        + "\n- <b>Confidence:</b> " + safe_str(te.get("confidence"))
        + "\n- <b>Buffer:</b> " + safe_str(te.get("buffer")), styles))
    elements.append(Spacer(1, 6))
    phase_rows = [[safe_str(p.get("name")), str(safe_int(p.get("hours"))), safe_str(p.get("percentage"))] for p in safe_list(te.get("phases")) if isinstance(p, dict)]
    if phase_rows:
        elements.append(_eci_table(["Phase", "Hours", "% of Total"], phase_rows, [220, 120, 120]))
    elements.append(PageBreak())

    # ── Infrastructure costs ──
    elements.append(Paragraph("Infrastructure Cost Estimate", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=rl_colors.Color(0, 180/255, 216/255), spaceAfter=8))
    elements.extend(_md_to_para(
        "- <b>Monthly Cost:</b> $" + str(safe_int(ce.get("total_monthly_cost")))
        + "\n- <b>Annual Cost:</b> $" + str(safe_int(ce.get("total_annual_cost"))), styles))
    elements.append(Spacer(1, 6))
    cost_rows = [[safe_str(a.get("service")), safe_str(a.get("tier", "")), "$" + str(safe_int(a.get("monthly_cost")))] for a in safe_list(ce.get("azure_costs")) if isinstance(a, dict)]
    if cost_rows:
        elements.append(_eci_table(["Service", "Tier", "Monthly Cost"], cost_rows, [200, 160, 100]))
    elements.append(PageBreak())

    # ── Risk ──
    elements.append(Paragraph("Risk Assessment", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=rl_colors.Color(0, 180/255, 216/255), spaceAfter=8))
    elements.extend(_md_to_para(
        "- <b>Overall Score:</b> " + str(safe_int(ri.get("overall_score"))) + "/10"
        + "\n- <b>Level:</b> " + safe_str(ri.get("overall_level")), styles))
    elements.append(Spacer(1, 6))
    risk_rows = [[safe_str(r.get("category")), safe_str(r.get("title")), safe_str(r.get("severity")), safe_str(r.get("mitigation"))] for r in safe_list(ri.get("risks")) if isinstance(r, dict)]
    if risk_rows:
        elements.append(_eci_table(["Category", "Risk", "Severity", "Mitigation"], risk_rows, [70, 110, 60, 220]))
    elements.append(PageBreak())

    # ── Architecture ──
    elements.append(Paragraph("Architecture Overview", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=rl_colors.Color(0, 180/255, 216/255), spaceAfter=8))
    elements.append(Paragraph("<b>Pattern:</b> " + safe_str(ar.get("pattern")), styles["ECIBody"]))
    elements.append(Spacer(1, 6))
    comp_rows = [[safe_str(c.get("name")), safe_str(c.get("type", "")), safe_str(c.get("azure_service", "")), ", ".join(safe_list(c.get("services")))] for c in safe_list(ar.get("components")) if isinstance(c, dict)]
    if comp_rows:
        elements.append(_eci_table(["Component", "Type", "Azure Service", "Details"], comp_rows, [80, 80, 120, 180]))
    df = safe_list(ar.get("data_flow"))
    if df:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph("<b>Data Flow:</b> " + " &rarr; ".join(safe_str(x) for x in df), styles["ECIBody"]))
    elements.append(PageBreak())

    # ── Scope ──
    elements.append(Paragraph("Scope Definition", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=rl_colors.Color(0, 180/255, 216/255), spaceAfter=8))
    def _sc_item(item, section="in_scope"):
        """Format a scope item: for in_scope show title, description, deliverable."""
        if not isinstance(item, dict):
            return safe_str(item)
        if section == "in_scope":
            title = safe_str(item.get("title", "")).strip()
            desc  = safe_str(item.get("description", "")).strip()
            deliv = safe_str(item.get("deliverable", "")).strip()
            main  = (f"<b>{title}</b> \u2014 {desc}" if title and desc
                     else f"<b>{title}</b>" if title else desc)
            return (main + f"  <i>(Deliverable: {deliv})</i>") if deliv else main
        if section == "out_of_scope":
            return safe_str(item.get("exclusion", item.get("description", item.get("title", "")))).strip() or safe_str(item)
        if section == "assumptions":
            return safe_str(item.get("statement", item.get("description", ""))).strip() or safe_str(item)
        if section == "prerequisites":
            return safe_str(item.get("item", item.get("description", ""))).strip() or safe_str(item)
        return sc_text(item, section)

    elements.append(Paragraph("<b>In Scope:</b>", styles["ECIBody"]))
    for item in safe_list(sc.get("in_scope")):
        elements.append(Paragraph(_sc_item(item, "in_scope"), styles["ECIBullet"], bulletText="\u2022"))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>Out of Scope:</b>", styles["ECIBody"]))
    for item in safe_list(sc.get("out_of_scope")):
        elements.append(Paragraph(_sc_item(item, "out_of_scope"), styles["ECIBullet"], bulletText="\u2022"))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>Assumptions:</b>", styles["ECIBody"]))
    for item in safe_list(sc.get("assumptions")):
        elements.append(Paragraph(_sc_item(item, "assumptions"), styles["ECIBullet"], bulletText="\u2022"))
    elements.append(Spacer(1, 6))
    elements.append(Paragraph("<b>Prerequisites:</b>", styles["ECIBody"]))
    for item in safe_list(sc.get("prerequisites")):
        elements.append(Paragraph(_sc_item(item, "prerequisites"), styles["ECIBullet"], bulletText="\u2022"))

    # Build
    def _footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(rl_colors.Color(27/255, 58/255, 92/255))
        canvas.line(18*mm, 15*mm, A4[0] - 18*mm, 15*mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(rl_colors.Color(100/255, 100/255, 100/255))
        canvas.drawString(18*mm, 10*mm, "ECI |  " + datetime.now().strftime("%B %d, %Y"))
        canvas.drawRightString(A4[0] - 18*mm, 10*mm, "Page " + str(canvas.getPageNumber()))
        canvas.restoreState()

    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════
#  SOW (STATEMENT OF WORK) PDF GENERATOR (ECI Template)
# ═══════════════════════════════════════════════════════════════════════

def generate_sow_pdf(results):
    """Generate a professional Statement of Work PDF using ECI branding.

    Includes: project overview, scope, deliverables, timeline, team,
    acceptance criteria, assumptions, payment terms, and signatures.
    """
    if not HAS_REPORTLAB:
        return None
    buf = io.BytesIO()
    styles = _eci_styles()
    eci_blue = rl_colors.Color(27/255, 58/255, 92/255)
    eci_light = rl_colors.Color(214/255, 228/255, 240/255)
    eci_accent = rl_colors.Color(0, 180/255, 216/255)
    eci_green = rl_colors.Color(0, 212/255, 170/255)
    gray = rl_colors.Color(100/255, 100/255, 100/255)

    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=25*mm, bottomMargin=20*mm,
                            leftMargin=18*mm, rightMargin=18*mm,
                            title="ECI Statement of Work", author="ECI")
    elements = []

    se = safe_dict(results.get("semantic_analysis"))
    te = safe_dict(results.get("time_estimate"))
    ce = safe_dict(results.get("cost_estimate"))
    ri = safe_dict(results.get("risk_assessment"))
    ar = safe_dict(results.get("architecture"))
    sc = safe_dict(results.get("scope"))
    proposal = safe_dict(results.get("proposal"))
    project_title = safe_str(se.get("project_type", "Technology Solution"))

    # ── Cover Page ──
    elements.append(Spacer(1, 50))
    cover_data = [
        [Paragraph("<b>STATEMENT OF WORK</b>", styles["ECITitle"])],
        [Paragraph(project_title, styles["ECISubtitle"])],
        [Paragraph("", styles["ECISubtitle"])],
        [Paragraph("Prepared by: ECI Consulting", styles["ECISubtitle"])],
        [Paragraph("Prepared for: [Client Name]", styles["ECISubtitle"])],
        [Paragraph("Date: " + datetime.now().strftime("%B %d, %Y"), styles["ECISubtitle"])],
        [Paragraph("Version: 1.0  |  Status: DRAFT", styles["ECISubtitle"])],
    ]
    cover = Table(cover_data, colWidths=[480])
    cover.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), eci_blue),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(cover)
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("CONFIDENTIAL — This document contains proprietary information.", styles["ECISmall"]))
    elements.append(PageBreak())

    # ── Table of Contents ──
    elements.append(Paragraph("Table of Contents", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))
    toc_items = [
        "1. Project Overview",
        "2. Scope of Work",
        "3. Deliverables",
        "4. Detailed Task Breakdown and Timeline",
        "5. Team Composition and Roles",
        "6. Infrastructure and Cost Estimate",
        "7. Risk Assessment",
        "8. Assumptions and Dependencies",
        "9. Acceptance Criteria",
        "10. Change Management",
        "11. Payment Terms",
        "12. Signatures",
    ]
    for item in toc_items:
        elements.append(Paragraph(item, styles["ECIBody"]))
    elements.append(PageBreak())

    # ── 1. Project Overview ──
    elements.append(Paragraph("1. Project Overview", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))
    # Executive summary from proposal if available
    exec_summary = ""
    for sec in safe_list(proposal.get("sections")):
        sec = safe_dict(sec)
        if "executive" in safe_str(sec.get("title")).lower() or "overview" in safe_str(sec.get("title")).lower():
            exec_summary = safe_str(sec.get("content"))
            break
    if exec_summary:
        elements.extend(_md_to_para(exec_summary, styles))
    else:
        elements.append(Paragraph("This Statement of Work defines the scope, deliverables, timeline, and terms for the " + project_title + " project.", styles["ECIBody"]))
    elements.append(Spacer(1, 6))

    # KPI summary
    kpi_data = [
        [Paragraph("<b>" + str(len(safe_list(se.get("requirements")))) + "</b>", styles["ECIKPIVal"]),
         Paragraph("<b>" + str(safe_int(te.get("total_hours"))) + "</b>", styles["ECIKPIVal"]),
         Paragraph("<b>" + safe_str(te.get("duration_weeks")) + "</b>", styles["ECIKPIVal"]),
         Paragraph("<b>$" + str(safe_int(ce.get("total_monthly_cost"))) + "/mo</b>", styles["ECIKPIVal"])],
        [Paragraph("Requirements", styles["ECIKPILabel"]),
         Paragraph("Total Hours", styles["ECIKPILabel"]),
         Paragraph("Duration", styles["ECIKPILabel"]),
         Paragraph("Infra Cost", styles["ECIKPILabel"])],
    ]
    kpi_table = Table(kpi_data, colWidths=[120, 120, 120, 120])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), eci_light),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.white),
    ]))
    elements.append(kpi_table)
    elements.append(Spacer(1, 6))

    # Business objectives
    objectives = safe_list(se.get("business_objectives"))
    if objectives:
        elements.append(Paragraph("<b>Business Objectives:</b>", styles["ECIBody"]))
        for obj in objectives:
            elements.append(Paragraph(safe_str(obj), styles["ECIBullet"], bulletText="\u2022"))
    elements.append(PageBreak())

    # ── 2. Scope of Work ──
    elements.append(Paragraph("2. Scope of Work", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    def _sc_item_sow(item, section="in_scope"):
        if not isinstance(item, dict):
            return safe_str(item)
        if section == "in_scope":
            title = safe_str(item.get("title", "")).strip()
            desc  = safe_str(item.get("description", "")).strip()
            deliv = safe_str(item.get("deliverable", "")).strip()
            main  = (f"<b>{title}</b> \u2014 {desc}" if title and desc
                     else f"<b>{title}</b>" if title else desc)
            return (main + f"  <i>(Deliverable: {deliv})</i>") if deliv else main
        if section == "out_of_scope":
            return safe_str(item.get("exclusion", item.get("description", item.get("title", "")))).strip() or safe_str(item)
        return sc_text(item, section)

    elements.append(Paragraph("<b>In Scope:</b>", styles["ECIBody"]))
    for item in safe_list(sc.get("in_scope")):
        elements.append(Paragraph(_sc_item_sow(item, "in_scope"), styles["ECIBullet"], bulletText="\u2022"))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("<b>Out of Scope:</b>", styles["ECIBody"]))
    for item in safe_list(sc.get("out_of_scope")):
        elements.append(Paragraph(_sc_item_sow(item, "out_of_scope"), styles["ECIBullet"], bulletText="\u2022"))
    elements.append(PageBreak())

    # ── 3. Deliverables ──
    elements.append(Paragraph("3. Deliverables", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    # Build deliverables from phases
    deliverable_rows = []
    phase_idx = 1
    for phase in safe_list(te.get("phases")):
        phase = safe_dict(phase)
        ph_name = safe_str(phase.get("name"))
        ph_week = safe_str(phase.get("week_label"))
        tasks = safe_list(phase.get("tasks"))
        task_names = ", ".join(safe_str(safe_dict(t).get("name")) for t in tasks[:3])
        if len(tasks) > 3:
            task_names += " (+" + str(len(tasks) - 3) + " more)"
        deliverable_rows.append([str(phase_idx), ph_name, ph_week, task_names])
        phase_idx += 1

    if deliverable_rows:
        elements.append(_eci_table(
            ["#", "Deliverable", "Timeline", "Key Tasks"],
            deliverable_rows,
            [30, 120, 80, 250],
        ))
    elements.append(PageBreak())

    # ── 4. Detailed Task Breakdown and Timeline ──
    elements.append(Paragraph("4. Detailed Task Breakdown and Timeline", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    elements.append(Paragraph(
        "Total Estimated Hours: <b>" + str(safe_int(te.get("total_hours"))) + "</b>"
        + "  |  Duration: <b>" + safe_str(te.get("duration_weeks")) + "</b>"
        + "  |  Confidence: <b>" + safe_str(te.get("confidence")) + "</b>"
        + "  |  Buffer: <b>" + safe_str(te.get("buffer")) + "</b>",
        styles["ECIBody"],
    ))
    elements.append(Spacer(1, 6))

    three_pt = safe_dict(te.get("three_point"))
    elements.append(Paragraph(
        "Three-Point Estimate: Optimistic <b>" + str(safe_int(three_pt.get("optimistic"))) + "h</b>"
        + "  |  Most Likely <b>" + str(safe_int(three_pt.get("most_likely"))) + "h</b>"
        + "  |  Pessimistic <b>" + str(safe_int(three_pt.get("pessimistic"))) + "h</b>",
        styles["ECIBody"],
    ))
    elements.append(Spacer(1, 8))

    for phase in safe_list(te.get("phases")):
        phase = safe_dict(phase)
        ph_name = safe_str(phase.get("name"))
        ph_week = safe_str(phase.get("week_label"))
        ph_hours = safe_int(phase.get("hours"))
        ph_low = safe_int(phase.get("low_hours"))
        ph_high = safe_int(phase.get("high_hours"))
        ph_pct = safe_str(phase.get("percentage"))

        elements.append(Paragraph(
            "<b>" + ph_name + "</b> (" + ph_week + ") — " + str(ph_hours) + "h [" + str(ph_low) + "-" + str(ph_high) + "h] " + ph_pct,
            styles["ECIBody"],
        ))

        task_rows = []
        for task in safe_list(phase.get("tasks")):
            task = safe_dict(task)
            task_rows.append([
                safe_str(task.get("name")),
                safe_str(task.get("role")),
                str(safe_int(task.get("low_hours"))),
                str(safe_int(task.get("hours"))),
                str(safe_int(task.get("high_hours"))),
                safe_str(task.get("justification"))[:60],
            ])
        if task_rows:
            elements.append(_eci_table(
                ["Sub-task", "Role", "Low", "Avg", "High", "Justification"],
                task_rows,
                [140, 60, 35, 35, 35, 175],
            ))
        elements.append(Spacer(1, 6))

    # Milestones
    milestones = safe_list(te.get("milestones"))
    if milestones:
        elements.append(Spacer(1, 4))
        elements.append(Paragraph("<b>Key Milestones:</b>", styles["ECIBody"]))
        ms_rows = [[safe_str(m.get("name")), "Week " + str(safe_int(m.get("week"))), safe_str(m.get("description"))]
                    for m in milestones if isinstance(m, dict)]
        if ms_rows:
            elements.append(_eci_table(["Milestone", "Week", "Description"], ms_rows, [150, 80, 250]))
    elements.append(PageBreak())

    # ── 5. Team Composition and Roles ──
    elements.append(Paragraph("5. Team Composition and Roles", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    total_h = safe_int(te.get("total_hours", 0))
    total_d = max(1, total_h / 7)
    role_rows = []
    for rl in safe_list(te.get("roles")):
        rl = safe_dict(rl)
        role_name = safe_str(rl.get("name"))
        pct = float(rl.get("allocation_pct", 0))
        rate = safe_int(rl.get("rate", 100))
        days = round(total_d * pct, 1)
        hours = int(round(days * 7, 0))
        cost = hours * rate
        role_rows.append([role_name, str(int(pct * 100)) + "%", str(days), str(hours), "$" + str(rate), "$" + str(cost)])
    if role_rows:
        elements.append(_eci_table(
            ["Role", "Allocation", "Days", "Hours", "Rate/hr", "Est. Cost"],
            role_rows,
            [110, 55, 50, 50, 55, 80],
        ))
    elements.append(PageBreak())

    # ── 6. Infrastructure and Cost Estimate ──
    elements.append(Paragraph("6. Infrastructure and Cost Estimate", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    elements.append(Paragraph(
        "Monthly Infrastructure Cost: <b>$" + str(safe_int(ce.get("total_monthly_cost"))) + "</b>"
        + "  |  Annual: <b>$" + str(safe_int(ce.get("total_annual_cost"))) + "</b>",
        styles["ECIBody"],
    ))
    elements.append(Spacer(1, 6))

    cost_rows = []
    for svc in safe_list(ce.get("azure_costs")):
        svc = safe_dict(svc)
        cost_rows.append([
            safe_str(svc.get("service")),
            safe_str(svc.get("tier", "")),
            "$" + str(safe_int(svc.get("monthly_cost"))),
            "$" + str(safe_int(svc.get("monthly_cost")) * 12),
            safe_str(svc.get("description", ""))[:50],
        ])
    if cost_rows:
        elements.append(_eci_table(
            ["Service", "Tier", "Monthly", "Annual", "Notes"],
            cost_rows,
            [110, 70, 60, 60, 180],
        ))
    elements.append(PageBreak())

    # ── 7. Risk Assessment ──
    elements.append(Paragraph("7. Risk Assessment", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    elements.append(Paragraph(
        "Overall Risk Score: <b>" + str(safe_int(ri.get("overall_score"))) + "/10</b>"
        + "  |  Level: <b>" + safe_str(ri.get("overall_level")) + "</b>",
        styles["ECIBody"],
    ))
    elements.append(Spacer(1, 6))

    risk_rows = []
    for rk in safe_list(ri.get("risks")):
        rk = safe_dict(rk)
        risk_rows.append([
            safe_str(rk.get("category")),
            safe_str(rk.get("title")),
            safe_str(rk.get("severity")),
            safe_str(rk.get("mitigation"))[:60],
        ])
    if risk_rows:
        elements.append(_eci_table(
            ["Category", "Risk", "Severity", "Mitigation"],
            risk_rows,
            [80, 140, 60, 200],
        ))
    elements.append(PageBreak())

    # ── 8. Assumptions and Dependencies ──
    elements.append(Paragraph("8. Assumptions and Dependencies", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    elements.append(Paragraph("<b>Assumptions:</b>", styles["ECIBody"]))
    assumptions = safe_list(sc.get("assumptions"))
    if not assumptions:
        assumptions = [
            "Client will provide timely access to required systems and environments",
            "Key stakeholders will be available for reviews and sign-offs within agreed timelines",
            "Requirements are baselined — changes will follow the change management process",
            "Client will provision necessary Azure subscriptions and licenses",
        ]
    for item in assumptions:
        elements.append(Paragraph(sc_text(item, "assumptions"), styles["ECIBullet"], bulletText="\u2022"))
    elements.append(Spacer(1, 6))

    elements.append(Paragraph("<b>Prerequisites:</b>", styles["ECIBody"]))
    prereqs = safe_list(sc.get("prerequisites"))
    if not prereqs:
        prereqs = [
            "Signed Statement of Work (this document)",
            "Cloud subscription access provisioned",
            "VPN/network access for development team",
            "Sample data and test accounts provided",
        ]
    for item in prereqs:
        elements.append(Paragraph(sc_text(item, "prerequisites"), styles["ECIBullet"], bulletText="\u2022"))
    elements.append(PageBreak())

    # ── 9. Acceptance Criteria ──
    elements.append(Paragraph("9. Acceptance Criteria", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    acceptance = [
        "All functional requirements as documented in Section 2 are implemented and verified",
        "All integration points are operational and tested end-to-end",
        "Non-functional requirements (performance, security, availability) meet agreed thresholds",
        "User Acceptance Testing (UAT) completed with formal sign-off from designated stakeholders",
        "All critical and high-severity defects are resolved prior to go-live",
        "Technical and user documentation delivered and reviewed",
        "Knowledge transfer sessions completed with client team",
        "Production environment deployed and verified with smoke testing",
    ]
    for item in acceptance:
        elements.append(Paragraph(item, styles["ECIBullet"], bulletText="\u2022"))
    elements.append(PageBreak())

    # ── 10. Change Management ──
    elements.append(Paragraph("10. Change Management", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    elements.append(Paragraph(
        "Any changes to the scope, timeline, or deliverables defined in this SOW must follow "
        "the change management process outlined below:",
        styles["ECIBody"],
    ))
    elements.append(Spacer(1, 4))
    change_items = [
        "<b>Change Request Submission:</b> All change requests must be submitted in writing with a description of the change, justification, and expected impact.",
        "<b>Impact Analysis:</b> ECI will assess the impact on timeline, cost, and resources within 3 business days.",
        "<b>Approval:</b> Changes must be approved in writing by both parties before implementation.",
        "<b>Tracking:</b> All approved changes will be tracked in the project change log with updated estimates.",
    ]
    for item in change_items:
        elements.append(Paragraph(item, styles["ECIBullet"], bulletText="\u2022"))
    elements.append(PageBreak())

    # ── 11. Payment Terms ──
    elements.append(Paragraph("11. Payment Terms", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    total_hours = safe_int(te.get("total_hours"))
    payment_rows = [
        ["Milestone 1: Project Kickoff", "Upon SOW signing", "20%", "Discovery & Design phase"],
        ["Milestone 2: Development Complete", "Core Development delivered", "30%", "All functional requirements implemented"],
        ["Milestone 3: UAT Sign-off", "UAT phase completed", "30%", "User acceptance testing approved"],
        ["Milestone 4: Go-Live", "Production deployment", "20%", "Production deployment and handover complete"],
    ]
    elements.append(_eci_table(
        ["Payment Milestone", "Trigger", "% of Total", "Deliverable"],
        payment_rows,
        [120, 120, 60, 180],
    ))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(
        "<b>Note:</b> Payment terms are subject to negotiation. Infrastructure costs (Section 6) "
        "are billed separately on a monthly basis based on actual consumption.",
        styles["ECIBody"],
    ))
    elements.append(PageBreak())

    # ── 12. Signatures ──
    elements.append(Paragraph("12. Signatures", styles["ECIHeading"]))
    elements.append(HRFlowable(width="30%", thickness=2, color=eci_accent, spaceAfter=8))

    elements.append(Paragraph(
        "By signing below, both parties agree to the terms and conditions outlined in this Statement of Work.",
        styles["ECIBody"],
    ))
    elements.append(Spacer(1, 20))

    sig_data = [
        [Paragraph("<b>For: ECI Consulting</b>", styles["ECIBody"]), Paragraph("", styles["ECIBody"]),
         Paragraph("<b>For: [Client Name]</b>", styles["ECIBody"])],
        [Paragraph("", styles["ECIBody"]), Paragraph("", styles["ECIBody"]), Paragraph("", styles["ECIBody"])],
        [Paragraph("____________________________", styles["ECIBody"]), Paragraph("", styles["ECIBody"]),
         Paragraph("____________________________", styles["ECIBody"])],
        [Paragraph("Name:", styles["ECIBody"]), Paragraph("", styles["ECIBody"]),
         Paragraph("Name:", styles["ECIBody"])],
        [Paragraph("Title:", styles["ECIBody"]), Paragraph("", styles["ECIBody"]),
         Paragraph("Title:", styles["ECIBody"])],
        [Paragraph("Date:", styles["ECIBody"]), Paragraph("", styles["ECIBody"]),
         Paragraph("Date:", styles["ECIBody"])],
    ]
    sig_table = Table(sig_data, colWidths=[200, 80, 200])
    sig_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(sig_table)

    # ── Build PDF ──
    def _sow_footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(rl_colors.Color(27/255, 58/255, 92/255))
        canvas.line(18*mm, 15*mm, A4[0] - 18*mm, 15*mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(rl_colors.Color(100/255, 100/255, 100/255))
        canvas.drawString(18*mm, 10*mm, "ECI Consulting  |  Statement of Work  |  CONFIDENTIAL  |  " + datetime.now().strftime("%B %d, %Y"))
        canvas.drawRightString(A4[0] - 18*mm, 10*mm, "Page " + str(canvas.getPageNumber()))
        canvas.restoreState()

    doc.build(elements, onFirstPage=_sow_footer, onLaterPages=_sow_footer)
    buf.seek(0)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════
#  DISCOVERY PREP DECK PDF  (Agent 9 output)
# ═══════════════════════════════════════════════════════════════════════

def generate_discovery_pdf(discovery_questions: dict):
    """Generate an ECI-branded Discovery Prep Deck PDF."""
    if not HAS_REPORTLAB:
        return None

    buf = io.BytesIO()
    styles = _eci_styles()
    eci_blue   = rl_colors.Color(27/255, 58/255, 92/255)
    eci_accent = rl_colors.Color(0, 180/255, 216/255)
    eci_green  = rl_colors.Color(0, 212/255, 170/255)
    amber      = rl_colors.Color(1, 209/255, 102/255)
    red_col    = rl_colors.Color(1, 107/255, 107/255)
    white      = rl_colors.white
    lt_gray    = rl_colors.Color(245/255, 247/255, 250/255)

    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=22*mm, bottomMargin=18*mm,
                            leftMargin=18*mm, rightMargin=18*mm,
                            title="ECI Discovery Prep Deck", author="ECI Agent 9")

    project_type  = safe_str(discovery_questions.get("project_type", "IT Project"))
    priority_sum  = safe_str(discovery_questions.get("priority_summary", ""))
    total_q       = safe_int(discovery_questions.get("total_questions", 0))
    categories    = safe_list(discovery_questions.get("categories"))

    _PRIORITY_COLORS = {
        "High":   red_col,
        "Medium": amber,
        "Low":    eci_green,
    }

    elements = []

    # ── Cover block ──────────────────────────────────────────────────────
    elements.append(Spacer(1, 10*mm))
    cover_data = [[
        Paragraph("<font color=white><b>ECI</b></font>", styles["ECISmall"]),
        Paragraph(
            "<font color=white><b>Discovery Prep Deck</b></font><br/>"            "<font color=white size=9>" + project_type + "</font>",
            styles["ECITableHeader"]),
        Paragraph(
            "<font color=white size=8>" + datetime.now().strftime("%d %b %Y") + "</font>",
            styles["ECISmall"]),
    ]]
    cover_tbl = Table(cover_data, colWidths=[25*mm, 120*mm, 30*mm])
    cover_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), eci_blue),
        ("TEXTCOLOR",    (0,0), (-1,-1), white),
        ("ALIGN",        (0,0), (-1,-1), "CENTER"),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("TOPPADDING",   (0,0), (-1,-1), 14),
        ("BOTTOMPADDING",(0,0), (-1,-1), 14),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    elements.append(cover_tbl)
    elements.append(Spacer(1, 6*mm))

    # Summary line
    if priority_sum:
        elements.append(Paragraph(priority_sum, styles["ECIBody"]))
    elements.append(Paragraph(
        f"<b>{total_q} discovery questions</b> across {len(categories)} categories.",
        styles["ECIBody"]))
    elements.append(Spacer(1, 6*mm))

    # ── Questions by category ─────────────────────────────────────────────
    for cat in categories:
        c_name     = safe_str(cat.get("name", ""))
        c_icon     = safe_str(cat.get("icon", ""))
        questions  = safe_list(cat.get("questions"))
        if not questions:
            continue

        # Category header
        elements.append(HRFlowable(width="100%", thickness=1, color=eci_accent, spaceAfter=3))
        elements.append(Paragraph(
            f"<b>{c_icon} {c_name}</b>",
            styles["ECIHeading"]))
        elements.append(Spacer(1, 2*mm))

        # Question rows
        for qi, q in enumerate(questions, 1):
            q          = safe_dict(q)
            pri        = safe_str(q.get("priority", "Medium"))
            pri_color  = _PRIORITY_COLORS.get(pri, amber)
            pri_hex    = "#{:02X}{:02X}{:02X}".format(
                int(pri_color.red*255), int(pri_color.green*255), int(pri_color.blue*255))
            q_text     = safe_str(q.get("question", ""))
            why_text   = safe_str(q.get("why", ""))
            follow_up  = safe_str(q.get("follow_up", ""))

            row_data = [[
                Paragraph(f"<b><font color={pri_hex}>{pri}</font></b>", styles["ECITableCell"]),
                Paragraph(
                    f"<b>Q{qi}. {q_text}</b><br/>"                    f"<font color=gray size=8>Why this matters: {why_text}</font>"                    + (f"<br/><font color=#7b61ff size=8>Follow-up: {follow_up}</font>" if follow_up else ""),
                    styles["ECITableCell"]),
            ]]
            row_tbl = Table(row_data, colWidths=[18*mm, 155*mm])
            row_tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,-1), lt_gray),
                ("TOPPADDING",    (0,0), (-1,-1), 6),
                ("BOTTOMPADDING", (0,0), (-1,-1), 6),
                ("LEFTPADDING",   (0,0), (-1,-1), 8),
                ("RIGHTPADDING",  (0,0), (-1,-1), 8),
                ("ROUNDEDCORNERS", [4, 4, 4, 4]),
                ("VALIGN",        (0,0), (-1,-1), "TOP"),
            ]))
            elements.append(row_tbl)
            elements.append(Spacer(1, 2*mm))

        elements.append(Spacer(1, 4*mm))

    # ── Footer note ───────────────────────────────────────────────────────
    elements.append(HRFlowable(width="100%", thickness=1, color=eci_accent, spaceAfter=4))
    elements.append(Paragraph(
        "Generated by ECI Business Estimation Tool — Agent 9: Smart Discovery Question Generator. "        "For internal presales use only.",
        styles["ECISmall"]))

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()
