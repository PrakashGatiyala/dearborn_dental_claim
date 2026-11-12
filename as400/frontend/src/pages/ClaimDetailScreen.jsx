import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import Screen, { Blank, Rule } from "../components/Screen";
import { STATUS_META, amt, api } from "../constants";
import { useAuth } from "../context/AuthContext";
import useFKeys from "../useFKeys";

function Field({ label, value, cls = "", width = 32 }) {
  return (
    <div className="row">
      {`  ${label.padEnd(width, ".")} : `}
      <span className={cls}>{value ?? "-"}</span>
    </div>
  );
}

export default function ClaimDetailScreen() {
  const { claimNo } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [claim, setClaim] = useState(null);
  const [msg, setMsg] = useState("");
  const [kind, setKind] = useState("info");
  const [view, setView] = useState(params.get("view") === "trace" ? "trace" : "detail");

  const load = useCallback(async () => {
    try {
      setClaim(await api(`/claims/${claimNo}`));
    } catch (e) {
      setMsg(e.message);
      setKind("error");
    }
  }, [claimNo]);

  useEffect(() => {
    load();
  }, [load]);

  async function adjudicateNow() {
    try {
      const r = await api(`/claims/${claimNo}/adjudicate`, { method: "POST" });
      await load();
      setMsg(`CPC2190 - ${claimNo} ${r.message}`);
      setKind(r.status === "SUSP" ? "error" : "ok");
    } catch (e) {
      setMsg(e.message);
      setKind("error");
    }
  }

  async function refer() {
    try {
      const r = await api(`/claims/${claimNo}/refer`, { method: "POST" });
      await load();
      setMsg(`CPC2110 - REFERRED TO ANALYST WORKBENCH AS ${r.dearborn_claim_id}`);
      setKind("ok");
    } catch (e) {
      setMsg(e.message);
      setKind("error");
    }
  }

  async function release() {
    try {
      const body = new FormData();
      body.append("operator", user || "OPER01");
      await api(`/claims/${claimNo}/release`, { method: "POST", body });
      await load();
      setMsg("CPC2120 - CLAIM RELEASED FROM SUSPENSE BY OPERATOR");
      setKind("ok");
    } catch (e) {
      setMsg(e.message);
      setKind("error");
    }
  }

  const handlers = useMemo(
    () => ({
      F3: () => navigate("/menu"),
      F12: () => navigate(-1),
      F5: load,
      F6: adjudicateNow,
      F8: () => setView((v) => (v === "trace" ? "detail" : "trace")),
      F9: refer,
      F10: release,
      F11: () =>
        claim?.status === "SUSP" || claim?.status === "RFRD"
          ? navigate(`/claim/${claimNo}/worksheet`)
          : null,
    }),
    [claim, claimNo]
  );
  useFKeys(handlers);

  if (!claim) {
    return (
      <Screen screenId="CLM220" title="DISPLAY CLAIM" message={msg} messageKind={kind} operator={user}>
        <div className="row a-dim">  RETRIEVING CLAIM FROM FILE . . .</div>
      </Screen>
    );
  }

  const meta = STATUS_META[claim.status] || { cls: "a-green" };
  const suspended = claim.status === "SUSP" || claim.status === "RFRD";

  const fkeys = [
    { key: "F3", label: "Exit", onPress: () => navigate("/menu") },
    { key: "F5", label: "Refresh", onPress: load },
    { key: "F8", label: view === "trace" ? "Claim detail" : "Edit trace", onPress: handlers.F8 },
  ];
  if (claim.status === "RCVD") fkeys.push({ key: "F6", label: "Adjudicate now", onPress: adjudicateNow });
  if (suspended) {
    fkeys.push({ key: "F11", label: "Review worksheet", onPress: handlers.F11 });
    fkeys.push({ key: "F9", label: "Refer to analyst", onPress: refer });
    fkeys.push({ key: "F10", label: "Release", onPress: release });
  }
  fkeys.push({ key: "F12", label: "Cancel", onPress: () => navigate(-1) });

  return (
    <Screen
      screenId={view === "trace" ? "CLM225" : "CLM220"}
      title={view === "trace" ? "DISPLAY ADJUDICATION EDIT TRACE" : "WORK WITH COB CLAIM"}
      subtitle={`CLAIM ${claim.claim_no}   BATCH ${claim.batch_no || "-"}`}
      message={msg || (suspended ? `${claim.suspend_code} - ${claim.reason_text}` : claim.reason_text)}
      messageKind={msg ? kind : suspended ? "error" : "ok"}
      operator={user}
      fkeys={fkeys}
    >
      {view === "detail" ? (
        <>
          <div className="row">
            {"  Claim number . . : "}
            <span className="a-white">{claim.claim_no}</span>
            {"      Status . . : "}
            <span className={meta.rev || meta.cls}>{claim.status}</span>
            {"  "}
            <span className={meta.cls}>{meta.text}</span>
          </div>
          <div className="row">
            {"  Vyne tracking  . : "}
            <span className="a-turq">{claim.vyne_id || "-"}</span>
            {"   Received . : "}
            <span className="a-dim">
              {claim.created_at ? new Date(claim.created_at).toLocaleString() : "-"}
            </span>
          </div>
          <Blank />
          <Rule />
          <div className="row a-white">  MEMBER AND PROVIDER</div>
          <Field label="Patient " value={claim.patient_name} />
          <Field label="Subscriber " value={`${claim.subscriber_name || "-"}  (${claim.subscriber_id || "-"})`} />
          <Field label="Billing provider " value={`${claim.provider_name || "-"}  NPI ${claim.provider_npi || "-"}`} />
          <Field label="Service date " value={claim.procedure_date} />
          <Field label="Procedures " value={(claim.cdt_codes || []).join("  ") || "-"} />

          <Blank />
          <Rule />
          <div className="row a-white">  COORDINATION OF BENEFITS</div>
          <Field label="Primary payer " value={`${claim.primary_payer || "-"}  (${claim.primary_payer_id || "-"})`} cls="a-turq" />
          <Field label="Primary EOB reference " value={claim.primary_eob_ref} cls="a-turq" />
          <Field
            label="Primary settlement mode "
            value={claim.primary_settlement || "-"}
            cls="a-turq"
          />
          <Field
            label="Secondary settlement mode "
            value={
              claim.secondary_settlement === "MONTHLY"
                ? `MONTHLY  CAP ${amt(claim.monthly_cap, 1).trim()} X ${claim.term_months || 0} MO`
                : claim.secondary_settlement || "-"
            }
            cls={claim.secondary_settlement !== claim.primary_settlement ? "a-red" : "a-turq"}
          />
          <Field
            label="Secondary coinsurance "
            value={claim.secondary_coinsurance ? `${claim.secondary_coinsurance}%` : "-"}
            cls="a-turq"
          />

          <Blank />
          <Rule />
          <div className="row a-white">  BENEFIT CALCULATION</div>
          <div className="row">
            {"    Billed charges . . . . . . . . . . "}
            <span className="a-white">{amt(claim.billed_amount)}</span>
          </div>
          <div className="row">
            {"    Less primary payer paid  . . . . .-"}
            <span>{amt(claim.primary_paid)}</span>
          </div>
          <div className="row">
            {"    Remaining balance  . . . . . . . . "}
            <span className="a-turq">{amt(claim.remaining_amount)}</span>
          </div>
          <div className="row">
            {"    Secondary payment authorised . . . "}
            <span className={claim.paid_amount ? "a-turq" : "a-red"}>
              {claim.paid_amount != null ? amt(claim.paid_amount) : "       NONE"}
            </span>
          </div>
          <div className="row">
            {"    Patient responsibility . . . . . . "}
            <span>{claim.patient_resp != null ? amt(claim.patient_resp) : "          -"}</span>
          </div>

          {claim.dearborn_claim_id && (
            <>
              <Blank />
              <Rule />
              <div className="row a-white">  REFERRED TO CLAIMS ANALYST WORKBENCH</div>
              <Field label="Workbench claim id " value={claim.dearborn_claim_id} cls="a-amber" />
              <div className="row">
                {"  Open workbench . . . . . . . . . . : "}
                <a
                  className="scr-link"
                  href={claim.dearborn_portal_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  {claim.dearborn_portal_url}
                </a>
              </div>
            </>
          )}
        </>
      ) : (
        <>
          <div className="row a-white">  ADJUDICATION EDIT SEQUENCE</div>
          <Blank />
          <table className="sfl">
            <thead>
              <tr>
                <th>Seq</th>
                <th>Edit</th>
                <th>Result</th>
                <th className="wrap">Detail</th>
              </tr>
            </thead>
            <tbody>
              {(claim.edit_trace || []).map((t) => (
                <tr key={t.seq}>
                  <td>{t.seq}</td>
                  <td>{t.name}</td>
                  <td>
                    <span className={t.result === "PASS" ? "a-turq" : "rev-red"}>{t.result}</span>
                  </td>
                  <td className={`wrap ${t.result === "PASS" ? "a-dim" : "a-red"}`}>{t.detail}</td>
                </tr>
              ))}
              {!(claim.edit_trace || []).length && (
                <tr>
                  <td colSpan={4} className="a-dim">
                    {"  (CLAIM NOT YET ADJUDICATED - NO EDIT TRACE ON FILE)"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <Blank />
          <div className="row a-dim">
            {"  AN EDIT THAT FAILS STOPS THE SEQUENCE AND SUSPENDS THE CLAIM."}
          </div>
        </>
      )}
    </Screen>
  );
}
