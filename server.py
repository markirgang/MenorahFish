#!/usr/bin/env python3
import http.server
import socketserver
import json
import os
import sys
import socket
import ssl
import cv2
import base64
import threading
import time
import random
import urllib.parse
import re
import math
from gemini_bridge import GeminiArmBridge
import numpy as np

PORT = int(os.environ.get("PORT", 1390))
HOST = os.environ.get("HOST", os.environ.get("IP", "127.0.0.1"))
DIRECTORY = os.environ.get("DIRECTORY", os.path.join(os.path.dirname(os.path.abspath(__file__)), "static"))

def generate_synthetic_camera_frame():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    frame[:, :] = (20, 30, 45)
    cv2.putText(frame, "MENORAH FISH & ROBOT ARM STAGE CAMERA", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 240, 255), 2)
    cv2.putText(frame, "STATUS: Virtual Stage Feed Active", (150, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (160, 255, 160), 1)
    t_str = time.strftime("%H:%M:%S")
    cv2.putText(frame, f"LIVE TIME: {t_str}", (220, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    return frame

class CameraStream:
    def __init__(self, source="usb"):
        self.source = str(source).lower()
        self.cap = None
        self.picam2 = None
        self.frame = None
        self.lock = threading.Lock()
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()

    def set_source(self, source):
        with self.lock:
            self.source = str(source).lower()
            self._close_cameras()
            self.frame = None

    def reset(self):
        with self.lock:
            self._close_cameras()
            self.frame = None

    def _close_cameras(self):
        if self.cap:
            try: self.cap.release()
            except Exception: pass
            self.cap = None
        if self.picam2:
            try:
                self.picam2.stop()
                self.picam2.close()
            except Exception: pass
            self.picam2 = None

    def _update(self):
        while self.running:
            with self.lock:
                cur_source = self.source

            if cur_source in ["csi", "picamera", "raspberry_pi", "ov5647"]:
                if self.picam2 is None:
                    self._close_cameras()
                    try:
                        from picamera2 import Picamera2
                        p = Picamera2()
                        config = p.create_preview_configuration(main={'size': (640, 480)})
                        p.configure(config)
                        p.start()
                        time.sleep(0.3)
                        self.picam2 = p
                    except Exception:
                        self.picam2 = None
                        time.sleep(1.0)
                        continue

                try:
                    frame_array = self.picam2.capture_array('main')
                    if frame_array is not None and frame_array.size > 0:
                        frame_bgr = cv2.cvtColor(frame_array, cv2.COLOR_RGBA2BGR) if frame_array.shape[2] == 4 else frame_array
                        with self.lock:
                            self.frame = frame_bgr
                    time.sleep(0.04)
                except Exception:
                    self._close_cameras()
                    time.sleep(0.5)

            elif cur_source == "virtual":
                with self.lock:
                    self.frame = generate_synthetic_camera_frame()
                time.sleep(0.5)

            else:
                if self.cap is None or not self.cap.isOpened():
                    self._close_cameras()
                    candidates = [0, 1, 2]
                    if cur_source.isdigit():
                        candidates.insert(0, int(cur_source))
                    candidates = list(dict.fromkeys(candidates))

                    opened = False
                    for idx in candidates:
                        try:
                            cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                            if cap.isOpened():
                                ret, frame = cap.read()
                                if ret and frame is not None and frame.size > 0:
                                    self.cap = cap
                                    with self.lock:
                                        self.frame = frame
                                    opened = True
                                    break
                                else:
                                    cap.release()
                        except Exception: pass

                    if not opened:
                        with self.lock:
                            self.frame = generate_synthetic_camera_frame()
                            self.source = "virtual"
                        time.sleep(0.5)

                if self.cap and self.cap.isOpened():
                    try:
                        ret, frame = self.cap.read()
                        if ret and frame is not None and frame.size > 0:
                            with self.lock:
                                self.frame = frame
                            time.sleep(0.04)
                        else:
                            self._close_cameras()
                            time.sleep(1.0)
                    except Exception:
                        self._close_cameras()
                        time.sleep(1.0)
                else:
                    time.sleep(0.5)

    def get_frame(self):
        if self.lock.acquire(timeout=0.05):
            try:
                if self.frame is not None:
                    return self.frame.copy()
            finally:
                self.lock.release()
        return generate_synthetic_camera_frame()

camera_stream = CameraStream("usb")
gemini_bridge = GeminiArmBridge()

# --- MENORAH FISH & ROBOT ARM GLOBAL HARDWARE STATE ---
menorah_fish_state = {
    "is_speaking": False,
    "is_dancing": False,
    "active_voice": "ai_male_us",

    # Animatronic Fish Motors & Stage Accessories:
    "fish": {
        "mouth_motor": False,       # L298 #1 Ch A: Mouth Open (Lipsync)
        "neck_motor_pwm": 0,        # L298 #1 Ch B: Neck Swing PWM (0-100%)
        "neck_position": 0.0,       # 0.0 (retracted rest) to 1.0 (outstretched)
        "tail_motor": False,        # L298 #2 Ch A: Tail Wag Motor
        "head_spotlight": True      # Fish Head Spotlight
    },

    # Stage Servos (PCA Channels 3 & 4):
    "stage_servos": {
        "dreidel_left_servo": 90,   # PCA Ch 3: Dreidel Left Servo (0-180°)
        "dreidel_right_servo": 90   # PCA Ch 4: Dreidel Right Servo (0-180°)
    },

    # 5-DOF Robot Arm Servos (PCA Channels 0 - 4 for arm, Ch 5 for claw candle):
    "robot_arm": {
        "j1_base": 0,               # Base rotation (-90° to +90°)
        "j2_shoulder": 30,          # Shoulder pitch (-90° to +90°)
        "j3_elbow": 45,             # Elbow pitch (-135° to +135°)
        "j4_wrist": 0,              # Wrist pitch (-90° to +90°)
        "j5_gripper": 50,           # Gripper claw
        "claw_candle_flicker": True # Flickering candle light bulb in claw (ALWAYS ON)
    },

    # 9 Menorah Candles (Center Shamash + 8 Side Candles in 180° Arc):
    "menorah": {
        "lit_count": 0,             # Number of side candles lit (0 to 8)
        "candles": [False] * 9      # Array of 9 booleans (Index 4 is Center Shamash)
    },

    # 4 Stage Light Domes (Breathing light sequence while fish talks/sings):
    "light_domes": {
        "breathing": False,
        "mouth_side_dome1": 100,    # Intensity 0-100%
        "mouth_side_dome2": 100,
        "tail_side_dome1": 100,
        "tail_side_dome2": 100
    }
}

state_lock = threading.Lock()

# Background Thread for Fish Neck Swing (3s gradual PWM ramp), Tail Wagging, Spotlights & Domes
def update_menorah_fish_background_loop():
    speak_start_time = None
    speak_stop_time = None

    while True:
        time.sleep(0.08)
        now = time.time()

        with state_lock:
            is_speaking = menorah_fish_state["is_speaking"]
            fish = menorah_fish_state["fish"]
            domes = menorah_fish_state["light_domes"]

            # 1. Fish Neck Swing Logic (L298 Ch B Forward Polarity with Thermal Overheat Protection)
            if is_speaking:
                speak_stop_time = None
                if speak_start_time is None:
                    speak_start_time = now

                # Swing neck out to full extension (1.0) over 1.2 seconds
                elapsed_speak = now - speak_start_time
                target_pos = min(1.0, elapsed_speak / 1.2)
                fish["neck_position"] = target_pos

                # Thermal Protection: Once neck is fully extended, DEPOWER motor (0% PWM)
                # to prevent continuous stall current & DC motor coil overheating while talking!
                if target_pos >= 1.0:
                    fish["neck_motor_pwm"] = 0
                else:
                    fish["neck_motor_pwm"] = int(target_pos * 100)

                # Head spotlight bright & tail motor wagging (L298 Ch B Reverse Polarity) during speech
                fish["head_spotlight"] = True
                fish["tail_motor"] = True

                # Dreidel Left & Right Servos sweep back & forth during speech
                sweep = int(90 + math.sin(now * 3.5) * 45)
                menorah_fish_state["stage_servos"]["dreidel_left_servo"] = max(30, min(150, sweep))
                menorah_fish_state["stage_servos"]["dreidel_right_servo"] = max(30, min(150, 180 - sweep))

                # 4 Light Domes slow breathing pulse sequence
                domes["breathing"] = True
                phase = now * 2.5
                domes["mouth_side_dome1"] = int(50 + math.sin(phase) * 50)
                domes["mouth_side_dome2"] = int(50 + math.sin(phase + 0.8) * 50)
                domes["tail_side_dome1"]  = int(50 + math.sin(phase + 1.6) * 50)
                domes["tail_side_dome2"]  = int(50 + math.sin(phase + 2.4) * 50)

            else:
                speak_start_time = None
                if speak_stop_time is None:
                    speak_stop_time = now

                # Retract neck back to rest stance (0.0) and depower motor
                elapsed_stop = now - speak_stop_time
                if elapsed_stop < 0.5:
                    target_pos = fish["neck_position"]
                else:
                    target_pos = max(0.0, 1.0 - ((elapsed_stop - 0.5) / 1.5))

                fish["neck_position"] = target_pos
                fish["neck_motor_pwm"] = 0  # Motor depowered to prevent thermal overheating

                domes["breathing"] = False
                domes["mouth_side_dome1"] = 100
                domes["mouth_side_dome2"] = 100
                domes["tail_side_dome1"]  = 100
                domes["tail_side_dome2"]  = 100

                # Idle behaviors when NOT speaking:
                if random.random() < 0.08:
                    fish["tail_motor"] = random.choice([True, False])
                else:
                    fish["tail_motor"] = False

                if random.random() < 0.05:
                    fish["head_spotlight"] = random.choice([True, False, True])

threading.Thread(target=update_menorah_fish_background_loop, daemon=True).start()

# Sequence to Extinguish All Candles & Light N Menorah Candles using Robot Arm
def execute_light_menorah_candles_sequence(count):
    count = max(0, min(8, int(count)))
    with state_lock:
        menorah_fish_state["menorah"]["lit_count"] = count
        # Step 1: Extinguish all candle light bulbs
        menorah_fish_state["menorah"]["candles"] = [False] * 9

    time.sleep(0.5)

    if count == 0:
        return

    # Always light Center Shamash Candle (Index 4) first
    with state_lock:
        menorah_fish_state["menorah"]["candles"][4] = True

    # 180° Arc Candle Positions for Robot Arm (Index 0 to 8)
    arc_angles = [-80, -60, -40, -20, 0, 20, 40, 60, 80]

    # Map requested count N to candle indices (Alternating or left-to-right side candles)
    # Side candle indices: [0, 1, 2, 3] (left) and [5, 6, 7, 8] (right)
    target_indices = []
    side_order = [3, 5, 2, 6, 1, 7, 0, 8] # Light inner to outer candles
    for i in range(min(count, 8)):
        target_indices.append(side_order[i])

    for idx in target_indices:
        target_angle = arc_angles[idx]
        
        # Step A: Move Robot Arm Over Candle
        with state_lock:
            menorah_fish_state["robot_arm"]["j1_base"] = target_angle
            menorah_fish_state["robot_arm"]["j2_shoulder"] = 45
            menorah_fish_state["robot_arm"]["j3_elbow"] = -30
            menorah_fish_state["robot_arm"]["j4_wrist"] = -15

        time.sleep(0.8)

        # Step B: Lower Claw Candle onto Candle Top & Light Bulb!
        with state_lock:
            menorah_fish_state["robot_arm"]["j2_shoulder"] = 60
            menorah_fish_state["robot_arm"]["j3_elbow"] = -45
            menorah_fish_state["menorah"]["candles"][idx] = True # Candle STAYS LIT!

        time.sleep(0.6)

        # Step C: Lift Arm Back Up
        with state_lock:
            menorah_fish_state["robot_arm"]["j2_shoulder"] = 30
            menorah_fish_state["robot_arm"]["j3_elbow"] = 20

        time.sleep(0.4)

    # Step D: Return Robot Arm to Standby Home Stance
    with state_lock:
        menorah_fish_state["robot_arm"]["j1_base"] = 0
        menorah_fish_state["robot_arm"]["j2_shoulder"] = 30
        menorah_fish_state["robot_arm"]["j3_elbow"] = 45
        menorah_fish_state["robot_arm"]["j4_wrist"] = 0

class MenorahFishRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, HEAD')
        self.send_header('Access-Control-Allow-Headers', 'X-Requested-With, Content-Type')
        if not self.path.startswith("/audio/") and not self.path.startswith("/lib/"):
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.end_headers()

    def do_HEAD(self):
        if self.path.startswith("/api/camera/frame"):
            self.send_response(200)
            self.send_header('Content-type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
        elif self.path.startswith("/api/export-pdf"):
            self.send_response(200)
            self.send_header('Content-type', 'application/pdf')
            self.send_header('Content-Disposition', 'attachment; filename="Menorah_Fish_Wiring_Schematic.pdf"')
            self.end_headers()
        elif self.path.startswith("/api/export-csv"):
            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.send_header('Content-Disposition', 'attachment; filename="Menorah_Fish_Hardware_Pinout.csv"')
            self.end_headers()
        elif self.path.startswith("/api/"):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
        else:
            super().do_HEAD()

    def do_GET(self):
        if self.path.startswith("/api/status"):
            self.send_json({
                "status": "online",
                "device": "Animatronic Menorah Fish & Robot Arm Controller",
                "python_version": sys.version
            })

        elif self.path.startswith("/api/menorah/state") or self.path.startswith("/api/birds/state") or self.path.startswith("/api/arm/state"):
            with state_lock:
                self.send_json(menorah_fish_state)

        elif self.path.startswith("/api/playlist"):
            audio_dir = os.path.join(DIRECTORY, "audio")
            os.makedirs(audio_dir, exist_ok=True)
            files = []
            for f in sorted(os.listdir(audio_dir)):
                if f.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac')):
                    files.append({
                        "filename": f,
                        "title": f.rsplit('.', 1)[0].replace('_', ' ').title(),
                        "url": f"/audio/{urllib.parse.quote(f)}"
                    })
            self.send_json({"songs": files})

        elif self.path.startswith("/api/camera/frame"):
            self.serve_camera_frame()

        elif self.path.startswith("/api/tts/speak"):
            query_params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            text_to_speak = query_params.get("text", ["Happy Hanukkah! Welcome to the Menorah Fish Show!"])[0]
            req_voice = query_params.get("voice", ["ai_male_us"])[0]

            with state_lock:
                menorah_fish_state["is_speaking"] = True
                menorah_fish_state["fish"]["mouth_motor"] = True
                menorah_fish_state["active_voice"] = req_voice

            try:
                from gtts import gTTS
                import io
                clean_text = re.sub(r'\*[^*]*\*', '', text_to_speak).strip() or "Happy Hanukkah!"

                tld_map = {
                    "ai_female_us": ("en", "com"),
                    "ai_male_us": ("en", "us"),
                    "ai_female_uk": ("en", "co.uk"),
                    "ai_male_uk": ("en", "co.uk"),
                    "ai_female_au": ("en", "com.au"),
                    "ai_male_au": ("en", "com.au"),
                    "ai_spanish": ("es", "com"),
                    "ai_french": ("fr", "fr")
                }
                lang, tld = tld_map.get(req_voice, ("en", "us"))
                tts = gTTS(text=clean_text, lang=lang, tld=tld)
                mp3_fp = io.BytesIO()
                tts.write_to_fp(mp3_fp)
                mp3_fp.seek(0)
                audio_bytes = mp3_fp.read()

                self.send_response(200)
                self.send_header('Content-type', 'audio/mpeg')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(audio_bytes)

            except Exception as e:
                self.send_json({"error": str(e)}, status=500)
            finally:
                def stop_speaking_delayed():
                    time.sleep(len(text_to_speak) * 0.08 + 1.2)
                    with state_lock:
                        menorah_fish_state["is_speaking"] = False
                        menorah_fish_state["fish"]["mouth_motor"] = False
                threading.Thread(target=stop_speaking_delayed, daemon=True).start()

        elif self.path.startswith("/api/export-pdf"):
            pdf_bytes = self.generate_schematic_pdf()
            desktop_dir = os.path.expanduser("~/Desktop")
            if os.path.exists(desktop_dir):
                try:
                    with open(os.path.join(desktop_dir, "Menorah_Fish_Wiring_Schematic.pdf"), "wb") as f:
                        f.write(pdf_bytes)
                except Exception: pass
            self.send_response(200)
            self.send_header('Content-type', 'application/pdf')
            self.send_header('Content-Disposition', 'attachment; filename="Menorah_Fish_Wiring_Schematic.pdf"')
            self.end_headers()
            self.wfile.write(pdf_bytes)

        elif self.path.startswith("/api/export-csv"):
            csv_path = os.path.join(DIRECTORY, "wiring_diagram.csv")
            if os.path.exists(csv_path):
                with open(csv_path, "rb") as f: csv_bytes = f.read()
            else: csv_bytes = b"Subsystem,Pin,Signal\n"

            desktop_dir = os.path.expanduser("~/Desktop")
            if os.path.exists(desktop_dir):
                try:
                    with open(os.path.join(desktop_dir, "Menorah_Fish_Hardware_Pinout.csv"), "wb") as f:
                        f.write(csv_bytes)
                except Exception: pass

            self.send_response(200)
            self.send_header('Content-type', 'text/csv')
            self.send_header('Content-Disposition', 'attachment; filename="Menorah_Fish_Hardware_Pinout.csv"')
            self.end_headers()
            self.wfile.write(csv_bytes)

        elif self.path.startswith("/api/wiring-schema"):
            self.send_json({
                "device": "Animatronic Menorah Fish & Robot Arm Controller",
                "i2c_bus": {"sda": "GPIO 2 (Pin 3)", "scl": "GPIO 3 (Pin 5)", "pca9685_address": "0x40"},
                "pca9685_channels": {
                    "0": "Robot Arm Joint 1 Base Servo (Yaw -90 to +90)",
                    "1": "Robot Arm Joint 2 Shoulder Servo (Pitch)",
                    "2": "Robot Arm Joint 3 Elbow Servo (Pitch)",
                    "3": "Dreidel Left Servo (PCA Ch 3)",
                    "4": "Dreidel Right Servo (PCA Ch 4)",
                    "5": "Robot Arm Joint 4 Wrist / Gripper Servo",
                    "6": "Center Shamash Candle Light Bulb PWM Dimmer",
                    "7": "Side Candles 1-4 Light Bulbs PWM Dimmer",
                    "8": "Side Candles 5-8 Light Bulbs PWM Dimmer",
                    "9": "Fish Head Spotlight Servo Pan",
                    "10": "Fish Head Spotlight Servo Tilt",
                    "11": "Stage Light Domes PWM Dimmer",
                    "12": "Auxiliary Output 1",
                    "13": "Auxiliary Output 2",
                    "14": "Auxiliary Output 3",
                    "15": "Stationary Fixed Base (No Servo)"
                },
                "l298_driver": {
                    "chA_mouth": "GPIO 18 ENA, GPIO 23 IN1, GPIO 24 IN2 (Forward Polarity Lipsync)",
                    "chB_body_tail": "GPIO 19 ENB, GPIO 25 IN3, GPIO 8 IN4 (Fwd Polarity 3s Body PWM Ramp / Rev Polarity Tail Wag)"
                }
            })

        else:
            super().do_GET()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
        try: data = json.loads(body)
        except json.JSONDecodeError: data = {}

        if self.path == "/api/menorah/light_candles":
            count = data.get("count", 0)
            threading.Thread(target=execute_light_menorah_candles_sequence, args=(count,), daemon=True).start()
            self.send_json({"success": True, "message": f"Lighting {count} Hanukkah candles with robot arm!"})

        elif self.path == "/api/playlist/upload":
            filename = data.get("filename", "custom_song.mp3")
            file_b64 = data.get("file_b64", "")
            if filename and file_b64:
                clean_filename = re.sub(r'[^a-zA-Z0-9_\-\.]', '_', filename)
                audio_dir = os.path.join(DIRECTORY, "audio")
                os.makedirs(audio_dir, exist_ok=True)
                file_bytes = base64.b64decode(file_b64)
                filepath = os.path.join(audio_dir, clean_filename)
                with open(filepath, "wb") as f: f.write(file_bytes)
                self.send_json({"success": True, "filename": clean_filename, "url": f"/audio/{clean_filename}"})
            else:
                self.send_json({"error": "Invalid upload payload"}, status=400)

        elif self.path == "/api/playlist/lipsync_state":
            is_singing = bool(data.get("is_singing", False))
            mouth_open = bool(data.get("mouth_open", False))
            beat_pulse = bool(data.get("beat_pulse", False))

            with state_lock:
                menorah_fish_state["is_speaking"] = False
                menorah_fish_state["is_dancing"] = is_singing
                menorah_fish_state["fish"]["mouth_motor"] = mouth_open
                if beat_pulse:
                    menorah_fish_state["fish"]["tail_motor"] = True

            self.send_json({"success": True, "state": menorah_fish_state})

        elif self.path in ["/api/menorah/state_update", "/api/birds/state_update", "/api/arm/joints"]:
            with state_lock:
                for k, v in data.items():
                    if k in menorah_fish_state and isinstance(v, dict):
                        menorah_fish_state[k].update(v)
                    elif k in menorah_fish_state:
                        menorah_fish_state[k] = v
                    elif k in menorah_fish_state["robot_arm"]:
                        menorah_fish_state["robot_arm"][k] = float(v)
            self.send_json({"success": True, "state": menorah_fish_state})

        elif self.path == "/api/camera/select":
            source = data.get("source", "usb")
            camera_stream.set_source(source)
            self.send_json({"success": True, "active_source": source})

        elif self.path == "/api/camera/reset":
            camera_stream.reset()
            self.send_json({"success": True, "message": "Camera reset successfully"})

        elif self.path == "/api/gemini/chat":
            user_text = data.get("prompt", "")
            DEFAULT_GEMINI_KEY = ""
            api_key = data.get("api_key") or os.environ.get("GEMINI_API_KEY") or DEFAULT_GEMINI_KEY
            include_vision = data.get("include_vision", True)

            image_bytes = self.capture_camera_bytes() if include_vision else None
            result = gemini_bridge.generate_chat_response(api_key, user_text, image_bytes)

            if result.get("action"):
                act = result["action"]
                if act.get("name") == "light_menorah_candles":
                    cnt = act.get("args", {}).get("count", 0)
                    threading.Thread(target=execute_light_menorah_candles_sequence, args=(cnt,), daemon=True).start()

            self.send_json(result)

        elif self.path == "/api/gemini/voice":
            DEFAULT_GEMINI_KEY = ""
            api_key = data.get("api_key") or os.environ.get("GEMINI_API_KEY") or DEFAULT_GEMINI_KEY
            audio_b64 = data.get("audio_b64", "")
            mime_type = data.get("mime_type", "audio/webm")
            include_vision = data.get("include_vision", True)

            audio_bytes = base64.b64decode(audio_b64) if audio_b64 else None
            image_bytes = self.capture_camera_bytes() if include_vision else None

            result = gemini_bridge.generate_voice_chat_response(api_key, audio_bytes, mime_type, image_bytes)

            if result.get("action"):
                act = result["action"]
                if act.get("name") == "light_menorah_candles":
                    cnt = act.get("args", {}).get("count", 0)
                    threading.Thread(target=execute_light_menorah_candles_sequence, args=(cnt,), daemon=True).start()

            self.send_json(result)

        elif self.path == "/api/export-python":
            python_script = self.generate_hardware_script(data)
            self.send_response(200)
            self.send_header('Content-type', 'application/x-python')
            self.send_header('Content-Disposition', 'attachment; filename="menorah_fish_master_driver.py"')
            self.end_headers()
            self.wfile.write(python_script.encode('utf-8'))

        else:
            self.send_json({"error": "Endpoint not found"}, status=404)

    def capture_camera_frame(self):
        return camera_stream.get_frame()

    def capture_camera_bytes(self):
        frame = self.capture_camera_frame()
        if frame is None: frame = generate_synthetic_camera_frame()
        ret, jpeg = cv2.imencode('.jpg', frame)
        return jpeg.tobytes() if ret else None

    def serve_camera_frame(self):
        jpeg_bytes = self.capture_camera_bytes()
        if jpeg_bytes is None:
            try: self.send_response(503); self.end_headers()
            except Exception: pass
            return
        try:
            self.send_response(200)
            self.send_header('Content-type', 'image/jpeg')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.end_headers()
            self.wfile.write(jpeg_bytes)
        except Exception: pass

    def send_json(self, data, status=200):
        try:
            self.send_response(status)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode('utf-8'))
        except Exception: pass

    def generate_hardware_script(self, data):
        return '''#!/usr/bin/env python3
"""
Animatronic Menorah Fish & Candle Lighting Robot Arm Master Hardware Driver
Single L298N Motor Driver Configurations:
- Channel 1 / Channel A (Fish Mouth DC Motor for Lipsync):
    * ENA = GPIO 18 (PWM), IN1 = GPIO 23, IN2 = GPIO 24
    * Forward Polarity (IN1=HIGH, IN2=LOW): Opens & closes fish mouth in sync with speech
- Channel 2 / Channel B (Fish Neck Swing & Tail Wag Motors):
    * ENB = GPIO 19 (PWM), IN3 = GPIO 25, IN4 = GPIO 8
    * Forward Polarity (IN3=HIGH, IN4=LOW): Swings Neck out (PWM 0% -> 100% over 1.2s, then DEPOWERED to 0% to prevent thermal overheating)
    * Reverse Polarity (IN3=LOW, IN4=HIGH): Drives Tail motor for wagging
- PCA9685 16-Channel PWM Servo Controller (Robot Arm Joints 1-5, Stage Servos & Dreidels, Spotlights, Domes)
"""
import time
import RPi.GPIO as GPIO
from adafruit_pca9685 import PCA9685
import board, busio

L298_ENA = 18  # Channel 1 PWM (Fish Mouth)
L298_IN1 = 23  # Direction IN1
L298_IN2 = 24  # Direction IN2

L298_ENB = 19  # Channel 2 PWM (Fish Neck & Tail)
L298_IN3 = 25  # Direction IN3
L298_IN4 = 8   # Direction IN4

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup([L298_ENA, L298_IN1, L298_IN2, L298_ENB, L298_IN3, L298_IN4], GPIO.OUT)

pwm_mouth = GPIO.PWM(L298_ENA, 1000)
pwm_body_tail = GPIO.PWM(L298_ENB, 1000)
pwm_mouth.start(0)
pwm_body_tail.start(0)

def swing_fish_neck_outstretched(duration_sec=1.2):
    """Channel 2 Forward Polarity: Swings neck out, then DEPOWERS motor (0% PWM) to prevent thermal overheating."""
    GPIO.output(L298_IN3, GPIO.HIGH)
    GPIO.output(L298_IN4, GPIO.LOW)
    steps = 15
    for i in range(1, steps + 1):
        duty = int((i / steps) * 100)
        pwm_body_tail.ChangeDutyCycle(duty)
        time.sleep(duration_sec / steps)
    # DEPOWER MOTOR AFTER EXTENSION TO PREVENT OVERHEATING WHILE TALKING:
    pwm_body_tail.ChangeDutyCycle(0)
    GPIO.output(L298_IN3, GPIO.LOW)
    GPIO.output(L298_IN4, GPIO.LOW)

def wag_fish_tail_reverse_polarity(active=True):
    """Channel 2 Reverse Polarity: Drives tail motor for tail wagging."""
    if active:
        GPIO.output(L298_IN3, GPIO.LOW)
        GPIO.output(L298_IN4, GPIO.HIGH)
        pwm_body_tail.ChangeDutyCycle(80)
    else:
        pwm_body_tail.ChangeDutyCycle(0)
        GPIO.output(L298_IN3, GPIO.LOW)
        GPIO.output(L298_IN4, GPIO.LOW)

def main():
    print("Menorah Fish L298N Master Motor Driver Online.")
    print("Testing Fish Neck Swing (Channel 2 Forward Polarity + Thermal Cutoff)...")
    swing_fish_neck_outstretched(1.2)
    time.sleep(1.0)
    print("Testing Fish Tail Wag (Channel 2 Reverse Polarity)...")
    wag_fish_tail_reverse_polarity(True)
    time.sleep(1.0)
    wag_fish_tail_reverse_polarity(False)

if __name__ == "__main__":
    try: main()
    finally: GPIO.cleanup()
'''

    def generate_schematic_pdf(self):
        import io
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('DocTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=18, textColor=colors.HexColor('#003366'), spaceAfter=4)
        subtitle_style = ParagraphStyle('DocSubTitle', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=9, textColor=colors.HexColor('#444444'), spaceAfter=10)
        heading_style = ParagraphStyle('SectionHeading', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=11, textColor=colors.HexColor('#0055a5'), spaceBefore=8, spaceAfter=4)
        cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor('#111111'))
        header_cell_style = ParagraphStyle('TableHeaderCell', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)

        story = [
            Paragraph("🦜 MENORAH FISH & CANDLE ROBOT ARM STAGE - MASTER WIRING SCHEMATIC", title_style),
            Paragraph("Complete Pinout Map for Raspberry Pi 4/5, PCA9685 PWM Driver, Dual L298N Motor Controllers & Menorah Stage", subtitle_style),
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0055a5'), spaceBefore=2, spaceAfter=8),
            Paragraph("⚡ Core System Hardware Overview", heading_style)
        ]

        overview_data = [
            [Paragraph("Module / Component", header_cell_style), Paragraph("Hardware Role & Signals", header_cell_style), Paragraph("Power Requirements", header_cell_style)],
            [Paragraph("<b>Raspberry Pi 4 / 5</b>", cell_style), Paragraph("Executes master server, Gemini AI, I2C bus (Pin 3 SDA, Pin 5 SCL), L298N drivers & Relays", cell_style), Paragraph("+5V @ 3A DC", cell_style)],
            [Paragraph("<b>PCA9685 16-Ch PWM Driver</b>", cell_style), Paragraph("I2C Address 0x40. Drives 16 PWM channels (5-DOF Robot Arm, Stage Servos, Spotlights, Domes)", cell_style), Paragraph("+5V Logic / +5V-+6V 12A V+", cell_style)],
            [Paragraph("<b>Single L298N Motor Driver</b>", cell_style), Paragraph("Ch A: Fish Mouth DC Motor (Forward Polarity Lipsync). Ch B: Fish Body 3s PWM Ramp Swing Out (Fwd) & Tail Reverse Polarity Wag", cell_style), Paragraph("+5V/+6V High-Current Rail", cell_style)]
        ]
        t_overview = Table(overview_data, colWidths=[150, 430, 140])
        t_overview.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#ffffff'), colors.HexColor('#f5f8ff')])
        ]))
        story.append(t_overview)
        doc.build(story)
        return buffer.getvalue()

class ThreadingReusableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True
    ssl_context = None

    def get_request(self):
        newsocket, fromaddr = self.socket.accept()
        if self.ssl_context:
            try:
                newsocket.settimeout(1.5)
                first_byte = newsocket.recv(1, socket.MSG_PEEK)
                if first_byte and len(first_byte) > 0 and first_byte[0] == 0x16:
                    newsocket = self.ssl_context.wrap_socket(newsocket, server_side=True)
                newsocket.settimeout(None)
            except Exception:
                try: newsocket.settimeout(None)
                except Exception: pass
        return newsocket, fromaddr

if __name__ == "__main__":
    for i in range(1, len(sys.argv)):
        if sys.argv[i] == "--port" and i + 1 < len(sys.argv):
            PORT = int(sys.argv[i + 1])
        elif sys.argv[i] == "--host" and i + 1 < len(sys.argv):
            HOST = sys.argv[i + 1]

    cert_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cert.pem")
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "key.pem")
    if not (os.path.exists(cert_path) and os.path.exists(key_path)):
        cert_path = "/home/markirgang/Tweedpump/cert.pem"
        key_path = "/home/markirgang/Tweedpump/key.pem"

    ssl_ctx = None
    if os.path.exists(cert_path) and os.path.exists(key_path):
        try:
            ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ssl_ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
        except Exception as e:
            print(f"SSL cert load warning: {e}")

    display_host = "localhost" if HOST in ["", "0.0.0.0", "127.0.0.1"] else HOST
    print(f"Starting Animatronic Menorah Fish Server on http://{display_host}:{PORT} (http & https supported)")
    bind_host = "" if HOST == "0.0.0.0" else HOST
    with ThreadingReusableTCPServer((bind_host, PORT), MenorahFishRequestHandler) as httpd:
        httpd.ssl_context = ssl_ctx
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
