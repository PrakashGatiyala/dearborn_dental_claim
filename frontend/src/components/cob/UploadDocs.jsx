import React, { useRef, useState } from "react";
import { T, btn } from "../../theme";
import { Card } from "./Ui";

/**
 * Extra evidence a technician attaches to a claim — a court decree, a corrected
 * EOB, a clinical note. Uploaded files are stored with the claim and read by the
 * agent the next time it runs ("Run AI adjudication again" in the recommendation).
 */
export default function UploadDocs({ documents = [], onUpload, onDelete, locked }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);

  const pending = documents.filter(d => !d.considered).length;

  async function pick(e) {
    const files = Array.from(e.target.files || []);
    e.target.value = "";
    if (!files.length) return;
    setBusy(true);
    setErr(null);
    try {
      await onUpload(files);
    } catch (ex) {
      setErr(ex.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="📎 Upload documents">
      <div style={{ fontSize: 11.5, color: T.mute2, lineHeight: 1.6, marginBottom: 10 }}>
        Add evidence the agent should weigh — PDF, text, CSV or EDI files are read;
        other files are stored but not read.
      </div>

      <input ref={input} type="file" multiple onChange={pick} style={{ display: "none" }}
             accept=".pdf,.txt,.md,.csv,.json,.edi,.xml,.png,.jpg,.jpeg,.docx" />
      <button
        style={{ ...btn.secondary, padding: "8px 16px", fontSize: 13, width: "100%" }}
        onClick={() => input.current?.click()}
        disabled={busy || locked}
      >
        {busy ? "Uploading…" : "＋ Choose files to upload"}
      </button>

      {err && <div style={{ color: T.red, fontSize: 12, marginTop: 8 }}>⚑ {err}</div>}

      {documents.map(d => (
        <div key={d.name} style={{
          display: "flex", alignItems: "center", gap: 8, marginTop: 8,
          padding: "8px 10px", background: T.panelR, borderRadius: 7, fontSize: 12.5,
        }}>
          <span>📄</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ color: T.white, fontWeight: 600, overflow: "hidden",
                          textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name}</div>
            <div style={{ color: T.mute2, fontSize: 11 }}>
              {(d.size / 1024).toFixed(1)} KB ·{" "}
              {d.extracted ? "text read" : "not readable by the agent"} ·{" "}
              <span style={{ color: d.considered ? T.greenText : T.amber, fontWeight: 700 }}>
                {d.considered ? "used in last run" : "not yet used"}
              </span>
            </div>
          </div>
          {!locked && (
            <button onClick={() => onDelete(d.name)} title="Remove" style={{
              background: "transparent", border: "none", color: T.mute2,
              cursor: "pointer", fontSize: 15,
            }}>✕</button>
          )}
        </div>
      ))}

      {pending > 0 && (
        <div style={{
          marginTop: 10, fontSize: 12, lineHeight: 1.55, padding: "8px 10px",
          background: T.amberBg, border: `1px solid ${T.amber}`, borderRadius: 7, color: "#6B3F00",
        }}>
          {pending} new document{pending === 1 ? "" : "s"} not yet considered. Click{" "}
          <b>Run AI adjudication again</b> in the recommendation so the agent reads
          {pending === 1 ? " it" : " them"}.
        </div>
      )}
    </Card>
  );
}
