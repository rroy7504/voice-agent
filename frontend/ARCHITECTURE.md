# Frontend Architecture

## Overview

A React 19 + TypeScript single-page application with two interfaces: a **customer call page** (voice + text chat with an AI agent) and an **agent dashboard** (real-time monitoring and override controls). Built with Vite, using native WebSocket and Web Audio API for real-time bidirectional audio streaming.

```
┌─────────────────────────────────────────────────────────────────┐
│  Browser                                                        │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  React Router                                             │  │
│  │                                                           │  │
│  │  /  ──────────────>  CustomerCallPage                     │  │
│  │  /dashboard  ──────>  DashboardPage                       │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ CustomerCallPage ────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  useCallWebSocket (hook)                                  │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐   │  │
│  │  │ Mic Capture  │  │ Audio        │  │ WebSocket      │   │  │
│  │  │ (AudioWorklet│  │ Playback     │  │ /ws/call       │   │  │
│  │  │  48k→16k PCM)│  │ (24k PCM)    │  │ (binary+JSON)  │   │  │
│  │  └──────┬───────┘  └──────▲───────┘  └───┬──────▲─────┘   │  │
│  │         │                 │               │      │         │  │
│  │         │    ┌────────────┴───────────┐   │      │         │  │
│  │         │    │ VAD (Voice Activity    │   │      │         │  │
│  │         │    │ Detection) ──> kills   │   │      │         │  │
│  │         │    │ playback on interrupt  │   │      │         │  │
│  │         │    └────────────────────────┘   │      │         │  │
│  │         │                                 │      │         │  │
│  │         └──── binary PCM ─────────────────┘      │         │  │
│  │                                                  │         │  │
│  │  ┌───────────────────────────────────────────────┴──────┐  │  │
│  │  │  useReducer (CustomerCallState)                      │  │  │
│  │  │  ┌────────────┐ ┌──────────┐ ┌───────────────────┐   │  │  │
│  │  │  │ transcript │ │ status   │ │ notification      │   │  │  │
│  │  │  │ (merged    │ │ (idle →  │ │ (post-call        │   │  │  │
│  │  │  │  chunks)   │ │  active) │ │  summary)         │   │  │  │
│  │  │  └────────────┘ └──────────┘ └───────────────────┘   │  │  │
│  │  └──────────────────────────────────────────────────────┘  │  │
│  │                                                           │  │
│  │  ┌─ UI ────────────────────────────────────────────────┐  │  │
│  │  │  Status Bar (connected/mic/processing)              │  │  │
│  │  │  Chat Bubbles (user right, agent left)              │  │  │
│  │  │  Text Input + Send Button                           │  │  │
│  │  │  Start/End Call Button                              │  │  │
│  │  │  Post-Call Notification Card                        │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌─ DashboardPage ───────────────────────────────────────────┐  │
│  │                                                           │  │
│  │  useWebSocket (hook) ── /ws/dashboard (read-only)         │  │
│  │                                                           │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐   │  │
│  │  │ CallStatus  │  │ OverrideBar  │  │ TranscriptPanel│   │  │
│  │  └─────────────┘  └──────────────┘  └────────────────┘   │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐   │  │
│  │  │ ToolCallLog │  │ CoveragePanel│  │ ActionPanel    │   │  │
│  │  └─────────────┘  └──────────────┘  └────────────────┘   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│                       ▼ WebSocket ▼                             │
└─────────────────────────────────────────────────────────────────┘
                        │
                        ▼
              Backend (FastAPI :8000)
```

---

## Directory Structure

