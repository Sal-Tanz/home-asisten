# Voice Pipeline + AI Agent — Architecture Design

## Executive Summary

**Goal**: Build a voice-controlled home assistant with Indonesian language support, always-on recording, and <2 second response time for device control.

**Key Technologies**:
- **STT**: Google Speech API v2 (batch mode, WebM → FLAC via ffmpeg)
- **TTS**: Edge TTS (id-ID-GadisNeural, streaming synthesis)
- **AI**: Custom OpenAI-compatible API (mmf/mimo-auto model, streaming with tool calls)
- **Communication**: Socket.IO (WebSocket)
- **Speech Trigger**: Always-on recording, manual stop button

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ BROWSER                                                      │
│                                                               │
│  [Mic Always ON] → Record Audio → User Clicks "Stop"         │
│                            ↓                                  │
│                    Send WebM via Socket.IO                    │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ BACKEND (FastAPI + Socket.IO)                                │
│                                                               │
│  1. Receive WebM Audio                                       │
│  2. ffmpeg: WebM → FLAC (16kHz, mono, s16)                   │
│  3. POST to Google Speech API v2                             │
│  4. Parse transcript + confidence                            │
│  5. Send to AI Agent with tools                              │
│  6. Stream response:                                         │
│     - If tool_call detected → execute immediately (MQTT)     │
│     - Continue streaming text response                       │
│  7. Edge TTS: synthesize text → audio chunks                 │
│  8. Stream audio chunks via Socket.IO                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ BROWSER                                                      │
│                                                               │
│  Receive audio chunks → Play in sequence                     │
│  Update chat UI with transcript + response                   │
└─────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
backend/app/
├── core/
│   ├── stt_service.py          # Google Speech API v2 integration
│   ├── tts_service.py          # Edge TTS integration
│   └── ai_agent.py             # OpenAI-compatible API with tools
├── chat/
│   ├── models.py               # ChatMessage dataclass (session-only)
│   ├── router.py               # Socket.IO event handlers
│   └── tools.py                # Tool definitions for AI
└── main.py                     # Update: add Socket.IO, CORS, lifespan
```

---

## Component Design

### 1. STT Service (`core/stt_service.py`)

**Responsibility**: Convert audio (WebM) to text transcript

**Key Features**:
- Persistent HTTP session (connection pooling, no TCP/TLS handshake per request)
- ffmpeg subprocess for audio conversion (WebM → FLAC)
- POST to `https://www.google.com/speech-api/v2/recognize`
- Parse JSON response, extract best transcript + confidence score

**API Key**: `AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw` (from user)

**Latency Budget**: ~300-500ms (audio conversion + API call)

---

### 2. TTS Service (`core/tts_service.py`)

**Responsibility**: Convert text to speech audio

