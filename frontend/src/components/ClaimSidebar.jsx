import React from "react";
import { C, AGENTS, btn } from "../constants";

export default function ClaimSidebar({ claims, currentClaim, onLoadClaim, onNewClaim }) {
  const dec = currentClaim?.decision;
  const gd = currentClaim?.gold_data;

  const pillColor = !dec
    ? { bg: "#FFF3CD", color: "#856404" }
    : dec.decision === "APPROVED" ? { bg: "#D4EDDA", color: C.green }
    : dec.decision === "DENIED"   ? { bg: "#FAD7D3", color: C.red }
    : { bg: "#FFF3CD", color: C.amber };

  const pillLabel = !dec ? "Processing"
    : dec.decision === "APPROVED" ? "Approved"
    : dec.decision === "DENIED"   ? "Denied"
    : "Needs Review";

  return (
    <div style={{ width: 280, flexShrink: 0, background: C.white, borderRight: `1px solid ${C.border}`, padding: "20px 0", position: "sticky", top: 108, height: "calc(100vh - 108px)", overflowY: "auto" }}>
      {currentClaim ? (
        <>
          {/* Back to home navigation */}
          <div style={{ padding: "0 18px 12px" }}>
            <button
              onClick={onNewClaim}
              style={{ background: "none", border: "none", cursor: "pointer", color: C.blue, fontSize: 12, fontWeight: 600, padding: "4px 0", display: "flex", alignItems: "center", gap: 4 }}
            >
              ← All Claims
            </button>
          </div>
          <div style={{ height: 1, background: C.lightGrey, margin: "0 18px 12px" }} />
          <div style={{ padding: "0 18px 14px" }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: C.grey, letterSpacing: ".8px", textTransform: "uppercase", marginBottom: 10 }}>Active Claim</div>
            {[
              ["Claim ID", currentClaim.claim_id],
              ["Subscriber ID", gd?.subscriber_id],
              ["CDT Codes", (gd?.cdt_codes || []).join(", ")],
              ["Provider", gd?.provider_name],
              ["Billed", gd?.billed_amount ? `$${Number(gd.billed_amount).toLocaleString()}` : null],
              ["Date of Service", gd?.procedure_date],
            ].map(([label, value]) => value && (
              <div key={label} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 10, color: C.grey }}>{label}</div>
                <div style={{ fontSize: 12, fontWeight: 600, color: C.black }}>{value}</div>
              </div>
            ))}
          </div>

          <div style={{ height: 1, background: C.lightGrey, margin: "0 18px 14px" }} />

          <div style={{ padding: "0 18px 10px" }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: C.grey, letterSpacing: ".8px", textTransform: "uppercase", marginBottom: 10 }}>Agent Status</div>
            {AGENTS.map((a, i) => {
              const done = currentClaim.status === "ADJUDICATED";
              return (
                <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 6, marginBottom: 4, fontSize: 12 }}>
                  <div style={{ width: 28, height: 28, borderRadius: 6, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 13, flexShrink: 0, background: "#E8F2FB" }}>{a.icon}</div>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 600, color: C.black }}>{a.name}</div>
                    <div style={{ fontSize: 10, color: done ? C.green : C.midGrey, marginTop: 1 }}>{done ? "✓ Done" : "Waiting"}</div>
                  </div>
                  {done && <div style={{ fontSize: 14, color: C.green }}>✓</div>}
                </div>
              );
            })}
          </div>

          <div style={{ height: 1, background: C.lightGrey, margin: "0 18px 14px" }} />

          <div style={{ padding: "0 18px" }}>
            <div style={{ display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 10px", borderRadius: 20, fontSize: 11, fontWeight: 600, background: pillColor.bg, color: pillColor.color }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "currentColor" }} />
              {pillLabel}
            </div>
          </div>
        </>
      ) : (
        <>
          <div style={{ padding: "0 18px 14px" }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: C.grey, letterSpacing: ".8px", textTransform: "uppercase", marginBottom: 10 }}>Recent Claims</div>
            {claims.length === 0 && <div style={{ fontSize: 12, color: C.grey }}>No claims yet.</div>}
            {claims.map(c => (
              <div key={c.claim_id} onClick={() => onLoadClaim(c.claim_id)} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", borderRadius: 6, marginBottom: 4, cursor: "pointer", fontSize: 12, background: C.lightGrey }}>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600 }}>{c.claim_id}</div>
                  <div style={{ fontSize: 10, color: C.grey, marginTop: 1 }}>{c.status} {c.decision ? `· ${c.decision}` : ""}</div>
                </div>
              </div>
            ))}
          </div>
          <div style={{ padding: "0 18px" }}>
            <button onClick={onNewClaim} style={{ ...btn.primary, width: "100%", textAlign: "center" }}>+ New Claim</button>
          </div>
        </>
      )}
    </div>
  );
}
