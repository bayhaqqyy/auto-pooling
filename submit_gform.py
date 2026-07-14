import os
import re
import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
SS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bukti-polling")
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeZeRQUntw1l_ELrblJRphissrNg0g4bg0ThqV0j4pekOM7IQ/viewform"
GOOGLE_2FA_WAIT_SECONDS = 180
SUBMITTED_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "submitted_gform.json")


def load_env_credentials():
    credentials = {}
    if not os.path.exists(ENV_FILE):
        return credentials
    with open(ENV_FILE, "r") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            credentials[key.strip().lower()] = value.strip().strip('"').strip("'")
    return credentials


def load_submitted_state():
    if not os.path.exists(SUBMITTED_STATE_FILE):
        return {"submitted_files": []}
    try:
        with open(SUBMITTED_STATE_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"submitted_files": []}
        data.setdefault("submitted_files", [])
        return data
    except Exception:
        return {"submitted_files": []}


def save_submitted_state(state):
    with open(SUBMITTED_STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def mark_files_as_submitted(files):
    state = load_submitted_state()
    submitted = set(state.get("submitted_files", []))
    for file_path in files:
        submitted.add(os.path.abspath(file_path))
    state["submitted_files"] = sorted(submitted)
    save_submitted_state(state)


async def click_next_button(page):
    button = page.locator('button:has-text("Next"), button:has-text("Berikutnya"), div[role="button"]:has-text("Next"), div[role="button"]:has-text("Berikutnya")').first
    await button.click(timeout=30000)


async def wait_for_google_2fa_approval(page, timeout_seconds=GOOGLE_2FA_WAIT_SECONDS):
    print(f"⏳ Menunggu approval 2FA Google sampai {timeout_seconds} detik tanpa rerun login...")
    deadline = asyncio.get_event_loop().time() + timeout_seconds
    last_prompt = None

    while asyncio.get_event_loop().time() < deadline:
        if "accounts.google.com" not in page.url:
            print("✅ Halaman sudah keluar dari challenge Google. Approval 2FA diterima.")
            return True

        try:
            prompt_number = None
            candidates = [
                page.locator('text=/Check your .*?/i').first,
                page.locator('text=/2-Step Verification/i').first,
            ]
            for candidate in candidates:
                if await candidate.count() > 0:
                    body_text = await page.locator('body').inner_text()
                    import re as _re
                    m = _re.search(r'\b(\d{2})\b', body_text)
                    if m:
                        prompt_number = m.group(1)
                    break
            if prompt_number and prompt_number != last_prompt:
                last_prompt = prompt_number
                print(f"📲 Prompt 2FA aktif. Pilih angka {prompt_number} di HP jika diminta.")
        except Exception:
            pass

        await page.wait_for_timeout(3000)
        try:
            await page.reload(wait_until="load", timeout=30000)
        except Exception:
            pass

    await page.screenshot(path="debug_google_login_challenge_timeout.png", full_page=True)
    print("❌ Timeout menunggu approval 2FA Google.")
    print("   Screenshot: debug_google_login_challenge_timeout.png")
    return False


async def login_google_if_needed(page):
    if "accounts.google.com" not in page.url:
        return True

    creds = load_env_credentials()
    config = load_config() or {}
    
    # Coba email dari .env dulu, fallback ke GMAIL_ADDRESS di config.json
    email = creds.get("email") or creds.get("google_email") or creds.get("gmail_address") or config.get("GMAIL_ADDRESS")
    password = creds.get("password") or creds.get("google_password") or creds.get("gmail_password")

    if not email or not password:
        await page.screenshot(path="debug_google_login_missing_credentials.png", full_page=True)
        print("❌ Google login dibutuhkan, tapi .env/config.json belum berisi email/password yang lengkap.")
        return False

    print(f"🔐 Google login dibutuhkan. Mencoba login otomatis memakai email: {email}...")
    try:
        email_input = page.locator('input[type="email"], input[name="identifier"]').first
        await email_input.fill(email)
        await click_next_button(page)
        await page.wait_for_timeout(3000)

        password_input = page.locator('input[type="password"], input[name="Passwd"]').first
        await password_input.wait_for(state="visible", timeout=60000)
        await password_input.fill(password)
        await click_next_button(page)
        await page.wait_for_timeout(8000)

        if "accounts.google.com" in page.url:
            if not await wait_for_google_2fa_approval(page):
                await page.screenshot(path="debug_google_login_challenge.png", full_page=True)
                print("❌ Login belum selesai. Google kemungkinan meminta 2FA/challenge/manual verification.")
                print("   Screenshot: debug_google_login_challenge.png")
                return False

        print("✅ Login Google berhasil dan session tersimpan di chrome_data_form.")
        return True
    except Exception as e:
        await page.screenshot(path="debug_google_login_failed.png", full_page=True)
        print(f"❌ Gagal auto-login Google: {e}")
        print("   Screenshot: debug_google_login_failed.png")
        return False


def screenshot_number(path):
    match = re.search(r'_(\d+)\.png$', os.path.basename(path))
    if match:
        return int(match.group(1))
    return 0


async def launch_browser(p, user_data_dir):
    has_display = bool(os.environ.get("DISPLAY"))
    launch_kwargs = {
        "headless": not has_display,
        "args": ["--start-maximized", "--disable-blink-features=AutomationControlled"],
        "no_viewport": True,
    }
    if has_display:
        print("🖥️ DISPLAY terdeteksi. Menjalankan browser non-headless.")
    else:
        print("🕶️ DISPLAY tidak ada. Menjalankan browser headless.")

    chrome_candidates = ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]
    chrome_path = next((path for path in chrome_candidates if os.path.exists(path)), None)
    if chrome_path:
        print(f"🌐 Menggunakan browser system: {chrome_path}")
        launch_kwargs["executable_path"] = chrome_path
    else:
        print("🌐 Browser system tidak ditemukan. Fallback ke Chromium Playwright.")

    return await p.chromium.launch_persistent_context(user_data_dir, **launch_kwargs)


