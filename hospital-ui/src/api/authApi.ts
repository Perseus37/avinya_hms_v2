import { apiClient, setAuthToken, clearAuthSession } from "./client";
import { UserProfile } from "../types";

export interface LoginResponse {
  access_token?: string;
  token_type?: string;
  mfa_required?: boolean;
  mfa_setup_required?: boolean;
  mfa_token?: string;
}

export const authApi = {
  login: async (email: string, password: string, hospitalSlug?: string): Promise<LoginResponse> => {
    const res = await apiClient<LoginResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password, hospital_slug: hospitalSlug }),
    });
    if (res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },

  verifyMfaLogin: async (mfaToken: string, code: string): Promise<{ access_token: string }> => {
    const res = await apiClient<{ access_token: string }>("/api/auth/mfa/verify-login", {
      method: "POST",
      body: JSON.stringify({ mfa_token: mfaToken, code }),
    });
    if (res.access_token) {
      setAuthToken(res.access_token);
    }
    return res;
  },

  getMe: async (): Promise<UserProfile> => {
    return apiClient<UserProfile>("/api/auth/me");
  },

  logout: async (): Promise<void> => {
    try {
      await apiClient("/api/auth/logout", { method: "POST" });
    } finally {
      clearAuthSession();
    }
  },

  getPreferences: async () => {
    return apiClient<{
      default_workspace?: string;
      theme?: string;
      default_ward_id?: number;
      default_department_id?: number;
    }>("/api/auth/me/preferences");
  },

  updatePreferences: async (prefs: Record<string, unknown>) => {
    return apiClient("/api/auth/me/preferences", {
      method: "PATCH",
      body: JSON.stringify(prefs),
    });
  },
};

