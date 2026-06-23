(function () {
  'use strict';

  // State
  let devices = [];
  let editingDeviceId = null;

  // ─── Init ───────────────────────────────────────
  function init() {
    lucide.createIcons();
    setupTabs();
    loadDevices();
    setupDeviceForm();
    setupFirmwareForm();
  }

  // ─── Tabs ───────────────────────────────────────
  function setupTabs() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
        btn.classList.add('active');
        document.getElementById('tab-' + btn.dataset.tab).classList.remove('hidden');
      });
    });
  }

  // ─── Device CRUD ────────────────────────────────
  async function loadDevices() {
    try {
      const resp = await fetch('/api/devices');
      if (!resp.ok) throw new Error('Gagal load devices (' + resp.status + ')');
      devices = await resp.json() || [];
      renderDeviceTable();
      loadDeviceDropdown();
    } catch (err) {
      console.error('loadDevices gagal:', err);
      document.getElementById('noDevices').classList.remove('hidden');
    }
  }

  function renderDeviceTable() {
    const tbody = document.getElementById('deviceTableBody');
    const cardsMobile = document.getElementById('deviceCardsMobile');
    const emptyEl = document.getElementById('noDevices');

    if (!devices.length) {
      tbody.innerHTML = '';
      cardsMobile.innerHTML = '';
      emptyEl.classList.remove('hidden');
      return;
    }

    emptyEl.classList.add('hidden');

    // Desktop table view
    tbody.innerHTML = devices.map(d => {
      const on = Object.values(d.state || {}).some(v => v === 'ON');
      const relayNames = d.relay_names || {};
      const relayNamesList = Object.values(relayNames).filter(n => n).join(', ') || `Relay 1-${d.relay_count}`;
      return `<tr class="hover:bg-bg-accent/60 transition-colors">
        <td class="px-6 py-4">
          <p class="text-sm font-medium text-text-main">${d.name}</p>
          <p class="text-xs text-text-muted font-mono">${d.device_id}</p>
          <p class="text-xs text-text-muted mt-1">${relayNamesList}</p>
        </td>
        <td class="px-6 py-4 text-sm text-text-muted">${d.room}</td>
        <td class="px-6 py-4 text-sm text-text-muted capitalize">${d.type}</td>
        <td class="px-6 py-4 text-center">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${on ? 'bg-success/15 text-success' : 'bg-bg-accent text-text-muted border border-border-light'}">
            <span class="w-1.5 h-1.5 rounded-full ${on ? 'bg-success' : 'bg-text-muted'}"></span>${on ? 'ON' : 'OFF'}
          </span>
        </td>
        <td class="px-6 py-4 text-center">
          <div class="flex justify-center gap-2">
            <button onclick="window.editDevice('${d.device_id}')" class="p-2 hover:bg-bg-accent rounded-lg transition-colors cursor-pointer text-text-muted hover:text-primary" aria-label="Edit"><i data-lucide="edit" class="w-4 h-4"></i></button>
            <button onclick="window.deleteDevice('${d.device_id}')" class="p-2 hover:bg-danger/10 rounded-lg transition-colors cursor-pointer text-text-muted hover:text-danger" aria-label="Hapus"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
          </div>
        </td>
      </tr>`;
    }).join('');

    // Mobile card view
    cardsMobile.innerHTML = devices.map(d => {
      const on = Object.values(d.state || {}).some(v => v === 'ON');
      return `<div class="bg-surface border border-border-light rounded-xl p-4 hover:border-primary/40 transition-colors">
        <div class="flex items-start justify-between mb-3">
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-text-main truncate">${d.name}</p>
            <p class="text-xs text-text-muted font-mono truncate">${d.device_id}</p>
          </div>
          <span class="flex-shrink-0 ml-3 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${on ? 'bg-success/15 text-success' : 'bg-bg-accent text-text-muted border border-border-light'}">
            <span class="w-1.5 h-1.5 rounded-full ${on ? 'bg-success' : 'bg-text-muted'}"></span>${on ? 'ON' : 'OFF'}
          </span>
        </div>
        <div class="flex items-center justify-between text-xs text-text-muted mb-3">
          <span><i data-lucide="map-pin" class="w-3 h-3 inline mr-1"></i>${d.room}</span>
          <span class="capitalize"><i data-lucide="cpu" class="w-3 h-3 inline mr-1"></i>${d.type}</span>
        </div>
        <div class="flex gap-2">
          <button onclick="window.editDevice('${d.device_id}')" class="flex-1 py-2 bg-bg-main hover:bg-bg-accent border border-border-light rounded-lg transition-colors cursor-pointer text-xs text-text-main flex items-center justify-center gap-1.5">
            <i data-lucide="edit" class="w-3.5 h-3.5"></i>Edit
          </button>
          <button onclick="window.deleteDevice('${d.device_id}')" class="flex-1 py-2 bg-danger/10 hover:bg-danger/20 border border-danger/20 rounded-lg transition-colors cursor-pointer text-danger text-xs flex items-center justify-center gap-1.5">
            <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>Hapus
          </button>
        </div>
      </div>`;
    }).join('');

    lucide.createIcons();
  }

  window.editDevice = function (id) {
    const d = devices.find(dev => dev.device_id === id);
    if (!d) return;
    editingDeviceId = id;
    document.getElementById('modalTitle').textContent = 'Edit Perangkat';
    document.getElementById('deviceIdOriginal').value = id;
    const deviceIdInput = document.getElementById('dDeviceId');
    deviceIdInput.value = d.device_id;
    deviceIdInput.disabled = true;  // Disable device_id saat edit
    deviceIdInput.classList.add('bg-bg-accent', 'cursor-not-allowed', 'opacity-60');
    document.getElementById('dName').value = d.name;
    document.getElementById('dRoom').value = d.room;
    document.getElementById('dType').value = d.type;
    document.getElementById('dRelayCount').value = d.relay_count;

    // Generate relay name inputs and populate with existing values
    updateRelayNameInputs();
    const relayNames = d.relay_names || {};
    for (let i = 1; i <= d.relay_count; i++) {
      const input = document.getElementById(`relayName_${i}`);
      if (input) {
        input.value = relayNames[`relay_${i}`] || `Relay ${i}`;
      }
    }

    document.getElementById('deviceModal').classList.remove('hidden');
  };

  window.deleteDevice = async function (id) {
    if (!confirm('Hapus perangkat?')) return;
    try {
      await fetch(`/api/devices/${id}`, { method: 'DELETE' });
      loadDevices();
    } catch (_) {}
  };

  window.updateRelayNameInputs = function() {
    const count = parseInt(document.getElementById('dRelayCount').value) || 4;
    const container = document.getElementById('relayNamesContainer');
    container.innerHTML = '';

    for (let i = 1; i <= count; i++) {
      container.innerHTML += `
        <div class="flex items-center gap-2">
          <label class="text-xs text-text-muted w-10 font-medium">R${i}:</label>
          <input type="text" id="relayName_${i}"
                 placeholder="Nama relay ${i}"
                 class="flex-1 bg-bg-main border border-border-light rounded-lg px-3 py-1.5 text-sm text-text-main placeholder-text-muted focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20">
        </div>
      `;
    }
  };

  function setupDeviceForm() {
    // Initialize relay name inputs on load
    updateRelayNameInputs();

    document.getElementById('deviceForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const relayCount = parseInt(document.getElementById('dRelayCount').value) || 4;
      const relay_names = {};
      for (let i = 1; i <= relayCount; i++) {
        const input = document.getElementById(`relayName_${i}`);
        relay_names[`relay_${i}`] = input ? input.value.trim() : `Relay ${i}`;
      }

      const data = {
        name: document.getElementById('dName').value.trim(),
        room: document.getElementById('dRoom').value.trim(),
        type: document.getElementById('dType').value,
        relay_count: relayCount,
        relay_names: relay_names,
      };
      try {
        const editing = editingDeviceId;
        const url = editing ? `/api/devices/${editing}` : '/api/devices';
        const method = editing ? 'PUT' : 'POST';
        const resp = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
        if (!resp.ok) { const err = await resp.json(); alert(err.detail || 'Error'); return; }
        closeDeviceModal();
        loadDevices();
      } catch (_) {}
    });
  }

  window.openDeviceModal = function () {
    editingDeviceId = null;
    document.getElementById('modalTitle').textContent = 'Tambah Perangkat';
    document.getElementById('deviceIdOriginal').value = '';
    document.getElementById('deviceForm').reset();
    document.getElementById('dRelayCount').value = 4;

    // Enable device_id input untuk tambah device baru
    const deviceIdInput = document.getElementById('dDeviceId');
    deviceIdInput.disabled = false;
    deviceIdInput.classList.remove('bg-bg-accent', 'cursor-not-allowed', 'opacity-60');

    // Generate relay name inputs for new device
    updateRelayNameInputs();

    document.getElementById('deviceModal').classList.remove('hidden');
  };

  window.closeDeviceModal = function () {
    document.getElementById('deviceModal').classList.add('hidden');
    editingDeviceId = null;
  };

  // ─── Firmware Upload ────────────────────────────
  async function loadDeviceDropdown() {
    const sel = document.getElementById('targetDevice');
    sel.innerHTML = '<option value="">Pilih perangkat...</option>' + devices.map(d => `<option value="${d.device_id}">${d.name} (${d.device_id})</option>`).join('');
  }

  function setupFirmwareForm() {
    document.getElementById('firmwareForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const deviceId = document.getElementById('targetDevice').value;
      const file = document.getElementById('firmwareFile').files[0];
      if (!deviceId || !file) { alert('Pilih perangkat dan file'); return; }

      const formData = new FormData();
      formData.append('file', file);
      document.getElementById('uploadProgress').classList.remove('hidden');

      try {
        const resp = await fetch(`/api/devices/${deviceId}/firmware`, { method: 'POST', body: formData });
        if (!resp.ok) throw new Error('Upload gagal');
        document.getElementById('progressBar').style.width = '100%';
        document.getElementById('progressPercent').textContent = '100%';
        alert('Firmware berhasil dikirim');
      } catch (err) {
        alert('Error: ' + err.message);
      }
    });
  }

  window.handleFileSelect = function (e) {
    const file = e.target.files[0];
    if (!file) return;
    document.getElementById('filePreview').classList.remove('hidden');
    document.getElementById('fileName').textContent = file.name;
    document.getElementById('fileSize').textContent = formatSize(file.size);
  };

  function formatSize(bytes) { return bytes < 1024 ? bytes + ' B' : bytes < 1048576 ? (bytes / 1024).toFixed(1) + ' KB' : (bytes / 1048576).toFixed(1) + ' MB'; }

  init();
})();