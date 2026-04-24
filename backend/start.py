# start.py — AGNI RAKSHAK Clean Launcher  (FINAL)
# Always run this instead of uvicorn directly.
# Usage:  python start.py

import subprocess
import sys
import os
import time

# Force UTF-8 stdout to fix Windows encodings for emojis
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')


def kill_port(port: int):
    """Kill ALL processes listening on a TCP port (Windows)."""
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True
        )
        killed = []
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit() and pid != "0":
                    subprocess.run(
                        ["taskkill", "/PID", pid, "/F"],
                        capture_output=True
                    )
                    killed.append(pid)
        if killed:
            print(f"   🗑️  Killed PIDs {killed} holding port {port}")
        else:
            print(f"   ✅ Port {port} is free")
    except Exception as e:
        print(f"   ⚠️  Could not free port {port}: {e}")


def main():
    print("=" * 55)
    print("🔥  AGNI RAKSHAK — Starting")
    print("=" * 55)

    # 1. Kill stale processes
    print("\n🧹 Freeing ports...")
    kill_port(8000)
    kill_port(5678)
    time.sleep(2)   # Let OS fully release sockets

    # 2. Launch uvicorn — inherit stdout/stderr so we see all logs
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--log-level", "info",
    ]

    print(f"\n🚀 Starting server...")
    print(f"   cmd: {' '.join(cmd)}\n")

    # Force UTF-8 encoding in the subprocess so emojis don't crash it
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    # No capture — output goes directly to this terminal window
    proc = subprocess.Popen(cmd, cwd=backend_dir, env=env)

    print("\n" + "─" * 55)
    print("  Dashboard  →  http://127.0.0.1:8000/")
    print("  API Docs   →  http://127.0.0.1:8000/docs")
    print(f"  Cooja TCP  →  127.0.0.1:5678")
    print("─" * 55)
    print("  Press CTRL+C to stop\n")

    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        proc.terminate()
        proc.wait()
        print("✅ Stopped cleanly.")


if __name__ == "__main__":
    main()