**Key Features**:
- Edge TTS library integration
- Voice: `id-ID-GadisNeural` (Indonesian female, natural)
- Streaming synthesis (send audio chunks as they're ready)
- Cache common phrases (e.g., "Perangkat sudah diaktifkan")

**Latency Budget**: ~200-400ms (first chunk, then streaming)

---

### 3. AI Agent (`core/ai_agent.py`)

**Responsibility**: Process user input, decide tool calls, generate response

**Key Features**:
- OpenAI-compatible API client (base_url: `https://api-ai.elektrounsub.com/v1`)
- Model: `mmf/mimo-auto`
- System prompt: ElBot identity (Indonesian, friendly, helpful)
- Tools: `control_device`, `get_device_status`, `list_devices`
- **Streaming response with immediate tool execution**:
  - Detect `tool_call` in stream → execute immediately (don't wait for full response)
  - Continue streaming text response
  - This enables device-first execution (<2s for device control)

**Latency Budget**: ~800-1500ms (time-to-first-token, depends on model)

---

### 4. Socket.IO Router (`chat/router.py`)

**Responsibility**: Handle WebSocket communication, orchestrate STT → AI → TTS pipeline

**Key Features**:
- Socket.IO event handlers (`connect`, `disconnect`, `audio_data`, `stop_recording`)
- Session management (chat history in memory, auto-clear on disconnect)
- Orchestrate pipeline:
  1. Receive audio data (WebM)
  2. Call STT service
  3. Send transcript to AI agent
  4. Stream text response back to client
  5. Call TTS service for audio
  6. Stream audio chunks back to client
- **Device-first execution**: When AI returns tool_call, execute immediately (MQTT publish) before streaming full text response

**Latency Optimization**:
- Parallel processing where possible
- Stream responses (don't wait for completion)
- Device control executes immediately on tool_call detection

---

### 5. Chat Models (`chat/models.py`)

**Responsibility**: Define data structures for chat (session-only, no database)

**Key Features**:
- `ChatMessage` dataclass (role, content, timestamp)
- Session dict to store chat history per user
- Auto-clear on disconnect or 5-minute timeout
- No database persistence (as per decision)

---

### 6. Tools Definition (`chat/tools.py`)

**Responsibility**: Define OpenAI-compatible tool schemas

**Tools**:

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "control_device",
            "description": "Control a smart home device (turn on/off/toggle)",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Device ID"},
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
            "description": "Get current status of a device",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {"type": "string", "description": "Device ID"}
                },
                "required": ["device_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": "List all available smart home devices",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]
```

---

## System Prompt (ElBot Identity)

```
Kamu adalah ElBot, asisten rumah pintar berbahasa Indonesia. Kamu ramah, helpful, dan efisien.

Aturan:
1. Selalu jawab dalam Bahasa Indonesia
2. Gunakan nama "ElBot" saat memperkenalkan diri
3. Untuk perintah kontrol perangkat, gunakan tools yang tersedia
4. Jawaban harus singkat dan jelas (1-2 kalimat)
5. Konfirmasi aksi yang dilakukan (misalnya: "Lampu ruang tamu sudah dinyalakan")
6. Jika tidak mengerti, minta klarifikasi dengan sopan

Contoh interaksi:
- User: "Nyalakan lampu ruang tamu"
- ElBot: [control_device("living_room_light", "ON")] "Baik, lampu ruang tamu sudah dinyalakan."

- User: "Apa status AC kamar?"
- ElBot: [get_device_status("bedroom_ac")] "AC kamar saat ini dalam keadaan mati dengan suhu 24°C."
```

---

## Latency Analysis

**Target**: <2 seconds for device control (from user stop speaking to device state change)

**Breakdown**:
1. **STT**: 300-500ms (ffmpeg + Google API)
2. **AI (time-to-first-token)**: 800-1500ms (depends on model)
3. **Tool execution (MQTT)**: 50-100ms (local broker)
4. **TTS (first chunk)**: 200-400ms (Edge TTS)

**Total**: ~1350-2500ms

**Optimization Strategy**:
- Device-first execution: Execute tool_call immediately when detected in stream (don't wait for full response)
- Parallel processing: STT → AI → TTS pipeline with streaming
- Connection pooling: Persistent HTTP sessions for STT and AI APIs
- Audio caching: Cache common TTS phrases

**Realistic Expectation**: ~1.5-2.5 seconds for device control (acceptable for v1)

---

## Session Management

**Chat History**: Session-only (in memory, no database)

**Storage**:
```python
chat_sessions = {
    "session_id_1": [
        ChatMessage(role="user", content="Nyalakan lampu", timestamp=...),
        ChatMessage(role="assistant", content="Baik, lampu sudah dinyalakan", timestamp=...),
    ],
    "session_id_2": [...]
}
```

**Cleanup**:
- Auto-clear on Socket.IO disconnect
- 5-minute timeout for inactive sessions
- No persistence (as per decision)

---

## Error Handling

**STT Errors**:
- Low confidence (<0.5): Ask user to repeat
- Network timeout: Retry once, then ask user to try again
- Invalid audio format: Log error, ask user to speak clearly

**AI Errors**:
- API timeout: Retry once, then apologize and ask user to try again
- Invalid tool call: Log error, continue with text response
- Rate limiting: Wait and retry, inform user

**TTS Errors**:
- Synthesis failure: Fall back to text-only response
- Audio playback error: Log error, continue with next chunk

**Tool Execution Errors**:
- Device not found: Inform user, suggest checking device list
- MQTT connection error: Inform user, suggest checking network
- Command timeout: Inform user, suggest retrying

---

## Security Considerations

**Audio Data**:
- Temporary storage only (deleted after STT processing)
- No persistence (session-only chat history)
- Local processing (ffmpeg on server)

**API Keys**:
- Stored in `.env` (not committed to git)
- Google Speech API key: `AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw`
- Custom AI API key: `sk-f86cd6ad61e2754f-tb3cn0-8412a37b`

**Network**:
- HTTPS for API calls (Google Speech, Custom AI)
- WSS for Socket.IO (in production)
- Local MQTT broker (no external access)

---

## Testing Strategy

**Unit Tests**:
- STT service: Mock Google API, test audio conversion
- TTS service: Mock Edge TTS, test streaming synthesis
- AI agent: Mock OpenAI API, test tool call detection
- Tools: Test device control, status query, list devices

**Integration Tests**:
- Socket.IO events: Test audio upload, streaming responses
- Pipeline: Test STT → AI → TTS flow
- Device control: Test tool execution via MQTT

**Manual Testing**:
- Record real Indonesian speech, test transcription accuracy
- Test device control commands, measure latency
- Test error scenarios (network timeout, invalid audio)

---

## Deployment Considerations

**Dependencies**:
- `python-socketio`: Socket.IO server
- `edge-tts`: Edge TTS library
- `openai`: OpenAI-compatible API client
- `ffmpeg`: Audio conversion (install via apt: `sudo apt install ffmpeg`)

**Configuration**:
- `.env` file with API keys and URLs
- Socket.IO CORS settings
- ffmpeg binary availability

**Scalability**:
- Session-only chat history (no database bottleneck)
- Streaming responses (low memory usage)
- Local MQTT broker (fast device control)

---

## Future Enhancements (Out of Scope for v1)

1. **Database persistence**: Save chat history to SQLite
2. **User authentication**: Link chat sessions to user accounts
3. **Fast-path intent detection**: Regex matching for common commands (bypass AI)
4. **Wake word detection**: "Hai ElBot" to activate listening
5. **Multi-language support**: Switch between Indonesian/English
6. **Audio streaming STT**: Replace batch API with streaming (if available)
7. **TTS voice selection**: Allow user to choose different voices
8. **Chat export**: Download chat history as JSON/CSV
