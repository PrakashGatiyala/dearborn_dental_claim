import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LIBRARY, SYSTEM } from "../constants";
import { useAuth } from "../context/AuthContext";

export default function SignOnScreen() {
  const { signOn } = useAuth();
  const navigate = useNavigate();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");

  function submit(e) {
    e.preventDefault();
    const problem = signOn(userId, password);
    if (problem) {
      setErr(problem);
      setPassword("");
    } else {
      navigate("/menu", { replace: true });
    }
  }

  return (
    <div className="crt">
      <div className="screen">
        <div className="hdr">
          <span> </span>
          <span className="hdr-mid a-white">Sign On</span>
          <span> </span>
        </div>
        <div className="hdr">
          <span> </span>
          <span className="hdr-mid a-dim">{`System  . . . . . :   ${SYSTEM}`}</span>
          <span> </span>
        </div>
        <div className="hdr">
          <span> </span>
          <span className="hdr-mid a-dim">{`Subsystem . . . . :   QINTER`}</span>
          <span> </span>
        </div>
        <div className="hdr">
          <span> </span>
          <span className="hdr-mid a-dim">{`Display . . . . . :   DSP01`}</span>
          <span> </span>
        </div>

        <div className="blank" />
        <div className="blank" />

        <form onSubmit={submit}>
          <div className="row">
            {"  User  . . . . . . . . . . . . . .   "}
            <input
              className="fld fld-10"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              autoFocus
              maxLength={10}
            />
          </div>
          <div className="row">
            {"  Password  . . . . . . . . . . . .   "}
            <input
              className="fld fld-10"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              maxLength={10}
            />
          </div>
          <div className="row">
            {"  Program/procedure . . . . . . . .   "}
            <span className="a-dim">CLMMENU</span>
          </div>
          <div className="row">
            {"  Menu  . . . . . . . . . . . . . .   "}
            <span className="a-dim">CLAIMS</span>
          </div>
          <div className="row">
            {"  Current library . . . . . . . . .   "}
            <span className="a-dim">{LIBRARY}</span>
          </div>
          <button type="submit" style={{ display: "none" }} />
        </form>

        <div className="blank" />
        <div className="blank" />

        <div className="msg">{err || " "}</div>

        <div className="blank" />
        <div className="row a-dim">
          {"              HEALTH CARE SERVICE CORPORATION - DENTAL CLAIMS"}
        </div>
        <div className="row a-dim">
          {"                   (C) COPYRIGHT HCSC 1994, 2026."}
        </div>

        <div className="fkeys">
          <span>
            <b>Enter</b>=Sign on
          </span>
          {"   "}
          <span>
            <b>F3</b>=Exit
          </span>
          {"   "}
          <span className="kbd-hint">OPER01 / DEMO123</span>
        </div>
      </div>
    </div>
  );
}
