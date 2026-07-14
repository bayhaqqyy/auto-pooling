import subprocess
import time
import sys
import os
import platform

# Wrapper script to run the bot forever
# If python script crashes, it will restart after a brief delay
def main():
    # Deteksi operating system
    is_windows = platform.system().lower() == "windows"
    
    # Tentukan command python yang sesuai dengan environment lokal/server
    # Cari venv python path yang ada
    current_dir = os.path.dirname(os.path.abspath(__file__))
    venv_python = os.path.join(current_dir, ".venv", "Scripts", "python.exe") if is_windows else os.path.join(current_dir, ".venv", "bin", "python")
    
    if not os.path.exists(venv_python):
        # Fallback ke python global jika venv belum di-setup di lokal
        venv_python = sys.executable

    if is_windows:
        cmd = [venv_python, "poll_danantara.py"]
        print("🚀 Starting auto-pooling runner on Windows...")
    else:
        # Jika Linux, gunakan xvfb-run
        cmd = ["/usr/bin/xvfb-run", "-a", venv_python, "poll_danantara.py"]
        print("🚀 Starting auto-pooling runner on Linux via xvfb-run virtual display...")
    
    while True:
        try:
            process = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
            process.wait()
            print(f"\n⚠️ Process exited with code {process.returncode}. Restarting in 5 seconds...")
        except KeyboardInterrupt:
            print("\n👋 Stopping runner.")
            break
        except Exception as e:
            print(f"\n💥 Error running process: {e}. Restarting in 5 seconds...")
        time.sleep(5)

if __name__ == "__main__":
    main()
