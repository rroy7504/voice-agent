"""Core voice agent: Gemini Live session with tool calling and event publishing.

Audio is provided externally (from browser WebSocket), not from PyAudio.
"""
import asyncio
import json
import math
import os
import struct
import uuid
from datetime import datetime
from typing import Awaitable, Callable

from google import genai
from google.genai import types

from app.models.call import IncidentData, TranscriptEntry, ToolCallEntry, NextAction, GarageInfo
from app.models.events import WSEvent
from app.services.event_bus import EventBus
from app.services.tool_handlers import dispatch_tool
from app.services.coverage_agent import evaluate_coverage
from app.services.notification import generate_notification
from app.core.call_store import CallStore

from enum import Enum

SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000


class CallStage(str, Enum):
    """Server-enforced conversation stages."""
    GREETING = "greeting"                    # Agent greets, waits for policy number
    ACCOUNT_VALIDATED = "account_validated"   # Policy confirmed, gather incident details
    INCIDENT_CLASSIFIED = "incident_classified"  # Incident typed, ready for coverage check
    COVERAGE_CHECKED = "coverage_checked"    # Coverage decided, ask customer if they want dispatch
    DISPATCHED = "dispatched"                # Service dispatched, wrapping up
    RESOLVED = "resolved"                    # Call complete


# Which tools are allowed at each stage.
# transfer_to_human_agent is always allowed — customer can ask for a human at any time.
STAGE_ALLOWED_TOOLS: dict[CallStage, set[str]] = {
    CallStage.GREETING: {"validate_account", "transfer_to_human_agent"},
    CallStage.ACCOUNT_VALIDATED: {"classify_incident", "get_policy_metadata", "transfer_to_human_agent"},
    CallStage.INCIDENT_CLASSIFIED: {"check_coverage", "transfer_to_human_agent"},
    CallStage.COVERAGE_CHECKED: {"dispatch_service", "transfer_to_human_agent"},
    CallStage.DISPATCHED: {"transfer_to_human_agent"},
    CallStage.RESOLVED: {"transfer_to_human_agent"},
}

# Guidance returned to the model when it tries a tool out of order
STAGE_GUIDANCE: dict[CallStage, str] = {
    CallStage.GREETING: "You must validate the customer's account first. Ask for their policy number and call validate_account.",
    CallStage.ACCOUNT_VALIDATED: "Account is validated. Now gather details about the incident and call classify_incident.",
    CallStage.INCIDENT_CLASSIFIED: "Incident is classified. You must call check_coverage before telling the customer about their coverage.",
    CallStage.COVERAGE_CHECKED: "Coverage has been checked. Tell the customer the result. If covered, ask if they want you to dispatch help, then call dispatch_service. If not covered, offer alternatives or transfer.",
    CallStage.DISPATCHED: "Service has been dispatched. Confirm the details to the customer and wrap up the call.",
    CallStage.RESOLVED: "The call is being wrapped up.",
}


def generate_beep_tones(sample_rate: int = 24000) -> bytes:
    """Generate 3 short beep tones as PCM Int16 at the given sample rate.

    Pattern: beep (200ms) silence (150ms) beep (200ms) silence (150ms) beep (400ms)
    """
    data = bytearray()

    def _tone(freq: float, duration_ms: int, volume: float = 0.3):
        n_samples = int(sample_rate * duration_ms / 1000)
        for i in range(n_samples):
            sample = volume * math.sin(2 * math.pi * freq * i / sample_rate)
            data.extend(struct.pack('<h', int(sample * 32767)))

    def _silence(duration_ms: int):
        n_samples = int(sample_rate * duration_ms / 1000)
        data.extend(b'\x00\x00' * n_samples)

    _tone(880, 200)
    _silence(150)
    _tone(880, 200)
    _silence(150)
    _tone(1100, 400)
    _silence(300)

    return bytes(data)

MODEL = "models/gemini-3.1-flash-live-preview"

