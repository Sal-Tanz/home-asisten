# Voice Pipeline + AI Agent — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build voice-controlled interaction pipeline: Google Speech API v2 STT → custom OpenAI-compatible AI Agent with tool calling → Edge TTS voice response, all via Socket.IO realtime communication.

**Architecture:** Socket.IO server alongside FastAPI, bidirectional audio/text streaming. STT batch (ffmpeg → FLAC → Google API). AI streaming (tool call detected → MQTT execute immediately). TTS streaming (Edge TTS per clause). Session-only chat history.

**Tech Stack:** python-socketio, edge-tts, openai SDK, ffmpeg CLI, google-speech-proto

**Base dir:** `/root/project/home-asisten/backend/`

**Spec ref:** `docs/superpowers/specs/2026-06-21-voice-pipeline-design.md`

---

## File Structure Overview

```
backend/app/
├── core/
│   ├── stt_service.py          # NEW: Google Speech API v2 + ffmpeg
│   ├── tts_service.py          # NEW: Edge TTS
│   └── ai_agent.py             # NEW: OpenAI-compatible with tools
├── chat/
│   ├── __init__.py             # NEW
│   ├── models.py               # NEW: ChatMessage dataclass
│   ├── tools.py                # NEW: Tool definitions
│   └── router.py               # NEW: Socket.IO events
├── config.py                   # MODIFY: add AI/STT/TTS settings
├── main.py                     # MODIFY: mount Socket.IO + lifespan
├── .env                        # MODIFY: add API keys
└── requirements.txt            # MODIFY: add deps
```

---

## Task 1: Dependency Setup

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/chat/__init__.py`

- [ ] **Step 1: Add new dependencies to requirements.txt**

Add these lines to `backend/requirements.txt`:

```txt
python-socketio[asyncio_client]==5.12.1
edge-tts==6.1.14
openai==1.68.0
aiofiles==24.1.0
```

- [ ] **Step 2: Install new packages**

```bash
cd /root/project/home-asisten/backend && source venv/bin/activate && pip install python-socketio edge-tts openai aiofiles
```

Expected: all packages install OK

- [ ] **Step 3: Verify imports**

```bash
cd /root/project/home-asisten/backend && source venv/bin/activate && python -c "
import socketio
import edge_tts
import openai
import aiofiles
print('All imports OK')
"
```

Expected: "All imports OK"

- [ ] **Step 4: Create chat package init**

```python
# backend/app/chat/__init__.py
# Empty file
```

- [ ] **Step 5: Verify ffmpeg is available**

```bash
which ffmpeg && ffmpeg -version | head -1
```

Expected: `/usr/bin/ffmpeg` and version info

- [ ] **Step 6: Commit**

```bash
cd /root/project/home-asisten && git add backend/requirements.txt backend/app/chat/
git commit -m "chore: add voice pipeline dependencies (socketio, edge-tts, openai)"
```
---

## Task 2: STT Service (Google Speech API v2)

**Files:**
- Create: `backend/app/core/stt_service.py`

- [ ] **Step 1: Create STT service with persistent session**

```python
# backend/app/core/stt_service.py
import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import aiofiles
import requests

logger = logging.getLogger(__name__)

# Google Speech API v2 configuration
GOOGLE_STT_KEY = "AIzaSyBOti4mM-6x9WDnZIjIeyEU21OpBXqWBgw"
GOOGLE_STT_URL = "https://www.google.com/speech-api/v2/recognize"

# Persistent HTTP session (connection pooling)
_stt_session = requests.Session()
_stt_session.headers.update({
    'User-Agent': 'Mozilla/5.0',
    'Content-Type': 'audio/x-flac; rate=16000',
})


