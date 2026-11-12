import React from "react";
import { C, STEPS } from "../constants";

export default function PipelineNav({ activeStep, maxStep, onStep }) {
  return (
    <div style={{ background: C.darkBlue, padding: "0 28px", display: "flex", gap: 0, overflowX: "auto", position: "sticky", top: 57, zIndex: 99 }}>
      {STEPS.map((label, i) => {
        const done = i < activeStep;
        const active = i === activeStep;
        const reachable = i <= maxStep;
        return (
          <React.Fragment key={i}>
            <div
              onClick={() => reachable && onStep(i)}
              style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 18px", cursor: reachable ? "pointer" : "default", borderBottom: `3px solid ${active ? C.lightBlue : "transparent"}`, color: active ? C.white : done ? "#7ed9a0" : "rgba(255,255,255,.45)", fontSize: 12, fontWeight: 600, whiteSpace: "nowrap", transition: "all .2s", userSelect: "none" }}
            >
              <div style={{ width: 20, height: 20, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 10, fontWeight: 700, border: `1.5px solid currentColor`, flexShrink: 0, background: done ? C.green : "transparent", borderColor: done ? C.green : "currentColor", color: done ? C.white : "currentColor" }}>
                {done ? "✓" : i + 1}
              </div>
              {label}
            </div>
            {i < STEPS.length - 1 && (
              <div style={{ color: "rgba(255,255,255,.3)", fontSize: 12, padding: "12px 0", alignSelf: "center", flexShrink: 0 }}>›</div>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}
