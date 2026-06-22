# ElBot Home Asisten — UI Redesign: OLED Pro

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform 3 pages (chat, settings, login) into a polished, professional dark-mode UI with consistent design tokens, proper spacing, and production-quality interactions.

**Architecture:** Refine existing HTML/CSS/JS — no framework migration. Centralize all tokens into shared Tailwind config, unify fonts to Inter + JetBrains Mono, apply 4dp spacing grid, ensure accessibility compliance.

**Tech Stack:** HTML + TailwindCSS CDN + Vanilla JS + Lucide Icons + Inter/Mono fonts

---

## Design System Reference

### Color Tokens
```
surface:         #0A0F1E
surface-muted:   #111827
surface-raised:  #1E293B
border:          #1E293B
border-accent:   #334155
text-primary:    #F1F5F9
text-secondary:  #94A3B8
text-muted:      #64748B
primary:         #3B82F6
primary-glow:    #60A5FA
secondary:       #10B981
accent:          #F59E0B
danger:          #EF4444
```

### Typography
```
Body:     Inter 400/500/600 (Google Fonts)
Mono:     JetBrains Mono 400/500 (Google Fonts)
Scale:    12/14/16/18/20/24/32px
Line:     1.5 body, 1.25 heading
```

---

## Task Breakdown

### Task 1: Centralize Design Tokens (shared CSS file)

**Files:** Create `frontend/static/css/design-tokens.css`, modify `index.html`, `settings.html`, `login.html`

- [ ] **Step 1: Create shared design tokens file**

Create `frontend/static/css/design-tokens.css`:
```css
/* ElBot Design Tokens — OLED Pro */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --surface: #0A0F1E;
  --surface-muted: #111827;
  --surface-raised: #1E293B;
  --border: #1E293B;
  --border-accent: #334155;
  --text-primary: #F1F5F9;
  --text-secondary: #94A3B8;
  --text-muted: #64748B;
  --primary: #3B82F6;
  --primary-glow: #60A5FA;
  --secondary: #10B981;
  --accent: #F59E0B;
  --danger: #EF4444;
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 20px;
}

body {
  font-family: 'Inter', system-ui, sans-serif;
}

code, pre, .mono {
  font-family: 'JetBrains Mono', monospace;
}

/* Focus ring standard */
*:focus-visible {
  outline: 2px solid var(--primary);
  outline-offset: 2px;
  border-radius: var(--radius-sm);
}

/* Scrollbar standard */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border-accent); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }
```

- [ ] **Step 2: Update Tailwind config in all 3 HTML files**

Replace each page's tailwind.config with unified version:
```javascript
tailwind.config = {
  darkMode: 'class',
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      colors: {
        primary: '#3B82F6',
        secondary: '#10B981',
        accent: '#F59E0B',
        danger: '#EF4444',
        surface: '#0A0F1E',
        'surface-muted': '#111827',
        'surface-raised': '#1E293B',
      },
    },
  },
}
```

- [ ] **Step 3: Remove Fira fonts, load Inter + JetBrains Mono**

Replace font links in index.html and settings.html:
```html
<!-- Remove: Fira Code + Fira Sans -->
<!-- Add: Inter + JetBrains Mono -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
```

- [ ] **Step 4: Link new tokens CSS in all 3 pages**

Add before `styles.css` in each page's `<head>`:
```html
<link rel="stylesheet" href="/static/css/design-tokens.css">
```

- [ ] **Step 5: Commit**

---

### Task 2: Rebuild Login Page (consistent design)

**Files:** Modify `frontend/login.html`

- [ ] **Step 1: Use shared tokens + Inter font**

Remove inline `<style>` block (lines 9-22). Already using design-tokens.css from Task 1.

- [ ] **Step 2: Redesign login card**

