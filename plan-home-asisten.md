# PLAN.md — ElBot Home Asisten

> Web Voice Chat Realtime Bahasa Indonesia untuk Home Automation berbasis AI Agent + ESP32 (MQTT)

---

## 1. Ringkasan Proyek

**ElBot Home Asisten** adalah aplikasi web berbasis Python yang memungkinkan pengguna mengontrol perangkat IoT (lampu, relay, perangkat lain) melalui **ngobrol suara realtime berbahasa Indonesia**. AI Agent bertindak sebagai "otak" yang memahami perintah, menentukan aksi, lalu mengirim perintah ke perangkat **ESP32** melalui **MQTT**. Web UI juga menyediakan fitur manajemen perangkat dan **OTA firmware update** ke ESP32 lewat MQTT.

### Identitas AI
- Nama: **ElBot**
- AI di-*system-prompt* (fine-tuned secara prompt-level) agar selalu menjawab sebagai "ElBot", asisten rumah pintar berbahasa Indonesia, ramah, ringkas, dan to-the-point saat mengeksekusi perintah perangkat.

### Fitur Utama
1. Voice chat realtime (STT Google) berbahasa Indonesia → AI Agent (custom OpenAI-compatible API) → TTS → balasan suara.
2. AI Agent dengan **function calling / tool use** untuk mengontrol perangkat (nyalakan/matikan lampu, relay, dsb).
3. Komunikasi ke ESP32 via **MQTT** (broker Mosquitto).
4. Web UI menarik bernama **"Elbot Home Asisten"**, mendukung obrolan teks + suara.
5. **Manajemen perangkat** lewat Web UI (tambah/edit/hapus device, mapping topic MQTT, jenis device, ruangan).
6. **OTA Firmware Update**: upload file `.bin` lewat Web UI → dikirim ke ESP32 lewat MQTT (chunked) → ESP32 menulis ke flash via `Update.h`.
7. Riwayat obrolan & log aksi perangkat tersimpan di **SQLite**.

---

## 2. Arsitektur Sistem

```
                         ┌─────────────────────────────┐
                         │        WEB BROWSER          │
                         │  (Elbot Home Asisten UI)    │
                         │  - Voice chat (mic)         │
                         │  - Chat text                │
                         │  - Device management        │
                         │  - Firmware upload          │
                         └──────────────┬───────────────┘
                                        │ WebSocket + REST (HTTPS)
                                        ▼
                         ┌─────────────────────────────┐
                         │        BACKEND (Python)     │
                         │        FastAPI Server       │
                         │  ┌─────────────────────────┐│
                         │  │ Voice Pipeline           ││
                         │  │ - Google STT (id-ID)     ││
                         │  │ - Google/Cloud TTS (id)  ││
                         │  ├─────────────────────────┤│
                         │  │ AI Agent Orchestrator    ││
                         │  │ - Custom OpenAI-compat   ││
                         │  │   API client             ││
                         │  │ - System prompt "ElBot"  ││
                         │  │ - Function/tool calling  ││
                         │  ├─────────────────────────┤│
                         │  │ Device Manager           ││
                         │  │ - CRUD device (SQLite)   ││
                         │  ├─────────────────────────┤│
                         │  │ MQTT Service             ││
                         │  │ - Publish command        ││
                         │  │ - Subscribe state/status ││
                         │  ├─────────────────────────┤│
                         │  │ OTA Firmware Service     ││
                         │  │ - Upload .bin             ││
                         │  │ - Chunk & publish via MQTT││
                         │  └─────────────────────────┘│
                         │        SQLite DB             │
                         └──────────────┬───────────────┘
                                        │ MQTT (pub/sub)
                                        ▼
                         ┌─────────────────────────────┐
                         │      MQTT BROKER             │
                         │      (Mosquitto)             │
                         └──────────────┬───────────────┘
                                        │
                ┌───────────────────────┼───────────────────────┐
                ▼                       ▼                       ▼
        ┌───────────────┐      ┌───────────────┐       ┌───────────────┐
        │   ESP32 #1     │      │   ESP32 #2     │       │   ESP32 #N     │
        │ Relay Lampu    │      │ Relay Lainnya  │       │  ...           │
        │ - Sub: cmd     │      │ - Sub: cmd     │       │                │
        │ - Pub: status  │      │ - Pub: status  │       │                │
        │ - OTA Update.h │      │ - OTA Update.h │       │                │
        └───────────────┘      └───────────────┘       └───────────────┘
```

---

## 3. Tech Stack

