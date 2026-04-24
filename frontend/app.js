// ══════════════════════════════════════════════════════
// AGNI RAKSHAK — Dashboard Application Logic
// ══════════════════════════════════════════════════════

const API_BASE = window.location.origin;
const WS_URL = `ws://${window.location.host}/ws`;

// ── State ────────────────────────────────────────────
const state = {
    connected: false,
    ws: null,
    latest: null,
    history: [],
    stats: {
        total_predictions: 0,
        fire_detections: 0,
        safe_readings: 0
    },
    sensorBuffer: {
        temp: null,
        rh: null,
        ws: null
    },
    chartData: {
        labels: [],
        temp: [],
        humidity: [],
        wind: [],
        risk: []
    },
    logs: [],
    reconnectAttempts: 0,
    maxReconnectAttempts: 50,
    reconnectDelay: 2000
};

// ── DOM Elements ─────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

// ── Initialize ───────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    initClock();
    initChart();
    connectWebSocket();
    startPollingFallback();
});

// ── Clock ────────────────────────────────────────────
function initClock() {
    const el = $("#time-display");
    if (!el) return;
    
    function update() {
        const now = new Date();
        el.textContent = now.toLocaleTimeString("en-IN", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
            hour12: false
        });
    }
    update();
    setInterval(update, 1000);
}

// ── WebSocket ────────────────────────────────────────
function connectWebSocket() {
    try {
        state.ws = new WebSocket(WS_URL);

        state.ws.onopen = () => {
            state.connected = true;
            state.reconnectAttempts = 0;
            updateConnectionStatus(true);
            addLog("info", "Connected to AGNI RAKSHAK backend");
            showToast("info", "🔗 Connected to server");
        };

        state.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleWSMessage(msg);
            } catch (e) {
                console.error("WS parse error:", e);
            }
        };

        state.ws.onclose = () => {
            state.connected = false;
            updateConnectionStatus(false);
            addLog("sensor", "Disconnected from server");
            attemptReconnect();
        };

        state.ws.onerror = (err) => {
            console.error("WS error:", err);
            state.connected = false;
            updateConnectionStatus(false);
        };

        // Keep alive
        setInterval(() => {
            if (state.ws && state.ws.readyState === WebSocket.OPEN) {
                state.ws.send("ping");
            }
        }, 30000);

    } catch (e) {
        console.error("WS connection failed:", e);
        updateConnectionStatus(false);
        attemptReconnect();
    }
}

function attemptReconnect() {
    if (state.reconnectAttempts >= state.maxReconnectAttempts) {
        addLog("sensor", "Max reconnect attempts reached. Using REST fallback.");
        return;
    }

    state.reconnectAttempts++;
    const delay = Math.min(state.reconnectDelay * state.reconnectAttempts, 10000);

    setTimeout(() => {
        console.log(`Reconnecting... attempt ${state.reconnectAttempts}`);
        connectWebSocket();
    }, delay);
}

function handleWSMessage(msg) {
    switch (msg.type) {
        case "init":
            // Initial state from server
            if (msg.latest && Object.keys(msg.latest).length > 0) {
                state.latest = msg.latest;
                updateRiskPanel(msg.latest);
                updateStatCards(msg.latest);
            }
            if (msg.history) {
                state.history = msg.history;
                updateHistoryTable();
                rebuildChart();
            }
            if (msg.stats) {
                state.stats = msg.stats;
                updatePredictionCount();
            }
            break;

        case "sensor_reading":
            // Partial sensor data
            state.sensorBuffer[msg.sensor] = msg.value;
            updateSensorNode(msg.sensor, msg.value);
            addLog("sensor", `${msg.sensor.toUpperCase()}: ${msg.value}`);
            break;

        case "prediction":
            // Full prediction result
            state.latest = msg.data;
            state.history.unshift(msg.data);
            if (state.history.length > 100) state.history.pop();

            state.stats.total_predictions++;
            if (msg.data.is_fire) {
                state.stats.fire_detections++;
            } else {
                state.stats.safe_readings++;
            }

            updateRiskPanel(msg.data);
            updateStatCards(msg.data);
            updatePredictionCount();
            updateHistoryTable();
            addChartData(msg.data);

            // Toast notification
            if (msg.data.is_fire) {
                showToast("fire", `🔥 FIRE DETECTED — Confidence: ${msg.data.confidence}%`);
                addLog("fire", `FIRE DETECTED! Temp: ${msg.data.input.temperature}°C, RH: ${msg.data.input.humidity}%, Wind: ${msg.data.input.wind_speed} km/h`);
            } else {
                addLog("safe", `SAFE — Temp: ${msg.data.input.temperature}°C, RH: ${msg.data.input.humidity}%, Wind: ${msg.data.input.wind_speed} km/h`);
            }
            break;

        case "cooja_connected":
            addLog("safe", `Cooja sink connected from ${msg.source || 'unknown'}`);
            showToast("info", `📡 Cooja connected — ${msg.source || ''}`);
            break;

        case "sink_ready":
            addLog("safe", "Sink node is online and forwarding data");
            showToast("info", "💚 Sink node READY");
            break;

        case "cooja_disconnected":
            addLog("sensor", "Cooja sink disconnected");
            showToast("info", "🔌 Cooja disconnected");
            break;

        case "pong":
            break;
    }
}

