# 🦜 ANIMATRONIC MENORAH FISH & CANDLE LIGHTING ROBOT ARM STAGE
## HARDWARE WIRING DIAGRAM & SYSTEM SCHEMATIC GUIDE

This document details all physical hardware connections, Raspberry Pi GPIO pin mappings, 120VAC Solid State Relays (SSRs), IRLZ44N N-Channel Logic-Level MOSFET lighting circuits (with 220Ω gate inrush resistors and 10kΩ pull-down resistors), PCA9685 12-bit PWM servo drivers, L298N motor driver connections, Menorah candle light bulbs, light domes, and power distribution rails.

---

## 📐 OVERVIEW OF SYSTEM HARDWARE ARCHITECTURE

```
+-----------------------------------------------------------------------------------+
|                                  MAIN POWER SUPPLY                                |
|  120VAC Line Voltage (Solid State Relays -> 120VAC Candles)                       |
|  +12V DC @ 10A (IRLZ44N MOSFET Dimmable Stage Lights)                             |
|  +5V / +6V @ 12A DC (PCA9685 Servos & L298N OEM Motors)                           |
|  +5V @ 3A DC (Raspberry Pi Logic Power)                                           |
+------------------------------------------+----------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------+
|                              RASPBERRY PI 4 / 5 MCU                               |
| - 40-Pin GPIO Header                                                              |
| - I2C Bus (SDA: GPIO 2, SCL: GPIO 3) -> PCA9685 PWM Servo Controller              |
| - 10x 120VAC SSR Outputs: GPIO 4, 17, 27, 22, 10, 9, 11, 5, 6, 13 (3.3V DC Trigger)|
| - 4x IRLZ44N MOSFET PWM Lights: GPIO 12 (Domes), 16, 20, 21 (Spotlights)          |
|   * Each Gate driven through a 220Ω Series Resistor & 10kΩ Pull-Down to GND       |
| - L298N Motor Driver: GPIO 18 ENA, 23 IN1, 24 IN2, 19 ENB, 25 IN3, 8 IN4          |
+-----+----------------------+---------------------+--------------------------------+
      | (I2C Bus)            | (PWM & GPIO)        | (120VAC SSR Triggers)
      v                      v                     v
+-----+--------------+  +----+---------------+  +--+--------------------------------+
| PCA9685 16-CHANNEL |  | SINGLE L298N DUAL  |  | 10x 120VAC SOLID STATE RELAYS     |
| 12-BIT PWM DRIVER  |  | H-BRIDGE DRIVER    |  | (8 Side + 1 Shamash + Claw Candle)|
| (I2C Addr: 0x40)   |  | (Ch 1 & Ch 2)      |  | 3.3V DC Input / 120VAC Line       |
+-----+--------------+  +----+---------------+  +-----------------------------------+
      |                      |
      v (5V Servos)          v (OEM Motors)
+-----+----------------------+------------------------------------------------------+
|                       ANIMATRONIC STAGE ACTUATORS & LIGHTS                        |
| - Animatronic Fish: Original OEM Mouth DC Motor (L298 Ch 1 Fwd), Original OEM     |
|   Neck Motor (L298 Ch 2 Fwd) & Original OEM Tail Motor (L298 Ch 2 Rev)            |
| - Stage Servos & Dreidels: Mouth-Side & Tail-Side Servos with Spinning Dreidels   |
| - 5-DOF Robot Arm: Base, Shoulder, Elbow, Wrist, Claw holding Flickering Candle   |
| - 120VAC Menorah Candles: 8 Side Candles + 1 Center Shamash + 1 Claw Candle (SSRs) |
| - IRLZ44N Logic-Level MOSFET 12V DC Lights (220Ω Gate Resistor / 10kΩ Pull-Down): |
|   * GPIO 12 (Pin 32) -> 220Ω -> Gate IRLZ44N #1 -> 12V 4 Stage Light Domes (-)    |
|   * GPIO 16 (Pin 36) -> 220Ω -> Gate IRLZ44N #2 -> 12V Fish Mouth Spotlight (-)   |
|   * GPIO 20 (Pin 38) -> 220Ω -> Gate IRLZ44N #3 -> 12V Left Dreidel Spotlight (-) |
|   * GPIO 21 (Pin 40) -> 220Ω -> Gate IRLZ44N #4 -> 12V Right Dreidel Spotlight (-)|
+-----------------------------------------------------------------------------------+
```

