from database import Database
from deepseek_agent import DeepSeekAgent
from telegram import Update
from telegram.ext import ContextTypes
from datetime import datetime

async def sleep_water_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💤💧 Режим и вода\n\n"
        "Здесь ты отмечаешь подъем и отбой, а также получаешь напоминания о воде.",
        reply_markup=sleep_keyboard()
    )

async def confirm_wake_up(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    motivation = DeepSeekAgent.get_motivation(
        "Пользователь подтвердил подъем. Напомни про стакан теплой воды и дай заряд на день."
    )
    
    await update.message.reply_text(
        f"☀️ Подъем зафиксирован в {datetime.now().strftime('%H:%M')}\n\n"
        f"💧 Выпей стакан теплой воды — это запускает организм!\n\n"
        f"{motivation}",
        reply_markup=main_keyboard()
    )

async def confirm_sleep(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    motivation = DeepSeekAgent.get_motivation(
        "Пользователь ложится спать. Похвали за соблюдение режима, напомни о важности сна."
    )
    
    await update.message.reply_text(
        f"🌙 Отбой зафиксирован в {datetime.now().strftime('%H:%M')}\n\n"
        f"{motivation}",
        reply_markup=main_keyboard()
    )

async def setup_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ Настройка времени\n\n"
        "Напиши время в формате ЧЧ:ММ (например, 23:00 для отбоя, 07:00 для подъема)",
        reply_markup=back_keyboard()
    )
    context.user_data['setting_time'] = True

async def process_time_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('setting_time'):
        return
    
    time_text = update.message.text
    try:
        time_obj = datetime.strptime(time_text, "%H:%M").time()
        # Здесь нужно добавить логику сохранения времени в БД
        await update.message.reply_text(
            f"✅ Время установлено: {time_text}",
            reply_markup=main_keyboard()
        )
        context.user_data['setting_time'] = False
    except ValueError:
        await update.message.reply_text(
            "❌ Неверный формат. Используй ЧЧ:ММ (например, 23:00)",
            reply_markup=back_keyboard()
        )