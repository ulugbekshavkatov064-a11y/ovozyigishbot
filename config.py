import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _parse_dt(value: str, tz: ZoneInfo) -> datetime:
    return datetime.strptime(value.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=tz)


@dataclass
class Position:
    key: str
    name: str
    has_subjects: bool = False


@dataclass
class Settings:
    bot_token: str
    admin_ids: set[int]
    channel_id: str
    channel_url: str
    tz: ZoneInfo
    vote_start: datetime
    vote_end: datetime
    results_admin_only: bool
    vote_days: int
    db_path: str
    data_file: str
    positions: list[Position] = field(default_factory=list)
    subjects: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    prizes: list[str] = field(default_factory=list)
    cert_org: str = ""

    def position(self, key: str) -> Position | None:
        return next((p for p in self.positions if p.key == key), None)

    def now(self) -> datetime:
        return datetime.now(self.tz)

    def voting_status(self) -> str:
        """'before' | 'open' | 'after'"""
        now = self.now()
        if now < self.vote_start:
            return "before"
        if now > self.vote_end:
            return "after"
        return "open"


def _db_path() -> str:
    """Railway Volume ulangan bo'lsa, baza avtomatik o'sha diskda saqlanadi."""
    path = os.getenv("DB_PATH", "votes.db").strip() or "votes.db"
    volume = os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if volume:
        path = os.path.join(volume, os.path.basename(path))
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    return path


def load_settings() -> Settings:
    tz = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN .env faylida ko'rsatilmagan!")

    admin_ids = {
        int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
    }
    channel_id = os.getenv("CHANNEL_ID", "").strip()
    channel_url = os.getenv("CHANNEL_URL", "").strip()
    if not channel_url and channel_id.startswith("@"):
        channel_url = f"https://t.me/{channel_id[1:]}"

    s = Settings(
        bot_token=token,
        admin_ids=admin_ids,
        channel_id=channel_id,
        channel_url=channel_url,
        tz=tz,
        vote_start=_parse_dt(os.getenv("VOTE_START", "2026-12-01 00:00"), tz),
        vote_end=_parse_dt(os.getenv("VOTE_END", "2026-12-15 23:59"), tz).replace(second=59),
        vote_days=int(os.getenv("VOTE_DAYS", "15")),
        results_admin_only=os.getenv("RESULTS_ADMIN_ONLY", "false").lower() in ("1", "true", "yes"),
        db_path=_db_path(),
        data_file=os.getenv("DATA_FILE", "data.json"),
    )
    s.cert_org = os.getenv("CERT_ORG", "").strip()
    load_data(s)
    return s


def load_data(s: Settings) -> None:
    """data.json dan lavozimlar, fanlar va qatnashuvchilarni o'qiydi."""
    with open(s.data_file, encoding="utf-8") as f:
        data = json.load(f)

    positions = [
        Position(p["key"], p["name"], bool(p.get("has_subjects"))) for p in data["positions"]
    ]
    subjects = list(data.get("subjects", []))
    by_key = {p.key: p for p in positions}
    candidates = data.get("candidates", [])
    for c in candidates:
        pos = by_key.get(c.get("position", ""))
        if pos is None:
            raise ValueError(f"noma'lum lavozim: {c}")
        if pos.has_subjects and c.get("subject") not in subjects:
            raise ValueError(f"fan noto'g'ri yoki ko'rsatilmagan: {c}")
        if not pos.has_subjects:
            c.pop("subject", None)
        if not c.get("name") or not c.get("branch"):
            raise ValueError(f"ism yoki filial yo'q: {c}")
    prizes = [p.strip() for p in data.get("prizes", []) if p.strip()]
    if not prizes:
        raise ValueError("data.json da 'prizes' (sovg'alar) ro'yxati bo'sh")
    s.positions, s.subjects, s.candidates, s.prizes = positions, subjects, candidates, prizes
