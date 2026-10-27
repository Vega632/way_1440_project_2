import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from bot.coach import Coach
from bot.store import Store


class CoachTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(self.tmp.name + "/db.sqlite3")
        self.store.ensure_user(1, "Тест")
        self.store.create_habit(1, "Чтение", "мин", 10)
        self.coach = Coach()
        self.create = AsyncMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="Начни с пяти минут.")
                    )
                ]
            )
        )
        self.coach.client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=self.create))
        )

    async def asyncTearDown(self):
        self.tmp.cleanup()

    async def test_context_history_and_rate_limit(self):
        result = await self.coach.answer(1, "Как начать?", self.store)
        self.assertEqual(result, "Начни с пяти минут.")
        messages = self.create.call_args.kwargs["messages"]
        self.assertIn("Чтение", messages[0]["content"])
        self.assertEqual(self.store.history(1)[0]["content"], "Как начать?")
        await self.coach.answer(1, "Ещё вопрос", self.store)
        self.assertEqual(self.create.await_count, 1)

    async def test_failure_releases_busy_and_is_not_saved(self):
        self.create.side_effect = TimeoutError()
        result = await self.coach.answer(1, "Вопрос", self.store)
        self.assertIn("недоступен", result)
        self.assertNotIn(1, self.coach.busy)
        self.assertEqual(self.store.history(1), [])
