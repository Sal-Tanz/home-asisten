// Chat page - Socket.IO & Voice Chat Logic
(function () {
  'use strict';

  // State
  let socket = null;
  let isRecording = false;
  let isSpeaking = false;
  let mediaRecorder = null;
  let audioChunks = [];

  // DOM elements
  const micBtn = document.getElementById('micButton');
  const sendBtn = document.getElementById('sendButton');
  const msgInput = document.getElementById('messageInput');
  const chatContainer = document.getElementById('chatContainer');
  const voiceIndicator = document.getElementById('voiceIndicator');
  const voiceStatus = document.getElementById('voiceStatus');
  const devicePanel = document.getElementById('devicePanel');
  const connectionStatus = document.getElementById('connectionStatus');

  // ─── Init ───────────────────────────────────────
  function init() {
    lucide.createIcons();
    loadDevices();
    setupSocket();
    setupInput();
    setupMic();
    autoResizeTextarea();
  }

  // ─── Socket.IO ──────────────────────────────────
  function setupSocket() {
    socket = io('/', { transports: ['websocket', 'polling'] });

    socket.on('connect', () => {
      connectionStatus.innerHTML = '<span class="w-2 h-2 bg-secondary rounded-full"></span>Terhubung';
    });
    socket.on('disconnect', () => {
      connectionStatus.innerHTML = '<span class="w-2 h-2 bg-danger rounded-full"></span>Terputus';
    });

    socket.on('transcript', (data) => {
      addMessage('user', data.text);
    });
    socket.on('response', (data) => {
      addMessage('assistant', data.text);
    });
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
    div.className = `flex gap-3 max-w-2xl chat-bubble-enter ${isUser ? 'ml-auto flex-row-reverse' : ''}`;
    div.innerHTML = isUser
      ? `<div class="flex-shrink-0 w-8 h-8 bg-slate-700 rounded-full flex items-center justify-center"><i data-lucide="user" class="w-5 h-5 text-slate-300"></i></div>
         <div class="flex-1"><div class="bg-primary rounded-2xl rounded-tr-none px-4 py-3"><p class="text-sm leading-relaxed">${escapeHtml(text)}</p></div></div>`
      : `<div class="flex-shrink-0 w-8 h-8 bg-primary rounded-full flex items-center justify-center"><i data-lucide="bot" class="w-5 h-5 text-white"></i></div>
         <div class="flex-1"><div class="bg-slate-800 rounded-2xl rounded-tl-none px-4 py-3"><p class="text-sm leading-relaxed bot-text">${escapeHtml(text)}</p></div></div>`;
    chatContainer.appendChild(div);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    lucide.createIcons();
  }

  function updateLastBotMessage(text, isPartial) {
    const messages = chatContainer.querySelectorAll('.bot-text');
    const last = messages[messages.length - 1];
    if (!last) { addMessage('assistant', text); return; }
    last.textContent += text;
    chatContainer.scrollTop = chatContainer.scrollHeight;
  }

  // ─── Mic / Recording ────────────────────────────
  async function setupMic() {
    micBtn.addEventListener('click', async () => {
      if (isRecording) stopRecording();
      else startRecording();
    });
  }

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
      });
      mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm;codecs=opus' });
      audioChunks = [];
      mediaRecorder.ondataavailable = (e) => { if (e.data.size > 0) audioChunks.push(e.data); };
      mediaRecorder.onstop = () => {
        const blob = new Blob(audioChunks, { type: 'audio/webm' });
        const reader = new FileReader();
        reader.onloadend = () => {
          const base64 = reader.result.split(',')[1];
          socket.emit('audio_data', { audio: base64 });
        };
        reader.readAsDataURL(blob);
        stream.getTracks().forEach(t => t.stop());
      };
      mediaRecorder.start();
      isRecording = true;
      micBtn.querySelector('i').setAttribute('data-lucide', 'mic-off');
      micBtn.classList.add('text-danger');
      showVoiceIndicator('Mendengarkan...');
    } catch (err) {
      showToast('Tidak bisa mengakses mikrofon', 'error');
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') { mediaRecorder.stop(); isRecording = false; }
    micBtn.querySelector('i').setAttribute('data-lucide', 'mic');
    micBtn.classList.remove('text-danger');
    hideVoiceIndicator();
    lucide.createIcons();
  }

  // ─── Voice Indicator ────────────────────────────
  function showVoiceIndicator(statusText) {
    voiceIndicator.classList.remove('hidden');
    voiceStatus.textContent = statusText;
  }
  function hideVoiceIndicator() {
    voiceIndicator.classList.add('hidden');
  }
  function handleStatus(state) {
    switch (state) {
      case 'transcribing': showVoiceIndicator('Mengenali ucapan...'); break;
      case 'thinking': showVoiceIndicator('Berpikir...'); break;
      case 'speaking': isSpeaking = true; showVoiceIndicator('ElBot berbicara...'); break;
      case 'listening': isSpeaking = false; hideVoiceIndicator(); break;
    }
  }

  // ─── Audio Playback ─────────────────────────────
  const audioContext = new (window.AudioContext || window.webkitAudioContext)();
  let audioQueue = [];

  async function playAudioChunk(hexData) {
    const bytes = new Uint8Array(hexData.match(/.{1,2}/g).map(b => parseInt(b, 16)));
    try {
      const audioBuffer = await audioContext.decodeAudioData(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength));
      const source = audioContext.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(audioContext.destination);
      source.start();
      source.onended = () => {
        if (audioQueue.length > 0) {
          const next = audioQueue.shift();
          next();
        }
      };
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
  }
  function sendMessage() {
    const text = msgInput.value.trim();
    if (!text) return;
    addMessage('user', text);
    // For text-only mode, send via Socket.IO or REST
    // Currently handled via Socket.IO emit (placeholder)
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
    if (!devices.length) return;
    devicePanel.innerHTML = devices.slice(0, 6).map(d => {
      const on = Object.values(d.state || {}).some(v => v === 'ON');
      return `<div class="flex-shrink-0 w-32 h-24 bg-slate-800 border ${on ? 'border-secondary' : 'border-slate-700'} rounded-xl p-3 flex flex-col justify-between hover:border-slate-600 transition-colors cursor-pointer" onclick="toggleDevice('${d.device_id}', '${on}')">
        <div class="flex items-center justify-between">
          <i data-lucide="${getDeviceIcon(d.type)}" class="w-5 h-5 ${on ? 'text-secondary' : 'text-slate-400'}"></i>
          <span class="w-2 h-2 ${on ? 'bg-secondary' : 'bg-danger'} rounded-full"></span>
        </div>
        <div><p class="text-xs font-medium truncate">${d.name}</p><p class="text-xs ${on ? 'text-secondary' : 'text-slate-400'}">${on ? 'ON' : 'OFF'}</p></div>
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
      const resp = await fetch(`/api/devices/${deviceId}/control`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ relay: 'relay_1', action: isOn ? 'OFF' : 'ON' })
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