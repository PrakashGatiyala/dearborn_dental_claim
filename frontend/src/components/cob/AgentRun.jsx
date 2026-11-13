import React, { useEffect, useMemo, useRef, useState } from "react";
import { S, T, btn, fmt$ } from "../../theme";
import { Confidence, Ext, Result } from "./Ui";

/**
 * The six agents, rendered as the prototype does: each reveals in sequence
 * with a "thinking" note, any external system it reached out to, and its
 * output. The difference from the prototype is that these are narrating a real
 * adjudication — the figures come from the claim and the agent's decision, not
 * from a fixture.
 */

function buildSteps(claim, decision) {
  const gold = claim?.gold_data || {};
  const prov = claim?.provenance || {};
  const silver = claim?.silver_summary || {};
  const segs = silver?.edi?.segment_count;

  const billed    = gold.billed_amount;
  const primPaid  = gold.primary_paid_amount;
  const allowed   = gold.primary_allowed_amount;
  const remaining = allowed != null && primPaid != null
    ? Math.round((allowed - primPaid) * 100) / 100
    : null;
  const coins     = gold.secondary_coinsurance;
  const obligation = decision?.approved_amount
    ?? decision?.display_metrics?.secondary_owes
    ?? claim?.display_metrics?.secondary_owes;

  const sources = decision?.data_sources || [];
  const srcNames = sources.map(s => s.table).filter(Boolean);

  const monthly = gold.secondary_settlement === "MONTHLY";
  const cap = gold.monthly_cap;
  const term = gold.term_months;
  const monthsNeeded = monthly && cap && obligation ? Math.ceil(obligation / cap) : null;

  return [
    {
      n: 1,
      title: "Intake Agent",
      tech: "Claim ingestion · EDI 837D parser",
      think: prov.source === "AS400_REFERRAL"
        ? `Received suspended claim ${prov.as400_claim_no} from the HCSC AS/400, originally transmitted through Vyne as ${prov.vyne_tracking_id}. Parsed the 837D${segs ? ` — ${segs} segments` : ""}. Suspend code ${prov.suspend_code} confirms coordination of benefits is the blocker.`
        : `Received claim ${claim?.claim_id} via direct upload. Parsed the 837D${segs ? ` — ${segs} segments` : ""} and normalised it through Bronze → Silver → Gold.`,
      result: `Claim normalised · ${(gold.cdt_codes || []).join(" + ") || "no CDT codes"} · billed ${fmt$(billed)}.`,
      ext: prov.source === "AS400_REFERRAL"
        ? [
            { t: `HCSC AS/400 · suspense queue · ${prov.as400_claim_no}`, kind: "vyne", href: prov.as400_screen_url },
            { t: `Vyne gateway · transmission ${prov.vyne_tracking_id}`, kind: "vyne", href: prov.vyne_portal_url },
          ]
        : [{ t: "Workbench upload", kind: "" }],
    },
    {
      n: 2,
      title: "Eligibility Agent",
      tech: "Member, plan and coverage lookups",
      think: "Verifying the member is active, resolving the plan, and pulling the coverage rule and contracted fee for every procedure on the claim.",
      result: srcNames.length
        ? `Coverage assembled from ${srcNames.length} table${srcNames.length === 1 ? "" : "s"}: ${srcNames.join(", ")}.`
        : "Awaiting adjudication — no lookups performed yet.",
      ext: [{ t: "HCSC member database · eligibility, plan, coverage rules, fee schedule", kind: "" }],
    },
    {
      n: 3,
      title: "COB Determination",
      tech: "Primary/secondary resolution",
      think: gold.cob_flag
        ? `Claim carries two plans. ${gold.primary_payer || "The primary payer"} has already settled; HCSC is secondary. Retrieving the primary EOB to establish what remains.`
        : "No secondary coverage flagged on this claim — standard single-plan adjudication.",
      result: gold.cob_flag
        ? `COB confirmed — primary ${gold.primary_payer || "unknown"}${gold.primary_eob_ref ? ` (EOB ${gold.primary_eob_ref})` : ""}, settled ${(gold.primary_settlement || "LUMP_SUM").replace("_", " ").toLowerCase()}.`
        : "Single plan — no coordination required.",
      ext: gold.primary_eob_ref
        ? [{ t: `${gold.primary_payer || "Primary payer"} · EOB ${gold.primary_eob_ref}`, kind: "vyne" }]
        : [],
      cob: gold.cob_flag ? {
        primary: gold.primary_payer,
        primarySettle: gold.primary_settlement,
        secondarySettle: gold.secondary_settlement,
        cap, term,
      } : null,
    },
    {
      n: 4,
      title: "Benefit Calculation",
      tech: "Remaining balance and coinsurance split",
      think: "Computing secondary obligation from primary allowed minus primary paid (COB remainder), applying coinsurance and plan caps, then checking no overpayment vs billed.",
      result: remaining != null
        ? `Allowed ${fmt$(allowed)} − primary ${fmt$(primPaid)} = ${fmt$(remaining)} remaining.`
        : "Figures unavailable until adjudication runs.",
      calc: remaining != null ? { billed, allowed, primPaid, remaining, coins, obligation, monthly, cap, term, monthsNeeded } : null,
      ext: [],
    },
    {
      n: 5,
      title: "Recommendation Agent",
      tech: "Decision assembly + audit lineage",
      think: "Assembling an auditable recommendation: the determination, every database row cited, the arithmetic, and a confidence score.",
      result: decision
        ? `Recommendation built · ${decision.decision} · ${Math.round((decision.confidence || 0) * 100)}% confidence · ${sources.length} row${sources.length === 1 ? "" : "s"} cited.`
        : "Not yet run.",
      conf: decision ? Math.round((decision.confidence || 0) * 100) : null,
      ext: [],
    },
    {
      n: 6,
      title: "Orchestrator → Human review",
      tech: "Routing · technician review",
      think: decision?.decision === "NEEDS_REVIEW"
        ? "This determination depends on a document nobody has physically verified with the primary insurer. Policy keeps a technician in the loop — routing the completed dossier for confirmation."
        : "Confidence is sufficient for straight-through handling, but COB policy keeps a technician in the loop on any coordinated payment.",
      result: decision
        ? (decision.decision === "NEEDS_REVIEW"
            ? "Escalated to a claims technician with the full dossier and the escalation reason."
            : "Routed to a technician for one-click approval.")
        : "Awaiting adjudication.",
      ext: [],
    },
  ];
}

