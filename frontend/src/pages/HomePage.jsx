import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { API } from "../constants";
import { S, T, fmtDate, pill } from "../theme";

/**
 * The workbench landing page — the referral queue.
 *
 * Claims reach this workbench when the payer's AS/400 suspends them. This page
 * is the queue a claims technician works from.
 */
export default function HomePage() {
  const [claims, setClaims] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [tab, setTab] = useState("queue");
  const navigate = useNavigate();

  useEffect(() => {
    const load = () =>
      fetch(`${API}/claims`)
        .then(r => {
          if (!r.ok) throw new Error(`API returned ${r.status}`);
          return r.json();
        })
        .then(data => { setClaims(data); setLoadError(null); })
        .catch(e => setLoadError(e.message));
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, []);

  const referred = claims.filter(c => c.source === "AS400_REFERRAL");
  const uploaded = claims.filter(c => c.source !== "AS400_REFERRAL");
  const pendingReview = claims.filter(c => !c.decision).length;

  const rows = tab === "queue" ? referred : tab === "uploads" ? uploaded : claims;

  function decisionPill(c) {
    if (c.resolution === "APPROVED") return { kind: "ok", text: "paid · AS/400" };
    if (c.resolution === "HELD") return { kind: "hold", text: "held" };
    if (!c.decision) return { kind: "pend", text: "awaiting agents" };
    if (c.decision === "APPROVED") return { kind: "ok", text: "recommended" };
    if (c.decision === "DENIED") return { kind: "hold", text: "denied" };
    return { kind: "pend", text: "needs review" };
  }

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 22 }}>
      <p style={{ color: T.mute, fontSize: 12.5, marginBottom: 16, lineHeight: 1.5, maxWidth: 860 }}>
        Claims arrive here when the payer's AS/400 suspends them — it runs a fixed
        edit sequence and stops on anything it has no rule for, which for
        coordination of benefits is most of the hard cases. The agents work the
        suspense and hand a technician a recommendation, not a decision.
      </p>

      {/* counters */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 18 }}>
        {[
          ["Referral queue", referred.length, T.amber, "suspended by the AS/400"],
          ["Direct uploads", uploaded.length, T.azure, "submitted here"],
          ["Awaiting agents", pendingReview, T.greenText, "not yet adjudicated"],
          ["Total on file", claims.length, T.white, "all sources"],
        ].map(([label, value, colour, sub]) => (
          <div key={label} style={{
            background: T.panel, border: `1px solid ${T.border}`,
            borderTop: `4px solid ${colour === T.white ? T.mute2 : colour}`,
            borderRadius: 12, padding: "16px 18px",
            boxShadow: "0 2px 10px rgba(0,90,50,.08)",
          }}>
            <div style={{ fontSize: 10, color: T.mute2, textTransform: "uppercase", letterSpacing: ".6px" }}>
              {label}
            </div>
            <div style={{ fontSize: 30, fontWeight: 800, color: colour, lineHeight: 1.2 }}>{value}</div>
            <div style={{ fontSize: 11, color: T.mute2 }}>{sub}</div>
          </div>
        ))}
      </div>

      <div>
        {/* queue */}
        <div style={S.card}>
          <div style={{
            ...S.cardHead, display: "flex", gap: 8, alignItems: "center",
            justifyContent: "space-between", flexWrap: "wrap",
          }}>
            <span>📥 Inbound claims</span>
            <span style={{ display: "flex", gap: 6 }}>
              {[["queue", "Referral queue"], ["uploads", "Uploads"], ["all", "All"]].map(([k, label]) => (
                <button
                  key={k}
                  onClick={() => setTab(k)}
                  style={{
                    background: tab === k ? T.greenBg : "transparent",
                    border: `1px solid ${tab === k ? T.green : T.border}`,
                    color: tab === k ? T.greenText : T.mute2,
                    padding: "4px 11px", borderRadius: 6, fontSize: 11,
                    cursor: "pointer", fontWeight: 700, textTransform: "none", letterSpacing: 0,
                  }}
                >
                  {label}
                </button>
              ))}
            </span>
          </div>

          {loadError && (
            <div style={{ ...S.flag, margin: 14 }}>
              ⚑ Cannot reach the claims API ({loadError}). Check the backend is running on port 8000.
            </div>
          )}

          {!loadError && rows.length === 0 && (
            <div style={{ padding: "40px 20px", textAlign: "center", color: T.mute2, fontSize: 13, lineHeight: 1.7 }}>
              {tab === "queue"
                ? <>Nothing in the referral queue.<br />
                    Send claims with <code style={{ background: T.panelR, padding: "2px 6px", borderRadius: 4 }}>
                      python vyne_sender.py --all</code></>
                : "No claims here yet."}
            </div>
          )}

          {rows.length > 0 && (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
              <thead>
                <tr>
                  {["Claim", "Patient", "COB liability", "Source", "Payer claim", "Suspend", "Status", "Received"].map(h => (
                    <th key={h} style={{
                      background: T.panelHd, color: T.mute2, textAlign: "left",
                      padding: "8px 14px", fontSize: 10.5, fontWeight: 700,
                      textTransform: "uppercase", letterSpacing: ".5px",
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map(c => {
                  const d = decisionPill(c);
                  return (
                    <tr
                      key={c.claim_id}
                      className="row-hover"
                      onClick={() => navigate(`/claim/${c.claim_id}`)}
                      style={{ cursor: "pointer", borderBottom: `1px solid ${T.border}` }}
                    >
                      <td style={{ padding: "10px 14px", fontWeight: 700, color: T.greenText, whiteSpace: "nowrap" }}>
                        {c.claim_id}
                      </td>
                      <td style={{ padding: "10px 14px", color: T.white, fontWeight: 600, whiteSpace: "nowrap" }}>
                        {c.patient_name || "—"}
                      </td>
                      <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
                        {c.liability ? (
                          <>
                            <span style={{
                              color: { SECONDARY: T.greenText, PRIMARY: T.amber }[c.liability.role] || T.azure,
                              fontWeight: 700,
                            }}>
                              {{ SECONDARY: "Secondary", PRIMARY: "Primary" }[c.liability.role] || "Undetermined"}
                            </span>
                            <span style={{ color: T.mute2, fontSize: 11 }}> · {c.liability.category}</span>
                          </>
                        ) : "—"}
                      </td>
                      <td style={{ padding: "10px 14px", color: T.mute2, whiteSpace: "nowrap" }}>
                        {c.source === "AS400_REFERRAL"
                          ? "Teledent"
                          : c.source
                            ? "Direct upload"
                            : "— not recorded"}
                      </td>
                      <td style={{ padding: "10px 14px", color: T.mute, whiteSpace: "nowrap" }}>
                        {c.as400_claim_no || "—"}
                      </td>
                      <td style={{ padding: "10px 14px", whiteSpace: "nowrap" }}>
                        {c.suspend_code
                          ? <span style={{ color: T.amber, fontWeight: 700 }}>{c.suspend_code}</span>
                          : <span style={{ color: T.mute2 }}>—</span>}
                      </td>
                      <td style={{ padding: "10px 14px" }}>
                        <span style={pill(d.kind)}>{d.text}</span>
                      </td>
                      <td style={{ padding: "10px 14px", color: T.mute2, fontSize: 11, whiteSpace: "nowrap" }}>
                        {fmtDate(c.created_at)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
