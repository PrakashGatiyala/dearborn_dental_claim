import React from "react";
import { C } from "../../constants";
import SectionTag from "../ui/SectionTag";
import MedalLayer from "../ui/MedalLayer";
import DetailGrid from "../ui/DetailGrid";
import NavButtons from "../ui/NavButtons";

export default function Panel3Gold({ claim, step, maxS, setStep }) {
  const g = claim?.gold_data;
  return (
    <div>
      <SectionTag text="Step 4 of 6" />
      <div style={{ fontSize: 20, fontWeight: 700, color: C.darkBlue, marginBottom: 4 }}>Gold Layer — Structured Claim Fields</div>
      <div style={{ fontSize: 13, color: C.grey, marginBottom: 22 }}>Parsed claim fields extracted from silver text and ready for the AI adjudication agent.</div>
      <MedalLayer tier="gold" title="Parsed Claim Data">
        {g ? (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: C.grey, marginBottom: 8, textTransform: "uppercase" }}>Member & Claim</div>
              <DetailGrid rows={[
                ["Subscriber ID", g.subscriber_id],
                ["CDT Codes", (g.cdt_codes || []).join(", ")],
                ["Procedure Date", g.procedure_date],
                ["Billed Amount", g.billed_amount != null ? `$${Number(g.billed_amount).toLocaleString()}` : null],
                ["Predetermination #", g.predetermination_number || "None"],
              ]} />
            </div>
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: C.grey, marginBottom: 8, textTransform: "uppercase" }}>Provider & Flags</div>
              <DetailGrid rows={[
                ["Provider", g.provider_name],
                ["NPI", g.provider_npi],
                ["X-Ray Present", g.xray_present ? "Yes ✓" : "No"],
                ["COB Flag", g.cob_flag ? "Yes — secondary insurance" : "No"],
                ["Parsed At", g.parsed_at ? new Date(g.parsed_at).toLocaleString() : null],
              ]} />
            </div>
          </div>
        ) : (
          <div style={{ color: C.grey, fontSize: 13 }}>No gold data available.</div>
        )}
      </MedalLayer>
      <NavButtons step={step} maxS={maxS} onPrev={() => setStep(2)} onNext={() => setStep(4)} nextLabel="Agent Orchestration →" />
    </div>
  );
}
