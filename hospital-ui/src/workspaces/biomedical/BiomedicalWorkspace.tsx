import React, { useState } from "react";
import {
  Wrench,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Printer,
  Search,
  Filter,
  ShieldAlert,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { printDocument } from "../../utils/printDocument";

export interface MedicalAsset {
  id: string;
  assetTag: string;
  name: string;
  model: string;
  manufacturer: string;
  serialNumber: string;
  tier: "TIER 1 - LIFE SUPPORT" | "TIER 2 - CRITICAL CARE" | "TIER 3 - DIAGNOSTIC";
  location: string;
  operationalStatus: "IN_SERVICE" | "BREAKDOWN" | "UNDER_CALIBRATION" | "DECOMMISSIONED";
  lastCalibrationDate: string;
  nextCalibrationDueDate: string;
  calibrationStatus: "VALID" | "DUE_SOON" | "OVERDUE";
  electricalSafetyTestPassed: boolean;
  leakageCurrentMicroAmps: number; // IEC 62353 limit < 100uA
  amcProvider: string;
}

export interface BreakdownTicket {
  id: string;
  assetTag: string;
  assetName: string;
  location: string;
  reportedBy: string;
  reportTimestamp: string;
  issueDescription: string;
  priority: "STAT_CRITICAL" | "URGENT" | "ROUTINE";
  assignedEngineer: string;
  status: "OPEN" | "IN_DIAGNOSIS" | "PARTS_AWAITED" | "RESOLVED";
  downtimeHours: number;
}

export const BiomedicalWorkspace: React.FC = () => {
  const { hospitalProfile, getPrinterForCategory } = useHospitalConfig();
  const [activeTab, setActiveTab] = useState<"ASSET_REGISTER" | "BREAKDOWN_TICKETS" | "CALIBRATION_SCHEDULE">("ASSET_REGISTER");
  const [searchQuery, setSearchQuery] = useState("");
  const [tierFilter, setTierFilter] = useState<string>("ALL");

  // Sample Asset Register
  const [assets, setAssets] = useState<MedicalAsset[]>([
    {
      id: "bme-1",
      assetTag: "BME-VENT-041",
      name: "ICU Mechanical Ventilator",
      model: "Hamilton-G5 Intelligent Ventilation",
      manufacturer: "Hamilton Medical",
      serialNumber: "HM-G5-98412",
      tier: "TIER 1 - LIFE SUPPORT",
      location: "MICU - Bed 04",
      operationalStatus: "IN_SERVICE",
      lastCalibrationDate: "15-Aug-2026",
      nextCalibrationDueDate: "15-Nov-2026",
      calibrationStatus: "DUE_SOON",
      electricalSafetyTestPassed: true,
      leakageCurrentMicroAmps: 42,
      amcProvider: "Hamilton India MedTech Care",
    },
    {
      id: "bme-2",
      assetTag: "BME-DEFIB-012",
      name: "Biphasic Defibrillator & Pacer",
      model: "Zoll R Series ALS Plus",
      manufacturer: "ZOLL Medical",
      serialNumber: "ZL-R90-4109",
      tier: "TIER 1 - LIFE SUPPORT",
      location: "ED Resuscitation Bay 1",
      operationalStatus: "IN_SERVICE",
      lastCalibrationDate: "01-Oct-2026",
      nextCalibrationDueDate: "01-Apr-2027",
      calibrationStatus: "VALID",
      electricalSafetyTestPassed: true,
      leakageCurrentMicroAmps: 28,
      amcProvider: "Zoll Direct Care AMC",
    },
    {
      id: "bme-3",
      assetTag: "BME-ANES-006",
      name: "Anesthesia Delivery Workstation",
      model: "Aisys CS2 Carestation",
      manufacturer: "GE Healthcare",
      serialNumber: "GE-CS2-2024-88",
      tier: "TIER 1 - LIFE SUPPORT",
      location: "OT-1 Cardiac Hybrid",
      operationalStatus: "IN_SERVICE",
      lastCalibrationDate: "20-May-2026",
      nextCalibrationDueDate: "20-Aug-2026",
      calibrationStatus: "OVERDUE",
      electricalSafetyTestPassed: true,
      leakageCurrentMicroAmps: 58,
      amcProvider: "Wipro GE Healthcare",
    },
    {
      id: "bme-4",
      assetTag: "BME-MON-114",
      name: "High-Acuity Multi-Parameter Monitor",
      model: "IntelliVue MX800",
      manufacturer: "Philips Healthcare",
      serialNumber: "PH-MX8-6612",
      tier: "TIER 2 - CRITICAL CARE",
      location: "SICU - Bed 02",
      operationalStatus: "BREAKDOWN",
      lastCalibrationDate: "10-Jun-2026",
      nextCalibrationDueDate: "10-Dec-2026",
      calibrationStatus: "VALID",
      electricalSafetyTestPassed: false,
      leakageCurrentMicroAmps: 112,
      amcProvider: "Philips Medical Systems",
    },
    {
      id: "bme-5",
      assetTag: "BME-DIAL-008",
      name: "Hemodialysis System",
      model: "Fresenius 4008S Next Gen",
      manufacturer: "Fresenius Medical Care",
      serialNumber: "FMC-408-3310",
      tier: "TIER 2 - CRITICAL CARE",
      location: "Dialysis Suite Unit 3",
      operationalStatus: "IN_SERVICE",
      lastCalibrationDate: "12-Sep-2026",
      nextCalibrationDueDate: "12-Mar-2027",
      calibrationStatus: "VALID",
      electricalSafetyTestPassed: true,
      leakageCurrentMicroAmps: 34,
      amcProvider: "Fresenius BioMed Services",
    },
  ]);

  // Sample Breakdown Tickets
  const [breakdownTickets, setBreakdownTickets] = useState<BreakdownTicket[]>([
    {
      id: "TK-BME-2026-089",
      assetTag: "BME-MON-114",
      assetName: "IntelliVue MX800 Multi-Parameter Monitor",
      location: "SICU - Bed 02",
      reportedBy: "Staff Nurse Shweta",
      reportTimestamp: "01-Nov-2026 07:45",
      issueDescription: "Chassis leakage current alarm triggered during morning routine safety check (112 uA). NIBP pump failing to hold pressure.",
      priority: "STAT_CRITICAL",
      assignedEngineer: "Eng. Karthik Raman (Lead BME)",
      status: "IN_DIAGNOSIS",
      downtimeHours: 4.5,
    },
    {
      id: "TK-BME-2026-090",
      assetTag: "BME-PUMP-230",
      assetName: "Alaris Syringe Infusion Pump",
      location: "NICU - Incubator 04",
      reportedBy: "Dr. Sunita Rao",
      reportTimestamp: "01-Nov-2026 09:20",
      issueDescription: "Keypad unresponsive on bolus delivery button. Replaced with buffer unit BME-PUMP-299.",
      priority: "URGENT",
      assignedEngineer: "Eng. Deepak Verma",
      status: "PARTS_AWAITED",
      downtimeHours: 2.8,
    },
  ]);

  const handleResolveTicket = (ticketId: string, assetTag: string) => {
    setBreakdownTickets((prev) =>
      prev.map((t) => (t.id === ticketId ? { ...t, status: "RESOLVED" } : t))
    );
    setAssets((prev) =>
      prev.map((a) =>
        a.assetTag === assetTag
          ? {
              ...a,
              operationalStatus: "IN_SERVICE",
              electricalSafetyTestPassed: true,
              leakageCurrentMicroAmps: 38,
            }
          : a
      )
    );
  };

  const handlePrintCalibrationCert = (asset: MedicalAsset) => {
    const certHtml = `
      <div style="font-family: sans-serif; padding: 24px; color: #0f172a; max-width: 800px; margin: 0 auto; line-height: 1.4;">
        <div style="border-bottom: 2px solid #0f172a; padding-bottom: 12px; margin-bottom: 16px; display: flex; justify-content: space-between; align-items: flex-start;">
          <div>
            <h1 style="font-size: 18px; font-weight: 800; margin: 0; text-transform: uppercase;">${hospitalProfile.name}</h1>
            <p style="font-size: 11px; color: #475569; margin: 2px 0;">DEPARTMENT OF BIOMEDICAL ENGINEERING & CLINICAL ASSET QUALITY</p>
            <p style="font-size: 10px; color: #64748b; margin: 0;">FORM BME-QC-08: STATUTORY EQUIPMENT CALIBRATION & ELECTRICAL SAFETY CLEARANCE</p>
          </div>
          <div style="text-align: right;">
            <span style="display: inline-block; padding: 4px 8px; background: #ecfdf5; color: #065f46; font-size: 11px; font-weight: 700; border: 1px solid #10b981; border-radius: 4px;">
              CALIBRATION CERTIFIED
            </span>
            <p style="font-size: 10px; font-family: monospace; margin: 4px 0 0 0;">ASSET TAG: ${asset.assetTag}</p>
          </div>
        </div>

        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 12px; margin-bottom: 16px;">
          <h3 style="font-size: 12px; font-weight: 700; margin: 0 0 8px 0; color: #1e293b; text-transform: uppercase;">Medical Equipment Master Details</h3>
          <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
            <tr>
              <td style="padding: 4px 0; width: 25%; color: #64748b;">Equipment Nomenclature:</td>
              <td style="padding: 4px 0; width: 25%; font-weight: 700;">${asset.name}</td>
              <td style="padding: 4px 0; width: 25%; color: #64748b;">OEM Model & Make:</td>
              <td style="padding: 4px 0; width: 25%; font-weight: 700;">${asset.manufacturer} ${asset.model}</td>
            </tr>
            <tr>
              <td style="padding: 4px 0; color: #64748b;">Serial Number:</td>
              <td style="padding: 4px 0; font-family: monospace; font-weight: 700;">${asset.serialNumber}</td>
              <td style="padding: 4px 0; color: #64748b;">Installed Location:</td>
              <td style="padding: 4px 0; font-weight: 700; color: #0284c7;">${asset.location}</td>
            </tr>
            <tr>
              <td style="padding: 4px 0; color: #64748b;">Criticality Classification:</td>
              <td style="padding: 4px 0; font-weight: 700; color: #b91c1c;">${asset.tier}</td>
              <td style="padding: 4px 0; color: #64748b;">AMC / Service Vendor:</td>
              <td style="padding: 4px 0; font-weight: 600;">${asset.amcProvider}</td>
            </tr>
          </table>
        </div>

        <div style="border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; margin-bottom: 16px;">
          <h3 style="font-size: 12px; font-weight: 700; margin: 0 0 8px 0; color: #065f46; text-transform: uppercase;">Calibration & Electrical Safety Test (IEC 62353 Standards)</h3>
          <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #f1f5f9;">
              <td style="padding: 6px 0; color: #64748b;">Calibration Execution Date:</td>
              <td style="padding: 6px 0; font-weight: 700;">${asset.lastCalibrationDate}</td>
              <td style="padding: 6px 0; color: #64748b;">Next Calibration Expiry:</td>
              <td style="padding: 6px 0; font-weight: 700; color: #0284c7;">${asset.nextCalibrationDueDate}</td>
            </tr>
            <tr style="border-bottom: 1px solid #f1f5f9;">
              <td style="padding: 6px 0; color: #64748b;">Chassis Earth Bond Resistance:</td>
              <td style="padding: 6px 0; font-mono; font-weight: 700;">0.08 Ω (Limit: &lt; 0.2 Ω) - PASS</td>
              <td style="padding: 6px 0; color: #64748b;">Direct Chassis Leakage Current:</td>
              <td style="padding: 6px 0; font-mono; font-weight: 700; color: #059669;">${asset.leakageCurrentMicroAmps} µA (Limit: &lt; 100 µA) - PASS</td>
            </tr>
            <tr>
              <td style="padding: 6px 0; color: #64748b;">Reference Test Analyzer:</td>
              <td colspan="3" style="padding: 6px 0; font-family: monospace; font-size: 10px; color: #475569;">
                Rigel 288+ Electrical Safety Analyzer (NABL Traceable Calib Cert #NABL-RIG-2026-904)
              </td>
            </tr>
          </table>
        </div>

        <div style="border: 1px solid #cbd5e1; border-radius: 6px; padding: 12px; margin-bottom: 24px; background: #ecfdf5;">
          <h4 style="font-size: 11px; font-weight: 700; margin: 0 0 4px 0; color: #065f46; text-transform: uppercase;">Clinical Safety Clearance Declaration</h4>
          <p style="font-size: 10px; color: #064e3b; margin: 0; line-height: 1.5;">
            This certifies that the referenced medical device has undergone comprehensive Planned Preventive Maintenance (PPM), flow/parameter verification against OEM specifications, and electrical safety testing per IEC 60601-1 and IEC 62353 standards. The equipment is certified fit for immediate patient clinical use.
          </p>
        </div>

        <div style="display: flex; justify-content: space-between; margin-top: 40px; padding-top: 16px; border-top: 1px dashed #94a3b8; font-size: 10px; color: #475569;">
          <div style="text-align: center; width: 30%;">
            <div style="border-bottom: 1px solid #0f172a; height: 35px; margin-bottom: 4px;"></div>
            <strong>Biomedical Service Engineer</strong><br />
            ID: BME-ENG-108
          </div>
          <div style="text-align: center; width: 30%;">
            <div style="border-bottom: 1px solid #0f172a; height: 35px; margin-bottom: 4px;"></div>
            <strong>Head of Biomedical Engineering</strong><br />
            Clinical Engineering Division
          </div>
          <div style="text-align: center; width: 30%;">
            <div style="border-bottom: 1px solid #0f172a; height: 35px; margin-bottom: 4px;"></div>
            <strong>Quality & Safety Director</strong><br />
            NABH Hospital Safety Committee
          </div>
        </div>
      </div>
    `;

    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(certHtml, {
      docType: "CLINICAL_SUMMARY",
      title: `BME_Calib_Cert_${asset.assetTag}`,
      printerDevice: a4Printer,
    });
  };

  const handlePrintLockoutPlacard = (ticket: BreakdownTicket) => {
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 650px; margin: 0 auto; border: 6px solid #dc2626; padding: 24px; text-align: center; background: #fff;">
        <div style="background: #dc2626; color: #fff; padding: 16px; border-radius: 6px; margin-bottom: 20px;">
          <h1 style="margin: 0; font-size: 32px; font-weight: 900; letter-spacing: 2px;">⚠️ DANGER</h1>
          <div style="font-size: 20px; font-weight: 800; margin-top: 4px; text-transform: uppercase;">
            DO NOT OPERATE • OUT OF SERVICE
          </div>
          <div style="font-size: 11px; margin-top: 4px;">STATUTORY BIOMEDICAL LOCKOUT TAGOUT (LOTO) • FORM BME-LOTO-01</div>
        </div>

        <div style="border: 2px dashed #dc2626; background: #fef2f2; padding: 16px; border-radius: 8px; margin-bottom: 20px; text-align: left;">
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 12px;">
            <div><b>Asset Tag:</b> <span style="font-family: monospace; font-size: 14px; font-weight: bold; color: #b91c1c;">${ticket.assetTag}</span></div>
            <div><b>Ticket No:</b> <span style="font-family: monospace; font-size: 13px;">${ticket.id}</span></div>
            <div><b>Equipment:</b> <b>${ticket.assetName}</b></div>
            <div><b>Ward Location:</b> <b>${ticket.location}</b></div>
          </div>
          <div style="margin-top: 10px; font-size: 12px; color: #991b1b; border-top: 1px solid #fecaca; padding-top: 8px;">
            <b>Failure / Safety Hazard:</b> ${ticket.issueDescription}
          </div>
        </div>

        <div style="background: #fffbeb; border: 1px solid #fde68a; padding: 12px; border-radius: 6px; font-size: 11px; color: #92400e; margin-bottom: 24px; text-align: left; line-height: 1.5;">
          <b>CRITICAL PATIENT SAFETY DIRECTIVE:</b><br/>
          This medical device has been locked out due to mechanical/electrical malfunction. Under NABH Hospital Safety Standard FMS.6, connecting this device to any patient is strictly prohibited. Only authorized Biomedical Engineering personnel may remove this tag following certified re-calibration.
        </div>

        <div style="display: flex; justify-content: space-between; font-size: 11px; border-top: 2px solid #000; padding-top: 10px; text-align: left;">
          <div>
            <b>Tagged Date:</b> ${ticket.reportTimestamp}<br/>
            <b>Reported By:</b> ${ticket.reportedBy}
          </div>
          <div style="text-align: right;">
            <b>Assigned Lead Engineer:</b> ${ticket.assignedEngineer}<br/>
            <b>Biomedical Control Room:</b> Ext. 108 / +91 40 8829 0108
          </div>
        </div>
      </div>
    `;

    const a4Printer = getPrinterForCategory("CLINICAL_A4");
    printDocument(html, {
      title: `LOTO_${ticket.assetTag}`,
      docType: "CLINICAL_SUMMARY",
      printerDevice: a4Printer,
    });
  };

  const filteredAssets = assets.filter((a) => {
    const matchesQuery =
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.assetTag.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.location.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.serialNumber.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesTier = tierFilter === "ALL" || a.tier === tierFilter;
    return matchesQuery && matchesTier;
  });

  const totalAssetsCount = assets.length;
  const inServiceCount = assets.filter((a) => a.operationalStatus === "IN_SERVICE").length;
  const breakdownCount = assets.filter((a) => a.operationalStatus === "BREAKDOWN").length;
  const overdueCalibCount = assets.filter((a) => a.calibrationStatus === "OVERDUE").length;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-slate-950 font-sans">
      {/* 1. Header Bar */}
      <div className="p-4 bg-slate-900 border-b border-slate-800 flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-base font-bold text-slate-100 flex items-center gap-2">
              <Wrench className="w-5 h-5 text-sky-400" />
              Biomedical Engineering & Clinical Asset Management (BME)
            </h1>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800 font-bold">
              IEC 62353 / NABH SAFETY
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Life-support asset inventory, preventive maintenance (PPM), electrical safety testing, and breakdown work orders.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Tabs */}
          <div className="flex rounded-lg bg-slate-950 p-1 border border-slate-800 text-xs">
            <button
              onClick={() => setActiveTab("ASSET_REGISTER")}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                activeTab === "ASSET_REGISTER"
                  ? "bg-sky-500/20 text-sky-300 border border-sky-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              Asset Register ({totalAssetsCount})
            </button>
            <button
              onClick={() => setActiveTab("BREAKDOWN_TICKETS")}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all flex items-center gap-1.5 ${
                activeTab === "BREAKDOWN_TICKETS"
                  ? "bg-rose-500/20 text-rose-300 border border-rose-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              <AlertTriangle size={12} />
              <span>Breakdown Tickets ({breakdownTickets.filter((t) => t.status !== "RESOLVED").length})</span>
            </button>
            <button
              onClick={() => setActiveTab("CALIBRATION_SCHEDULE")}
              className={`px-3 py-1.5 rounded-md font-semibold transition-all ${
                activeTab === "CALIBRATION_SCHEDULE"
                  ? "bg-amber-500/20 text-amber-300 border border-amber-500/40"
                  : "text-slate-400 hover:text-white"
              }`}
            >
              PPM & Calibration
            </button>
          </div>
        </div>
      </div>

      {/* 2. Executive KPI Ribbon */}
      <div className="p-4 border-b border-slate-800/80 bg-slate-900/40 grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Operational Assets</span>
            <CheckCircle2 size={12} className="text-emerald-400" />
          </div>
          <div className="text-2xl font-black font-mono text-emerald-400 mt-1 flex items-baseline gap-2">
            <span>{inServiceCount}</span>
            <span className="text-[10px] text-slate-400 font-normal">/ {totalAssetsCount} Online (98%)</span>
          </div>
        </Card>

        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Active Breakdown</span>
            <AlertTriangle size={12} className="text-rose-400" />
          </div>
          <div className="text-2xl font-black font-mono text-rose-400 mt-1 flex items-baseline gap-2">
            <span>{breakdownCount}</span>
            <span className="text-[10px] text-slate-400 font-normal">In Triage / Repair</span>
          </div>
        </Card>

        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Calibration Overdue</span>
            <ShieldAlert size={12} className="text-amber-400" />
          </div>
          <div className="text-2xl font-black font-mono text-amber-400 mt-1 flex items-baseline gap-2">
            <span>{overdueCalibCount}</span>
            <span className="text-[10px] text-rose-400 font-normal">Requires Recalibration</span>
          </div>
        </Card>

        <Card className="p-3 bg-slate-900 border-slate-800">
          <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider flex items-center justify-between">
            <span>Mean Time To Repair (MTTR)</span>
            <Clock size={12} className="text-sky-400" />
          </div>
          <div className="text-2xl font-black font-mono text-sky-400 mt-1 flex items-baseline gap-2">
            <span>3.2h</span>
            <span className="text-[10px] text-slate-400 font-normal">Target: &lt; 4.0h</span>
          </div>
        </Card>
      </div>

      {/* 3. Main Body */}
      <div className="flex-1 overflow-y-auto p-4">
        {/* TAB 1: ASSET REGISTER */}
        {activeTab === "ASSET_REGISTER" && (
          <div className="space-y-4">
            {/* Search and Filters */}
            <div className="flex items-center justify-between gap-3 bg-slate-900 p-3 rounded-xl border border-slate-800">
              <div className="flex items-center gap-2 flex-1 max-w-md">
                <Search size={15} className="text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter by asset tag, device name, location, or serial..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-transparent text-xs text-white placeholder-slate-500 focus:outline-none w-full"
                />
              </div>

              <div className="flex items-center gap-2 text-xs">
                <Filter size={13} className="text-slate-400" />
                <select
                  value={tierFilter}
                  onChange={(e) => setTierFilter(e.target.value)}
                  className="bg-slate-950 border border-slate-700 rounded px-2.5 py-1 text-slate-200 focus:outline-none"
                >
                  <option value="ALL">All Criticality Tiers</option>
                  <option value="TIER 1 - LIFE SUPPORT">Tier 1 - Life Support (Ventilators, Defibs, Anesthesia)</option>
                  <option value="TIER 2 - CRITICAL CARE">Tier 2 - Critical Care (Monitors, Dialysis)</option>
                  <option value="TIER 3 - DIAGNOSTIC">Tier 3 - Diagnostic</option>
                </select>
              </div>
            </div>

            {/* Asset Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {filteredAssets.map((asset) => (
                <Card
                  key={asset.id}
                  className="p-4 bg-slate-900 border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between text-xs mb-2 pb-2 border-b border-slate-800">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-bold text-sky-400 bg-sky-950/80 px-2 py-0.5 rounded border border-sky-800">
                          {asset.assetTag}
                        </span>
                        <Badge
                          variant={
                            asset.operationalStatus === "IN_SERVICE"
                              ? "success"
                              : asset.operationalStatus === "BREAKDOWN"
                              ? "danger"
                              : "warning"
                          }
                        >
                          {asset.operationalStatus}
                        </Badge>
                      </div>
                      <span className="text-[10px] font-mono text-slate-400">
                        Location: <strong className="text-slate-200">{asset.location}</strong>
                      </span>
                    </div>

                    <div className="text-base font-bold text-white">{asset.name}</div>
                    <div className="text-xs text-slate-400 font-mono mt-0.5">
                      {asset.manufacturer} {asset.model} • S/N: {asset.serialNumber}
                    </div>

                    <div className="mt-3 p-2.5 rounded-lg bg-slate-950 border border-slate-800/80 text-xs space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Criticality Tier:</span>
                        <span className="font-bold text-rose-400">{asset.tier}</span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Calibration Expiry:</span>
                        <div className="flex items-center gap-1.5">
                          <span className="font-mono text-slate-200">{asset.nextCalibrationDueDate}</span>
                          <Badge
                            variant={
                              asset.calibrationStatus === "VALID"
                                ? "success"
                                : asset.calibrationStatus === "DUE_SOON"
                                ? "warning"
                                : "danger"
                            }
                            className="text-[9px]"
                          >
                            {asset.calibrationStatus}
                          </Badge>
                        </div>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="text-slate-400">Electrical Safety (IEC 62353):</span>
                        <span
                          className={`font-mono font-bold ${
                            asset.electricalSafetyTestPassed ? "text-emerald-400" : "text-rose-400"
                          }`}
                        >
                          {asset.leakageCurrentMicroAmps} µA ({asset.electricalSafetyTestPassed ? "PASSED" : "FAILED"})
                        </span>
                      </div>
                      <div className="flex items-center justify-between pt-1 border-t border-slate-800">
                        <span className="text-slate-400">Service Provider / AMC:</span>
                        <span className="text-slate-300 font-medium">{asset.amcProvider}</span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between">
                    <span className="text-[10px] text-slate-500 font-mono">
                      Last Calib: {asset.lastCalibrationDate}
                    </span>
                    <Button
                      onClick={() => handlePrintCalibrationCert(asset)}
                      variant="outline"
                      className="text-xs py-1 px-2.5 flex items-center gap-1.5 border-sky-800 text-sky-300 bg-sky-950/40 hover:bg-sky-900/60 font-semibold"
                    >
                      <Printer size={12} /> Print BME Certificate
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* TAB 2: BREAKDOWN TICKETS */}
        {activeTab === "BREAKDOWN_TICKETS" && (
          <div className="space-y-4">
            <div className="bg-rose-950/20 border border-rose-800/60 rounded-xl p-3 flex items-center justify-between text-xs text-rose-300">
              <div className="flex items-center gap-2">
                <AlertTriangle size={16} className="text-rose-400" />
                <span>
                  <strong>Priority 1 Life-Support Escalation:</strong> Breakdown of Tier 1 equipment requires dispatch of immediate buffer units within 15 minutes to guarantee patient continuity of care.
                </span>
              </div>
            </div>

            <div className="space-y-3">
              {breakdownTickets.map((ticket) => (
                <Card
                  key={ticket.id}
                  className="p-4 bg-slate-900 border-slate-800 hover:border-slate-700 transition-all"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-slate-800 mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-rose-400 bg-rose-950/80 px-2 py-0.5 rounded border border-rose-800 text-xs">
                        {ticket.id}
                      </span>
                      <span className="font-bold text-sm text-white">{ticket.assetName}</span>
                      <span className="text-xs font-mono text-sky-400 font-bold">({ticket.assetTag})</span>
                    </div>

                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          ticket.status === "RESOLVED"
                            ? "success"
                            : ticket.status === "PARTS_AWAITED"
                            ? "warning"
                            : "danger"
                        }
                      >
                        {ticket.status}
                      </Badge>
                      <span className="text-[10px] font-mono text-slate-400">
                        Downtime: <strong className="text-rose-400">{ticket.downtimeHours}h</strong>
                      </span>
                    </div>
                  </div>

                  <div className="text-xs space-y-2 bg-slate-950 p-3 rounded-lg border border-slate-800">
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="text-slate-400">Location:</span>{" "}
                        <strong className="text-slate-200">{ticket.location}</strong>
                      </div>
                      <div>
                        <span className="text-slate-400">Reported By:</span>{" "}
                        <span className="text-slate-300">{ticket.reportedBy} ({ticket.reportTimestamp})</span>
                      </div>
                    </div>
                    <div>
                      <span className="text-slate-400">Incident Details:</span>{" "}
                      <span className="text-slate-200">{ticket.issueDescription}</span>
                    </div>
                    <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
                      <div>
                        <span className="text-slate-400">Assigned Engineer:</span>{" "}
                        <strong className="text-sky-400">{ticket.assignedEngineer}</strong>
                      </div>
                      <Badge variant="purple" className="text-[10px]">
                        {ticket.priority}
                      </Badge>
                    </div>
                  </div>

                  {ticket.status !== "RESOLVED" && (
                    <div className="mt-3 pt-3 border-t border-slate-800 flex items-center justify-end gap-2">
                      <Button
                        onClick={() => handlePrintLockoutPlacard(ticket)}
                        variant="outline"
                        className="text-xs py-1 px-2.5 border-rose-800 text-rose-300 hover:bg-rose-950/50 flex items-center gap-1 font-semibold"
                        title="Print Physical Equipment Out-of-Service / Lockout Placard"
                      >
                        <ShieldAlert size={12} /> Print Lockout Placard
                      </Button>
                      <Button
                        onClick={() => handleResolveTicket(ticket.id, ticket.assetTag)}
                        className="text-xs py-1 px-3 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold flex items-center gap-1"
                      >
                        <CheckCircle2 size={13} /> Complete Repair &amp; Recalibrate (Return to Service)
                      </Button>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* TAB 3: CALIBRATION SCHEDULE */}
        {activeTab === "CALIBRATION_SCHEDULE" && (
          <div className="bg-slate-900 p-4 rounded-xl border border-slate-800">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800 mb-3">
              <div>
                <h3 className="font-bold text-sm text-slate-100">
                  Planned Preventive Maintenance (PPM) & Annual Calibration Schedule
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  NABH Medical Equipment Quality Standard FMS.6 Compliance Calendar.
                </p>
              </div>
              <Badge variant="info">NABL TRACEABLE</Badge>
            </div>

            <div className="divide-y divide-slate-800">
              {assets.map((item) => (
                <div key={item.id} className="py-3 flex items-center justify-between text-xs">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-sky-400">{item.assetTag}</span>
                      <span className="font-semibold text-slate-200">{item.name}</span>
                      <span className="text-slate-500 font-mono">({item.location})</span>
                    </div>
                    <div className="text-[11px] text-slate-400 mt-0.5">
                      AMC Partner: {item.amcProvider}
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right font-mono">
                      <div className="text-[10px] text-slate-500 uppercase">Next Calibration Due</div>
                      <div className="font-bold text-slate-200">{item.nextCalibrationDueDate}</div>
                    </div>
                    <Badge
                      variant={
                        item.calibrationStatus === "VALID"
                          ? "success"
                          : item.calibrationStatus === "DUE_SOON"
                          ? "warning"
                          : "danger"
                      }
                    >
                      {item.calibrationStatus}
                    </Badge>
                    <Button
                      onClick={() => handlePrintCalibrationCert(item)}
                      variant="outline"
                      className="text-xs py-1 px-2.5 text-slate-300 border-slate-700 hover:text-white"
                    >
                      <Printer size={12} className="mr-1" /> Certificate
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
