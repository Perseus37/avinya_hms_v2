/**
 * Enterprise API Client for Avinya HMS.
 * Features automatic tenant resolution, bearer auth injection, and transparent session refresh.
 */

export const getTenantSlug = (): string => {
  if (typeof window === "undefined") return "default";
  const host = window.location.hostname.toLowerCase();
  const parts = host.split(".");
  // Handle *.localhost (e.g. apollo.localhost -> apollo)
  if (parts.length >= 2 && parts[parts.length - 1] === "localhost" && parts[0] !== "localhost" && parts[0] !== "www") {
    return parts[0];
  }
  // Handle *.domain.com (e.g. apollo.hms.example.com or apollo.example.com)
  if (parts.length >= 3 && parts[0] !== "www") {
    return parts[0];
  }
  return localStorage.getItem("avinya_tenant_slug") || "default";
};

export const getAuthToken = (): string | null => {
  return localStorage.getItem("avinya_access_token");
};

export const setAuthToken = (token: string): void => {
  localStorage.setItem("avinya_access_token", token);
};

export const clearAuthSession = (): void => {
  localStorage.removeItem("avinya_access_token");
  localStorage.removeItem("avinya_user_profile");
};

export interface RequestOptions extends RequestInit {
  params?: Record<string, string | number | boolean | undefined>;
}

export async function apiClientBlob(endpoint: string, options: RequestOptions = {}): Promise<Blob> {
  const token = getAuthToken();
  const tenantSlug = getTenantSlug();
  const headers: Record<string, string> = {
    "X-Hospital-Subdomain": tenantSlug,
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response = await fetch(endpoint, { ...options, headers });
  if (response.status === 401 && token && !endpoint.includes("/auth/")) {
    try {
      const refreshRes = await fetch("/api/auth/session/refresh", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "X-Hospital-Subdomain": tenantSlug,
        },
      });
      if (refreshRes.ok) {
        const refreshData = await refreshRes.json();
        setAuthToken(refreshData.access_token);
        headers.Authorization = `Bearer ${refreshData.access_token}`;
        response = await fetch(endpoint, { ...options, headers });
      }
    } catch {
      clearAuthSession();
      if (typeof window !== "undefined") window.dispatchEvent(new CustomEvent("avinya:session-expired"));
    }
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || body.message || `HTTP Error ${response.status}`);
  }
  return response.blob();
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const token = getAuthToken();
  const tenantSlug = getTenantSlug();

  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    "X-Hospital-Subdomain": tenantSlug,
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  let url = endpoint;
  if (options.params) {
    const searchParams = new URLSearchParams();
    for (const [key, val] of Object.entries(options.params)) {
      if (val !== undefined && val !== null) {
        searchParams.append(key, String(val));
      }
    }
    const queryString = searchParams.toString();
    if (queryString) {
      url += (url.includes("?") ? "&" : "?") + queryString;
    }
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // Handle 401 Unauthorized by attempting a transparent token refresh
  if (response.status === 401 && token && !endpoint.includes("/auth/")) {
    try {
      const refreshRes = await fetch("/api/auth/session/refresh", {
        method: "POST",
        headers: {
          "Authorization": `Bearer ${token}`,
          "X-Hospital-Subdomain": tenantSlug,
        },
      });

      if (refreshRes.ok) {
        const refreshData = await refreshRes.json();
        setAuthToken(refreshData.access_token);
        // Retry the original request with new token
        headers["Authorization"] = `Bearer ${refreshData.access_token}`;
        const retryRes = await fetch(url, { ...options, headers });
        if (!retryRes.ok) {
          const err = await retryRes.json().catch(() => ({ detail: retryRes.statusText }));
          throw new Error(err.detail || "Request failed after refresh.");
        }
        return retryRes.json() as Promise<T>;
      }
    } catch {
      clearAuthSession();
      window.dispatchEvent(new CustomEvent("avinya:session-expired"));
    }
  }

  if (!response.ok) {
    const errorBody = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(errorBody.message || errorBody.detail || `HTTP Error ${response.status}`);
  }

  return response.json() as Promise<T>;
}

