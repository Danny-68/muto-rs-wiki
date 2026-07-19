#!/usr/bin/env python3
"""
robot_bridge.py — Flask bridge voor Muto RS hexapod
Verbindt Dify/HTTP-requests én spraakcommando's met STM32-serieel protocol.

Snelheidskalibratie (gemeten 2026-07-01, vlakke ondergrond, 5s looptijd):
  step=10 → 13.5cm → 0.027 m/s
  step=15 → 30.5cm → 0.061 m/s
  step=18 → gem. 34.7cm → 0.069 m/s
  step=20 → gem. 49.0cm → 0.096 m/s
  step=25 → 62.5cm → 0.125 m/s

Spraakcommando-IDs (empirisch bepaald 2026-07-01):
  0 = wake-word "Hallo Yahboom"
  2 = stop
  4 = go ahead (vooruit)
  5 = back off (achteruit)
  6 = turn left (roteer links)
  7 = turn right (roteer rechts)

Sensor-uitbreiding (2026-07-02):
  /lidar/obstacle          — dichtstbijzijnde LiDAR-afstand, via sensor_relay.py
                              (draait in humble_run container, poort 5001)
  /camera/depth/obstacle   — pinhole-projectie op dieptebeeld, via sensor_relay.py
  /camera/describe         — foto + scene-beschrijving via qwen3-vl op Windows-Ollama

Uitbreiding (2026-07-08):
  /health                  — eenvoudige liveness-check
  /robot/imu               — huidige yaw (+ pitch/roll indien beschikbaar) via STM32 IMU
"""

from flask import Flask, request, jsonify, send_file
import os
import base64
import requests
import serial, time, subprocess, threading

app = Flask(__name__)

SERIAL_PORT = "/dev/myserial"
BAUD        = 115200
_serial_lock = threading.Lock()

# Relay in de humble_run container (host-netwerk) — levert LiDAR/diepte/kleur
SENSOR_RELAY_URL = "http://localhost:5001"

# ------------------------------------------------------------------ #
#  STM32 protocol                                                      #
# ------------------------------------------------------------------ #

def make_cmd(addr, data=0x00):
    wr     = 0x01
    length = 0x09
    body   = [wr, addr, data]
    chk    = (0xFF - ((length + sum(body)) & 0xFF)) & 0xFF
    return bytes([0x55, 0x00, length] + body + [chk, 0x00, 0xAA])

def send_cmd(data):
    with _serial_lock:
        with serial.Serial(SERIAL_PORT, BAUD, timeout=1) as ser:
            ser.write(data)
            time.sleep(0.05)

# ------------------------------------------------------------------ #
#  IMU yaw-uitlezing + closed-loop rotatie                             #
# ------------------------------------------------------------------ #

# IMU yaw-uitlees commando (bevestigd: respons yaw op bytes i+9:i+11,
# signed big-endian, /100 = graden). Yaw in rust stabiel binnen ~0.1 graden.
IMU_CMD = bytes([0x55, 0x00, 0x09, 0x02, 0x60, 0x07, 0x8D, 0x00, 0xAA])

def _read_imu_frame(ser):
    """
    Leest een volledig IMU-frame via een reeds-geopende seriele verbinding.
    Retourneert dict met yaw, pitch, roll (in graden, float) of None bij mislukking.

    Responsframe (bevestigd via baseboard-protocol):
        0x55 0x00 0x0F 0x12 0x60 d1 d2 d3 d4 d5 d6 ... 0x00 0xAA
        roll  = (d1<<8)|d2  (signed, /100 = graden)
        pitch = (d3<<8)|d4  (signed, /100 = graden)
        yaw   = (d5<<8)|d6  (signed, /100 = graden)
    """
    ser.reset_input_buffer()
    ser.write(IMU_CMD)
    time.sleep(0.05)
    raw = ser.read(64)
    for i in range(len(raw) - 11):
        if (raw[i] == 0x55 and raw[i + 1] == 0x00
                and raw[i + 3] == 0x12 and raw[i + 4] == 0x60):
            def signed16(hi, lo):
                val = (hi << 8) | lo
                if val >= 0x8000:
                    val -= 0x10000
                return val / 100.0
            roll  = signed16(raw[i + 5], raw[i + 6])   # d1,d2
            pitch = signed16(raw[i + 7], raw[i + 8])   # d3,d4
            yaw   = signed16(raw[i + 9], raw[i + 10])  # d5,d6
            return {"yaw": yaw, "pitch": pitch, "roll": roll}
    return None

