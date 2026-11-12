import React from "react";

const LAYERS = [
  { key: "UPLOADED", label: "Bronze", desc: "Raw PDFs saved" },
  { key: "SILVER_DONE", label: "Silver", desc: "Text extracted" },
  { key: "GOLD_DONE", label: "Gold", desc: "Claim structured" },
  { key: "ADJUDICATED", label: "Agent", desc: "Decision ready" },
];

const STATUS_ORDER = ["UPLOADED", "SILVER_DONE", "GOLD_DONE", "ADJUDICATED"];

const LAYER_COLORS = {
  Bronze: "#cd7f32",
  Silver: "#aaa9ad",
  Gold: "#f0c040",
  Agent: "#4a90d9",
};

export default function MedallionStatus({ status }) {
  const currentIndex = STATUS_ORDER.indexOf(status);

  return (
    <div style={styles.container}>
      {LAYERS.map((layer, i) => {
        const done = i <= currentIndex;
        const color = done ? LAYER_COLORS[layer.label] : "#333";
        return (
          <div key={layer.key} style={styles.step}>
            <div style={{ ...styles.circle, background: done ? color : "#1e2535", borderColor: color }}>
              {done ? "✓" : i + 1}
            </div>
            <div style={styles.info}>
              <div style={{ ...styles.name, color: done ? color : "#555" }}>{layer.label}</div>
              <div style={styles.desc}>{layer.desc}</div>
            </div>
            {i < LAYERS.length - 1 && (
              <div style={{ ...styles.line, background: done && currentIndex > i ? color : "#2a3545" }} />
            )}
          </div>
        );
      })}
    </div>
  );
}

const styles = {
  container: { display: "flex", alignItems: "center", gap: "0", margin: "20px 0" },
  step: { display: "flex", alignItems: "center", flex: 1 },
  circle: {
    width: 32,
    height: 32,
    borderRadius: "50%",
    border: "2px solid",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: "13px",
    fontWeight: 700,
    color: "#fff",
    flexShrink: 0,
  },
  info: { marginLeft: 8, marginRight: 4 },
  name: { fontSize: "12px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.5px" },
  desc: { fontSize: "10px", color: "#556" },
  line: { flex: 1, height: 2, margin: "0 4px" },
};