// ── REST Polling Fallback ────────────────────────────
function startPollingFallback() {
    setInterval(async () => {
        if (state.connected) return; // Use WS if connected

        try {
            const res = await fetch(`${API_BASE}/data`);
            const data = await res.json();
            if (data.latest && Object.keys(data.latest).length > 0) {
                state.latest = data.latest;
                updateRiskPanel(data.latest);
                updateStatCards(data.latest);
            }

            const histRes = await fetch(`${API_BASE}/history`);
            const histData = await histRes.json();
            if (histData.results) {
                state.history = histData.results;
                updateHistoryTable();
            }

            const statsRes = await fetch(`${API_BASE}/stats`);
            state.stats = await statsRes.json();
            updatePredictionCount();

            updateConnectionStatus(true, "REST");
        } catch (e) {
            updateConnectionStatus(false);
        }
    }, 3000);
}

// ── UI Updates ───────────────────────────────────────

function updateConnectionStatus(connected, mode = "WS") {
    const badge = $("#connection-badge");
    if (!badge) return;

    if (connected) {
        badge.className = "connection-badge connected";
        badge.innerHTML = `<span class="connection-dot"></span>${mode} LIVE`;
    } else {
        badge.className = "connection-badge disconnected";
        badge.innerHTML = `<span class="connection-dot"></span>OFFLINE`;
    }
}

function updateRiskPanel(data) {
    const panel = $("#risk-panel");
    if (!panel || !data) return;

    const isFire = data.is_fire;
    const riskLevel = data.risk_level || "UNKNOWN";

    // Update risk state class
    panel.className = `risk-panel ${isFire ? "danger" : "safe"}`;

    // Update emoji and label
    const emoji = $("#risk-emoji");
    const label = $("#risk-label");
    const confidence = $("#risk-confidence");

    if (emoji) emoji.textContent = isFire ? "🔥" : "✅";
    if (label) label.textContent = isFire ? "FIRE DETECTED" : "ALL SAFE";
    if (confidence) confidence.textContent = `Confidence: ${data.confidence || 0}% • ${riskLevel}`;

    // Update details
    const input = data.input || {};
    const tempEl = $("#detail-temp");
    const rhEl = $("#detail-rh");
    const wsEl = $("#detail-ws");

    if (tempEl) tempEl.textContent = `${input.temperature || "--"}°C`;
    if (rhEl) rhEl.textContent = `${input.humidity || "--"}%`;
    if (wsEl) wsEl.textContent = `${input.wind_speed || "--"} km/h`;
}

function updateStatCards(data) {
    if (!data || !data.input) return;

    const input = data.input;
    const extra = data.extra || {};

    // Temperature
    const tempVal = $("#stat-temp-value");
    const tempGauge = $("#gauge-temp");
    if (tempVal) tempVal.textContent = input.temperature || "--";
    if (tempGauge) tempGauge.style.width = `${Math.min((input.temperature / 100) * 100, 100)}%`;

    // Humidity
    const rhVal = $("#stat-rh-value");
    const rhGauge = $("#gauge-rh");
    if (rhVal) rhVal.textContent = input.humidity || "--";
    if (rhGauge) rhGauge.style.width = `${Math.min(input.humidity, 100)}%`;

    // Wind speed
    const wsVal = $("#stat-ws-value");
    const wsGauge = $("#gauge-ws");
    if (wsVal) wsVal.textContent = input.wind_speed || "--";
    if (wsGauge) wsGauge.style.width = `${Math.min((input.wind_speed / 50) * 100, 100)}%`;

    // Moisture (extra)
    if (extra.moisture !== undefined) {
        const el = $("#stat-moisture-value");
        const g  = $("#gauge-moisture");
        if (el) el.textContent = extra.moisture;
        if (g)  g.style.width = `${Math.min(extra.moisture, 100)}%`;
    }

    // pH (extra)
    if (extra.ph !== undefined) {
        const el = $("#stat-ph-value");
        const g  = $("#gauge-ph");
        if (el) el.textContent = extra.ph;
        if (g)  g.style.width = `${Math.min((extra.ph / 14) * 100, 100)}%`;
    }

    // Light (extra)
    if (extra.light !== undefined) {
        const el = $("#stat-light-value");
        const g  = $("#gauge-light");
        if (el) el.textContent = extra.light;
        if (g)  g.style.width = `${Math.min((extra.light / 1000) * 100, 100)}%`;
    }

    // Animate sensor nodes
    updateSensorNode("temp", input.temperature);
    updateSensorNode("rh", input.humidity);
    updateSensorNode("ws", input.wind_speed);
}

