from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
from reportlab.pdfgen import canvas

from .storage import WORKSHEETS_DIR


PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_X = 28
MARGIN_Y = 28
ROWS_PER_PAGE = 5
ROW_HEIGHT = (PAGE_HEIGHT - MARGIN_Y * 2) / ROWS_PER_PAGE
LEFT_BLOCK_WIDTH = 82
INFO_BLOCK_WIDTH = 90
TOP_SECTION_HEIGHT = ROW_HEIGHT * 0.68
BOTTOM_GRID_HEIGHT = ROW_HEIGHT - TOP_SECTION_HEIGHT
TOP_HEADER_HEIGHT = 22
INFO_ROW_HEIGHT = (TOP_SECTION_HEIGHT - TOP_HEADER_HEIGHT) / 3
PRACTICE_GRID_HEIGHT = TOP_SECTION_HEIGHT - TOP_HEADER_HEIGHT
PRACTICE_COLUMNS = 8
GRID_COLOR = colors.HexColor("#9EBD85")
TEXT_COLOR = colors.HexColor("#333333")
RED_COLOR = colors.HexColor("#C0352B")
LIGHT_CHAR_COLOR = colors.HexColor("#BBBBBB")


def _register_fonts() -> None:
    try:
        registerFont(UnicodeCIDFont("STSong-Light"))
    except Exception:
        pass


def _draw_grid(c: canvas.Canvas, x: float, y: float, width: float, height: float, columns: int) -> None:
    cell_width = width / columns
    c.setStrokeColor(GRID_COLOR)
    c.setLineWidth(0.6)
    c.rect(x, y, width, height)

    for col in range(1, columns):
        c.line(x + cell_width * col, y, x + cell_width * col, y + height)

    for col in range(columns):
        left = x + cell_width * col
        c.line(left, y + height / 2, left + cell_width, y + height / 2)
        c.line(left + cell_width / 2, y, left + cell_width / 2, y + height)
        c.line(left, y, left + cell_width, y + height)
        c.line(left, y + height, left + cell_width, y)


def _draw_mixed_hint(c: canvas.Canvas, x: float, y: float, max_width: float, text: str) -> None:
    tokens = [token for token in text.split() if token]
    if not tokens:
        return

    font_size = _fit_text(c, " ".join(tokens), max_width, 14, 9)
    cursor_x = x
    for index, token in enumerate(tokens):
        color = RED_COLOR if index % 2 == 0 else colors.black
        c.setFillColor(color)
        c.setFont("STSong-Light", font_size)
        c.drawString(cursor_x, y, token)
        cursor_x += stringWidth(token, "STSong-Light", font_size) + 4
        if cursor_x >= x + max_width:
            break


def _fit_text(c: canvas.Canvas, text: str, width: float, max_size: int, min_size: int = 10) -> int:
    size = max_size
    while size > min_size and stringWidth(text, "STSong-Light", size) > width:
        size -= 1
    return size


