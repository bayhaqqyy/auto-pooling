import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
from playwright.async_api import async_playwright
import re
import os
import random

async def click_captcha(page):
    print("Mencoba klik Captcha Cloudflare Turnstile...")
    try:
        # Turnstile iframe biasanya ada di src yang mengandung 'challenges.cloudflare.com'
        # Kita tunggu iframe-nya muncul
        iframe = page.frame_locator('iframe[src*="cloudflare"], iframe[src*="turnstile"]').first
        
        # Di dalam iframe Turnstile, ada checkbox / area yang bisa diklik. 
        # Kita tunggu checkbox/body nya clickable
        await iframe.locator('body').click(timeout=15000, position={"x": 20, "y": 20})
        print("Berhasil klik Captcha! (Tunggu proses validasi dari Cloudflare...)")
    except Exception as e:
        print(f"Peringatan: Gagal klik Captcha otomatis ({str(e)}). Jika ada Captcha yang belum tercentang, silakan klik manual.")

async def proses_email(page, email, idx):
    print(f"\n======================================")
    print(f"Memulai proses untuk email: {email}")
    print(f"======================================")
    
    # Ambil ID email terakhir sebelum mulai ngisi form (untuk perbandingan Auto-OTP)
    last_email_id = None
    try:
        from gmail_otp import get_latest_email_id
        last_email_id = get_latest_email_id()
    except Exception:
        pass
    
    await page.goto("https://danantaraindonesiacx100.com/polls/cx100-danantara", wait_until="load")

    print("1. Mengisi email...")
    # Sesuai DOM inspect: type="email" placeholder="john.doe@gmail.com"
    email_locator = page.locator('input[type="email"]')
    try:
        await email_locator.wait_for(timeout=15000)
        await email_locator.fill(email)
    except Exception as e:
        print(f"Peringatan: Gagal menemukan field email otomatis ({str(e)}).")

    print("2. Mencentang persetujuan...")
    # Sesuai DOM inspect: Label: Saya menyetujui pengiriman email verifikasi terkait polling yang akan dilakukan.
    label_persetujuan = page.locator('label').filter(has_text=re.compile(r"Saya menyetujui pengiriman email verifikasi", re.IGNORECASE))
    try:
        await label_persetujuan.wait_for(timeout=10000)
        await label_persetujuan.click() # Klik pada labelnya untuk mentrigger checkbox
        print("Berhasil mencentang persetujuan.")
    except Exception as e:
        print(f"Gagal mencentang otomatis persetujuan ({str(e)}). Silakan centang manual jika belum tercentang.")

    # Eksekusi Captcha
    print("3. Mengelola Captcha...")
    await click_captcha(page)

    print("4. Mencoba klik Selanjutnya secara agresif...")
    selanjutnya_btn = page.locator('button').filter(has_text=re.compile(r"^Selanjutnya$", re.IGNORECASE)).first
    try:
        # Cek super cepat (tiap 0.2 detik) selama 15 detik (75 iterasi)
        for _ in range(75): 
            if await selanjutnya_btn.is_enabled():
                await selanjutnya_btn.click(timeout=1000)
                print("Berhasil klik Selanjutnya secepat kilat!")
                break
            await page.wait_for_timeout(200)
    except Exception as e:
        print(f"Peringatan: Gagal klik Selanjutnya otomatis ({str(e)}).")
        
    print("5. Menunggu halaman Syarat & Ketentuan...")
    try:
        # Menunggu sampai ada elemen baru yang menunjukkan halaman syarat dan ketentuan (teks syarat / setuju)
        await page.wait_for_function(
            '''() => document.body.innerText.toLowerCase().includes("syarat") || document.body.innerText.toLowerCase().includes("setuju")''', 
            timeout=30000
            
        )
        print("Halaman Syarat & Ketentuan terdeteksi.")
        
        print("Scroll ke bawah dan centang...")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(500) # Jeda kecil agar trigger scroll terbaca

        # Mencari checkbox persetujuan syarat dan klik
        # Terkadang checkbox tersembunyi dan harus diklik labelnya
        label_syarat = page.locator('label').filter(has_text=re.compile(r"setuju", re.IGNORECASE))
        if await label_syarat.count() > 0:
            await label_syarat.first.click()
        else:
            # Jika tidak ketemu teks 'setuju', cari semua checkbox di halaman dan centang
            checkboxes = await page.locator('input[type="checkbox"]').all()
            for cb in checkboxes:
                await cb.check(force=True)

        print("Mencoba klik Selanjutnya (Halaman Syarat)...")
        # Karena kita sudah pindah halaman, cari lagi tombol Selanjutnya
        selanjutnya_btn2 = page.locator('button').filter(has_text=re.compile(r"^Selanjutnya$", re.IGNORECASE)).last
        await selanjutnya_btn2.click(timeout=5000)
        print("Berhasil klik Selanjutnya di halaman syarat.")
    except Exception as e:
        print(f"Proses di halaman Syarat & Ketentuan gagal dieksekusi otomatis ({str(e)}). Silakan teruskan secara manual di browser.")

    print("6. Menunggu halaman verifikasi OTP (Periksa Inbox/Spam)...")
    try:
        # Menunggu tulisan "Periksa Inbox" atau "Masukkan kode" menggunakan regex agar lebih longgar
        verif_text = page.locator('text=/Periksa Inbox|Masukkan kode/i').first
        await verif_text.wait_for(timeout=30000, state="visible")
        print("Halaman verifikasi OTP terdeteksi!")
        
        try:
            print("Mencoba klik tombol 'Masukkan Kode' untuk memunculkan form input OTP...")
            # Pake get_by_role yang paling stabil buat nembus React DOM
            btn_masukkan_kode = page.get_by_role("button", name=re.compile(r"Masukkan Kode", re.IGNORECASE)).first
            await btn_masukkan_kode.wait_for(timeout=10000, state="visible")
            await page.wait_for_timeout(500)
            await btn_masukkan_kode.click(force=True)
            print("Berhasil klik tombol 'Masukkan Kode'.")
        except Exception as e:
            print(f"Tombol 'Masukkan Kode' tidak diklik otomatis. Detail: {e}")
    except:
        print("Deteksi halaman verifikasi otomatis gagal, lanjut mencari OTP...")

    otp_kode = None
    
    # Fungsi pembantu untuk Auto-Fetch
    def coba_auto_fetch():
        try:
            from gmail_otp import get_latest_email_id, fetch_new_otp, load_config
            config = load_config()
            if config:
                print("\n[Mode Auto-OTP] Mengecek email OTP di Gmail...")
                return fetch_new_otp(last_email_id, timeout=45)
        except Exception as e:
            print(f"Error Auto-OTP: {e}")
        return None

    otp_kode = coba_auto_fetch()

    # Fallback ke Manual Input jika Auto-OTP gagal/tidak dikonfigurasi
    if not otp_kode:
        print("\n⚠️ OTP tidak ditemukan otomatis. Jika belum terkirim, silakan klik tombol 'Masukkan Kode' secara manual di browser.")
        while True:
            otp_kode = input(f"\n[Email: {email}] Masukkan kode verifikasi (OTP)\n(Ketik 'baru' minta ulang, 'skip' lewati, atau TEKAN ENTER KOSONG untuk cek Gmail lagi): ")
            
            if otp_kode.strip().lower() == 'skip':
                print("Melewati email ini dan lanjut ke berikutnya...")
                return
            elif otp_kode.strip().lower() == 'baru':
                print("Meminta kode baru...")
                minta_baru_btn = page.locator('button, a').filter(has_text=re.compile(r"minta kode baru|kirim ulang", re.IGNORECASE)).first
                try:
                    await minta_baru_btn.click()
                except:
                    pass
                continue
            elif otp_kode.strip() == "":
                # User menekan enter kosong, coba fetch lagi!
                hasil = coba_auto_fetch()
                if hasil:
                    otp_kode = hasil
                    break
            else:
                break

    print(f"Mengisi kode OTP: {otp_kode}")
    try:
        # Karena ada 4 kotak terpisah (masing-masing 1 digit), kita kumpulkan semua input yang terlihat
        inputs = await page.locator('input').all()
        valid_inputs = []
        for inp in inputs:
            if await inp.is_visible() and await inp.is_editable():
                valid_inputs.append(inp)
                
        if len(valid_inputs) == 1:
            # Jika webnya update jadi 1 kotak panjang
            await valid_inputs[0].fill(otp_kode)
        elif len(valid_inputs) >= 4 and len(otp_kode) == 4:
            # Isi per digit ke 4 kotak pertama
            for i in range(4):
                await valid_inputs[i].fill(otp_kode[i])
        else:
            # Fallback: isi per karakter ke kotak-kotak yang ada
            for i, char in enumerate(otp_kode):
                if i < len(valid_inputs):
                    await valid_inputs[i].fill(char)
    except Exception as e:
        print(f"Gagal menemukan field input OTP otomatis ({str(e)}). Silakan isi kode di browser secara manual.")

    # 7. Pilih Sektor: Jasa Keuangan (Langsung klik tanpa klik Lanjut karena web otomatis navigasi)
    print("7. Menunggu Halaman Sektor (Memilih Jasa Keuangan)...")
    try:
        jasa_keuangan = page.locator('text="Jasa Keuangan"').first
        await jasa_keuangan.wait_for(timeout=30000, state="visible")
        await page.wait_for_timeout(500)
        await jasa_keuangan.click()
        print("Berhasil klik Jasa Keuangan.")
    except Exception as e:
        print("Error memilih Jasa Keuangan. Lanjut manual...", e)

    # 8. Pilih Sub-Sektor: Multifinance (Langsung klik tanpa klik Lanjut)
    print("8. Menunggu Halaman Sub-Sektor (Memilih Multifinance)...")
    try:
        multifinance = page.locator('text="Multifinance"').first
        await multifinance.wait_for(timeout=30000, state="visible")
        await page.wait_for_timeout(500)
        await multifinance.click()
        print("Berhasil klik Multifinance.")
    except Exception as e:
        print("Error memilih Multifinance. Lanjut manual...", e)

    # 9. Pilih 3 Faktor Teratas
    print("9. Menunggu Halaman Faktor (Memilih 3 Faktor)...")
    try:
        # Kita tunggu div yg memiliki teks "Mudah menemukan" muncul
        mudah_div = page.locator('div[role="checkbox"]').filter(has_text=re.compile(r"Mudah menemukan informasi", re.IGNORECASE)).first
        await mudah_div.wait_for(timeout=30000, state="visible")
        
        # 3 faktor yang diminta
        print("Mencentang faktor dengan cepat...")
        async def klik_faktor(keyword):
            ele = page.locator('div[role="checkbox"]').filter(has_text=re.compile(keyword, re.IGNORECASE)).first
            await ele.wait_for(timeout=5000, state="visible")
            await ele.click()
            await page.wait_for_timeout(50) # Dipercepat
            
        await klik_faktor("Mudah menemukan")
        await klik_faktor("Hasil pembiayaan")
        await klik_faktor("Keluhan ditangani")
        
        print("Mencoba klik Lanjut...")
        lanjut_btn = page.locator('button, div[role="button"]').filter(has_text=re.compile(r"^Lanjut$|^Selanjutnya$", re.IGNORECASE)).last
        for _ in range(15):
            if await lanjut_btn.is_enabled():
                await lanjut_btn.click(timeout=1000)
                print("Berhasil klik Lanjut di halaman faktor.")
                break
            await page.wait_for_timeout(500)
    except Exception as e:
        print("Error mencentang faktor. Gagal melanjutkan...", e)
        return # STOP proses email ini supaya nggak salah screenshot

    print("10. Memilih Institusi: Pegadaian...")
    try:
        pegadaian = page.locator('text="Pegadaian"').first
        await pegadaian.wait_for(timeout=30000, state="visible")
        await page.wait_for_timeout(500)
        await pegadaian.click()
        await page.wait_for_timeout(1000)
        
        print("Mencoba klik Lanjut (Pegadaian)...")
        lanjut_btn = page.locator('button, div[role="button"]').filter(has_text=re.compile(r"^Lanjut$|^Selanjutnya$", re.IGNORECASE)).last
        for _ in range(15):
            if await lanjut_btn.is_enabled():
                await lanjut_btn.click(timeout=1000)
                print("Berhasil klik Lanjut di halaman institusi.")
                break
            await page.wait_for_timeout(500)
    except Exception as e:
        print("Error memilih Pegadaian. Gagal melanjutkan...", e)
        return # STOP proses email ini supaya nggak salah screenshot

    print("11. Menunggu halaman Terima Kasih dan Screenshot...")
    try:
        # Tunggu teks khusus di dalam modal agar lebih pasti
        modal_text = page.locator('text="Terima Kasih Atas Partisipasinya"').first
        await modal_text.wait_for(timeout=30000, state="visible")
        await page.wait_for_timeout(1000) # Jeda animasi
    except Exception as e:
        print(f"Halaman terima kasih lambat/tidak terdeteksi otomatis ({e}), tetap lanjut screenshot...")

    # Simpan screenshot menggunakan nomor urut
    ss_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bukti-polling")
    
    if not os.path.exists(ss_dir):
        os.makedirs(ss_dir)
        
    ss_path = os.path.join(ss_dir, f"rafli_14_07_2026_{idx + 1}.png")
    await page.screenshot(path=ss_path, full_page=False) # Capture area yang terlihat saja (pop-up)
    print(f"✅ Screenshot berhasil disimpan: {ss_path}")

    print("12. Klik Simpan & Akhiri...")
    try:
        simpan_akhiri = page.locator('button, div[role="button"]').filter(has_text=re.compile(r"Simpan & Akhiri|Selesai|Akhiri", re.IGNORECASE)).first
        if await simpan_akhiri.is_visible(timeout=5000):
            await simpan_akhiri.click()
            print("Berhasil menyelesaikan polling untuk email ini!")
    except:
        print("Tombol Simpan & Akhiri tidak ditemukan atau gagal diklik. Silakan periksa browser.")