def _read_yaw(ser):
    """
    Leest alleen de yaw via een reeds-geopende seriele verbinding.
    Retourneert de yaw in graden (float) of None als geen geldig frame.
    """
    frame = _read_imu_frame(ser)
    return frame["yaw"] if frame is not None else None

def _read_yaw_retry(ser, attempts=6):
    """
    Robuuste yaw-lezing: probeert meerdere keren, want de buffer kan af en toe
    een respons van een ander commando bevatten in plaats van een IMU-frame.
    """
    for _ in range(attempts):
        yaw = _read_yaw(ser)
        if yaw is not None:
            return yaw
        time.sleep(0.02)
    return None

def _yaw_delta(from_yaw, to_yaw):
    """
    Kortste hoekverschil to_yaw - from_yaw, genormaliseerd naar (-180, 180].
    Lost de wrap-around op bij het passeren van +/-180 graden.
    """
    d = (to_yaw - from_yaw) % 360.0
    if d > 180.0:
        d -= 360.0
    return d

# Rotatie-parameters
ROTATE_STEP          = 10     # kleine stap = langzaam draaien = preciezere stop
ROTATE_STOP_MARGIN   = 20.0   # graden voor het doel stoppen (globale uitloop-compensatie)
ROTATE_TIMEOUT_S     = 25.0   # veiligheidslimiet, nooit langer draaien dan dit
ROTATE_POLL_S        = 0.02   # pauze tussen yaw-metingen tijdens draaien
ROTATE_SETTLE_S      = 0.4    # wachttijd na stop zodat de robot echt stilstaat

def rotate_to_angle(angle_deg: float) -> dict:
    """
    Draait de robot closed-loop over 'angle_deg' graden.
    Positief = naar links (0x16), negatief = naar rechts (0x17).
    """
    target = abs(float(angle_deg))
    if target < 1.0:
        return {"ok": True, "action": "rotate_to_angle", "requested_deg": angle_deg,
                "turned_deg": 0.0, "note": "hoek te klein, genegeerd"}

    stop_margin = min(ROTATE_STOP_MARGIN, target * 0.5)
    turn_addr   = 0x17 if angle_deg > 0 else 0x16
    direction   = "rechts" if angle_deg > 0 else "links"

    with _serial_lock:
        with serial.Serial(SERIAL_PORT, BAUD, timeout=1) as ser:
            time.sleep(0.1)
            _read_yaw_retry(ser)
            start_yaw = _read_yaw_retry(ser)
            if start_yaw is None:
                return {"ok": False, "error": "kon begin-yaw niet lezen"}

            move = make_cmd(turn_addr, ROTATE_STEP)
            ser.write(move)
            time.sleep(0.05)

            cumulative = 0.0
            prev_yaw   = start_yaw
            t0         = time.time()

            while True:
                time.sleep(ROTATE_POLL_S)
                yaw = _read_yaw(ser)
                if yaw is not None:
                    step_delta  = _yaw_delta(prev_yaw, yaw)
                    cumulative += step_delta
                    prev_yaw    = yaw

                if abs(cumulative) >= (target - stop_margin):
                    break
                if time.time() - t0 > ROTATE_TIMEOUT_S:
                    ser.write(make_cmd(0x11, 0x00))
                    return {"ok": False, "error": "rotatie-timeout",
                            "turned_deg": round(abs(cumulative), 1),
                            "requested_deg": angle_deg}

                ser.write(move)

            ser.write(make_cmd(0x11, 0x00))

            time.sleep(ROTATE_SETTLE_S)
            end_yaw = _read_yaw_retry(ser)
            if end_yaw is not None:
                cumulative += _yaw_delta(prev_yaw, end_yaw)
                prev_yaw    = end_yaw

    turned    = abs(cumulative)
    overshoot = round(turned - target, 1)
    return {
        "ok": True,
        "action": "rotate_to_angle",
        "direction": direction,
        "requested_deg": angle_deg,
        "turned_deg": round(turned, 1),
        "afwijking_deg": overshoot,
        "start_yaw": round(start_yaw, 1),
        "end_yaw": round(end_yaw, 1) if end_yaw is not None else None,
    }

