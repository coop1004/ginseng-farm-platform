import datetime as dt
from io import BytesIO
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import ParagraphStyle

from app.models import Diagnosis, Farm, WorkLog

pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))

FONT = "HYSMyeongJo-Medium"

TITLE_STYLE = ParagraphStyle(name="Title", fontName=FONT, fontSize=18, leading=22, spaceAfter=12)
H2_STYLE = ParagraphStyle(name="H2", fontName=FONT, fontSize=13, leading=18, spaceBefore=14, spaceAfter=6)
BODY_STYLE = ParagraphStyle(name="Body", fontName=FONT, fontSize=9.5, leading=14)


def generate_farm_report_pdf(
    farm: Farm,
    work_logs: List[WorkLog],
    diagnoses: List[Diagnosis],
    start_date: dt.date,
    end_date: dt.date,
) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
    )
    elements = []

    elements.append(Paragraph(f"{farm.farm_name} 영농일지 리포트", TITLE_STYLE))
    elements.append(
        Paragraph(
            f"기간: {start_date.isoformat()} ~ {end_date.isoformat()}  |  생성일: {dt.date.today().isoformat()}",
            BODY_STYLE,
        )
    )

    elements.append(Paragraph("농장 정보", H2_STYLE))
    farm_table_data = [
        ["농장명", farm.farm_name, "경영주", farm.owner_name],
        ["소재지", farm.address, "지역", farm.region or "-"],
        [
            "면적",
            f"{farm.area_pyeong:g}평 ({farm.area_m2:g}㎡)",
            "시설구분",
            farm.facility_type,
        ],
        ["연차", f"{farm.cultivation_year}년근", "", ""],
    ]
    ft = Table(farm_table_data, colWidths=[25 * mm, 60 * mm, 25 * mm, 60 * mm])
    ft.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F5E9")),
                ("BACKGROUND", (2, 0), (2, -1), colors.HexColor("#E8F5E9")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDBDBD")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(ft)

    elements.append(Paragraph(f"영농작업 내역 ({len(work_logs)}건)", H2_STYLE))
    if work_logs:
        rows = [["일자", "작업면적(㎡)", "작업내용"]]
        for w in work_logs:
            rows.append(
                [
                    w.work_date.isoformat() if w.work_date else "-",
                    f"{w.work_area_m2:g}",
                    Paragraph(w.content or "", BODY_STYLE),
                ]
            )
        wt = Table(rows, colWidths=[25 * mm, 25 * mm, 120 * mm], repeatRows=1)
        wt.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), FONT),
                    ("FONTSIZE", (0, 0), (-1, 0), 9.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2E7D32")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BDBDBD")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
                ]
            )
        )
        elements.append(wt)
    else:
        elements.append(Paragraph("해당 기간 작업 내역이 없습니다.", BODY_STYLE))

    elements.append(Paragraph(f"병해충/생리장애 진단 내역 ({len(diagnoses)}건)", H2_STYLE))
    if diagnoses:
        rows = [["일자", "구분", "진단명", "확신도", "추천 친환경자재"]]
        for d in diagnoses:
            eco_first = "-"
            if d.eco_treatments_json:
                import json

                try:
                    items = json.loads(d.eco_treatments_json)
                    if items:
                        eco_first = items[0].get("product_name", "-")
                except Exception:
                    pass
            rows.append(
                [
                    d.occurrence_date.isoformat() if d.occurrence_date else "-",
                    d.diagnosis_type,
                    d.ai_disease_name or "-",
                    f"{(d.ai_confidence or 0) * 100:.0f}%",
                    Paragraph(eco_first, BODY_STYLE),
                ]
            )
        dtable = Table(rows, colWidths=[22 * mm, 18 * mm, 35 * mm, 18 * mm, 77 * mm], repeatRows=1)
        dtable.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), FONT),
                    ("FONTSIZE", (0, 0), (-1, 0), 9.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EF6C00")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#BDBDBD")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FFF3E0")]),
                ]
            )
        )
        elements.append(dtable)
    else:
        elements.append(Paragraph("해당 기간 진단 내역이 없습니다.", BODY_STYLE))

    elements.append(Spacer(1, 10 * mm))
    elements.append(
        Paragraph(
            "본 리포트는 인삼 농장 AI 영농일지 앱에서 자동 생성되었습니다.",
            ParagraphStyle(name="Footer", fontName=FONT, fontSize=8, textColor=colors.grey),
        )
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer
