import React from "react";
import { LucideIcon, UserPlus, User, Clock3, DoorOpen, Stethoscope, BedDouble, Siren, Pill, Microscope, CreditCard, ShieldCheck, Scissors, Droplet, ShieldAlert, Wrench, LayoutDashboard } from "lucide-react";
import { WorkspaceId } from "../../types";
import { usePermissions } from "../../core/context/PermissionsContext";

interface SidebarProps {
  activeWorkspace: WorkspaceId;
  onSelectWorkspace: (workspace: WorkspaceId) => void;
}

type NavItem = { id: WorkspaceId; label: string; icon: LucideIcon; badge?: string };
type NavGroup = { label: string; items: NavItem[] };

export const Sidebar: React.FC<SidebarProps> = ({ activeWorkspace, onSelectWorkspace }) => {
  const { isWorkspaceAllowed, roleDefinition } = usePermissions();

  const groups: NavGroup[] = [
    {
      label: "Home",
      items: [{ id: "admin", label: "Overview", icon: LayoutDashboard }],
    },
    {
      label: "Patient Flow",
      items: [
        { id: "registration", label: "Registration", icon: UserPlus },
        { id: "patient-record", label: "Patients", icon: User },
        { id: "opd-queue", label: "OPD Queue", icon: Clock3 },
        { id: "adt", label: "Admissions & Beds", icon: DoorOpen },
        { id: "triage", label: "Emergency", icon: Siren, badge: "ED" },
      ],
    },
    {
      label: "Clinical",
      items: [
        { id: "doctor", label: "Clinical", icon: Stethoscope },
        { id: "nursing", label: "Nursing", icon: BedDouble },
        { id: "diagnostics", label: "Diagnostics", icon: Microscope },
        { id: "pharmacy", label: "Pharmacy", icon: Pill },
        { id: "surgery", label: "Surgery", icon: Scissors },
        { id: "blood-bank", label: "Blood Bank", icon: Droplet },
      ],
    },
    {
      label: "Operations",
      items: [
        { id: "billing", label: "Billing & Cashier", icon: CreditCard },
        { id: "infection-control", label: "Quality & Infection", icon: ShieldAlert },
        { id: "biomedical", label: "Biomedical", icon: Wrench },
      ],
    },
  ];

  return (
    <aside className="w-[240px] shrink-0 bg-white border-r border-slate-200 flex flex-col select-none">
      <div className="px-4 py-3 border-b border-slate-100">
        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Workspace</div>
        <div className="mt-1 text-sm font-semibold text-slate-900 truncate">{roleDefinition.label}</div>
        <div className="mt-1 text-[11px] text-slate-500">Focused tools for your role</div>
      </div>

      <nav aria-label="Hospital navigation" className="flex-1 overflow-y-auto px-3 py-3 space-y-4">
        {groups.map((group) => {
          const items = group.items.filter((item) => isWorkspaceAllowed(item.id));
          if (!items.length) return null;
          return (
            <section key={group.label}>
              <div className="px-2 mb-1.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{group.label}</div>
              <div className="space-y-0.5">
                {items.map((item) => {
                  const Icon = item.icon;
                  const active = activeWorkspace === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() => onSelectWorkspace(item.id)}
                      aria-current={active ? "page" : undefined}
                      className={`w-full flex items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] transition-colors ${
                        active
                          ? "bg-blue-50 text-blue-700 font-semibold"
                          : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"
                      }`}
                    >
                      <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
                      <span className="flex-1 text-left">{item.label}</span>
                      {item.badge && (
                        <span className={`text-[9px] font-semibold px-1.5 py-0.5 rounded-full ${active ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500"}`}>
                          {item.badge}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </section>
          );
        })}
      </nav>

      <div className="p-3 border-t border-slate-100">
        <div className="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2.5">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-700">
            <ShieldCheck size={14} className="text-emerald-600" />
            Access controlled
          </div>
          <div className="mt-1 text-[10px] leading-relaxed text-slate-500">Only workspaces permitted for the active role are shown.</div>
        </div>
      </div>
    </aside>
  );
};
