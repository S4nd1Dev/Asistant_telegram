import os
from dotenv import load_dotenv
from google import genai

# Load API Key dari file .env
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Menggunakan format inisiasi client SDK terbaru
client = genai.Client(api_key=api_key)

print("Mencari daftar model yang tersedia...")
print("-" * 30)

try:
    # Perintah list model di SDK terbaru
    models = client.models.list()
    for m in models:
        # Cek apakah model mendukung generateContent (untuk chat)
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ {m.name}")
            
except Exception as e:
    print(f"❌ Ada error saat mengecek: {e}")