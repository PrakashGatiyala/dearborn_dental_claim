import React, { useState } from "react";
import { T } from "../../theme";
import { Card } from "./Ui";

/**
 * "Determining COB Liability (COBD)" — the client's own decision procedure
 * (flowchart revised 07/07/25), shown as the path THIS claim took.
 *
 * The walk itself is computed by the backend (backend/cobd.py) from the claim's
 * relationship, birth-date and decree data, so the page and the AS/400 agree.
 * This component only draws it.
 */

const YES = { text: "YES", colour: T.greenText, bg: T.greenBg };
const NO  = { text: "NO",  colour: T.amber, bg: T.amberBg };

// What the branch NOT taken would have done, straight from the flowchart.
const OFF = {
  1:  { no: "6 · process and allow system denial" },
  2:  { no: "7 · process as primary" },
  3:  { no: "8 · process on processor note" },
  4:  { yes: "5 · route to Security" },
  9:  { yes: "11 · determine Medicare COB liability" },
  12: { no: "Rules 4 and 5" },
  13: { yes: "14 · process as primary (Rule 1)" },
  15: { yes: "16 · process as secondary (Rule 1)" },
  17: { yes: "Rule 6" },
  18: { yes: "Rule 3", no: "Rule 2" },
};

// Every place the flowchart can end → [node key, label, result]
const ENDINGS = [
  ["6",   "Not eligible for DOS",             "System denial"],
  ["7",   "No other coverage",                "Process as primary"],
  ["8",   "No determination needed",          "Per processor note"],
  ["5",   "Restricted group",                 "Security"],
  ["COB", "Medicare / Supplement",            "Secondary"],
  ["4/5", "Same subscriber on both plans",    "Rules 4 & 5"],
  ["14",  "Patient is our subscriber",        "Primary · Rule 1"],
  ["16",  "Patient is other insurer's sub.",  "Secondary · Rule 1"],
  ["R6",  "Spouse on either policy",          "Rule 6"],
  ["R3",  "Separated / divorced parents",     "Rule 3"],
  ["R2",  "Child of married parents",         "Rule 2 · birthday"],
];

const ROLE = {
  SECONDARY:    { colour: T.greenText, bg: T.greenBg, text: "HCSC is SECONDARY",
                  note: "Proceed to COB claim entry and the settlement reconciliation below." },
  PRIMARY:      { colour: T.amber, bg: T.amberBg, text: "HCSC is PRIMARY",
                  note: "The other plan should not have paid first — reprocess as primary and recover its payment." },
  UNDETERMINED: { colour: T.azure, bg: "transparent", text: "NEEDS A TECHNICIAN",
                  note: "The flowchart routes this to a rule that needs a person to apply it." },
};

