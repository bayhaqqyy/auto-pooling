import imaplib
import email
import re
import time
import json
import os

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return None
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            # Hapus spasi pada app password jika ada
            if "GMAIL_APP_PASSWORD" in config:
                config["GMAIL_APP_PASSWORD"] = config["GMAIL_APP_PASSWORD"].replace(" ", "")
            return config
    except:
        return None

def get_latest_email_id():
    config = load_config()
    if not config or not config.get("GMAIL_ADDRESS") or not config.get("GMAIL_APP_PASSWORD"):
        return None
        
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(config["GMAIL_ADDRESS"], config["GMAIL_APP_PASSWORD"])
        mail.select("inbox")
        status, messages = mail.search(None, "ALL")
        if status == "OK" and messages[0]:
            latest_id = messages[0].split()[-1]
            mail.logout()
            return latest_id
        mail.logout()
    except Exception as e:
        print(f"Warning: Gagal ngecek email terakhir ({e})")
    return None

def fetch_new_otp(last_id, timeout=90):
    config = load_config()
    if not config:
        return None
        
    print("\n⏳ [Auto-OTP] Menunggu email OTP masuk ke Gmail...")
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(config["GMAIL_ADDRESS"], config["GMAIL_APP_PASSWORD"])
        mail.select("inbox")
    except Exception as e:
        print(f"❌ [Auto-OTP] Gagal login ke Gmail: {e}")
        return None
        
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        # Refresh mailbox state
        mail.select("inbox")
        
        # Cari email yang belum terbaca (UNSEEN)
        status, messages = mail.search(None, "UNSEEN")
        if status == "OK" and messages[0]:
            mail_ids = messages[0].split()
            
            for current_id in mail_ids:
                # Cek apakah ID ini lebih baru dari last_id (jika last_id ada)
                if last_id is not None and int(current_id) <= int(last_id):
                    continue
                    
                res, msg_data = mail.fetch(current_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                if part.get_content_type() in ["text/plain", "text/html"]:
                                    try:
                                        body += part.get_payload(decode=True).decode(errors='ignore')
                                    except:
                                        pass
                        else:
                            try:
                                body = msg.get_payload(decode=True).decode(errors='ignore')
                            except:
                                pass
                                
                        # Cari 4 digit angka di dalam body
                        matches = re.findall(r'\b\d{4}\b', body)
                        # Buang angka tahun biar ga salah tangkep
                        codes = [m for m in matches if m not in ["2023", "2024", "2025", "2026", "2027"]]
                        
                        if codes:
                            kode_otp = codes[0]
                            print(f"✅ [Auto-OTP] Berhasil mendapatkan kode: {kode_otp}")
                            mail.logout()
                            return kode_otp
                
                # Update last_id dengan id terbesar yang sudah dicek
                last_id = current_id
                
        time.sleep(1) # Cek setiap 1 detik biar ngebut
        
    print("❌ [Auto-OTP] Waktu tunggu habis (timeout). Tidak ada email OTP masuk.")
    mail.logout()
    return None
