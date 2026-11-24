import asyncio
import logging
from html import escape

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

import reports
from config import Settings, load_data, load_settings
from db import Database, category_key

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("ovoz_bot")

BTN_VOTE = "🗳 Ovoz berish"
BTN_RESULTS = "📊 Natijalar"

settings: Settings = load_settings()
log.info("Ma'lumotlar bazasi: %s", settings.db_path)
db = Database(settings.db_path)
db.sync_candidates(settings.candidates)


def apply_saved_period() -> None:
    """/goo orqali belgilangan muddat bazada saqlanadi va .env dagidan ustun turadi."""
    from datetime import datetime as _dt
    s, e = db.get_setting("vote_start"), db.get_setting("vote_end")
    if s and e:
        settings.vote_start = _dt.fromisoformat(s).astimezone(settings.tz)
        settings.vote_end = _dt.fromisoformat(e).astimezone(settings.tz)


apply_saved_period()
router = Router()


# ======================= yordamchi funksiyalar =======================
def is_admin(user_id: int) -> bool:
    return user_id in settings.admin_ids


def fmt_dt(dt) -> str:
    return dt.strftime("%d.%m.%Y %H:%M")


def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_VOTE), KeyboardButton(text=BTN_RESULTS)]],
        resize_keyboard=True,
    )


def ikb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows]
    )


def positions_kb(prefix: str) -> InlineKeyboardMarkup:
    rows = [[(f"{i}) {p.name}", f"{prefix}:p:{p.key}")] for i, p in enumerate(settings.positions, 1)]
    return ikb(rows)


def subjects_kb(prefix: str) -> InlineKeyboardMarkup:
    rows = [[(subj, f"{prefix}:s:{i}")] for i, subj in enumerate(settings.subjects)]
    rows.append([("⬅️ Orqaga", f"{prefix}:back")])
    return ikb(rows)


def candidates_kb(position: str, subject: str) -> InlineKeyboardMarkup:
    rows = [
        [(f"{c['name']} — {c['branch']}", f"v:c:{c['id']}")]
        for c in db.get_candidates(position, subject)
    ]
    back = "v:backs" if subject else "v:back"
    rows.append([("⬅️ Orqaga", back)])
    return ikb(rows)


def sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Kanalga obuna bo'lish", url=settings.channel_url)],
            [InlineKeyboardButton(text="✅ Obuna bo'ldim", callback_data="chk")],
        ]
    )


def section_title(position: str, subject: str) -> str:
    pos = settings.position(position)
    return f"{pos.name} — {subject}" if subject else pos.name


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    if not settings.channel_id:
        return True
    try:
        m = await bot.get_chat_member(settings.channel_id, user_id)
    except TelegramBadRequest as e:
        log.error("Obunani tekshirib bo'lmadi (bot kanalda admin ekanini tekshiring): %s", e)
        return False
    if m.status in (ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR):
        return True
    return m.status == ChatMemberStatus.RESTRICTED and getattr(m, "is_member", False)


def voting_closed_text() -> str | None:
    st = settings.voting_status()
    if st == "before":
        return (
            f"⏳ Ovoz berish hali boshlanmadi.\n"
            f"Muddat: <b>{fmt_dt(settings.vote_start)}</b> — <b>{fmt_dt(settings.vote_end)}</b>"
        )
    if st == "after":
        return (
            "⛔️ Ovoz berish muddati tugagan.\n"
            f"Natijalarni «{BTN_RESULTS}» tugmasi orqali ko'rishingiz mumkin."
        )
    return None


