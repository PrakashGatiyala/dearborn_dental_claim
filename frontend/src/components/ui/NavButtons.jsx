import React from "react";
import { C, btn } from "../../constants";

export default function NavButtons({ step, maxS, onPrev, onNext, nextLabel }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", marginTop: 24, paddingTop: 18, borderTop: `1px solid ${C.border}` }}>
      <button onClick={onPrev} disabled={step === 0} style={step === 0 ? { ...btn.secondary, opacity: .4, cursor: "not-allowed" } : btn.secondary}>
        ← Previous
      </button>
      <button onClick={onNext} disabled={step >= maxS} style={step >= maxS ? { ...btn.primary, opacity: .4, cursor: "not-allowed" } : btn.primary}>
        {nextLabel || "Next →"}
      </button>
    </div>
  );
}