function CobPath({ cob }) {
  if (!cob) return null;
  const incompatible = cob.primarySettle !== cob.secondarySettle;
  const rows = [
    ["Two plans on the claim?", "Primary and secondary subscriber loops present", "Yes"],
    ["Primary already settled?", `${cob.primary || "Primary"} paid before submission`, "Yes"],
    ["Primary settlement mode", (cob.primarySettle || "—").replace("_", " "), "—"],
    ["Secondary settlement mode",
      cob.secondarySettle === "MONTHLY"
        ? `Monthly, capped ${fmt$(cob.cap)} × ${cob.term} months`
        : (cob.secondarySettle || "—").replace("_", " "),
      "—"],
    ["Settlement rules reconcile?",
      incompatible ? "Lump-sum obligation vs capped monthly schedule" : "Both plans settle the same way",
      incompatible ? "No" : "Yes"],
  ];
  return (
    <Result label="COB DETERMINATION PATH">
      <div style={{ fontSize: 11.5, lineHeight: 1.9 }}>
        {rows.map(([q, detail, verdict], i) => (
          <div key={i}>
            <span style={{
              display: "inline-block", background: T.panelHd, border: `1px solid ${T.azure}`,
              borderRadius: 4, padding: "1px 7px", margin: "2px 0", fontWeight: 600, color: "#0A5E91",
            }}>{q}</span>{" "}
            <span style={{ color: T.mute2 }}>{detail}</span>
            {verdict !== "—" && (
              <> → <span style={{ color: verdict === "Yes" ? T.greenText : T.red, fontWeight: 700 }}>{verdict}</span></>
            )}
          </div>
        ))}
      </div>
    </Result>
  );
}

function CalcTable({ calc }) {
  if (!calc) return null;
  const { billed, allowed, primPaid, remaining, coins, obligation, monthly, cap, term, monthsNeeded } = calc;
  const total = obligation != null && primPaid != null ? Math.round((primPaid + obligation) * 100) / 100 : null;
  const safe = total != null && billed != null && total <= billed;

  const rows = [
    ["Primary allowed (COB basis)", fmt$(allowed), null],
    [`Less primary paid`, "−" + fmt$(primPaid), null],
    ["Remaining COB balance", fmt$(remaining), T.azure],
    ["Billed charges (overpayment check)", fmt$(billed), null],
    [coins ? `Secondary coinsurance ${coins}%` : "Secondary obligation", fmt$(obligation), T.amber],
  ];

  return (
    <Result label="LINE-LEVEL COORDINATION">
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, marginTop: 4 }}>
        <tbody>
          {rows.map(([label, value, colour], i) => (
            <tr key={i}>
              <td style={{ padding: "6px 9px", borderBottom: `1px solid ${T.border}`, color: T.mute }}>{label}</td>
              <td style={{
                padding: "6px 9px", borderBottom: `1px solid ${T.border}`,
                textAlign: "right", fontWeight: 700, color: colour || T.white,
              }}>{value}</td>
            </tr>
          ))}
          {total != null && (
            <tr>
              <td style={{ padding: "6px 9px", fontWeight: 700, color: T.mute }}>
                Combined payers vs billed
              </td>
              <td style={{
                padding: "6px 9px", textAlign: "right", fontWeight: 700,
                color: safe ? T.greenText : T.red,
              }}>
                {fmt$(total)} {safe ? "≤" : ">"} {fmt$(billed)} {safe ? "✓" : "✕"}
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {monthly && (
        <div style={{ ...S.flag, marginTop: 10 }}>
          ⚑ Secondary disburses {fmt$(cap)} per month for {term} months — a ceiling of{" "}
          {fmt$((cap || 0) * (term || 0))}.{" "}
          {monthsNeeded
            ? `Clearing ${fmt$(obligation)} needs ${monthsNeeded} month${monthsNeeded === 1 ? "" : "s"}, ${monthsNeeded > (term || 0) ? "which exceeds the term — an override is required." : "which fits inside the term."}`
            : "The obligation has not been computed yet."}
        </div>
      )}
    </Result>
  );
}

