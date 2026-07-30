import sys
import traceback
import threading
from flask import request
from google_auth_oauthlib.flow import Flow
from keep_alive import app
from config.settings import Config
from database.db import SessionLocal
from database.models import User
import json
import os

# PERBAIKAN: Gunakan alias 'jarvis_bot' agar tidak bentrok dengan nama folder 'bot'
from bot.core import bot as jarvis_bot 

# --- PENAMBAHAN KODE DATABASE ---
from database.db import engine, Base
import database.models  # Membaca cetak biru
Base.metadata.create_all(bind=engine) # Mengeksekusi pembuatan jarvis.db
# --------------------------------

# Izinkan transport HTTP untuk development lokal (jika diuji di laptop)
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

@app.route('/callback')
def oauth_callback():
    code = request.args.get('code')
    state = request.args.get('state') # state berisi chat_id Telegram user
    
    if not code or not state:
        return "❌ Autentikasi gagal: Parameter dari Google tidak lengkap.", 400

    chat_id = int(state)

    try:
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": Config.GOOGLE_CLIENT_ID,
                    "client_secret": Config.GOOGLE_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [Config.GOOGLE_REDIRECT_URI]
                }
            },
            scopes=['https://www.googleapis.com/auth/calendar']
        )
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Konversi credentials ke dalam dictionary agar bisa disimpan ke database SQLite
        token_json = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes
        }

        db = SessionLocal()
        user = db.query(User).filter(User.chat_id == chat_id).first()
        if user:
            user.google_oauth_token = json.dumps(token_json)
            db.commit()
        db.close()

        return "<h2>✅ Autentikasi Berhasil!</h2><p>Kalender Google kamu berhasil ditautkan ke JARVIS. Silakan tutup halaman ini dan kembali ke Telegram.</p>"

    except Exception as e:
        return f"❌ Terjadi kesalahan saat memproses token: {str(e)}", 500


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