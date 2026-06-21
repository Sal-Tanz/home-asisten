# ElBot Home Asisten - Web UI Design System

## Design Philosophy

**Modern Smart Home Assistant** - Clean, intuitive, voice-first interface for Indonesian smart home control.

### Core Principles
- **Voice-First**: Prominent mic button, visual feedback for listening/speaking states
- **Device-Centric**: Quick access to device controls without deep navigation
- **Dark Mode**: Professional, modern aesthetic suitable for home automation
- **Responsive**: Works on desktop, tablet, and mobile
- **Bahasa Indonesia**: All UI text in Indonesian

## Color Palette

### Primary Colors (Dark Mode)
```
Background: #0F172A (slate-900)
Surface: #1E293B (slate-800)
Card: #334155 (slate-700)
Primary: #3B82F6 (blue-500) - Actions, active states
Secondary: #10B981 (emerald-500) - Success, device ON
Accent: #F59E0B (amber-500) - Warnings, attention
Danger: #EF4444 (red-500) - Errors, device OFF
```

### Text Colors (Dark Mode)
```
Primary Text: #F1F5F9 (slate-100)
Secondary Text: #CBD5E1 (slate-300)
Muted Text: #94A3B8 (slate-400)
Disabled Text: #64748B (slate-500)
```

### Light Mode (Auto via prefers-color-scheme)
```
Background: #FFFFFF
Surface: #F8FAFC (slate-50)
Card: #FFFFFF
Primary: #2563EB (blue-600)
Text: #0F172A (slate-900)
```

## Typography

### Font Stack
```
Font Family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif
Fallback: system-ui, sans-serif
```

### Scale
```
Display: 36px / 700 (weight) - Page titles
H1: 30px / 600 - Section headers
H2: 24px / 600 - Card titles
H3: 20px / 600 - Subsections
Body: 16px / 400 - Main text
Small: 14px / 400 - Captions, labels
Caption: 12px / 500 - Metadata, timestamps
```

## Spacing System

```
xs: 4px (0.25rem)
sm: 8px (0.5rem)
md: 16px (1rem)
lg: 24px (1.5rem)
xl: 32px (2rem)
2xl: 48px (3rem)
```

## Component Patterns

### Buttons
```
Primary: bg-blue-500 hover:bg-blue-600 text-white
Secondary: bg-slate-700 hover:bg-slate-600 text-slate-100
Danger: bg-red-500 hover:bg-red-600 text-white
Ghost: hover:bg-slate-700 text-slate-300
```

### Cards
```
Default: bg-slate-800 border border-slate-700 rounded-xl p-6
Interactive: hover:border-slate-600 hover:shadow-lg transition-all
```

### Inputs
```
Default: bg-slate-900 border border-slate-700 rounded-lg px-4 py-2
Focus: border-blue-500 ring-2 ring-blue-500/20
Error: border-red-500 ring-2 ring-red-500/20
```

## Layout Grid

### Desktop (1280px+)
```
Sidebar: 280px fixed
Main Content: flex-1
Max Width: 1600px centered
```

### Tablet (768px-1279px)
```
Sidebar: Collapsible (64px icons only)
Main Content: full width
```

### Mobile (<768px)
```
Sidebar: Bottom navigation bar
Main Content: full width, stacked
```

## Page Structure

### Chat Page (Home)
```
┌─────────────────────────────────────┐
│ Header: Logo + Status + Settings   │
├─────────────────────────────────────┤
│                                     │
│  Device Quick Status (horizontal)   │
│  [Device1] [Device2] [Device3]      │
│                                     │
├─────────────────────────────────────┤
│                                     │
│  Chat Messages Area                 │
│  ┌─────────────────────────────┐   │
│  │ User message (right)        │   │
│  │ Bot message (left)          │   │
│  │ Voice indicator             │   │
│  └─────────────────────────────┘   │
│                                     │
├─────────────────────────────────────┤
│  Input Area                         │
│  [Text Input] [Mic Button] [Send]  │
└─────────────────────────────────────┘
```

### Settings Page
```
┌─────────────────────────────────────┐
│ Header: "Pengaturan"               │
├─────────────────────────────────────┤
│  Tabs: [Perangkat] [Firmware] [Umum]│
├─────────────────────────────────────┤
│                                     │
│  Tab Content                        │
│  - Perangkat: Device CRUD table     │
│  - Firmware: OTA upload UI          │
│  - Umum: General settings           │
│                                     │
└─────────────────────────────────────┘
```

## Icons

Use **Lucide Icons** (lucide.dev) via CDN or inline SVG:
- Home, MessageCircle, Settings, Plus, Edit, Trash2
- Power, Wifi, WifiOff, Mic, MicOff, Volume2
- Upload, Download, Check, X, AlertCircle

## Animations

```
Transitions: 200-300ms ease-in-out
Hover: scale(1.02) for cards
Active: scale(0.98) for buttons
Loading: animate-pulse for skeletons
Voice Listening: animate-pulse + ring animation
```

## Accessibility

- All interactive elements: min 44x44px touch target
- Color contrast: 4.5:1 minimum (WCAG AA)
- Focus visible: ring-2 ring-blue-500
- ARIA labels for icon-only buttons
- Keyboard navigation support

## Tech Stack

- **Framework**: Vanilla JS + HTML (no build step, per spec)
- **Styling**: Tailwind CSS via CDN
- **Icons**: Lucide Icons via CDN
- **Real-time**: Socket.IO client
- **State**: Plain JS objects (no framework)

## Implementation Notes

1. **No build tools** - Direct HTML/CSS/JS, served by FastAPI
2. **Socket.IO** - Connect to backend for real-time updates
3. **Web Audio API** - For microphone recording and playback
4. **LocalStorage** - For user preferences (theme, last device)
5. **Fetch API** - For REST endpoints (device CRUD, firmware upload)