Replace full body markup:
```html
<body class="bg-surface text-text-primary font-sans antialiased min-h-screen flex items-center justify-center p-4">
  <div class="w-full max-w-[400px] bg-surface-raised border border-border rounded-2xl p-8 shadow-2xl animate-fade-in">
    <!-- Logo -->
    <div class="text-center mb-8">
      <div class="inline-flex items-center justify-center w-16 h-16 bg-primary/20 rounded-2xl mb-4">
        <i data-lucide="bot" class="w-8 h-8 text-primary"></i>
      </div>
      <h1 class="text-2xl font-semibold text-text-primary mb-1">ElBot</h1>
      <p class="text-sm text-text-secondary">Masuk untuk mengontrol rumah pintar Anda</p>
    </div>

    <!-- Form -->
    <form id="loginForm" class="space-y-5">
      <div>
        <label for="password" class="block text-sm text-text-secondary mb-1.5">Password</label>
        <div class="relative">
          <input type="password" id="password" required
            class="w-full bg-surface border border-border-accent rounded-xl px-4 py-3 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all pr-10"
            placeholder="••••••••">
          <button type="button" onclick="togglePassword()"
            class="absolute right-3 top-1/2 -translate-y-1/2 p-1 hover:bg-slate-700 rounded-lg transition-colors"
            aria-label="Toggle password visibility">
            <i data-lucide="eye-off" id="eyeIcon" class="w-4 h-4 text-text-muted"></i>
          </button>
        </div>
      </div>

      <div id="error-message" class="hidden bg-danger/10 border border-danger/30 text-danger px-4 py-3 rounded-xl text-sm flex items-center gap-2">
        <i data-lucide="alert-circle" class="w-4 h-4 flex-shrink-0"></i>
        <span id="errorText">Password salah</span>
      </div>

      <button type="submit" id="loginBtn"
        class="w-full h-11 bg-primary hover:bg-primary/90 text-white font-medium rounded-xl transition-all flex items-center justify-center gap-2 focus:ring-2 focus:ring-primary/50 disabled:opacity-50 disabled:cursor-not-allowed">
        <span id="loginText">Masuk</span>
        <div id="loginSpinner" class="hidden w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
      </button>
    </form>

    <p class="mt-6 text-center text-xs text-text-muted">
      Default password: <code class="text-text-secondary bg-surface px-2 py-0.5 rounded font-mono text-xs">admin123</code>
    </p>
  </div>

  <script src="https://unpkg.com/lucide@latest"></script>
  <script>
    lucide.createIcons();
    // Login logic + password toggle
  </script>
</body>
```

- [ ] **Step 3: Add password visibility toggle JS**

Add togglePassword function in login script.

- [ ] **Step 4: Commit**

---

### Task 3: Polish Chat Page (index.html)

**Files:** Modify `frontend/index.html`

- [ ] **Step 1: Update body bg to use token**

Change `bg-slate-900` to `bg-surface` on body.

- [ ] **Step 2: Compact header (h-14)**

Remove redundant height, make cleaner:
```html
<header class="fixed top-0 inset-x-0 h-14 bg-surface/95 backdrop-blur-sm border-b border-border z-50">
  <div class="max-w-6xl mx-auto px-4 h-full flex items-center justify-between">
    <div class="flex items-center gap-2.5">
      <div class="w-8 h-8 bg-primary/20 rounded-lg flex items-center justify-center">
        <i data-lucide="bot" class="w-5 h-5 text-primary"></i>
      </div>
      <span class="font-semibold text-sm">ElBot</span>
    </div>
    <div class="flex items-center gap-3">
      <div id="connectionStatus" class="flex items-center gap-1.5 px-2.5 py-1 bg-surface-raised rounded-lg text-xs">
        <span class="w-1.5 h-1.5 bg-secondary rounded-full"></span>
        <span class="text-text-secondary">Online</span>
      </div>
      <a href="/settings" class="w-8 h-8 flex items-center justify-center hover:bg-slate-800 rounded-lg transition-colors" aria-label="Pengaturan">
        <i data-lucide="settings" class="w-4 h-4 text-text-secondary"></i>
      </a>
    </div>
  </div>
</header>
```

- [ ] **Step 3: Remove hardcoded example messages**

Delete placeholder bot welcome + user example + bot response with action (lines 123-163). Chat container becomes:
```html
<div id="chatContainer" class="space-y-4 min-h-[400px]"></div>
```

- [ ] **Step 4: Clean device panel section**

Simplify heading + remove hardcoded example cards, keep only dynamic `#devicePanel`:
```html
<section class="mt-6 mb-8">
  <div class="flex items-center justify-between mb-3">
    <h2 class="text-xs font-medium text-text-muted uppercase tracking-wider">Perangkat Aktif</h2>
    <span id="deviceCount" class="text-xs text-text-muted">0 perangkat</span>
  </div>
  <div id="devicePanel" class="flex gap-3 overflow-x-auto pb-2 scrollbar-none"></div>
</section>
```

- [ ] **Step 5: Refine voice indicator**

Slimmer, cleaner pill:
```html
<div id="voiceIndicator" class="hidden mb-6">
  <div class="flex items-center justify-center gap-2 py-3 px-4 bg-surface-raised border border-border rounded-full max-w-xs mx-auto">
    <div id="waveformBars" class="flex items-center gap-0.5">
      <div class="waveform-bar w-[2px] bg-primary/60 rounded-full" data-bar="0"></div>
      <!-- bars 1-4 same -->
    </div>
    <div id="typingDots" class="hidden flex items-center gap-1">
      <div class="typing-dot w-1.5 h-1.5 bg-accent rounded-full"></div>
      <!-- dots 2-3 -->
    </div>
    <p class="text-xs text-text-secondary ml-1" id="voiceStatus">Mendengarkan...</p>
  </div>
</div>
```

