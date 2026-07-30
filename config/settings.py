import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CALENDAR_ID = os.getenv("CALENDAR_ID")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    PORT = int(os.environ.get("PORT", 10000))
    
    # Google Credentials (Master / Service Account lama jika masih dipakai)
    GOOGLE_CREDENTIALS_ENV = os.getenv("GOOGLE_CREDENTIALS")

    # --- TAMBAHAN KUNCI GOOGLE OAUTH WEB (WAJIB ADA) ---
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
    GOOGLE_REDIRECT_URI = "https://asistant-telegram.onrender.com/callback"
    # ---------------------------------------------------

    @classmethod
    def get_google_creds_info(cls):
        if cls.GOOGLE_CREDENTIALS_ENV:
            return json.loads(cls.GOOGLE_CREDENTIALS_ENV)
        return None