| Komponen | Teknologi |
|---|---|
| Backend framework | **Python 3.11+, FastAPI** (async, native WebSocket support) |
| Realtime komunikasi web | **WebSocket** (audio stream + chat events) |
| Speech-to-Text | **Google Cloud Speech-to-Text** (`id-ID`), streaming recognition |
| Text-to-Speech | **Google Cloud Text-to-Speech** (`id-ID`, voice Wavenet/Neural2) |
| AI Agent | **Custom OpenAI-compatible API** (via `openai` python SDK, `base_url` di-custom) |
| Tool/Function calling | OpenAI-style `tools` schema (function calling) |
| Pesan IoT | **MQTT** — broker **Eclipse Mosquitto**, client `paho-mqtt` (async wrapper) |
| Firmware target | **ESP32 (Arduino framework)**, OTA via `Update.h` + `PubSubClient`/`AsyncMqttClient` |
| Database | **SQLite** (via `SQLAlchemy` + `aiosqlite`) |
| Web UI | **HTML + TailwindCSS + Vanilla JS / Alpine.js** (ringan, tanpa build step rumit) — atau React jika butuh interaktivitas lebih |
| Realtime UI update | WebSocket (status device, chat stream) |
| Auth (opsional, disarankan) | Simple session/JWT-based login |

---

## 4. Struktur Folder Proyek

```
elbot-home-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                  # Entry point FastAPI
│   │   ├── config.py                # Load .env (API key, MQTT broker, dll)
│   │   ├── core/
│   │   │   ├── ai_agent.py          # Orchestrator: prompt ElBot + tool calling
│   │   │   ├── system_prompt.py     # System prompt identitas ElBot
│   │   │   ├── stt_service.py       # Google STT streaming
│   │   │   ├── tts_service.py       # Google TTS
│   │   │   └── mqtt_service.py      # Publish/subscribe MQTT, async
│   │   ├── ota/
│   │   │   ├── ota_service.py       # Upload .bin, chunking, publish OTA via MQTT
│   │   │   └── firmware_store/      # Folder simpan file .bin yang diupload
│   │   ├── devices/
│   │   │   ├── models.py            # SQLAlchemy model: Device, Room, ActionLog
│   │   │   ├── schemas.py           # Pydantic schema request/response
│   │   │   ├── crud.py              # CRUD device
│   │   │   └── router.py            # REST endpoint device management
│   │   ├── chat/
│   │   │   ├── models.py            # Model riwayat chat
│   │   │   ├── router.py            # WebSocket endpoint voice/text chat
│   │   │   └── tools.py             # Definisi tools (function schema) untuk AI Agent
│   │   ├── db/
│   │   │   ├── database.py          # SQLite engine & session
│   │   │   └── init_db.py
│   │   └── ws/
│   │       └── connection_manager.py
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── index.html                   # Halaman utama "Elbot Home Asisten" (chat)
│   ├── settings.html                # Halaman Pengaturan (tab: Perangkat, Firmware OTA, Umum)
│   ├── static/
│   │   ├── css/style.css
│   │   ├── js/
│   │   │   ├── voice-chat.js        # Rekam mic, kirim audio via WS, mainkan TTS
│   │   │   ├── chat-ui.js           # Render bubble chat
│   │   │   ├── device-manager.js    # CRUD UI device (dipakai di tab Pengaturan)
│   │   │   └── firmware-upload.js   # Upload progress, kirim ke backend (dipakai di tab Pengaturan)
│   │   └── img/logo-elbot.svg
│   └── components/                  # (jika pakai templating/partials)
│
├── firmware/
│   ├── esp32_relay/
│   │   ├── esp32_relay.ino          # Firmware dasar: subscribe cmd, kontrol relay
│   │   ├── ota_handler.h            # Handler OTA terima chunk via MQTT, tulis ke flash
│   │   └── mqtt_config.h
│   └── README.md                    # Cara flashing awal & wiring relay
│
├── docs/
│   ├── mqtt-topics.md                # Daftar topic & payload format
│   ├── api-endpoints.md              # Dokumentasi REST & WS API
│   └── architecture.png
│
├── docker-compose.yml                # Mosquitto + backend (opsional, untuk deploy gampang)
├── .gitignore
└── README.md
```

---

## 5. Desain MQTT (Topic & Payload)

### Konvensi Topic
```
elbot/<device_id>/cmd          # Backend → ESP32 (perintah aksi)
elbot/<device_id>/status       # ESP32 → Backend (status realtime/heartbeat)
elbot/<device_id>/ota/data     # Backend → ESP32 (kirim chunk firmware)
elbot/<device_id>/ota/status   # ESP32 → Backend (progress/hasil OTA)
elbot/<device_id>/lwt          # Last Will Testament (online/offline)
```

### Contoh Payload `cmd` (Backend → ESP32)
```json
{
  "action": "set_state",
  "target": "relay_1",
  "value": "ON"
}
```

### Contoh Payload `status` (ESP32 → Backend)
```json
{
  "device_id": "esp32-lampu-ruangtamu",
  "relay_1": "ON",
  "rssi": -55,
  "uptime": 13452
}
```