# ------------------------------------------------------------------ #
#  Snelheidskalibratie                                                 #
# ------------------------------------------------------------------ #

SPEED_TABLE = {
    10: 0.027,
    15: 0.061,
    18: 0.069,
    20: 0.096,
    25: 0.125,
}

DEFAULT_STEP    = 18
STEP_DISTANCE_M = 0.10
SAFETY_CAP_S    = 30.0

def get_speed_for_step(step: int) -> float:
    keys = sorted(SPEED_TABLE.keys())
    if step <= keys[0]:
        return SPEED_TABLE[keys[0]]
    if step >= keys[-1]:
        return SPEED_TABLE[keys[-1]]
    for i in range(len(keys) - 1):
        s0, s1 = keys[i], keys[i + 1]
        if s0 <= step <= s1:
            v0, v1 = SPEED_TABLE[s0], SPEED_TABLE[s1]
            t = (step - s0) / (s1 - s0)
            return v0 + t * (v1 - v0)
    return SPEED_TABLE[DEFAULT_STEP]

# ------------------------------------------------------------------ #
#  Duurresolutie                                                       #
# ------------------------------------------------------------------ #

def resolve_duration(body: dict, step: int):
    speed    = get_speed_for_step(step)
    steps    = body.get("steps")
    distance = body.get("distance_m")
    time_s   = body.get("time_s")
    if steps is not None:
        return float(steps) * STEP_DISTANCE_M / speed
    if distance is not None:
        return float(distance) / speed
    if time_s is not None:
        return float(time_s)
    return None

# ------------------------------------------------------------------ #
#  Bewegingsafhandeling                                                #
# ------------------------------------------------------------------ #

def _move_and_autostop(addr, step, duration):
    send_cmd(make_cmd(addr, step))
    if duration is not None:
        time.sleep(min(duration, SAFETY_CAP_S))
        send_cmd(make_cmd(0x11, 0x00))

def _start_move(addr, body: dict) -> dict:
    step     = max(10, min(25, int(body.get("step", DEFAULT_STEP))))
    duration = resolve_duration(body, step)
    speed    = get_speed_for_step(step)
    threading.Thread(
        target=_move_and_autostop,
        args=(addr, step, duration),
        daemon=True
    ).start()
    return {"step": step, "duration": duration, "speed_m_per_s": round(speed, 4)}

# ------------------------------------------------------------------ #
#  Spraakcommando poller                                               #
# ------------------------------------------------------------------ #

VOICE_CMD_MAP = {
    0: None,
    2: "stop",
    4: "forward",
    5: "backward",
    6: "rotate_left",
    7: "rotate_right",
}

VOICE_MOVE_DURATION = 5.0
VOICE_WAKE_TIMEOUT  = 10.0

_voice_wake_until = 0.0
_voice_lock       = threading.Lock()

def _execute_voice_cmd(cmd_name: str):
    body = {"time_s": VOICE_MOVE_DURATION, "step": DEFAULT_STEP}
    if cmd_name == "stop":
        send_cmd(make_cmd(0x11, 0x00))
        print(f"[VOICE] stop", flush=True)
    elif cmd_name == "forward":
        _start_move(0x12, body)
        print(f"[VOICE] forward ({VOICE_MOVE_DURATION}s)", flush=True)
    elif cmd_name == "backward":
        _start_move(0x13, body)
        print(f"[VOICE] backward ({VOICE_MOVE_DURATION}s)", flush=True)
    elif cmd_name == "rotate_left":
        _start_move(0x16, body)
        print(f"[VOICE] rotate_left ({VOICE_MOVE_DURATION}s)", flush=True)
    elif cmd_name == "rotate_right":
        _start_move(0x17, body)
        print(f"[VOICE] rotate_right ({VOICE_MOVE_DURATION}s)", flush=True)

