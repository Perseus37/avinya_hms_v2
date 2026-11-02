import React, { useState } from "react";
import { Search, LogOut, Activity, User, HelpCircle, Keyboard, ChevronDown, ShieldCheck, CheckSquare, Building2 } from "lucide-react";
import { useAuth } from "../../core/context/AuthContext";
import { usePermissions, ROLE_DEFINITIONS, RoleCode } from "../../core/context/PermissionsContext";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";\nimport { useTenantBranding } from "../../core/context/TenantBrandingContext";
import { Modal } from "../ui/Modal";

interface TopNavbarProps {
  onOpenCommandPalette: () => void;
  onOpenTasks?: () => void;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({ onOpenCommandPalette, onOpenTasks }) => {
  const { user, logout } = useAuth();
  const { activeRole, roleDefinition, isSimulating, isDev, setActiveRole, resetToAuthenticatedRole } = usePermissions();
  const { hospitalProfile } = useHospitalConfig();\n  const { branding } = useTenantBranding();
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isRoleMenuOpen, setIsRoleMenuOpen] = useState(false);

  return (
    <header className="h-16 shrink-0 bg-white border-b border-slate-200 px-5 flex items-center gap-5 select-none">
      <div className="flex items-center gap-3 min-w-[235px]">
        <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center text-white shadow-sm">
          <Activity size={17} />
        </div>
        <div>
          <div className="text-sm font-bold tracking-tight text-slate-950">AVINYA</div>
          <div className="text-[9px] font-semibold uppercase tracking-[0.14em] text-slate-400">Hospital Management</div>
        </div>
        <div className="hidden lg:flex items-center gap-2 ml-2 pl-3 border-l border-slate-200 text-xs text-slate-600">
          <Building2 size={14} className="text-slate-400" />
          <span className="font-medium truncate max-w-[150px]">{hospitalProfile.name}</span>
        </div>
      </div>

      <button
        onClick={onOpenCommandPalette}
        className="flex-1 max-w-[560px] h-9 flex items-center gap-2.5 px-3 rounded-lg bg-slate-50 border border-slate-200 text-xs text-slate-500 hover:border-slate-300 hover:bg-white transition-colors"
      >
        <Search size={15} className="text-slate-400" />
        <span>Search patients, MRN, appointments, orders...</span>
        <kbd className="ml-auto px-1.5 py-0.5 rounded border border-slate-200 bg-white text-[10px] text-slate-400">Ctrl K</kbd>
      </button>

      <div className="ml-auto flex items-center gap-2">
        {onOpenTasks && (
          <button onClick={onOpenTasks} className="h-9 px-3 flex items-center gap-2 rounded-lg border border-slate-200 text-xs font-medium text-slate-600 hover:bg-slate-50">
            <CheckSquare size={15} className="text-blue-600" />
            <span className="hidden lg:inline">My Work</span>
            <span className="min-w-5 h-5 px-1 rounded-full bg-rose-50 text-rose-700 flex items-center justify-center text-[10px] font-bold">5</span>
          </button>
        )}

        <button onClick={() => setIsHelpOpen(true)} className="h-9 w-9 flex items-center justify-center rounded-lg text-slate-500 hover:bg-slate-50" title="Keyboard shortcuts">
          <HelpCircle size={17} />
        </button>

        {isDev ? (
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsRoleMenuOpen(!isRoleMenuOpen)}
              className={`h-9 px-3 flex items-center gap-2 rounded-lg border text-xs font-semibold ${isSimulating ? "border-amber-300 bg-amber-50 text-amber-800" : "border-slate-200 text-slate-600 hover:bg-slate-50"}`}
            >
              <ShieldCheck size={14} className={isSimulating ? "text-amber-600" : "text-emerald-600"} />
              <span className="hidden xl:inline">{roleDefinition.badge}</span>
              <ChevronDown size={13} />
            </button>
            {isRoleMenuOpen && (
              <div className="absolute right-0 top-11 w-80 bg-white border border-slate-200 rounded-xl shadow-xl z-50 p-2">
                <div className="px-2 py-2 border-b border-slate-100 mb-1">
                  <div className="text-xs font-semibold text-slate-800">Development role simulator</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Available only in local development.</div>
                </div>
                {Object.values(ROLE_DEFINITIONS).map((r) => (
                  <button
                    key={r.code}
                    type="button"
                    onClick={() => { setActiveRole(r.code as RoleCode); setIsRoleMenuOpen(false); }}
                    className={`w-full text-left px-2.5 py-2 rounded-lg text-xs ${activeRole === r.code ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50"}`}
                  >
                    <div className="font-semibold">{r.label}</div>
                    <div className="text-[10px] text-slate-400 mt-0.5 truncate">{r.description}</div>
                  </button>
                ))}
                {isSimulating && <button onClick={() => { resetToAuthenticatedRole(); setIsRoleMenuOpen(false); }} className="w-full mt-1 px-2.5 py-2 text-left text-[11px] text-amber-700 hover:bg-amber-50 rounded-lg">Reset to authenticated role</button>}
              </div>
            )}
          </div>
        ) : (
          <div className="hidden xl:flex items-center gap-2 px-3 h-9 rounded-lg bg-emerald-50 text-emerald-700 text-xs font-semibold">
            <ShieldCheck size={14} /> Verified session
          </div>
        )}

        <div className="h-6 w-px bg-slate-200 mx-1" />
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200 flex items-center justify-center text-slate-600"><User size={15} /></div>
          <div className="hidden xl:block leading-tight">
            <div className="text-xs font-semibold text-slate-800">{user?.full_name || "Staff Member"}</div>
            <div className="text-[10px] text-slate-400 max-w-[160px] truncate">{user?.email}</div>
          </div>
        </div>
        <button onClick={logout} className="h-9 w-9 flex items-center justify-center rounded-lg text-slate-500 hover:bg-rose-50 hover:text-rose-600" title="Sign out"><LogOut size={16} /></button>
      </div>

      <Modal isOpen={isHelpOpen} onClose={() => setIsHelpOpen(false)} title="Keyboard shortcuts">
        <div className="space-y-3">
          <div className="p-3 rounded-lg bg-blue-50 border border-blue-100 text-xs text-blue-800 flex items-center gap-2"><Keyboard size={15} /> Use the command palette for patient and workflow navigation.</div>
          <div className="space-y-2 text-xs">
            {["Ctrl/Cmd + K — Global search and commands", "Esc — Close dialogs and overlays", "Alt + 1–9 — Legacy workspace shortcuts"].map((text) => (
              <div key={text} className="p-2.5 rounded-lg bg-slate-50 border border-slate-200 text-slate-600">{text}</div>
            ))}
          </div>
        </div>
      </Modal>
    </header>
  );
};
