import { useEffect, useRef } from "react";
import type { TranscriptEntry } from "../types";

interface Props {
  transcript: TranscriptEntry[];
}

export function TranscriptPanel({ transcript }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcript.length]);

  return (
    <div style={{ background: "#0f172a", borderRadius: 8, padding: 16, flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
      <h3 style={{ margin: "0 0 12px", color: "#f1f5f9", fontSize: 14, fontWeight: 600 }}>Live Transcript</h3>
      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: 8 }}>
        {transcript.length === 0 && (
          <div style={{ color: "#475569", fontStyle: "italic", fontSize: 13 }}>Waiting for conversation...</div>
        )}
        {transcript.map((entry, i) => (
          <div key={entry.id || i} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
            <span style={{
              fontSize: 11,
              fontWeight: 600,
              padding: "2px 6px",
              borderRadius: 4,
              background: entry.role === "agent" ? "#1e40af" : "#065f46",
              color: "#f1f5f9",
              flexShrink: 0,
            }}>
              {entry.role === "agent" ? "AGENT" : "CUSTOMER"}
            </span>
            <span style={{ color: "#cbd5e1", fontSize: 13 }}>{entry.text}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
