"""Run the Путь-24 Telegram bot from the repository root."""

import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from telegram.request import HTTPXRequest
from bot.store import Store
from bot.coach import Coach
from bot.handlers import Handlers
from bot.updates import PerUserProcessor

load_dotenv()


def build_application():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        raise RuntimeError("Set TELEGRAM_TOKEN in environment settings.")
    store = Store(
        os.getenv(
            "DATABASE_PATH", str(Path(__file__).parent / "data" / "way24.sqlite3")
        )
    )
    handlers = Handlers(store, Coach(os.getenv("DEEPSEEK_API_KEY")))
    proxy = os.getenv("PROXY_URL") or None
    app = (
        Application.builder()
        .token(token)
        .concurrent_updates(PerUserProcessor())
        .request(HTTPXRequest(proxy_url=proxy, connect_timeout=20, read_timeout=30))
        .get_updates_request(
            HTTPXRequest(proxy_url=proxy, connect_timeout=20, read_timeout=40)
        )
        .post_init(handlers.post_init)
        .post_stop(handlers.post_stop)
        .build()
    )
    app.add_handler(
        CommandHandler("start", handlers.start, filters=filters.ChatType.PRIVATE)
    )
    app.add_handler(
        CommandHandler("today", handlers.today, filters=filters.ChatType.PRIVATE)
    )
    app.add_handler(
        CommandHandler("cancel", handlers.today, filters=filters.ChatType.PRIVATE)
    )
    app.add_handler(
        CommandHandler(
            "delete_data", handlers.delete_data, filters=filters.ChatType.PRIVATE
        )
    )
    app.add_handler(
        CommandHandler(
            "confirm_delete", handlers.confirm_delete, filters=filters.ChatType.PRIVATE
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handlers.text
        )
    )

    async def error_handler(update, context):
        logging.getLogger(__name__).error(
            "Update failed: %s", type(context.error).__name__
        )
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "Не удалось обработать действие. Попробуйте /today."
            )

    app.add_error_handler(error_handler)
    return app


def main():
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s", level=logging.INFO
    )
    # HTTP request URLs contain Telegram bot credentials.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    build_application().run_polling(drop_pending_updates=False)


if __name__ == "__main__":
    main()
