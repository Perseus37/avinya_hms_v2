import React, { useState } from "react";
import {
  CheckSquare,
  X,
  AlertTriangle,
  ArrowRight,
  Stethoscope,
  Pill,
  CreditCard,
} from "lucide-react";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { WorkspaceId } from "../../types";

interface MyWorkDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateWorkspace: (workspace: WorkspaceId) => void;
}

export const MyWorkDrawer: React.FC<MyWorkDrawerProps> = ({
  isOpen,
  onClose,
  onNavigateWorkspace,
}) => {
  const [activeTab, setActiveTab] = useState<"ALL" | "OVERDUE" | "TODAY" | "APPROVALS">("ALL");

  if (!isOpen) return null;

  const tasks = [
    {
      id: "task-1",
      title: "Overdue Dose: IV Furosemide 20mg",
      category: "OVERDUE",
      urgency: "CRITICAL",
      patient: "Doe, John (CCU-204)",
      mrn: "AV-2026-00412",
      targetWorkspace: "nursing" as WorkspaceId,
      timeDue: "34 mins overdue",
      description: "Scheduled 12:00 round. High risk patient with acute pulmonary congestion.",
      icon: Pill,
    },
    {
      id: "task-2",
      title: "Panic Critical Value Read-Back Required",
      category: "OVERDUE",
      urgency: "CRITICAL",
      patient: "Doe, John (CCU-204)",
      mrn: "AV-2026-00412",
      targetWorkspace: "diagnostics" as WorkspaceId,
      timeDue: "18 mins overdue",
      description: "Serum Troponin-I: 0.12 ng/mL (High). Telephone read-back confirmation pending with Dr. Gupta.",
      icon: AlertTriangle,
    },
    {
      id: "task-3",
      title: "Sign SOAP Consultation Note",
      category: "TODAY",
      urgency: "MEDIUM",
      patient: "Sharma, Sunita (OPD)",
      mrn: "AV-2026-00415",
      targetWorkspace: "doctor" as WorkspaceId,
      timeDue: "Due Today",
      description: "Draft clinical note authored at 09:42. Awaiting final digital signature.",
      icon: Stethoscope,
    },
    {
      id: "task-4",
      title: "Discharge Clearance: Verify Pharmacy Return",
      category: "APPROVALS",
      urgency: "MEDIUM",
      patient: "Mehta, S. (W-302)",
      mrn: "AV-2026-00392",
      targetWorkspace: "pharmacy" as WorkspaceId,
      timeDue: "Pending Approval",
      description: "3 unconsumed IV Ceftriaxone ampoules returned from Ward. Credit voucher pending.",
      icon: CheckSquare,
    },
    {
      id: "task-5",
      title: "TPA Cashless Pre-Auth Query Resolution",
      category: "APPROVALS",
      urgency: "MEDIUM",
      patient: "Doe, John (CCU-204)",
      mrn: "AV-2026-00412",
      targetWorkspace: "billing" as WorkspaceId,
      timeDue: "Pending Approval",
      description: "Star Health requested previous 6-month angiogram records before approving ₹1.5L enhancement.",
      icon: CreditCard,
    },
  ];

  const filteredTasks = tasks.filter((t) => activeTab === "ALL" || t.category === activeTab);

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm transition-opacity" onClick={onClose} />

      <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
        <div className="w-screen max-w-md bg-slate-900 border-l border-slate-800 shadow-2xl flex flex-col z-10">
          {/* Header */}
          <div className="p-4 bg-slate-950 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <CheckSquare size={18} className="text-sky-400" />
              <div>
                <h2 className="text-sm font-bold text-slate-100">My Clinical Work Center</h2>
                <p className="text-[11px] text-slate-400">Assigned tasks, overdue items & clinical approvals</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-slate-100 hover:bg-slate-800"
            >
              <X size={18} />
            </button>
          </div>

          {/* Filter Pills */}
          <div className="p-3 bg-slate-900 border-b border-slate-800 flex space-x-1 text-xs">
            {(["ALL", "OVERDUE", "TODAY", "APPROVALS"] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`flex-1 py-1 px-2 rounded-lg font-semibold transition-all ${
                  activeTab === tab
                    ? "bg-sky-500 text-slate-950 font-bold"
                    : "text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Task List Body */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {filteredTasks.length === 0 ? (
              <div className="text-center py-12 text-slate-500 text-xs">No pending tasks in this category.</div>
            ) : (
              filteredTasks.map((task) => {
                const Icon = task.icon;
                const isCritical = task.urgency === "CRITICAL";
                return (
                  <div
                    key={task.id}
                    className={`p-3 rounded-xl border bg-slate-950 transition-all hover:border-slate-700 ${
                      isCritical ? "border-rose-900/80 bg-rose-950/10" : "border-slate-800"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className={`font-mono text-[10px] font-bold ${isCritical ? "text-rose-400" : "text-amber-400"}`}>
                        {task.timeDue}
                      </span>
                      <Badge variant={isCritical ? "danger" : "warning"}>{task.urgency}</Badge>
                    </div>

                    <div className="font-bold text-xs text-slate-200 flex items-center gap-1.5 mb-1">
                      <Icon size={14} className={isCritical ? "text-rose-400" : "text-sky-400"} />
                      <span>{task.title}</span>
                    </div>

                    <div className="text-[11px] text-slate-400 font-mono mb-2">
                      Patient: <span className="text-slate-200 font-semibold">{task.patient}</span> ({task.mrn})
                    </div>

                    <p className="text-[11px] text-slate-400 bg-slate-900 p-2 rounded border border-slate-800 leading-relaxed mb-3">
                      {task.description}
                    </p>

                    <Button
                      onClick={() => {
                        onNavigateWorkspace(task.targetWorkspace);
                        onClose();
                      }}
                      className="w-full flex items-center justify-center gap-1 text-xs py-1.5 bg-slate-800 hover:bg-sky-600 hover:text-slate-950 text-slate-200 font-semibold transition-all"
                    >
                      <span>Open Task in {task.targetWorkspace.toUpperCase()}</span>
                      <ArrowRight size={12} />
                    </Button>
                  </div>
                );
              })
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