export default function CobdFlow({ cobd }) {
  const [open, setOpen] = useState(true);
  if (!cobd) return null;

  const { path, terminal, hcsc_role: role, category } = cobd;
  const r = ROLE[role] || ROLE.UNDETERMINED;
  const endKey = terminal.node === "DOC" ? "COB" : String(terminal.node);

  return (
    <Card title="🧭 COB liability determination · client procedure (COBD)">
      <div style={{ fontSize: 11.5, color: T.mute2, lineHeight: 1.6, marginBottom: 10 }}>
        The client's decision tree for which plan pays first, walked against this
        claim's own data. Procedure revised 07/07/25.
      </div>

      {/* verdict */}
      <div style={{
        padding: "10px 12px", borderRadius: 8, marginBottom: 12,
        background: r.bg, border: `1px solid ${r.colour}`, lineHeight: 1.55,
      }}>
        <div style={{ fontSize: 13, fontWeight: 800, color: r.colour }}>
          {r.text} <span style={{ color: T.white, fontWeight: 600 }}>· {category}</span>
        </div>
        <div style={{ fontSize: 12, color: T.white, marginTop: 2 }}>{terminal.detail || r.note}</div>
        <div style={{ fontSize: 11, color: T.mute2, marginTop: 3 }}>
          Ends at: {terminal.label}
          {terminal.rule && terminal.rule !== terminal.label ? ` (${terminal.rule})` : ""}
          {terminal.to && terminal.to !== terminal.label ? ` → ${terminal.to}` : ""}
        </div>
        {terminal.assumed && (
          <div style={{ fontSize: 11, color: T.amber, marginTop: 4 }}>
            ⚑ The client's text for this rule was not supplied — applied as the standard
            industry rule. Confirm against the client's rulebook.
          </div>
        )}
      </div>

      <div onClick={() => setOpen(!open)} style={{
        display: "flex", justifyContent: "space-between", cursor: "pointer",
        fontSize: 11.5, color: T.azure, fontWeight: 700, marginBottom: 8,
      }}>
        <span>Path taken · {path.length} decisions</span>
        <span>{open ? "Hide ▲" : "Show ▼"}</span>
      </div>

      {open && path.map((s, i) => {
        const a = s.a === "yes" ? YES : NO;
        const off = (OFF[s.n] || {})[s.a === "yes" ? "no" : "yes"];
        return (
          <div key={`${s.n}-${i}`} style={{ display: "flex", gap: 12 }}>
            <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
              <div style={{
                width: 26, height: 26, borderRadius: 6, transform: "rotate(45deg) scale(.85)",
                border: `1.5px solid ${a.colour}`, background: a.bg,
                display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
              }}>
                <span style={{ transform: "rotate(-45deg)", fontSize: 11, fontWeight: 700, color: a.colour }}>
                  {s.n}
                </span>
              </div>
              <div style={{ width: 2, flex: 1, minHeight: 14, background: T.border, marginTop: 4 }} />
            </div>
            <div style={{ paddingBottom: 12, flex: 1, minWidth: 0 }}>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <span style={{ fontSize: 12.5, fontWeight: 700, color: T.white }}>{s.q}</span>
                <span style={{
                  fontSize: 10, fontWeight: 800, padding: "1px 8px", borderRadius: 10,
                  color: a.colour, border: `1px solid ${a.colour}`, background: a.bg,
                }}>{a.text}</span>
              </div>
              <div style={{ fontSize: 12, color: T.mute, lineHeight: 1.55, marginTop: 2 }}>{s.ev}</div>
              {off && (
                <div style={{ fontSize: 11, color: T.mute2, marginTop: 2 }}>
                  Other branch ({s.a === "yes" ? "NO" : "YES"}) → {off}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {open && (
        <div style={{ display: "flex", gap: 12 }}>
          <div style={{
            width: 26, height: 26, borderRadius: "50%", background: r.colour, flexShrink: 0,
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "#FFFFFF", fontWeight: 800, fontSize: 13,
          }}>■</div>
          <div style={{ fontSize: 12.5, fontWeight: 700, color: T.white, paddingTop: 3 }}>
            {terminal.label}{terminal.rule && terminal.rule !== terminal.label ? ` · ${terminal.rule}` : ""}
          </div>
        </div>
      )}

      {/* every possible ending, this claim's highlighted */}
      <div style={{
        fontSize: 10.5, fontWeight: 700, color: T.mute2, textTransform: "uppercase",
        letterSpacing: ".5px", margin: "16px 0 6px",
      }}>
        All flowchart endings · this claim highlighted
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6 }}>
        {ENDINGS.map(([key, label, result]) => {
          const on = key === endKey;
          return (
            <div key={key} style={{
              padding: "6px 9px", borderRadius: 6, fontSize: 11, lineHeight: 1.4,
              border: `1px solid ${on ? r.colour : T.border}`,
              background: on ? r.bg : "transparent",
              color: on ? T.white : T.mute2, fontWeight: on ? 700 : 400,
            }}>
              {label}
              <div style={{ color: on ? r.colour : T.mute2, fontSize: 10.5 }}>→ {result}</div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
