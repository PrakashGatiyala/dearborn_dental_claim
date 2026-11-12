import React from "react";
import { V, fmt$ } from "../constants";

/**
 * Supporting documents the practice sends with a claim.
 * Vyne stores and relays them; it does not interpret them.
 */

function Box({ title, children, accent }) {
  return (
    <div style={{
      background: V.white, border: `1px solid ${V.border}`, borderRadius: 10,
      marginBottom: 16, overflow: "hidden",
      borderTop: accent ? `3px solid ${accent}` : undefined,
    }}>
      <div style={{ padding: "12px 20px", borderBottom: `1px solid ${V.border}`, background: V.lightGrey }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: V.navy }}>{title}</div>
      </div>
      <div style={{ padding: "16px 20px" }}>{children}</div>
    </div>
  );
}

function Row({ label, value, mono }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "5px 0", fontSize: 13 }}>
      <span style={{ color: V.grey }}>{label}</span>
      <span style={{ color: V.black, fontFamily: mono ? "monospace" : undefined, textAlign: "right" }}>
        {value ?? "—"}
      </span>
    </div>
  );
}

function Table({ cols, rows }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12.5 }}>
      <thead>
        <tr style={{ background: V.lightGrey }}>
          {cols.map(c => (
            <th key={c} style={{
              padding: "7px 10px", textAlign: "left", fontSize: 10.5, fontWeight: 700,
              color: V.grey, textTransform: "uppercase", letterSpacing: ".5px",
            }}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} style={{ borderTop: `1px solid ${V.border}` }}>
            {r.map((cell, j) => (
              <td key={j} style={{ padding: "8px 10px", color: V.black }}>{cell}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const ATTACH_ICON = { NARRATIVE: "📝", EOB: "📑", AOB: "✍️", XRAY: "🩻", PERIO: "🦷" };

export default function PatientDocuments({ details }) {
  if (!details) {
    return (
      <Box title="Supporting documents">
        <div style={{ fontSize: 13, color: V.grey }}>
          No supporting documents were sent with this claim.
        </div>
      </Box>
    );
  }

  const {
    clinical_narrative, treatment_history = [], prior_claims = [],
    eob_summary: eob, cob_questionnaire: q, eligibility: el, attachments = [],
  } = details;

  return (
    <>
      {attachments.length > 0 && (
        <Box title={`Attachments received (${attachments.length})`} accent={V.teal}>
          <Table
            cols={["Document", "Type", "Date", "Pages"]}
            rows={attachments.map(a => [
              <span key="n">{ATTACH_ICON[a.type] || "📄"} {a.name}</span>,
              a.type, a.date, a.pages,
            ])}
          />
        </Box>
      )}

      {clinical_narrative && (
        <Box title="Clinical narrative">
          <div style={{ fontSize: 13, lineHeight: 1.7, color: V.black }}>{clinical_narrative}</div>
        </Box>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {treatment_history.length > 0 && (
          <Box title="Treatment history">
            <Table
              cols={["Date", "Code", "Tooth", "Note"]}
              rows={treatment_history.map(h => [h.date, h.code, h.tooth || "—", h.note])}
            />
          </Box>
        )}
        {prior_claims.length > 0 && (
          <Box title="Prior claims on file">
            <Table
              cols={["Date", "Payer", "Code", "Paid"]}
              rows={prior_claims.map(p => [p.date, p.payer, p.code, fmt$(p.paid)])}
            />
          </Box>
        )}
      </div>

      {eob && (
        <Box title={`Primary payer EOB · ${eob.eob_ref}`}>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 32px" }}>
            <div>
              <Row label="Payer" value={eob.payer} />
              <Row label="Billed" value={fmt$(eob.billed)} />
              <Row label="Contractual write-off" value={fmt$(eob.contractual_write_off)} />
              <Row label="Allowed" value={fmt$(eob.allowed)} />
            </div>
            <div>
              <Row label="Paid" value={fmt$(eob.paid)} />
              <Row label="Patient responsibility" value={fmt$(eob.patient_responsibility)} />
              <Row label="Paid on" value={`${eob.payment_date} · ${eob.payment_method}`} />
              <Row label="Settlement" value={(eob.settlement || "").replace("_", " ")} />
            </div>
          </div>
          <div style={{ marginTop: 10, fontSize: 12, color: V.grey }}>
            {(eob.remark_codes || []).map((r, i) => <div key={i}>• {r}</div>)}
          </div>
        </Box>
      )}

      {q && (
        <Box title="Coordination of benefits questionnaire">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 32px" }}>
            <div>
              <Row label="Other coverage" value={q.other_coverage ? "Yes" : "No"} />
              <Row label="Other payer" value={q.other_payer} />
              <Row label="Other policyholder" value={q.other_policyholder} />
              <Row label="Other member ID" value={q.other_member_id} mono />
              <Row label="Other policy effective" value={q.other_policy_effective} />
            </div>
            <div>
              <Row label="Patient relationship" value={`${q.patient_relationship} (age ${q.patient_age})`} />
              <Row label="Our subscriber" value={`${q.our_subscriber} · b. ${q.our_subscriber_dob}`} />
              {q.birthday_rule_applies !== false && (
                <Row label="Other policyholder DOB" value={q.other_policyholder_dob} />
              )}
              <Row label="Court order" value={q.court_order ? "Yes" : "None"} />
            </div>
          </div>
          {q.birthday_rule_applies === false ? (
            <div style={{
              marginTop: 10, padding: "9px 12px", borderRadius: 6, fontSize: 12.5,
              background: V.greenBg, color: V.green,
            }}>
              The birthday rule does not apply to this claim
              {q.liability_note ? <> ({q.liability_note})</> : null}. Order of liability
              is set by the payer's COB determination, not by the practice.
            </div>
          ) : (
            <div style={{
              marginTop: 10, padding: "9px 12px", borderRadius: 6, fontSize: 12.5,
              background: q.birthday_rule_consistent ? V.greenBg : V.redBg,
              color: q.birthday_rule_consistent ? V.green : V.red,
            }}>
              Birthday rule → <b>{q.birthday_rule_primary}</b> is primary.{" "}
              {q.birthday_rule_consistent
                ? "Consistent with the primary payer listed on the claim."
                : "Does not match the primary payer listed on the claim."}
            </div>
          )}
        </Box>
      )}

      {el && (
        <Box title="Eligibility at date of service (271 response)">
          <Table
            cols={["Plan", "Active", "Effective", "Annual max", "Remaining"]}
            rows={[el.primary, el.secondary].filter(Boolean).map(p => [
              p.payer, p.active ? "Yes" : "No", p.effective,
              fmt$(p.annual_max), fmt$(p.remaining),
            ])}
          />
        </Box>
      )}
    </>
  );
}
