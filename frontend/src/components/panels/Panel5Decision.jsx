import React from "react";
import { C } from "../../constants";
import Card from "../ui/Card";
import SectionTag from "../ui/SectionTag";
import NavButtons from "../ui/NavButtons";

const DEC_COLORS = {
  APPROVED:     { border: "#1E8A4A", bg: "#F0FAF4", stamp: "#1E8A4A" },
  DENIED:       { border: "#C0392B", bg: "#FFF5F5", stamp: "#C0392B" },
  NEEDS_REVIEW: { border: "#E8820C", bg: "#FFFBF0", stamp: "#E8820C" },
};

export default function Panel5Decision({ claim, step, maxS, setStep }) {
  const dec = claim?.decision;

  if (!dec) {
    return (
      <div>
        <SectionTag text="Step 6 of 6" />
        <div style={{ fontSize: 20, fontWeight: 700, color: C.darkBlue, marginBottom: 16 }}>Decision & Audit Trail</div>
        <div style={{ color: C.grey, fontSize: 13 }}>No decision yet. Run AI Adjudication in the previous step.</div>
        <NavButtons step={step} maxS={maxS} onPrev={() => setStep(4)} onNext={() => {}} />
      </div>
    );
  }

  const dc = DEC_COLORS[dec.decision] || DEC_COLORS.NEEDS_REVIEW;
  const pct = Math.round((dec.confidence || 0) * 100);

  // How much human work this claim still needs. A claim the agent settled on
  // its own is zero; one routed for review costs however many steps the
  // reviewer has to carry out. Reporting a flat zero on a NEEDS_REVIEW claim
  // overstates the automation.
  const guidance = dec.human_reviewer_guidance;
  const guidanceSteps = Array.isArray(guidance)
    ? guidance.length
    : typeof guidance === "string" && guidance.trim()
      ? guidance.split(/\n+|(?:^|\s)\d+[.)]\s/).filter(s => s.trim()).length
      : 0;
  const touchpoints = dec.decision === "NEEDS_REVIEW" ? Math.max(guidanceSteps, 1) : 0;

  return (
    <div>
      <SectionTag text="Step 6 of 6" />
      <div style={{ fontSize: 20, fontWeight: 700, color: C.darkBlue, marginBottom: 4 }}>Decision & Audit Trail</div>
      <div style={{ fontSize: 13, color: C.grey, marginBottom: 22 }}>Full decision lineage captured. All database rows cited by the agent are recorded below.</div>

      {/* KPI row */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 20 }}>
        {[
          ["Decision", dec.decision, dec.decision === "APPROVED" ? C.green : dec.decision === "DENIED" ? C.red : C.amber],
          ["Confidence", pct + "%", pct >= 90 ? C.green : C.amber],
          ["Manual Touchpoints", String(touchpoints), touchpoints === 0 ? C.green : C.amber],
          ["Approved Amount", dec.approved_amount != null ? "$" + Number(dec.approved_amount).toFixed(2) : "—", C.blue],
        ].map(([label, val, color]) => (
          <div key={label} style={{ background: C.white, border: `1px solid ${C.border}`, borderRadius: 8, padding: "14px 16px" }}>
            <div style={{ fontSize: 10, color: C.grey, textTransform: "uppercase", letterSpacing: ".5px", marginBottom: 6 }}>{label}</div>
            <div style={{ fontSize: 22, fontWeight: 800, color, lineHeight: 1 }}>{val}</div>
          </div>
        ))}
      </div>

      {/* Decision stamp */}
      <div style={{ borderRadius: 8, padding: "22px 24px", marginBottom: 16, border: `2px solid ${dc.border}`, background: dc.bg }}>
        <div style={{ fontSize: 28, fontWeight: 800, color: dc.stamp, letterSpacing: 2, border: `3px solid ${dc.stamp}`, display: "inline-block", padding: "4px 16px", borderRadius: 4, transform: "rotate(-2deg)", marginBottom: 14 }}>
          {dec.decision}
        </div>
        <div style={{ fontSize: 13, color: C.black, lineHeight: 1.7, marginTop: 10 }}>{dec.justification}</div>
        {dec.denial_codes && dec.denial_codes.length > 0 && (
          <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
            {dec.denial_codes.map(c => (
              <span key={c} style={{ background: "#FAD7D3", color: C.red, fontSize: 11, fontWeight: 700, padding: "2px 8px", borderRadius: 3 }}>{c}</span>
            ))}
          </div>
        )}
      </div>

      {/* Audit trail */}
      {dec.data_sources && dec.data_sources.length > 0 && (
        <Card title="📋 Audit & Data Lineage">
          <div style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: "2px 14px", fontSize: 10, fontWeight: 700, color: C.grey, letterSpacing: ".5px", textTransform: "uppercase", paddingBottom: 8, borderBottom: `2px solid ${C.midGrey}`, marginBottom: 4 }}>
            <div>TABLE</div><div>FIELDS USED</div>
          </div>
          {dec.data_sources.map((ds, i) => (
            <div key={i} style={{ display: "grid", gridTemplateColumns: "140px 1fr", gap: "2px 14px", padding: "9px 0", borderBottom: `1px solid ${C.lightGrey}`, fontSize: 11.5, alignItems: "start" }}>
              <div style={{ fontWeight: 700, color: C.blue }}>{ds.table}</div>
              <div style={{ color: C.black, lineHeight: 1.6 }}>
                {Object.entries(ds.row || {}).map(([k, v]) => `${k}: ${v}`).join(" · ")}
              </div>
            </div>
          ))}
        </Card>
      )}

      <NavButtons step={step} maxS={maxS} onPrev={() => setStep(4)} onNext={() => {}} nextLabel="Done" />
    </div>
  );
}
