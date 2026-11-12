import React from "react";
import { C } from "../../constants";
import Card from "../ui/Card";
import SectionTag from "../ui/SectionTag";
import MedalLayer from "../ui/MedalLayer";
import CodeBlock from "../ui/CodeBlock";
import NavButtons from "../ui/NavButtons";
import UploadForm from "../UploadForm";

export default function Panel0Upload({ claim, onClaimReady, step, maxS, setStep }) {
  if (!claim || !claim.bronze_meta) {
    return (
      <div>
        <SectionTag text="Step 1 of 6" />
        <div style={{ fontSize: 20, fontWeight: 700, color: C.darkBlue, marginBottom: 4 }}>Submit New Claim</div>
        <div style={{ fontSize: 13, color: C.grey, marginBottom: 22 }}>Upload the patient's ADA claim form and any supporting document (radiograph, predetermination notice, or EOB).</div>
        <Card><UploadForm onClaimReady={onClaimReady} /></Card>
      </div>
    );
  }

  const m = claim.bronze_meta;
  return (
    <div>
      <SectionTag text="Step 1 of 6" />
      <div style={{ fontSize: 20, fontWeight: 700, color: C.darkBlue, marginBottom: 4 }}>Raw Claim Data Ingested</div>
      <div style={{ fontSize: 13, color: C.grey, marginBottom: 22 }}>PDFs received and stored as the immutable bronze record.</div>
      <MedalLayer tier="bronze" title="Ingestion Record">
        <CodeBlock>{JSON.stringify({ claim_id: m.claim_id, ingested_at: m.upload_ts, claim_pdf_bytes: m.claim_size_bytes, proof_pdf_bytes: m.policy_size_bytes, immutable: true }, null, 2)}</CodeBlock>
      </MedalLayer>
      <NavButtons step={step} maxS={maxS} onPrev={() => {}} onNext={() => setStep(1)} nextLabel="Bronze Layer →" />
    </div>
  );
}
