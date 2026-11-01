import React, { useState, useEffect } from "react";
import { WorkspaceId } from "../../types";
import { usePermissions } from "../../core/context/PermissionsContext";
import { TopNavbar } from "./TopNavbar";
import { Sidebar } from "./Sidebar";
import { PatientSafetyBanner } from "../clinical/PatientSafetyBanner";
import { CommandPalette } from "../clinical/CommandPalette";

import { PatientRegistrationWorkspace } from "../../workspaces/registration/PatientRegistrationWorkspace";
import { PatientRecordWorkspace } from "../../workspaces/patient/PatientRecordWorkspace";
import { OPDQueueWorkspace } from "../../workspaces/opd/OPDQueueWorkspace";
import { InpatientAdmissionWorkspace } from "../../workspaces/adt/InpatientAdmissionWorkspace";
import { DoctorCockpit } from "../../workspaces/doctor/DoctorCockpit";
import { WardNursingStation } from "../../workspaces/nursing/WardNursingStation";
import { EDTriageBoard } from "../../workspaces/triage/EDTriageBoard";
import { SurgeryWorkspace } from "../../workspaces/surgery/SurgeryWorkspace";
import { BloodBankWorkspace } from "../../workspaces/bloodbank/BloodBankWorkspace";
import { PharmacyWorkspace } from "../../workspaces/pharmacy/PharmacyWorkspace";
import { DiagnosticsWorkspace } from "../../workspaces/diagnostics/DiagnosticsWorkspace";
import { CashierCounterWorkspace } from "../../workspaces/billing/CashierCounterWorkspace";
import { AdminWorkspace } from "../../workspaces/admin/AdminWorkspace";
import { MyWorkDrawer } from "./MyWorkDrawer";
import { ErrorBoundary } from "../ui/ErrorBoundary";

export const AppShell: React.FC = () => {
  const { isWorkspaceAllowed, roleDefinition } = usePermissions();
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>(roleDefinition.defaultWorkspace);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isTasksOpen, setIsTasksOpen] = useState(false);

  // If active role changes and current workspace is not allowed, route to role's default workspace
  useEffect(() => {
    if (!isWorkspaceAllowed(activeWorkspace)) {
      setActiveWorkspace(roleDefinition.defaultWorkspace);
    }
  }, [roleDefinition, activeWorkspace]);

  // Global Keyboard Listener for Cmd+K / Ctrl+K and Alt+1..9
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }

      // Fast workspace switching via Alt+1..9
      if (e.altKey && !e.ctrlKey && !e.metaKey) {
        const workspaceOrder: WorkspaceId[] = [
          "registration",
          "patient-record",
          "opd-queue",
          "adt",
          "doctor",
          "nursing",
          "triage",
          "surgery",
          "blood-bank",
          "pharmacy",
          "diagnostics",
          "billing",
          "admin",
        ];
        const num = parseInt(e.key, 10);
        if (num >= 1 && num <= workspaceOrder.length) {
          e.preventDefault();
          setActiveWorkspace(workspaceOrder[num - 1]);
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const renderActiveWorkspace = () => {
    switch (activeWorkspace) {
      case "registration":
        return <PatientRegistrationWorkspace />;
      case "patient-record":
        return <PatientRecordWorkspace />;
      case "opd-queue":
        return <OPDQueueWorkspace />;
      case "adt":
        return <InpatientAdmissionWorkspace />;
      case "doctor":
        return <DoctorCockpit />;
      case "nursing":
        return <WardNursingStation />;
      case "triage":
        return <EDTriageBoard />;
      case "surgery":
        return <SurgeryWorkspace />;
      case "blood-bank":
        return <BloodBankWorkspace />;
      case "pharmacy":
        return <PharmacyWorkspace />;
      case "diagnostics":
        return <DiagnosticsWorkspace />;
      case "billing":
        return <CashierCounterWorkspace />;
      case "admin":
        return <AdminWorkspace onSelectWorkspace={setActiveWorkspace} />;
      default:
        return <PatientRegistrationWorkspace />;
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 overflow-hidden select-none">
      {/* 1. Global Navigation Bar with My Work Drawer Trigger */}
      <TopNavbar
        onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
        onOpenTasks={() => setIsTasksOpen(true)}
      />

      {/* 2. Universal Clinical Patient Safety Banner (CCOW Context) */}
      <PatientSafetyBanner onOpenPatientRecord={() => setActiveWorkspace("patient-record")} />

      {/* 3. Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar activeWorkspace={activeWorkspace} onSelectWorkspace={setActiveWorkspace} />
        <main className="flex-1 flex overflow-hidden bg-slate-950">
          <ErrorBoundary moduleName={`Workspace: ${activeWorkspace}`}>
            {renderActiveWorkspace()}
          </ErrorBoundary>
        </main>
      </div>

      {/* 4. Command Palette (Cmd+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onSelectWorkspace={setActiveWorkspace}
      />

      {/* 5. My Clinical Work Center Slide-Over Drawer */}
      <MyWorkDrawer
        isOpen={isTasksOpen}
        onClose={() => setIsTasksOpen(false)}
        onNavigateWorkspace={(ws) => setActiveWorkspace(ws)}
      />
    </div>
  );
};

