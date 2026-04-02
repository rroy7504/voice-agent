import { useCallback, useEffect, useRef, useReducer } from "react";
import type { TranscriptEntry, CustomerNotification } from "../types";

export interface CustomerCallState {
  isConnected: boolean;
  isCallActive: boolean;
  isMicActive: boolean;
  transcript: TranscriptEntry[];
  status: string; // idle, active, processing, completed
  notification: CustomerNotification | null;
  callId: string;
}

const initialState: CustomerCallState = {
  isConnected: false,
  isCallActive: false,
  isMicActive: false,
  transcript: [],
  status: "idle",
  notification: null,
  callId: "",
};

type Action =
  | { type: "CONNECTED" }
  | { type: "DISCONNECTED" }
  | { type: "MIC_ACTIVE"; active: boolean }
  | { type: "CALL_STATUS"; status: string; callId?: string }
  | { type: "TRANSCRIPT"; entry: TranscriptEntry }
  | { type: "NOTIFICATION"; notification: CustomerNotification }
  | { type: "RESET" };

function reducer(state: CustomerCallState, action: Action): CustomerCallState {
  switch (action.type) {
    case "CONNECTED":
      return { ...state, isConnected: true, isCallActive: true };
    case "DISCONNECTED":
      return { ...state, isConnected: false, isCallActive: false, isMicActive: false };
    case "MIC_ACTIVE":
      return { ...state, isMicActive: action.active };
    case "CALL_STATUS":
      return {
        ...state,
        status: action.status,
        callId: action.callId || state.callId,
        isCallActive: action.status === "active",
      };
    case "TRANSCRIPT": {
      const prev = state.transcript;
      const last = prev[prev.length - 1];
      // Append to the last bubble if same role and no attachment on either
      if (last && last.role === action.entry.role && !last.attachment && !action.entry.attachment) {
        const updated = [...prev];
        updated[updated.length - 1] = {
          ...last,
          text: last.text + " " + action.entry.text,
          timestamp: action.entry.timestamp,
        };
        return { ...state, transcript: updated };
      }
      return { ...state, transcript: [...prev, action.entry] };
    }
    case "NOTIFICATION":
      return { ...state, notification: action.notification };
    case "RESET":
      return initialState;
    default:
      return state;
  }
}

const WS_URL = `ws://${window.location.hostname}:8000/ws/call`;