SYSTEM_INSTRUCTION = """You are Alex, a friendly and empathetic insurance customer service agent. You handle a wide range of insurance inquiries — roadside assistance, claims, policy questions, billing, and more.

IMPORTANT: As soon as the session starts, YOU must speak first. Greet the customer warmly and ask how you can help today. Do NOT wait for them to speak first. Do NOT assume what they are calling about. Example opening: "Hi there, this is Alex from SafeDrive Insurance. How can I help you today?"

CONVERSATION FLOW:
1. Greet the customer and ask how you can help (do this immediately)
2. Listen to their issue and respond accordingly
3. When you need to look up their account, ask for their policy number and validate it using the validate_account tool
4. Depending on their issue, gather relevant details (vehicle, location, what happened, etc.)
5. Use classify_incident to categorize roadside issues when you have enough description
6. IMPORTANT: Once you have the policy number, incident type, and situation summary, you MUST call check_coverage to determine whether the incident is covered. Tell the customer "Let me check your coverage now, one moment please." then call the tool.
7. After check_coverage returns, communicate the FULL result to the customer:
   - If COVERED: Tell them they're covered and explain what's included. Then ASK the customer: "Would you like me to dispatch [service type] to your location?" Wait for their explicit confirmation before calling dispatch_service.
   - If NOT COVERED: Explain clearly why it's not covered, cite the specific reason from the result, and offer alternatives (speak to a human agent at 1-800-555-HELP, request paid service, or file an appeal)
   - If UNCERTAIN: Tell them you need a specialist to review, and offer to transfer them
8. DISPATCH: Only call dispatch_service AFTER the customer says yes. Once dispatched, tell the customer the provider name, ETA, and phone number. Ask if there's anything else you can help with.

GUIDELINES:
- Be empathetic and patient
- NEVER invent, guess, or assume a policy number. You MUST explicitly ask the customer for their policy number and wait for them to tell you. Only use a policy number that the customer has clearly stated.
- Do NOT call validate_account, get_policy_metadata, or check_coverage until the customer has explicitly provided their policy number.
- Validate the policy number as soon as the customer provides it
- IMPORTANT: When a policy lookup fails (valid=false), repeat the policy number back to the customer so they can confirm it, explain that you could not locate that policy in the system, and ask them to double-check or provide a different number.
- If the account is expired or suspended, tell the customer the specific status and offer to connect them with a human agent
- Keep responses concise but warm
- If the customer seems distressed about safety, remind them to call 911 for emergencies
- CRITICAL: After EVERY tool call completes, you MUST immediately speak to the customer about the result. Never go silent after a tool call.
- You MUST always call check_coverage before telling the customer whether they are covered or not. Do NOT guess coverage — always use the tool.
"""

