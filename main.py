import threading
from keep_alive import app
from config.settings import Config
from bot.core import bot

# PENTING: Mengimpor handler agar terdaftar ke dalam bot
import bot.handlers.main_handlers 

print("Mini JARVIS v3.1 (Clean Arch Phase 1B) Aktif.", flush=True)

def jalankan_bot():
    bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)

bot_thread = threading.Thread(target=jalankan_bot)
bot_thread.daemon = True
bot_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=Config.PORT, use_reloader=False)