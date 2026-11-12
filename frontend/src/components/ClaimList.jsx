import React from "react";

const STATUS_COLOR = {
  UPLOADED: "#888",
  SILVER_DONE: "#aaa",
  GOLD_DONE: "#f0a500",
  ADJUDICATED: "#4caf50",
};

const DECISION_COLOR = {
  APPROVED: "#2e7d32",
  DENIED: "#c62828",
  NEEDS_REVIEW: "#e65100",
};

export default function ClaimList({ claims, selectedId, onSelect }) {
  if (!claims.length) {
    return (
      <div style={styles.empty}>No claims yet. Upload a claim to get started.</div>
    );
  }

  return (
    <div>
      {claims.map((c) => (
        <div
          key={c.claim_id}
          onClick={() => onSelect(c.claim_id)}
          style={{
            ...styles.item,
            background: c.claim_id === selectedId ? "#1e2a3a" : "transparent",
          }}
        >
          <div style={styles.claimId}>#{c.claim_id}</div>
          <div style={styles.row}>
            <span style={{ ...styles.badge, background: STATUS_COLOR[c.status] || "#888" }}>
              {c.status.replace("_", " ")}
            </span>
            {c.decision && (
              <span style={{ ...styles.badge, background: DECISION_COLOR[c.decision] || "#888" }}>
                {c.decision}
              </span>
            )}
          </div>
          <div style={styles.date}>
            {c.created_at ? new Date(c.created_at).toLocaleString() : ""}
          </div>
        </div>
      ))}
    </div>
  );
}

const styles = {
  empty: { padding: "16px", color: "#888", fontSize: "13px" },
  item: {
    padding: "12px 16px",
    borderBottom: "1px solid #1a2535",
    cursor: "pointer",
    borderRadius: "4px",
  },
  claimId: { fontWeight: 600, color: "#e0e6f0", fontSize: "13px", marginBottom: "6px" },
  row: { display: "flex", gap: "6px", flexWrap: "wrap", marginBottom: "4px" },
  badge: {
    fontSize: "10px",
    fontWeight: 700,
    padding: "2px 7px",
    borderRadius: "10px",
    color: "#fff",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
  },
  date: { fontSize: "11px", color: "#667" },
};
