import os
import json
import threading
from datetime import datetime, timedelta, timezone
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from google import genai
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from keep_alive import app

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
temp_delete_events = {} # Menyimpan ID event sementara untuk fitur hapus

# ==========================================
# 3. FUNGSI MENU PERMANEN (REPLY KEYBOARD)
# ==========================================
def menu_keyboard_permanen():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("🗓️ Buat Jadwal"), 
        KeyboardButton("📋 Agenda Hari Ini")
    )
    markup.add(
        KeyboardButton("⚙️ Hapus Jadwal"), 
        KeyboardButton("💬 Tanya JARVIS")
    )
    return markup

@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    pesan = (
        "🤖 **MINI JARVIS v3.0 - Command Center** ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "Sistem utama *online*. Modul AI dan kalender tersinkronisasi.\n\n"
        "Gunakan panel menu di bawah layar untuk navigasi cepat."
    )
    bot.send_message(message.chat.id, pesan, reply_markup=menu_keyboard_permanen(), parse_mode="Markdown")

# ==========================================
# 4. HANDLER MENU BAWAH LAYAR
# ==========================================
@bot.message_handler(func=lambda message: message.text in ["🗓️ Buat Jadwal", "📋 Agenda Hari Ini", "⚙️ Hapus Jadwal", "💬 Tanya JARVIS"])
def handle_menu_bawah(message):
    chat_id = message.chat.id
    teks = message.text

    if teks == "🗓️ Buat Jadwal":
        pesan = "🤖 **Mode Penjadwalan Aktif.**\n\nKetik ide/judul aktivitas yang ingin dijadwalkan:"
        msg = bot.send_message(chat_id, pesan, parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m: proses_judul(m, msg.message_id))
        
    elif teks == "📋 Agenda Hari Ini":
        bot.send_message(chat_id, "⏳ *Menarik data dari Google Calendar...*", parse_mode="Markdown")
        tampilkan_agenda_hari_ini(chat_id)
        
    elif teks == "⚙️ Hapus Jadwal":
        bot.send_message(chat_id, "⏳ *Memindai jadwal mendatang...*", parse_mode="Markdown")
        tampilkan_menu_hapus(chat_id)
        
    elif teks == "💬 Tanya JARVIS":
        pesan = "🧠 **Mode Diskusi Terbuka.**\n\nAda masalah teknis, *bug*, atau butuh teman *brainstorming*? Ketik pertanyaanmu di bawah:"
        msg = bot.send_message(chat_id, pesan, parse_mode="Markdown")
        bot.register_next_step_handler(msg, proses_tanya_jarvis)

# ==========================================
# 5. LOGIKA FITUR BARU: LIHAT, HAPUS & TANYA
# ==========================================
def tampilkan_agenda_hari_ini(chat_id):
    wib = timezone(timedelta(hours=7))
    now = datetime.now(wib)
    awal_hari = now.replace(hour=0, minute=0, second=0).isoformat()
    akhir_hari = now.replace(hour=23, minute=59, second=59).isoformat()
    
    try:
        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID, timeMin=awal_hari, timeMax=akhir_hari,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        if not events:
            bot.send_message(chat_id, "🟢 **Kalender Kosong.** Tidak ada agenda terjadwal hari ini.", parse_mode="Markdown")
            return
            
        pesan = "📋 **AGENDA HARI INI:**\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for event in events:
            waktu_mulai = event['start'].get('dateTime', event['start'].get('date'))
            jam_mulai = waktu_mulai.split('T')[1][:5] if 'T' in waktu_mulai else "Seharian"
            pesan += f"🔹 **{jam_mulai}** - {event['summary']}\n"
            
        bot.send_message(chat_id, pesan, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Gagal mengambil jadwal: {e}")

def tampilkan_menu_hapus(chat_id):
    wib = timezone(timedelta(hours=7))
    now = datetime.now(wib).isoformat()
    
    try:
        # Mengambil 5 jadwal terdekat mulai dari sekarang
        events_result = calendar_service.events().list(
            calendarId=CALENDAR_ID, timeMin=now, maxResults=5,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        if not events:
            bot.send_message(chat_id, "🟢 **Bersih.** Tidak ada jadwal mendatang untuk dihapus.", parse_mode="Markdown")
            return
            
        temp_delete_events[chat_id] = {}
        markup = InlineKeyboardMarkup(row_width=1)
        
        for idx, event in enumerate(events):
            # Memetakan ID event asli Google ke ID pendek untuk tombol Telegram
            temp_delete_events[chat_id][str(idx)] = event['id']
            waktu = event['start'].get('dateTime', event['start'].get('date'))
            jam_tgl = waktu.replace('T', ' ')[:16] if 'T' in waktu else waktu
            judul = f"❌ {jam_tgl} | {event['summary']}"
            markup.add(InlineKeyboardButton(judul, callback_data=f"del_{idx}"))
            
        bot.send_message(chat_id, "⚠️ **Pilih jadwal yang ingin dihapus permanen:**", reply_markup=markup, parse_mode="Markdown")
    except Exception as e:
        bot.send_message(chat_id, f"❌ Gagal mengambil daftar hapus: {e}")

def proses_tanya_jarvis(message):
    chat_id = message.chat.id
    if message.text.startswith('/'): return
    
    bot.send_chat_action(chat_id, 'typing')
    try:
        prompt_system = (
            "Konteks: Kamu adalah Mini JARVIS, AI Assistant untuk seorang AI Engineer MBKM & Mahasiswa Informatika. "
            "Jawablah dengan ringkas, teknis, dan *straight to the point*. "
            f"Pertanyaan User: {message.text}"
        )
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_system
        )
        bot.reply_to(message, response.text, parse_mode="Markdown")
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal memproses AI: {e}")

# ==========================================
# 6. LOGIKA BUAT JADWAL & CALLBACK LAMA
# ==========================================
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
    bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=pesan_konfirmasi, reply_markup=markup, parse_mode="Markdown")

