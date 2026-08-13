#!/usr/bin/env python3
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = REPO_ROOT / "output" / "pdf" / "localos-checklist-audita-kartochki.pdf"
FONT_REGULAR = Path("/System/Library/Fonts/Supplemental/Verdana.ttf")
FONT_BOLD = Path("/System/Library/Fonts/Supplemental/Verdana Bold.ttf")

ORANGE = colors.HexColor("#FF6B17")
ORANGE_LIGHT = colors.HexColor("#FFF3E9")
INK = colors.HexColor("#071024")
TEXT = colors.HexColor("#44516A")
MUTED = colors.HexColor("#78849A")
LINE = colors.HexColor("#E6E9EF")
WHITE = colors.white


class ChecklistItem(Flowable):
    def __init__(self, text: str, style: ParagraphStyle, width: float):
        super().__init__()
        self.paragraph = Paragraph(text, style)
        self.available_width = width
        _, paragraph_height = self.paragraph.wrap(width - 12 * mm, 100 * mm)
        self.height = max(9 * mm, paragraph_height + 3.5 * mm)

    def wrap(self, available_width, available_height):
        return min(self.available_width, available_width), self.height

    def draw(self):
        box_size = 4.2 * mm
        box_y = self.height - box_size - 2.3 * mm
        self.canv.setStrokeColor(ORANGE)
        self.canv.setLineWidth(1.1)
        self.canv.roundRect(0, box_y, box_size, box_size, 1.2 * mm, stroke=1, fill=0)
        paragraph_width = self.available_width - 8 * mm
        _, paragraph_height = self.paragraph.wrap(paragraph_width, self.height)
        self.paragraph.drawOn(self.canv, 8 * mm, self.height - paragraph_height - 1.3 * mm)
        self.canv.setStrokeColor(LINE)
        self.canv.setLineWidth(0.5)
        self.canv.line(8 * mm, 0.4 * mm, self.available_width, 0.4 * mm)


def build_styles():
    pdfmetrics.registerFont(TTFont("Verdana", str(FONT_REGULAR)))
    pdfmetrics.registerFont(TTFont("Verdana-Bold", str(FONT_BOLD)))
    base = getSampleStyleSheet()
    return {
        "cover_label": ParagraphStyle(
            "CoverLabel", parent=base["Normal"], fontName="Verdana-Bold", fontSize=9,
            leading=12, textColor=ORANGE, spaceAfter=10, uppercase=True,
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle", parent=base["Title"], fontName="Verdana-Bold", fontSize=28,
            leading=34, textColor=INK, alignment=TA_LEFT, spaceAfter=12,
        ),
        "cover_text": ParagraphStyle(
            "CoverText", parent=base["BodyText"], fontName="Verdana", fontSize=11,
            leading=18, textColor=TEXT, spaceAfter=18,
        ),
        "section": ParagraphStyle(
            "Section", parent=base["Heading2"], fontName="Verdana-Bold", fontSize=17,
            leading=22, textColor=INK, spaceBefore=5, spaceAfter=7,
        ),
        "section_intro": ParagraphStyle(
            "SectionIntro", parent=base["BodyText"], fontName="Verdana", fontSize=9.4,
            leading=14, textColor=MUTED, spaceAfter=5,
        ),
        "item": ParagraphStyle(
            "Item", parent=base["BodyText"], fontName="Verdana", fontSize=9.6,
            leading=14, textColor=TEXT,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["BodyText"], fontName="Verdana", fontSize=8.5,
            leading=12.5, textColor=MUTED,
        ),
        "score": ParagraphStyle(
            "Score", parent=base["BodyText"], fontName="Verdana-Bold", fontSize=10,
            leading=14, textColor=INK, alignment=TA_CENTER,
        ),
        "plan": ParagraphStyle(
            "Plan", parent=base["BodyText"], fontName="Verdana", fontSize=9.2,
            leading=14, textColor=TEXT,
        ),
        "cta": ParagraphStyle(
            "Cta", parent=base["BodyText"], fontName="Verdana-Bold", fontSize=10.5,
            leading=15, textColor=WHITE,
        ),
        "cta_link": ParagraphStyle(
            "CtaLink", parent=base["BodyText"], fontName="Verdana-Bold", fontSize=10,
            leading=14, textColor=WHITE, alignment=TA_CENTER,
        ),
    }


