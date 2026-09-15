"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";

import { api, clearToken, getToken, setToken } from "@/lib/api";
import type { CurrentUser } from "@/lib/types";

interface AuthContextValue {
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api.get<CurrentUser>("/api/auth/me");
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshUser();
  }, [refreshUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      const resp = await api.post<{ access_token: string; role: string; display_name: string }>(
        "/api/auth/login",
        { email, password }
      );
      setToken(resp.access_token);
      await refreshUser();
    },
    [refreshUser]
  );

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }, []);

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

// Roles allowed to create/update incidents & interventions (mirrors backend D24).
export const CAN_WRITE_ROLES = ["admin", "pm", "ops", "engineer"];
export const CAN_CREATE_EXPERIMENTS_ROLES = ["admin", "pm"];
