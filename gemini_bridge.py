import cv2
import numpy as np
import base64
import json
import os
from google import genai
from google.genai import types

class GeminiArmBridge:
    def __init__(self):
        self.system_instruction = (
            "You are the friendly, intelligent AI voice and brain of the Animatronic Menorah Fish & Candle Lighting Robot Arm Stage. "
            "You talk through an animatronic fish on stage whose mouth lipsyncs, neck swings out horizontally, tail wags, and spotlight shines while you speak. "
            "On stage, a 5-DOF Robot Arm holding a constantly lit flickering candle in its claw lights candles arranged in a 180-degree circular Menorah arc (8 side candles plus 1 center Shamash candle). "
            "Your job is to:\n"
            "1. Produce warm, cheerful, conversational responses (1-3 concise sentences).\n"
            "2. Whenever asked to light candles for Hanukkah (1 to 8 candles), call the `light_menorah_candles` tool with requested `count`.\n"
            "3. Whenever asked to return arm to rest position / park arm, give a high five, say yes (nod arm), or say no (shake arm), call `arm_gesture` with `gesture_name` ('rest', 'high_five', 'yes', 'no').\n"
            "Keep spoken responses concise, joyful, and tailored to Hanukkah, Menorah lighting, or robotics performance!"
        )

    def detect_hand_gestures(self, frame):
        """
        Analyzes camera frame for hand gestures (skin color segmentation + contour defects)
        Returns: (gesture_name, finger_count, annotated_frame)
        """
        try:
            resized = cv2.resize(frame, (320, 240))
            blur = cv2.GaussianBlur(resized, (5, 5), 0)
            hsv = cv2.cvtColor(blur, cv2.COLOR_BGR2HSV)

            lower_skin = np.array([0, 20, 70], dtype=np.uint8)
            upper_skin = np.array([20, 255, 255], dtype=np.uint8)
            mask = cv2.inRange(hsv, lower_skin, upper_skin)

            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
            mask = cv2.erode(mask, kernel, iterations=1)
            mask = cv2.dilate(mask, kernel, iterations=2)

            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return "None", 0, frame

            max_contour = max(contours, key=cv2.contourArea)
            area = cv2.contourArea(max_contour)

            if area < 3000:
                return "None", 0, frame

            hull = cv2.convexHull(max_contour, returnPoints=False)
            if hull is None or len(hull) < 3:
                return "None", 0, frame

            defects = cv2.convexityDefects(max_contour, hull)
            finger_count = 0

            if defects is not None:
                for i in range(defects.shape[0]):
                    s, e, f, d = defects[i, 0]
                    start = tuple(max_contour[s][0])
                    end = tuple(max_contour[e][0])
                    far = tuple(max_contour[f][0])

                    a = np.sqrt((end[0] - start[0])**2 + (end[1] - start[1])**2)
                    b = np.sqrt((far[0] - start[0])**2 + (far[1] - start[1])**2)
                    c = np.sqrt((end[0] - far[0])**2 + (end[1] - far[1])**2)

                    angle = np.arccos((b**2 + c**2 - a**2) / (2 * b * c + 1e-5))

                    if angle <= np.pi / 2 and d > 1200:
                        finger_count += 1

                finger_count += 1

            gesture = "None"
            if finger_count >= 4:
                gesture = "5_FINGERS_FORWARD"
            elif finger_count == 2 or finger_count == 3:
                gesture = "2_FINGERS_WAVE"
            elif finger_count == 1:
                gesture = "1_FINGER_ATTACK"

            return gesture, finger_count, frame
        except Exception as e:
            return "None", 0, frame

    def generate_chat_response(self, api_key, user_text="", image_bytes=None):
        if not api_key:
            return {
                "text": "Please provide a valid Google Gemini API Key in the settings tab to enable AI vision & voice features.",
                "action": None
            }

        client = genai.Client(api_key=api_key)

        tools = [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name="light_menorah_candles",
                    description="Extinguishes all current Menorah candles and uses the 5-DOF Robot Arm to light the requested number of Hanukkah candles (1 to 8 candles).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "count": types.Schema(type=types.Type.INTEGER, description="Number of candles to light (1 to 8, or 0 to extinguish all)")
                        },
                        required=["count"]
                    )
                ),
                types.FunctionDeclaration(
                    name="arm_move",
                    description="Sets individual joint angles for the 5-DOF Robot Arm.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "j1_base": types.Schema(type=types.Type.NUMBER, description="Base rotation angle (-90 to +90 degrees)"),
                            "j2_shoulder": types.Schema(type=types.Type.NUMBER, description="Shoulder pitch angle (-90 to +90 degrees)"),
                            "j3_elbow": types.Schema(type=types.Type.NUMBER, description="Elbow pitch angle (-135 to +135 degrees)"),
                            "j4_wrist": types.Schema(type=types.Type.NUMBER, description="Wrist pitch angle (-90 to +90 degrees)"),
                            "j5_gripper": types.Schema(type=types.Type.NUMBER, description="Gripper claw open/close percentage (0=closed, 100=open)")
                        }
                    )
                ),
                types.FunctionDeclaration(
                    name="arm_gesture",
                    description="Triggers a robot arm gesture or movement routine (rest, high_five, yes, no).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "gesture_name": types.Schema(
                                type=types.Type.STRING,
                                enum=["rest", "high_five", "yes", "no"]
                            )
                        },
                        required=["gesture_name"]
                    )
                )
            ])
        ]

        contents = []

        if image_bytes:
            contents.append(types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg"
            ))

        prompt_text = user_text if user_text else "Greeting! Ask me to light Hanukkah Menorah candles or talk to the animatronic fish!"
        contents.append(prompt_text)

        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            tools=tools,
            temperature=0.7
        )

        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=contents,
                config=config
            )

            action = None
            text_response = response.text or ""

            if response.function_calls:
                call = response.function_calls[0]
                args_dict = {}
                if hasattr(call.args, "items"):
                    args_dict = {k: v for k, v in call.args.items()}
                elif isinstance(call.args, dict):
                    args_dict = call.args

                action = {
                    "name": call.name,
                    "args": args_dict
                }
                if not text_response:
                    text_response = f"Executing command: {call.name}"

            return {
                "text": text_response,
                "action": action
            }

        except Exception as e:
            return {
                "text": f"Gemini API Error: {str(e)}",
                "action": None
            }

    def generate_voice_chat_response(self, api_key, audio_bytes, mime_type="audio/webm", image_bytes=None):
        if not api_key:
            return {"text": "Please provide a valid Google Gemini API Key.", "action": None}

        client = genai.Client(api_key=api_key)

        tools = [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name="light_menorah_candles",
                    description="Extinguishes all current Menorah candles and uses the 5-DOF Robot Arm to light the requested number of Hanukkah candles (1 to 8 candles).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "count": types.Schema(type=types.Type.INTEGER, description="Number of candles to light (1 to 8, or 0 to extinguish all)")
                        },
                        required=["count"]
                    )
                ),
                types.FunctionDeclaration(
                    name="arm_move",
                    description="Sets individual joint angles for the 5-DOF Robot Arm.",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "j1_base": types.Schema(type=types.Type.NUMBER),
                            "j2_shoulder": types.Schema(type=types.Type.NUMBER),
                            "j3_elbow": types.Schema(type=types.Type.NUMBER),
                            "j4_wrist": types.Schema(type=types.Type.NUMBER),
                            "j5_gripper": types.Schema(type=types.Type.NUMBER)
                        }
                    )
                ),
                types.FunctionDeclaration(
                    name="arm_gesture",
                    description="Triggers a robot arm gesture or movement routine (rest, high_five, yes, no).",
                    parameters=types.Schema(
                        type=types.Type.OBJECT,
                        properties={
                            "gesture_name": types.Schema(
                                type=types.Type.STRING,
                                enum=["rest", "high_five", "yes", "no"]
                            )
                        },
                        required=["gesture_name"]
                    )
                )
            ])
        ]

        contents = []

        if audio_bytes:
            contents.append(types.Part.from_bytes(
                data=audio_bytes,
                mime_type=mime_type
            ))

        if image_bytes:
            contents.append(types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg"
            ))

        contents.append(
            "Listen to my spoken voice input in the audio file above.\n"
            "1. Transcribe the exact words I spoke.\n"
            "2. Respond to me concisely in 1-2 cheerful sentences as the Menorah Fish.\n"
            "3. If I asked to light Hanukkah candles (e.g. 1 to 8 candles), call the `light_menorah_candles` function tool with `count`.\n\n"
            "Format your text response as:\n"
            "TRANSCRIPTION: [exact spoken words]\n"
            "RESPONSE: [your conversational answer]"
        )

        config = types.GenerateContentConfig(
            system_instruction=self.system_instruction,
            tools=tools,
            temperature=0.7
        )

        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=contents,
                config=config
            )

            action = None
            raw_text = response.text or ""
            user_transcription = ""
            text_response = raw_text

            if "TRANSCRIPTION:" in raw_text:
                parts = raw_text.split("RESPONSE:", 1)
                user_transcription = parts[0].replace("TRANSCRIPTION:", "").strip()
                if len(parts) > 1:
                    text_response = parts[1].strip()

            if response.function_calls:
                call = response.function_calls[0]
                args_dict = {}
                if hasattr(call.args, "items"):
                    args_dict = {k: v for k, v in call.args.items()}
                elif isinstance(call.args, dict):
                    args_dict = call.args

                action = {"name": call.name, "args": args_dict}
                if not text_response:
                    text_response = f"Executing command: {call.name}"

            return {
                "transcription": user_transcription,
                "text": text_response,
                "action": action
            }

        except Exception as e:
            return {"text": f"Gemini Voice Processing Error: {str(e)}", "action": None}
