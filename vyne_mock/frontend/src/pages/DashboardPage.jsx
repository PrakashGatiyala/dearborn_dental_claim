import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API, AS400_PORTAL, V, fmt$, fmtDate } from "../constants";
import StatusBadge from "../components/StatusBadge";

function StatTile({ label, value, sub, accent, large }) {
  return (
    <div style={{
      background: V.white, border: `1px solid ${V.border}`, borderRadius: 10,
      padding: "20px 22px", flex: 1, minWidth: 140,
      borderTop: `3px solid ${accent || V.teal}`,
    }}>
      <div style={{ fontSize: 11, color: V.grey, fontWeight: 600, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: large ? 32 : 28, fontWeight: 800, color: V.black }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: V.grey, marginTop: 3 }}>{sub}</div>}
    </div>
  );
}

/** Envelope acceptance is the only ratio a clearinghouse owns. */
function TransmissionSplit({ forwarded, rejected, inTransit }) {
  const total = forwarded + rejected + inTransit;
  const pct = (n) => (total ? Math.round((n / total) * 100) : 0);

  return (
    <div style={{ background: V.white, border: `1px solid ${V.border}`, borderRadius: 10, padding: "20px 22px", marginBottom: 24 }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: V.navy, marginBottom: 14 }}>
        Transmission Outcome
      </div>
      <div style={{ display: "flex", height: 28, borderRadius: 6, overflow: "hidden", marginBottom: 14, background: V.lightGrey }}>
        {forwarded > 0 && (
          <div style={{ width: `${pct(forwarded)}%`, background: V.teal, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, color: V.white, transition: "width .6s" }}>
            {pct(forwarded)}% sent
          </div>
        )}
        {inTransit > 0 && (
          <div style={{ width: `${pct(inTransit)}%`, background: V.midGrey, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, color: V.navy, transition: "width .6s" }}>
            {pct(inTransit)}%
          </div>
        )}
        {rejected > 0 && (
          <div style={{ width: `${pct(rejected)}%`, background: V.red, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 800, color: V.white, transition: "width .6s" }}>
            {pct(rejected)}%
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: V.teal, display: "inline-block" }} />
          <span style={{ fontSize: 12, color: V.grey }}>
            <strong style={{ color: V.black }}>{forwarded}</strong> forwarded to the payer
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: V.midGrey, display: "inline-block" }} />
          <span style={{ fontSize: 12, color: V.grey }}>
            <strong style={{ color: V.black }}>{inTransit}</strong> in transit
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ width: 10, height: 10, borderRadius: 2, background: V.red, display: "inline-block" }} />
          <span style={{ fontSize: 12, color: V.grey }}>
            <strong style={{ color: V.black }}>{rejected}</strong> rejected at the envelope check
          </span>
        </div>
      </div>
    </div>
  );
}

function ScopeNote() {
  return (
    <div style={{
      background: V.tealLight, border: `1px solid ${V.teal}`, borderRadius: 10,
      padding: "16px 20px", marginBottom: 24,
    }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: V.tealDark, marginBottom: 6 }}>
        Vyne is a clearinghouse — adjudication happens at the payer
      </div>
      <div style={{ fontSize: 12, color: "#0a5158", lineHeight: 1.7 }}>
        Every claim here is a <strong>Coordination of Benefits</strong> claim: the patient is covered
        by two plans. Vyne validates the EDI envelope and transmits. Whether a claim pays
        automatically or suspends for a human reviewer is decided on HCSC's AS/400.
      </div>
      <a href={AS400_PORTAL} target="_blank" rel="noreferrer" style={{
        display: "inline-block", marginTop: 10, fontSize: 12, fontWeight: 600,
        color: V.teal, textDecoration: "none",
      }}>
        Open the HCSC AS/400 claims system →
      </a>
    </div>
  );
}