class STTService:
    """Speech-to-Text service using Google Speech API v2."""

    def __init__(self, api_key: str = GOOGLE_STT_KEY):
        self.api_key = api_key
        self.session = _stt_session

    async def transcribe(self, audio_data: bytes, audio_format: str = "webm") -> dict:
        """Convert audio to text transcript.

        Args:
            audio_data: Raw audio bytes (WebM from browser)
            audio_format: Input format (webm, ogg, etc)

        Returns:
            {"transcript": str, "confidence": float, "error": Optional[str]}
        """
        try:
            # Convert audio to FLAC (16kHz, mono, s16)
            flac_data = await self._convert_to_flac(audio_data, audio_format)
            
            if not flac_data:
                return {"transcript": "", "confidence": 0.0, "error": "Audio conversion failed"}

            # Call Google Speech API v2
            transcript, confidence = await self._call_google_stt(flac_data)

            return {
                "transcript": transcript,
                "confidence": confidence,
                "error": None
            }

        except Exception as e:
            logger.error(f"STT error: {e}")
            return {"transcript": "", "confidence": 0.0, "error": str(e)}

    async def _convert_to_flac(self, audio_data: bytes, input_format: str) -> Optional[bytes]:
        """Convert audio to FLAC using ffmpeg subprocess."""
        try:
            # Run ffmpeg in thread pool (blocking I/O)
            loop = asyncio.get_event_loop()
            flac_data = await loop.run_in_executor(
                None,
                self._ffmpeg_convert,
                audio_data,
                input_format
            )
            return flac_data

        except Exception as e:
            logger.error(f"ffmpeg conversion error: {e}")
            return None

    def _ffmpeg_convert(self, audio_data: bytes, input_format: str) -> bytes:
        """Synchronous ffmpeg conversion (called in thread pool)."""
        # ffmpeg: input format -> FLAC (16kHz, mono, s16)
        proc = subprocess.Popen(
            [
                'ffmpeg',
                '-i', 'pipe:0',          # Read from stdin
                '-f', input_format,      # Input format
                '-ar', '16000',          # Sample rate 16kHz
                '-ac', '1',              # Mono
                '-sample_fmt', 's16',    # 16-bit signed
                '-f', 'flac',            # Output format
                'pipe:1'                 # Write to stdout
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout, stderr = proc.communicate(input=audio_data, timeout=10)

        if proc.returncode != 0:
            logger.error(f"ffmpeg stderr: {stderr.decode()}")
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()[:200]}")

        return stdout

    async def _call_google_stt(self, flac_data: bytes) -> tuple[str, float]:
        """Call Google Speech API v2 with FLAC audio."""
        url = f"{GOOGLE_STT_URL}?key={self.api_key}&lang=id-ID"

        # Run requests in thread pool (blocking I/O)
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.session.post(url, data=flac_data, timeout=10)
        )

        if response.status_code != 200:
            raise RuntimeError(f"Google STT API error: {response.status_code}")

        # Parse response (JSON lines format)
        lines = response.text.strip().split('\n')
        for line in lines:
            if not line:
                continue
            try:
                data = json.loads(line)
                if 'result' in data and data['result']:
                    result = data['result'][0]
                    if 'alternative' in result and result['alternative']:
                        alt = result['alternative'][0]
                        transcript = alt.get('transcript', '')
                        confidence = alt.get('confidence', 0.0)
                        return transcript, confidence
            except json.JSONDecodeError:
                continue

        return "", 0.0
```

- [ ] **Step 2: Verify imports and ffmpeg**

```bash
cd /root/project/home-asisten/backend && source venv/bin/activate && python -c "
from app.core.stt_service import STTService
import subprocess
# Check ffmpeg available
result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
print('STT Service import OK')
print('ffmpeg available:', result.returncode == 0)
"
```

Expected: "STT Service import OK" and "ffmpeg available: True"

- [ ] **Step 3: Commit STT service**

```bash
git add backend/app/core/stt_service.py
git commit -m "feat: add Google Speech API v2 STT service with ffmpeg conversion"
```

---

## Task 3: TTS Service (Edge TTS)

**Files:**
- Create: `backend/app/core/tts_service.py`

- [ ] **Step 1: Create TTS service with clause streaming**

```python
# backend/app/core/tts_service.py
import asyncio
import logging
import re
from typing import AsyncIterator, Callable, Awaitable

import edge_tts

logger = logging.getLogger(__name__)

# Edge TTS configuration
DEFAULT_VOICE = "id-ID-GadisNeural"
DEFAULT_RATE = "+0%"
DEFAULT_VOLUME = "+0%"


