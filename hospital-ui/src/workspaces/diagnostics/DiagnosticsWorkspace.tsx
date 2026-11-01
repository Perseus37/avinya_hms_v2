import React, { useState } from "react";
import { Microscope, AlertCircle, PhoneCall, CheckCircle2, FileCheck, Barcode } from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";

interface LabOrder {
  id: number;
  orderNumber: string;
  patientName: string;
  mrn: string;
  sampleType: string;
  status: "COLLECTED" | "IN_ANALYSIS" | "AUTHORIZED";
  tests: Array<{
    name: string;
    barcode: string;
    result?: string;
    unit?: string;
    referenceRange?: string;
    flag?: "NORMAL" | "HIGH" | "PANIC";
  }>;
}

export const DiagnosticsWorkspace: React.FC = () => {
  const [orders, setOrders] = useState<LabOrder[]>([
    {
      id: 1,
      orderNumber: "LAB-4029",
      patientName: "Siddharth Verma",
      mrn: "MRN-2026-0001",
      sampleType: "EDTA Whole Blood",
      status: "COLLECTED",
      tests: [
        { name: "Complete Blood Count (CBC) - Hemoglobin", barcode: "SMP-88219", result: "14.2", unit: "g/dL", referenceRange: "13.0 - 17.0", flag: "NORMAL" },
        { name: "Total White Blood Cell Count (WBC)", barcode: "SMP-88219", result: "7800", unit: "/cumm", referenceRange: "4000 - 11000", flag: "NORMAL" },
        { name: "Platelet Count", barcode: "SMP-88219", result: "245000", unit: "/cumm", referenceRange: "150000 - 450000", flag: "NORMAL" },
      ],
    },
    {
      id: 2,
      orderNumber: "LAB-4031",
      patientName: "Harish Rao",
      mrn: "ER-0915",
      sampleType: "Serum Gel Tube",
      status: "IN_ANALYSIS",
      tests: [
        { name: "C-Reactive Protein (CRP) Quantitative", barcode: "SMP-88225", result: "42.0", unit: "mg/L", referenceRange: "< 5.0", flag: "HIGH" },
        { name: "Serum Creatinine", barcode: "SMP-88226", result: "1.1", unit: "mg/dL", referenceRange: "0.7 - 1.3", flag: "NORMAL" },
      ],
    },
  ]);

  const [activePanicCallout, setActivePanicCallout] = useState<{
    analyte: string;
    value: string;
    patient: string;
    mrn: string;
    calloutDone: boolean;
  } | null>({
    analyte: "Potassium (K+) Serum",
    value: "6.8 mmol/L (CRITICAL HIGH)",
    patient: "Ananya Deshmukh",
    mrn: "ER-0914",
    calloutDone: false,
  });

  const [isResultModalOpen, setIsResultModalOpen] = useState(false);
  const [selectedOrder, setSelectedOrder] = useState<LabOrder | null>(null);

  // Form values for result entry
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  const [isCalloutModalOpen, setIsCalloutModalOpen] = useState(false);
  const [doctorContacted, setDoctorContacted] = useState("Dr. Sameer Joshi (Emergency Physician)");
  const [readbackConfirmed, setReadbackConfirmed] = useState(false);

  const handleOpenResultModal = (order: LabOrder) => {
    setSelectedOrder(order);
    const initial: Record<string, string> = {};
    order.tests.forEach((t) => {
      initial[t.name] = t.result || "";
    });
    setTestResults(initial);
    setIsResultModalOpen(true);
  };

  const handleSaveResults = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedOrder) return;

    setOrders((prev) =>
      prev.map((o) =>
        o.id === selectedOrder.id
          ? {
              ...o,
              status: "AUTHORIZED",
              tests: o.tests.map((t) => ({
                ...t,
                result: testResults[t.name] || t.result,
              })),
            }
          : o
      )
    );

    setIsResultModalOpen(false);
    alert(`Results for order ${selectedOrder.orderNumber} authorized and pushed to EMR.`);
  };

  const advanceOrderStatus = (orderId: number) => {
    setOrders((prev) =>
      prev.map((o) => {
        if (o.id !== orderId) return o;
        const nextStatus =
          o.status === "COLLECTED"
            ? "IN_ANALYSIS"
            : o.status === "IN_ANALYSIS"
            ? "AUTHORIZED"
            : "AUTHORIZED";
        return { ...o, status: nextStatus };
      })
    );
  };

  const handleConfirmCallout = (e: React.FormEvent) => {
    e.preventDefault();
    if (!readbackConfirmed) {
      alert("Please check the verbal read-back confirmation box.");
      return;
    }

    if (activePanicCallout) {
      setActivePanicCallout({ ...activePanicCallout, calloutDone: true });
    }
    setIsCalloutModalOpen(false);
    alert("Critical panic delta verbal callout successfully recorded in audit log.");
  };

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
            Specimen Accessioning • Auto-Analyzer HL7 Feeds • Panic Critical Delta Callout Documentation
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Badge variant="neutral" size="sm" className="font-mono">
            HL7 ASTM Analyzer Feed: Connected (Port 5001)
          </Badge>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-3 gap-6 mt-6">
        {/* Laboratory Tasks Grid */}
        <div className="col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Accessioning & Processing Queue ({orders.length})
            </h2>
          </div>

          <div className="space-y-3">
            {orders.map((order) => (
              <Card key={order.id} className="p-4 bg-slate-900 border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="font-semibold text-sm text-slate-100">
                      Order #{order.orderNumber} — {order.patientName}
                    </span>
                    <span className="text-xs text-slate-400 ml-2 font-mono">
                      Sample: {order.sampleType} • {order.mrn}
                    </span>
                  </div>
                  <Badge
                    variant={
                      order.status === "AUTHORIZED"
                        ? "success"
                        : order.status === "IN_ANALYSIS"
                        ? "warning"
                        : "info"
                    }
                    size="sm"
                  >
                    {order.status === "COLLECTED"
                      ? "Specimen Collected"
                      : order.status === "IN_ANALYSIS"
                      ? "In Analyzer"
                      : "Verified & Released"}
                  </Badge>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                  {order.tests.map((t, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between text-xs pb-1.5 border-b border-slate-900 last:border-0 last:pb-0"
                    >
                      <div>
                        <span className="text-slate-300 font-medium">{t.name}</span>
                        <span className="text-[10px] text-slate-500 font-mono ml-2">
                          (Ref: {t.referenceRange} {t.unit})
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {t.result ? (
                          <span
                            className={`font-mono font-bold ${
                              t.flag === "HIGH"
                                ? "text-amber-400"
                                : t.flag === "PANIC"
                                ? "text-rose-400"
                                : "text-emerald-400"
                            }`}
                          >
                            {t.result} {t.unit}
                          </span>
                        ) : (
                          <span className="text-slate-500 italic">Pending</span>
                        )}
                        <span className="font-mono text-[10px] text-sky-400">
                          #{t.barcode}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-end gap-3 pt-2">
                  {order.status === "COLLECTED" && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => advanceOrderStatus(order.id)}
                      className="text-xs flex items-center gap-1"
                    >
                      <Barcode size={13} /> Receive & Load to Analyzer
                    </Button>
                  )}

                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => handleOpenResultModal(order)}
                    className="text-xs flex items-center gap-1"
                  >
                    <FileCheck size={13} /> {order.status === "AUTHORIZED" ? "View / Edit Results" : "Enter Results & Release"}
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* Critical Panic Delta Watch */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-rose-400 uppercase tracking-wider flex items-center gap-1.5">
              <AlertCircle size={16} /> Panic Critical Delta Callouts
            </h2>
            <Badge variant="danger" size="sm">
              Urgent (15m SLA)
            </Badge>
          </div>

          {activePanicCallout && (
            <Card
              className={`p-4 border space-y-3 ${
                activePanicCallout.calloutDone
                  ? "bg-slate-900 border-slate-800"
                  : "bg-rose-950/20 border-rose-900/60"
              }`}
            >
              <div className="text-xs text-rose-300 leading-relaxed">
                Values exceeding critical life-threatening thresholds require immediate verbal read-back to attending physician under NABH standards.
              </div>

              <div className="p-3 rounded-lg bg-slate-900 border border-rose-900/50 space-y-1.5">
                <div className="flex items-center justify-between text-xs font-bold text-rose-400">
                  <span>{activePanicCallout.analyte}</span>
                  <span className="font-mono">{activePanicCallout.value}</span>
                </div>
                <div className="text-[11px] text-slate-400">
                  Patient: {activePanicCallout.patient} ({activePanicCallout.mrn})
                </div>
                <div className="text-[10px] text-slate-500 font-mono">
                  Reported: 6 mins ago • Specimen: Heparinized Plasma
                </div>

                {activePanicCallout.calloutDone ? (
                  <div className="mt-3 p-2 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 text-xs flex items-center gap-2">
                    <CheckCircle2 size={14} /> Verbal Read-Back Confirmed & Documented
                  </div>
                ) : (
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => setIsCalloutModalOpen(true)}
                    className="w-full text-xs mt-2 flex items-center justify-center gap-1.5"
                  >
                    <PhoneCall size={13} /> Document Doctor Verbal Callout
                  </Button>
                )}
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Modal: Enter Results */}
      {selectedOrder && (
        <Modal
          isOpen={isResultModalOpen}
          onClose={() => setIsResultModalOpen(false)}
          title={`Enter / Verify Laboratory Analyte Results — ${selectedOrder.orderNumber}`}
        >
          <form onSubmit={handleSaveResults} className="space-y-4">
            <div className="text-xs text-slate-400">
              Patient: <strong className="text-slate-200">{selectedOrder.patientName}</strong> ({selectedOrder.mrn})
            </div>

            <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
              {selectedOrder.tests.map((t, idx) => (
                <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                  <div className="flex items-center justify-between text-xs font-semibold text-slate-200">
                    <span>{t.name}</span>
                    <span className="font-mono text-slate-500 text-[11px]">
                      Ref: {t.referenceRange} {t.unit}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      required
                      value={testResults[t.name] || ""}
                      onChange={(e) =>
                        setTestResults({ ...testResults, [t.name]: e.target.value })
                      }
                      className="flex-1 bg-slate-900 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                    />
                    <span className="text-xs font-mono text-slate-400">{t.unit}</span>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsResultModalOpen(false)}
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm">
                Verify & Authorize Report
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: Doctor Callout Documentation */}
      <Modal
        isOpen={isCalloutModalOpen}
        onClose={() => setIsCalloutModalOpen(false)}
        title="Document Critical Panic Delta Verbal Callout"
      >
        <form onSubmit={handleConfirmCallout} className="space-y-4">
          <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-900 text-xs text-rose-300 font-mono">
            Analyte: <strong>{activePanicCallout?.analyte} = {activePanicCallout?.value}</strong>
            <br />
            Patient: {activePanicCallout?.patient} ({activePanicCallout?.mrn})
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Physician / Resident Contacted
            </label>
            <input
              type="text"
              required
              value={doctorContacted}
              onChange={(e) => setDoctorContacted(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-rose-500"
            />
          </div>

          <div className="flex items-center gap-2 p-2.5 rounded bg-slate-950 border border-slate-800">
            <input
              type="checkbox"
              id="readback"
              checked={readbackConfirmed}
              onChange={(e) => setReadbackConfirmed(e.target.checked)}
              className="rounded bg-slate-900 border-slate-700 text-rose-500 focus:ring-rose-500"
            />
            <label htmlFor="readback" className="text-xs text-slate-300 cursor-pointer">
              I certify that the physician repeated back the critical value verbally and acknowledged immediate intervention.
            </label>
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsCalloutModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="danger" size="sm">
              Save Verbal Callout Log
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
