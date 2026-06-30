from database import Database
from deepseek_agent import DeepSeekAgent
from telegram import Update
from telegram.ext import ContextTypes

async def share_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    challenges = Database.get_stats(user_id)
    
    if not challenges:
        await update.message.reply_text(
            "Нечем делиться! Начни челлендж сначала.",
            reply_markup=main_keyboard()
        )
        return
    
    # Генерируем текст для соцсетей (только спорт)
    share_text = "🔥 Мой прогресс с коучем «Путь-24»:\n\n"
    
    for ch in challenges:
        share_text += (
            f"💪 {ch['exercise_type']}\n"
            f"📊 Стрик: {ch['current_streak']} дней\n"
            f"💯 Всего: {ch['total_done']} повторений\n\n"
        )
    
    share_text += "Присоединяйся: @put24_bot\n#Путь24 #Дисциплина"
    
    await update.message.reply_text(
        f"📤 Готово! Вот текст для публикации:\n\n"
        f"{share_text}\n\n"
        f"(скопируй и поделись в соцсетях)",
        reply_markup=main_keyboard()
    )