```
frontend/
├── index.html                          # Root HTML, mounts #root
├── package.json                        # React 19, Vite 8, react-router-dom 7
├── vite.config.ts                      # Dev proxy: /ws → ws://localhost:8000
├── tsconfig.json                       # Composite TS config
├── public/
│   ├── pcm-worklet-processor.js        # AudioWorklet: resample + Int16 encode
│   ├── favicon.svg
│   └── icons.svg
└── src/
    ├── main.tsx                        # React root, StrictMode
    ├── App.tsx                         # Router: / and /dashboard
    ├── index.css                       # Global dark theme, scrollbar styling
    ├── types/
    │   └── index.ts                    # All shared TypeScript interfaces
    ├── pages/
    │   ├── CustomerCallPage.tsx        # Voice call UI (customer-facing)
    │   └── DashboardPage.tsx           # Monitoring UI (agent-facing)
    ├── hooks/
    │   ├── useCallWebSocket.ts         # Call hook: audio, VAD, transcript sync
    │   └── useWebSocket.ts             # Dashboard hook: event stream + reconnect
    └── components/
        ├── CallStatus.tsx              # Status badge with indicator dot
        ├── TranscriptPanel.tsx         # Scrollable transcript (dashboard)
        ├── ToolCallLog.tsx             # Expandable tool call list
        ├── CoveragePanel.tsx           # Coverage decision + confidence bar
        ├── ActionPanel.tsx             # Dispatch details + notification
        └── OverrideBar.tsx             # Approve/Deny/Escalate buttons
```

---

## Control Flow: Customer Call

### 1. Call Initiation (`startCall`)

User clicks "Start Call", which triggers this sequence **inside a user gesture** (important for browser audio policy):

```
User clicks "Start Call"
        │
        ├── 1. dispatch(RESET)  — clear all previous state
        │
        ├── 2. Create playback AudioContext (24kHz)
        │       └── Create GainNode (volume control + interrupt target)
        │
        ├── 3. Open WebSocket to ws://localhost:8000/ws/call
        │       └── Wait for onopen → dispatch(CONNECTED)
        │
        ├── 4. Set up ws.onmessage handler
        │       ├── ArrayBuffer → playAudioChunk()
        │       └── JSON string → dispatch by event_type
        │
        ├── 5. getUserMedia({ audio: { echoCancellation, noiseSuppression, autoGainControl } })
        │
        ├── 6. Create mic AudioContext (48kHz)
        │       └── Load AudioWorklet: pcm-worklet-processor.js
        │
        ├── 7. Connect: mic stream → MediaStreamSource → AudioWorkletNode
        │       └── worklet.port.onmessage → VAD check → ws.send(pcmBuffer)
        │
        └── 8. dispatch(MIC_ACTIVE)
```

### 2. Audio Pipeline

#### Mic → Backend (Outbound)

```
Microphone (48kHz Float32)
    │
    ▼
AudioWorkletNode ("pcm-processor")
    │  Accumulates samples in buffer (2048 samples)
    │  Resamples 48kHz → 16kHz via linear interpolation
    │  Converts Float32 → Int16 PCM
    │
    ▼
worklet.port.postMessage(pcm16.buffer)
    │
    ▼
Main thread: worklet.port.onmessage
    │
    ├── Compute RMS energy for VAD
    │   (see Voice Activity Detection below)
    │
    └── ws.send(pcmBuffer)  →  Backend  →  Gemini Live
```

#### Backend → Speaker (Inbound)

```
Gemini Live  →  Backend  →  ws.onmessage (ArrayBuffer)
    │
    ▼
playAudioChunk(pcmData)
    │
    ├── Convert Int16 → Float32
    │
    ├── Create AudioBuffer (24kHz, mono)
    │
    ├── Create BufferSource → connect to GainNode → destination
    │
    └── Schedule: source.start(startTime)
        │  startTime = max(now + 0.01, nextPlayTimeRef)
        │  nextPlayTimeRef = startTime + buffer.duration
        │
        └── Gapless playback via sequential scheduling
```

### 3. Voice Activity Detection (VAD)

Detects when the user starts speaking and interrupts agent audio playback.