export default function DashboardPage() {
  const [stats, setStats]   = useState(null);
  const [claims, setClaims] = useState([]);
  const [resetting, setResetting] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    fetch(`${API}/stats`).then(r => r.json()).then(setStats).catch(() => {});
    fetch(`${API}/claims`).then(r => r.json()).then(d => setClaims(d.slice(0, 8))).catch(() => {});
  };

  const handleReset = () => {
    if (!window.confirm("Clear all claims from the Vyne gateway? This cannot be undone.")) return;
    setResetting(true);
    fetch(`${API}/claims/reset`, { method: "DELETE" })
      .then(() => { load(); setResetting(false); })
      .catch(() => setResetting(false));
  };

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);

  const s = stats || {};
  const forwarded = s.forwarded ?? 0;
  const rejected  = s.rejected ?? 0;
  const inTransit = s.in_transit ?? 0;

  return (
    <div style={{ padding: 28, maxWidth: 1100 }}>
      <div style={{ marginBottom: 20, display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: V.navy }}>Claim Transmission Dashboard</div>
          <div style={{ fontSize: 13, color: V.grey, marginTop: 3 }}>
          NEA Gateway — EDI validation and routing to payer systems
          </div>
        </div>
        <button onClick={handleReset} disabled={resetting} style={{
          background: "none", border: `1px solid ${V.border}`, color: V.grey,
          fontSize: 12, fontWeight: 600, padding: "6px 14px", borderRadius: 6,
          cursor: resetting ? "not-allowed" : "pointer", opacity: resetting ? 0.6 : 1,
        }}>
          {resetting ? "Clearing…" : "Clear claims"}
        </button>
      </div>

      <div style={{ display: "flex", gap: 14, flexWrap: "wrap", marginBottom: 20 }}>
        <StatTile label="Total Claims"   value={s.total_claims ?? 0} sub="received"                     accent={V.teal} />
        <StatTile label="Forwarded"      value={forwarded}           sub={`${s.accept_pct ?? 0}% accepted`} accent={V.green} />
        <StatTile label="In Transit"     value={inTransit}           sub="awaiting transmission"        accent={V.blue} />
        <StatTile label="EDI Rejected"   value={rejected}            sub="envelope errors"              accent={V.red} />
        <StatTile label="COB Claims"     value={s.cob_claims ?? 0}   sub="two-plan coordination"        accent={V.purple} />
      </div>

      <TransmissionSplit forwarded={forwarded} rejected={rejected} inTransit={inTransit} />
      <ScopeNote />

      <div style={{ background: V.white, border: `1px solid ${V.border}`, borderRadius: 10, overflow: "hidden" }}>
        <div style={{ padding: "14px 20px", borderBottom: `1px solid ${V.border}`, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 14, fontWeight: 700, color: V.navy }}>Recent Claims</div>
          <button onClick={() => navigate("/claims")} style={{
            background: "none", border: `1px solid ${V.teal}`, color: V.teal,
            fontSize: 12, fontWeight: 600, padding: "5px 12px", borderRadius: 6, cursor: "pointer",
          }}>View All</button>
        </div>
        {claims.length === 0 ? (
          <div style={{ padding: "40px 20px", textAlign: "center", color: V.grey, fontSize: 13 }}>
            No claims yet. Run <code style={{ background: V.lightGrey, padding: "2px 6px", borderRadius: 4 }}>python vyne_sender.py --interval 30</code>
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: V.lightGrey }}>
                {["Tracking ID", "Patient", "Primary Payer", "Billed", "Status", "Payer Claim", "Received"].map(h => (
                  <th key={h} style={{ padding: "9px 14px", textAlign: "left", fontSize: 11, fontWeight: 700, color: V.grey, textTransform: "uppercase", letterSpacing: ".5px" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {claims.map((c, i) => (
                <tr key={c.tracking_id} onClick={() => navigate(`/claims/${c.tracking_id}`)}
                  style={{ borderTop: `1px solid ${V.border}`, cursor: "pointer", background: i % 2 === 0 ? V.white : "#FAFBFC" }}>
                  <td style={{ padding: "10px 14px", fontWeight: 700, color: V.teal, fontFamily: "monospace" }}>{c.tracking_id}</td>
                  <td style={{ padding: "10px 14px" }}>{c.patient_name || c.subscriber_name || "—"}</td>
                  <td style={{ padding: "10px 14px", color: V.grey }}>{c.primary_payer || "—"}</td>
                  <td style={{ padding: "10px 14px", fontWeight: 600 }}>{fmt$(c.billed_amount)}</td>
                  <td style={{ padding: "10px 14px" }}><StatusBadge status={c.status} /></td>
                  <td style={{ padding: "10px 14px", fontFamily: "monospace", fontSize: 12, color: c.as400_claim_no ? V.navy : V.midGrey }}>
                    {c.as400_claim_no || "—"}
                  </td>
                  <td style={{ padding: "10px 14px", color: V.grey, fontSize: 11 }}>{fmtDate(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