---

## 🍓 1. RASPBERRY PI 40-PIN GPIO PINOUT MAP

| Header Pin # | GPIO Name | Signal Description | Target Module Connected | Terminal & Resistor Wiring |
| :---: | :---: | :--- | :--- | :--- |
| **Pin 1** | 3.3V Power | Logic VCC (3.3V) | Logic Reference | 3.3V Logic Reference |
| **Pin 2** | 5V Power | Logic VCC (5V) | PCA9685 VCC & L298N 5V | 5V Logic VCC Rail |
| **Pin 3** | GPIO 2 (SDA1) | I2C Serial Data | PCA9685 SDA Terminal | I2C Data for 16-Ch Servo Controller |
| **Pin 5** | GPIO 3 (SCL1) | I2C Serial Clock | PCA9685 SCL Terminal | I2C Clock for 16-Ch Servo Controller |
| **Pin 6** | Ground (GND) | Common Ground | Common GND Bus | Shared Ground Reference |
| **Pin 7** | GPIO 4 | Digital Output | Claw Candle 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 11** | GPIO 17 | Digital Output | Center Shamash 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 13** | GPIO 27 | Digital Output | Side Candle 1 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 15** | GPIO 22 | Digital Output | Side Candle 2 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 19** | GPIO 10 | Digital Output | Side Candle 3 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 21** | GPIO 9 | Digital Output | Side Candle 4 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 23** | GPIO 11 | Digital Output | Side Candle 5 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 29** | GPIO 5 | Digital Output | Side Candle 6 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 31** | GPIO 6 | Digital Output | Side Candle 7 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 33** | GPIO 13 | Digital Output | Side Candle 8 120VAC SSR | DC Input (+) Terminal (3.3V DC Trigger) |
| **Pin 32** | GPIO 12 (PWM) | PWM Output | IRLZ44N MOSFET #1 (Domes) | **220Ω Series Resistor to Gate (Pin 1) & 10kΩ Pull-Down to GND** |
| **Pin 36** | GPIO 16 (PWM) | PWM Output | IRLZ44N MOSFET #2 (Fish Spot) | **220Ω Series Resistor to Gate (Pin 1) & 10kΩ Pull-Down to GND** |
| **Pin 38** | GPIO 20 (PWM) | PWM Output | IRLZ44N MOSFET #3 (Left Spot) | **220Ω Series Resistor to Gate (Pin 1) & 10kΩ Pull-Down to GND** |
| **Pin 40** | GPIO 21 (PWM) | PWM Output | IRLZ44N MOSFET #4 (Right Spot)| **220Ω Series Resistor to Gate (Pin 1) & 10kΩ Pull-Down to GND** |
| **Pin 12** | GPIO 18 (PWM) | PWM Output | L298N ENA (Mouth Speed) | L298N Channel 1 ENA Terminal |
| **Pin 16** | GPIO 23 | Digital Output | L298N IN1 (Mouth Dir 1) | L298N Channel 1 IN1 Terminal (Forward) |
| **Pin 18** | GPIO 24 | Digital Output | L298N IN2 (Mouth Dir 2) | L298N Channel 1 IN2 Terminal (Forward) |
| **Pin 35** | GPIO 19 (PWM) | PWM Output | L298N ENB (Neck/Tail Speed) | L298N Channel 2 ENB Terminal |
| **Pin 22** | GPIO 25 | Digital Output | L298N IN3 (Neck/Tail Dir 1) | L298N Channel 2 IN3 Terminal (Fwd Neck / Rev Tail) |
| **Pin 24** | GPIO 8 | Digital Output | L298N IN4 (Neck/Tail Dir 2) | L298N Channel 2 IN4 Terminal (Fwd Neck / Rev Tail) |

---

## 🎛️ 2. PCA9685 16-CHANNEL PWM SERVO DRIVER (I2C Addr: 0x40)

