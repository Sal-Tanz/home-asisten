# Frontend Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 9 frontend issues from review - always-on mic, text input, 4-state voice indicator, real-time waveform, accessibility fixes.

**Architecture:** Rewrite mic logic from push-to-talk to always-on with mute toggle. Add Web Audio API analyser for real-time volume. Wire text input to backend. Add 4 distinct voice states with animations.

**Tech Stack:** Vanilla JS, Socket.IO client, Web Audio API, TailwindCSS, Lucide icons

---

## Task 1: Backend - Add text_message Socket.IO Handler

**Files:**
- Modify: `backend/app/chat/router.py:46-138`

- [ ] **Step 1: Add text_message event handler after audio_data handler**

```python
@sio.event
async def text_message(sid, data):
    """Handle text input — same pipeline as audio_data but skip STT."""
    session = sessions.get(sid)
    if not session:
        logger.warning(f"No session found for {sid}")
        return

    try:
        transcript = data.get('text', '').strip()
        if not transcript:
            await sio.emit('error', {'message': 'Pesan kosong'}, to=sid)
            return

        logger.info(f"Text message: {transcript}")
        await sio.emit('transcript', {'text': transcript}, to=sid)
        session.add_message('user', transcript)

        # Step 2: AI Agent processing with tools
        await sio.emit('status', {'state': 'thinking'}, to=sid)

        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + session.get_messages_as_openai_format()

        response_text = ""

        async def on_text_chunk(chunk: str):
            """Handle streaming text chunks from AI."""
            nonlocal response_text
            response_text += chunk
            await sio.emit('text_chunk', {'text': chunk}, to=sid)

        async def on_tool_call(tool_call: dict):
            """Handle tool execution requests from AI."""
            tool_name = tool_call['name']

            args = tool_call['args']
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}

            logger.info(f"Tool call: {tool_name} with args: {args}")

            if tool_name == 'list_devices':
                return await _list_devices()

            elif tool_name == 'get_device_status':
                return await _get_device_status(args.get('device_id', ''))

            elif tool_name == 'control_device':
                return await _control_device(
                    device_id=args.get('device_id', ''),
                    action=args.get('action', ''),
                )

            return {"error": f"Unknown tool: {tool_name}"}

        # Stream AI response with tool support
        await ai_agent.stream_with_tools(messages, TOOLS, on_text_chunk, on_tool_call)

        # Step 3: Text-to-Speech (if we have response text)
        if response_text:
            session.add_message('assistant', response_text)
            await sio.emit('response', {'text': response_text}, to=sid)

            await sio.emit('status', {'state': 'speaking'}, to=sid)

            # Stream TTS clause-by-clause for lower latency
            clauses = tts_service.split_into_clauses(response_text)
            for clause in clauses:
                await tts_service.synthesize_stream(clause, lambda chunk: sio.emit(
                    'audio_chunk', {'audio': base64.b64encode(chunk).decode()}, to=sid
                ))

            await sio.emit('audio_done', {}, to=sid)

        # Return to listening state
        await sio.emit('status', {'state': 'listening'}, to=sid)

    except Exception as e:
        logger.error(f"Error in text_message handler: {e}", exc_info=True)
        await sio.emit('error', {'message': str(e)}, to=sid)
        await sio.emit('status', {'state': 'listening'}, to=sid)
```

- [ ] **Step 2: Test text_message handler**

Start backend:
```bash
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8500
```

Test via browser console:
```javascript
socket.emit('text_message', { text: 'nyalakan lampu' })
```

Expected: `status(thinking)` → `text_chunk` events → `status(speaking)` → `audio_chunk` → `audio_done` → `status(listening)`

- [ ] **Step 3: Commit backend change**

```bash
git add backend/app/chat/router.py
git commit -m "feat(backend): add text_message Socket.IO handler for text input

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 2: Frontend - Fix Settings Link Href

**Files:**
- Modify: `frontend/index.html:79`

- [ ] **Step 1: Change settings link from .html to server route**

```html
<a href="/settings" class="p-2 hover:bg-slate-800 rounded-lg transition-colors cursor-pointer" aria-label="Pengaturan">
    <i data-lucide="settings" class="w-5 h-5"></i>
