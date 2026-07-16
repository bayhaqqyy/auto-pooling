import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import asyncio
from playwright.async_api import async_playwright
import re
import os
import random
import json
import datetime

SCREENSHOT_PREFIX = f"rafli_{datetime.datetime.now().strftime('%d_%m_%Y')}_"
SCREENSHOT_SUFFIX = ".png"
EMAIL_PROCESS_TIMEOUT_SECONDS = 180
MAX_RETRIES_PER_EMAIL = 2
POLLING_SUCCESS_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "polling_success_emails.json")


def load_success_emails():
    if not os.path.exists(POLLING_SUCCESS_STATE_FILE):
        return set()
    try:
        with open(POLLING_SUCCESS_STATE_FILE, "r") as f:
            data = json.load(f)
        return set(data.get("success_emails", []))
    except Exception:
        return set()


def mark_success_email(email):
    success_emails = load_success_emails()
    success_emails.add(email)
    tmp_path = POLLING_SUCCESS_STATE_FILE + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump({"success_emails": sorted(success_emails)}, f, indent=2)
    os.replace(tmp_path, POLLING_SUCCESS_STATE_FILE)


def get_screenshot_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "bukti-polling")


def get_next_screenshot_number(ss_dir=None):
    ss_dir = ss_dir or get_screenshot_dir()
    if not os.path.exists(ss_dir):
        return 1

    max_num = 0
    for entry in os.listdir(ss_dir):
        if not (entry.startswith(SCREENSHOT_PREFIX) and entry.endswith(SCREENSHOT_SUFFIX)):
            continue
        middle = entry[len(SCREENSHOT_PREFIX):-len(SCREENSHOT_SUFFIX)]
        if middle.isdigit():
            max_num = max(max_num, int(middle))
    return max_num + 1


def build_screenshot_path(next_number, ss_dir=None):
    ss_dir = ss_dir or get_screenshot_dir()
    return os.path.join(ss_dir, f"{SCREENSHOT_PREFIX}{next_number}{SCREENSHOT_SUFFIX}")


def should_retry_status(status):
    return status in {"failed", "timeout", "crashed"}

async def wait_next_enabled(next_button, timeout_ms=15000):
    deadline = asyncio.get_event_loop().time() + (timeout_ms / 1000)
    while asyncio.get_event_loop().time() < deadline:
        try:
            if await next_button.count() > 0 and await next_button.is_visible() and await next_button.is_enabled():
                return True
        except Exception:
            pass
        await page_safe_sleep(250)
    return False


async def page_safe_sleep(ms):
    await asyncio.sleep(ms / 1000)


async def click_captcha(page, next_button=None):
    print("Mencoba deteksi Captcha Cloudflare Turnstile...")
    candidate_selectors = [
        '#cf-turnstile',
        '[class*="turnstile"]',
        'iframe[src*="cloudflare"]',
        'iframe[src*="turnstile"]',
    ]

    for attempt in range(1, 4):
        print(f"Percobaan captcha {attempt}/3...")
        for selector in candidate_selectors:
            try:
                locator = page.locator(selector).first
                if await locator.count() == 0:
                    continue
                box = await locator.bounding_box()
                if not box:
                    continue

                click_x = box["x"] + min(30, max(10, box["width"] / 2))
                click_y = box["y"] + min(30, max(10, box["height"] / 2))
                await page.mouse.move(click_x, click_y)
                await page.mouse.click(click_x, click_y)
                print(f"Klik area Turnstile via selector: {selector}. Verifikasi tombol Selanjutnya...")

                if next_button is not None:
                    if await wait_next_enabled(next_button, timeout_ms=10000):
                        print("✅ Captcha valid: tombol Selanjutnya sudah aktif.")
                        return True
                    print("⚠️ Captcha belum valid: tombol Selanjutnya masih disabled.")
                else:
                    await page.wait_for_timeout(3000)
                    return True
            except Exception as e:
                print(f"Selector captcha gagal ({selector}): {e}")
                continue

        await page.wait_for_timeout(1500)

    print("❌ Captcha tidak terverifikasi setelah 3 percobaan. Email akan dianggap gagal agar self-heal rerun.")
    return False

