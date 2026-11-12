import React from "react";
import { C } from "../../constants";
import SectionTag from "../ui/SectionTag";
import MedalLayer from "../ui/MedalLayer";
import CodeBlock from "../ui/CodeBlock";
import NavButtons from "../ui/NavButtons";

export default function Panel2Silver({ claim, step, maxS, setStep }) {
  const sv = claim?.silver_summary;
  const isEdi = sv?.input_type === "edi";

  return (
    <div>
      <SectionTag text="Step 3 of 6" />
      <div style={{ fontSize: 20, fontWeight: 700, color: C.darkBlue, marginBottom: 4 }}>
        Silver Layer — {isEdi ? "EDI Parsed" : "Text Extracted"}
      </div>
      <div style={{ fontSize: 13, color: C.grey, marginBottom: 22 }}>
        {isEdi
          ? "EDI 837D transmission parsed into structured segments. Each X12 segment decoded to human-readable form."
          : "Text extracted from each PDF using native parsing (or OCR fallback)."}
      </div>

      <MedalLayer tier="silver" title={isEdi ? "EDI 837D Segment Breakdown" : "PDF Text Extraction"}>
        {sv ? (
          isEdi ? <EdiSegmentTable data={sv.edi} /> : <PdfTextView sv={sv} />
        ) : (
          <div style={{ color: C.grey, fontSize: 13 }}>No silver data available.</div>
        )}
      </MedalLayer>

      <NavButtons step={step} maxS={maxS} onPrev={() => setStep(1)} onNext={() => setStep(3)} nextLabel="Gold Layer →" />
    </div>
  );
}

function EdiSegmentTable({ data }) {
  if (!data || !data.segments || data.segments.length === 0) {
    return <div style={{ color: C.grey, fontSize: 13 }}>No EDI segments available.</div>;
  }

  return (
    <div>
      <div style={{ fontSize: 12, color: "#1E8A4A", fontWeight: 600, marginBottom: 10 }}>
        {data.segment_count} segments · X12 005010X224A2
      </div>

      {/* Segment table */}
      <div style={{ borderRadius: 6, overflow: "hidden", border: "1px solid #A8DBBE" }}>
        {/* Header */}
        <div style={{
          display: "grid", gridTemplateColumns: "56px 170px 150px 1fr",
          background: "#1E8A4A", color: "#fff",
          fontSize: 10, fontWeight: 700, letterSpacing: ".5px",
          padding: "7px 12px", textTransform: "uppercase",
        }}>
          <div>ID</div>
          <div>Segment Name</div>
          <div>Context</div>
          <div>Description</div>
        </div>

        {data.segments.map((seg, i) => (
          <div key={i} style={{
            display: "grid", gridTemplateColumns: "56px 170px 150px 1fr",
            padding: "7px 12px", fontSize: 12,
            background: i % 2 === 0 ? "#fff" : "#F4FBF7",
            borderBottom: "1px solid #ddeee6",
            alignItems: "start",
          }}>
            <div style={{ fontFamily: "monospace", fontWeight: 700, color: "#1E8A4A" }}>{seg.id}</div>
            <div style={{ color: C.darkBlue, fontWeight: 600, lineHeight: 1.4 }}>{seg.name}</div>
            <div style={{ color: C.grey, fontStyle: seg.qualifier_context ? "normal" : "italic", lineHeight: 1.4 }}>
              {seg.qualifier_context || "—"}
            </div>
            <div style={{ color: C.black, lineHeight: 1.5 }}>{seg.description}</div>
          </div>
        ))}
      </div>

      {/* Raw EDI toggle */}
      <details style={{ marginTop: 10 }}>
        <summary style={{ fontSize: 11, color: C.grey, cursor: "pointer", userSelect: "none" }}>
          Show raw EDI text
        </summary>
        <div style={{ marginTop: 6 }}>
          <CodeBlock>{data.raw_preview || "(empty)"}</CodeBlock>
        </div>
      </details>
    </div>
  );
}

function PdfTextView({ sv }) {
  return (
    <div>
      <div style={{ fontSize: 11, fontWeight: 700, color: C.grey, marginBottom: 6, textTransform: "uppercase" }}>
        Claim PDF — Method: {sv.claim_pdf.method} · Pages: {sv.claim_pdf.page_count}
      </div>
      <CodeBlock>{sv.claim_pdf.text_preview || "(no text)"}</CodeBlock>
      <div style={{ fontSize: 11, fontWeight: 700, color: C.grey, margin: "14px 0 6px", textTransform: "uppercase" }}>
        Proof / Policy PDF — Method: {sv.policy_pdf.method} · Pages: {sv.policy_pdf.page_count}
      </div>
      <CodeBlock>{sv.policy_pdf.text_preview || "(no text)"}</CodeBlock>
      <div style={{ fontSize: 11, color: C.grey, marginTop: 8 }}>
        Extracted at: {sv.extracted_at ? new Date(sv.extracted_at).toLocaleString() : "—"}
      </div>
    </div>
  );
}
