import React from "react";
import { Pill, ShieldAlert, Download } from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";

export const PharmacyWorkspace: React.FC = () => {
  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Pill className="text-emerald-400" />
            Central Pharmacy & Controlled Substances Vault
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            eRx Verification • DDI Interaction Radar • Schedule H1 & NDPS Dual-Custody Ledger
          </p>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="/api/registers/ndps-ledger?format=csv"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-md bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-200 transition-colors"
          >
            <Download size={13} /> Export NDPS Ledger CSV
          </a>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-3 gap-6 mt-6">
        {/* Prescription Verification Queue */}
        <div className="col-span-2 space-y-4">
          <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
            Pending e-Prescriptions for Dispense
          </h2>

          <div className="space-y-3">
            <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-sm text-slate-100">Rx #9021 — Siddharth Verma</span>
                  <span className="text-xs text-slate-400 ml-2 font-mono">MRN: MRN-2026-0001</span>
                </div>
                <Badge variant="warning" size="sm">Awaiting Dispense</Badge>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-200">Amoxicillin + Clavulanate 625mg</span>
                  <span className="font-mono text-emerald-400">Batch #AMC-2026-B1 • Qty: 10</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-slate-200">Paracetamol 500mg</span>
                  <span className="font-mono text-emerald-400">Batch #PCM-2026-X4 • Qty: 15</span>
                </div>
              </div>

              <div className="flex items-center justify-between pt-2">
                <span className="text-xs text-emerald-400 flex items-center gap-1 font-mono">
                  ✓ Clinical DDI Screening Passed
                </span>
                <Button variant="primary" size="sm">
                  Verify & Dispense (Scan Batch)
                </Button>
              </div>
            </Card>
          </div>
        </div>

        {/* NDPS Narcotics Double-Custody Vault Status */}
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5 text-amber-400">
            <ShieldAlert size={16} /> NDPS Schedule H1 Vault
          </h2>

          <Card className="p-4 bg-slate-900 border-amber-900/40 space-y-3">
            <div className="text-xs text-slate-400">
              Narcotic and psychotropic substances require biometric/witness sign-off for movement.
            </div>

            <div className="space-y-2 font-mono text-xs">
              <div className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800">
                <span>Morphine Sulfate 10mg/mL</span>
                <span className="font-bold text-amber-400">42 amps</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800">
                <span>Fentanyl Citrate 50mcg/mL</span>
                <span className="font-bold text-amber-400">18 amps</span>
              </div>
              <div className="flex items-center justify-between p-2 rounded bg-slate-950 border border-slate-800">
                <span>Midazolam 5mg/mL</span>
                <span className="font-bold text-amber-400">35 amps</span>
              </div>
            </div>

            <Button variant="secondary" size="sm" className="w-full">
              Record Vault Stock Movement
            </Button>
          </Card>
        </div>
      </div>
    </div>
  );
};

