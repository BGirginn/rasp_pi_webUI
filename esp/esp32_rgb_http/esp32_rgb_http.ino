/*
 * ESP32 RGB LED HTTP Controller
 *
 * Endpoints:
 *  - GET  /status
 *  - GET  /set?r=..&g=..&b=..&brightness=..&power=..
 *  - GET  /info
 *  - POST /api/led/command  (also /led/command, /command)
 *
 * mDNS:
 *  - Advertises _iot-device._tcp on port 80 (service "iot-device", proto "tcp")
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>

// === WiFi ===
// Fill these in.
static const char* WIFI_SSID = "YOUR_WIFI_SSID";
static const char* WIFI_PASS = "YOUR_WIFI_PASSWORD";

// === Device ===
static const char* DEVICE_NAME = "esp32-rgb";

// === RGB LED wiring ===
// Choose stable PWM-capable pins (avoid strapping pins unless you know what you're doing).
static const int PIN_R = 25;
static const int PIN_G = 26;
static const int PIN_B = 27;

// If your RGB LED is common-anode (common leg to 3V3), set true.
static const bool COMMON_ANODE = false;

// LEDC PWM
static const int PWM_FREQ_HZ = 5000;
static const int PWM_RES_BITS = 8;   // 0-255
static const int CH_R = 0;
static const int CH_G = 1;
static const int CH_B = 2;

static WebServer server(80);

// Current state (0-255)
static int curR = 0;
static int curG = 0;
static int curB = 0;
static int curBrightness = 255;
static bool curPower = true;

static int clamp255(int v) {
  if (v < 0) return 0;
  if (v > 255) return 255;
  return v;
}

static bool parseBool(String v, bool defVal) {
  v.toLowerCase();
  if (v == "1" || v == "true" || v == "on" || v == "yes") return true;
  if (v == "0" || v == "false" || v == "off" || v == "no") return false;
  return defVal;
}

static int scaleWithBrightness(int v, int brightness, bool power) {
  if (!power || brightness <= 0) return 0;
  if (brightness >= 255) return clamp255(v);
  float s = (float)brightness / 255.0f;
  return clamp255((int)((float)v * s));
}

static void writeChannel(int channel, int value /* 0-255 */) {
  int duty = clamp255(value);
  if (COMMON_ANODE) duty = 255 - duty;
  ledcWrite(channel, duty);
}

static void applyState() {
  int r = scaleWithBrightness(curR, curBrightness, curPower);
  int g = scaleWithBrightness(curG, curBrightness, curPower);
  int b = scaleWithBrightness(curB, curBrightness, curPower);
  writeChannel(CH_R, r);
  writeChannel(CH_G, g);
  writeChannel(CH_B, b);
}

static String jsonEscape(const String& s) {
  String out;
  out.reserve(s.length() + 8);
  for (size_t i = 0; i < s.length(); i++) {
    char c = s[i];
    if (c == '\\\\' || c == '"') { out += '\\\\'; out += c; }
    else if (c == '\n') out += "\\n";
    else out += c;
  }
  return out;
}

static void sendJson(int code, const String& body) {
  server.sendHeader("Cache-Control", "no-store");
  server.send(code, "application/json", body);
}

static void handleStatus() {
  String body = "{";
  body += "\"device\":\"" + jsonEscape(String(DEVICE_NAME)) + "\",";
  body += "\"r\":" + String(curR) + ",";
  body += "\"g\":" + String(curG) + ",";
  body += "\"b\":" + String(curB) + ",";
  body += "\"brightness\":" + String(curBrightness) + ",";
  body += "\"power\":" + String(curPower ? "true" : "false") + ",";
  body += "\"pins\":{";
  body += "\"r\":" + String(PIN_R) + ",";
  body += "\"g\":" + String(PIN_G) + ",";
  body += "\"b\":" + String(PIN_B) + "},";
  body += "\"common_anode\":" + String(COMMON_ANODE ? "true" : "false");
  body += "}";
  sendJson(200, body);
}

static void handleInfo() {
  // Minimal `/info` payload compatible with panel polling:
  // {"id":"...","name":"...","sensors":[{"type":"...","value":..,"unit":".."}, ...]}
  int r = curPower ? curR : 0;
  int g = curPower ? curG : 0;
  int b = curPower ? curB : 0;
  int rssi = (int)WiFi.RSSI();

  String body = "{";
  body += "\"id\":\"" + jsonEscape(String(DEVICE_NAME)) + "\",";
  body += "\"name\":\"" + jsonEscape(String(DEVICE_NAME)) + "\",";
  body += "\"sensors\":[";
  body += "{\"type\":\"led_r\",\"value\":" + String(r) + ",\"unit\":\"\"},";
  body += "{\"type\":\"led_g\",\"value\":" + String(g) + ",\"unit\":\"\"},";
  body += "{\"type\":\"led_b\",\"value\":" + String(b) + ",\"unit\":\"\"},";
  body += "{\"type\":\"wifi_rssi\",\"value\":" + String(rssi) + ",\"unit\":\"dBm\"}";
  body += "]";
  body += "}";
  sendJson(200, body);
}

