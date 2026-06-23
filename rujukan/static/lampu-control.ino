// Kontrol Relay ESP32 via Serial Monitor + MQTT
// Relay terhubung ke pin D19
// Library yang dibutuhkan: PubSubClient (install dari Library Manager)

#include <WiFi.h>
#include <PubSubClient.h>

// ====== KONFIGURASI WIFI ======
const char* WIFI_SSID = "Wifi-Elektro-Pengajar";
const char* WIFI_PASSWORD = "yangtautauaja";

// ====== MQTT TOPIC CONFIGURATION ======
// Change these for each ESP32 device
#define LAMP_ID "lamp1"
#define COMMAND_TOPIC "rumah/relay1/cmd"
#define STATUS_TOPIC "rumah/relay1/status"

// ====== KONFIGURASI MQTT ======
const char* MQTT_SERVER = "panel.elektrounsub.com"; // ganti dengan broker kamu
const int MQTT_PORT = 1883;
const char* MQTT_CLIENT_ID = "esp32-relay-001"; // buat unik kalau ada banyak device
const char* MQTT_USER = "";     // kosongkan jika broker tidak pakai auth
const char* MQTT_PASS = "";     // kosongkan jika broker tidak pakai auth


// ====== KONFIGURASI RELAY ======
const int RELAY_PIN = 19;

// Ubah ke true jika modul relay kamu aktif LOW (kebanyakan modul relay murah pakai LOW = ON)
const bool ACTIVE_LOW = true;

bool relayState = false; // false = OFF, true = ON

WiFiClient espClient;
PubSubClient mqttClient(espClient);

unsigned long lastReconnectAttempt = 0;

void setup() {
  Serial.begin(115200);
  pinMode(RELAY_PIN, OUTPUT);
  setRelay(false); // pastikan relay mati saat awal

  Serial.println();
  Serial.println("=== Kontrol Relay ESP32 (Serial + MQTT) ===");
  printHelp();

  connectWiFi();

  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
}

void loop() {
  // Jaga koneksi WiFi
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  // Jaga koneksi MQTT
  if (!mqttClient.connected()) {
    unsigned long now = millis();
    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = now;
      reconnectMQTT();
    }
  } else {
    mqttClient.loop();
  }

  // Cek perintah dari Serial Monitor
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    handleCommand(cmd, "Serial");
  }
}

// ====== HANDLE PERINTAH (dipakai oleh Serial maupun MQTT) ======
void handleCommand(String cmd, String source) {
  cmd.toLowerCase();

  if (cmd == "on" || cmd == "1") {
    setRelay(true);
    Serial.println("[" + source + "] Relay: ON");
  }
  else if (cmd == "off" || cmd == "0") {
    setRelay(false);
    Serial.println("[" + source + "] Relay: OFF");
  }
  else if (cmd == "toggle" || cmd == "t") {
    setRelay(!relayState);
    Serial.println("[" + source + "] Relay: " + String(relayState ? "ON" : "OFF"));
  }
  else if (cmd == "status" || cmd == "s") {
    Serial.println("Status relay saat ini: " + String(relayState ? "ON" : "OFF"));
  }
  else if (cmd == "help" || cmd == "h") {
    printHelp();
  }
  else {
    Serial.println("[" + source + "] Perintah tidak dikenal: " + cmd);
  }
}

// ====== SET RELAY + PUBLISH STATUS ======
void setRelay(bool on) {
  relayState = on;
  if (ACTIVE_LOW) {
    digitalWrite(RELAY_PIN, on ? LOW : HIGH);
  } else {
    digitalWrite(RELAY_PIN, on ? HIGH : LOW);
  }
  publishStatus();
}

void publishStatus() {
  if (mqttClient.connected()) {
    mqttClient.publish(STATUS_TOPIC, relayState ? "ON" : "OFF", true); // retained
  }
}

// ====== WIFI ======
void connectWiFi() {
  Serial.print("Menghubungkan ke WiFi: ");
  Serial.println(WIFI_SSID);

  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - startAttempt < 15000) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("WiFi terhubung. IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println();
    Serial.println("Gagal konek WiFi, akan dicoba lagi di loop().");
  }
}

// ====== MQTT ======
void reconnectMQTT() {
  if (WiFi.status() != WL_CONNECTED) return;

  Serial.print("Menghubungkan ke MQTT broker...");

  bool connected;
  if (strlen(MQTT_USER) > 0) {
    connected = mqttClient.connect(MQTT_CLIENT_ID, MQTT_USER, MQTT_PASS);
  } else {
    connected = mqttClient.connect(MQTT_CLIENT_ID);
  }

  if (connected) {
    Serial.println(" berhasil!");
    mqttClient.subscribe(COMMAND_TOPIC);
    Serial.println("Subscribe ke topic: " + String(COMMAND_TOPIC));
    publishStatus(); // kirim status awal
  } else {
    Serial.print(" gagal, rc=");
    Serial.println(mqttClient.state());
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  String message;
  for (unsigned int i = 0; i < length; i++) {
    message += (char)payload[i];
  }

  Serial.println("Pesan MQTT diterima [" + String(topic) + "]: " + message);

  if (String(topic) == COMMAND_TOPIC) {
    handleCommand(message, "MQTT");
  }
}

void printHelp() {
  Serial.println("Perintah yang tersedia (Serial / MQTT):");
  Serial.println("  on / 1     -> nyalakan relay");
  Serial.println("  off / 0    -> matikan relay");
  Serial.println("  toggle / t -> ganti status relay");
  Serial.println("  status / s -> tampilkan status relay (hanya Serial)");
  Serial.println("  help / h   -> tampilkan bantuan ini (hanya Serial)");
}