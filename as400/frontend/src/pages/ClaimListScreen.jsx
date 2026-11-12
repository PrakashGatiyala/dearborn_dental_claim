import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import Screen, { Blank } from "../components/Screen";
import { STATUS_META, amt, api, pad } from "../constants";
import { useAuth } from "../context/AuthContext";
import useFKeys from "../useFKeys";

const PAGE = 12;

export default function ClaimListScreen() {
  const navigate = useNavigate();
  const { user, signOff } = useAuth();
  const [params, setParams] = useSearchParams();

  const statusFilter = params.get("status") || "";
  const [claims, setClaims] = useState([]);
  const [opts, setOpts] = useState({});          // claim_no → option digit
  const [positionTo, setPositionTo] = useState("");
  const [filterInput, setFilterInput] = useState(statusFilter || "ALL");
  const [page, setPage] = useState(0);
  const [msg, setMsg] = useState("");
  const [kind, setKind] = useState("info");

  const load = useCallback(async () => {
    try {
      const qs = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : "";
      setClaims(await api(`/claims${qs}`));
    } catch (e) {
      setMsg(e.message);
      setKind("error");
    }
  }, [statusFilter]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const visible = useMemo(() => {
    let rows = claims;
    if (positionTo.trim()) {
      const needle = positionTo.trim().toUpperCase();
      const idx = rows.findIndex(
        (c) =>
          c.claim_no.includes(needle) ||
          (c.patient_name || "").toUpperCase().includes(needle)
      );
      if (idx > 0) rows = rows.slice(idx);
    }
    return rows;
  }, [claims, positionTo]);

  const pageRows = visible.slice(page * PAGE, page * PAGE + PAGE);
  const more = visible.length > (page + 1) * PAGE;

  function applyOptions() {
    const entries = Object.entries(opts).filter(([, v]) => v && v.trim());
    if (!entries.length) {
      setMsg("CPF0002 - NO OPTION ENTERED");
      setKind("error");
      return;
    }
    const [claimNo, raw] = entries[0];
    const opt = raw.trim();
    setOpts({});
    if (opt === "2" || opt === "5") return navigate(`/claim/${claimNo}`);
    if (opt === "8") return navigate(`/claim/${claimNo}?view=trace`);
    if (opt === "9") return refer(claimNo);
    setMsg(`CPF0001 - OPTION ${opt} IS NOT VALID`);
    setKind("error");
  }

  async function refer(claimNo) {
    try {
      const r = await api(`/claims/${claimNo}/refer`, { method: "POST" });
      await load();
      setMsg(`CPC2110 - ${claimNo} REFERRED TO ANALYST WORKBENCH AS ${r.dearborn_claim_id}`);
      setKind("ok");
    } catch (e) {
      setMsg(e.message);
      setKind("error");
    }
  }

  async function referAllSuspense() {
    const suspended = claims.filter((c) => c.status === "SUSP");
    if (!suspended.length) {
      setMsg("CPF9898 - NO CLAIMS IN SUSPENSE");
      setKind("info");
      return;
    }
    let ok = 0;
    for (const c of suspended) {
      try {
        await api(`/claims/${c.claim_no}/refer`, { method: "POST" });
        ok += 1;
      } catch {
        /* reported in aggregate below */
      }
    }
    await load();
    setMsg(`CPC2111 - ${ok} OF ${suspended.length} CLAIM(S) REFERRED TO ANALYST WORKBENCH`);
    setKind(ok === suspended.length ? "ok" : "error");
  }

  function applyFilter(e) {
    e?.preventDefault();
    const v = filterInput.trim().toUpperCase();
    if (!v || v === "ALL") setParams({});
    else setParams({ status: v });
    setPage(0);
  }

  const handlers = useMemo(
    () => ({
      Enter: applyOptions,
      F5: load,
      F3: () => navigate("/menu"),
      F12: () => navigate("/menu"),
      F9: referAllSuspense,
      PageDown: () => more && setPage((p) => p + 1),
      PageUp: () => page > 0 && setPage((p) => p - 1),
    }),
    [opts, claims, more, page]
  );
  useFKeys(handlers);

  const suspenseCount = claims.filter((c) => c.status === "SUSP").length;

  return (
    <Screen
      screenId="CLM210"
      title="WORK WITH COB CLAIMS"
      message={
        msg ||
        (suspenseCount
          ? `CPF9897 - ${suspenseCount} CLAIM(S) IN SUSPENSE REQUIRE MANUAL COB RECONCILIATION`
          : "")
      }
      messageKind={msg ? kind : suspenseCount ? "error" : "info"}
      operator={user}
      fkeys={[
        { key: "F3", label: "Exit", onPress: () => navigate("/menu") },
        { key: "F5", label: "Refresh", onPress: load },
        { key: "F9", label: "Refer all suspense", onPress: referAllSuspense },
        { key: "F12", label: "Cancel", onPress: () => navigate("/menu") },
      ]}
    >
      <form onSubmit={applyFilter}>
        <div className="row">
          {"Position to claim . . . "}
          <input
            className="fld fld-10"
            value={positionTo}
            onChange={(e) => setPositionTo(e.target.value)}
          />
          {"   Status . . . "}
          <input
            className="fld fld-8"
            value={filterInput}
            onChange={(e) => setFilterInput(e.target.value)}
            onBlur={applyFilter}
          />
          <span className="a-dim">{"  (ALL, RCVD, PAID, SUSP, RFRD)"}</span>
        </div>
        <button type="submit" style={{ display: "none" }} />
      </form>

      <Blank />
      <div className="row a-white">Type option, press Enter.</div>
      <div className="row a-dim">
        {"  2=Work with claim   5=Display   8=Display edit trace   9=Refer to analyst"}
      </div>
      <Blank />

      <table className="sfl">
        <thead>
          <tr>
            <th>Opt</th>
            <th>Claim No</th>
            <th>Patient</th>
            <th>Primary Payer</th>
            <th style={{ textAlign: "right" }}>Billed</th>
            <th style={{ textAlign: "right" }}>Prim Paid</th>
            <th>St</th>
            <th>Rsn</th>
          </tr>
        </thead>
        <tbody>
          {pageRows.map((c) => {
            const meta = STATUS_META[c.status] || { cls: "a-green" };
            return (
              <tr key={c.claim_no} onClick={() => navigate(`/claim/${c.claim_no}`)}>
                <td onClick={(e) => e.stopPropagation()}>
                  <input
                    className="fld fld-2"
                    value={opts[c.claim_no] || ""}
                    onChange={(e) =>
                      setOpts((o) => ({ ...o, [c.claim_no]: e.target.value }))
                    }
                    maxLength={1}
                  />
                </td>
                <td>{c.claim_no}</td>
                <td>{pad(c.patient_name, 17)}</td>
                <td>{pad(c.primary_payer, 16)}</td>
                <td style={{ textAlign: "right" }}>{amt(c.billed_amount, 10)}</td>
                <td style={{ textAlign: "right" }}>{amt(c.primary_paid, 10)}</td>
                <td>
                  <span className={meta.rev ? meta.rev : meta.cls}>{c.status}</span>
                </td>
                <td>
                  <span className={c.suspend_code ? "a-red" : "a-dim"}>
                    {c.suspend_code || c.reason_code || "-"}
                  </span>
                </td>
              </tr>
            );
          })}
          {!pageRows.length && (
            <tr>
              <td colSpan={8} className="a-dim">
                {"  (NO CLAIMS ON FILE MATCHING SELECTION)"}
              </td>
            </tr>
          )}
        </tbody>
      </table>

      <Blank />
      <div className="row a-dim">
        {`${" ".repeat(62)}${more ? "More..." : "Bottom "}`}
      </div>
    </Screen>
  );
}
