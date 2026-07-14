import os
import re
import json
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
SS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bukti-polling")
FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLSeZeRQUntw1l_ELrblJRphissrNg0g4bg0ThqV0j4pekOM7IQ/viewform"

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
    try:
        all_files.sort(key=lambda x: int(re.search(r'\d+', x).group()))
    except:
        all_files.sort()
    
    if len(all_files) == 0:
        print("❌ Tidak ada file screenshot .png di dalam folder bukti-polling!")
        return
        
    print(f"📦 Ditemukan total {len(all_files)} screenshot untuk diupload.")
    
    # Kelompokkan per 50 file (1 form submit max 50 file dibagi ke 5 tombol)
    batches = [all_files[i:i + 50] for i in range(0, len(all_files), 50)]
    
    user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chrome_data_form")
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
        
    async with async_playwright() as p:
        print("\n🌐 Membuka Google Chrome otomatis...")
        # Menggunakan Chrome asli tanpa perlu tutup browser manual (bebas ribet)
        browser = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            channel="chrome",
            args=["--start-maximized", "--disable-blink-features=AutomationControlled"],
            no_viewport=True
        )
        
        page = browser.pages[0] if browser.pages else await browser.new_page()
        page.set_default_timeout(60000)
        
        for batch_idx, batch_files in enumerate(batches):
            print(f"\n======================================")
            print(f"🚀 Memproses Submit Form ke-{batch_idx + 1} (Membawa {len(batch_files)} Screenshot)")
            print(f"======================================")
            
            await page.goto(FORM_URL)
            
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
            
            # Cari semua tombol upload menggunakan teks biasa (lebih aman dari ARIA)
            add_file_buttons = page.locator('div[role="button"]:has-text("Add file"), div[role="button"]:has-text("Tambahkan file")')
            
            for i, sub_batch in enumerate(sub_batches):
                print(f"   -> Mengupload grup gambar ke-{i+1} ({len(sub_batch)} file)...")
                await page.wait_for_timeout(1000)
                await add_file_buttons.nth(i).click()
                
                print("   -> Menunggu modal upload terbuka...")
                
                uploaded = False
                for attempt in range(15):
                    await page.wait_for_timeout(1000)
                    
                    # 1. Cek di layar utama (Main DOM)
                    try:
                        # Cari teks di elemen APA SAJA (tidak peduli mau tombol atau bukan)
                        btn = page.locator('text=/Browse|Jelajah|Pilih|Cari/i')
                        if await btn.count() > 0:
                            print(f"      [DEBUG] Teks ditemukan di DOM Utama (Jumlah: {await btn.count()}). Mengklik...")
                            async with page.expect_file_chooser(timeout=5000) as fc:
                                await btn.last.click(timeout=3000, force=True)
                            await (await fc.value).set_files(sub_batch)
                            uploaded = True
                            break
                    except Exception as e:
                        if "Timeout 5000ms exceeded" not in str(e):
                            pass
                    
                    # 2. Cek di semua iframe (Iframe DOM)
                    if not uploaded:
                        try:
                            for f in page.frames:
                                btn = f.locator('text=/Browse|Jelajah|Pilih|Cari/i')
                                if await btn.count() > 0:
                                    print(f"      [DEBUG] Teks ditemukan di Iframe! Mengklik...")
                                    async with page.expect_file_chooser(timeout=5000) as fc:
                                        await btn.last.click(timeout=3000, force=True)
                                    await (await fc.value).set_files(sub_batch)
                                    uploaded = True
                                    break
                            if uploaded: break
                        except Exception as e:
                            if "Timeout 5000ms exceeded" not in str(e):
                                pass
                
                if not uploaded:
                    print("❌ GAGAL MENGUPLOAD! Tidak bisa menemukan tombol Browse/Jelajahi.")
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
            await page.wait_for_timeout(3000)
            
        print("\n🎉 SELAMAT! SEMUA BUKTI POLLING TELAH SELESAI DI-SUBMIT KE GOOGLE FORM!")
        # Tidak usah ditutup browser aslinya
        # await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