static void handleSetQuery() {
  if (server.hasArg("r")) curR = clamp255(server.arg("r").toInt());
  if (server.hasArg("g")) curG = clamp255(server.arg("g").toInt());
  if (server.hasArg("b")) curB = clamp255(server.arg("b").toInt());
  if (server.hasArg("brightness")) curBrightness = clamp255(server.arg("brightness").toInt());
  if (server.hasArg("power")) curPower = parseBool(server.arg("power"), curPower);

  applyState();

  String body = "{";
  body += "\"r\":" + String(curR) + ",";
  body += "\"g\":" + String(curG) + ",";
  body += "\"b\":" + String(curB) + "}";
  sendJson(200, body);
}

static int jsonGetInt(const String& body, const char* key, int defVal) {
  String k = String("\"") + key + "\"";
  int p = body.indexOf(k);
  if (p < 0) return defVal;
  p = body.indexOf(':', p);
  if (p < 0) return defVal;
  p++;
  while (p < (int)body.length() && (body[p] == ' ' || body[p] == '\n' || body[p] == '\r' || body[p] == '\t')) p++;
  bool neg = false;
  if (p < (int)body.length() && body[p] == '-') { neg = true; p++; }
  long v = 0;
  bool any = false;
  while (p < (int)body.length() && body[p] >= '0' && body[p] <= '9') {
    v = v * 10 + (body[p] - '0');
    p++;
    any = true;
  }
  if (!any) return defVal;
  if (neg) v = -v;
  return (int)v;
}

static bool jsonGetBool(const String& body, const char* key, bool defVal) {
  String k = String("\"") + key + "\"";
  int p = body.indexOf(k);
  if (p < 0) return defVal;
  p = body.indexOf(':', p);
  if (p < 0) return defVal;
  p++;
  while (p < (int)body.length() && (body[p] == ' ' || body[p] == '\n' || body[p] == '\r' || body[p] == '\t')) p++;
  if (body.startsWith("true", p)) return true;
  if (body.startsWith("false", p)) return false;
  return defVal;
}

static String jsonGetString(const String& body, const char* key, const String& defVal) {
  String k = String("\"") + key + "\"";
  int p = body.indexOf(k);
  if (p < 0) return defVal;
  p = body.indexOf(':', p);
  if (p < 0) return defVal;
  p++;
  while (p < (int)body.length() && (body[p] == ' ' || body[p] == '\n' || body[p] == '\r' || body[p] == '\t')) p++;
  if (p >= (int)body.length() || body[p] != '"') return defVal;
  p++;
  int e = body.indexOf('"', p);
  if (e < 0) return defVal;
  return body.substring(p, e);
}

static void handleLedCommandJson() {
  String body = server.arg("plain");
  if (body.length() == 0) {
    sendJson(400, "{\"success\":false,\"error\":\"missing body\"}");
    return;
  }

  String command = jsonGetString(body, "command", "");
  command.toLowerCase();

  if (command == "ping") {
    sendJson(200, "{\"success\":true}");
    return;
  }

  // Payload is nested but we just search keys in the whole body.
  if (command == "set_color") {
    curR = clamp255(jsonGetInt(body, "r", curR));
    curG = clamp255(jsonGetInt(body, "g", curG));
    curB = clamp255(jsonGetInt(body, "b", curB));
    curBrightness = clamp255(jsonGetInt(body, "brightness", curBrightness));
    curPower = jsonGetBool(body, "power", curPower);
    applyState();
    sendJson(200, "{\"success\":true}");
    return;
  }

  if (command == "set_power") {
    bool on = jsonGetBool(body, "on", curPower);
    curPower = on;
    applyState();
    sendJson(200, "{\"success\":true}");
    return;
  }

  sendJson(400, "{\"success\":false,\"error\":\"unknown command\"}");
}

static void handleNotFound() {
  server.send(404, "text/plain", String("Not found: ") + server.uri());
}

static void setupPwm() {
  ledcSetup(CH_R, PWM_FREQ_HZ, PWM_RES_BITS);
  ledcSetup(CH_G, PWM_FREQ_HZ, PWM_RES_BITS);
  ledcSetup(CH_B, PWM_FREQ_HZ, PWM_RES_BITS);
  ledcAttachPin(PIN_R, CH_R);
  ledcAttachPin(PIN_G, CH_G);
  ledcAttachPin(PIN_B, CH_B);
  applyState();
}

static void setupWifi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(250);
  }
}

static void setupMdns() {
  if (MDNS.begin(DEVICE_NAME)) {
    MDNS.addService("iot-device", "tcp", 80);
  }
}

void setup() {
  Serial.begin(115200);
  delay(200);

  setupPwm();
  setupWifi();
  setupMdns();

  server.on("/status", HTTP_GET, handleStatus);
  server.on("/info", HTTP_GET, handleInfo);
  server.on("/set", HTTP_GET, handleSetQuery);

  server.on("/api/led/command", HTTP_POST, handleLedCommandJson);
  server.on("/led/command", HTTP_POST, handleLedCommandJson);
  server.on("/command", HTTP_POST, handleLedCommandJson);

  server.onNotFound(handleNotFound);
  server.begin();

  Serial.print("IP: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  server.handleClient();
}

