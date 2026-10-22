# 🦜 ANIMATRONIC MENORAH FISH & CANDLE LIGHTING ROBOT ARM STAGE
## HARDWARE WIRING DIAGRAM & SYSTEM SCHEMATIC GUIDE

This document details all physical hardware connections, Raspberry Pi GPIO pin mappings, PCA9685 PWM channel assignments, L298N motor driver connections, Menorah candle light bulbs, light domes, and power distribution rails.

---

## 📐 OVERVIEW OF SYSTEM HARDWARE ARCHITECTURE

```
+-----------------------------------------------------------------------------------+
|                                  MAIN POWER SUPPLY                                |
|  5V / 6V @ 12A DC (Servos & DC Motors)       +5V @ 3A DC (Raspberry Pi Logic)     |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                              RASPBERRY PI 4 / 5 MCU                               |
| - 40-Pin GPIO Header                                                              |
| - I2C Bus (SDA: GPIO 2, SCL: GPIO 3)                                              |
| - CSI Video Camera / USB Webcams                                                  |
| - 3.5mm Headphone Jack / USB Audio Out                                            |
+-----+----------------------+---------------------+--------------------------------+
      | (I2C Bus)            | (PWM & GPIO)        | (GPIO Triggers)
      v                      v                     v
+-----+--------------+  +----+---------------+  +--+--------------------------------+
| PCA9685 16-CHANNEL |  | SINGLE L298N DUAL  |  | MENORAH CANDLES & STAGE LIGHT     |
| 12-BIT PWM DRIVER  |  | H-BRIDGE DRIVER    |  | DOMES CONTROLLER                  |
| (I2C Addr: 0x40)   |  | (Ch A & Ch B)      |  | (8 Side + 1 Shamash + 4 Domes)    |
+-----+--------------+  +----+---------------+  +--+--------------------------------+
      |                      |                     |
      v                      v                     v
+-----+----------------------+---------------------+--------------------------------+
|                       ANIMATRONIC STAGE ACTUATORS & ENDPOINTS                     |
| - Animatronic Fish: Mouth DC Motor (L298 Ch A), Body 3s PWM Ramp Swing Out        |
|   (L298 Ch B Fwd) & Tail Reverse Polarity Wag Motor (L298 Ch B Rev)               |
| - Stage Servos & Dreidels: Mouth-Side & Tail-Side Servos with Spinning Dreidels   |
| - 5-DOF Robot Arm: Base, Shoulder, Elbow, Wrist, Claw holding Flickering Candle   |
| - 180° Menorah Arc: 8 Side Candles + 1 Center Shamash Candle                      |
| - 4 Light Domes: Smooth Breathing Light Pulse Sequence                            |
+-----------------------------------------------------------------------------------+
```

---

## 🍓 1. RASPBERRY PI 40-PIN GPIO PINOUT MAP

| Header Pin # | GPIO Name | Function / Signal Description | Target Module Connected | Wire Color Code |
| :---: | :---: | :--- | :--- | :--- |
| **Pin 1** | 3.3V Power | Logic VCC (3.3V) | Sensors / Optional Logic | 🟡 Yellow |
| **Pin 2** | 5V Power | Logic VCC (5V) | PCA9685 VCC & Relay VCC | 🔴 Red |
| **Pin 3** | GPIO 2 (SDA1) | I2C Serial Data | PCA9685 SDA Terminal | 🔵 Cyan |
| **Pin 4** | 5V Power | Secondary 5V VCC | Power Rail | 🔴 Red |
| **Pin 5** | GPIO 3 (SCL1) | I2C Serial Clock | PCA9685 SCL Terminal | 🟦 Blue |
| **Pin 6** | Ground (GND) | Common Reference Ground | Common GND Bus | ⬛ Black |
| **Pin 12** | GPIO 18 | PWM Output | L298N ENA (Fish Mouth Speed PWM) | 🟣 Magenta |
| **Pin 16** | GPIO 23 | Digital Output | L298N IN1 (Fish Mouth Direction 1) | 🟦 Blue |
| **Pin 18** | GPIO 24 | Digital Output | L298N IN2 (Fish Mouth Direction 2) | 🟦 Blue |
| **Pin 22** | GPIO 25 | Digital Output | L298N IN3 (Body 3s Ramp Fwd / Tail Rev) | 🟢 Green |
| **Pin 24** | GPIO 8 | Digital Output | L298N IN4 (Body 3s Ramp Fwd / Tail Rev) | 🟢 Green |
| **Pin 35** | GPIO 19 | PWM Output | L298N ENB (Fish Body & Tail Speed PWM) | 🟣 Magenta |

