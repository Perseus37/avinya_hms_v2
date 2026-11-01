import React from "react";
import { Microscope, AlertCircle } from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";

export const DiagnosticsWorkspace: React.FC = () => {
  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Microscope className="text-sky-400" />
            Diagnostics & Clinical Laboratory Information System (LIS)
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Specimen Accessioning • HL7 Analyzer Feeds • Critical Delta Check Callouts
          </p>
        </div>
      </div>

      {/* Laboratory Tasks Grid */}
      <div className="grid grid-cols-3 gap-6 mt-6">
        <div className="col-span-2 space-y-4">
          <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
            Pending Orders for Accessioning & Processing
          </h2>

          <div className="space-y-3">
            <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="font-semibold text-sm text-slate-100">Order #LAB-4029 — Siddharth Verma</span>
                  <span className="text-xs text-slate-400 ml-2 font-mono">Sample: EDTA Whole Blood</span>
                </div>
                <Badge variant="info" size="sm">Specimen Collected</Badge>
              </div>

              <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300">Complete Blood Count (CBC) with Differential</span>
                  <span className="font-mono text-sky-400">Barcode: #SMP-88219</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-300">C-Reactive Protein (CRP) Quantitative</span>
                  <span className="font-mono text-sky-400">Barcode: #SMP-88220</span>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <Button variant="outline" size="sm">
                  Reprint Barcode Label
                </Button>
                <Button variant="primary" size="sm">
                  Enter Results / Verify
                </Button>
              </div>
            </Card>
          </div>
        </div>

        {/* Critical Panic Delta Watch */}
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5 text-rose-400">
            <AlertCircle size={16} /> Panic Critical Delta Callouts
          </h2>

          <Card className="p-4 bg-rose-950/20 border-rose-900/60 space-y-3">
            <div className="text-xs text-rose-300">
              Values exceeding critical statutory thresholds require verbal doctor read-back within 15 minutes.
            </div>

            <div className="p-3 rounded-lg bg-slate-900 border border-rose-900/50 space-y-1.5">
              <div className="flex items-center justify-between text-xs font-bold text-rose-400">
                <span>Potassium (K+) Serum</span>
                <span>6.8 mmol/L (HIGH)</span>
              </div>
              <div className="text-[11px] text-slate-400">
                Patient: Ananya Deshmukh (ER-0914) • Reported 5m ago
              </div>
              <Button variant="danger" size="sm" className="w-full text-xs mt-2">
                Document Doctor Verbal Callout
              </Button>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};

