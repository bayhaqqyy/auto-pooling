# Bot Auto Polling Danantara

Script automation buat ngisi polling massal di web Danantara pakai Python & Playwright, lengkap dengan OTP Gmail, screenshot bukti, auto-submit Google Form, dan orchestrator buat jalan terus otomatis.

## Gambaran Alur

Alur kerjanya sekarang begini:

1. `poll_danantara.py` menjalankan polling dari daftar email di `email.txt`
2. hasil sukses disimpan jadi screenshot di folder `bukti-polling/`
3. `orchestrator_5000.py` memantau screenshot yang belum terkirim
4. kalau pending screenshot **>= 50**, orchestrator otomatis menjalankan `submit_gform.py`
5. `submit_gform.py` upload bukti ke Google Form
6. file yang sudah terkirim dicatat di `submitted_gform.json`
7. malam hari cron akan stop, submit sisa bukti, lalu housekeeping

---

## File yang Wajib Dipahami

### 1. `config.json`
Ini file identitas utama untuk form dan OTP Gmail.

Yang wajib diisi / dicek:
- `GMAIL_ADDRESS` → email Gmail utama untuk baca OTP
- `GMAIL_APP_PASSWORD` → App Password Gmail, **bukan password login biasa**
- `FORM_NAMA` → nama yang diisi ke form
- `FORM_NIK` → NIK / ID yang diisi ke form

Contoh isi:
```json
{
  "GMAIL_ADDRESS": "emailkamu@gmail.com",
  "GMAIL_APP_PASSWORD": "xxxx xxxx xxxx xxxx",
  "FORM_NAMA": "Nama Kamu",
  "FORM_NIK": "IDKAMU"
}
```

### 2. `.env`
Ini dipakai untuk login inbox email tambahan / akun email polling.

Yang wajib diisi:
```env
email=alamat_email_login
password=password_email_login
```

### 3. `email_master_5000.txt`
Ini bank email sumber besar. Biasanya dipakai sebagai master list.

### 4. `email.txt`
Ini daftar email aktif yang akan diproses oleh bot saat ini.

Artinya:
- `email_master_5000.txt` = sumber besar
- `email.txt` = batch aktif yang sedang dipakai bot

### 5. `bukti-polling/`
Semua screenshot hasil polling sukses akan masuk ke sini.

### 6. `submitted_gform.json`
Dipakai untuk menandai screenshot mana yang **sudah berhasil dikirim** ke Google Form.

Kalau file ini belum ada, biasanya akan dibuat otomatis saat submit pertama.

### 7. `orchestrator_5000.py`
Script utama buat mode jalan otomatis.

Fungsinya:
- jalanin polling batch
- cek backlog screenshot pending
- trigger submit otomatis kalau pending >= 50
- lanjut loop terus

### 8. `submit_gform.py`
Script khusus untuk upload screenshot ke Google Form.

Konfigurasi aktif sekarang:
- maksimal **50 file per submit**
- slot upload dibagi: `1-10`, `11-20`, `21-30`, `31-40`, `41-50`
- timeout submit: **300 detik / 5 menit**

---

## Yang Harus Diganti Saat Baru Pakai Script

Kalau baru mau pakai folder script ini, minimal cek dan sesuaikan ini dulu:

### Wajib diganti
- [ ] `config.json`
  - `GMAIL_ADDRESS`
  - `GMAIL_APP_PASSWORD`
  - `FORM_NAMA`
  - `FORM_NIK`
- [ ] `.env`
  - `email`
  - `password`
- [ ] `email.txt`
  - isi daftar email batch aktif

### Wajib dicek
- [ ] `email_master_5000.txt` tersedia dan sesuai sumber email
- [ ] folder `bukti-polling/` ada
- [ ] virtualenv `.venv/` tersedia
- [ ] Chromium / Playwright sudah terpasang di environment folder ini

---

## Step by Step Pemakaian dari Nol

## Step 1 — Masuk ke folder script
Contoh:
```bash
cd /home/rafli/auto-pooling
```

## Step 2 — Isi `config.json`
Edit file `config.json`, lalu isi:
- Gmail utama untuk OTP
- App Password Gmail
- Nama form
- NIK / ID form

## Step 3 — Isi `.env`
Edit file `.env`, lalu isi akun email login:
```env
email=...
password=...
```

## Step 4 — Siapkan daftar email di `email.txt`
Kalau mau ambil dari master, bisa isi batch aktif ke `email.txt`.

Contoh konsep:
- `email_master_5000.txt` = semua email
- `email.txt` = bagian yang sedang dipakai sekarang

