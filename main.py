import os
import json
from datetime import datetime, timedelta, timezone
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google import genai
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from keep_alive import keep_alive

# ==========================================
# 1. SETUP & ENVIRONMENT VARIABLES
# ==========================================
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
CALENDAR_ID = os.getenv("CALENDAR_ID")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
client = genai.Client(api_key=GEMINI_API_KEY)

# ==========================================
# 2. SETUP GOOGLE CALENDAR
# ==========================================
SCOPES = ['https://www.googleapis.com/auth/calendar']
creds_env = os.getenv("GOOGLE_CREDENTIALS")

if creds_env:
    creds_info = json.loads(creds_env)
    creds = service_account.Credentials.from_service_account_info(creds_info, scopes=SCOPES)
else:
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

calendar_service = build('calendar', 'v3', credentials=creds)

pending_events = {}
wizard_data = {}

def create_calendar_event(event_data):
    event = {
        'summary': event_data.get('nama_acara', 'Jadwal Baru'),
        'description': event_data.get('deskripsi', ''),
        'start': {'dateTime': event_data['waktu_mulai'], 'timeZone': 'Asia/Jakarta'},
        'end': {'dateTime': event_data['waktu_selesai'], 'timeZone': 'Asia/Jakarta'},
    }
    event_result = calendar_service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return event_result.get('htmlLink')

def tampilkan_konfirmasi(chat_id, bot_msg_id, event_data):
    waktu_format_baca = event_data['waktu_mulai'].replace('T', ' ')
    pesan_konfirmasi = (
        f"🧠 **JARVIS Intelligence Report**\n\n"
        f"📌 **Acara:** {event_data['nama_acara']}\n"
        f"🟢 **Waktu:** {waktu_format_baca} WIB\n"
    )
    
    if event_data.get("alasan_waktu"):
        pesan_konfirmasi += f"📋 **Analisis Alasan:** {event_data['alasan_waktu']}\n\n"
    else:
        pesan_konfirmasi += "\n"
        
    markup = InlineKeyboardMarkup(row_width=1)
    if event_data.get("penawaran_bantuan"):
        pesan_konfirmasi += f"💡 **Saran Sistem:**\n_{event_data['penawaran_bantuan']}_\n\n"
        markup.add(InlineKeyboardButton("🚀 Eksekusi Jadwal + Jalankan Skenario AI", callback_data="confirm_help"))
        
    markup.add(
        InlineKeyboardButton("✅ Masukkan Kalender Saja", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Batalkan Perintah", callback_data="confirm_no")
    )
    
    bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id,
                          text=pesan_konfirmasi, reply_markup=markup, parse_mode="Markdown")

def menu_utama(chat_id, message_id=None):
    """Fungsi pembantu untuk menampilkan dasbor utama"""
    pesan = (
        "🤖 **MINI JARVIS - Command Center** ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Sistem utama *online*. Modul AI dan kalender telah disinkronisasi.\n\n"
        "Saya siap mengamankan blok waktu untuk progres arsitektur Two-Tower, rutinitas gym, atau sesi eksperimen di Linux hari ini.\n\n"
        "🛠️ **Daftar Perintah Manual:**\n"
        "🔹 `/buat` - Langsung jadwalkan aktivitas\n"
        "🔹 `/menu` - Tampilkan kembali dasbor ini\n\n"
        "Atau gunakan panel kendali cepat di bawah:"
    )
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("➕ Buat Jadwal Baru", callback_data="trigger_buat"),
        InlineKeyboardButton("⚙️ Status Sistem", callback_data="trigger_status")
    )
    
    if message_id:
        bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=pesan, reply_markup=markup, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, pesan, reply_markup=markup, parse_mode="Markdown")

# ==========================================
# STEP 1: INTERFACE MENU & INPUT TOPIK
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    menu_utama(message.chat.id)

@bot.message_handler(commands=['buat'])
def command_buat(message):
    chat_id = message.chat.id
    pesan = "🤖 **Mode Penjadwalan Aktif.**\n\nKetik ide/judul aktivitas yang ingin dijadwalkan:"
    msg = bot.reply_to(message, pesan, parse_mode="Markdown")
    bot.register_next_step_handler(msg, lambda m: proses_judul(m, msg.message_id))

def proses_judul(message, bot_msg_id):
    chat_id = message.chat.id
    if message.text.startswith('/'): return

    wizard_data[chat_id] = {
        'nama_acara': message.text,
        'bot_msg_id': bot_msg_id
    }
    
    try: bot.delete_message(chat_id, message.message_id)
    except: pass

    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("🤖 Biarkan JARVIS Atur (Otomatis + Alasan)", callback_data="mode_auto"),
        InlineKeyboardButton("✍️ Saya Mau Ketik Waktu Sendiri", callback_data="mode_manual")
    )
    
    bot.edit_message_text(
        chat_id=chat_id, message_id=bot_msg_id,
        text=f"📌 **Aktivitas:** {message.text}\n\nBagaimana kamu ingin menentukan alokasi waktu untuk jadwal ini?",
        reply_markup=markup, parse_mode="Markdown"
    )

