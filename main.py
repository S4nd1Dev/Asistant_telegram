import sys
import traceback
import threading
from keep_alive import app
from config.settings import Config
from bot.core import bot

try:
    print("🚀 [1/3] Memulai inisialisasi...", flush=True)
    import bot.handlers.main_handlers
    
    print("✅ [2/3] Handlers berhasil dihubungkan...", flush=True)
    print("✅ [3/3] Semua sistem siap! Menyalakan JARVIS...", flush=True)

    def jalankan_bot():
        try:
            print("🤖 [T-01] Memulai proses Polling Telegram di background...", flush=True)
            bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            print("\n" + "="*40, flush=True)
            print(f"❌ THREAD CRASH: Polling Telegram Gagal!", flush=True)
            traceback.print_exc(file=sys.stdout)
            print("="*40 + "\n", flush=True)

    # Menjalankan bot di thread terpisah
    bot_thread = threading.Thread(target=jalankan_bot)
    bot_thread.daemon = True
    bot_thread.start()

    if __name__ == "__main__":
        print("🌐 [W-01] Menyalakan Web Server Flask...", flush=True)
        app.run(host="0.0.0.0", port=Config.PORT, use_reloader=False)

except Exception as e:
    print("\n" + "="*40, flush=True)
    print("❌ CRASH DETECTED (Mati Saat Inisialisasi):", flush=True)
    traceback.print_exc(file=sys.stdout)
    print("="*40 + "\n", flush=True)
    sys.exit(1)