class TTSService:
    """Text-to-Speech service using Edge TTS with streaming output."""

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        rate: str = DEFAULT_RATE,
        volume: str = DEFAULT_VOLUME,
    ):
        self.voice = voice
        self.rate = rate
        self.volume = volume

    async def synthesize_stream(
        self,
        text: str,
        on_audio_chunk: Callable[[bytes], Awaitable[None]]
    ) -> None:
        """Synthesize text to speech and stream audio chunks.

        Args:
            text: Text to synthesize
            on_audio_chunk: Async callback for each audio chunk (MP3 bytes)
        """
        if not text.strip():
            return

        try:
            # Create Edge TTS communication object
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
            )

            # Stream audio chunks
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    await on_audio_chunk(chunk["data"])

        except Exception as e:
            logger.error(f"TTS synthesis error: {e}")
            raise

    async def synthesize_to_bytes(self, text: str) -> bytes:
        """Synthesize text to complete audio bytes (for caching/testing).

        Args:
            text: Text to synthesize

        Returns:
            Complete MP3 audio bytes
        """
        chunks = []

        async def collect_chunk(data: bytes):
            chunks.append(data)

        await self.synthesize_stream(text, collect_chunk)
        return b''.join(chunks)

    def split_into_clauses(self, text: str) -> list[str]:
        """Split text into clauses for streaming TTS (reduces first-audio latency).

        Args:
            text: Full text to split

        Returns:
            List of text clauses
        """
        # Split on sentence boundaries
        clauses = re.split(r'(?<=[.!?])\s+', text)
        return [c.strip() for c in clauses if c.strip()]
```

- [ ] **Step 2: Verify imports**

```bash
cd /root/project/home-asisten/backend && source venv/bin/activate && python -c "
from app.core.tts_service import TTSService
tts = TTSService()
print('TTS Service import OK')
print('Voice:', tts.voice)
"
```

Expected: "TTS Service import OK" and "Voice: id-ID-GadisNeural"

- [ ] **Step 3: Commit TTS service**

```bash
git add backend/app/core/tts_service.py
git commit -m "feat: add Edge TTS service with streaming synthesis"
```

---

## Task 4: AI Agent (OpenAI-compatible with Streaming)

**Files:**
- Create: `backend/app/core/ai_agent.py`

- [ ] **Step 1: Create AI agent with streaming and tool call detection**

```python
# backend/app/core/ai_agent.py
import json
import logging
from typing import AsyncIterator, Callable, Awaitable, Optional

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# AI API configuration
AI_API_BASE_URL = "https://api-ai.elektrounsub.com/v1"
AI_API_KEY = "sk-f86cd6ad61e2754f-tb3cn0-8412a37b"
AI_MODEL = "mmf/mimo-auto"


class AIAgent:
    """AI Agent using OpenAI-compatible API with streaming and tool calls."""

    def __init__(
        self,
        base_url: str = AI_API_BASE_URL,
        api_key: str = AI_API_KEY,
        model: str = AI_MODEL,
    ):
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    async def stream_with_tools(
        self,
        messages: list[dict],
        tools: Optional[list[dict]],
        on_text_chunk: Callable[[str], Awaitable[None]],
        on_tool_call: Callable[[str, str, dict], Awaitable[Optional[dict]]],
    ) -> None:
        """Stream AI response, detect tool calls, execute immediately.

        Args:
            messages: Chat history (OpenAI format)
            tools: Tool definitions (OpenAI format)
            on_text_chunk: Callback for each text chunk
            on_tool_call: Callback when tool call detected (tool_name, call_id, args)
                          Should return tool result dict or None
        """
        try:
            # Start streaming request
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools if tools else None,
                stream=True,
            )

            # Accumulate chunks and detect tool calls
            tool_call_accumulator = {}
            current_tool_call_id = None
            current_tool_name = None

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None

                if not delta:
                    continue

                # Check for tool call
                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        if tool_call_delta.index == 0:
                            # First tool call
                            if tool_call_delta.id:
                                current_tool_call_id = tool_call_delta.id
                            if tool_call_delta.function and tool_call_delta.function.name:
                                current_tool_name = tool_call_delta.function.name

                            # Accumulate arguments
                            if tool_call_delta.function and tool_call_delta.function.arguments:
                                if current_tool_call_id not in tool_call_accumulator:
                                    tool_call_accumulator[current_tool_call_id] = ""
                                tool_call_accumulator[current_tool_call_id] += tool_call_delta.function.arguments

                # Check for text content
                if delta.content:
                    await on_text_chunk(delta.content)

                # Check if stream finished with tool call
                if chunk.choices[0].finish_reason == "tool_calls" and current_tool_call_id:
                    # Parse accumulated arguments
                    args_str = tool_call_accumulator.get(current_tool_call_id, "{}")
                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {}

                    # Execute tool immediately
                    logger.info(f"Executing tool: {current_tool_name}({args})")
                    result = await on_tool_call(current_tool_name, current_tool_call_id, args)

                    # If tool executed, add result to messages for next request
                    if result is not None:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": current_tool_call_id,
                            "content": json.dumps(result),
                        })

                        # Request continuation after tool execution
                        await self.stream_with_tools(
                            messages=messages,
                            tools=tools,
                            on_text_chunk=on_text_chunk,
                            on_tool_call=on_tool_call,
                        )
                        return

        except Exception as e:
            logger.error(f"AI Agent error: {e}")
            raise

    async def simple_chat(self, messages: list[dict]) -> str:
        """Simple non-streaming chat (for testing).

        Args:
            messages: Chat history

        Returns:
            Assistant response text
        """
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            stream=False,
        )
        return response.choices[0].message.content or ""
