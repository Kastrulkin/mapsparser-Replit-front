"""Read-only, deterministic exports of a saved content plan."""
from datetime import date, datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape


def fingerprint(plan):
    return sha256(json.dumps(plan, sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def display_date(value):
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    try:
        return datetime.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except (ValueError, TypeError):
        return str(value or "Без даты")


def export_rows(plan):
    rows = []
    for item in plan.get("items", []):
        status = item.get("status")
        label = "Опубликовано" if status == "published" else "На проверке" if status in {"review", "pending_review", "waiting_for_review"} else "Черновик" if item.get("draft_text") else "Идея"
        meta = item.get("metadata_json") or {}
        platforms = meta.get("platforms") if isinstance(meta.get("platforms"), list) else []
        rows.append([item.get("scheduled_for"), item.get("location_label", ""),
                     str(meta.get("platform") or ", ".join(str(value) for value in platforms)), item.get("theme", ""),
                     item.get("goal", ""), item.get("draft_text", ""), label,
                     item.get("source_ref", "")])
    return rows


def render_export(plan, file_format):
    output = BytesIO()
    title = plan.get("title") or "Контент-план"
    context = f"{plan.get('scope_target_label') or ''} · {display_date(plan.get('period_start'))} — {display_date(plan.get('period_end'))}"
    headers = ["Дата", "Точка", "Площадка", "Тема", "Описание идеи", "Текст публикации", "Статус", "Источник / материалы"]
    rows = export_rows(plan)
    if file_format == "xlsx":
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
        book = Workbook()
        sheet = book.active
        sheet.title = "Контент-план"
        for values in [[title], [context], ["Выгружено", datetime.now(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")], headers, *rows]:
            clean = [re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value) if isinstance(value, str) else value for value in values]
            pieces = max([1, *[(len(value) + 29999) // 30000 for value in clean if isinstance(value, str)]])
            for part in range(pieces):
                sheet.append([value[part * 30000:(part + 1) * 30000] if isinstance(value, str) and len(value) > 30000 else value if part == 0 or index in {0, 1, 2, 3, 6} else None for index, value in enumerate(clean)])
        for row in sheet:
            for cell in row:
                if isinstance(cell.value, str):
                    cell.data_type = "s"  # Never interpret customer content as a formula.
                if isinstance(cell.value, datetime):
                    cell.value = cell.value.replace(tzinfo=None)
                if isinstance(cell.value, (date, datetime)):
                    cell.number_format = "dd.mm.yyyy"
                cell.alignment = Alignment(wrap_text=True, vertical="top")
        for cell in sheet[4]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="334155")
        for index, width in enumerate([16, 28, 20, 40, 55, 90, 20, 45], 1):
            sheet.column_dimensions[get_column_letter(index)].width = width
        sheet.freeze_panes = "A5"
        sheet.auto_filter.ref = f"A4:H{max(4, sheet.max_row)}"
        book.save(output)
    elif file_format == "pdf":
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        paths = [Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"), Path("/System/Library/Fonts/Supplemental/Arial.ttf")]
        font = next((path for path in paths if path.exists()), None)
        if not font:
            raise RuntimeError("Шрифт PDF недоступен")
        if "ContentExport" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("ContentExport", str(font)))
        style = ParagraphStyle("body", fontName="ContentExport", fontSize=10, leading=15, spaceAfter=8, splitLongWords=True)
        heading = ParagraphStyle("heading", parent=style, fontSize=16, leading=21, spaceAfter=12, keepWithNext=True)
        label_style = ParagraphStyle("label", parent=style, textColor="#475569", keepWithNext=True)
        paragraph = lambda value, chosen=style: Paragraph(escape(str(value or "")).replace("\n", "<br/>"), chosen)
        story = [paragraph(title, heading), paragraph(context), paragraph(datetime.now(timezone.utc).strftime("Выгружено %d.%m.%Y %H:%M UTC"))]
        for row in rows:
            story.extend([Spacer(1, 12), paragraph(f"{display_date(row[0])} · {row[3]}", heading)])
            for index, (label, value) in enumerate(zip(headers, row)):
                if index in {0, 3}:
                    continue
                if value:
                    # Small paragraphs allow arbitrary long posts to span pages safely.
                    story.append(paragraph(label, label_style))
                    story.extend(paragraph(str(value)[offset:offset + 2500]) for offset in range(0, len(str(value)), 2500))
        def footer(canvas, document):
            canvas.setFont("ContentExport", 9)
            canvas.drawRightString(document.pagesize[0] - 40, 20, str(document.page))
        SimpleDocTemplate(output, rightMargin=40, leftMargin=40, topMargin=36, bottomMargin=36).build(story, onFirstPage=footer, onLaterPages=footer)
    else:
        raise ValueError("Выберите Excel или PDF")
    output.seek(0)
    return output
