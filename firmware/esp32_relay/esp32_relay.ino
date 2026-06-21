/*
 * ElBot Home Asisten - ESP32 Relay Controller
 *
 * Full firmware in single file - controls 4 relays via MQTT with OTA support
 *
 * Hardware:
 * - ESP32 DevKit (any variant)
 * - 4-channel relay module (active LOW)
 *
 * MQTT Topics:
 * - elbot/{device_id}/cmd - Receive relay commands
 * - elbot/{device_id}/status - Send relay status
 * - elbot/{device_id}/ota - Receive OTA firmware chunks
 * - elbot/{device_id}/lwt - Last Will Testament (online/offline)
 *
 * Command format (JSON):
 * { "relay": "relay_1", "state": "ON" }
 *
 * Status format (JSON):
 * { "relay_1": "ON", "relay_2": "OFF", "relay_3": "OFF", "relay_4": "OFF", "rssi": -55, "uptime": 12345 }
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include <Update.h>

// ═══════════════════════════════════════════════════
// CONFIGURATION - Update these for your setup
// ═══════════════════════════════════════════════════
const char* WIFI_SSID = "YourSSID";
const char* WIFI_PASSWORD = "YourPassword";
const char* MQTT_BROKER = "192.168.1.100";  // Backend server IP
const int MQTT_PORT = 1883;
const char* MQTT_USERNAME = "";             // Leave empty if no auth
const char* MQTT_PASSWORD = "";             // Leave empty if no auth
const char* DEVICE_ID = "esp32_relay_01";   // Unique device ID

// Relay GPIO pins (active LOW)
const int RELAY_PINS[4] = {26, 25, 33, 32};  // relay_1 to relay_4
const int RELAY_COUNT = 4;

// Status interval
const unsigned long STATUS_INTERVAL = 5000;  // 5 seconds

// ═══════════════════════════════════════════════════
// GLOBALS
// ═══════════════════════════════════════════════════
WiFiClient espClient;
PubSubClient mqttClient(espClient);
Preferences preferences;

// Relay state tracking
String relayStates[4] = {"OFF", "OFF", "OFF", "OFF"};

// Timing
unsigned long lastStatusTime = 0;
unsigned long bootTime = 0;

// OTA state
#define OTA_CHUNK_SIZE 8192
bool otaActive = false;
unsigned int otaExpectedChunks = 0;
unsigned int otaReceivedChunks = 0;
unsigned long otaStartTime = 0;
const unsigned long OTA_TIMEOUT = 300000;  // 5 minutes
char* otaDecodeBuffer = NULL;

// ═══════════════════════════════════════════════════
// OTA FUNCTIONS
// ═══════════════════════════════════════════════════

/**
 * Base64 decode - standard algorithm
 * Returns number of bytes decoded
 */
int base64Decode(const char* input, unsigned char* output) {
  const char b64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
  int decodeTable[128];
  for (int i = 0; i < 64; i++) decodeTable[(int)b64[i]] = i;

  unsigned int inputLen = strlen(input);
  unsigned int outputLen = 0;
  unsigned int quad = 0;  // accumulated 24-bit group
  int charsInQuad = 0;    // how many b64 chars we've read in this group

  for (unsigned int i = 0; i < inputLen; i++) {
    char c = input[i];
    if (c == '=') break;  // padding = end of data

    int val = decodeTable[(int)c];
    if (val < 0 || val >= 64) continue;  // skip whitespace/non-b64 chars

    quad = (quad << 6) | val;
    charsInQuad++;

    if (charsInQuad == 4) {
      // 4 b64 chars → 3 output bytes
      output[outputLen++] = (quad >> 16) & 0xFF;
      output[outputLen++] = (quad >> 8) & 0xFF;
      output[outputLen++] = quad & 0xFF;
      quad = 0;
      charsInQuad = 0;
    }
  }

  // Handle remaining partial quad (padding case)
  if (charsInQuad == 3) {
    quad <<= 6;
    output[outputLen++] = (quad >> 16) & 0xFF;
    output[outputLen++] = (quad >> 8) & 0xFF;
  } else if (charsInQuad == 2) {
    quad <<= 12;
    output[outputLen++] = (quad >> 16) & 0xFF;
  }

  return outputLen;
}

/**
 * Initialize OTA handler
 */
void initOTA() {
  otaDecodeBuffer = (char*)malloc(OTA_CHUNK_SIZE);
  if (!otaDecodeBuffer) {
    Serial.println("ERROR: Could not allocate OTA buffer");
  } else {
    Serial.println("OTA handler initialized");
  }
}

/**
 * Handle OTA chunk from MQTT
 */
