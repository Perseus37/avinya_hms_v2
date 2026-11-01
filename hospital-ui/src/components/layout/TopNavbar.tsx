import React from "react";
import { Search, LogOut, Activity, User } from "lucide-react";
import { useAuth } from "../../core/context/AuthContext";

interface TopNavbarProps {
  onOpenCommandPalette: () => void;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({ onOpenCommandPalette }) => {
  const { user, logout } = useAuth();

  return (
    <header className="h-14 bg-slate-950 border-b border-slate-800 px-4 flex items-center justify-between select-none">
      {/* Brand & Subdomain */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="h-7 w-7 rounded-lg bg-sky-500 flex items-center justify-center text-slate-950 font-black text-xs shadow-md shadow-sky-500/20">
            <Activity size={16} />
          </div>
          <span className="font-bold text-sm tracking-wide text-slate-100">
            AVINYA <span className="text-sky-400 font-mono font-medium">HMS</span>
          </span>
        </div>
        <span className="text-slate-600">|</span>
        <span className="text-xs font-mono text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
          Hospital Node: <span className="text-slate-200 font-semibold">{localStorage.getItem("avinya_tenant_slug") || "General Base"}</span>
        </span>
      </div>

      {/* Global Command Search (Cmd+K) */}
      <div className="flex-1 max-w-md mx-6">
        <button
          onClick={onOpenCommandPalette}
          className="w-full flex items-center justify-between px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs text-slate-400 hover:border-slate-700 hover:text-slate-200 transition-colors shadow-inner"
        >
          <div className="flex items-center gap-2">
            <Search size={14} className="text-slate-500" />
            <span>Search patient by MRN, name, phone...</span>
          </div>
          <kbd className="px-1.5 py-0.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono">
            Cmd+K
          </kbd>
        </button>
      </div>

      {/* User Session & Logout */}
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2.5 text-xs">
          <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
            <User size={14} />
          </div>
          <div className="text-left">
            <div className="font-semibold text-slate-200 leading-tight">{user?.full_name || "Staff Member"}</div>
            <div className="text-[10px] text-slate-400 leading-tight font-mono">{user?.email}</div>
          </div>
        </div>

        <button
          onClick={logout}
          title="Sign Out"
          className="p-1.5 rounded-md hover:bg-slate-900 text-slate-400 hover:text-rose-400 transition-colors"
        >
          <LogOut size={16} />
        </button>
      </div>
    </header>
  );
};

