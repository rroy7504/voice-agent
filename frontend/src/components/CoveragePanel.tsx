import type { CoverageDecision } from "../types";

interface Props {
  coverage: CoverageDecision | null;
}

const STATUS_CONFIG: Record<string, { bg: string; text: string; label: string }> = {
  covered: { bg: "#065f46", text: "#6ee7b7", label: "COVERED" },
  not_covered: { bg: "#7f1d1d", text: "#fca5a5", label: "NOT COVERED" },
  uncertain: { bg: "#78350f", text: "#fcd34d", label: "UNCERTAIN" },
};

export function CoveragePanel({ coverage }: Props) {
  if (!coverage) {
    return (
      <div style={{ background: "#0f172a", borderRadius: 8, padding: 16 }}>
        <h3 style={{ margin: "0 0 12px", color: "#f1f5f9", fontSize: 14, fontWeight: 600 }}>Coverage Decision</h3>
        <div style={{ color: "#475569", fontStyle: "italic", fontSize: 13 }}>Pending coverage analysis...</div>
      </div>
    );
  }

  const config = STATUS_CONFIG[coverage.status] || STATUS_CONFIG.uncertain;
  const confidencePct = Math.round(coverage.confidence * 100);

  return (
    <div style={{ background: "#0f172a", borderRadius: 8, padding: 16 }}>
      <h3 style={{ margin: "0 0 12px", color: "#f1f5f9", fontSize: 14, fontWeight: 600 }}>Coverage Decision</h3>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12 }}>
        <span style={{ padding: "4px 10px", borderRadius: 4, background: config.bg, color: config.text, fontWeight: 700, fontSize: 13 }}>
          {config.label}
        </span>
        {coverage.requires_human_review && (
          <span style={{ padding: "4px 10px", borderRadius: 4, background: "#78350f", color: "#fcd34d", fontSize: 12 }}>
            NEEDS REVIEW
          </span>
        )}
      </div>

      {/* Confidence bar */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, color: "#94a3b8", marginBottom: 4 }}>
          <span>Confidence</span>
          <span>{confidencePct}%</span>
        </div>
        <div style={{ height: 6, background: "#1e293b", borderRadius: 3 }}>
          <div style={{
            height: "100%",
            width: `${confidencePct}%`,
            background: confidencePct >= 70 ? "#22c55e" : confidencePct >= 40 ? "#eab308" : "#ef4444",
            borderRadius: 3,
            transition: "width 0.5s ease",
          }} />
        </div>
      </div>

      <div style={{ color: "#cbd5e1", fontSize: 13, marginBottom: 12 }}>{coverage.explanation}</div>

      {coverage.cited_clauses.length > 0 && (
        <div>
          <div style={{ color: "#94a3b8", fontSize: 12, marginBottom: 4 }}>Cited Clauses:</div>
          {coverage.cited_clauses.map((clause, i) => (
            <div key={i} style={{ color: "#a78bfa", fontSize: 12, padding: "2px 0" }}>{clause}</div>
          ))}
        </div>
      )}
    </div>
  );
}
