from telebot.types import ReplyKeyboardMarkup, KeyboardButton

def menu_keyboard_permanen():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🗓️ Buat Jadwal"), 
        KeyboardButton("📋 Agenda Hari Ini")
    )
    markup.add(
        KeyboardButton("⚙️ Hapus Jadwal"), 
        KeyboardButton("💬 Tanya JARVIS")
    )
    return markup