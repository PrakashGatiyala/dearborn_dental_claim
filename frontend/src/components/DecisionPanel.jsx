import React from "react";
import JustificationTable from "./JustificationTable";

const DECISION_STYLES = {
  APPROVED: { bg: "#0d2818", border: "#2e7d32", color: "#4caf50", icon: "✓" },
  DENIED: { bg: "#1c0a0a", border: "#c62828", color: "#ef5350", icon: "✗" },
  NEEDS_REVIEW: { bg: "#1c1000", border: "#e65100", color: "#ff9800", icon: "⚠" },
};

export default function DecisionPanel({ decision }) {
  if (!decision) return null;

  const style = DECISION_STYLES[decision.decision] || DECISION_STYLES.NEEDS_REVIEW;

  return (
    <div style={{ ...styles.banner, background: style.bg, borderColor: style.border }}>
      {/* Header */}
      <div style={styles.header}>
        <span style={{ ...styles.icon, color: style.color }}>{style.icon}</span>
        <span style={{ ...styles.decision, color: style.color }}>{decision.decision}</span>
        <span style={styles.confidence}>
          Confidence: {Math.round(decision.confidence * 100)}%
        </span>
      </div>

      {/* Approved amount */}
      {decision.approved_amount != null && (
        <div style={styles.amount}>
          Plan Approved Amount:{" "}
          <strong style={{ color: "#4caf50" }}>
            ${decision.approved_amount.toFixed(2)}
          </strong>
        </div>
      )}

      {/* Denial codes */}
      {decision.denial_codes && decision.denial_codes.length > 0 && (
        <div style={styles.codesRow}>
          <span style={styles.codesLabel}>Denial Codes: </span>
          {decision.denial_codes.map((code) => (
            <span key={code} style={styles.code}>{code}</span>
          ))}
        </div>
      )}

      {/* Justification */}
      <div style={styles.justification}>{decision.justification}</div>

      {/* Needs further review note */}
      {decision.decision === "NEEDS_REVIEW" && (
        <div style={styles.reviewNote}>
          This claim requires manual specialist review. The agent has flagged it
          based on the data sources below. A human adjudicator must verify and
          approve before any payment is issued.
        </div>
      )}

      {/* Complex case escalation card */}
      {decision.complex_case_type && (
        <div style={{
          background: "#0a0a1c", border: "1px solid #4f46e5",
          borderRadius: "8px", padding: "16px 20px", marginBottom: "12px",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
            <span style={{ fontSize: 18 }}>🧠</span>
            <span style={{ fontSize: 13, fontWeight: 800, color: "#818cf8", letterSpacing: ".5px", textTransform: "uppercase" }}>
              Complex Case — Agent Escalation Required
            </span>
            <span style={{
              background: "#312e81", color: "#a5b4fc",
              fontSize: 10, fontWeight: 700, padding: "2px 8px", borderRadius: 4, marginLeft: "auto",
              letterSpacing: ".5px",
            }}>
              {{
                ORTHO_AMBIGUITY: "ORTHO-01 · Age–Narrative Conflict",
                WIP_ORTHO_COB:   "WIP-01 · Mid-Treatment Insurance Switch",
                CROSS_PLAN_COB:  "COB-03 · Cross-Plan Coordination",
              }[decision.complex_case_type] || decision.complex_case_type}
            </span>
          </div>
          {decision.complex_case_type === "ORTHO_AMBIGUITY" && (
            <div style={{ fontSize: 12, color: "#c7d2fe", lineHeight: 1.7 }}>
              <strong style={{ color: "#e0e7ff" }}>Why a computer fails here:</strong> The patient's age does not match
              the expected range for the submitted CDT code. An RPA system auto-denies on this mismatch.
              The agent has read the doctor's clinical narrative and found medical justification that
              requires a licensed orthodontic specialist to review.
            </div>
          )}
          {decision.complex_case_type === "WIP_ORTHO_COB" && (
            <div style={{ fontSize: 12, color: "#c7d2fe", lineHeight: 1.7 }}>
              <strong style={{ color: "#e0e7ff" }}>Why a computer fails here:</strong> Patient switched insurers
              mid-orthodontic treatment. The new plan has no record of prior payments. A human reviewer
              must call the prior insurer, verify the amount already paid, calculate remaining months,
              and build a custom prorated payment schedule in the system.
            </div>
          )}
          {decision.complex_case_type === "CROSS_PLAN_COB" && (
            <div style={{ fontSize: 12, color: "#c7d2fe", lineHeight: 1.7 }}>
              <strong style={{ color: "#e0e7ff" }}>Why a computer fails here:</strong> Two insurance plans use
              incompatible payment structures (lump-sum vs. monthly). The agent has retrieved the primary
              EOB and calculated the secondary obligation to prevent illegal overpayment, but a human
              must verify the EOB figures and override the plan's automated payment system.
            </div>
          )}
          {decision.human_reviewer_guidance && (
            <div style={{ marginTop: 12, background: "#1e1b4b", borderRadius: 6, padding: "10px 14px" }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: "#6366f1", letterSpacing: ".6px", textTransform: "uppercase", marginBottom: 6 }}>
                Human Reviewer Action Items
              </div>
              <div style={{ fontSize: 12, color: "#e0e7ff", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>
                {decision.human_reviewer_guidance}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Data sources table */}
      <JustificationTable dataSources={decision.data_sources} />
    </div>
  );
}

const styles = {
  banner: {
    border: "1px solid",
    borderRadius: "8px",
    padding: "20px 24px",
    marginTop: "16px",
  },
  header: { display: "flex", alignItems: "center", gap: "12px", marginBottom: "12px" },
  icon: { fontSize: "24px", fontWeight: 700 },
  decision: { fontSize: "22px", fontWeight: 800, letterSpacing: "1px" },
  confidence: { fontSize: "13px", color: "#667", marginLeft: "auto" },
  amount: { fontSize: "15px", color: "#aab", marginBottom: "10px" },
  codesRow: { marginBottom: "12px" },
  codesLabel: { fontSize: "12px", color: "#667", marginRight: "8px" },
  code: {
    display: "inline-block",
    background: "#2a0a0a",
    border: "1px solid #c62828",
    color: "#ef5350",
    fontSize: "11px",
    fontWeight: 700,
    padding: "2px 8px",
    borderRadius: "4px",
    marginRight: "6px",
    letterSpacing: "0.5px",
  },
  justification: {
    fontSize: "14px",
    color: "#c0cce0",
    lineHeight: "1.6",
    marginBottom: "12px",
  },
  reviewNote: {
    background: "#1c1400",
    border: "1px solid #f0a500",
    borderRadius: "6px",
    padding: "12px 16px",
    fontSize: "13px",
    color: "#f0a500",
    marginBottom: "12px",
  },
};
