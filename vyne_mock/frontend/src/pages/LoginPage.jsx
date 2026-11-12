import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { V } from "../constants";
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
      const ok = login(username, password);
      if (ok) {
        navigate("/", { replace: true });
      } else {
        setError("Invalid username or password.");
        setLoading(false);
      }
    }, 400);
  }

  return (
    <div style={{
      minHeight: "100vh", background: V.bg,
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
    }}>
      {/* Header bar */}
      <div style={{
        position: "fixed", top: 0, left: 0, right: 0,
        background: V.tealDark, color: V.white,
        height: 56, display: "flex", alignItems: "center",
        padding: "0 28px", gap: 14,
        boxShadow: "0 2px 8px rgba(0,0,0,.3)",
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: V.tealBright, display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18, fontWeight: 900, color: V.white,
        }}>V</div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: ".5px" }}>vyne</div>
          <div style={{ fontSize: 9, opacity: .7, letterSpacing: "1px", textTransform: "uppercase", marginTop: -2 }}>Dental</div>
        </div>
      </div>

      {/* Card */}
      <div style={{
        background: V.white, borderRadius: 12, padding: "40px 44px",
        boxShadow: "0 4px 24px rgba(0,0,0,.10)", width: "100%", maxWidth: 400,
        border: `1px solid ${V.border}`,
      }}>
        {/* Icon */}
        <div style={{
          width: 52, height: 52, borderRadius: 12,
          background: V.tealDark,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 22, fontWeight: 900, color: V.white,
          margin: "0 auto 20px",
        }}>V</div>

        <h2 style={{ margin: "0 0 4px", fontSize: 20, fontWeight: 700, color: V.black, textAlign: "center" }}>
          Sign in
        </h2>
        <p style={{ margin: "0 0 28px", fontSize: 13, color: V.grey, textAlign: "center" }}>
          NEA Provider Portal
        </p>

        <form onSubmit={handleSubmit}>
          <label style={{ fontSize: 12, fontWeight: 600, color: V.black, display: "block", marginBottom: 6 }}>
            Username
          </label>
          <input
            type="text"
            value={username}
            onChange={e => setUsername(e.target.value)}
            placeholder="Enter username"
            required
            style={{
              width: "100%", padding: "10px 12px", borderRadius: 7,
              border: `1.5px solid ${V.border}`, fontSize: 14, outline: "none",
              boxSizing: "border-box", marginBottom: 16, color: V.black,
              background: V.white,
            }}
          />

          <label style={{ fontSize: 12, fontWeight: 600, color: V.black, display: "block", marginBottom: 6 }}>
            Password
          </label>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Enter password"
            required
            style={{
              width: "100%", padding: "10px 12px", borderRadius: 7,
              border: `1.5px solid ${V.border}`, fontSize: 14, outline: "none",
              boxSizing: "border-box", marginBottom: 20, color: V.black,
              background: V.white,
            }}
          />

          {error && (
            <div style={{
              background: V.redBg, color: V.red, border: `1px solid #FECACA`,
              borderRadius: 7, padding: "9px 12px", fontSize: 13, marginBottom: 16,
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%", padding: "11px", borderRadius: 7, border: "none",
              background: loading ? V.midGrey : V.tealDark,
              color: V.white, fontSize: 14, fontWeight: 600, cursor: loading ? "not-allowed" : "pointer",
              transition: "opacity .15s",
            }}
          >
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <div style={{
          marginTop: 24, padding: "12px 14px", borderRadius: 7,
          background: V.lightGrey, border: `1px solid ${V.border}`,
          fontSize: 12, color: V.grey, textAlign: "center",
        }}>
          Demo credentials: <strong style={{ color: V.black }}>admin</strong> / <strong style={{ color: V.black }}>demo123</strong>
        </div>
      </div>
    </div>
  );
}