async def ensure_form_loaded(page):
    await page.goto(FORM_URL, wait_until="load", timeout=120000)
    await page.wait_for_timeout(3000)
    if "accounts.google.com" in page.url:
        if not await login_google_if_needed(page):
            await page.screenshot(path="debug_google_login_required.png", full_page=True)
            print("❌ Google Forms meminta login Google dulu dan auto-login belum berhasil.")
            print("   Screenshot kondisi login: debug_google_login_required.png")
            return False
        await page.goto(FORM_URL, wait_until="load", timeout=120000)
        await page.wait_for_timeout(3000)
        if "accounts.google.com" in page.url:
            await page.screenshot(path="debug_google_login_required.png", full_page=True)
            print("❌ Setelah login attempt, Google masih meminta login/challenge.")
            return False
    return True


async def click_upload_and_set_files(page, files):
    upload_buttons = page.locator(
        'div[role="button"]:has-text("Add file"), '
        'div[role="button"]:has-text("Tambahkan file"), '
        'span:has-text("Add file"), '
        'span:has-text("Tambahkan file")'
    )
    count = await upload_buttons.count()
    if count == 0:
        raise RuntimeError("Tombol Add file/Tambahkan file tidak ditemukan di form")

    # 1. Klik Add File untuk buka Modal internal Google
    await upload_buttons.first.click(force=True)
    
    # 2. Cari iframe modal picker yang muncul
    print("      Menunggu modal Insert file terbuka...")
    picker_iframe = page.frame_locator('iframe.picker-frame, iframe[src*="picker"]')
    
    # 3. Tunggu tombol Browse muncul di dalam iframe picker
    browse_btn = picker_iframe.locator('text=/Browse|Jelajah|Pilih|Cari/i').first
    await browse_btn.wait_for(state="visible", timeout=15000)

    # 4. Klik Browse dan tangkap OS File Chooser
    print("      Mengklik Browse dan menangkap file chooser...")
    async with page.expect_file_chooser(timeout=30000) as fc:
        await browse_btn.click(force=True)
        
    await (await fc.value).set_files(files)

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("Error: config.json tidak ditemukan!")
        return None
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error baca config.json: {e}")
        return None

