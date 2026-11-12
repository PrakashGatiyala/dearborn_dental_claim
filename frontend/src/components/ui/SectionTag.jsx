import React from "react";
import { C } from "../../constants";

export default function SectionTag({ text }) {
  return (
    <div style={{ display: "inline-block", background: C.blue, color: C.white, fontSize: 10, fontWeight: 700, letterSpacing: ".8px", padding: "3px 10px", borderRadius: 3, textTransform: "uppercase", marginBottom: 10 }}>
      {text}
    </div>
  );
}
