from io import BytesIO
from pathlib import Path
from typing import Any, List
from fpdf import FPDF

BASE_DIR = Path(__file__).resolve().parent.parent
FONT_DIR = BASE_DIR / "static" / "fonts"


class PDFReport(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(40, 167, 69)
        self.cell(0, 10, "Smart Fertilizer Advisor - Recommendation Report", align="C", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(40, 167, 69)
        self.line(15, 22, 195, 22)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}} | Educational Guidance - Consult Local Extension Officer", align="C")


def sanitize(text: str) -> str:
    if not text:
        return ""
    # Map common non-latin1 characters
    replacements = {
        "—": "-",
        "–": "-",
        "°": " deg ",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "₹": "Rs ",
        "•": "*",
        "…": "...",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "replace").decode("latin-1")


def build_pdf(prediction: Any, chats: List[Any] = None) -> bytes:
    chats = chats or []
    pdf = PDFReport(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)
    pdf.alias_nb_pages()
    pdf.add_page()

    # Meta
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(50, 50, 50)
    farmer_name = sanitize(prediction.user.name if hasattr(prediction, "user") and prediction.user else "Farmer")
    date_str = prediction.created_at.strftime("%Y-%m-%d %H:%M") if prediction.created_at else "Recent"
    location_str = sanitize(prediction.location or "Manual Location")

    pdf.cell(90, 7, f"Farmer: {farmer_name}", new_x="RIGHT", new_y="TOP")
    pdf.cell(90, 7, f"Date: {date_str}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(90, 7, f"Location: {location_str}", new_x="RIGHT", new_y="TOP")
    pdf.cell(90, 7, f"Report ID: #{prediction.id}", align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # 1. Recommendation Box
    pdf.set_fill_color(240, 248, 240)
    pdf.set_draw_color(40, 167, 69)
    pdf.rect(15, pdf.get_y(), 180, 20, style="FD")
    pdf.set_xy(18, pdf.get_y() + 3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(40, 167, 69)
    fert_name = sanitize(str(prediction.fertilizer))
    pdf.cell(100, 7, f"Recommended Fertilizer: {fert_name}", new_x="RIGHT", new_y="TOP")
    conf_pct = int(round(prediction.confidence * 100))
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(70, 7, f"Confidence: {conf_pct}%", align="R", new_x="LMARGIN", new_y="NEXT")

    pdf.set_xy(18, pdf.get_y())
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(100, 100, 100)
    crop_str = sanitize(str(prediction.crop_type))
    soil_str = sanitize(str(prediction.soil_type))
    pdf.cell(170, 6, f"Crop: {crop_str} | Soil: {soil_str} | Area: {prediction.area_value} {prediction.area_unit}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    # 2. Input Conditions Table
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(0, 6, "1. Recorded Soil & Environment Conditions", new_x="LMARGIN", new_y="NEXT")

    input_data = [
        ["Temperature", f"{prediction.temperature} C", "Humidity", f"{prediction.humidity} %"],
        ["Soil Moisture", f"{prediction.moisture} %", "Soil Texture", soil_str],
        ["Nitrogen (N)", f"{prediction.nitrogen} ({prediction.rating_n})", "Phosphorous (P)", f"{prediction.phosphorous} ({prediction.rating_p})"],
        ["Potassium (K)", f"{prediction.potassium} ({prediction.rating_k})", "Weather Source", sanitize(str(prediction.weather_source or 'manual'))],
    ]
    with pdf.table(col_widths=(45, 45, 45, 45), text_align="LEFT") as table:
        for row in input_data:
            r = table.row()
            for cell in row:
                r.cell(sanitize(str(cell)))
    pdf.ln(4)

    # 3. Dosage & Cost Table
    dosage = prediction.dosage
    if dosage and dosage.get("lines"):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "2. Balanced Product Dosage & Estimated Cost", new_x="LMARGIN", new_y="NEXT")

        headers = ["Product", "Rate (kg/ha)", "Farm Total (kg)", "Bags Needed", "Estimated Cost (INR)"]
        rows = [headers]
        for line in dosage["lines"]:
            rows.append([
                sanitize(str(line["product"])),
                str(line["kg_per_ha"]),
                f"{line['kg_total']} kg",
                f"{line['bags']} (Buy {line['bags_rounded']})",
                f"Rs {line['cost']:,}",
            ])
        rows.append(["Total Estimated Cost", "", "", "", f"Rs {dosage['total_cost']:,}"])

        with pdf.table(col_widths=(40, 35, 35, 35, 35), text_align=("LEFT", "RIGHT", "RIGHT", "RIGHT", "RIGHT")) as table:
            for row in rows:
                r = table.row()
                for cell in row:
                    r.cell(sanitize(str(cell)))
    pdf.ln(4)

    # 4. Split Schedule
    if dosage and dosage.get("schedule"):
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "3. Application Split Schedule", new_x="LMARGIN", new_y="NEXT")
        for stage_item in dosage["schedule"]:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(0, 5, f"- {sanitize(stage_item['stage'])}:", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", "", 9)
            for item in stage_item.get("items", []):
                pdf.cell(10, 5, "", new_x="RIGHT", new_y="TOP")
                pdf.cell(0, 5, f"* {sanitize(item)}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

    # 5. Advisory Chat Q&A Summary
    if chats:
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "4. Agronomy Consultations Summary", new_x="LMARGIN", new_y="NEXT")
        for c in chats[:4]:
            if c.role == "user":
                pdf.set_font("Helvetica", "B", 9)
                pdf.multi_cell(0, 5, f"Q: {sanitize(c.content)}")
            else:
                pdf.set_font("Helvetica", "", 9)
                ans = sanitize(c.content[:600] + ("..." if len(c.content) > 600 else ""))
                pdf.multi_cell(0, 5, f"A: {ans}")
                pdf.ln(2)

    return bytes(pdf.output())
