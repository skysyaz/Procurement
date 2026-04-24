import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = loading, false = not logged in, object = logged in
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const r = await api.get("/auth/me");
      setUser(r.data);
    } catch {
      setUser(false);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const login = async (email, password) => {
    const r = await api.post("/auth/login", { email, password });
    // Access token is delivered via httpOnly cookie; we only keep the user payload in memory.
    setUser(r.data.user);
    return r.data.user;
  };

  const register = async (email, password, name) => {
    const r = await api.post("/auth/register", { email, password, name });
    setUser(r.data.user);
    return r.data.user;
  };

  const logout = async () => {
    try {
      await api.post("/auth/logout");
    } catch (err) {
      // Non-fatal: still clear local state even if the server couldn't be reached.
      console.warn("Logout request failed:", err?.message || err);
    }
    setUser(false);
  };

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);

export const ROLE_RANK = { viewer: 0, user: 1, manager: 2, admin: 3 };
export const can = (user, min) =>
  user && ROLE_RANK[user.role] !== undefined && ROLE_RANK[user.role] >= ROLE_RANK[min];
