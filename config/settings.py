import os
import json
from dotenv import load_dotenv

load_dotenv()

class Config:
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    CALENDAR_ID = os.getenv("CALENDAR_ID")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    PORT = int(os.environ.get("PORT", 10000))
    
    # Google Credentials
    GOOGLE_CREDENTIALS_ENV = os.getenv("GOOGLE_CREDENTIALS")

    @classmethod
    def get_google_creds_info(cls):
        if cls.GOOGLE_CREDENTIALS_ENV:
            return json.loads(cls.GOOGLE_CREDENTIALS_ENV)
        return None