#!/usr/bin/env python3
"""
Orchestrator polling CX100:
- Menghasilkan/memuat target 5000 email (Gmail Dot Trick).
- Secara dinamis membagi email yang belum sukses polling ke dalam batch berisi 150 email.
- Menjalankan poll_danantara.py untuk memproses batch email tersebut.
- Menyimpan status email yang sukses ke polling_success_emails.json untuk menghindari dobel proses.
- Jika screenshot yang terkumpul dan belum dikirim (pending) mencapai >= 150, otomatis men-trigger submit_gform.py.
- Jika terjadi error/timeout, otomatis melakukan rerun dan lanjut dari data terakhir.

Jalankan dengan:
  cd /home/rafli/auto-pooling
  PYTHONUNBUFFERED=1 python3 orchestrator_5000.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EMAIL_FILE = BASE_DIR / "email.txt"
MASTER_EMAIL_FILE = BASE_DIR / "email_master_5000.txt"
STATE_FILE = BASE_DIR / "orchestrator_state.json"
SCREENSHOT_DIR = BASE_DIR / "bukti-polling"
SUBMITTED_GFORM_STATE = BASE_DIR / "submitted_gform.json"
POLLING_SUCCESS_STATE_FILE = BASE_DIR / "polling_success_emails.json"

POLL_SCRIPT = BASE_DIR / "poll_danantara.py"
SUBMIT_SCRIPT = BASE_DIR / "submit_gform.py"

BASE_EMAIL = "rafliabdulbayhaqqy"
DOMAIN_EMAIL = "@googlemail.com"
TARGET_EMAILS = 5000
SUBMIT_TRIGGER = 50
POLL_BATCH_SIZE = 50
MAX_POLL_ATTEMPTS_PER_BATCH = 5
POLL_TIMEOUT_SECONDS = 3 * 60 * 60
SUBMIT_TIMEOUT_SECONDS = 60 * 60
RESTART_DELAY_SECONDS = 10

SCREENSHOT_RE = re.compile(r"_(\d+)\.png$")


def log(message: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] {message}", flush=True)


def run_command(cmd: list[str], timeout: int) -> int:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    log("▶️ RUN: " + " ".join(cmd))
    process = subprocess.Popen(cmd, cwd=str(BASE_DIR), env=env)
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        log(f"⏰ Timeout {timeout}s. Kill process: {' '.join(cmd)}")
        process.kill()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.terminate()
        return 124


def generate_dot_variants(base_username: str, limit: int) -> list[str]:
    variants: list[str] = []
    n = len(base_username) - 1
    max_variants = 2 ** n
    for i in range(min(limit, max_variants)):
        binary = bin(i)[2:].zfill(n)
        variant = base_username[0]
        for j, bit in enumerate(binary):
            if bit == "1":
                variant += "."
            variant += base_username[j + 1]
        variants.append(f"{variant}{DOMAIN_EMAIL}")
    return variants


def ensure_master_emails() -> list[str]:
    if MASTER_EMAIL_FILE.exists():
        emails = [line.strip() for line in MASTER_EMAIL_FILE.read_text().splitlines() if line.strip()]
        if len(emails) >= TARGET_EMAILS:
            return emails[:TARGET_EMAILS]
        log(f"⚠️ {MASTER_EMAIL_FILE.name} hanya berisi {len(emails)} email. Generate ulang {TARGET_EMAILS} email.")

    emails = generate_dot_variants(BASE_EMAIL, TARGET_EMAILS)
    MASTER_EMAIL_FILE.write_text("\n".join(emails) + "\n")
    log(f"✅ Master email dibuat: {MASTER_EMAIL_FILE} ({len(emails)} email)")
    return emails


def load_success_emails() -> set[str]:
    if not POLLING_SUCCESS_STATE_FILE.exists():
        return set()
    try:
        data = json.loads(POLLING_SUCCESS_STATE_FILE.read_text())
        return set(data.get("success_emails", []))
    except Exception:
        return set()


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {
            "completed_submit_batches": 0,
            "last_submit_at": None,
        }
    try:
        state = json.loads(STATE_FILE.read_text())
    except Exception:
        backup = STATE_FILE.with_suffix(f".broken.{int(time.time())}.json")
        shutil.copy2(STATE_FILE, backup)
        log(f"⚠️ State orchestrator rusak, backup ke {backup}.")
        return {
            "completed_submit_batches": 0,
            "last_submit_at": None,
        }
    return state


def save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_FILE)


def screenshot_number(path: Path) -> int:
    match = SCREENSHOT_RE.search(path.name)
    return int(match.group(1)) if match else 0


def all_screenshots() -> list[Path]:
    if not SCREENSHOT_DIR.exists():
        return []
    files = [p for p in SCREENSHOT_DIR.glob("*.png") if p.is_file()]
    return sorted(files, key=screenshot_number)


def submitted_screenshots() -> set[str]:
    if not SUBMITTED_GFORM_STATE.exists():
        return set()
    try:
        data = json.loads(SUBMITTED_GFORM_STATE.read_text())
        return {os.path.abspath(x) for x in data.get("submitted_files", [])}
    except Exception:
        return set()


def pending_screenshots() -> list[Path]:
    submitted = submitted_screenshots()
    return [p for p in all_screenshots() if os.path.abspath(p) not in submitted]


def get_pending_emails(master_emails: list[str]) -> list[str]:
    success_set = load_success_emails()
    return [email for email in master_emails if email not in success_set]


def poll_command() -> list[str]:
    if sys.platform.startswith("linux") and Path("/usr/bin/xvfb-run").exists():
        return ["/usr/bin/xvfb-run", "-a", sys.executable, str(POLL_SCRIPT)]
    return [sys.executable, str(POLL_SCRIPT)]


def submit_command() -> list[str]:
    if sys.platform.startswith("linux") and Path("/usr/bin/xvfb-run").exists():
        return ["/usr/bin/xvfb-run", "-a", sys.executable, str(SUBMIT_SCRIPT)]
    return [sys.executable, str(SUBMIT_SCRIPT)]


def run_poll_batch_until_progress(master_emails: list[str]) -> None:
    pending_emails = get_pending_emails(master_emails)
    if not pending_emails:
        log("✅ Semua email 5000 target sudah sukses polling.")
        return

    batch = pending_emails[:POLL_BATCH_SIZE]
    EMAIL_FILE.write_text("\n".join(batch) + "\n")
    log(f"📧 Mempersiapkan {len(batch)} email untuk polling batch (Sisa antrean total: {len(pending_emails)})")

    success_before = len(load_success_emails())

    for attempt in range(1, MAX_POLL_ATTEMPTS_PER_BATCH + 1):
        log(f"🚀 Polling batch berjalan. Attempt {attempt}/{MAX_POLL_ATTEMPTS_PER_BATCH}")
        code = run_command(poll_command(), timeout=POLL_TIMEOUT_SECONDS)
        
        success_after = len(load_success_emails())
        gained = success_after - success_before
        log(f"📊 Hasil polling attempt {attempt}: exit={code}, sukses baru={gained}, total sukses={success_after}")

        if gained > 0:
            return

        log(f"⚠️ Tidak ada kemajuan sukses di batch ini. Rerun polling dalam {RESTART_DELAY_SECONDS}s...")
        time.sleep(RESTART_DELAY_SECONDS)

    log("🚨 Peringatan: Batch ini gagal mendapatkan sukses baru setelah percobaan maksimal. Melanjutkan ke antrean berikutnya.")


def run_submit_if_needed(force: bool = False) -> bool:
    pending = pending_screenshots()
    if not force and len(pending) < SUBMIT_TRIGGER:
        log(f"📦 Pending screenshot {len(pending)}/{SUBMIT_TRIGGER}. Belum mencapai batas submit.")
        return False
    if not pending:
        log("✅ Tidak ada screenshot pending untuk di-submit.")
        return False

    log(f"📤 Trigger submit aktif: Ada {len(pending)} screenshot pending. Menjalankan submit_gform.py...")
    code = run_command(submit_command(), timeout=SUBMIT_TIMEOUT_SECONDS)
    if code != 0:
        log(f"⚠️ submit_gform.py keluar dengan exit code {code}. Akan dicoba lagi nanti.")
        return False

    still_pending = pending_screenshots()
    log(f"📊 Proses submit form selesai. Screenshot pending tersisa: {len(still_pending)}")
    return len(still_pending) < len(pending)


def main() -> None:
    log("🚀 Orchestrator CX100 5000 Email dimulai")
    log(f"🎯 Target total email: {TARGET_EMAILS} | Trigger submit per {SUBMIT_TRIGGER} screenshot")

    if not POLL_SCRIPT.exists():
        raise FileNotFoundError(POLL_SCRIPT)
    if not SUBMIT_SCRIPT.exists():
        raise FileNotFoundError(SUBMIT_SCRIPT)

    SCREENSHOT_DIR.mkdir(exist_ok=True)
    master_emails = ensure_master_emails()
    state = load_state()
    save_state(state)

    while True:
        # Cek apakah jumlah screenshot pending memenuhi syarat submit 50
        if len(pending_screenshots()) >= SUBMIT_TRIGGER:
            if run_submit_if_needed(force=False):
                state = load_state()
                state["completed_submit_batches"] = state.get("completed_submit_batches", 0) + 1
                state["last_submit_at"] = datetime.now().isoformat()
                save_state(state)
            time.sleep(3)
            continue

        # Ambil email yang belum dipolling
        pending_emails = get_pending_emails(master_emails)
        if not pending_emails:
            break

        # Jalankan polling batch
        run_poll_batch_until_progress(master_emails)

    log("🏁 Semua email target sudah sukses polling. Mengecek sisa screenshot pending...")
    while pending_screenshots():
        if not run_submit_if_needed(force=True):
            log("⚠️ Gagal men-submit sisa screenshot. Retry kembali setelah jeda...")
            time.sleep(RESTART_DELAY_SECONDS)
        else:
            state = load_state()
            state["completed_submit_batches"] = state.get("completed_submit_batches", 0) + 1
            state["last_submit_at"] = datetime.now().isoformat()
            save_state(state)

    log("🎉 SELESAI: 5000 email berhasil diproses polling dan seluruh bukti telah di-submit ke Google Form!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("👋 Orchestrator dihentikan manual oleh user.")
    except Exception as exc:
        log(f"💥 Orchestrator fatal error: {exc}")
        raise
