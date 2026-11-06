import React from "react";
import { LucideIcon, UserPlus, User, Clock3, DoorOpen, Stethoscope, BedDouble, Siren, Pill, Microscope, CreditCard, ShieldCheck, Scissors, Droplet, ShieldAlert, Wrench, LayoutDashboard, Settings, Wallet } from "lucide-react";
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
    { label: "Home", items: [{ id: "overview", label: "Overview", icon: LayoutDashboard }] },
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
        { id: "procurement-reconciliation", label: "Procurement Finance", icon: Wallet },
        { id: "infection-control", label: "Quality & Infection", icon: ShieldAlert },
        { id: "biomedical", label: "Biomedical", icon: Wrench },
      ],
    },
    { label: "Administration", items: [{ id: "admin", label: "Settings", icon: Settings }] },
  ];

  return (
    <aside className="flex w-[240px] shrink-0 select-none flex-col border-r border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-4 py-3">
        <div className="text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">Workspace</div>
        <div className="mt-1 truncate text-sm font-semibold text-slate-900">{roleDefinition.label}</div>
        <div className="mt-1 text-[11px] text-slate-500">Focused tools for your role</div>
      </div>

      <nav aria-label="Hospital navigation" className="flex-1 space-y-4 overflow-y-auto px-3 py-3">
        {groups.map((group) => {
          const items = group.items.filter((item) => isWorkspaceAllowed(item.id));
          if (!items.length) return null;
          return (
            <section key={group.label}>
              <div className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-400">{group.label}</div>
              <div className="space-y-0.5">
                {items.map((item) => {
                  const Icon = item.icon;
                  const active = activeWorkspace === item.id;
                  return (
                    <button key={item.id} type="button" onClick={() => onSelectWorkspace(item.id)} aria-current={active ? "page" : undefined} className={`flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-[13px] transition-colors ${active ? "bg-blue-50 font-semibold text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}>
                      <Icon size={16} strokeWidth={active ? 2.2 : 1.8} />
                      <span className="flex-1 text-left">{item.label}</span>
                      {item.badge && <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${active ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-500"}`}>{item.badge}</span>}
                    </button>
                  );
                })}
              </div>
            </section>
          );
        })}
      </nav>

      <div className="border-t border-slate-100 p-3">
        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-slate-700"><ShieldCheck size={14} className="text-emerald-600" />Access controlled</div>
          <div className="mt-1 text-[10px] leading-relaxed text-slate-500">Only workspaces permitted for the active role are shown.</div>
        </div>
      </div>
    </aside>
  );
};
