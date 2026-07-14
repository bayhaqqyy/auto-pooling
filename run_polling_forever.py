import subprocess
import time
import sys

# Wrapper script to run the bot forever
# If python script crashes, it will restart after a brief delay
def main():
    cmd = ["/usr/bin/xvfb-run", "-a", "/home/rafli/auto-pooling/.venv/bin/python", "poll_danantara.py"]
    print("🚀 Starting auto-pooling runner via xvfb-run virtual display...")
    
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
