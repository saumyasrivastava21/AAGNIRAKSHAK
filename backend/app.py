# app.py — AGNI RAKSHAK FastAPI Backend  (FINAL)
# ─────────────────────────────────────────────
# TCP 5678  ← Cooja Serial Socket CLIENT connects here
# UDP 5679  ← optional fallback
# GET  /    ← serves the dashboard (index.html)
# WS   /ws  ← real-time pushes to frontend
# GET  /data /history /stats /health /log

import sys
import os
import socket
import threading
import asyncio
from datetime import datetime
from collections import deque

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from cooja_parser import parse_cooja_line, SensorAccumulator
from predictor import predict_fire

app = FastAPI(title="AGNI RAKSHAK API 🔥", docs_url="/docs")

# ── CORS ──────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Paths ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "frontend"))

# ── Shared State ──────────────────────────────────────
latest_result: dict = {}
prediction_history: deque = deque(maxlen=100)
raw_log: deque = deque(maxlen=200)
connected_clients: list = []
_event_loop: asyncio.AbstractEventLoop = None  # type: ignore

stats = {
    "total_predictions": 0,
    "fire_detections": 0,
    "safe_readings": 0,
    "server_start": None,
    "last_reading": None,
    "cooja_connected": False,
}

HOST = "0.0.0.0"
TCP_PORT = 5678
UDP_PORT = 5679


# ──────────────────────────────────────────────────────
# Logging helper — always flush so output appears live
# ──────────────────────────────────────────────────────
def log(*args):
    print(*args, flush=True)


# ──────────────────────────────────────────────────────
# WebSocket broadcast
# ──────────────────────────────────────────────────────
async def _broadcast(payload: dict):
    dead = []
    for ws in list(connected_clients):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in connected_clients:
            connected_clients.remove(ws)


def sync_broadcast(payload: dict):
    if _event_loop and _event_loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast(payload), _event_loop)


# ──────────────────────────────────────────────────────
# Core message processor (shared by TCP + UDP)
# ──────────────────────────────────────────────────────
def process_message(msg: str, accumulator: SensorAccumulator, source: str):
    global latest_result

    timestamp = datetime.now().isoformat()

    for line in msg.splitlines():
        line = line.strip()
        if not line:
            continue

        # ── Sink heartbeat (printed by sink.c on startup) ────
        if line == "SINK_READY":
            log(f"💚 Sink node READY signal received from {source}")
            sync_broadcast({"type": "sink_ready", "source": source})
            continue

        log(f"\n📡 [{timestamp}] {source} → {line!r}")
        raw_log.append({"timestamp": timestamp, "raw": line, "source": source})

        parsed = parse_cooja_line(line)
        if parsed is None:
            log(f"   ⚠️  Unrecognised: {line!r}")
            continue

        sensor_type, value = parsed

        if sensor_type == "json":
            log(f"   📦 JSON parsed: temp={value.get('temp') or value.get('temperature')} "
                f"hum={value.get('humidity') or value.get('rh')} "
                f"wind={value.get('wind') or value.get('ws')}")
            complete = accumulator.add_json(value)
        else:
            log(f"   ✅ {sensor_type.upper()} = {value}")
            complete = accumulator.add_reading(sensor_type, value)
            sync_broadcast({
                "type": "sensor_reading",
                "sensor": sensor_type,
                "value": value,
                "timestamp": timestamp,
            })

        if complete:
            result = predict_fire(complete["temp"], complete["rh"], complete["ws"])
            result["timestamp"] = timestamp

            # Attach extra fields from sensor if present
            extras = {k: complete[k] for k in ("moisture", "ph", "light", "node")
                      if k in complete}
            if extras:
                result["extra"] = extras
                log(f"   🌿 Extras: {extras}")

            latest_result = result
            prediction_history.appendleft(result)

            stats["total_predictions"] += 1
            stats["last_reading"] = timestamp
            if result.get("is_fire"):
                stats["fire_detections"] += 1
            else:
                stats["safe_readings"] += 1

            icon = "🔥" if result["is_fire"] else "✅"
            log(
                f"\n{icon} PREDICTION #{stats['total_predictions']}: "
                f"{result['prediction']} | "
                f"conf={result['confidence']}% | "
                f"risk={result['risk_level']}"
            )
            log(f"   Temp={complete['temp']}°C  RH={complete['rh']}%  WS={complete['ws']}km/h\n")

            sync_broadcast({"type": "prediction", "data": result})


# ──────────────────────────────────────────────────────
# TCP handler — one thread per Cooja connection
# ──────────────────────────────────────────────────────
def tcp_client_handler(conn: socket.socket, addr):
    source = f"{addr[0]}:{addr[1]}"
    log(f"\n🔌 Cooja CONNECTED from {source}")
    stats["cooja_connected"] = True
    sync_broadcast({"type": "cooja_connected", "source": source})

    accumulator = SensorAccumulator()
    buf = ""
    chunk_count = 0  # For debug logging

    try:
        conn.settimeout(5.0)
        while True:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                continue
            if not chunk:
                break

            chunk_count += 1
            # Log first 5 raw chunks verbosely so we can diagnose format issues
            if chunk_count <= 5:
                log(f"🔬 RAW chunk #{chunk_count} ({len(chunk)} bytes): {chunk!r}")

            text = chunk.decode(errors="replace")
            buf += text

            # Process complete lines
            while "\n" in buf:
                line, buf = buf.split("\n", 1)
                stripped = line.strip()
                if stripped:
                    process_message(stripped, accumulator, source)

    except Exception as e:
        log(f"❌ TCP handler error ({source}): {e}")
    finally:
        conn.close()
        stats["cooja_connected"] = False
        sync_broadcast({"type": "cooja_disconnected"})
        log(f"\n🔌 Cooja DISCONNECTED from {source}")

    # Flush anything left in buffer
    if buf.strip():
        process_message(buf.strip(), accumulator, source)


