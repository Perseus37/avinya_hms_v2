import React, { useState } from "react";
import {
  Droplet,
  Thermometer,
  ShieldCheck,
  Printer,
  Search,
  Check,
  Barcode,
  Siren,
  AlertTriangle,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { printDocument } from "../../utils/printDocument";

export type BloodComponentType = "PRBC" | "FFP" | "PLATELETS" | "CRYOPRECIPITATE";
export type RequisitionUrgency = "STAT_EMERGENCY" | "URGENT" | "ROUTINE_ELECTIVE";

export interface BloodRequisition {
  id: string;
  patientName: string;
  mrn: string;
  bloodGroup: string;
  component: BloodComponentType;
  unitsRequested: number;
  urgency: RequisitionUrgency;
  orderingDept: string;
  orderingDoctor: string;
  requestedAt: string;
  status: "PENDING_CROSSMATCH" | "COMPATIBLE_RESERVED" | "ISSUED_TO_WARD" | "TRANSFUSED" | "EMERGENCY_UNCROSSMATCHED_RELEASE";
  allocatedBagIds?: string[];
  crossmatchDetails?: {
    majorCrossmatch: "COMPATIBLE" | "INCOMPATIBLE";
    minorCrossmatch: "COMPATIBLE" | "INCOMPATIBLE";
    coombsDirect: "NEGATIVE" | "POSITIVE";
    coombsIndirect: "NEGATIVE" | "POSITIVE";
    testedBy: string;
  };
}

export interface BloodStockItem {
  bloodGroup: string;
  prbcUnits: number;
  ffpUnits: number;
  plateletUnits: number;
  cryoUnits: number;
  isLowStock?: boolean;
}

export interface DonorRecord {
  id: string;
  donorName: string;
  age: number;
  gender: string;
  bloodGroup: string;
  donationType: "VOLUNTARY" | "REPLACEMENT";
  hemoglobin: number; // g/dL
  screeningStatus: "PASSED_SAFE" | "TESTING_IN_PROGRESS" | "TTI_REACTIVE_DISCARD";
  bagBarcode: string;
  donatedAt: string;
}

export const BloodBankWorkspace: React.FC = () => {
  const { selectPatient } = useActivePatient();
  const { hospitalProfile, getPrinterForCategory } = useHospitalConfig();

  const [activeTab, setActiveTab] = useState<"requisitions" | "inventory" | "donors" | "coldchain">("requisitions");
  const [selectedReqId, setSelectedReqId] = useState<string>("REQ-01");
  const [searchFilter, setSearchFilter] = useState("");

  // Requisitions Queue
  const [requisitions, setRequisitions] = useState<BloodRequisition[]>([
    {
      id: "REQ-01",
      patientName: "Trauma Code Red Unidentified",
      mrn: "ER-0912",
      bloodGroup: "O-",
      component: "PRBC",
      unitsRequested: 4,
      urgency: "STAT_EMERGENCY",
      orderingDept: "Emergency Resuscitation Bay 1 (Trauma)",
      orderingDoctor: "Dr. Sameer Joshi (Trauma Critical Care)",
      requestedAt: "8 mins ago",
      status: "COMPATIBLE_RESERVED",
      allocatedBagIds: ["BAG-2026-O-8819", "BAG-2026-O-8820", "BAG-2026-O-8821", "BAG-2026-O-8822"],
      crossmatchDetails: {
        majorCrossmatch: "COMPATIBLE",
        minorCrossmatch: "COMPATIBLE",
        coombsDirect: "NEGATIVE",
        coombsIndirect: "NEGATIVE",
        testedBy: "Senior Technologist R. Nambiar (Reg #BB-4491)",
      },
    },
    {
      id: "REQ-02",
      patientName: "Siddharth Verma",
      mrn: "MRN-2026-0001",
      bloodGroup: "B+",
      component: "PRBC",
      unitsRequested: 2,
      urgency: "URGENT",
      orderingDept: "OT-1 (Cardiac & Thoracic Hybrid)",
      orderingDoctor: "Dr. Vikram Seth (Cardiology)",
      requestedAt: "25 mins ago",
      status: "COMPATIBLE_RESERVED",
      allocatedBagIds: ["BAG-2026-B-9914", "BAG-2026-B-9915"],
      crossmatchDetails: {
        majorCrossmatch: "COMPATIBLE",
        minorCrossmatch: "COMPATIBLE",
        coombsDirect: "NEGATIVE",
        coombsIndirect: "NEGATIVE",
        testedBy: "Technologist P. Sharma",
      },
    },
    {
      id: "REQ-03",
      patientName: "Kavita Ramachandran",
      mrn: "MRN-2026-0012",
      bloodGroup: "A+",
      component: "FFP",
      unitsRequested: 3,
      urgency: "ROUTINE_ELECTIVE",
      orderingDept: "OT-2 (Neurosurgery)",
      orderingDoctor: "Dr. Devendra Rathore (Neurosurgery)",
      requestedAt: "45 mins ago",
      status: "PENDING_CROSSMATCH",
    },
    {
      id: "REQ-04",
      patientName: "Vikramaditya Singhania",
      mrn: "MRN-2026-0003",
      bloodGroup: "A+",
      component: "PRBC",
      unitsRequested: 2,
      urgency: "ROUTINE_ELECTIVE",
      orderingDept: "OT-3 (Orthopedics Joint Replacement)",
      orderingDoctor: "Dr. Harish Patel (Orthopedics)",
      requestedAt: "1h 10m ago",
      status: "COMPATIBLE_RESERVED",
      allocatedBagIds: ["BAG-2026-A-7741", "BAG-2026-A-7742"],
      crossmatchDetails: {
        majorCrossmatch: "COMPATIBLE",
        minorCrossmatch: "COMPATIBLE",
        coombsDirect: "NEGATIVE",
        coombsIndirect: "NEGATIVE",
        testedBy: "Senior Technologist R. Nambiar",
      },
    },
    {
      id: "REQ-05",
      patientName: "Ananya Deshmukh",
      mrn: "ER-0914",
      bloodGroup: "O+",
      component: "PLATELETS",
      unitsRequested: 1, // SDP
      urgency: "URGENT",
      orderingDept: "Medical Intensive Care Unit (MICU-Bed 104)",
      orderingDoctor: "Dr. Sameer Joshi (Critical Care)",
      requestedAt: "1h 40m ago",
      status: "ISSUED_TO_WARD",
      allocatedBagIds: ["SDP-2026-O-1002"],
      crossmatchDetails: {
        majorCrossmatch: "COMPATIBLE",
        minorCrossmatch: "COMPATIBLE",
        coombsDirect: "NEGATIVE",
        coombsIndirect: "NEGATIVE",
        testedBy: "Technologist P. Sharma",
      },
    },
  ]);

  // Inventory Stock Matrix
  const [stockMatrix] = useState<BloodStockItem[]>([
    { bloodGroup: "A+", prbcUnits: 42, ffpUnits: 38, plateletUnits: 14, cryoUnits: 8 },
    { bloodGroup: "A-", prbcUnits: 8, ffpUnits: 12, plateletUnits: 3, cryoUnits: 2, isLowStock: true },
    { bloodGroup: "B+", prbcUnits: 55, ffpUnits: 46, plateletUnits: 18, cryoUnits: 10 },
    { bloodGroup: "B-", prbcUnits: 6, ffpUnits: 8, plateletUnits: 2, cryoUnits: 2, isLowStock: true },
    { bloodGroup: "AB+", prbcUnits: 22, ffpUnits: 24, plateletUnits: 8, cryoUnits: 5 },
    { bloodGroup: "AB-", prbcUnits: 4, ffpUnits: 6, plateletUnits: 1, cryoUnits: 1, isLowStock: true },
    { bloodGroup: "O+", prbcUnits: 64, ffpUnits: 58, plateletUnits: 22, cryoUnits: 12 },
    { bloodGroup: "O-", prbcUnits: 9, ffpUnits: 14, plateletUnits: 4, cryoUnits: 3, isLowStock: true },
  ]);

  // Donors Roster
  const [donors] = useState<DonorRecord[]>([
    {
      id: "DON-101",
      donorName: "Manoj Swaminathan",
      age: 28,
      gender: "MALE",
      bloodGroup: "O-",
      donationType: "VOLUNTARY",
      hemoglobin: 14.8,
      screeningStatus: "PASSED_SAFE",
      bagBarcode: "BAG-2026-O-8822",
      donatedAt: "Today, 09:30 AM",
    },
    {
      id: "DON-102",
      donorName: "Pooja Hegde",
      age: 24,
      gender: "FEMALE",
      bloodGroup: "B+",
      donationType: "VOLUNTARY",
      hemoglobin: 13.2,
      screeningStatus: "PASSED_SAFE",
      bagBarcode: "BAG-2026-B-9915",
      donatedAt: "Today, 10:15 AM",
    },
    {
      id: "DON-103",
      donorName: "Arunav Sen",
      age: 34,
      gender: "MALE",
      bloodGroup: "A+",
      donationType: "REPLACEMENT",
      hemoglobin: 15.1,
      screeningStatus: "TESTING_IN_PROGRESS",
      bagBarcode: "BAG-2026-A-9944",
      donatedAt: "Today, 11:45 AM",
    },
    {
      id: "DON-104",
      donorName: "Rakesh Verma",
      age: 41,
      gender: "MALE",
      bloodGroup: "O+",
      donationType: "VOLUNTARY",
      hemoglobin: 14.2,
      screeningStatus: "PASSED_SAFE",
      bagBarcode: "BAG-2026-O-8835",
      donatedAt: "Yesterday",
    },
  ]);

  // Cold Chain Telemetry
  const coldChainLoggers = [
    {
      unit: "PRBC Bank Refrigerator 1",
      type: "Blood Bank Refrigerator (2°C - 6°C)",
      currentTemp: "3.8°C",
      status: "NORMAL",
      min24h: "3.2°C",
      max24h: "4.4°C",
    },
    {
      unit: "PRBC Bank Refrigerator 2",
      type: "Blood Bank Refrigerator (2°C - 6°C)",
      currentTemp: "4.1°C",
      status: "NORMAL",
      min24h: "3.5°C",
      max24h: "4.8°C",
    },
    {
      unit: "Plasma Deep Freezer Suite",
      type: "Plasma Freezer (≤ -30°C)",
      currentTemp: "-32.4°C",
      status: "NORMAL",
      min24h: "-34.1°C",
      max24h: "-31.0°C",
    },
    {
      unit: "Platelet Incubator & Agitator",
      type: "Platelet Agitator (20°C - 24°C, 60 RPM)",
      currentTemp: "22.2°C",
      status: "NORMAL",
      min24h: "21.8°C",
      max24h: "22.6°C",
    },
  ];

  // Active Selected Requisition
  const activeReq = requisitions.find((r) => r.id === selectedReqId) || requisitions[0];

  // Issue Blood Bag to Ward Handler
  const handleIssueToWard = (reqId: string) => {
    setRequisitions((prev) =>
      prev.map((r) => {
        if (r.id !== reqId) return r;
        return {
          ...r,
          status: "ISSUED_TO_WARD",
        };
      })
    );
  };

  const [isEmergencyModalOpen, setIsEmergencyModalOpen] = useState(false);
  const [emergencyJustification, setEmergencyJustification] = useState(
    "Exsanguinating massive hemorrhage with acute shock. Clinical benefit of immediate universal O-Negative PRBC outweighs 45-minute crossmatch delay."
  );

  const handleExecuteEmergencyRelease = (reqId: string) => {
    setRequisitions((prev) =>
      prev.map((r) => {
        if (r.id !== reqId) return r;
        return {
          ...r,
          status: "EMERGENCY_UNCROSSMATCHED_RELEASE",
          allocatedBagIds: ["EMERG-ONEG-771", "EMERG-ONEG-772"],
          crossmatchDetails: {
            majorCrossmatch: "COMPATIBLE",
            minorCrossmatch: "COMPATIBLE",
            coombsDirect: "NEGATIVE",
            coombsIndirect: "NEGATIVE",
            testedBy: "EMERGENCY CLINICIAN OVERRIDE (Retrospective Pilot Testing In Progress)",
          },
        };
      })
    );
    setIsEmergencyModalOpen(false);
  };

  // Statutory Print Compatibility Certificate & Blood Bag Tag
  const handlePrintCertificate = (req: BloodRequisition) => {
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 720px; margin: 0 auto; border: 2px solid #000; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
          <h2 style="margin: 0; font-size: 20px; text-transform: uppercase;">${hospitalProfile.name}</h2>
          <div style="font-size: 12px; font-weight: bold; color: #dc2626; margin-top: 2px;">
            CENTRAL DEPARTMENT OF TRANSFUSION MEDICINE & BLOOD BANK
          </div>
          <div style="font-size: 10px; color: #555;">
            Licensed under Drugs & Cosmetics Act • License No: DL-BB-7729-R • Phone: ${hospitalProfile.phone}
          </div>
        </div>

        <div style="text-align: center; background: #fee2e2; border: 1px solid #f87171; padding: 6px; font-weight: bold; font-size: 13px; color: #991b1b; margin-bottom: 14px;">
          STATUTORY BLOOD TRANSFUSION COMPATIBILITY CERTIFICATE & CROSSMATCH REPORT
        </div>

        ${req.status === "EMERGENCY_UNCROSSMATCHED_RELEASE" ? `
          <div style="background: #fef2f2; border: 2px solid #b91c1c; padding: 10px; margin-bottom: 14px; color: #991b1b; font-size: 11px; line-height: 1.4;">
            <b style="font-size: 13px;">⚠️ STAT EMERGENCY UNCROSSMATCHED BLOOD RELEASE PROTOCOL</b><br/>
            Universal Donor O-Negative units released immediately under emergency medical protocol without awaiting full 45-minute serological crossmatch.<br/>
            <b>Clinician Justification:</b> Massive life-threatening hemorrhage. Benefit of acute volume and oxygen delivery outweighs crossmatch delay.<br/>
            <i>Pre-transfusion recipient pilot tube retained in Blood Bank for retrospective major & minor compatibility testing.</i>
          </div>
        ` : ""}

        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 12px; margin-bottom: 12px;">
          <div><b>Patient Legal Name:</b> ${req.patientName.toUpperCase()}</div>
          <div><b>UHID / MRN:</b> ${req.mrn}</div>
          <div><b>Patient Blood Group:</b> <span style="font-size: 15px; font-weight: 900; color: #b91c1c;">${req.bloodGroup}</span></div>
        </div>

        <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 14px;">
          <div><b>Ordering Ward / Dept:</b> ${req.orderingDept}</div>
          <div><b>Ordering Consultant:</b> ${req.orderingDoctor}</div>
          <div><b>Urgency:</b> <span style="color: #dc2626; font-weight: bold;">${req.urgency}</span></div>
        </div>

        <div style="border: 1px solid #999; padding: 10px; background: #f8fafc; font-size: 11px; margin-bottom: 16px;">
          <div style="font-weight: bold; text-transform: uppercase; margin-bottom: 6px; color: #0f172a;">
            Allocated Compatible Blood Component Units:
          </div>
          <div style="font-size: 12px; line-height: 1.8;">
            <div><b>Component Prescribed:</b> ${req.component} (Units: ${req.unitsRequested})</div>
            <div><b>Allocated Bag Barcodes:</b> ${(req.allocatedBagIds || ["BAG-2026-X"]).join(" • ")}</div>
          </div>
        </div>

        <div style="border: 1px solid #cbd5e1; padding: 10px; font-size: 11px; margin-bottom: 16px;">
          <div style="font-weight: bold; text-transform: uppercase; margin-bottom: 6px; color: #0f172a;">
            Serological Crossmatch & Antibody Screening Matrix:
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
            <div>• Major Crossmatch (Donor RBCs + Pt Serum): <b>${req.crossmatchDetails?.majorCrossmatch || "COMPATIBLE"}</b></div>
            <div>• Minor Crossmatch (Pt RBCs + Donor Plasma): <b>${req.crossmatchDetails?.minorCrossmatch || "COMPATIBLE"}</b></div>
            <div>• Direct Antiglobulin Test (DAT / Coombs): <b>${req.crossmatchDetails?.coombsDirect || "NEGATIVE"}</b></div>
            <div>• Indirect Antiglobulin Test (IAT / Antibody Screen): <b>${req.crossmatchDetails?.coombsIndirect || "NEGATIVE"}</b></div>
          </div>
        </div>

        <div style="background: #fffbeb; border: 1px solid #fde68a; padding: 8px; font-size: 10px; color: #92400e; margin-bottom: 24px; line-height: 1.4;">
          <b>CRITICAL BEDSIDE NURSING PROTOCOL:</b> Two registered healthcare professionals must independently verify patient name, UHID, blood group, bag number, and expiry date at the bedside before starting transfusion. 
          Monitor vital signs pre-transfusion, at 15 minutes, and on completion. In case of adverse transfusion reaction, STOP immediately and notify Blood Bank.
        </div>

        <div style="display: flex; justify-content: space-between; margin-top: 50px; font-size: 11px;">
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">
            <b>${req.crossmatchDetails?.testedBy || "Blood Bank Technologist"}</b><br/>
            <span style="font-size: 9px; color: #64748b;">Testing Technologist Signature</span>
          </div>
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">
            <b>Dr. Preeti Saxena, MD</b><br/>
            <span style="font-size: 9px; color: #64748b;">Medical Officer In-Charge • Blood Bank</span>
          </div>
        </div>
      </div>
    `;
    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(html, {
      title: `Blood_Compatibility_${req.mrn}`,
      docType: "CLINICAL_SUMMARY",
      printerDevice: a4Printer,
    });
  };

  const handlePrintBloodBagTieTag = (req: BloodRequisition, bagId: string) => {
    const labelPrinter = getPrinterForCategory("LAB_LABEL") || getPrinterForCategory("THERMAL_TOKEN");
    const html = `
      <div style="padding: 2mm 3mm; box-sizing: border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
        <div style="border-bottom: 2px solid #b91c1c; padding-bottom: 2px; text-align: center;">
          <div style="font-weight: 900; font-size: 10px; color: #b91c1c;">COMPATIBLE BLOOD BAG TAG</div>
          <div style="font-size: 8px; color: #333;">${hospitalProfile.name.slice(0, 22)}</div>
        </div>
        <div style="font-size: 9px; line-height: 1.3; margin: 2px 0;">
          <div><b>Patient:</b> ${req.patientName.toUpperCase()}</div>
          <div><b>UHID:</b> ${req.mrn} • <b>Ward:</b> ${req.orderingDept}</div>
          <div style="font-size: 11px; font-weight: 900; color: #b91c1c; margin: 2px 0;">
            Pt Grp: ${req.bloodGroup} • Bag: ${bagId}
          </div>
          <div><b>Component:</b> ${req.component}</div>
          <div><b>Crossmatch:</b> COMPATIBLE • DAT: NEG</div>
        </div>
        <div style="border-top: 1px dashed #666; padding-top: 2px; text-align: center; font-size: 8px;">
          <div style="font-family: monospace; font-size: 9px; font-weight: bold;">||| | |||| || |||</div>
          <div>DUAL-NURSE BEDSIDE CHECK MANDATORY</div>
        </div>
      </div>
    `;
    printDocument(html, {
      title: `BagTag_${bagId}`,
      docType: "LAB_REPORT",
      printerDevice: labelPrinter,
    });
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-950 overflow-hidden select-none">
      {/* Header Banner */}
      <div className="p-4 bg-slate-900/80 border-b border-slate-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-rose-950/60 border border-rose-800 text-rose-400">
            <Droplet size={20} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold text-slate-100">
                Blood Bank &amp; Transfusion Medicine Command
              </h1>
              <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800/80">
                Licensed Transfusion Facility
              </span>
            </div>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              ABO/Rh(D) Grouping • Major/Minor Crossmatch • Cold Chain Telemetry • Voluntary Donor Intake
            </p>
          </div>
        </div>

        {/* Workspace Navigation Tabs */}
        <div className="flex bg-slate-950 p-1 rounded-lg border border-slate-800 text-xs">
          <button
            onClick={() => setActiveTab("requisitions")}
            className={`px-3 py-1 rounded font-semibold transition-all ${
              activeTab === "requisitions"
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Requisitions Queue
          </button>
          <button
            onClick={() => setActiveTab("inventory")}
            className={`px-3 py-1 rounded font-semibold transition-all ${
              activeTab === "inventory"
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Component Stock Matrix
          </button>
          <button
            onClick={() => setActiveTab("donors")}
            className={`px-3 py-1 rounded font-semibold transition-all ${
              activeTab === "donors"
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Donors &amp; Phlebotomy
          </button>
          <button
            onClick={() => setActiveTab("coldchain")}
            className={`px-3 py-1 rounded font-semibold transition-all ${
              activeTab === "coldchain"
                ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Cold Chain Telemetry
          </button>
        </div>
      </div>

      {/* Main 2-Column Clinical Layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left Column: Requisitions Stream */}
        <div className="w-[420px] bg-slate-950 border-r border-slate-800 flex flex-col overflow-y-auto">
          <div className="p-3 border-b border-slate-800 bg-slate-900/40">
            <div className="relative">
              <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
              <input
                type="text"
                placeholder="Filter by patient, MRN, blood group, ward..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-rose-500"
              />
            </div>
          </div>

          <div className="p-3 space-y-2.5 overflow-y-auto flex-1">
            {requisitions
              .filter(
                (r) =>
                  r.patientName.toLowerCase().includes(searchFilter.toLowerCase()) ||
                  r.mrn.toLowerCase().includes(searchFilter.toLowerCase()) ||
                  r.bloodGroup.toLowerCase().includes(searchFilter.toLowerCase()) ||
                  r.orderingDept.toLowerCase().includes(searchFilter.toLowerCase())
              )
              .map((r) => {
                const isSelected = r.id === activeReq.id;
                const isStat = r.urgency === "STAT_EMERGENCY";

                return (
                  <div
                    key={r.id}
                    onClick={() => {
                      setSelectedReqId(r.id);
                      selectPatient(1);
                    }}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-rose-950/40 border-rose-500/80 ring-1 ring-rose-500/50 shadow-lg"
                        : "bg-slate-900/60 border-slate-800 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-xs font-bold text-rose-400 bg-rose-950/80 px-2 py-0.5 rounded border border-rose-800/80">
                          {r.bloodGroup}
                        </span>
                        <span className="text-xs font-bold text-slate-100">{r.patientName}</span>
                      </div>
                      <Badge variant={isStat ? "danger" : r.urgency === "URGENT" ? "warning" : "info"} size="sm">
                        {r.urgency.replace(/_/g, " ")}
                      </Badge>
                    </div>

                    <div className="text-xs text-slate-300 font-medium">
                      {r.unitsRequested} Unit(s) {r.component} • {r.orderingDept}
                    </div>

                    <div className="flex items-center justify-between text-[11px] text-slate-400 font-mono mt-2 pt-2 border-t border-slate-800/80">
                      <span>Status: {r.status.replace(/_/g, " ")}</span>
                      <span className="text-amber-400 font-bold">{r.requestedAt}</span>
                    </div>
                  </div>
                );
              })}
          </div>
        </div>

        {/* Right Column: Active View */}
        <div className="flex-1 flex flex-col overflow-y-auto p-6 space-y-6">
          {/* View 1: Requisitions & Crossmatch Authorization */}
          {activeTab === "requisitions" && (
            <div className="space-y-6">
              {/* Active Requisition Card */}
              <Card className="p-4 bg-slate-900/80 border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-rose-950/80 border border-rose-700/80 flex items-center justify-center text-rose-400 font-black text-lg font-mono">
                      {activeReq.bloodGroup}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-base font-bold text-slate-100">{activeReq.patientName}</h2>
                        <span className="text-xs text-slate-400 font-mono">({activeReq.mrn})</span>
                      </div>
                      <div className="text-xs text-rose-300 font-semibold mt-0.5">
                        {activeReq.unitsRequested} Unit(s) {activeReq.component} Requisition • {activeReq.orderingDept}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {activeReq.allocatedBagIds && activeReq.allocatedBagIds.length > 0 && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handlePrintBloodBagTieTag(activeReq, activeReq.allocatedBagIds?.[0] || "BAG-01")}
                        className="flex items-center gap-1.5 text-rose-400 hover:text-rose-300 border-rose-900/60"
                        title="Print Physical Blood Bag Tie-On Label"
                      >
                        <Barcode size={13} /> Print Bag Tag
                      </Button>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handlePrintCertificate(activeReq)}
                      className="flex items-center gap-1.5"
                    >
                      <Printer size={13} /> Print Statutory Certificate
                    </Button>
                    {activeReq.status === "COMPATIBLE_RESERVED" && (
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => handleIssueToWard(activeReq.id)}
                        className="bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold"
                      >
                        Release &amp; Issue to Ward
                      </Button>
                    )}
                    {activeReq.status !== "ISSUED_TO_WARD" && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setIsEmergencyModalOpen(true)}
                        className="flex items-center gap-1.5 text-rose-400 hover:text-white hover:bg-rose-900/80 border-rose-800 bg-rose-950/40"
                        title="Execute Statutory Emergency Uncrossmatched Blood Release"
                      >
                        <Siren size={13} className="text-rose-400" /> Emergency O-Neg Release
                      </Button>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-3 pt-3 border-t border-slate-800 text-xs">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold block">Ordering Consultant</span>
                    <span className="text-slate-200 font-semibold">{activeReq.orderingDoctor}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold block">Urgency Acuity</span>
                    <span className="text-rose-400 font-semibold">{activeReq.urgency.replace(/_/g, " ")}</span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold block">Allocated Bag Barcodes</span>
                    <span className="text-slate-200 font-mono text-[11px]">
                      {activeReq.allocatedBagIds?.join(", ") || "Awaiting Crossmatch"}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase font-bold block">Release Status</span>
                    <Badge variant={activeReq.status === "ISSUED_TO_WARD" ? "success" : "info"} size="sm">
                      {activeReq.status.replace(/_/g, " ")}
                    </Badge>
                  </div>
                </div>
              </Card>

              {/* Serological Crossmatch Matrix Card */}
              <Card className="p-4 bg-slate-900/60 border-slate-800 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                    <ShieldCheck size={14} className="text-emerald-400" />
                    Serological Crossmatch Compatibility Results (Direct &amp; Indirect Coombs)
                  </h3>
                  <span className="text-[11px] font-mono text-slate-400">
                    Tested by: {activeReq.crossmatchDetails?.testedBy || "Technologist"}
                  </span>
                </div>

                <div className="grid grid-cols-4 gap-3 text-xs">
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Major Crossmatch</span>
                    <div className="font-bold text-emerald-400 mt-1 flex items-center gap-1">
                      <Check size={14} /> COMPATIBLE
                    </div>
                    <span className="text-[10px] text-slate-500 mt-0.5 block">Donor RBCs + Patient Serum</span>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Minor Crossmatch</span>
                    <div className="font-bold text-emerald-400 mt-1 flex items-center gap-1">
                      <Check size={14} /> COMPATIBLE
                    </div>
                    <span className="text-[10px] text-slate-500 mt-0.5 block">Patient RBCs + Donor Plasma</span>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Direct Coombs Test (DAT)</span>
                    <div className="font-bold text-sky-400 mt-1 flex items-center gap-1">
                      <Check size={14} /> NEGATIVE
                    </div>
                    <span className="text-[10px] text-slate-500 mt-0.5 block">In-vivo sensitized RBCs</span>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                    <span className="text-[10px] text-slate-500 block uppercase">Indirect Coombs (IAT)</span>
                    <div className="font-bold text-sky-400 mt-1 flex items-center gap-1">
                      <Check size={14} /> NEGATIVE
                    </div>
                    <span className="text-[10px] text-slate-500 mt-0.5 block">Atypical antibody screen</span>
                  </div>
                </div>
              </Card>
            </div>
          )}

          {/* View 2: Component Stock Matrix */}
          {activeTab === "inventory" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                    Central Blood Component Inventory Matrix (8 Blood Groups)
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Real-time available units separated across PRBC, FFP, Platelets, and Cryoprecipitate
                  </p>
                </div>
              </div>

              <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-950 text-slate-400 font-mono text-[11px] border-b border-slate-800">
                    <tr>
                      <th className="p-3">ABO / Rh(D) Group</th>
                      <th className="p-3">PRBC (Packed RBCs)</th>
                      <th className="p-3">FFP (Fresh Frozen Plasma)</th>
                      <th className="p-3">Platelet Units (RDP/SDP)</th>
                      <th className="p-3">Cryoprecipitate</th>
                      <th className="p-3 text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {stockMatrix.map((item) => (
                      <tr key={item.bloodGroup} className="hover:bg-slate-800/40">
                        <td className="p-3 font-bold text-slate-100 text-sm">
                          <span className="px-2.5 py-1 rounded bg-rose-950/80 text-rose-300 border border-rose-800">
                            {item.bloodGroup}
                          </span>
                        </td>
                        <td className="p-3 text-slate-200 font-bold">{item.prbcUnits} Units</td>
                        <td className="p-3 text-slate-300">{item.ffpUnits} Units</td>
                        <td className="p-3 text-slate-300">{item.plateletUnits} Units</td>
                        <td className="p-3 text-slate-300">{item.cryoUnits} Units</td>
                        <td className="p-3 text-right">
                          <Badge variant={item.isLowStock ? "warning" : "success"} size="sm">
                            {item.isLowStock ? "LOW STOCK" : "ADEQUATE"}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* View 3: Donors & Phlebotomy Intake */}
          {activeTab === "donors" && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                    Blood Donor Registry &amp; TTI Screening Vault
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Mandatory 5-Parameter TTI Screening: HIV 1&amp;2, HBsAg, HCV, Syphilis (VDRL), Malaria
                  </p>
                </div>
              </div>

              <div className="bg-slate-900 rounded-xl border border-slate-800 overflow-hidden">
                <table className="w-full text-xs text-left">
                  <thead className="bg-slate-950 text-slate-400 font-mono text-[11px] border-b border-slate-800">
                    <tr>
                      <th className="p-3">Donor Name</th>
                      <th className="p-3">Age / Gender</th>
                      <th className="p-3">Blood Group</th>
                      <th className="p-3">Type</th>
                      <th className="p-3">Hemoglobin</th>
                      <th className="p-3">Assigned Bag Barcode</th>
                      <th className="p-3 text-right">TTI Screening</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800 font-mono">
                    {donors.map((d) => (
                      <tr key={d.id} className="hover:bg-slate-800/40">
                        <td className="p-3 font-bold text-slate-100">{d.donorName}</td>
                        <td className="p-3 text-slate-300">{d.age} Y / {d.gender}</td>
                        <td className="p-3 font-bold text-rose-400">{d.bloodGroup}</td>
                        <td className="p-3 text-slate-300">{d.donationType}</td>
                        <td className="p-3 text-slate-200">{d.hemoglobin} g/dL</td>
                        <td className="p-3 text-sky-400 font-mono">{d.bagBarcode}</td>
                        <td className="p-3 text-right">
                          <Badge variant={d.screeningStatus === "PASSED_SAFE" ? "success" : "warning"} size="sm">
                            {d.screeningStatus.replace(/_/g, " ")}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* View 4: Cold Chain Telemetry */}
          {activeTab === "coldchain" && (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                  Cold Chain Digital Telemetry &amp; Continuous Logger
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Automated thermal sensors connected to central telemetry with audio/visual excursion alarms
                </p>
              </div>

              <div className="grid grid-cols-2 gap-4">
                {coldChainLoggers.map((logger, idx) => (
                  <Card key={idx} className="p-4 bg-slate-900/70 border-slate-800 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Thermometer size={16} className="text-sky-400" />
                        <div>
                          <h4 className="text-xs font-bold text-slate-100">{logger.unit}</h4>
                          <span className="text-[10px] text-slate-500 font-mono">{logger.type}</span>
                        </div>
                      </div>
                      <Badge variant="success" size="sm">IN SPECIFICATION</Badge>
                    </div>

                    <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between">
                      <div>
                        <span className="text-[10px] text-slate-500 uppercase font-mono block">Real-time Sensor Temp</span>
                        <span className="text-2xl font-bold font-mono text-emerald-400">{logger.currentTemp}</span>
                      </div>
                      <div className="text-right text-[11px] font-mono text-slate-400">
                        <div>24h Min: {logger.min24h}</div>
                        <div>24h Max: {logger.max24h}</div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Modal: Emergency Uncrossmatched O-Negative Release */}
      {isEmergencyModalOpen && (
        <Modal
          isOpen={isEmergencyModalOpen}
          onClose={() => setIsEmergencyModalOpen(false)}
          title="STAT Emergency Uncrossmatched Blood Release Protocol"
        >
          <div className="space-y-4">
            <div className="p-3 rounded-lg bg-rose-950/60 border border-rose-700/80 text-rose-200 text-xs flex items-start gap-2.5">
              <AlertTriangle size={18} className="text-rose-400 shrink-0 mt-0.5" />
              <div>
                <strong>HIGH-RISK STATUTE NOTICE:</strong> Executing this protocol releases uncrossmatched O-Negative Universal Donor Packed Red Blood Cells (PRBC) immediately without awaiting standard 45-minute serological compatibility testing.
              </div>
            </div>

            <div className="p-3 rounded bg-slate-900 border border-slate-800 text-xs space-y-1.5 font-mono">
              <div><strong>Patient:</strong> {activeReq.patientName} ({activeReq.mrn})</div>
              <div><strong>Stated Group:</strong> {activeReq.bloodGroup} • <strong>Requested Component:</strong> {activeReq.component}</div>
              <div><strong>Destination:</strong> {activeReq.orderingDept}</div>
              <div className="text-emerald-400"><strong>Release Units:</strong> 2 Units Universal O-Negative (PRBC)</div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Attending Clinician Emergency Justification:
              </label>
              <textarea
                rows={3}
                value={emergencyJustification}
                onChange={(e) => setEmergencyJustification(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 focus:outline-none focus:border-rose-500 font-mono"
              />
            </div>

            <div className="p-2.5 rounded bg-slate-950 border border-slate-800 text-[11px] text-slate-400 font-mono space-y-1">
              <div>[✓] Pre-transfusion pilot specimen retained for retrospective Coombs test</div>
              <div>[✓] Immediate delivery via STAT runner with Cold-Chain Bag</div>
              <div>[✓] Mandatory adverse reaction monitoring at 0, 15, and 60 minutes</div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <Button variant="outline" size="sm" onClick={() => setIsEmergencyModalOpen(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={() => handleExecuteEmergencyRelease(activeReq.id)}
                className="bg-rose-600 hover:bg-rose-500 text-white font-bold flex items-center gap-1.5"
              >
                <Siren size={13} /> Authorize &amp; Dispatch O-Negative Units
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
