/*
 * ElBot Home Asisten - ESP32 Relay Controller
 *
 * Controls 4 relays via MQTT and supports OTA firmware updates
 *
 * Hardware:
 * - ESP32 DevKit (any variant)
 * - 4-channel relay module (active LOW)
 *
 * MQTT Topics:
 * - elbot/{device_id}/cmd - Receive relay commands
 * - elbot/{device_id}/status - Send relay status
 * - elbot/{device_id}/ota - Receive OTA firmware chunks
 *
 * Command format (JSON):
 * { "relay": "relay_1", "state": "on" }
 *
 * Status format (JSON):
 * { "relay_1": "off", "relay_2": "off", "relay_3": "off", "relay_4": "off" }
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include "ota_handler.h"

// ═══════════════════════════════════════════════════
// CONFIGURATION (Update these for your setup)
// ═══════════════════════════════════════════════════
const char* WIFI_SSID = "YourSSID";
const char* WIFI_PASSWORD = "YourPassword";
const char* MQTT_BROKER = "192.168.1.100";  // Your backend server IP
const int MQTT_PORT = 1883;
const char* DEVICE_ID = "esp32_relay_01";

// Relay GPIO pins (update if using different pins)
const int RELAY_PINS[4] = {13, 12, 14, 27};  // relay_1 to relay_4
const int RELAY_COUNT = 4;

// ═══════════════════════════════════════════════════
// GLOBALS
// ═══════════════════════════════════════════════════
WiFiClient espClient;
PubSubClient mqttClient(espClient);
Preferences preferences;

// Relay state tracking
String relayStates[4] = {"off", "off", "off", "off"};

// Timing
unsigned long lastStatusTime = 0;
const unsigned long STATUS_INTERVAL = 5000;  // Send status every 5 seconds

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
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi connection failed");
    ESP.restart();
  }
}

// ═══════════════════════════════════════════════════
// MQTT CALLBACK
// ═══════════════════════════════════════════════════
void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String topicStr = String(topic);

  // Allocate JSON buffer
  StaticJsonDocument<512> doc;
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

  // Handle OTA data
  if (topicStr.endsWith("/ota")) {
    handleOTAChunk(doc);
  }
}

// ═══════════════════════════════════════════════════
// RELAY CONTROL
// ═══════════════════════════════════════════════════
void handleRelayCommand(const char* relay, const char* state) {
  int relayNum = -1;

  // Parse relay number (relay_1, relay_2, etc)
  if (strncmp(relay, "relay_", 6) == 0) {
    relayNum = atoi(relay + 6) - 1;  // Convert to 0-indexed
  }

  if (relayNum < 0 || relayNum >= RELAY_COUNT) {
    Serial.print("Invalid relay: ");
    Serial.println(relay);
    return;
  }

  // Set relay state (active LOW)
  bool turnOn = (strcmp(state, "on") == 0);
  digitalWrite(RELAY_PINS[relayNum], turnOn ? LOW : HIGH);

  // Update state tracking
  relayStates[relayNum] = turnOn ? "on" : "off";

  Serial.print("Relay ");
  Serial.print(relayNum + 1);
  Serial.print(" = ");
  Serial.println(relayStates[relayNum]);

  // Send immediate status update
  publishStatus();
}

// ═══════════════════════════════════════════════════
// MQTT STATUS PUBLISH
// ═══════════════════════════════════════════════════
void publishStatus() {
  StaticJsonDocument<256> doc;

  for (int i = 0; i < RELAY_COUNT; i++) {
    String key = "relay_" + String(i + 1);
    doc[key] = relayStates[i];
  }

  char buffer[256];
  serializeJson(doc, buffer);

  String topic = "elbot/" + String(DEVICE_ID) + "/status";
  mqttClient.publish(topic.c_str(), buffer);
}

// ═══════════════════════════════════════════════════
// MQTT CONNECTION
// ═══════════════════════════════════════════════════
void reconnectMQTT() {
  // Loop until connected
  while (!mqttClient.connected()) {
    Serial.print("Connecting to MQTT broker...");

    String clientId = "ESP32_";
    clientId += String(random(0xffff), HEX);

    if (mqttClient.connect(clientId.c_str())) {
      Serial.println("connected");

      // Subscribe to command topic
      String cmdTopic = "elbot/" + String(DEVICE_ID) + "/cmd";
      mqttClient.subscribe(cmdTopic.c_str());
      Serial.print("Subscribed to: ");
      Serial.println(cmdTopic);

      // Subscribe to OTA topic
      String otaTopic = "elbot/" + String(DEVICE_ID) + "/ota";
      mqttClient.subscribe(otaTopic.c_str());
      Serial.print("Subscribed to: ");
      Serial.println(otaTopic);

      // Send initial status
      publishStatus();

    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" retrying in 5 seconds");
      delay(5000);
    }
  }
}

// ═══════════════════════════════════════════════════
// SETUP
// ═══════════════════════════════════════════════════
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n╔════════════════════════════════════╗");
  Serial.println("║  ElBot Home Asisten - ESP32 Relay  ║");
  Serial.println("╚════════════════════════════════════╝\n");

  // Initialize relay pins as outputs (HIGH = OFF for active LOW relays)
  for (int i = 0; i < RELAY_COUNT; i++) {
    pinMode(RELAY_PINS[i], OUTPUT);
    digitalWrite(RELAY_PINS[i], HIGH);  // Start OFF
  }

  // Load saved states from preferences
  preferences.begin("elbot", false);
  for (int i = 0; i < RELAY_COUNT; i++) {
    String key = "relay_" + String(i + 1);
    String savedState = preferences.getString(key.c_str(), "off");
    relayStates[i] = savedState;

    // Apply saved state
    bool isOn = (savedState == "on");
    digitalWrite(RELAY_PINS[i], isOn ? LOW : HIGH);

    Serial.print("Loaded ");
    Serial.print(key);
    Serial.print(": ");
    Serial.println(savedState);
  }
  preferences.end();

  // Setup WiFi and MQTT
  setupWiFi();
  mqttClient.setServer(MQTT_BROKER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  mqttClient.setBufferSize(4096);  // Larger buffer for OTA

  // Initialize OTA handler
  initOTA();

  Serial.println("\nSetup complete. Ready to receive commands.\n");
}

// ═══════════════════════════════════════════════════
// MAIN LOOP
// ═══════════════════════════════════════════════════
void loop() {
  // Reconnect MQTT if needed
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }

  // Handle MQTT messages
  mqttClient.loop();

  // Periodic status update
  unsigned long now = millis();
  if (now - lastStatusTime > STATUS_INTERVAL) {
    lastStatusTime = now;
    publishStatus();

    // Save states to preferences
    preferences.begin("elbot", false);
    for (int i = 0; i < RELAY_COUNT; i++) {
      String key = "relay_" + String(i + 1);
      preferences.putString(key.c_str(), relayStates[i]);
    }
    preferences.end();
  }
}
