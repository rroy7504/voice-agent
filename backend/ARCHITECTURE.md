# Backend Architecture

## Overview

A real-time voice agent for insurance customer service, built on **FastAPI** + **Gemini Live API**. The agent handles roadside assistance calls end-to-end: greeting, account validation, incident classification, coverage analysis (RAG), and dispatch — all via streaming audio with server-enforced state management.

```
Browser (mic/speaker)
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  FastAPI Server (ws.py)                             │
│  ┌───────────────┐    ┌──────────────────────────┐  │
│  │ /ws/call       │    │ /ws/dashboard            │  │
│  │ (customer WS)  │    │ (observer WS, read-only) │  │
│  └───────┬───────┘    └──────────▲───────────────┘  │
│          │                       │                  │
│          ▼                       │                  │
│  ┌───────────────────────────────┴───────────────┐  │
│  │           VoiceAgent                          │  │
│  │  ┌─────────────┐  ┌───────────────────────┐   │  │
│  │  │ State Machine│  │ Gemini Live Session   │   │  │
│  │  │ (CallStage)  │  │ (bidirectional audio) │   │  │
│  │  └──────┬──────┘  └───────────┬───────────┘   │  │
│  │         │                     │               │  │
│  │         ▼                     ▼               │  │
│  │  ┌─────────────┐  ┌───────────────────────┐   │  │
│  │  │ Tool Gate   │  │ _receive_audio loop   │   │  │
│  │  │ (allow/deny)│  │ (audio, text, tools)  │   │  │
│  │  └──────┬──────┘  └───────────────────────┘   │  │
│  │         │                                     │  │
│  │         ▼                                     │  │
│  │  ┌────────────────────────────────────────┐   │  │
│  │  │ Tool Handlers (tool_handlers.py)       │   │  │
│  │  │  validate_account   (sync, mock DB)    │   │  │
│  │  │  classify_incident  (sync, keyword)    │   │  │
│  │  │  get_policy_metadata(sync, mock DB)    │   │  │
│  │  │  check_coverage     (async, RAG+LLM)   │   │  │
│  │  │  dispatch_service   (sync, mock garage) │   │  │
│  │  │  transfer_to_human  (sync, flag)       │   │  │
│  │  └────────────────┬───────────────────────┘   │  │
│  │                   │                           │  │
│  │                   ▼                           │  │
│  │  ┌────────────────────────────────────────┐   │  │
│  │  │ Post-Call Pipeline                     │   │  │
│  │  │  coverage (cached) → dispatch (cached) │   │  │
│  │  │  → notification                        │   │  │
│  │  └────────────────────────────────────────┘   │  │
│  └───────────────────────────────────────────────┘  │
│                                                     │
│  ┌────────────────┐  ┌────────────────────────┐     │
│  │ EventBus       │  │ CallStore (in-memory)  │     │
│  │ (pub/sub)      │  │                        │     │
│  └────────────────┘  └────────────────────────┘     │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ RAG Layer                                    │   │
│  │  PolicyRetriever (ChromaDB + Gemini embed)   │   │
│  │  Policy PDFs: basic / standard / premium     │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

---

## Directory Structure

```
backend/
├── run_voice_agent.py              # Entry point (uvicorn on 0.0.0.0:8000)
├── app/
│   ├── main.py                     # FastAPI app, CORS, router registration
│   ├── core/
│   │   ├── config.py               # Pydantic settings (GEMINI_API_KEY, host, port)
│   │   └── call_store.py           # In-memory dict-based call state store
│   ├── models/
│   │   ├── call.py                 # IncidentData, CoverageDecision, CallState, etc.
│   │   ├── events.py               # WSEvent schema
│   │   └── policy.py               # CustomerInfo, PolicyChunk
│   ├── routers/
│   │   ├── ws.py                   # WebSocket endpoints (/ws/call, /ws/dashboard)
│   │   └── calls.py                # REST endpoints (GET /calls, POST override)
│   ├── services/
│   │   ├── voice_agent.py          # VoiceAgent class, state machine, Gemini session
│   │   ├── tool_handlers.py        # Tool implementations + dispatch registry
│   │   ├── coverage_agent.py       # RAG-based coverage evaluator (Gemini text call)
│   │   ├── next_action.py          # Service dispatch + mock garage assignment
│   │   ├── notification.py         # Post-call summary generator
│   │   └── event_bus.py            # Async pub/sub for dashboard streaming
│   └── rag/
│       ├── ingest.py               # PDF → chunks → Gemini embeddings → ChromaDB
│       └── retriever.py            # Query ChromaDB, return ranked PolicyChunks
└── data/
    ├── mock_customers.json         # 7 mock customers (active/expired/suspended)
    ├── generate_policies.py        # Script to create policy PDFs
    ├── policies/                   # basic/standard/premium roadside policy PDFs
    └── chroma_db/                  # Persisted ChromaDB vector store
