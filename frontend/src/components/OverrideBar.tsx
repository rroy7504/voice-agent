import { useState } from "react";

interface Props {
  callId: string;
  status: string;
  humanOverride: string | null;
}

export function OverrideBar({ callId, status, humanOverride }: Props) {
  const [loading, setLoading] = useState(false);

  const canOverride = status === "completed" || status === "processing";

  const handleOverride = async (action: string) => {
    if (!callId) return;
    setLoading(true);
    try {
      await fetch(`http://localhost:8000/calls/${callId}/override`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action, notes: "" }),
      });
    } catch (err) {
      console.error("Override failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: "#1e293b", borderRadius: 8, padding: 12, display: "flex", alignItems: "center", gap: 12 }}>
      <span style={{ color: "#94a3b8", fontSize: 13, flexShrink: 0 }}>Agent Actions:</span>
      <button
        disabled={!canOverride || loading}
        onClick={() => handleOverride("approve")}
        style={{
          padding: "6px 16px", borderRadius: 6, border: "none", cursor: canOverride ? "pointer" : "not-allowed",
          background: canOverride ? "#065f46" : "#1e293b", color: canOverride ? "#6ee7b7" : "#475569",
          fontWeight: 600, fontSize: 13,
        }}
      >
        Approve
      </button>
      <button
        disabled={!canOverride || loading}
        onClick={() => handleOverride("deny")}
        style={{
          padding: "6px 16px", borderRadius: 6, border: "none", cursor: canOverride ? "pointer" : "not-allowed",
          background: canOverride ? "#7f1d1d" : "#1e293b", color: canOverride ? "#fca5a5" : "#475569",
          fontWeight: 600, fontSize: 13,
        }}
      >
        Deny
      </button>
      <button
        disabled={!canOverride || loading}
        onClick={() => handleOverride("escalate")}
        style={{
          padding: "6px 16px", borderRadius: 6, border: "none", cursor: canOverride ? "pointer" : "not-allowed",
          background: canOverride ? "#78350f" : "#1e293b", color: canOverride ? "#fcd34d" : "#475569",
          fontWeight: 600, fontSize: 13,
        }}
      >
        Escalate
      </button>
      {humanOverride && (
        <span style={{ color: "#a78bfa", fontSize: 12, marginLeft: "auto" }}>Override: {humanOverride}</span>
      )}
    </div>
  );
}