- [ ] **Step 6: Refine input bar**

Compact glass bar, proper touch targets:
```html
<div class="fixed bottom-0 inset-x-0 bg-surface/95 backdrop-blur-sm border-t border-border p-3 z-40">
  <div class="max-w-3xl mx-auto">
    <div class="flex gap-2 items-end">
      <div class="flex-1 relative">
        <textarea id="messageInput" rows="1"
          placeholder="Ketik atau gunakan suara..."
          class="w-full bg-surface-raised border border-border rounded-xl px-4 py-2.5 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary/30 resize-none transition-all"
          aria-label="Ketik pesan"></textarea>
      </div>
      <button id="micButton"
        class="flex-shrink-0 w-11 h-11 bg-surface-raised hover:bg-slate-700 border border-border rounded-xl flex items-center justify-center transition-all group"
        aria-label="Mikrofon">
        <i data-lucide="mic" class="w-5 h-5 mic-icon text-text-secondary group-hover:text-text-primary transition-colors"></i>
      </button>
      <button id="sendButton"
        class="flex-shrink-0 w-11 h-11 bg-primary hover:bg-primary/90 rounded-xl flex items-center justify-center transition-all disabled:opacity-40 disabled:cursor-not-allowed"
        aria-label="Kirim">
        <i data-lucide="send" class="w-5 h-5 text-white"></i>
      </button>
    </div>
  </div>
</div>
```

- [ ] **Step 7: Commit**

---

### Task 4: Polish Settings Page (settings.html)

**Files:** Modify `frontend/settings.html`

- [ ] **Step 1: Update body + header to match new tokens**

Same compact header pattern, bg-surface, etc.

- [ ] **Step 2: Compact tab bar**

```html
<nav class="fixed top-14 inset-x-0 bg-surface/95 backdrop-blur-sm border-b border-border z-40">
  <div class="max-w-6xl mx-auto px-4">
    <div class="flex gap-1">
      <button class="tab-btn active px-4 py-2.5 text-sm font-medium border-b-2 border-primary text-primary transition-colors" data-tab="devices">
        <i data-lucide="cpu" class="w-3.5 h-3.5 inline mr-1.5"></i>Perangkat
      </button>
      <!-- firmware, general tabs same pattern -->
    </div>
  </div>
</nav>
```

- [ ] **Step 3: Improve device table styling**

Zebra stripes, better spacing:
```html
<tbody id="deviceTableBody" class="divide-y divide-border">
  <!-- JS renders rows with: even:bg-surface odd:bg-surface-raised -->
</tbody>
```

- [ ] **Step 4: Improve empty state**

```html
<div id="noDevices" class="hidden py-16 text-center">
  <i data-lucide="cpu" class="w-12 h-12 mx-auto mb-3 text-text-muted"></i>
  <p class="text-text-secondary font-medium mb-1">Belum ada perangkat</p>
  <p class="text-sm text-text-muted mb-4">Tambahkan perangkat ESP32 untuk mulai mengontrol</p>
  <button onclick="openDeviceModal()"
    class="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 rounded-lg text-sm font-medium transition-colors">
    <i data-lucide="plus" class="w-4 h-4"></i>Tambah Perangkat
  </button>
</div>
```

- [ ] **Step 5: Improve firmware upload zone**

Dashed border drop zone:
```html
<div class="border-2 border-dashed border-border-accent rounded-xl p-8 text-center hover:border-primary/50 transition-colors">
  <i data-lucide="upload-cloud" class="w-10 h-10 mx-auto mb-3 text-text-muted"></i>
  <p class="text-sm text-text-secondary mb-1">Seret file .bin ke sini</p>
  <p class="text-xs text-text-muted mb-4">atau</p>
  <label class="inline-flex items-center gap-2 px-4 py-2 bg-primary hover:bg-primary/90 rounded-lg text-sm font-medium transition-colors cursor-pointer">
    <i data-lucide="folder-open" class="w-4 h-4"></i>Pilih File
    <input type="file" id="firmwareFile" accept=".bin" onchange="handleFileSelect(event)" class="hidden">
  </label>
</div>
```

- [ ] **Step 6: Commit**

---

### Task 5: Unify Animations + Visual Polish (styles.css)

**Files:** Modify `frontend/static/css/styles.css`