function updatePredictionCount() {
    const el = $("#stat-pred-value");
    if (el) el.textContent = state.stats.total_predictions || 0;

    const fireEl = $("#fire-count");
    const safeEl = $("#safe-count");
    if (fireEl) fireEl.textContent = state.stats.fire_detections || 0;
    if (safeEl) safeEl.textContent = state.stats.safe_readings || 0;
}

function updateSensorNode(type, value) {
    // Update sensor grid nodes
    const nodes = $$(`[data-sensor="${type}"]`);
    nodes.forEach(node => {
        node.classList.add("active");
        const valEl = node.querySelector(".sensor-node-value");
        if (valEl) {
            let unit = "";
            if (type === "temp") unit = "°C";
            else if (type === "rh") unit = "%";
            else if (type === "ws") unit = " km/h";
            valEl.textContent = `${value}${unit}`;
        }

        // Flash animation
        node.style.transition = "none";
        node.style.boxShadow = type === "temp"
            ? "0 0 20px rgba(255, 100, 0, 0.3)"
            : type === "rh"
            ? "0 0 20px rgba(68, 138, 255, 0.3)"
            : "0 0 20px rgba(0, 230, 118, 0.3)";
        
        setTimeout(() => {
            node.style.transition = "box-shadow 1s ease";
            node.style.boxShadow = "";
        }, 100);
    });
}

// ── Activity Log ─────────────────────────────────────
function addLog(type, message) {
    const log = $("#activity-log");
    if (!log) return;

    // Remove empty state
    const empty = log.querySelector(".empty-state");
    if (empty) empty.remove();

    const time = new Date().toLocaleTimeString("en-IN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
    });

    const entry = document.createElement("div");
    entry.className = "log-entry";
    entry.innerHTML = `
        <div class="log-dot ${type}"></div>
        <div class="log-content">
            <div class="log-message">${message}</div>
            <div class="log-time">${time}</div>
        </div>
    `;

    log.prepend(entry);

    // Limit entries
    const entries = log.querySelectorAll(".log-entry");
    if (entries.length > 50) {
        entries[entries.length - 1].remove();
    }

    state.logs.push({ type, message, time });
}

