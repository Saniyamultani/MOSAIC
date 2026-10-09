"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api } from "@/lib/api";

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  profile?: Record<string, { value: any; shared: boolean }>;
}

interface AuthContextType {
  user: UserProfile | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
  updateUserProfile: (updates: Record<string, { value: any; shared: boolean }>) => Promise<void>;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  token: null,
  loading: true,
  login: async () => {},
  signup: async () => {},
  logout: async () => {},
  refreshUser: async () => {},
  updateUserProfile: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const syncStateFromStorage = useCallback(async () => {
    try {
      const savedToken = localStorage.getItem("mosaic_token");
      const savedUser = localStorage.getItem("mosaic_user");
      if (savedToken) {
        setToken(savedToken);
        if (savedUser) {
          try {
            setUser(JSON.parse(savedUser));
          } catch (error) {
            console.error("Unable to read the saved MOSAIC user", error);
            localStorage.removeItem("mosaic_user");
          }
        }
        try {
          const res = await api.me();
          if (res.user) {
            setUser(res.user);
            localStorage.setItem("mosaic_user", JSON.stringify(res.user));
          }
        } catch (error) {
          console.error("Unable to validate the saved MOSAIC session", error);
          localStorage.removeItem("mosaic_token");
          localStorage.removeItem("mosaic_user");
          setToken(null);
          setUser(null);
        }
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    syncStateFromStorage();
  }, [syncStateFromStorage]);

  const login = async (email: string, password: string) => {
    const res = await api.login({ email, password });
    if (res.token && res.user) {
      localStorage.setItem("mosaic_token", res.token);
      localStorage.setItem("mosaic_user", JSON.stringify(res.user));
      setToken(res.token);
      setUser(res.user);
    }
  };

  const signup = async (name: string, email: string, password: string) => {
    const res = await api.signup({ name, email, password });
    if (res.token && res.user) {
      localStorage.setItem("mosaic_token", res.token);
      localStorage.setItem("mosaic_user", JSON.stringify(res.user));
      setToken(res.token);
      setUser(res.user);
    }
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // ignore network errors on logout
    }
    localStorage.removeItem("mosaic_token");
    localStorage.removeItem("mosaic_user");
    setToken(null);
    setUser(null);
  };

  const refreshUser = async () => {
    try {
      const res = await api.me();
      if (res.user) {
        setUser(res.user);
        localStorage.setItem("mosaic_user", JSON.stringify(res.user));
      }
    } catch {
      // ignore
    }
  };

  const updateUserProfile = async (updates: Record<string, { value: any; shared: boolean }>) => {
    const res = await api.updateProfile(updates);
    if (res) {
      const updatedUser = {
        id: res.user_id,
        name: res.name,
        email: res.email,
        profile: res.profile,
      };
      setUser(updatedUser);
      localStorage.setItem("mosaic_user", JSON.stringify(updatedUser));
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        signup,
        logout,
        refreshUser,
        updateUserProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