## Step 5 — Pastikan environment Python siap
Minimal harus ada:
- `.venv`
- module Playwright
- browser Chromium Playwright

Kalau setup baru, biasanya konsepnya:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

> Kalau folder ini sudah jadi dan tinggal pakai, biasanya tidak perlu install ulang.

## Step 6 — Jalankan manual polling saja kalau mau tes
Kalau mau tes polling manual tanpa orchestrator:
```bash
.venv/bin/python3 poll_danantara.py
```

## Step 7 — Jalankan auto-submit manual kalau diperlukan
Kalau screenshot sudah banyak dan mau submit manual:
```bash
xvfb-run -a .venv/bin/python3 submit_gform.py
```

## Step 8 — Jalankan mode otomatis penuh
Kalau mau mode otomatis penuh, jalankan orchestrator:
```bash
.venv/bin/python3 orchestrator_5000.py
```

Orchestrator akan:
- jalanin polling
- hitung pending screenshot
- submit otomatis kalau pending >= 50
- loop terus

---

## Aturan Operasional yang Berlaku Sekarang

### Auto-submit trigger
Trigger aktif sekarang:
- **`SUBMIT_TRIGGER = 50`**

Artinya kalau ada **50 atau lebih** screenshot yang belum terkirim, orchestrator akan mencoba menjalankan `submit_gform.py`.

### Batas submit Google Form
- maksimal **50 screenshot per form submit**
- pembagian slot upload tetap:
  - `1-10`
  - `11-20`
  - `21-30`
  - `31-40`
  - `41-50`

### Timeout submit
- submit Google Form tunggu sampai **300 detik / 5 menit**

---

## Cron Harian yang Berlaku Sekarang

### Stop flow malam
Cron stop dijadwalkan jam:
```cron
50 23 16-31 * *
```

Artinya mulai jam **23:50**, sistem akan masuk flow stop malam.

Target flow malam:
1. hentikan alur polling
2. jalankan / tunggu auto-submit sisa bukti
3. kalau semua sudah beres baru housekeeping

### Start lagi tengah malam
Cron start:
```cron
1 0 16-31 * *
```

Artinya jam **00:01** sistem akan start lagi.

> Catatan: perubahan cron saja tidak otomatis mengubah logika isi script stop/reset. Kalau alur stop mau benar-benar "submit dulu baru housekeeping", script stop/reset harus disesuaikan juga.

---

## Cara Cek Status

### Cek orchestrator jalan atau tidak
```bash
ps -ef | grep orchestrator_5000.py
```

### Cek submit jalan atau tidak
```bash
ps -ef | grep submit_gform.py
```

### Cek log orchestrator
```bash
tail -f cron_orchestrator.log
```

### Cek jumlah screenshot pending
Hitung dari:
- file PNG di `bukti-polling/`
- dikurangi daftar file di `submitted_gform.json`

---

## Troubleshooting Singkat

### 1. Pending banyak tapi tidak auto-submit
Cek:
- apakah `orchestrator_5000.py` benar-benar jalan
- apakah `SUBMIT_TRIGGER` sudah 50
- apakah ada proses duplikat orchestrator
- apakah `submit_gform.py` sedang jalan / stuck

### 2. OTP gagal terbaca
Cek:
- `GMAIL_ADDRESS` benar
- `GMAIL_APP_PASSWORD` benar
- email OTP jangan dibuka manual dulu
- inbox masih bisa diakses bot

### 3. Screenshot ada tapi tidak masuk Google Form
Cek:
- `submitted_gform.json`
- log `submit_gform.py`
- limit batch 50
- timeout submit 300 detik

### 4. Playwright / Chromium error
Cek environment Playwright di folder itu. Pastikan browser Chromium untuk environment folder sudah tersedia.

---

## Catatan Penting

- Jangan asal jalankan 2 orchestrator di folder yang sama
- Jangan asal jalankan 2 `submit_gform.py` di folder yang sama kecuali memang sengaja recovery
- `submitted_gform.json` adalah state penting
- `email.txt` adalah batch aktif, jadi isi file ini menentukan email mana yang sedang diproses
- screenshot bukti aktif ada di `bukti-polling/`

---

## Ringkas Banget

Kalau baru pakai script ini, yang paling penting kamu cek dulu:

1. `config.json`
2. `.env`
3. `email.txt`
4. `.venv`
5. `orchestrator_5000.py`

Kalau mau jalan otomatis penuh:
```bash
.venv/bin/python3 orchestrator_5000.py
```
