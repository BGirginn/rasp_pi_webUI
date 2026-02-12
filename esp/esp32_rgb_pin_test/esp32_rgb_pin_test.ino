/*
 * ESP32 RGB LED Pin Test (Common Anode)
 *
 * Wiring (common-anode RGB LED):
 *  - Long leg (common) -> 3V3
 *  - R/G/B legs -> GPIO pins THROUGH 220-330 ohm resistors
 *
 * Common-anode logic:
 *  - GPIO LOW  -> LED ON (sinking current)
 *  - GPIO HIGH -> LED OFF
 *
 * IMPORTANT:
 *  - Do not connect LED legs directly to GND or 3V3 without resistors.
 *  - Prefer GPIO25/26/27 on ESP32 Dev Module (avoid strapping pins).
 */

static const int PIN_R = 25;
static const int PIN_G = 26;
static const int PIN_B = 27;

static void allOff() {
  digitalWrite(PIN_R, HIGH);
  digitalWrite(PIN_G, HIGH);
  digitalWrite(PIN_B, HIGH);
}

static void showR() {
  allOff();
  digitalWrite(PIN_R, LOW);
}

static void showG() {
  allOff();
  digitalWrite(PIN_G, LOW);
}

static void showB() {
  allOff();
  digitalWrite(PIN_B, LOW);
}

void setup() {
  pinMode(PIN_R, OUTPUT);
  pinMode(PIN_G, OUTPUT);
  pinMode(PIN_B, OUTPUT);
  allOff();
}

void loop() {
  showR(); delay(800);
  showG(); delay(800);
  showB(); delay(800);
  allOff(); delay(600);
}