```
Every mic PCM frame (~50ms):
    │
    ├── Compute RMS: sqrt(sum(sample²) / N)
    │
    ├── If RMS > 800 (Int16 scale):
    │       loudFrameCount++
    │       │
    │       └── If loudFrameCount >= 3 (~150ms sustained):
    │               interruptPlayback()
    │
    └── If RMS <= 800:
            loudFrameCount = 0  (reset)
```

**`interruptPlayback()`** does three things:
1. **Disconnect GainNode** — instantly silences all scheduled audio sources
2. **Create new GainNode** — future audio connects here
3. **Reset `nextPlayTimeRef`** — next chunk plays immediately, not at old queue position
4. **Clear pending transcript timers** — stop delayed text from appearing

**VAD is disabled** when `vadEnabledRef = false` (set during call transfer so beep tones play through).

### 4. WebSocket Message Handling

```
ws.onmessage(event)
    │
    ├── event.data instanceof ArrayBuffer
    │       └── playAudioChunk(data)
    │
    └── JSON string
            │
            ├── call_status
            │       ├── "transferring"/"transferred" → disable VAD
            │       └── dispatch(CALL_STATUS, { status, callId })
            │
            ├── transcript_update
            │       ├── User role → dispatch immediately
            │       └── Agent role → delay dispatch by audio buffer offset
            │           │  delay = (nextPlayTimeRef - ctx.currentTime) * 1000
            │           └── setTimeout(() => dispatch(TRANSCRIPT), delay)
            │
            └── notification
                    └── dispatch(NOTIFICATION, payload)
```

### 5. Transcript Accumulation

The reducer merges consecutive fragments from the same speaker into one chat bubble:

```
case "TRANSCRIPT":
    │
    ├── Last entry exists AND same role AND no attachments?
    │       └── YES: update last entry's text: last.text + " " + new.text
    │
    └── NO: append as new entry
```

This is necessary because the model sends transcription in small chunks (word or phrase level), and without merging each fragment would be a separate bubble.

### 6. Text Input

```
User types message + presses Enter
    │
    ├── ws.send(JSON: { type: "text_message", text })
    │       └── Backend → agent.send_text() → session.send_realtime_input(text=...)
    │
    └── dispatch(TRANSCRIPT, { role: "user", text })  (optimistic local append)
```

### 7. Call End

```
User clicks "End Call"
    │
    ├── ws.send(JSON: { type: "end_call" })
    │
    ├── Stop mic: stream.getTracks().forEach(t.stop())
    ├── Disconnect worklet
    ├── Close mic AudioContext
    ├── dispatch(MIC_ACTIVE, false)
    │
    ├── Clear pending transcript timers
    │
    └── Close playback AudioContext
        Reset GainNode, nextPlayTimeRef
```

The WebSocket stays open — the backend sends `"processing"` and eventually `"completed"` status + notification before closing.

---

## Control Flow: Dashboard

### Connection

```
DashboardPage mounts
    │
    └── useWebSocket("ws://localhost:8000/ws/dashboard")
            │
            ├── Opens WebSocket
            ├── On close: auto-reconnect after 3s
            │
            └── ws.onmessage → parse WSEvent → dispatch by event_type:
                    ├── call_status    → CALL_STATUS
                    ├── transcript_update → TRANSCRIPT_UPDATE (with merging)
                    ├── tool_call      → TOOL_CALL
                    ├── coverage_decision → COVERAGE_DECISION
                    ├── next_action    → NEXT_ACTION
                    ├── notification   → NOTIFICATION
                    └── human_override → HUMAN_OVERRIDE
```

### State Shape (CallState)

```typescript
{
  callId: string;
  status: "idle" | "active" | "processing" | "completed";
  transcript: TranscriptEntry[];       // merged same-role chunks
  toolCalls: ToolCallEntry[];          // all tool calls with I/O
  coverage: CoverageDecision | null;   // from check_coverage
  action: NextAction | null;           // dispatch + garage info
  notification: CustomerNotification | null;
  humanOverride: string | null;        // "approve" / "deny" / "escalate"
}
```

### Override Flow