SECTIONS = [
    (
        "01. Основная информация",
        "Клиент должен понять, куда он попал и как связаться с компанией.",
        [
            "Название совпадает с вывеской и официальными каналами компании.",
            "Категория точно описывает основной вид деятельности, дополнительные категории не подменяют главную.",
            "Адрес, вход, этаж и ориентиры указаны без двусмысленности.",
            "Телефон, сайт и часы работы актуальны, включая праздники и выходные.",
            "Описание отвечает на вопрос, кому и с какой задачей помогает компания.",
        ],
    ),
    (
        "02. Услуги и цены",
        "Карточка должна помогать выбрать услугу до звонка или перехода на сайт.",
        [
            "Ключевые услуги добавлены отдельно, а не спрятаны в общем описании.",
            "Названия услуг понятны клиенту и совпадают с реальными поисковыми формулировками.",
            "У ключевых услуг есть цена или честный ценовой ориентир.",
            "В описании услуги указан результат, длительность и важные ограничения.",
            "Нет дублей, устаревших услуг и предложений, которые компания больше не оказывает.",
            "Самые важные услуги видны без длинного прокручивания списка.",
        ],
    ),
    (
        "03. Фотографии",
        "Фото должны снижать неопределённость, а не просто заполнять галерею.",
        [
            "Первое фото сразу показывает тип бизнеса и его уровень.",
            "Есть свежие фотографии входа, интерьера, команды, процесса и результата.",
            "Клиент может по фото понять, как найти вход и чего ждать внутри.",
            "Нет размытых, тёмных, устаревших изображений и случайных рекламных макетов.",
            "Новые фотографии появляются регулярно, а не один раз при создании карточки.",
        ],
    ),
    (
        "04. Отзывы и ответы",
        "Отзывы показывают не только рейтинг, но и то, как компания работает с клиентами.",
        [
            "За последние 30 дней появились новые отзывы.",
            "На свежие отзывы есть ответы от компании.",
            "Ответы содержат конкретику и не выглядят одинаковой копипастой.",
            "На претензии отвечают спокойно: признают ситуацию, уточняют факты и предлагают следующий шаг.",
            "В отзывах упоминаются ключевые услуги, результат и причины выбора компании.",
            "Нет признаков искусственной накрутки: одинаковых текстов, резких всплесков и пустых профилей.",
        ],
    ),
    (
        "05. Активность карточки",
        "Живая карточка регулярно подтверждает, что бизнес работает сейчас.",
        [
            "За последний месяц опубликованы новости, предложения или полезные обновления.",
            "Публикации отвечают на реальные вопросы клиентов, а не состоят из общих поздравлений.",
            "Акции имеют понятные условия и срок действия.",
            "Изменения цен, расписания и услуг быстро попадают в карточку.",
            "Компания проверяет карточку на основных картах, а не только на одной площадке.",
        ],
    ),
    (
        "06. Путь до действия",
        "После просмотра карточки клиенту должно быть легко сделать следующий шаг.",
        [
            "Кнопки звонка, маршрута, записи и перехода на сайт работают.",
            "На сайте или в форме записи открывается нужная услуга, а не главная страница без контекста.",
            "Человек понимает, как записаться, сколько ждать ответа и что подготовить к визиту.",
            "UTM-метки или внутренняя аналитика позволяют увидеть переходы из карт.",
            "Компания отслеживает звонки, маршруты, переходы, записи и изменение показателей по неделям.",
        ],
    ),
]


def section_block(title, intro, items, styles, width):
    content = [Paragraph(title, styles["section"]), Paragraph(intro, styles["section_intro"])]
    content.extend(ChecklistItem(item, styles["item"], width) for item in items)
    content.append(Spacer(1, 4 * mm))
    return KeepTogether(content)


