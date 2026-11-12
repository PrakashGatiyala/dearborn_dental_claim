import React from "react";
import { C, btn } from "../../constants";
import Card from "../ui/Card";
import SectionTag from "../ui/SectionTag";
import NavButtons from "../ui/NavButtons";

export default function Panel4Agent({ claim, step, maxS, setStep, adjudicating, adjError, onAdjudicate }) {
  const dec = claim?.decision;
  return (
    <div>
      <SectionTag text="Step 5 of 6" />
      <div style={{ fontSize: 20, fontWeight: 700, color: C.darkBlue, marginBottom: 4 }}>Agentic AI Orchestration</div>
      <div style={{ fontSize: 13, color: C.grey, marginBottom: 22 }}>The AI agent queries the insurance master database using tool calls to verify eligibility, coverage rules, and fee schedules.</div>

      {!dec ? (
        <Card title="🤖 Ready for Adjudication">
          <div style={{ fontSize: 13, color: C.grey, marginBottom: 16 }}>Gold-layer context is loaded. Click below to run the GPT-4o agent against the master insurance database.</div>
          <button onClick={onAdjudicate} disabled={adjudicating} style={{ ...btn.primary, opacity: adjudicating ? .6 : 1, cursor: adjudicating ? "not-allowed" : "pointer" }}>
            {adjudicating ? "Agent is reviewing…" : "Run AI Adjudication"}
          </button>
          {adjudicating && (
            <div style={{ marginTop: 12, padding: "10px 14px", background: "#E8F2FB", borderRadius: 6, fontSize: 12, color: C.darkBlue }}>
              GPT-4o agent is querying coverage rules, waiting periods, and fee schedules…
            </div>
          )}
          {adjError && (
            <div style={{ marginTop: 12, padding: "10px 14px", background: "#FAD7D3", borderRadius: 6, fontSize: 12, color: C.red }}>
              <strong>Error:</strong> {adjError}
            </div>
          )}
        </Card>
      ) : (
        <div>
          <div style={{ padding: "10px 14px", background: "#E8F2FB", border: `1px solid #b3d4f0`, borderRadius: 6, fontSize: 12, color: C.darkBlue, marginBottom: 16 }}>
            🤖 All agent tool calls complete. Claim adjudicated with {Math.round((dec.confidence || 0) * 100)}% confidence.
          </div>
          <Card title="🧠 Agent Reasoning">
            <div style={{ background: "#F8F9FF", borderLeft: `3px solid ${C.lightBlue}`, padding: "10px 12px", borderRadius: "0 4px 4px 0", fontSize: 12, color: C.black, lineHeight: 1.7 }}>
              {dec.justification}
            </div>
          </Card>
          {dec.data_sources && dec.data_sources.length > 0 && (
            <Card title="🔍 Database Tool Calls">
              {dec.data_sources.map((ds, i) => (
                <div key={i} style={{ marginBottom: 12, paddingBottom: 12, borderBottom: i < dec.data_sources.length - 1 ? `1px solid ${C.border}` : "none" }}>
                  <div style={{ fontSize: 11, fontWeight: 700, color: C.blue, textTransform: "uppercase", marginBottom: 6 }}>lookup_{ds.table}()</div>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                    {Object.entries(ds.row || {}).map(([k, v]) => (
                      <span key={k} style={{ background: C.lightGrey, border: `1px solid ${C.border}`, borderRadius: 4, fontSize: 11, padding: "2px 8px" }}>
                        <span style={{ color: C.grey }}>{k}: </span><span style={{ fontWeight: 600 }}>{String(v)}</span>
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </Card>
          )}
        </div>
      )}

      <NavButtons step={step} maxS={maxS} onPrev={() => setStep(3)} onNext={() => setStep(5)} nextLabel="Decision & Audit →" />
    </div>
  );
}