async def proses_email(page, email, screenshot_number):
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

    print("4. Mempersiapkan tombol Selanjutnya dan verifikasi Captcha...")
    selanjutnya_btn = page.locator('button').filter(has_text=re.compile(r"^Selanjutnya$", re.IGNORECASE)).first

    # Eksekusi Captcha wajib valid: tombol Selanjutnya harus aktif dulu.
    print("3. Mengelola Captcha...")
    captcha_ok = await click_captcha(page, selanjutnya_btn)
    if not captcha_ok:
        print("❌ Captcha belum terceklis/valid. Stop email ini dan biarkan self-heal rerun.")
        return {"status": "failed", "screenshot_taken": False}

    print("4. Mencoba klik Selanjutnya setelah captcha valid...")
    clicked_next = False
    try:
        for _ in range(75):
            if await selanjutnya_btn.is_visible() and await selanjutnya_btn.is_enabled():
                await selanjutnya_btn.click(timeout=1000)
                clicked_next = True
                print("Berhasil klik Selanjutnya setelah captcha aktif!")
                break
            await page.wait_for_timeout(200)
    except Exception as e:
        print(f"Peringatan: Gagal klik Selanjutnya otomatis ({str(e)}).")

    if not clicked_next:
        print("❌ Tombol Selanjutnya tidak aktif/berhasil diklik. Stop email ini dan rerun.")
        return {"status": "failed", "screenshot_taken": False}
        
    print("5. Menangani halaman lanjutan (Syarat & Ketentuan / OTP)...")
    try:
        state = None
        for _ in range(30):
            body_text = (await page.locator('body').inner_text()).lower()
            if any(keyword in body_text for keyword in ["periksa inbox", "masukkan kode", "kode verifikasi", "otp"]):
                state = "otp"
                break
            if any(keyword in body_text for keyword in ["syarat", "ketentuan", "saya setuju", "setuju"]):
                state = "terms"
                break

            # dorong transisi kalau tombol next masih ada
            try:
                if await selanjutnya_btn.is_enabled():
                    await selanjutnya_btn.click(timeout=1000)
            except Exception:
                pass
            await page.wait_for_timeout(1000)

        if state == "terms":
            print("Halaman Syarat & Ketentuan terdeteksi.")
            print("Scroll ke bawah dan centang...")
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

            label_syarat = page.locator('label').filter(has_text=re.compile(r"setuju|saya setuju|syarat|ketentuan", re.IGNORECASE))
            if await label_syarat.count() > 0:
                await label_syarat.first.click(force=True)
            else:
                checkboxes = await page.locator('input[type="checkbox"], div[role="checkbox"]').all()
                for cb in checkboxes:
                    try:
                        await cb.click(force=True)
                    except Exception:
                        try:
                            await cb.check(force=True)
                        except Exception:
                            pass

            print("Mencoba klik Selanjutnya (Halaman Syarat)...")
            selanjutnya_btn2 = page.locator('button').filter(has_text=re.compile(r"^Selanjutnya$|^Lanjut$|^Berikutnya$", re.IGNORECASE)).last
            await selanjutnya_btn2.click(timeout=5000)
            print("Berhasil klik Selanjutnya di halaman syarat.")
        elif state == "otp":
            print("Halaman OTP terdeteksi langsung; skip handling syarat.")
        else:
            print("Halaman syarat tidak terdeteksi jelas; lanjut cek OTP tanpa berhenti total.")
    except Exception as e:
        print(f"Handling halaman lanjutan tidak full otomatis ({str(e)}). Lanjut cek OTP...")

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

    # Fallback: di server/tmux non-interactive, jangan masuk input() manual karena akan bikin self-heal macet.
    if not otp_kode:
        print("\n⚠️ OTP tidak ditemukan otomatis. Email ini dianggap gagal agar self-heal bisa rerun tanpa input manual.")
        return {"status": "failed", "screenshot_taken": False}

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
        
        # Cek jika Multifinance terdeteksi limit / "tersedia lagi"
        body_text_subsector = (await page.locator('body').inner_text()).lower()
        if "tersedia lagi" in body_text_subsector:
            print("⚠️ Terdeteksi limit sub-sektor (Tersedia lagi). Skip email ini.")
            return {"status": "failed_limit_multifinance", "screenshot_taken": False}
            
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
        return {"status": "failed", "screenshot_taken": False}

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
        return {"status": "failed", "screenshot_taken": False}

    print("11. Menunggu halaman Terima Kasih dan Screenshot...")
    try:
        # Tunggu teks khusus di dalam modal agar lebih pasti
        modal_text = page.locator('text="Terima Kasih Atas Partisipasinya"').first
        await modal_text.wait_for(timeout=30000, state="visible")
        await page.wait_for_timeout(1000) # Jeda animasi
    except Exception as e:
        print(f"Halaman terima kasih lambat/tidak terdeteksi otomatis ({e}), tetap lanjut screenshot...")

    # Simpan screenshot menggunakan nomor urut
    ss_dir = get_screenshot_dir()
    
    if not os.path.exists(ss_dir):
        os.makedirs(ss_dir)
        
    ss_path = build_screenshot_path(screenshot_number, ss_dir)
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

    return {"status": "success", "screenshot_taken": True, "screenshot_path": ss_path}


