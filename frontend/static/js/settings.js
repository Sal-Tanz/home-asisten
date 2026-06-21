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
    loadDeviceDropdown();
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
      if (!resp.ok) throw new Error('Gagal load devices');
      devices = await resp.json();
      renderDeviceTable();
    } catch (_) {
      document.getElementById('noDevices').classList.remove('hidden');
    }
  }

  function renderDeviceTable() {
    const tbody = document.getElementById('deviceTableBody');
    const emptyEl = document.getElementById('noDevices');
    if (!devices.length) { tbody.innerHTML = ''; emptyEl.classList.remove('hidden'); return; }
    emptyEl.classList.add('hidden');

    tbody.innerHTML = devices.map(d => {
      const on = Object.values(d.state || {}).some(v => v === 'ON');
      return `<tr class="hover:bg-slate-700/50 transition-colors">
        <td class="px-6 py-4"><p class="text-sm font-medium">${d.name}</p><p class="text-xs text-slate-400 font-mono">${d.device_id}</p></td>
        <td class="px-6 py-4 text-sm text-slate-300">${d.room}</td>
        <td class="px-6 py-4 text-sm text-slate-300 capitalize">${d.type}</td>
        <td class="px-6 py-4 text-center">
          <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${on ? 'bg-secondary/20 text-secondary' : 'bg-slate-700 text-slate-400'}">
            <span class="w-1.5 h-1.5 rounded-full ${on ? 'bg-secondary' : 'bg-slate-500'}"></span>${on ? 'ON' : 'OFF'}
          </span>
        </td>
        <td class="px-6 py-4 text-center">
          <div class="flex justify-center gap-2">
            <button onclick="window.editDevice('${d.device_id}')" class="p-2 hover:bg-slate-600 rounded-lg transition-colors cursor-pointer" aria-label="Edit"><i data-lucide="edit" class="w-4 h-4"></i></button>
            <button onclick="window.deleteDevice('${d.device_id}')" class="p-2 hover:bg-danger/20 rounded-lg transition-colors cursor-pointer text-slate-400 hover:text-danger" aria-label="Hapus"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
          </div>
        </td>
      </tr>`;
    }).join('');
    lucide.createIcons();
  }

  window.editDevice = function (id) {
    const d = devices.find(dev => dev.device_id === id);
    if (!d) return;
    editingDeviceId = id;
    document.getElementById('modalTitle').textContent = 'Edit Perangkat';
    document.getElementById('deviceIdOriginal').value = id;
    document.getElementById('dDeviceId').value = d.device_id;
    document.getElementById('dName').value = d.name;
    document.getElementById('dRoom').value = d.room;
    document.getElementById('dType').value = d.type;
    document.getElementById('dRelayCount').value = d.relay_count;
    document.getElementById('deviceModal').classList.remove('hidden');
  };

  window.deleteDevice = async function (id) {
    if (!confirm('Hapus perangkat?')) return;
    try {
      await fetch(`/api/devices/${id}`, { method: 'DELETE' });
      loadDevices();
    } catch (_) {}
  };

  function setupDeviceForm() {
    document.getElementById('deviceForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const data = {
        device_id: document.getElementById('dDeviceId').value.trim(),
        name: document.getElementById('dName').value.trim(),
        room: document.getElementById('dRoom').value.trim(),
        type: document.getElementById('dType').value,
        relay_count: parseInt(document.getElementById('dRelayCount').value) || 4,
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