void handleOTAChunk(JsonDocument& doc) {
  int chunkIndex = doc["chunk"] | -1;
  int totalChunks = doc["total"] | -1;
  const char* data = doc["data"];
  const char* firmwareHash = doc["hash"];

  if (chunkIndex < 0 || totalChunks <= 0 || !data) {
    Serial.println("OTA: Invalid chunk metadata");
    return;
  }

  // Start new OTA on first chunk
  if (chunkIndex == 0) {
    Serial.printf("OTA: Starting update (%d chunks)\n", totalChunks);

    if (!Update.begin(UPDATE_SIZE_UNKNOWN)) {
      Serial.printf("OTA: begin() failed - %s\n", Update.errorString());
      return;
    }

    otaActive = true;
    otaExpectedChunks = totalChunks;
    otaReceivedChunks = 0;
    otaStartTime = millis();
  }

  if (!otaActive) {
    Serial.println("OTA: No active update");
    return;
  }

  // Check chunk order
  if (chunkIndex != otaReceivedChunks) {
    Serial.printf("OTA: Expected chunk %d, got %d\n", otaReceivedChunks, chunkIndex);
    Update.abort();
    otaActive = false;
    return;
  }

  // Decode and write
  int dataLen = base64Decode(data, (unsigned char*)otaDecodeBuffer);

  if (dataLen <= 0) {
    Serial.println("OTA: Decode failed");
    Update.abort();
    otaActive = false;
    return;
  }

  size_t written = Update.write((uint8_t*)otaDecodeBuffer, dataLen);

  if (written != dataLen) {
    Serial.printf("OTA: Write failed - %s\n", Update.errorString());
    Update.abort();
    otaActive = false;
    return;
  }

  otaReceivedChunks++;
  Serial.printf("OTA: Chunk %d/%d (%d bytes)\n", chunkIndex + 1, totalChunks, dataLen);

  // Check if complete
  if (otaReceivedChunks >= otaExpectedChunks) {
    if (Update.end(true)) {
      Serial.println("OTA: Success! Restarting...");
      delay(1000);
      ESP.restart();
    } else {
      Serial.printf("OTA: end() failed - %s\n", Update.errorString());
      otaActive = false;
    }
  }

  // Timeout check
  if (otaActive && (millis() - otaStartTime > OTA_TIMEOUT)) {
    Serial.println("OTA: Timeout");
    Update.abort();
    otaActive = false;
  }
}

// ═══════════════════════════════════════════════════
// WIFI SETUP
// ═══════════════════════════════════════════════════
void setupWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 50) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
    Serial.print("RSSI: ");
    Serial.println(WiFi.RSSI());
  } else {
    Serial.println("\nWiFi failed - restarting");
    ESP.restart();
  }
}

// ═══════════════════════════════════════════════════
// MQTT CALLBACK
// ═══════════════════════════════════════════════════
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicStr = String(topic);

  StaticJsonDocument<1024> doc;
  DeserializationError error = deserializeJson(doc, payload, length);

  if (error) {
    Serial.print("JSON parse error: ");
    Serial.println(error.c_str());
    return;
  }

  // Handle relay command
  if (topicStr.endsWith("/cmd")) {
    const char* relay = doc["relay"];
    const char* state = doc["state"];

    if (relay && state) {
      handleRelayCommand(relay, state);
    }
  }

  // Handle OTA
  if (topicStr.endsWith("/ota")) {
    handleOTAChunk(doc);
  }
}

// ═══════════════════════════════════════════════════
// RELAY CONTROL
// ═══════════════════════════════════════════════════
void handleRelayCommand(const char* relay, const char* value) {
  int relayNum = -1;

  // Parse relay_1, relay_2, etc
  if (strncmp(relay, "relay_", 6) == 0) {
    relayNum = atoi(relay + 6) - 1;
  }

  if (relayNum < 0 || relayNum >= RELAY_COUNT) {
    Serial.print("Invalid relay: ");
    Serial.println(relay);
    return;
  }

  // Set relay (active LOW)
  bool turnOn = (strcmp(value, "ON") == 0);
  digitalWrite(RELAY_PINS[relayNum], turnOn ? LOW : HIGH);

  relayStates[relayNum] = turnOn ? "ON" : "OFF";

  Serial.print("Relay ");
  Serial.print(relayNum + 1);
  Serial.print(" -> ");
  Serial.println(relayStates[relayNum]);

  // Immediate status update
  publishStatus();

  // Save to preferences
  preferences.begin("elbot", false);
  String key = "relay_" + String(relayNum + 1);
  preferences.putString(key.c_str(), relayStates[relayNum]);
  preferences.end();
}

