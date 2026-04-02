import { useState } from "react";
import type { ToolCallEntry } from "../types";

interface Props {
  toolCalls: ToolCallEntry[];
}

export function ToolCallLog({ toolCalls }: Props) {
  const [expanded, setExpanded] = useState<number | null>(null);

  return (
    <div style={{ background: "#0f172a", borderRadius: 8, padding: 16 }}>
      <h3 style={{ margin: "0 0 12px", color: "#f1f5f9", fontSize: 14, fontWeight: 600 }}>Tool Calls</h3>
      {toolCalls.length === 0 && (
        <div style={{ color: "#475569", fontStyle: "italic", fontSize: 13 }}>No tool calls yet</div>
      )}
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {toolCalls.map((tc, i) => (
          <div
            key={i}
            style={{ background: "#1e293b", borderRadius: 6, padding: "8px 12px", cursor: "pointer" }}
            onClick={() => setExpanded(expanded === i ? null : i)}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "#a78bfa", fontWeight: 600, fontSize: 13 }}>{tc.tool}</span>
              <span style={{ color: "#475569", fontSize: 11 }}>
                {new Date(tc.timestamp).toLocaleTimeString()}
              </span>
            </div>
            {expanded === i && (
              <div style={{ marginTop: 8, fontSize: 12 }}>
                <div style={{ color: "#94a3b8", marginBottom: 4 }}>Input:</div>
                <pre style={{ color: "#cbd5e1", background: "#0f172a", padding: 8, borderRadius: 4, overflow: "auto", margin: 0 }}>
                  {JSON.stringify(tc.input, null, 2)}
                </pre>
                <div style={{ color: "#94a3b8", marginTop: 8, marginBottom: 4 }}>Output:</div>
                <pre style={{ color: "#cbd5e1", background: "#0f172a", padding: 8, borderRadius: 4, overflow: "auto", margin: 0 }}>
                  {JSON.stringify(tc.output, null, 2)}
                </pre>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