def proses_judul(message, bot_msg_id):
    chat_id = message.chat.id
    if message.text.startswith('/'): return

    wizard_data[chat_id] = {'nama_acara': message.text, 'bot_msg_id': bot_msg_id}
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

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    data = call.data
    bot_msg_id = call.message.message_id

    # --- HANDLER HAPUS JADWAL ---
    if data.startswith("del_"):
        idx_event = data.split("_")[1]
        if chat_id in temp_delete_events and idx_event in temp_delete_events[chat_id]:
            real_event_id = temp_delete_events[chat_id][idx_event]
            bot.answer_callback_query(call.id, "Menghapus jadwal...")
            try:
                calendar_service.events().delete(calendarId=CALENDAR_ID, eventId=real_event_id).execute()
                bot.edit_message_text("✅ **Jadwal telah dihanguskan dari Google Calendar.**", chat_id=chat_id, message_id=bot_msg_id, parse_mode="Markdown")
            except Exception as e:
                bot.edit_message_text(f"❌ Gagal menghapus: {e}", chat_id=chat_id, message_id=bot_msg_id)
        else:
            bot.answer_callback_query(call.id, "⚠️ Sesi kedaluwarsa.")
        return

    # --- MODE AUTO & MANUAL ---
    if data == "mode_auto":
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
                "alasan_waktu": "Berikan penjelasan taktis.",
                "deskripsi": "Catatan singkat untuk Google Calendar.",
                "penawaran_bantuan": "Tawarkan 1 bantuan spesifik teknis/materi jika relevan. Maks 1 kalimat.",
                "prompt_bantuan": "Instruksi rahasia buat dirimu sendiri jika user menerima bantuan. Kosongkan jika tidak ada."
            }}
            """
            response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_ai)
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
            
            bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"✨ **JARVIS Core:** Tugas berhasil dialokasikan ke Google Calendar.\n🔗 [Buka Kalender]({event_link})", parse_mode="Markdown")
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
                    bantuan_response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_rahasia)
                    hasil_bantuan = bantuan_response.text
                except Exception as e:
                    hasil_bantuan = f"Gagal mengeksekusi AI: {str(e)}"
            else:
                hasil_bantuan = "Skenario dieksekusi, namun tidak ada instruksi tambahan dari sistem."

            bot.send_message(chat_id, f"💡 **Hasil Eksekusi Otomatis:**\n\n{hasil_bantuan}", parse_mode="Markdown")
        else:
            bot.answer_callback_query(call.id, "⚠️ Sesi kedaluwarsa.")

    elif data == "confirm_no":
        if chat_id in pending_events: del pending_events[chat_id]
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="❌ **Perintah dibatalkan oleh pengguna.**", parse_mode="Markdown")

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
        Tugas: Ubah input waktu manual dari user menjadi format ISO kalender yang tepat.
        Nama Acara: '{topik}'
        Input Waktu User: '{waktu_user}'
        
        Keluarkan output DALAM FORMAT JSON MURNI (tanpa block markdown ```json):
        {{
            "nama_acara": "Judul acara yang dirapikan",
            "waktu_mulai": "YYYY-MM-DDTHH:MM:SS",
            "waktu_selesai": "YYYY-MM-DDTHH:MM:SS",
            "alasan_waktu": "",
            "deskripsi": "Catatan singkat.",
            "penawaran_bantuan": "",
            "prompt_bantuan": ""
        }}
        """
        response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt_ai)
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

# ==========================================
# EKSEKUSI UTAMA (RENDER BULLETPROOF MODE)
# ==========================================
print("Mini JARVIS v3.0 (The App Dashboard) Aktif.", flush=True)

# 1. Nyalakan Telegram Bot di Background Thread
def jalankan_bot():
    print("🤖 Memulai proses bot Telegram di latar belakang...", flush=True)
    bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)

bot_thread = threading.Thread(target=jalankan_bot)
bot_thread.daemon = True
bot_thread.start()

# 2. Nyalakan Web Server di Main Thread agar Render mendeteksinya
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    print(f"🌍 Membuka Web Service di Port {port} (Main Thread)...", flush=True)
    app.run(host="0.0.0.0", port=port, use_reloader=False)