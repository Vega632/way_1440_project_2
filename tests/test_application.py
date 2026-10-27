"""Exercise real Telegram application routing without network or real credentials."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch
from telegram import Update
from telegram.request import BaseRequest
import main


class TelegramStub(BaseRequest):
    def __init__(self, **kwargs):
        self.sent = []

    async def initialize(self):
        pass

    async def shutdown(self):
        pass

    async def do_request(self, url, method, request_data=None, **kwargs):
        endpoint = url.rsplit("/", 1)[-1]
        if endpoint == "getMe":
            result = {
                "id": 123,
                "is_bot": True,
                "first_name": "Test",
                "username": "test_bot",
            }
        elif endpoint == "sendMessage":
            params = request_data.parameters
            self.sent.append(params["text"])
            result = {
                "message_id": len(self.sent),
                "date": 0,
                "chat": {"id": 1, "type": "private"},
                "text": params["text"],
            }
        else:
            raise AssertionError("Unexpected endpoint: " + endpoint)
        return 200, json.dumps({"ok": True, "result": result}).encode()


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_application_routes_commands_buttons_and_cancel(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(
                os.environ,
                {
                    "TELEGRAM_TOKEN": "123:offline_test",
                    "DATABASE_PATH": tmp + "/db.sqlite3",
                    "DEEPSEEK_API_KEY": "",
                },
            ), patch("main.HTTPXRequest", TelegramStub):
                app = main.build_application()
            await app.initialize()
            try:
                inputs = [
                    "/today",
                    "➕ Привычка",
                    "Прогулка",
                    "мин",
                    "10",
                    "7",
                    "Отметить #1 · Прогулка",
                    "+5",
                    "🎯 Цели",
                    "/cancel",
                    "📊 Неделя",
                ]
                for index, text in enumerate(inputs):
                    message = {
                        "message_id": index + 1,
                        "date": 0,
                        "chat": {"id": 1, "type": "private"},
                        "from": {"id": 1, "is_bot": False, "first_name": "Test"},
                        "text": text,
                    }
                    if text.startswith("/"):
                        message["entities"] = [
                            {"type": "bot_command", "offset": 0, "length": len(text)}
                        ]
                    update = Update.de_json(
                        {"update_id": index, "message": message}, app.bot
                    )
                    await app.process_update(update)
                output = "\n".join(app.bot.request.sent)
                self.assertIn("Привычка создана", output)
                self.assertIn("Сохранено: 5/10", output)
                self.assertIn("0/1 дней выполнено", output)
                from bot.store import Store

                store = Store(tmp + "/db.sqlite3")
                self.assertEqual(store.context(1)["goals"], [])
                self.assertEqual(store.summary(1, store.habit(1, 1))["today"], 5)
            finally:
                await app.shutdown()
