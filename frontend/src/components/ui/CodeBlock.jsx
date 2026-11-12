import React from "react";

export default function CodeBlock({ children }) {
  return (
    <pre style={{ background: "#1e2635", color: "#a8d8a8", fontFamily: "'Courier New', monospace", fontSize: 11, padding: "14px 16px", borderRadius: 6, overflowX: "auto", lineHeight: 1.6, margin: "10px 0", whiteSpace: "pre-wrap", wordBreak: "break-word", maxHeight: 300, overflowY: "auto" }}>
      {children}
    </pre>
  );
}
