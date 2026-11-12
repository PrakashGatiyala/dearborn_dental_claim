import React, { createContext, useContext, useState } from "react";

// Set VITE_LOGIN_USER / VITE_LOGIN_PASSWORD in Netlify (then redeploy) to change these.
// NOTE: this is a client-side demo gate — the values are bundled into the page.
const CREDS = {
  username: import.meta.env.VITE_LOGIN_USER || "admin",
  password: import.meta.env.VITE_LOGIN_PASSWORD || "demo123",
};
const KEY = "vyne_auth";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => localStorage.getItem(KEY));

  function login(username, password) {
    if (username === CREDS.username && password === CREDS.password) {
      localStorage.setItem(KEY, username);
      setUser(username);
      return true;
    }
    return false;
  }

  function logout() {
    localStorage.removeItem(KEY);
    setUser(null);
  }

  return (
    <AuthContext.Provider value={{ user, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