```

---

## Control Flow

### 1. Connection

Browser opens WebSocket to `/ws/call`. The handler (`ws.py:call_ws`) creates:
- A `VoiceAgent` instance
- An `audio_out_queue` (agent audio -> browser)
- A `text_out_callback` (JSON events -> browser)

Three concurrent loops start:
- **`agent.run()`** — connects to Gemini Live, spawns send/receive tasks
- **`send_audio_to_browser()`** — drains `audio_out_queue`, sends binary PCM to WebSocket
- **Main WS receive loop** — routes browser messages: binary (mic audio) -> `agent.feed_audio()`, JSON `text_message` -> `agent.send_text()`, JSON `end_call` -> break

### 2. Gemini Live Session

`VoiceAgent.run()` opens a persistent bidirectional WebSocket to Gemini via `client.aio.live.connect()`. Configuration:

| Setting | Value |
|---|---|
| Model | `gemini-3.1-flash-live-preview` |
| Response modality | Audio only |
| Voice | Zephyr |
| Input transcription | Enabled |
| Output transcription | Enabled |
| Tools | 6 function declarations |
| System instruction | Alex, insurance customer service agent |

On connect, sends `send_realtime_input(text="Hello")` to trigger the agent's greeting, then spawns:

- **`_send_realtime()`** — pumps mic PCM from `audio_in_queue` to `session.send_realtime_input(audio=...)`
- **`_receive_audio()`** — iterates `session.receive()`, processes each server event

### 3. Receive Loop

Each server event can contain multiple parts simultaneously (a key behavior of the new model). The loop checks in order:

1. **`response.data`** — raw audio bytes -> `audio_out_queue` -> browser speaker
2. **`server_content.input_transcription`** — Gemini's STT of user speech -> `transcript_update` event
3. **`server_content.output_transcription`** — text of agent speech -> `transcript_update` event
4. **`response.text`** — fallback text (only if no `output_transcription`)
5. **`response.tool_call`** — function calls from the model -> state gate -> execute -> respond

### 4. Text Input

User text from the browser is forwarded to the Gemini session via `session.send_realtime_input(text=...)`. This works alongside audio — the model processes both modalities.

---

## State Machine

The conversation workflow is enforced server-side, not just by the system prompt. A `CallStage` enum tracks progress, and `_gate_tool()` rejects out-of-order tool calls with guidance messages that steer the model back on track.

```
    GREETING
       │
       │  validate_account (valid=true)
       ▼
  ACCOUNT_VALIDATED
       │
       │  classify_incident
       ▼
  INCIDENT_CLASSIFIED
       │
       │  check_coverage
       ▼
  COVERAGE_CHECKED ──────────────────────┐
       │                                 │
       │  coverage = "covered"           │  coverage ≠ "covered"
       │  + customer confirms            │  (not_covered / uncertain)
       │                                 │
       │  dispatch_service               │
       ▼                                 │
    DISPATCHED                           │
       │                                 │
       └──── wrap up or transfer ────────┘
                     │
                     ▼
                  RESOLVED

  transfer_to_human_agent → RESOLVED  (allowed from ANY stage)
```

### Allowed Tools Per Stage

| Stage | Allowed Tools |
|---|---|
| `GREETING` | `validate_account`, `transfer_to_human_agent` |
| `ACCOUNT_VALIDATED` | `classify_incident`, `get_policy_metadata`, `transfer_to_human_agent` |
| `INCIDENT_CLASSIFIED` | `check_coverage`, `transfer_to_human_agent` |
| `COVERAGE_CHECKED` | `dispatch_service`, `transfer_to_human_agent` |
| `DISPATCHED` | `transfer_to_human_agent` |
| `RESOLVED` | `transfer_to_human_agent` |

### Dispatch Preconditions

`dispatch_service` is double-gated:

1. **Stage gate** — only callable at `COVERAGE_CHECKED` (so `check_coverage` must have run)
2. **Tool-level guard** — the handler checks `coverage_status == "covered"` and returns an error if not. This prevents dispatch even if the model passes the wrong status.

The model is instructed to ask the customer "Would you like me to dispatch help?" and only call `dispatch_service` after explicit confirmation.

### What Happens When a Tool Is Blocked

The tool is **not executed**. Instead, a structured error is returned to Gemini as the function response:

```json
{
  "error": "BLOCKED: 'check_coverage' is not available at stage greeting. You must validate the customer's account first. Ask for their policy number and call validate_account."
}
```

The model reads this, self-corrects, and asks the customer for the missing information.

### Stage Transitions

Transitions only happen on **meaningful success**:
- `validate_account` must return `valid: true` (expired/not-found stays at `GREETING`)
- `classify_incident` must return an `incident_type`
- `check_coverage` always advances (result may be covered/not_covered/uncertain)
- `dispatch_service` must return `dispatched: true` (rejected if coverage ≠ "covered")

Stage changes are published as `stage_change` events to the dashboard.

---

## Tool Calling

### Flow

```
Gemini decides to call tool(s)
        │
        ▼
