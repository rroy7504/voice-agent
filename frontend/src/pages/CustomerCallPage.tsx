import { useRef, useEffect, useState } from "react";
import { useCallWebSocket } from "../hooks/useCallWebSocket";

export default function CustomerCallPage() {
  const { state, startCall, endCall, sendText } = useCallWebSocket();
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const [textInput, setTextInput] = useState("");

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [state.transcript]);

  const handleSendText = () => {
    const trimmed = textInput.trim();
    if (!trimmed) return;
    sendText(trimmed);
    setTextInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendText();
    }
  };

  const isUserRole = (role: string) => role === "user" || role === "customer";

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0f172a",
        color: "#f1f5f9",
        fontFamily:
          "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <header
        style={{
          padding: "16px 24px",
          background: "#1e293b",
          borderBottom: "1px solid #334155",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>
          Roadside Assistance
        </h1>
        {state.callId && (
          <span style={{ color: "#94a3b8", fontSize: 12 }}>
            Call: {state.callId}
          </span>
        )}
      </header>

      {/* Main content */}
      <div
        style={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          maxWidth: 640,
          width: "100%",
          margin: "0 auto",
          padding: "16px 16px 0",
        }}
      >
        {/* Status bar */}
        {state.status !== "idle" && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: "8px 12px",
              marginBottom: 12,
              background: "#1e293b",
              borderRadius: 8,
              fontSize: 13,
            }}
          >
            <div
              style={{
                width: 8,
                height: 8,
                borderRadius: "50%",
                background: state.isCallActive
                  ? "#22c55e"
                  : state.status === "processing"
                    ? "#eab308"
                    : "#6b7280",
                boxShadow: state.isCallActive ? "0 0 6px #22c55e" : "none",
              }}
            />
            <span style={{ color: "#94a3b8" }}>
              {state.status === "active" &&
                state.isMicActive &&
                "Connected — speak now"}
              {state.status === "active" &&
                !state.isMicActive &&
                "Connecting microphone..."}
              {state.status === "processing" && "Processing your request..."}
              {state.status === "transferring" && "Transferring to a human agent..."}
              {state.status === "transferred" && "Transferred to a human agent"}
              {state.status === "completed" && "Call ended"}
            </span>
            {state.isMicActive && (
              <div
                style={{
                  marginLeft: "auto",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                  color: "#ef4444",
                  fontSize: 12,
                }}
              >
                <div
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: "50%",
                    background: "#ef4444",
                    animation: "pulse 1.5s ease-in-out infinite",
                  }}
                />
                MIC
              </div>
            )}
          </div>
        )}

        {/* Transcript */}
        <div
          style={{
            flex: 1,
            overflowY: "auto",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            paddingBottom: 16,
            minHeight: 200,
          }}
        >
          {state.transcript.length === 0 && state.status === "idle" && (
            <div
              style={{
                flex: 1,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                color: "#475569",
                gap: 12,
              }}
            >
              <svg
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
              </svg>
              <p style={{ fontSize: 14 }}>
                Press the button below to connect with an agent
              </p>
            </div>
          )}

          {state.transcript.length === 0 && state.status === "active" && (
            <div
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#475569",
                fontStyle: "italic",
                fontSize: 13,
              }}
            >
              Waiting for the agent to greet you...
            </div>
          )}

          {state.transcript.map((entry, i) => {
            const fromUser = isUserRole(entry.role);
            return (
              <div
                key={i}
                style={{
                  display: "flex",
                  justifyContent: fromUser ? "flex-end" : "flex-start",
                }}
              >
                <div
                  style={{
                    maxWidth: "80%",
                    padding: "10px 14px",
                    borderRadius: fromUser
                      ? "16px 16px 4px 16px"
                      : "16px 16px 16px 4px",
                    background: fromUser ? "#1e40af" : "#1e293b",
                    color: "#f1f5f9",
                    fontSize: 14,
                    lineHeight: 1.5,
                  }}
                >
                  {!fromUser && (
                    <div
                      style={{
                        fontSize: 11,
                        color: "#94a3b8",
                        marginBottom: 4,
                        fontWeight: 600,
                      }}
                    >
                      Alex
                    </div>
                  )}
                  {entry.text}

                  {/* Location attachment */}
                  {entry.attachment?.type === "location" && (
                    <div
                      style={{
                        marginTop: 8,
                        padding: "8px 10px",
                        background: "rgba(255,255,255,0.08)",
                        borderRadius: 8,
                        fontSize: 12,
                        display: "flex",
                        alignItems: "center",
                        gap: 6,
                      }}
                    >
                      <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#60a5fa"
                        strokeWidth="2"
                      >
                        <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" />
                        <circle cx="12" cy="10" r="3" />
                      </svg>
                      <span style={{ color: "#93c5fd" }}>
                        {entry.attachment.label}
                      </span>
                    </div>
                  )}

                  {/* Image attachment */}
                  {entry.attachment?.type === "image" && entry.attachment.url && (
                    <div style={{ marginTop: 8 }}>
                      <img
                        src={entry.attachment.url}
                        alt={entry.attachment.label}
                        style={{
                          maxWidth: "100%",
                          maxHeight: 200,
                          borderRadius: 8,
                          display: "block",
                        }}
                      />
                    </div>
                  )}
                </div>
              </div>
            );
          })}
          <div ref={transcriptEndRef} />
        </div>

        {/* Notification (after call) */}
        {state.notification && (
          <div
            style={{
              background: "#1e293b",
              borderRadius: 12,
              padding: 16,
              marginBottom: 12,
              border: "1px solid #334155",
            }}
          >
            <div
              style={{
                fontSize: 12,
                color: "#94a3b8",
                marginBottom: 8,
                fontWeight: 600,
              }}
            >
              {state.notification.reference_number}
            </div>
            <pre
              style={{
                color: "#cbd5e1",
                fontSize: 13,
                whiteSpace: "pre-wrap",
                margin: 0,
                lineHeight: 1.5,
              }}
            >
              {state.notification.message_text}
            </pre>
          </div>
        )}

        {/* Text input (visible during active call) */}
        {state.isCallActive && (
          <div
            style={{
              display: "flex",
              gap: 8,
              padding: "8px 0",
              alignItems: "flex-end",
            }}
          >
            {/* Text input */}
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type a message..."
              style={{
                flex: 1,
                padding: "9px 14px",
                borderRadius: 10,
                border: "1px solid #334155",
                background: "#1e293b",
                color: "#f1f5f9",
                fontSize: 14,
                outline: "none",
              }}
            />

            {/* Send */}
            <button
              onClick={handleSendText}
              disabled={!textInput.trim()}
              style={{
                width: 38,
                height: 38,
                borderRadius: 10,
                border: "none",
                background: textInput.trim() ? "#3b82f6" : "#334155",
                color: "#fff",
                cursor: textInput.trim() ? "pointer" : "default",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="currentColor"
              >
                <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
              </svg>
            </button>
          </div>
        )}

        {/* Call button */}
        <div
          style={{
            padding: "12px 0 24px",
            display: "flex",
            justifyContent: "center",
          }}
        >
          {!state.isCallActive && state.status !== "processing" ? (
            <button
              onClick={startCall}
              style={{
                padding: "14px 40px",
                borderRadius: 50,
                border: "none",
                background: "#22c55e",
                color: "#fff",
                fontSize: 16,
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 0 20px rgba(34,197,94,0.3)",
                transition: "all 0.2s",
              }}
              onMouseEnter={(e) =>
                (e.currentTarget.style.background = "#16a34a")
              }
              onMouseLeave={(e) =>
                (e.currentTarget.style.background = "#22c55e")
              }
            >
              {state.status === "completed" ? "Start New Call" : "Start Call"}
            </button>
          ) : (
            <button
              onClick={endCall}
              disabled={state.status === "processing"}
              style={{
                padding: "14px 40px",
                borderRadius: 50,
                border: "none",
                background:
                  state.status === "processing" ? "#475569" : "#ef4444",
                color: "#fff",
                fontSize: 16,
                fontWeight: 700,
                cursor:
                  state.status === "processing" ? "not-allowed" : "pointer",
                transition: "all 0.2s",
              }}
            >
              {state.status === "processing" ? "Processing..." : "End Call"}
            </button>
          )}
        </div>
      </div>

      {/* CSS animation for mic pulse */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
