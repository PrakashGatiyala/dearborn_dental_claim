import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import Screen, { Blank, Rule } from "../components/Screen";
import { api } from "../constants";
import { useAuth } from "../context/AuthContext";
import useFKeys from "../useFKeys";

/**
 * CLM230 — the manual COB reconciliation worksheet.
 *
 * This is the screen the client's reviewer works from today: the box states
 * what it could not do, prints the arithmetic, and lists the steps a human
 * must carry out by hand. It is the exact workload the analyst workbench is
 * being introduced to absorb.
 */
export default function WorksheetScreen() {
  const { claimNo } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [sheet, setSheet] = useState(null);
  const [claim, setClaim] = useState(null);
  const [msg, setMsg] = useState("");
  const [kind, setKind] = useState("error");

  const load = useCallback(async () => {
    try {
      const [w, c] = await Promise.all([
        api(`/claims/${claimNo}/worksheet`),
        api(`/claims/${claimNo}`),
      ]);
      setSheet(w);
      setClaim(c);
    } catch (e) {
      setMsg(e.message);
      setKind("error");
    }
  }, [claimNo]);

  useEffect(() => {
    load();
  }, [load]);

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

  const handlers = useMemo(
    () => ({
      F3: () => navigate("/menu"),
      F12: () => navigate(`/claim/${claimNo}`),
      F5: load,
      F9: refer,
    }),
    [claimNo]
  );
  useFKeys(handlers);

  if (!sheet) {
    return (
      <Screen screenId="CLM230" title="COB RECONCILIATION WORKSHEET" message={msg} messageKind={kind} operator={user}>
        <div className="row a-dim">  RETRIEVING WORKSHEET . . .</div>
      </Screen>
    );
  }

  return (
    <Screen
      screenId="CLM230"
      title="COB RECONCILIATION WORKSHEET"
      subtitle={`CLAIM ${claimNo}   SUSPEND ${sheet.suspend_code}`}
      message={msg || `${sheet.suspend_code} - ${sheet.suspend_text}`}
      messageKind={msg ? kind : "error"}
      operator={user}
      fkeys={[
        { key: "F3", label: "Exit", onPress: () => navigate("/menu") },
        { key: "F5", label: "Refresh", onPress: load },
        { key: "F9", label: "Refer to analyst", onPress: refer },
        { key: "F12", label: "Cancel", onPress: () => navigate(`/claim/${claimNo}`) },
      ]}
    >
      <div className="row a-white">  WHY ADJUDICATION STOPPED</div>
      <div className="row-wrap a-red" style={{ paddingLeft: "2ch" }}>
        {sheet.why_the_box_failed}
      </div>

      <Blank />
      <Rule />
      <div className="row a-white">  BENEFIT ARITHMETIC</div>
      {sheet.arithmetic.map((line, i) => (
        <div className="row" key={i}>
          {"    "}
          <span className={line.includes("<-") ? "a-turq" : line.startsWith("Shortfall") ? "a-red" : ""}>
            {line}
          </span>
        </div>
      ))}
      <div className="row">
        {"    Overpayment check . . . . . . . "}
        <span className={sheet.overpayment_safe ? "a-turq" : "rev-red"}>
          {sheet.overpayment_safe ? "WITHIN BILLED CHARGES - SAFE" : "EXCEEDS BILLED - DO NOT PAY"}
        </span>
      </div>

      <Blank />
      <Rule />
      <div className="row a-white">  OPERATOR ACTION REQUIRED</div>
      {sheet.reviewer_steps.map((step, i) => (
        <div className="row-wrap" key={i} style={{ paddingLeft: "2ch" }}>
          <span className="a-amber">{`${String(i + 1).padStart(2, "0")}. `}</span>
          {step}
        </div>
      ))}

      <Blank />
      <Rule />
      {claim?.dearborn_claim_id ? (
        <>
          <div className="row a-white">  REFERRED TO CLAIMS ANALYST WORKBENCH</div>
          <div className="row">
            {"    Workbench claim id . . . . . . "}
            <span className="a-amber">{claim.dearborn_claim_id}</span>
          </div>
          <div className="row">
            {"    Open . . . . . . . . . . . . . "}
            <a className="scr-link" href={claim.dearborn_portal_url} target="_blank" rel="noreferrer">
              {claim.dearborn_portal_url}
            </a>
          </div>
        </>
      ) : (
        <div className="row a-dim">
          {"  NOT YET REFERRED - PRESS F9 TO SEND TO THE CLAIMS ANALYST WORKBENCH"}
        </div>
      )}
    </Screen>
  );
}
