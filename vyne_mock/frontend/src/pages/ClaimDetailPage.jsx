import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { API, V, STATUS_META, fmt$, fmtDate } from "../constants";
import StatusBadge from "../components/StatusBadge";
import PatientDocuments from "../components/PatientDocuments";

function Field({ label, value, mono }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: V.grey, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 13, color: V.black, fontFamily: mono ? "monospace" : undefined, wordBreak: "break-all" }}>{value || "—"}</div>
    </div>
  );
}

function Section({ title, children, accent }) {
  return (
    <div style={{ background: V.white, border: `1px solid ${V.border}`, borderRadius: 10, marginBottom: 16, overflow: "hidden", borderTop: accent ? `3px solid ${accent}` : undefined }}>
      <div style={{ padding: "12px 20px", borderBottom: `1px solid ${V.border}`, background: V.lightGrey }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: V.navy }}>{title}</div>
      </div>
      <div style={{ padding: "18px 20px" }}>{children}</div>
    </div>
  );
}

/**
 * Vyne's only job is transmission, so the timeline is linear:
 * received → acknowledged → forwarded to the payer. Rejection is the one
 * branch, and it happens at the envelope check.
 */
function StatusTimeline({ status }) {
  const flow = ["RECEIVED", "ACKNOWLEDGED", "FORWARDED"];
  const rejected = status === "REJECTED";
  const idx = flow.indexOf(status);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0, flexWrap: "wrap" }}>
      {flow.map((s, i) => {
        const meta      = STATUS_META[s] || { label: s, dot: V.grey, color: V.grey };
        const isCurrent = s === status;
        const isPast    = idx > -1 && i < idx;
        const active    = isCurrent || isPast;
        return (
          <React.Fragment key={s}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
              <div style={{
                width: 32, height: 32, borderRadius: "50%",
                background: active ? meta.dot : V.lightGrey,
                border: `2px solid ${active ? meta.dot : V.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all .3s",
              }}>
                {isPast ? <span style={{ color: V.white, fontWeight: 700, fontSize: 12 }}>✓</span>
                  : isCurrent ? <span style={{ width: 10, height: 10, borderRadius: "50%", background: V.white }} />
                  : null}
              </div>
              <div style={{ fontSize: 10, fontWeight: isCurrent ? 700 : 400, color: active ? meta.color : V.grey, whiteSpace: "nowrap" }}>
                {meta.label}
              </div>
            </div>
            {i < flow.length - 1 && (
              <div style={{ flex: 1, height: 2, background: isPast ? V.teal : V.border, minWidth: 30, marginBottom: 20, transition: "all .3s" }} />
            )}
          </React.Fragment>
        );
      })}
      {rejected && (
        <div style={{ marginLeft: 12, background: "#FEE2E2", border: "1px solid #B91C1C33", borderRadius: 6, padding: "4px 10px", fontSize: 11, fontWeight: 700, color: "#B91C1C" }}>
          ✕ EDI envelope error — claim never forwarded
        </div>
      )}
    </div>
  );
}

export default function ClaimDetailPage() {
  const { trackingId } = useParams();
  const [claim, setClaim] = useState(null);
  const [err,   setErr]   = useState(null);
  const navigate = useNavigate();

  const load = () => {
    fetch(`${API}/claims/${trackingId}`)
      .then(r => { if (!r.ok) throw new Error("Not found"); return r.json(); })
      .then(setClaim)
      .catch(() => setErr("Claim not found."));
  };

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [trackingId]);

  if (err) return (
    <div style={{ padding: 40, textAlign: "center", color: V.red }}>
      {err} <button onClick={() => navigate("/claims")} style={{ marginLeft: 12, color: V.teal, background: "none", border: "none", cursor: "pointer", fontWeight: 600 }}>Back</button>
    </div>
  );
  if (!claim) return <div style={{ padding: 40, color: V.grey, textAlign: "center" }}>Loading…</div>;

  return (
    <div style={{ padding: 28, maxWidth: 960 }}>
      <div style={{ fontSize: 12, color: V.grey, marginBottom: 16 }}>
        <span style={{ cursor: "pointer", color: V.teal }} onClick={() => navigate("/claims")}>Claims</span>
        <span style={{ margin: "0 6px" }}>›</span>
        <span style={{ fontFamily: "monospace" }}>{trackingId}</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: V.navy, fontFamily: "monospace" }}>{claim.tracking_id}</div>
          <div style={{ fontSize: 13, color: V.grey, marginTop: 2 }}>Submitted {fmtDate(claim.created_at)}</div>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <StatusBadge status={claim.status} size="lg" />
          {claim.is_cob && (
            <span style={{ background: "#E0F2FE", color: "#0369A1", fontSize: 11, fontWeight: 700, padding: "4px 10px", borderRadius: 4 }}>
              ⚖️ COB — two plans
            </span>
          )}
        </div>
      </div>

      <Section title="Transmission Status">
        <StatusTimeline status={claim.status} />
        {claim.response_message && (
          <div style={{ marginTop: 16, background: V.lightGrey, borderRadius: 6, padding: "10px 14px", fontSize: 12, color: V.grey }}>
            <strong style={{ color: V.black }}>[{claim.response_code}]</strong> {claim.response_message}
          </div>
        )}
        {claim.envelope_errors?.length > 0 && (
          <ul style={{ margin: "12px 0 0", paddingLeft: 20 }}>
            {claim.envelope_errors.map((e, i) => (
              <li key={i} style={{ fontSize: 12, color: "#B91C1C", lineHeight: 1.7 }}>{e}</li>
            ))}
          </ul>
        )}
      </Section>

      {/* Where it went next — Vyne does not adjudicate */}
      {claim.as400_claim_no ? (
        <div style={{ background: V.tealLight, border: `1px solid ${V.teal}`, borderRadius: 10, padding: "16px 20px", marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: V.tealDark, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 6 }}>
            Forwarded to payer adjudication system
          </div>
          <div style={{ fontSize: 13, color: V.black, marginBottom: 8, lineHeight: 1.6 }}>
            Vyne validated the EDI envelope and transmitted this claim to HCSC. Adjudication —
            whether it pays, suspends, or needs a reviewer — happens there, not here.
          </div>
          <div style={{ fontSize: 13, fontFamily: "monospace", color: V.black, marginBottom: 8 }}>
            Payer claim number: <strong>{claim.as400_claim_no}</strong>
          </div>
          <a href={claim.as400_screen_url} target="_blank" rel="noreferrer" style={{
            fontSize: 12, color: V.teal, fontWeight: 600, textDecoration: "none",
            display: "inline-flex", alignItems: "center", gap: 4,
          }}>
            Open claim on HCSC AS/400 →
          </a>
        </div>
      ) : claim.status !== "REJECTED" && (
        <div style={{ background: V.lightGrey, border: `1px solid ${V.border}`, borderRadius: 10, padding: "14px 20px", marginBottom: 16, fontSize: 13, color: V.grey }}>
          Awaiting transmission to the payer adjudication system…
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <Section title="Patient &amp; Subscriber">
          <Field label="Subscriber Name" value={claim.subscriber_name} />
          <Field label="Subscriber ID"   value={claim.subscriber_id} mono />
          <Field label="Patient Name"    value={claim.patient_name} />
          <Field label="Date of Service" value={claim.procedure_date} />
        </Section>
        <Section title="Provider &amp; Coverage">
          <Field label="Provider / Practice"      value={claim.provider_name} />
          <Field label="Provider NPI"             value={claim.provider_npi} mono />
          <Field label="Destination Payer"        value={claim.payer_name} />
          <Field label="Primary Payer (COB)"      value={claim.primary_payer} />
        </Section>
      </div>

      <Section title="Billed Charges">
        <div style={{ background: V.lightGrey, borderRadius: 8, padding: "14px 16px", maxWidth: 260 }}>
          <div style={{ fontSize: 10, color: V.grey, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".6px", marginBottom: 4 }}>
            Billed Amount
          </div>
          <div style={{ fontSize: 22, fontWeight: 800, color: V.black }}>{fmt$(claim.billed_amount)}</div>
        </div>
        <div style={{ fontSize: 12, color: V.grey, marginTop: 10 }}>
          Allowed and paid amounts are determined by the payer, not the clearinghouse.
        </div>
      </Section>

      {claim.procedures?.length > 0 && (
        <Section title="Procedure Lines">
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: V.lightGrey }}>
                {["CDT Code", "Tooth", "Fee"].map(h => (
                  <th key={h} style={{ padding: "8px 12px", textAlign: "left", fontSize: 11, fontWeight: 700, color: V.grey, textTransform: "uppercase", letterSpacing: ".5px" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {claim.procedures.map((p, i) => (
                <tr key={i} style={{ borderTop: `1px solid ${V.border}` }}>
                  <td style={{ padding: "9px 12px" }}>
                    <span style={{ background: V.tealLight, color: V.tealDark, fontWeight: 700, fontSize: 12, padding: "3px 8px", borderRadius: 4 }}>{p.cdt_code}</span>
                  </td>
                  <td style={{ padding: "9px 12px", color: V.grey }}>{p.tooth || "—"}</td>
                  <td style={{ padding: "9px 12px", fontWeight: 600 }}>{fmt$(p.fee)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      <PatientDocuments details={claim.patient_details} />

      <Section title="Transmission Details">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 0 }}>
          <Field label="Source EDI File"  value={claim.filename} mono />
          <Field label="Submission Date"  value={claim.submission_date} />
          <Field label="Forwarded At"     value={claim.forwarded_at ? fmtDate(claim.forwarded_at) : "—"} />
          <Field label="Vyne Tracking ID" value={claim.tracking_id} mono />
        </div>
      </Section>
    </div>
  );
}
