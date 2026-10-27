import tempfile
import unittest
from datetime import date, datetime, timezone
from bot.store import Store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name + "/db.sqlite3")
        self.store.ensure_user(1, "Один")
        self.store.ensure_user(2, "Два")
        self.hid = self.store.create_habit(1, "Чтение", "стр", 10)

    def tearDown(self):
        self.tmp.cleanup()

    def log(self, day, amount):
        with self.store.connect() as db:
            db.execute(
                "INSERT INTO progress(habit_id,day,amount) VALUES (?,?,?)",
                (self.hid, day, amount),
            )

    def test_persistence_and_isolation(self):
        self.store.add_progress(1, self.hid, 2.5)
        reopened = Store(self.store.path)
        self.assertEqual(reopened.summary(1, reopened.habit(1, self.hid))["today"], 2.5)
        with self.assertRaises(ValueError):
            self.store.add_progress(2, self.hid, 3)

    def test_streak_counts_dates_and_breaks(self):
        self.log("2026-10-20", 10)
        self.log("2026-10-20", 5)
        self.log("2026-10-21", 10)
        h = self.store.habit(1, self.hid)
        s = self.store.summary(1, h, date(2026, 10, 21))
        self.assertEqual(s["streak"], 2)
        self.assertEqual(s["best"], 2)
        self.assertEqual(self.store.summary(1, h, date(2026, 10, 22))["streak"], 2)
        self.assertEqual(self.store.summary(1, h, date(2026, 10, 23))["streak"], 0)

    def test_invalid_numbers(self):
        for n in (-1, 0, float("nan"), float("inf"), 1000001):
            with self.subTest(n=n), self.assertRaises(ValueError):
                self.store.add_progress(1, self.hid, n)

    def test_awards_cross_threshold_and_are_unique(self):
        _, first = self.store.add_progress(1, self.hid, 99)
        self.assertIn("Первый выполненный день", first)
        _, second = self.store.add_progress(1, self.hid, 3)
        self.assertIn("100 стр", second)
        s, third = self.store.add_progress(1, self.hid, 1)
        self.assertEqual(third, [])
        self.assertEqual(s["streak"], 1)

    def test_limit_archive_and_expiry(self):
        self.store.create_habit(1, "Бег", "км", 0.5)
        self.store.create_habit(1, "Учёба", "мин", 15)
        with self.assertRaises(ValueError):
            self.store.create_habit(1, "Четвёртая", "раз", 1)
        self.store.archive(1, self.hid)
        other = self.store.create_habit(1, "Новая", "раз", 1, 1)
        self.assertEqual(len(self.store.habits(1)), 3)
        with self.store.connect() as db:
            db.execute("UPDATE habits SET end_date='2000-01-01' WHERE id=?", (other,))
        with self.assertRaises(ValueError):
            self.store.add_progress(1, other, 1)
        self.assertEqual(len(self.store.habits(1)), 2)

    def test_timezone_boundary(self):
        self.store.settings(1, timezone="Europe/Samara")
        self.assertEqual(
            self.store.today(1, datetime(2026, 10, 27, 21, tzinfo=timezone.utc)),
            date(2026, 10, 28),
        )
        self.assertEqual(
            self.store.today(2, datetime(2026, 10, 27, 21, tzinfo=timezone.utc)),
            date(2026, 10, 27),
        )

    def test_week_excludes_days_before_start(self):
        s = self.store.summary(1, self.store.habit(1, self.hid))
        self.assertEqual(s["week_planned"], 1)

    def test_history_bounded_and_private(self):
        for i in range(10):
            self.store.save_exchange(1, str(i), "ответ")
        self.assertEqual(len(self.store.history(1)), 8)
        self.assertEqual(self.store.history(2), [])
        self.assertEqual(self.store.history(1)[0]["content"], "6")