def _voice_poller():
    global _voice_wake_until
    try:
        from Speech_Lib import Speech
        speech = Speech(path='/home/pi/speech_music/')
        print("[VOICE] Spraakmodule geinitialiseerd, luistert...", flush=True)
    except Exception as e:
        print(f"[VOICE] Kon spraakmodule niet initialiseren: {e}", flush=True)
        return

    while True:
        try:
            result = speech.speech_read()
            if result is None or result == 999:
                time.sleep(0.01)
                continue

            now = time.time()

            if result == 0:
                with _voice_lock:
                    _voice_wake_until = now + VOICE_WAKE_TIMEOUT
                print(f"[VOICE] Wake-word! Luistert {VOICE_WAKE_TIMEOUT}s naar commando's", flush=True)

            elif result in VOICE_CMD_MAP and VOICE_CMD_MAP[result] is not None:
                with _voice_lock:
                    wake_active = now < _voice_wake_until
                if wake_active:
                    cmd_name = VOICE_CMD_MAP[result]
                    _execute_voice_cmd(cmd_name)
                    with _voice_lock:
                        _voice_wake_until = now + VOICE_WAKE_TIMEOUT
                else:
                    print(f"[VOICE] ID {result} genegeerd — geen actief wake-word", flush=True)
            else:
                print(f"[VOICE] Onbekend ID {result}", flush=True)

        except Exception as e:
            print(f"[VOICE] Fout: {e}", flush=True)

        time.sleep(0.01)

threading.Thread(target=_voice_poller, daemon=True).start()

# ------------------------------------------------------------------ #
#  Debug logging                                                       #
# ------------------------------------------------------------------ #

@app.before_request
def _debug_log():
    if request.path.startswith("/robot/") and request.method == "POST":
        print("=== INCOMING REQUEST ===", flush=True)
        print("PATH:", request.path, flush=True)
        print("BODY:", request.get_data(), flush=True)
        print("JSON:", request.get_json(silent=True), flush=True)
        print("========================", flush=True)

# ------------------------------------------------------------------ #
#  Health endpoint                                                     #
# ------------------------------------------------------------------ #

@app.route("/health", methods=["GET"])
def health():
    """Eenvoudige liveness-check — geeft 200 OK als de bridge draait."""
    return jsonify({"ok": True, "service": "robot_bridge", "version": "2026-07-08"})

# ------------------------------------------------------------------ #
#  IMU endpoint                                                        #
# ------------------------------------------------------------------ #

@app.route("/robot/imu", methods=["GET"])
def imu():
    """
    Leest het huidige IMU-frame van de STM32 baseboard.
    Retourneert yaw, pitch en roll in graden (signed float, /100).
    Positieve yaw = linksom, negatieve yaw = rechtsom (vanuit robot-perspectief).
    """
    try:
        with _serial_lock:
            with serial.Serial(SERIAL_PORT, BAUD, timeout=1) as ser:
                # Eerste lezing weggooien (buffer-ruis), dan robuust uitlezen
                _read_imu_frame(ser)
                frame = None
                for _ in range(6):
                    frame = _read_imu_frame(ser)
                    if frame is not None:
                        break
                    time.sleep(0.02)
        if frame is None:
            return jsonify({"ok": False, "error": "geen geldig IMU-frame ontvangen"}), 502
        return jsonify({
            "ok":    True,
            "yaw":   round(frame["yaw"],   2),
            "pitch": round(frame["pitch"], 2),
            "roll":  round(frame["roll"],  2),
        })
    except serial.SerialException as e:
        return jsonify({"ok": False, "error": f"seriele poort fout: {e}"}), 502

# ------------------------------------------------------------------ #
#  Camera endpoints — via ROS2-relay (sensor_relay.py, poort 5001)     #
# ------------------------------------------------------------------ #

CAPTURE_PATH = "/home/pi/camera_capture.jpg"

