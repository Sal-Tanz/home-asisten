# Frontend Fix Design — ElBot Home Asisten

> Fix plan compliance issues dari frontend review (Bab 8 & 13)

---

## 1. Scope

Fix 9 issues dari frontend review, diurutkan berdasarkan severity:

| # | Issue | Severity |
|---|-------|----------|
| 1 | Always-on mic tidak diimplementasi (push-to-talk) | CRITICAL |
| 2 | Text input tidak fungsional | CRITICAL |
| 3 | Tidak ada self-mute saat AI bicara | HIGH |
| 4 | Tidak ada auto-resume mic setelah TTS | HIGH |
| 5 | Waveform animasi static (tidak follow mic volume) | HIGH |
| 6 | Voice indicator hanya 1 state (plan minta 4) | MEDIUM |
| 7 | Color-only status di device cards | MEDIUM |
| 8 | Settings link href salah | MEDIUM |
| 9 | Toast tidak auto-dismiss (sudah ada tapi verify) | LOW |

## 2. Always-On Mic Pattern (CRITICAL #1, #3, #4)

### Current (Push-to-Talk)
```
User klik mic → rekam mulai → user bicara → user klik mic lagi → stop → kirim
```

### New Design (Always-On + Mute Toggle)
```
Page load → minta izin mic SEKALI → mic langsung aktif → stream audio kontinu
```

**Mic lifecycle:**
1. `init()` → `startListening()` otomatis (tanpa klik tombol)
2. `MediaRecorder` dibuka sekali, `start(250)` untuk chunk tiap 250ms
3. `ondataavailable` → kirim base64 audio chunk via Socket.IO terus-menerus
4. Mic button = **Mute/Unmute toggle** (ikon `mic` / `mic-off`)
5. Mute = `tracks.forEach(t => t.enabled = false)` — stream hidup, audio tidak dikirim
6. Unmute = `tracks.forEach(t => t.enabled = true)` — audio kembali dikirim

**Self-mute saat AI bicara (#3):**
```
Backend emit status(speaking) → frontend set flag isSpeaking=true
→ audio chunks dikirim tapi BUKAN diproses (backend-side ignore)
→ ATAU frontend-side: skip emit audio_data saat isSpeaking=true
```
Pilih **frontend-side skip** — lebih efisien, tidak buang bandwidth.

**Auto-resume (#4):**
```
Backend emit audio_done → frontend set isSpeaking=false
→ mic kembali aktif (track.enabled = true jika sebelumnya di-mute otomatis)
```

### State machine:
```
IDLE (listening) ──[user speaks, volume > threshold]──→ RECORDING
RECORDING ──[backend: transcribing]──→ PROCESSING
PROCESSING ──[backend: thinking]──→ THINKING
THINKING ──[backend: speaking]──→ SPEAKING
SPEAKING ──[audio_done event]──→ IDLE

Any state ──[user clicks mute]──→ MUTED
MUTED ──[user clicks unmute]──→ IDLE
```

## 3. Text Input Fix (CRITICAL #2)

```javascript
function sendMessage() {
  const text = msgInput.value.trim();
  if (!text || !socket?.connected) return;
  addMessage('user', text);
  socket.emit('text_message', { text });
  msgInput.value = '';
  msgInput.style.height = 'auto';
}
```

**Backend:** Tambah Socket.IO event handler `text_message` di `chat/router.py`:
```python
@sio.event
async def text_message(sid, data):
    """Handle text input — same pipeline as audio_data but skip STT."""
    transcript = data.get('text', '').strip()
    if not transcript:
        return
    # Same AI → TTS pipeline as audio_data handler
    ...
```

## 4. 4-State Voice Indicator (MEDIUM #6, HIGH #5)

| State | Status text | Animasi | Warna |
|-------|------------|---------|-------|
| `listening` | "Mendengarkan..." | Pulsing halus, waveform bar pendek bergerak lambat | `primary` (blue) |
| `user_speaking` | "Anda berbicara..." | Waveform bars follow mic volume real-time | `secondary` (green) |
| `thinking` | "Berpikir..." | Typing dots (3 titik bouncing) | `accent` (amber) |
| `speaking` | "ElBot berbicara..." | Audio output bars (solid waveform) | `secondary` (green) |

### Real-time Volume via Web Audio API (#5)
```javascript
const audioCtx = new AudioContext();
const analyser = audioCtx.createAnalyser();
analyser.fftSize = 256;
const source = audioCtx.createMediaStreamSource(mediaStream);
source.connect(analyser);

function updateVolume() {
  const data = new Uint8Array(analyser.frequencyBinCount);
  analyser.getByteFrequencyData(data);
  const avg = data.reduce((a, b) => a + b, 0) / data.length;
  // Update waveform bar heights based on avg (0-255 → 0-100%)
  updateWaveformBars(avg);
  requestAnimationFrame(updateVolume);
}
```

## 5. Minor Fixes

### Color-only status (#7)
Device cards: tambah icon (`check-circle` / `x-circle`) + text "ON"/"OFF" di samping colored dot.

### Settings link (#8)
`index.html` line 79: `href="/settings.html"` → `href="/settings"`

### Toast auto-dismiss (#9)
Sudah ada di `settings.js` (`setTimeout(() => t.remove(), 3000)`) tapi `app.js` `showToast` juga sudah ada. Verify both konsisten.

## 6. Files Changed

| File | Scope |
|------|-------|
| `frontend/static/js/app.js` | Rewrite mic logic, text input, voice states, real-time waveform, self-mute, auto-resume |
| `frontend/index.html` | Voice indicator 4-state markup, mic button jadi mute toggle |
| `frontend/static/css/styles.css` | 4 voice state styles, real-time waveform, modal animation |
| `backend/app/chat/router.py` | Tambah `text_message` Socket.IO event handler |
| `frontend/settings.html` | Fix link href |

## 7. Out of Scope

- Backend AI logic changes
- ESP32 firmware changes
- Settings tab Umum completeness (API/TTS config) — separate task
- Wake-word detection — future enhancement per plan
