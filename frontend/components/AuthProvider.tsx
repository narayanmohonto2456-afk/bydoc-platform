"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { Account, ApiError, apiRequest, postJson } from "@/lib/api";

type AuthState = {
  user: Account | null;
  loading: boolean;
  refresh: () => Promise<void>;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Account | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setUser(await apiRequest<Account>("/auth/me/"));
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) {
        setUser(null);
      } else {
        throw error;
      }
    }
  }, []);

  useEffect(() => {
    refresh().catch(() => setUser(null)).finally(() => setLoading(false));
  }, [refresh]);

  async function login(username: string, password: string) {
    const result = await postJson<{ user: Account }>("/auth/login/", { username, password });
    setUser(result.user);
  }

  async function logout() {
    await postJson<void>("/auth/logout/", {});
    setUser(null);
  }

  return <AuthContext.Provider value={{ user, loading, refresh, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
