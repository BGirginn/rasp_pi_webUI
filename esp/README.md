# ESP32 RGB LED Firmware

This folder contains a minimal ESP32 firmware that works with this project:

- Supports device discovery via mDNS `_iot-device._tcp`
- Exposes HTTP endpoints used by the panel:
  - `GET /status` -> current RGB state
  - `GET /set?r=..&g=..&b=..&power=..` -> set RGB + power (query-string)
  - `GET /info` -> sensors payload for panel discovery polling
  - `POST /api/led/command` (and `/led/command`, `/command`) -> JSON command (`set_color`, `set_power`, `ping`)

## Wiring (4-pin RGB LED)

Use a resistor per color channel (220-330 ohm).

1. Identify the **common** leg (usually the longest).
2. Common Cathode LED:
   - Common -> `GND`
   - R/G/B legs -> GPIO pins through resistors
   - Logic: `HIGH`/PWM increases brightness
3. Common Anode LED:
   - Common -> `3V3`
   - R/G/B legs -> GPIO pins through resistors
   - Logic: inverted (PWM is inverted in code via `COMMON_ANODE`)

## "Power Off" Behavior

The panel's LED **On/Off** uses `power=0|1`.

- `power=0`: firmware sets pins to `INPUT` (high impedance) to stop driving the LED.
- Some firmware variants (see `esp32_rgb_minimal_common_anode`) also set **all safe GPIOs** to `INPUT/FLOATING` (and can include UART pins).

Note: Firmware cannot physically cut the ESP32's `3V3` rail. For a true power cut to external loads, add a load switch/MOSFET on the supply line.

Important: a 4-pin RGB LED has **one common pin**. You should NOT connect both `GND` and `3V3` to the LED.

## Default Pins

The default sketch uses PWM-safe ESP32 pins:

- Red: `GPIO25`
- Green: `GPIO26`
- Blue: `GPIO27`

If you wired to different pins, update `PIN_R`, `PIN_G`, `PIN_B` in the sketch.
