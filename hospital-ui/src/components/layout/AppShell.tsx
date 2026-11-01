import React, { useState, useEffect } from "react";
import { WorkspaceId } from "../../types";
import { TopNavbar } from "./TopNavbar";
import { Sidebar } from "./Sidebar";
import { PatientSafetyBanner } from "../clinical/PatientSafetyBanner";
import { CommandPalette } from "../clinical/CommandPalette";

import { DoctorCockpit } from "../../workspaces/doctor/DoctorCockpit";
import { WardNursingStation } from "../../workspaces/nursing/WardNursingStation";
import { EDTriageBoard } from "../../workspaces/triage/EDTriageBoard";
import { PharmacyWorkspace } from "../../workspaces/pharmacy/PharmacyWorkspace";
import { DiagnosticsWorkspace } from "../../workspaces/diagnostics/DiagnosticsWorkspace";
import { CashierCounterWorkspace } from "../../workspaces/billing/CashierCounterWorkspace";
import { AdminWorkspace } from "../../workspaces/admin/AdminWorkspace";

export const AppShell: React.FC = () => {
  const [activeWorkspace, setActiveWorkspace] = useState<WorkspaceId>("doctor");
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);

  // Global Keyboard Listener for Cmd+K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsCommandPaletteOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const renderActiveWorkspace = () => {
    switch (activeWorkspace) {
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
        return <AdminWorkspace />;
      default:
        return <DoctorCockpit />;
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

