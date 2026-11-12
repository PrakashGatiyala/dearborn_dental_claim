import React, { useState } from "react";

const LAYER_META = [
  { key: "bronze", label: "Bronze",  color: "#cd7f32", statusMin: 0 },
  { key: "silver", label: "Silver",  color: "#c0c0c0", statusMin: 1 },
  { key: "gold",   label: "Gold",    color: "#f0c040", statusMin: 2 },
];

const STATUS_ORDER = ["UPLOADED", "SILVER_DONE", "GOLD_DONE", "ADJUDICATED"];

export default function MedallionLayers({ status, bronzeMeta, silverSummary, goldData }) {
  // track which layer is expanded; default: all open
  const [open, setOpen] = useState({ bronze: true, silver: true, gold: true });

  const currentIdx = STATUS_ORDER.indexOf(status);

  function toggle(key) {
    setOpen((prev) => ({ ...prev, [key]: !prev[key] }));
  }

  function renderBronzeBody() {
    if (!bronzeMeta) return <p style={s.none}>No metadata available.</p>;
    return (
      <table style={s.table}>
        <tbody>
          <TR k="Claim ID"       v={bronzeMeta.claim_id} />
          <TR k="Upload Time"    v={new Date(bronzeMeta.upload_ts).toLocaleString()} />
          <TR k="Claim PDF Size" v={`${(bronzeMeta.claim_size_bytes / 1024).toFixed(1)} KB`} />
          <TR k="Proof PDF Size" v={`${(bronzeMeta.policy_size_bytes / 1024).toFixed(1)} KB`} />
          <TR k="Files Stored"   v="claim.pdf  ·  policy.pdf  ·  meta.json" />
        </tbody>
      </table>
    );
  }

  function renderSilverBody() {
    if (!silverSummary) return <p style={s.none}>No extraction data available.</p>;
    const { claim_pdf, policy_pdf } = silverSummary;
    return (
      <div>
        <div style={s.pdfLabel}>Claim PDF — raw extracted text (preview)</div>
        <div style={s.meta}>
          Method: <b>{claim_pdf.method}</b>  ·  Pages: <b>{claim_pdf.page_count}</b>
        </div>
        <pre style={s.pre}>{claim_pdf.text_preview || "(empty)"}</pre>

        <div style={{ ...s.pdfLabel, marginTop: 14 }}>Proof / Policy PDF — raw extracted text (preview)</div>
        <div style={s.meta}>
          Method: <b>{policy_pdf.method}</b>  ·  Pages: <b>{policy_pdf.page_count}</b>
        </div>
        <pre style={s.pre}>{policy_pdf.text_preview || "(empty)"}</pre>
      </div>
    );
  }

  function renderGoldBody() {
    if (!goldData) return <p style={s.none}>No parsed data available.</p>;
    return (
      <table style={s.table}>
        <tbody>
          <TR k="Subscriber ID"      v={goldData.subscriber_id} />
          <TR k="CDT Codes"          v={(goldData.cdt_codes || []).join(", ")} />
          <TR k="Procedure Date"     v={goldData.procedure_date} />
          <TR k="Billed Amount"      v={goldData.billed_amount != null ? `$${Number(goldData.billed_amount).toLocaleString()}` : null} />
          <TR k="Provider Name"      v={goldData.provider_name} />
          <TR k="Provider NPI"       v={goldData.provider_npi} />
          <TR k="X-Ray Present"      v={goldData.xray_present ? "Yes" : "No"} />
          <TR k="COB Flag"           v={goldData.cob_flag ? "Yes — secondary insurance found" : "No"} />
          <TR k="Predetermination #" v={goldData.predetermination_number || "None"} />
          <TR k="Parsed At"          v={goldData.parsed_at ? new Date(goldData.parsed_at).toLocaleString() : null} />
        </tbody>
      </table>
    );
  }

  const bodies = { bronze: renderBronzeBody, silver: renderSilverBody, gold: renderGoldBody };

  return (
    <div style={s.wrapper}>
      <div style={s.heading}>Medallion Pipeline — Extracted Data</div>

      {LAYER_META.map(({ key, label, color, statusMin }) => {
        if (currentIdx < statusMin) return null; // layer not reached yet

        const isOpen = open[key];
        return (
          <div key={key} style={{ ...s.card, borderLeftColor: color }}>
            {/* Header — always visible */}
            <button style={s.header} onClick={() => toggle(key)}>
              <span style={{ ...s.badge, color, borderColor: color }}>
                {label}
              </span>
              <span style={s.headerLabel}>
                {key === "bronze" && "Raw PDFs — upload metadata"}
                {key === "silver" && "Extracted text from each PDF"}
                {key === "gold"   && "Structured parsed claim fields"}
              </span>
              <span style={{ ...s.chevron, color }}>
                {isOpen ? "▲" : "▼"}
              </span>
            </button>

            {/* Body — shown when expanded */}
            {isOpen && (
              <div style={s.body}>
                {bodies[key]()}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function TR({ k, v }) {
  return (
    <tr>
      <td style={s.tdKey}>{k}</td>
      <td style={s.tdVal}>{v ?? "—"}</td>
    </tr>
  );
}

const s = {
  wrapper: { marginBottom: 24 },
  heading: {
    fontSize: 11,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "1px",
    color: "#8090a0",
    marginBottom: 10,
  },
  card: {
    borderLeft: "3px solid",
    borderRadius: "0 6px 6px 0",
    background: "#0d1828",
    marginBottom: 8,
    overflow: "hidden",
  },
  header: {
    width: "100%",
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "10px 16px",
    background: "transparent",
    border: "none",
    borderBottom: "1px solid #1a2535",
    cursor: "pointer",
    textAlign: "left",
    color: "#c0cce0",
  },
  badge: {
    fontSize: 11,
    fontWeight: 800,
    textTransform: "uppercase",
    letterSpacing: "1px",
    border: "1px solid",
    borderRadius: 4,
    padding: "2px 8px",
    flexShrink: 0,
  },
  headerLabel: {
    flex: 1,
    fontSize: 13,
    color: "#8090a0",
  },
  chevron: {
    fontSize: 11,
    fontWeight: 700,
    flexShrink: 0,
  },
  body: {
    padding: "14px 16px",
  },
  table: {
    width: "100%",
    borderCollapse: "collapse",
  },
  tdKey: {
    fontSize: 11,
    color: "#6070a0",
    textTransform: "uppercase",
    letterSpacing: "0.5px",
    padding: "5px 16px 5px 0",
    verticalAlign: "top",
    whiteSpace: "nowrap",
    width: "32%",
  },
  tdVal: {
    fontSize: 13,
    color: "#c8d8e8",
    padding: "5px 0",
    wordBreak: "break-word",
  },
  pdfLabel: {
    fontSize: 11,
    fontWeight: 700,
    textTransform: "uppercase",
    letterSpacing: "0.5px",
    color: "#6070a0",
    marginBottom: 6,
  },
  meta: {
    fontSize: 12,
    color: "#7a8a9a",
    marginBottom: 6,
  },
  pre: {
    background: "#060d18",
    border: "1px solid #1e2d40",
    borderRadius: 4,
    padding: "10px 12px",
    fontSize: 11,
    color: "#6a9a6a",
    overflowX: "auto",
    overflowY: "auto",
    whiteSpace: "pre-wrap",
    wordBreak: "break-word",
    maxHeight: 180,
    margin: 0,
  },
  none: {
    fontSize: 13,
    color: "#445",
    margin: 0,
  },
};
