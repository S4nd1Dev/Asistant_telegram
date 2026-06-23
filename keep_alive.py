import os
from flask import Flask
from threading import Thread
import logging

# Matikan log bawaan Flask agar terminal rapi
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask('')

@app.route('/')
def home():
    return "JARVIS Web Server is Online!"

def run():
    # Mengambil port dinamis dari Render, atau pakai 10000 sebagai cadangan
    port = int(os.environ.get('PORT', 10000))
    print(f"🌍 Membuka jalur Web Service di Port: {port}", flush=True)
    # use_reloader=False sangat penting agar tidak bentrok dengan multi-threading
    app.run(host='0.0.0.0', port=port, use_reloader=False)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True # Memastikan server tipuan mati otomatis jika bot utama mati
    t.start()