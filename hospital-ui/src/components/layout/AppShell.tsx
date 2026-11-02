import React, { useState, useEffect, Suspense, lazy } from "react";
import { WorkspaceId } from "../../types";
import { usePermissions } from "../../core/context/PermissionsContext";
import { TopNavbar } from "./TopNavbar";
import { Sidebar } from "./Sidebar";
import { PatientSafetyBanner } from "../clinical/PatientSafetyBanner";
import { CommandPalette } from "../clinical/CommandPalette";
import { MyWorkDrawer } from "./MyWorkDrawer";
import { ErrorBoundary } from "../ui/ErrorBoundary";

const PatientRegistrationWorkspace = lazy(() => import("../../workspaces/registration/PatientRegistrationWorkspace").then((m) => ({ default: m.PatientRegistrationWorkspace })));
const PatientRecordWorkspace = lazy(() => import("../../workspaces/patient/PatientRecordWorkspace").then((m) => ({ default: m.PatientRecordWorkspace })));
const OPDQueueWorkspace = lazy(() => import("../../workspaces/opd/OPDQueueWorkspace").then((m) => ({ default: m.OPDQueueWorkspace })));
const InpatientAdmissionWorkspace = lazy(() => import("../../workspaces/adt/InpatientAdmissionWorkspace").then((m) => ({ default: m.InpatientAdmissionWorkspace })));
const DoctorCockpit = lazy(() => import("../../workspaces/doctor/DoctorCockpit").then((m) => ({ default: m.DoctorCockpit })));
const WardNursingStation = lazy(() => import("../../workspaces/nursing/WardNursingStation").then((m) => ({ default: m.WardNursingStation })));
const EDTriageBoard = lazy(() => import("../../workspaces/triage/EDTriageBoard").then((m) => ({ default: m.EDTriageBoard })));
const SurgeryWorkspace = lazy(() => import("../../workspaces/surgery/SurgeryWorkspace").then((m) => ({ default: m.SurgeryWorkspace })));
const BloodBankWorkspace = lazy(() => import("../../workspaces/bloodbank/BloodBankWorkspace").then((m) => ({ default: m.BloodBankWorkspace })));
const PharmacyWorkspace = lazy(() => import("../../workspaces/pharmacy/PharmacyWorkspace").then((m) => ({ default: m.PharmacyWorkspace })));
const DiagnosticsWorkspace = lazy(() => import("../../workspaces/diagnostics/DiagnosticsWorkspace").then((m) => ({ default: m.DiagnosticsWorkspace })));
const CashierCounterWorkspace = lazy(() => import("../../workspaces/billing/CashierCounterWorkspace").then((m) => ({ default: m.CashierCounterWorkspace })));
const InfectionControlWorkspace = lazy(() => import("../../workspaces/infection/InfectionControlWorkspace").then((m) => ({ default: m.InfectionControlWorkspace })));
const BiomedicalWorkspace = lazy(() => import("../../workspaces/biomedical/BiomedicalWorkspace").then((m) => ({ default: m.BiomedicalWorkspace })));
const AdminWorkspace = lazy(() => import("../../workspaces/admin/AdminWorkspace").then((m) => ({ default: m.AdminWorkspace })));

const WorkspaceSkeleton: React.FC<{ activeWorkspace: WorkspaceId }> = ({ activeWorkspace }) => (
  <div className="flex-1 flex flex-col items-center justify-center bg-slate-950 text-slate-400">
    <div className="w-7 h-7 border-2 border-blue-400 border-t-transparent rounded-full animate-spin mb-3" />
    <span className="text-sm font-medium text-slate-200">Loading workspace</span>
    <span className="text-[11px] text-slate-500 mt-1">{activeWorkspace.replaceAll("-", " ")}</span>
  </div>
);

export const AppShell: React.FC = () => {
  const { isWorkspaceAllowed, roleDefinition } = usePermissions();
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>(roleDefinition.defaultWorkspace);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isTasksOpen, setIsTasksOpen] = useState(false);

  useEffect(() => {
    if (!isWorkspaceAllowed(activeWorkspace)) setActiveWorkspace(roleDefinition.defaultWorkspace);
  }, [roleDefinition, activeWorkspace, isWorkspaceAllowed]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const renderActiveWorkspace = () => {
    switch (activeWorkspace) {
      case "registration": return <PatientRegistrationWorkspace />;
      case "patient-record": return <PatientRecordWorkspace />;
      case "opd-queue": return <OPDQueueWorkspace />;
      case "adt": return <InpatientAdmissionWorkspace />;
      case "doctor": return <DoctorCockpit />;
      case "nursing": return <WardNursingStation />;
      case "triage": return <EDTriageBoard />;
      case "surgery": return <SurgeryWorkspace />;
      case "blood-bank": return <BloodBankWorkspace />;
      case "pharmacy": return <PharmacyWorkspace />;
      case "diagnostics": return <DiagnosticsWorkspace />;
      case "billing": return <CashierCounterWorkspace />;
      case "infection-control": return <InfectionControlWorkspace />;
      case "biomedical": return <BiomedicalWorkspace />;
      case "admin": return <AdminWorkspace onSelectWorkspace={setActiveWorkspace} />;
      default: return <PatientRegistrationWorkspace />;
    }
  };

  return (
    <div className="av-shell h-screen w-screen flex flex-col overflow-hidden">
      <TopNavbar onOpenCommandPalette={() => setIsCommandPaletteOpen(true)} onOpenTasks={() => setIsTasksOpen(true)} />
      <PatientSafetyBanner onOpenPatientRecord={() => setActiveWorkspace("patient-record")} />
      <div className="flex-1 flex min-h-0 overflow-hidden">
        <Sidebar activeWorkspace={activeWorkspace} onSelectWorkspace={setActiveWorkspace} />
        <main className="flex-1 min-w-0 flex overflow-hidden bg-slate-950">
          <ErrorBoundary moduleName={`Workspace: ${activeWorkspace}`}>
            <Suspense fallback={<WorkspaceSkeleton activeWorkspace={activeWorkspace} />}>
              {renderActiveWorkspace()}
            </Suspense>
          </ErrorBoundary>
        </main>
      </div>
      <CommandPalette isOpen={isCommandPaletteOpen} onClose={() => setIsCommandPaletteOpen(false)} onSelectWorkspace={setActiveWorkspace} />
      <MyWorkDrawer isOpen={isTasksOpen} onClose={() => setIsTasksOpen(false)} onNavigateWorkspace={(ws) => setActiveWorkspace(ws)} />
    </div>
  );
};
