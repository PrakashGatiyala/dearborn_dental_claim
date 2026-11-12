import React from "react";
import { C } from "../../constants";

export default function Card({ title, children, style }) {
  return (
    <div style={{ background: C.white, border: `1px solid ${C.border}`, borderRadius: 8, padding: 18, marginBottom: 16, ...style }}>
      {title && <div style={{ fontSize: 13, fontWeight: 700, color: C.darkBlue, marginBottom: 10 }}>{title}</div>}
      {children}
    </div>
  );
}
