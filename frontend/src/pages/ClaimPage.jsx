import React, { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { API } from "../constants";
import { S, T, fmt$, fmtDate, pill } from "../theme";
import UploadDocs from "../components/cob/UploadDocs";
import AgentRun from "../components/cob/AgentRun";
import CobRules from "../components/cob/CobRules";
import CobdFlow from "../components/cob/CobdFlow";
import Recommendation from "../components/cob/Recommendation";
import ReferralChain from "../components/cob/ReferralChain";
import { Card, DocRow, KV, Toast } from "../components/cob/Ui";

export default function ClaimPage() {
  const { claimId } = useParams();
  const navigate = useNavigate();

  const [claim, setClaim] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [toast, setToast] = useState(null);
  const [outcome, setOutcome] = useState(null);   // technician's own action

  const load = useCallback(async () => {
    const res = await fetch(`${API}/claim/${claimId}`);
    if (!res.ok) throw new Error("not found");
    return res.json();
  }, [claimId]);

  useEffect(() => {
    load().then(setClaim).catch(() => navigate("/"));
  }, [load, navigate]);

  // Run (or re-run) the agents. `body` carries technician edits; without it the
  // run simply picks up whatever edits and documents are already stored.
  async function runAdjudication(body) {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch(`${API}/claim/${claimId}/adjudicate`, {
        method: "POST",
        headers: body ? { "Content-Type": "application/json" } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      });
      if (!res.ok) {
        let msg = await res.text();
        try { msg = JSON.parse(msg).detail || msg; } catch { /* plain text */ }
        throw new Error(String(msg).slice(0, 300));
      }
      // Let the agent cards finish revealing before the verdict lands.
      await new Promise(r => setTimeout(r, 5400));
      setClaim(await load());
      setOutcome(null);
    } catch (err) {
      setError(err.message);
      throw err;
    } finally {
      setRunning(false);
    }
  }

  async function uploadDocuments(files) {
    const fd = new FormData();
    files.forEach(f => fd.append("files", f));
    const res = await fetch(`${API}/claim/${claimId}/documents`, { method: "POST", body: fd });
    if (!res.ok) {
      let msg = await res.text();
      try { msg = JSON.parse(msg).detail || msg; } catch { /* plain text */ }
      throw new Error(String(msg).slice(0, 200));
    }
    setClaim(await load());
    setToast(`${files.length} document${files.length === 1 ? "" : "s"} uploaded — run the AI adjudication again to include ${files.length === 1 ? "it" : "them"}.`);
  }

  async function deleteDocument(name) {
    await fetch(`${API}/claim/${claimId}/documents/${encodeURIComponent(name)}`, { method: "DELETE" });
    setClaim(await load());
  }

  async function decide(action) {
    if (action === "approve" || action === "hold") {
      try {
        const res = await fetch(`${API}/claim/${claimId}/resolve`, {
          method: "POST",
          body: new URLSearchParams({ action }),
        });
        if (!res.ok) throw new Error((await res.json()).detail || res.status);
        setClaim(await load());
        setToast(action === "approve"
          ? "✓ Approved. Payment written back — the AS/400 now shows this claim PAID."
          : "Claim held. Request sent to the primary insurer for additional information.");
      } catch (err) {
        setToast(`Write-back failed: ${err.message}`);
      }
    } else {
      setToast("Edit mode — a technician can adjust the figures before approving (prototype).");
    }
  }

  if (!claim) {
    return (
      <div style={{ padding: 60, textAlign: "center", color: T.mute, fontSize: 14 }}>
        Loading claim <strong style={{ color: T.white }}>{claimId}</strong>…
      </div>
    );
  }

  const gold = claim.gold_data || {};
  const prov = claim.provenance || {};
  const decision = claim.decision;
  const referred = prov.source === "AS400_REFERRAL";

  const statusPill = claim.resolution === "APPROVED"
    ? { kind: "ok",   text: "● PAID · written back to the AS/400" }
    : claim.resolution === "HELD"
      ? { kind: "hold", text: "● HELD · info requested" }
      : decision
        ? { kind: decision.decision === "APPROVED" ? "ok" : "pend",
            text: decision.decision === "APPROVED"
              ? "● RECOMMENDED · awaiting technician approval"
              : `● ${decision.decision.replace("_", " ")}` }
        : referred
          ? { kind: "pend", text: `● COB SUSPENSE · ${prov.suspend_code || "pending"}` }
          : { kind: "pend", text: "● AWAITING ADJUDICATION" };

  const procedures = gold.procedures || [];

  return (
    <div style={{ maxWidth: 1280, margin: "0 auto", padding: 22 }}>
      <p style={{ color: T.mute, fontSize: 12.5, marginBottom: 14, lineHeight: 1.5 }}>
        {referred
          ? "The payer's AS/400 could not coordinate this claim at line level, so it suspended and referred it. Watch the agents gather coverage, resolve the COB, compute the split, and produce an auditable recommendation for a technician to approve."
          : "A claim submitted directly to the workbench. Run the agents to adjudicate it end to end."}
      </p>

      {/* claim header */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: T.panel, border: `1px solid ${T.border}`, borderRadius: 10,
        padding: "16px 20px", marginBottom: 18, gap: 14, flexWrap: "wrap",
      }}>
        <div>
          <h2 style={{ fontSize: 18, color: T.white, margin: 0 }}>
            Claim {claim.claim_id}
            {(gold.patient_name || gold.subscriber_name) ? ` · ${gold.patient_name || gold.subscriber_name}` : ""}
          </h2>
          <div style={{ color: T.mute, fontSize: 12.5, marginTop: 3 }}>
            {(gold.cdt_codes || []).join(" + ") || "—"} · Billed {fmt$(gold.billed_amount)}
            {prov.as400_claim_no ? ` · Payer claim ${prov.as400_claim_no}` : ""}
          </div>
        </div>
        <span style={pill(statusPill.kind)}>{statusPill.text}</span>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "340px 1fr", gap: 18, alignItems: "start" }}>
        {/* ── LEFT: where it came from, and what we know ─────────────────── */}
        <div>
          <ReferralChain provenance={prov} />

          <Card title="📤 Source data">
            <DocRow
              icon="📄"
              name="837D claim"
              meta={`${(gold.cdt_codes || []).join(" + ") || "—"} · ${fmt$(gold.billed_amount)}`}
              badge="ok"
            />
            <DocRow
              icon="🪪"
              name="HCSC eligibility"
              meta={gold.subscriber_id || "—"}
              badge="ok"
            />
            {gold.cob_flag && (
              <DocRow
                icon="🪪"
                name={`${gold.primary_payer || "Primary"} coverage`}
                meta="secondary plan flagged on claim"
                badge="warn"
              />
            )}
            {gold.primary_eob_ref && (
              <DocRow
                icon="📑"
                name="Primary payer EOB"
                meta={gold.primary_eob_ref}
                badge="ok"
              />
            )}
            <div style={{ borderTop: `1px solid ${T.border}`, marginTop: 12, paddingTop: 12 }}>
              <KV rows={{
                Patient: gold.patient_name || gold.subscriber_name,
                Subscriber: gold.patient_name ? gold.subscriber_name : null,
                "Subscriber ID": gold.subscriber_id,
                Provider: gold.provider_name,
                "Date of service": gold.procedure_date,
                Received: fmtDate(claim.created_at),
              }} />
            </div>
          </Card>

          <UploadDocs
            documents={claim.documents || []}
            onUpload={uploadDocuments}
            onDelete={deleteDocument}
            locked={claim.resolution === "APPROVED"}
          />

          <Card title="🏥 Coverage on file">
            <div style={{ fontSize: 11, fontWeight: 700, color: T.greenText, marginBottom: 6 }}>
              PRIMARY
            </div>
            <KV rows={{
              Carrier: gold.primary_payer,
              "EOB reference": gold.primary_eob_ref,
              "Already paid": fmt$(gold.primary_paid_amount),
              Settlement: (gold.primary_settlement || "—").replace("_", " "),
            }} />
            <div style={{ fontSize: 11, fontWeight: 700, color: T.amber, margin: "12px 0 6px" }}>
              SECONDARY
            </div>
            <KV rows={{
              Carrier: "HCSC Dental",
              Coinsurance: gold.secondary_coinsurance ? `${gold.secondary_coinsurance}%` : null,
              Settlement: gold.secondary_settlement === "MONTHLY"
                ? `Monthly · ${fmt$(gold.monthly_cap)} × ${gold.term_months} mo`
                : (gold.secondary_settlement || "—").replace("_", " "),
            }} />
          </Card>

          {procedures.length > 0 && (
            <Card title="🦷 Procedure lines">
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <tbody>
                  {procedures.map((p, i) => (
                    <tr key={i}>
                      <td style={{ padding: "6px 0", borderBottom: `1px solid ${T.border}`, color: T.white, fontWeight: 600 }}>
                        {p.cdt_code}
                        {p.tooth_number ? <span style={{ color: T.mute2, fontWeight: 400 }}> · tooth {p.tooth_number}</span> : null}
                      </td>
                      <td style={{ padding: "6px 0", borderBottom: `1px solid ${T.border}`, textAlign: "right", color: T.mute }}>
                        {fmt$(p.fee)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Card>
          )}
        </div>

        {/* ── RIGHT: the agents, then the recommendation ──────────────────── */}
        <div>
          {claim.cobd && <CobdFlow cobd={claim.cobd} />}
          <AgentRun
            claim={claim}
            decision={running ? null : decision}
            running={running}
            error={error}
            onRun={() => runAdjudication().catch(() => {})}
          />
          <Recommendation
            claim={claim}
            decision={running ? null : decision}
            onDecide={decide}
            onRerun={() => runAdjudication().catch(() => {})}
            onSubmitEdits={body => runAdjudication(body)}
            running={running}
          />
          {gold.cob_flag && claim.cobd?.hcsc_role === "SECONDARY" && (
            <CobRules gold={gold} displayMetrics={claim.display_metrics} />
          )}

          {decision?.data_sources?.length > 0 && (
            <div style={{ ...S.card, marginTop: 18 }}>
              <div style={S.cardHead}>📋 Audit &amp; data lineage</div>
              <div style={{ padding: 0 }}>
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 11.5 }}>
                  <thead>
                    <tr>
                      {["Table", "Fields used"].map(h => (
                        <th key={h} style={{
                          background: T.panelHd, color: T.mute2, textAlign: "left",
                          padding: "8px 14px", fontSize: 10.5, fontWeight: 700,
                          textTransform: "uppercase", letterSpacing: ".5px",
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {decision.data_sources.map((s, i) => (
                      <tr key={i}>
                        <td style={{
                          padding: "9px 14px", borderBottom: `1px solid ${T.border}`,
                          color: T.azure, fontWeight: 700, whiteSpace: "nowrap", verticalAlign: "top",
                        }}>{s.table}</td>
                        <td style={{
                          padding: "9px 14px", borderBottom: `1px solid ${T.border}`,
                          color: T.mute, lineHeight: 1.7,
                        }}>
                          {Object.entries(s.row || {}).map(([k, v]) => (
                            <span key={k} style={{ marginRight: 10 }}>
                              <span style={{ color: T.mute2 }}>{k}:</span>{" "}
                              <span style={{ color: T.white }}>{String(v)}</span>
                            </span>
                          ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </div>

      <Toast message={toast} onDone={() => setToast(null)} />
    </div>
  );
}
