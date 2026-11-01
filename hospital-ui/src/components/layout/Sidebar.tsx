import React from "react";
import {
  LucideIcon,
  UserPlus,
  DoorOpen,
  Stethoscope,
  BedDouble,
  Siren,
  Pill,
  Microscope,
  CreditCard,
  ShieldCheck,
} from "lucide-react";
import { WorkspaceId } from "../../types";

interface SidebarProps {
  activeWorkspace: WorkspaceId;
  onSelectWorkspace: (workspace: WorkspaceId) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeWorkspace,
  onSelectWorkspace,
}) => {
  const items: Array<{
    id: WorkspaceId;
    label: string;
    icon: LucideIcon;
    shortcut: string;
    badge?: string;
  }> = [
    { id: "registration", label: "Patient Intake", icon: UserPlus, shortcut: "Alt+1", badge: "New" },
    { id: "adt", label: "Inpatient ADT", icon: DoorOpen, shortcut: "Alt+2" },
    { id: "doctor", label: "Doctor Cockpit", icon: Stethoscope, shortcut: "Alt+3" },
    { id: "nursing", label: "Ward Nursing", icon: BedDouble, shortcut: "Alt+4" },
    { id: "triage", label: "ED Triage", icon: Siren, shortcut: "Alt+5", badge: "Trauma" },
    { id: "pharmacy", label: "Pharmacy & NDPS", icon: Pill, shortcut: "Alt+6" },
    { id: "diagnostics", label: "Diagnostics & LIS", icon: Microscope, shortcut: "Alt+7" },
    { id: "billing", label: "Cashier Billing", icon: CreditCard, shortcut: "Alt+8" },
    { id: "admin", label: "Executive HUD", icon: ShieldCheck, shortcut: "Alt+9" },
  ];

  return (
    <aside className="w-64 bg-slate-950 border-r border-slate-800 flex flex-col justify-between p-3 select-none">
      <div className="space-y-1">
        <div className="px-3 py-2 text-[11px] font-bold uppercase tracking-wider text-slate-500 font-mono">
          Workspaces
        </div>
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = activeWorkspace === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onSelectWorkspace(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                isActive
                  ? "bg-sky-500/10 text-sky-400 border border-sky-500/30 font-semibold"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
              }`}
            >
              <div className="flex items-center gap-3">
                <Icon size={17} className={isActive ? "text-sky-400" : "text-slate-400"} />
                <span>{item.label}</span>
              </div>
              <div className="flex items-center gap-1.5">
                {item.badge && (
                  <span className="text-[10px] font-mono font-bold px-1.5 py-0.2 rounded bg-rose-950 text-rose-400 border border-rose-900/60">
                    {item.badge}
                  </span>
                )}
                <span className="text-[9px] font-mono text-slate-600 opacity-60 group-hover:opacity-100">
                  {item.shortcut}
                </span>
              </div>
            </button>
          );
        })}
      </div>

      <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-[11px] text-slate-500">
        <div className="font-semibold text-slate-400">Avinya Core Engine</div>
        <div>v4.5.0 Enterprise</div>
        <div className="text-[10px] text-slate-600 mt-1 font-mono">DPDP Act 2023 Enforced</div>
      </div>
    </aside>
  );
};

