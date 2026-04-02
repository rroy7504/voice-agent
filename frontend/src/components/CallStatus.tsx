interface Props {
  callId: string;
  status: string;
}

const STATUS_COLORS: Record<string, string> = {
  active: "#22c55e",
  processing: "#eab308",
  completed: "#6b7280",
  idle: "#9ca3af",
};

export function CallStatus({ callId, status }: Props) {
  const color = STATUS_COLORS[status] || "#9ca3af";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", background: "#1e293b", borderRadius: 8 }}>
      <div style={{ width: 12, height: 12, borderRadius: "50%", background: color, boxShadow: status === "active" ? `0 0 8px ${color}` : "none" }} />
      <div>
        <div style={{ fontSize: 14, fontWeight: 600, color: "#f1f5f9" }}>
          {status === "idle" ? "Waiting for call..." : `Call ${callId}`}
        </div>
        <div style={{ fontSize: 12, color: "#94a3b8", textTransform: "uppercase" }}>{status}</div>
      </div>
    </div>
  );
}
