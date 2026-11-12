import React from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { V } from "../constants";
import { useAuth } from "../context/AuthContext";

const NAV = [
  { label: "Dashboard", path: "/" },
  { label: "Claims",    path: "/claims" },
];

export default function VyneHeader() {
  const navigate  = useNavigate();
  const { pathname } = useLocation();
  const { user, logout } = useAuth();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  return (
    <header style={{
      background: V.tealDark, color: V.white, height: 56,
      display: "flex", alignItems: "center", justifyContent: "space-between",
      padding: "0 28px", position: "sticky", top: 0, zIndex: 200,
      boxShadow: "0 2px 8px rgba(0,0,0,.3)",
    }}>
      {/* Logo */}
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }} onClick={() => navigate("/")}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: V.tealBright, display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 18, fontWeight: 900, color: V.white, letterSpacing: "-1px",
          }}>V</div>
          <div>
            <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: ".5px" }}>NEA</div>
            <div style={{ fontSize: 9, opacity: .7, letterSpacing: "1px", textTransform: "uppercase", marginTop: -2 }}>Dental</div>
          </div>
        </div>

        <div style={{ width: 1, height: 28, background: "rgba(255,255,255,.2)", margin: "0 6px" }} />

        {/* Nav */}
        <nav style={{ display: "flex", gap: 4 }}>
          {NAV.map(({ label, path }) => {
            const active = pathname === path || (path !== "/" && pathname.startsWith(path));
            return (
              <button key={path} onClick={() => navigate(path)} style={{
                background: active ? "rgba(255,255,255,.15)" : "transparent",
                border: "none", color: V.white, padding: "6px 14px", borderRadius: 6,
                fontSize: 13, fontWeight: active ? 600 : 400, cursor: "pointer",
                transition: "background .15s",
              }}>{label}</button>
            );
          })}
        </nav>
      </div>

      {/* Right: user + logout */}
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ fontSize: 12, opacity: .8 }}>{user}</span>
        <button onClick={handleLogout} style={{
          background: "rgba(255,255,255,.15)", border: "1px solid rgba(255,255,255,.3)",
          color: V.white, padding: "5px 14px", borderRadius: 6, fontSize: 12,
          fontWeight: 600, cursor: "pointer",
        }}>
          Sign Out
        </button>
      </div>
    </header>
  );
}
