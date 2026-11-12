import React from "react";
import { STATUS_META } from "../constants";

export default function StatusBadge({ status, size = "sm" }) {
  const meta = STATUS_META[status] || { label: status, color: "#666", bg: "#eee", dot: "#666" };
  const pad  = size === "lg" ? "5px 12px" : "3px 9px";
  const fs   = size === "lg" ? 13 : 11;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 5,
      background: meta.bg, color: meta.color,
      padding: pad, borderRadius: 20, fontSize: fs, fontWeight: 700,
      whiteSpace: "nowrap",
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: meta.dot, flexShrink: 0 }} />
      {meta.label}
    </span>
  );
}