</a>
```

- [ ] **Step 2: Test navigation**

Open http://localhost:8500 → click settings icon → should navigate to http://localhost:8500/settings (not 404)

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "fix(frontend): correct settings link href to /settings

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 3: Frontend - Fix Color-Only Status in Device Cards

**Files:**
- Modify: `frontend/static/js/app.js:201-214`

- [ ] **Step 1: Add icon + text to device card rendering**

Replace `renderDeviceCards` function:

```javascript
function renderDeviceCards(devices) {
  if (!devices.length) return;
  devicePanel.innerHTML = devices.slice(0, 6).map(d => {
    const on = Object.values(d.state || {}).some(v => v === 'ON');
    const statusIcon = on ? 'check-circle' : 'x-circle';
    const statusText = on ? 'ON' : 'OFF';
    return `<div class="flex-shrink-0 w-32 h-24 bg-slate-800 border ${on ? 'border-secondary' : 'border-slate-700'} rounded-xl p-3 flex flex-col justify-between hover:border-slate-600 transition-colors cursor-pointer" onclick="toggleDevice('${d.device_id}', '${on}')">
      <div class="flex items-center justify-between">
        <i data-lucide="${getDeviceIcon(d.type)}" class="w-5 h-5 ${on ? 'text-secondary' : 'text-slate-400'}"></i>
        <i data-lucide="${statusIcon}" class="w-4 h-4 ${on ? 'text-secondary' : 'text-danger'}"></i>
      </div>
      <div>
        <p class="text-xs font-medium truncate">${d.name}</p>
        <p class="text-xs ${on ? 'text-secondary' : 'text-slate-400'} font-medium">${statusText}</p>
      </div>
    </div>`;
  }).join('');
  lucide.createIcons();
}
```

- [ ] **Step 2: Test device card display**

Open http://localhost:8500 → device cards should show icon (check-circle or x-circle) + text "ON"/"OFF" instead of just colored dot

- [ ] **Step 3: Commit**

```bash
git add frontend/static/js/app.js
git commit -m "fix(frontend): add icon and text to device status for accessibility

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 4: Frontend - Verify Toast Auto-Dismiss

**Files:**
- Verify: `frontend/static/js/app.js:233-239`

- [ ] **Step 1: Check showToast implementation**

Current code already has auto-dismiss:
```javascript
function showToast(msg, type) {
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);  // ← Auto-dismiss after 3s
}
```

✅ Already correct, no changes needed.

- [ ] **Step 2: Test toast display**

Open browser console → run:
```javascript
showToast('Test toast', 'success')
```

Expected: Toast appears bottom-right → disappears after 3 seconds

- [ ] **Step 3: No commit needed (verification only)**

---

## Task 5: Frontend - Add 4-State Voice Indicator Markup

**Files:**
- Modify: `frontend/index.html:167-179`

- [ ] **Step 1: Replace voice indicator with 4-state markup**

Replace the voice indicator section:

```html
<!-- Voice Indicator (4 States) -->
<div id="voiceIndicator" class="hidden mb-6">
    <div class="flex items-center justify-center gap-3 py-4 bg-slate-800/50 border border-slate-700 rounded-xl">
        <!-- Waveform bars (for listening & user_speaking states) -->
        <div id="waveformBars" class="flex items-center gap-1">
            <div class="waveform-bar" data-bar="0"></div>
            <div class="waveform-bar" data-bar="1"></div>
            <div class="waveform-bar" data-bar="2"></div>
            <div class="waveform-bar" data-bar="3"></div>
            <div class="waveform-bar" data-bar="4"></div>
        </div>
        <!-- Typing dots (for thinking state) -->
        <div id="typingDots" class="hidden flex items-center gap-1">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
        </div>
        <p class="text-sm text-slate-300" id="voiceStatus">Mendengarkan...</p>
    </div>
</div>
```

- [ ] **Step 2: Commit HTML changes**

```bash
git add frontend/index.html
git commit -m "feat(frontend): add 4-state voice indicator markup

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 6: Frontend - Add CSS for 4 Voice States

**Files:**
- Modify: `frontend/static/css/styles.css:1-116`

- [ ] **Step 1: Add voice state-specific CSS classes**


Append after existing styles:

```css
/* Voice Indicator States */
.voice-listening .waveform-bar { animation: wave-listen 2s ease-in-out infinite; }
@keyframes wave-listen {
  0%, 100% { height: 4px; }
  50% { height: 16px; }
}

