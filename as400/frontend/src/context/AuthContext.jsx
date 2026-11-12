import React, { createContext, useContext, useState } from "react";

/** Mock 5250 sign-on. Matches the other demo apps' credentials. */
// Set VITE_LOGIN_USER / VITE_LOGIN_PASSWORD in Netlify (then redeploy) to change these.
// NOTE: this is a client-side demo gate — the values are bundled into the page.
const CREDS = {
  user: (import.meta.env.VITE_LOGIN_USER || "OPER01").toUpperCase(),
  password: (import.meta.env.VITE_LOGIN_PASSWORD || "DEMO123").toUpperCase(),
};
const KEY = "as400_session";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => localStorage.getItem(KEY));

  function signOn(userId, password) {
    if (
      (userId || "").trim().toUpperCase() === CREDS.user &&
      (password || "").trim().toUpperCase() === CREDS.password
    ) {
      localStorage.setItem(KEY, CREDS.user);
      setUser(CREDS.user);
      return null;
    }
    return "CPF1120 - USER PROFILE OR PASSWORD NOT CORRECT";
  }

  function signOff() {
    localStorage.removeItem(KEY);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, signOn, signOff }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
