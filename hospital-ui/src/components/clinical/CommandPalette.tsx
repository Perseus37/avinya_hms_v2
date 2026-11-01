import React, { useEffect, useState, useRef } from "react";
import { Search, User, ArrowRight, LayoutGrid } from "lucide-react";
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
  const [selectedIndex, setSelectedIndex] = useState(0);
  const { selectPatient } = useActivePatient();
  const inputRef = useRef<HTMLInputElement>(null);

  const workspaces: Array<{ id: WorkspaceId; label: string; shortcut: string; altShortcut: string }> = [
    { id: "registration", label: "Patient Registration & Front Desk Intake", shortcut: "R", altShortcut: "Alt+1" },
    { id: "adt", label: "Inpatient Admission & Bed Allocation (ADT)", shortcut: "I", altShortcut: "Alt+2" },
    { id: "doctor", label: "Doctor Clinical Cockpit (OPD)", shortcut: "D", altShortcut: "Alt+3" },
    { id: "nursing", label: "Ward Nursing Station & eMAR", shortcut: "N", altShortcut: "Alt+4" },
    { id: "triage", label: "Emergency & ED Triage Board", shortcut: "E", altShortcut: "Alt+5" },
    { id: "billing", label: "Billing & Cashier Settlement", shortcut: "B", altShortcut: "Alt+6" },
    { id: "pharmacy", label: "Pharmacy & NDPS Register", shortcut: "P", altShortcut: "Alt+7" },
    { id: "diagnostics", label: "Diagnostics & Laboratory LIS", shortcut: "L", altShortcut: "Alt+8" },
    { id: "admin", label: "Executive HUD & Data Inventory", shortcut: "A", altShortcut: "Alt+9" },
  ];

  // Filter workspaces based on search query
  const filteredWorkspaces = searchTerm.trim()
    ? workspaces.filter(
        (ws) =>
          ws.label.toLowerCase().includes(searchTerm.toLowerCase()) ||
          ws.id.toLowerCase().includes(searchTerm.toLowerCase()) ||
          ws.shortcut.toLowerCase() === searchTerm.toLowerCase()
      )
    : workspaces;

  // Total selectable items count
  const totalItems = searchResults.length + filteredWorkspaces.length;

  useEffect(() => {
    if (isOpen) {
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setSearchTerm("");
      setSearchResults([]);
      setSelectedIndex(0);
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
        setSelectedIndex(0);
      } catch (err) {
        console.error("Quick search failed:", err);
      } finally {
        setIsSearching(false);
      }
    }, 180);

    return () => clearTimeout(timer);
  }, [searchTerm]);

  // Keyboard navigation listener (ArrowUp, ArrowDown, Enter, Esc)
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") {
      e.preventDefault();
      onClose();
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (totalItems > 0) {
        setSelectedIndex((prev) => (prev + 1) % totalItems);
      }
      return;
    }

    if (e.key === "ArrowUp") {
      e.preventDefault();
      if (totalItems > 0) {
        setSelectedIndex((prev) => (prev - 1 + totalItems) % totalItems);
      }
      return;
    }

    if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIndex < searchResults.length) {
        // Select patient
        const patient = searchResults[selectedIndex];
        selectPatient(patient.id);
        onClose();
      } else {
        // Select workspace
        const wsIndex = selectedIndex - searchResults.length;
        if (wsIndex >= 0 && wsIndex < filteredWorkspaces.length) {
          onSelectWorkspace(filteredWorkspaces[wsIndex].id);
          onClose();
        }
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 p-4">
      <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm" onClick={onClose} />

      <div className="relative w-full max-w-2xl rounded-2xl bg-slate-900 border border-slate-700 shadow-2xl overflow-hidden z-10 flex flex-col max-h-[75vh]">
        {/* Search Header */}
        <div className="flex items-center px-4 py-3.5 border-b border-slate-800 bg-slate-900/90">
          <Search size={18} className="text-sky-400 mr-3" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search patient by Name, MRN, Phone (or type workspace name)..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyDown={handleKeyDown}
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
              <div className="px-3 py-1 text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center justify-between">
                <span>Patients (MPI Master Patient Index)</span>
                <span className="font-mono text-[10px] text-sky-400">{searchResults.length} Found</span>
              </div>
              {searchResults.map((patient, idx) => {
                const isSelected = selectedIndex === idx;
                return (
                  <div
                    key={patient.id}
                    onClick={() => {
                      selectPatient(patient.id);
                      onClose();
                    }}
                    onMouseEnter={() => setSelectedIndex(idx)}
                    className={`flex items-center justify-between px-3 py-2.5 rounded-xl cursor-pointer transition-colors ${
                      isSelected ? "bg-slate-800/90 ring-1 ring-sky-500/50" : "hover:bg-slate-800/50"
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-sky-950 border border-sky-800 flex items-center justify-center text-sky-400 font-bold text-xs">
                        <User size={14} />
                      </div>
                      <div>
                        <div className="text-sm font-medium text-slate-200 flex items-center gap-2">
                          {patient.full_name}
                          <span className="font-mono text-xs text-sky-400 bg-sky-950 px-1.5 py-0.5 rounded border border-sky-800/60">
                            {patient.mrn}
                          </span>
                        </div>
                        <div className="text-xs text-slate-400 font-mono">
                          {patient.gender} • {patient.age_years !== null ? `${patient.age_years} yrs` : "--"} • Ph: {patient.phone_number || "--"}
                        </div>
                      </div>
                    </div>
                    <div className="text-xs text-slate-500 flex items-center gap-1 font-mono">
                      <span>Select</span> <ArrowRight size={12} />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Workspaces Navigation */}
          {filteredWorkspaces.length > 0 && (
            <div className="py-2">
              <div className="px-3 py-1 text-[11px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1.5">
                <LayoutGrid size={11} className="text-slate-400" />
                <span>Workspaces &amp; Clinical Navigation</span>
              </div>
              {filteredWorkspaces.map((ws, idx) => {
                const itemIndex = searchResults.length + idx;
                const isSelected = selectedIndex === itemIndex;
                return (
                  <div
                    key={ws.id}
                    onClick={() => {
                      onSelectWorkspace(ws.id);
                      onClose();
                    }}
                    onMouseEnter={() => setSelectedIndex(itemIndex)}
                    className={`flex items-center justify-between px-3 py-2 rounded-xl cursor-pointer transition-colors text-sm ${
                      isSelected
                        ? "bg-slate-800/90 text-white ring-1 ring-sky-500/50"
                        : "text-slate-300 hover:text-white hover:bg-slate-800/50"
                    }`}
                  >
                    <span className="font-medium text-xs">{ws.label}</span>
                    <div className="flex items-center gap-1.5 font-mono">
                      <kbd className="px-1.5 py-0.5 bg-slate-950 border border-slate-800 rounded text-[10px] text-sky-400 font-bold">
                        {ws.altShortcut}
                      </kbd>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Empty search fallback */}
          {searchTerm.trim().length > 0 && searchResults.length === 0 && filteredWorkspaces.length === 0 && (
            <div className="py-8 text-center text-xs text-slate-500 font-mono">
              No patients or workspaces matching &quot;{searchTerm}&quot;.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-4 py-2 border-t border-slate-800 bg-slate-950/80 text-[11px] text-slate-500 flex items-center justify-between font-mono">
          <div className="flex items-center gap-3">
            <span>↑↓ Navigate</span>
            <span>↵ Select</span>
            <span>ESC Close</span>
          </div>
          <span className="text-slate-400">Avinya Universal Clinical Command Palette</span>
        </div>
      </div>
    </div>
  );
};
