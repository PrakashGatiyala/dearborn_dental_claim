import React, { useLayoutEffect, useRef, useState } from "react";
import { S, T, btn, fmt$ } from "../../theme";
/**
 * The agent's recommendation, and the controls that keep a human in front of it.
 *
 * "Edit values" turns the recommendation itself into an editable page: figures,
 * justification and action steps all become text you type straight into, like a
 * text file. Submit re-runs the agents with those changes; Cancel throws them away.
 * Nothing here writes back to the payer — the technician decides.
 */

// ── In-place editing primitives ───────────────────────────────────────────────

/** Looks like text; shows a dashed underline so it reads as editable. */
const flat = {
  font: "inherit", color: "inherit", background: "transparent",
  border: "none", borderBottom: `1.5px dashed ${T.green}`, outline: "none",
  padding: "0 2px", borderRadius: 0, width: "100%",
};

function FlatInput({ value, onChange, bold }) {
  return (
    <input
      type="text" inputMode="decimal" autoComplete="off" spellCheck={false}
      value={value} onChange={e => onChange(e.target.value)}
      onFocus={e => e.target.select()}
      style={{ ...flat, fontWeight: bold ? 800 : 600 }}
    />
  );
}

/** A textarea that grows with its content, so it reads like a document. */
function FlatText({ value, onChange, placeholder }) {
  const ref = useRef(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el) { el.style.height = "auto"; el.style.height = `${el.scrollHeight + 2}px`; }
  }, [value]);
  return (
    <textarea
      ref={ref} value={value} placeholder={placeholder} rows={1} spellCheck
      onChange={e => onChange(e.target.value)}
      style={{
        ...flat, display: "block", resize: "none", overflow: "hidden", lineHeight: "inherit",
        background: T.greenBg, padding: "8px 10px", borderRadius: 7,
        border: `1px dashed ${T.green}`,
      }}
    />
  );
}

const num = v => {
  const n = parseFloat(String(v).replace(/[$,\s]/g, ""));
  return Number.isFinite(n) ? n : null;
};
const show = v => (v === null || v === undefined ? "" : String(v));

