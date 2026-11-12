import React from "react";
import { C } from "../../constants";

const COLORS = {
  bronze: { border: "#CD7F32", bg: "#FDF6EE", badge: "#CD7F32" },
  silver: { border: "#999",    bg: "#F7F7F7", badge: "#999"    },
  gold:   { border: "#DAA520", bg: "#FDFDF0", badge: "#DAA520" },
};

export default function MedalLayer({ tier, title, children }) {
  const col = COLORS[tier];
  return (
    <div style={{ borderRadius: 8, padding: "16px 18px", marginBottom: 14, borderLeft: `4px solid ${col.border}`, background: col.bg }}>
      <div style={{ display: "inline-block", fontSize: 10, fontWeight: 700, letterSpacing: ".5px", padding: "2px 8px", borderRadius: 3, marginBottom: 8, background: col.badge, color: C.white }}>
        {tier.toUpperCase()}
      </div>
      {title && <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 10 }}>{title}</div>}
      {children}
    </div>
  );
}