### Contoh Payload OTA (`ota/data`, dikirim per-chunk base64)
```json
{
  "firmware_id": "fw_20260621_01",
  "chunk_index": 12,
  "total_chunks": 240,
  "data": "<base64-chunk>",
  "checksum": "<md5-per-chunk-opsional>"
}
```

> **Catatan teknis OTA:** MQTT broker default punya batas payload (Mosquitto default 256MB tapi praktiknya kita pakai chunk kecil ±4–8KB per pesan agar stabil di ESP32). Setelah semua chunk diterima dan diverifikasi (md5 keseluruhan), ESP32 memanggil `Update.end()` lalu restart.

---

## 6. AI Agent — Function Calling (Tools)

AI Agent (lewat custom OpenAI-compatible API) diberi daftar **tools** agar bisa mengambil aksi nyata, bukan cuma jawab teks:

```jsonc
[
  {
    "type": "function",
    "function": {
      "name": "control_device",
      "description": "Menyalakan, mematikan, atau mengatur state sebuah perangkat IoT (lampu/relay/dll)",
      "parameters": {
        "type": "object",
        "properties": {
          "device_id": {"type": "string", "description": "ID unik perangkat"},
          "action": {"type": "string", "enum": ["ON", "OFF", "TOGGLE"]}
        },
        "required": ["device_id", "action"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "get_device_status",
      "description": "Mengecek status terkini sebuah perangkat",
      "parameters": {
        "type": "object",
        "properties": {"device_id": {"type": "string"}},
        "required": ["device_id"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "list_devices",
      "description": "Menampilkan semua perangkat yang terdaftar beserta ruangannya",
      "parameters": {"type": "object", "properties": {}}
    }
  }
]
```

### Alur Eksekusi (Optimized — Device-First)
> Urutan ini didesain ulang supaya **eksekusi device tidak menunggu** model menyusun kalimat balasan natural. Lihat detail lengkap di **Bab 13 — Optimasi Latensi (<2 Detik)**.

1. User bicara → STT streaming → teks perintah final, misal: *"ElBot, nyalain lampu ruang tamu"*.
2. Teks dikirim ke AI Agent dengan system prompt + daftar tools + konteks daftar device user, **`tool_choice` diarahkan agresif** agar model langsung memutuskan tool_call tanpa muter-muter generate teks dulu.
3. **Begitu tool_call pertama muncul di stream response model** (tidak menunggu seluruh response selesai) → backend langsung **eksekusi**: publish MQTT ke `elbot/lampu_ruang_tamu/cmd` dengan **QoS 1**.
4. **Paralel/bersamaan**, backend lanjut menerima sisa stream dari model untuk menyusun balasan natural: *"Siap, lampu ruang tamu sudah dinyalakan."*
5. Begitu kalimat balasan (atau potongan kalimat pertama) tersedia → langsung dikirim ke **TTS streaming** → audio mulai diputar di browser.
6. ESP32 publish status terbaru (`elbot/lampu_ruang_tamu/status`) → backend update UI realtime (indikator device) — ini berjalan independen, tidak menghambat suara ElBot.

**Hasil:** device fisik mulai menyala **sebelum atau bersamaan** dengan ElBot mulai mengucapkan kalimat balasan, bukan menunggu kalimat lengkap selesai disusun.

### Contoh System Prompt (ringkas, lengkapnya di `system_prompt.py`)
```
Kamu adalah ElBot, asisten rumah pintar berbahasa Indonesia.
Nama kamu SELALU ElBot — jika ditanya siapa namamu atau siapa kamu, jawab sebagai ElBot.
Tugasmu membantu pengguna mengontrol perangkat rumah (lampu, relay, dll) dan mengobrol santai.
Gunakan tools yang tersedia untuk benar-benar mengeksekusi perintah, jangan hanya berpura-pura.
Jawablah singkat, jelas, ramah, dengan gaya bahasa Indonesia sehari-hari yang sopan.
```

---

## 7. Alur Voice Chat Realtime (Always-On, Streaming, Low-Latency)

> **Mic terbuka terus-menerus** selama halaman chat aktif — bukan sesi rekam per-tekan-tombol. Koneksi WebSocket & STT streaming dibuka **sekali** saat halaman dimuat dan tetap hidup selama percakapan berlangsung, mengalir dari satu giliran bicara ke giliran berikutnya tanpa interupsi UI.

