import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ClaimDetailScreen from "./pages/ClaimDetailScreen";
import ClaimListScreen from "./pages/ClaimListScreen";
import MainMenu from "./pages/MainMenu";
import SignOnScreen from "./pages/SignOnScreen";
import WorksheetScreen from "./pages/WorksheetScreen";

function Protected({ children }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/signon" replace />;
}

function Shell() {
  return (
    <Routes>
      <Route path="/signon" element={<SignOnScreen />} />
      <Route path="/menu" element={<Protected><MainMenu /></Protected>} />
      <Route path="/claims" element={<Protected><ClaimListScreen /></Protected>} />
      <Route path="/claim/:claimNo" element={<Protected><ClaimDetailScreen /></Protected>} />
      <Route
        path="/claim/:claimNo/worksheet"
        element={<Protected><WorksheetScreen /></Protected>}
      />
      <Route path="*" element={<Navigate to="/menu" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  );
}