TOOL_DECLARATIONS = types.Tool(
    function_declarations=[
        types.FunctionDeclaration(
            name="validate_account",
            description="Validate a customer's insurance account by policy number. Call this when the customer provides their policy number.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "policy_number": types.Schema(type=types.Type.STRING, description="The customer's policy number"),
                },
                required=["policy_number"],
            ),
        ),
        types.FunctionDeclaration(
            name="classify_incident",
            description="Classify the type of roadside incident from the customer's description. Call this when you have enough details about what happened.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "description": types.Schema(type=types.Type.STRING, description="Description of the incident"),
                },
                required=["description"],
            ),
        ),
        types.FunctionDeclaration(
            name="get_policy_metadata",
            description="Get coverage details for a validated policy. Call this after validating the account to understand what the customer's plan covers.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "policy_number": types.Schema(type=types.Type.STRING, description="The customer's policy number"),
                },
                required=["policy_number"],
            ),
        ),
        types.FunctionDeclaration(
            name="check_coverage",
            description="Check whether a specific incident is covered under the customer's policy. Call this AFTER you have validated the account, classified the incident, and collected all details. This performs a detailed policy analysis and returns a coverage decision. You MUST call this before telling the customer whether they are covered.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "policy_number": types.Schema(type=types.Type.STRING, description="The customer's validated policy number"),
                    "incident_type": types.Schema(type=types.Type.STRING, description="The classified incident type (e.g. flat_tire, engine_failure, lockout)"),
                    "situation_summary": types.Schema(type=types.Type.STRING, description="Brief summary of what happened"),
                },
                required=["policy_number", "incident_type", "situation_summary"],
            ),
        ),
        types.FunctionDeclaration(
            name="dispatch_service",
            description="Dispatch roadside assistance to the customer's location. Call this ONLY after check_coverage returns 'covered' AND the customer explicitly confirms they want help sent. You MUST ask the customer for confirmation before calling this. Pass the coverage_status exactly as returned by check_coverage.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "policy_number": types.Schema(type=types.Type.STRING, description="The customer's validated policy number"),
                    "incident_type": types.Schema(type=types.Type.STRING, description="The classified incident type"),
                    "coverage_status": types.Schema(type=types.Type.STRING, description="The coverage status from check_coverage (must be 'covered')"),
                },
                required=["policy_number", "incident_type", "coverage_status"],
            ),
        ),
        types.FunctionDeclaration(
            name="transfer_to_human_agent",
            description="Transfer the call to a human agent. Call this when the customer requests to speak to a person, when coverage is uncertain and needs specialist review, when the customer's account is expired or suspended, or when you cannot resolve the issue. Before calling this, briefly tell the customer you are transferring them.",
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties={
                    "reason": types.Schema(type=types.Type.STRING, description="Reason for the transfer (e.g. 'customer requested', 'coverage uncertain', 'account expired')"),
                },
                required=["reason"],
            ),
        ),
    ]
)