```

- [ ] **Step 2: Verify imports**

```bash
cd /root/project/home-asisten/backend && source venv/bin/activate && python -c "
from app.core.ai_agent import AIAgent
agent = AIAgent()
print('AI Agent import OK')
print('Model:', agent.model)
print('Base URL:', agent.client.base_url)
"
```

Expected: "AI Agent import OK", "Model: mmf/mimo-auto", "Base URL: https://api-ai.elektrounsub.com/v1"

- [ ] **Step 3: Commit AI agent**

```bash
git add backend/app/core/ai_agent.py
git commit -m "feat: add OpenAI-compatible AI agent with streaming and tool call detection"
```

---

## Task 5: Chat Models (Session-Only)

**Files:**
- Create: `backend/app/chat/models.py`

- [ ] **Step 1: Create chat models**

```python
# backend/app/chat/models.py
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List


@dataclass
class ChatMessage:
    """Single chat message."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ChatSession:
    """In-memory chat session (no database persistence)."""
    session_id: str
    messages: List[ChatMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_activity: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_message(self, role: str, content: str):
        """Add a message to the session and update activity timestamp."""
        self.messages.append(ChatMessage(role=role, content=content))
        self.last_activity = datetime.now(timezone.utc)

    def get_messages_as_openai_format(self) -> List[Dict]:
        """Convert chat messages to OpenAI API format."""
        return [{"role": msg.role, "content": msg.content} for msg in self.messages]

    def clear(self):
        """Clear all messages from session."""
        self.messages.clear()

    def to_dict(self) -> List[Dict]:
        """Serialize messages for Socket.IO response."""
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in self.messages
        ]
```

- [ ] **Step 2: Verify imports**

```bash
cd /root/project/home-asisten/backend && source venv/bin/activate && python -c "
from app.chat.models import ChatSession, ChatMessage
session = ChatSession(session_id='test')
session.add_message('user', 'Halo')
session.add_message('assistant', 'Hai, ada yang bisa dibantu?')
print('Messages:', len(session.messages))
print('OpenAI format:', session.get_messages_as_openai_format())
print('OK')
"
```

Expected: 2 messages in OpenAI format

- [ ] **Step 3: Commit chat models**

```bash
git add backend/app/chat/models.py
git commit -m "feat: add session-only chat models for in-memory conversation"
```

---

## Task 6: Tools Definition

**Files:**
- Create: `backend/app/chat/tools.py`

- [ ] **Step 1: Create tools definition**

```python
# backend/app/chat/tools.py
"""OpenAI-compatible tool definitions for ElBot Home Asisten."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "control_device",
            "description": "Menyalakan, mematikan, atau toggle perangkat rumah pintar",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device ID unik perangkat (misal: 'esp32-ruang-tamu')",
                    },
                    "action": {
                        "type": "string",
                        "enum": ["ON", "OFF", "TOGGLE"],
                        "description": "Aksi yang dilakukan pada perangkat",
                    },
                },
                "required": ["device_id", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_status",
            "description": "Cek status terkini dari sebuah perangkat",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "Device ID perangkat yang ingin dicek",
                    },
                },
                "required": ["device_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_devices",
            "description": "Menampilkan daftar semua perangkat yang terdaftar di rumah",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]
```

- [ ] **Step 2: Verify imports**

```bash
cd /root/project/home-asisten/backend && source venv/bin/activate && python -c "
from app.chat.tools import TOOLS
print('Tools count:', len(TOOLS))
for t in TOOLS:
    print(f'  - {t[\"function\"][\"name\"]}')
print('OK')
"
```

Expected: 3 tools listed (control_device, get_device_status, list_devices)

- [ ] **Step 3: Commit tools**

```bash
git add backend/app/chat/tools.py
git commit -m "feat: add AI tool definitions for device control"
```
