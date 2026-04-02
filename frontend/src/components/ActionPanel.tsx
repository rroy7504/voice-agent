import type { NextAction, CustomerNotification } from "../types";

interface Props {
  action: NextAction | null;
  notification: CustomerNotification | null;
}

export function ActionPanel({ action, notification }: Props) {
  return (
    <div style={{ background: "#0f172a", borderRadius: 8, padding: 16 }}>
      <h3 style={{ margin: "0 0 12px", color: "#f1f5f9", fontSize: 14, fontWeight: 600 }}>Recommended Action</h3>

      {!action && !notification && (
        <div style={{ color: "#475569", fontStyle: "italic", fontSize: 13 }}>Waiting for coverage decision...</div>
      )}

      {action && (
        <div style={{ marginBottom: 16 }}>
          <div style={{ padding: "8px 12px", background: "#1e293b", borderRadius: 6, marginBottom: 8 }}>
            <div style={{ color: "#38bdf8", fontWeight: 600, fontSize: 13 }}>{action.service_type}</div>
            <div style={{ color: "#94a3b8", fontSize: 12, marginTop: 4 }}>{action.recommended_action.replace(/_/g, " ")}</div>
          </div>
          <div style={{ padding: "8px 12px", background: "#1e293b", borderRadius: 6 }}>
            <div style={{ color: "#f1f5f9", fontWeight: 600, fontSize: 13 }}>{action.assigned_garage.name}</div>
            <div style={{ color: "#94a3b8", fontSize: 12 }}>{action.assigned_garage.address}</div>
            <div style={{ display: "flex", gap: 16, marginTop: 4 }}>
              <span style={{ color: "#6ee7b7", fontSize: 12 }}>ETA: {action.assigned_garage.eta_minutes} min</span>
              <span style={{ color: "#94a3b8", fontSize: 12 }}>{action.assigned_garage.distance_miles} miles</span>
              <span style={{ color: "#94a3b8", fontSize: 12 }}>{action.assigned_garage.phone}</span>
            </div>
          </div>
        </div>
      )}

      {notification && (
        <div>
          <div style={{ color: "#94a3b8", fontSize: 12, marginBottom: 4 }}>Customer Notification ({notification.reference_number}):</div>
          <pre style={{
            color: "#cbd5e1",
            fontSize: 12,
            background: "#1e293b",
            padding: 12,
            borderRadius: 6,
            whiteSpace: "pre-wrap",
            margin: 0,
          }}>
            {notification.message_text}
          </pre>
        </div>
      )}
    </div>
  );
}