```
Operator clicks Approve / Deny / Escalate
    │
    └── POST http://localhost:8000/calls/{callId}/override
            body: { action: "approve", notes: "" }
            │
            └── Backend publishes human_override WSEvent
                    │
                    └── Dashboard receives via /ws/dashboard
                            └── dispatch(HUMAN_OVERRIDE)
```

---

## Component Hierarchy

### CustomerCallPage

```
CustomerCallPage
│
├── Header (call ID display)
│
├── Status Bar
│   ├── Indicator dot (green=active, yellow=processing, gray=idle)
│   ├── Status text ("Connected — speak now", "Processing...", etc.)
│   └── MIC indicator (pulsing red dot)
│
├── Transcript Area (scrollable)
│   ├── Empty state: "Press the button below..."
│   ├── Waiting state: "Waiting for the agent to greet you..."
│   └── Messages: map over state.transcript
│       ├── User bubble (right-aligned, blue #1e40af)
│       │   └── Optional: location attachment, image attachment
│       └── Agent bubble (left-aligned, dark #1e293b)
│           └── "Alex" label
│
├── Notification Card (post-call, if present)
│   ├── Reference number
│   └── Summary text (pre-formatted)
│
├── Text Input (visible during active call)
│   ├── Input field
│   └── Send button (blue when text present)
│
└── Call Button
    ├── "Start Call" / "Start New Call" (green, idle)
    └── "End Call" / "Processing..." (red / gray, active)
```

### DashboardPage

```
DashboardPage
│
├── Header ("Insurance Co-Pilot")
│
├── Status Row
│   ├── CallStatus (call ID + status badge)
│   └── OverrideBar (Approve / Deny / Escalate buttons)
│
└── Two-Column Grid
    ├── Left Column
    │   ├── TranscriptPanel
    │   │   └── Scrollable list: AGENT (blue) / CUSTOMER (green) badges + text
    │   └── ToolCallLog
    │       └── Expandable entries: tool name, timestamp
    │           └── Expanded: input JSON + output JSON
    │
    └── Right Column
        ├── CoveragePanel
        │   ├── Status badge (COVERED=green / NOT COVERED=red / UNCERTAIN=yellow)
        │   ├── Confidence bar (animated, color-coded)
        │   ├── Explanation text
        │   ├── Cited clauses list
        │   └── "NEEDS REVIEW" indicator
        │
        └── ActionPanel
            ├── Service type + recommended action
            ├── Garage info (name, address, distance, ETA, phone)
            └── Notification card (reference number + message text)
```

---

## Audio Architecture

### Sample Rates

| Path | Rate | Format |
|---|---|---|
| Mic capture | 48kHz | Float32 (Web Audio native) |
| Mic → Backend | 16kHz | Int16 PCM (resampled in worklet) |
| Backend → Playback | 24kHz | Int16 PCM (Gemini output rate) |

### AudioWorklet (`pcm-worklet-processor.js`)

Runs on a separate audio thread to avoid blocking the main thread:

1. Receives 128-sample Float32 frames from the mic at device sample rate
2. Accumulates into a buffer (2048 samples)
3. When buffer is full:
   - Resamples to 16kHz using linear interpolation
   - Converts Float32 → Int16 (clamp to [-32768, 32767])
   - Posts ArrayBuffer to main thread via `port.postMessage` (transferable)
4. Main thread sends the buffer over WebSocket as binary

### Playback Scheduling

Audio chunks arrive asynchronously. To avoid gaps or overlaps, each chunk is scheduled to start right after the previous one ends:

```
startTime = max(now + 0.01, nextPlayTimeRef)
nextPlayTimeRef = startTime + buffer.duration
```

This creates a gapless queue. The 10ms minimum offset (`now + 0.01`) prevents scheduling in the past.

### Transcript Synchronization

Agent transcript text arrives before or alongside audio. To sync text with what the user actually hears:

