import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { T } from "./theme";
import { AuthProvider, useAuth } from "./context/AuthContext";
import AppHeader from "./components/AppHeader";
import LoginPage from "./pages/LoginPage";
import HomePage from "./pages/HomePage";
import ClaimPage from "./pages/ClaimPage";

function ProtectedRoute({ children }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/login" replace />;
}

function AppShell() {
  const { user } = useAuth();
  return (
    <div style={{
      fontFamily: "'Segoe UI', Arial, sans-serif",
      background: T.bgGrad, backgroundAttachment: "fixed",
      color: T.white, minHeight: "100vh", fontSize: 14,
    }}>
      {user && <AppHeader />}
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<ProtectedRoute><HomePage /></ProtectedRoute>} />
        <Route path="/claim/:claimId" element={<ProtectedRoute><ClaimPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  );
}
