import sys
import traceback
import threading
from keep_alive import app
from config.settings import Config

# PERBAIKAN: Gunakan alias 'jarvis_bot' agar tidak bentrok dengan nama folder 'bot'
from bot.core import bot as jarvis_bot 

# --- PENAMBAHAN KODE DATABASE ---
from database.db import engine, Base
import database.models  # Membaca cetak biru
Base.metadata.create_all(bind=engine) # Mengeksekusi pembuatan jarvis.db
# --------------------------------

try:
    print("🚀 [1/3] Memulai inisialisasi...", flush=True)
    
    # PERBAIKAN: Cara impor yang lebih aman untuk modul
    from bot.handlers import main_handlers 
    
    print("✅ [2/3] Handlers berhasil dihubungkan...", flush=True)
    print("✅ [3/3] Semua sistem siap! Menyalakan JARVIS...", flush=True)

    def jalankan_bot():
        try:
            print("🤖 [T-01] Memulai proses Polling Telegram di background...", flush=True)
            # Panggil menggunakan alias
            jarvis_bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
        except Exception as e:
            print("\n" + "="*40, flush=True)
            print(f"❌ THREAD CRASH: Polling Telegram Gagal!", flush=True)
            traceback.print_exc(file=sys.stdout)
            print("="*40 + "\n", flush=True)

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