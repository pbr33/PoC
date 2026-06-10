# ═══════════════════════════════════════════════════════════════════════
#  EXCEL GENERATORS
# ═══════════════════════════════════════════════════════════════════════

import io
from datetime import datetime

import streamlit as st

from .utils import safe_int, safe_str, safe_list, safe_dict

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, numbers
    from openpyxl.utils import get_column_letter
    from openpyxl.chart import BarChart, PieChart, Reference
except ImportError:
    Workbook = None


def generate_time_excel(time_est, semantic):
    if not Workbook:
        return None
    wb = Workbook()

    # ── Styles ──
    hdr_font = Font(name="Calibri", bold=True, size=12, color="FFFFFF")
    hdr_fill = PatternFill(start_color="1B3A5C", end_color="1B3A5C", fill_type="solid")
    sub_font = Font(name="Calibri", bold=True, size=10, color="1B3A5C")
    sub_fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
    normal_font = Font(name="Calibri", size=10)
    bold_font = Font(name="Calibri", bold=True, size=10)
    total_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    total_font = Font(name="Calibri", bold=True, size=11, color="1B3A5C")
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    center = Alignment(horizontal="center", vertical="center")
    wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)

    def style_header_row(ws, row, cols):
        for c in range(1, cols + 1):
            cell = ws.cell(row=row, column=c)
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = center
            cell.border = thin_border

    def style_cell(ws, row, col, font=normal_font, fill=None, align=None):
        cell = ws.cell(row=row, column=col)
        cell.font = font
        cell.border = thin_border
        if fill:
            cell.fill = fill
        if align:
            cell.alignment = align
        return cell

    # ═══ Sheet 1: Summary ═══
    ws1 = wb.active
    ws1.title = "Summary"
    ws1.sheet_properties.tabColor = "1B3A5C"

    # Title
    ws1.merge_cells("A1:F1")
    title_cell = ws1["A1"]
    title_cell.value = "ECI — Project Time Estimation Summary"
    title_cell.font = Font(name="Calibri", bold=True, size=16, color="1B3A5C")
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 40

    ws1.merge_cells("A2:F2")
    ws1["A2"].value = "Generated: " + datetime.now().strftime("%B %d, %Y %H:%M")
    ws1["A2"].font = Font(name="Calibri", size=9, color="666666")
    ws1["A2"].alignment = Alignment(horizontal="center")

    # Project Info
    row = 4
    ws1.cell(row=row, column=1, value="Project Type").font = bold_font
    ws1.cell(row=row, column=2, value=safe_str(semantic.get("project_type", "N/A"))).font = normal_font
    row += 1
    ws1.cell(row=row, column=1, value="Complexity Score").font = bold_font
    ws1.cell(row=row, column=2, value=str(semantic.get("complexity_score", "N/A")) + " / 10").font = normal_font
    row += 1
    ws1.cell(row=row, column=1, value="Total Requirements").font = bold_font
    ws1.cell(row=row, column=2, value=len(safe_list(semantic.get("requirements")))).font = normal_font

    # Summary metrics
    row = 8
    headers = ["Metric", "Value"]
    for c, h in enumerate(headers, 1):
        ws1.cell(row=row, column=c, value=h)
    style_header_row(ws1, row, len(headers))
    row += 1
    metrics = [
        ("Total Hours", str(safe_int(time_est.get("total_hours"))) + " hours"),
        ("Duration", safe_str(time_est.get("duration_weeks"))),
        ("Confidence", safe_str(time_est.get("confidence"))),
        ("Buffer", safe_str(time_est.get("buffer"))),
    ]
    for label, val in metrics:
        style_cell(ws1, row, 1, font=bold_font).value = label
        style_cell(ws1, row, 2).value = val
        row += 1

    # Three-point estimation
    tp = safe_dict(time_est.get("three_point"))
    if tp:
        row += 1
        ws1.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
        ws1.cell(row=row, column=1, value="Three-Point Estimation").font = Font(name="Calibri", bold=True, size=12, color="1B3A5C")
        row += 1
        headers_tp = ["Scenario", "Hours"]
        for c, h in enumerate(headers_tp, 1):
            ws1.cell(row=row, column=c, value=h)
        style_header_row(ws1, row, len(headers_tp))
        row += 1
        for label, key in [("Optimistic", "optimistic"), ("Most Likely", "most_likely"), ("Pessimistic", "pessimistic")]:
            style_cell(ws1, row, 1, font=bold_font).value = label
            style_cell(ws1, row, 2, align=center).value = safe_int(tp.get(key))
            row += 1

    ws1.column_dimensions["A"].width = 22
    ws1.column_dimensions["B"].width = 30

    # ═══ Sheet 2: Phase Breakdown ═══
    ws2 = wb.create_sheet("Phase Breakdown")
    ws2.sheet_properties.tabColor = "00B4D8"

    ws2.merge_cells("A1:F1")
    ws2["A1"].value = "Phase-wise Effort Breakdown"
    ws2["A1"].font = Font(name="Calibri", bold=True, size=14, color="1B3A5C")
    ws2["A1"].alignment = Alignment(horizontal="center")
    ws2.row_dimensions[1].height = 35

    row = 3
    headers = ["Phase / Week", "Sub-task", "Role", "Dev Low (hrs)", "Dev High (hrs)", "Dev Avg (hrs)", "Justification"]
    for c, h in enumerate(headers, 1):
        ws2.cell(row=row, column=c, value=h)
    style_header_row(ws2, row, len(headers))
    row += 1

    total_hours = safe_int(time_est.get("total_hours", 1))
    grand_low = 0
    grand_high = 0
    grand_avg = 0
    for phase in safe_list(time_est.get("phases")):
        phase = safe_dict(phase)
        phase_name = safe_str(phase.get("name"))
        phase_week = safe_str(phase.get("week_label", ""))
        phase_label = phase_name + (" (" + phase_week + ")" if phase_week else "")
        phase_hours = safe_int(phase.get("hours"))
        phase_low = safe_int(phase.get("low_hours", int(phase_hours * 0.8)))
        phase_high = safe_int(phase.get("high_hours", int(phase_hours * 1.35)))
        tasks = safe_list(phase.get("tasks"))
        if not tasks:
            style_cell(ws2, row, 1, font=sub_font, fill=sub_fill).value = phase_label
            style_cell(ws2, row, 2, fill=sub_fill)
            style_cell(ws2, row, 3, fill=sub_fill)
            style_cell(ws2, row, 4, font=sub_font, fill=sub_fill, align=center).value = phase_low
            style_cell(ws2, row, 5, font=sub_font, fill=sub_fill, align=center).value = phase_high
            style_cell(ws2, row, 6, font=sub_font, fill=sub_fill, align=center).value = phase_hours
            style_cell(ws2, row, 7, fill=sub_fill)
            row += 1
        else:
            first_task = True
            for task in tasks:
                task = safe_dict(task)
                if first_task:
                    style_cell(ws2, row, 1, font=sub_font, fill=sub_fill).value = phase_label
                    first_task = False
                else:
                    style_cell(ws2, row, 1, fill=None)
                t_hrs = safe_int(task.get("hours"))
                t_low = safe_int(task.get("low_hours", int(t_hrs * 0.8)))
                t_high = safe_int(task.get("high_hours", int(t_hrs * 1.35)))
                style_cell(ws2, row, 2).value = safe_str(task.get("name"))
                style_cell(ws2, row, 3).value = safe_str(task.get("role"))
                style_cell(ws2, row, 4, align=center).value = t_low
                style_cell(ws2, row, 5, align=center).value = t_high
                style_cell(ws2, row, 6, align=center).value = t_hrs
                style_cell(ws2, row, 7, align=wrap).value = safe_str(task.get("justification", ""))
                row += 1
            # Phase subtotal
            style_cell(ws2, row, 1, font=bold_font, fill=total_fill)
            style_cell(ws2, row, 2, font=bold_font, fill=total_fill).value = "Subtotal — " + phase_name
            style_cell(ws2, row, 3, fill=total_fill)
            style_cell(ws2, row, 4, font=bold_font, fill=total_fill, align=center).value = phase_low
            style_cell(ws2, row, 5, font=bold_font, fill=total_fill, align=center).value = phase_high
            style_cell(ws2, row, 6, font=bold_font, fill=total_fill, align=center).value = phase_hours
            style_cell(ws2, row, 7, fill=total_fill)
            row += 1
        grand_low += phase_low
        grand_high += phase_high
        grand_avg += phase_hours

    # Grand total
    row += 1
    style_cell(ws2, row, 1, font=total_font, fill=total_fill)
    style_cell(ws2, row, 2, font=total_font, fill=total_fill).value = "GRAND TOTAL"
    style_cell(ws2, row, 3, fill=total_fill)
    style_cell(ws2, row, 4, font=total_font, fill=total_fill, align=center).value = grand_low
    style_cell(ws2, row, 5, font=total_font, fill=total_fill, align=center).value = grand_high
    style_cell(ws2, row, 6, font=total_font, fill=total_fill, align=center).value = grand_avg
    style_cell(ws2, row, 7, fill=total_fill)

    for c, w in [(1, 22), (2, 35), (3, 15), (4, 14), (5, 14), (6, 14), (7, 40)]:
        ws2.column_dimensions[get_column_letter(c)].width = w

    # ═══ Sheet 3: Milestones ═══
    ws3 = wb.create_sheet("Milestones")
    ws3.sheet_properties.tabColor = "00D4AA"

    ws3.merge_cells("A1:D1")
    ws3["A1"].value = "Project Milestones"
    ws3["A1"].font = Font(name="Calibri", bold=True, size=14, color="1B3A5C")
    ws3["A1"].alignment = Alignment(horizontal="center")
    ws3.row_dimensions[1].height = 35

    row = 3
    headers = ["#", "Milestone", "Week", "Description"]
    for c, h in enumerate(headers, 1):
        ws3.cell(row=row, column=c, value=h)
    style_header_row(ws3, row, len(headers))
    row += 1
    for i, m in enumerate(safe_list(time_est.get("milestones")), 1):
        m = safe_dict(m)
        style_cell(ws3, row, 1, align=center).value = i
        style_cell(ws3, row, 2, font=bold_font).value = safe_str(m.get("name"))
        style_cell(ws3, row, 3, align=center).value = safe_int(m.get("week"))
        style_cell(ws3, row, 4, align=wrap).value = safe_str(m.get("description"))
        row += 1

    for c, w in [(1, 6), (2, 30), (3, 10), (4, 45)]:
        ws3.column_dimensions[get_column_letter(c)].width = w

    # ═══ Sheet 4: Three-Point Detail ═══
    ws4 = wb.create_sheet("Three-Point Estimation")
    ws4.sheet_properties.tabColor = "7B61FF"

    ws4.merge_cells("A1:E1")
    ws4["A1"].value = "Three-Point Estimation Detail"
    ws4["A1"].font = Font(name="Calibri", bold=True, size=14, color="1B3A5C")
    ws4["A1"].alignment = Alignment(horizontal="center")
    ws4.row_dimensions[1].height = 35

    row = 3
    headers = ["Phase", "Optimistic (hrs)", "Most Likely (hrs)", "Pessimistic (hrs)", "PERT Estimate (hrs)"]
    for c, h in enumerate(headers, 1):
        ws4.cell(row=row, column=c, value=h)
    style_header_row(ws4, row, len(headers))
    row += 1
    total_o, total_m, total_p, total_pert = 0, 0, 0, 0
    for phase in safe_list(time_est.get("phases")):
        phase = safe_dict(phase)
        ph_hours = safe_int(phase.get("hours"))
        opt = int(ph_hours * 0.8)
        ml = ph_hours
        pes = int(ph_hours * 1.35)
        pert = int((opt + 4 * ml + pes) / 6)
        total_o += opt
        total_m += ml
        total_p += pes
        total_pert += pert
        style_cell(ws4, row, 1, font=bold_font).value = safe_str(phase.get("name"))
        style_cell(ws4, row, 2, align=center).value = opt
        style_cell(ws4, row, 3, align=center).value = ml
        style_cell(ws4, row, 4, align=center).value = pes
        style_cell(ws4, row, 5, align=center, font=bold_font).value = pert
        row += 1

    # Totals
    style_cell(ws4, row, 1, font=total_font, fill=total_fill).value = "TOTAL"
    style_cell(ws4, row, 2, font=total_font, fill=total_fill, align=center).value = total_o
    style_cell(ws4, row, 3, font=total_font, fill=total_fill, align=center).value = total_m
    style_cell(ws4, row, 4, font=total_font, fill=total_fill, align=center).value = total_p
    style_cell(ws4, row, 5, font=total_font, fill=total_fill, align=center).value = total_pert

    for c, w in [(1, 22), (2, 18), (3, 18), (4, 18), (5, 20)]:
        ws4.column_dimensions[get_column_letter(c)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════
#  DETAILED COST ESTIMATE EXCEL (Inflexion Format)
# ═══════════════════════════════════════════════════════════════════════

def generate_cost_excel(cost_est, time_est, semantic):
    """Generate a detailed cost estimate Excel matching Inflexion.xlsx format."""
    if not Workbook:
        return None
    wb = Workbook()

    hdr_font = Font(name="Calibri", bold=True, size=12, color="FFFFFF")
    hdr_fill = PatternFill(start_color="1B3A5C", end_color="1B3A5C", fill_type="solid")
    sub_font = Font(name="Calibri", bold=True, size=10, color="1B3A5C")
    sub_fill = PatternFill(start_color="D6E4F0", end_color="D6E4F0", fill_type="solid")
    normal_font = Font(name="Calibri", size=10)
    bold_font = Font(name="Calibri", bold=True, size=10)
    total_fill = PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid")
    total_font = Font(name="Calibri", bold=True, size=11, color="1B3A5C")
    accent_fill = PatternFill(start_color="1B3A5C", end_color="1B3A5C", fill_type="solid")
    accent_font = Font(name="Calibri", bold=True, size=12, color="FFFFFF")
    warn_fill = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
    currency_fmt = '$#,##0'
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    center = Alignment(horizontal="center", vertical="center")
    wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)

    def style_header_row(ws, row, cols):
        for c in range(1, cols + 1):
            cell = ws.cell(row=row, column=c)
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = center
            cell.border = thin_border

    def style_cell(ws, row, col, font=normal_font, fill=None, align=None, num_fmt=None):
        cell = ws.cell(row=row, column=col)
        cell.font = font
        cell.border = thin_border
        if fill:
            cell.fill = fill
        if align:
            cell.alignment = align
        if num_fmt:
            cell.number_format = num_fmt
        return cell

    # ═══ Sheet 1: Infrastructure Cost Summary ═══
    ws1 = wb.active
    ws1.title = "Infrastructure Costs"
    ws1.sheet_properties.tabColor = "1B3A5C"

    ws1.merge_cells("A1:F1")
    t_cell = ws1["A1"]
    t_cell.value = "ECI — Monthly Infrastructure Cost Estimates"
    t_cell.font = Font(name="Calibri", bold=True, size=16, color="1B3A5C")
    t_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 40

    ws1.merge_cells("A2:F2")
    ws1["A2"].value = "Azure Infrastructure + AI Models  |  Generated: " + datetime.now().strftime("%B %d, %Y %H:%M")
    ws1["A2"].font = Font(name="Calibri", size=9, color="666666")
    ws1["A2"].alignment = Alignment(horizontal="center")

    row = 4
    headers = ["Azure Service / AI Model", "Description & Assumptions", "Low Cost/Mo", "High Cost/Mo", "Average Cost/Mo", "Notes"]
    for c, h in enumerate(headers, 1):
        ws1.cell(row=row, column=c, value=h)
    style_header_row(ws1, row, len(headers))
    row += 1

    azure_costs = safe_list(cost_est.get("azure_costs"))
    third_party = safe_list(cost_est.get("third_party_costs"))

    categories = {}
    for svc in azure_costs:
        svc = safe_dict(svc)
        service_name = safe_str(svc.get("service", ""))
        name_lower = service_name.lower()
        if any(k in name_lower for k in ["openai", "ai search", "foundry", "cognitive", "ml", "embedding"]):
            cat = "AI & ML SERVICES"
        elif any(k in name_lower for k in ["app service", "function", "container", "kubernetes"]):
            cat = "COMPUTE SERVICES"
        elif any(k in name_lower for k in ["blob", "storage", "redis", "cache", "cosmos", "sql"]):
            cat = "DATA & STORAGE SERVICES"
        elif any(k in name_lower for k in ["key vault", "monitor", "insights", "sentinel", "ad "]):
            cat = "SECURITY & MONITORING"
        elif any(k in name_lower for k in ["front door", "cdn", "api management", "service bus", "logic"]):
            cat = "NETWORKING & INTEGRATION"
        else:
            cat = "OTHER SERVICES"
        if cat not in categories:
            categories[cat] = []
        monthly = safe_int(svc.get("monthly_cost", 0))
        categories[cat].append({
            "service": service_name,
            "description": safe_str(svc.get("description", "")),
            "low": int(monthly * 0.85),
            "high": int(monthly * 1.25),
            "average": monthly,
            "notes": safe_str(svc.get("tier", "")),
        })

    if third_party:
        categories["THIRD-PARTY SERVICES"] = []
        for tp in third_party:
            tp = safe_dict(tp)
            monthly = safe_int(tp.get("monthly_cost", 0))
            categories["THIRD-PARTY SERVICES"].append({
                "service": safe_str(tp.get("name", "")),
                "description": safe_str(tp.get("description", "")),
                "low": int(monthly * 0.85),
                "high": int(monthly * 1.25),
                "average": monthly,
                "notes": "",
            })

    grand_low, grand_high, grand_avg = 0, 0, 0
    cat_order = ["AI & ML SERVICES", "COMPUTE SERVICES", "DATA & STORAGE SERVICES",
                 "SECURITY & MONITORING", "NETWORKING & INTEGRATION", "THIRD-PARTY SERVICES", "OTHER SERVICES"]

    for cat_name in cat_order:
        if cat_name not in categories:
            continue
        items = categories[cat_name]
        style_cell(ws1, row, 1, font=sub_font, fill=sub_fill).value = cat_name
        for c in range(2, 7):
            style_cell(ws1, row, c, fill=sub_fill)
        row += 1

        cat_low, cat_high, cat_avg = 0, 0, 0
        for item in items:
            style_cell(ws1, row, 1).value = item["service"]
            style_cell(ws1, row, 2, align=wrap).value = item["description"]
            style_cell(ws1, row, 3, align=center, num_fmt=currency_fmt).value = item["low"]
            style_cell(ws1, row, 4, align=center, num_fmt=currency_fmt).value = item["high"]
            style_cell(ws1, row, 5, align=center, num_fmt=currency_fmt).value = item["average"]
            style_cell(ws1, row, 6).value = item["notes"]
            cat_low += item["low"]
            cat_high += item["high"]
            cat_avg += item["average"]
            row += 1

        style_cell(ws1, row, 1, font=bold_font, fill=total_fill).value = "Subtotal: " + cat_name.title().split(" ")[0]
        style_cell(ws1, row, 2, fill=total_fill)
        style_cell(ws1, row, 3, font=bold_font, fill=total_fill, align=center, num_fmt=currency_fmt).value = cat_low
        style_cell(ws1, row, 4, font=bold_font, fill=total_fill, align=center, num_fmt=currency_fmt).value = cat_high
        style_cell(ws1, row, 5, font=bold_font, fill=total_fill, align=center, num_fmt=currency_fmt).value = cat_avg
        style_cell(ws1, row, 6, fill=total_fill)
        grand_low += cat_low
        grand_high += cat_high
        grand_avg += cat_avg
        row += 2

    style_cell(ws1, row, 1, font=accent_font, fill=accent_fill).value = "TOTAL MONTHLY COST"
    style_cell(ws1, row, 2, fill=accent_fill)
    style_cell(ws1, row, 3, font=accent_font, fill=accent_fill, align=center, num_fmt=currency_fmt).value = grand_low
    style_cell(ws1, row, 4, font=accent_font, fill=accent_fill, align=center, num_fmt=currency_fmt).value = grand_high
    style_cell(ws1, row, 5, font=accent_font, fill=accent_fill, align=center, num_fmt=currency_fmt).value = grand_avg
    style_cell(ws1, row, 6, fill=accent_fill)
    row += 2

    style_cell(ws1, row, 1, font=total_font).value = "ANNUAL PROJECTION (12 MONTHS)"
    style_cell(ws1, row, 2)
    style_cell(ws1, row, 3, font=total_font, align=center, num_fmt=currency_fmt).value = grand_low * 12
    style_cell(ws1, row, 4, font=total_font, align=center, num_fmt=currency_fmt).value = grand_high * 12
    style_cell(ws1, row, 5, font=total_font, align=center, num_fmt=currency_fmt).value = grand_avg * 12
    style_cell(ws1, row, 6)
    row += 3

    style_cell(ws1, row, 1, font=sub_font).value = "KEY ASSUMPTIONS"
    row += 1
    notes_str = safe_str(cost_est.get("notes", ""))
    if notes_str:
        ws1.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        style_cell(ws1, row, 1).value = "\u2022 " + notes_str
        row += 1
    for a in safe_list(cost_est.get("cost_optimization", [])):
        ws1.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        style_cell(ws1, row, 1).value = "\u2022 " + safe_str(a)
        row += 1

    for c, w in [(1, 32), (2, 48), (3, 14), (4, 14), (5, 16), (6, 25)]:
        ws1.column_dimensions[get_column_letter(c)].width = w

    # ═══ Sheet 2: Team & Role Allocation ═══
    ws2 = wb.create_sheet("Team & Roles")
    ws2.sheet_properties.tabColor = "00B4D8"

    ws2.merge_cells("A1:G1")
    ws2["A1"].value = "Team Composition & Role Allocation"
    ws2["A1"].font = Font(name="Calibri", bold=True, size=14, color="1B3A5C")
    ws2["A1"].alignment = Alignment(horizontal="center")
    ws2.row_dimensions[1].height = 35

    row = 3
    headers = ["S.N.", "Role", "Allocation %", "Days", "Hours", "Rate ($/hr)", "Cost"]
    for c, h in enumerate(headers, 1):
        ws2.cell(row=row, column=c, value=h)
    style_header_row(ws2, row, len(headers))
    row += 1

    total_hours_val = safe_int(time_est.get("total_hours", 0))
    total_days_val = max(1, total_hours_val / 7)
    dynamic_roles = safe_list(time_est.get("roles"))
    if not dynamic_roles:
        dynamic_roles = [
            {"name": "Project Manager", "allocation_pct": 0.15, "rate": 125},
            {"name": "Developer", "allocation_pct": 0.60, "rate": 110},
            {"name": "QA Engineer", "allocation_pct": 0.25, "rate": 95},
        ]
    sum_days, sum_hours, sum_cost = 0, 0, 0
    for i, rl in enumerate(dynamic_roles, 1):
        rl = safe_dict(rl)
        role_name = safe_str(rl.get("name", "Team Member"))
        pct = float(rl.get("allocation_pct", 0))
        rate = safe_int(rl.get("rate", 100))
        days = round(total_days_val * pct, 1)
        hours = int(round(days * 7, 0))
        cost = hours * rate
        sum_days += days
        sum_hours += hours
        sum_cost += cost
        style_cell(ws2, row, 1, align=center).value = i
        style_cell(ws2, row, 2, font=bold_font).value = role_name
        style_cell(ws2, row, 3, align=center).value = str(int(pct * 100)) + "%"
        style_cell(ws2, row, 4, align=center).value = days
        style_cell(ws2, row, 5, align=center).value = hours
        style_cell(ws2, row, 6, align=center, num_fmt=currency_fmt).value = rate
        style_cell(ws2, row, 7, align=center, num_fmt=currency_fmt).value = cost
        row += 1

    style_cell(ws2, row, 1, fill=total_fill)
    style_cell(ws2, row, 2, font=total_font, fill=total_fill).value = "TOTAL"
    style_cell(ws2, row, 3, fill=total_fill)
    style_cell(ws2, row, 4, font=total_font, fill=total_fill, align=center).value = round(sum_days, 1)
    style_cell(ws2, row, 5, font=total_font, fill=total_fill, align=center).value = sum_hours
    style_cell(ws2, row, 6, fill=total_fill)
    style_cell(ws2, row, 7, font=total_font, fill=total_fill, align=center, num_fmt=currency_fmt).value = sum_cost

    for c, w in [(1, 6), (2, 30), (3, 14), (4, 10), (5, 10), (6, 14), (7, 14)]:
        ws2.column_dimensions[get_column_letter(c)].width = w

    # ═══ Sheet 3: Project Labor Cost (Three-Point) ═══
    ws3 = wb.create_sheet("Project Labor Cost")
    ws3.sheet_properties.tabColor = "00D4AA"

    ws3.merge_cells("A1:G1")
    ws3["A1"].value = "Project Labor Cost Breakdown (Three-Point Estimation)"
    ws3["A1"].font = Font(name="Calibri", bold=True, size=14, color="1B3A5C")
    ws3["A1"].alignment = Alignment(horizontal="center")
    ws3.row_dimensions[1].height = 35

    row = 3
    headers = ["Phase", "Hours", "% of Total", "Low Cost ($)", "High Cost ($)", "Average Cost ($)", "Notes"]
    for c, h in enumerate(headers, 1):
        ws3.cell(row=row, column=c, value=h)
    style_header_row(ws3, row, len(headers))
    row += 1

    blended_rate = 115
    gl_low, gl_high, gl_avg = 0, 0, 0
    for phase in safe_list(time_est.get("phases")):
        phase = safe_dict(phase)
        ph_name = safe_str(phase.get("name"))
        ph_hours = safe_int(phase.get("hours"))
        low_hrs = safe_int(phase.get("low_hours", int(ph_hours * 0.8)))
        high_hrs = safe_int(phase.get("high_hours", int(ph_hours * 1.35)))
        low_cost = low_hrs * blended_rate
        high_cost = high_hrs * blended_rate
        avg_cost = ph_hours * blended_rate
        gl_low += low_cost
        gl_high += high_cost
        gl_avg += avg_cost
        style_cell(ws3, row, 1, font=bold_font).value = ph_name
        style_cell(ws3, row, 2, align=center).value = ph_hours
        style_cell(ws3, row, 3, align=center).value = safe_str(phase.get("percentage"))
        style_cell(ws3, row, 4, align=center, num_fmt=currency_fmt).value = low_cost
        style_cell(ws3, row, 5, align=center, num_fmt=currency_fmt).value = high_cost
        style_cell(ws3, row, 6, align=center, num_fmt=currency_fmt).value = avg_cost
        style_cell(ws3, row, 7)
        row += 1

    row += 1
    style_cell(ws3, row, 1, font=accent_font, fill=accent_fill).value = "TOTAL PROJECT LABOR"
    style_cell(ws3, row, 2, font=accent_font, fill=accent_fill, align=center).value = safe_int(time_est.get("total_hours"))
    style_cell(ws3, row, 3, font=accent_font, fill=accent_fill, align=center).value = "100%"
    style_cell(ws3, row, 4, font=accent_font, fill=accent_fill, align=center, num_fmt=currency_fmt).value = gl_low
    style_cell(ws3, row, 5, font=accent_font, fill=accent_fill, align=center, num_fmt=currency_fmt).value = gl_high
    style_cell(ws3, row, 6, font=accent_font, fill=accent_fill, align=center, num_fmt=currency_fmt).value = gl_avg
    style_cell(ws3, row, 7, fill=accent_fill)

    for c, w in [(1, 20), (2, 10), (3, 12), (4, 14), (5, 14), (6, 16), (7, 25)]:
        ws3.column_dimensions[get_column_letter(c)].width = w

    # ═══ Sheet 4: Total Cost Summary ═══
    ws4 = wb.create_sheet("Total Cost Summary")
    ws4.sheet_properties.tabColor = "7B61FF"

    ws4.merge_cells("A1:D1")
    ws4["A1"].value = "Total Project Cost Summary"
    ws4["A1"].font = Font(name="Calibri", bold=True, size=16, color="1B3A5C")
    ws4["A1"].alignment = Alignment(horizontal="center")
    ws4.row_dimensions[1].height = 40

    ws4.merge_cells("A2:D2")
    ws4["A2"].value = "ECI Consulting  |  " + datetime.now().strftime("%B %d, %Y")
    ws4["A2"].font = Font(name="Calibri", size=9, color="666666")
    ws4["A2"].alignment = Alignment(horizontal="center")

    row = 4
    headers = ["Cost Category", "Low Estimate ($)", "High Estimate ($)", "Average Estimate ($)"]
    for c, h in enumerate(headers, 1):
        ws4.cell(row=row, column=c, value=h)
    style_header_row(ws4, row, len(headers))
    row += 1

    style_cell(ws4, row, 1, font=sub_font, fill=sub_fill).value = "ONE-TIME COSTS"
    for c in range(2, 5):
        style_cell(ws4, row, c, fill=sub_fill)
    row += 1
    style_cell(ws4, row, 1).value = "Project Labor (Development)"
    style_cell(ws4, row, 2, align=center, num_fmt=currency_fmt).value = gl_low
    style_cell(ws4, row, 3, align=center, num_fmt=currency_fmt).value = gl_high
    style_cell(ws4, row, 4, align=center, num_fmt=currency_fmt).value = gl_avg
    row += 2

    style_cell(ws4, row, 1, font=sub_font, fill=sub_fill).value = "RECURRING COSTS (Monthly)"
    for c in range(2, 5):
        style_cell(ws4, row, c, fill=sub_fill)
    row += 1
    style_cell(ws4, row, 1).value = "Azure Infrastructure"
    style_cell(ws4, row, 2, align=center, num_fmt=currency_fmt).value = grand_low
    style_cell(ws4, row, 3, align=center, num_fmt=currency_fmt).value = grand_high
    style_cell(ws4, row, 4, align=center, num_fmt=currency_fmt).value = grand_avg
    row += 2

    style_cell(ws4, row, 1, font=sub_font, fill=sub_fill).value = "RECURRING COSTS (Annual)"
    for c in range(2, 5):
        style_cell(ws4, row, c, fill=sub_fill)
    row += 1
    style_cell(ws4, row, 1).value = "Azure Infrastructure (x12)"
    style_cell(ws4, row, 2, align=center, num_fmt=currency_fmt).value = grand_low * 12
    style_cell(ws4, row, 3, align=center, num_fmt=currency_fmt).value = grand_high * 12
    style_cell(ws4, row, 4, align=center, num_fmt=currency_fmt).value = grand_avg * 12
    row += 2

    y1_low = gl_low + grand_low * 12
    y1_high = gl_high + grand_high * 12
    y1_avg = gl_avg + grand_avg * 12
    style_cell(ws4, row, 1, font=accent_font, fill=accent_fill).value = "YEAR 1 TOTAL COST"
    style_cell(ws4, row, 2, font=accent_font, fill=accent_fill, align=center, num_fmt=currency_fmt).value = y1_low
    style_cell(ws4, row, 3, font=accent_font, fill=accent_fill, align=center, num_fmt=currency_fmt).value = y1_high
    style_cell(ws4, row, 4, font=accent_font, fill=accent_fill, align=center, num_fmt=currency_fmt).value = y1_avg
    row += 2

    style_cell(ws4, row, 1, font=bold_font, fill=warn_fill).value = "YEAR 2+ ANNUAL (Infra Only)"
    style_cell(ws4, row, 2, font=bold_font, fill=warn_fill, align=center, num_fmt=currency_fmt).value = grand_low * 12
    style_cell(ws4, row, 3, font=bold_font, fill=warn_fill, align=center, num_fmt=currency_fmt).value = grand_high * 12
    style_cell(ws4, row, 4, font=bold_font, fill=warn_fill, align=center, num_fmt=currency_fmt).value = grand_avg * 12

    for c, w in [(1, 36), (2, 20), (3, 20), (4, 20)]:
        ws4.column_dimensions[get_column_letter(c)].width = w

    # ═══ Sheet 5: Assumptions, Prerequisites & Scope ═══
    ws5 = wb.create_sheet("Assumptions & Scope")
    ws5.sheet_properties.tabColor = "FFD166"

    ws5.merge_cells("A1:C1")
    ws5["A1"].value = "Assumptions, Prerequisites & Out-of-Scope"
    ws5["A1"].font = Font(name="Calibri", bold=True, size=14, color="1B3A5C")
    ws5["A1"].alignment = Alignment(horizontal="center")
    ws5.row_dimensions[1].height = 35

    row = 3
    sections_data = [
        ("PREREQUISITES", [
            "Azure subscription with Contributor/Owner access at resource group level",
            "SharePoint Online Read/Write access to document library",
            "Sample documents from all types (PDF, Excel, PPT, Word)",
            "Microsoft Teams admin consent for bot deployment",
            "Azure AD user accounts for MVP users",
            "Service principal credentials with SharePoint API access",
        ]),
        ("KEY ASSUMPTIONS", [
            "Client provides Azure subscription with appropriate access levels",
            "Dedicated product owner available for requirements sign-off and UAT",
            "SME availability minimum 10 hours/week during development",
            "All third-party APIs are documented and accessible",
            "Standard business hours (9 AM - 6 PM) for team availability",
            "Documents are in standard formats without password protection or DRM",
            "Total document size approximately 1-2 GB",
            "SharePoint Online (not on-premise SharePoint Server)",
            "Client responsible for all software licenses and ongoing infrastructure costs",
            "Estimates based on production environment; Dev/staging adds ~40% of prod costs",
            "Pricing based on current Azure pricing; subject to change",
            "Buffer of 10-20% included for usage spikes and scaling",
        ]),
        ("OUT OF SCOPE", [
            "Integration with database systems (SQL, NoSQL, data warehouses)",
            "Web scraping or external data source ingestion",
            "Real-time data feeds or APIs",
            "Multi-language support (English only for MVP)",
            "Custom mobile application development",
            "CI/CD pipeline setup and automation (manual deployments for MVP)",
            "Legacy system decommissioning",
            "End-user training beyond knowledge transfer",
            "Hardware procurement",
            "Penetration testing",
        ]),
    ]

    for sec_title, sec_items in sections_data:
        style_cell(ws5, row, 1, font=sub_font, fill=sub_fill).value = "S.N."
        style_cell(ws5, row, 2, font=sub_font, fill=sub_fill).value = sec_title
        style_cell(ws5, row, 3, fill=sub_fill)
        row += 1
        for i, item in enumerate(sec_items, 1):
            style_cell(ws5, row, 1, align=center).value = i
            ws5.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
            style_cell(ws5, row, 2, align=wrap).value = item
            row += 1
        row += 1

    ws5.column_dimensions["A"].width = 8
    ws5.column_dimensions["B"].width = 70
    ws5.column_dimensions["C"].width = 20

    # ═══ Sheet 6: Week-by-Week Breakdown ═══
    ws6 = wb.create_sheet("Week-by-Week Breakdown")
    ws6.sheet_properties.tabColor = "FF6B6B"

    ws6.merge_cells("A1:F1")
    ws6["A1"].value = "Week-by-Week Task Breakdown"
    ws6["A1"].font = Font(name="Calibri", bold=True, size=14, color="1B3A5C")
    ws6["A1"].alignment = Alignment(horizontal="center")
    ws6.row_dimensions[1].height = 35

    row = 3
    headers = ["Week/Phase", "Task", "Role", "Low (hrs)", "High (hrs)", "Avg (hrs)"]
    for c, h in enumerate(headers, 1):
        ws6.cell(row=row, column=c, value=h)
    style_header_row(ws6, row, len(headers))
    row += 1

    total_hours_est = safe_int(time_est.get("total_hours", 1))
    week_counter = 1
    for phase in safe_list(time_est.get("phases")):
        phase = safe_dict(phase)
        ph_name = safe_str(phase.get("name"))
        ph_hours = safe_int(phase.get("hours"))
        ph_weeks = max(1, ph_hours // 40)
        week_label = "Week " + str(week_counter) + ("-" + str(week_counter + ph_weeks - 1) if ph_weeks > 1 else "") + ": " + ph_name

        style_cell(ws6, row, 1, font=sub_font, fill=sub_fill).value = week_label
        style_cell(ws6, row, 2, fill=sub_fill)
        style_cell(ws6, row, 3, fill=sub_fill)
        low_total = int(ph_hours * 0.8)
        high_total = int(ph_hours * 1.35)
        style_cell(ws6, row, 4, font=sub_font, fill=sub_fill, align=center).value = low_total
        style_cell(ws6, row, 5, font=sub_font, fill=sub_fill, align=center).value = high_total
        style_cell(ws6, row, 6, font=sub_font, fill=sub_fill, align=center).value = ph_hours
        row += 1

        for task in safe_list(phase.get("tasks")):
            task = safe_dict(task)
            t_hours = safe_int(task.get("hours"))
            style_cell(ws6, row, 1)
            style_cell(ws6, row, 2).value = safe_str(task.get("name"))
            style_cell(ws6, row, 3).value = safe_str(task.get("role"))
            style_cell(ws6, row, 4, align=center).value = int(t_hours * 0.8)
            style_cell(ws6, row, 5, align=center).value = int(t_hours * 1.35)
            style_cell(ws6, row, 6, align=center).value = t_hours
            row += 1

        week_counter += ph_weeks

    row += 1
    style_cell(ws6, row, 1, font=accent_font, fill=accent_fill).value = "GRAND TOTAL"
    style_cell(ws6, row, 2, fill=accent_fill)
    style_cell(ws6, row, 3, fill=accent_fill)
    style_cell(ws6, row, 4, font=accent_font, fill=accent_fill, align=center).value = int(total_hours_est * 0.8)
    style_cell(ws6, row, 5, font=accent_font, fill=accent_fill, align=center).value = int(total_hours_est * 1.35)
    style_cell(ws6, row, 6, font=accent_font, fill=accent_fill, align=center).value = total_hours_est

    for c, w in [(1, 28), (2, 35), (3, 18), (4, 12), (5, 12), (6, 12)]:
        ws6.column_dimensions[get_column_letter(c)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════
#  LENOX-STYLE ESTIMATION EXCEL (All Formulas + Comprehensive)
# ═══════════════════════════════════════════════════════════════════════

def generate_lenox_excel(time_est, semantic, cost_est=None, risk_info=None, full_results=None):
    """Generate a comprehensive Lenox-style estimation Excel with real Excel formulas."""
    if not Workbook:
        return None
    wb = Workbook()

    # ── Palette ──
    C_NAVY   = "1B3A5C"
    C_SKY    = "00B4D8"
    C_TEAL   = "00D4AA"
    C_PURPLE = "7B61FF"
    C_GOLD   = "FFD166"
    C_RED    = "FF6B6B"
    C_LGRAY  = "F5F8FC"
    C_DGRAY  = "E2EFDA"
    C_WHITE  = "FFFFFF"

    # ── Shared styles ──
    def _font(bold=False, size=10, color=C_NAVY, name="Calibri"):
        return Font(name=name, bold=bold, size=size, color=color)

    def _fill(hex_color):
        return PatternFill(start_color=hex_color, end_color=hex_color, fill_type="solid")

    def _border():
        s = Side(style="thin", color="CCCCCC")
        return Border(left=s, right=s, top=s, bottom=s)

    def _align(h="left", v="center", wrap=False):
        return Alignment(horizontal=h, vertical=v, wrap_text=wrap)

    def _style(cell, bold=False, size=10, color=C_NAVY, fill_hex=None, halign="left", wrap=False):
        cell.font = _font(bold=bold, size=size, color=color)
        cell.border = _border()
        cell.alignment = _align(h=halign, wrap=wrap)
        if fill_hex:
            cell.fill = _fill(fill_hex)

    def _hdr(ws, row, cols, text=None, fill=C_NAVY, fsize=10):
        for c in range(1, cols + 1):
            cell = ws.cell(row=row, column=c)
            cell.font = Font(name="Calibri", bold=True, size=fsize, color=C_WHITE)
            cell.fill = _fill(fill)
            cell.border = _border()
            cell.alignment = _align(h="center")
        if text:
            ws.cell(row=row, column=1).value = text

    def _title_row(ws, text, span_cols, row=1, bg=C_NAVY):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span_cols)
        c = ws.cell(row=row, column=1, value=text)
        c.font = Font(name="Calibri", bold=True, size=16, color=C_WHITE)
        c.fill = _fill(bg)
        c.alignment = _align(h="center")
        ws.row_dimensions[row].height = 38

    def _sub_title(ws, text, span_cols, row=2, bg=C_SKY):
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span_cols)
        c = ws.cell(row=row, column=1, value=text)
        c.font = Font(name="Calibri", bold=False, size=9, color=C_WHITE)
        c.fill = _fill(bg)
        c.alignment = _align(h="center")
        ws.row_dimensions[row].height = 18

    # ════════════════════════════════════════════════════
    # SHEET 1 — Dashboard (formula-driven KPIs)
    # ════════════════════════════════════════════════════
    ws_dash = wb.active
    ws_dash.title = "Dashboard"
    ws_dash.sheet_properties.tabColor = C_NAVY
    ws_dash.sheet_view.showGridLines = False

    _title_row(ws_dash, "ECI — Project Estimation Dashboard", 6, row=1, bg=C_NAVY)
    _sub_title(ws_dash, "Generated: " + datetime.now().strftime("%B %d, %Y %H:%M") + "  |  Powered by ECI BEAL", 6, row=2, bg=C_SKY)

    proj_labels = [
        ("Project Type",       safe_str(semantic.get("project_type", "N/A"))),
        ("Complexity Score",   str(safe_int(semantic.get("complexity_score", 0))) + " / 10"),
        ("Total Requirements", str(len(safe_list(semantic.get("requirements"))))),
        ("Technology Stack",   ", ".join(str(x) for x in safe_list(semantic.get("technology_stack"))[:6])),
        ("Confidence Level",   safe_str(time_est.get("confidence", "N/A"))),
        ("Risk Level",         safe_str(safe_dict(risk_info).get("overall_level", "N/A")) if risk_info else "N/A"),
    ]
    ws_dash.cell(row=4, column=1, value="PROJECT SUMMARY").font = Font(name="Calibri", bold=True, size=11, color=C_NAVY)
    ws_dash.row_dimensions[4].height = 22
    for i, (lbl, val) in enumerate(proj_labels, start=5):
        ws_dash.cell(row=i, column=1, value=lbl).font = _font(bold=True, size=10, color=C_NAVY)
        ws_dash.cell(row=i, column=2, value=val).font = _font(size=10, color="333333")
        ws_dash.row_dimensions[i].height = 18

    ws_dash.cell(row=12, column=1, value="KPI SUMMARY").font = Font(name="Calibri", bold=True, size=11, color=C_NAVY)
    kpi_headers = ["Metric", "Value", "Unit", "Source Sheet"]
    for ci, h in enumerate(kpi_headers, 1):
        c = ws_dash.cell(row=13, column=ci, value=h)
        c.font = Font(name="Calibri", bold=True, size=10, color=C_WHITE)
        c.fill = _fill(C_NAVY)
        c.border = _border()
        c.alignment = _align(h="center")

    total_hours = safe_int(time_est.get("total_hours", 0))
    tp = safe_dict(time_est.get("three_point", {}))
    phases = safe_list(time_est.get("phases", []))
    monthly_cost = safe_int(safe_dict(cost_est).get("total_monthly_cost", 0)) if cost_est else 0
    annual_cost  = safe_int(safe_dict(cost_est).get("total_annual_cost", 0))  if cost_est else 0
    risk_score   = safe_int(safe_dict(risk_info).get("overall_score", 0))     if risk_info else 0

    kpi_rows = [
        ("Total Person-Hours",  "='Effort Estimation'!B4",  "Hours",    "Effort Estimation"),
        ("Optimistic Hours",    "='Effort Estimation'!B5",  "Hours",    "Effort Estimation"),
        ("Most Likely Hours",   "='Effort Estimation'!B6",  "Hours",    "Effort Estimation"),
        ("Pessimistic Hours",   "='Effort Estimation'!B7",  "Hours",    "Effort Estimation"),
        ("PERT Estimate",       "='Effort Estimation'!B8",  "Hours",    "Effort Estimation"),
        ("Monthly Infra Cost",  "='Cost Estimation'!C4",    "USD/mo",   "Cost Estimation"),
        ("Annual Infra Cost",   "='Cost Estimation'!C5",    "USD/yr",   "Cost Estimation"),
        ("Risk Score",          "='Risk Register'!B4",      "/ 10",     "Risk Register"),
        ("Total Phases",        "='Phase Detail'!B4",       "Phases",   "Phase Detail"),
        ("Req. Count",          "='Requirements'!B4",       "Items",    "Requirements"),
    ]
    for i, (metric, formula, unit, src) in enumerate(kpi_rows, start=14):
        _style(ws_dash.cell(row=i, column=1, value=metric), bold=True,
               fill_hex=C_LGRAY if i % 2 == 0 else None)
        c_val = ws_dash.cell(row=i, column=2, value=formula)
        _style(c_val, halign="center", fill_hex=C_LGRAY if i % 2 == 0 else None)
        _style(ws_dash.cell(row=i, column=3, value=unit), halign="center",
               fill_hex=C_LGRAY if i % 2 == 0 else None)
        _style(ws_dash.cell(row=i, column=4, value=src),
               fill_hex=C_LGRAY if i % 2 == 0 else None)
        ws_dash.row_dimensions[i].height = 18

    ws_dash.column_dimensions["A"].width = 24
    ws_dash.column_dimensions["B"].width = 20
    ws_dash.column_dimensions["C"].width = 14
    ws_dash.column_dimensions["D"].width = 22

    # ════════════════════════════════════════════════════
    # SHEET 2 — Effort Estimation (PERT formula engine)
    # ════════════════════════════════════════════════════
    ws_eff = wb.create_sheet("Effort Estimation")
    ws_eff.sheet_properties.tabColor = C_SKY
    ws_eff.sheet_view.showGridLines = False

    _title_row(ws_eff, "Effort Estimation — Three-Point PERT Analysis", 7, row=1, bg=C_NAVY)
    _sub_title(ws_eff, "PERT = (Optimistic + 4 × Most Likely + Pessimistic) / 6", 7, row=2, bg=C_SKY)

    summary_labels = [
        ("B4", "Total Hours",  total_hours),
        ("B5", "Optimistic",   safe_int(tp.get("optimistic",  int(total_hours * 0.8)))),
        ("B6", "Most Likely",  safe_int(tp.get("most_likely", total_hours))),
        ("B7", "Pessimistic",  safe_int(tp.get("pessimistic", int(total_hours * 1.35)))),
    ]
    for addr, lbl, val in summary_labels:
        row_n = int(addr[1:])
        ws_eff.cell(row=row_n, column=1, value=lbl).font = _font(bold=True)
        c = ws_eff.cell(row=row_n, column=2, value=val)
        c.font = _font(bold=True, size=11)
        c.fill = _fill(C_DGRAY)
        c.border = _border()
        c.alignment = _align(h="center")
        ws_eff.row_dimensions[row_n].height = 20

    ws_eff.cell(row=8, column=1, value="PERT Estimate").font = _font(bold=True)
    c_pert = ws_eff.cell(row=8, column=2, value="=(B5+4*B6+B7)/6")
    c_pert.font = Font(name="Calibri", bold=True, size=12, color=C_WHITE)
    c_pert.fill = _fill(C_NAVY)
    c_pert.border = _border()
    c_pert.alignment = _align(h="center")
    c_pert.number_format = "0.0"
    ws_eff.row_dimensions[8].height = 24

    ws_eff.cell(row=9,  column=1, value="Std Deviation (σ)").font  = _font(bold=True)
    c_sd  = ws_eff.cell(row=9,  column=2, value="=(B7-B5)/6")
    c_sd.border  = _border(); c_sd.alignment  = _align(h="center"); c_sd.number_format  = "0.0"
    ws_eff.cell(row=10, column=1, value="Variance (σ²)").font      = _font(bold=True)
    c_var = ws_eff.cell(row=10, column=2, value="=B9^2")
    c_var.border = _border(); c_var.alignment = _align(h="center"); c_var.number_format = "0.0"
    ws_eff.cell(row=11, column=1, value="90% Confidence (PERT+1.28σ)").font = _font(bold=True)
    c_ci  = ws_eff.cell(row=11, column=2, value="=B8+1.28*B9")
    c_ci.border  = _border(); c_ci.alignment  = _align(h="center"); c_ci.number_format  = "0.0"
    c_ci.fill = _fill(C_LGRAY)

    ws_eff.row_dimensions[13].height = 22
    phase_hdr = ["Phase", "Most Likely (hrs)", "Optimistic (hrs)", "Pessimistic (hrs)",
                 "PERT (hrs)", "Std Dev (σ)", "% of Total"]
    for ci, h in enumerate(phase_hdr, 1):
        c = ws_eff.cell(row=13, column=ci, value=h)
        c.font = Font(name="Calibri", bold=True, size=10, color=C_WHITE)
        c.fill = _fill(C_NAVY)
        c.border = _border()
        c.alignment = _align(h="center")

    data_start = 14
    for pi, phase in enumerate(phases):
        phase = safe_dict(phase)
        ph_name  = safe_str(phase.get("name", "Phase " + str(pi + 1)))
        ph_hours = safe_int(phase.get("hours", 0))
        opt_h    = int(ph_hours * 0.8)
        pes_h    = int(ph_hours * 1.35)
        r_row    = data_start + pi
        fill_hex = C_LGRAY if pi % 2 == 0 else None
        ws_eff.row_dimensions[r_row].height = 18
        _style(ws_eff.cell(r_row, 1, value=ph_name), bold=True, fill_hex=fill_hex)
        c_ml = ws_eff.cell(r_row, 2, value=ph_hours)
        _style(c_ml, halign="center", fill_hex=fill_hex)
        c_op = ws_eff.cell(r_row, 3, value=opt_h)
        _style(c_op, halign="center", fill_hex=fill_hex)
        c_ps = ws_eff.cell(r_row, 4, value=pes_h)
        _style(c_ps, halign="center", fill_hex=fill_hex)
        c_pert_ph = ws_eff.cell(r_row, 5, value="=(C{r}+4*B{r}+D{r})/6".format(r=r_row))
        c_pert_ph.font = Font(name="Calibri", bold=True, size=10, color=C_NAVY)
        c_pert_ph.fill = _fill(C_DGRAY)
        c_pert_ph.border = _border()
        c_pert_ph.alignment = _align(h="center")
        c_pert_ph.number_format = "0.0"
        c_sd_ph = ws_eff.cell(r_row, 6, value="=(D{r}-C{r})/6".format(r=r_row))
        _style(c_sd_ph, halign="center", fill_hex=fill_hex)
        c_sd_ph.number_format = "0.0"
        c_pct = ws_eff.cell(r_row, 7, value="=IF($B$4>0,B{r}/$B$4*100,0)".format(r=r_row))
        _style(c_pct, halign="center", fill_hex=fill_hex)
        c_pct.number_format = "0.0\"%\""

    total_row = data_start + len(phases)
    ws_eff.row_dimensions[total_row].height = 22
    _style(ws_eff.cell(total_row, 1, value="GRAND TOTAL"), bold=True, size=11,
           color=C_WHITE, fill_hex=C_NAVY, halign="center")
    for col_idx, col_letter in [(2, "B"), (3, "C"), (4, "D"), (5, "E")]:
        f = "=SUM({l}{s}:{l}{e})".format(l=col_letter, s=data_start, e=total_row - 1)
        c = ws_eff.cell(total_row, col_idx, value=f)
        c.font = Font(name="Calibri", bold=True, size=11, color=C_WHITE)
        c.fill = _fill(C_NAVY)
        c.border = _border()
        c.alignment = _align(h="center")
        c.number_format = "0.0"
    _style(ws_eff.cell(total_row, 6, value=""), bold=True, color=C_WHITE, fill_hex=C_NAVY, halign="center")
    _style(ws_eff.cell(total_row, 7, value="100%"), bold=True, color=C_WHITE, fill_hex=C_NAVY, halign="center")

    for ci, w in [(1, 26), (2, 18), (3, 18), (4, 18), (5, 16), (6, 14), (7, 14)]:
        ws_eff.column_dimensions[get_column_letter(ci)].width = w

    # ════════════════════════════════════════════════════
    # SHEET 3 — Phase Detail
    # ════════════════════════════════════════════════════
    ws_ph = wb.create_sheet("Phase Detail")
    ws_ph.sheet_properties.tabColor = C_TEAL
    ws_ph.sheet_view.showGridLines = False

    _title_row(ws_ph, "Phase & Task Detail", 7, row=1, bg=C_NAVY)
    _sub_title(ws_ph, "Detailed task breakdown with roles and effort", 7, row=2, bg=C_TEAL)

    ws_ph.cell(row=4, column=1, value="Total Phases").font = _font(bold=True)
    c_tp = ws_ph.cell(row=4, column=2, value=len(phases))
    _style(c_tp, bold=True, halign="center", fill_hex=C_DGRAY)

    ph_cols = ["Phase", "Task / Description", "Role", "Est. Hours",
               "% of Phase", "% of Total", "Notes"]
    ws_ph.row_dimensions[6].height = 22
    for ci, h in enumerate(ph_cols, 1):
        c = ws_ph.cell(6, ci, value=h)
        c.font = Font(name="Calibri", bold=True, size=10, color=C_WHITE)
        c.fill = _fill(C_NAVY)
        c.border = _border()
        c.alignment = _align(h="center")

    total_h = safe_int(time_est.get("total_hours", 1)) or 1
    ph_row = 7
    for phase in phases:
        phase = safe_dict(phase)
        ph_name  = safe_str(phase.get("name", ""))
        ph_hours = safe_int(phase.get("hours", 0))
        tasks    = safe_list(phase.get("tasks", []))
        pct_str  = safe_str(phase.get("percentage", ""))

        ws_ph.merge_cells(start_row=ph_row, start_column=1, end_row=ph_row, end_column=7)
        c_banner = ws_ph.cell(ph_row, 1, value="▶  " + ph_name + "  |  " + str(ph_hours) + " hrs")
        c_banner.font = Font(name="Calibri", bold=True, size=10, color=C_WHITE)
        c_banner.fill = _fill(C_SKY)
        c_banner.border = _border()
        ws_ph.row_dimensions[ph_row].height = 20
        ph_row += 1

        if tasks:
            task_start = ph_row
            for task in tasks:
                task = safe_dict(task)
                th = safe_int(task.get("hours", 0))
                _style(ws_ph.cell(ph_row, 1, value=""), fill_hex=C_LGRAY)
                _style(ws_ph.cell(ph_row, 2, value=safe_str(task.get("name", ""))), wrap=True, fill_hex=C_LGRAY)
                _style(ws_ph.cell(ph_row, 3, value=safe_str(task.get("role", ""))), halign="center", fill_hex=C_LGRAY)
                c_th = ws_ph.cell(ph_row, 4, value=th)
                _style(c_th, halign="center", fill_hex=C_LGRAY)
                c_ppct = ws_ph.cell(ph_row, 5, value="=IF({ph}>0,D{r}/{ph}*100,0)".format(ph=ph_hours or 1, r=ph_row))
                _style(c_ppct, halign="center", fill_hex=C_LGRAY)
                c_ppct.number_format = "0.0\"%\""
                c_tpct = ws_ph.cell(ph_row, 6, value="=IF({tot}>0,D{r}/{tot}*100,0)".format(tot=total_h, r=ph_row))
                _style(c_tpct, halign="center", fill_hex=C_LGRAY)
                c_tpct.number_format = "0.0\"%\""
                _style(ws_ph.cell(ph_row, 7, value=""), fill_hex=C_LGRAY)
                ws_ph.row_dimensions[ph_row].height = 18
                ph_row += 1

            _style(ws_ph.cell(ph_row, 1, value=""), bold=True, fill_hex=C_DGRAY)
            _style(ws_ph.cell(ph_row, 2, value="Subtotal — " + ph_name), bold=True, fill_hex=C_DGRAY)
            _style(ws_ph.cell(ph_row, 3, value=""), fill_hex=C_DGRAY)
            c_sub = ws_ph.cell(ph_row, 4, value="=SUM(D{s}:D{e})".format(s=task_start, e=ph_row - 1))
            c_sub.font = Font(name="Calibri", bold=True, size=10, color=C_NAVY)
            c_sub.fill = _fill(C_DGRAY)
            c_sub.border = _border()
            c_sub.alignment = _align(h="center")
            _style(ws_ph.cell(ph_row, 5, value=pct_str), halign="center", fill_hex=C_DGRAY)
            _style(ws_ph.cell(ph_row, 6, value=""), fill_hex=C_DGRAY)
            _style(ws_ph.cell(ph_row, 7, value=""), fill_hex=C_DGRAY)
            ws_ph.row_dimensions[ph_row].height = 20
            ph_row += 1
        else:
            _style(ws_ph.cell(ph_row, 1, value=ph_name), bold=True)
            _style(ws_ph.cell(ph_row, 2, value="(no sub-tasks)"), color="888888")
            _style(ws_ph.cell(ph_row, 3, value=""))
            _style(ws_ph.cell(ph_row, 4, value=ph_hours), halign="center")
            _style(ws_ph.cell(ph_row, 5, value=pct_str), halign="center")
            _style(ws_ph.cell(ph_row, 6, value=""))
            _style(ws_ph.cell(ph_row, 7, value=""))
            ws_ph.row_dimensions[ph_row].height = 18
            ph_row += 1

    _style(ws_ph.cell(ph_row, 1, value=""), bold=True, color=C_WHITE, fill_hex=C_NAVY)
    _style(ws_ph.cell(ph_row, 2, value="GRAND TOTAL"), bold=True, size=11, color=C_WHITE, fill_hex=C_NAVY)
    _style(ws_ph.cell(ph_row, 3, value=""), color=C_WHITE, fill_hex=C_NAVY)
    c_gt = ws_ph.cell(ph_row, 4, value=total_h)
    c_gt.font = Font(name="Calibri", bold=True, size=11, color=C_WHITE)
    c_gt.fill = _fill(C_NAVY)
    c_gt.border = _border()
    c_gt.alignment = _align(h="center")
    _style(ws_ph.cell(ph_row, 5, value="100%"), bold=True, color=C_WHITE, fill_hex=C_NAVY, halign="center")
    _style(ws_ph.cell(ph_row, 6, value=""), color=C_WHITE, fill_hex=C_NAVY)
    _style(ws_ph.cell(ph_row, 7, value=""), color=C_WHITE, fill_hex=C_NAVY)
    ws_ph.row_dimensions[ph_row].height = 24

    for ci, w in [(1, 20), (2, 32), (3, 18), (4, 14), (5, 12), (6, 12), (7, 22)]:
        ws_ph.column_dimensions[get_column_letter(ci)].width = w

    # ════════════════════════════════════════════════════
    # SHEET 4 — Cost Estimation
    # ════════════════════════════════════════════════════
    ws_cost = wb.create_sheet("Cost Estimation")
    ws_cost.sheet_properties.tabColor = C_GOLD
    ws_cost.sheet_view.showGridLines = False

    _title_row(ws_cost, "Infrastructure & Cost Estimation", 5, row=1, bg=C_NAVY)
    _sub_title(ws_cost, "Azure cloud services + third-party monthly/annual costs", 5, row=2, bg=C_GOLD)

    ws_cost.cell(4, 1, value="Total Monthly Cost").font = _font(bold=True)
    c_mc = ws_cost.cell(4, 2, value="")
    c_mc.font = _font(bold=True, size=11)
    c_mc.fill = _fill(C_DGRAY)
    c_mc.border = _border()
    c_mc.alignment = _align(h="center")
    c_mc.number_format = '"$"#,##0'

    ws_cost.cell(5, 1, value="Total Annual Cost").font = _font(bold=True)
    c_ac = ws_cost.cell(5, 2, value="")
    c_ac.font = _font(bold=True, size=11)
    c_ac.fill = _fill(C_DGRAY)
    c_ac.border = _border()
    c_ac.alignment = _align(h="center")
    c_ac.number_format = '"$"#,##0'

    azure_svcs = safe_list(safe_dict(cost_est).get("azure_costs", [])) if cost_est else []
    third_party = safe_list(safe_dict(cost_est).get("third_party_costs", [])) if cost_est else []

    ws_cost.row_dimensions[7].height = 22
    cost_cols = ["Service / Item", "Tier / Plan", "Monthly Cost (USD)", "Annual Cost (USD)", "Description"]
    for ci, h in enumerate(cost_cols, 1):
        c = ws_cost.cell(7, ci, value=h)
        c.font = Font(name="Calibri", bold=True, size=10, color=C_WHITE)
        c.fill = _fill(C_NAVY)
        c.border = _border()
        c.alignment = _align(h="center")

    cost_row = 8
    azure_start = cost_row
    for svc in azure_svcs:
        svc = safe_dict(svc)
        mc_val = safe_int(svc.get("monthly_cost", 0))
        fill_h = C_LGRAY if (cost_row - azure_start) % 2 == 0 else None
        _style(ws_cost.cell(cost_row, 1, value=safe_str(svc.get("service", ""))), bold=True, fill_hex=fill_h)
        _style(ws_cost.cell(cost_row, 2, value=safe_str(svc.get("tier", ""))), halign="center", fill_hex=fill_h)
        c_mc_cell = ws_cost.cell(cost_row, 3, value=mc_val)
        _style(c_mc_cell, halign="center", fill_hex=fill_h)
        c_mc_cell.number_format = '"$"#,##0'
        c_ac_cell = ws_cost.cell(cost_row, 4, value="=C{r}*12".format(r=cost_row))
        _style(c_ac_cell, halign="center", fill_hex=fill_h)
        c_ac_cell.number_format = '"$"#,##0'
        _style(ws_cost.cell(cost_row, 5, value=safe_str(svc.get("description", ""))), wrap=True, fill_hex=fill_h)
        ws_cost.row_dimensions[cost_row].height = 18
        cost_row += 1
    azure_end = cost_row - 1

    if third_party:
        ws_cost.merge_cells(start_row=cost_row, start_column=1, end_row=cost_row, end_column=5)
        c_sep = ws_cost.cell(cost_row, 1, value="Third-Party Services")
        c_sep.font = Font(name="Calibri", bold=True, size=10, color=C_WHITE)
        c_sep.fill = _fill(C_PURPLE)
        c_sep.border = _border()
        ws_cost.row_dimensions[cost_row].height = 20
        tp_start = cost_row + 1
        cost_row += 1
        for tp_svc in third_party:
            tp_svc = safe_dict(tp_svc)
            mc_val = safe_int(tp_svc.get("monthly_cost", 0))
            fill_h = C_LGRAY if (cost_row - tp_start) % 2 == 0 else None
            _style(ws_cost.cell(cost_row, 1, value=safe_str(tp_svc.get("name", ""))), bold=True, fill_hex=fill_h)
            _style(ws_cost.cell(cost_row, 2, value="SaaS/API"), halign="center", fill_hex=fill_h)
            c_mc_cell = ws_cost.cell(cost_row, 3, value=mc_val)
            _style(c_mc_cell, halign="center", fill_hex=fill_h)
            c_mc_cell.number_format = '"$"#,##0'
            c_ac_cell = ws_cost.cell(cost_row, 4, value="=C{r}*12".format(r=cost_row))
            _style(c_ac_cell, halign="center", fill_hex=fill_h)
            c_ac_cell.number_format = '"$"#,##0'
            _style(ws_cost.cell(cost_row, 5, value=safe_str(tp_svc.get("description", ""))), wrap=True, fill_hex=fill_h)
            ws_cost.row_dimensions[cost_row].height = 18
            cost_row += 1
        tp_end = cost_row - 1
        total_sum_formula_m = "=SUM(C{s}:C{e})".format(s=azure_start, e=tp_end)
        total_sum_formula_a = "=SUM(D{s}:D{e})".format(s=azure_start, e=tp_end)
    else:
        total_sum_formula_m = "=SUM(C{s}:C{e})".format(s=azure_start, e=azure_end)
        total_sum_formula_a = "=SUM(D{s}:D{e})".format(s=azure_start, e=azure_end)

    ws_cost.merge_cells(start_row=cost_row, start_column=1, end_row=cost_row, end_column=2)
    c_tlbl = ws_cost.cell(cost_row, 1, value="TOTAL")
    c_tlbl.font = Font(name="Calibri", bold=True, size=11, color=C_WHITE)
    c_tlbl.fill = _fill(C_NAVY)
    c_tlbl.border = _border()
    c_mc_tot = ws_cost.cell(cost_row, 3, value=total_sum_formula_m)
    c_mc_tot.font = Font(name="Calibri", bold=True, size=11, color=C_WHITE)
    c_mc_tot.fill = _fill(C_NAVY)
    c_mc_tot.border = _border()
    c_mc_tot.alignment = _align(h="center")
    c_mc_tot.number_format = '"$"#,##0'
    c_ac_tot = ws_cost.cell(cost_row, 4, value=total_sum_formula_a)
    c_ac_tot.font = Font(name="Calibri", bold=True, size=11, color=C_WHITE)
    c_ac_tot.fill = _fill(C_NAVY)
    c_ac_tot.border = _border()
    c_ac_tot.alignment = _align(h="center")
    c_ac_tot.number_format = '"$"#,##0'
    _style(ws_cost.cell(cost_row, 5, value=""), color=C_WHITE, fill_hex=C_NAVY)
    ws_cost.row_dimensions[cost_row].height = 24
    ws_cost.cell(4, 2).value = total_sum_formula_m
    ws_cost.cell(5, 2).value = total_sum_formula_a
    ws_cost.cell(4, 3, value=total_sum_formula_m).number_format = '"$"#,##0'
    ws_cost.cell(5, 3, value=total_sum_formula_a).number_format = '"$"#,##0'

    for ci, w in [(1, 28), (2, 16), (3, 20), (4, 20), (5, 35)]:
        ws_cost.column_dimensions[get_column_letter(ci)].width = w

    # ════════════════════════════════════════════════════
    # SHEET 5 — Risk Register
    # ════════════════════════════════════════════════════
    ws_risk = wb.create_sheet("Risk Register")
    ws_risk.sheet_properties.tabColor = C_RED
    ws_risk.sheet_view.showGridLines = False

    _title_row(ws_risk, "Risk Register & Mitigation Plan", 6, row=1, bg=C_NAVY)
    _sub_title(ws_risk, "Risk scoring: Impact × Likelihood (1-5 scale). Score ≤ 8 = Low, ≤ 15 = Medium, > 15 = High", 6, row=2, bg=C_RED)

    ws_risk.cell(4, 1, value="Overall Risk Score").font = _font(bold=True)
    c_rs = ws_risk.cell(4, 2, value=risk_score)
    _style(c_rs, bold=True, halign="center", fill_hex=C_DGRAY)

    risks = safe_list(safe_dict(risk_info).get("risks", [])) if risk_info else []

    risk_cols = ["#", "Category", "Risk Title", "Severity", "Impact (1-5)",
                 "Likelihood (1-5)", "Score (I×L)", "Mitigation Strategy"]
    ws_risk.row_dimensions[6].height = 22
    for ci, h in enumerate(risk_cols, 1):
        c = ws_risk.cell(6, ci, value=h)
        c.font = Font(name="Calibri", bold=True, size=10, color=C_WHITE)
        c.fill = _fill(C_NAVY)
        c.border = _border()
        c.alignment = _align(h="center", wrap=True)

    SEV_MAP = {"Low": (1, 2), "Medium": (2, 3), "High": (4, 4), "Critical": (5, 5)}
    risk_row = 7
    for ri_i, rk in enumerate(risks, 1):
        rk = safe_dict(rk)
        sev = safe_str(rk.get("severity", "Medium"))
        impact, likelihood = SEV_MAP.get(sev, (3, 3))
        fill_sev = {"Low": "E2EFDA", "Medium": "FFF3CD", "High": "FDDEDE",
                    "Critical": "FF6B6B"}.get(sev, C_LGRAY)
        _style(ws_risk.cell(risk_row, 1, value=ri_i), halign="center", fill_hex=C_LGRAY if ri_i % 2 == 0 else None)
        _style(ws_risk.cell(risk_row, 2, value=safe_str(rk.get("category", ""))), fill_hex=C_LGRAY if ri_i % 2 == 0 else None)
        _style(ws_risk.cell(risk_row, 3, value=safe_str(rk.get("title", ""))), bold=True, fill_hex=C_LGRAY if ri_i % 2 == 0 else None)
        c_sev = ws_risk.cell(risk_row, 4, value=sev)
        c_sev.font = Font(name="Calibri", bold=True, size=10, color="333333")
        c_sev.fill = _fill(fill_sev)
        c_sev.border = _border()
        c_sev.alignment = _align(h="center")
        c_imp = ws_risk.cell(risk_row, 5, value=impact)
        _style(c_imp, halign="center", fill_hex=C_LGRAY if ri_i % 2 == 0 else None)
        c_lkh = ws_risk.cell(risk_row, 6, value=likelihood)
        _style(c_lkh, halign="center", fill_hex=C_LGRAY if ri_i % 2 == 0 else None)
        c_score = ws_risk.cell(risk_row, 7, value="=E{r}*F{r}".format(r=risk_row))
        c_score.font = Font(name="Calibri", bold=True, size=10, color=C_NAVY)
        c_score.fill = _fill(fill_sev)
        c_score.border = _border()
        c_score.alignment = _align(h="center")
        _style(ws_risk.cell(risk_row, 8, value=safe_str(rk.get("mitigation", ""))), wrap=True, fill_hex=C_LGRAY if ri_i % 2 == 0 else None)
        ws_risk.row_dimensions[risk_row].height = 32
        risk_row += 1

    for ci, w in [(1, 6), (2, 18), (3, 28), (4, 12), (5, 12), (6, 14), (7, 12), (8, 40)]:
        ws_risk.column_dimensions[get_column_letter(ci)].width = w

    # ════════════════════════════════════════════════════
    # SHEET 6 — Requirements
    # ════════════════════════════════════════════════════
    ws_req = wb.create_sheet("Requirements")
    ws_req.sheet_properties.tabColor = C_PURPLE
    ws_req.sheet_view.showGridLines = False

    _title_row(ws_req, "Requirements Register", 5, row=1, bg=C_NAVY)
    _sub_title(ws_req, "Functional • Non-Functional • Integration requirements extracted by AI", 5, row=2, bg=C_PURPLE)

    reqs = safe_list(semantic.get("requirements", []))
    ws_req.cell(4, 1, value="Total Requirements").font = _font(bold=True)
    c_rq = ws_req.cell(4, 2, value=len(reqs))
    _style(c_rq, bold=True, halign="center", fill_hex=C_DGRAY)

    req_cols = ["#", "Type", "Title", "Complexity", "Description"]
    ws_req.row_dimensions[6].height = 22
    for ci, h in enumerate(req_cols, 1):
        c = ws_req.cell(6, ci, value=h)
        c.font = Font(name="Calibri", bold=True, size=10, color=C_WHITE)
        c.fill = _fill(C_NAVY)
        c.border = _border()
        c.alignment = _align(h="center")

    TYPE_FILL = {"functional": "E8F4FD", "non-functional": "E8F8E8", "integration": "FDF3E8"}
    req_row = 7
    for ri_q, rq in enumerate(reqs, 1):
        rq = safe_dict(rq)
        rq_type = safe_str(rq.get("type", "functional"))
        fill_h = TYPE_FILL.get(rq_type, C_LGRAY)
        _style(ws_req.cell(req_row, 1, value=ri_q), halign="center", fill_hex=fill_h)
        c_type = ws_req.cell(req_row, 2, value=rq_type.title())
        c_type.font = Font(name="Calibri", bold=True, size=9, color="333333")
        c_type.fill = _fill(fill_h)
        c_type.border = _border()
        c_type.alignment = _align(h="center")
        _style(ws_req.cell(req_row, 3, value=safe_str(rq.get("title", ""))), bold=True, fill_hex=fill_h)
        _style(ws_req.cell(req_row, 4, value=safe_str(rq.get("complexity", ""))), halign="center", fill_hex=fill_h)
        _style(ws_req.cell(req_row, 5, value=safe_str(rq.get("description", ""))), wrap=True, fill_hex=fill_h)
        ws_req.row_dimensions[req_row].height = 40
        req_row += 1

    req_row += 1
    for rq_type, fill_h in TYPE_FILL.items():
        f = "=COUNTIF(B7:B{e},\"{t}\")".format(e=req_row - 2, t=rq_type.title())
        ws_req.cell(req_row, 2, value=rq_type.title() + " Count:").font = _font(bold=True)
        c_cnt = ws_req.cell(req_row, 3, value=f)
        _style(c_cnt, bold=True, halign="center", fill_hex=fill_h)
        req_row += 1

    for ci, w in [(1, 6), (2, 18), (3, 30), (4, 14), (5, 55)]:
        ws_req.column_dimensions[get_column_letter(ci)].width = w

    # ════════════════════════════════════════════════════
    # SHEET 7 — Milestones
    # ════════════════════════════════════════════════════
    ws_ms = wb.create_sheet("Milestones")
    ws_ms.sheet_properties.tabColor = C_TEAL
    ws_ms.sheet_view.showGridLines = False

    _title_row(ws_ms, "Project Milestones & Delivery Plan", 5, row=1, bg=C_NAVY)
    _sub_title(ws_ms, "Delivery timeline with cumulative progress tracking", 5, row=2, bg=C_TEAL)

    ms_cols = ["#", "Milestone", "Target Week", "Cumulative Hrs", "Description"]
    ws_ms.row_dimensions[4].height = 22
    for ci, h in enumerate(ms_cols, 1):
        c = ws_ms.cell(4, ci, value=h)
        c.font = Font(name="Calibri", bold=True, size=10, color=C_WHITE)
        c.fill = _fill(C_NAVY)
        c.border = _border()
        c.alignment = _align(h="center")

    milestones = safe_list(time_est.get("milestones", []))
    ms_row = 5
    for mi, m in enumerate(milestones, 1):
        m = safe_dict(m)
        wk = safe_int(m.get("week", 0))
        total_wks = safe_int(str(safe_str(time_est.get("duration_weeks", "1"))).split()[0]) or 1
        cum_hrs_val = int(total_h * wk / max(total_wks, 1))
        fill_h = C_LGRAY if mi % 2 == 0 else None
        _style(ws_ms.cell(ms_row, 1, value=mi), halign="center", fill_hex=fill_h)
        _style(ws_ms.cell(ms_row, 2, value=safe_str(m.get("name", ""))), bold=True, fill_hex=fill_h)
        _style(ws_ms.cell(ms_row, 3, value=wk), halign="center", fill_hex=fill_h)
        c_cum = ws_ms.cell(ms_row, 4, value=cum_hrs_val)
        _style(c_cum, halign="center", fill_hex=fill_h)
        _style(ws_ms.cell(ms_row, 5, value=safe_str(m.get("description", ""))), wrap=True, fill_hex=fill_h)
        ws_ms.row_dimensions[ms_row].height = 28
        ms_row += 1

    for ci, w in [(1, 6), (2, 30), (3, 14), (4, 16), (5, 50)]:
        ws_ms.column_dimensions[get_column_letter(ci)].width = w

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf.getvalue()
