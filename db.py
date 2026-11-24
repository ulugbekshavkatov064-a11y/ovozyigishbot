import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS candidates (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    position TEXT NOT NULL,
    subject  TEXT NOT NULL DEFAULT '',
    name     TEXT NOT NULL,
    branch   TEXT NOT NULL,
    active   INTEGER NOT NULL DEFAULT 1,
    UNIQUE (position, subject, name, branch)
);
CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    full_name  TEXT,
    username   TEXT,
    first_seen TEXT
);
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS votes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    category     TEXT NOT NULL,          -- 'manager' yoki 'ustoz:Matematika'
    candidate_id INTEGER NOT NULL REFERENCES candidates(id),
    voted_at     TEXT NOT NULL,
    UNIQUE (user_id, category)
);
"""


def category_key(position: str, subject: str = "") -> str:
    return f"{position}:{subject}" if subject else position


class Database:
    def __init__(self, path: str):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---------- qatnashuvchilar ----------
    def sync_candidates(self, candidates: list[dict]) -> None:
        """data.json bilan bazani moslashtiradi. Ro'yxatdan olib tashlanganlar
        o'chirilmaydi (ovozlari saqlanadi), faqat yashiriladi."""
        cur = self.conn.cursor()
        cur.execute("UPDATE candidates SET active = 0")
        for c in candidates:
            subject = c.get("subject", "") or ""
            cur.execute(
                """INSERT INTO candidates (position, subject, name, branch, active)
                   VALUES (?, ?, ?, ?, 1)
                   ON CONFLICT(position, subject, name, branch) DO UPDATE SET active = 1""",
                (c["position"], subject, c["name"].strip(), c["branch"].strip()),
            )
        self.conn.commit()

    def get_candidates(self, position: str, subject: str = "") -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM candidates WHERE position=? AND subject=? AND active=1 ORDER BY id",
            (position, subject),
        ).fetchall()

    def get_candidate(self, cand_id: int) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM candidates WHERE id=?", (cand_id,)).fetchone()

    # ---------- foydalanuvchilar ----------
    def save_user(self, user_id: int, full_name: str, username: str | None) -> None:
        self.conn.execute(
            """INSERT INTO users (user_id, full_name, username, first_seen) VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET full_name=excluded.full_name,
                                                  username=excluded.username""",
            (user_id, full_name, username, datetime.utcnow().isoformat(timespec="seconds")),
        )
        self.conn.commit()

    # ---------- ovozlar ----------
    def has_voted(self, user_id: int, category: str) -> bool:
        return (
            self.conn.execute(
                "SELECT 1 FROM votes WHERE user_id=? AND category=?", (user_id, category)
            ).fetchone()
            is not None
        )

    def add_vote(self, user_id: int, category: str, candidate_id: int) -> bool:
        """True - ovoz qabul qilindi, False - avval ovoz bergan."""
        try:
            self.conn.execute(
                "INSERT INTO votes (user_id, category, candidate_id, voted_at) VALUES (?, ?, ?, ?)",
                (user_id, category, candidate_id, datetime.utcnow().isoformat(timespec="seconds")),
            )
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            self.conn.rollback()
            return False

    def results(self, position: str, subject: str = "") -> list[dict]:
        """Bo'lim natijalari: ovozlar soni bo'yicha kamayish tartibida."""
        cat = category_key(position, subject)
        rows = self.conn.execute(
            """SELECT c.id, c.name, c.branch,
                      (SELECT COUNT(*) FROM votes v
                        WHERE v.candidate_id = c.id AND v.category = ?) AS cnt
               FROM candidates c
               WHERE c.position = ? AND c.subject = ?
               ORDER BY cnt DESC, c.name""",
            (cat, position, subject),
        ).fetchall()
        active_ids = {r["id"] for r in self.get_candidates(position, subject)}
        # yashirilgan qatnashuvchi faqat ovozi bo'lsa ko'rsatiladi
        return [dict(r) for r in rows if r["id"] in active_ids or r["cnt"] > 0]

    def get_setting(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()

    def reset_votes(self) -> int:
        n = self.total_votes()
        self.conn.execute("DELETE FROM votes")
        self.conn.commit()
        return n

    def total_votes(self, category: str | None = None) -> int:
        if category is None:
            return self.conn.execute("SELECT COUNT(*) FROM votes").fetchone()[0]
        return self.conn.execute(
            "SELECT COUNT(*) FROM votes WHERE category=?", (category,)
        ).fetchone()[0]

    def total_voters(self) -> int:
        return self.conn.execute("SELECT COUNT(DISTINCT user_id) FROM votes").fetchone()[0]

    def total_users(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