- [ ] **Step 1: Replace all animation timings with token-friendly values**

Ensure all animations use:
- 150-300ms duration (UX rule §7)
- transform + opacity only (no width/height)
- ease-out for enter, ease-in for exit

- [ ] **Step 2: Add missing animations**

```css
/* Fade-in animation for login card */
@keyframes fade-in {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
.animate-fade-in { animation: fade-in 0.3s ease-out; }

/* Skeleton loading */
@keyframes shimmer {
  0% { background-position: -200% 0; }
  100% { background-position: 200% 0; }
}
.skeleton {
  background: linear-gradient(90deg, var(--surface-raised) 25%, var(--border-accent) 50%, var(--surface-raised) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
}

/* Status badge pulses */
@keyframes status-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
```

- [ ] **Step 3: Add scrollbar-none utility**

```css
.scrollbar-none::-webkit-scrollbar { display: none; }
.scrollbar-none { -ms-overflow-style: none; scrollbar-width: none; }
```

- [ ] **Step 4: Verify reduced-motion media query**

Already present at line 86 — keep exactly as is (UX requirement).

- [ ] **Step 5: Commit**

---

### Task 6: Frontend JS Polish (device cards + UI state)

**Files:** Modify `frontend/static/js/app.js`

- [ ] **Step 1: Update device card rendering**

Add proper status text + icon in renderDeviceCards:
```javascript
function renderDeviceCards(devices) {
  if (!devices.length) {
    devicePanel.innerHTML = '<p class="text-xs text-text-muted py-2">Belum ada perangkat</p>';
    return;
  }
  devicePanel.innerHTML = devices.slice(0, 6).map(d => {
    const on = Object.values(d.state || {}).some(v => v === 'ON');
    return `<div class="flex-shrink-0 w-36 bg-surface-raised border ${on ? 'border-secondary/30' : 'border-border'} rounded-xl p-3 flex flex-col gap-2 hover:border-border-accent transition-colors cursor-pointer" onclick="toggleDevice('${d.device_id}', '${on}')">
      <div class="flex items-center justify-between">
        <i data-lucide="${getDeviceIcon(d.type)}" class="w-4 h-4 ${on ? 'text-secondary' : 'text-text-muted'}"></i>
        <span class="w-2 h-2 ${on ? 'bg-secondary' : 'bg-slate-600'} rounded-full"></span>
      </div>
      <div>
        <p class="text-xs font-medium truncate text-text-primary">${d.name}</p>
        <p class="text-xs ${on ? 'text-secondary font-medium' : 'text-text-muted'}">${on ? 'ON' : 'OFF'}</p>
      </div>
    </div>`;
  }).join('');
  lucide.createIcons();
}
```

- [ ] **Step 2: Update connection status format**

```javascript
socket.on('connect', () => {
  connectionStatus.innerHTML = '<span class="w-1.5 h-1.5 bg-secondary rounded-full"></span><span class="text-text-secondary">Online</span>';
});
socket.on('disconnect', () => {
  connectionStatus.innerHTML = '<span class="w-1.5 h-1.5 bg-danger rounded-full"></span><span class="text-text-secondary">Offline</span>';
});
```

- [ ] **Step 3: Commit**

---

## Verification

After all tasks complete:
1. Restart backend: `cd backend && source venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8500 --reload`
2. Open `http://localhost:8500/login` — verify login page loads clean with Inter font, no Fira
3. Login with `admin123` — verify redirect works
4. Chat page: verify header compact, device cards correct, no hardcoded messages
5. Send a text message — verify chat works, responses in proper bubbles
6. Settings page: verify tabs work, device table styled, firmware upload zone clean
7. Check browser console for errors
8. Test at 375px width (mobile)
9. Verify all touch targets ≥44px
10. Check focus rings visible on all interactive elements

## Summary

| Task | Files | Est. Changes |
|------|-------|-------------|
| 1. Design tokens | `design-tokens.css`, 3 HTML files | ~80 lines new, 30 lines edit |
| 2. Login page | `login.html` | ~30 lines edit |
| 3. Chat page | `index.html` | ~60 lines edit |
| 4. Settings page | `settings.html` | ~40 lines edit |
| 5. Animations | `styles.css` | ~30 lines add, minimal delete |
| 6. Device cards | `app.js` | ~15 lines edit |
| **Total** | 7 files | ~250 lines |

**Key improvements:**
- Unified token system across all pages
- Font upgraded to Inter + JetBrains Mono (more professional than Fira)
- Consistent 44px touch targets (accessibility)
- No hardcoded example content in chat
- Proper visual hierarchy with semantic color usage
- All animations respect reduced-motion