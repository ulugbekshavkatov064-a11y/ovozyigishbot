"""Natijalarni matn va Excel ko'rinishida tayyorlash."""
from html import escape
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from config import Settings
from db import Database, category_key

HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
HEADER_FONT = Font(bold=True, color="FFFFFF")
PLACE_FILLS = {1: "FFD966", 2: "D9D9D9", 3: "F4B183"}  # oltin, kumush, bronza


def sections(s: Settings) -> list[tuple[str, str, str]]:
    """Barcha bo'limlar: (position_key, subject, sarlavha)."""
    out = []
    for p in s.positions:
        if p.has_subjects:
            for subj in s.subjects:
                out.append((p.key, subj, f"{p.name} — {subj}"))
        else:
            out.append((p.key, "", p.name))
    return out


def ranked(rows: list[dict]) -> list[tuple[int, dict]]:
    """Teng ovozlilar bir xil o'rinni oladi (1, 1, 3 ...). 0 ovozlilar o'rin olmaydi."""
    out, place, prev = [], 0, None
    for i, r in enumerate(rows, start=1):
        if r["cnt"] != prev:
            place, prev = i, r["cnt"]
        out.append((place if r["cnt"] > 0 else 0, r))
    return out


def results_text(db: Database, position: str, subject: str, title: str) -> str:
    rows = db.results(position, subject)
    total = db.total_votes(category_key(position, subject))
    lines = [f"📊 <b>{escape(title)}</b> natijalari", f"Jami ovozlar: <b>{total}</b>", ""]
    if not rows:
        lines.append("Qatnashuvchilar yo'q.")
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, (place, r) in enumerate(ranked(rows), start=1):
        mark = medals.get(place, f"{i}.")
        lines.append(f"{mark} {escape(r['name'])} ({escape(r['branch'])}) — <b>{r['cnt']}</b> ta ovoz")
    return "\n".join(lines)


def all_results_text(db: Database, s: Settings) -> list[str]:
    """Barcha bo'limlar natijasi; Telegram limiti (4096) uchun bo'laklarga bo'linadi."""
    blocks = [results_text(db, p, subj, title) for p, subj, title in sections(s)]
    header = (
        f"📋 <b>Barcha natijalar</b>\n"
        f"Jami ovozlar: <b>{db.total_votes()}</b>, ovoz berganlar: <b>{db.total_voters()}</b>"
    )
    chunks, cur = [], header
    for b in blocks:
        if len(cur) + len(b) + 2 > 4000:
            chunks.append(cur)
            cur = b
        else:
            cur += "\n\n" + b
    chunks.append(cur)
    return chunks


def _style_header(ws, ncols: int) -> None:
    for col in range(1, ncols + 1):
        cell = ws.cell(row=1, column=col)
        cell.fill, cell.font = HEADER_FILL, HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.freeze_panes = "A2"


def _autowidth(ws) -> None:
    for col in ws.columns:
        width = max(len(str(c.value or "")) for c in col) + 3
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(width, 45)


def top3_excel(db: Database, s: Settings) -> BytesIO:
    """/result: har bir lavozim va fan bo'yicha 1-2-3 o'rinlar."""
    wb = Workbook()
    ws = wb.active
    ws.title = "1-2-3 o'rinlar"
    ws.append(["Lavozim", "Fan", "O'rin", "Ism familiya", "Filial", "Ovozlar soni"])
    _style_header(ws, 6)
    for p_key, subj, _ in sections(s):
        pos = s.position(p_key)
        winners = [(pl, r) for pl, r in ranked(db.results(p_key, subj)) if 1 <= pl <= 3]
        if not winners:
            ws.append([pos.name, subj or "—", "—", "Ovoz berilmagan", "", 0])
            continue
        for place, r in winners:
            ws.append([pos.name, subj or "—", place, r["name"], r["branch"], r["cnt"]])
            color = PLACE_FILLS.get(place)
            for cell in ws[ws.max_row]:
                cell.fill = PatternFill("solid", fgColor=color)
    _autowidth(ws)
    return _save(wb)


def all_excel(db: Database, s: Settings) -> BytesIO:
    """/all: barcha qatnashuvchilar va ularning ovozlari soni."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Barcha ovozlar"
    ws.append(["Lavozim", "Fan", "O'rin", "Ism familiya", "Filial", "Ovozlar soni"])
    _style_header(ws, 6)
    for p_key, subj, _ in sections(s):
        pos = s.position(p_key)
        for place, r in ranked(db.results(p_key, subj)):
            ws.append([pos.name, subj or "—", place or "—", r["name"], r["branch"], r["cnt"]])
    _autowidth(ws)

    ws2 = wb.create_sheet("Umumiy")
    ws2.append(["Bo'lim", "Jami ovozlar"])
    _style_header(ws2, 2)
    for p_key, subj, title in sections(s):
        ws2.append([title, db.total_votes(category_key(p_key, subj))])
    ws2.append(["JAMI", db.total_votes()])
    ws2.append(["Ovoz bergan foydalanuvchilar", db.total_voters()])
    ws2[ws2.max_row - 1][0].font = Font(bold=True)
    _autowidth(ws2)
    return _save(wb)


def _save(wb: Workbook) -> BytesIO:
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
