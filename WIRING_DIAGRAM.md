# 🦜 ANIMATRONIC MENORAH FISH & CANDLE LIGHTING ROBOT ARM STAGE
## HARDWARE WIRING DIAGRAM & SYSTEM SCHEMATIC GUIDE

This document details all physical hardware connections, Raspberry Pi GPIO pin mappings, 120VAC Solid State Relays (SSRs), MOSFET power transistors for stage lighting, PCA9685 PWM channel assignments, L298N motor driver connections, Menorah candle light bulbs, light domes, and power distribution rails.

---

## 📐 OVERVIEW OF SYSTEM HARDWARE ARCHITECTURE

```
+-----------------------------------------------------------------------------------+
|                                  MAIN POWER SUPPLY                                |
|  120VAC Line (Solid State Relays)          +5V / +6V @ 12A DC (Servos & Motors)   |
|  +5V @ 3A DC (Raspberry Pi Logic)                                                 |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                              RASPBERRY PI 4 / 5 MCU                               |
| - 40-Pin GPIO Header                                                              |
| - I2C Bus (SDA: GPIO 2, SCL: GPIO 3)                                              |
| - 120VAC SSR Outputs: GPIO 4, 17, 27, 22, 10, 9, 11, 5, 6, 13 (3.3V DC Trigger)   |
| - MOSFET Dimmable Lighting: GPIO 12 (Domes PWM), 16, 20, 21 (Spotlights PWM)      |
| - L298N Motor Driver: GPIO 18 ENA, 23 IN1, 24 IN2, 19 ENB, 25 IN3, 8 IN4          |
+-----+----------------------+---------------------+--------------------------------+
      | (I2C Bus)            | (PWM & GPIO)        | (120VAC SSR Triggers)
      v                      v                     v
+-----+--------------+  +----+---------------+  +--+--------------------------------+
| PCA9685 16-CHANNEL |  | SINGLE L298N DUAL  |  | 10x 120VAC SOLID STATE RELAYS     |
| 12-BIT PWM DRIVER  |  | H-BRIDGE DRIVER    |  | & MOSFET DIMMABLE STAGE LIGHTING  |
| (I2C Addr: 0x40)   |  | (Ch 1 & Ch 2)      |  | (8 Side + 1 Shamash + Claw Candle)|
+-----+--------------+  +----+---------------+  +--+--------------------------------+
      |                      |                     |
      v                      v                     v
+-----+----------------------+---------------------+--------------------------------+
|                       ANIMATRONIC STAGE ACTUATORS & ENDPOINTS                     |
| - Animatronic Fish: Original OEM Mouth DC Motor (L298 Ch 1 Fwd), Original OEM     |
|   Neck Motor (L298 Ch 2 Fwd) & Original OEM Tail Motor (L298 Ch 2 Rev)            |
| - Stage Servos & Dreidels: Mouth-Side & Tail-Side Servos with Spinning Dreidels   |
| - 5-DOF Robot Arm: Base, Shoulder, Elbow, Wrist, Claw holding Flickering Candle   |
| - 120VAC Menorah Candles: 8 Side Candles + 1 Center Shamash + 1 Claw Candle (SSRs) |
| - MOSFET Dimmable Stage Lights: 4 Light Domes (Breathing/Chases) + 3 Spotlights  |
+-----------------------------------------------------------------------------------+
```

---

## 🍓 1. RASPBERRY PI 40-PIN GPIO PINOUT MAP

