# Ovoz yig'ish Telegram boti

Python 3.10+ · aiogram 3 · SQLite · Excel (openpyxl)

## Imkoniyatlar
- `/start` → **🗳 Ovoz berish** va **📊 Natijalar** tugmalari
- Ovoz berishdan oldin kanalga majburiy obuna tekshiriladi
- Lavozimlar: Manager, Filial rahbari, Tozalik hodimlari, Operatorlar, Ustozlar, Mobilograf
- Ustozlar bo'limida avval fan tanlanadi, keyin shu fan ustozlari chiqadi
- Qatnashuvchi tugmasida: **Ism familiya — Filial**
- Har bir bo'limga (Ustozlarda har bir fanga) foydalanuvchi faqat **1 marta** ovoz beradi
- Ovozdan keyin shu bo'lim natijasi **ovozlar soni** bilan ko'rsatiladi (foiz emas)
- Muddat: 1-dekabr 00:00 — 15-dekabr 23:59 (Toshkent vaqti). Muddatdan keyin ovoz berib bo'lmaydi, natijalarni ko'rish mumkin

## Admin buyruqlari
| Buyruq | Vazifasi |
|---|---|
| `/result` | Barcha lavozim va fanlar bo'yicha 1-2-3 o'rinlar, Excel fayl |
| `/all` | Barcha qatnashuvchilarning ovozlari soni (matn + Excel) |
| `/stats` | Umumiy statistika |
| `/reload` | `data.json` o'zgargandan keyin qayta yuklash (botni o'chirmasdan) |
| `/admin` | Buyruqlar ro'yxati |

## O'rnatish
1. @BotFather da bot yarating va tokenni oling.
2. Botni kanalingizga **admin** qilib qo'shing (aks holda obunani tekshira olmaydi).
3. O'zingizning Telegram ID ingizni @userinfobot orqali bilib oling.
4. Terminalda:
   ```bash
   cd ovoz_bot
   python -m venv venv
   # Windows: venv\Scripts\activate    Linux/Mac: source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env        # Windows: copy .env.example .env
   ```
5. `.env` faylini to'ldiring: `BOT_TOKEN`, `ADMIN_IDS`, `CHANNEL_ID`, `CHANNEL_URL`.
6. `data.json` ga haqiqiy qatnashuvchilar va fanlarni yozing (pastga qarang).
7. Ishga tushirish: `python bot.py`

Bot 24/7 ishlashi uchun uni VPS serverda (masalan `systemd`, `screen` yoki `pm2` bilan) ishga tushiring.

## Qatnashuvchilarni qo'shish (`data.json`)
```json
{"position": "manager", "name": "Aliyev Jasur", "branch": "Chilonzor filiali"},
{"position": "ustoz", "subject": "Matematika", "name": "Nazarov Akmal", "branch": "Chilonzor filiali"}
```
- `position` — lavozim kaliti: `manager`, `filial`, `tozalik`, `operator`, `ustoz`, `mobilograf`
- Ustozlar uchun `subject` majburiy va u `subjects` ro'yxatida bo'lishi kerak
- Fan qo'shish uchun `subjects` ro'yxatiga yozing
- O'zgartirgandan keyin botga `/reload` yuboring yoki botni qayta ishga tushiring
- Ro'yxatdan olib tashlangan qatnashuvchi botda yashiriladi, ammo uning ovozlari o'chmaydi

## Sozlamalar (`.env`)
- `VOTE_START`, `VOTE_END` — muddat, `YYYY-MM-DD HH:MM` formatida
- `RESULTS_ADMIN_ONLY=true` — "Natijalar" tugmasini faqat adminlar uchun qilish
- Barcha ovozlar `votes.db` faylida saqlanadi. Uni o'chirmang!

## Railway'ga joylash (24/7)
1. GitHub'da yangi **private** repozitoriy yarating va shu papkadagi fayllarni yuklang (`.env` va `votes.db` ni YUKLAMANG).
2. railway.com → **New Project → Deploy from GitHub repo** → repozitoriyni tanlang.
3. Servis ichida **Variables** bo'limiga `.env` dagi qiymatlarni kiriting:
   `BOT_TOKEN`, `ADMIN_IDS`, `CHANNEL_ID`, `CHANNEL_URL`, `VOTE_START`, `VOTE_END`, `TIMEZONE`,
   va **`DB_PATH=/data/votes.db`**
4. Servisga o'ng tugma → **Attach Volume** → Mount path: **`/data`**. (Busiz qayta ishga tushganda ovozlar o'chadi!)
5. **Deploy** tugmasini bosing. **Deployments → Logs** da `✅ Ulandi: @botnomi` chiqishi kerak.
6. Botni faqat bitta joyda ishga tushiring: Railway'da ishlayotganda kompyuterdagi botni o'chiring.
