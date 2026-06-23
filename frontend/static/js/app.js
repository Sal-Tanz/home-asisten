// Chat page - Socket.IO & Voice Chat Logic
(function () {
  'use strict';

  // State
  let socket = null;
  let isSpeaking = false;          // Bot is speaking (suppresses VAD)
  let isRecording = false;          // Mic recording active (push-to-start)
  let mediaStream = null;
  let mediaRecorder = null;
  let audioCtx = null;
  let analyser = null;
  let volumeAnimationId = null;
  let buildingBotResponse = false;  // Track bot message building state
  let isProcessingMessage = false;  // Lock: prevent concurrent message sends

  // Voice Activity Detection (VAD) state — segments speech into whole utterances
  let audioChunks = [];
  let segmentStartTime = 0;
  let silenceTimer = null;
  let speechDetected = false;
  const SILENCE_THRESHOLD = -30;    // dB above which audio counts as speech
  const SILENCE_DURATION = 600;      // ms of silence after speech → finalize segment
  const MIN_SEGMENT_MS = 1500;       // minimum segment length to send

  // DOM elements
  const micBtn = document.getElementById('micButton');
  const sendBtn = document.getElementById('sendButton');
  const msgInput = document.getElementById('messageInput');
  const chatContainer = document.getElementById('chatContainer');
  const voiceIndicator = document.getElementById('voiceIndicator');
  const voiceStatus = document.getElementById('voiceStatus');
  const waveformBars = document.getElementById('waveformBars');
  const typingDots = document.getElementById('typingDots');
  const islandIdle = document.getElementById('islandIdle');
  const devicePanel = document.getElementById('devicePanel');
  const connectionStatus = document.getElementById('connectionStatus');

  // ─── Init ───────────────────────────────────────
  async function init() {
    lucide.createIcons();
    loadDevices();
    setupSocket();
    setupInput();
    setupMicToggle();
    autoResizeTextarea();
    window.addEventListener('beforeunload', () => {
      if (volumeAnimationId) cancelAnimationFrame(volumeAnimationId);
      if (silenceTimer) clearTimeout(silenceTimer);
      stopRecording();
      if (audioCtx) audioCtx.close();
    });
  }

  // ─── Socket.IO ──────────────────────────────────
  function setupSocket() {
    socket = io('/', { transports: ['websocket', 'polling'] });

    socket.on('connect', () => {
      connectionStatus.innerHTML = '<span class="w-1.5 h-1.5 bg-primary rounded-full status-online"></span><span class="text-text-muted">Online</span>';
    });
    socket.on('disconnect', () => {
      connectionStatus.innerHTML = '<span class="w-1.5 h-1.5 bg-danger rounded-full"></span><span class="text-text-muted">Offline</span>';

    });

    socket.on('transcript', (data) => {
      stopAudioPlayback();  // interrupt TTS when a new user message arrives
      addMessage('user', data.text);
    });
    // Removed 'response' handler - we use streaming 'text_chunk' instead
    socket.on('text_chunk', (data) => {
      updateLastBotMessage(data.text, false);
    });
    socket.on('status', (data) => {
      handleStatus(data.state);
    });
    socket.on('audio_chunk', (data) => {
      playAudioChunk(data.audio);
    });
    socket.on('audio_done', () => {
      finishAudioPlayback();
    });
    socket.on('error', (data) => {
      showToast(data.message, 'error');
    });
    socket.on('transcription_error', (data) => {
      showToast('Transcription failed: ' + (data.message || 'Unknown error'), 'error');
    });
    socket.on('device_update', () => {
      // A device's state changed (e.g. via AI control) — refresh the panel.
      loadDevices();
    });
  }

  // ─── Messages ───────────────────────────────────
  // Scroll the chat column to the bottom after the next paint, so newly added
  // bubbles and streamed text stay in view. rAF guarantees the DOM/layout has
  // settled before we measure scrollHeight.
  function scrollChatToBottom() {
    requestAnimationFrame(() => {
      chatContainer.scrollTop = chatContainer.scrollHeight;
    });
  }

  function addMessage(role, text) {
    const isUser = role === 'user';
    const div = document.createElement('div');
    div.className = `flex gap-3 max-w-[85%] sm:max-w-[75%] w-fit chat-bubble-enter ${isUser ? 'ml-auto flex-row-reverse' : ''}`;
    div.innerHTML = isUser
      ? `<div class="flex-shrink-0 w-8 h-8 bg-primary/15 rounded-full flex items-center justify-center"><i data-lucide="user" class="w-5 h-5 text-primary"></i></div>
         <div class="w-fit"><div class="bg-primary rounded-2xl rounded-tr-none px-3 py-2 sm:px-4 sm:py-3 shadow-[0_4px_12px_-2px_rgba(8,145,178,0.35)]"><p class="text-sm leading-relaxed text-white">${escapeHtml(text)}</p></div></div>`
      : `<div class="flex-shrink-0 w-8 h-8 bg-primary rounded-full flex items-center justify-center shadow-[0_4px_10px_-2px_rgba(8,145,178,0.4)]"><i data-lucide="bot" class="w-5 h-5 text-white"></i></div>
         <div class="w-fit"><div class="bg-surface rounded-2xl rounded-tl-none px-3 py-2 sm:px-4 sm:py-3 border border-border-light shadow-sm"><p class="text-sm leading-relaxed text-text-main bot-text">${escapeHtml(text)}</p></div></div>`;
    // Append bubble to the end of the chat container.
    chatContainer.append(div);
    scrollChatToBottom();
    lucide.createIcons();
  }

  function updateLastBotMessage(text, isPartial) {
    if (!buildingBotResponse) {
      // Start a NEW bot message bubble
      addMessage('assistant', text);
      buildingBotResponse = true;
      return;
    }
    // Append to existing bot message
    const messages = chatContainer.querySelectorAll('.bot-text');
    const last = messages[messages.length - 1];
    if (!last) { addMessage('assistant', text); buildingBotResponse = true; return; }
    last.textContent += text;
    scrollChatToBottom();
  }

  

  // ─── Voice Activity Detection (VAD) Recording ──
  // Push-to-start mic: clicking the mic button starts/stops recording.
  // While recording, speech is segmented automatically by silence detection;
  // each complete utterance is sent as one binary WebM blob.
  function setupMicToggle() {
    micBtn.addEventListener('click', () => {
      if (isRecording) stopRecording();
      else startRecording();
    });
  }

  async function startRecording() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });

      // AudioContext + AnalyserNode for live volume / silence detection
      audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioCtx.createMediaStreamSource(mediaStream);
      analyser = audioCtx.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.3;
      source.connect(analyser);

      isRecording = true;
      speechDetected = false;
      beginNewSegment();
      monitorSilence();

      // UI: mark recording
      const icon = micBtn.querySelector('.mic-icon');
      icon.setAttribute('data-lucide', 'mic');
      icon.classList.add('text-danger');
      micBtn.setAttribute('aria-label', 'Hentikan merekam');
      lucide.createIcons();
      showVoiceIndicator('listening');
      showToast('Rekaman aktif — bicara kapan saja', 'success');
    } catch (err) {
      console.error('Error starting microphone:', err);
      showToast('Tidak bisa mengakses mikrofon', 'error');
    }
  }

  function beginNewSegment() {
    audioChunks = [];
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus' : 'audio/webm';
    mediaRecorder = new MediaRecorder(mediaStream, { mimeType });

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = () => {
      const duration = Date.now() - segmentStartTime;
      if (audioChunks.length === 0 || duration < MIN_SEGMENT_MS) return;
      const blob = new Blob(audioChunks, { type: 'audio/webm' });
      blob.arrayBuffer().then((buf) => {
        if (socket && socket.connected) {
          socket.emit('audio_data', buf);  // binary ArrayBuffer
        }
      });
    };

    segmentStartTime = Date.now();
    mediaRecorder.start(50);  // small timeslice for finer chunks
  }

  function finalizeSegment() {
    if (mediaRecorder && mediaRecorder.state === 'recording') {
      mediaRecorder.stop();  // triggers onstop → emits segment
    }
  }

  function monitorSilence() {
    if (!isRecording || !analyser) return;

    const freqLength = analyser.frequencyBinCount;       // fftSize/2 — for frequency bars
    const timeLength = analyser.fftSize;                  // fftSize   — for time-domain VAD
    const freqData = new Uint8Array(freqLength);
    const timeData = new Uint8Array(timeLength);

    const check = () => {
      if (!isRecording) return;

      // Waveform visualization (frequency data)
      analyser.getByteFrequencyData(freqData);
      if (waveformBars) {
        const bars = waveformBars.querySelectorAll('.waveform-bar');
        bars.forEach((bar, i) => {
          const freqSlice = freqData.slice(i * 20, (i + 1) * 20);
          const sliceAvg = freqSlice.reduce((a, b) => a + b, 0) / freqSlice.length;
          const height = Math.max(4, (sliceAvg / 255) * 32);
          bar.style.height = height + 'px';
        });
      }

      // RMS volume in dB from time-domain data for VAD
      analyser.getByteTimeDomainData(timeData);
      let sumSquares = 0;
      for (let i = 0; i < timeLength; i++) {
        const normalized = (timeData[i] - 128) / 128;
        sumSquares += normalized * normalized;
      }
      const rms = Math.sqrt(sumSquares / timeLength);
      const db = 20 * Math.log10(Math.max(rms, 1e-10));

      // Suppress VAD while the bot is speaking (avoid capturing TTS output)
      if (db > SILENCE_THRESHOLD && !isSpeaking) {
        if (!speechDetected) {
          speechDetected = true;
          showVoiceIndicator('user_speaking');
        }
        if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
      } else if (speechDetected && !silenceTimer) {
        // Was speaking, now silent → countdown to send
        silenceTimer = setTimeout(() => {
          if (!isRecording) return;
          finalizeSegment();          // stop & send current segment
          setTimeout(() => {
            if (isRecording) {
              beginNewSegment();
              speechDetected = false;
              showVoiceIndicator('listening');
            }
          }, 200);
          silenceTimer = null;
        }, SILENCE_DURATION);
      }

      volumeAnimationId = requestAnimationFrame(check);
    };

    volumeAnimationId = requestAnimationFrame(check);
  }

  function stopRecording() {
    if (!isRecording) return;
    isRecording = false;

    if (silenceTimer) { clearTimeout(silenceTimer); silenceTimer = null; }
    if (volumeAnimationId) { cancelAnimationFrame(volumeAnimationId); volumeAnimationId = null; }

    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    mediaRecorder = null;

    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
    if (audioCtx) {
      audioCtx.close().catch(() => {});
      audioCtx = null;
    }
    analyser = null;

    // UI: back to idle
    const icon = micBtn.querySelector('.mic-icon');
    icon.setAttribute('data-lucide', 'mic');
    icon.classList.remove('text-danger');
    micBtn.setAttribute('aria-label', 'Mulai merekam');
    lucide.createIcons();
    hideVoiceIndicator();
  }

  // ─── Dynamic Island (voice indicator) ────────────
  // State classes drive the pill's morph: is-idle / is-listening /
  // is-user-speaking / is-thinking / is-speaking. The island is always
  // visible — idle shows a small pill, activity expands it.
  const ISLAND_STATES = ['is-idle', 'is-listening', 'is-user-speaking', 'is-thinking', 'is-speaking'];

  function setVoiceState(stateClass) {
    voiceIndicator.classList.remove(...ISLAND_STATES);
    voiceIndicator.classList.add(stateClass);
  }

  // Fade-based visibility toggle (opacity instead of display:none for smooth transitions)
  function setElVisible(el, visible) {
    if (!el) return;
    el.classList.toggle('island-hidden', !visible);
    el.classList.toggle('island-visible', visible);
  }

  function showVoiceIndicator(state) {
    // Always hide the idle dot while an activity state is active.
    setElVisible(islandIdle, false);

    switch (state) {
      case 'listening':
        setVoiceState('is-listening');
        voiceStatus.textContent = 'Mendengarkan...';
        setElVisible(voiceStatus, true);
        setElVisible(waveformBars, true);
        setElVisible(typingDots, false);
        break;
      case 'user_speaking':
        setVoiceState('is-user-speaking');
        voiceStatus.textContent = 'Anda berbicara...';
        setElVisible(voiceStatus, true);
        setElVisible(waveformBars, true);
        setElVisible(typingDots, false);
        break;
      case 'thinking':
        setVoiceState('is-thinking');
        voiceStatus.textContent = 'Berpikir...';
        setElVisible(voiceStatus, true);
        setElVisible(waveformBars, false);
        setElVisible(typingDots, true);
        break;
      case 'speaking':
        setVoiceState('is-speaking');
        voiceStatus.textContent = 'ElBot berbicara...';
        setElVisible(voiceStatus, true);
        setElVisible(waveformBars, true);
        setElVisible(typingDots, false);
        break;
    }
  }

  function hideVoiceIndicator() {
    // Dynamic Island selalu tampil — kembali ke pill idle kecil.
    setVoiceState('is-idle');
    voiceStatus.textContent = 'ElBot';
    setElVisible(voiceStatus, true);
    setElVisible(waveformBars, false);
    setElVisible(typingDots, false);
    setElVisible(islandIdle, true);
  }

  function handleStatus(state) {
    switch (state) {
      case 'transcribing': if (isRecording) showVoiceIndicator('user_speaking'); break;
      case 'thinking':
        buildingBotResponse = false;  // Reset for new bot response
        showVoiceIndicator('thinking');
        break;
      case 'speaking': isSpeaking = true; showVoiceIndicator('speaking'); break;
      case 'listening':
        buildingBotResponse = false;  // Reset for next bot response
        isSpeaking = false;
        isProcessingMessage = false;  // Reset lock
        // Only show listening indicator if mic is actively recording
        if (isRecording) showVoiceIndicator('listening');
        else hideVoiceIndicator();
        break;
    }
  }

  // ─── Audio Playback ─────────────────────────────
  // Separate AudioContext for TTS playback so it works even when not recording.
  let playbackCtx = null;
  function getPlaybackCtx() {
    if (!playbackCtx) {
      playbackCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    return playbackCtx;
  }

  // Queue clauses so they play sequentially (no overlap). Each audio_chunk
  // now carries one complete clause MP3; we decode it and play after the
  // previous one finishes.
  let playbackQueue = [];
  let isPlaying = false;
  let currentSource = null;

  function playAudioChunk(b64Data) {
    playbackQueue.push(b64Data);
    if (!isPlaying) playNextChunk();
  }

  function playNextChunk() {
    if (playbackQueue.length === 0) {
      isPlaying = false;
      currentSource = null;
      return;
    }
    isPlaying = true;
    const b64 = playbackQueue.shift();
    let binary;
    try {
      binary = atob(b64);
    } catch (err) {
      console.error('Audio base64 decode error:', err);
      playNextChunk();
      return;
    }
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    const ctx = getPlaybackCtx();
    ctx.decodeAudioData(
      bytes.buffer,
      (audioBuffer) => {
        const source = ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(ctx.destination);
        source.onended = playNextChunk;   // clause finished → play next
        currentSource = source;
        source.start();
      },
      (err) => {
        console.error('Audio decode error:', err);
        playNextChunk();   // skip bad chunk so queue doesn't stall
      }
    );
  }

  function stopAudioPlayback() {
    playbackQueue = [];
    if (currentSource) {
      try { currentSource.onended = null; currentSource.stop(); } catch (_) {}
      currentSource = null;
    }
    isPlaying = false;
  }

  function finishAudioPlayback() {
    isSpeaking = false;
    // Don't clear the queue here — audio_done means all chunks were sent;
    // let any buffered ones finish. stopAudioPlayback() handles interrupts.
    if (playbackQueue.length === 0 && !isPlaying) hideVoiceIndicator();
  }

  // ─── Text Input ─────────────────────────────────
  function setupInput() {
    msgInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    sendBtn.addEventListener('click', sendMessage);
  }
  function sendMessage() {
    const text = msgInput.value.trim();
    if (!text || !socket?.connected || isProcessingMessage) return;  // Add lock check

    isProcessingMessage = true;  // Set lock
    // Don't add message here - backend will echo via 'transcript' event
    socket.emit('text_message', { text });
    msgInput.value = '';
    msgInput.style.height = 'auto';
  }
  function autoResizeTextarea() {
    msgInput.addEventListener('input', () => { msgInput.style.height = 'auto'; msgInput.style.height = msgInput.scrollHeight + 'px'; });
  }

  // ─── Devices ────────────────────────────────────
  async function loadDevices() {
    try {
      const resp = await fetch('/api/devices');
      if (!resp.ok) return;
      const devices = await resp.json();
      renderDeviceCards(devices);
    } catch (_) { /* auth required */ }
  }
  function renderDeviceCards(devices) {
    if (!devices.length) {
      devicePanel.innerHTML = '<p class="text-xs text-text-muted py-2 col-span-full text-center">Belum ada perangkat</p>';
      return;
    }
    devicePanel.innerHTML = devices.slice(0, 10).map(d => {
      const state = d.state || {};
      const relayCount = d.relay_count || 4;
      const relayNames = d.relay_names || {};
      let relayButtons = '';
      for (let i = 1; i <= relayCount; i++) {
        const relayKey = `relay_${i}`;
        const isOn = state[relayKey] === 'ON';
        const displayName = relayNames[relayKey] || `Relay ${i}`;
        relayButtons += `<button onclick="event.stopPropagation(); toggleRelay('${d.device_id}', '${relayKey}', ${isOn})" class="flex items-center justify-between px-2 py-1.5 rounded-lg ${isOn ? 'bg-primary/10 border border-primary/30' : 'bg-bg-main border border-border-light'} hover:bg-primary/15 transition-colors cursor-pointer">
          <span class="text-xs text-text-main font-medium truncate">${escapeHtml(displayName)}</span>
          <span class="text-[10px] font-bold ${isOn ? 'text-primary' : 'text-text-muted'}">${isOn ? 'ON' : 'OFF'}</span>
        </button>`;
      }
      const anyOn = Object.values(state).some(v => v === 'ON');
      return `<div class="bg-surface border ${anyOn ? 'border-primary/40' : 'border-border-light'} rounded-xl p-3 flex flex-col gap-2 hover:border-primary/50 hover:shadow-md transition-all">
        <div class="flex items-center gap-2">
          <i data-lucide="${getDeviceIcon(d.type)}" class="w-4 h-4 ${anyOn ? 'text-primary' : 'text-text-muted'}"></i>
          <p class="text-xs font-medium truncate text-text-main flex-1">${d.name}</p>
        </div>
        <div class="grid grid-cols-1 gap-1">${relayButtons}</div>
      </div>`;
    }).join('');
    lucide.createIcons();
  }
  function getDeviceIcon(type) {
    const map = { relay: 'zap', lampu: 'lightbulb', sensor: 'thermometer' };
    return map[type] || 'cpu';
  }

  window.toggleRelay = async function (deviceId, relayKey, isOn) {
    try {
      const action = isOn ? 'OFF' : 'ON';
      const resp = await fetch(`/api/devices/${deviceId}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ relay: relayKey, action })
      });
      if (resp.ok) loadDevices();
    } catch (_) {}
  };

  // ─── Utilities ──────────────────────────────────
  function escapeHtml(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
  function showToast(msg, type) {
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3000);
  }

  init();
})();