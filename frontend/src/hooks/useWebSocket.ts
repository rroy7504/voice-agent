import { useEffect, useReducer, useRef, useCallback } from "react";
import type {
  CallState,
  WSEvent,
  TranscriptEntry,
  ToolCallEntry,
  CoverageDecision,
  NextAction,
  CustomerNotification,
} from "../types";

const initialState: CallState = {
  callId: "",
  status: "idle",
  transcript: [],
  toolCalls: [],
  coverage: null,
  action: null,
  notification: null,
  humanOverride: null,
};

type Action =
  | { type: "CALL_STATUS"; callId: string; status: string }
  | { type: "TRANSCRIPT_UPDATE"; entry: TranscriptEntry }
  | { type: "TOOL_CALL"; entry: ToolCallEntry }
  | { type: "COVERAGE_DECISION"; decision: CoverageDecision }
  | { type: "NEXT_ACTION"; action: NextAction }
  | { type: "NOTIFICATION"; notification: CustomerNotification }
  | { type: "HUMAN_OVERRIDE"; override: string }
  | { type: "RESET" };

function reducer(state: CallState, action: Action): CallState {
  switch (action.type) {
    case "CALL_STATUS":
      return {
        ...state,
        callId: action.callId || state.callId,
        status: action.status as CallState["status"],
      };
    case "TRANSCRIPT_UPDATE": {
      const prev = state.transcript;
      const last = prev[prev.length - 1];
      if (last && last.role === action.entry.role) {
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
    case "TOOL_CALL":
      return { ...state, toolCalls: [...state.toolCalls, action.entry] };
    case "COVERAGE_DECISION":
      return { ...state, coverage: action.decision };
    case "NEXT_ACTION":
      return { ...state, action: action.action };
    case "NOTIFICATION":
      return { ...state, notification: action.notification };
    case "HUMAN_OVERRIDE":
      return { ...state, humanOverride: action.override };
    case "RESET":
      return initialState;
    default:
      return state;
  }
}

export function useWebSocket(url: string) {
  const [state, dispatch] = useReducer(reducer, initialState);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => console.log("WebSocket connected");

    ws.onmessage = (event) => {
      const data: WSEvent = JSON.parse(event.data);
      const { event_type, call_id, payload } = data;

      switch (event_type) {
        case "call_status":
          dispatch({
            type: "CALL_STATUS",
            callId: (payload.call_id as string) || call_id,
            status: payload.status as string,
          });
          break;
        case "transcript_update":
          dispatch({
            type: "TRANSCRIPT_UPDATE",
            entry: payload as unknown as TranscriptEntry,
          });
          break;
        case "tool_call":
          dispatch({
            type: "TOOL_CALL",
            entry: payload as unknown as ToolCallEntry,
          });
          break;
        case "coverage_decision":
          dispatch({
            type: "COVERAGE_DECISION",
            decision: payload as unknown as CoverageDecision,
          });
          break;
        case "next_action":
          dispatch({
            type: "NEXT_ACTION",
            action: payload as unknown as NextAction,
          });
          break;
        case "notification":
          dispatch({
            type: "NOTIFICATION",
            notification: payload as unknown as CustomerNotification,
          });
          break;
        case "human_override":
          dispatch({
            type: "HUMAN_OVERRIDE",
            override: `${payload.action}: ${payload.notes}`,
          });
          break;
      }
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected, reconnecting in 3s...");
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => ws.close();
  }, [url]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return state;
}