_gate_tool(name)  ──blocked──>  return error to Gemini
        │
      allowed
        │
        ▼
dispatch_tool(name, args)  ──>  TOOL_REGISTRY[name](**args)
        │
        ▼
_advance_stage(name, result)   (if no error)
        │
        ▼
_update_collected_data(name, args, result)  (side-effect tracking)
        │
        ▼
Collect into function_responses[]
        │
        ▼
session.send_tool_response(function_responses)
        │
        ▼
Gemini generates spoken response about the result
```

### Tool Implementations

| Tool | Type | What It Does |
|---|---|---|
| `validate_account` | Sync | Looks up policy number in `mock_customers.json`. Returns customer name, vehicle, plan, or error for expired/suspended/not-found. |
| `classify_incident` | Sync | Keyword matching against the description. Maps to: `flat_tire`, `engine_failure`, `accident`, `lockout`, `fuel_empty`, `battery_dead`, or `other`. |
| `get_policy_metadata` | Sync | Returns coverage details for the customer's plan tier (towing miles, lockout coverage, etc.). |
| `check_coverage` | **Async** | RAG pipeline. Retrieves policy document chunks from ChromaDB, builds a prompt, calls `gemini-2.0-flash` (separate, non-live API call) to get a structured coverage decision. |
| `dispatch_service` | Sync | Guards on `coverage_status == "covered"`. Calls `determine_next_action()` to pick a service type + nearest mock garage. Returns provider name, address, phone, distance, and ETA. |
| `transfer_to_human_agent` | Sync | Sets a flag. Returns a confirmation message. |

### check_coverage Deep Dive

This is the most complex tool — it makes a **second LLM call** during the live session:

```
check_coverage(policy_number, incident_type, situation_summary)
        │
        ▼
PolicyRetriever.retrieve(query, top_k=5, plan_filter)
        │  (ChromaDB cosine similarity search over Gemini embeddings)
        ▼
Build prompt with policy excerpts + incident details
        │
        ▼
client.aio.models.generate_content(model="gemini-2.0-flash")
        │  (structured JSON output, temperature=0.1)
        ▼
Parse CoverageDecision {status, confidence, cited_clauses, explanation}
```

---

## RAG Pipeline

### Ingestion (`rag/ingest.py`)

1. Reads all PDFs from `data/policies/`
2. Extracts text via PyPDF2
3. Chunks with 500-char window, 100-char overlap
4. Embeds chunks using Gemini embedding model
5. Stores in ChromaDB (`data/chroma_db/`, collection: `"policies"`)

### Retrieval (`rag/retriever.py`)

1. Embeds the query using the same Gemini embedding model
2. Queries ChromaDB with cosine similarity
3. Optionally filters by plan (basic/standard/premium) via source filename metadata
4. Returns top-k `PolicyChunk` objects with text, source, page, and relevance score

### Policy Documents

Three generated PDFs covering roadside assistance tiers:

| Plan | Towing | Lockout | Battery | Fuel | Vehicle Recovery |
|---|---|---|---|---|---|
| Basic | 25 mi, 2/yr | No | No | 2 gal (no cost coverage) | No |
| Standard | 50 mi, 4/yr | Yes, 2/yr | Yes | 3 gal (cost covered) | No |
| Premium | Unlimited | Unlimited | Yes | 5 gal (cost covered) | Yes |

---

## Event System

### Dual-Channel Publishing

Every event is published to **two channels** simultaneously via `_publish()`:

1. **EventBus** (pub/sub) — dashboard WebSocket subscribers receive all events
2. **text_out_callback** — direct JSON to the customer's browser WebSocket

### Event Types

| Event | Payload | When |
|---|---|---|
| `call_status` | `{status, call_id?}` | Call lifecycle: `active`, `processing`, `transferring`, `transferred`, `completed`, `error` |
| `transcript_update` | `{role, text, timestamp}` | User or agent speech transcribed |
| `tool_call` | `{tool, input, output, timestamp}` | Tool executed (or blocked) |
| `stage_change` | `{from, to}` | State machine transition |
| `notification` | `{reference_number, message_text, ...}` | Post-call summary |
| `next_action` | `{recommended_action, service_type, assigned_garage, ...}` | Dispatch decision |
| `coverage_decision` | `{status, confidence, ...}` | Coverage result (from REST override) |
| `human_override` | `{action, notes}` | Dashboard operator override |

---

## Post-Call Pipeline

Runs in the `finally` block after the Gemini session closes, regardless of how the call ended.

```
_post_call_pipeline()
        │
        ├── If _live_coverage_result exists:
        │       Build CoverageDecision from cached check_coverage result
        │
        ├── If _live_dispatch_result exists:
        │       Build NextAction + GarageInfo from cached dispatch_service result
        │       Publish "next_action" event
        │       (No second call to determine_next_action — uses live data)
        │
        ├── generate_notification()
        │       → Build summary text with reference number
        │       → Include: policy, incident, coverage status, dispatch details, ETA
        │       → Publish "notification" event
        │
        └── Set call status to "completed"
