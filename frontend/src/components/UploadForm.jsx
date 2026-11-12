import React, { useRef, useState } from "react";
import { API } from "../constants";
import { S, T, btn } from "../theme";

export default function UploadForm({ onClaimReady }) {
  const claimRef = useRef();
  const policyRef = useRef();
  const [claimFile, setClaimFile] = useState(null);
  const [policyFile, setPolicyFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!claimFile || !policyFile) {
      setError("Select both a claim PDF and a supporting PDF.");
      return;
    }
    setLoading(true);
    setError(null);
    const form = new FormData();
    form.append("claim_pdf", claimFile);
    form.append("policy_pdf", policyFile);
    try {
      const res = await fetch(`${API}/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error(`Upload failed: ${res.status} ${res.statusText}`);
      const data = await res.json();
      onClaimReady(data.claim_id);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      <FileInput
        label="Claim PDF"
        hint="ADA claim form with D-code procedures"
        inputRef={claimRef}
        file={claimFile}
        onChange={setClaimFile}
      />
      <FileInput
        label="Supporting PDF"
        hint="Radiograph report, predetermination notice, or EOB"
        inputRef={policyRef}
        file={policyFile}
        onChange={setPolicyFile}
      />
      {error && <div style={S.flag}>⚑ {error}</div>}
      <button
        type="submit"
        disabled={loading}
        style={{ ...btn.primary, opacity: loading ? 0.5 : 1, cursor: loading ? "not-allowed" : "pointer" }}
      >
        {loading ? "Processing…" : "Submit claim"}
      </button>
    </form>
  );
}

function FileInput({ label, hint, inputRef, file, onChange }) {
  return (
    <div>
      <div style={{ fontSize: 12.5, fontWeight: 600, color: T.white, marginBottom: 3 }}>{label}</div>
      <div style={{ fontSize: 11, color: T.mute2, marginBottom: 8 }}>{hint}</div>
      <div
        onClick={() => inputRef.current.click()}
        style={{
          border: `2px dashed ${file ? T.green : T.border}`,
          borderRadius: 7, padding: 18, textAlign: "center", cursor: "pointer",
          fontSize: 12.5, background: file ? T.greenBg : T.panelR, transition: "all .2s",
        }}
      >
        {file
          ? <span style={{ color: T.greenText, fontWeight: 600 }}>📄 {file.name}</span>
          : <span style={{ color: T.mute2 }}>Click to select a PDF</span>}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          style={{ display: "none" }}
          onChange={e => onChange(e.target.files[0] || null)}
        />
      </div>
    </div>
  );
}
