import React, { useState, useEffect } from "react";
import { WorkspaceId } from "../../types";
import { usePermissions } from "../../core/context/PermissionsContext";
import { TopNavbar } from "./TopNavbar";
import { Sidebar } from "./Sidebar";
import { PatientSafetyBanner } from "../clinical/PatientSafetyBanner";
import { CommandPalette } from "../clinical/CommandPalette";

import { PatientRegistrationWorkspace } from "../../workspaces/registration/PatientRegistrationWorkspace";
import { InpatientAdmissionWorkspace } from "../../workspaces/adt/InpatientAdmissionWorkspace";
import { DoctorCockpit } from "../../workspaces/doctor/DoctorCockpit";
import { WardNursingStation } from "../../workspaces/nursing/WardNursingStation";
import { EDTriageBoard } from "../../workspaces/triage/EDTriageBoard";
import { PharmacyWorkspace } from "../../workspaces/pharmacy/PharmacyWorkspace";
import { DiagnosticsWorkspace } from "../../workspaces/diagnostics/DiagnosticsWorkspace";
import { CashierCounterWorkspace } from "../../workspaces/billing/CashierCounterWorkspace";
import { AdminWorkspace } from "../../workspaces/admin/AdminWorkspace";

export const AppShell: React.FC = () => {
  const { isWorkspaceAllowed, roleDefinition } = usePermissions();
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>(roleDefinition.defaultWorkspace);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

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
          "adt",
          "doctor",
          "nursing",
          "triage",
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
      case "adt":
        return <InpatientAdmissionWorkspace />;
      case "doctor":
        return <DoctorCockpit />;
      case "nursing":
        return <WardNursingStation />;
      case "triage":
        return <EDTriageBoard />;
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
      {/* 1. Global Navigation Bar */}
      <TopNavbar onOpenCommandPalette={() => setIsCommandPaletteOpen(true)} />

      {/* 2. Universal Clinical Patient Safety Banner (CCOW Context) */}
      <PatientSafetyBanner />

      {/* 3. Main Workspace Layout */}
      <div className="flex-1 flex overflow-hidden">
        <Sidebar activeWorkspace={activeWorkspace} onSelectWorkspace={setActiveWorkspace} />
        <main className="flex-1 flex overflow-hidden bg-slate-950">{renderActiveWorkspace()}</main>
      </div>

      {/* 4. Command Palette (Cmd+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onSelectWorkspace={setActiveWorkspace}
      />
    </div>
  );
};