# ==========================================
# STEP 2: HANDLER CALLBACK & SELEKSI MODE
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    data = call.data
    bot_msg_id = call.message.message_id

    # --- MENU NAVIGATION ---
    if data == "trigger_buat":
        bot.answer_callback_query(call.id)
        pesan = "🤖 **Mode Penjadwalan Aktif.**\n\nKetik ide/judul aktivitas yang ingin dijadwalkan:"
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=pesan, parse_mode="Markdown")
        bot.register_next_step_handler_by_chat_id(chat_id, lambda m: proses_judul(m, bot_msg_id))
        
    elif data == "trigger_status":
        bot.answer_callback_query(call.id)
        pesan = (
            "🟢 **STATUS SISTEM:**\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🧠 **Engine:** Gemini 2.5 Flash\n"
            "📅 **Kalender:** Tersambung (Google API v3)\n"
            "🛡️ **Mode Keamanan:** Aktif (Env Vars)\n\n"
            "_Semua subsistem beroperasi dalam batas normal._"
        )
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("⬅️ Kembali ke Dasbor", callback_data="trigger_back_menu"))
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=pesan, reply_markup=markup, parse_mode="Markdown")
        
    elif data == "trigger_back_menu":
        bot.answer_callback_query(call.id)
        menu_utama(chat_id, bot_msg_id)

    # --- MODE AUTO & MANUAL ---
    elif data == "mode_auto":
        bot.answer_callback_query(call.id, "Menganalisis opsi waktu terbaik...")
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="⚡ *[■■■■□□□□□□] JARVIS sedang menghitung ritme produktivitas optimal...*", parse_mode="Markdown")
        
        topik = wizard_data[chat_id]['nama_acara']
        wib = timezone(timedelta(hours=7))
        waktu_sekarang_str = datetime.now(wib).strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            prompt_ai = f"""
            Waktu saat ini: {waktu_sekarang_str} WIB.
            Konteks User: Mahasiswa Informatika ITERA, AI Engineer MBKM DBS Foundation. Proyek utama: SisaBisa (Two-Tower). Pacar: Hanifa. Rutinitas: Gym (PPL/Upper-Lower), Bug Hunting (Linux, Nuclei, Subfinder).
            
            Tugas: Rekomendasikan waktu mulai dan selesai terbaik (bisa hari ini atau beberapa hari ke depan) untuk aktivitas berikut. Berikan ALASAN logis mengapa slot waktu tersebut dipilih.
            Nama Acara: '{topik}'
            
            Keluarkan output DALAM FORMAT JSON MURNI (tanpa block markdown ```json):
            {{
                "nama_acara": "Judul acara yang dirapikan",
                "waktu_mulai": "YYYY-MM-DDTHH:MM:SS",
                "waktu_selesai": "YYYY-MM-DDTHH:MM:SS",
                "alasan_waktu": "Berikan penjelasan taktis kenapa memilih jam/hari ini dengan gaya asisten pintar.",
                "deskripsi": "Catatan singkat untuk Google Calendar.",
                "penawaran_bantuan": "Tawarkan 1 bantuan spesifik teknis/materi jika relevan. Maks 1 kalimat.",
                "prompt_bantuan": "Instruksi rahasia buat dirimu sendiri jika user menerima bantuan. Kosongkan jika tidak ada."
            }}
            """
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt_ai
            )
            raw_json = response.text.strip().replace("```json", "").replace("```", "").strip()
            ai_data = json.loads(raw_json)
            
            event_data = {
                "nama_acara": ai_data.get('nama_acara', topik),
                "deskripsi": ai_data.get('deskripsi', ''),
                "waktu_mulai": ai_data.get('waktu_mulai'),
                "waktu_selesai": ai_data.get('waktu_selesai'),
                "alasan_waktu": ai_data.get('alasan_waktu'),
                "penawaran_bantuan": ai_data.get('penawaran_bantuan', ''),
                "prompt_bantuan": ai_data.get('prompt_bantuan', '')
            }
            pending_events[chat_id] = event_data
            tampilkan_konfirmasi(chat_id, bot_msg_id, event_data)
            
        except Exception as e:
            bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"❌ Gagal kalkulasi waktu otomatis: {str(e)}")

    elif data == "mode_manual":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(
            chat_id=chat_id, message_id=bot_msg_id,
            text="✍️ **Ketik kapan aktivitas ini akan dilaksanakan:**\n*(Contoh: 'besok jam 3 sore', 'nanti malam jam 8')*",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler_by_chat_id(chat_id, lambda m: proses_waktu_manual(m, bot_msg_id))

    # --- HANDLER EKSEKUSI KALENDER ---
    elif data == "confirm_yes":
        if chat_id in pending_events:
            bot.answer_callback_query(call.id, "Menyimpan ke kalender...")
            bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="⏳ *Mengirim data ke Google Calendar API...*")
            event_data = pending_events[chat_id]
            event_link = create_calendar_event(event_data)
            
            # Kembali memunculkan tombol menu setelah sukses
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🏠 Kembali ke Dasbor", callback_data="trigger_back_menu"))
            bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"✨ **JARVIS Core:** Tugas berhasil dialokasikan ke Google Calendar.\n🔗 [Buka Kalender]({event_link})", reply_markup=markup, parse_mode="Markdown")
            del pending_events[chat_id]
        else:
            bot.answer_callback_query(call.id, "⚠️ Sesi kedaluwarsa.")
            
    elif data == "confirm_help":
        if chat_id in pending_events:
            bot.answer_callback_query(call.id, "Memproses skenario bantuan...")
            event_data = pending_events.pop(chat_id) 
            bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="⏳ *Mengamankan slot waktu & memproses berkas bantuan...*")
            
            event_link = create_calendar_event(event_data)
            bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"✅ **Slot waktu diamankan!** 🔗 [Link Kalender]({event_link})\n\n🤖 *JARVIS sedang menulis dokumen yang kamu butuhkan...*", parse_mode="Markdown")
            
            prompt_rahasia = event_data.get('prompt_bantuan', '').strip()
            
            if prompt_rahasia:
                try:
                    bantuan_response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt_rahasia
                    )
                    hasil_bantuan = bantuan_response.text
                except Exception as e:
                    hasil_bantuan = f"Gagal mengeksekusi AI: {str(e)}"
            else:
                hasil_bantuan = "Skenario dieksekusi, namun tidak ada instruksi tambahan dari sistem."

            # Tombol kembali ke dasbor setelah bantuan dikirim
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🏠 Kembali ke Dasbor", callback_data="trigger_back_menu"))
            bot.send_message(chat_id, f"💡 **Hasil Eksekusi Otomatis:**\n\n{hasil_bantuan}", reply_markup=markup, parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "⚠️ Sesi kedaluwarsa.")

    elif data == "confirm_no":
        if chat_id in pending_events: del pending_events[chat_id]
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("🏠 Kembali ke Dasbor", callback_data="trigger_back_menu"))
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="❌ **Perintah dibatalkan oleh pengguna.**", reply_markup=markup, parse_mode="Markdown")

