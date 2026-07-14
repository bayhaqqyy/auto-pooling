# Bot Auto Polling Danantara

Script automation buat ngisi polling massal di web Danantara pake Python & Playwright. Udah *include* bypass Cloudflare, otomatis isi OTP (bisa narik langsung dari Gmail secara gaib), screenshot bukti, sama berjalan ngebut.

## Fitur
- **Email Generator (Baru!)**: Otomatis mengkalkulasi kemungkinan **Gmail Dot Trick** (seperti di mailmeteor) dari base email Anda. Menggunakan titik yang disisipkan tanpa batas variasi!
- **Full Auto Polling**: Ngeklik dari awal persetujuan, ngelewatin captcha, milih sektor, centang 3 faktor, sampe pilih institusi.
- **Auto-OTP via Gmail**: Bisa ngebaca inbox lu secara background dan masukin 4 digit kode OTP-nya sendiri tanpa perlu lu ngetik.
- **Auto Screenshot (Numbered)**: Kelar polling langsung di-screenshot pop-upnya (rapi) dan disimpen ke folder `bukti-polling/` dengan urutan nomor, misal: `screenshot_85.png`.

## Persiapan
Script ini butuh Python 3 sama browser Chrome bawaan Playwright.

1. Buka terminal di dalem folder script ini.
2. Setup virtual environment:
   ```bash
   python -m venv venv
   # Di Windows: .\venv\Scripts\activate
   # Di Mac/Linux: source venv/bin/activate
   ```
3. Install module yang dibutuhin:
   ```bash
   pip install playwright
   playwright install chromium
   ```

## Setup Auto-OTP (Wajib Kalo Mau Full Bengong)
Biar botnya bisa narik kode OTP langsung dari Gmail lu:
1. Buka file `config.json`.
2. Isi `"GMAIL_ADDRESS"` sama email utama lu (yang jadi base email).
3. Isi `"GMAIL_APP_PASSWORD"` pake **App Password** Google lu (bukan password biasa). 
   - **Langkah-langkah mendapatkan App Password Google:**
     1. Pastikan **Verifikasi 2 Langkah (2FA)** di akun Google lu udah nyala.
     2. Buka link ini di browser: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
     3. Kalo diminta login, login aja pake akun Gmail lu.
     4. Di kolom *App name*, ketik nama bebas (misal: `Bot Polling`).
     5. Klik tombol **Buat (Create)**.
     6. Google bakal nampilin kotak berisi **16 digit huruf unik** (biasanya warna kuning).
     7. Copy 16 huruf tersebut dan paste ke dalam file `config.json`.
   
> [!WARNING]
> **PENTING UNTUK CONFIG.JSON & OTP:**
> 1. File JSON **TIDAK MENDUKUNG** komentar. Jangan pernah taruh tanda `//` di dalam `config.json` karena akan bikin error tak terlihat (bot diam-diam gagal baca config).
> 2. Bot hanya mencari email dengan status **Belum Dibaca (UNSEEN)**. Jadi selama bot berjalan, **jangan membuka email OTP** di HP/Browser secara manual!

## Cara Pake

### 1. Generate Email Dot Trick
Jalanin script ini buat nyetak variasi titik di `email.txt`:
```bash
python generate_150_emails.py
```
*(Bisa cek dan ganti `BASE_EMAIL` di dalam scriptnya dulu sebelum di-run)*

### 2. Jalanin Bot
Kalo file `email.txt` udah ada isinya dan `config.json` udah disetting, gas jalanin:
```bash
python poll_danantara.py
```

### 3. Cara Kerja Bot
- Bot bakal ngebuka Chrome dan otomatis jalanin webnya.
- Pas nyampe di OTP, dia bakal **mantengin inbox Gmail lu (max 45 detik)**. Kalo kodenya masuk, dia tarik dan masukin sendiri.
- Kelar 1 email, bot bakal nunggu bentar (2-5 detik aja biar ngebut), lalu lanjut ke email berikutnya.

## Notes & TroubleShooting
- **OTP Gagal Ke-Tarik**: Kalo misal webnya ngelag atau telat ngirim email, bot bakal nyerah dan nanya di terminal. Lu tinggal klik tombol "Masukkan Kode" di browser secara manual, terus balik ke terminal dan **tekan tombol Enter (Kosong)**. Bot bakal nyoba narik emailnya lagi secara instan!
- **Lewati Email**: Kalo lu mau skip email yang nyangkut, ketik `skip` pas ditanya di terminal.
- **Minta Ulang**: Kalo mau minta kode ulang manual, ketik `baru` di terminal.