.voice-user-speaking .waveform-bar { animation: none; transition: height 0.05s linear; }
.voice-user-speaking { border-color: #10B981; }

.voice-thinking .typing-dot { background: #F59E0B; }
.voice-thinking { border-color: #F59E0B; }

.voice-speaking .waveform-bar { animation: wave-speak 0.5s ease-in-out infinite; height: 20px; }
@keyframes wave-speak {
  0%, 100% { height: 8px; opacity: 0.4; }
  50% { height: 24px; opacity: 1; }
}
.voice-speaking { border-color: #10B981; }

/* Modal animation */
.modal-enter {
  animation: modal-in 0.2s ease-out;
}
@keyframes modal-in {
  from { opacity: 0; transform: scale(0.95) translateY(-8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.modal-exit {
  animation: modal-out 0.15s ease-in;
}
@keyframes modal-out {
  from { opacity: 1; transform: scale(1) translateY(0); }
  to { opacity: 0; transform: scale(0.95) translateY(-8px); }
}

/* Waveform bars base style (overrides old wave animation) */
.voice-indicator .waveform-bar {
  width: 3px;
  min-height: 4px;
  background: currentColor;
  border-radius: 2px;
}

/* Muted state */
.mic-muted .mic-icon {
  color: #EF4444;
}
```

- [ ] **Step 2: Commit CSS**

```bash
git add frontend/static/css/styles.css
git commit -m "feat(frontend): add CSS for 4 voice states and modal animation

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 7: Frontend - Rewrite Mic Logic (Always-On + Mute Toggle)

**Files:**
- Modify: `frontend/static/js/app.js` (full rewrite of mic section)
- Modify: `frontend/index.html:198-203` (mic button becomes mute toggle)

**This is the core change.** Replace push-to-talk (click to start, click to stop) with always-on (mic auto-starts on page load, mute toggle only).

- [ ] **Step 1: Replace mic button markup in index.html**

Change mic button (line 198-203) from recording icon to mute/unmute:

```html
<!-- Mic Mute/Unmute Button -->
<button
    id="micButton"
    class="flex-shrink-0 w-12 h-12 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl flex items-center justify-center transition-all cursor-pointer group"
    aria-label="Mute mikrofon"
>
    <i data-lucide="mic" class="w-5 h-5 mic-icon group-hover:scale-110 transition-transform"></i>
</button>
```

- [ ] **Step 2: Rewrite app.js — replace recording logic with always-on pattern**

Replace lines 5-10 (State) and 89-131 (Mic/Recording section) with:

```javascript
  // State
  let socket = null;
  let isMuted = false;
  let isSpeaking = false;
  let mediaStream = null;
  let mediaRecorder = null;
  let audioCtx = null;
  let analyser = null;
  let volumeAnimationId = null;

  // DOM elements
  const micBtn = document.getElementById('micButton');
  const sendBtn = document.getElementById('sendButton');
  const msgInput = document.getElementById('messageInput');
  const chatContainer = document.getElementById('chatContainer');
  const voiceIndicator = document.getElementById('voiceIndicator');
  const voiceStatus = document.getElementById('voiceStatus');
  const waveformBars = document.getElementById('waveformBars');
  const typingDots = document.getElementById('typingDots');
  const devicePanel = document.getElementById('devicePanel');
  const connectionStatus = document.getElementById('connectionStatus');

  // ─── Init ───────────────────────────────────────
  async function init() {
    lucide.createIcons();
    loadDevices();
    setupSocket();
    setupInput();
    await startListening();  // ← Auto-start mic on page load
    setupMuteToggle();
    autoResizeTextarea();
  }

  // ─── Always-On Mic ──────────────────────────────
  async function startListening() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });

      // Set up Web Audio API analyser for real-time volume
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      const source = audioCtx.createMediaStreamSource(mediaStream);
      source.connect(analyser);

      // Start volume visualization loop
      trackVolume();

      // Create MediaRecorder with continuous chunks (250ms)
      mediaRecorder = new MediaRecorder(mediaStream, { mimeType: 'audio/webm;codecs=opus' });
      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0 && !isMuted && !isSpeaking) {
          // Convert blob → base64 and send via Socket.IO
          const reader = new FileReader();
          reader.onloadend = () => {
            const base64 = reader.result.split(',')[1];
            if (socket && socket.connected) {
              socket.emit('audio_data', { audio: base64 });
            }
          };
          reader.readAsDataURL(e.data);
        }
      };
      mediaRecorder.start(250);

      showVoiceIndicator('listening');
      console.log('Always-on mic started');
    } catch (err) {
      showToast('Tidak bisa mengakses mikrofon', 'error');
    }
  }

  function setupMuteToggle() {
    micBtn.addEventListener('click', () => {
      if (isMuted) unmuteMic();
      else muteMic();
    });
  }

  function muteMic() {
    isMuted = true;
    mediaStream.getTracks().forEach(t => t.enabled = false);
    micBtn.querySelector('.mic-icon').setAttribute('data-lucide', 'mic-off');
    micBtn.querySelector('.mic-icon').classList.add('text-danger');
    micBtn.setAttribute('aria-label', 'Unmute mikrofon');
    hideVoiceIndicator();
    lucide.createIcons();
  }

  function unmuteMic() {
    isMuted = false;
    mediaStream.getTracks().forEach(t => t.enabled = true);
    micBtn.querySelector('.mic-icon').setAttribute('data-lucide', 'mic');
    micBtn.querySelector('.mic-icon').classList.remove('text-danger');
    micBtn.setAttribute('aria-label', 'Mute mikrofon');
    showVoiceIndicator('listening');
    lucide.createIcons();
  }
```

- [ ] **Step 3: Remove old startRecording/stopRecording functions**

Delete the old functions `startRecording()`, `stopRecording()` from the file.

- [ ] **Step 4: Commit mic rewrite**

```bash
git add frontend/static/js/app.js frontend/index.html
git commit -m "feat(frontend): rewrite mic logic to always-on with mute toggle

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 8: Frontend - Real-Time Waveform + 4-State Voice Indicator

**Files:**
- Modify: `frontend/static/js/app.js` (replace voice indicator section)

- [ ] **Step 1: Replace voice indicator functions with 4-state handler**

Replace lines 133-148 (Voice Indicator section) with:

```javascript
  // ─── Voice Indicator (4 States) ─────────────────
  function showVoiceIndicator(state) {
    voiceIndicator.classList.remove('hidden',
      'voice-listening', 'voice-user-speaking', 'voice-thinking', 'voice-speaking');

    switch (state) {
      case 'listening':
        voiceIndicator.classList.add('voice-listening');
        voiceStatus.textContent = 'Mendengarkan...';
        waveformBars.classList.remove('hidden');
        typingDots.classList.add('hidden');
        break;
      case 'user_speaking':
        voiceIndicator.classList.add('voice-user-speaking');
        voiceStatus.textContent = 'Anda berbicara...';
        waveformBars.classList.remove('hidden');
        typingDots.classList.add('hidden');
        break;
      case 'thinking':
        voiceIndicator.classList.add('voice-thinking');
        voiceStatus.textContent = 'Berpikir...';
        waveformBars.classList.add('hidden');
        typingDots.classList.remove('hidden');
        break;
      case 'speaking':
        voiceIndicator.classList.add('voice-speaking');
        voiceStatus.textContent = 'ElBot berbicara...';
        waveformBars.classList.remove('hidden');
        typingDots.classList.add('hidden');
        break;
    }
  }

  function hideVoiceIndicator() {
    voiceIndicator.classList.add('hidden');
    voiceIndicator.classList.remove(
      'voice-listening', 'voice-user-speaking', 'voice-thinking', 'voice-speaking');
  }

  function handleStatus(state) {
    switch (state) {
      case 'transcribing': showVoiceIndicator('user_speaking'); break;
      case 'thinking': showVoiceIndicator('thinking'); break;
      case 'speaking': isSpeaking = true; showVoiceIndicator('speaking'); break;
      case 'listening': isSpeaking = false; showVoiceIndicator('listening'); break;
    }
  }
```

- [ ] **Step 2: Add real-time volume visualization**

Add after the `setupMuteToggle` function:

```javascript
  function trackVolume() {
    if (!analyser) return;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    function updateBars() {
      analyser.getByteFrequencyData(dataArray);

      // Calculate average volume across frequency bins
      const avg = dataArray.reduce((a, b) => a + b, 0) / dataArray.length;
      // Normalize to 0-1 range
      const normalized = Math.min(avg / 128, 1);

      // Update waveform bar heights (5 bars)
      const bars = waveformBars.querySelectorAll('.waveform-bar');
      bars.forEach((bar, i) => {
        // Vary each bar slightly based on its position in frequency spectrum
        const freqSlice = dataArray.slice(i * 20, (i + 1) * 20);
        const sliceAvg = freqSlice.reduce((a, b) => a + b, 0) / freqSlice.length;
        const height = Math.max(4, (sliceAvg / 255) * 32);
        bar.style.height = height + 'px';
      });

      // Detect if user is speaking (volume above threshold)
      if (!isMuted && !isSpeaking && normalized > 0.15) {
        // User is speaking - this triggers transcribing on backend side
      }

      volumeAnimationId = requestAnimationFrame(updateBars);
    }

    volumeAnimationId = requestAnimationFrame(updateBars);
  }
```

- [ ] **Step 3: Clean up volume animation on page unload**

Add cleanup in init:

```javascript
  window.addEventListener('beforeunload', () => {
    if (volumeAnimationId) cancelAnimationFrame(volumeAnimationId);
    if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
    if (audioCtx) audioCtx.close();
  });
```

- [ ] **Step 4: Commit voice indicator + waveform**

```bash
git add frontend/static/js/app.js
git commit -m "feat(frontend): add 4-state voice indicator and real-time waveform

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 9: Frontend - Wire Text Input to Backend

**Files:**
- Modify: `frontend/static/js/app.js:179-187`

- [ ] **Step 1: Replace sendMessage function**

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

- [ ] **Step 2: Keep existing setupInput and autoResizeTextarea unchanged**

✅ Already correct — just need the emit in sendMessage.

- [ ] **Step 3: Commit**

```bash
git add frontend/static/js/app.js
git commit -m "fix(frontend): wire text input to backend via text_message event

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Task 10: Frontend - Wire Self-Mute During TTS

**Files:**
- Modify: `frontend/static/js/app.js` (handleStatus already sets isSpeaking)

- [ ] **Step 1: Verify self-mute logic in audio_data sending**

The `mediaRecorder.ondataavailable` handler from Task 7 already includes:
```javascript
if (e.data.size > 0 && !isMuted && !isSpeaking) {
```
→ `!isSpeaking` ensures audio is NOT sent while ElBot is speaking.

✅ Self-mute already implemented in Task 7.

- [ ] **Step 2: Verify isSpeaking is correctly set on status events**

`handleStatus` function from Task 8:
```javascript
case 'speaking': isSpeaking = true; showVoiceIndicator('speaking'); break;
case 'listening': isSpeaking = false; showVoiceIndicator('listening'); break;
```

✅ Auto-resume happens when backend emits `status(listening)`.

- [ ] **Step 3: No additional commit needed (already integrated)**

---

## Task 11: Integration — Verify Full Pipeline

**Files:**
- No code changes — verification only

- [ ] **Step 1: Start backend**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8500
```

- [ ] **Step 2: Test always-on mic flow**

Open http://localhost:8500 in browser:
1. Browser asks for mic permission → Allow
2. Mic auto-starts (no button click needed) → waveform visible, "Mendengarkan..."
3. Speak "Nyalakan lampu" → status changes: listening → transcribing → thinking → speaking → listening
4. ElBot responds with audio
5. While ElBot speaks, mic audio should NOT be sent (self-mute)
6. After ElBot finishes, mic auto-resumes

- [ ] **Step 3: Test mute toggle**

On chat page:
1. Click mic button → icon changes to mic-off, waveform hidden, muted state
2. Speak → no response from ElBot (audio not sent)
3. Click mic button again → unmute, waveform returns
4. Speak → ElBot responds normally

- [ ] **Step 4: Test text input**

In chat page:
1. Type "nyalakan lampu" in textarea
2. Press Enter → message appears in chat, sent to backend
3. ElBot responds with AI processing → TTS audio

- [ ] **Step 5: Test device cards accessibility**

1. Add a device via Settings → check device card shows check-circle/x-circle icon + ON/OFF text
2. Toggle device from chat page → verify icon and text update

- [ ] **Step 6: Test settings navigation**

From chat page → click settings icon → should navigate to /settings (not 404)

---

## Task 12: Final Commit — All Fixes

- [ ] **Step 1: Verify all changes committed**

```bash
git status
git log --oneline -5
```

- [ ] **Step 2: Create squash commit message if needed, or verify each commit is clean**

Expected commits:
```
feat(backend): add text_message Socket.IO handler
fix(frontend): correct settings link href to /settings
fix(frontend): add icon and text to device status for accessibility
feat(frontend): add 4-state voice indicator markup
feat(frontend): add CSS for 4 voice states and modal animation
feat(frontend): rewrite mic logic to always-on with mute toggle
feat(frontend): add 4-state voice indicator and real-time waveform
fix(frontend): wire text input to backend via text_message event
```

- [ ] **Step 3: Run final smoke test**

```bash
cd /root/project/home-asisten/backend
source venv/bin/activate
python -c "from app.main import app; print('App OK')"
```

Expected: `App OK`

---

**Plan complete.** All 9 issues mapped to tasks:
1. ✅ Always-on mic → Task 7
2. ✅ Text input → Task 1 + Task 9
3. ✅ Self-mute → Task 10
4. ✅ Auto-resume → Task 10
5. ✅ Real-time waveform → Task 8
6. ✅ 4-state voice indicator → Task 5 + Task 6 + Task 8
7. ✅ Color-only status → Task 3
8. ✅ Settings link → Task 2
9. ✅ Toast auto-dismiss → Task 4 (verified, already correct)

