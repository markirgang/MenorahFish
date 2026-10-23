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

    # 4 Stage Light Domes (Individual IRLZ44N MOSFETs & Pi GPIOs):
    "light_domes": {
        "breathing": False,
        "mouth_side_dome1": 100,    # GPIO 4 (Pin 7) -> IRLZ44N MOSFET PWM (0-100%)
        "mouth_side_dome2": 100,    # GPIO 12 (Pin 32) -> IRLZ44N MOSFET PWM (0-100%)
        "tail_side_dome1": 100,     # GPIO 7 (Pin 26) -> IRLZ44N MOSFET PWM (0-100%)
        "tail_side_dome2": 100      # GPIO 1 (Pin 28) -> IRLZ44N MOSFET PWM (0-100%)
    },

    # 3 Stage Spotlights (Individual IRLZ44N MOSFETs & Pi GPIOs):
    "spotlights": {
        "fish_spot": 100,           # GPIO 16 (Pin 36) -> IRLZ44N MOSFET PWM (0-100%)
        "left_spot": 100,           # GPIO 20 (Pin 38) -> IRLZ44N MOSFET PWM (0-100%)
        "right_spot": 100           # GPIO 21 (Pin 40) -> IRLZ44N MOSFET PWM (0-100%)
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

            # 1. Fish Neck Swing Logic (L298 Ch B Forward Polarity driving original OEM Neck Motor)
            if is_speaking:
                speak_stop_time = None
                if speak_start_time is None:
                    speak_start_time = now

                # Swing neck out to full extension (1.0) over 1.0s and HOLD powered while talking
                elapsed_speak = now - speak_start_time
                target_pos = min(1.0, elapsed_speak / 1.0)
                fish["neck_position"] = target_pos
                fish["neck_motor_pwm"] = 100  # Held active forward to hold neck extended against OEM spring while talking

                # Head spotlight bright during speech.
                # NOTE: Tail motor CANNOT wag while speaking/singing because Channel 2 is in Forward Polarity for the neck motor!
                fish["head_spotlight"] = True
                fish["tail_motor"] = False

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

                # When talking stops, depower motor (0% PWM) so OEM return spring retracts neck flat against plaque
                elapsed_stop = now - speak_stop_time
                target_pos = max(0.0, 1.0 - (elapsed_stop / 0.8))

                fish["neck_position"] = target_pos
                fish["neck_motor_pwm"] = 0  # Motor depowered; OEM return spring retracts neck

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

# --- 5-DOF ROBOT ARM KINEMATIC ROUTINES & GESTURES ---

def execute_arm_rest_position():
    """Returns the 5-DOF Robot Arm to standard rest / park standby position."""
    with state_lock:
        menorah_fish_state["robot_arm"]["j1_base"] = 0
        menorah_fish_state["robot_arm"]["j2_shoulder"] = 30
        menorah_fish_state["robot_arm"]["j3_elbow"] = 45
        menorah_fish_state["robot_arm"]["j4_wrist"] = 0
        menorah_fish_state["robot_arm"]["j5_gripper"] = 50

def execute_arm_high_five():
    """Performs a High-Five gesture with the 5-DOF Robot Arm."""
    # Step A: Center base and raise arm high
    with state_lock:
        menorah_fish_state["robot_arm"]["j1_base"] = 0
        menorah_fish_state["robot_arm"]["j2_shoulder"] = 75
        menorah_fish_state["robot_arm"]["j3_elbow"] = 20
        menorah_fish_state["robot_arm"]["j4_wrist"] = 40

    time.sleep(0.6)

    # Step B: Push forward into High Five contact!
    with state_lock:
        menorah_fish_state["robot_arm"]["j2_shoulder"] = 85
        menorah_fish_state["robot_arm"]["j4_wrist"] = 55

    time.sleep(1.2)

    # Step C: Return to Rest Stance
    execute_arm_rest_position()

def execute_arm_nod_yes():
    """Performs a smooth 'Nod Yes' gesture by tilting shoulder, elbow, and wrist joints up and down twice."""
    with state_lock:
        menorah_fish_state["robot_arm"]["j1_base"] = 0

    for _ in range(2):
        # Nod Down
        with state_lock:
            menorah_fish_state["robot_arm"]["j2_shoulder"] = 55
            menorah_fish_state["robot_arm"]["j3_elbow"] = -20
            menorah_fish_state["robot_arm"]["j4_wrist"] = -30
        time.sleep(0.35)

        # Nod Up
        with state_lock:
            menorah_fish_state["robot_arm"]["j2_shoulder"] = 20
            menorah_fish_state["robot_arm"]["j3_elbow"] = 60
            menorah_fish_state["robot_arm"]["j4_wrist"] = 20
        time.sleep(0.35)

    execute_arm_rest_position()

def execute_arm_shake_no():
    """Performs a smooth 'Shake No' gesture by sweeping base/shoulder yaw left and right twice."""
    with state_lock:
        menorah_fish_state["robot_arm"]["j2_shoulder"] = 40
        menorah_fish_state["robot_arm"]["j3_elbow"] = 30
        menorah_fish_state["robot_arm"]["j4_wrist"] = 0

    for _ in range(2):
        # Shake Left
        with state_lock:
            menorah_fish_state["robot_arm"]["j1_base"] = -35
        time.sleep(0.35)

        # Shake Right
        with state_lock:
            menorah_fish_state["robot_arm"]["j1_base"] = 35
        time.sleep(0.35)

    execute_arm_rest_position()

def trigger_arm_action(action_name, args=None):
    action_name = str(action_name).lower().strip()
    if any(k in action_name for k in ["rest", "home", "park", "standby"]):
        threading.Thread(target=execute_arm_rest_position, daemon=True).start()
    elif "five" in action_name or "high_five" in action_name:
        threading.Thread(target=execute_arm_high_five, daemon=True).start()
    elif any(k in action_name for k in ["yes", "nod"]):
        threading.Thread(target=execute_arm_nod_yes, daemon=True).start()
    elif any(k in action_name for k in ["no", "shake"]):
        threading.Thread(target=execute_arm_shake_no, daemon=True).start()
    elif any(k in action_name for k in ["candle", "light"]):
        count = 8
        if args and isinstance(args, dict) and "count" in args:
            count = int(args["count"])
        threading.Thread(target=execute_light_menorah_candles_sequence, args=(count,), daemon=True).start()
def execute_light_menorah_candles_sequence(count):
    count = max(0, min(8, int(count)))
    with state_lock:
        menorah_fish_state["menorah"]["lit_count"] = count
        # Extinguish all candle light bulbs initially
        menorah_fish_state["menorah"]["candles"] = [False] * 9

    time.sleep(0.5)

    if count == 0:
        execute_arm_rest_position()
        return

    # Always light Center Shamash Candle (Index 4) first
    with state_lock:
        menorah_fish_state["menorah"]["candles"][4] = True

    arc_angles = [-80, -60, -40, -20, 0, 20, 40, 60, 80]
    side_order = [3, 5, 2, 6, 1, 7, 0, 8] # Light inner to outer candles
    target_indices = [side_order[i] for i in range(min(count, 8))]

    for idx in target_indices:
        target_angle = arc_angles[idx]

        # Step 1: Rotate shoulder/base J1 to align arm with target candle
        with state_lock:
            menorah_fish_state["robot_arm"]["j1_base"] = target_angle
            menorah_fish_state["robot_arm"]["j2_shoulder"] = 35
            menorah_fish_state["robot_arm"]["j3_elbow"] = 25
            menorah_fish_state["robot_arm"]["j4_wrist"] = 0

        time.sleep(0.6)

        # Step 2: Coordinate Shoulder (J2), Elbow (J3), and Wrist (J4) TOGETHER
        # to lower the claw candle flame tip directly onto the top bulb of the menorah candle!
        with state_lock:
            menorah_fish_state["robot_arm"]["j2_shoulder"] = 55
            menorah_fish_state["robot_arm"]["j3_elbow"] = -35
            menorah_fish_state["robot_arm"]["j4_wrist"] = -25
            # Light the candle bulb!
            menorah_fish_state["menorah"]["candles"][idx] = True

        time.sleep(0.8) # Hold flame touching candle top to make it look like it lights it!

        # Step 3: Return Wrist (J4), Elbow (J3), and Shoulder (J2) back to rest stance TOGETHER
        with state_lock:
            menorah_fish_state["robot_arm"]["j4_wrist"] = 0
            menorah_fish_state["robot_arm"]["j3_elbow"] = 45
            menorah_fish_state["robot_arm"]["j2_shoulder"] = 30

        time.sleep(0.5)

    # Step 4: Park arm at rest stance after lighting last candle
    execute_arm_rest_position()

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
                "120vac_ssr_candles": {
                    "shamash_candle": "GPIO 17 (Pin 11) -> 3.3V DC SSR for 120VAC Center Shamash Candle",
                    "side_candle_1": "GPIO 27 (Pin 13) -> 3.3V DC SSR for 120VAC Menorah Side Candle 1",
                    "side_candle_2": "GPIO 22 (Pin 15) -> 3.3V DC SSR for 120VAC Menorah Side Candle 2",
                    "side_candle_3": "GPIO 10 (Pin 19) -> 3.3V DC SSR for 120VAC Menorah Side Candle 3",
                    "side_candle_4": "GPIO 9 (Pin 21) -> 3.3V DC SSR for 120VAC Menorah Side Candle 4",
                    "side_candle_5": "GPIO 11 (Pin 23) -> 3.3V DC SSR for 120VAC Menorah Side Candle 5",
                    "side_candle_6": "GPIO 5 (Pin 29) -> 3.3V DC SSR for 120VAC Menorah Side Candle 6",
                    "side_candle_7": "GPIO 6 (Pin 31) -> 3.3V DC SSR for 120VAC Menorah Side Candle 7",
                    "side_candle_8": "GPIO 13 (Pin 33) -> 3.3V DC SSR for 120VAC Menorah Side Candle 8"
                },
                "individual_mosfet_lights": {
                    "mouth_side_dome1": "GPIO 4 (Pin 7) -> IRLZ44N MOSFET Gate (220Ω / 10kΩ GND) -> 12V DC Dome Light 1",
                    "mouth_side_dome2": "GPIO 12 (Pin 32) -> IRLZ44N MOSFET Gate (220Ω / 10kΩ GND) -> 12V DC Dome Light 2",
                    "tail_side_dome1": "GPIO 7 (Pin 26) -> IRLZ44N MOSFET Gate (220Ω / 10kΩ GND) -> 12V DC Dome Light 3",
                    "tail_side_dome2": "GPIO 1 (Pin 28) -> IRLZ44N MOSFET Gate (220Ω / 10kΩ GND) -> 12V DC Dome Light 4",
                    "fish_mouth_spotlight": "GPIO 16 (Pin 36) -> IRLZ44N MOSFET Gate (220Ω / 10kΩ GND) -> 12V DC Middle Fish Spotlight",
                    "left_dreidel_spotlight": "GPIO 20 (Pin 38) -> IRLZ44N MOSFET Gate (220Ω / 10kΩ GND) -> 12V DC Left Dreidel Spotlight",
                    "right_dreidel_spotlight": "GPIO 21 (Pin 40) -> IRLZ44N MOSFET Gate (220Ω / 10kΩ GND) -> 12V DC Right Dreidel Spotlight"
                },
                "pca9685_channels_servos_only": {
                    "0": "Robot Arm Joint 1 Base Yaw Servo (-90° to +90°)",
                    "1": "Robot Arm Joint 2 Shoulder Pitch Servo (-90° to +90°)",
                    "2": "Robot Arm Joint 3 Elbow Pitch Servo (-135° to +135°)",
                    "3": "Stage Servo 1 (Mouth-Side Servo & Spinning Dreidel)",
                    "4": "Stage Servo 2 (Tail-Side Servo & Spinning Dreidel)",
                    "5": "Robot Arm Joint 4/5 Wrist Pitch & Gripper Claw Servo",
                    "10": "Fish Head Spotlight Pan Servo",
                    "11": "Fish Head Spotlight Tilt Servo"
                },
                "l298_driver": {
                    "ch1_mouth": "GPIO 18 ENA, GPIO 23 IN1, GPIO 24 IN2 (Forward Polarity OEM Mouth Motor)",
                    "ch2_neck_tail": "GPIO 19 ENB, GPIO 25 IN3, GPIO 8 IN4 (Fwd Polarity OEM Neck Motor / Rev Polarity OEM Tail Motor)"
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

        elif self.path == "/api/arm/action":
            act = data.get("action") or data.get("gesture") or "rest"
            trigger_arm_action(act, data)
            self.send_json({"success": True, "action": act})

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
                act_name = act.get("name", "")
                if act_name == "light_menorah_candles":
                    cnt = act.get("args", {}).get("count", 0)
                    threading.Thread(target=execute_light_menorah_candles_sequence, args=(cnt,), daemon=True).start()
                elif act_name in ["arm_pose", "arm_gesture", "arm_move", "arm_action"]:
                    pose = act.get("args", {}).get("pose_name") or act.get("args", {}).get("gesture_name") or act_name
                    trigger_arm_action(pose, act.get("args"))

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
                act_name = act.get("name", "")
                if act_name == "light_menorah_candles":
                    cnt = act.get("args", {}).get("count", 0)
                    threading.Thread(target=execute_light_menorah_candles_sequence, args=(cnt,), daemon=True).start()
                elif act_name in ["arm_pose", "arm_gesture", "arm_move", "arm_action"]:
                    pose = act.get("args", {}).get("pose_name") or act.get("args", {}).get("gesture_name") or act_name
                    trigger_arm_action(pose, act.get("args"))

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
Single L298N Motor Driver Configurations (100% Original OEM Gemmy Fish Hardware & Motors):
- Channel 1 / Channel A (Original OEM Mouth DC Motor):
    * ENA = GPIO 18 (PWM), IN1 = GPIO 23, IN2 = GPIO 24
    * Forward Polarity (IN1=HIGH, IN2=LOW): Opens mouth in sync with speech
- Channel 2 / Channel B (Original OEM Neck & Tail DC Motors):
    * ENB = GPIO 19 (PWM), IN3 = GPIO 25, IN4 = GPIO 8
    * Forward Polarity (IN3=HIGH, IN4=LOW): Powers OEM neck motor to extend neck out and hold it extended while talking.
    * Depower (IN3=LOW, IN4=LOW): Depowers neck motor when done talking, allowing OEM return spring to pull neck flat against plaque.
    * Reverse Polarity (IN3=LOW, IN4=HIGH): Powers original OEM tail motor for tail wagging.
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

def swing_fish_neck_outstretched(hold_sec=3.0):
    """Channel 2 Forward Polarity (IN3=HIGH, IN4=LOW): Powers OEM neck motor forward to extend neck out and holds it extended while talking."""
    GPIO.output(L298_IN3, GPIO.HIGH)
    GPIO.output(L298_IN4, GPIO.LOW)
    pwm_body_tail.ChangeDutyCycle(100)
    time.sleep(hold_sec)

def retract_fish_neck():
    """Channel 2 Depower (IN3=LOW, IN4=LOW): Depowers OEM neck motor, allowing original OEM return spring to retract neck flat against plaque."""
    pwm_body_tail.ChangeDutyCycle(0)
    GPIO.output(L298_IN3, GPIO.LOW)
    GPIO.output(L298_IN4, GPIO.LOW)

def wag_fish_tail_reverse_polarity(active=True):
    """Channel 2 Reverse Polarity (IN3=LOW, IN4=HIGH): Drives original OEM tail motor for tail wagging."""
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
    print("Testing Fish Neck Swing (Channel 2 Forward Polarity - OEM Neck Motor)...")
    swing_fish_neck_outstretched(3.0)
    print("Retracting Neck (OEM Return Spring)...")
    retract_fish_neck()
    time.sleep(1.0)
    print("Testing Fish Tail Wag (Channel 2 Reverse Polarity - OEM Tail Motor)...")
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
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
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
            Paragraph("Page 1 of 2: Complete Pinout Map for Raspberry Pi 4/5, PCA9685 PWM Driver, L298N Motor Controllers, SSRs & Stage Lighting", subtitle_style),
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0055a5'), spaceBefore=2, spaceAfter=8),
            Paragraph("⚡ Core System Hardware Overview", heading_style)
        ]

        overview_data = [
            [Paragraph("Module / Component", header_cell_style), Paragraph("Hardware Role & Signals", header_cell_style), Paragraph("Power Requirements", header_cell_style)],
            [Paragraph("<b>Raspberry Pi 4 / 5</b>", cell_style), Paragraph("Executes master server, Gemini AI, I2C bus (Pin 3 SDA, Pin 5 SCL), SSR Triggers, MOSFET PWM & L298N drivers", cell_style), Paragraph("+5V @ 3A DC", cell_style)],
            [Paragraph("<b>PCA9685 16-Ch PWM Driver</b>", cell_style), Paragraph("I2C Address 0x40. Drives 16 PWM channels (5-DOF Robot Arm, Stage Servos & Spinning Dreidels)", cell_style), Paragraph("3.3V DC Logic VCC / +5V-+6V 12A V+", cell_style)],
            [Paragraph("<b>Single L298N Motor Driver</b>", cell_style), Paragraph("Ch 1: OEM Mouth DC Motor (Forward Polarity). Ch 2: OEM Neck Motor (Fwd Polarity) & OEM Tail Motor (Rev Polarity)", cell_style), Paragraph("+5V/+6V High-Current Rail", cell_style)],
            [Paragraph("<b>120VAC Solid State Relays (10x)</b>", cell_style), Paragraph("10x 3.3V DC Triggered SSRs for 8 Menorah Side Candles, 1 Shamash Candle, and 1 Claw Candle", cell_style), Paragraph("3.3V DC Logic / 120VAC Line", cell_style)],
            [Paragraph("<b>MOSFET Power Transistors (4x)</b>", cell_style), Paragraph("4x MOSFET Gate Switches for Dimmable 4 Stage Domes (Breathing/Chases) & 3 Pole Spotlights", cell_style), Paragraph("3.3V DC PWM / 12V Stage Power", cell_style)]
        ]
        t_overview = Table(overview_data, colWidths=[150, 430, 140])
        t_overview.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#ffffff'), colors.HexColor('#f5f8ff')])
        ]))
        story.append(t_overview)
        story.append(Spacer(1, 8))

        # Complete Pinout Map Table
        story.append(Paragraph("📋 Complete GPIO & PCA9685 Pinout Connection Lookup Table", heading_style))
        pinout_rows = [[
            Paragraph("Header / Module", header_cell_style),
            Paragraph("Pin / Ch #", header_cell_style),
            Paragraph("Signal Name", header_cell_style),
            Paragraph("Connected Hardware Module", header_cell_style),
            Paragraph("Terminal", header_cell_style),
            Paragraph("Function Description", header_cell_style)
        ]]

        pinout_items = [
            ("Raspberry Pi", "Pin 3", "GPIO 2 (SDA1)", "PCA9685 PWM Driver", "SDA Terminal", "I2C Serial Data Bus for 16-Channel Servo Controller"),
            ("Raspberry Pi", "Pin 5", "GPIO 3 (SCL1)", "PCA9685 PWM Driver", "SCL Terminal", "I2C Serial Clock Line for 16-Channel Servo Controller"),
            ("Raspberry Pi", "Pin 7", "GPIO 4", "Claw Candle 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Claw Candle (Always ON)"),
            ("Raspberry Pi", "Pin 11", "GPIO 17", "Shamash Candle 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Center Shamash Candle"),
            ("Raspberry Pi", "Pin 13", "GPIO 27", "Side Candle 1 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Side Candle 1"),
            ("Raspberry Pi", "Pin 15", "GPIO 22", "Side Candle 2 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Side Candle 2"),
            ("Raspberry Pi", "Pin 19", "GPIO 10", "Side Candle 3 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Side Candle 3"),
            ("Raspberry Pi", "Pin 21", "GPIO 9", "Side Candle 4 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Side Candle 4"),
            ("Raspberry Pi", "Pin 23", "GPIO 11", "Side Candle 5 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Side Candle 5"),
            ("Raspberry Pi", "Pin 29", "GPIO 5", "Side Candle 6 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Side Candle 6"),
            ("Raspberry Pi", "Pin 31", "GPIO 6", "Side Candle 7 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Side Candle 7"),
            ("Raspberry Pi", "Pin 33", "GPIO 13", "Side Candle 8 120VAC SSR", "DC Input Terminal", "3.3V DC Solid State Relay for 120VAC Side Candle 8"),
            ("Raspberry Pi", "Pin 32", "GPIO 12 (PWM)", "4 Stage Light Domes MOSFET", "Gate Terminal", "MOSFET Power Switch / PWM Dimmer for 4 Stage Light Domes"),
            ("Raspberry Pi", "Pin 36", "GPIO 16 (PWM)", "Fish Mouth Spotlight MOSFET", "Gate Terminal", "MOSFET Power Switch / PWM Dimmer for Fish Spotlight"),
            ("Raspberry Pi", "Pin 38", "GPIO 20 (PWM)", "Left Dreidel Spotlight MOSFET", "Gate Terminal", "MOSFET Power Switch / PWM Dimmer for Left Dreidel Spotlight"),
            ("Raspberry Pi", "Pin 40", "GPIO 21 (PWM)", "Right Dreidel Spotlight MOSFET", "Gate Terminal", "MOSFET Power Switch / PWM Dimmer for Right Dreidel Spotlight"),
            ("Raspberry Pi", "Pin 12", "GPIO 18 (PWM)", "L298N Motor Driver", "ENA Terminal", "Channel 1: OEM Mouth DC Motor Speed PWM"),
            ("Raspberry Pi", "Pin 16", "GPIO 23", "L298N Motor Driver", "IN1 Terminal", "Channel 1: OEM Mouth Direction 1 (Forward Polarity)"),
            ("Raspberry Pi", "Pin 18", "GPIO 24", "L298N Motor Driver", "IN2 Terminal", "Channel 1: OEM Mouth Direction 2 (Forward Polarity)"),
            ("Raspberry Pi", "Pin 35", "GPIO 19 (PWM)", "L298N Motor Driver", "ENB Terminal", "Channel 2: OEM Neck & Tail DC Motors Speed PWM"),
            ("Raspberry Pi", "Pin 22", "GPIO 25", "L298N Motor Driver", "IN3 Terminal", "Channel 2: OEM Neck Forward Swing / Tail Reverse Wag"),
            ("Raspberry Pi", "Pin 24", "GPIO 8", "L298N Motor Driver", "IN4 Terminal", "Channel 2: OEM Neck Forward Swing / Tail Reverse Wag"),
            ("PCA9685 PWM", "Ch 0 - 2", "PWM Servo Out", "Robot Arm Joints 1-3", "Servos", "Base Yaw (-90° to +90°), Shoulder Pitch, Elbow Pitch"),
            ("PCA9685 PWM", "Ch 3 - 4", "PWM Servo Out", "Mouth & Tail Side Servos", "Servos", "Stage Servos & Spinning Dreidels"),
            ("PCA9685 PWM", "Ch 5", "PWM Servo Out", "Robot Arm Joint 4/5 Claw", "Servo", "Wrist Pitch & Gripper Candle Claw")
        ]

        for item in pinout_items:
            pinout_rows.append([
                Paragraph(f"<b>{item[0]}</b>", cell_style),
                Paragraph(f"<b>{item[1]}</b>", cell_style),
                Paragraph(f"<code>{item[2]}</code>", cell_style),
                Paragraph(item[3], cell_style),
                Paragraph(item[4], cell_style),
                Paragraph(item[5], cell_style)
            ])

        t_pinout = Table(pinout_rows, colWidths=[90, 65, 95, 125, 85, 260])
        t_pinout.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0055a5')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafd')])
        ]))
        story.append(t_pinout)

        # --- PAGE 2: FRITZING-STYLE VISUAL PINOUT DIAGRAM PAGE ---
        story.append(PageBreak())
        story.append(Paragraph("🍓 FRITZING-STYLE RASPBERRY PI GPIO & PCA9685 PINOUT DIAGRAM", title_style))
        story.append(Paragraph("Page 2 of 3: Visual Labeled Hardware Pinout Diagrams for Raspberry Pi 40-Pin Header & PCA9685 16-Channel Board", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0055a5'), spaceBefore=2, spaceAfter=8))

        story.append(Paragraph("📌 Raspberry Pi 40-Pin GPIO Header (Dual-Row Fritzing-Style Pin Layout)", heading_style))

        # 40-Pin Dual Row Table (Odd pins on left, Even pins on right)
        rpi_header_rows = [[
            Paragraph("Odd Pin (Left)", header_cell_style),
            Paragraph("BCM Signal / Function", header_cell_style),
            Paragraph("Pin #", header_cell_style),
            Paragraph("Pin #", header_cell_style),
            Paragraph("BCM Signal / Function", header_cell_style),
            Paragraph("Even Pin (Right)", header_cell_style)
        ]]

        rpi_pin_pairs = [
            ("3.3V Power", "Pin 1", "Pin 2", "5.0V Power"),
            ("GPIO 2 (SDA1) - I2C Data", "Pin 3", "Pin 4", "5.0V Power"),
            ("GPIO 3 (SCL1) - I2C Clock", "Pin 5", "Pin 6", "Ground (GND)"),
            ("GPIO 4 - Claw Candle SSR", "Pin 7", "Pin 8", "GPIO 14 (TX)"),
            ("Ground (GND)", "Pin 9", "Pin 10", "GPIO 15 (RX)"),
            ("GPIO 17 - Shamash Candle SSR", "Pin 11", "Pin 12", "GPIO 18 (PWM) - L298 Ch1 ENA"),
            ("GPIO 27 - Side Candle 1 SSR", "Pin 13", "Pin 14", "Ground (GND)"),
            ("GPIO 22 - Side Candle 2 SSR", "Pin 15", "Pin 16", "GPIO 23 - L298 Ch1 IN1"),
            ("3.3V Power", "Pin 17", "Pin 18", "GPIO 24 - L298 Ch1 IN2"),
            ("GPIO 10 - Side Candle 3 SSR", "Pin 19", "Pin 20", "Ground (GND)"),
            ("GPIO 9 - Side Candle 4 SSR", "Pin 21", "Pin 22", "GPIO 25 - L298 Ch2 IN3"),
            ("GPIO 11 - Side Candle 5 SSR", "Pin 23", "Pin 24", "GPIO 8 - L298 Ch2 IN4"),
            ("Ground (GND)", "Pin 25", "Pin 26", "GPIO 7"),
            ("GPIO 0 (ID_SD)", "Pin 27", "Pin 28", "GPIO 1 (ID_SC)"),
            ("GPIO 5 - Side Candle 6 SSR", "Pin 29", "Pin 30", "Ground (GND)"),
            ("GPIO 6 - Side Candle 7 SSR", "Pin 31", "Pin 32", "GPIO 12 (PWM) - Stage Domes MOSFET"),
            ("GPIO 13 - Side Candle 8 SSR", "Pin 33", "Pin 34", "Ground (GND)"),
            ("GPIO 19 (PWM) - L298 Ch2 ENB", "Pin 35", "Pin 36", "GPIO 16 (PWM) - Fish Spot MOSFET"),
            ("GPIO 26", "Pin 37", "Pin 38", "GPIO 20 (PWM) - Left Spot MOSFET"),
            ("Ground (GND)", "Pin 39", "Pin 40", "GPIO 21 (PWM) - Right Spot MOSFET")
        ]

        for left_sig, left_p, right_p, right_sig in rpi_pin_pairs:
            # Color accents
            left_bg = "#f5f8ff"
            right_bg = "#ffffff"
            if "5.0V" in left_sig or "5.0V" in right_sig or "3.3V" in left_sig or "3.3V" in right_sig:
                left_bg = "#fff5f5" if "V" in left_sig else left_bg
                right_bg = "#fff5f5" if "V" in right_sig else right_bg
            elif "GND" in left_sig or "Ground" in right_sig or "Ground" in left_sig or "GND" in right_sig:
                left_bg = "#f0f0f0" if "GND" in left_sig or "Ground" in left_sig else left_bg
                right_bg = "#f0f0f0" if "GND" in right_sig or "Ground" in right_sig else right_bg

            rpi_header_rows.append([
                Paragraph(f"<b>{left_sig}</b>", cell_style),
                Paragraph(f"<code>{left_sig.split(' - ')[0]}</code>", cell_style),
                Paragraph(f"<b>{left_p}</b>", cell_style),
                Paragraph(f"<b>{right_p}</b>", cell_style),
                Paragraph(f"<code>{right_sig.split(' - ')[0]}</code>", cell_style),
                Paragraph(f"<b>{right_sig}</b>", cell_style)
            ])

        t_rpi = Table(rpi_header_rows, colWidths=[150, 100, 45, 45, 100, 150])
        t_rpi.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0055a5')),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
            ('BACKGROUND', (2,1), (2,-1), colors.HexColor('#e6f2ff')),
            ('BACKGROUND', (3,1), (3,-1), colors.HexColor('#e6f2ff'))
        ]))
        story.append(t_rpi)
        story.append(Spacer(1, 10))

        # PCA9685 Fritzing Pinout Table
        story.append(Paragraph("🎛️ PCA9685 16-Channel PWM Servo Driver (Pinout Diagram & Signal Map)", heading_style))
        pca_rows = [[
            Paragraph("Terminal / Channel", header_cell_style),
            Paragraph("Signal Type", header_cell_style),
            Paragraph("Target Module Connected", header_cell_style),
            Paragraph("Function Description", header_cell_style),
            Paragraph("Output Voltage / Power", header_cell_style)
        ]]

        pca_items = [
            ("I2C Header", "SDA / SCL / VCC / GND", "Raspberry Pi GPIO 2, 3 & 3.3V Pin 1", "I2C Serial Communication Bus (Addr: 0x40)", "3.3V DC VCC Logic"),
            ("Ext Power V+", "V+ Screw Terminal", "5V / 6V 12A Power Supply", "High-Current Servo Power Rail", "5V - 6V DC @ 12A"),
            ("Channel 0", "PWM Servo Out", "Robot Arm Joint 1 Base", "Base Rotation Servo (-90° to +90°)", "5V Servo Power"),
            ("Channel 1", "PWM Servo Out", "Robot Arm Joint 2 Shoulder", "Shoulder Pitch Servo (-90° to +90°)", "5V Servo Power"),
            ("Channel 2", "PWM Servo Out", "Robot Arm Joint 3 Elbow", "Elbow Pitch Servo (-135° to +135°)", "5V Servo Power"),
            ("Channel 3", "PWM Servo Out", "Stage Servo 1 (Mouth Side)", "Sweeps Mouth-Side Servo & Spinning Dreidel", "5V Servo Power"),
            ("Channel 4", "PWM Servo Out", "Stage Servo 2 (Tail Side)", "Sweeps Tail-Side Servo & Spinning Dreidel", "5V Servo Power"),
            ("Channel 5", "PWM Servo Out", "Robot Arm Joint 4/5 Claw", "Wrist Pitch & Gripper Candle Claw", "5V Servo Power"),
            ("Channel 6", "PWM Dimmer Out", "Center Fish Spot MOSFET", "3.3V Gate MOSFET -> 12V Fish Mouth Spotlight", "3.3V PWM / 12V DC"),
            ("Channel 7", "PWM Dimmer Out", "Left Dreidel Spot MOSFET", "3.3V Gate MOSFET -> 12V Left Dreidel Spotlight", "3.3V PWM / 12V DC"),
            ("Channel 8", "PWM Dimmer Out", "Right Dreidel Spot MOSFET", "3.3V Gate MOSFET -> 12V Right Dreidel Spotlight", "3.3V PWM / 12V DC"),
            ("Channel 9", "PWM Dimmer Out", "4 Stage Light Domes MOSFET", "3.3V Gate MOSFET -> 12V 4 Stage Light Domes (Breathing/Chases)", "3.3V PWM / 12V DC"),
            ("Channel 10", "PWM Servo Out", "Fish Head Spotlight Pan", "Fish Head Spotlight Servo Pan", "5V Servo Power"),
            ("Channel 11", "PWM Servo Out", "Fish Head Spotlight Tilt", "Fish Head Spotlight Servo Tilt", "5V Servo Power")
        ]

        for item in pca_items:
            pca_rows.append([
                Paragraph(f"<b>{item[0]}</b>", cell_style),
                Paragraph(item[1], cell_style),
                Paragraph(f"<b>{item[2]}</b>", cell_style),
                Paragraph(item[3], cell_style),
                Paragraph(item[4], cell_style)
            ])

        t_pca = Table(pca_rows, colWidths=[110, 100, 140, 150, 90])
        t_pca.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cccccc')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#ffffff'), colors.HexColor('#f5f8ff')])
        ]))
        story.append(t_pca)

        # --- PAGE 3: COMPLETE BILL OF MATERIALS & PARTS LIST ---
        story.append(PageBreak())
        story.append(Paragraph("📦 MENORAH FISH & ROBOT ARM STAGE - BILL OF MATERIALS (PARTS LIST)", title_style))
        story.append(Paragraph("Page 3 of 3: Complete Parts Specification, Quantities, Power Requirements & Subsystem Roles", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#0055a5'), spaceBefore=2, spaceAfter=8))

        bom_rows = [[
            Paragraph("Item #", header_cell_style),
            Paragraph("Component / Part Name", header_cell_style),
            Paragraph("Specification / Model", header_cell_style),
            Paragraph("Qty", header_cell_style),
            Paragraph("Subsystem Role & Interface", header_cell_style),
            Paragraph("Power / Voltage", header_cell_style)
        ]]

        bom_data_items = [
            ("1", "Raspberry Pi 4 or 5", "4GB / 8GB RAM Model B", "1", "Master Application & Server Controller, I2C Bus, GPIO Triggers", "5V @ 3A DC (Type-C)"),
            ("2", "Gemmy Animatronic Trout Fish", "Original OEM Big Mouth Billy Bass / Trout", "1", "OEM Mouth Motor (Ch 1) & OEM Neck/Tail Motors (Ch 2) on Wooden Plaque", "5V - 6V DC High Current"),
            ("3", "5-DOF Robot Arm Kit", "Aluminum Alloy Arm with Claw & Candle Holder", "1", "5-DOF Candle Lighting Robot Arm holding 120VAC Claw Candle", "5V - 6V DC (PCA9685 V+)"),
            ("4", "PCA9685 PWM Servo Driver", "16-Channel 12-Bit I2C Board (0x40)", "1", "Drives 6 Servos (Robot Arm J1-J5, Stage Servos & Dreidels)", "5V Logic / 5V-6V V+"),
            ("5", "L298N Dual H-Bridge Motor Driver", "Dual Channel DC Motor Controller", "1", "Ch 1: OEM Mouth Motor Fwd | Ch 2: OEM Neck Motor Fwd / Tail Motor Rev", "5V - 6V DC Motor Power"),
            ("6", "Solid State Relays (SSRs)", "3.3V DC Trigger / 120VAC Output SSRs", "10", "Controls 10 120VAC Candle Bulbs (8 Side + 1 Shamash + 1 Claw Candle)", "3.3V DC Trigger / 120VAC Line"),
            ("7", "MOSFET Power Switch Modules", "IRF520 / D4184 MOSFET Boards", "4", "PWM Dimmer for 4 Stage Light Domes & 3 Tall Pole Spotlights", "3.3V DC PWM / 12V DC Stage"),
            ("8", "High-Torque Metal Servos", "MG996R / SG90 Digital Servos", "6", "Robot Arm Joint Servos & Stage Servo Drives for Spinning Dreidels", "5V - 6V DC"),
            ("9", "120VAC Menorah Candle Bulbs", "E12 / C7 Electric Candle Bulbs & Sockets", "10", "8 Menorah Side Candles + 1 Center Shamash Candle + 1 Claw Candle", "120VAC Line Voltage"),
            ("10", "Stage Light Domes", "Frosted Glass RGB/Cyan Light Domes", "4", "2 Mouth-Side & 2 Tail-Side Dimmable Domes (Breathing/Chases)", "12V DC / MOSFET Gate"),
            ("11", "Tall Pole Spotlights", "Adjustable Pole Spotlight Lamp Assemblies", "3", "Center Fish Mouth Spotlight + Left & Right Dreidel Spotlights", "12V DC / MOSFET Gate"),
            ("12", "Main Power Supply", "5V/6V 12A Switching DC Power Supply", "1", "High-Current Power Rail for Servos, L298N DC Motors & Stage Lights", "110V-240VAC Input / 5V-6V 12A Out"),
            ("13", "Common Ground Bus & Wiring", "20 AWG / 18 AWG Wire Harness & Bus Bar", "1", "Common Reference Ground Rail connecting Pi, L298N, PCA9685 & SSRs", "Common GND Reference")
        ]

        for item in bom_data_items:
            bom_rows.append([
                Paragraph(f"<b>{item[0]}</b>", cell_style),
                Paragraph(f"<b>{item[1]}</b>", cell_style),
                Paragraph(item[2], cell_style),
                Paragraph(f"<b>{item[3]}</b>", cell_style),
                Paragraph(item[4], cell_style),
                Paragraph(item[5], cell_style)
            ])

        t_bom = Table(bom_rows, colWidths=[40, 130, 130, 35, 255, 130])
        t_bom.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#0055a5')),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#dddddd')),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#ffffff'), colors.HexColor('#f8fafd')])
        ]))
        story.append(t_bom)

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