def page_decor(canvas, document):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(INK)
    canvas.setFont("Verdana-Bold", 8.5)
    canvas.drawString(18 * mm, height - 12 * mm, "LocalOS")
    canvas.setFillColor(MUTED)
    canvas.setFont("Verdana", 8)
    canvas.drawRightString(width - 18 * mm, height - 12 * mm, "Чек-лист аудита карточки компании")
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9 * mm, "localos.pro")
    canvas.drawRightString(width - 18 * mm, 9 * mm, f"{document.page}")
    canvas.restoreState()


def build_pdf():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    styles = build_styles()
    page_width = A4[0] - 36 * mm
    document = SimpleDocTemplate(
        str(OUTPUT_PATH), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=22 * mm, bottomMargin=20 * mm, title="Чек-лист аудита карточки компании",
        author="LocalOS", subject="Проверка карточки локального бизнеса на картах",
    )

    story = [
        Spacer(1, 8 * mm),
        Paragraph("ПРАКТИЧЕСКИЙ МАТЕРИАЛ LOCALOS", styles["cover_label"]),
        Paragraph("Чек-лист аудита<br/>карточки компании", styles["cover_title"]),
        Paragraph(
            "32 проверки, которые помогут понять, мешает ли карточка клиенту найти, сравнить и выбрать ваш бизнес. "
            "Пройдите список по порядку и отметьте только то, что действительно выполнено.",
            styles["cover_text"],
        ),
    ]

    score_data = [
        [Paragraph("0-12", styles["score"]), Paragraph("13-23", styles["score"]), Paragraph("24-32", styles["score"])],
        [Paragraph("Карточка теряет спрос", styles["small"]), Paragraph("Основа есть, нужна системность", styles["small"]), Paragraph("Карточка помогает выбирать вас", styles["small"])],
    ]
    score_table = Table(score_data, colWidths=[page_width / 3] * 3, rowHeights=[12 * mm, 14 * mm])
    score_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ORANGE_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#FFD1B2")),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#FFD1B2")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    story.extend([
        score_table,
        Spacer(1, 7 * mm),
        Paragraph("Дата проверки: ____________________&nbsp;&nbsp;&nbsp;&nbsp; Компания: ______________________________", styles["small"]),
        Spacer(1, 8 * mm),
        section_block(*SECTIONS[0], styles, page_width),
        PageBreak(),
        section_block(*SECTIONS[1], styles, page_width),
        section_block(*SECTIONS[2], styles, page_width),
        PageBreak(),
        section_block(*SECTIONS[3], styles, page_width),
        section_block(*SECTIONS[4], styles, page_width),
        PageBreak(),
        section_block(*SECTIONS[5], styles, page_width),
        Paragraph("План на ближайшие 7 дней", styles["section"]),
        Paragraph("Не исправляйте всё сразу. Выберите три пункта, которые сильнее всего мешают клиенту сделать следующий шаг.", styles["section_intro"]),
    ])

    plan_rows = [[Paragraph("Приоритет", styles["score"]), Paragraph("Что исправить", styles["score"]), Paragraph("Кто делает", styles["score"]), Paragraph("Срок", styles["score"])]]
    for number in range(1, 4):
        plan_rows.append([Paragraph(str(number), styles["score"]), "", "", ""])
    plan_table = Table(plan_rows, colWidths=[23 * mm, 77 * mm, 42 * mm, 31 * mm], rowHeights=[11 * mm, 20 * mm, 20 * mm, 20 * mm])
    plan_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ORANGE_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.7, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
    ]))
    story.extend([
        plan_table,
        Spacer(1, 8 * mm),
        Table(
            [[Paragraph("Хотите не только проверить карточку, но и снять регулярную работу с себя?", styles["cta"]), Paragraph("localos.pro", styles["cta_link"])]],
            colWidths=[130 * mm, 43 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, -1), INK),
                ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 5 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5 * mm),
            ]),
        ),
    ])

    document.build(story, onFirstPage=page_decor, onLaterPages=page_decor)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    build_pdf()
