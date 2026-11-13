import React from "react";
import { T, fmt$ } from "../../theme";
import { Card } from "./Ui";

/**
 * The arithmetic behind a COB recommendation, as rules, with this claim's own
 * numbers plugged in. Mirrors the rules the agent is instructed to follow.
 */

const mono = { fontFamily: "Consolas, 'Courier New', monospace" };

function Rule({ n, title, formula, live, ok }) {
  return (
    <div style={{ display: "flex", gap: 12, padding: "10px 0", borderBottom: `1px solid ${T.border}` }}>
      <div style={{
        width: 24, height: 24, borderRadius: "50%", flexShrink: 0,
        border: `1.5px solid ${T.green}`, color: T.greenText, fontSize: 12, fontWeight: 700,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>{n}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 12.5, fontWeight: 700, color: T.white }}>{title}</div>
        <div style={{ ...mono, fontSize: 11.5, color: T.azure, margin: "3px 0" }}>{formula}</div>
        {live && (
          <div style={{ ...mono, fontSize: 12, color: ok === false ? T.amber : T.white }}>
            {live}{ok === true ? "  ✓" : ok === false ? "  ⚑" : ""}
          </div>
        )}
      </div>
    </div>
  );
}

export default function CobRules({ gold, displayMetrics }) {
  const g = gold || {};
  const billed = Number(g.billed_amount);
  const paid = Number(g.primary_paid_amount);
  const allowed = Number(g.primary_allowed_amount);
  const coins = Number(g.secondary_coinsurance);
  const have = [billed, paid, allowed, coins].every(Number.isFinite);

  const remaining = have ? Math.round((allowed - paid) * 100) / 100 : null;
  const obligation = displayMetrics?.secondary_owes != null
    ? Number(displayMetrics.secondary_owes)
    : (have ? Math.round(remaining * (coins / 100) * 100) / 100 : null);
  const total = have ? paid + obligation : null;

  const monthly = g.secondary_settlement === "MONTHLY" && Number(g.monthly_cap) > 0;
  const cap = Number(g.monthly_cap);
  const term = Number(g.term_months);
  const monthsNeeded = have && monthly ? Math.ceil(obligation / cap) : null;

  return (
    <Card title="🧮 How the numbers are calculated · COB rules">
      <div style={{ fontSize: 11.5, color: T.mute2, lineHeight: 1.6, marginBottom: 6 }}>
        Every recommendation follows these four rules in order. The lines in
        white are this claim's own figures.
      </div>

      <Rule
        n={1}
        title="Remaining balance after the primary plan"
        formula="remaining = primary_allowed − primary_paid"
        live={have ? `${fmt$(allowed)} − ${fmt$(paid)} = ${fmt$(remaining)}` : "Awaiting figures on claim"}
      />
      <Rule
        n={2}
        title="Secondary plan's share"
        formula="obligation = remaining × coinsurance %"
        live={have ? `${fmt$(remaining)} × ${coins}% = ${fmt$(obligation)}` : null}
      />
      <Rule
        n={3}
        title="No overpayment"
        formula="primary_paid + obligation ≤ billed   (and obligation ≤ annual max)"
        live={have ? `${fmt$(paid)} + ${fmt$(obligation)} = ${fmt$(total)}  vs billed ${fmt$(billed)}` : null}
        ok={have ? total <= billed : undefined}
      />
      <Rule
        n={4}
        title="Settlement schedule"
        formula={monthly
          ? "months_needed = ceil(obligation ÷ monthly_cap)   must be ≤ term"
          : "Lump sum: obligation is paid once — no schedule to check"}
        live={monthly && have
          ? `ceil(${fmt$(obligation)} ÷ ${fmt$(cap)}) = ${monthsNeeded} months  vs term ${term} months`
          : null}
        ok={monthly && have ? monthsNeeded <= term : undefined}
      />

      <div style={{ fontSize: 11.5, color: T.mute2, lineHeight: 1.6, marginTop: 10 }}>
        <b style={{ color: T.white }}>Decision:</b> all four pass and the primary EOB is
        on file → <span style={{ color: T.greenText }}>approve</span>. Any rule fails or the EOB
        is missing → <span style={{ color: T.amber }}>escalate to a technician</span> with the
        failing rule named.
      </div>
    </Card>
  );
}