```
[Halaman dibuka] --> [Browser minta izin mic SEKALI] --> [WebSocket connect] --> [Google STT streaming session dibuka & terus berjalan]

LOOP terus-menerus selama halaman aktif:
  [Browser Mic, selalu ON] --(audio chunk PCM16, dikirim tiap ~100-250ms)-->
  [Backend WS Endpoint] --(stream)--> [Google STT STREAMING, interim_results=True]
     --(partial transcript)--> [Live caption ke UI + "intent pre-check" lokal — lihat Bab 13]
     --(final transcript, dipicu VAD/endpointing otomatis)--> [AI Agent Orchestrator, streaming=True]
        --(token stream)--> begitu tool_call lengkap terdeteksi:
             --> [MQTT publish ke ESP32, QoS 1] (paralel, tidak menunggu sisa teks)
        --(lanjut stream token kalimat balasan)--> per-klausa selesai:
             --> [Google TTS STREAMING] --(audio chunk)--> [Browser autoplay]
             --> (selama audio ElBot diputar: mic input dari browser DIABAIKAN backend, lihat catatan self-mute di bawah)
  [ESP32] --(eksekusi relay)--> --(publish status balik)--> [Backend update UI device realtime]
  --(ElBot selesai bicara)--> [Mic kembali aktif mendengarkan giliran berikutnya, otomatis, tanpa input user]
END LOOP (berhenti hanya jika user menutup halaman atau menekan tombol Mute)
```

**Catatan implementasi:**
- WebSocket **dibuka sekali per sesi** (saat halaman dimuat) dan tetap terbuka selama percakapan — bukan dibuka-tutup tiap kali user mau bicara. Ini mendukung pengalaman "ngobrol terus-menerus" tanpa friksi.
- **Tidak ada tombol untuk memulai bicara.** Trigger satu-satunya adalah **VAD/endpointing otomatis** dari STT streaming yang mendeteksi awal & akhir ucapan secara real-time.
- **Mencegah AI mendengar suaranya sendiri (self-listening loop):** saat backend sedang mengirim audio TTS ke browser ("ElBot bicara"), backend menandai state `ai_speaking=true` dan **mengabaikan/membuang** audio yang masuk dari mic pada periode tersebut (di luar `echoCancellation` browser sebagai lapisan pertama). Begitu audio TTS selesai diputar (event `ended` dari elemen audio dikirim balik via WS), state direset ke `ai_speaking=false` dan STT streaming kembali memproses input mic secara normal — semua otomatis, tanpa aksi user.
- Hindari false-trigger dari suara latar/TV/orang lain ngobrol: gunakan **noise suppression** browser (`noiseSuppression: true`) dan pertimbangkan threshold confidence STT minimum sebelum transcript final dikirim ke AI Agent (lihat juga opsi wake-word di catatan bawah).
- Semua tahap (STT, AI Agent, TTS) wajib pakai **streaming API**, bukan request-response biasa — kontributor terbesar pengurangan latensi sekaligus prasyarat agar pengalaman always-on terasa natural.
- **Opsional (pertimbangan masa depan, bukan wajib di versi awal):** wake-word detection (mis. "Hai ElBot" / "Oke ElBot") sebagai gerbang sebelum transcript dikirim ke AI Agent, untuk mengurangi risiko ElBot bereaksi terhadap obrolan yang tidak ditujukan padanya. Ini trade-off vs kecepatan (menambah sedikit kompleksitas) — didiskusikan lebih lanjut setelah versi always-on dasar berjalan dan diuji di lingkungan nyata.

---

## 8. Desain Web UI — "Elbot Home Asisten"

### Halaman 1 — Chat Utama (`/`)
- Header dengan logo & nama **Elbot Home Asisten**, indikator status koneksi (online/offline ke broker).
- Bubble chat (riwayat obrolan teks + suara).
- **Mic otomatis aktif (always-on listening)** begitu halaman dibuka dan izin mikrofon diberikan — **tidak perlu menekan/menahan tombol apapun** untuk mulai bicara. User cukup ngobrol seperti bicara ke orang sebenarnya, AI mendeteksi sendiri kapan user mulai & selesai bicara (VAD/endpointing, lihat Bab 13.2.A).
- Indikator visual status mic dengan beberapa state berbeda (bukan tombol, murni indikator):
  - 🎙️ **Mendengarkan** (idle, menunggu user bicara) — animasi waveform halus/pulsing tenang.
  - 🗣️ **User sedang bicara** — animasi waveform mengikuti volume suara real-time.
  - 🤔 **Memproses** — AI Agent sedang berpikir/eksekusi tool.
  - 🔊 **ElBot bicara** — animasi waveform saat audio TTS diputar.
