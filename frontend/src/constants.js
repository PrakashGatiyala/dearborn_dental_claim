export const API = import.meta.env.VITE_API_URL || "/api";

export const C = {
  blue: "#1171B9", darkBlue: "#0D558B", lightBlue: "#51ADEF",
  green: "#1E8A4A", red: "#C0392B", amber: "#E8820C",
  grey: "#666666", midGrey: "#CCCCCC", lightGrey: "#F4F6F9",
  bg: "#F0F4F8", black: "#1A1A1A", white: "#FFFFFF",
  border: "#dde3ea",
};

export const STEPS = [
  "Raw Claim Data", "Bronze Layer", "Silver Layer",
  "Gold Layer", "Agent Orchestration", "Decision & Audit",
];

export const AGENTS = [
  { icon: "📥", name: "Intake Agent" },
  { icon: "🔍", name: "Eligibility Agent" },
  { icon: "🦷", name: "CDT Validation" },
  { icon: "🩺", name: "Clinical Review" },
  { icon: "⚖️", name: "Adjudication" },
  { icon: "📋", name: "Audit & Lineage" },
];

export const btn = {
  primary: { padding: "10px 20px", borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: "pointer", border: "none", background: C.blue, color: C.white },
  secondary: { padding: "10px 20px", borderRadius: 6, fontSize: 13, fontWeight: 600, cursor: "pointer", border: `1.5px solid ${C.blue}`, background: C.white, color: C.blue },
};

export function maxStep(status) {
  if (!status) return 0;
  const m = { UPLOADED: 1, SILVER_DONE: 2, GOLD_DONE: 4, ADJUDICATED: 5 };
  return m[status] ?? 0;
}
