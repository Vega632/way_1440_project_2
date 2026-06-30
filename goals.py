from database import Database
from deepseek_agent import DeepSeekAgent
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

async def goals_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎯 Жизненные цели\n\n"
        "Здесь ты ставишь личные цели на месяц. Это не попадет в публичный профиль.\n\n"
        "Напиши свою цель на текущий месяц (одним сообщением):",
        reply_markup=back_keyboard()
    )
    context.user_data['waiting_goal'] = True

async def add_goal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_goal'):
        return
    
    user_id = update.effective_user.id
    goal_text = update.message.text
    month_year = datetime.now().strftime("%Y-%m")
    
    Database.add_goal(user_id, goal_text, month_year)
    
    motivation = DeepSeekAgent.get_motivation(
        f"Пользователь поставил цель на месяц: '{goal_text}'. Вдохнови на достижение."
    )
    
    await update.message.reply_text(
        f"✅ Цель записана:\n\n"
        f"📝 {goal_text}\n"
        f"📅 На {datetime.now().strftime('%B %Y')}\n\n"
        f"{motivation}",
        reply_markup=main_keyboard()
    )
    context.user_data['waiting_goal'] = False