- Tombol **Mute/Unmute** (toggle sederhana, bukan push-to-talk) untuk user yang ingin sementara menonaktifkan mic — misalnya saat ada percakapan lain di sekitar yang tidak ingin "didengar" ElBot.
- **Echo-cancellation / self-mute otomatis**: saat ElBot sedang memutar audio balasannya sendiri, mic tidak diproses sebagai input baru (dicegah lewat AEC browser `echoCancellation: true` + flag backend "AI is speaking" agar tidak terjadi AI mendengar suaranya sendiri/feedback loop). Begitu ElBot selesai bicara, mic otomatis kembali mendengarkan tanpa aksi apapun dari user.
- Input teks alternatif (untuk yang tidak mau/tidak bisa pakai suara, mis. lingkungan berisik).
- Panel kecil "Perangkat Aktif" (quick status lampu yang menyala) di sisi/atas.

### Halaman 2 — Pengaturan (`/settings`)
Halaman **Pengaturan** menjadi pusat konfigurasi sistem, terdiri dari beberapa tab/sub-section:

#### Tab 2.1 — Manajemen Perangkat (`/settings/devices`)
- Tabel/list semua device: nama, ruangan, tipe (relay/lampu/sensor), status online/offline, status ON/OFF.
- Tombol **Tambah Perangkat**: form input nama, device_id (unik, dipakai di topic MQTT), ruangan, tipe.
- Edit/hapus device.
- Tombol toggle manual ON/OFF langsung dari tabel (tanpa harus ngobrol).

#### Tab 2.2 — Firmware OTA (`/settings/firmware`)
- Pilih target device (dropdown dari daftar device terdaftar).
- Upload file `.bin`.
- Progress bar pengiriman chunk via MQTT (live update via WebSocket).
- Riwayat update firmware per device (versi, tanggal, status sukses/gagal).

#### Tab 2.3 — Pengaturan Umum (opsional, bisa menyusul)
- Konfigurasi koneksi MQTT broker (host, port, kredensial) — tampil/edit dari UI.
- Konfigurasi API key/endpoint AI Agent.
- Pengaturan suara TTS (pilihan voice, kecepatan bicara).
- Manajemen akun/login (jika multi-user diaktifkan).

> **Catatan navigasi:** Halaman Chat utama (`/`) berfokus murni pada percakapan dengan ElBot dan kontrol cepat (toggle device on/off) tanpa elemen administratif. Semua aksi administratif (tambah/edit/hapus perangkat, upload firmware, konfigurasi sistem) dikelompokkan dalam satu halaman **Pengaturan** agar UI utama tetap bersih dan fokus untuk mengobrol, sementara fitur teknis tidak tercampur di percakapan.

### Gaya Visual
- Tema modern, dark-mode friendly, aksen warna biru/cyan ("teknologi/AI feel"), logo ElBot berbentuk robot sederhana.
- Akan dibangun menggunakan TailwindCSS + sedikit animasi (Framer Motion jika React, atau CSS animation jika vanilla).

---

## 9. Desain Database (SQLite)

### Tabel `devices`
| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER PK | |
| device_id | TEXT UNIQUE | dipakai di topic MQTT |
| name | TEXT | nama tampilan, mis. "Lampu Ruang Tamu" |
| room | TEXT | ruangan |
| type | TEXT | relay / lampu / sensor / lainnya |
| state | TEXT | ON/OFF/UNKNOWN |
| is_online | BOOLEAN | dari LWT MQTT |
| last_seen | DATETIME | |
| created_at | DATETIME | |

### Tabel `chat_history`
| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER PK | |
| role | TEXT | user / assistant / tool |
| content | TEXT | |
| created_at | DATETIME | |

### Tabel `action_logs`
| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER PK | |
| device_id | TEXT | |
| action | TEXT | |
| source | TEXT | voice / manual / text |
| created_at | DATETIME | |

### Tabel `firmware_updates`
| Kolom | Tipe | Keterangan |
|---|---|---|
| id | INTEGER PK | |
| device_id | TEXT | |
| filename | TEXT | |
| version_note | TEXT | |
| status | TEXT | pending/sending/success/failed |
| created_at | DATETIME | |

---

## 10. Firmware ESP32 (Garis Besar)

### Library yang dipakai
- `WiFi.h`
- `PubSubClient.h` atau `AsyncMqttClient` (rekomendasi: `PubSubClient` untuk simplicity awal)
- `ArduinoJson.h` (parsing payload)
- `Update.h` (OTA flashing)
- `Preferences.h` (simpan device_id/config di NVS)

### Logika Utama
1. Connect WiFi → connect MQTT broker.
2. Subscribe ke `elbot/<device_id>/cmd` dan `elbot/<device_id>/ota/data`.
3. Saat terima `cmd` → ubah pin relay (digitalWrite) → publish status terbaru ke `elbot/<device_id>/status`.
4. Saat terima `ota/data`:
   - Decode base64 chunk → tulis ke `Update` buffer.
   - Saat `chunk_index == total_chunks - 1` → `Update.end()`, verifikasi, `ESP.restart()`.
   - Publish progress ke `elbot/<device_id>/ota/status` tiap beberapa chunk.
