import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "./api";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null); // null = loading, false = not logged in, object = logged in
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    // Retry transient failures (Render free-tier cold-starts can take 30-60 s,
    // backend OOM-restarts during heavy OCR also produce a 10-30 s blackout).
    // Only treat HTTP 401 as "definitely logged out".  Network errors / 5xx
    // are retried so the user isn't bounced to /login mid-restart.
    const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
    const attempts = [0, 1500, 4000, 8000]; // total ~13.5 s before giving up
    for (let i = 0; i < attempts.length; i++) {
      if (attempts[i]) await sleep(attempts[i]);
      try {
        const r = await api.get("/auth/me", { timeout: 8000 });
        setUser(r.data);
        setReady(true);
        return;
      } catch (err) {
        const status = err?.response?.status;
        if (status === 401 || status === 403) {
          setUser(false);
          setReady(true);
          return;
        }
        // network error / 5xx — retry
        if (i === attempts.length - 1) {
          // Out of retries: keep current value (null = still loading) so we don't
          // wrongly redirect to /login.  Mark ready so the UI can render an error.
          setUser((prev) => (prev === null ? false : prev));
          setReady(true);
          return;
        }
      }
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