```

The post-call pipeline does **not** re-run any logic. It assembles the notification from data already collected during the live call (coverage result from `check_coverage`, dispatch result from `dispatch_service`). If the customer declined dispatch or wasn't covered, `_live_dispatch_result` is `None` and no action is included.

### Transfer Flow

When `transfer_to_human_agent` is called:
1. `_transfer_pending = True` is set
2. After the current Gemini turn completes (agent says farewell)
3. `"transferring"` status published (frontend disables voice interruption)
4. 0.5s pause for farewell audio to flush
5. Beep tones generated (880Hz, 880Hz, 1100Hz) and sent as PCM chunks
6. 2s pause for beeps to play
7. `"transferred"` status published, `_stop_event` set

---

## REST API

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/calls` | GET | List all calls (from in-memory store) |
| `/calls/{call_id}` | GET | Get call details (transcript, tools, coverage, etc.) |
| `/calls/{call_id}/override` | POST | Human operator override (approve/deny/escalate) |

---

## Data Models

### CallState (Pydantic)

The central model that accumulates throughout a call:

```
CallState
├── call_id: str
├── status: str (active → processing → completed)
├── started_at / ended_at: datetime
├── incident: IncidentData
│   ├── customer_name, policy_number, vehicle
│   ├── location, incident_type, situation_summary
├── transcript: list[TranscriptEntry]
│   └── {role: "user"|"agent", text, timestamp}
├── tool_calls: list[ToolCallEntry]
│   └── {tool, input, output, timestamp}
├── coverage: CoverageDecision?
│   └── {status, confidence, cited_clauses, explanation, requires_human_review}
├── action: NextAction?
│   └── {recommended_action, service_type, assigned_garage: GarageInfo, estimated_arrival}
├── notification: CustomerNotification?
│   └── {reference_number, message_text, coverage_summary, assistance_type, eta}
└── human_override: str?
```

---

## Known Limitations

1. **In-memory state** — `CallStore` and `EventBus` are singletons in process memory. No persistence, no multi-worker support. Server restart loses all call data.

2. **No Gemini-side interruption** — when the frontend interrupts playback (VAD), Gemini doesn't know. It keeps generating audio for the rest of its response. Wasted tokens and bandwidth.

3. **Blocking tool execution** — while `check_coverage` runs its RAG + second Gemini call (2-5s), the receive loop is blocked. The user hears silence with no feedback.

4. **Keyword-based classification** — `classify_incident` uses string matching, not the model. Descriptions that don't contain expected keywords fall through to `"other"`.

5. **Single concurrent call** — the architecture supports multiple calls (each gets its own `VoiceAgent`), but there's no rate limiting, connection pooling, or resource management.

6. **No session reconnection** — if the Gemini WebSocket drops (1007 error), the call ends. No retry or reconnect logic.

7. **Mock data** — customers, garages, and service availability are all hardcoded. The `determine_next_action` picks randomly from mock garages.

8. **Post-call always runs** — even for zero-data calls (immediate hang-up), it generates a notification with empty fields.

9. **No audio persistence** — raw audio is streamed and discarded. No call recording capability.