5. Set **LWT** (`elbot/<device_id>/lwt`) = "offline" saat disconnect, "online" saat connect — agar backend tahu status real perangkat.

> Detail kode firmware akan dibuat di tahap implementasi (`firmware/esp32_relay/esp32_relay.ino`), termasuk wiring relay & contoh `mqtt_config.h` untuk broker address/credential.

---

## 11. Environment Variables (`.env`)

```env
# Custom OpenAI-compatible API
AI_API_BASE_URL=https://your-custom-endpoint.com/v1
AI_API_KEY=xxxxxxxx
AI_MODEL_NAME=your-model-name

# Google Cloud (STT & TTS)
GOOGLE_APPLICATION_CREDENTIALS=./secrets/google-credentials.json
STT_LANGUAGE_CODE=id-ID
TTS_VOICE_NAME=id-ID-Wavenet-A

# MQTT Broker
MQTT_BROKER_HOST=localhost
MQTT_BROKER_PORT=1883
MQTT_USERNAME=elbot
MQTT_PASSWORD=xxxxxxxx

# Database
DATABASE_URL=sqlite+aiosqlite:///./elbot.db

# App
APP_SECRET_KEY=xxxxxxxx
```

---

## 12. Roadmap Implementasi (Tahapan)

| Fase | Deliverable |
|---|---|
| **Fase 0 — Setup** | Struktur folder, `requirements.txt`, `docker-compose.yml` (Mosquitto + backend), `.env` |
| **Fase 1 — Backend Core** | FastAPI base, koneksi SQLite + model, koneksi MQTT service, endpoint REST device CRUD |
| **Fase 2 — AI Agent** | Integrasi custom OpenAI-compatible API, system prompt ElBot, function calling `control_device` dummy (tanpa MQTT dulu) |
| **Fase 3 — Voice Pipeline** | Integrasi Google STT streaming + Google TTS, endpoint WebSocket `/ws/chat` |
| **Fase 4 — Integrasi MQTT Real** | Tool `control_device` benar-benar publish ke MQTT, subscribe status device, update SQLite real-time |
| **Fase 5 — Web UI Chat** | Halaman utama chat, tombol mic, animasi waveform, live caption |
| **Fase 6 — Web UI Pengaturan: Manajemen Perangkat** | Halaman `/settings` (tab Perangkat), form tambah/edit/hapus, toggle manual |
| **Fase 7 — Firmware ESP32 Dasar** | `.ino` dasar: WiFi + MQTT + kontrol relay + status + LWT |
| **Fase 8 — OTA Firmware** | `ota_service.py` (chunking & publish), tab Firmware OTA di `/settings` (upload UI + progress), `ota_handler.h` di firmware ESP32 |
| **Fase 9 — Testing End-to-End** | Uji voice command → device nyala fisik, uji OTA update versi firmware |
| **Fase 10 — Optimasi Latensi (<2 Detik)** | Implementasi fast-path tool execution, streaming penuh STT/AI/TTS, benchmark & tuning per komponen — lihat Bab 13 |
| **Fase 11 — Polish UI & Deploy** | Refine tampilan, dark mode, dokumentasi `README.md`, panduan instalasi |

---

## 13. Optimasi Latensi (<2 Detik) — Critical Path

**Target:** dari saat user **selesai bicara** sampai **device fisik mulai menyala DAN/ATAU ElBot mulai mengucapkan balasan**, total waktu **< 2.000 ms**.

### 13.1 Budget Latensi Per Tahap

| Tahap | Komponen | Target Waktu | Catatan |
|---|---|---|---|
| 1 | STT endpointing (deteksi "user selesai bicara") | 100–300 ms | Pakai VAD/endpointing bawaan Google STT streaming, bukan timeout tetap |
| 2 | Transcript final → request AI Agent terkirim | <50 ms | Negligible jika di server yang sama/region dekat |
| 3 | AI Agent: time-to-first-tool-call (bukan full response) | 300–800 ms | **Bagian paling tidak pasti** — tergantung model. Lihat 13.2 |
| 4 | Backend eksekusi tool_call → publish MQTT | <30 ms | Publish lokal, sangat cepat |
| 5 | MQTT broker → ESP32 terima & eksekusi relay | 20–100 ms | Tergantung jaringan lokal & QoS |
| 6 | (Paralel) AI lanjut stream teks balasan → TTS chunk pertama → audio mulai main | 300–600 ms | Berjalan **paralel** dengan tahap 4-5, tidak menambah total waktu kalau didesain dengan benar |
| **Total (jalur device)** | Tahap 1+2+3+4+5 | **~450–1.280 ms** | Ini jalur kritis untuk "device menyala" |
| **Total (jalur suara mulai)** | Tahap 1+2+3+6 (paralel dgn 4-5) | **~700–1.750 ms** | Ini jalur kritis untuk "ElBot mulai bicara" |

