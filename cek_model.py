import google.generativeai as genai
import os
from dotenv import load_dotenv

# Load API Key dari file .env
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

print("Mencari daftar model yang tersedia...")
print("-" * 30)

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print("Ada error saat mengecek:", e)