export default function Recommendation({ claim, decision, onDecide, onRerun, onSubmitEdits, running }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(null);
  const [formErr, setFormErr] = useState(null);

  if (!decision) return null;

  const gold = claim?.gold_data || {};
  const dm = decision?.display_metrics ?? claim?.display_metrics;
  const approve = decision.decision === "APPROVED";
  const approvedAlready = claim.resolution === "APPROVED";
  const stampColour = approve ? T.green : decision.decision === "DENIED" ? T.red : T.amber;

  // Guidance should arrive as an array, but the model sometimes returns one
  // string with the steps numbered inline ("1. … 2. …"). Split on the numbering
  // as well as on newlines, otherwise every step collapses into one bullet.
  const guidance = decision.human_reviewer_guidance;
  const steps = Array.isArray(guidance)
    ? guidance.map(s => String(s).replace(/^\s*\d+[.)]\s*/, "").trim()).filter(Boolean)
    : typeof guidance === "string" && guidance.trim()
      ? guidance
          .split(/\n+|(?<=[.!?])\s+(?=\d{1,2}[.)]\s)/)
          .map(s => s.replace(/^\s*\d+[.)]\s*/, "").trim())
          .filter(Boolean)
      : [];

  // The values the form starts from, and is compared against on submit.
  const base = {
    primary_paid_amount: show(gold.primary_paid_amount),
    secondary_owes_override: show(decision.approved_amount ?? dm?.secondary_owes),
    billed_amount: show(gold.billed_amount),
    secondary_coinsurance: show(gold.secondary_coinsurance),
    secondary_settlement: gold.secondary_settlement || "",
    monthly_cap: show(gold.monthly_cap),
    term_months: show(gold.term_months),
  };

  // ── editing ────────────────────────────────────────────────────────────────
  function startEdit() {
    setDraft({ ...base, justification: decision.justification || "", steps: steps.join("\n") });
    setFormErr(null);
    setEditing(true);
  }
  const set = (k, v) => setDraft(d => ({ ...d, [k]: v }));

  async function submit() {
    setFormErr(null);
    // Only what the person actually changed is sent.
    const values = {};
    for (const k of Object.keys(base)) {
      if (String(draft[k]).trim() === String(base[k]).trim()) continue;
      if (k === "secondary_settlement") { values[k] = draft[k]; continue; }
      const n = num(draft[k]);
      if (n === null) { setFormErr(`"${draft[k]}" is not a valid number.`); return; }
      values[k] = n;
    }

    // Edited prose goes to the agent as the reviewer's note.
    const parts = [];
    if (draft.justification.trim() !== (decision.justification || "").trim()) {
      parts.push(`Technician's edited justification: ${draft.justification.trim()}`);
    }
    if (draft.steps.trim() !== steps.join("\n").trim()) {
      parts.push(`Technician's edited action steps:\n${draft.steps.trim()}`);
    }
    const note = parts.join("\n\n");

    if (!Object.keys(values).length && !note) {
      setFormErr("Nothing has been changed yet.");
      return;
    }
    try {
      await onSubmitEdits({ values, note });
      setEditing(false);
    } catch (ex) {
      setFormErr(ex.message);
    }
  }

  // ── figures shown in the tiles (live while editing) ────────────────────────
  const billed     = editing ? num(draft.billed_amount) : gold.billed_amount;
  const primPaid   = editing ? num(draft.primary_paid_amount) : gold.primary_paid_amount;
  const secondary  = editing ? num(draft.secondary_owes_override)
    : (decision.approved_amount ?? dm?.secondary_owes ?? null);
  const memberResp = editing
    ? (billed != null && primPaid != null && secondary != null
        ? Math.round((billed - primPaid - secondary) * 100) / 100
        : null)
    : (dm?.member_liability ?? (billed != null && primPaid != null && secondary != null
        ? Math.round((billed - primPaid - secondary) * 100) / 100
        : null));

  const lbl = { fontSize: 10, color: T.mute2 };
  const tile = { background: T.panelR, borderRadius: 7, padding: 10 };

  return (
    <div style={{
      background: T.panel, border: `2px solid ${editing ? T.green : stampColour}`,
      borderRadius: 10, overflow: "hidden", marginTop: 18,
    }}>
      <div style={{
        background: T.greenBg, padding: "14px 18px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        gap: 12, flexWrap: "wrap",
      }}>
        <h3 style={{ color: T.greenText, fontSize: 15, margin: 0 }}>
          🧾 AI recommendation — for human review
          {editing && <span style={{ color: T.amber, marginLeft: 10, fontSize: 12 }}>✎ editing</span>}
        </h3>
        <span style={{
          fontSize: 18, fontWeight: 800, color: approve ? T.greenText : stampColour,
          border: `2px solid ${stampColour}`, padding: "4px 14px", borderRadius: 5,
          display: "inline-block", transform: "rotate(-2deg)",
        }}>
          {approve ? "RECOMMEND: APPROVE" : decision.decision.replace("_", " ")}
        </span>
      </div>

      <div style={{ padding: "16px 18px" }}>
        {editing && (
          <div style={{ fontSize: 11.5, color: T.mute, marginBottom: 12, lineHeight: 1.5 }}>
            Click any dashed value or paragraph and type over it. <b>Submit</b> re-runs the
            agents using your changes; <b>Cancel</b> discards them.
          </div>
        )}

        {gold.cob_flag && gold.primary_payer && (
          <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 6, color: T.white }}>
            {gold.primary_payer} = PRIMARY · HCSC = SECONDARY
          </div>
        )}

        <div style={{ color: T.mute, fontSize: 12.5, lineHeight: 1.6, marginBottom: 14 }}>
          {editing
            ? <FlatText value={draft.justification} onChange={v => set("justification", v)} />
            : decision.justification}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 10, marginBottom: 12 }}>
          <div style={tile}>
            <div style={lbl}>PRIMARY PAID</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: T.mute }}>
              {editing
                ? <FlatInput bold value={draft.primary_paid_amount} onChange={v => set("primary_paid_amount", v)} />
                : fmt$(primPaid)}
            </div>
          </div>
          <div style={tile}>
            <div style={lbl}>SECONDARY OWES</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: T.amber }}>
              {editing
                ? <FlatInput bold value={draft.secondary_owes_override} onChange={v => set("secondary_owes_override", v)} />
                : fmt$(secondary)}
            </div>
          </div>
          <div style={tile}>
            <div style={lbl}>MEMBER LIABILITY</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: T.white }}>
              {memberResp != null ? fmt$(memberResp) : "—"}
            </div>
          </div>
        </div>

        {editing && (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 10, marginBottom: 12 }}>
            {[
              ["BILLED ($)", "billed_amount"],
              ["COINSURANCE (%)", "secondary_coinsurance"],
              ["SETTLEMENT", "secondary_settlement"],
              ["MONTHLY CAP ($)", "monthly_cap"],
              ["TERM (MONTHS)", "term_months"],
            ].map(([label, k]) => (
              <div key={k} style={tile}>
                <div style={lbl}>{label}</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: T.white }}>
                  {k === "secondary_settlement" ? (
                    <select value={draft[k]} onChange={e => set(k, e.target.value)}
                            style={{ ...flat, cursor: "pointer" }}>
                      <option value="">—</option>
                      <option value="LUMP_SUM">LUMP SUM</option>
                      <option value="MONTHLY">MONTHLY</option>
                    </select>
                  ) : (
                    <FlatInput value={draft[k]} onChange={v => set(k, v)} />
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Only an actual escalation gets the amber flag. An approved
            coordination gets credit for having been resolved. */}
        {!editing && decision.decision === "NEEDS_REVIEW" && decision.complex_case_type && (
          <div style={S.flag}>
            ⚑ Escalation reason: {{
              ORTHO_AMBIGUITY: "Orthodontic CDT code does not match the patient's age; the clinical narrative has to be read by a specialist.",
              WIP_ORTHO_COB:   "Treatment began under a prior insurer. The prior plan's payments must be confirmed before a prorated schedule can be built.",
              CROSS_PLAN_COB:  "The coordination could not be settled automatically — see the justification above for the specific blocker.",
            }[decision.complex_case_type] || decision.complex_case_type}
          </div>
        )}

        {!editing && approve && decision.complex_case_type === "CROSS_PLAN_COB" && (
          <div style={{
            background: T.greenBg, border: `1px solid ${T.greenBd}`,
            color: "#05683A", borderRadius: 7, padding: "10px 13px",
            fontSize: 12, marginTop: 10, lineHeight: 1.6,
          }}>
            ✓ Resolved automatically. The payer's AS/400 suspended this claim because it
            has no rule for coordinating two different settlement models. The agent
            established the primary payment, computed the secondary obligation and
            confirmed there is no overpayment — no manual override is required.
          </div>
        )}

        {(steps.length > 0 || editing) && (
          <div style={{
            background: T.azureBg, border: `1px solid ${T.azure}`,
            borderRadius: 7, padding: "12px 15px", marginTop: 12,
          }}>
            <div style={{
              fontSize: 10, fontWeight: 700, color: "#0A5E91",
              letterSpacing: ".5px", marginBottom: 8, textTransform: "uppercase",
            }}>
              {approve ? "Technician confirmation steps" : "Reviewer action items"}
              {editing && " · one step per line"}
            </div>
            {editing ? (
              <div style={{ fontSize: 12.5, color: T.mute, lineHeight: 1.7 }}>
                <FlatText value={draft.steps} onChange={v => set("steps", v)}
                          placeholder="One action step per line" />
              </div>
            ) : (
              <ol style={{ margin: 0, paddingLeft: 18 }}>
                {steps.map((s, i) => (
                  <li key={i} style={{ fontSize: 12.5, color: T.mute, lineHeight: 1.7, marginBottom: 3 }}>{s}</li>
                ))}
              </ol>
            )}
          </div>
        )}

        {/* What human input this run took into account */}
        {!editing && decision.human_inputs && (decision.human_inputs.overrides?.length > 0
          || decision.human_inputs.documents?.length > 0 || decision.human_inputs.note) && (
          <div style={{
            marginTop: 12, padding: "10px 13px", borderRadius: 7, fontSize: 12, lineHeight: 1.65,
            background: T.panelR, border: `1px dashed ${T.green}`, color: T.mute,
          }}>
            <b style={{ color: T.greenText }}>✎ This run included human input</b>
            {decision.human_inputs.overrides?.map(o => (
              <div key={o.field}>
                • {o.label}: {String(o.original ?? "—")} → <b style={{ color: T.white }}>{String(o.edited)}</b>
              </div>
            ))}
            {decision.human_inputs.documents?.length > 0 && (
              <div>• Documents read: {decision.human_inputs.documents.join(", ")}</div>
            )}
            {decision.human_inputs.note && (
              <div style={{ whiteSpace: "pre-wrap" }}>• Note: {decision.human_inputs.note}</div>
            )}
          </div>
        )}

        {claim.resolution && (
          <div style={{
            marginTop: 16, padding: "12px 14px", borderRadius: 8, fontSize: 13, lineHeight: 1.6,
            background: claim.resolution === "APPROVED" ? T.greenBg : T.amberBg,
            border: `1px solid ${claim.resolution === "APPROVED" ? T.green : T.amber}`,
            color: T.white,
          }}>
            {claim.resolution === "APPROVED"
              ? <>✓ <b>Approved by technician.</b> Written back to the AS/400
                  {claim.provenance?.as400_claim_no ? <> — claim <b>{claim.provenance.as400_claim_no}</b></> : null} is
                  now <b style={{ color: T.greenText }}>PAID</b>.</>
              : <>● <b>Held.</b> Information requested from the primary insurer.</>}
          </div>
        )}

        {formErr && <div style={{ color: T.red, fontSize: 12.5, marginTop: 12 }}>⚑ {formErr}</div>}

        {editing ? (
          <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
            <button style={btn.primary} onClick={submit} disabled={running}>
              {running ? "Running…" : "Submit & re-run agents"}
            </button>
            <button style={btn.secondary} onClick={() => setEditing(false)} disabled={running}>
              Cancel
            </button>
          </div>
        ) : (
          <div style={{ display: "flex", gap: 10, marginTop: 16, flexWrap: "wrap" }}>
            {!claim.resolution && (
              <>
                <button style={btn.primary} onClick={() => onDecide("approve")} disabled={!approve}>
                  ✓ Approve &amp; write back to the payer
                </button>
                <button style={btn.hold} onClick={() => onDecide("hold")}>Hold / request info</button>
              </>
            )}
            {!approvedAlready && (
              <>
                <button style={btn.secondary} onClick={startEdit} disabled={running}>Edit values</button>
                <button style={btn.secondary} onClick={onRerun} disabled={running}>
                  {running ? "Running…" : "↻ Run AI adjudication again"}
                </button>
              </>
            )}
          </div>
        )}

        <div style={{ fontSize: 11, color: T.mute2, fontStyle: "italic", marginTop: 8 }}>
          Human-in-the-loop: nothing posts back to the payer until a technician approves.
          Every database row the agent cited is recorded below.
        </div>
      </div>
    </div>
  );
}
