<div align="center">

```
  ███████╗██╗     ██████╗  ██████╗ ████████╗
  ██╔════╝██║     ██╔══██╗██╔═══██╗╚══██╔══╝
  █████╗  ██║     ██████╔╝██║   ██║   ██║
  ██╔══╝  ██║     ██╔══██╗██║   ██║   ██║
  ███████╗███████╗██████╔╝╚██████╔╝   ██║
  ╚══════╝╚══════╝╚═════╝  ╚═════╝    ╚═╝
```

# ElBot Home Asisten

### Asisten Rumah Pintar Berbahasa Indonesia dengan Voice Chat AI

*Kontrol perangkat IoT cukup dengan berbicara — tanpa tombol, tanpa ribet.*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![ESP32](https://img.shields.io/badge/ESP32-Arduino-E7352C?logo=espressif&logoColor=white)](https://www.espressif.com)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?logo=eclipsemosquitto&logoColor=white)](https://mosquitto.org)
[![Socket.IO](https://img.shields.io/badge/Socket.IO-5.12-010101?logo=socket.io&logoColor=white)](https://socket.io)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

---

</div>

## ✨ Fitur Utama

| Fitur | Deskripsi |
|:------|:----------|
| 🎙️ **Voice Chat Realtime** | Bicara langsung ke ElBot — AI memahami perintah Bahasa Indonesia dan merespons dengan suara |
| 🤖 **AI Agent Cerdas** | Menggunakan OpenAI-compatible API dengan *function calling* — ElBot benar-benar mengeksekusi perintah, bukan hanya menjawab teks |
| ⚡ **Device-First Execution** | Perintah dieksekusi ke perangkat *sebelum* AI selesai menyusun kalimat balasan — latensi < 2 detik |
| 💡 **Kontrol ESP32 via MQTT** | Kendalikan relay 4-channel di ESP32 melalui protokol MQTT yang ringan dan reliable |
| 🔄 **OTA Firmware Update** | Upload firmware `.bin` dari web → dikirim via MQTT → ESP32 auto-update tanpa kabel |
| 🎨 **Dark Mode UI** | Tampilan modern bergaya OLED dengan animasi halus dan responsif |
| 🔒 **Session Auth** | Proteksi akses dengan login password sederhana |
| 📊 **Device Dashboard** | Pantau status semua perangkat secara realtime di panel cepat |

---

## 🏗️ Arsitektur Sistem

```
┌──────────────────────────────────────────────────────────┐
│                     🌐 WEB BROWSER                        │
│              ElBot Home Asisten UI                        │
│         Voice Chat  •  Device Panel  •  Settings          │
└──────────────────────┬───────────────────────────────────┘
                       │ Socket.IO + REST API
                       ▼
┌──────────────────────────────────────────────────────────┐
│                   ⚙️  BACKEND (FastAPI)                    │
│                                                           │
│  ┌─────────────┐  ┌──────────┐  ┌───────────────────┐   │
│  │ Voice       │  │ AI Agent │  │ Device Manager    │   │
│  │ Pipeline    │  │          │  │                   │   │
│  │ • Google STT│  │ • OpenAI │  │ • CRUD (SQLite)   │   │
│  │ • Edge TTS  │  │   Compat │  │ • MQTT Publish    │   │
│  │ • Socket.IO │  │ • Tools  │  │ • OTA Chunking    │   │
│  └─────────────┘  └──────────┘  └───────────────────┘   │
│                                                           │
│  ┌─────────────────────────────────────────────────┐     │
│  │              MQTT Service (paho-mqtt)             │     │
│  │         Publish cmd  •  Subscribe status          │     │
│  └─────────────────────────────────────────────────┘     │
└──────────────────────┬───────────────────────────────────┘
                       │ MQTT Protocol
                       ▼
┌──────────────────────────────────────────────────────────┐
│                  📡 MQTT BROKER (Mosquitto)                │
└──────────────────────┬───────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
   │   ESP32 #1  │ │   ESP32 #2  │ │   ESP32 #N  │
   │ 🔌 Relay 4ch│ │ 🔌 Relay 4ch│ │     ...     │
   │ OTA Support │ │ OTA Support │ │             │
   └─────────────┘ └─────────────┘ └─────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Teknologi |
|:------|:----------|
| **Backend** | Python 3.11+, FastAPI, SQLAlchemy (async), aiosqlite |
| **Realtime** | python-socketio, Socket.IO client |
| **Voice — STT** | Google Speech API v2 + ffmpeg (WebM → FLAC) |
| **Voice — TTS** | Edge TTS (`id-ID-GadisNeural`) |
| **AI Agent** | OpenAI-compatible API, streaming + function calling |
| **IoT Protocol** | MQTT (paho-mqtt + Eclipse Mosquitto) |
| **Database** | SQLite (via aiosqlite, zero-config) |
| **Frontend** | HTML + TailwindCSS + Lucide Icons + Vanilla JS |
| **Firmware** | ESP32 Arduino, PubSubClient, Update.h (OTA) |

---

## 🚀 Quick Start

### Prasyarat

- **Python** 3.11+
- **Mosquitto** MQTT Broker
- **ffmpeg** (untuk konversi audio)
- **ESP32** dengan relay module (opsional, bisa test tanpa hardware)

### 1. Clone & Setup

```bash
git clone <repository-url>
cd home-asisten

# Buat virtual environment
cd backend
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Konfigurasi

```bash
cp .env.example .env
# Edit .env dengan konfigurasi kamu
```

Variabel penting di `.env`:

| Variabel | Deskripsi | Default |
|:---------|:----------|:--------|
| `APP_PASSWORD_HASH` | Hash bcrypt untuk login | *(generate dengan bcrypt)* |
| `SECRET_KEY` | Secret key untuk session | *(random string)* |
| `MQTT_BROKER_HOST` | Alamat MQTT broker | `localhost` |
| `MQTT_BROKER_PORT` | Port MQTT broker | `1883` |
| `AI_API_BASE_URL` | Base URL OpenAI-compatible API | *(required)* |
| `AI_API_KEY` | API key untuk AI | *(required)* |
| `AI_MODEL_NAME` | Nama model AI | *(required)* |
| `GOOGLE_STT_KEY` | Google Speech API key | *(required)* |

### 3. Jalankan MQTT Broker

```bash
# Install Mosquitto (jika belum)
sudo apt install mosquitto mosquitto-clients

# Start broker
mosquitto -v
```

### 4. Jalankan Backend

```bash
cd backend
source venv/bin/activate

# Jalankan server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server berjalan di **http://localhost:8000**

### 5. Flash ESP32 (Opsional)

1. Buka `firmware/esp32_relay/esp32_relay.ino` di Arduino IDE
2. Sesuaikan konfigurasi WiFi dan MQTT di bagian atas file
3. Upload ke ESP32 via USB
4. ESP32 akan otomatis connect ke broker dan subscribe topic

---

## 📁 Struktur Proyek

```
home-asisten/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI entry point + Socket.IO wrapper
│   │   ├── config.py               # Pydantic settings dari .env
│   │   ├── auth.py                 # Session-based authentication
│   │   ├── core/
│   │   │   ├── ai_agent.py         # AI orchestrator + streaming + tool calls
│   │   │   ├── stt_service.py      # Google Speech-to-Text
│   │   │   ├── tts_service.py      # Edge Text-to-Speech
│   │   │   └── mqtt_service.py     # MQTT client async wrapper
│   │   ├── chat/
│   │   │   ├── router.py           # Socket.IO event handlers (STT→AI→TTS)
│   │   │   ├── tools.py            # AI tool definitions + system prompt
│   │   │   └── models.py           # Session-only chat models
│   │   ├── devices/
│   │   │   ├── router.py           # REST API device CRUD + control
│   │   │   ├── crud.py             # Async database operations
│   │   │   ├── models.py           # SQLAlchemy models
│   │   │   └── schemas.py          # Pydantic request/response schemas
│   │   ├── db/
│   │   │   ├── database.py         # Async SQLite engine + sessions
│   │   │   └── init_db.py          # Database initialization
│   │   └── ws/
│   │       └── connection_manager.py
│   ├── .env                        # Environment configuration
│   ├── requirements.txt            # Python dependencies
│   └── run.sh                      # Convenience startup script
│
├── frontend/
│   ├── index.html                  # Halaman utama — Voice Chat
│   ├── settings.html               # Pengaturan — Device & Firmware
│   ├── login.html                  # Halaman login
│   └── static/
│       ├── css/styles.css          # Custom animations & theming
│       └── js/
│           ├── app.js              # Chat logic + Socket.IO + mic
│           └── settings.js         # Device CRUD + firmware upload
│
├── firmware/
│   └── esp32_relay/
│       ├── esp32_relay.ino         # Main firmware — WiFi + MQTT + relay
│       └── ota_handler.h           # OTA update via MQTT chunks
│
└── plan-home-asisten.md            # Blueprint proyek lengkap
```

---

## 📡 MQTT Topic Convention

| Topic | Arah | Deskripsi |
|:------|:-----|:----------|
| `elbot/{device_id}/cmd` | Backend → ESP32 | Perintah kontrol relay |
| `elbot/{device_id}/status` | ESP32 → Backend | Status relay + heartbeat |
| `elbot/{device_id}/lwt` | ESP32 → Broker | Last Will (online/offline) |
| `elbot/{device_id}/ota/data` | Backend → ESP32 | Chunk firmware (base64) |
| `elbot/{device_id}/ota/status` | ESP32 → Backend | Progress OTA update |

### Contoh Payload

**Command** (Backend → ESP32):
```json
{
  "action": "set_state",
  "target": "relay_1",
  "value": "ON"
}
```

**Status** (ESP32 → Backend):
```json
{
  "device_id": "esp32-ruangtamu",
  "relay_1": "ON",
  "relay_2": "OFF",
  "relay_3": "OFF",
  "relay_4": "OFF",
  "rssi": -55,
  "uptime": 13452
}
```

---

## 🔌 REST API Endpoints

| Method | Endpoint | Deskripsi |
|:-------|:---------|:----------|
| `POST` | `/api/auth/login` | Login dengan password |
| `GET` | `/api/devices` | Daftar semua perangkat |
| `POST` | `/api/devices` | Tambah perangkat baru |
| `GET` | `/api/devices/{id}` | Detail perangkat |
| `PUT` | `/api/devices/{id}` | Update perangkat |
| `DELETE` | `/api/devices/{id}` | Hapus perangkat |
| `POST` | `/api/devices/{id}/control` | Kontrol relay (ON/OFF/TOGGLE) |
| `POST` | `/api/devices/{id}/firmware` | Upload firmware OTA |
| `GET` | `/api/hello` | API info |
| `GET` | `/health` | Health check + MQTT status |

> Semua endpoint `/api/devices/*` dilindungi oleh session authentication.

---

## 🎯 Cara Kerja Voice Chat

```
User bicara → Browser rekam (WebM)
                ↓
        Socket.IO kirim base64 audio
                ↓
        Backend: Google STT (WebM → FLAC → transcript)
                ↓
        AI Agent: proses perintah + function calling
                ↓
    ┌───────────┴───────────┐
    ↓                       ↓
 Tool call detected     Stream teks balasan
    ↓                       ↓
 MQTT publish           Edge TTS (per-klausa)
 ke ESP32                   ↓
    ↓                   Audio chunk → Browser
 Device nyala!          ElBot bicara!
```

**AI Tools yang tersedia:**
- `control_device` — Nyalakan/matikan/toggle perangkat
- `get_device_status` — Cek status perangkat
- `list_devices` — Lihat semua perangkat terdaftar

---

## ⚡ Optimasi Latensi

Target: **< 2 detik** dari user selesai bicara → device menyala + ElBot mulai bicara.

Strategi:
1. **Device-First Execution** — Tool call dieksekusi segera saat terdeteksi di stream, tanpa menunggu AI selesai
2. **Clause-by-Clause TTS** — Audio mulai diputar per-klausa, tidak menunggu seluruh kalimat
3. **Persistent MQTT** — Koneksi tetap terbuka, tidak ada overhead connect/disconnect
4. **Async Throughout** — Semua operasi I/O non-blocking

---

## 🔧 ESP32 Firmware

### Wiring Relay 4-Channel

| Relay | GPIO | Fungsi |
|:------|:-----|:-------|
| Relay 1 | GPIO 26 | Channel 1 |
| Relay 2 | GPIO 25 | Channel 2 |
| Relay 3 | GPIO 33 | Channel 3 |
| Relay 4 | GPIO 32 | Channel 4 |

> Relay bersifat **active LOW** — `LOW` = ON, `HIGH` = OFF

### Fitur Firmware

- Auto-connect WiFi + MQTT saat boot
- Subscribe ke topic command, eksekusi relay
- Publish status periodik (heartbeat)
- Last Will Testament (LWT) untuk deteksi offline
- OTA update via MQTT (chunked base64, 4KB per chunk)
- State persistence via Preferences (NVS)

---

## 🎨 UI Preview

### Halaman Chat
- Bubble chat real-time dengan ElBot
- Panel cepat status perangkat (toggle langsung)
- Tombol mikrofon + indikator visual (listening/thinking/speaking)
- Input teks alternatif

### Halaman Settings
- **Tab Perangkat** — CRUD device, toggle manual ON/OFF
- **Tab Firmware** — Upload `.bin` dengan progress bar
- **Tab Umum** — Konfigurasi sistem

---

## 📦 Dependencies

### Backend (Python)

| Package | Versi | Kegunaan |
|:--------|:------|:---------|
| fastapi | 0.115.0 | Web framework |
| uvicorn | 0.32.0 | ASGI server |
| sqlalchemy | 2.0.36 | ORM (async) |
| aiosqlite | 0.20.0 | Async SQLite driver |
| python-socketio | 5.12.1 | Realtime Socket.IO server |
| paho-mqtt | 2.1.0 | MQTT client |
| edge-tts | 6.1.14 | Free TTS (Indonesian) |
| openai | 1.68.0 | OpenAI-compatible SDK |
| passlib | 1.7.4 | Password hashing (bcrypt) |

### Firmware (ESP32)

| Library | Kegunaan |
|:--------|:---------|
| WiFi.h | Koneksi WiFi |
| PubSubClient | MQTT client |
| ArduinoJson | Parse JSON payload |
| Update.h | OTA firmware flashing |
| Preferences.h | State persistence (NVS) |

---

## 🐛 Troubleshooting

| Masalah | Solusi |
|:--------|:-------|
| MQTT connection refused | Pastikan Mosquitto berjalan: `mosquitto -v` |
| STT tidak mengenali suara | Cek ffmpeg terinstall: `ffmpeg -version` |
| ESP32 tidak connect | Periksa SSID/password WiFi di firmware |
| Audio TTS tidak keluar | Pastikan browser mengizinkan autoplay audio |
| Login gagal | Regenerate password hash: `python -c "from passlib.context import CryptContext; print(CryptContext(['bcrypt']).hash('password'))"` |

---

## 📝 License

MIT License — bebas digunakan dan dimodifikasi.

---

<div align="center">

**Dibuat dengan ❤️ untuk Smart Home Indonesia**

*ElBot — Asisten rumah pintar yang selalu siap membantu.*

</div>