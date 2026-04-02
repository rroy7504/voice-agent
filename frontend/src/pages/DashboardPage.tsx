import { useWebSocket } from "../hooks/useWebSocket";
import { CallStatus } from "../components/CallStatus";
import { TranscriptPanel } from "../components/TranscriptPanel";
import { ToolCallLog } from "../components/ToolCallLog";
import { CoveragePanel } from "../components/CoveragePanel";
import { ActionPanel } from "../components/ActionPanel";
import { OverrideBar } from "../components/OverrideBar";

const WS_URL = "ws://localhost:8000/ws/dashboard";

export default function DashboardPage() {
  const state = useWebSocket(WS_URL);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0f172a",
      color: "#f1f5f9",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    }}>
      <header style={{
        padding: "16px 24px",
        background: "#1e293b",
        borderBottom: "1px solid #334155",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}>
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Insurance Co-Pilot</h1>
        <span style={{ color: "#94a3b8", fontSize: 13 }}>Human Agent Dashboard</span>
      </header>

      <div style={{ padding: "16px 24px", display: "flex", gap: 16 }}>
        <div style={{ flex: "0 0 auto" }}>
          <CallStatus callId={state.callId} status={state.status} />
        </div>
        <div style={{ flex: 1 }}>
          <OverrideBar callId={state.callId} status={state.status} humanOverride={state.humanOverride} />
        </div>
      </div>

      <div style={{
        padding: "0 24px 24px",
        display: "grid",
        gridTemplateColumns: "1fr 1fr",
        gap: 16,
        height: "calc(100vh - 140px)",
      }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, overflow: "hidden" }}>
          <TranscriptPanel transcript={state.transcript} />
          <ToolCallLog toolCalls={state.toolCalls} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, overflow: "auto" }}>
          <CoveragePanel coverage={state.coverage} />
          <ActionPanel action={state.action} notification={state.notification} />
        </div>
      </div>
    </div>
  );
}
