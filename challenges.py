from database import Database
from deepseek_agent import DeepSeekAgent
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

WAITING_EXERCISE = 1
WAITING_DAILY_TARGET = 2
WAITING_DAYS = 3
WAITING_PROGRESS = 4

async def start_challenge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Выбери тип упражнения:",
        reply_markup=challenge_keyboard()
    )
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
        
        challenge = Database.create_challenge(
            user_id,
            exercise,
            daily_target,
            days if days > 0 else None
        )
        
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
        
        # Сохраняем состояние для добавления прогресса
        context.user_data['state'] = 'tracking'
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
            f"Пользователь выполнил дневную норму! Упражнение: {challenge['exercise_type']}, "
            f"стрик: {challenge['current_streak']} дней. Похвали, но напомни что это только начало."
        )
        await update.message.reply_text(
            f"✅ Добавлено: {amount}\n"
            f"🎯 Дневная цель выполнена! Стрик: {challenge['current_streak']} дней\n\n"
            f"{motivation}",
            reply_markup=progress_keyboard()
        )
    else:
        await update.message.reply_text(
            f"✅ Добавлено: {amount}\n"
            f"📊 Осталось до дневной цели: {remaining}\n"
            f"Всего сделано: {challenge['total_done']}",
            reply_markup=progress_keyboard()
        )
    
    # Проверяем достижения
    achievements = Database.check_achievement(user_id, challenge)
    for achievement in achievements:
        await update.message.reply_text(f"🏆 Достижение разблокировано: {achievement}!")
    
    return WAITING_PROGRESS

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    challenges = Database.get_stats(user_id)
    
    if not challenges:
        await update.message.reply_text(
            "У тебя пока нет активных челленджей. Создай первый!",
            reply_markup=main_keyboard()
        )
        return ConversationHandler.END
    
    message = "📊 Твоя статистика:\n\n"
    for ch in challenges:
        message += (
            f"🏋️ {ch['exercise_type']}\n"
            f"📅 Стрик: {ch['current_streak']} дней (лучший: {ch['best_streak']})\n"
            f"💯 Всего: {ch['total_done']}\n"
            f"🎯 Цель в день: {ch['daily_target']}\n"
            f"{'─' * 30}\n"
        )
    
    await update.message.reply_text(message, reply_markup=main_keyboard())
    return ConversationHandler.END