async def safe_edit(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except TelegramBadRequest as e:
        if "not modified" not in str(e):
            await call.message.answer(text, reply_markup=kb)


async def guard(call: CallbackQuery, bot: Bot) -> bool:
    """Har bir ovoz berish bosqichida muddat va obunani tekshiradi."""
    closed = voting_closed_text()
    if closed:
        await safe_edit(call, closed)
        await call.answer()
        return False
    if not await is_subscribed(bot, call.from_user.id):
        await safe_edit(call, "❗️ Ovoz berish uchun avval kanalga obuna bo'ling:", sub_kb())
        await call.answer()
        return False
    return True


# ======================= foydalanuvchi =======================
@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    u = message.from_user
    db.save_user(u.id, u.full_name, u.username)
    await message.answer(
        f"Assalomu alaykum, <b>{escape(u.first_name)}</b>!\n\n"
        f"Ovoz berish muddati: <b>{fmt_dt(settings.vote_start)}</b> — <b>{fmt_dt(settings.vote_end)}</b>\n"
        "Kerakli bo'limni tanlang 👇",
        reply_markup=main_kb(),
    )


@router.message(F.text == BTN_VOTE)
async def vote_entry(message: Message, bot: Bot) -> None:
    closed = voting_closed_text()
    if closed:
        await message.answer(closed)
        return
    if not await is_subscribed(bot, message.from_user.id):
        await message.answer("❗️ Ovoz berish uchun avval kanalga obuna bo'ling:", reply_markup=sub_kb())
        return
    await message.answer("👔 Lavozimni tanlang:", reply_markup=positions_kb("v"))


@router.callback_query(F.data == "chk")
async def check_sub(call: CallbackQuery, bot: Bot) -> None:
    if not await is_subscribed(bot, call.from_user.id):
        await call.answer("Siz hali kanalga obuna bo'lmadingiz!", show_alert=True)
        return
    if not await guard(call, bot):
        return
    await safe_edit(call, "👔 Lavozimni tanlang:", positions_kb("v"))
    await call.answer("Rahmat! ✅")


@router.callback_query(F.data == "v:back")
async def vote_back(call: CallbackQuery, bot: Bot) -> None:
    if await guard(call, bot):
        await safe_edit(call, "👔 Lavozimni tanlang:", positions_kb("v"))
        await call.answer()


@router.callback_query(F.data == "v:backs")
async def vote_back_subjects(call: CallbackQuery, bot: Bot) -> None:
    if await guard(call, bot):
        await safe_edit(call, "📚 Qaysi fan ustoziga ovoz bermoqchisiz?", subjects_kb("v"))
        await call.answer()


async def show_candidates(call: CallbackQuery, position: str, subject: str) -> None:
    cat = category_key(position, subject)
    title = section_title(position, subject)
    if db.has_voted(call.from_user.id, cat):
        text = "ℹ️ Siz bu bo'limga allaqachon ovoz bergansiz.\n\n" + reports.results_text(db, position, subject, title)
        await safe_edit(call, text, ikb([[("⬅️ Orqaga", "v:backs" if subject else "v:back")]]))
        return
    if not db.get_candidates(position, subject):
        await safe_edit(call, f"<b>{escape(title)}</b>\n\nHozircha qatnashuvchilar yo'q.",
                        ikb([[("⬅️ Orqaga", "v:backs" if subject else "v:back")]]))
        return
    await safe_edit(
        call,
        f"<b>{escape(title)}</b>\n\nQuyidagi qatnashuvchilardan biriga ovoz bering 👇\n"
        "<i>Diqqat: har bir bo'limga faqat 1 marta ovoz berish mumkin.</i>",
        candidates_kb(position, subject),
    )


@router.callback_query(F.data.startswith("v:p:"))
async def vote_position(call: CallbackQuery, bot: Bot) -> None:
    if not await guard(call, bot):
        return
    pos = settings.position(call.data[4:])
    if pos is None:
        await call.answer("Bo'lim topilmadi", show_alert=True)
        return
    if pos.has_subjects:
        await safe_edit(call, "📚 Qaysi fan ustoziga ovoz bermoqchisiz?", subjects_kb("v"))
    else:
        await show_candidates(call, pos.key, "")
    await call.answer()


@router.callback_query(F.data.startswith("v:s:"))
async def vote_subject(call: CallbackQuery, bot: Bot) -> None:
    if not await guard(call, bot):
        return
    idx = int(call.data[4:])
    if idx >= len(settings.subjects):
        await call.answer("Fan topilmadi", show_alert=True)
        return
    pos = next(p for p in settings.positions if p.has_subjects)
    await show_candidates(call, pos.key, settings.subjects[idx])
    await call.answer()


@router.callback_query(F.data.startswith("v:c:"))
async def vote_candidate(call: CallbackQuery, bot: Bot) -> None:
    if not await guard(call, bot):
        return
    cand = db.get_candidate(int(call.data[4:]))
    if cand is None or not cand["active"]:
        await call.answer("Qatnashuvchi topilmadi", show_alert=True)
        return
    position, subject = cand["position"], cand["subject"]
    title = section_title(position, subject)
    u = call.from_user
    db.save_user(u.id, u.full_name, u.username)
    if db.add_vote(u.id, category_key(position, subject), cand["id"]):
        head = f"✅ Ovozingiz qabul qilindi: <b>{escape(cand['name'])}</b> ({escape(cand['branch'])})\n\n"
        await call.answer("Ovozingiz qabul qilindi ✅")
    else:
        head = "ℹ️ Siz bu bo'limga allaqachon ovoz bergansiz.\n\n"
        await call.answer("Siz bu bo'limga avval ovoz bergansiz", show_alert=True)
    text = head + reports.results_text(db, position, subject, title)
    await safe_edit(call, text, ikb([[("⬅️ Boshqa bo'limga ovoz berish", "v:back")]]))


# ======================= natijalar =======================
def results_allowed(user_id: int) -> bool:
    return not settings.results_admin_only or is_admin(user_id)


@router.message(F.text == BTN_RESULTS)
async def results_entry(message: Message) -> None:
    if not results_allowed(message.from_user.id):
        await message.answer("Natijalarni faqat adminlar ko'ra oladi.")
        return
    await message.answer("📊 Qaysi lavozim natijasini ko'rmoqchisiz?", reply_markup=positions_kb("r"))


@router.callback_query(F.data == "r:back")
async def results_back(call: CallbackQuery) -> None:
    await safe_edit(call, "📊 Qaysi lavozim natijasini ko'rmoqchisiz?", positions_kb("r"))
    await call.answer()


@router.callback_query(F.data.startswith("r:p:"))
async def results_position(call: CallbackQuery) -> None:
    if not results_allowed(call.from_user.id):
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    pos = settings.position(call.data[4:])
    if pos is None:
        await call.answer("Bo'lim topilmadi", show_alert=True)
        return
    if pos.has_subjects:
        await safe_edit(call, "📚 Qaysi fan natijasini ko'rmoqchisiz?", subjects_kb("r"))
    else:
        await safe_edit(call, reports.results_text(db, pos.key, "", pos.name),
                        ikb([[("🔄 Yangilash", call.data)], [("⬅️ Orqaga", "r:back")]]))
    await call.answer()


@router.callback_query(F.data.startswith("r:s:"))
async def results_subject(call: CallbackQuery) -> None:
    if not results_allowed(call.from_user.id):
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    idx = int(call.data[4:])
    if idx >= len(settings.subjects):
        await call.answer("Fan topilmadi", show_alert=True)
        return
    pos = next(p for p in settings.positions if p.has_subjects)
    subj = settings.subjects[idx]
    ustoz_back = f"r:p:{pos.key}"
    await safe_edit(call, reports.results_text(db, pos.key, subj, f"{pos.name} — {subj}"),
                    ikb([[("🔄 Yangilash", call.data)], [("⬅️ Orqaga", ustoz_back)]]))
    await call.answer()


# ======================= admin buyruqlari =======================
@router.message(Command("result"))
async def cmd_result(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    buf = reports.top3_excel(db, settings)
    name = f"top3_{settings.now():%Y-%m-%d_%H-%M}.xlsx"
    await message.answer_document(
        BufferedInputFile(buf.read(), filename=name),
        caption="🏆 Barcha lavozim va fanlar bo'yicha 1-2-3 o'rinlar",
    )


@router.message(Command("all"))
async def cmd_all(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    for chunk in reports.all_results_text(db, settings):
        await message.answer(chunk)
    buf = reports.all_excel(db, settings)
    name = f"barcha_ovozlar_{settings.now():%Y-%m-%d_%H-%M}.xlsx"
    await message.answer_document(BufferedInputFile(buf.read(), filename=name),
                                  caption="📋 Barcha ovozlar (Excel)")


@router.message(Command("stats"))
async def cmd_stats(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    st = {"before": "boshlanmagan", "open": "davom etmoqda ✅", "after": "tugagan ⛔️"}[settings.voting_status()]
    await message.answer(
        f"📈 <b>Statistika</b>\n"
        f"Botga kirganlar: <b>{db.total_users()}</b>\n"
        f"Ovoz berganlar: <b>{db.total_voters()}</b>\n"
        f"Jami ovozlar: <b>{db.total_votes()}</b>\n"
        f"Ovoz berish: {st} ({fmt_dt(settings.vote_start)} — {fmt_dt(settings.vote_end)})"
    )


@router.message(Command("reload"))
async def cmd_reload(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    try:
        load_data(settings)
        db.sync_candidates(settings.candidates)
    except Exception as e:  # noqa: BLE001
        await message.answer(f"❌ data.json da xato: {e}")
        return
    await message.answer(f"✅ data.json qayta yuklandi. Qatnashuvchilar: {len(settings.candidates)}")


@router.message(Command("goo"))
async def cmd_goo(message: Message) -> None:
    """Barcha ovozlarni o'chirib, ovoz berishni hozirdan boshlab qaytadan ochadi."""
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        f"⚠️ <b>Diqqat!</b>\n"
        f"• Barcha ovozlar o'chiriladi (hozir: <b>{db.total_votes()}</b> ta)\n"
        f"• Ovoz berish <b>hozirdan</b> boshlanadi va <b>{settings.vote_days} kun</b> davom etadi\n\n"
        "Davom etasizmi?",
        reply_markup=ikb([[("✅ Ha, boshlash", "goo:yes"), ("❌ Bekor qilish", "goo:no")]]),
    )


@router.callback_query(F.data.startswith("goo:"))
async def goo_confirm(call: CallbackQuery) -> None:
    if not is_admin(call.from_user.id):
        await call.answer("Ruxsat yo'q", show_alert=True)
        return
    if call.data == "goo:no":
        await safe_edit(call, "Bekor qilindi.")
        await call.answer()
        return
    from datetime import timedelta
    n = db.reset_votes()
    start = settings.now().replace(second=0, microsecond=0)
    end = start + timedelta(days=settings.vote_days)
    db.set_setting("vote_start", start.isoformat())
    db.set_setting("vote_end", end.isoformat())
    apply_saved_period()
    log.info("/goo: %s ovoz o'chirildi, yangi muddat %s — %s", n, start, end)
    await safe_edit(
        call,
        f"🚀 <b>Ovoz berish boshlandi!</b>\n"
        f"🗑 O'chirilgan ovozlar: {n} ta\n"
        f"🕐 Muddat: <b>{fmt_dt(settings.vote_start)}</b> — <b>{fmt_dt(settings.vote_end)}</b>",
    )
    await call.answer("Boshlandi ✅")


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        return
    await message.answer(
        "👨‍💼 <b>Admin buyruqlari</b>\n"
        "/result — 1-2-3 o'rinlar (Excel)\n"
        "/all — barcha ovozlar soni (matn + Excel)\n"
        "/stats — umumiy statistika\n"
        "/reload — data.json ni qayta yuklash (yangi qatnashuvchilar)\n"
        "/goo — barcha ovozlarni o'chirib, ovoz berishni hozirdan qaytadan boshlash"
    )


# ======================= kanal ID sini aniqlash =======================
@router.my_chat_member()
async def bot_added(event: ChatMemberUpdated, bot: Bot) -> None:
    """Bot kanalga admin qilinganda kanal ID sini adminlarga yuboradi."""
    if event.chat.type != "channel" or event.new_chat_member.status != ChatMemberStatus.ADMINISTRATOR:
        return
    text = (
        f"✅ Bot <b>{escape(event.chat.title or '')}</b> kanaliga admin qilindi.\n"
        f"Kanal ID: <code>{event.chat.id}</code>\n\n"
        f".env faylga <code>CHANNEL_ID={event.chat.id}</code> deb yozing va botni qayta ishga tushiring."
    )
    log.info("Kanal ID: %s (%s)", event.chat.id, event.chat.title)
    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:  # noqa: BLE001
            pass


async def log_updates(handler, event, data):
    """Har bir kelgan xabarni terminalga yozadi (tekshirish uchun)."""
    u = data.get("event_from_user")
    what = getattr(event, "text", None) or getattr(event, "data", None) or type(event).__name__
    log.info("Xabar keldi: %s (%s) -> %s", u.full_name if u else "?", u.id if u else "?", what)
    return await handler(event, data)


async def main() -> None:
    import os
    from aiogram.client.session.aiohttp import AiohttpSession

    proxy = os.getenv("PROXY_URL", "").strip() or None
    if not proxy:
        # Windows/tizim proksisi bo'lsa (curl va brauzer shuni ishlatadi), uni ham olamiz
        import urllib.request
        sys_proxy = urllib.request.getproxies()
        proxy = sys_proxy.get("https") or sys_proxy.get("http") or None
        if proxy and "://" not in proxy:
            proxy = "http://" + proxy
    if proxy:
        log.info("Proksi orqali ulanaman: %s", proxy)
    session = AiohttpSession(proxy=proxy) if proxy else AiohttpSession()
    # Ba'zi tarmoqlarda IPv6 orqali ulanish osilib qoladi, shuning uchun IPv4 majburiy
    import socket
    session._connector_init["family"] = socket.AF_INET
    bot = Bot(settings.bot_token, session=session,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.message.outer_middleware(log_updates)
    dp.callback_query.outer_middleware(log_updates)
    dp.include_router(router)
    log.info("Muddat: %s — %s", settings.vote_start, settings.vote_end)
    log.info("Telegram serveriga ulanyapman...")
    try:
        me = None
        wait = 60
        while me is None:
            try:
                me = await asyncio.wait_for(bot.get_me(), timeout=90)
            except TelegramRetryAfter as e:
                # Cheklov tugashi uchun har safar uzoqroq kutamiz (60s -> 2 -> 4 -> 8 -> 15 daqiqa)
                pause = max(e.retry_after + 1, wait)
                log.warning("Telegram cheklovi (retry_after=%s). %s soniya kutib qayta urinaman...",
                            e.retry_after, pause)
                await asyncio.sleep(pause)
                wait = min(wait * 2, 900)
            except Exception as e:  # noqa: BLE001
                log.error("Telegramga ulanib bo'lmadi: %r", e)
                log.error("Internet/VPN ni yoki BOT_TOKEN to'g'riligini tekshiring.")
                return
        log.info("✅ Ulandi: @%s. Endi botga /start yuboring.", me.username)
        info = await bot.get_webhook_info()
        if info.url:
            log.warning("Botda webhook o'rnatilgan (%s), o'chiryapman...", info.url)
            await bot.delete_webhook()
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
