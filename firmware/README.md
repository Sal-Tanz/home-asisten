# ESP32 Relay Firmware - ElBot Home Asisten

## Hardware Requirements

- ESP32 DevKit (any variant: ESP32-WROOM, ESP32-S3, etc)
- 4-channel relay module (active LOW recommended)
- 5V power supply

## Wiring

| ESP32 GPIO | Relay Channel | Wire Color |
|------------|---------------|------------|
| GPIO 13 | Relay 1 (relay_1) | - |
| GPIO 12 | Relay 2 (relay_2) | - |
| GPIO 14 | Relay 3 (relay_3) | - |
| GPIO 27 | Relay 4 (relay_4) | - |
| GND | GND | - |
| VIN/5V | VCC | - |

## Configuration

Before flashing, update these values in `esp32_relay.ino`:

```cpp
const char* WIFI_SSID = "YourSSID";
const char* WIFI_PASSWORD = "YourPassword";
const char* MQTT_BROKER = "192.168.1.100";  // Backend IP
const char* DEVICE_ID = "esp32_relay_01";    // Unique device ID
```

## Flashing (Arduino IDE)

1. Install ESP32 board support: File → Preferences → `https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json`
2. Install libraries: PubSubClient, ArduinoJson
3. Open `esp32_relay.ino`
4. Select board: ESP32 Dev Module
5. Flash via USB

## MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `elbot/{device_id}/cmd` | Backend → ESP32 | Relay commands |
| `elbot/{device_id}/status` | ESP32 → Backend | Relay status + RSSI |
| `elbot/{device_id}/lwt` | ESP32 → Backend | Online/offline (LWT) |
| `elbot/{device_id}/ota` | Backend → ESP32 | OTA firmware chunks |

## Command Format

```json
{"relay": "relay_1", "state": "on"}
```

## Status Format

```json
{"relay_1": "on", "relay_2": "off", "relay_3": "off", "relay_4": "off"}
```

## OTA Update

1. Build new firmware in Arduino IDE
2. Export compiled binary: Sketch → Export compiled Binary
3. Upload .bin file via Web UI (Settings → Firmware)

## Troubleshooting

- Relay not responding: Check wiring (active LOW means ON = LOW)
- MQTT connection fails: Verify broker IP and port
- WiFi not connecting: Check SSID and password
- OTA update fails: Ensure ESP32 has enough flash space