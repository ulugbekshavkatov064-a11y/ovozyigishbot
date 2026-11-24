"""Sovg'a sertifikatini PDF ko'rinishida yaratish."""
import os
from io import BytesIO

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
pdfmetrics.registerFont(TTFont("Sans", os.path.join(FONT_DIR, "DejaVuSans.ttf")))
pdfmetrics.registerFont(TTFont("Sans-Bold", os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Serif-Bold", os.path.join(FONT_DIR, "DejaVuSerif-Bold.ttf")))

NAVY = HexColor("#1F3A5F")
GOLD = HexColor("#C9A227")
GREY = HexColor("#555555")
RED = HexColor("#B00020")

WARNING_TEXT = (
    "Diqqat! Ushbu sertifikat oila a'zolaringiz uchun amal qiladi. "
    "O'qiyotgan o'quvchilar uchun emas."
)


def _fit(c: canvas.Canvas, text: str, font: str, size: float, max_w: float) -> float:
    """Matn sig'maguncha shrift o'lchamini kichraytiradi."""
    while size > 10 and pdfmetrics.stringWidth(text, font, size) > max_w:
        size -= 1
    return size


def _wrap(text: str, font: str, size: float, max_w: float) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = f"{cur} {w}".strip()
        if pdfmetrics.stringWidth(test, font, size) <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def make_certificate(full_name: str, prize: str, cert_no: str, date_str: str,
                     org_name: str = "") -> BytesIO:
    buf = BytesIO()
    w, h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setTitle(f"Sertifikat {cert_no}")

    # fon va ramkalar
    c.setFillColor(HexColor("#FFFDF5"))
    c.rect(0, 0, w, h, stroke=0, fill=1)
    c.setStrokeColor(NAVY)
    c.setLineWidth(6)
    c.rect(20, 20, w - 40, h - 40)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.rect(34, 34, w - 68, h - 68)
    # burchak bezaklari
    c.setFillColor(GOLD)
    for x, y in ((34, 34), (w - 34, 34), (34, h - 34), (w - 34, h - 34)):
        c.circle(x, y, 7, stroke=0, fill=1)

    cx = w / 2
    y = h - 115
    if org_name:
        c.setFillColor(GREY)
        c.setFont("Sans-Bold", 14)
        c.drawCentredString(cx, y + 18, org_name.upper())
        y -= 12

    c.setFillColor(NAVY)
    c.setFont("Serif-Bold", 50)
    c.drawCentredString(cx, y - 30, "SERTIFIKAT")
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.5)
    c.line(cx - 170, y - 48, cx + 170, y - 48)

    c.setFillColor(GREY)
    c.setFont("Sans", 15)
    c.drawCentredString(cx, y - 82, "Ushbu sertifikat")

    name = full_name.strip()
    size = _fit(c, name, "Serif-Bold", 34, w - 200)
    c.setFillColor(NAVY)
    c.setFont("Serif-Bold", size)
    c.drawCentredString(cx, y - 125, name)
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.8)
    c.line(cx - 230, y - 143, cx + 230, y - 143)

    c.setFillColor(GREY)
    c.setFont("Sans", 15)
    c.drawCentredString(cx, y - 170, "ovoz berishda faol ishtirok etgani uchun taqdim etiladi.")

    # sovg'a bloki
    box_w, box_h = w - 240, 78
    bx, by = cx - box_w / 2, y - 275
    c.setFillColor(HexColor("#FFF4D1"))
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.roundRect(bx, by, box_w, box_h, 12, stroke=1, fill=1)
    c.setFillColor(GREY)
    c.setFont("Sans", 12)
    c.drawCentredString(cx, by + box_h - 20, "SOVG'A")
    psize = _fit(c, prize, "Sans-Bold", 22, box_w - 30)
    c.setFillColor(NAVY)
    c.setFont("Sans-Bold", psize)
    c.drawCentredString(cx, by + 20, prize)

    # raqam va sana
    c.setFillColor(GREY)
    c.setFont("Sans", 11)
    c.drawString(70, 62, f"Sertifikat raqami: {cert_no}")
    c.drawRightString(w - 70, 62, f"Berilgan sana: {date_str}")

    # ogohlantirish
    lines = _wrap(WARNING_TEXT, "Sans-Bold", 13, w - 200)
    wb_h = 14 + 17 * len(lines)
    c.setFillColor(HexColor("#FDECEC"))
    c.setStrokeColor(RED)
    c.setLineWidth(1)
    c.roundRect(80, 128 - wb_h + 10, w - 160, wb_h, 8, stroke=1, fill=1)
    c.setFillColor(RED)
    c.setFont("Sans-Bold", 13)
    for i, line in enumerate(lines):
        c.drawCentredString(cx, 120 - i * 17, line)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
