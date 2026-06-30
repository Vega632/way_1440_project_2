from telegram import ReplyKeyboardMarkup, KeyboardButton

def main_keyboard():
    keyboard = [
        [KeyboardButton("🏋️ Челленджи"), KeyboardButton("💤 Режим")],
        [KeyboardButton("💧 Вода"), KeyboardButton("🎯 Цели")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("🏆 Достижения")],
        [KeyboardButton("📤 Поделиться"), KeyboardButton("❓ Спросить коуча")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def challenge_keyboard():
    keyboard = [
        [KeyboardButton("💪 Отжимания"), KeyboardButton("🦵 Берпи")],
        [KeyboardButton("🏃 Бег (км)"), KeyboardButton("🎯 Свой челлендж")],
        [KeyboardButton("◀️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def progress_keyboard():
    keyboard = [
        [KeyboardButton("+1"), KeyboardButton("+3"), KeyboardButton("+5")],
        [KeyboardButton("+10"), KeyboardButton("+20"), KeyboardButton("+50")],
        [KeyboardButton("Ввести число"), KeyboardButton("◀️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def sleep_keyboard():
    keyboard = [
        [KeyboardButton("✅ Подтвердить подъем"), KeyboardButton("🌙 Подтвердить отбой")],
        [KeyboardButton("⚙️ Настроить время"), KeyboardButton("◀️ Назад")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def back_keyboard():
    keyboard = [[KeyboardButton("◀️ Назад")]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)