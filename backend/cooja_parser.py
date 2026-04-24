# cooja_parser.py — Cooja Sink Output Parser
# ────────────────────────────────────────────────────────────────
# Handles multiple input formats from the Cooja Serial Socket:
#
#  1. Pure JSON (from sink.c printf):
#       {"temp":25,"humidity":65,"wind":12,"moisture":55,"ph":6,"light":420}
#
#  2. JSON embedded in a Contiki LOG_INFO line:
#       [INFO: SINK      ] DATA: {"temp":25,...}
#       [INFO: SENSOR    ] Sending: {"temp":25,...}
#
#  3. Legacy key:value format (older sketches):
#       TEMP:79   RH:42   WS:11
#
# JSON keys recognised:
#   temp / temperature  → temperature °C
#   humidity / rh       → relative humidity %
#   wind / ws / wind_speed → wind speed km/h
#   moisture, ph, light → passed through as extra fields
# ────────────────────────────────────────────────────────────────

import re
import json


# ──────────────────────────────────────────────────────────────
# parse_cooja_line
# ──────────────────────────────────────────────────────────────
def parse_cooja_line(line):
    """
    Parse a single line from the Cooja Serial Socket.

    Returns:
        ("json",   dict)  — complete JSON object (may have extra fields)
        ("temp",   float) — single temperature reading
        ("rh",     float) — single humidity reading
        ("ws",     float) — single wind-speed reading
        None              — line not recognised
    """
    line = line.strip()
    if not line:
        return None

    # ── 1. Pure JSON line ─────────────────────────────────────
    if line.startswith("{"):
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                return ("json", data)
        except (json.JSONDecodeError, ValueError):
            pass

    # ── 2. JSON embedded anywhere in the line ────────────────
    #   Matches the first {...} block (greedy to handle nested quotes)
    json_match = re.search(r'\{[^{}]*\}', line)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if isinstance(data, dict):
                return ("json", data)
        except (json.JSONDecodeError, ValueError):
            pass

    # ── 3. Legacy key:value formats ──────────────────────────
    temp_match = re.search(r'TEMP\s*:\s*(\d+\.?\d*)', line, re.IGNORECASE)
    if temp_match:
        return ("temp", float(temp_match.group(1)))

    rh_match = re.search(r'(?:RH|HUMIDITY)\s*:\s*(\d+\.?\d*)', line, re.IGNORECASE)
    if rh_match:
        return ("rh", float(rh_match.group(1)))

    ws_match = re.search(r'(?:WS|WIND|WINDSPEED)\s*:\s*(\d+\.?\d*)', line, re.IGNORECASE)
    if ws_match:
        return ("ws", float(ws_match.group(1)))

    return None


# ──────────────────────────────────────────────────────────────
# SensorAccumulator
# ──────────────────────────────────────────────────────────────
class SensorAccumulator:
    """
    Accumulates individual sensor readings (TEMP / RH / WS) that may
    arrive as separate packets.  Once all 3 core values are present,
    emits a complete reading dict.

    For JSON packets that already contain all 3 values (the normal case
    with the updated sensor.c), use add_json() directly.
    """

    def __init__(self):
        self._reset()

    def _reset(self):
        self.buffer = {"temp": None, "rh": None, "ws": None}
        self.extra = {}

    def add_reading(self, sensor_type, value):
        """
        Add a single key:value reading.

        Returns a complete dict when temp+rh+ws are all present, else None.
        """
        if sensor_type in self.buffer:
            self.buffer[sensor_type] = value
            if all(v is not None for v in self.buffer.values()):
                complete = {**self.buffer, **self.extra}
                self._reset()
                return complete
        return None

    def add_json(self, data):
        """
        Handle a JSON packet.  Extracts core fields and any extras.

        Returns a complete dict immediately if all 3 core values are present.
        Returns None if some values are missing (will wait for more packets).
        """
        # ── Core fields (flexible key names) ─────────────────
        temp = _first(data, ["temp", "temperature"])
        rh   = _first(data, ["humidity", "rh"])
        ws   = _first(data, ["wind", "ws", "wind_speed"])

        # ── Extra fields passthrough ──────────────────────────
        extra = {}
        for k in ("moisture", "ph", "light", "node"):
            if k in data:
                extra[k] = data[k]

        if temp is not None and rh is not None and ws is not None:
            return {
                "temp":  float(temp),
                "rh":    float(rh),
                "ws":    float(ws),
                **{k: v for k, v in extra.items()},
            }

        # Partial JSON — fold into accumulator buffer
        if temp is not None:
            self.buffer["temp"] = float(temp)
        if rh is not None:
            self.buffer["rh"] = float(rh)
        if ws is not None:
            self.buffer["ws"] = float(ws)
        self.extra.update(extra)

        if all(v is not None for v in self.buffer.values()):
            complete = {**self.buffer, **self.extra}
            self._reset()
            return complete

        return None


def _first(d, keys):
    """Return the first non-None value found for any key in `keys`."""
    for k in keys:
        v = d.get(k)
        if v is not None:
            return v
    return None


# ──────────────────────────────────────────────────────────────
# Legacy bulk-parse helper
# ──────────────────────────────────────────────────────────────
def parse_text(file_content, predict_fn):
    """Parse text content and run predictions (legacy / offline use)."""
    results = []
    accumulator = SensorAccumulator()

    for line in file_content.strip().split("\n"):
        parsed = parse_cooja_line(line)
        if parsed is None:
            continue

        sensor_type, value = parsed

        if sensor_type == "json":
            complete = accumulator.add_json(value)
        else:
            complete = accumulator.add_reading(sensor_type, value)

        if complete:
            result = predict_fn(complete["temp"], complete["rh"], complete["ws"])
            results.append(result)

    return results