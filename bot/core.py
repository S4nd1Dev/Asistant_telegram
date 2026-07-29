import telebot
from groq import Groq
from config.settings import Config

# Inisialisasi instance Bot dan AI secara terpusat
bot = telebot.TeleBot(Config.TELEGRAM_TOKEN)
groq_client = Groq(api_key=Config.GROQ_API_KEY)