| Header Pin # | GPIO Name | Signal Description | Target Module Connected | Function Description |
| :---: | :---: | :--- | :--- | :--- |
| **Pin 1** | 3.3V Power | Logic VCC (3.3V) | Sensors / Optional Logic | 3.3V Logic Reference |
| **Pin 2** | 5V Power | Logic VCC (5V) | PCA9685 VCC & Relays | 5V Logic VCC Rail |
| **Pin 3** | GPIO 2 (SDA1) | I2C Serial Data | PCA9685 SDA Terminal | I2C Data for 16-Ch Servo Controller |
| **Pin 5** | GPIO 3 (SCL1) | I2C Serial Clock | PCA9685 SCL Terminal | I2C Clock for 16-Ch Servo Controller |
| **Pin 6** | Ground (GND) | Common Ground | Common GND Bus | Shared Ground Reference |
| **Pin 7** | GPIO 4 | Digital Output | Claw Candle 120VAC SSR | 3.3V DC Trigger for 120VAC Claw Candle |
| **Pin 11** | GPIO 17 | Digital Output | Center Shamash 120VAC SSR | 3.3V DC Trigger for 120VAC Shamash Candle |
| **Pin 13** | GPIO 27 | Digital Output | Side Candle 1 120VAC SSR | 3.3V DC Trigger for 120VAC Side Candle 1 |
| **Pin 15** | GPIO 22 | Digital Output | Side Candle 2 120VAC SSR | 3.3V DC Trigger for 120VAC Side Candle 2 |
| **Pin 19** | GPIO 10 | Digital Output | Side Candle 3 120VAC SSR | 3.3V DC Trigger for 120VAC Side Candle 3 |
| **Pin 21** | GPIO 9 | Digital Output | Side Candle 4 120VAC SSR | 3.3V DC Trigger for 120VAC Side Candle 4 |
| **Pin 23** | GPIO 11 | Digital Output | Side Candle 5 120VAC SSR | 3.3V DC Trigger for 120VAC Side Candle 5 |
| **Pin 29** | GPIO 5 | Digital Output | Side Candle 6 120VAC SSR | 3.3V DC Trigger for 120VAC Side Candle 6 |
| **Pin 31** | GPIO 6 | Digital Output | Side Candle 7 120VAC SSR | 3.3V DC Trigger for 120VAC Side Candle 7 |
| **Pin 33** | GPIO 13 | Digital Output | Side Candle 8 120VAC SSR | 3.3V DC Trigger for 120VAC Side Candle 8 |
| **Pin 32** | GPIO 12 (PWM) | PWM Output | 4 Stage Domes MOSFET | MOSFET Gate for Dimmable Breathing Domes |
| **Pin 36** | GPIO 16 (PWM) | PWM Output | Fish Spotlight MOSFET | MOSFET Gate for Fish Mouth Spotlight PWM |
| **Pin 38** | GPIO 20 (PWM) | PWM Output | Left Dreidel Spotlight MOSFET | MOSFET Gate for Left Dreidel Spotlight PWM |
| **Pin 40** | GPIO 21 (PWM) | PWM Output | Right Dreidel Spotlight MOSFET | MOSFET Gate for Right Dreidel Spotlight PWM |
| **Pin 12** | GPIO 18 (PWM) | PWM Output | L298N ENA (Mouth Speed PWM) | Channel 1: OEM Mouth Motor PWM |
| **Pin 16** | GPIO 23 | Digital Output | L298N IN1 (Mouth Dir 1) | Channel 1: OEM Mouth Forward Polarity |
| **Pin 18** | GPIO 24 | Digital Output | L298N IN2 (Mouth Dir 2) | Channel 1: OEM Mouth Reverse Polarity |
| **Pin 35** | GPIO 19 (PWM) | PWM Output | L298N ENB (Neck/Tail Speed PWM) | Channel 2: OEM Neck/Tail Motor PWM |
| **Pin 22** | GPIO 25 | Digital Output | L298N IN3 (Neck/Tail Dir 1) | Channel 2: OEM Neck Forward / Tail Reverse |
| **Pin 24** | GPIO 8 | Digital Output | L298N IN4 (Neck/Tail Dir 2) | Channel 2: OEM Neck Forward / Tail Reverse |

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

---

## ⚙️ 3. SINGLE L298N DUAL H-BRIDGE MOTOR DRIVER (OEM FISH MOTORS)

- **Channel 1 / Channel A (Original OEM Mouth DC Motor for Lipsync):**
  - `ENA` (PWM) -> Raspberry Pi **GPIO 18** (Pin 12)
  - `IN1` -> **GPIO 23** (Pin 16) | `IN2` -> **GPIO 24** (Pin 18)
  - *Forward Polarity (`IN1=HIGH, IN2=LOW`):* Powers original OEM mouth motor to open lower jaw in sync with speech/song!

- **Channel 2 / Channel B (Original OEM Neck & Tail DC Motors):**
  - `ENB` (PWM) -> Raspberry Pi **GPIO 19** (Pin 35)
  - `IN3` -> **GPIO 25** (Pin 22) | `IN4` -> **GPIO 8** (Pin 24)
  - *Forward Polarity (`IN3=HIGH, IN4=LOW` with 100% PWM):* Powers original OEM neck motor forward to swing fish head/neck out horizontally facing the audience and holds it extended continuously while talking against the original OEM return spring.
  - *Depower (`IN3=LOW, IN4=LOW`, 0% PWM):* Cuts power to neck motor when done talking, allowing the original OEM return spring to pull the fish head/neck back flat against the wall plaque.
  - *Reverse Polarity (`IN3=LOW, IN4=HIGH` with 80% PWM):* Powers original OEM tail motor mechanism for tail wagging! (Note: Active ONLY when NOT speaking because Channel 2 is dedicated to Forward Polarity for the neck motor while talking).

---

## 💡 4. 120VAC SOLID STATE RELAYS (SSRs) & MOSFET LIGHTING

1. **120VAC Menorah & Claw Candles (3.3V DC Input Solid State Relays):**
   - 10 Solid State Relays (SSRs) with 3.3V DC trigger inputs driven directly by Raspberry Pi GPIO pins (`GPIO 4, 17, 27, 22, 10, 9, 11, 5, 6, 13`).
   - `HIGH` (+3.3V DC) turns ON the corresponding 120VAC candle bulb; `LOW` turns it OFF.

2. **Dimmable Stage Domes & Spotlights (MOSFET Power Transistors):**
   - Solid state MOSFET power switches / power transistors driven by Raspberry Pi PWM GPIO pins (`GPIO 12` for Domes, `GPIO 16, 20, 21` for Spotlights).
   - Allows full smooth PWM brightness control:
     - **Fish Speaking**: 4 Stage Light Domes "breathe" slowly in unison / smooth PWM sine wave pulse (`50%` -> `100%` -> `50%`).
     - **Fish Dancing**: 4 Stage Light Domes flash and perform running light chases around the 4 stage positions!
     - **Spotlights**: Fully illuminated during speech/dance, dimmed or off during idle states.

3. **Common Ground:**
   - Connect Raspberry Pi GND, PCA9685 GND, L298N GND, MOSFET source GND, and Power Supply GND together to a shared common ground bus.