// ═══════════════════════════════════════════════════
// MQTT STATUS PUBLISH
// ═══════════════════════════════════════════════════
void publishStatus() {
  StaticJsonDocument<384> doc;

  doc["device_id"] = DEVICE_ID;
  for (int i = 0; i < RELAY_COUNT; i++) {
    String key = "relay_" + String(i + 1);
    doc[key] = relayStates[i];
  }
  doc["rssi"] = WiFi.RSSI();
  doc["uptime"] = (millis() - bootTime) / 1000;

  char buffer[384];
  serializeJson(doc, buffer);

  String topic = "elbot/" + String(DEVICE_ID) + "/status";
  mqttClient.publish(topic.c_str(), buffer, true);

  Serial.printf("Status published (relay_1=%s, relay_2=%s, rssi=%d)\n",
    relayStates[0].c_str(), relayStates[1].c_str(), WiFi.RSSI());
}

// ═══════════════════════════════════════════════════
// MQTT CONNECTION
// ═══════════════════════════════════════════════════
void reconnectMQTT() {
  if (mqttClient.connected()) return;

  Serial.print("MQTT connecting... ");

  String clientId = "ESP32_" + String(DEVICE_ID) + "_" + String(random(0xffff), HEX);

  // LWT (Last Will Testament) — broker will publish "offline" if we disconnect
  String lwtTopic = "elbot/" + String(DEVICE_ID) + "/lwt";
  const char* lwtOnline = "{\"status\":\"online\"}";
  const char* lwtOffline = "{\"status\":\"offline\"}";

  if (mqttClient.connect(clientId.c_str(),
                          MQTT_USERNAME, MQTT_PASSWORD,
                          lwtTopic.c_str(), 0, true, lwtOffline)) {
    Serial.println("connected");

    // Publish online status
    mqttClient.publish(lwtTopic.c_str(), lwtOnline, true);

    // Subscribe to command topic
    String cmdTopic = "elbot/" + String(DEVICE_ID) + "/cmd";
    mqttClient.subscribe(cmdTopic.c_str());
    Serial.printf("Sub: %s\n", cmdTopic.c_str());

    // Subscribe to OTA topic
    String otaTopic = "elbot/" + String(DEVICE_ID) + "/ota";
    mqttClient.subscribe(otaTopic.c_str());
    Serial.printf("Sub: %s\n", otaTopic.c_str());

    // Send initial status
    publishStatus();

  } else {
    Serial.printf("failed (rc=%d)\n", mqttClient.state());
  }
}

// ═══════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println();
  Serial.println("╔══════════════════════════════════════╗");
  Serial.println("║   ElBot Home Asisten - ESP32 Relay   ║");
  Serial.println("║   WiFi + MQTT + 4 Relay + OTA        ║");
  Serial.println("╚══════════════════════════════════════╝");
  Serial.println();

  // Init relay pins (HIGH = OFF for active LOW relays)
  for (int i = 0; i < RELAY_COUNT; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], HIGH);
    Serial.printf("Relay %d -> GPIO %d (OFF)\n", i + 1, RELAY_PINS[i]);
  }

  // Restore saved relay states
  preferences.begin("elbot", false);
  for (int i = 0; i < RELAY_COUNT; i++) {
    String key = "relay_" + String(i + 1);
    String saved = preferences.getString(key.c_str(), "OFF");
    relayStates[i] = saved;

    bool isOn = (saved == "ON");
    digitalWrite(RELAY_PINS[i], isOn ? LOW : HIGH);

    Serial.printf("Restored relay_%d: %s\n", i + 1, saved.c_str());
  }
  preferences.end();

  // WiFi + MQTT
  setupWiFi();

  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(4096);

  // Init OTA
  initOTA();

  // Connect MQTT
  reconnectMQTT();

  bootTime = millis();
  Serial.println("\nReady.\n");
}

// ═══════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════
void loop() {
  mqttClient.loop();

  unsigned long now = millis();

  // Non-blocking MQTT reconnect with 5s backoff
  static unsigned long lastReconnectAttempt = 0;
  if (!mqttClient.connected() && (now - lastReconnectAttempt > 5000)) {
    lastReconnectAttempt = now;
    reconnectMQTT();
  }

  // Periodic status publish
  if (now - lastStatusTime >= STATUS_INTERVAL) {
    lastStatusTime = now;
    publishStatus();

    // Persist relay states
    preferences.begin("elbot", false);
    for (int i = 0; i < RELAY_COUNT; i++) {
      String key = "relay_" + String(i + 1);
      preferences.putString(key.c_str(), relayStates[i]);
    }
    preferences.end();
  }
}