# ──────────────────────────────────────────────────────
# TCP Server Thread
# ──────────────────────────────────────────────────────
def tcp_listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        srv.bind((HOST, TCP_PORT))
    except OSError as e:
        log(f"❌ Cannot bind TCP {HOST}:{TCP_PORT} — {e}")
        return

    srv.listen(5)
    log("=" * 60)
    log(f"🚀 TCP Server ready on {HOST}:{TCP_PORT}")
    log(f"   Cooja → Mote tools → Serial Socket (CLIENT)")
    log(f"   Host: 127.0.0.1   Port: {TCP_PORT}")
    log("=" * 60)

    while True:
        try:
            conn, addr = srv.accept()
            t = threading.Thread(
                target=tcp_client_handler, args=(conn, addr), daemon=True
            )
            t.start()
        except Exception as e:
            log(f"❌ TCP accept error: {e}")


# ──────────────────────────────────────────────────────
# UDP Listener (fallback, port 5679)
# ──────────────────────────────────────────────────────
def udp_listener():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((HOST, UDP_PORT))
    except OSError as e:
        log(f"⚠️  UDP {UDP_PORT} unavailable: {e}")
        return

    log(f"📡 UDP fallback listening on {HOST}:{UDP_PORT}")
    accumulator = SensorAccumulator()

    while True:
        try:
            raw, addr = sock.recvfrom(4096)
            msg = raw.decode(errors="replace").strip()
            if msg:
                process_message(msg, accumulator, f"{addr[0]}:{addr[1]}(udp)")
        except Exception as e:
            log(f"❌ UDP error: {e}")


# ──────────────────────────────────────────────────────
# Startup
# ──────────────────────────────────────────────────────
@app.on_event("startup")
async def on_startup():
    global _event_loop
    _event_loop = asyncio.get_running_loop()
    stats["server_start"] = datetime.now().isoformat()

    threading.Thread(target=tcp_listener, daemon=True).start()
    threading.Thread(target=udp_listener, daemon=True).start()

    log("\n" + "=" * 60)
    log("🌐 AGNI RAKSHAK API READY")
    log(f"   Dashboard:  http://127.0.0.1:8000/")
    log(f"   API docs:   http://127.0.0.1:8000/docs")
    log(f"   Cooja TCP:  127.0.0.1:{TCP_PORT}")
    log("=" * 60 + "\n")


# ──────────────────────────────────────────────────────
# WebSocket
# ──────────────────────────────────────────────────────
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    log(f"🔗 WS client connected ({len(connected_clients)} total)")

    # Send full current state immediately
    await ws.send_json({
        "type": "init",
        "latest": latest_result,
        "history": list(prediction_history),
        "stats": stats,
    })

    try:
        while True:
            txt = await ws.receive_text()
            if txt == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)
        log(f"🔌 WS disconnected ({len(connected_clients)} total)")


# ──────────────────────────────────────────────────────
# REST Endpoints
# ──────────────────────────────────────────────────────
@app.get("/data")
def get_data():
    return {"latest": latest_result, "count": len(prediction_history)}


@app.get("/history")
def get_history():
    return {"count": len(prediction_history), "results": list(prediction_history)}


@app.get("/stats")
def get_stats():
    return stats


@app.get("/log")
def get_log():
    return {"count": len(raw_log), "entries": list(raw_log)}


@app.get("/debug")
def debug_state():
    """Debug endpoint — shows current internal state."""
    return {
        "latest_result": latest_result,
        "history_count": len(prediction_history),
        "raw_log_count": len(raw_log),
        "ws_clients": len(connected_clients),
        "cooja_connected": stats["cooja_connected"],
        "event_loop_alive": _event_loop is not None and _event_loop.is_running(),
    }


@app.post("/test")
async def inject_test_data(
    temp: float = 75.0,
    rh: float = 30.0,
    ws: float = 15.0
):
    """
    Inject a fake sensor reading to test the full pipeline without Cooja.
    Usage: POST http://127.0.0.1:8000/test?temp=75&rh=30&ws=15
    """
    global latest_result
    timestamp = datetime.now().isoformat()
    result = predict_fire(temp, rh, ws)
    result["timestamp"] = timestamp

    latest_result = result
    prediction_history.appendleft(result)
    stats["total_predictions"] += 1
    stats["last_reading"] = timestamp
    if result.get("is_fire"):
        stats["fire_detections"] += 1
    else:
        stats["safe_readings"] += 1

    raw_log.append({"timestamp": timestamp, "raw": f"TEST INJECT: temp={temp} rh={rh} ws={ws}", "source": "test"})

    # Push to all WebSocket clients
    await _broadcast({"type": "prediction", "data": result})

    log(f"🧪 TEST INJECT: temp={temp} rh={rh} ws={ws} → {result['prediction']}")
    return {"status": "ok", "result": result}


@app.get("/health")
def health():
    return {
        "status": "OK",
        "uptime_since": stats["server_start"],
        "predictions": stats["total_predictions"],
        "websocket_clients": len(connected_clients),
        "cooja_connected": stats["cooja_connected"],
        "cooja_tcp_port": TCP_PORT,
    }

# ──────────────────────────────────────────────────────
# Frontend Static Files (Must be at the very bottom!)
# ──────────────────────────────────────────────────────
if os.path.isdir(FRONTEND_DIR):
    # Mounts the whole frontend directory at root so /app.js and /style.css resolve natively
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    log(f"🖥️  Frontend directory mounted at root: {FRONTEND_DIR}")