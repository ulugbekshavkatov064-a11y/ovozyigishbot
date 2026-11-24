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

BLUE = HexColor("#0A1FE0")       # logotip rangi
NAVY = HexColor("#0B1450")
GOLD = HexColor("#C9A227")
GOLD_LIGHT = HexColor("#F3E3A6")
GREY = HexColor("#4A4F63")
RED = HexColor("#B00020")
LOGO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")

WARNING_TEXT = (
    "Diqqat! Ushbu sertifikat oila a'zolaringiz uchun amal qiladi. "
    "O'qiyotgan o'quvchilar uchun emas."
)


def _fit(text: str, font: str, size: float, max_w: float) -> float:
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


def _spaced(c: canvas.Canvas, x: float, y: float, text: str, font: str, size: float, gap: float) -> None:
    """Harflar orasi ochiq, markazlashtirilgan matn."""
    total = sum(pdfmetrics.stringWidth(ch, font, size) for ch in text) + gap * (len(text) - 1)
    cx = x - total / 2
    c.setFont(font, size)
    for ch in text:
        c.drawString(cx, y, ch)
        cx += pdfmetrics.stringWidth(ch, font, size) + gap


def _corner(c: canvas.Canvas, x: float, y: float, sx: int, sy: int) -> None:
    """Burchakdagi ko'k-oltin uchburchak bezak."""
    p = c.beginPath()
    p.moveTo(x, y)
    p.lineTo(x + sx * 150, y)
    p.lineTo(x, y + sy * 150)
    p.close()
    c.setFillColor(NAVY)
    c.drawPath(p, stroke=0, fill=1)
    p = c.beginPath()
    p.moveTo(x, y)
    p.lineTo(x + sx * 105, y)
    p.lineTo(x, y + sy * 105)
    p.close()
    c.setFillColor(BLUE)
    c.drawPath(p, stroke=0, fill=1)
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.line(x + sx * 170, y, x, y + sy * 170)


def _seal(c: canvas.Canvas, x: float, y: float) -> None:
    """Oltin muhr."""
    c.setFillColor(GOLD)
    c.circle(x, y, 38, stroke=0, fill=1)
    c.setStrokeColor(HexColor("#FFFFFF"))
    c.setLineWidth(1.2)
    c.circle(x, y, 32, stroke=1, fill=0)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Sans-Bold", 9)
    c.drawCentredString(x, y + 8, "AL AZIZ")
    c.drawCentredString(x, y - 3, "ACADEMY")
    c.setFont("Sans", 6.5)
    c.drawCentredString(x, y - 14, "★ 2026 ★")