// ── History Table ────────────────────────────────────
function updateHistoryTable() {
    const tbody = $("#history-tbody");
    if (!tbody) return;

    tbody.innerHTML = "";

    const items = state.history.slice(0, 20);

    if (items.length === 0) {
        tbody.innerHTML = `
            <tr><td colspan="5" style="text-align:center; color: var(--text-muted); padding: 2rem;">
                Waiting for predictions...
            </td></tr>
        `;
        return;
    }

    items.forEach((item, i) => {
        const input = item.input || {};
        const time = item.timestamp
            ? new Date(item.timestamp).toLocaleTimeString("en-IN", {
                hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
            })
            : "--";

        const statusClass = item.is_fire ? "fire" : "safe";
        const statusText = item.is_fire ? "FIRE 🔥" : "SAFE ✅";

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td style="font-family: 'JetBrains Mono', monospace; font-size:0.7rem;">${time}</td>
            <td>${input.temperature || "--"}°C</td>
            <td>${input.humidity || "--"}%</td>
            <td>${input.wind_speed || "--"}</td>
            <td><span class="status-pill ${statusClass}">${statusText}</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// ── Chart ────────────────────────────────────────────
let chart = null;

function initChart() {
    const canvas = $("#prediction-chart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    
    // Set canvas size
    const container = canvas.parentElement;
    canvas.width = container.offsetWidth;
    canvas.height = container.offsetHeight;

    chart = {
        ctx,
        canvas,
        data: {
            labels: [],
            temp: [],
            humidity: [],
            wind: []
        },
        colors: {
            temp: "#ff6b35",
            humidity: "#448aff",
            wind: "#00e676"
        }
    };

    drawChart();
}

function addChartData(data) {
    if (!chart || !data.input) return;

    const time = new Date().toLocaleTimeString("en-IN", {
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
    });

    chart.data.labels.push(time);
    chart.data.temp.push(data.input.temperature || 0);
    chart.data.humidity.push(data.input.humidity || 0);
    chart.data.wind.push(data.input.wind_speed || 0);

    // Keep last 20 points
    if (chart.data.labels.length > 20) {
        chart.data.labels.shift();
        chart.data.temp.shift();
        chart.data.humidity.shift();
        chart.data.wind.shift();
    }

    drawChart();
}

function rebuildChart() {
    if (!chart) return;

    chart.data = { labels: [], temp: [], humidity: [], wind: [] };

    const items = [...state.history].reverse().slice(-20);
    items.forEach(item => {
        const input = item.input || {};
        const time = item.timestamp
            ? new Date(item.timestamp).toLocaleTimeString("en-IN", {
                hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
            })
            : "";
        chart.data.labels.push(time);
        chart.data.temp.push(input.temperature || 0);
        chart.data.humidity.push(input.humidity || 0);
        chart.data.wind.push(input.wind_speed || 0);
    });

    drawChart();
}

function drawChart() {
    if (!chart) return;

    const { ctx, canvas, data, colors } = chart;
    const w = canvas.width;
    const h = canvas.height;

    const padding = { top: 30, right: 20, bottom: 40, left: 50 };
    const plotW = w - padding.left - padding.right;
    const plotH = h - padding.top - padding.bottom;

    // Clear
    ctx.clearRect(0, 0, w, h);

    if (data.labels.length === 0) {
        ctx.fillStyle = "#55556a";
        ctx.font = "14px Inter, sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("Waiting for sensor data...", w / 2, h / 2);
        return;
    }

    // Find max value for Y axis
    const allValues = [...data.temp, ...data.humidity, ...data.wind];
    const maxVal = Math.max(...allValues, 10);
    const yMax = Math.ceil(maxVal / 10) * 10 + 10;

    // Grid lines
    ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
    ctx.lineWidth = 1;
    const gridLines = 5;
    for (let i = 0; i <= gridLines; i++) {
        const y = padding.top + (plotH / gridLines) * i;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(w - padding.right, y);
        ctx.stroke();

        // Y labels
        const val = Math.round(yMax - (yMax / gridLines) * i);
        ctx.fillStyle = "#55556a";
        ctx.font = "10px 'JetBrains Mono', monospace";
        ctx.textAlign = "right";
        ctx.fillText(val, padding.left - 10, y + 4);
    }

    // X labels
    ctx.textAlign = "center";
    const step = Math.max(1, Math.floor(data.labels.length / 6));
    data.labels.forEach((label, i) => {
        if (i % step === 0) {
            const x = padding.left + (plotW / (data.labels.length - 1 || 1)) * i;
            ctx.fillStyle = "#55556a";
            ctx.font = "9px 'JetBrains Mono', monospace";
            ctx.fillText(label, x, h - padding.bottom + 20);
        }
    });

    // Draw lines
    function drawLine(values, color) {
        if (values.length < 2) return;

        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.lineJoin = "round";
        ctx.lineCap = "round";

        values.forEach((val, i) => {
            const x = padding.left + (plotW / (values.length - 1 || 1)) * i;
            const y = padding.top + plotH - (val / yMax) * plotH;
            
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });

        ctx.stroke();

        // Gradient fill
        const gradient = ctx.createLinearGradient(0, padding.top, 0, padding.top + plotH);
        gradient.addColorStop(0, color.replace(")", ", 0.15)").replace("rgb", "rgba"));
        gradient.addColorStop(1, color.replace(")", ", 0)").replace("rgb", "rgba"));

        ctx.lineTo(padding.left + plotW, padding.top + plotH);
        ctx.lineTo(padding.left, padding.top + plotH);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        // Data points
        values.forEach((val, i) => {
            const x = padding.left + (plotW / (values.length - 1 || 1)) * i;
            const y = padding.top + plotH - (val / yMax) * plotH;

            ctx.beginPath();
            ctx.arc(x, y, 3, 0, Math.PI * 2);
            ctx.fillStyle = color;
            ctx.fill();
        });
    }

    drawLine(data.temp, colors.temp);
    drawLine(data.humidity, colors.humidity);
    drawLine(data.wind, colors.wind);

    // Legend
    const legendItems = [
        { label: "Temperature", color: colors.temp },
        { label: "Humidity", color: colors.humidity },
        { label: "Wind Speed", color: colors.wind }
    ];

    let legendX = padding.left;
    legendItems.forEach(item => {
        ctx.fillStyle = item.color;
        ctx.fillRect(legendX, 8, 12, 3);
        ctx.fillStyle = "#8888a0";
        ctx.font = "10px Inter, sans-serif";
        ctx.textAlign = "left";
        ctx.fillText(item.label, legendX + 16, 13);
        legendX += ctx.measureText(item.label).width + 36;
    });
}

// Handle resize
window.addEventListener("resize", () => {
    if (chart) {
        const container = chart.canvas.parentElement;
        chart.canvas.width = container.offsetWidth;
        chart.canvas.height = container.offsetHeight;
        drawChart();
    }
});

// ── Toast Notifications ──────────────────────────────
function showToast(type, message) {
    const container = $("#toast-container");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = "0";
        toast.style.transform = "translateX(30px)";
        toast.style.transition = "all 0.3s ease";
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}