class VoiceAgent:
    def __init__(
        self,
        event_bus: EventBus,
        call_store: CallStore,
        audio_out_queue: asyncio.Queue,
        text_out_callback: Callable[[str, dict], Awaitable[None]],
    ):
        self.event_bus = event_bus
        self.call_store = call_store
        self.call_id = f"call-{uuid.uuid4().hex[:8]}"
        self.session = None
        self.audio_in_queue: asyncio.Queue = asyncio.Queue(maxsize=50)
        self.audio_out_queue = audio_out_queue
        self.text_out_callback = text_out_callback
        self._collected_data = IncidentData()
        self._plan: str | None = None
        self._stop_event = asyncio.Event()
        self._transfer_pending = False
        self._live_coverage_result: dict | None = None  # set by check_coverage tool during call
        self._live_dispatch_result: dict | None = None  # set by dispatch_service tool during call
        self._stage = CallStage.GREETING

    async def feed_audio(self, data: bytes):
        """Feed audio data from the browser WebSocket."""
        try:
            self.audio_in_queue.put_nowait(data)
        except asyncio.QueueFull:
            # Drop oldest frame to avoid blocking
            try:
                self.audio_in_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            self.audio_in_queue.put_nowait(data)

    async def stop(self):
        """Signal the agent to stop."""
        self._stop_event.set()

    async def _publish(self, event_type: str, payload: dict):
        """Publish event to both EventBus (dashboard) and customer WebSocket."""
        event = WSEvent(
            event_type=event_type,
            call_id=self.call_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            payload=payload,
        )
        await self.event_bus.publish(event)
        # Also send to customer browser
        try:
            await self.text_out_callback(event_type, payload)
        except Exception:
            pass

    async def send_text(self, text: str):
        """Send a user text message to the Gemini session."""
        if self.session is not None:
            await self.session.send_realtime_input(text=text)

    def _gate_tool(self, tool_name: str) -> str | None:
        """Check if a tool call is allowed in the current stage.

        Returns None if allowed, or an error message string if blocked.
        """
        allowed = STAGE_ALLOWED_TOOLS.get(self._stage, set())
        if tool_name in allowed:
            return None
        guidance = STAGE_GUIDANCE.get(self._stage, "")
        return (
            f"BLOCKED: '{tool_name}' is not available at the current stage "
            f"({self._stage.value}). {guidance}"
        )

    async def _advance_stage(self, tool_name: str, result: dict):
        """Transition to the next stage after a successful tool call."""
        prev = self._stage
        if tool_name == "validate_account" and result.get("valid"):
            self._stage = CallStage.ACCOUNT_VALIDATED
        elif tool_name == "classify_incident" and result.get("incident_type"):
            self._stage = CallStage.INCIDENT_CLASSIFIED
        elif tool_name == "check_coverage":
            self._stage = CallStage.COVERAGE_CHECKED
        elif tool_name == "dispatch_service" and result.get("dispatched"):
            self._stage = CallStage.DISPATCHED
        elif tool_name == "transfer_to_human_agent":
            self._stage = CallStage.RESOLVED
        if self._stage != prev:
            print(f"  [Stage] {prev.value} -> {self._stage.value}")
            await self._publish("stage_change", {
                "from": prev.value,
                "to": self._stage.value,
            })

    async def _send_realtime(self):
        """Read audio from browser queue and send to Gemini."""
        while not self._stop_event.is_set():
            try:
                data = await asyncio.wait_for(self.audio_in_queue.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            if self.session is not None:
                await self.session.send_realtime_input(
                    audio=types.Blob(data=data, mime_type="audio/pcm")
                )

    async def _receive_audio(self):
        """Receive responses from Gemini: audio, text, and tool calls."""
        while not self._stop_event.is_set():
            if self.session is None:
                await asyncio.sleep(0.1)
                continue

            try:
                turn = self.session.receive()
                async for response in turn:
                    if self._stop_event.is_set():
                        break

                    # Audio data → send to browser for playback
                    if data := response.data:
                        await self.audio_out_queue.put(data)

                    # Input transcription (user speech → text)
                    sc = response.server_content
                    if sc and sc.input_transcription and sc.input_transcription.text:
                        user_text = sc.input_transcription.text.strip()
                        if user_text:
                            print(f"User: {user_text}")
                            entry = TranscriptEntry(
                                role="user",
                                text=user_text,
                                timestamp=datetime.utcnow().isoformat() + "Z",
                            )
                            call = self.call_store.get_call(self.call_id)
                            if call:
                                call.transcript.append(entry)
                            await self._publish("transcript_update", entry.model_dump())

                    # Output transcription (agent speech → text)
                    if sc and sc.output_transcription and sc.output_transcription.text:
                        agent_text = sc.output_transcription.text.strip()
                        if agent_text:
                            print(f"Agent: {agent_text}")
                            entry = TranscriptEntry(
                                role="agent",
                                text=agent_text,
                                timestamp=datetime.utcnow().isoformat() + "Z",
                            )
                            call = self.call_store.get_call(self.call_id)
                            if call:
                                call.transcript.append(entry)
                            await self._publish("transcript_update", entry.model_dump())

                    # Agent text response (non-audio, fallback)
                    if text := response.text:
                        # Skip if we already got this from output_transcription
                        if not (sc and sc.output_transcription and sc.output_transcription.text):
                            print(f"Agent (text): {text}")
                            entry = TranscriptEntry(
                                role="agent",
                                text=text,
                                timestamp=datetime.utcnow().isoformat() + "Z",
                            )
                            call = self.call_store.get_call(self.call_id)
                            if call:
                                call.transcript.append(entry)
                            await self._publish("transcript_update", entry.model_dump())

                    # Tool calls — gate, execute, advance stage, batch responses
                    if hasattr(response, 'tool_call') and response.tool_call:
                        function_responses = []
                        for fc in response.tool_call.function_calls:
                            tool_name = fc.name
                            tool_id = fc.id
                            tool_args = dict(fc.args) if fc.args else {}
                            print(f"  [Tool Call] {tool_name}({tool_args}) id={tool_id} stage={self._stage.value}")

                            # --- State gate ---
                            blocked = self._gate_tool(tool_name)
                            if blocked:
                                print(f"  [BLOCKED] {blocked}")
                                result = {"error": blocked}
                            else:
                                try:
                                    result = await dispatch_tool(tool_name, tool_args)
                                except Exception as tool_err:
                                    print(f"  [Tool Error] {tool_err}")
                                    result = {"error": f"Tool execution failed: {tool_err}"}

                                # Advance stage on success (no error key)
                                if "error" not in result:
                                    await self._advance_stage(tool_name, result)

                            print(f"  [Tool Result] {json.dumps(result, indent=2)}")

                            tc_entry = ToolCallEntry(
                                tool=tool_name,
                                input=tool_args,
                                output=result,
                                timestamp=datetime.utcnow().isoformat() + "Z",
                            )
                            call = self.call_store.get_call(self.call_id)
                            if call:
                                call.tool_calls.append(tc_entry)
                            await self._publish("tool_call", tc_entry.model_dump())

                            self._update_collected_data(tool_name, tool_args, result)

                            # Check if this is a transfer request
                            if tool_name == "transfer_to_human_agent" and not blocked:
                                self._transfer_pending = True

                            function_responses.append(
                                types.FunctionResponse(
                                    id=tool_id,
                                    name=tool_name,
                                    response=result,
                                )
                            )

                        # Send all tool responses at once so Gemini
                        # immediately generates a spoken response
                        try:
                            await self.session.send_tool_response(
                                function_responses=function_responses
                            )
                            print(f"  [Sent {len(function_responses)} tool response(s)]")
                        except Exception as resp_err:
                            print(f"  [Tool Response Send Error] {resp_err}")
                            import traceback
                            traceback.print_exc()

                # Turn complete
                if self._transfer_pending:
                    print("Transfer requested — playing beep tones and ending call")
                    # Tell frontend to stop interrupting so beeps play through
                    await self._publish("call_status", {"status": "transferring"})
                    # Give Gemini's farewell a moment to be sent to browser
                    await asyncio.sleep(0.5)
                    # Send beep tones to the browser
                    beep_data = generate_beep_tones(RECEIVE_SAMPLE_RATE)
                    # Send in chunks to match typical audio chunk size
                    chunk_size = 4800  # 100ms at 24kHz, 2 bytes per sample
                    for i in range(0, len(beep_data), chunk_size):
                        await self.audio_out_queue.put(beep_data[i:i + chunk_size])
                    # Wait for beeps to finish playing (~1.4s of audio)
                    await asyncio.sleep(2.0)
                    await self._publish("call_status", {"status": "transferred"})
                    self._stop_event.set()
                    break

            except Exception as e:
                if self._stop_event.is_set():
                    break
                import traceback
                print(f"Receive error: {e}")
                traceback.print_exc()
                # If connection is dead (1007, ConnectionClosed), stop looping
                err_str = str(e)
                if "1007" in err_str or "ConnectionClosed" in err_str or "closed" in err_str.lower():
                    print("Gemini connection lost, stopping receive loop")
                    self._stop_event.set()
                    break
                await asyncio.sleep(0.5)

    def _update_collected_data(self, tool_name: str, args: dict, result: dict):
        """Update incident data from tool call results."""
        if tool_name == "validate_account" and result.get("valid"):
            self._collected_data.customer_name = result.get("customer_name")
            self._collected_data.policy_number = args.get("policy_number")
            self._collected_data.vehicle = result.get("vehicle")
            self._plan = result.get("plan")
        elif tool_name == "classify_incident":
            self._collected_data.incident_type = result.get("incident_type")
            self._collected_data.situation_summary = args.get("description")
        elif tool_name == "check_coverage":
            self._live_coverage_result = result
        elif tool_name == "dispatch_service" and result.get("dispatched"):
            self._live_dispatch_result = result

    async def _post_call_pipeline(self):
        """Generate a notification summarizing what happened during the call.

        Uses the live coverage result from check_coverage tool if available,
        rather than re-running coverage analysis.
        """
        call = self.call_store.get_call(self.call_id)
        if not call:
            return

        call.status = "processing"
        call.incident = self._collected_data
        await self._publish("call_status", {"status": "processing"})

        print("\n--- Post-Call Pipeline ---")
        print(f"Collected data: {self._collected_data.model_dump()}")
        print(f"Transfer: {self._transfer_pending}")
        print(f"Live coverage result: {self._live_coverage_result}")
        print(f"Live dispatch result: {self._live_dispatch_result}")

        # Use the coverage decision from the live call (check_coverage tool)
        if self._live_coverage_result:
            from app.models.call import CoverageDecision
            r = self._live_coverage_result
            call.coverage = CoverageDecision(
                status=r.get("status", "uncertain"),
                confidence=float(r.get("confidence", 0.5)),
                cited_clauses=r.get("cited_clauses", []),
                explanation=r.get("explanation", ""),
                requires_human_review=r.get("requires_human_review", False),
            )
            print(f"Coverage (from live call): {call.coverage.status}")

        # Use dispatch result from the live call (dispatch_service tool)
        if self._live_dispatch_result:
            d = self._live_dispatch_result
            garage = GarageInfo(
                name=d.get("provider", ""),
                address=d.get("provider_address", ""),
                distance_miles=d.get("distance_miles", 0),
                eta_minutes=d.get("eta_minutes", 0),
                phone=d.get("provider_phone", ""),
            )
            action = NextAction(
                recommended_action="dispatch_service",
                service_type=d.get("service_type", ""),
                assigned_garage=garage,
                estimated_arrival=d.get("estimated_arrival", ""),
            )
            call.action = action
            await self._publish("next_action", action.model_dump())
            print(f"Action (from live call): {action.service_type} -> {garage.name}")

        print("Generating notification...")
        notification = generate_notification(call)
        call.notification = notification
        await self._publish("notification", notification.model_dump())
        print(f"Notification:\n{notification.message_text}")

        call.status = "completed"
        call.ended_at = datetime.utcnow()
        await self._publish("call_status", {"status": "completed"})
        print("--- Pipeline Complete ---\n")

    async def run(self):
        """Connect to Gemini Live and run send/receive tasks until stopped."""
        self.call_store.create_call(self.call_id)
        await self._publish("call_status", {"status": "active", "call_id": self.call_id})
        print(f"Call started: {self.call_id}")

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("ERROR: GEMINI_API_KEY not set!")
            await self._publish("call_status", {"status": "error", "message": "API key not configured"})
            return

        client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=api_key,
        )

        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Zephyr")
                )
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            system_instruction=types.Content(
                parts=[types.Part(text=SYSTEM_INSTRUCTION)]
            ),
            tools=[TOOL_DECLARATIONS],
            # context_window_compression=types.ContextWindowCompressionConfig(
            #     trigger_tokens=104857,
            #     sliding_window=types.SlidingWindow(target_tokens=52428),
            # ),
        )

        try:
            async with client.aio.live.connect(model=MODEL, config=config) as session:
                self.session = session
                print("Gemini Live session connected")

                # Prompt the agent to greet the user immediately
                await session.send_realtime_input(text="Hello")

                send_task = asyncio.create_task(self._send_realtime())
                receive_task = asyncio.create_task(self._receive_audio())

                # Wait until stop is signaled
                await self._stop_event.wait()

                send_task.cancel()
                receive_task.cancel()
                try:
                    await send_task
                except asyncio.CancelledError:
                    pass
                try:
                    await receive_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            import traceback
            print(f"Gemini session error: {e}")
            traceback.print_exc()
            await self._publish("call_status", {"status": "error", "message": str(e)})
        finally:
            self.session = None
            await self._post_call_pipeline()
