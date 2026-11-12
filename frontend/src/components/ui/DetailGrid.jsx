import React from "react";
import { C } from "../../constants";

export default function DetailGrid({ rows }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 14px", fontSize: 11.5 }}>
      {rows.map(([k, v]) => v != null && [
        <div key={k + "k"} style={{ color: C.grey, fontWeight: 600, whiteSpace: "nowrap" }}>{k}:</div>,
        <div key={k + "v"} style={{ color: C.black }}>{v}</div>,
      ])}
    </div>
  );
}
