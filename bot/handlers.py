import asyncio
import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from telegram import ReplyKeyboardMarkup
from telegram.error import Forbidden, TelegramError

logger = logging.getLogger(__name__)
MENU = [
    ["📅 Сегодня", "➕ Привычка"],
    ["📊 Неделя", "🎯 Цели"],
    ["🤖 Коуч", "🏆 Достижения"],
    ["⚙️ Настройки", "📤 Поделиться"],
]
BACK = "◀️ Назад"


def keyboard(rows=None):
    return ReplyKeyboardMarkup(rows or MENU, resize_keyboard=True)


def num(value):
    return f"{value:g}"


async def reply(update, text, rows=None):
    # Telegram caps a message at 4096 characters.
    for offset in range(0, len(text), 3900):
        await update.message.reply_text(
            text[offset : offset + 3900], reply_markup=keyboard(rows)
        )


class Handlers:
    def __init__(self, store, coach):
        self.store = store
        self.coach = coach
        self.reminder_task = None

    async def start(self, update, context):
        user = update.effective_user
        self.store.ensure_user(user.id, user.first_name or "Друг")
        context.user_data.clear()
        await reply(
            update,
            "Путь-24 — небольшие действия каждый день.\nВыберите до трёх привычек, отмечайте прогресс и обсуждайте план с коучем.\n\nВ настройках укажите свой часовой пояс и стиль общения. AI получает ваши цели, прогресс и последние сообщения. Данные хранятся локально; /delete_data удаляет их.",
        )
        await self.today(update, context)

    async def today(self, update, context):
        uid = update.effective_user.id
        self.store.ensure_user(uid, update.effective_user.first_name or "Друг")
        context.user_data.clear()
        habits = self.store.habits(uid)
        lines = [f"📅 Сегодня · {self.store.today(uid)}"]
        rows = []
        for h in habits:
            s = self.store.summary(uid, h)
            done = s["today"] + 1e-9 >= h["target"]
            lines.append(
                f'{"✅" if done else "▫️"} {h["name"]}: {num(s["today"])}/{num(h["target"])} {h["unit"]} · серия {s["streak"]} дн.'
            )
            rows.append([f'Отметить #{h["id"]} · {h["name"]}'])
        if not habits:
            lines.append(
                "Начните с одной небольшой привычки: прогулка, чтение, учёба или движение."
            )
        await reply(update, "\n\n".join(lines), rows + MENU)

    async def coach_reply(self, update, question):
        await reply(update, "🤔 Разбираю ваш вопрос…", [[BACK]])
        answer = await self.coach.answer(update.effective_user.id, question, self.store)
        await reply(
            update, answer, [["Почему не получилось?", "Разбор недели"], [BACK]]
        )

    async def text(self, update, context):
        uid = update.effective_user.id
        self.store.ensure_user(uid, update.effective_user.first_name or "Друг")
        text = update.message.text.strip()
        state = context.user_data.get("state")
        try:
            if text in {cell for row in MENU for cell in row}:
                context.user_data.clear()
                state = None
            # Global navigation precedes state-specific free text.
            if text in (BACK, "📅 Сегодня", "/today"):
                return await self.today(update, context)
            if text == "➕ Привычка":
                context.user_data.clear()
                if len(self.store.habits(uid)) >= 3:
                    return await reply(
                        update,
                        "У вас уже три привычки. Откройте привычку на экране «Сегодня» и завершите одну.",
                    )
                context.user_data["state"] = "name"
                return await reply(
                    update,
                    "Что хотите делать? Например: прогулка, чтение, отжимания. Введите название (до 80 символов).",
                    [[BACK]],
                )
            if text == "📊 Неделя":
                lines = ["📊 Последние 7 дней (включая сегодня)"]
                for h in self.store.habits(uid):
                    s = self.store.summary(uid, h)
                    lines.append(
                        f'{h["name"]}: {s["week_done"]}/{s["week_planned"]} дней выполнено; лучшая серия {s["best"]}; всего {num(s["total"])} {h["unit"]}.'
                    )
                return await reply(
                    update, "\n\n".join(lines), [["Разбор недели", "🗂 История"], [BACK]]
                )
            if text == "🗂 История":
                with self.store.connect() as db:
                    history = [
                        dict(r)
                        for r in db.execute(
                            "SELECT * FROM habits WHERE user_id=? ORDER BY id DESC LIMIT 20",
                            (uid,),
                        )
                    ]
                lines = ["🗂 Последние 20 привычек"]
                for h in history:
                    stats = self.store.summary(uid, h)
                    ended = h["archived"] or (
                        h["end_date"] and h["end_date"] < str(self.store.today(uid))
                    )
                    lines.append(
                        f'{h["name"]} · {"завершена" if ended else "активна"}: {num(stats["total"])} {h["unit"]}, выполнено дней {stats["completed_days"]}, лучшая серия {stats["best"]}.'
                    )
                return await reply(update, "\n\n".join(lines))
            if text == "🎯 Цели":
                context.user_data["state"] = "goal"
                goals = self.store.context(uid)["goals"]
                return await reply(
                    update,
                    "🎯 Последние цели:\n"
                    + ("\n".join(goals) or "Пока нет целей.")
                    + "\n\nНапишите новую цель. Коуч поможет разбить её на шаги.",
                    [[BACK]],
                )
            if text == "🤖 Коуч":
                context.user_data["state"] = "coach"
                return await reply(
                    update,
                    "Задайте вопрос о плане или привычках. Коуч видит ваши цели, результаты и последние сообщения.\nНапример: «Устаю после работы — как сохранить привычку?»",
                    [["Почему не получилось?", "Разбор недели"], [BACK]],
                )
            if text in ("Разбор недели", "Почему не получилось?"):
                context.user_data["state"] = "coach"
                question = (
                    "Подведи итоги последних семи дней по сводке: что удалось и какой один шаг выбрать дальше."
                    if text == "Разбор недели"
                    else "Помоги разобраться с пропуском привычки. Сначала спроси меня о причине, не делай предположений."
                )
                return await self.coach_reply(update, question)
            if text == "🏆 Достижения":
                awards = self.store.awards(uid)
                return await reply(
                    update,
                    "🏆 Достижения\n\n"
                    + (
                        "\n".join(f'{a["habit"]}: {a["name"]}' for a in awards)
                        or "Первая награда — за первый выполненный день."
                    ),
                )
            if text == "📤 Поделиться":
                lines = ["Мой Путь-24:"]
                for h in self.store.habits(uid):
                    s = self.store.summary(uid, h)
                    lines.append(
                        f'{h["name"]}: {s["week_done"]}/{s["week_planned"]} дней за неделю'
                    )
                lines.append(f"https://t.me/{context.bot.username}")
                return await reply(
                    update,
                    "\n".join(lines)
                    + "\n\nТекст можно скопировать. Личные цели и разговоры сюда не включены.",
                )
            if text == "⚙️ Настройки":
                context.user_data.clear()
                user = self.store.user(uid)
                return await reply(
                    update,
                    f'Стиль: {user["tone"]}\nЧасовой пояс: {user["timezone"]}\nНапоминание: {user["reminder"] or "выключено"}',
                    [
                        ["Стиль коуча", "Часовой пояс"],
                        ["Напоминание", "Отключить напоминания"],
                        [BACK],
                    ],
                )
            if text == "Стиль коуча":
                context.user_data["state"] = "tone"
                return await reply(
                    update,
                    "Выберите стиль. В любом стиле — уважение и посильная нагрузка.",
                    [["спокойный", "требовательный", "жёсткий"], [BACK]],
                )
            if text == "Часовой пояс":
                context.user_data["state"] = "timezone"
                return await reply(
                    update,
                    "Введите часовой пояс IANA: Europe/Samara, Europe/Moscow, Asia/Yekaterinburg или UTC. Даты прежних отметок не меняются.",
                    [[BACK]],
                )
            if text == "Напоминание":
                context.user_data["state"] = "reminder"
                return await reply(
                    update,
                    "Во сколько напоминать о незавершённых привычках? Формат ЧЧ:ММ, по вашему часовому поясу. Работает, пока бот запущен.",
                    [[BACK]],
                )
            if text == "Отключить напоминания":
                self.store.settings(uid, reminder=None)
                return await reply(update, "Напоминания отключены.")
            if text.startswith("Отметить #"):
                hid = int(text.split("#", 1)[1].split()[0])
                h = self.store.habit(uid, hid)
                context.user_data.clear()
                context.user_data.update(state="progress", hid=hid)
                return await reply(
                    update,
                    f'{h["name"]} · дневная норма {num(h["target"])} {h["unit"]}.\nВведите, сколько добавляем (например, 0,5), или нажмите кнопку.',
                    [
                        ["+1", "+5", "+10"],
                        ["✅ Выполнить норму", "Завершить привычку"],
                        [BACK],
                    ],
                )
            if state == "name":
                if not 1 <= len(text) <= 80:
                    raise ValueError("Название должно содержать 1–80 символов.")
                context.user_data.update(name=text, state="unit")
                return await reply(
                    update,
                    "В чём измерять? Например: мин, км, страниц, повторений.",
                    [["мин", "км", "страниц"], ["повторений", "раз"], [BACK]],
                )
            if state == "unit":
                if not 1 <= len(text) <= 20:
                    raise ValueError("Единица измерения: 1–20 символов.")
                context.user_data.update(unit=text, state="target")
                return await reply(
                    update,
                    "Какая посильная дневная норма? Можно дробное число: 0,5. Лучше начать с малого.",
                    [[BACK]],
                )
            if state == "target":
                import math

                target = float(text.replace(",", "."))
                if not math.isfinite(target) or not 0 < target <= 1000000:
                    raise ValueError("Нужно положительное число до 1000000.")
                context.user_data.update(target=target, state="days")
                return await reply(
                    update,
                    "Сколько дней? 7, 14, 30 или 0 — без срока.",
                    [["7", "14", "30"], ["0"], [BACK]],
                )
            if state == "days":
                d = context.user_data
                self.store.create_habit(
                    uid, d["name"], d["unit"], d["target"], int(text)
                )
                await reply(update, "Привычка создана. Начнём с сегодняшнего дня!")
                return await self.today(update, context)
            if state == "progress":
                hid = context.user_data["hid"]
                h = self.store.habit(uid, hid)
                if text == "Завершить привычку":
                    context.user_data["state"] = "archive"
                    return await reply(
                        update,
                        "Завершить привычку? История и награды сохранятся.",
                        [["Да, завершить"], [BACK]],
                    )
                amount = (
                    max(0, h["target"] - self.store.summary(uid, h)["today"])
                    if text == "✅ Выполнить норму"
                    else float(text.lstrip("+").replace(",", "."))
                )
                if text == "✅ Выполнить норму" and amount == 0:
                    return await reply(
                        update, "Норма уже выполнена. Отдых тоже часть плана.", [[BACK]]
                    )
                s, awards = self.store.add_progress(uid, hid, amount)
                await reply(
                    update,
                    f'Сохранено: {num(s["today"])}/{num(h["target"])} {h["unit"]}. Серия: {s["streak"]} дн.'
                    + "".join("\n🏆 " + a for a in awards),
                )
                return await self.today(update, context)
            if state == "archive" and text == "Да, завершить":
                self.store.archive(uid, context.user_data["hid"])
                return await self.today(update, context)
            if state == "goal":
                self.store.add_goal(uid, text)
                context.user_data["state"] = "coach"
                await reply(update, "Цель сохранена.")
                return await self.coach_reply(
                    update,
                    "Помоги разбить мою новую цель на 2–3 небольших шага: " + text,
                )
            if state == "coach":
                if len(text) > 2000:
                    raise ValueError("Сократите вопрос до 2000 символов.")
                return await self.coach_reply(update, text)
            if state == "tone":
                self.store.settings(uid, tone=text)
                return await self.today(update, context)
            if state == "timezone":
                self.store.settings(uid, timezone=text)
                return await self.today(update, context)
            if state == "reminder":
                value = datetime.strptime(text, "%H:%M").strftime("%H:%M")
                self.store.settings(uid, reminder=value, last_reminder=None)
                await reply(update, "Ежедневное напоминание сохранено.")
                return await self.today(update, context)
            await reply(update, "Выберите действие в меню. /start — начать заново.")
        except (ValueError, ZoneInfoNotFoundError, OverflowError):
            await reply(
                update,
                "Не удалось сохранить. Проверьте формат: положительное число, допустимый срок или часовой пояс. Для выхода нажмите «Назад».",
                [[BACK]],
            )

    async def delete_data(self, update, context):
        context.user_data.clear()
        context.user_data["delete_confirm"] = True
        await reply(
            update,
            "Удалить все ваши цели, привычки, прогресс и историю коуча? Отправьте /confirm_delete. «Назад» отменяет удаление.",
            [[BACK]],
        )

    async def confirm_delete(self, update, context):
        if not context.user_data.pop("delete_confirm", False):
            return await reply(update, "Сначала используйте /delete_data.")
        uid = update.effective_user.id
        with self.store.connect() as db:
            db.execute(
                "DELETE FROM progress WHERE habit_id IN (SELECT id FROM habits WHERE user_id=?)",
                (uid,),
            )
            for table in ("awards", "messages", "goals"):
                db.execute(f"DELETE FROM {table} WHERE user_id=?", (uid,))
            db.execute("DELETE FROM habits WHERE user_id=?", (uid,))
            db.execute("DELETE FROM users WHERE id=?", (uid,))
        context.user_data.clear()
        await reply(update, "Ваши данные удалены. /start — начать заново.")

    async def reminder_tick(self, app, now=None):
        now = now or datetime.now(timezone.utc)
        for user in self.store.reminder_users():
            local = now.astimezone(ZoneInfo(user["timezone"]))
            day = str(local.date())
            if (
                user["last_reminder"] == day
                or local.strftime("%H:%M") < user["reminder"]
            ):
                continue
            pending = [
                h["name"]
                for h in self.store.habits(user["id"], local.date())
                if self.store.summary(user["id"], h, local.date())["today"] + 1e-9
                < h["target"]
            ]
            if not pending:
                continue
            try:
                await app.bot.send_message(
                    user["id"],
                    "Путь-24 · На сегодня осталось: "
                    + ", ".join(pending)
                    + ".\nВыберите посильный шаг. /today — открыть план.",
                )
                self.store.settings(user["id"], last_reminder=day)
            except Forbidden:
                self.store.settings(user["id"], reminder=None)
            except TelegramError as exc:
                logger.warning("Reminder failed: %s", type(exc).__name__)

    async def post_init(self, app):
        async def loop():
            while True:
                try:
                    await self.reminder_tick(app)
                except Exception as exc:
                    logger.error("Reminder loop failed: %s", type(exc).__name__)
                await asyncio.sleep(30)

        self.reminder_task = asyncio.create_task(loop())

    async def post_stop(self, app):
        if self.reminder_task:
            self.reminder_task.cancel()
            try:
                await self.reminder_task
            except asyncio.CancelledError:
                pass
        await self.coach.close()
