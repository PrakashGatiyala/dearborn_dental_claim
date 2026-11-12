import React from "react";
import { C } from "../../constants";
import Card from "../ui/Card";
import SectionTag from "../ui/SectionTag";
import MedalLayer from "../ui/MedalLayer";
import CodeBlock from "../ui/CodeBlock";
import NavButtons from "../ui/NavButtons";

export default function Panel1Bronze({ claim, step, maxS, setStep }) {
  const m = claim?.bronze_meta;
  const isEdi = m?.input_type === "edi";

  const bronzeJson = m
    ? isEdi
      ? JSON.stringify({
          claim_id:      m.claim_id,
          ingested_at:   m.upload_ts,
          input_type:    "edi",
          edi_filename:  m.edi_filename,
          edi_size_kb:   (m.edi_size_bytes / 1024).toFixed(1),
          files:         ["transmission.edi", "meta.json"],
          immutable:     true,
        }, null, 2)
      : JSON.stringify({
          claim_id:      m.claim_id,
          ingested_at:   m.upload_ts,
          input_type:    "pdf",
          claim_pdf_kb:  (m.claim_size_bytes / 1024).toFixed(1),
          proof_pdf_kb:  (m.policy_size_bytes / 1024).toFixed(1),
          files:         ["claim.pdf", "policy.pdf", "meta.json"],
          immutable:     true,
        }, null, 2)
    : "No bronze metadata available.";

  return (
    <div>
      <SectionTag text="Step 2 of 6" />
      <div style={{ fontSize: 20, fontWeight: 700, color: C.darkBlue, marginBottom: 4 }}>Bronze Layer — Raw Ingestion</div>
      <div style={{ fontSize: 13, color: C.grey, marginBottom: 22 }}>
        {isEdi
          ? "Immutable EDI transmission record created. Raw 837D bytes stored without modification."
          : "Immutable record created. Data timestamped and stored without modification."}
      </div>
      {isEdi && (
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          padding: "10px 14px", marginBottom: 14,
          background: "#E8F5F0", border: "1px solid #A8DBBE", borderRadius: 8,
        }}>
          <span style={{ background: "#1E8A4A", color: "#fff", fontSize: 10, fontWeight: 700, letterSpacing: 1, padding: "3px 8px", borderRadius: 3 }}>
            EDI 837D
          </span>
          <span style={{ fontSize: 13, fontWeight: 600, color: "#1E8A4A" }}>Transmission Received</span>
          <span style={{ fontSize: 12, color: C.grey, marginLeft: "auto" }}>
            {m?.edi_filename} · {(m?.edi_size_bytes / 1024).toFixed(1)} KB
          </span>
        </div>
      )}
      <MedalLayer tier="bronze" title="Ingestion Record Created">
        <CodeBlock>{bronzeJson}</CodeBlock>
      </MedalLayer>
      <Card title="🔒 Bronze Layer Principles">
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, fontSize: 12 }}>
          {[
            ["Immutable", "Records never overwritten — original PDFs always retrievable for dispute resolution."],
            ["Source-tagged", "Every file carries its origin: upload timestamp, size, and claim reference."],
            ["Checksummed", "Raw bytes preserved — any downstream modification is detectable."],
          ].map(([h, d]) => (
            <div key={h}><strong style={{ color: C.darkBlue }}>{h}</strong><br /><span style={{ color: C.grey }}>{d}</span></div>
          ))}
        </div>
      </Card>
      <NavButtons step={step} maxS={maxS} onPrev={() => setStep(0)} onNext={() => setStep(2)} nextLabel="Silver Layer →" />
    </div>
  );
}
