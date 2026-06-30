import os
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ConversationHandler, ContextTypes
)
import logging
from datetime import datetime

from database import Database
from deepseek_agent import DeepSeekAgent

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CHOOSING = 0
WAITING_EXERCISE = 1
WAITING_DAILY_TARGET = 2
WAITING_DAYS = 3
WAITING_PROGRESS = 4
WAITING_QUESTION = 5
WAITING_GOAL = 6

def main_keyboard():
    keyboard = [
        ["🏋️ Челленджи", "💤 Режим"],
        ["💧 Вода", "🎯 Цели"],
        ["📊 Статистика", "🏆 Достижения"],
        ["📤 Поделиться", "❓ Спросить коуча"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def progress_keyboard():
    keyboard = [
        ["+1", "+3", "+5"],
        ["+10", "+20", "+50"],
        ["Ввести число", "◀️ Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def challenge_keyboard():
    keyboard = [
        ["💪 Отжимания", "🦵 Берпи"],
        ["🏃 Бег (км)", "🎯 Свой челлендж"],
        ["◀️ Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def sleep_keyboard():
    keyboard = [
        ["✅ Подтвердить подъем", "🌙 Подтвердить отбой"],
        ["⚙️ Настроить время", "◀️ Назад"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_keyboard():
    keyboard = [["◀️ Назад"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    Database.init_user(user.id, user.username, user.first_name)
    
    motivation = DeepSeekAgent.get_motivation(
        f"Новый пользователь {user.first_name} только что присоединился. Поприветствуй жестко."
    )
    
    await update.message.reply_text(
        f"🔥 ПУТЬ-24 🔥\n\n"
        f"Привет, {user.first_name}!\n\n"
        f"Я твой цифровой коуч. Никакой жалости, только дисциплина.\n"
        f"«Ты либо строишь себя, либо смотришь, как другие строят»\n\n"
        f"{motivation}\n\n"
        f"Выбери действие:",
        reply_markup=main_keyboard()
    )
    return CHOOSING

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("Выбери действие:", reply_markup=main_keyboard())
    return CHOOSING

async def start_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Выбери тип упражнения:", reply_markup=challenge_keyboard())
    return WAITING_EXERCISE

async def choose_exercise(update: Update, context: ContextTypes.DEFAULT_TYPE):
    exercise = update.message.text
    context.user_data['exercise'] = exercise
    await update.message.reply_text(
        f"Сколько {exercise.lower()} в день планируешь делать? (только число)",
        reply_markup=back_keyboard()
    )
    return WAITING_DAILY_TARGET

async def set_daily_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        daily_target = int(update.message.text)
        if daily_target <= 0:
            await update.message.reply_text("Число должно быть больше 0. Попробуй еще раз:")
            return WAITING_DAILY_TARGET
        context.user_data['daily_target'] = daily_target
        await update.message.reply_text(
            "На сколько дней челлендж? (если без срока — напиши 0)",
            reply_markup=back_keyboard()
        )
        return WAITING_DAYS
    except ValueError:
        await update.message.reply_text("Пожалуйста, введи число:")
        return WAITING_DAILY_TARGET

async def set_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        days = int(update.message.text)
        if days < 0:
            await update.message.reply_text("Число должно быть 0 или больше:")
            return WAITING_DAYS
        
        user_id = update.effective_user.id
        exercise = context.user_data['exercise']
        daily_target = context.user_data['daily_target']
        
        challenge = Database.create_challenge(user_id, exercise, daily_target, days if days > 0 else None)
        context.user_data['challenge_id'] = challenge['id']
        
        motivation = DeepSeekAgent.get_motivation(
            f"Пользователь начал челлендж: {exercise}, {daily_target} в день. Поддержи его жестко."
        )
        
        await update.message.reply_text(
            f"🔥 Челлендж создан!\n\n"
            f"Упражнение: {exercise}\n"
            f"Цель в день: {daily_target}\n"
            f"Срок: {'∞ (без срока)' if days == 0 else f'{days} дней'}\n\n"
            f"{motivation}\n\n"
            f"Теперь отмечай прогресс кнопками ниже:",
            reply_markup=progress_keyboard()
        )
        return WAITING_PROGRESS
    except ValueError:
        await update.message.reply_text("Пожалуйста, введи число:")
        return WAITING_DAYS

async def add_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    challenge_id = context.user_data.get('challenge_id')
    
    if not challenge_id:
        await update.message.reply_text("Сначала создай или выбери челлендж!")
        return ConversationHandler.END
    
    text = update.message.text
    
    if text == "Ввести число":
        await update.message.reply_text("Введи количество сделанных повторений:", reply_markup=back_keyboard())
        context.user_data['expecting_number'] = True
        return WAITING_PROGRESS
    
    if text.startswith("+"):
        amount = int(text[1:])
    elif context.user_data.get('expecting_number'):
        try:
            amount = int(text)
            context.user_data['expecting_number'] = False
        except ValueError:
            await update.message.reply_text("Введи корректное число:")
            return WAITING_PROGRESS
    else:
        return WAITING_PROGRESS
    
    remaining = Database.add_progress(user_id, challenge_id, amount)
    challenge = Database.get_active_challenge(user_id)
    
    if remaining <= 0:
        motivation = DeepSeekAgent.get_motivation(
            f"Пользователь выполнил дневную норму! Упражнение: {challenge['exercise_type']}, стрик: {challenge['current_streak']} дней."
        )
        await update.message.reply_text(
            f"✅ Добавлено: {amount}\n🎯 Дневная цель выполнена! Стрик: {challenge['current_streak']} дней\n\n{motivation}",
            reply_markup=progress_keyboard()
        )
    else:
        await update.message.reply_text(
            f"✅ Добавлено: {amount}\n📊 Осталось до дневной цели: {remaining}\nВсего сделано: {challenge['total_done']}",
            reply_markup=progress_keyboard()
        )
    
    achievements = Database.check_achievement(user_id, challenge)
    for achievement in achievements:
        await update.message.reply_text(f"🏆 Достижение разблокировано: {achievement}!")
    
    return WAITING_PROGRESS

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    challenges = Database.get_stats(user_id)
    
    if not challenges:
        await update.message.reply_text("У тебя пока нет активных челленджей. Создай первый!", reply_markup=main_keyboard())
        return CHOOSING
    
    message = "📊 Твоя статистика:\n\n"
    for ch in challenges:
        message += f"🏋️ {ch['exercise_type']}\n📅 Стрик: {ch['current_streak']} дней (лучший: {ch['best_streak']})\n💯 Всего: {ch['total_done']}\n🎯 Цель в день: {ch['daily_target']}\n{'─' * 30}\n"
    
    await update.message.reply_text(message, reply_markup=main_keyboard())
    return CHOOSING

async def sleep_water_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💤💧 Режим и вода\n\nЗдесь ты отмечаешь подъем и отбой.", reply_markup=sleep_keyboard())
    return CHOOSING

async def confirm_wake_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    motivation = DeepSeekAgent.get_motivation("Пользователь подтвердил подъем. Напомни про стакан теплой воды.")
    await update.message.reply_text(
        f"☀️ Подъем зафиксирован в {datetime.now().strftime('%H:%M')}\n\n💧 Выпей стакан теплой воды!\n\n{motivation}",
        reply_markup=main_keyboard()
    )
    return CHOOSING

async def confirm_sleep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    motivation = DeepSeekAgent.get_motivation("Пользователь ложится спать. Похвали за соблюдение режима.")
    await update.message.reply_text(
        f"🌙 Отбой зафиксирован в {datetime.now().strftime('%H:%M')}\n\n{motivation}",
        reply_markup=main_keyboard()
    )
    return CHOOSING

async def handle_water(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💧 Не забудь выпить стакан теплой воды!\n\nЭто запускает метаболизм и дает энергию.", reply_markup=main_keyboard())
    return CHOOSING

async def goals_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎯 Жизненные цели\n\nНапиши свою цель на текущий месяц:", reply_markup=back_keyboard())
    return WAITING_GOAL

async def add_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    goal_text = update.message.text
    month_year = datetime.now().strftime("%Y-%m")
    
    Database.add_goal(user_id, goal_text, month_year)
    motivation = DeepSeekAgent.get_motivation(f"Пользователь поставил цель: '{goal_text}'. Вдохнови.")
    
    await update.message.reply_text(
        f"✅ Цель записана:\n\n📝 {goal_text}\n📅 {datetime.now().strftime('%B %Y')}\n\n{motivation}",
        reply_markup=main_keyboard()
    )
    return CHOOSING

async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    from database import memory_db
    
    achievements = [a for a in memory_db["achievements"] if a["user_id"] == user_id]
    
    if not achievements:
        await update.message.reply_text("🏆 У тебя пока нет достижений. Продолжай работать!", reply_markup=main_keyboard())
        return CHOOSING
    
    message = "🏆 Твои достижения:\n\n"
    for ach in achievements:
        emoji = "🔥" if ach['achievement_type'] == "streak" else "💪"
        message += f"{emoji} {ach['achievement_name']} — {ach['unlocked_at']}\n"
    
    await update.message.reply_text(message, reply_markup=main_keyboard())
    return CHOOSING

async def share_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    challenges = Database.get_stats(user_id)
    
    if not challenges:
        await update.message.reply_text("Нечем делиться! Начни челлендж.", reply_markup=main_keyboard())
        return CHOOSING
    
    share_text = "🔥 Мой прогресс с коучем «Путь-24»:\n\n"
    for ch in challenges:
        share_text += f"💪 {ch['exercise_type']}\n📊 Стрик: {ch['current_streak']} дней\n💯 Всего: {ch['total_done']}\n\n"
    share_text += "Присоединяйся: @put24_bot\n#Путь24 #Дисциплина"
    
    await update.message.reply_text(f"📤 Готово!\n\n{share_text}", reply_markup=main_keyboard())
    return CHOOSING

async def ask_coach(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Задай свой вопрос коучу:", reply_markup=back_keyboard())
    return WAITING_QUESTION

async def answer_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_data = Database.get_user(user_id)
    question = update.message.text
    
    await update.message.reply_text("🤔 Дай подумать...")
    answer = DeepSeekAgent.answer_question(question, user_data or {})
    
    await update.message.reply_text(answer, reply_markup=main_keyboard())
    return CHOOSING

def main():
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("TELEGRAM_TOKEN не найден!")
        return
    
    app = Application.builder().token(token).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING: [
                MessageHandler(filters.Regex(r'^🏋️ Челленджи$'), start_challenge),
                MessageHandler(filters.Regex(r'^💤 Режим$'), sleep_water_menu),
                MessageHandler(filters.Regex(r'^💧 Вода$'), handle_water),
                MessageHandler(filters.Regex(r'^🎯 Цели$'), goals_menu),
                MessageHandler(filters.Regex(r'^📊 Статистика$'), show_stats),
                MessageHandler(filters.Regex(r'^🏆 Достижения$'), show_achievements),
                MessageHandler(filters.Regex(r'^📤 Поделиться$'), share_progress),
                MessageHandler(filters.Regex(r'^❓ Спросить коуча$'), ask_coach),
                MessageHandler(filters.Regex(r'^✅ Подтвердить подъем$'), confirm_wake_up),
                MessageHandler(filters.Regex(r'^🌙 Подтвердить отбой$'), confirm_sleep),
            ],
            WAITING_EXERCISE: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_exercise)],
            WAITING_DAILY_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_daily_target)],
            WAITING_DAYS: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_days)],
            WAITING_PROGRESS: [
                MessageHandler(filters.Regex(r'^\+'), add_progress),
                MessageHandler(filters.Regex(r'^Ввести число$'), add_progress),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_progress),
            ],
            WAITING_QUESTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, answer_question)],
            WAITING_GOAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_goal)],
        },
        fallbacks=[
            MessageHandler(filters.Regex(r'^◀️ Назад$'), back_to_main),
            CommandHandler('start', start),
        ],
    )
    
    app.add_handler(conv_handler)
    
    logger.info("🤖 Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()