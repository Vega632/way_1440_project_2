"""SQLite repository. Dates are recorded in each user's configured timezone."""

import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.executescript(
                """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL,
                timezone TEXT NOT NULL DEFAULT 'UTC', tone TEXT NOT NULL DEFAULT 'требовательный',
                reminder TEXT, last_reminder TEXT);
            CREATE TABLE IF NOT EXISTS habits (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                name TEXT NOT NULL, unit TEXT NOT NULL, target REAL NOT NULL CHECK(target>0),
                start_date TEXT NOT NULL, end_date TEXT, archived INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS progress (
                id INTEGER PRIMARY KEY, habit_id INTEGER NOT NULL REFERENCES habits(id),
                day TEXT NOT NULL, amount REAL NOT NULL CHECK(amount>0));
            CREATE TABLE IF NOT EXISTS goals (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                text TEXT NOT NULL, created TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                role TEXT NOT NULL, text TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS awards (
                user_id INTEGER NOT NULL, habit_id INTEGER NOT NULL, name TEXT NOT NULL,
                PRIMARY KEY(user_id,habit_id,name));
            CREATE INDEX IF NOT EXISTS progress_habit_day ON progress(habit_id,day);
            """
            )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def user(self, uid):
        with self.connect() as db:
            row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            return dict(row) if row else None

    def ensure_user(self, uid, name):
        with self.connect() as db:
            db.execute(
                "INSERT INTO users(id,name) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name",
                (uid, name),
            )

    def today(self, uid, now=None):
        return (
            (now or datetime.now(timezone.utc))
            .astimezone(ZoneInfo(self.user(uid)["timezone"]))
            .date()
        )

    def settings(self, uid, **values):
        if not values.keys() <= {"timezone", "tone", "reminder", "last_reminder"}:
            raise ValueError("Неизвестная настройка")
        if "timezone" in values:
            ZoneInfo(values["timezone"])
        if "tone" in values and values["tone"] not in (
            "спокойный",
            "требовательный",
            "жёсткий",
        ):
            raise ValueError("Неизвестный стиль")
        if values.get("reminder"):
            datetime.strptime(values["reminder"], "%H:%M")
        with self.connect() as db:
            for key, value in values.items():
                db.execute(f"UPDATE users SET {key}=? WHERE id=?", (value, uid))

    def habits(self, uid, day=None):
        day = str(day or self.today(uid))
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM habits WHERE user_id=? AND archived=0 AND (end_date IS NULL OR end_date>=?) ORDER BY id",
                    (uid, day),
                )
            ]

    def create_habit(self, uid, name, unit, target, days=0):
        if not name.strip() or len(name) > 80 or not unit.strip() or len(unit) > 20:
            raise ValueError("Название: 1–80 символов, единица: 1–20.")
        if (
            not math.isfinite(target)
            or not 0 < target <= 1000000
            or not 0 <= days <= 3650
        ):
            raise ValueError("Проверьте норму и срок (0–3650 дней).")
        today = self.today(uid)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            count = db.execute(
                "SELECT COUNT(*) FROM habits WHERE user_id=? AND archived=0 AND (end_date IS NULL OR end_date>=?)",
                (uid, str(today)),
            ).fetchone()[0]
            if count >= 3:
                raise ValueError(
                    "Можно вести до трёх привычек. Сначала завершите одну из текущих."
                )
            return db.execute(
                "INSERT INTO habits(user_id,name,unit,target,start_date,end_date) VALUES (?,?,?,?,?,?)",
                (
                    uid,
                    name.strip(),
                    unit.strip(),
                    target,
                    str(today),
                    str(today + timedelta(days=days - 1)) if days else None,
                ),
            ).lastrowid

    def habit(self, uid, hid):
        with self.connect() as db:
            row = db.execute(
                "SELECT * FROM habits WHERE id=? AND user_id=?", (hid, uid)
            ).fetchone()
            if not row:
                raise ValueError("Привычка не найдена.")
            return dict(row)

    def totals(self, hid):
        with self.connect() as db:
            return {
                r["day"]: r["total"]
                for r in db.execute(
                    "SELECT day,SUM(amount) total FROM progress WHERE habit_id=? GROUP BY day",
                    (hid,),
                )
            }

    def summary(self, uid, habit, today=None):
        today = today or self.today(uid)
        totals = self.totals(habit["id"])
        completed = sorted(d for d, v in totals.items() if v + 1e-9 >= habit["target"])
        cursor = today if str(today) in completed else today - timedelta(days=1)
        streak = 0
        while str(cursor) in completed:
            streak += 1
            cursor -= timedelta(days=1)
        best = run = 0
        previous = None
        for day in completed:
            date = datetime.strptime(day, "%Y-%m-%d").date()
            run = run + 1 if previous and date - previous == timedelta(days=1) else 1
            best = max(best, run)
            previous = date
        start = max(
            datetime.strptime(habit["start_date"], "%Y-%m-%d").date(),
            today - timedelta(days=6),
        )
        end = (
            min(today, datetime.strptime(habit["end_date"], "%Y-%m-%d").date())
            if habit["end_date"]
            else today
        )
        planned = max(0, (end - start).days + 1)
        week = sum(str(start) <= d <= str(end) for d in completed)
        return {
            "today": totals.get(str(today), 0),
            "total": sum(totals.values()),
            "streak": streak,
            "best": best,
            "week_done": week,
            "week_planned": planned,
            "completed_days": len(completed),
        }

    def add_progress(self, uid, hid, amount):
        if not math.isfinite(amount) or not 0 < amount <= 1000000:
            raise ValueError("Введите положительное число не больше 1000000.")
        habit = self.habit(uid, hid)
        today = self.today(uid)
        if habit["archived"] or (habit["end_date"] and habit["end_date"] < str(today)):
            raise ValueError("Эта привычка завершена.")
        before = self.summary(uid, habit, today)
        with self.connect() as db:
            db.execute(
                "INSERT INTO progress(habit_id,day,amount) VALUES (?,?,?)",
                (hid, str(today), amount),
            )
        after = self.summary(uid, habit, today)
        candidates = []
        if after["completed_days"] >= 1:
            candidates.append("Первый выполненный день")
        for n in (7, 14, 30):
            if after["best"] >= n:
                candidates.append(f"{n} дней подряд")
        # Count units only within this habit; kilometres and repetitions are never mixed.
        for n in (100, 1000, 3000, 10000):
            if after["total"] >= n:
                candidates.append(f'{n} {habit["unit"]}')
        if before["streak"] == 0 and before["completed_days"] and after["streak"]:
            candidates.append("Возвращение после перерыва")
        awards = []
        with self.connect() as db:
            for name in candidates:
                if db.execute(
                    "INSERT OR IGNORE INTO awards VALUES (?,?,?)", (uid, hid, name)
                ).rowcount:
                    awards.append(name)
        return after, awards

    def archive(self, uid, hid):
        self.habit(uid, hid)
        with self.connect() as db:
            db.execute(
                "UPDATE habits SET archived=1 WHERE id=? AND user_id=?", (hid, uid)
            )

    def add_goal(self, uid, text):
        if not 1 <= len(text.strip()) <= 1000:
            raise ValueError("Цель должна содержать 1–1000 символов.")
        with self.connect() as db:
            db.execute(
                "INSERT INTO goals(user_id,text,created) VALUES (?,?,?)",
                (uid, text.strip(), str(self.today(uid))),
            )

    def context(self, uid):
        with self.connect() as db:
            goals = [
                r[0]
                for r in db.execute(
                    "SELECT text FROM goals WHERE user_id=? ORDER BY id DESC LIMIT 3",
                    (uid,),
                )
            ]
        return {
            "date": str(self.today(uid)),
            "tone": self.user(uid)["tone"],
            "goals": goals,
            "habits": [
                {
                    **{
                        k: h[k]
                        for k in ("name", "unit", "target", "start_date", "end_date")
                    },
                    **self.summary(uid, h),
                }
                for h in self.habits(uid)
            ],
        }

    def history(self, uid):
        with self.connect() as db:
            rows = list(
                db.execute(
                    "SELECT role,text FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 8",
                    (uid,),
                )
            )
            return [{"role": r["role"], "content": r["text"]} for r in reversed(rows)]

    def save_exchange(self, uid, question, answer):
        with self.connect() as db:
            db.executemany(
                "INSERT INTO messages(user_id,role,text) VALUES (?,?,?)",
                [(uid, "user", question), (uid, "assistant", answer)],
            )
            db.execute(
                "DELETE FROM messages WHERE user_id=? AND id NOT IN (SELECT id FROM messages WHERE user_id=? ORDER BY id DESC LIMIT 8)",
                (uid, uid),
            )

    def awards(self, uid):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT a.name,h.name habit FROM awards a JOIN habits h ON h.id=a.habit_id WHERE a.user_id=?",
                    (uid,),
                )
            ]

    def reminder_users(self):
        with self.connect() as db:
            return [
                dict(r)
                for r in db.execute("SELECT * FROM users WHERE reminder IS NOT NULL")
            ]