async def main():
    file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email.txt")
    if not os.path.exists(file_path):
        with open(file_path, "w") as f:
            f.write("user1@email.com\nuser2@email.com\n")
        print(f"File {file_path} belum ada. Saya sudah buatkan format contohnya.")
        print("Silakan edit isi file tersebut dengan daftar email Anda, lalu jalankan ulang script.")
        return

    with open(file_path, "r") as f:
        emails = [line.strip() for line in f if line.strip()]
        
    if not emails or emails == ["user1@email.com", "user2@email.com"]:
        print(f"File {file_path} masih kosong atau berisi contoh default.")
        print("Silakan edit file tersebut dan isi dengan alamat email (satu baris satu email).")
        return
        
    print(f"Ditemukan {len(emails)} email untuk diproses.")

    async with async_playwright() as p:
        print("\n🌐 Membuka browser Microsoft Edge...")
        browser = await p.chromium.launch(
            headless=False, 
            channel="msedge",
            args=["--start-maximized", "--incognito", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(no_viewport=True)
        page = await context.new_page()
        # Biarkan lebih fleksibel kalau halamannya butuh waktu lama utk pindah/loading
        page.set_default_timeout(15000) 

        for idx, email in enumerate(emails):
            await proses_email(page, email, idx)
            
            # Waktu jeda anti-spam jika bukan email terakhir
            if idx < len(emails) - 1:
                jeda = random.randint(2, 5) # Dipercepat ekstrim
                print(f"\n=> Selesai untuk email {email}.")
                print(f"=> Menunggu {jeda} detik sebelum melanjutkan ke email berikutnya...")
                await page.wait_for_timeout(jeda * 1000)

        print("\n🎉 Semua email di dalam file email.txt telah diproses!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