export function useCallWebSocket() {
  const [state, dispatch] = useReducer(reducer, initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const micStreamRef = useRef<MediaStream | null>(null);

  // Playback state for received Gemini audio
  const playbackCtxRef = useRef<AudioContext | null>(null);
  const nextPlayTimeRef = useRef(0);
  const gainNodeRef = useRef<GainNode | null>(null);
  const pendingTranscriptsRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // VAD interruption state
  const loudFrameCountRef = useRef(0);
  const vadEnabledRef = useRef(true);
  const VAD_RMS_THRESHOLD = 800;    // Int16 RMS threshold (out of 32768)
  const VAD_FRAMES_REQUIRED = 3;    // consecutive loud frames (~150ms) before interrupt

  // Stop all agent audio and pending transcript chunks
  const interruptPlayback = useCallback(() => {
    const ctx = playbackCtxRef.current;
    if (!ctx || ctx.state === "closed") return;

    // Disconnect old gain node to instantly silence all scheduled sources
    gainNodeRef.current?.disconnect();
    const gain = ctx.createGain();
    gain.gain.value = 1.0;
    gain.connect(ctx.destination);
    gainNodeRef.current = gain;

    // Reset playback clock so next audio starts immediately
    nextPlayTimeRef.current = 0;

    // Cancel pending transcript timers
    pendingTranscriptsRef.current.forEach(clearTimeout);
    pendingTranscriptsRef.current = [];
  }, []);

  const playAudioChunk = useCallback((pcmData: ArrayBuffer) => {
    const ctx = playbackCtxRef.current;
    if (!ctx || ctx.state === "closed") return;

    // Resume if suspended (browser autoplay policy)
    if (ctx.state === "suspended") {
      ctx.resume();
    }

    // Convert Int16 PCM to Float32
    const int16 = new Int16Array(pcmData);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768;
    }

    const buffer = ctx.createBuffer(1, float32.length, 24000);
    buffer.copyToChannel(float32, 0);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(gainNodeRef.current || ctx.destination);

    const now = ctx.currentTime;
    const startTime = Math.max(now + 0.01, nextPlayTimeRef.current);
    source.start(startTime);
    nextPlayTimeRef.current = startTime + buffer.duration;
  }, []);

  const startCall = useCallback(async () => {
    dispatch({ type: "RESET" });
    vadEnabledRef.current = true;
    loudFrameCountRef.current = 0;

    // Create playback AudioContext eagerly (inside user gesture)
    // so it won't be blocked by autoplay policy
    const playbackCtx = new AudioContext({ sampleRate: 24000 });
    playbackCtxRef.current = playbackCtx;
    nextPlayTimeRef.current = 0;
    const gain = playbackCtx.createGain();
    gain.gain.value = 1.0;
    gain.connect(playbackCtx.destination);
    gainNodeRef.current = gain;
    // Force resume within user gesture
    if (playbackCtx.state === "suspended") {
      await playbackCtx.resume();
    }

    // Open WebSocket
    const ws = new WebSocket(WS_URL);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;

    // Wait for WS to open before starting mic
    await new Promise<void>((resolve, reject) => {
      ws.onopen = () => {
        dispatch({ type: "CONNECTED" });
        resolve();
      };
      ws.onerror = () => {
        reject(new Error("WebSocket connection failed"));
        ws.close();
      };
      // If already open
      if (ws.readyState === WebSocket.OPEN) {
        dispatch({ type: "CONNECTED" });
        resolve();
      }
    });

    ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary = Gemini audio response
        playAudioChunk(event.data);
      } else {
        // JSON event
        try {
          const msg = JSON.parse(event.data);
          const { event_type, payload } = msg;
          switch (event_type) {
            case "call_status":
              // Disable VAD interruption during transfer so beeps play
              if (payload.status === "transferring" || payload.status === "transferred") {
                vadEnabledRef.current = false;
              }
              dispatch({
                type: "CALL_STATUS",
                status: payload.status,
                callId: payload.call_id,
              });
              break;
            case "transcript_update": {
              const entry = payload as TranscriptEntry;
              const isAgent = entry.role === "agent";
              const ctx = playbackCtxRef.current;
              // Delay agent text to sync with audio playback
              if (isAgent && ctx && ctx.state === "running") {
                const delay = Math.max(0, (nextPlayTimeRef.current - ctx.currentTime) * 1000);
                const timer = setTimeout(() => {
                  dispatch({ type: "TRANSCRIPT", entry });
                }, delay);
                pendingTranscriptsRef.current.push(timer);
              } else {
                dispatch({ type: "TRANSCRIPT", entry });
              }
              break;
            }
            case "notification":
              dispatch({
                type: "NOTIFICATION",
                notification: payload as CustomerNotification,
              });
              break;
          }
        } catch {
          // ignore parse errors
        }
      }
    };

    ws.onclose = () => {
      dispatch({ type: "DISCONNECTED" });
    };

    // Start microphone capture
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      micStreamRef.current = stream;

      const audioCtx = new AudioContext({ sampleRate: 48000 });
      audioContextRef.current = audioCtx;

      if (audioCtx.state === "suspended") {
        await audioCtx.resume();
      }

      await audioCtx.audioWorklet.addModule("/pcm-worklet-processor.js");

      const source = audioCtx.createMediaStreamSource(stream);
      const worklet = new AudioWorkletNode(audioCtx, "pcm-processor");
      workletNodeRef.current = worklet;

      worklet.port.onmessage = (e) => {
        const pcmBuf: ArrayBuffer = e.data;

        // Compute RMS energy for voice activity detection
        const samples = new Int16Array(pcmBuf);
        let sumSq = 0;
        for (let i = 0; i < samples.length; i++) {
          sumSq += samples[i] * samples[i];
        }
        const rms = Math.sqrt(sumSq / samples.length);

        if (vadEnabledRef.current && rms > VAD_RMS_THRESHOLD) {
          loudFrameCountRef.current++;
          if (loudFrameCountRef.current === VAD_FRAMES_REQUIRED) {
            // User is speaking — interrupt agent playback
            interruptPlayback();
          }
        } else {
          loudFrameCountRef.current = 0;
        }

        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(pcmBuf);
        }
      };

      source.connect(worklet);
      worklet.connect(audioCtx.destination); // needed to keep the worklet running
      dispatch({ type: "MIC_ACTIVE", active: true });
    } catch (err) {
      console.error("Microphone access failed:", err);
    }
  }, [playAudioChunk, interruptPlayback]);

  const endCall = useCallback(() => {
    // Send end_call signal
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "end_call" }));
    }

    // Stop mic
    micStreamRef.current?.getTracks().forEach((t) => t.stop());
    micStreamRef.current = null;
    workletNodeRef.current?.disconnect();
    workletNodeRef.current = null;
    audioContextRef.current?.close();
    audioContextRef.current = null;
    dispatch({ type: "MIC_ACTIVE", active: false });

    // Flush pending transcript timers
    pendingTranscriptsRef.current.forEach(clearTimeout);
    pendingTranscriptsRef.current = [];

    // Close playback context
    playbackCtxRef.current?.close();
    playbackCtxRef.current = null;
    gainNodeRef.current = null;
    nextPlayTimeRef.current = 0;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      pendingTranscriptsRef.current.forEach(clearTimeout);
      micStreamRef.current?.getTracks().forEach((t) => t.stop());
      audioContextRef.current?.close();
      playbackCtxRef.current?.close();
      wsRef.current?.close();
    };
  }, []);

  const sendText = useCallback((text: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "text_message", text }));
      dispatch({
        type: "TRANSCRIPT",
        entry: { role: "user", text, timestamp: new Date().toISOString() },
      });
    }
  }, []);

  const shareLocation = useCallback(() => {
    // Mock location — pretend we got GPS coords
    const mockLat = 37.7749 + (Math.random() - 0.5) * 0.05;
    const mockLng = -122.4194 + (Math.random() - 0.5) * 0.05;
    const locationText = `Sharing location: ${mockLat.toFixed(4)}, ${mockLng.toFixed(4)}`;

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "text_message", text: locationText })
      );
    }
    dispatch({
      type: "TRANSCRIPT",
      entry: {
        role: "user",
        text: locationText,
        timestamp: new Date().toISOString(),
        attachment: {
          type: "location",
          label: `${mockLat.toFixed(4)}, ${mockLng.toFixed(4)}`,
        },
      },
    });
  }, []);

  const shareImage = useCallback((file: File) => {
    const url = URL.createObjectURL(file);
    const caption = `Shared image: ${file.name}`;

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "text_message", text: caption })
      );
    }
    dispatch({
      type: "TRANSCRIPT",
      entry: {
        role: "user",
        text: caption,
        timestamp: new Date().toISOString(),
        attachment: { type: "image", label: file.name, url },
      },
    });
  }, []);

  return { state, startCall, endCall, sendText, shareLocation, shareImage };
}