```
delay = max(0, (nextPlayTimeRef - audioContext.currentTime) * 1000)
setTimeout(() => dispatch(TRANSCRIPT, entry), delay)
```

The delay equals how far ahead the audio queue extends — so text appears when the corresponding audio starts playing, not when it was received.

---

## State Management

Both hooks use `useReducer` (not external state libraries). This keeps state co-located with the WebSocket lifecycle.

### CustomerCallState (useCallWebSocket)

```
Action Types:
  CONNECTED      → isConnected: true, isCallActive: true
  DISCONNECTED   → isConnected: false, isCallActive: false
  MIC_ACTIVE     → isMicActive: boolean
  CALL_STATUS    → status, callId, isCallActive
  TRANSCRIPT     → append or merge into transcript[]
  NOTIFICATION   → notification object
  RESET          → back to initialState
```

### CallState (useWebSocket — dashboard)

```
Action Types:
  CALL_STATUS       → callId, status
  TRANSCRIPT_UPDATE → append or merge into transcript[]
  TOOL_CALL         → append to toolCalls[]
  COVERAGE_DECISION → coverage object
  NEXT_ACTION       → action object
  NOTIFICATION      → notification object
  HUMAN_OVERRIDE    → override string
  RESET             → back to initialState
```

---

## WebSocket Protocol

### Customer WebSocket (`/ws/call`)

**Outbound (browser → backend):**

| Type | Format | Content |
|---|---|---|
| Mic audio | Binary (ArrayBuffer) | Int16 PCM at 16kHz |
| Text message | JSON | `{ type: "text_message", text: "..." }` |
| End call | JSON | `{ type: "end_call" }` |

**Inbound (backend → browser):**

| Type | Format | Content |
|---|---|---|
| Agent audio | Binary (ArrayBuffer) | Int16 PCM at 24kHz |
| Event | JSON | `{ event_type: "...", payload: {...} }` |

### Dashboard WebSocket (`/ws/dashboard`)

Read-only. Receives all `WSEvent` JSON objects published by the backend's EventBus.

---

## Styling

All components use **inline styles** with a consistent dark color palette:

| Token | Value | Usage |
|---|---|---|
| Background | `#0f172a` | Page background |
| Surface | `#1e293b` | Cards, panels, agent bubbles |
| Border | `#334155` | Dividers, input borders |
| Text primary | `#f1f5f9` | Main text |
| Text secondary | `#94a3b8` | Labels, timestamps |
| Text muted | `#475569` | Placeholder, empty states |
| User bubble | `#1e40af` | User message background |
| Active green | `#22c55e` | Call active, start button |
| Error red | `#ef4444` | End call, mic indicator |
| Warning yellow | `#eab308` | Processing status |

No CSS framework (Tailwind, etc.) — color values are from the Tailwind palette but applied via inline `style` props.

---

## Known Limitations

1. **No reconnection on customer WebSocket** — if the connection drops mid-call, the call is lost. The dashboard hook auto-reconnects; the call hook does not.

2. **Inline styles everywhere** — no CSS modules, styled-components, or Tailwind. Makes theming and responsive design harder to maintain.

3. **No audio level visualization** — VAD computes RMS energy but doesn't expose it to the UI. No waveform, no volume meter.

4. **Optimistic text input** — `sendText` appends to the local transcript immediately without waiting for server acknowledgment. If the WebSocket send fails, the message appears in the UI but was never received.

5. **No error UI** — WebSocket failures, mic permission denial, and audio context errors are logged to console but not surfaced to the user.

6. **Single-call assumption** — the dashboard shows one call at a time. Multiple concurrent calls would overwrite each other's state.

7. **No mobile optimization** — layout and touch targets are designed for desktop. The mic/audio pipeline works on mobile browsers but the UI doesn't adapt.

8. **Timer leak potential** — `pendingTranscriptsRef` timers are cleaned on call end and unmount, but if the component re-renders rapidly or the WebSocket fires events after cleanup starts, a timer could fire after the reducer is gone (harmless but wasteful).
