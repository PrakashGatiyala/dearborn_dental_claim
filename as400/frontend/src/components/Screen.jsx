import React, { useEffect, useState } from "react";
import { LIBRARY, SYSTEM, julianBatch, sysClock } from "../constants";

/** Horizontal rule drawn with box characters, full 80 columns. */
export function Rule({ char = "─" }) {
  return <div className="rule">{char.repeat(80)}</div>;
}

export function Blank({ n = 1 }) {
  return Array.from({ length: n }, (_, i) => <div className="blank" key={i} />);
}

/**
 * The standard display-file frame: two header rows, a rule, the body, then
 * the message line, function-key legend and operator status strip.
 */
export default function Screen({
  screenId,
  title,
  subtitle,
  message,
  messageKind = "error",
  fkeys = [],
  operator = "OPER01",
  children,
}) {
  const [clock, setClock] = useState(() => sysClock());

  useEffect(() => {
    const t = setInterval(() => setClock(sysClock()), 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="crt">
      <div className="screen">
        <div className="hdr">
          <span>{screenId}</span>
          <span className="hdr-mid">{title}</span>
          <span>{SYSTEM}</span>
        </div>
        <div className="hdr">
          <span className="a-dim">{LIBRARY}</span>
          <span className="hdr-mid a-dim">{subtitle ?? `BATCH ${julianBatch()}`}</span>
          <span className="a-dim">{clock}</span>
        </div>
        <Rule />
        <Blank />

        {children}

        <Blank />
        <div className={`msg ${messageKind}`}>{message || " "}</div>

        {fkeys.length > 0 && (
          <div className="fkeys">
            {fkeys.map((k, i) => (
              <React.Fragment key={k.key}>
                {i > 0 && "   "}
                {k.onPress ? (
                  <button type="button" onClick={k.onPress}>
                    <b>{k.key}</b>={k.label}
                  </button>
                ) : (
                  <span>
                    <b>{k.key}</b>={k.label}
                  </span>
                )}
              </React.Fragment>
            ))}
          </div>
        )}

        <div className="opstat">
          <span>MW</span>
          <span>{`${operator} / ${SYSTEM}`}</span>
          <span>07/012</span>
        </div>
      </div>
    </div>
  );
}