def _draw_row(c: canvas.Canvas, card: dict, row_index: int) -> None:
    top = PAGE_HEIGHT - MARGIN_Y - row_index * ROW_HEIGHT
    bottom = top - ROW_HEIGHT
    right = PAGE_WIDTH - MARGIN_X
    left = MARGIN_X
    top_section_bottom = top - TOP_SECTION_HEIGHT
    info_left = left + LEFT_BLOCK_WIDTH
    practice_left = info_left + INFO_BLOCK_WIDTH

    c.setStrokeColor(GRID_COLOR)
    c.setLineWidth(0.8)
    c.rect(left, bottom, right - left, ROW_HEIGHT)
    c.line(info_left, top_section_bottom, info_left, top)
    c.line(practice_left, top_section_bottom, practice_left, top)
    c.line(left, top_section_bottom, right, top_section_bottom)
    c.line(info_left, top - TOP_HEADER_HEIGHT, right, top - TOP_HEADER_HEIGHT)
    c.line(info_left, top - TOP_HEADER_HEIGHT - INFO_ROW_HEIGHT, practice_left, top - TOP_HEADER_HEIGHT - INFO_ROW_HEIGHT)
    c.line(info_left, top - TOP_HEADER_HEIGHT - INFO_ROW_HEIGHT * 2, practice_left, top - TOP_HEADER_HEIGHT - INFO_ROW_HEIGHT * 2)

    _draw_grid(c, left, top_section_bottom, LEFT_BLOCK_WIDTH, TOP_SECTION_HEIGHT, 2)
    _draw_grid(c, left, bottom, LEFT_BLOCK_WIDTH, BOTTOM_GRID_HEIGHT, 2)
    _draw_grid(c, info_left, bottom, INFO_BLOCK_WIDTH, BOTTOM_GRID_HEIGHT, 2)

    practice_width = right - practice_left
    _draw_grid(c, practice_left, top_section_bottom, practice_width, PRACTICE_GRID_HEIGHT, PRACTICE_COLUMNS)
    _draw_grid(c, practice_left, bottom, practice_width, BOTTOM_GRID_HEIGHT, PRACTICE_COLUMNS)

    big_char_size = min(LEFT_BLOCK_WIDTH * 0.86, TOP_SECTION_HEIGHT * 0.82)
    c.setFont("STSong-Light", big_char_size)
    c.setFillColor(TEXT_COLOR)
    c.drawCentredString(
        left + LEFT_BLOCK_WIDTH / 2,
        top_section_bottom + TOP_SECTION_HEIGHT / 2 - big_char_size * 0.34,
        card.get("char", ""),
    )

    info_x = info_left + 8
    c.setFont("STSong-Light", 12)
    c.setFillColor(TEXT_COLOR)
    c.drawCentredString(info_left + INFO_BLOCK_WIDTH / 2, top - 16, card.get("pinyin", ""))
    c.setFont("STSong-Light", 10)
    radical_y = top - TOP_HEADER_HEIGHT - 15
    strokes_y = radical_y - INFO_ROW_HEIGHT
    structure_y = strokes_y - INFO_ROW_HEIGHT
    c.drawString(info_x, radical_y, f"部首：{card.get('radical', '—')}")
    c.drawString(info_x, strokes_y, f"笔画：{card.get('stroke_count', '—')}画")
    c.drawString(info_x, structure_y, f"结构：{card.get('structure', '—')}")

    model_text = card.get("stroke_hint") or " ".join(card.get("components", [])) or card.get("char", "")
    _draw_mixed_hint(c, practice_left + 8, top - 15, practice_width - 12, model_text)

    c.setFillColor(LIGHT_CHAR_COLOR)
    first_cell_center_x = practice_left + (practice_width / PRACTICE_COLUMNS) / 2
    cell_width = practice_width / PRACTICE_COLUMNS
    guide_char_size = min(cell_width * 0.9, PRACTICE_GRID_HEIGHT * 0.88)
    c.setFont("STSong-Light", guide_char_size)
    for column in range(PRACTICE_COLUMNS):
        char_x = first_cell_center_x + cell_width * column
        c.drawCentredString(
            char_x,
            top_section_bottom + PRACTICE_GRID_HEIGHT / 2 - guide_char_size * 0.34,
            card.get("char", ""),
        )


def generate_handwriting_worksheet(pack: dict) -> dict:
    _register_fonts()

    week_id = pack["week_id"]
    target_dir = WORKSHEETS_DIR / week_id
    target_dir.mkdir(parents=True, exist_ok=True)
    output_path = target_dir / "handwriting_practice.pdf"

    c = canvas.Canvas(str(output_path), pagesize=A4)
    cards = list(pack.get("char_cards", []))

    for index, card in enumerate(cards):
        row_index = index % ROWS_PER_PAGE
        if index > 0 and row_index == 0:
            c.showPage()
            _register_fonts()
        _draw_row(c, card, row_index)

    c.save()

    return {
        "status": "ready",
        "file_path": f"/assets/worksheets/{week_id}/handwriting_practice.pdf",
        "page_size": "A4",
        "entries": len(cards),
    }
