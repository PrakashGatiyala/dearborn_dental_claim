import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Screen, { Blank } from "../components/Screen";
import { api } from "../constants";
import { useAuth } from "../context/AuthContext";
import useFKeys from "../useFKeys";

const OPTIONS = [
  { n: "1", label: "Work with COB claims",            to: "/claims" },
  { n: "2", label: "Work with claims in suspense",    to: "/claims?status=SUSP,RFRD" },
  { n: "3", label: "Display adjudicated claims",      to: "/claims?status=PAID,RVWD" },
  { n: "4", label: "Run batch adjudication",          action: "BATCH" },
  { n: "5", label: "Display claim file statistics",   action: "STATS" },
  { n: "90", label: "Sign off",                        action: "SIGNOFF" },
];

export default function MainMenu() {
  const navigate = useNavigate();
  const { user, signOff } = useAuth();
  const [opt, setOpt] = useState("");
  const [stats, setStats] = useState(null);
  const [msg, setMsg] = useState("");
  const [kind, setKind] = useState("info");

  async function loadStats() {
    try {
      setStats(await api("/stats"));
    } catch (e) {
      setMsg(e.message);
      setKind("error");
    }
  }

  useEffect(() => {
    loadStats();
    const t = setInterval(loadStats, 6000);
    return () => clearInterval(t);
  }, []);

  async function runBatch() {
    setMsg("RUNNING ADJUDICATION BATCH . . .");
    setKind("info");
    try {
      const queued = await api("/claims?status=RCVD");
      if (!queued.length) {
        setMsg("CPF9898 - NO CLAIMS QUEUED FOR ADJUDICATION");
        setKind("info");
        return;
      }
      for (const c of queued) {
        await api(`/claims/${c.claim_no}/adjudicate`, { method: "POST" });
      }
      await loadStats();
      setMsg(`CPC2191 - ${queued.length} CLAIM(S) ADJUDICATED - BATCH COMPLETE`);
      setKind("ok");
    } catch (e) {
      setMsg(e.message);
      setKind("error");
    }
  }

  function enter() {
    const chosen = OPTIONS.find((o) => o.n === opt.trim());
    if (!chosen) {
      setMsg("CPF0001 - OPTION ENTERED IS NOT VALID");
      setKind("error");
      return;
    }
    setOpt("");
    if (chosen.to) return navigate(chosen.to);
    if (chosen.action === "BATCH") return runBatch();
    if (chosen.action === "STATS") {
      loadStats();
      setMsg("CPC0001 - STATISTICS REFRESHED FROM CLAIM FILE");
      setKind("ok");
      return;
    }
    if (chosen.action === "SIGNOFF") {
      signOff();
      navigate("/signon", { replace: true });
    }
  }

  const handlers = useMemo(
    () => ({
      Enter: enter,
      F5: loadStats,
      F3: () => {
        signOff();
        navigate("/signon", { replace: true });
      },
    }),
    [opt]
  );
  useFKeys(handlers);

  const s = stats || {};
  const by = s.by_status || {};

  return (
    <Screen
      screenId="CLMMENU"
      title="DENTAL CLAIMS ADJUDICATION - MAIN MENU"
      message={msg}
      messageKind={kind}
      operator={user}
      fkeys={[
        { key: "F3", label: "Exit", onPress: handlers.F3 },
        { key: "F5", label: "Refresh", onPress: loadStats },
        { key: "F6", label: "Run batch", onPress: runBatch },
      ]}
    >
      <div className="row a-white">Select one of the following:</div>
      <Blank />
      {OPTIONS.map((o) => (
        <div className="row" key={o.n}>
          {`     ${o.n.padStart(2, " ")}. `}
          <span>{o.label}</span>
        </div>
      ))}

      <Blank n={2} />

      <div className="rule">{"─".repeat(80)}</div>
      <div className="row a-white">{"  CLAIM FILE SUMMARY"}</div>
      <div className="row">
        {"    Claims on file . . . . . . . "}
        <span className="a-turq">{String(s.total_claims ?? 0).padStart(6, " ")}</span>
        {"     Batch . . . "}
        <span className="a-turq">{s.batch_no ?? "-"}</span>
      </div>
      <div className="row">
        {"    Auto-adjudicated . . . . . . "}
        <span className="a-turq">{String(s.auto_adjudicated ?? 0).padStart(6, " ")}</span>
        {"     Rate  . . . "}
        <span className="a-turq">{`${s.auto_pct ?? 0}%`}</span>
      </div>
      <div className="row">
        {"    In suspense  . . . . . . . . "}
        <span className={by.SUSP ? "a-red" : "a-dim"}>
          {String(by.SUSP ?? 0).padStart(6, " ")}
        </span>
        {"     Referred  . "}
        <span className="a-amber">{String(by.RFRD ?? 0)}</span>
      </div>
      <div className="row">
        {"    Queued for adjudication  . . "}
        <span className="a-dim">{String(by.RCVD ?? 0).padStart(6, " ")}</span>
      </div>
      <div className="rule">{"─".repeat(80)}</div>

      <Blank />
      <div className="row">
        {"Selection or command"}
      </div>
      <div className="row">
        {"===> "}
        <input
          className="fld fld-60"
          value={opt}
          onChange={(e) => setOpt(e.target.value)}
          autoFocus
        />
      </div>
    </Screen>
  );
}
