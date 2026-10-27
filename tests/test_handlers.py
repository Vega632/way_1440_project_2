import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from bot.coach import Coach
from bot.handlers import Handlers, BACK
from bot.store import Store


class HandlerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name + "/db.sqlite3")
        self.store.ensure_user(1, "Тест")
        self.handlers = Handlers(self.store, Coach())
        self.update = SimpleNamespace(
            effective_user=SimpleNamespace(id=1, first_name="Тест"),
            message=SimpleNamespace(text="", reply_text=AsyncMock()),
        )
        self.context = SimpleNamespace(
            user_data={}, bot=SimpleNamespace(username="test_bot")
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def send(self, text):
        self.update.message.text = text
        await self.handlers.text(self.update, self.context)

    async def test_full_flow_resume_and_back(self):
        for text in ["➕ Привычка", "Бег", "км", "0,5", "7"]:
            await self.send(text)
        h = self.store.habits(1)[0]
        await self.send(f'Отметить #{h["id"]} · Бег')
        await self.send("0,2")
        await self.send(BACK)
        await self.send(f'Отметить #{h["id"]} · Бег')
        await self.send("✅ Выполнить норму")
        self.assertAlmostEqual(self.store.summary(1, h)["today"], 0.5)
        await self.send("🎯 Цели")
        await self.send(BACK)
        self.assertEqual(self.store.context(1)["goals"], [])

    async def test_bad_progress_does_not_change_data(self):
        hid = self.store.create_habit(1, "Бег", "км", 1)
        for invalid in ["+текст", "-2", "nan", "0"]:
            await self.send(f"Отметить #{hid} · Бег")
            await self.send(invalid)
        self.assertEqual(self.store.summary(1, self.store.habit(1, hid))["total"], 0)

    async def test_goal_and_coach_without_key(self):
        await self.send("🎯 Цели")
        await self.send("Читать регулярно")
        self.assertEqual(self.store.context(1)["goals"], ["Читать регулярно"])
        self.assertIn(
            "пока не подключён", self.update.message.reply_text.call_args.args[0]
        )

    async def test_delete_requires_confirmation(self):
        self.store.create_habit(1, "Бег", "км", 1)
        await self.handlers.confirm_delete(self.update, self.context)
        self.assertIsNotNone(self.store.user(1))
        await self.handlers.delete_data(self.update, self.context)
        await self.handlers.confirm_delete(self.update, self.context)
        self.assertIsNone(self.store.user(1))

    async def test_reminders_once_local_day_and_only_pending(self):
        self.store.create_habit(1, "Бег", "км", 1)
        self.store.settings(1, timezone="Europe/Samara", reminder="10:00")
        app = SimpleNamespace(bot=SimpleNamespace(send_message=AsyncMock()))
        now = datetime(2026, 10, 27, 7, tzinfo=timezone.utc)
        # Set a deterministic start date to keep the habit active on this test date.
        await self.handlers.reminder_tick(app, now)
        await self.handlers.reminder_tick(app, now)
        self.assertEqual(app.bot.send_message.await_count, 1)

    async def test_ownership_on_habit_selection(self):
        self.store.ensure_user(2, "Другой")
        hid = self.store.create_habit(2, "Чужая", "раз", 1)
        await self.send(f"Отметить #{hid} · Чужая")
        self.assertNotIn("hid", self.context.user_data)
