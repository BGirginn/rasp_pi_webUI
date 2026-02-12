/*
 * Minimal ESP32 RGB HTTP (Common Anode) + True Power Off
 *
 * Wiring:
 *  - RGB LED long leg (common) -> 3V3  (common anode)
 *  - R/G/B legs -> GPIO pins THROUGH 220-330 ohm resistors
 *
 * Endpoints:
 *  - GET /set?r=..&g=..&b=..&power=0|1
 *    - power=0: sets pins to INPUT (cuts output drive)
 *    - power=1: sets pins OUTPUT and applies last RGB
 *  - GET /status -> {"device":"esp32-rgb","r":..,"g":..,"b":..,"power":..}
 */

#include <WiFi.h>
#include <WebServer.h>
#include <driver/gpio.h>

#define WIFI_SSID "uni1n020"
#define WIFI_PASS "368117bG!!!"

// Wiring pins (color control still needs concrete pins).
// WROOM-32 does NOT have GPIO24.
// Your earlier wiring was GPIO12/13/14; keep defaults there.
#define RED_PIN   12
#define GREEN_PIN 14
#define BLUE_PIN  13

static const bool COMMON_ANODE = true;
static const bool POWER_OFF_ALL_SAFE_GPIO = true;
// If you truly want "all pins", include UART0 pins too. This disables Serial RX/TX while off.
static const bool KEEP_UART0_PINS = false;

uint8_t curR = 0, curG = 0, curB = 0;
bool curPower = true;

WebServer server(80);

static uint8_t clamp255(int v) {
  if (v < 0) return 0;
  if (v > 255) return 255;
  return (uint8_t)v;
}

static bool parseBoolArg(const String& v, bool defVal) {
  String s = v; s.toLowerCase();
  if (s == "1" || s == "true" || s == "on" || s == "yes") return true;
  if (s == "0" || s == "false" || s == "off" || s == "no") return false;
  return defVal;
}

static void pinsOutput() {
  pinMode(RED_PIN, OUTPUT);
  pinMode(GREEN_PIN, OUTPUT);
  pinMode(BLUE_PIN, OUTPUT);
}

static void pinsInput() {
  pinMode(RED_PIN, INPUT);
  pinMode(GREEN_PIN, INPUT);
  pinMode(BLUE_PIN, INPUT);
}

static void setHiZFloating(int pin) {
  if (!digitalPinIsValid(pin)) return;
  gpio_num_t gp = (gpio_num_t)pin;
  // Reset to default mux/function and float it.
  gpio_reset_pin(gp);
  gpio_set_pull_mode(gp, GPIO_FLOATING);
  pinMode(pin, INPUT);
}

static void cutAllSafeGpioOutputs() {
  // We cannot safely touch GPIO6-11 (connected to SPI flash) from Arduino; doing so may crash.
  // For classic ESP32, this list covers the typical "safe" GPIOs on dev boards.
  static const int pins[] = {
    0, 2, 4, 5,
    12, 13, 14, 15,
    16, 17, 18, 19,
    21, 22, 23,
    25, 26, 27,
    32, 33,
    34, 35, 36, 39
  };

  for (size_t i = 0; i < (sizeof(pins) / sizeof(pins[0])); i++) {
    int p = pins[i];
    if (KEEP_UART0_PINS && (p == 1 || p == 3)) continue;
    setHiZFloating(p);
  }

  if (!KEEP_UART0_PINS) {
    setHiZFloating(1);
    setHiZFloating(3);
  }
}

static void writePwm(int pin, uint8_t value /* 0..255 */) {
  uint8_t duty = value;
  if (COMMON_ANODE) duty = 255 - duty;
  analogWrite(pin, duty);
}

static void applyRgb() {
  if (!curPower) return;
  writePwm(RED_PIN, curR);
  writePwm(GREEN_PIN, curG);
  writePwm(BLUE_PIN, curB);
}

static void setPower(bool on) {
  curPower = on;
  if (!on) {
    // True "cut output drive" for RGB pins, and optionally for all safe pins.
    // This does NOT cut the ESP32's 3V3 supply. It only makes GPIOs high-impedance.
    pinsInput();
    // Detach PWM if it was attached (safe even if not attached).
    ledcDetachPin(RED_PIN);
    ledcDetachPin(GREEN_PIN);
    ledcDetachPin(BLUE_PIN);
    if (POWER_OFF_ALL_SAFE_GPIO) {
      cutAllSafeGpioOutputs();
      Serial.println("POWER OFF (all safe GPIO -> INPUT/FLOATING)");
    } else {
      Serial.println("POWER OFF (RGB pins INPUT)");
    }
  } else {
    pinsOutput();
    applyRgb();
    Serial.println("POWER ON (pins OUTPUT)");
  }
}

static void setRgb(uint8_t r, uint8_t g, uint8_t b) {
  curR = r; curG = g; curB = b;
  if (curPower) applyRgb();
  Serial.printf("RGB: R=%u G=%u B=%u (power=%d)\n", r, g, b, (int)curPower);
}

void handleSet() {
  if (server.hasArg("power")) setPower(parseBoolArg(server.arg("power"), curPower));

  int r = server.hasArg("r") ? server.arg("r").toInt() : curR;
  int g = server.hasArg("g") ? server.arg("g").toInt() : curG;
  int b = server.hasArg("b") ? server.arg("b").toInt() : curB;
  setRgb(clamp255(r), clamp255(g), clamp255(b));

  server.send(200, "application/json",
    String("{\"r\":") + curR +
    ",\"g\":" + curG +
    ",\"b\":" + curB +
    ",\"power\":" + (curPower ? "true" : "false") + "}"
  );
}

void handleStatus() {
  server.send(200, "application/json",
    String("{\"device\":\"esp32-rgb\",\"r\":") + curR +
    ",\"g\":" + curG + ",\"b\":" + curB +
    ",\"power\":" + (curPower ? "true" : "false") + "}"
  );
}

void setup() {
  Serial.begin(115200);
  delay(200);

  // Start in ON mode with outputs.
  pinsOutput();
  setRgb(0, 0, 0);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  Serial.print("Connecting");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  server.on("/set", HTTP_GET, handleSet);
  server.on("/status", HTTP_GET, handleStatus);
  server.begin();
  Serial.println("API ready");
}

void loop() {
  server.handleClient();
}
