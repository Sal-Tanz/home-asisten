# ElBot Home Asisten - ESP32 Relay (Wokwi Simulation)

Versi simulasi firmware ESP32 relay untuk platform Wokwi. Gunakan untuk testing dan development tanpa hardware fisik.

## 🚀 Quick Start

### 1. Buka di Wokwi

Ada 2 cara:

**Cara A: Upload Manual**
1. Buka [Wokwi.com](https://wokwi.com)
2. Buat New Project → ESP32
3. Upload semua file dari folder ini:
   - `sketch.ino`
   - `diagram.json`
   - `wokwi.toml`
   - `libraries.txt`

**Cara B: Wokwi CLI** (jika tersedia)
```bash
wokwi-cli project upload
```

### 2. Konfigurasi WiFi & MQTT

Edit `sketch.ino` baris 37-43:

```cpp
const char* WIFI_SSID = "Wokwi-GUEST";           // WiFi SSID
const char* WIFI_PASSWORD = "";                   // WiFi password
const char* MQTT_BROKER = "test.mosquitto.org";   // MQTT broker address
const int MQTT_PORT = 1883;
const char* MQTT_USERNAME = "";                   // MQTT username (kosongkan jika tidak ada)
const char* MQTT_PASSWORD = "";                   // MQTT password (kosongkan jika tidak ada)
const char* DEVICE_ID = "wokwi_relay_01";         // Unique device ID
```

**⚠️ PENTING:**
- Wokwi default WiFi: `Wokwi-GUEST` (no password)
- MQTT broker HARUS publicly accessible (tidak bisa `localhost`)
- Gunakan `test.mosquitto.org` untuk testing atau deploy broker cloud sendiri

### 3. Jalankan Simulasi

1. Klik tombol **Start Simulation** (▶️)
2. Buka **Serial Monitor** untuk melihat log
3. Tunggu hingga ESP32 connect ke WiFi dan MQTT
4. Status "Ready (Wokwi Mode)" muncul di serial

## 🎯 Cara Testing

### Test 1: Manual MQTT Command (via MQTT Explorer/CLI)

Publish ke topic: `elbot/wokwi_relay_01/cmd`

**Nyalakan relay 1:**
```json
{"relay": "relay_1", "state": "ON"}
```

**Matikan relay 2:**
```json
{"relay": "relay_2", "state": "OFF"}
```

**LED visual feedback:**
- 🔴 LED Merah = Relay 1
- 🟡 LED Kuning = Relay 2
- 🟢 LED Hijau = Relay 3
- 🔵 LED Biru = Relay 4

### Test 2: Integrasi dengan Backend ElBot

1. Pastikan backend ElBot running (`uvicorn app.main:app --port 8500`)
2. Update `backend/.env` agar MQTT broker sama dengan Wokwi
3. Tambah device di Settings → Device ID: `wokwi_relay_01`
4. Test voice command: "Bot, nyalakan lampu"

### Test 3: Monitor Status

Subscribe ke topic: `elbot/wokwi_relay_01/status`

Akan terima status setiap 5 detik:
```json
{
  "device_id": "wokwi_relay_01",
  "relay_1": "ON",
  "relay_2": "OFF",
  "relay_3": "OFF",
  "relay_4": "OFF",
  "rssi": -45,
  "uptime": 120
}
```

## 📡 MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `elbot/wokwi_relay_01/cmd` | Backend → ESP32 | Command relay ON/OFF |
| `elbot/wokwi_relay_01/status` | ESP32 → Backend | Heartbeat status (5s interval) |
| `elbot/wokwi_relay_01/lwt` | ESP32 → Broker | Last Will Testament (online/offline) |
| `elbot/wokwi_relay_01/ota` | Backend → ESP32 | OTA firmware update (limited in Wokwi) |

## 🔧 Diagram Wiring

```
ESP32 GPIO 26 → Relay 1 → LED Merah (220Ω)
ESP32 GPIO 25 → Relay 2 → LED Kuning (220Ω)
ESP32 GPIO 33 → Relay 3 → LED Hijau (220Ω)
ESP32 GPIO 32 → Relay 4 → LED Biru (220Ω)
```

Relay active **LOW** (GPIO LOW = Relay ON = LED menyala).

## ⚠️ Limitasi Wokwi

| Fitur | Status | Catatan |
|-------|--------|---------|
| WiFi connection | ✅ Supported | Via `Wokwi-GUEST` |
| MQTT pub/sub | ✅ Supported | Broker harus public |
| Relay control | ✅ Supported | Visual via LED indicator |
| Serial monitor | ✅ Supported | Untuk debugging |
| OTA update | ⚠️ Limited | Struktur code preserved tapi OTA mungkin tidak fully functional |
| Preferences (NVS) | ✅ Supported | State persistence antar restart |
| Real hardware I/O | ❌ Not supported | Simulasi saja |

## 🐛 Troubleshooting

### WiFi tidak connect
- Pastikan menggunakan `Wokwi-GUEST` atau WiFi yang valid di Wokwi
- Cek serial monitor untuk error message

### MQTT connection failed
- Broker harus publicly accessible (bukan `localhost` atau `192.168.x.x`)
- Test broker dulu dengan MQTT Explorer dari komputer lokal
- Gunakan `test.mosquitto.org:1883` untuk quick test

### Relay tidak respond
- Cek serial monitor: apakah MQTT subscribe berhasil?
- Pastikan payload JSON exact match format
- Device ID harus sama dengan yang di topic

### LED tidak menyala
- Pastikan simulasi sudah running (▶️)
- Relay active LOW: GPIO LOW = LED ON
- Cek wiring di `diagram.json`

## 📦 Files Structure

```
esp32_relay_wokwi/
├── sketch.ino          # Main firmware code
├── diagram.json        # Circuit wiring (4 relay + 4 LED)
├── wokwi.toml          # Wokwi project config
├── libraries.txt       # Dependencies (PubSubClient, ArduinoJson, etc)
└── README.md           # This file
```

## 🔗 Resources

- [Wokwi Documentation](https://docs.wokwi.com/)
- [PubSubClient Library](https://github.com/knolleary/pubsubclient)
- [ArduinoJson Library](https://arduinojson.org/)
- [Test MQTT Broker](https://test.mosquitto.org/)

## 🆚 Perbedaan dengan Hardware Version

| Aspek | Hardware (`esp32_relay.ino`) | Wokwi (`sketch.ino`) |
|-------|------------------------------|----------------------|
| WiFi credentials | Hardcoded real SSID | `Wokwi-GUEST` default |
| MQTT broker | Local IP (`192.168.x.x`) | Public broker required |
| Device ID | `esp32_relay_01` | `wokwi_relay_01` |
| Visual feedback | Real relay module | LED indicators |
| OTA update | Fully functional |Structurally preserved |

## 💡 Tips

1. **Public MQTT Broker:** Deploy Mosquitto di cloud (DigitalOcean, AWS, dll) atau gunakan HiveMQ Cloud free tier
2. **Multiple Devices:** Clone project, ubah `DEVICE_ID` untuk simulasi multi-device
3. **Debugging:** Serial monitor adalah teman terbaik — semua event ter-log disana
4. **State Persistence:** Relay state tersimpan di NVS, bertahan antar restart simulasi

---

**Dibuat untuk ElBot Home Asisten Project**  
Version: Wokwi Simulation  
Last Updated: 2026-06-22
