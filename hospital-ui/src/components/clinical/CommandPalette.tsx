import React, { useEffect, useState, useRef } from "react";
import { Search, User, ArrowRight } from "lucide-react";
import { uiApi } from "../../api/uiApi";
import { PatientQuickSearchItem, WorkspaceId } from "../../types";
import { useActivePatient } from "../../core/context/ActivePatientContext";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectWorkspace: (workspace: WorkspaceId) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  isOpen,
  onClose,
  onSelectWorkspace,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<PatientQuickSearchItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const { selectPatient } = useActivePatient();
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setSearchTerm("");
      setSearchResults([]);
    }
  }, [isOpen]);

  // Debounced search on query
  useEffect(() => {
    if (!searchTerm.trim()) {
      setSearchResults([]);
      return;
    }
    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const results = await uiApi.quickSearchPatients(searchTerm);
        setSearchResults(results);
      } catch (err) {
        console.error("Quick search failed:", err);
      } finally {
        setIsSearching(false);
      }
    }, 200);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  if (!isOpen) return null;

  const workspaces: Array<{ id: WorkspaceId; label: string; shortcut: string }> = [
    { id: "registration", label: "Patient Registration & Front Desk Intake", shortcut: "R" },
    { id: "adt", label: "Inpatient Admission & Bed Allocation (ADT)", shortcut: "I" },
    { id: "doctor", label: "Doctor Clinical Cockpit (OPD)", shortcut: "D" },
    { id: "nursing", label: "Ward Nursing & Bed Board", shortcut: "N" },
    { id: "triage", label: "Emergency & ED Triage Board", shortcut: "E" },
    { id: "billing", label: "Billing & Cashier Counter", shortcut: "B" },
    { id: "pharmacy", label: "Pharmacy & NDPS Register", shortcut: "P" },
    { id: "diagnostics", label: "Diagnostics & Laboratory LIS", shortcut: "L" },
    { id: "admin", label: "Executive HUD & Data Inventory", shortcut: "A" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 p-4">
      <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-2xl rounded-xl bg-slate-900 border border-slate-700 shadow-2xl overflow-hidden z-10 flex flex-col max-h-[75vh]">
        {/* Search Header */}
        <div className="flex items-center px-4 py-3.5 border-b border-slate-800 bg-slate-900/90">
          <Search size={18} className="text-slate-400 mr-3" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search patient by Name, MRN, Phone, or ABHA (or jump to workspace)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none"
          />
          {isSearching && (
            <div className="w-4 h-4 border-2 border-sky-400 border-t-transparent rounded-full animate-spin ml-2" />
          )}
        </div>

        {/* Results Body */}
        <div className="overflow-y-auto p-2 divide-y divide-slate-800/50">
          {/* Patient Search Results */}
          {searchResults.length > 0 && (
            <div className="py-2">
              <div className="px-3 py-1 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                Patients (MPI)
              </div>
              {searchResults.map((patient) => (
                <div
                  key={patient.id}
                  onClick={() => {
                    selectPatient(patient.id);
                    onClose();
                  }}
                  className="flex items-center justify-between px-3 py-2.5 rounded-lg hover:bg-slate-800 cursor-pointer transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-full bg-sky-950 border border-sky-800 flex items-center justify-center text-sky-400 font-bold text-xs">
                      <User size={14} />
                    </div>
                    <div>
                      <div className="text-sm font-medium text-slate-200 group-hover:text-sky-400 flex items-center gap-2">
                        {patient.full_name}
                        <span className="font-mono text-xs text-sky-400 bg-sky-950 px-1.5 py-0.2 rounded">
                          {patient.mrn}
                        </span>
                      </div>
                      <div className="text-xs text-slate-400">
                        {patient.gender} • {patient.age_years !== null ? `${patient.age_years} yrs` : "--"} • Ph: {patient.phone_number || "--"}
                      </div>
                    </div>
                  </div>
                  <div className="text-xs text-slate-500 group-hover:text-slate-300 flex items-center gap-1">
                    Select <ArrowRight size={12} />
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Quick Workspaces Navigation */}
          {searchTerm.trim().length === 0 && (
            <div className="py-2">
              <div className="px-3 py-1 text-[11px] font-semibold text-slate-500 uppercase tracking-wider">
                Workspaces Navigation
              </div>
              {workspaces.map((ws) => (
                <div
                  key={ws.id}
                  onClick={() => {
                    onSelectWorkspace(ws.id);
                    onClose();
                  }}
                  className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-slate-800 cursor-pointer transition-colors text-sm text-slate-300 hover:text-white"
                >
                  <span>{ws.label}</span>
                  <kbd className="px-2 py-0.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-400 font-mono">
                    {ws.shortcut}
                  </kbd>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-slate-800 bg-slate-950/80 text-[11px] text-slate-500 flex items-center justify-between">
          <span>Tip: Press ESC to exit</span>
          <span>Avinya Clinical Command Palette</span>
        </div>
      </div>
    </div>
  );
};

