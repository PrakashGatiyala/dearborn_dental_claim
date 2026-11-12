import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { S, T, btn } from "../theme";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    setTimeout(() => {
      if (login(username, password)) {
        navigate("/", { replace: true });
      } else {
        setError("Invalid username or password.");
        setLoading(false);
      }
    }, 400);
  }

  const field = {
    width: "100%", padding: "11px 13px", borderRadius: 7,
    border: `1px solid ${T.border}`, background: T.panelR,
    color: T.white, fontSize: 13, outline: "none",
    fontFamily: "inherit", marginTop: 5,
  };

  return (
    <div style={{ minHeight: "100vh", display: "flex", flexDirection: "column" }}>
      <div style={{
        background: T.topbar, borderBottom: "3px solid #005F33",
        padding: "12px 24px", display: "flex", alignItems: "center",
        justifyContent: "space-between", gap: 14, flexWrap: "wrap",
      }}>
        <div style={{ fontWeight: 800, letterSpacing: ".5px", color: "#FFFFFF", fontSize: 15 }}>
          MASTECH · APPLIED AI
          <span style={{ color: "#D6F5E4", fontWeight: 400, fontSize: 12, marginLeft: 10 }}>
            Agentic COB Adjudication — Dearborn Group / HCSC
          </span>
        </div>
        <span style={{
          background: "#FFFFFF", color: "#008A4B", fontWeight: 700, fontSize: 11,
          padding: "4px 10px", borderRadius: 4,
        }}>
          WORKING PROTOTYPE · SAMPLE DATA
        </span>
      </div>

      <div style={{
        flex: 1, display: "flex", alignItems: "center",
        justifyContent: "center", padding: 24,
      }}>
        <div style={{ width: "100%", maxWidth: 400 }}>
          <div style={{ ...S.card, marginBottom: 0 }}>
            <div style={S.cardHead}>🔐 Sign in to the workbench</div>
            <div style={{ padding: "20px 22px" }}>
              <div style={{ fontSize: 12.5, color: T.mute, lineHeight: 1.6, marginBottom: 18 }}>
                Claims technicians review the agents' coordination-of-benefits
                recommendations here before anything is written back to the payer.
              </div>

              <form onSubmit={handleSubmit}>
                <label style={{ display: "block", marginBottom: 14 }}>
                  <span style={{ fontSize: 11, color: T.mute2, fontWeight: 700, letterSpacing: ".5px", textTransform: "uppercase" }}>
                    Username
                  </span>
                  <input
                    style={field}
                    value={username}
                    onChange={e => setUsername(e.target.value)}
                    autoFocus
                  />
                </label>
                <label style={{ display: "block", marginBottom: 16 }}>
                  <span style={{ fontSize: 11, color: T.mute2, fontWeight: 700, letterSpacing: ".5px", textTransform: "uppercase" }}>
                    Password
                  </span>
                  <input
                    style={field}
                    type="password"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                  />
                </label>

                {error && <div style={{ ...S.flag, marginTop: 0, marginBottom: 14 }}>⚑ {error}</div>}

                <button
                  type="submit"
                  disabled={loading}
                  style={{ ...btn.primary, width: "100%", opacity: loading ? 0.5 : 1 }}
                >
                  {loading ? "Signing in…" : "Sign in"}
                </button>
              </form>
            </div>
          </div>
          <div style={{ textAlign: "center", marginTop: 14, fontSize: 11.5, color: T.mute2 }}>
            Demo credentials: <b style={{ color: T.mute }}>admin / demo123</b>
          </div>
        </div>
      </div>
    </div>
  );
}
