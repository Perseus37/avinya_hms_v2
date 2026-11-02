import React, { useState } from "react";
import { Microscope, AlertCircle, PhoneCall, CheckCircle2, FileCheck, Barcode, Printer, PlusCircle } from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { printDocument } from "../../utils/printDocument";

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
  const { hospitalProfile, getPrinterForCategory } = useHospitalConfig();
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

  // New Walk-in Lab Order Intake State
  const [isNewOrderModalOpen, setIsNewOrderModalOpen] = useState(false);
  const [newPatientName, setNewPatientName] = useState("Vijay Sharma");
  const [newMrn, setNewMrn] = useState("MRN-2026-0009");
  const [newSampleType, setNewSampleType] = useState("Serum Gel Tube (Yellow)");
  const [newTestCategory, setNewTestCategory] = useState("Biochemistry");
  const [newTestName, setNewTestName] = useState("Lipid Profile (Total Cholesterol, HDL, LDL, Triglycerides)");
  const [newRefRange, setNewRefRange] = useState("< 200");
  const [newUnit, setNewUnit] = useState("mg/dL");

  // Print Lab Report State
  const [isPrintReportModalOpen, setIsPrintReportModalOpen] = useState(false);
  const [reportOrder, setReportOrder] = useState<LabOrder | null>(null);

  const handleCreateLabOrder = (e: React.FormEvent) => {
    e.preventDefault();
    const newId = Date.now();
    const barcodeNum = `SMP-${Math.floor(10000 + Math.random() * 90000)}`;
    const newOrder: LabOrder = {
      id: newId,
      orderNumber: `LAB-${Math.floor(4100 + Math.random() * 900)}`,
      patientName: newPatientName,
      mrn: newMrn,
      sampleType: `${newSampleType} [${newTestCategory}]`,
      status: "COLLECTED",
      tests: [
        {
          name: newTestName,
          barcode: barcodeNum,
          result: "",
          unit: newUnit,
          referenceRange: newRefRange,
          flag: "NORMAL",
        },
      ],
    };

    setOrders([newOrder, ...orders]);
    setIsNewOrderModalOpen(false);
  };

  const handleOpenPrintReport = (order: LabOrder) => {
    setReportOrder(order);
    setIsPrintReportModalOpen(true);
  };

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

  const handlePrintLabReport = (order: LabOrder) => {
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 750px; margin: 0 auto; border: 1px solid #333; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
          <h2 style="margin: 0; font-size: 20px; text-transform: uppercase;">${hospitalProfile.name}</h2>
          <div style="font-size: 12px; font-weight: bold; color: #0284c7; margin-top: 2px;">NABL ACCREDITED CENTRAL CLINICAL LABORATORY REPORT</div>
          <div style="font-size: 10px; color: #555;">${hospitalProfile.accreditation} • Phone: ${hospitalProfile.phone}</div>
        </div>
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 12px; margin-bottom: 14px;">
          <div><b>Patient:</b> ${order.patientName.toUpperCase()}</div>
          <div><b>UHID / MRN:</b> ${order.mrn}</div>
          <div><b>Lab Order No:</b> ${order.orderNumber}</div>
        </div>
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 11px; margin-bottom: 16px;">
          <div><b>Specimen Type:</b> ${order.sampleType}</div>
          <div><b>Status:</b> ${order.status}</div>
          <div><b>Date:</b> ${new Date().toLocaleDateString()}</div>
        </div>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px; margin-bottom: 20px;">
          <thead>
            <tr style="background: #f1f5f9; border-bottom: 2px solid #cbd5e1; text-align: left;">
              <th style="padding: 8px;">Investigation / Analyte</th>
              <th style="padding: 8px;">Result Value</th>
              <th style="padding: 8px;">Reference Range</th>
              <th style="padding: 8px;">Unit</th>
              <th style="padding: 8px;">Barcode</th>
            </tr>
          </thead>
          <tbody>
            ${order.tests.map((t) => `
              <tr style="border-bottom: 1px solid #e2e8f0;">
                <td style="padding: 8px; font-weight: bold;">${t.name}</td>
                <td style="padding: 8px; font-family: monospace; font-weight: bold; color: ${t.flag === "PANIC" ? "#dc2626" : t.flag === "HIGH" ? "#ea580c" : "#0f172a"};">
                  ${t.result || "Verified Normal"}
                </td>
                <td style="padding: 8px; color: #64748b;">${t.referenceRange || "--"}</td>
                <td style="padding: 8px; color: #64748b;">${t.unit || "--"}</td>
                <td style="padding: 8px; font-family: monospace; font-size: 10px;">${t.barcode}</td>
              </tr>
            `).join("")}
          </tbody>
        </table>
        <div style="margin-top: 50px; display: flex; justify-content: space-between; font-size: 11px;">
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Medical Laboratory Technologist</div>
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Dr. Anjali Mehta, MD (Pathology)<br/><span style="font-size: 9px; color: #64748b;">Authorized Pathologist • Reg #MC-44910</span></div>
        </div>
      </div>
    `;
    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(html, {
      title: `Lab_Report_${order.orderNumber}`,
      docType: "CLINICAL_SUMMARY",
      printerDevice: a4Printer,
    });
  };

  const handlePrintSpecimenTubeLabel = (order: LabOrder) => {
    const labPrinter = getPrinterForCategory("LAB_LABEL");
    const barcodeCode = order.tests[0]?.barcode || `SMP-${order.orderNumber}`;
    const testNames = order.tests.map((t) => t.name.replace(/\(.*\)/g, "").trim()).join(", ");

    const html = `
      <div style="width: 100%; height: 100%; padding: 1mm 2mm; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; display: flex; flex-direction: column; justify-content: space-between;">
        <div style="display: flex; justify-content: space-between; align-items: baseline; border-bottom: 1px solid #000; padding-bottom: 1px;">
          <span style="font-weight: 900; font-size: 9px; text-transform: uppercase;">${hospitalProfile.name.slice(0, 18)}</span>
          <span style="font-size: 8px; font-weight: bold; font-family: monospace;">${order.mrn}</span>
        </div>
        <div>
          <div style="font-weight: 900; font-size: 11px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${order.patientName.toUpperCase()}</div>
          <div style="font-size: 8px; font-weight: bold; color: #333;">${order.sampleType}</div>
          <div style="font-size: 7.5px; color: #555; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${testNames}</div>
        </div>
        <div style="text-align: center; border-top: 1px dashed #666; padding-top: 1px;">
          <div style="font-family: monospace; font-size: 11px; font-weight: 900; letter-spacing: 2px;">||| | |||| || |||</div>
          <div style="font-family: monospace; font-size: 8.5px; font-weight: bold;">*${barcodeCode}*</div>
        </div>
      </div>
    `;

    printDocument(html, {
      title: `TubeLabel_${barcodeCode}`,
      docType: "LAB_REPORT",
      printerDevice: labPrinter,
    });
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
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsNewOrderModalOpen(true)}
              className="flex items-center gap-1.5 text-xs font-semibold"
            >
              <PlusCircle size={14} /> Intake Walk-in Specimen
            </Button>
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

                <div className="flex items-center justify-end gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePrintSpecimenTubeLabel(order)}
                    className="text-xs flex items-center gap-1 text-sky-400 hover:text-sky-300 border-sky-800/80"
                    title="Print Barcode Specimen Tube Label (50x25mm Labeler)"
                  >
                    <Barcode size={13} /> Tube Label
                  </Button>

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

                  {order.status === "AUTHORIZED" && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleOpenPrintReport(order)}
                      className="text-xs flex items-center gap-1 text-slate-300 hover:text-white"
                    >
                      <Printer size={13} /> Print Lab Report
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

      {/* Modal: Intake Walk-in Lab Specimen */}
      <Modal
        isOpen={isNewOrderModalOpen}
        onClose={() => setIsNewOrderModalOpen(false)}
        title="Intake Walk-in Laboratory Specimen & Order Investigation"
      >
        <form onSubmit={handleCreateLabOrder} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Patient Full Name</label>
              <input
                type="text"
                required
                value={newPatientName}
                onChange={(e) => setNewPatientName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500 font-semibold"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">MRN / UHID</label>
              <input
                type="text"
                required
                value={newMrn}
                onChange={(e) => setNewMrn(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Laboratory Discipline</label>
              <select
                value={newTestCategory}
                onChange={(e) => setNewTestCategory(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
              >
                <option value="Biochemistry">Clinical Biochemistry</option>
                <option value="Hematology">Hematology & Coagulation</option>
                <option value="Microbiology">Microbiology & Serology</option>
                <option value="Histopathology">Histopathology / Cytology</option>
                <option value="Immunology">Clinical Immunology</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Specimen Collection Tube</label>
              <select
                value={newSampleType}
                onChange={(e) => setNewSampleType(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
              >
                <option value="Serum Gel Tube (Yellow)">SST / Serum Gel Tube (Yellow Top)</option>
                <option value="EDTA Whole Blood (Lavender)">EDTA K2/K3 Whole Blood (Lavender Top)</option>
                <option value="Sodium Citrate 3.2% (Light Blue)">Sodium Citrate Coagulation (Light Blue)</option>
                <option value="Sodium Fluoride (Grey)">Fluoride Glycolysis Inhibitor (Grey Top)</option>
                <option value="Sterile Urine Container">Sterile Mid-Stream Urine Container</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Investigation Name / Test Panel</label>
            <input
              type="text"
              required
              value={newTestName}
              onChange={(e) => setNewTestName(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500 font-semibold"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Standard Reference Range</label>
              <input
                type="text"
                required
                value={newRefRange}
                onChange={(e) => setNewRefRange(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Measurement Unit</label>
              <input
                type="text"
                required
                value={newUnit}
                onChange={(e) => setNewUnit(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsNewOrderModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" className="flex items-center gap-1.5 font-semibold">
              <Barcode size={13} /> Accession & Generate Barcode
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Printable Laboratory Report Slip */}
      {reportOrder && (
        <Modal
          isOpen={isPrintReportModalOpen}
          onClose={() => setIsPrintReportModalOpen(false)}
          title={`Clinical Diagnostic Report — ${reportOrder.orderNumber}`}
        >
          <div className="space-y-4">
            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3 font-mono text-xs">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <div>
                  <span className="text-slate-400 text-[10px] uppercase block">Department of Pathology & LIS</span>
                  <span className="font-bold text-emerald-400 text-sm">ACCESSION #{reportOrder.orderNumber}</span>
                </div>
                <div className="text-right">
                  <span className="text-slate-400 text-[10px] uppercase block">Status</span>
                  <Badge variant="success" size="sm">NABL Authorized</Badge>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-slate-500 text-[10px] block">Patient Name</span>
                  <span className="text-slate-200 font-semibold">{reportOrder.patientName}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">UHID / MRN</span>
                  <span className="text-slate-200">{reportOrder.mrn}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Specimen Type</span>
                  <span className="text-slate-200">{reportOrder.sampleType}</span>
                </div>
                <div>
                  <span className="text-slate-500 text-[10px] block">Report Date</span>
                  <span className="text-slate-200">{new Date().toISOString().substring(0, 10)}</span>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800 space-y-2">
                <div className="text-[10px] text-slate-400 uppercase font-bold">Investigation Results</div>
                <div className="bg-slate-900 rounded-lg p-2.5 space-y-2">
                  {reportOrder.tests.map((t, idx) => (
                    <div key={idx} className="flex items-center justify-between text-xs pb-1 border-b border-slate-800 last:border-0 last:pb-0">
                      <div>
                        <div className="text-slate-200 font-medium">{t.name}</div>
                        <div className="text-[10px] text-slate-500">Ref: {t.referenceRange} {t.unit}</div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-sky-400 font-mono">{t.result || "Normal"} {t.unit}</div>
                        <div className="text-[9px] text-slate-500 font-mono">Barcode: {t.barcode}</div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[10px] text-slate-500">
                <span>Verified by: Dr. Anjali Mehta, MD (Pathology)</span>
                <span>Reg #MC-44910</span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => reportOrder && handlePrintLabReport(reportOrder)}
                  className="flex items-center gap-1.5"
                >
                  <Printer size={13} /> Print Laboratory Report
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => reportOrder && handlePrintSpecimenTubeLabel(reportOrder)}
                  className="flex items-center gap-1.5 text-sky-400 hover:text-sky-300 border-sky-800/80"
                >
                  <Barcode size={13} /> Print Specimen Tube Label
                </Button>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsPrintReportModalOpen(false)}
              >
                Close
              </Button>
            </div>
          </div>
        </Modal>
      )}

    </div>
  );
};