| Channel # | Connected Servo Output | Function Description | Signal Range & Voltage |
| :---: | :--- | :--- | :---: |
| **Ch 0** | Robot Arm Joint 1 Base | Base Rotation Servo (-90° to +90°) | 500μs - 2500μs (5V) |
| **Ch 1** | Robot Arm Joint 2 Shoulder | Shoulder Pitch Servo (-90° to +90°) | 500μs - 2500μs (5V) |
| **Ch 2** | Robot Arm Joint 3 Elbow | Elbow Pitch Servo (-135° to +135°) | 500μs - 2500μs (5V) |
| **Ch 3** | Mouth-Side Servo & Dreidel | Sweeps Mouth-Side Servo & Spinning Dreidel | 500μs - 2500μs (5V) |
| **Ch 4** | Tail-Side Servo & Dreidel | Sweeps Tail-Side Servo & Spinning Dreidel | 500μs - 2500μs (5V) |
| **Ch 5** | Robot Arm Joint 4/5 Claw | Wrist Pitch & Gripper Candle Claw | 500μs - 2500μs (5V) |
| **Ch 10** | Fish Head Spotlight Pan Servo | Fish Head Spotlight Servo Pan | 500μs - 2500μs (5V) |
| **Ch 11** | Fish Head Spotlight Tilt Servo | Fish Head Spotlight Servo Tilt | 500μs - 2500μs (5V) |

---

## ⚡ 3. DISCRETE IRLZ44N MOSFET LIGHTING CIRCUIT SCHEMATIC

```
        Raspberry Pi GPIO Pin (e.g. GPIO 4 / 12 / 7 / 1 / 16 / 20 / 21)
                                |
                                |
                             [220Ω Series Gate Resistor]
                                |
                                +-------------------+
                                |                   |
                          (Gate - Pin 1)     [22kΩ Pull-Down]
                          IRLZ44N MOSFET           |
                         +--------------+           |
                         |  G    D    S |           |
                         +--|----|----|-+           |
                            |    |    +-------------+----> Raspberry Pi GND &
                            |    |                         12V Power Supply (-) GND
                            |    |
                            |    +-----------------------> 12V DC Light (-) Negative Wire
                            |
                     12V Light (+) Positive Wire --------> +12V DC Power Supply (+) Rail
```

- **Gate (Pin 1):** Connected directly from Pi GPIO pin through a **220Ω series gate resistor** (protects GPIO from inrush current) and a **22kΩ pull-down resistor to GND** (prevents floating gate & flickering on bootup).
- **Drain (Pin 2):** Connected to the **Negative (-) load wire** of the 12V DC Stage Spotlight or Light Dome.
- **Source (Pin 3):** Connected directly to **Common Ground (GND)** (shared between 12V Power Supply (-) and Raspberry Pi GND).
- **Light Load (+):** Positive (+) wire of 12V Light connects directly to **+12V DC Power Supply (+)**.

---

## ⚙️ 4. SINGLE L298N DUAL H-BRIDGE MOTOR DRIVER (OEM FISH MOTORS)

- **Channel 1 / Channel A (Original OEM Mouth DC Motor for Lipsync):**
  - `ENA` (PWM) -> Raspberry Pi **GPIO 18** (Pin 12)
  - `IN1` -> **GPIO 23** (Pin 16) | `IN2` -> **GPIO 24** (Pin 18)
  - *Forward Polarity (`IN1=HIGH, IN2=LOW`):* Powers original OEM mouth motor to open lower jaw in sync with speech/song!

- **Channel 2 / Channel B (Original OEM Neck & Tail DC Motors):**
  - `ENB` (PWM) -> Raspberry Pi **GPIO 19** (Pin 35)
  - `IN3` -> **GPIO 25** (Pin 22) | `IN4` -> **GPIO 8** (Pin 24)
  - *Forward Polarity (`IN3=HIGH, IN4=LOW` with 100% PWM):* Powers original OEM neck motor forward to swing fish head/neck out horizontally facing the audience and holds it extended continuously while talking against the original OEM return spring.
  - *Depower (`IN3=LOW, IN4=LOW`, 0% PWM):* Cuts power to neck motor when done talking, allowing the original OEM return spring to pull the fish head/neck back flat against the wall plaque.
  - *Reverse Polarity (`IN3=LOW, IN4=HIGH` with 80% PWM):* Powers original OEM tail motor mechanism for tail wagging! (Active ONLY when NOT speaking).

---

## 🕯️ 5. 120VAC SOLID STATE RELAYS (SSRs) FOR MENORAH CANDLES

- 10 Solid State Relays (SSRs) with 3.3V DC trigger inputs driven directly by Raspberry Pi GPIO pins (`GPIO 4, 17, 27, 22, 10, 9, 11, 5, 6, 13`).
- `HIGH` (+3.3V DC) turns ON the corresponding 120VAC candle bulb; `LOW` turns it OFF.