async def main():
    config = load_config()
    if not config:
        return
        
    nama = config.get("FORM_NAMA", "")
    nik = config.get("FORM_NIK", "")
    
    if not nama or not nik or nama == "Isi Nama Lengkap Disini":
        print("❌ STOP! Anda belum mengisi FORM_NAMA dan FORM_NIK di config.json.")
        print("Silakan buka file config.json dan isi data diri Anda terlebih dahulu.")
        return
        
    if not os.path.exists(SS_DIR):
        print(f"❌ Folder {SS_DIR} tidak ditemukan! Pastikan Anda sudah menjalankan bot polling minimal sekali.")
        return
        
    all_files = [os.path.join(SS_DIR, f) for f in os.listdir(SS_DIR) if f.endswith(".png")]
    # Urutkan file berdasarkan angka di nama file (biar screenshot_85 diproses duluan dari screenshot_100)
    all_files.sort(key=screenshot_number)
    
    if len(all_files) == 0:
        print("❌ Tidak ada file screenshot .png di dalam folder bukti-polling!")
        return

    state = load_submitted_state()
    submitted_files = set(state.get("submitted_files", []))
    pending_files = [f for f in all_files if os.path.abspath(f) not in submitted_files]

    if len(pending_files) == 0:
        print("✅ Semua file di folder bukti-polling sudah pernah dikirim ke Google Form.")
        print(f"   State file: {SUBMITTED_STATE_FILE}")
        return
        
    print(f"📦 Ditemukan total {len(all_files)} screenshot di folder bukti-polling.")
    print(f"🆕 Yang belum pernah dikirim: {len(pending_files)} file.")
    
    # Kelompokkan per 50 file (1 form submit max 50 file dibagi ke 5 tombol)
    batches = [pending_files[i:i + 50] for i in range(0, len(pending_files), 50)]
    
    user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_data_form")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        
    async with async_playwright() as p:
        print("\n🌐 Membuka browser otomatis...")
        browser = await launch_browser(p, user_data_dir)
        
        page = browser.pages[0] if browser.pages else await browser.new_page()
        page.set_default_timeout(60000)
        
        for batch_idx, batch_files in enumerate(batches):
            print(f"\n======================================")
            print(f"🚀 Memproses Submit Form ke-{batch_idx + 1} (Membawa {len(batch_files)} Screenshot)")
            print(f"======================================")
            
            if not await ensure_form_loaded(page):
                await browser.close()
                return
            
            # Karena ini Chrome asli Anda, kemungkinan besar sudah login!
            # Namun kita tetap beri jeda sebentar untuk memastikan form termuat penuh
            await page.wait_for_timeout(3000)
                
            print("\n1. Mengisi Nama dan NIK...")
            # Perbaikan: Tambahkan :visible agar tidak error mengenai input tersembunyi (seperti captcha)
            text_inputs = page.locator('input.whsOnd.zHQkBf:visible')
            await text_inputs.nth(0).fill(nama)
            await text_inputs.nth(1).fill(nik)
            
            print("2. Memilih Jabatan dan Unit Kerja...")
            listboxes = page.get_by_role("listbox")
            
            # Klik Dropdown 1: Jabatan
            await listboxes.nth(0).click()
            await page.wait_for_timeout(1000)
            await page.get_by_role("option", name="TAD", exact=True).click()
            await page.wait_for_timeout(500)
            
            # Klik Dropdown 2: Unit Kerja
            await listboxes.nth(1).click()
            await page.wait_for_timeout(1000)
            await page.get_by_role("option", name="DIVISI OPERASIONAL & INFRASTRUKTUR TI", exact=True).click()
            await page.wait_for_timeout(500)
            
            print("3. Mengisi Tanggal...")
            date_input = page.locator('input[type="date"]')
            # Format tanggal biasanya YYYY-MM-DD
            today = datetime.now().strftime("%Y-%m-%d")
            await date_input.fill(today)
            
            print("4. Mulai Mengupload Gambar...")
            # Bagi lagi 50 gambar jadi 5 grup (karena 1 tombol "Add file" maksimal hanya bisa 10 gambar)
            sub_batches = [batch_files[i:i + 10] for i in range(0, len(batch_files), 10)]
            
            for i, sub_batch in enumerate(sub_batches):
                print(f"   -> Mengupload grup gambar ke-{i+1} ({len(sub_batch)} file)...")
                await page.wait_for_timeout(1000)
                try:
                    await click_upload_and_set_files(page, sub_batch)
                except Exception as e:
                    print("❌ GAGAL MENGUPLOAD! Tidak bisa menemukan tombol Browse/Jelajahi.")
                    print(f"Detail error: {e}")
                    print("==== MENGAMBIL GAMBAR BUKTI ERROR ====")
                    await page.screenshot(path="debug_gagal_upload.png")
                    print("Screenshot disimpan sebagai: debug_gagal_upload.png")
                    print("Silakan buka gambar tersebut untuk melihat apa yang bot lihat!")
                    return
                
                print("   -> Menunggu proses upload selesai (mohon bersabar)...")
                # Popup upload otomatis tertutup jika upload beres (tunggu sampai elemennya hilang)
                try:
                    await page.locator('div[role="dialog"]').wait_for(state="hidden", timeout=60000)
                except:
                    pass
                try:
                    await page.locator('iframe.picker-frame, iframe[src*="picker"]').wait_for(state="hidden", timeout=60000)
                except:
                    pass
                print("   -> Upload grup selesai!")
                await page.wait_for_timeout(1000)
            
            print("\n5. Mencentang Persetujuan...")
            checkbox = page.get_by_role("checkbox")
            await checkbox.click()
            
            print("6. Mengirim Form...")
            submit_btn = page.get_by_role("button", name=re.compile(r"Submit|Kirim", re.IGNORECASE))
            await submit_btn.click()
            
            print("Menunggu konfirmasi...")
            try:
                # Cari salah satu dari teks sukses (Inggris/Indo)
                await page.wait_for_selector('text="Your response has been recorded.", text="Tanggapan Anda telah direkam."', timeout=60000)
                print(f"✅ Form ke-{batch_idx + 1} BERHASIL DIKIRIM!")
            except:
                print("⚠️ Tidak dapat mendeteksi halaman sukses, tapi form mungkin sudah terkirim.")

            mark_files_as_submitted(batch_files)
            print(f"📝 Menandai {len(batch_files)} file sebagai sudah terkirim di {SUBMITTED_STATE_FILE}")
            await page.wait_for_timeout(3000)
            
        print("\n🎉 SELAMAT! SEMUA BUKTI POLLING TELAH SELESAI DI-SUBMIT KE GOOGLE FORM!")
        # Tidak usah ditutup browser aslinya
        # await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
