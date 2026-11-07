import React, { useEffect, useState, useRef } from "react";
import { Search, User, ArrowRight, LayoutGrid } from "lucide-react";
import { uiApi } from "../../api/uiApi";
import { PatientQuickSearchItem, WorkspaceId } from "../../types";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { usePermissions } from "../../core/context/PermissionsContext";

interface CommandPaletteProps {
  isOpen: boolean;
  onClose: () => void;
  onSelectWorkspace: (workspace: WorkspaceId) => void;
}

export const CommandPalette: React.FC<CommandPaletteProps> = ({ isOpen, onClose, onSelectWorkspace }) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [searchResults, setSearchResults] = useState<PatientQuickSearchItem[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const { selectPatient } = useActivePatient();
  const { isWorkspaceAllowed } = usePermissions();
  const inputRef = useRef<HTMLInputElement>(null);

  const workspaces: Array<{ id: WorkspaceId; label: string; shortcut: string; altShortcut: string }> = [
    { id: "overview", label: "Hospital Operations Overview", shortcut: "O", altShortcut: "Alt+0" },
    { id: "registration", label: "Patient Registration & Front Desk Intake", shortcut: "R", altShortcut: "Alt+1" },
    { id: "patient-record", label: "Patient 360 & Longitudinal Care Timeline", shortcut: "P360", altShortcut: "Alt+P" },
    { id: "opd-queue", label: "OPD Command Center & Queue Board", shortcut: "Q", altShortcut: "Alt+Q" },
    { id: "adt", label: "Inpatient Admission & Bed Allocation (ADT)", shortcut: "I", altShortcut: "Alt+2" },
    { id: "doctor", label: "Doctor Clinical Cockpit (OPD)", shortcut: "D", altShortcut: "Alt+3" },
    { id: "nursing", label: "Ward Nursing Station & eMAR", shortcut: "N", altShortcut: "Alt+4" },
    { id: "triage", label: "Emergency & ED Triage Board", shortcut: "E", altShortcut: "Alt+5" },
    { id: "surgery", label: "Operating Theatre (OT) & Surgical Suite", shortcut: "S", altShortcut: "Alt+S" },
    { id: "blood-bank", label: "Blood Bank & Transfusion Medicine", shortcut: "BB", altShortcut: "Alt+B" },
    { id: "pharmacy", label: "Pharmacy & NDPS Register", shortcut: "P", altShortcut: "Alt+6" },
    { id: "diagnostics", label: "Diagnostics & Laboratory LIS", shortcut: "L", altShortcut: "Alt+7" },
    { id: "billing", label: "Billing & Cashier Settlement", shortcut: "B", altShortcut: "Alt+8" },
    { id: "infection-control", label: "Infection Prevention & Antimicrobial Stewardship", shortcut: "IC", altShortcut: "Alt+I" },
    { id: "biomedical", label: "Biomedical Engineering & Medical Asset Management", shortcut: "BME", altShortcut: "Alt+M" },
    { id: "admin", label: "Hospital Administration & Configuration", shortcut: "A", altShortcut: "Alt+9" },
  ];

  const allowedWorkspaces = workspaces.filter((ws) => isWorkspaceAllowed(ws.id));
  const filteredWorkspaces = searchTerm.trim()
    ? allowedWorkspaces.filter((ws) => ws.label.toLowerCase().includes(searchTerm.toLowerCase()) || ws.id.toLowerCase().includes(searchTerm.toLowerCase()) || ws.shortcut.toLowerCase() === searchTerm.toLowerCase())
    : allowedWorkspaces;

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

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); if (totalItems > 0) setSelectedIndex((prev) => (prev + 1) % totalItems); return; }
    if (e.key === "ArrowUp") { e.preventDefault(); if (totalItems > 0) setSelectedIndex((prev) => (prev - 1 + totalItems) % totalItems); return; }
    if (e.key === "Enter") {
      e.preventDefault();
      if (selectedIndex < searchResults.length) {
        const patient = searchResults[selectedIndex];
        selectPatient(patient.id);
        onSelectWorkspace("patient-record");
        onClose();
      } else {
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
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-slate-950/10 pt-20 p-4">
      <div className="fixed inset-0 bg-slate-950/25 backdrop-blur-sm" onClick={onClose} />
      <div className="relative z-10 flex max-h-[75vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="flex items-center border-b border-slate-200 px-4 py-3.5">
          <Search size={18} className="mr-3 text-slate-500" />
          <input ref={inputRef} type="text" placeholder="Search patient by name, MRN, phone, or workspace..." value={searchTerm} onChange={(e) => setSearchTerm(e.target.value)} onKeyDown={handleKeyDown} className="w-full bg-transparent text-sm text-slate-900 placeholder-slate-400 focus:outline-none" />
          {isSearching && <div className="ml-2 h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-700" />}
        </div>

        <div className="divide-y divide-slate-100 overflow-y-auto p-2">
          {searchResults.length > 0 && <div className="py-2">
            <div className="flex items-center justify-between px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500"><span>Patients</span><span className="text-[10px] text-slate-400">{searchResults.length} found</span></div>
            {searchResults.map((patient, idx) => {
              const isSelected = selectedIndex === idx;
              return <div key={patient.id} onClick={() => { selectPatient(patient.id); onSelectWorkspace("patient-record"); onClose(); }} onMouseEnter={() => setSelectedIndex(idx)} className={`flex cursor-pointer items-center justify-between rounded-xl px-3 py-2.5 transition-colors ${isSelected ? "bg-slate-100 ring-1 ring-slate-200" : "hover:bg-slate-50"}`}>
                <div className="flex items-center gap-3"><div className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-600"><User size={14} /></div><div><div className="flex items-center gap-2 text-sm font-medium text-slate-800">{patient.full_name}<span className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-xs text-slate-600">{patient.mrn}</span></div><div className="text-xs text-slate-500">{patient.gender} · {patient.age_years !== null ? `${patient.age_years} yrs` : "--"} · Ph: {patient.phone_number || "--"}</div></div></div>
                <div className="flex items-center gap-1 text-xs text-slate-400">Select <ArrowRight size={12} /></div>
              </div>;
            })}
          </div>}

          {filteredWorkspaces.length > 0 && <div className="py-2">
            <div className="flex items-center gap-1.5 px-3 py-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500"><LayoutGrid size={11} />Workspaces</div>
            {filteredWorkspaces.map((ws, idx) => {
              const itemIndex = searchResults.length + idx;
              const isSelected = selectedIndex === itemIndex;
              return <div key={ws.id} onClick={() => { onSelectWorkspace(ws.id); onClose(); }} onMouseEnter={() => setSelectedIndex(itemIndex)} className={`flex cursor-pointer items-center justify-between rounded-xl px-3 py-2.5 text-sm transition-colors ${isSelected ? "bg-slate-100 text-slate-900 ring-1 ring-slate-200" : "text-slate-600 hover:bg-slate-50"}`}><span className="text-xs font-medium">{ws.label}</span><kbd className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-[10px] text-slate-500">{ws.altShortcut}</kbd></div>;
            })}
          </div>}

          {searchTerm.trim().length > 0 && searchResults.length === 0 && filteredWorkspaces.length === 0 && <div className="py-8 text-center text-xs text-slate-500">No patients or workspaces matching &quot;{searchTerm}&quot;.</div>}
        </div>
        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-2 text-[11px] text-slate-500"><div className="flex items-center gap-3"><span>↑↓ Navigate</span><span>↵ Select</span><span>ESC Close</span></div><span className="text-slate-400">Avinya Command Palette</span></div>
      </div>
    </div>
  );
};
