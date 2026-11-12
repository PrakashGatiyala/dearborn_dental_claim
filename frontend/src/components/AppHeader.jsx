import React from "react";
import { useNavigate } from "react-router-dom";
import { T } from "../theme";
import { useAuth } from "../context/AuthContext";

export default function AppHeader() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <div style={{
      background: T.topbar, borderBottom: "3px solid #005F33",
      padding: "12px 24px", display: "flex", alignItems: "center",
      justifyContent: "space-between", position: "sticky", top: 0, zIndex: 50,
      gap: 14, flexWrap: "wrap",
    }}>
      <div
        onClick={() => navigate("/")}
        style={{ cursor: "pointer", fontWeight: 800, letterSpacing: ".5px", color: "#FFFFFF", fontSize: 15 }}
      >
        MASTECH · APPLIED AI
        <span style={{ color: "#D6F5E4", fontWeight: 400, fontSize: 12, marginLeft: 10 }}>
          Agentic COB Adjudication — Dearborn Group / HCSC
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        {/* <span style={{
          background: T.azure, color: "#042", fontWeight: 700, fontSize: 11,
          padding: "4px 10px", borderRadius: 4,
        }}>
          WORKING PROTOTYPE · SAMPLE DATA
        </span> */}
        <span style={{ fontSize: 12, color: "#FFFFFF", fontWeight: 600 }}>{user}</span>
        <button onClick={handleLogout} style={{
          background: "transparent", border: "1px solid #FFFFFF",
          color: "#FFFFFF", padding: "5px 14px", borderRadius: 6, fontSize: 12,
          fontWeight: 600, cursor: "pointer",
        }}>
          Sign Out
        </button>
      </div>
    </div>
  );
}
