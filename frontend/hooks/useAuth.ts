"use client";

import { useState, useEffect, useCallback } from "react";
import { getApiUrl, fetchWithTimeout } from "@/lib/runtime-config";

export interface User {
  user_id: string;
  email: string;
  name: string;
  role: "customer" | "agent" | "admin";
  team: string | null;
}

interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;
  error: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
}

const TOKEN_KEY = "support_agent_token";
const USER_KEY = "support_agent_user";

export function useAuth(): AuthState {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // On mount, restore session from localStorage
  useEffect(() => {
    const stored_token = localStorage.getItem(TOKEN_KEY);
    const stored_user = localStorage.getItem(USER_KEY);

    if (!stored_token) {
      setLoading(false);
      return;
    }

    // Validate token with backend
    fetchWithTimeout(`${getApiUrl()}/api/auth/me`, {
      headers: { Authorization: `Bearer ${stored_token}` },
    }, 5000)
      .then((res) => res.json())
      .then((data) => {
        setUser(data as User);
        setToken(stored_token);
        localStorage.setItem(USER_KEY, JSON.stringify(data));
      })
      .catch(() => {
        // Token expired or invalid
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    setError(null);
    const res = await fetchWithTimeout(`${getApiUrl()}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    }, 10000);

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Login failed");
    }

    const data = await res.json();
    setToken(data.token);
    setUser(data.user);
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  }, []);

  const register = useCallback(async (email: string, password: string, name: string) => {
    setError(null);
    const res = await fetchWithTimeout(`${getApiUrl()}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, name }),
    }, 10000);

    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || "Registration failed");
    }

    const data = await res.json();
    setToken(data.token);
    setUser(data.user);
    localStorage.setItem(TOKEN_KEY, data.token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  }, []);

  const logout = useCallback(() => {
    setUser(null);
    setToken(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }, []);

  return { user, token, loading, error, login, register, logout };
}

/**
 * Get stored token for use in fetch calls.
 */
export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}