function AgentCard({ step, state, open, onToggle }) {
  const done = state === "done";
  const active = state === "active";
  return (
    <div style={{
      background: T.panel,
      border: `1px solid ${active ? T.green : T.border}`,
      borderRadius: 10, marginBottom: 12, overflow: "hidden",
      opacity: state === "waiting" ? 0.35 : 1,
      transition: "opacity .4s, border-color .3s",
    }}>
      <div onClick={onToggle} style={{
        display: "flex", alignItems: "center", gap: 12, padding: "12px 16px", cursor: "pointer",
      }}>
        <div style={{
          width: 30, height: 30, borderRadius: "50%", flexShrink: 0,
          background: done ? T.green : T.panelHd,
          border: `1.5px solid ${T.green}`, color: done ? "#FFFFFF" : T.greenText,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontWeight: 700, fontSize: 13,
        }}>{step.n}</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: 13.5, color: T.white }}>{step.title}</div>
          <div style={{ fontSize: 11, color: T.azure, marginTop: 2 }}>{step.tech}</div>
        </div>
        <div style={{
          marginLeft: "auto", fontSize: 11, fontWeight: 700,
          color: done ? T.greenText : active ? T.amber : T.mute2,
        }}>
          {done ? "✓ done" : active ? "running…" : "waiting"}
        </div>
      </div>

      {open && state !== "waiting" && (
        <div style={{ padding: "0 16px 14px 58px" }}>
          <div style={S.think}>{step.think}</div>
          {step.ext.map((e, i) => (
            <Ext key={i} kind={e.kind} href={e.href}>{e.t}</Ext>
          ))}
          <Result label="OUTPUT">{step.result}</Result>
          <CobPath cob={step.cob} />
          <CalcTable calc={step.calc} />
          {step.conf != null && <Confidence pct={step.conf} />}
        </div>
      )}
    </div>
  );
}

export default function AgentRun({ claim, decision, running, onRun, error }) {
  const steps = useMemo(() => buildSteps(claim, decision), [claim, decision]);
  const [revealed, setRevealed] = useState(decision ? steps.length : 0);
  const [open, setOpen] = useState(() => new Set());
  const timers = useRef([]);

  // When a run starts, reveal the agents one at a time so the reviewer can
  // follow the reasoning rather than being handed a finished wall of text.
  useEffect(() => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
    if (!running) {
      if (decision) {
        setRevealed(steps.length);
        setOpen(new Set([steps.length - 1]));
      }
      return undefined;
    }
    setRevealed(0);
    setOpen(new Set());
    for (let i = 0; i < steps.length; i += 1) {
      timers.current.push(setTimeout(() => {
        setRevealed(i + 1);
        setOpen(new Set([i]));
      }, i * 900));
    }
    return () => timers.current.forEach(clearTimeout);
  }, [running, decision, steps.length]);

  function toggle(i) {
    setOpen(prev => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }

  if (!decision && !running) {
    return (
      <div style={{
        textAlign: "center", padding: 30, background: T.panel,
        border: `1px dashed ${T.border}`, borderRadius: 10,
      }}>
        <p style={{ color: T.mute, marginBottom: 16, fontSize: 13 }}>
          Six agents are ready to work this COB claim end to end.
        </p>
        <button style={btn.primary} onClick={onRun}>▶ Run agentic COB adjudication</button>
        {error && (
          <div style={{ ...S.flag, marginTop: 14, textAlign: "left" }}>⚑ {error}</div>
        )}
      </div>
    );
  }

  return (
    <div>
      {steps.map((s, i) => (
        <AgentCard
          key={s.n}
          step={s}
          state={i < revealed - (running ? 1 : 0) ? "done" : i < revealed ? (running ? "active" : "done") : "waiting"}
          open={open.has(i)}
          onToggle={() => toggle(i)}
        />
      ))}
      {error && <div style={S.flag}>⚑ {error}</div>}
    </div>
  );
}