async def create_page(context):
    page = await context.new_page()
    page.set_default_timeout(15000)
    return page


async def process_email_with_self_heal(context, email, screenshot_number):
    last_status = "failed"
    for attempt in range(1, MAX_RETRIES_PER_EMAIL + 1):
        page = await create_page(context)
        try:
            print(f"\n🔁 Attempt {attempt}/{MAX_RETRIES_PER_EMAIL} untuk email: {email}")
            result = await asyncio.wait_for(
                proses_email(page, email, screenshot_number),
                timeout=EMAIL_PROCESS_TIMEOUT_SECONDS,
            )
            status = (result or {}).get("status", "failed")
            last_status = status
            if status == "success":
                await page.close()
                return result
            if not should_retry_status(status):
                await page.close()
                return result
            print(f"⚠️ Status {status} untuk {email}. Menjalankan self-heal rerun...")
        except asyncio.TimeoutError:
            last_status = "timeout"
            print(f"⏰ Timeout {EMAIL_PROCESS_TIMEOUT_SECONDS} detik untuk {email}. Self-heal rerun...")
        except Exception as e:
            last_status = "crashed"
            print(f"💥 Error tidak terduga untuk {email}: {e}. Self-heal rerun...")
        finally:
            try:
                await page.close()
            except Exception:
                pass

    return {"status": last_status, "screenshot_taken": False}

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
        edge_path = "/opt/microsoft/msedge/msedge"
        has_display = bool(os.environ.get("DISPLAY"))
        launch_kwargs = {
            "headless": not has_display,
            "args": ["--start-maximized", "--incognito", "--disable-blink-features=AutomationControlled"],
        }
        if has_display:
            print("🖥️ DISPLAY terdeteksi. Menjalankan browser non-headless.")
        else:
            print("🕶️ DISPLAY tidak ada. Menjalankan browser headless untuk server mode.")
        if os.path.exists(edge_path):
            print("\n🌐 Membuka browser Microsoft Edge...")
            launch_kwargs["channel"] = "msedge"
        else:
            print("\n🌐 Microsoft Edge tidak ditemukan. Fallback ke Chromium Playwright...")

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(no_viewport=True)

        screenshot_counter = get_next_screenshot_number()
        success_emails_set = load_success_emails()

        for idx, email in enumerate(emails):
            if email in success_emails_set:
                print(f"⏩ Email {email} sudah pernah sukses polling. Melewati...")
                continue

            result = await process_email_with_self_heal(context, email, screenshot_counter)
            if (result or {}).get("screenshot_taken"):
                screenshot_counter += 1
                mark_success_email(email)
                success_emails_set.add(email)
            
            # Waktu jeda anti-spam jika bukan email terakhir
            if idx < len(emails) - 1:
                jeda = random.randint(2, 5) # Dipercepat ekstrim
                print(f"\n=> Selesai untuk email {email}.")
                print(f"=> Status akhir: {(result or {}).get('status', 'unknown')}")
                print(f"=> Menunggu {jeda} detik sebelum melanjutkan ke email berikutnya...")
                await asyncio.sleep(jeda)

        print("\n🎉 Semua email di dalam file email.txt telah diproses!")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