# ==========================================
# STEP 3: LOGIKA UTK MODE MANUAL
# ==========================================
def proses_waktu_manual(message, bot_msg_id):
    chat_id = message.chat.id
    if message.text.startswith('/'): return

    waktu_user = message.text
    topik = wizard_data[chat_id]['nama_acara']
    
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="⚡ *[■■■■■■□□□□] JARVIS sedang memproses format waktu...*", parse_mode="Markdown")
    
    wib = timezone(timedelta(hours=7))
    waktu_sekarang_str = datetime.now(wib).strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        prompt_ai = f"""
        Waktu saat ini: {waktu_sekarang_str} WIB.
        Konteks User: Mahasiswa Informatika ITERA, AI Engineer MBKM DBS Foundation. Proyek utama: SisaBisa (Two-Tower). Pacar: Hanifa. Rutinitas: Gym (PPL/Upper-Lower), Bug Hunting (Linux, Nuclei, Subfinder).
        
        Tugas: Ubah input waktu manual dari user menjadi format ISO kalender yang tepat.
        Nama Acara: '{topik}'
        Input Waktu User: '{waktu_user}'
        
        Keluarkan output DALAM FORMAT JSON MURNI (tanpa block markdown ```json):
        {{
            "nama_acara": "Judul acara yang dirapikan",
            "waktu_mulai": "YYYY-MM-DDTHH:MM:SS",
            "waktu_selesai": "YYYY-MM-DDTHH:MM:SS",
            "alasan_waktu": "",
            "deskripsi": "Catatan singkat untuk Google Calendar.",
            "penawaran_bantuan": "Tawarkan 1 bantuan spesifik teknis/materi jika relevan. Maks 1 kalimat.",
            "prompt_bantuan": "Instruksi rahasia buat dirimu sendiri jika user menerima bantuan. Kosongkan jika tidak ada."
        }}
        """
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_ai
        )
        raw_json = response.text.strip().replace("```json", "").replace("```", "").strip()
        ai_data = json.loads(raw_json)
        
        event_data = {
            "nama_acara": ai_data.get('nama_acara', topik),
            "deskripsi": ai_data.get('deskripsi', ''),
            "waktu_mulai": ai_data.get('waktu_mulai'),
            "waktu_selesai": ai_data.get('waktu_selesai'),
            "alasan_waktu": None,
            "penawaran_bantuan": ai_data.get('penawaran_bantuan', ''),
            "prompt_bantuan": ai_data.get('prompt_bantuan', '')
        }
        pending_events[chat_id] = event_data
        tampilkan_konfirmasi(chat_id, bot_msg_id, event_data)
        
    except Exception as e:
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"❌ Gagal memproses waktu manual: {str(e)}")

print("Mini JARVIS v2.8 (Interactive Dashboard) Aktif.")
bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)

print("Mini JARVIS v2.8 (Interactive Dashboard) Aktif.")
keep_alive() # <-- Trik server tipuan dinyalakan di sini
bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)

