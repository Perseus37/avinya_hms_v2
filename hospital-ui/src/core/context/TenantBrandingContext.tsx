import React, { createContext, useContext, useEffect, useState } from "react";
import { uiApi, TenantBranding } from "../../api/uiApi";

interface TenantBrandingContextValue {
  branding: TenantBranding | null;
  isLoading: boolean;
  error: string | null;
}

const TenantBrandingContext = createContext<TenantBrandingContextValue>({
  branding: null,
  isLoading: true,
  error: null,
});

export const TenantBrandingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [branding, setBranding] = useState<TenantBranding | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    uiApi.getTenantBranding()
      .then((config) => {
        if (!active) return;
        setBranding(config);
        document.title = config.display_name || config.hospital_name || "Healthcare";
        document.documentElement.style.setProperty("--tenant-primary", config.primary_color);
        document.documentElement.style.setProperty("--tenant-secondary", config.secondary_color);
        document.documentElement.style.setProperty("--tenant-accent", config.accent_color);
        if (config.favicon_url) {
          let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
          if (!link) {
            link = document.createElement("link");
            link.rel = "icon";
            document.head.appendChild(link);
          }
          link.href = config.favicon_url;
        }
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Tenant branding could not be loaded.");
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => { active = false; };
  }, []);

  return (
    <TenantBrandingContext.Provider value={{ branding, isLoading, error }}>
      {children}
    </TenantBrandingContext.Provider>
  );
};

export const useTenantBranding = (): TenantBrandingContextValue => useContext(TenantBrandingContext);
