import React from "react";
import { S, T, pill } from "../../theme";

export function Card({ title, children, accent, style }) {
  return (
    <div style={{ ...S.card, ...(accent ? { border: `2px solid ${accent}` } : null), ...style }}>
      {title && <div style={S.cardHead}>{title}</div>}
      <div style={S.cardBody}>{children}</div>
    </div>
  );
}

/** Two-column key/value grid, as used throughout the prototype's left rail. */
export function KV({ rows }) {
  const entries = Array.isArray(rows) ? rows : Object.entries(rows || {});
  if (!entries.length) {
    return <div style={{ color: T.mute2, fontSize: 12.5 }}>—</div>;
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "5px 12px" }}>
      {entries.map(([k, v], i) => (
        <React.Fragment key={`${k}-${i}`}>
          <div style={S.kvKey}>{k}</div>
          <div style={{ ...S.kvVal, wordBreak: "break-word" }}>
            {v === null || v === undefined || v === "" ? "—" : v}
          </div>
        </React.Fragment>
      ))}
    </div>
  );
}

export function Pill({ kind = "pend", children }) {
  return <span style={pill(kind)}>{children}</span>;
}

/** A document/source row with an icon and a status tick. */
export function DocRow({ icon, name, meta, badge = "ok" }) {
  const mark = badge === "ok" ? "✓" : badge === "warn" ? "⚑" : "…";
  const kind = badge === "ok" ? "ok" : badge === "warn" ? "hold" : "pend";
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "9px 11px",
      background: T.panelR, borderRadius: 7, marginBottom: 8, fontSize: 12.5,
    }}>
      <span style={{ fontSize: 18 }}>{icon}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 600, color: T.white }}>{name}</div>
        <div style={{ color: T.mute2, fontSize: 11 }}>{meta}</div>
      </div>
      <span style={{ ...pill(kind), marginLeft: "auto", fontSize: 9, padding: "2px 7px" }}>{mark}</span>
    </div>
  );
}

export function Confidence({ pct }) {
  const good = pct >= 92;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 8 }}>
      <span style={{ fontSize: 11, color: T.mute2 }}>Confidence</span>
      <div style={{ flex: 1, height: 8, background: T.panelHd, borderRadius: 4, overflow: "hidden" }}>
        <div style={{
          height: "100%", width: `${pct}%`, borderRadius: 4,
          background: good ? T.green : T.amber, transition: "width .6s",
        }} />
      </div>
      <b style={{ color: good ? T.greenText : T.amber }}>{pct}%</b>
    </div>
  );
}

/**
 * Which external system this agent step reached into, e.g.
 * "↔ HCSC AS/400 · suspense queue · CLM0000008". When an href is supplied the
 * badge links straight into that system, so a reviewer can verify the source
 * rather than taking the agent's word for it.
 */
export function Ext({ children, kind, href }) {
  const azure = kind === "vyne";
  const style = {
    display: "inline-flex", alignItems: "center", gap: 6,
    background: azure ? T.azureBg : "#FFF1D6",
    color: azure ? "#0A5E91" : "#7A4B00",
    border: `1px solid ${azure ? T.azure : T.amber}`,
    borderRadius: 6, padding: "4px 10px", fontSize: 11, fontWeight: 700,
    margin: "6px 6px 0 0", textDecoration: "none",
  };

  if (href) {
    return (
      <a href={href} target="_blank" rel="noreferrer" style={style}>
        ↔ {children} ↗
      </a>
    );
  }
  return <span style={style}>↔ {children}</span>;
}

export function Result({ label, children }) {
  return (
    <div style={S.result}>
      <div style={S.resultLabel}>{label}</div>
      <div>{children}</div>
    </div>
  );
}

export function Toast({ message, onDone }) {
  React.useEffect(() => {
    if (!message) return undefined;
    const t = setTimeout(onDone, 3800);
    return () => clearTimeout(t);
  }, [message, onDone]);

  if (!message) return null;
  return (
    <div style={{
      position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)",
      background: T.greenBg, border: `1px solid ${T.green}`, color: T.white,
      padding: "14px 22px", borderRadius: 9, fontSize: 13.5, fontWeight: 600,
      boxShadow: "0 6px 20px rgba(16,35,26,.18)", zIndex: 100, maxWidth: "90vw",
    }}>
      {message}
    </div>
  );
}