def make_certificate(full_name: str, prize: str, cert_no: str, date_str: str,
                     org_name: str = "") -> BytesIO:
    org_name = (org_name or "AL AZIZ ACADEMY").upper()
    buf = BytesIO()
    w, h = landscape(A4)
    c = canvas.Canvas(buf, pagesize=(w, h))
    c.setTitle(f"Sertifikat {cert_no}")

    # fon
    c.setFillColor(HexColor("#FFFFFF"))
    c.rect(0, 0, w, h, stroke=0, fill=1)
    c.setFillColor(HexColor("#F5F7FF"))
    c.rect(28, 28, w - 56, h - 56, stroke=0, fill=1)

    # burchak bezaklari (chap-yuqori va o'ng-past)
    _corner(c, 0, h, 1, -1)
    _corner(c, w, 0, -1, 1)

    # ramkalar
    c.setStrokeColor(NAVY)
    c.setLineWidth(3)
    c.rect(28, 28, w - 56, h - 56)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1.2)
    c.rect(38, 38, w - 76, h - 76)

    cx = w / 2

    # logo va akademiya nomi
    if os.path.exists(LOGO):
        c.drawImage(LOGO, cx - 26, h - 112, width=52, height=51, mask="auto")
    c.setFillColor(BLUE)
    _spaced(c, cx, h - 132, org_name, "Sans-Bold", 15, 3.5)

    # sarlavha
    c.setFillColor(NAVY)
    _spaced(c, cx, h - 190, "SERTIFIKAT", "Serif-Bold", 46, 6)
    c.setFillColor(GOLD)
    _spaced(c, cx, h - 212, "SOVG'A SERTIFIKATI", "Sans-Bold", 11, 4)
    c.setStrokeColor(GOLD)
    c.setLineWidth(1)
    c.line(cx - 200, h - 222, cx - 60, h - 222)
    c.line(cx + 60, h - 222, cx + 200, h - 222)
    c.setFillColor(GOLD)
    c.circle(cx, h - 222, 3, stroke=0, fill=1)

    c.setFillColor(GREY)
    c.setFont("Sans", 13)
    c.drawCentredString(cx, h - 250, "Ushbu sertifikat egasi")

    name = full_name.strip()
    size = _fit(name, "Serif-Bold", 32, w - 220)
    c.setFillColor(BLUE)
    c.setFont("Serif-Bold", size)
    c.drawCentredString(cx, h - 290, name)
    c.setStrokeColor(NAVY)
    c.setLineWidth(0.7)
    c.line(cx - 220, h - 302, cx + 220, h - 302)

    c.setFillColor(GREY)
    c.setFont("Sans", 13)
    c.drawCentredString(cx, h - 324, "ovoz berishda faol ishtirok etgani uchun quyidagi sovg'a bilan taqdirlanadi:")

    # sovg'a lentasi
    box_w, box_h = w - 260, 56
    bx, by = cx - box_w / 2, h - 398
    c.setFillColor(NAVY)
    for sx in (-1, 1):  # lenta uchlari
        ex = bx if sx < 0 else bx + box_w
        p = c.beginPath()
        p.moveTo(ex, by + 8)
        p.lineTo(ex + sx * 34, by + 8)
        p.lineTo(ex + sx * 22, by + box_h / 2)
        p.lineTo(ex + sx * 34, by + box_h - 8)
        p.lineTo(ex, by + box_h - 8)
        p.close()
        c.drawPath(p, stroke=0, fill=1)
    c.setFillColor(BLUE)
    c.roundRect(bx, by, box_w, box_h, 6, stroke=0, fill=1)
    c.setStrokeColor(GOLD_LIGHT)
    c.setLineWidth(1)
    c.roundRect(bx + 5, by + 5, box_w - 10, box_h - 10, 4, stroke=1, fill=0)
    psize = _fit(prize, "Sans-Bold", 20, box_w - 40)
    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Sans-Bold", psize)
    c.drawCentredString(cx, by + box_h / 2 - psize / 3, prize)

    # raqam, sana va muhr
    c.setFillColor(GREY)
    c.setFont("Sans", 10)
    c.drawString(90, 148, "Sertifikat raqami")
    c.drawRightString(w - 90, 148, "Berilgan sana")
    c.setFillColor(NAVY)
    c.setFont("Sans-Bold", 13)
    c.drawString(90, 130, cert_no)
    c.drawRightString(w - 90, 130, date_str)
    c.setStrokeColor(GOLD)
    c.line(90, 124, 230, 124)
    c.line(w - 230, 124, w - 90, 124)
    _seal(c, cx, 140)

    # ogohlantirish
    lines = _wrap(WARNING_TEXT, "Sans-Bold", 11, w - 170)
    wb_h = 12 + 15 * len(lines)
    c.setFillColor(HexColor("#FDECEC"))
    c.setStrokeColor(RED)
    c.setLineWidth(0.8)
    c.roundRect(75, 54, w - 150, wb_h, 6, stroke=1, fill=1)
    c.setFillColor(RED)
    c.setFont("Sans-Bold", 11)
    for i, line in enumerate(lines):
        c.drawCentredString(cx, 54 + wb_h - 17 - i * 15, line)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf
