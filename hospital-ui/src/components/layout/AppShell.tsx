import React, { useState, useEffect, Suspense, lazy } from "react";
import { WorkspaceId } from "../../types";
import { usePermissions } from "../../core/context/PermissionsContext";
import { TopNavbar } from "./TopNavbar";
import { Sidebar } from "./Sidebar";
import { PatientSafetyBanner } from "../clinical/PatientSafetyBanner";
import { CommandPalette } from "../clinical/CommandPalette";
import { MyWorkDrawer } from "./MyWorkDrawer";
import { ErrorBoundary } from "../ui/ErrorBoundary";

const HospitalAdminDashboard = lazy(() => import("../../workspaces/overview/HospitalAdminDashboard").then((m) => ({ default: m.HospitalAdminDashboard })));
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
  <div className="flex flex-1 flex-col items-center justify-center bg-[#f5f7fa] text-slate-500">
    <div className="mb-3 h-7 w-7 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />
    <span className="text-sm font-medium text-slate-700">Loading workspace</span>
    <span className="mt-1 text-[11px] text-slate-400">{activeWorkspace.replaceAll("-", " ")}</span>
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
      case "overview": return <HospitalAdminDashboard />;
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
      default: return <HospitalAdminDashboard />;
    }
  };

  return (
    <div className="av-shell flex h-screen w-screen flex-col overflow-hidden">
      <TopNavbar onOpenCommandPalette={() => setIsCommandPaletteOpen(true)} onOpenTasks={() => setIsTasksOpen(true)} />
      <PatientSafetyBanner onOpenPatientRecord={() => setActiveWorkspace("patient-record")} />
      <div className="flex min-h-0 flex-1 overflow-hidden">
        <Sidebar activeWorkspace={activeWorkspace} onSelectWorkspace={setActiveWorkspace} />
        <main className="flex min-w-0 flex-1 overflow-hidden bg-[#f5f7fa]">
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
