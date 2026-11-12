import React from "react";
import { T, fmtDate } from "../../theme";
import { Card } from "./Ui";

/**
 * Where this claim came from.
 *
 * A claim reaches this workbench one of two ways: someone uploaded it here, or
 * the payer's AS/400 ran its edit sequence, could not reconcile the COB, and
 * referred it. In the second case the reviewer needs to be able to walk back up
 * the chain — to the claim number the payer knows it by, and to the gateway
 * transmission before that — so each hop links out to the system that holds it.
 */

function Hop({ n, system, tech, lines, href, linkLabel, state }) {
  const colour = state === "fail" ? T.amber : T.greenText;
  return (
    <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
      {/* rail */}
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flexShrink: 0 }}>
        <div style={{
          width: 26, height: 26, borderRadius: "50%",
          background: state === "fail" ? T.amberBg : T.greenBg,
          border: `1.5px solid ${colour}`, color: colour,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontWeight: 700, fontSize: 12,
        }}>{n}</div>
        {state !== "last" && (
          <div style={{ width: 2, flex: 1, minHeight: 26, background: T.border, marginTop: 2 }} />
        )}
      </div>

      <div style={{ paddingBottom: 14, minWidth: 0, flex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: 13, color: T.white }}>{system}</div>
        <div style={{ fontSize: 11, color: T.azure, marginBottom: 5 }}>{tech}</div>
        {lines.map((l, i) => (
          <div key={i} style={{ fontSize: 12, color: T.mute, lineHeight: 1.65 }}>{l}</div>
        ))}
        {href && (
          <a href={href} target="_blank" rel="noreferrer" style={{
            display: "inline-block", marginTop: 6, fontSize: 11.5, fontWeight: 700,
            color: T.azure, textDecoration: "none",
            border: `1px solid ${T.azure}`, borderRadius: 6, padding: "3px 9px",
          }}>
            {linkLabel} ↗
          </a>
        )}
      </div>
    </div>
  );
}

export default function ReferralChain({ provenance }) {
  const p = provenance || {};
  const referred = p.source === "AS400_REFERRAL";

  // No source recorded at all — the claim predates referral tracking. Say that
  // plainly rather than claiming it was uploaded here.
  if (!p.source) {
    return (
      <Card title="🗂 How this claim arrived">
        <div style={{ fontSize: 12.5, color: T.mute, lineHeight: 1.6 }}>
          No origin recorded for this claim. It was processed before referral
          tracking was added, so the chain back through the gateway and the
          payer's adjudicator is not available.
        </div>
        <div style={{ fontSize: 11.5, color: T.mute2, lineHeight: 1.6, marginTop: 8 }}>
          Claims received from now on carry their full chain. Re-send this one
          to see it.
        </div>
      </Card>
    );
  }

  if (!referred) {
    return (
      <Card title="🗂 How this claim arrived">
        <div style={{ fontSize: 12.5, color: T.mute, lineHeight: 1.6 }}>
          Submitted directly to this workbench. It did not pass through the
          clearinghouse or the payer's adjudication system, so there is no
          upstream chain to trace.
        </div>
      </Card>
    );
  }

  return (
    <Card title="🗂 Referral chain">
      <div style={{
        fontSize: 11.5, color: T.mute2, marginBottom: 12, lineHeight: 1.6,
        paddingBottom: 10, borderBottom: `1px solid ${T.border}`,
      }}>
        This claim was not uploaded here. The payer's adjudicator stopped on an
        edit it has no rule for and handed it over.
      </div>

      <Hop
        n={1}
        system="Vyne Dental Gateway"
        tech="Clearinghouse · EDI 837D transmission"
        lines={[
          <>Tracking <b style={{ color: T.white }}>{p.vyne_tracking_id || "—"}</b></>,
          "Envelope validated and forwarded. No adjudication here.",
        ]}
        href={p.vyne_portal_url}
        linkLabel="Open in Vyne"
      />

      <Hop
        n={2}
        system="HCSC AS/400"
        tech="Legacy adjudication · batch edit sequence"
        state="fail"
        lines={[
          <>Claim <b style={{ color: T.white }}>{p.as400_claim_no || "—"}</b>
            {p.as400_batch_no ? <span style={{ color: T.mute2 }}> · batch {p.as400_batch_no}</span> : null}</>,
          <>Suspended on <b style={{ color: T.amber }}>{p.suspend_code || "—"}</b></>,
          <span style={{ color: T.mute2 }}>{p.suspend_reason || ""}</span>,
        ]}
        href={p.as400_screen_url}
        linkLabel="Open in AS400"
      />

      <Hop
        n={3}
        system="Agent Workbench"
        tech="Azure OpenAI · agentic COB adjudication"
        state="last"
        lines={[
          <>Received {p.referred_at ? fmtDate(p.referred_at) : "—"}</>,
          "Agents reason over the COB and build a recommendation for a human.",
        ]}
      />
    </Card>
  );
}