def _get_color_bytes():
    try:
        r = requests.get(f"{SENSOR_RELAY_URL}/camera/color/jpeg", timeout=3)
        if r.status_code == 200 and r.headers.get("Content-Type", "").startswith("image/"):
            return r.content, r.headers["Content-Type"]
        try:
            return None, r.json().get("error", "onbekende relay-fout")
        except Exception:
            return None, f"relay status {r.status_code}"
    except requests.exceptions.RequestException as e:
        return None, f"sensor_relay onbereikbaar: {e}"

@app.route("/camera/capture", methods=["POST"])
def camera_capture():
    data, ctype = _get_color_bytes()
    if data is None:
        return jsonify({"ok": False, "error": ctype}), 502
    with open(CAPTURE_PATH, "wb") as f:
        f.write(data)
    return jsonify({"ok": True, "action": "capture", "path": CAPTURE_PATH,
                    "content_type": ctype, "image_url": "/camera/image"})

@app.route("/camera/image", methods=["GET"])
def camera_image():
    if not os.path.exists(CAPTURE_PATH):
        return jsonify({"ok": False, "error": "nog geen foto gemaakt"}), 404
    return send_file(CAPTURE_PATH, mimetype="image/jpeg")

# ------------------------------------------------------------------ #
#  Sensor-endpoints — LiDAR + dieptecamera (via sensor_relay.py)       #
# ------------------------------------------------------------------ #

@app.route("/lidar/obstacle", methods=["GET"])
def lidar_obstacle():
    """Dichtstbijzijnde LiDAR-afstand + hoek."""
    try:
        r = requests.get(f"{SENSOR_RELAY_URL}/scan/nearest", timeout=2)
        return jsonify(r.json()), r.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"ok": False, "error": f"sensor_relay onbereikbaar: {e}"}), 502

@app.route("/camera/depth/obstacle", methods=["GET"])
def camera_depth_obstacle():
    """Pinhole-projectie op het midden van het dieptebeeld."""
    try:
        params = {}
        if "u" in request.args:
            params["u"] = request.args.get("u")
        if "v" in request.args:
            params["v"] = request.args.get("v")
        r = requests.get(f"{SENSOR_RELAY_URL}/depth/center", params=params, timeout=2)
        return jsonify(r.json()), r.status_code
    except requests.exceptions.RequestException as e:
        return jsonify({"ok": False, "error": f"sensor_relay onbereikbaar: {e}"}), 502

# ------------------------------------------------------------------ #
#  Scene-beschrijving via vision-LLM (qwen3-vl op Windows-Ollama)      #
# ------------------------------------------------------------------ #

OLLAMA_VISION_URL = "http://192.168.68.77:11434/api/generate"
VISION_MODEL      = "qwen3-vl"

@app.route("/camera/describe", methods=["POST"])
def camera_describe():
    data, ctype = _get_color_bytes()
    if data is None:
        return jsonify({"ok": False, "error": ctype}), 502

    image_b64 = base64.b64encode(data).decode("utf-8")
    prompt = (
        "Beschrijf kort en concreet wat je ziet in dit beeld, vanuit het "
        "perspectief van een hexapod-robot op grondniveau. Noem obstakels, "
        "vrije ruimte, en opvallende objecten. Antwoord in het Nederlands."
    )

    try:
        r = requests.post(
            OLLAMA_VISION_URL,
            json={"model": VISION_MODEL, "prompt": prompt,
                  "images": [image_b64], "stream": False},
            timeout=30,
        )
        r.raise_for_status()
        description = r.json().get("response", "").strip()
        return jsonify({"ok": True, "description": description})
    except requests.exceptions.RequestException as e:
        return jsonify({"ok": False, "error": f"Ollama vision-model onbereikbaar: {e}"}), 502

# ------------------------------------------------------------------ #
#  Robot bewegingsendpoints                                            #
# ------------------------------------------------------------------ #

@app.route("/robot/stop", methods=["POST"])
def stop():
    send_cmd(make_cmd(0x11, 0x00))
    return jsonify({"ok": True, "action": "stop"})

@app.route("/robot/forward", methods=["POST"])
def forward():
    body = request.json or {}
    info = _start_move(0x12, body)
    return jsonify({"ok": True, "action": "forward", **info})

