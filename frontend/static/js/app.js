// Chat page - Socket.IO & Voice Chat Logic
(function () {
  'use strict';

  // State
  let socket = null;
  let isMuted = false;
  let isSpeaking = false;
  let mediaStream = null;
  let mediaRecorder = null;
  let audioCtx = null;
  let analyser = null;
  let volumeAnimationId = null;
  let buildingBotResponse = false;  // Track bot message building state
  let wasManuallyMuted = false;  // Track if user manually muted (vs auto-mute from typing)
  let isProcessingMessage = false;  // Lock: prevent concurrent message sends

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
    await startListening();  // Auto-start mic on page load
    setupMuteToggle();
    autoResizeTextarea();
    window.addEventListener('beforeunload', () => {
      if (volumeAnimationId) cancelAnimationFrame(volumeAnimationId);
      if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
      if (audioCtx) audioCtx.close();
    });
  }

  // ─── Socket.IO ──────────────────────────────────
  function setupSocket() {
    socket = io('/', { transports: ['websocket', 'polling'] });

    socket.on('connect', () => {
      connectionStatus.innerHTML = '<span class="w-1.5 h-1.5 bg-secondary rounded-full"></span><span class="text-slate-400">Online</span>';
    });
    socket.on('disconnect', () => {
      connectionStatus.innerHTML = '<span class="w-1.5 h-1.5 bg-danger rounded-full"></span><span class="text-slate-400">Offline</span>';
    });

    socket.on('transcript', (data) => {
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
  }

  // ─── Messages ───────────────────────────────────
  function addMessage(role, text) {
    const isUser = role === 'user';
    const div = document.createElement('div');
    div.className = `flex gap-3 max-w-[85%] sm:max-w-[75%] chat-bubble-enter ${isUser ? 'ml-auto flex-row-reverse' : ''}`;
    div.innerHTML = isUser
      ? `<div class="flex-shrink-0 w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center"><i data-lucide="user" class="w-5 h-5 text-slate-300"></i></div>
         <div class="flex-1"><div class="bg-primary rounded-2xl rounded-tr-none px-3 py-2 sm:px-4 sm:py-3"><p class="text-sm leading-relaxed">${escapeHtml(text)}</p></div></div>`
      : `<div class="flex-shrink-0 w-8 h-8 bg-primary rounded-full flex items-center justify-center"><i data-lucide="bot" class="w-5 h-5 text-white"></i></div>
         <div class="flex-1"><div class="bg-slate-800 rounded-2xl rounded-tl-none px-3 py-2 sm:px-4 sm:py-3"><p class="text-sm leading-relaxed bot-text">${escapeHtml(text)}</p></div></div>`;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
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
    chatContainer.scrollTop = chatContainer.scrollHeight;
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
      if (isMuted) {
        unmuteMic();
      } else {
        muteMic();
        wasManuallyMuted = true;  // Mark as manual mute
      }
    });
  }

  function muteMic() {
    isMuted = true;
    if (mediaStream) {
      mediaStream.getTracks().forEach(t => t.enabled = false);
    }
    micBtn.querySelector('.mic-icon').setAttribute('data-lucide', 'mic-off');
    micBtn.querySelector('.mic-icon').classList.add('text-danger');
    micBtn.setAttribute('aria-label', 'Unmute mikrofon');
    hideVoiceIndicator();
    lucide.createIcons();
  }

  function unmuteMic() {
    isMuted = false;
    wasManuallyMuted = false;
    mediaStream.getTracks().forEach(t => t.enabled = true);
    micBtn.querySelector('.mic-icon').setAttribute('data-lucide', 'mic');
    micBtn.querySelector('.mic-icon').classList.remove('text-danger');
    micBtn.setAttribute('aria-label', 'Mute mikrofon');
    showVoiceIndicator('listening');
    lucide.createIcons();
  }

  function trackVolume() {
    if (!analyser) return;

    const dataArray = new Uint8Array(analyser.frequencyBinCount);

    function updateBars() {
      analyser.getByteFrequencyData(dataArray);

      // Update waveform bar heights (5 bars)
      if (waveformBars) {
        const bars = waveformBars.querySelectorAll('.waveform-bar');
        bars.forEach((bar, i) => {
          // Vary each bar slightly based on its position in frequency spectrum
          const freqSlice = dataArray.slice(i * 20, (i + 1) * 20);
          const sliceAvg = freqSlice.reduce((a, b) => a + b, 0) / freqSlice.length;
          const height = Math.max(4, (sliceAvg / 255) * 32);
          bar.style.height = height + 'px';
        });
      }

      volumeAnimationId = requestAnimationFrame(updateBars);
    }

    volumeAnimationId = requestAnimationFrame(updateBars);
  }

  // ─── Voice Indicator (4 States) ─────────────────
  function showVoiceIndicator(state) {
    voiceIndicator.classList.remove('hidden',
      'voice-listening', 'voice-user-speaking', 'voice-thinking', 'voice-speaking');

    switch (state) {
      case 'listening':
        voiceIndicator.classList.add('voice-listening');
        voiceStatus.textContent = 'Mendengarkan...';
        if (waveformBars) waveformBars.classList.remove('hidden');
        if (typingDots) typingDots.classList.add('hidden');
        break;
      case 'user_speaking':
        voiceIndicator.classList.add('voice-user-speaking');
        voiceStatus.textContent = 'Anda berbicara...';
        if (waveformBars) waveformBars.classList.remove('hidden');
        if (typingDots) typingDots.classList.add('hidden');
        break;
      case 'thinking':
        voiceIndicator.classList.add('voice-thinking');
        voiceStatus.textContent = 'Berpikir...';
        if (waveformBars) waveformBars.classList.add('hidden');
        if (typingDots) typingDots.classList.remove('hidden');
        break;
      case 'speaking':
        voiceIndicator.classList.add('voice-speaking');
        voiceStatus.textContent = 'ElBot berbicara...';
        if (waveformBars) waveformBars.classList.remove('hidden');
        if (typingDots) typingDots.classList.add('hidden');
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
      case 'thinking':
        buildingBotResponse = false;  // Reset for new bot response
        showVoiceIndicator('thinking');
        break;
      case 'speaking': isSpeaking = true; showVoiceIndicator('speaking'); break;
      case 'listening':
        buildingBotResponse = false;  // Reset for next bot response
        isSpeaking = false;
        isProcessingMessage = false;  // Reset lock
        showVoiceIndicator('listening');
        break;
    }
  }

  // ─── Audio Playback ─────────────────────────────
  let audioQueue = [];

  async function playAudioChunk(b64Data) {
    try {
      const binary = atob(b64Data);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
      const audioBuffer = await audioCtx.decodeAudioData(bytes.buffer);
      const source = audioCtx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioCtx.destination);
      source.start();
    } catch (_) { /* skip decode errors */ }
  }

  function finishAudioPlayback() {
    isSpeaking = false;
    hideVoiceIndicator();
  }

  // ─── Text Input ─────────────────────────────────
  function setupInput() {
    msgInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    sendBtn.addEventListener('click', sendMessage);

    // Auto-mute mic when typing to prevent double transcript (text + voice)
    msgInput.addEventListener('focus', () => {
      if (!isMuted) {
        muteMic();
        wasManuallyMuted = false;  // Mark as auto-mute, not manual
      }
    });
    msgInput.addEventListener('blur', () => {
      setTimeout(() => {
        if (!wasManuallyMuted && isMuted) {
          unmuteMic();  // Auto-unmute if it was auto-muted
        }
      }, 100);  // Small delay to prevent premature unmute during send
    });
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
      devicePanel.innerHTML = '<p class="text-xs text-slate-500 py-2 col-span-full">Belum ada perangkat</p>';
      return;
    }
    devicePanel.innerHTML = devices.slice(0, 10).map(d => {
      const on = Object.values(d.state || {}).some(v => v === 'ON');
      return `<div class="bg-slate-800 border ${on ? 'border-secondary/30' : 'border-slate-700'} rounded-xl p-3 flex flex-col gap-2 hover:border-slate-600 transition-colors cursor-pointer" onclick="toggleDevice('${d.device_id}', '${on}')">
        <div class="flex items-center justify-between">
          <i data-lucide="${getDeviceIcon(d.type)}" class="w-4 h-4 ${on ? 'text-secondary' : 'text-slate-500'}"></i>
          <span class="w-2 h-2 ${on ? 'bg-secondary' : 'bg-slate-600'} rounded-full"></span>
        </div>
        <div>
          <p class="text-xs font-medium truncate text-slate-200">${d.name}</p>
          <p class="text-xs ${on ? 'text-secondary font-medium' : 'text-slate-500'}">${on ? 'ON' : 'OFF'}</p>
        </div>
      </div>`;
    }).join('');
    lucide.createIcons();
  }
  function getDeviceIcon(type) {
    const map = { relay: 'zap', lampu: 'lightbulb', sensor: 'thermometer' };
    return map[type] || 'cpu';
  }

  window.toggleDevice = async function (deviceId, isOn) {
    try {
      const action = isOn === 'true' ? 'OFF' : 'ON';
      const resp = await fetch(`/api/devices/${deviceId}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ relay: 'relay_1', action })
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