Dengan desain **paralel** (device-first, lihat Bab 6), kedua jalur ini **tidak dijumlahkan** — keduanya berjalan dari titik cabang yang sama setelah tool_call terdeteksi, sehingga realistis berada di bawah 2 detik bahkan dengan model yang tidak terlalu cepat.

### 13.2 Strategi Teknis per Komponen

#### A. STT (Speech-to-Text) — Continuous Listening
- Gunakan **Google STT Streaming API** dengan `interim_results=True` agar endpointing otomatis memicu "final transcript" secepat mungkin setelah user berhenti bicara — hindari pendekatan rekam-dulu-baru-kirim.
- Karena pengalaman yang diinginkan adalah **mic selalu aktif tanpa tombol**, backend mengelola siklus sesi STT secara **otomatis dan transparan bagi user**: begitu satu sesi streaming Google STT menghasilkan `is_final=True` (satu utterance selesai), backend langsung membuka sesi streaming baru untuk menangkap ucapan berikutnya — dilakukan di belakang layar dalam hitungan milidetik, sehingga dari sisi user terasa seperti satu mic yang terus mendengarkan tanpa jeda.
- Audio dari browser **tidak pernah berhenti dikirim** selama mic tidak di-mute user; yang berganti hanya sesi STT di sisi backend per-utterance.
- Kirim audio dalam chunk kecil (100–250ms) secara kontinu via WebSocket selama mic aktif, bukan menunggu seluruh rekaman selesai.

#### A.1 Mute Manual & Pengelolaan Privasi
- Tombol **Mute** di UI menghentikan pengiriman audio dari browser ke backend (stream `getUserMedia` di-pause/track di-disable), bukan menutup koneksi WebSocket — agar saat Unmute, sistem bisa langsung lanjut mendengarkan tanpa delay re-handshake.
- Indikator mic (lihat Bab 8) harus jelas membedakan state "mendengarkan" vs "di-mute" agar user yakin kapan ElBot benar-benar bisa mendengar — penting untuk kepercayaan pengguna pada sistem always-on.

#### B. AI Agent — Mengurangi Time-to-First-Tool-Call
Karena modelnya **belum ditentukan** (custom OpenAI-compatible API, akan dites), plan ini menyiapkan beberapa strategi mitigasi yang bisa dipilih sesuai hasil benchmark nanti:

1. **Streaming response wajib** (`stream=True`) — backend memproses token sambil masuk, begitu sebuah `tool_call` object lengkap terdeteksi di stream, langsung eksekusi tanpa menunggu `finish_reason`.
2. **System prompt & tool schema seminimal mungkin** — prompt yang lebih pendek = prefill lebih cepat = time-to-first-token lebih cepat. Hindari menyuntikkan seluruh riwayat chat panjang; gunakan ringkasan konteks atau windowing (mis. 5-10 turn terakhir saja).
3. **`tool_choice` diarahkan** (bukan `"auto"` polos) ketika konteks mengindikasikan kuat ini perintah kontrol device (lihat poin C di bawah) — beberapa provider OpenAI-compatible mendukung `tool_choice: "required"` untuk memaksa model langsung memutuskan tool tanpa basa-basi teks dulu.
4. **Fallback jika model lambat (>1.5 detik time-to-first-token saat benchmark):** pertimbangkan model lebih kecil/cepat khusus untuk **intent classification + slot filling** (model A: cepat, hanya tugas "device mana + aksi apa"), dipisah dari model B yang lebih besar untuk obrolan umum/non-device. Keputusan ini diambil **setelah Fase 10 benchmark**, bukan didesain di muka tanpa data.

#### C. Fast-Path Intent Detection (Opsional, Lapisan Tambahan)
Sebagai jaring pengaman tambahan di luar AI Agent (bukan pengganti, tapi *shortcut* paralel):
- Backend menjalankan **pencocokan pola sederhana** (regex/keyword matching bahasa Indonesia: "nyalain", "matiin", "hidupkan", "padamkan" + nama device yang terdaftar) **bersamaan** saat transcript final masuk, **paralel** dengan request ke AI Agent.
- Jika pola cocok dengan confidence tinggi dan device dikenali persis → **langsung publish MQTT** tanpa menunggu AI Agent sama sekali, sehingga device menyala dalam hitungan puluhan-ratusan milidetik.
- AI Agent tetap dipanggil untuk menyusun kalimat balasan natural (dan sebagai otoritas akhir kalau pola tidak cocok/ambigu) — tapi **tidak lagi berada di jalur kritis eksekusi device**.
- Ini murni **enhancement opsional** untuk fase optimasi (Fase 10), bukan pengganti AI Agent — tetap dipakai sebagai pengaman ganda, bukan keharusan di awal.