@app.route("/robot/backward", methods=["POST"])
def backward():
    body = request.json or {}
    info = _start_move(0x13, body)
    return jsonify({"ok": True, "action": "backward", **info})

@app.route("/robot/left", methods=["POST"])
def left():
    body = request.json or {}
    info = _start_move(0x14, body)
    return jsonify({"ok": True, "action": "left", **info})

@app.route("/robot/right", methods=["POST"])
def right():
    body = request.json or {}
    info = _start_move(0x15, body)
    return jsonify({"ok": True, "action": "right", **info})

@app.route("/robot/rotate_left", methods=["POST"])
def rotate_left():
    body = request.json or {}
    info = _start_move(0x16, body)
    return jsonify({"ok": True, "action": "rotate_left", **info})

@app.route("/robot/rotate_right", methods=["POST"])
def rotate_right():
    body = request.json or {}
    info = _start_move(0x17, body)
    return jsonify({"ok": True, "action": "rotate_right", **info})

@app.route("/robot/rotate_to_angle", methods=["POST"])
def rotate_to_angle_endpoint():
    body = request.json or {}
    try:
        angle = float(body.get("angle_deg"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "angle_deg (getal) is verplicht"}), 400
    result = rotate_to_angle(angle)
    status = 200 if result.get("ok") else 500
    return jsonify(result), status

# ------------------------------------------------------------------ #
#  Robot configuratie-endpoints                                        #
# ------------------------------------------------------------------ #

@app.route("/robot/height", methods=["POST"])
def height():
    level = max(1, min(3, int((request.json or {}).get("level", 2))))
    send_cmd(make_cmd(0x18, level))
    return jsonify({"ok": True, "action": "height", "level": level})

@app.route("/robot/speed", methods=["POST"])
def speed():
    level = max(0, min(4, int((request.json or {}).get("level", 2))))
    send_cmd(make_cmd(0x23, level))
    return jsonify({"ok": True, "action": "speed", "level": level})

@app.route("/robot/perform", methods=["POST"])
def perform():
    group = max(0, min(8, int((request.json or {}).get("group", 0))))
    send_cmd(make_cmd(0x3E, group))
    return jsonify({"ok": True, "action": "perform", "group": group})

# ------------------------------------------------------------------ #
#  Gait engine endpoints                                               #
# ------------------------------------------------------------------ #

_gait_proc = None

@app.route("/robot/gait", methods=["POST"])
def gait():
    global _gait_proc
    gait_name = (request.json or {}).get("gait", "phoenix")
    if _gait_proc and _gait_proc.poll() is None:
        _gait_proc.terminate()
        time.sleep(0.5)
    scripts = {
        "phoenix":   "/home/pi/phoenix_gait.py",
        "centipede": "/home/pi/centipede_gait.py",
    }
    script = scripts.get(gait_name)
    if not script:
        return jsonify({"ok": False, "error": "onbekende gait"}), 400
    _gait_proc = subprocess.Popen(["docker", "exec", "humble_run", "bash", "-c", f"source /opt/ros/humble/setup.bash && source /root/yahboomcar_ros2_ws/software/library_ws_humble/install/setup.bash && python3 /root/{os.path.basename(script)}"])
    return jsonify({"ok": True, "action": "gait", "gait": gait_name})

@app.route("/robot/gait/stop", methods=["POST"])
def gait_stop():
    global _gait_proc
    if _gait_proc and _gait_proc.poll() is None:
        _gait_proc.terminate()
    send_cmd(make_cmd(0x11, 0x00))
    return jsonify({"ok": True, "action": "gait_stop"})

# ------------------------------------------------------------------ #
#  Status endpoint                                                     #
# ------------------------------------------------------------------ #

@app.route("/robot/status", methods=["GET"])
def status():
    gait_running = _gait_proc is not None and _gait_proc.poll() is None
    with _voice_lock:
        voice_wake_active = time.time() < _voice_wake_until
    return jsonify({
        "ok": True,
        "serial": SERIAL_PORT,
        "gait_running": gait_running,
        "voice_wake_active": voice_wake_active,
        "speed_table": SPEED_TABLE,
        "default_step": DEFAULT_STEP,
        "step_distance_m": STEP_DISTANCE_M,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)