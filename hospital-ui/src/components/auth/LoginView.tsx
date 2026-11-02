import React, { useState } from "react";
import { useAuth } from "../../core/context/AuthContext";
import { getTenantSlug } from "../../api/client";
import { authApi } from "../../api/authApi";\nimport { useTenantBranding } from "../../core/context/TenantBrandingContext";
import { Activity, ShieldCheck, KeyRound, Unlock, Key, ArrowLeft, CheckCircle2 } from "lucide-react";
import { Button } from "../ui/Button";

type AuthMode = "login" | "unlock" | "forgot_password";

export const LoginView: React.FC = () => {
  const { login, verifyMfa, isLoading } = useAuth();
  const { branding } = useTenantBranding();\n  const { branding } = useTenantBranding();
  const detectedSlug = getTenantSlug();
  const [authMode, setAuthMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [hospitalSlug, setHospitalSlug] = useState(detectedSlug !== "default" ? detectedSlug : "");
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [actionLoading, setActionLoading] = useState(false);

  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");
    try {
      const effectiveSlug = (hospitalSlug || detectedSlug || "").trim() || undefined;
      const res = await login(email, password, effectiveSlug);
      if (res.mfaRequired && res.mfaToken) {
        setMfaToken(res.mfaToken);
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Login failed. Verify credentials.");
      }
    }
  };

  const handleMfaSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");
    if (!mfaToken) return;
    try {
      await verifyMfa(mfaToken, mfaCode);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Invalid MFA verification code.");
      }
    }
  };

  const handleUnlockSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");
    setActionLoading(true);
    try {
      const res = await authApi.requestUnlock(email);
      setSuccessMessage(res.message || "Unlock instructions dispatched. Please check your registered email.");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Failed to submit unlock request. Contact hospital administrator.");
      }
    } finally {
      setActionLoading(false);
    }
  };

  const handleForgotSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");
    setSuccessMessage("");
    setActionLoading(true);
    try {
      const res = await authApi.requestPasswordReset(email);
      setSuccessMessage(res.message || "Password reset instructions dispatched. Please check your registered email.");
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Failed to submit password reset request.");
      }
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-slate-950 p-4">
      <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 p-8 shadow-2xl">
        {/* Brand Header */}
        <div className="flex flex-col items-center mb-8">
          {branding?.logo_url ? (
            <img src={branding.logo_url} alt="" className="h-12 w-12 rounded-2xl object-contain mb-3" />
          ) : (
            <div className="h-12 w-12 rounded-2xl bg-[var(--tenant-primary,#0ea5e9)] flex items-center justify-center text-white font-black mb-3 shadow-lg"><Activity size={26} /></div>
          )}
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">{branding?.display_name || branding?.hospital_name || "Healthcare"}</h1>
          <p className="text-xs text-slate-400 mt-1">{branding?.tagline || "Clinical and hospital operations"}</p>
        </div>

        {errorMessage && (
          <div className="mb-4 p-3 rounded-lg bg-rose-950/80 border border-rose-800 text-rose-300 text-xs">
            {errorMessage}
          </div>
        )}

        {successMessage && (
          <div className="mb-4 p-3 rounded-lg bg-emerald-950/80 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-400 shrink-0" />
            <span>{successMessage}</span>
          </div>
        )}

        {authMode === "login" && !mfaToken && (
          <form onSubmit={handleLoginSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@hospital.org"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-100 focus:outline-none focus:border-sky-500 font-mono"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-100 focus:outline-none focus:border-sky-500 font-mono"
                required
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1">Hospital Node / Subdomain (Optional)</label>
              <input
                type="text"
                value={hospitalSlug}
                onChange={(e) => setHospitalSlug(e.target.value)}
                placeholder="Leave blank for host subdomain"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-300 focus:outline-none focus:border-sky-500 font-mono"
              />
            </div>

            <Button type="submit" variant="primary" isLoading={isLoading} className="w-full mt-2">
              Sign In to Workspace
            </Button>

            <div className="flex items-center justify-between pt-2 text-xs text-slate-400">
              <button
                type="button"
                onClick={() => {
                  setAuthMode("unlock");
                  setErrorMessage("");
                  setSuccessMessage("");
                }}
                className="hover:text-sky-400 transition-colors flex items-center gap-1"
              >
                <Unlock size={13} />
                <span>Account Locked?</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setAuthMode("forgot_password");
                  setErrorMessage("");
                  setSuccessMessage("");
                }}
                className="hover:text-sky-400 transition-colors flex items-center gap-1"
              >
                <Key size={13} />
                <span>Forgot Password?</span>
              </button>
            </div>
          </form>
        )}

        {authMode === "login" && mfaToken && (
          <form onSubmit={handleMfaSubmit} className="space-y-4">
            <div className="p-3 rounded-lg bg-sky-950/40 border border-sky-800/60 text-xs text-sky-300 flex items-center gap-2">
              <KeyRound size={16} className="text-sky-400" />
              <span>Multi-Factor Authentication Required (TOTP)</span>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">6-Digit Authenticator Code</label>
              <input
                type="text"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                placeholder="000000"
                maxLength={8}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-center text-lg tracking-widest text-slate-100 focus:outline-none focus:border-sky-500 font-mono"
                required
                autoFocus
              />
            </div>

            <Button type="submit" variant="primary" isLoading={isLoading} className="w-full">
              Verify Code & Continue
            </Button>
          </form>
        )}

        {authMode === "unlock" && (
          <form onSubmit={handleUnlockSubmit} className="space-y-4">
            <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-800/60 text-xs text-amber-300 flex items-center gap-2">
              <Unlock size={16} className="text-amber-400" />
              <span>Self-Service Account Unlock (F-05)</span>
            </div>

            <p className="text-xs text-slate-400">
              Enter your registered clinical staff email address. If the account is locked due to repeated invalid attempts, an instant one-click unlock link will be sent.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@hospital.org"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-100 focus:outline-none focus:border-sky-500 font-mono"
                required
                autoFocus
              />
            </div>

            <Button type="submit" variant="primary" isLoading={actionLoading} className="w-full">
              Send Instant Unlock Link
            </Button>

            <button
              type="button"
              onClick={() => {
                setAuthMode("login");
                setErrorMessage("");
                setSuccessMessage("");
              }}
              className="w-full text-center text-xs text-slate-400 hover:text-slate-200 transition-colors flex items-center justify-center gap-1.5 pt-2"
            >
              <ArrowLeft size={13} />
              <span>Back to Login</span>
            </button>
          </form>
        )}

        {authMode === "forgot_password" && (
          <form onSubmit={handleForgotSubmit} className="space-y-4">
            <div className="p-3 rounded-lg bg-sky-950/40 border border-sky-800/60 text-xs text-sky-300 flex items-center gap-2">
              <Key size={16} className="text-sky-400" />
              <span>Password Recovery</span>
            </div>

            <p className="text-xs text-slate-400">
              Enter your registered clinical staff email address to receive secure, single-use password reset instructions.
            </p>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Email Address</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@hospital.org"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-100 focus:outline-none focus:border-sky-500 font-mono"
                required
                autoFocus
              />
            </div>

            <Button type="submit" variant="primary" isLoading={actionLoading} className="w-full">
              Send Password Reset Link
            </Button>

            <button
              type="button"
              onClick={() => {
                setAuthMode("login");
                setErrorMessage("");
                setSuccessMessage("");
              }}
              className="w-full text-center text-xs text-slate-400 hover:text-slate-200 transition-colors flex items-center justify-center gap-1.5 pt-2"
            >
              <ArrowLeft size={13} />
              <span>Back to Login</span>
            </button>
          </form>
        )}

        <div className="mt-8 pt-6 border-t border-slate-800/80 text-center text-[11px] text-slate-500 flex items-center justify-center gap-1.5 font-mono">
          <ShieldCheck size={13} className="text-emerald-500" />
          <span>FIPS 140-2 Encrypted Session</span>
        </div>
      </div>
    </div>
  );
};

