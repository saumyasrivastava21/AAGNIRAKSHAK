# udp_server.py — Standalone TCP/UDP listener for testing WITHOUT the FastAPI app
# ──────────────────────────────────────────────────────────────────────────────
# ⚠️  DO NOT run this while app.py (uvicorn) is running — port conflict!
#
# Cooja setup (Serial Socket):
#   Right-click sink mote → Mote tools → Serial Socket (CLIENT)
#   Host: 127.0.0.1   Port: 5678   (TCP)
# ──────────────────────────────────────────────────────────────────────────────

import socket
import threading
from cooja_parser import parse_cooja_line, SensorAccumulator
from predictor import predict_fire

PORT = 5678
prediction_count = 0


def handle_client(conn, addr):
    global prediction_count
    source = f"{addr[0]}:{addr[1]}"
    print(f"🔌 Cooja connected from {source}")
    accumulator = SensorAccumulator()
    buf = ""

    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buf += chunk.decode(errors="replace")

            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                line = line.strip()
                if not line:
                    continue

                print(f"📡 Raw: {line!r}")
                parsed = parse_cooja_line(line)

                if parsed is None:
                    print(f"   ⚠️  Unrecognised: {line!r}")
                    continue

                sensor_type, value = parsed

                if sensor_type == "json":
                    complete = accumulator.add_json(value)
                else:
                    print(f"   ✅ {sensor_type.upper()} = {value}")
                    complete = accumulator.add_reading(sensor_type, value)

                if complete:
                    prediction_count += 1
                    result = predict_fire(complete["temp"], complete["rh"], complete["ws"])
                    print(f"\n{'=' * 50}")
                    print(f"🔬 PREDICTION #{prediction_count}")
                    print(f"   Temperature : {complete['temp']} °C")
                    print(f"   Humidity    : {complete['rh']} %")
                    print(f"   Wind Speed  : {complete['ws']} km/h")
                    print(f"   Result      : {result['prediction']}")
                    print(f"   Confidence  : {result['confidence']} %")
                    print(f"   Risk Level  : {result['risk_level']}")
                    print(f"{'=' * 50}\n")

    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()
        print(f"🔌 Disconnected: {source}")


srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

try:
    srv.bind((HOST, PORT))
except OSError as e:
    print(f"❌ Cannot bind {HOST}:{PORT}: {e}")
    print("   Is app.py (uvicorn) already running? Stop it first.")
    raise SystemExit(1)

srv.listen(5)
print("=" * 60)
print("🚀 AGNI RAKSHAK — Standalone TCP Server")
print(f"📡 Listening on {HOST}:{PORT}  (TCP)")
print()
print("  Cooja: right-click sink mote")
print("  → Mote tools → Serial Socket (CLIENT)")
print(f"  → Host: 127.0.0.1   Port: {PORT}")
print("=" * 60)

try:
    while True:
        conn, addr = srv.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()
except KeyboardInterrupt:
    print("\n👋 Stopped.")