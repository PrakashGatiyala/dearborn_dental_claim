import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { V } from "./constants";
import { AuthProvider, useAuth } from "./context/AuthContext";
import VyneHeader from "./components/VyneHeader";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import ClaimsPage from "./pages/ClaimsPage";
import ClaimDetailPage from "./pages/ClaimDetailPage";

function ProtectedRoute({ children }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/login" replace />;
}

function AppShell() {
  const { user } = useAuth();
  return (
    <div style={{ fontFamily: "'Segoe UI', system-ui, sans-serif", background: V.bg, color: V.black, minHeight: "100vh" }}>
      {user && <VyneHeader />}
      <main>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
          <Route path="/claims" element={<ProtectedRoute><ClaimsPage /></ProtectedRoute>} />
          <Route path="/claims/:trackingId" element={<ProtectedRoute><ClaimDetailPage /></ProtectedRoute>} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
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
