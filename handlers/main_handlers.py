import json
from datetime import datetime, timedelta, timezone
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config.settings import Config
from utils.state import pending_events, wizard_data, temp_delete_events, chat_histories
from bot.keyboards.reply import menu_keyboard_permanen
from bot.core import bot, groq_client

# --- IMPOR DATABASE ---
from database.db import SessionLocal
from database.models import User
# ----------------------

def get_user_calendar_service(chat_id):
    """Membangun Google Calendar Service khusus untuk user tertentu berdasarkan OAuth Token di DB"""
    db = SessionLocal()
    user = db.query(User).filter(User.chat_id == chat_id).first()
    db.close()
    
    if not user or not user.google_oauth_token:
        return None
        
    try:
        token_data = json.loads(user.google_oauth_token)
        creds = Credentials(**token_data)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        print(f"❌ Gagal memuat token Google untuk user {chat_id}: {e}")
        return None

# ==========================================
# 1. HANDLER MENU BAWAH & START (GERBANG REGISTRASI)
# ==========================================
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    chat_id = message.chat.id
    db = SessionLocal()
    
    # 1. Cari user di database
    user = db.query(User).filter(User.chat_id == chat_id).first()
    
    # 2. Jika user belum ada sama sekali, buatkan datanya
    if not user:
        user = User(chat_id=chat_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    # 3. Cek apakah user sudah menaruh API Key Groq-nya
    if not user.ai_api_key:
        pesan = (
            "👋 **Halo! Selamat Datang di Sandi Assistan v3.1** ⚡\n\n"
            "Saya melihat kamu adalah pengguna baru. Untuk mulai menggunakan otak AI saya secara personal, "
            "kamu perlu menautkan **API Key Groq** milikmu sendiri (gratis).\n\n"
            "🔑 **Silakan balas pesan ini dengan menempelkan (paste) API Key Groq kamu:**\n\n"
            "*(Ketik /batal jika ingin membatalkan)*"
        )
        msg = bot.send_message(chat_id, pesan, parse_mode="Markdown")
        bot.register_next_step_handler(msg, proses_simpan_api_key)
        db.close()
        return
        
    db.close() # Tutup koneksi database jika tidak dipakai lagi

    # 4. JIKA SUDAH PUNYA API KEY, TAMPILKAN BUKU PANDUAN
    pesan = (
        "🤖 **Selamat Datang kembali di Sandi Assistan v3.1** ⚡\n\n"
        "Saya adalah Asisten AI Cerdas yang dirancang khusus untuk membantumu mengatur jadwal, memikirkan ide, dan menjaga produktivitasmu tetap maksimal.\n\n"
        "📖 **PANDUAN PENGGUNAAN CEPAT:**\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "1️⃣ **🗓️ Buat Jadwal:** Ketik ide acaramu, dan biarkan otak AI saya memikirkan alokasi waktu terbaik untukmu (atau kamu bisa tentukan sendiri).\n"
        "2️⃣ **📋 Agenda Hari Ini:** Tarik jadwalmu langsung dari Google Calendar agar kamu tahu apa fokusmu hari ini.\n"
        "3️⃣ **⚙️ Hapus Jadwal:** Batalkan agenda yang tidak jadi kamu ikuti dengan cepat.\n"
        "4️⃣ **💬 Tanya JARVIS:** Butuh teman *brainstorming*, mencari *bug* kode, atau sekadar bertanya? Diskusikan di sini, lalu jadwalkan hasil diskusinya menjadi aksi nyata!\n\n"
        "💡 *Tips: Gunakan panel menu di bawah layar untuk mulai memberikan perintah kepada saya.*"
    )
    bot.send_message(message.chat.id, pesan, reply_markup=menu_keyboard_permanen(), parse_mode="Markdown")

def proses_simpan_api_key(message):
    chat_id = message.chat.id
    api_key = message.text.strip()
    
    if api_key == '/batal':
        bot.send_message(chat_id, "❌ **Registrasi dibatalkan.** Ketik /start untuk mencoba lagi.", parse_mode="Markdown")
        return
        
    if len(api_key) < 20:
        msg = bot.send_message(chat_id, "❌ **API Key tidak valid.** Sepertinya itu bukan kunci yang benar.\n\nSilakan kirimkan ulang API Key Groq milikmu:", parse_mode="Markdown")
        bot.register_next_step_handler(msg, proses_simpan_api_key)
        return
        
    db = SessionLocal()
    user = db.query(User).filter(User.chat_id == chat_id).first()
    if user:
        user.ai_api_key = api_key
        db.commit()
    db.close()
    
    bot.send_message(chat_id, "✅ **API Key berhasil diamankan ke dalam Database!** 🔒\n\nSekarang ketik /start sekali lagi untuk menyalakan mesin utama JARVIS.", parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text in ["🗓️ Buat Jadwal", "📋 Agenda Hari Ini", "⚙️ Hapus Jadwal", "💬 Tanya JARVIS"])
def handle_menu_bawah(message):
    chat_id = message.chat.id
    teks = message.text

    if teks == "🗓️ Buat Jadwal":
        pesan = "🤖 **Mode Penjadwalan Aktif.**\n\nKetik ide/judul aktivitas yang ingin dijadwalkan:"
        msg = bot.send_message(chat_id, pesan, parse_mode="Markdown")
        bot.register_next_step_handler(msg, lambda m: proses_judul(m, msg.message_id))
        
    elif teks == "📋 Agenda Hari Ini":
        # Cek apakah user sudah menghubungkan Google Calendar lewat OAuth
        service = get_user_calendar_service(chat_id)
        if not service:
            auth_url = (
                f"https://accounts.google.com/o/oauth2/auth?"
                f"client_id={Config.GOOGLE_CLIENT_ID}&"
                f"redirect_uri={Config.GOOGLE_REDIRECT_URI}&"
                f"response_type=code&"
                f"scope=https://www.googleapis.com/auth/calendar&"
                f"access_type=offline&prompt=consent&"
                f"state={chat_id}"
            )
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🔗 Login dengan Google", url=auth_url))
            bot.send_message(
                chat_id, 
                "🔒 **Akses Kalender Belum Ditautkan!**\n\n"
                "Untuk menjaga privasi dan melihat agenda pribadimu, silakan hubungkan akun Google Calendar milikmu melalui tombol di bawah:",
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return

        bot.send_message(chat_id, "⏳ *Menarik data dari Google Calendar...*", parse_mode="Markdown")
        tampilkan_agenda_hari_ini(chat_id, service)
        
    elif teks == "⚙️ Hapus Jadwal":
        service = get_user_calendar_service(chat_id)
        if not service:
            bot.send_message(chat_id, "❌ Silakan hubungkan Google Calendar terlebih dahulu melalui menu **📋 Agenda Hari Ini**.", parse_mode="Markdown")
            return
            
        bot.send_message(chat_id, "⏳ *Memindai jadwal mendatang...*", parse_mode="Markdown")
        tampilkan_menu_hapus(chat_id, service)
        
    elif teks == "💬 Tanya JARVIS":
        pesan = "🧠 **Mode Diskusi Terbuka.**\n\nAda masalah teknis, *bug*, atau butuh teman *brainstorming*? Ketik pertanyaanmu di bawah:"
        msg = bot.send_message(chat_id, pesan, parse_mode="Markdown")
        bot.register_next_step_handler(msg, proses_tanya_jarvis)

# ==========================================
# 2. FUNGSI LOGIKA FITUR
# ==========================================
def tampilkan_agenda_hari_ini(chat_id, service):
    wib = timezone(timedelta(hours=7))
    now = datetime.now(wib)
    awal_hari = now.replace(hour=0, minute=0, second=0).isoformat()
    akhir_hari = now.replace(hour=23, minute=59, second=59).isoformat()
    
    try:
        events_result = service.events().list(
            calendarId='primary', timeMin=awal_hari, timeMax=akhir_hari,
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

def tampilkan_menu_hapus(chat_id, service):
    wib = timezone(timedelta(hours=7))
    now = datetime.now(wib).isoformat()
    
    try:
        events_result = service.events().list(
            calendarId='primary', timeMin=now, maxResults=5,
            singleEvents=True, orderBy='startTime'
        ).execute()
        events = events_result.get('items', [])
        
        if not events:
            bot.send_message(chat_id, "🟢 **Bersih.** Tidak ada jadwal mendatang untuk dihapus.", parse_mode="Markdown")
            return
            
        temp_delete_events[chat_id] = {}
        markup = InlineKeyboardMarkup(row_width=1)
        
        for idx, event in enumerate(events):
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
        if chat_id not in chat_histories:
            chat_histories[chat_id] = [{"role": "system", "content": "Konteks: Kamu adalah Mini JARVIS, AI Assistant untuk seorang AI Engineer MBKM & Mahasiswa Informatika. Jawablah dengan ringkas, teknis, dan *straight to the point*."}]
            
        chat_histories[chat_id].append({"role": "user", "content": message.text})
        
        if len(chat_histories[chat_id]) > 11:
            chat_histories[chat_id] = [chat_histories[chat_id][0]] + chat_histories[chat_id][-10:]
            
        completion = groq_client.chat.completions.create(
            messages=chat_histories[chat_id], 
            model="llama-3.3-70b-versatile",
            temperature=0.7,
        )
        balasan_ai = completion.choices[0].message.content
        
        chat_histories[chat_id].append({"role": "assistant", "content": balasan_ai})
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🗓️ Jadwalkan Hasil Diskusi Ini", callback_data="jadwalkan_diskusi"),
            InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="kembali_menu")
        )
        
        try:
            bot.reply_to(message, balasan_ai, reply_markup=markup, parse_mode="Markdown")
        except telebot.apihelper.ApiTelegramException:
            bot.reply_to(message, balasan_ai, reply_markup=markup)
            
    except Exception as e:
        bot.reply_to(message, f"❌ Gagal memproses AI: {e}")

def create_calendar_event(chat_id, jadwal):
    service = get_user_calendar_service(chat_id)
    if not service:
        raise Exception("Google Calendar belum ditautkan.")
        
    event = {
        'summary': jadwal.get('nama_acara', 'Jadwal Baru'),
        'description': jadwal.get('deskripsi', ''),
        'start': {'dateTime': jadwal['waktu_mulai'], 'timeZone': 'Asia/Jakarta'},
        'end': {'dateTime': jadwal['waktu_selesai'], 'timeZone': 'Asia/Jakarta'},
    }
    event_result = service.events().insert(calendarId='primary', body=event).execute()
    return event_result.get('htmlLink')

def tampilkan_konfirmasi(chat_id, bot_msg_id, event_data):
    pesan_konfirmasi = f"🧠 **JARVIS Intelligence Report**\n\n"
    for i, jadwal in enumerate(event_data.get('daftar_jadwal', [])):
        waktu_mulai = jadwal['waktu_mulai'].replace('T', ' ')[:16]
        waktu_selesai = jadwal['waktu_selesai'].split('T')[1][:5] if 'T' in jadwal['waktu_selesai'] else ""
        pesan_konfirmasi += f"📌 **{i+1}. {jadwal['nama_acara']}**\n🟢 {waktu_mulai} - {waktu_selesai} WIB\n\n"
        
    if event_data.get("alasan_waktu"):
        pesan_konfirmasi += f"📋 **Analisis:** {event_data['alasan_waktu']}\n\n"
        
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

# ==========================================
# 3. CALLBACK HANDLER (Tombol Inline)
# ==========================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    chat_id = call.message.chat.id
    data = call.data
    bot_msg_id = call.message.message_id

    if data == "kembali_menu":
        bot.answer_callback_query(call.id)
        try: bot.delete_message(chat_id, bot_msg_id) 
        except: pass
        send_welcome(call.message) 
        return

    if data == "jadwalkan_diskusi":
        bot.answer_callback_query(call.id)
        teks_diskusi = call.message.text
        wizard_data[chat_id] = {'nama_acara': "Eksekusi Agenda Diskusi", 'konteks_diskusi': teks_diskusi, 'bot_msg_id': bot_msg_id}
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🤖 Biarkan JARVIS Ekstrak & Atur Waktu", callback_data="mode_auto"),
            InlineKeyboardButton("✍️ Saya Ingin Tentukan Waktu Sendiri", callback_data="mode_manual"),
            InlineKeyboardButton("🏠 Batal & Kembali", callback_data="kembali_menu")
        )
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="🗓️ **Sistem Penjadwalan Cepat Aktif**\n\nBagaimana kamu ingin menentukan waktu pelaksanaannya?", reply_markup=markup, parse_mode="Markdown")
        return

    if data.startswith("del_"):
        idx_event = data.split("_")[1]
        markup_kembali = InlineKeyboardMarkup().add(InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="kembali_menu"))
        if chat_id in temp_delete_events and idx_event in temp_delete_events[chat_id]:
            real_event_id = temp_delete_events[chat_id][idx_event]
            bot.answer_callback_query(call.id, "Menghapus jadwal...")
            try:
                service = get_user_calendar_service(chat_id)
                if not service: raise Exception("Autentikasi kalender terputus.")
                service.events().delete(calendarId='primary', eventId=real_event_id).execute()
                bot.edit_message_text("✅ **Jadwal telah dihapus.**", chat_id=chat_id, message_id=bot_msg_id, reply_markup=markup_kembali, parse_mode="Markdown")
            except Exception as e:
                bot.edit_message_text(f"❌ Gagal menghapus: {e}", chat_id=chat_id, message_id=bot_msg_id, reply_markup=markup_kembali)
        return

    if data == "mode_auto":
        bot.answer_callback_query(call.id, "Menganalisis opsi waktu terbaik...")
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="⚡ *JARVIS sedang menghitung ritme produktivitas...*", parse_mode="Markdown")
        
        topik = wizard_data[chat_id]['nama_acara']
        konteks = wizard_data[chat_id].get('konteks_diskusi', '')
        info_tambahan = f"\nKonteks Aktivitas: {konteks}" if konteks else ""
        
        wib = timezone(timedelta(hours=7))
        waktu_sekarang_str = datetime.now(wib).strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            prompt_ai = f"""
            Waktu saat ini: {waktu_sekarang_str} WIB.
            Konteks User: Mahasiswa Informatika, AI Engineer MBKM. 
            Tugas: Buat jadwal terpisah untuk: '{topik}' {info_tambahan}
            Keluarkan output JSON MURNI:
            {{
                "daftar_jadwal": [{{"nama_acara": "Acara", "waktu_mulai": "YYYY-MM-DDTHH:MM:SS", "waktu_selesai": "YYYY-MM-DDTHH:MM:SS", "deskripsi": "Ket"}}],
                "alasan_waktu": "Alasan",
                "penawaran_bantuan": "",
                "prompt_bantuan": ""
            }}
            """
            completion = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt_ai}],
                model="llama-3.3-70b-versatile",
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            raw_content = completion.choices[0].message.content.strip()
            simbol_kode = "`" * 3
            ai_data = json.loads(raw_content.replace(simbol_kode + "json", "").replace(simbol_kode, "").strip())
            
            pending_events[chat_id] = {
                "daftar_jadwal": ai_data.get('daftar_jadwal', []),
                "alasan_waktu": ai_data.get('alasan_waktu'),
                "penawaran_bantuan": ai_data.get('penawaran_bantuan', ''),
                "prompt_bantuan": ai_data.get('prompt_bantuan', '')
            }
            tampilkan_konfirmasi(chat_id, bot_msg_id, pending_events[chat_id])
        except Exception as e:
            markup_kembali = InlineKeyboardMarkup().add(InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="kembali_menu"))
            bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"❌ Gagal kalkulasi: {str(e)}", reply_markup=markup_kembali)

    elif data == "mode_manual":
        bot.answer_callback_query(call.id)
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="✍️ **Ketik kapan aktivitas ini akan dilaksanakan:**", parse_mode="Markdown")
        bot.register_next_step_handler_by_chat_id(chat_id, lambda m: proses_waktu_manual(m, bot_msg_id))

    elif data == "confirm_yes":
        markup_kembali = InlineKeyboardMarkup().add(InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="kembali_menu"))
        if chat_id in pending_events:
            bot.answer_callback_query(call.id, "Menyimpan ke kalender...")
            bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="⏳ *Mengirim data ke Google Calendar...*", parse_mode="Markdown")
            
            try:
                event_data = pending_events[chat_id]
                links = [f"[{j['nama_acara']}]({create_calendar_event(chat_id, j)})" for j in event_data.get('daftar_jadwal', [])]
                teks_link = "\n".join(f"🔗 {l}" for l in links)
                
                bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"✨ **JARVIS Core:** Semua tugas berhasil dialokasikan!\n\n{teks_link}", reply_markup=markup_kembali, parse_mode="Markdown", disable_web_page_preview=True)
                del pending_events[chat_id]
            except Exception as e:
                bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"❌ Gagal menyimpan ke kalender: {e}", reply_markup=markup_kembali)

    elif data == "confirm_help":
        markup_kembali = InlineKeyboardMarkup().add(InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="kembali_menu"))
        if chat_id in pending_events:
            event_data = pending_events.pop(chat_id) 
            bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="⏳ *Mengamankan slot waktu & memproses bantuan...*", parse_mode="Markdown")
            try:
                links = [f"[{j['nama_acara']}]({create_calendar_event(chat_id, j)})" for j in event_data.get('daftar_jadwal', [])]
                teks_link = "\n".join(f"🔗 {l}" for l in links)
                bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"✅ **Slot diamankan!**\n{teks_link}\n\n🤖 *Menulis dokumen...*", parse_mode="Markdown", disable_web_page_preview=True)
                
                prompt_rahasia = event_data.get('prompt_bantuan', '').strip()
                if prompt_rahasia:
                    hasil_bantuan = groq_client.chat.completions.create(
                        messages=[{"role": "system", "content": "Kamu adalah JARVIS."}, {"role": "user", "content": prompt_rahasia}],
                        model="llama-3.3-70b-versatile", temperature=0.7
                    ).choices[0].message.content
                else:
                    hasil_bantuan = "Skenario dieksekusi."

                bot.send_message(chat_id, f"💡 **Hasil:**\n\n{hasil_bantuan}", reply_markup=markup_kembali, parse_mode="Markdown")
            except Exception as e:
                bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"❌ Gagal: {str(e)}", reply_markup=markup_kembali)

    elif data == "confirm_no":
        markup_kembali = InlineKeyboardMarkup().add(InlineKeyboardButton("🏠 Kembali ke Menu Utama", callback_data="kembali_menu"))
        if chat_id in pending_events: del pending_events[chat_id]
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="❌ **Dibatalkan.**", reply_markup=markup_kembali, parse_mode="Markdown")

