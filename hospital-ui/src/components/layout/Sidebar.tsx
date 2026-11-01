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
  Shield,
  User,
  Clock,
  Scissors,
} from "lucide-react";
import { WorkspaceId } from "../../types";
import { usePermissions } from "../../core/context/PermissionsContext";

interface SidebarProps {
  activeWorkspace: WorkspaceId;
  onSelectWorkspace: (workspace: WorkspaceId) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeWorkspace,
  onSelectWorkspace,
}) => {
  const { isWorkspaceAllowed, roleDefinition } = usePermissions();

  const allItems: Array<{
    id: WorkspaceId;
    label: string;
    icon: LucideIcon;
    shortcut: string;
    badge?: string;
  }> = [
    { id: "registration", label: "Patient Intake", icon: UserPlus, shortcut: "Alt+1", badge: "New" },
    { id: "patient-record", label: "Patient 360", icon: User, shortcut: "Alt+P", badge: "Core" },
    { id: "opd-queue", label: "OPD Command", icon: Clock, shortcut: "Alt+Q", badge: "Queue" },
    { id: "adt", label: "Inpatient ADT", icon: DoorOpen, shortcut: "Alt+2" },
    { id: "doctor", label: "Doctor Cockpit", icon: Stethoscope, shortcut: "Alt+3" },
    { id: "nursing", label: "Ward Nursing", icon: BedDouble, shortcut: "Alt+4" },
    { id: "triage", label: "ED Triage", icon: Siren, shortcut: "Alt+5", badge: "Trauma" },
    { id: "surgery", label: "Surgery & OT Suite", icon: Scissors, shortcut: "Alt+S", badge: "OT" },
    { id: "pharmacy", label: "Pharmacy & NDPS", icon: Pill, shortcut: "Alt+6" },
    { id: "diagnostics", label: "Diagnostics & LIS", icon: Microscope, shortcut: "Alt+7" },
    { id: "billing", label: "Cashier Billing", icon: CreditCard, shortcut: "Alt+8" },
    { id: "admin", label: "Executive HUD", icon: ShieldCheck, shortcut: "Alt+9" },
  ];

  // Filter workspaces allowed for the user's active simulated role
  const items = allItems.filter((item) => isWorkspaceAllowed(item.id));

  return (
    <aside className="w-64 bg-slate-950 border-r border-slate-800 flex flex-col justify-between p-3 select-none">
      <nav aria-label="Hospital Workspaces" className="space-y-1">
        {/* Active Role Scope Badge */}
        <div className="px-3 py-2 bg-slate-900/60 rounded-lg border border-slate-800/80 mb-2">
          <div className="text-[10px] font-mono text-slate-500 uppercase flex items-center gap-1 font-bold">
            <Shield size={11} className="text-sky-400" /> Active Role Scope
          </div>
          <div className="text-xs font-bold text-slate-200 mt-0.5">{roleDefinition.label}</div>
          <div className="text-[10px] text-slate-400 font-mono mt-0.5">
            {items.length} of {allItems.length} workspaces granted
          </div>
        </div>

        <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-500 font-mono">
          Permitted Workspaces
        </div>
        <ul className="space-y-1">
          {items.map((item) => {
            const Icon = item.icon;
            const isActive = activeWorkspace === item.id;

            return (
              <li key={item.id}>
                <a
                  href={`#workspace/${item.id}`}
                  onClick={(e) => {
                    e.preventDefault();
                    onSelectWorkspace(item.id);
                  }}
                  aria-current={isActive ? "page" : undefined}
                  className={`w-full flex items-center justify-between px-3 py-2.5 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-sky-500/10 text-sky-400 border border-sky-500/30 font-semibold"
                      : "text-slate-400 hover:text-slate-200 hover:bg-slate-900 border border-transparent"
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
                </a>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="p-3 rounded-lg bg-slate-900/60 border border-slate-800 text-[11px] text-slate-500">
        <div className="font-semibold text-slate-400">Avinya Customization Engine</div>
        <div>Dynamic Role-Based Access Control</div>
        <div className="text-[10px] text-slate-600 mt-1 font-mono">DPDP Act 2023 Statutory RBAC</div>
      </div>
    </aside>
  );
};

