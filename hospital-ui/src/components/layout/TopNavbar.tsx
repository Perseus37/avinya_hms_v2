import React, { useState } from "react";
import { Search, LogOut, Activity, User, HelpCircle, Keyboard, ChevronDown, Shield, CheckSquare } from "lucide-react";
import { useAuth } from "../../core/context/AuthContext";
import { usePermissions, ROLE_DEFINITIONS, RoleCode } from "../../core/context/PermissionsContext";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { Modal } from "../ui/Modal";

interface TopNavbarProps {
  onOpenCommandPalette: () => void;
  onOpenTasks?: () => void;
}

export const TopNavbar: React.FC<TopNavbarProps> = ({ onOpenCommandPalette, onOpenTasks }) => {
  const { user, logout } = useAuth();
  const { activeRole, roleDefinition, isSimulating, isDev, setActiveRole, resetToAuthenticatedRole } = usePermissions();
  const { hospitalProfile } = useHospitalConfig();
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isRoleMenuOpen, setIsRoleMenuOpen] = useState(false);

  return (
    <header className="h-14 bg-slate-950 border-b border-slate-800 px-4 flex items-center justify-between select-none">
      {/* Brand & Hospital Identity */}
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
        <div className="flex items-center gap-2 text-[11px] font-mono">
          <span className="text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800 flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-200 font-semibold">{hospitalProfile.name.split(" ")[0]} {hospitalProfile.name.split(" ")[1] || ""}</span>
            <span className="text-slate-500 hidden md:inline">• Main Tower</span>
          </span>
          <span className="hidden lg:inline-flex text-slate-400 bg-slate-900/80 px-2 py-0.5 rounded border border-slate-800">
            ☀️ Morning Shift (07:00–15:00)
          </span>
          <span className="hidden xl:inline-flex items-center gap-1 text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/60 text-[10px]">
            <span className="w-1 h-1 rounded-full bg-emerald-400" /> 12ms Sync
          </span>
        </div>
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

      {/* User Session, Role Badge / Dev Simulator & Logout */}
      <div className="flex items-center gap-3">
        {/* Production: Read-only Authenticated Role Chip | Dev: Simulator Menu */}
        {!isDev ? (
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 text-xs font-semibold shadow-inner"
            title={`Authenticated Session: ${roleDefinition.label} (Enforced by JWT Claims)`}
          >
            <Shield size={13} className="text-emerald-400" />
            <span className="hidden sm:inline text-slate-400">Role:</span>
            <span className="font-bold text-slate-200">{roleDefinition.label}</span>
            <span className="text-[9px] font-mono px-1 py-0.2 rounded bg-emerald-950/80 text-emerald-400 border border-emerald-800">
              VERIFIED
            </span>
          </div>
        ) : (
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsRoleMenuOpen(!isRoleMenuOpen)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 text-xs font-semibold transition-all shadow-sm ${
                isSimulating
                  ? "border border-amber-500/80 text-amber-300 shadow-amber-500/10 shadow-lg"
                  : "border border-slate-700 hover:border-slate-500 text-slate-300"
              }`}
              title="Development RBAC Simulator (Dev Mode Only - Demoted in Production)"
            >
              <Shield size={13} className={isSimulating ? "text-amber-400" : "text-sky-400"} />
              <span className="text-[9px] font-mono font-bold uppercase px-1 py-0.2 rounded bg-amber-950 text-amber-400 border border-amber-800/80">
                DEV SIM
              </span>
              <span className="font-bold">{roleDefinition.label}</span>
              <ChevronDown size={12} className="text-slate-400" />
            </button>

            {isRoleMenuOpen && (
              <div className="absolute right-0 top-full mt-2 w-80 bg-slate-900 border border-slate-700 rounded-xl shadow-2xl z-50 p-2 space-y-1">
                <div className="px-2 py-1 text-[10px] font-mono uppercase text-slate-400 font-bold border-b border-slate-800 flex justify-between items-center">
                  <span>RBAC Role Simulator (Dev Only)</span>
                  {isSimulating && (
                    <button
                      type="button"
                      onClick={() => {
                        resetToAuthenticatedRole();
                        setIsRoleMenuOpen(false);
                      }}
                      className="text-[10px] text-amber-400 hover:text-amber-300 underline font-semibold"
                    >
                      Reset to Auth
                    </button>
                  )}
                </div>

                <div className="p-1.5 text-[10px] text-slate-400 bg-slate-950 rounded border border-slate-800/80 leading-relaxed">
                  In production, staff roles are derived strictly from JWT claims & Active Directory. This switcher is active in local development only.
                </div>

                {Object.values(ROLE_DEFINITIONS).map((r) => {
                  const isSelected = activeRole === r.code;
                  return (
                    <button
                      key={r.code}
                      type="button"
                      onClick={() => {
                        setActiveRole(r.code as RoleCode);
                        setIsRoleMenuOpen(false);
                      }}
                      className={`w-full text-left p-2 rounded-lg text-xs transition-all ${
                        isSelected
                          ? "bg-amber-500/20 text-amber-200 border border-amber-500/50 font-bold shadow-sm"
                          : "text-slate-300 hover:bg-slate-800/70 border border-transparent"
                      }`}
                    >
                      <div className="flex items-center justify-between mb-0.5">
                        <span>{r.label}</span>
                        <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-slate-950 text-slate-400 border border-slate-800">
                          {r.badge}
                        </span>
                      </div>
                      <div className="text-[10px] text-slate-400 font-normal line-clamp-1">{r.description}</div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* Global Task Center ("My Work") Trigger */}
        {onOpenTasks && (
          <button
            onClick={onOpenTasks}
            title="My Clinical Work Center (Tasks & Approvals)"
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs text-slate-300 hover:text-sky-400 transition-colors shadow-sm"
          >
            <CheckSquare size={13} className="text-sky-400" />
            <span className="hidden md:inline font-semibold">My Work</span>
            <span className="font-mono text-[10px] px-1.5 py-0.2 rounded-full bg-rose-950 text-rose-300 border border-rose-800 font-bold">
              5
            </span>
          </button>
        )}

        <button
          onClick={() => setIsHelpOpen(true)}
          title="Clinical Hotkeys & Keyboard Navigation (Press ?)"
          className="p-1.5 rounded-md hover:bg-slate-900 text-slate-400 hover:text-sky-400 transition-colors"
        >
          <HelpCircle size={17} />
        </button>

        <div className="h-4 w-[1px] bg-slate-800" />

        <div className="flex items-center gap-2.5 text-xs">
          <div className="w-7 h-7 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300">
            <User size={14} />
          </div>
          <div className="text-left hidden sm:block">
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

      {/* Modal: Fast Clinical Hotkeys & Keyboard Navigation */}
      <Modal
        isOpen={isHelpOpen}
        onClose={() => setIsHelpOpen(false)}
        title="Avinya Clinical Keyboard Navigation & Hotkeys"
      >
        <div className="space-y-4">
          <div className="p-3 rounded-lg bg-sky-950/30 border border-sky-900/60 text-xs text-sky-300 flex items-center gap-2">
            <Keyboard size={16} />
            <span>High-throughput keyboard shortcuts engineered for rapid clinical and front-desk workflows.</span>
          </div>

          <div className="space-y-2 text-xs font-mono max-h-[60vh] overflow-y-auto pr-1">
            {[
              { key: "Cmd + K / Ctrl + K", desc: "Universal Patient MPI Search & Command Launcher" },
              { key: "Alt + 1", desc: "Patient Intake & Registration Desk" },
              { key: "Alt + P", desc: "Longitudinal Patient 360 & DPDP Consent" },
              { key: "Alt + Q", desc: "OPD Queue Command & 4K Lounge Calling" },
              { key: "Alt + 2", desc: "Inpatient ADT, Bed Booking & Visitor Pass" },
              { key: "Alt + 3", desc: "Doctor Cockpit, CPOE & Admission Orders" },
              { key: "Alt + 4", desc: "Ward Nursing, eMAR BCMA & Fluid Balance" },
              { key: "Alt + 5", desc: "Emergency Triage, Trauma MLC & MCI Intake" },
              { key: "Alt + S", desc: "Surgery Suite, WHO Checklist & RSI Safety" },
              { key: "Alt + B", desc: "Blood Bank, Form 27C & STAT O-Neg Release" },
              { key: "Alt + 6", desc: "Central Pharmacy, Tall Man & NDPS Vault" },
              { key: "Alt + 7", desc: "Laboratory Diagnostics & Sample Rejections" },
              { key: "Alt + I", desc: "Infection Control & MDR Isolation Placards" },
              { key: "Alt + M", desc: "Biomedical Engineering & LOTO Safety" },
              { key: "Alt + 8", desc: "Cashier Billing, EWS Waivers & GST Invoice" },
              { key: "Alt + 9", desc: "Executive Cockpit, Downtime BCP & Facility Dossier" },
              { key: "Esc", desc: "Close any open dialog or modal without committing" },
            ].map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800/80"
              >
                <span className="text-slate-300">{item.desc}</span>
                <kbd className="px-2 py-0.5 bg-slate-900 border border-slate-700 rounded text-sky-400 font-bold text-[11px]">
                  {item.key}
                </kbd>
              </div>
            ))}
          </div>

          <div className="pt-2 border-t border-slate-800 flex justify-end">
            <button
              onClick={() => setIsHelpOpen(false)}
              className="px-4 py-1.5 rounded-lg bg-sky-500 hover:bg-sky-400 text-slate-950 text-xs font-bold transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </Modal>
    </header>
  );
};


