import React, { useState } from "react";
import { useAuth } from "../../core/context/AuthContext";
import { Activity, ShieldCheck, KeyRound } from "lucide-react";
import { Button } from "../ui/Button";

export const LoginView: React.FC = () => {
  const { login, verifyMfa, isLoading } = useAuth();
  const [email, setEmail] = useState("doctor@avinya-hms.local");
  const [password, setPassword] = useState("DoctorPass123!");
  const [hospitalSlug, setHospitalSlug] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");
    try {
      const res = await login(email, password, hospitalSlug || undefined);
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

  return (
    <div className="min-h-screen w-full flex items-center justify-center bg-slate-950 p-4">
      <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 p-8 shadow-2xl">
        {/* Brand Header */}
        <div className="flex flex-col items-center mb-8">
          <div className="h-12 w-12 rounded-2xl bg-sky-500 flex items-center justify-center text-slate-950 font-black mb-3 shadow-lg shadow-sky-500/20">
            <Activity size={26} />
          </div>
          <h1 className="text-xl font-bold text-slate-100 tracking-tight">Avinya HMS</h1>
          <p className="text-xs text-slate-400 mt-1">Clinical & Hospital Operational Operating System</p>
        </div>

        {errorMessage && (
          <div className="mb-4 p-3 rounded-lg bg-rose-950/80 border border-rose-800 text-rose-300 text-xs">
            {errorMessage}
          </div>
        )}

        {!mfaToken ? (
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
          </form>
        ) : (
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

        <div className="mt-8 pt-6 border-t border-slate-800/80 text-center text-[11px] text-slate-500 flex items-center justify-center gap-1.5 font-mono">
          <ShieldCheck size={13} className="text-emerald-500" />
          <span>FIPS 140-2 Encrypted Session</span>
        </div>
      </div>
    </div>
  );
};

