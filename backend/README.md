<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0F172A,100:6366F1&height=220&section=header&text=ElBot%20Home%20Asisten&fontSize=46&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Asisten%20Rumah%20Pintar%20Berbahasa%20Indonesia%20dengan%20Voice%20Chat%20AI&descAlignY=58&descAlign=50" width="100%"/>

<a href="#-quick-start">
  <img src="https://readme-typing-svg.demolab.com/?lines=Kontrol+perangkat+IoT+cukup+dengan+berbicara...;Tanpa+tombol%2C+tanpa+ribet.;%22Bot%2C+nyalakan+lampu+ruang+tamu%22;Latensi+kurang+dari+2+detik+%E2%9A%A1&font=Fira+Code&center=true&width=600&height=45&color=818CF8&vCenter=true&size=20&pause=1800" alt="Typing SVG" />
</a>

<br/>

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![ESP32](https://img.shields.io/badge/ESP32-Arduino-E7352C?style=for-the-badge&logo=espressif&logoColor=white)](https://www.espressif.com)
[![MQTT](https://img.shields.io/badge/MQTT-Mosquitto-660066?style=for-the-badge&logo=eclipsemosquitto&logoColor=white)](https://mosquitto.org)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)

<img src="https://img.shields.io/github/last-commit/your-username/home-asisten?style=flat-square&color=6366F1&label=last%20update" />
<img src="https://img.shields.io/badge/status-active%20development-success?style=flat-square" />
<img src="https://img.shields.io/badge/made%20with-%E2%9D%A4%EF%B8%8F%20in%20Indonesia-red?style=flat-square" />

</div>

<br/>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## ✨ Fitur Utama

<table>
<tr>
<td width="50%" valign="top">

### 🎙️ Voice Chat Realtime
Bicara langsung ke ElBot — AI memahami perintah Bahasa Indonesia dan merespons dengan suara, tanpa jeda canggung.

### 🤖 AI Agent Cerdas
Menggunakan OpenAI-compatible API dengan *function calling* — ElBot benar-benar **mengeksekusi** perintah, bukan sekadar menjawab teks.

### ⚡ Device-First Execution
Perintah dieksekusi ke perangkat **sebelum** AI selesai menyusun kalimat balasan. Target latensi **< 2 detik**.

### 💡 Kontrol ESP32 via MQTT
Kendalikan relay 4-channel di ESP32 melalui protokol MQTT yang ringan dan reliable.

</td>
<td width="50%" valign="top">

### 🔄 OTA Firmware Update
Upload firmware `.bin` dari web → dikirim via MQTT → ESP32 auto-update tanpa kabel sama sekali.

### 🎨 Dark Mode UI
Tampilan modern bergaya OLED dengan animasi halus dan responsif di semua ukuran layar.

### 🔒 Session Auth
Proteksi akses dengan login password sederhana berbasis bcrypt.

### 📊 Device Dashboard
Pantau status semua perangkat secara realtime di panel cepat, lengkap dengan RSSI & uptime.

</td>
</tr>
</table>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 🏗️ Arsitektur Sistem

```mermaid
flowchart TB
    subgraph Client["🌐 WEB BROWSER"]
        UI["ElBot Home Asisten UI<br/>Voice Chat • Device Panel • Settings"]
    end

    subgraph Backend["⚙️ BACKEND — FastAPI"]
        direction LR
        Voice["🎙️ Voice Pipeline<br/>Google STT • Edge TTS<br/>Socket.IO"]
        Agent["🤖 AI Agent<br/>OpenAI Compat<br/>Function Calling"]
        Manager["📦 Device Manager<br/>CRUD SQLite<br/>OTA Chunking"]
    end

    MQTTSvc["📨 MQTT Service — paho-mqtt<br/>Publish cmd • Subscribe status"]
    Broker["📡 MQTT BROKER — Mosquitto"]

    ESP1["📟 ESP32 #1<br/>Relay 4ch + OTA"]
    ESP2["📟 ESP32 #2<br/>Relay 4ch + OTA"]
    ESPN["📟 ESP32 #N<br/>..."]

    Client <-->|Socket.IO + REST API| Backend
    Voice --- Agent --- Manager
    Backend --> MQTTSvc
    MQTTSvc <-->|MQTT Protocol| Broker
    Broker <--> ESP1
    Broker <--> ESP2
    Broker <--> ESPN

    style Client fill:#1e1b4b,stroke:#818cf8,color:#fff
    style Backend fill:#0f172a,stroke:#6366f1,color:#fff
    style MQTTSvc fill:#312e81,stroke:#818cf8,color:#fff
    style Broker fill:#3730a3,stroke:#818cf8,color:#fff
    style ESP1 fill:#1e293b,stroke:#e7352c,color:#fff
    style ESP2 fill:#1e293b,stroke:#e7352c,color:#fff
    style ESPN fill:#1e293b,stroke:#e7352c,color:#fff
```

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 🎯 Cara Kerja Voice Chat

```mermaid
sequenceDiagram
    participant U as 🧑 User
    participant B as 🌐 Browser
    participant S as ⚙️ Backend
    participant A as 🤖 AI Agent
    participant M as 📡 MQTT
    participant E as 📟 ESP32

    U->>B: Bicara ("nyalakan lampu")
    B->>S: Kirim audio (base64, WebM)
    S->>S: Google STT → transcript
    S->>A: Proses perintah
    A-->>M: Tool call terdeteksi → publish cmd
    M-->>E: Eksekusi relay
    E-->>M: Status ON
    A-->>S: Stream teks balasan (per-klausa)
    S-->>B: Edge TTS audio chunk
    B-->>U: 🔊 "Siap, lampu sudah menyala!"

    Note over A,E: Device-First Execution — relay menyala<br/>sebelum AI selesai bicara
```

**AI Tools yang tersedia:**

| Tool | Fungsi |
|:-----|:-------|
| `control_device` | Nyalakan / matikan / toggle perangkat |
| `get_device_status` | Cek status perangkat saat ini |
| `list_devices` | Lihat semua perangkat terdaftar |

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 🛠️ Tech Stack

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![SocketIO](https://img.shields.io/badge/Socket.IO-010101?style=for-the-badge&logo=socket.io&logoColor=white)
![MQTT](https://img.shields.io/badge/MQTT-660066?style=for-the-badge&logo=eclipsemosquitto&logoColor=white)
![ESP32](https://img.shields.io/badge/ESP32-E7352C?style=for-the-badge&logo=espressif&logoColor=white)
![Arduino](https://img.shields.io/badge/Arduino-00979D?style=for-the-badge&logo=arduino&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI%20Compatible-412991?style=for-the-badge&logo=openai&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/TailwindCSS-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)

</div>

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

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 🚀 Quick Start

### Prasyarat

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)
![Mosquitto](https://img.shields.io/badge/Mosquitto-Required-660066?style=flat-square)
![ffmpeg](https://img.shields.io/badge/ffmpeg-Required-007808?style=flat-square)
![ESP32](https://img.shields.io/badge/ESP32-Optional-lightgrey?style=flat-square)

### 1️⃣ Clone & Setup

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

### 2️⃣ Konfigurasi

```bash
cp .env.example .env
# Edit .env dengan konfigurasi kamu
```

<details>
<summary><b>📋 Klik untuk lihat variabel environment penting</b></summary>

<br/>

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

</details>

### 3️⃣ Jalankan MQTT Broker

```bash
# Install Mosquitto (jika belum)
sudo apt install mosquitto mosquitto-clients

# Start broker
mosquitto -v
```

### 4️⃣ Jalankan Backend

```bash
cd backend
source venv/bin/activate

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

> 🌐 Server berjalan di **http://localhost:8000**

### 5️⃣ Flash ESP32 *(opsional)*

1. Buka `firmware/esp32_relay/esp32_relay.ino` di Arduino IDE
2. Sesuaikan konfigurasi WiFi dan MQTT di bagian atas file
3. Upload ke ESP32 via USB
4. ESP32 akan otomatis connect ke broker dan subscribe topic

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 📁 Struktur Proyek

<details>
<summary><b>📂 Klik untuk membuka struktur folder lengkap</b></summary>

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

</details>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 📡 MQTT Topic Convention

| Topic | Arah | Deskripsi |
|:------|:----:|:----------|
| `elbot/{device_id}/cmd` | Backend ➡️ ESP32 | Perintah kontrol relay |
| `elbot/{device_id}/status` | ESP32 ➡️ Backend | Status relay + heartbeat |
| `elbot/{device_id}/lwt` | ESP32 ➡️ Broker | Last Will (online/offline) |
| `elbot/{device_id}/ota/data` | Backend ➡️ ESP32 | Chunk firmware (base64) |
| `elbot/{device_id}/ota/status` | ESP32 ➡️ Backend | Progress OTA update |

<details>
<summary><b>📦 Contoh Payload</b></summary>

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

</details>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 🔌 REST API Endpoints

| Method | Endpoint | Deskripsi |
|:------:|:---------|:----------|
| ![POST](https://img.shields.io/badge/POST-49cc90?style=flat-square) | `/api/auth/login` | Login dengan password |
| ![GET](https://img.shields.io/badge/GET-61affe?style=flat-square) | `/api/devices` | Daftar semua perangkat |
| ![POST](https://img.shields.io/badge/POST-49cc90?style=flat-square) | `/api/devices` | Tambah perangkat baru |
| ![GET](https://img.shields.io/badge/GET-61affe?style=flat-square) | `/api/devices/{id}` | Detail perangkat |
| ![PUT](https://img.shields.io/badge/PUT-fca130?style=flat-square) | `/api/devices/{id}` | Update perangkat |
| ![DELETE](https://img.shields.io/badge/DELETE-f93e3e?style=flat-square) | `/api/devices/{id}` | Hapus perangkat |
| ![POST](https://img.shields.io/badge/POST-49cc90?style=flat-square) | `/api/devices/{id}/control` | Kontrol relay (ON/OFF/TOGGLE) |
| ![POST](https://img.shields.io/badge/POST-49cc90?style=flat-square) | `/api/devices/{id}/firmware` | Upload firmware OTA |
| ![GET](https://img.shields.io/badge/GET-61affe?style=flat-square) | `/api/hello` | API info |
| ![GET](https://img.shields.io/badge/GET-61affe?style=flat-square) | `/health` | Health check + MQTT status |

> 🔒 Semua endpoint `/api/devices/*` dilindungi oleh session authentication.

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## ⚡ Optimasi Latensi

<div align="center">

### Target: **&lt; 2 detik** dari user selesai bicara → device menyala + ElBot mulai bicara

</div>

| Strategi | Penjelasan |
|:---------|:-----------|
| 🚀 **Device-First Execution** | Tool call dieksekusi segera saat terdeteksi di stream, tanpa menunggu AI selesai |
| 🔊 **Clause-by-Clause TTS** | Audio mulai diputar per-klausa, tidak menunggu seluruh kalimat |
| 🔗 **Persistent MQTT** | Koneksi tetap terbuka, tidak ada overhead connect/disconnect |
| ⚙️ **Async Throughout** | Semua operasi I/O non-blocking |

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 🔧 ESP32 Firmware

### Wiring Relay 4-Channel

| Relay | GPIO | Fungsi |
|:-----:|:----:|:-------|
| Relay 1 | `GPIO 26` | Channel 1 |
| Relay 2 | `GPIO 25` | Channel 2 |
| Relay 3 | `GPIO 33` | Channel 3 |
| Relay 4 | `GPIO 32` | Channel 4 |

> ⚠️ Relay bersifat **active LOW** — `LOW` = ON, `HIGH` = OFF

### Fitur Firmware

- ✅ Auto-connect WiFi + MQTT saat boot
- ✅ Subscribe ke topic command, eksekusi relay
- ✅ Publish status periodik (heartbeat)
- ✅ Last Will Testament (LWT) untuk deteksi offline
- ✅ OTA update via MQTT (chunked base64, 4KB per chunk)
- ✅ State persistence via Preferences (NVS)

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 🎨 UI Preview

<table>
<tr>
<td width="50%" valign="top">

### 💬 Halaman Chat
- Bubble chat real-time dengan ElBot
- Panel cepat status perangkat (toggle langsung)
- Tombol mikrofon + indikator visual (listening/thinking/speaking)
- Input teks alternatif

</td>
<td width="50%" valign="top">

### ⚙️ Halaman Settings
- **Tab Perangkat** — CRUD device, toggle manual ON/OFF
- **Tab Firmware** — Upload `.bin` dengan progress bar
- **Tab Umum** — Konfigurasi sistem

</td>
</tr>
</table>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 📦 Dependencies

<details>
<summary><b>🐍 Backend (Python)</b></summary>

<br/>

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

</details>

<details>
<summary><b>📟 Firmware (ESP32)</b></summary>

<br/>

| Library | Kegunaan |
|:--------|:---------|
| WiFi.h | Koneksi WiFi |
| PubSubClient | MQTT client |
| ArduinoJson | Parse JSON payload |
| Update.h | OTA firmware flashing |
| Preferences.h | State persistence (NVS) |

</details>

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 🐛 Troubleshooting

| Masalah | Solusi |
|:--------|:-------|
| ❌ MQTT connection refused | Pastikan Mosquitto berjalan: `mosquitto -v` |
| ❌ STT tidak mengenali suara | Cek ffmpeg terinstall: `ffmpeg -version` |
| ❌ ESP32 tidak connect | Periksa SSID/password WiFi di firmware |
| ❌ Audio TTS tidak keluar | Pastikan browser mengizinkan autoplay audio |
| ❌ Login gagal | Regenerate password hash: `python -c "from passlib.context import CryptContext; print(CryptContext(['bcrypt']).hash('password'))"` |

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6366F1,100:0F172A&height=2&width=100%25" width="100%"/>

## 📝 License

Proyek ini menggunakan **MIT License** — bebas digunakan dan dimodifikasi.

<br/>

<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:6366F1,100:0F172A&height=150&section=footer"/>

*ElBot — Asisten rumah pintar yang selalu siap membantu.*

</div>