import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { API, V, STATUS_META, fmt$, fmtDate } from "../constants";
import StatusBadge from "../components/StatusBadge";

export default function ClaimsPage() {
  const [claims,    setClaims]    = useState([]);
  const [filter,    setFilter]    = useState("ALL");
  const [search,    setSearch]    = useState("");
  const navigate = useNavigate();

  const load = () => {
    const qs = filter !== "ALL" ? `?status=${filter}` : "";
    fetch(`${API}/claims${qs}`).then(r => r.json()).then(setClaims).catch(() => {});
  };

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, [filter]);

  const visible = claims.filter(c => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      c.tracking_id?.toLowerCase().includes(q) ||
      c.subscriber_name?.toLowerCase().includes(q) ||
      c.payer_name?.toLowerCase().includes(q) ||
      (c.cdt_codes || []).some(code => code.toLowerCase().includes(q))
    );
  });

  return (
    <div style={{ padding: 28, maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 20 }}>
        <div>
          <div style={{ fontSize: 20, fontWeight: 700, color: V.navy }}>Claims</div>
          <div style={{ fontSize: 13, color: V.grey, marginTop: 3 }}>{visible.length} claim{visible.length !== 1 ? "s" : ""} found</div>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by ID, subscriber, payer, CDT..."
            style={{
              border: `1px solid ${V.border}`, borderRadius: 6, padding: "8px 12px",
              fontSize: 13, width: 280, outline: "none", color: V.black,
            }}
          />
        </div>
      </div>

      {/* Status filter tabs */}
      <div style={{ display: "flex", gap: 6, marginBottom: 18, flexWrap: "wrap" }}>
        {["ALL", ...Object.keys(STATUS_META)].map(key => (
          <button key={key} onClick={() => setFilter(key)} style={{
            padding: "5px 14px", borderRadius: 20, fontSize: 12, fontWeight: 600,
            cursor: "pointer", border: "1.5px solid",
            borderColor: filter === key ? V.teal : V.border,
            background: filter === key ? V.tealLight : V.white,
            color: filter === key ? V.tealDark : V.grey,
          }}>
            {key === "ALL" ? "All" : STATUS_META[key].label}
          </button>
        ))}
      </div>

      {/* Table */}
      <div style={{ background: V.white, border: `1px solid ${V.border}`, borderRadius: 10, overflow: "hidden" }}>
        {visible.length === 0 ? (
          <div style={{ padding: "60px 20px", textAlign: "center", color: V.grey, fontSize: 13 }}>
            No claims match your filter. Run <code style={{ background: V.lightGrey, padding: "2px 6px", borderRadius: 4 }}>vyne_sender.py</code> to submit claims.
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ background: V.lightGrey }}>
                {["Tracking ID","Patient","Primary Payer","CDT Codes","Date of Service","Billed","Payer Claim","Status","Submitted"].map(h => (
                  <th key={h} style={{ padding: "10px 14px", textAlign: "left", fontSize: 11, fontWeight: 700, color: V.grey, textTransform: "uppercase", letterSpacing: ".5px", whiteSpace: "nowrap" }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visible.map((c, i) => (
                <tr key={c.tracking_id}
                  onClick={() => navigate(`/claims/${c.tracking_id}`)}
                  style={{ borderTop: `1px solid ${V.border}`, cursor: "pointer", background: i % 2 === 0 ? V.white : "#FAFBFC" }}
                >
                  <td style={{ padding: "11px 14px", fontWeight: 700, color: V.teal, fontFamily: "monospace", whiteSpace: "nowrap" }}>{c.tracking_id}</td>
                  <td style={{ padding: "11px 14px", color: V.black, whiteSpace: "nowrap" }}>{c.patient_name || c.subscriber_name || "—"}</td>
                  <td style={{ padding: "11px 14px", color: V.grey, whiteSpace: "nowrap" }}>{c.primary_payer || "—"}</td>
                  <td style={{ padding: "11px 14px" }}>
                    {(c.cdt_codes || []).map(code => (
                      <span key={code} style={{ background: V.tealLight, color: V.tealDark, fontSize: 10, fontWeight: 700, padding: "2px 6px", borderRadius: 4, marginRight: 3, whiteSpace: "nowrap", display: "inline-block" }}>{code}</span>
                    ))}
                  </td>
                  <td style={{ padding: "11px 14px", color: V.grey, whiteSpace: "nowrap" }}>{c.procedure_date || "—"}</td>
                  <td style={{ padding: "11px 14px", fontWeight: 600, whiteSpace: "nowrap" }}>{fmt$(c.billed_amount)}</td>
                  <td style={{ padding: "11px 14px", fontFamily: "monospace", fontSize: 12, color: c.as400_claim_no ? V.navy : V.midGrey, whiteSpace: "nowrap" }}>{c.as400_claim_no || "—"}</td>
                  <td style={{ padding: "11px 14px" }}><StatusBadge status={c.status} /></td>
                  <td style={{ padding: "11px 14px", color: V.grey, fontSize: 11, whiteSpace: "nowrap" }}>{fmtDate(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