#### D. TTS (Text-to-Speech)
- Gunakan **Google TTS Streaming** (atau pecah kalimat balasan jadi klausa pendek dan panggil TTS per-klausa) agar audio pertama bisa mulai diputar browser sebelum seluruh kalimat balasan model selesai di-generate.
- Cache hasil TTS untuk frasa yang sering berulang (mis. "Siap, sudah dinyalakan.", "Oke, sudah dimatikan.") agar untuk kasus umum bisa langsung play tanpa round-trip TTS API sama sekali.

#### E. MQTT
- Gunakan **QoS 1** (bukan QoS 0 yang tidak ada jaminan, bukan QoS 2 yang lebih lambat karena 4-way handshake) untuk topic `cmd` — balance antara kecepatan dan keandalan.
- Pastikan koneksi backend↔broker dan broker↔ESP32 **persistent** (tidak connect/disconnect tiap perintah) — koneksi MQTT dibuka sekali saat startup dan dijaga tetap hidup (keepalive).
- ESP32 sebaiknya **non-blocking** dalam `loop()` (hindari `delay()` panjang) agar bisa langsung memproses pesan MQTT begitu masuk.

#### F. Jaringan
- Idealnya backend, MQTT broker, dan ESP32 berada di **jaringan lokal yang sama (LAN)** agar tidak ada round-trip ke internet untuk tahap 4-5 (eksekusi device) — ini kontributor besar untuk konsistensi di bawah 2 detik. STT/TTS/AI Agent tetap ke cloud, tapi jalur device tetap lokal.

### 13.3 Pengukuran & Monitoring
- Backend mencatat **timestamp di setiap tahap** (audio final → tool_call terdeteksi → MQTT published → ESP32 ack status → TTS chunk pertama terkirim) dan menyimpannya di log/`action_logs` untuk analisis.
- Tambahkan endpoint/dashboard kecil (bisa di tab Pengaturan Umum) yang menampilkan **rata-rata latensi 7 hari terakhir** per tahap, agar mudah mengidentifikasi bottleneck mana yang perlu dioptimasi lebih lanjut setelah live.

---

## 14. Pertimbangan Keamanan

- MQTT broker sebaiknya pakai **username/password** + **TLS** (port 8883) bila diakses di luar jaringan lokal.
- Web UI sebaiknya ada **login sederhana** (terutama karena ada fitur upload firmware — risiko tinggi jika diakses sembarangan orang).
- Validasi file `.bin` yang diupload (cek ukuran, ekstensi, opsional signing/checksum) sebelum dikirim ke device.
- Rate limit endpoint AI Agent untuk menghindari biaya API membengkak.

---

## 15. Dependencies Utama (`requirements.txt` — draft)

```
fastapi
uvicorn[standard]
websockets
sqlalchemy
aiosqlite
pydantic
paho-mqtt
openai                  # dipakai dengan base_url custom (OpenAI-compatible)
google-cloud-speech
google-cloud-texttospeech
python-dotenv
python-multipart        # untuk upload file firmware
jinja2                  # jika render template server-side
```

---

## 16. Hal yang Perlu Dikonfirmasi Sebelum Coding (Open Questions)

1. **Endpoint custom OpenAI-compatible** — apakah sudah mendukung `tools`/function calling sesuai spec OpenAI **dan mendukung `stream=True`**? Ini wajib dicek di awal karena seluruh strategi optimasi latensi (Bab 13) bergantung pada streaming response.
2. **Jumlah & jenis perangkat ESP32** awal — berapa relay per ESP32 (1 channel / 4 channel / 8 channel)?
3. **Jaringan**: backend & ESP32 di jaringan lokal yang sama (LAN/WiFi rumah) atau perlu akses dari luar (internet) juga? (Memengaruhi konsistensi latensi tahap MQTT — lihat 13.2.F)
4. **Hosting**: backend akan jalan di server lokal (Raspberry Pi/mini PC) atau VPS? (Jika model AI dipanggil ke cloud yang jauh secara geografis, time-to-first-token bisa melebihi budget di Bab 13)
5. **Login/Auth**: perlu sistem login multi-user atau single-user (1 device akses) saja untuk versi awal?
6. **Benchmark model AI** — perlu dilakukan **secepatnya di Fase 2** (bukan ditunda ke akhir) untuk mengukur time-to-first-tool-call dari custom API yang dipakai, supaya strategi mitigasi di Bab 13.2.B (fast-path/model terpisah) bisa diputuskan lebih awal jika ternyata model lambat.

---

*Dokumen ini adalah blueprint awal. Detail kode per-fase akan dikembangkan secara bertahap mengikuti roadmap di atas.*