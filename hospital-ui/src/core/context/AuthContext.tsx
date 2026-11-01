import React, { createContext, useContext, useEffect, useState } from "react";
import { UserProfile } from "../../types";
import { authApi } from "../../api/authApi";
import { getAuthToken, clearAuthSession } from "../../api/client";

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, pass: string, slug?: string) => Promise<{ mfaRequired?: boolean; mfaToken?: string }>;
  verifyMfa: (mfaToken: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchCurrentUser = async () => {
    const token = getAuthToken();
    if (!token) {
      setUser(null);
      setIsLoading(false);
      return;
    }
    try {
      const profile = await authApi.getMe();
      setUser(profile);
    } catch {
      clearAuthSession();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCurrentUser();

    const handleExpired = () => {
      setUser(null);
    };
    window.addEventListener("avinya:session-expired", handleExpired);
    return () => window.removeEventListener("avinya:session-expired", handleExpired);
  }, []);

  const login = async (email: string, pass: string, slug?: string) => {
    setIsLoading(true);
    try {
      const res = await authApi.login(email, pass, slug);
      if (res.mfa_required || res.mfa_setup_required) {
        setIsLoading(false);
        return { mfaRequired: true, mfaToken: res.mfa_token };
      }
      await fetchCurrentUser();
      return {};
    } finally {
      setIsLoading(false);
    }
  };

  const verifyMfa = async (mfaToken: string, code: string) => {
    setIsLoading(true);
    try {
      await authApi.verifyMfaLogin(mfaToken, code);
      await fetchCurrentUser();
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      await authApi.logout();
    } finally {
      setUser(null);
      setIsLoading(false);
    }
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        verifyMfa,
        logout,
        reloadUser: fetchCurrentUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