---

## 🎛️ 2. PCA9685 16-CHANNEL PWM SERVO DRIVER (I2C Addr: 0x40)

| Channel # | Connected Hardware Output | Function Description | Signal Range |
| :---: | :--- | :--- | :---: |
| **Ch 0** | Robot Arm Joint 1 Base | Base Rotation Servo (-90° to +90°) | 500μs - 2500μs |
| **Ch 1** | Robot Arm Joint 2 Shoulder | Shoulder Pitch Servo (-90° to +90°) | 500μs - 2500μs |
| **Ch 2** | Robot Arm Joint 3 Elbow | Elbow Pitch Servo (-135° to +135°) | 500μs - 2500μs |
| **Ch 3** | Mouth-Side Servo & Dreidel | Sweeps Mouth-Side Servo & Spinning Dreidel | 500μs - 2500μs |
| **Ch 4** | Tail-Side Servo & Dreidel | Sweeps Tail-Side Servo & Spinning Dreidel | 500μs - 2500μs |
| **Ch 5** | Robot Arm Joint 4/5 Claw | Wrist & Gripper Claw holding Candle | 500μs - 2500μs |
| **Ch 6** | Center Shamash Candle Light | Center Shamash Light Bulb PWM Dimmer | 0% - 100% PWM |
| **Ch 7** | Side Candles 1-4 Light Bulbs | Side Candles 1 to 4 Light Bulbs PWM | 0% - 100% PWM |
| **Ch 8** | Side Candles 5-8 Light Bulbs | Side Candles 5 to 8 Light Bulbs PWM | 0% - 100% PWM |
| **Ch 9** | Fish Head Spotlight Pan | Fish Head Spotlight Servo Pan | 500μs - 2500μs |
| **Ch 10** | Fish Head Spotlight Tilt | Fish Head Spotlight Servo Tilt | 500μs - 2500μs |
| **Ch 11** | 4 Stage Light Domes | Light Domes PWM Dimmer (Breathing Pulse) | 0% - 100% PWM |

---

## ⚙️ 3. SINGLE L298N DUAL H-BRIDGE MOTOR DRIVER

- **Channel 1 / Channel A (Fish Mouth DC Motor for Lipsync):**
  - `ENA` (PWM) -> Raspberry Pi **GPIO 18** (Pin 12)
  - `IN1` -> **GPIO 23** (Pin 16) | `IN2` -> **GPIO 24** (Pin 18)
  - *Forward Polarity (`IN1=HIGH, IN2=LOW`):* Opens & closes fish mouth in sync with speech/song!

- **Channel 2 / Channel B (Fish Neck Swing & Reverse Polarity Tail Wag):**
  - `ENB` (PWM) -> Raspberry Pi **GPIO 19** (Pin 35)
  - `IN3` -> **GPIO 25** (Pin 22) | `IN4` -> **GPIO 8** (Pin 24)
  - *Forward Polarity (`IN3=HIGH, IN4=LOW`):* Swings fish neck out horizontally facing the audience while talking. Once fully extended, motor power is DEPOWERED (`0% PWM`) to prevent continuous stall current & motor coil overheating!
  - *Reverse Polarity (`IN3=LOW, IN4=HIGH`):* Drives fish tail motor for tail wagging!

---

## ⚡ 4. POWER DISTRIBUTION & SAFETY RULES

1. **Common Ground:**
   - Connect Raspberry Pi GND, PCA9685 GND, L298N GND, and External Power Supply GND together to a shared common ground bus.
2. **High-Current Power Rail:**
   - Power PCA9685 `V+` screw terminals and L298N motor driver from a dedicated 5V/6V 12A DC Power Supply.