def proses_waktu_manual(message, bot_msg_id):
    chat_id = message.chat.id
    if message.text.startswith('/'): return
    topik = wizard_data[chat_id]['nama_acara']
    
    try: bot.delete_message(chat_id, message.message_id)
    except: pass
    
    bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text="⚡ *JARVIS memproses format waktu...*", parse_mode="Markdown")
    
    try:
        prompt_ai = f"""Waktu: {datetime.now(timezone(timedelta(hours=7))).strftime("%Y-%m-%d %H:%M:%S")}. Formatkan acara '{topik}' pada '{message.text}' ke JSON: {{"daftar_jadwal": [{{"nama_acara": "Acara", "waktu_mulai": "YYYY-MM-DDTHH:MM:SS", "waktu_selesai": "YYYY-MM-DDTHH:MM:SS", "deskripsi": ""}}]}}"""
        completion = groq_client.chat.completions.create(messages=[{"role": "user", "content": prompt_ai}], model="llama-3.3-70b-versatile", temperature=0.2, response_format={"type": "json_object"})
        simbol_kode = "`" * 3
        ai_data = json.loads(completion.choices[0].message.content.strip().replace(simbol_kode + "json", "").replace(simbol_kode, "").strip())
        
        pending_events[chat_id] = {"daftar_jadwal": ai_data.get('daftar_jadwal', []), "alasan_waktu": None, "penawaran_bantuan": "", "prompt_bantuan": ""}
        tampilkan_konfirmasi(chat_id, bot_msg_id, pending_events[chat_id])
    except Exception as e:
        markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🏠 Kembali", callback_data="kembali_menu"))
        bot.edit_message_text(chat_id=chat_id, message_id=bot_msg_id, text=f"❌ Gagal: {str(e)}", reply_markup=markup)