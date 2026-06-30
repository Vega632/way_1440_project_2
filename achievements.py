from database import Database
from telegram import Update
from telegram.ext import ContextTypes

async def show_achievements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Получаем достижения из базы (нужно добавить метод в database.py)
    from database import supabase
    achievements = supabase.table("achievements").select("*").eq("user_id", user_id).execute().data
    
    if not achievements:
        await update.message.reply_text(
            "🏆 У тебя пока нет достижений. Продолжай работать, и они появятся!",
            reply_markup=main_keyboard()
        )
        return
    
    message = "🏆 Твои достижения:\n\n"
    for ach in achievements:
        emoji = "🔥" if ach['achievement_type'] == "streak" else "💪"
        message += f"{emoji} {ach['achievement_name']} — {ach['unlocked_at'][:10]}\n"
    
    await update.message.reply_text(message, reply_markup=main_keyboard())