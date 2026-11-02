import React, { useEffect, useState } from "react";
import { registersApi } from "../../api/registersApi";
import { analyticsApi, ExecutiveCommandCenterData } from "../../api/analyticsApi";
import { METRIC_DOMAINS, SAMPLE_METRIC_CATALOG } from "../../data/metricCatalog";
import { OperationalTrendsDashboard } from "../../components/analytics/OperationalTrendsDashboard";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Badge } from "../../components/ui/Badge";
import { WorkspaceId } from "../../types";
import {
  useHospitalConfig,
  WristbandPreset,
  ThermalRollWidth,
  PrinterConnectionType,
  PrinterTargetCategory,
  PrinterProtocol,
  HospitalPrinterDevice,
} from "../../core/context/HospitalConfigContext";
import { printDocument } from "../../utils/printDocument";
import { useTenantBranding } from "../../core/context/TenantBrandingContext";
import {
  Database,
  Download,
  FileText,
  ShieldCheck,
  RefreshCw,
  Layers,
  Eye,
  Lock,
  UserPlus,
  DoorOpen,
  Stethoscope,
  BedDouble,
  Siren,
  Pill,
  Microscope,
  CreditCard,
  TrendingUp,
  Activity,
  ArrowUpRight,
  Users,
  BarChart3,
  Search,
  Settings,
  Plus,
  Trash2,
  RotateCcw,
  Building,
  CheckCircle2,
  Printer,
  Cpu,
  Wifi,
  Network,
  HardDrive,
  Zap,
  Flame,
  BellRing,
  AlertOctagon,
  ShieldAlert,
} from "lucide-react";

interface AdminWorkspaceProps {
  onSelectWorkspace?: (workspace: WorkspaceId) => void;
}

export const AdminWorkspace: React.FC<AdminWorkspaceProps> = ({ onSelectWorkspace }) => {
  const { branding, updateBranding, uploadAsset } = useTenantBranding();
  const [activeTab, setActiveTab] = useState<"overview" | "metrics" | "registers" | "customization">("overview");
  const [customSubTab, setCustomSubTab] = useState<"facility" | "doctors" | "branding" | "policies" | "printTemplates" | "printers">("facility");
  const [activeDocTemplate, setActiveDocTemplate] = useState<"thermal" | "wristband" | "bht" | "discharge">("thermal");

  const {
    hospitalProfile,
    policies,
    doctors,
    beds,
    printTemplates,
    printers,
    getPrinterForCategory,
    updateHospitalProfile,
    updatePolicies,
    updatePrintTemplates,
    addBed,
    deleteBed,
    addDoctor,
    deleteDoctor,
    addPrinter,
    deletePrinter,
    setDefaultPrinter,
    resetToDefaultCatalog,
  } = useHospitalConfig();

  // Hardware Printer Management Local Form State
  const [prnName, setPrnName] = useState("");
  const [prnLocation, setPrnLocation] = useState("");
  const [prnConnType, setPrnConnType] = useState<PrinterConnectionType>("NETWORK_IP");
  const [prnCategory, setPrnCategory] = useState<PrinterTargetCategory>("WRISTBAND");
  const [prnProtocol, setPrnProtocol] = useState<PrinterProtocol>("RAW_ZPL");
  const [prnIp, setPrnIp] = useState("192.168.1.182");
  const [prnPort, setPrnPort] = useState(9100);
  const [prnWidthMm, setPrnWidthMm] = useState(25);
  const [prnHeightMm, setPrnHeightMm] = useState(280);
  const [prnPrintableWidthMm, setPrnPrintableWidthMm] = useState(22);
  const [prnPrintableHeightMm, setPrnPrintableHeightMm] = useState(75);
  const [prnOrientation, setPrnOrientation] = useState<"PORTRAIT" | "LANDSCAPE">("PORTRAIT");
  const [prnDpi, setPrnDpi] = useState(300);
  const [prnMarginTop, setPrnMarginTop] = useState(1);
  const [prnMarginBottom, setPrnMarginBottom] = useState(1);
  const [prnMarginLeft, setPrnMarginLeft] = useState(2);
  const [prnMarginRight, setPrnMarginRight] = useState(2);
  const [prnIsDefault, setPrnIsDefault] = useState(false);
  const [printerSuccessMsg, setPrinterSuccessMsg] = useState("");

  const applyPrinterHardwarePreset = (presetName: string) => {
    switch (presetName) {
      case "ZEBRA_ZD510_HC":
        setPrnName("Zebra ZD510-HC Dedicated Healthcare Wristband Cartridge Printer");
        setPrnLocation("Admission Desk Counter 1");
        setPrnConnType("NETWORK_IP");
        setPrnCategory("WRISTBAND");
        setPrnProtocol("RAW_ZPL");
        setPrnWidthMm(25);
        setPrnHeightMm(280);
        setPrnPrintableWidthMm(22);
        setPrnPrintableHeightMm(75);
        setPrnOrientation("PORTRAIT");
        setPrnDpi(300);
        setPrnPort(9100);
        break;
      case "DIRECT_THERMAL_WRISTBAND":
        setPrnName("Desktop Direct Thermal Wristband Printer (Wide Feed)");
        setPrnLocation("Emergency Triage Counter");
        setPrnConnType("NETWORK_IP");
        setPrnCategory("WRISTBAND");
        setPrnProtocol("HTML_DRIVER");
        setPrnWidthMm(280);
        setPrnHeightMm(25);
        setPrnPrintableWidthMm(75);
        setPrnPrintableHeightMm(22);
        setPrnOrientation("LANDSCAPE");
        setPrnDpi(203);
        setPrnPort(9100);
        break;
      case "EPSON_80MM_THERMAL":
        setPrnName("Epson TM-T88 / POS 80mm Reception Token Slip Printer");
        setPrnLocation("OPD Registration Slip Counter");
        setPrnConnType("USB");
        setPrnCategory("THERMAL_TOKEN");
        setPrnProtocol("RAW_ESCPOS");
        setPrnWidthMm(80);
        setPrnHeightMm(0);
        setPrnPrintableWidthMm(76);
        setPrnPrintableHeightMm(0);
        setPrnOrientation("PORTRAIT");
        setPrnDpi(203);
        break;
      case "COMPACT_58MM_THERMAL":
        setPrnName("Compact POS 58mm Token Slip Printer");
        setPrnLocation("Pharmacy Cashier Window");
        setPrnConnType("USB");
        setPrnCategory("THERMAL_TOKEN");
        setPrnProtocol("RAW_ESCPOS");
        setPrnWidthMm(58);
        setPrnHeightMm(0);
        setPrnPrintableWidthMm(54);
        setPrnPrintableHeightMm(0);
        setPrnOrientation("PORTRAIT");
        setPrnDpi(203);
        break;
      case "WARD_LASER_A4":
        setPrnName("Ward Central HP LaserJet Managed A4 Printer");
        setPrnLocation("Inpatient Nursing Station Floor 3");
        setPrnConnType("NETWORK_IP");
        setPrnCategory("CLINICAL_A4");
        setPrnProtocol("HTML_DRIVER");
        setPrnWidthMm(210);
        setPrnHeightMm(297);
        setPrnPrintableWidthMm(200);
        setPrnPrintableHeightMm(287);
        setPrnOrientation("PORTRAIT");
        setPrnDpi(600);
        setPrnPort(9100);
        break;
      case "LAB_TUBE_LABELER":
        setPrnName("Central Specimen Barcode Tube Labeler");
        setPrnLocation("Phlebotomy Collection Room");
        setPrnConnType("USB");
        setPrnCategory("LAB_LABEL");
        setPrnProtocol("RAW_ZPL");
        setPrnWidthMm(50);
        setPrnHeightMm(25);
        setPrnPrintableWidthMm(46);
        setPrnPrintableHeightMm(22);
        setPrnOrientation("LANDSCAPE");
        setPrnDpi(203);
        break;
    }
  };

  const handleTestPrint = (printer: HospitalPrinterDevice) => {
    const isWb = printer.targetCategory === "WRISTBAND";
    const isThermal = printer.targetCategory === "THERMAL_TOKEN";
    const isLabel = printer.targetCategory === "LAB_LABEL";

    const htmlContent = `
      <div style="text-align: center; border: 2px dashed #000; padding: 4px; box-sizing: border-box; height: 100%;">
        <div style="font-weight: 900; font-size: 11px; text-transform: uppercase;">*** HARDWARE CALIBRATION TEST ***</div>
        <div style="font-size: 10px; font-weight: bold; margin-top: 2px;">${printer.name}</div>
        <div style="font-size: 9px; color: #333; margin-top: 1px;">
          Category: <b>${printer.targetCategory}</b> | Protocol: <b>${printer.protocol}</b>
        </div>
        <div style="font-size: 9px; color: #333;">
          Conn: <b>${printer.connectionType}</b> ${printer.ipAddress ? `(${printer.ipAddress}:${printer.port || 9100})` : "(Direct Hardware Port)"}
        </div>
        <div style="font-size: 9px; margin-top: 2px;">
          Media: <b>${printer.mediaWidthMm}mm × ${printer.mediaHeightMm > 0 ? `${printer.mediaHeightMm}mm` : "Roll"}</b> | ${printer.orientation} | ${printer.dpi} DPI
        </div>
        <div style="margin: 4px auto; display: inline-block; padding: 2px 8px; border: 1px solid #000; font-family: monospace; font-weight: bold; font-size: 10px;">
          *CALIB-${printer.id.toUpperCase()}-OK*
        </div>
        <div style="font-size: 8px; color: #555;">
          Margins: T:${printer.marginTopMm}mm B:${printer.marginBottomMm}mm L:${printer.marginLeftMm}mm R:${printer.marginRightMm}mm
        </div>
        <div style="font-size: 8px; color: #777; margin-top: 2px;">
          Timestamp: ${new Date().toISOString()} | Hardware calibration service
        </div>
      </div>
    `;

    printDocument(htmlContent, {
      title: `Hardware Test Slip — ${printer.name}`,
      docType: isWb ? "WRISTBAND" : isThermal ? "THERMAL_TOKEN" : isLabel ? "LAB_REPORT" : "CLINICAL_SUMMARY",
      printerDevice: printer,
    });
  };

  // Print Templates Local Form State
  const [thermalTitle, setThermalTitle] = useState(printTemplates.thermalToken.headerTitle);
  const [thermalSubHeader, setThermalSubHeader] = useState(printTemplates.thermalToken.subHeader);
  const [thermalRollWidth, setThermalRollWidth] = useState<ThermalRollWidth>(printTemplates.thermalToken.rollWidth || "80mm");
  const [thermalShowWait, setThermalShowWait] = useState(printTemplates.thermalToken.showEstimatedWait);
  const [thermalShowReceipt, setThermalShowReceipt] = useState(printTemplates.thermalToken.showCashierReceipt);
  const [thermalShowBarcode, setThermalShowBarcode] = useState(printTemplates.thermalToken.showBarcode);
  const [thermalFooter, setThermalFooter] = useState(printTemplates.thermalToken.footerNotice);

  const [wristbandName, setWristbandName] = useState(printTemplates.wristband.hospitalName);
  const [wristbandPreset, setWristbandPreset] = useState<WristbandPreset>(printTemplates.wristband.preset || "ADULT_STANDARD_280x25");
  const [wristbandWidthMm, setWristbandWidthMm] = useState<number>(printTemplates.wristband.widthMm || 280);
  const [wristbandHeightMm, setWristbandHeightMm] = useState<number>(printTemplates.wristband.heightMm || 25);
  const [wristbandPrintableLengthMm, setWristbandPrintableLengthMm] = useState<number>(printTemplates.wristband.printableLengthMm || 75);
  const [wristbandOrientation, setWristbandOrientation] = useState<"LANDSCAPE" | "PORTRAIT">(printTemplates.wristband.orientation || "LANDSCAPE");
  const [wristbandPrinterType, setWristbandPrinterType] = useState<"ZEBRA_HC100" | "DIRECT_THERMAL_ROLL" | "LASER_SHEETLET" | "STANDARD_POS">(printTemplates.wristband.printerType || "DIRECT_THERMAL_ROLL");
  const [wristbandType, setWristbandType] = useState<"ADULT_STANDARD" | "PEDIATRIC" | "INFANT_NICU" | "BARCODE_ONLY">(printTemplates.wristband.wristbandType || "ADULT_STANDARD");
  const [wristbandBlood, setWristbandBlood] = useState(printTemplates.wristband.showBloodGroup);
  const [wristbandPhone, setWristbandPhone] = useState(printTemplates.wristband.showEmergencyPhone);
  const [wristbandAllergy, setWristbandAllergy] = useState(printTemplates.wristband.showAllergyWarning);
  const [wristbandBarcode, setWristbandBarcode] = useState<"CODE128" | "QR">(printTemplates.wristband.barcodeFormat);

  const handleWristbandPresetChange = (preset: WristbandPreset) => {
    setWristbandPreset(preset);
    switch (preset) {
      case "ADULT_STANDARD_280x25":
        setWristbandWidthMm(280);
        setWristbandHeightMm(25);
        setWristbandPrintableLengthMm(75);
        setWristbandOrientation("LANDSCAPE");
        setWristbandType("ADULT_STANDARD");
        break;
      case "ADULT_WIDE_280x28":
        setWristbandWidthMm(280);
        setWristbandHeightMm(28);
        setWristbandPrintableLengthMm(80);
        setWristbandOrientation("LANDSCAPE");
        setWristbandType("ADULT_STANDARD");
        break;
      case "ADULT_SLIM_250x19":
        setWristbandWidthMm(250);
        setWristbandHeightMm(19);
        setWristbandPrintableLengthMm(70);
        setWristbandOrientation("LANDSCAPE");
        setWristbandType("ADULT_STANDARD");
        break;
      case "PEDIATRIC_180x19":
        setWristbandWidthMm(180);
        setWristbandHeightMm(19);
        setWristbandPrintableLengthMm(60);
        setWristbandOrientation("LANDSCAPE");
        setWristbandType("PEDIATRIC");
        break;
      case "INFANT_NICU_150x15":
        setWristbandWidthMm(150);
        setWristbandHeightMm(15);
        setWristbandPrintableLengthMm(50);
        setWristbandOrientation("LANDSCAPE");
        setWristbandType("INFANT_NICU");
        break;
      case "NEONATE_MICRO_100x12":
        setWristbandWidthMm(100);
        setWristbandHeightMm(12);
        setWristbandPrintableLengthMm(40);
        setWristbandOrientation("LANDSCAPE");
        setWristbandType("INFANT_NICU");
        break;
      case "CUSTOM":
        break;
    }
  };

  const [bhtTitle, setBhtTitle] = useState(printTemplates.bedHeadTicket.hospitalTitle);
  const [bhtSubTitle, setBhtSubTitle] = useState(printTemplates.bedHeadTicket.subTitle);
  const [bhtFinancial, setBhtFinancial] = useState(printTemplates.bedHeadTicket.showFinancialInfo);
  const [bhtNurseChecklist, setBhtNurseChecklist] = useState(printTemplates.bedHeadTicket.showNurseChecklist);
  const [bhtSignatures, setBhtSignatures] = useState(printTemplates.bedHeadTicket.showSignatureBlock);
  const [bhtSeal, setBhtSeal] = useState(printTemplates.bedHeadTicket.customSealText);

  const [dischargeHeader, setDischargeHeader] = useState(printTemplates.dischargeSummary.hospitalHeader);
  const [dischargeSubTitle, setDischargeSubTitle] = useState(printTemplates.dischargeSummary.subTitle);
  const [dischargeMeds, setDischargeMeds] = useState(printTemplates.dischargeSummary.showMedicationReconciliation);
  const [dischargeDiet, setDischargeDiet] = useState(printTemplates.dischargeSummary.showDietaryInstructions);
  const [dischargeWarnings, setDischargeWarnings] = useState(printTemplates.dischargeSummary.showWarningSigns);
  const [dischargeSeal, setDischargeSeal] = useState(printTemplates.dischargeSummary.showDoctorSealBlock);
  const [dischargeSuperintendent, setDischargeSuperintendent] = useState(printTemplates.dischargeSummary.showSuperintendentSign);
  const [dischargeDisclaimer, setDischargeDisclaimer] = useState(printTemplates.dischargeSummary.disclaimerText);
  const [templateSavedMsg, setTemplateSavedMsg] = useState("");

  // Custom Bed Creation Form State
  const [newBedNumber, setNewBedNumber] = useState("");
  const [newRoomNumber, setNewRoomNumber] = useState("");
  const [newTower, setNewTower] = useState("Main Tower");
  const [newFloor, setNewFloor] = useState("Floor 2");
  const [newWardName, setNewWardName] = useState("General Surgical Ward 2A");
  const [newCategory, setNewCategory] = useState<"General" | "Semi-Private" | "Private" | "ICU">("General");
  const [newTariff, setNewTariff] = useState("2500");
  const [newFeatures, setNewFeatures] = useState("O2 Wall Outlet, Call Bell");
  const [bedSuccessMsg, setBedSuccessMsg] = useState("");

  // Batch Bed Provisioning State
  const [batchModalOpen, setBatchModalOpen] = useState(false);
  const [batchWardName, setBatchWardName] = useState("Surgical ICU Wing B");
  const [batchTower, setBatchTower] = useState("Main Tower");
  const [batchFloor, setBatchFloor] = useState("Floor 4");
  const [batchRoomPrefix, setBatchRoomPrefix] = useState("R-40");
  const [batchBedPrefix, setBatchBedPrefix] = useState("ICU-");
  const [batchStartNum, setBatchStartNum] = useState(1);
  const [batchCount, setBatchCount] = useState(10);
  const [batchCategory, setBatchCategory] = useState<"General" | "Semi-Private" | "Private" | "ICU">("ICU");
  const [batchTariff, setBatchTariff] = useState("5500");
  const [batchFeatures, setBatchFeatures] = useState("Multi-Para Monitor, Ventilator Ready, O2 Wall Outlet, Suction Unit");

  // Hospital Downtime BCP & Disaster Continuity State
  const [downtimeModeActive, setDowntimeModeActive] = useState(false);
  const [bcpPrintSuccess, setBcpPrintSuccess] = useState("");

  // Hospital Emergency Code Drills State
  const [drillModalOpen, setDrillModalOpen] = useState(false);
  const [selectedDrillCode, setSelectedDrillCode] = useState<"CODE_RED" | "CODE_BLUE" | "CODE_PINK" | "CODE_ORANGE" | "CODE_YELLOW" | "CODE_BLACK">("CODE_RED");
  const [drillLocation, setDrillLocation] = useState("Ward 3B Corridor");
  const [drillResponseSecs, setDrillResponseSecs] = useState("102");
  const [drillStaffCount, setDrillStaffCount] = useState("14");
  const [recentDrills, setRecentDrills] = useState<
    Array<{
      id: string;
      code: "CODE_RED" | "CODE_BLUE" | "CODE_PINK" | "CODE_ORANGE" | "CODE_YELLOW" | "CODE_BLACK";
      location: string;
      date: string;
      responseTime: string;
      staffCount: number;
      result: string;
      evaluator: string;
    }>
  >([
    {
      id: "DRL-2026-041",
      code: "CODE_RED",
      location: "Ward 3B Corridor",
      date: "2026-10-28",
      responseTime: "1m 42s",
      staffCount: 14,
      result: "PASSED (NABH FMS.4)",
      evaluator: "Safety Officer K. Sharma",
    },
    {
      id: "DRL-2026-040",
      code: "CODE_BLUE",
      location: "OPD Waiting Bay 2",
      date: "2026-10-22",
      responseTime: "1m 18s",
      staffCount: 6,
      result: "PASSED (AHA / ACLS)",
      evaluator: "ICU Registrar Dr. Sen",
    },
    {
      id: "DRL-2026-039",
      code: "CODE_PINK",
      location: "NICU Mother Ward",
      date: "2026-10-15",
      responseTime: "2m 04s",
      staffCount: 18,
      result: "PASSED (Infant Security)",
      evaluator: "Chief Security Officer",
    },
  ]);

  const handleBatchAddBeds = () => {
    if (!batchWardName.trim() || batchCount <= 0) {
      alert("Please specify a valid Ward Name and positive count.");
      return;
    }
    const feats = batchFeatures.split(",").map((s) => s.trim()).filter(Boolean);
    const tariffNum = parseInt(batchTariff || "3500", 10);

    for (let i = 0; i < batchCount; i++) {
      const currentNum = batchStartNum + i;
      const bedNumber = `${batchBedPrefix}${currentNum.toString().padStart(2, "0")}`;
      const roomNumber = `${batchRoomPrefix}${Math.floor((currentNum - 1) / 4) + 1}`;
      addBed({
        bedNumber,
        roomNumber,
        tower: batchTower,
        floor: batchFloor,
        wardName: batchWardName.trim(),
        category: batchCategory,
        status: "VACANT_CLEAN",
        dailyTariffRupees: tariffNum,
        features: feats,
      });
    }

    setBatchModalOpen(false);
    setBedSuccessMsg(`Successfully provisioned batch of ${batchCount} operational beds!`);
    setTimeout(() => setBedSuccessMsg(""), 3500);
  };

  const handleRecordEmergencyDrill = () => {
    const drillId = `DRL-${new Date().getFullYear()}-${Math.floor(100 + Math.random() * 900)}`;
    const newDrill = {
      id: drillId,
      code: selectedDrillCode,
      location: drillLocation,
      date: new Date().toISOString().slice(0, 10),
      responseTime: `${drillResponseSecs}s`,
      staffCount: parseInt(drillStaffCount || "10", 10),
      result: parseInt(drillResponseSecs, 10) <= 180 ? "PASSED (NABH FMS.4)" : "ACTION REQUIRED",
      evaluator: "Safety Officer / Drill Commander",
    };
    setRecentDrills([newDrill, ...recentDrills]);
    setDrillModalOpen(false);
  };

  const handlePrintDowntimeBcpPack = () => {
    const targetPrinter = getPrinterForCategory("CLINICAL_A4");
    const timestamp = new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });
    const batchId = `BCP-${Date.now().toString().slice(-6)}`;

    const htmlContent = `
      <div style="font-family: Arial, sans-serif; color: #000; line-height: 1.3; font-size: 11px;">
        <!-- Top Institutional Header -->
        <div style="border-bottom: 2px solid #000; padding-bottom: 6px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: flex-start;">
          <div>
            <div style="font-size: 17px; font-weight: 900; letter-spacing: 0.5px; text-transform: uppercase;">
              ${hospitalProfile.name}
            </div>
            <div style="font-size: 10px; color: #333;">
              ${hospitalProfile.address} | Ph: ${hospitalProfile.phone}
            </div>
            <div style="font-size: 9px; font-weight: bold; color: #b91c1c; margin-top: 2px;">
              ${hospitalProfile.accreditation} • EMERGENCY BUSINESS CONTINUITY PLAN (NABH FMS.8)
            </div>
          </div>
          <div style="text-align: right; border: 1.5px solid #000; padding: 4px 8px; border-radius: 4px; background: #fee2e2;">
            <div style="font-size: 11px; font-weight: 900; color: #991b1b;">FORM ADM-BCP-01</div>
            <div style="font-size: 9px; font-weight: bold; color: #000;">OFFLINE CONTINGENCY PACK</div>
            <div style="font-size: 8px; font-family: monospace;">BATCH: ${batchId}</div>
          </div>
        </div>

        <div style="background: #fef2f2; border: 1px solid #f87171; padding: 6px 10px; margin-bottom: 12px; border-radius: 4px;">
          <div style="font-weight: 900; color: #991b1b; font-size: 11px; text-transform: uppercase;">
            ⚠️ CRITICAL NOTICE: ACTIVE SYSTEM DOWNTIME / DISASTER OPERATIONAL MODE
          </div>
          <div style="font-size: 9.5px; color: #333; margin-top: 2px;">
            This packet contains statutory paper counterparts for clinical care during HIS/network outages. All entries must be documented in ballpoint pen and preserved for post-recovery reconciliation under NABH Standard COP.2.
          </div>
        </div>

        <!-- FORM 1: EMERGENCY TRIAGE DOCKET -->
        <div style="border: 1.5px solid #000; border-radius: 4px; padding: 8px; margin-bottom: 14px; page-break-inside: avoid;">
          <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #000; padding-bottom: 4px; margin-bottom: 6px;">
            <div style="font-weight: 900; font-size: 11px; text-transform: uppercase;">
              1. EMERGENCY DEPARTMENT START OFFLINE TRIAGE & INTAKE DOCKET
            </div>
            <div style="font-size: 9px; font-weight: bold;">STAT-ER-DOWNTIME</div>
          </div>

          <div style="display: grid; grid-template-columns: 2fr 1fr 1fr 1fr; gap: 6px; margin-bottom: 6px; font-size: 10px;">
            <div style="border-bottom: 1px dotted #000; padding-bottom: 2px;"><b>Patient Name:</b> ___________________________</div>
            <div style="border-bottom: 1px dotted #000; padding-bottom: 2px;"><b>Age / Sex:</b> ___ / ___</div>
            <div style="border-bottom: 1px dotted #000; padding-bottom: 2px;"><b>Temp UHID:</b> ____________</div>
            <div style="border-bottom: 1px dotted #000; padding-bottom: 2px;"><b>Time Arrived:</b> _______</div>
          </div>

          <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px; margin: 6px 0; text-align: center; font-size: 9.5px; font-weight: bold;">
            <div style="border: 2px solid #dc2626; background: #fee2e2; color: #991b1b; padding: 4px; border-radius: 3px;">
              [ ] RED (IMMEDIATE)<br/><span style="font-size: 8px; font-weight: normal;">Resp &gt; 30, Pulse weak, Unconscious</span>
            </div>
            <div style="border: 2px solid #f59e0b; background: #fef3c7; color: #92400e; padding: 4px; border-radius: 3px;">
              [ ] YELLOW (DELAYED)<br/><span style="font-size: 8px; font-weight: normal;">Serious fracture, severe pain, stable</span>
            </div>
            <div style="border: 2px solid #16a34a; background: #dcfce7; color: #166534; padding: 4px; border-radius: 3px;">
              [ ] GREEN (WALKING)<br/><span style="font-size: 8px; font-weight: normal;">Minor lacerations, ambulating</span>
            </div>
            <div style="border: 2px solid #000; background: #e2e8f0; color: #000; padding: 4px; border-radius: 3px;">
              [ ] BLACK (EXPECTANT)<br/><span style="font-size: 8px; font-weight: normal;">No respiration after airway cleared</span>
            </div>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr 1fr; gap: 4px; font-size: 9px; margin-top: 6px;">
            <div style="border: 1px solid #999; padding: 2px 4px;">BP: _____ / _____ mmHg</div>
            <div style="border: 1px solid #999; padding: 2px 4px;">HR: _____ bpm</div>
            <div style="border: 1px solid #999; padding: 2px 4px;">SpO2: _____ %</div>
            <div style="border: 1px solid #999; padding: 2px 4px;">GCS (E+V+M): _____ / 15</div>
            <div style="border: 1px solid #999; padding: 2px 4px;">GRBS: _____ mg/dL</div>
          </div>
        </div>

        <!-- FORM 2: DOCTOR OFFLINE CLINICAL ORDER & PRESCRIPTION SHEET -->
        <div style="border: 1.5px solid #000; border-radius: 4px; padding: 8px; margin-bottom: 14px; page-break-inside: avoid;">
          <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #000; padding-bottom: 4px; margin-bottom: 6px;">
            <div style="font-weight: 900; font-size: 11px; text-transform: uppercase;">
              2. PHYSICIAN DOWNTIME CPOE &amp; STAT PRESCRIPTION SHEET
            </div>
            <div style="font-size: 9px; font-weight: bold; color: #b91c1c;">MANDATORY ALLERGY CHECK</div>
          </div>

          <div style="background: #fffbeb; border: 1px solid #f59e0b; padding: 4px 6px; font-size: 9.5px; margin-bottom: 6px; display: flex; justify-content: space-between;">
            <div><b>Known Drug Allergies:</b> [ ] NKDA &nbsp;&nbsp;&nbsp; [ ] Penicillin &nbsp;&nbsp;&nbsp; [ ] Sulfa &nbsp;&nbsp;&nbsp; [ ] NSAIDs &nbsp;&nbsp;&nbsp; [ ] Other: ______________________</div>
          </div>

          <table style="width: 100%; border-collapse: collapse; font-size: 9px; margin-bottom: 8px;">
            <thead>
              <tr style="background: #f1f5f9; border: 1px solid #000;">
                <th style="border: 1px solid #000; padding: 3px; width: 5%;">#</th>
                <th style="border: 1px solid #000; padding: 3px; width: 35%;">Drug Generic Name &amp; Strength</th>
                <th style="border: 1px solid #000; padding: 3px; width: 15%;">Dose &amp; Route</th>
                <th style="border: 1px solid #000; padding: 3px; width: 15%;">Frequency</th>
                <th style="border: 1px solid #000; padding: 3px; width: 15%;">Duration</th>
                <th style="border: 1px solid #000; padding: 3px; width: 15%;">Nurse Admin Sign</th>
              </tr>
            </thead>
            <tbody>
              ${[1, 2, 3, 4].map((i) => `
                <tr style="height: 22px;">
                  <td style="border: 1px solid #000; text-align: center; font-weight: bold;">${i}</td>
                  <td style="border: 1px solid #000; padding: 2px;"></td>
                  <td style="border: 1px solid #000; padding: 2px;"></td>
                  <td style="border: 1px solid #000; padding: 2px;"></td>
                  <td style="border: 1px solid #000; padding: 2px;"></td>
                  <td style="border: 1px solid #000; padding: 2px;"></td>
                </tr>
              `).join("")}
            </tbody>
          </table>

          <div style="display: flex; justify-content: space-between; font-size: 9px; margin-top: 4px;">
            <div>Clinical Diagnosis / Directives: ________________________________________________</div>
            <div style="border-top: 1px solid #000; padding-top: 2px; width: 220px; text-align: center;">
              <b>Treating Clinician Sign &amp; NMC Reg No.</b>
            </div>
          </div>
        </div>

        <!-- FORM 3: STAT UNCROSSMATCHED BLOOD REQUISITION -->
        <div style="border: 1.5px solid #000; border-radius: 4px; padding: 8px; margin-bottom: 14px; page-break-inside: avoid;">
          <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #000; padding-bottom: 4px; margin-bottom: 6px;">
            <div style="font-weight: 900; font-size: 11px; text-transform: uppercase;">
              3. STAT UNCROSSMATCHED EMERGENCY BLOOD RELEASE FORM
            </div>
            <div style="font-size: 9px; font-weight: bold;">FORM 27-C DOWNTIME</div>
          </div>

          <div style="font-size: 9px; margin-bottom: 4px;">
            [ ] <b>EMERGENCY O-NEGATIVE / UNCROSSMATCHED PROTOCOL:</b> I certify that waiting for standard crossmatching entails imminent loss of life.
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 6px; font-size: 9px;">
            <div>Product: [ ] PRBC [ ] FFP [ ] Platelets</div>
            <div>Units: _________</div>
            <div>Patient ABO/Rh: _________</div>
            <div>Clinician Signature: __________________</div>
          </div>
        </div>

        <!-- FORM 4: MANUAL CASHIER COUNTERFOIL RECEIPT -->
        <div style="border: 1.5px dashed #000; border-radius: 4px; padding: 8px; page-break-inside: avoid; background: #fafafa;">
          <div style="display: flex; justify-content: space-between; border-bottom: 1px dashed #000; padding-bottom: 4px; margin-bottom: 6px;">
            <div style="font-weight: 900; font-size: 11px; text-transform: uppercase;">
              4. MANUAL CASHIER EMERGENCY RECEIPT &amp; AUDIT COUNTERFOIL
            </div>
            <div style="font-size: 9px; font-weight: bold;">SERIES: MAN-${batchId}</div>
          </div>

          <div style="display: grid; grid-template-columns: 2fr 1fr 1fr; gap: 6px; font-size: 9.5px; margin-bottom: 4px;">
            <div>Received from: ____________________________________</div>
            <div>Dept: [ ] OPD [ ] IPD [ ] ER</div>
            <div>Tender: [ ] Cash [ ] UPI Manual Ref</div>
          </div>
          <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 6px; font-size: 9.5px;">
            <div>Gross: ₹ _____________</div>
            <div>Concession: ₹ _____________</div>
            <div><b>Net Received: ₹ _____________</b></div>
            <div style="text-align: right;">Cashier Sign: __________________</div>
          </div>
        </div>

        <!-- Footer Verification -->
        <div style="margin-top: 10px; border-top: 1px solid #999; padding-top: 4px; display: flex; justify-content: space-between; font-size: 8px; color: #555;">
          <div>Print Category: <b>CLINICAL_A4</b> | Configured Device: <b>${targetPrinter ? targetPrinter.name : "System Default Laser/A4"}</b></div>
          <div>Generated At: ${timestamp} | Hospital business continuity framework</div>
        </div>
      </div>
    `;

    printDocument(htmlContent, {
      title: `Emergency Downtime Clinical Pack — ${batchId}`,
      docType: "CLINICAL_SUMMARY",
      printerDevice: targetPrinter,
    });

    setBcpPrintSuccess(`Offline Contingency Pack (${batchId}) dispatched to ${targetPrinter ? targetPrinter.name : "A4 Laser Printer"}.`);
    setTimeout(() => setBcpPrintSuccess(""), 4000);
  };

  const handlePrintFacilityComplianceDossier = () => {
    const targetPrinter = getPrinterForCategory("CLINICAL_A4");
    const timestamp = new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });

    const htmlContent = `
      <div style="font-family: Arial, sans-serif; color: #000; line-height: 1.35; font-size: 10.5px;">
        <div style="border-bottom: 2px solid #000; padding-bottom: 6px; margin-bottom: 12px; display: flex; justify-content: space-between; align-items: flex-start;">
          <div>
            <div style="font-size: 17px; font-weight: 900; letter-spacing: 0.5px; text-transform: uppercase;">
              ${hospitalProfile.name}
            </div>
            <div style="font-size: 10px; color: #333;">
              ${hospitalProfile.address} | Ph: ${hospitalProfile.phone}
            </div>
            <div style="font-size: 9px; font-weight: bold; color: #1e3a8a; margin-top: 2px;">
              FACILITY MANAGEMENT & SAFETY (FMS) EXECUTIVE STATUTORY AUDIT DOSSIER
            </div>
          </div>
          <div style="text-align: right; border: 1.5px solid #000; padding: 4px 8px; border-radius: 4px; background: #f0fdf4;">
            <div style="font-size: 11px; font-weight: 900; color: #166534;">FORM NABH-FMS-01</div>
            <div style="font-size: 8px; font-weight: bold; color: #000;">NABH 5TH EDITION / CPCB COMPLIANCE</div>
            <div style="font-size: 8px; font-family: monospace;">AUDIT DATE: ${new Date().toISOString().slice(0, 10)}</div>
          </div>
        </div>

        <div style="border: 1px solid #000; padding: 8px; border-radius: 4px; margin-bottom: 10px; background: #fafafa;">
          <div style="font-weight: 900; font-size: 11px; text-transform: uppercase; margin-bottom: 4px; color: #0f172a;">
            1. BIO-MEDICAL WASTE (BMW) MANAGEMENT STATUTORY ANNUAL RETURN (CPCB FORM IV)
          </div>
          <table style="width: 100%; border-collapse: collapse; font-size: 9.5px; margin-bottom: 4px;">
            <thead>
              <tr style="background: #e2e8f0; border: 1px solid #000;">
                <th style="border: 1px solid #000; padding: 3px;">Category</th>
                <th style="border: 1px solid #000; padding: 3px;">Color Code</th>
                <th style="border: 1px solid #000; padding: 3px;">Waste Description</th>
                <th style="border: 1px solid #000; padding: 3px;">Annual Generation</th>
                <th style="border: 1px solid #000; padding: 3px;">Treatment / Disposal Mode</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style="border: 1px solid #000; padding: 3px; font-weight: bold;">Yellow</td>
                <td style="border: 1px solid #000; padding: 3px; background: #fef08a;">Yellow Non-Chlorinated</td>
                <td style="border: 1px solid #000; padding: 3px;">Human anatomical, soiled cotton, expired drugs</td>
                <td style="border: 1px solid #000; padding: 3px; font-family: monospace; font-weight: bold;">4,820.5 kg</td>
                <td style="border: 1px solid #000; padding: 3px;">Common Bio-medical Incineration (1050°C)</td>
              </tr>
              <tr>
                <td style="border: 1px solid #000; padding: 3px; font-weight: bold;">Red</td>
                <td style="border: 1px solid #000; padding: 3px; background: #fecaca;">Red Autoclave Safe</td>
                <td style="border: 1px solid #000; padding: 3px;">Contaminated plastics, tubing, catheters, IV bottles</td>
                <td style="border: 1px solid #000; padding: 3px; font-family: monospace; font-weight: bold;">7,142.0 kg</td>
                <td style="border: 1px solid #000; padding: 3px;">Autoclaving + Shredding + Recycling</td>
              </tr>
              <tr>
                <td style="border: 1px solid #000; padding: 3px; font-weight: bold;">White (Translucent)</td>
                <td style="border: 1px solid #000; padding: 3px; background: #f8fafc;">Puncture-Proof Container</td>
                <td style="border: 1px solid #000; padding: 3px;">Needles, scalpels, blades, fixed needles</td>
                <td style="border: 1px solid #000; padding: 3px; font-family: monospace; font-weight: bold;">892.4 kg</td>
                <td style="border: 1px solid #000; padding: 3px;">Autoclaving + Encapsulation / Metal Sharp Pit</td>
              </tr>
              <tr>
                <td style="border: 1px solid #000; padding: 3px; font-weight: bold;">Blue</td>
                <td style="border: 1px solid #000; padding: 3px; background: #bfdbfe;">Cardboard Box / Blue Mark</td>
                <td style="border: 1px solid #000; padding: 3px;">Glassware, medicine vials, ampoules</td>
                <td style="border: 1px solid #000; padding: 3px; font-family: monospace; font-weight: bold;">1,425.8 kg</td>
                <td style="border: 1px solid #000; padding: 3px;">1% Sodium Hypochlorite Disinfection + Recycling</td>
              </tr>
            </tbody>
          </table>
          <div style="font-size: 8.5px; color: #475569;">
            Authorized Transporter: <b>CleanEnv Solutions Pvt Ltd (Auth No: CPCB/BMW-TR-81/2024, Valid to: 31-Dec-2028)</b> • 100% Barcoded Bag Manifesting active.
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;">
          <!-- 2. Fire Safety -->
          <div style="border: 1px solid #000; padding: 6px; border-radius: 4px;">
            <div style="font-weight: 900; font-size: 10px; text-transform: uppercase; margin-bottom: 2px;">
              2. FIRE SAFETY &amp; LIFE PROTECTION (FMS.4)
            </div>
            <div style="font-size: 9px;">• State Fire Service NOC: <b>FS-NOC-2024-9182 (Valid to 14-Nov-2027)</b></div>
            <div style="font-size: 9px;">• Wet Riser &amp; Yard Hydrant Pressure: <b>7.2 kg/cm² (Weekly Tested)</b></div>
            <div style="font-size: 9px;">• Optical Smoke Detectors: <b>128/128 Operational (Tested Oct 2026)</b></div>
            <div style="font-size: 9px;">• Evacuation Mock Drills: <b>Completed 28-Oct-2026 (Avg time: 1m 42s)</b></div>
          </div>

          <!-- 3. AERB Radiation Safety -->
          <div style="border: 1px solid #000; padding: 6px; border-radius: 4px;">
            <div style="font-weight: 900; font-size: 10px; text-transform: uppercase; margin-bottom: 2px;">
              3. AERB RADIATION SAFETY (NABH FMS.6)
            </div>
            <div style="font-size: 9px;">• Radiological Safety Officer: <b>Dr. S. Nambiar (RSO-III Reg #AERB-8821)</b></div>
            <div style="font-size: 9px;">• 128-Slice CT &amp; Digital X-Ray QA: <b>Calibrated &amp; Certified (Sep 2026)</b></div>
            <div style="font-size: 9px;">• Lead Apron Integrity: <b>24/24 aprons 0.5mm Pb eq. inspected (0 tears)</b></div>
            <div style="font-size: 9px;">• Staff TLD Badges: <b>18 Badges quarterly monitored (All &lt; 1 mSv)</b></div>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px;">
          <!-- 4. Medical Gas Pipeline -->
          <div style="border: 1px solid #000; padding: 6px; border-radius: 4px;">
            <div style="font-weight: 900; font-size: 10px; text-transform: uppercase; margin-bottom: 2px;">
              4. MEDICAL GAS PIPELINE SYSTEM (MGPS)
            </div>
            <div style="font-size: 9px;">• Cryogenic Liquid Medical O2 (LMO): <b>10,000 Liters Vessel (99.4% Purity)</b></div>
            <div style="font-size: 9px;">• Emergency Backup Manifold: <b>60 High-Pressure D-Type Cylinders</b></div>
            <div style="font-size: 9px;">• Terminal Line Pressure: <b>O2 4.2 Bar • Suction -60 kPa • MedAir 4 Bar</b></div>
            <div style="font-size: 9px;">• Master Alarm Panel: <b>Audible/Visual sensors active in ICU &amp; Control Room</b></div>
          </div>

          <!-- 5. Emergency Power & Water -->
          <div style="border: 1px solid #000; padding: 6px; border-radius: 4px;">
            <div style="font-weight: 900; font-size: 10px; text-transform: uppercase; margin-bottom: 2px;">
              5. EMERGENCY UTILITIES &amp; INFECTION SAFETY
            </div>
            <div style="font-size: 9px;">• Dual Cummins DG Sets: <b>500 kVA + 380 kVA with ATS (12s cutover)</b></div>
            <div style="font-size: 9px;">• On-Site Fuel Reserve: <b>4,000 Liters HSD (72 hours full load runtime)</b></div>
            <div style="font-size: 9px;">• Drinking &amp; Dialysis RO Water: <b>TDS 42 ppm, E. coli: 0 CFU/100ml</b></div>
            <div style="font-size: 9px;">• Legionella Water Test: <b>Negative (NABL Report #LAB-W-2026-904)</b></div>
          </div>
        </div>

        <!-- Statutory Endorsement & Seals -->
        <div style="margin-top: 14px; border-top: 1.5px solid #000; padding-top: 8px; display: grid; grid-template-columns: 1fr 1fr 1fr; text-align: center; font-size: 9.5px;">
          <div>
            ____________________________________<br/>
            <b>Er. K. Sharma, B.E. (Mech)</b><br/>
            Chief Biomedical &amp; Facility Engineer
          </div>
          <div>
            ____________________________________<br/>
            <b>Dr. R. Swaminathan, MD (Micro)</b><br/>
            Infection Control &amp; BMW Officer
          </div>
          <div>
            ____________________________________<br/>
            <b>Dr. A. Sengupta, MS, MHA</b><br/>
            Medical Superintendent &amp; Director
          </div>
        </div>

        <div style="margin-top: 10px; border-top: 1px solid #ccc; padding-top: 4px; display: flex; justify-content: space-between; font-size: 8px; color: #555;">
          <div>Print Category: <b>CLINICAL_A4</b> | Hardware Device: <b>${targetPrinter ? targetPrinter.name : "System Default Laser/A4"}</b></div>
          <div>Statutory Verification Timestamp: ${timestamp} | Hospital audit record</div>
        </div>
      </div>
    `;

    printDocument(htmlContent, {
      title: "Statutory Facility Management & Safety Dossier",
      docType: "CLINICAL_SUMMARY",
      printerDevice: targetPrinter,
    });
  };

  const handlePrintEmergencyPlacard = () => {
    const targetPrinter = getPrinterForCategory("CLINICAL_A4");
    const timestamp = new Date().toLocaleString("en-IN", { timeZone: "Asia/Kolkata" });

    const htmlContent = `
      <div style="font-family: Arial, sans-serif; color: #000; line-height: 1.25; font-size: 10.5px;">
        <div style="text-align: center; border-bottom: 3px solid #000; padding-bottom: 6px; margin-bottom: 8px;">
          <div style="font-size: 18px; font-weight: 900; letter-spacing: 1px; text-transform: uppercase;">
            ${hospitalProfile.name}
          </div>
          <div style="font-size: 13px; font-weight: 900; color: #b91c1c; text-transform: uppercase; margin-top: 2px;">
            EMERGENCY HOSPITAL CODE RESPONSE QUICK REFERENCE PROTOCOL
          </div>
          <div style="font-size: 9.5px; font-weight: bold; color: #333;">
            MANDATORY POSTING AT ALL NURSING STATIONS, ICUS, OTS &amp; OPERATIONAL CORRIDORS (NABH FMS.4)
          </div>
          <div style="display: inline-block; background: #fee2e2; border: 2px solid #dc2626; padding: 3px 12px; border-radius: 4px; font-weight: 900; font-size: 11px; color: #991b1b; margin-top: 4px;">
            INTERNAL EMERGENCY SPEED DIAL: EXT 2222 / EXT 3333
          </div>
        </div>

        <table style="width: 100%; border-collapse: collapse; font-size: 9.5px; margin-bottom: 8px;">
          <thead>
            <tr style="background: #0f172a; color: #fff; text-align: left;">
              <th style="padding: 4px; border: 1px solid #000; width: 18%;">Emergency Code</th>
              <th style="padding: 4px; border: 1px solid #000; width: 22%;">Clinical / Crisis Event</th>
              <th style="padding: 4px; border: 1px solid #000; width: 35%;">Immediate First-Responder Actions</th>
              <th style="padding: 4px; border: 1px solid #000; width: 25%;">Primary Response Team</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="padding: 5px; border: 1px solid #000; font-weight: 900; background: #fee2e2; color: #991b1b;">
                🔴 CODE RED
              </td>
              <td style="padding: 5px; border: 1px solid #000; font-weight: bold;">
                FIRE / SMOKE DETECTED
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                <b>R.A.C.E.:</b> Rescue patients in immediate danger &bull; Alarm (pull pull-station) &bull; Contain (close fire doors) &bull; Extinguish / Evacuate.
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Fire Safety Team &bull; Ward Staff &bull; Security (Ext 2222)
              </td>
            </tr>
            <tr>
              <td style="padding: 5px; border: 1px solid #000; font-weight: 900; background: #dbeafe; color: #1e40af;">
                🔵 CODE BLUE
              </td>
              <td style="padding: 5px; border: 1px solid #000; font-weight: bold;">
                CARDIAC / RESPIRATORY ARREST
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Announce location via PA &bull; Initiate CPR immediately (30:2) &bull; Bring Crash Cart &amp; Defibrillator &bull; Maintain airway.
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                ICU Registrar &bull; Anaesthesiologist &bull; Code Blue Nurse Team
              </td>
            </tr>
            <tr>
              <td style="padding: 5px; border: 1px solid #000; font-weight: 900; background: #fce7f3; color: #9d174d;">
                🌸 CODE PINK
              </td>
              <td style="padding: 5px; border: 1px solid #000; font-weight: bold;">
                INFANT / CHILD ABDUCTION
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Lock all perimeter hospital exits immediately &bull; Stop and inspect all large bags, strollers, blankets &bull; Alert CCTV command.
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Chief Security Officer &bull; Floor Wardens &bull; Local Police
              </td>
            </tr>
            <tr>
              <td style="padding: 5px; border: 1px solid #000; font-weight: 900; background: #ffedd5; color: #9a3412;">
                🟠 CODE ORANGE
              </td>
              <td style="padding: 5px; border: 1px solid #000; font-weight: bold;">
                MASS CASUALTY DISASTER (MCI)
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Clear Emergency Department bays &bull; Activate Incident Command System (ICS) &bull; Mobilize off-duty trauma surgeons &bull; Stock O-Neg blood.
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Trauma &amp; Emergency HOD &bull; Nursing Superintendent
              </td>
            </tr>
            <tr>
              <td style="padding: 5px; border: 1px solid #000; font-weight: 900; background: #fef9c3; color: #854d0e;">
                🟡 CODE YELLOW
              </td>
              <td style="padding: 5px; border: 1px solid #000; font-weight: bold;">
                HAZARDOUS MATERIAL / CHEMICAL SPILL
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Evacuate spill zone immediately &bull; Do NOT touch substance &bull; Deploy Hazmat Spill Kit &bull; Neutralize acid/alkali per SDS.
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Hospital Hazmat Team &bull; Housekeeping In-charge
              </td>
            </tr>
            <tr>
              <td style="padding: 5px; border: 1px solid #000; font-weight: 900; background: #f1f5f9; color: #000;">
                ⚫ CODE BLACK
              </td>
              <td style="padding: 5px; border: 1px solid #000; font-weight: bold;">
                ARMED INTRUDER / BOMB THREAT
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Run, Hide, Fight protocol &bull; Lock and barricade doors &bull; Silence mobile phones &bull; Do NOT use elevators &bull; Await SWAT/Police all-clear.
              </td>
              <td style="padding: 5px; border: 1px solid #000;">
                Armed Security &bull; Police Control Room (112)
              </td>
            </tr>
          </tbody>
        </table>

        <div style="border: 1px solid #000; padding: 5px; border-radius: 4px; font-size: 8.5px; background: #f8fafc; display: flex; justify-content: space-between;">
          <div>Placard Serial: <b>ADM-CODE-PLACARD-V4</b> | Routing Category: <b>CLINICAL_A4</b></div>
          <div>Approved by: <b>Medical Superintendent &amp; Safety Committee Chairman</b></div>
          <div>Printed: ${timestamp}</div>
        </div>
      </div>
    `;

    printDocument(htmlContent, {
      title: "Statutory Hospital Emergency Code Wall Placard",
      docType: "CLINICAL_SUMMARY",
      printerDevice: targetPrinter,
    });
  };

  // Custom Doctor Creation Form State with Revisit Rules
  const [newDocName, setNewDocName] = useState("");
  const [newDocSpecialty, setNewDocSpecialty] = useState("");
  const [newDocDept, setNewDocDept] = useState("General Medicine");
  const [newDocRoom, setNewDocRoom] = useState("OPD Cabin 104");
  const [newDocFee, setNewDocFee] = useState("600");
  const [newDocRevisitDays, setNewDocRevisitDays] = useState("7");
  const [newDocMaxFreeVisits, setNewDocMaxFreeVisits] = useState("1");
  const [newDocDiscountPct, setNewDocDiscountPct] = useState("100");
  const [docSuccessMsg, setDocSuccessMsg] = useState("");

  // Hospital Profile Edit State
  const [editHospName, setEditHospName] = useState(hospitalProfile.name);
  const [editHospAddress, setEditHospAddress] = useState(hospitalProfile.address);
  const [editHospPhone, setEditHospPhone] = useState(hospitalProfile.phone);
  const [editHospAccreditation, setEditHospAccreditation] = useState(hospitalProfile.accreditation);
  const [profileSavedMsg, setProfileSavedMsg] = useState("");
  const [brandDisplayName, setBrandDisplayName] = useState("");
  const [brandTagline, setBrandTagline] = useState("");
  const [brandLogoUrl, setBrandLogoUrl] = useState("");
  const [brandFaviconUrl, setBrandFaviconUrl] = useState("");
  const [brandPrimaryColor, setBrandPrimaryColor] = useState("#2563EB");
  const [brandSecondaryColor, setBrandSecondaryColor] = useState("#0F172A");
  const [brandAccentColor, setBrandAccentColor] = useState("#0D9488");
  const [brandSaving, setBrandSaving] = useState(false);
  const [brandSavedMsg, setBrandSavedMsg] = useState("");
  const [brandError, setBrandError] = useState("");
  const [brandAssetUploading, setBrandAssetUploading] = useState<"logo" | "favicon" | null>(null);

  useEffect(() => {
    if (!branding) return;
    setBrandDisplayName(branding.display_name || branding.hospital_name);
    setBrandTagline(branding.tagline || "");
    setBrandLogoUrl(branding.logo_url || "");
    setBrandFaviconUrl(branding.favicon_url || "");
    setBrandPrimaryColor(branding.primary_color);
    setBrandSecondaryColor(branding.secondary_color);
    setBrandAccentColor(branding.accent_color);
  }, [branding]);

  const handleBrandAssetUpload = async (kind: "logo" | "favicon", file?: File) => {
    if (!file) return;
    setBrandAssetUploading(kind);
    setBrandError("");
    setBrandSavedMsg("");
    try {
      await uploadAsset(file, kind);
      setBrandSavedMsg(kind === "logo" ? "Tenant logo uploaded and applied." : "Tenant favicon uploaded and applied.");
    } catch (error) {
      setBrandError(error instanceof Error ? error.message : "Brand asset upload failed.");
    } finally {
      setBrandAssetUploading(null);
    }
  };

  const handleSaveTenantBranding = async () => {
    if (brandDisplayName.trim().length < 2) {
      setBrandError("Enter a display name with at least two characters.");
      return;
    }
    setBrandSaving(true);
    setBrandError("");
    setBrandSavedMsg("");
    try {
      await updateBranding({
        display_name: brandDisplayName.trim(),
        tagline: brandTagline.trim() || null,
        logo_url: brandLogoUrl.trim() || null,
        favicon_url: brandFaviconUrl.trim() || null,
        primary_color: brandPrimaryColor,
        secondary_color: brandSecondaryColor,
        accent_color: brandAccentColor,
      });
      setBrandSavedMsg("Tenant branding saved and applied.");
    } catch (error) {
      setBrandError(error instanceof Error ? error.message : "Branding could not be saved.");
    } finally {
      setBrandSaving(false);
    }
  };

  // Metrics Catalog Filters
  const [metricSearch, setMetricSearch] = useState("");
  const [selectedDomainId, setSelectedDomainId] = useState<number | "ALL">("ALL");
  const [selectedCategory, setSelectedCategory] = useState<string>("ALL");

  const filteredMetrics = SAMPLE_METRIC_CATALOG.filter((m) => {
    const matchesDomain = selectedDomainId === "ALL" || m.domainId === selectedDomainId;
    const matchesCategory = selectedCategory === "ALL" || m.category === selectedCategory;
    const matchesSearch =
      !metricSearch.trim() ||
      m.name.toLowerCase().includes(metricSearch.toLowerCase()) ||
      m.description.toLowerCase().includes(metricSearch.toLowerCase()) ||
      m.formula.toLowerCase().includes(metricSearch.toLowerCase()) ||
      m.domainName.toLowerCase().includes(metricSearch.toLowerCase());
    return matchesDomain && matchesCategory && matchesSearch;
  });

  const [inventory, setInventory] = useState<{
    tenant_id: number;
    total_hospital_records: number;
    timestamp_utc: string;
    tables: Record<string, number>;
  } | null>(null);
  const [liveMetrics, setLiveMetrics] = useState<ExecutiveCommandCenterData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);

  // Register Preview Modal
  const [activePreviewRegister, setActivePreviewRegister] = useState<{
    name: string;
    code: string;
    headers: string[];
    rows: string[][];
    isLive: boolean;
    endpoint: string;
  } | null>(null);

  const loadDataInventory = async () => {
    setIsLoading(true);
    try {
      const [invData, metricsData] = await Promise.allSettled([
        registersApi.getDataInventory(),
        analyticsApi.getExecutiveCommandCenter(),
      ]);
      if (invData.status === "fulfilled") {
        setInventory(invData.value);
      }
      if (metricsData.status === "fulfilled") {
        setLiveMetrics(metricsData.value);
      }
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    } finally {
      setIsLoading(false);
    }
  };

  const handlePreviewRegister = async (reg: (typeof registers)[0]) => {
    setIsPreviewLoading(true);
    try {
      if (reg.code === "MIDNIGHT-CENSUS") {
        const res = (await registersApi.getMidnightCensus()) as { items?: Array<Record<string, unknown>> };
        if (res && res.items && Array.isArray(res.items) && res.items.length > 0) {
          const rows = res.items.slice(0, 5).map((it) => [
            String(it.census_date || ""),
            "All Wards",
            String(it.total_licensed_beds || "0"),
            String(it.new_admissions || "0"),
            String(it.total_discharges || "0"),
            String(it.total_deaths || "0"),
            `${it.bor_percent || 0}%`,
          ]);
          setActivePreviewRegister({
            name: reg.name,
            code: reg.code,
            headers: reg.previewHeaders,
            rows,
            isLive: true,
            endpoint: reg.endpoint,
          });
          return;
        }
      } else if (reg.code === "CASHIER-RECON") {
        const res = (await registersApi.getCashierReconciliation()) as { items?: Array<Record<string, unknown>> };
        if (res && res.items && Array.isArray(res.items) && res.items.length > 0) {
          const rows = res.items.slice(0, 5).map((it) => [
            `SHF-${it.id || "001"}`,
            String(it.counter_id || "COUNTER-01"),
            String(it.cashier_name || "operator"),
            `₹${(((it.cash_amount_paise as number) || 0) / 100).toLocaleString("en-IN")}`,
            `₹${(((it.upi_amount_paise as number) || 0) / 100).toLocaleString("en-IN")}`,
            `₹${(((it.card_amount_paise as number) || 0) / 100).toLocaleString("en-IN")}`,
            `₹${(((it.variance_paise as number) || 0) / 100).toLocaleString("en-IN")}`,
          ]);
          setActivePreviewRegister({
            name: reg.name,
            code: reg.code,
            headers: reg.previewHeaders,
            rows,
            isLive: true,
            endpoint: reg.endpoint,
          });
          return;
        }
      } else if (reg.code === "NDPS-LEDGER") {
        const res = (await registersApi.getNdpsLedger()) as { items?: Array<Record<string, unknown>> };
        if (res && res.items && Array.isArray(res.items) && res.items.length > 0) {
          const rows = res.items.slice(0, 5).map((it) => [
            it.created_at ? String(it.created_at).substring(0, 16).replace("T", " ") : "2026-10-31 18:20",
            String(it.substance_name || "Morphine Sulfate 10mg"),
            String(it.batch_number || "MOR-9982-A"),
            String(it.movement_type || "DISPENSE"),
            `${it.quantity} amps`,
            String(it.witness_name || "Dr. Radhika Sen"),
            `${it.closing_balance || 42} amps`,
          ]);
          setActivePreviewRegister({
            name: reg.name,
            code: reg.code,
            headers: reg.previewHeaders,
            rows,
            isLive: true,
            endpoint: reg.endpoint,
          });
          return;
        }
      }
    } catch (err) {
      console.warn("Live register preview fallback:", err);
    } finally {
      setIsPreviewLoading(false);
    }

    // Standard fallback schema preview
    setActivePreviewRegister({
      name: reg.name,
      code: reg.code,
      headers: reg.previewHeaders,
      rows: reg.previewRows,
      isLive: false,
      endpoint: reg.endpoint,
    });
  };

  useEffect(() => {
    loadDataInventory();
  }, []);

  const registers = [
    {
      name: "Daily Midnight ADT Bed Census Register",
      code: "MIDNIGHT-CENSUS",
      description: "Opening beds, inpatient admissions, discharges, deaths, BOR % occupancy rate.",
      endpoint: "/api/registers/midnight-census?format=csv",
      format: "RFC 4180 CSV (BOM)",
      previewHeaders: ["Date", "Ward", "Beds Total", "Admissions", "Discharges", "Deaths", "BOR %"],
      previewRows: [
        ["2026-10-31", "ICU Step-down", "24", "6", "4", "0", "91.6%"],
        ["2026-10-31", "General Ward 1", "40", "12", "10", "0", "87.5%"],
        ["2026-10-31", "Maternity & NICU", "18", "4", "3", "0", "83.3%"],
      ],
    },
    {
      name: "Cashier Shift Handover & Reconciliation Ledger",
      code: "CASHIER-RECON",
      description: "Counter collections by tender (Cash, UPI, Card, NetBanking), shift variances.",
      endpoint: "/api/registers/cashier-shift-reconciliation?format=csv",
      format: "RFC 4180 CSV (BOM)",
      previewHeaders: ["Shift ID", "Counter", "Cashier", "Cash Collected", "UPI", "Card", "Variance"],
      previewRows: [
        ["SHF-0012", "COUNTER-01", "operator", "₹14,500.00", "₹38,200.00", "₹22,000.00", "₹0.00"],
        ["SHF-0011", "COUNTER-02", "cashier_b", "₹18,000.00", "₹45,100.00", "₹15,400.00", "-₹200.00"],
      ],
    },
    {
      name: "NDPS Schedule H1 Narcotics Controlled Substances Register",
      code: "NDPS-LEDGER",
      description: "Perpetual double-custody ledger with batch numbers, movements, and witness sign-offs.",
      endpoint: "/api/registers/ndps-ledger?format=csv",
      format: "RFC 4180 CSV (BOM)",
      previewHeaders: ["Timestamp", "Substance", "Batch", "Type", "Qty", "Witness Doctor", "Balance"],
      previewRows: [
        ["2026-10-31 18:20", "Morphine Sulfate 10mg", "MOR-9982-A", "DISPENSE", "-2 amps", "Dr. Radhika Sen", "42 amps"],
        ["2026-10-31 14:15", "Fentanyl 50mcg", "FEN-7741-C", "DISPENSE", "-1 amp", "Dr. Sameer Joshi", "18 amps"],
      ],
    },
    {
      name: "Accounts Receivable (AR) Aging Ledger",
      code: "AR-AGING",
      description: "Outstanding dues bucketed into 0-30, 31-60, 61-90, and >90 days by TPA and Self-Pay.",
      endpoint: "/api/registers/ar-aging?format=csv",
      format: "RFC 4180 CSV (BOM)",
      previewHeaders: ["Patient / Payer", "Total Dues", "Current (0-30d)", "31-60d", "61-90d", "> 90d"],
      previewRows: [
        ["Star Health Insurance (TPA)", "₹1,42,000.00", "₹98,000.00", "₹44,000.00", "₹0.00", "₹0.00"],
        ["HDFC ERGO General Ins", "₹86,500.00", "₹86,500.00", "₹0.00", "₹0.00", "₹0.00"],
        ["Self-Pay Inpatient Balance", "₹34,200.00", "₹22,000.00", "₹12,200.00", "₹0.00", "₹0.00"],
      ],
    },
    {
      name: "Bio-Medical Waste (BMW) Management Statutory Register",
      code: "BMW-REGISTER",
      description: "CPCB/SPCB daily color-coded manifests (Yellow, Red, White, Blue) in kg.",
      endpoint: "/api/registers/biomedical-waste?format=csv",
      format: "RFC 4180 CSV (BOM)",
      previewHeaders: ["Date", "Yellow (Anatomical)", "Red (Contaminated)", "White (Sharps)", "Blue (Glass)", "Transporter"],
      previewRows: [
        ["2026-10-31", "14.2 kg", "22.8 kg", "4.1 kg", "6.5 kg", "CleanEnv Solutions (#BMW-TR-81)"],
        ["2026-10-30", "16.8 kg", "20.1 kg", "3.9 kg", "5.8 kg", "CleanEnv Solutions (#BMW-TR-81)"],
      ],
    },
  ];

  const dpdpConsents = [
    {
      id: "DPDP-9921",
      patient: "Siddharth Verma (MRN-2026-0001)",
      purpose: "Clinical Care & Treatment",
      status: "ACTIVE",
      timestamp: "2026-10-31 10:14 UTC",
      hash: "8f4a...e12b",
    },
    {
      id: "DPDP-9922",
      patient: "Ananya Deshmukh (ER-0914)",
      purpose: "Telemedicine & Messaging",
      status: "ACTIVE",
      timestamp: "2026-10-31 11:22 UTC",
      hash: "3b2c...fa79",
    },
    {
      id: "DPDP-9923",
      patient: "Harish Rao (ER-0915)",
      purpose: "Third-Party TPA Insurance Sharing",
      status: "WITHDRAWN",
      timestamp: "2026-10-31 15:02 UTC",
      hash: "90da...8831",
    },
  ];

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <ShieldCheck className="text-sky-400" />
            Executive Command Center & Statutory Registers HUD
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            Tenant ID: #{inventory?.tenant_id || 1} • Live Database Footprint &amp; Statutory Regulatory Exports
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={loadDataInventory}
            disabled={isLoading}
            className="flex items-center gap-2"
          >
            <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} /> Refresh Data Footprint
          </Button>
        </div>
      </div>

      {/* Workspace Sub-Tabs */}
      <div className="flex items-center gap-2 mt-4 pb-2 border-b border-slate-800">
        <button
          type="button"
          onClick={() => setActiveTab("overview")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "overview"
              ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
          }`}
        >
          <Activity size={14} /> Executive Cockpit &amp; Launchpad
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("metrics")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "metrics"
              ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
          }`}
        >
          <BarChart3 size={14} /> Enterprise 700+ Metrics &amp; Cube Explorer
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("registers")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "registers"
              ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
          }`}
        >
          <FileText size={14} /> Statutory Registers &amp; DPDP Ledger
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("customization")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "customization"
              ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
          }`}
        >
          <Settings size={14} /> Hospital Master &amp; Facility Builder
        </button>
      </div>

      {/* TAB 1: EXECUTIVE COCKPIT & LAUNCHPAD */}
      {activeTab === "overview" && (
        <div className="space-y-6">
          {/* Operational Continuity & Emergency Readiness HUD */}
          <Card className={`p-4 border transition-all mt-4 ${
            downtimeModeActive
              ? "bg-rose-950/40 border-rose-500/70 shadow-lg shadow-rose-950/50"
              : "bg-slate-900 border-slate-800"
          }`}>
            <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <ShieldAlert size={15} className={downtimeModeActive ? "text-rose-400 animate-pulse" : "text-sky-400"} />
                    Hospital Continuity &amp; Statutory Emergency Readiness Hub
                  </span>
                  <Badge variant={downtimeModeActive ? "danger" : "neutral"} size="sm" className="font-mono">
                    {downtimeModeActive ? "⚠️ DOWNTIME BCP PROTOCOL ACTIVE" : "NORMAL HIS OPERATION"}
                  </Badge>
                </div>
                <p className="text-xs text-slate-400">
                  Instant offline emergency documentation packs, NABH statutory facility compliance dossier, and emergency code protocol alerts routed dynamically to configured A4 laser printers.
                </p>
                {bcpPrintSuccess && (
                  <div className="text-xs text-emerald-400 font-mono flex items-center gap-1 mt-1">
                    <CheckCircle2 size={13} /> {bcpPrintSuccess}
                  </div>
                )}
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant={downtimeModeActive ? "danger" : "outline"}
                  onClick={() => setDowntimeModeActive(!downtimeModeActive)}
                  className="flex items-center gap-1.5 text-xs"
                >
                  <AlertOctagon size={13} /> {downtimeModeActive ? "Deactivate Downtime" : "Simulate Downtime Mode"}
                </Button>

                <Button
                  size="sm"
                  variant="primary"
                  onClick={handlePrintDowntimeBcpPack}
                  className="flex items-center gap-1.5 text-xs bg-rose-600 hover:bg-rose-500 text-white"
                >
                  <Printer size={13} /> Print Offline BCP Pack (Form ADM-BCP-01)
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={handlePrintEmergencyPlacard}
                  className="flex items-center gap-1.5 text-xs text-amber-400 border-amber-500/40 hover:bg-amber-500/10"
                >
                  <Flame size={13} /> Emergency Code Placard
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={handlePrintFacilityComplianceDossier}
                  className="flex items-center gap-1.5 text-xs text-emerald-400 border-emerald-500/40 hover:bg-emerald-500/10"
                >
                  <FileText size={13} /> Statutory Facility Dossier
                </Button>

                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setDrillModalOpen(true)}
                  className="flex items-center gap-1.5 text-xs text-sky-400 border-sky-500/40 hover:bg-sky-500/10"
                >
                  <BellRing size={13} /> Log Code Drill
                </Button>
              </div>
            </div>
          </Card>

          {/* 1. Real-Time Hospital Operational KPIs */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mt-6">
            <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Users size={14} className="text-sky-400" /> Today&apos;s OPD Consults
                </span>
                <Badge variant="info" size="sm">Live</Badge>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono text-slate-100">
                  {liveMetrics ? liveMetrics.opd_funnel.total_appointments : 142}
                </span>
                <span className="text-xs text-emerald-400 font-mono flex items-center">
                  <TrendingUp size={12} className="mr-0.5" /> +12% vs avg
                </span>
              </div>
              <div className="text-[11px] text-slate-500 font-mono">
                {liveMetrics
                  ? `Completed: ${liveMetrics.opd_funnel.status_breakdown["COMPLETED"] || 0} • Sched: ${liveMetrics.opd_funnel.status_breakdown["SCHEDULED"] || 0}`
                  : "General Med: 54 • Cardio: 38 • Ortho: 50"}
              </div>
            </Card>

            <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <BedDouble size={14} className="text-emerald-400" /> Bed Occupancy (BOR)
                </span>
                <Badge variant="success" size="sm">
                  {liveMetrics
                    ? `${liveMetrics.bed_census.overall_occupancy_rate_pct.toFixed(1)}%`
                    : "87.5%"}
                </Badge>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono text-slate-100">
                  {liveMetrics
                    ? `${liveMetrics.bed_census.status_breakdown["OCCUPIED"] || 0} / ${liveMetrics.bed_census.total_beds}`
                    : "105 / 120"}
                </span>
                <span className="text-xs text-slate-400 font-mono">
                  {liveMetrics
                    ? `${liveMetrics.bed_census.status_breakdown["AVAILABLE"] || 0} Available`
                    : "15 Available"}
                </span>
              </div>
              <div className="text-[11px] text-slate-500 font-mono">
                Turnovers: {liveMetrics?.bed_census.bed_turnover_events_count ?? 6} • Ward: 88%
              </div>
            </Card>

            <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <Siren size={14} className="text-rose-400" /> Emergency Trauma (ESI-1/2)
                </span>
                <Badge variant="danger" size="sm">Priority</Badge>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono text-rose-400">
                  {liveMetrics
                    ? `${liveMetrics.encounters_and_ipd_alos.active_encounters_by_type["ER"] || 3} Cases`
                    : "3 Cases"}
                </span>
                <span className="text-xs text-rose-400 font-mono">Avg Triage: 4m</span>
              </div>
              <div className="text-[11px] text-slate-500 font-mono">RTA Poly-Trauma • Acute STEMI • Stroke</div>
            </Card>

            <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
                  <CreditCard size={14} className="text-amber-400" /> Today&apos;s Gross Collections
                </span>
                <Badge variant="warning" size="sm">Audited</Badge>
              </div>
              <div className="flex items-baseline justify-between">
                <span className="text-2xl font-bold font-mono text-emerald-400">
                  ₹
                  {liveMetrics
                    ? (liveMetrics.unit_economics.total_net_billed_paise / 100).toLocaleString("en-IN")
                    : "3,48,650"}
                </span>
                <span className="text-xs text-slate-400 font-mono">94 Receipts</span>
              </div>
              <div className="text-[11px] text-slate-500 font-mono">UPI: 48% • Card: 32% • Cash: 20%</div>
            </Card>
          </div>

          {/* 2. Departmental Quick Intake Launchpad */}
          <div className="mt-6">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2 mb-3">
              <Activity size={16} className="text-sky-400" />
              Clinical &amp; Operational Intake Launchpad
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                {
                  id: "registration" as WorkspaceId,
                  title: "Patient Registration",
                  desc: "New UHID, PIN lookup, DPDP consent",
                  icon: UserPlus,
                  color: "text-sky-400",
                },
                {
                  id: "adt" as WorkspaceId,
                  title: "Inpatient Bed ADT",
                  desc: "Admit, transfer bed, discharge summary",
                  icon: DoorOpen,
                  color: "text-emerald-400",
                },
                {
                  id: "doctor" as WorkspaceId,
                  title: "Doctor Cockpit",
                  desc: "SOAP consult, CPOE e-Rx, lab orders",
                  icon: Stethoscope,
                  color: "text-purple-400",
                },
                {
                  id: "nursing" as WorkspaceId,
                  title: "Ward Nursing Station",
                  desc: "NEWS2 early warning, vitals, MAR",
                  icon: BedDouble,
                  color: "text-teal-400",
                },
                {
                  id: "triage" as WorkspaceId,
                  title: "Emergency Triage",
                  desc: "ESI 1-5 triage, GCS score, trauma MLC",
                  icon: Siren,
                  color: "text-rose-400",
                },
                {
                  id: "pharmacy" as WorkspaceId,
                  title: "Pharmacy & NDPS",
                  desc: "Barcode dispensing, Schedule H1 ledger",
                  icon: Pill,
                  color: "text-emerald-400",
                },
                {
                  id: "diagnostics" as WorkspaceId,
                  title: "Diagnostics & LIS",
                  desc: "Accessioning, panic callouts, reports",
                  icon: Microscope,
                  color: "text-indigo-400",
                },
                {
                  id: "billing" as WorkspaceId,
                  title: "Cashier Billing Counter",
                  desc: "Shift reconciliations, split tender, tax invoice",
                  icon: CreditCard,
                  color: "text-amber-400",
                },
              ].map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => onSelectWorkspace && onSelectWorkspace(item.id)}
                    className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 hover:border-sky-500/50 hover:bg-slate-800/80 transition-all text-left group flex flex-col justify-between"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className={`p-2 rounded-lg bg-slate-950 border border-slate-800 ${item.color}`}>
                        <Icon size={18} />
                      </div>
                      <ArrowUpRight
                        size={14}
                        className="text-slate-600 group-hover:text-sky-400 transition-colors"
                      />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-200 group-hover:text-white transition-colors">
                        {item.title}
                      </div>
                      <div className="text-[11px] text-slate-500 mt-0.5 leading-snug">
                        {item.desc}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Operational Velocity & Visual Trend Analytics */}
          <div className="mt-8 pt-6 border-t border-slate-800/80">
            <OperationalTrendsDashboard
              totalBeds={liveMetrics?.bed_census.total_beds || 120}
              occupiedBeds={liveMetrics?.bed_census.status_breakdown["OCCUPIED"] || 105}
              totalCollectionsPaise={liveMetrics?.unit_economics.total_net_billed_paise || 34865000}
            />
          </div>

          {/* Database Footprint Live Overview */}
          <div className="mt-6">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2 mb-3">
              <Database size={16} className="text-emerald-400" />
              Live Table Record Inventory (Total Records: {inventory?.total_hospital_records.toLocaleString() || "0"})
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3">
              {inventory?.tables ? (
                Object.entries(inventory.tables).map(([table, count]) => (
                  <Card key={table} className="p-3 bg-slate-900 border-slate-800 text-center">
                    <div className="text-[11px] text-slate-400 font-mono truncate" title={table}>
                      {table}
                    </div>
                    <div className="text-lg font-bold font-mono text-slate-100 mt-1">
                      {count.toLocaleString()}
                    </div>
                  </Card>
                ))
              ) : (
                <div className="col-span-full py-8 text-center text-slate-500 text-xs">
                  Loading table record footprint...
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* TAB 2: ENTERPRISE 700+ METRICS & OLAP CUBE EXPLORER */}
      {activeTab === "metrics" && (
        <div className="space-y-6 mt-6">
          {/* OLAP Cube Coordinates Banner */}
          <Card className="p-4 bg-slate-900 border-sky-500/40 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-sky-400 uppercase tracking-wider flex items-center gap-1.5">
                <BarChart3 size={15} /> 11-Dimensional OLAP Cube Coordinates
              </span>
              <Badge variant="info" size="sm">700+ Metrics Baseline</Badge>
            </div>
            <p className="text-xs text-slate-300 font-mono">
              Time × Branch × Department × Specialty × Doctor × Ward × Service × Payer × Patient Type × Encounter Type × Shift
            </p>
            <div className="text-[11px] text-slate-500">
              Query any clinical, operational, financial, or quality metric across all institutional dimensions with zero-waterfall aggregation.
            </div>
          </Card>

          {/* Search & Domain Filter Toolbar */}
          <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-3 text-slate-500" />
              <input
                type="text"
                value={metricSearch}
                onChange={(e) => setMetricSearch(e.target.value)}
                placeholder="Search by metric name, formula, code, or description (e.g. BOR, AR Days, ALOS)..."
                className="w-full bg-slate-900 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div className="flex items-center gap-2">
              <select
                value={selectedDomainId}
                onChange={(e) => setSelectedDomainId(e.target.value === "ALL" ? "ALL" : parseInt(e.target.value, 10))}
                className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
              >
                <option value="ALL">All 32 Hospital Domains ({METRIC_DOMAINS.reduce((acc, d) => acc + d.count, 0)} KPIs)</option>
                {METRIC_DOMAINS.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.id}. {d.name} ({d.count} metrics)
                  </option>
                ))}
              </select>

              <select
                value={selectedCategory}
                onChange={(e) => setSelectedCategory(e.target.value)}
                className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200"
              >
                <option value="ALL">All Categories</option>
                <option value="Clinical">Clinical</option>
                <option value="Financial">Financial</option>
                <option value="Operational">Operational</option>
                <option value="Quality">Quality</option>
                <option value="Governance">Governance</option>
                <option value="Infrastructure">Infrastructure</option>
              </select>
            </div>
          </div>

          {/* Metric Explorer Table */}
          <Card className="p-4 bg-slate-900 border-slate-800">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                    <th className="pb-2.5">ID &amp; Name</th>
                    <th className="pb-2.5">Domain</th>
                    <th className="pb-2.5">Category</th>
                    <th className="pb-2.5">Definition &amp; Formula</th>
                    <th className="pb-2.5 text-right">Target Benchmark</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/50">
                  {filteredMetrics.map((m) => (
                    <tr key={m.id} className="text-slate-300 hover:bg-slate-800/40">
                      <td className="py-3">
                        <span className="font-bold text-sky-400 block">{m.name}</span>
                        <span className="text-[10px] text-slate-500 font-mono">{m.id}</span>
                      </td>
                      <td className="py-3">
                        <span className="text-slate-200">{m.domainName}</span>
                      </td>
                      <td className="py-3">
                        <Badge
                          variant={
                            m.category === "Financial"
                              ? "warning"
                              : m.category === "Clinical"
                              ? "info"
                              : m.category === "Quality"
                              ? "danger"
                              : "neutral"
                          }
                          size="sm"
                        >
                          {m.category}
                        </Badge>
                      </td>
                      <td className="py-3 max-w-md">
                        <div className="text-slate-300 font-sans text-xs mb-1">{m.description}</div>
                        <code className="text-[10px] text-emerald-400 bg-slate-950 px-2 py-0.5 rounded border border-slate-800 block truncate" title={m.formula}>
                          {m.formula}
                        </code>
                      </td>
                      <td className="py-3 text-right">
                        <span className="text-emerald-400 font-bold block">{m.targetBenchmark || "--"}</span>
                        <span className="text-[10px] text-slate-500">Unit: {m.unit}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}

      {/* TAB 3: STATUTORY REGISTERS & DPDP AUDIT LEDGER */}
      {activeTab === "registers" && (
        <div className="space-y-6 mt-6">
          {/* Statutory Facility Safety & Environmental Compliance Dossier */}
          <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-3 pb-3 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-emerald-950/60 border border-emerald-800/60 text-emerald-400">
                  <ShieldCheck size={20} />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-slate-100 text-sm">
                      NABH 5th Edition / CPCB / AERB Statutory Facility Safety &amp; Environmental Audit Dossier
                    </span>
                    <Badge variant="success" size="sm" className="font-mono">
                      FORM NABH-FMS-01
                    </Badge>
                  </div>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Consolidated regulatory inspection report: CPCB Form IV Bio-Medical Waste return, Fire Service NOC &amp; hydrant tests, AERB radiation compliance, Cryogenic Liquid Oxygen (LMO) tank purity, and 15s DG ATS cutover.
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="primary"
                  onClick={handlePrintFacilityComplianceDossier}
                  className="flex items-center gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-bold"
                >
                  <Printer size={13} /> Print Statutory Dossier (CLINICAL_A4)
                </Button>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-1 text-xs">
              <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                <div className="text-[11px] text-slate-400 uppercase font-mono">CPCB Form IV Waste</div>
                <div className="text-emerald-400 font-bold font-mono text-sm mt-0.5">14,280 kg / yr</div>
                <div className="text-[10px] text-slate-500">100% Barcoded Bag Manifest</div>
              </div>

              <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                <div className="text-[11px] text-slate-400 uppercase font-mono">Fire Service NOC</div>
                <div className="text-sky-400 font-bold font-mono text-sm mt-0.5">Valid to Nov 2027</div>
                <div className="text-[10px] text-slate-500">Pressure: 7.2 kg/cm² • Mock: Pass</div>
              </div>

              <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                <div className="text-[11px] text-slate-400 uppercase font-mono">AERB Radiation QA</div>
                <div className="text-purple-400 font-bold font-mono text-sm mt-0.5">24/24 Aprons Intact</div>
                <div className="text-[10px] text-slate-500">RSO-III Reg #AERB-8821</div>
              </div>

              <div className="p-2.5 rounded bg-slate-950 border border-slate-800">
                <div className="text-[11px] text-slate-400 uppercase font-mono">LMO Cryogenic Vessel</div>
                <div className="text-amber-400 font-bold font-mono text-sm mt-0.5">10,000 L (99.4%)</div>
                <div className="text-[10px] text-slate-500">Line: 4.2 Bar • 60 Cyl Backup</div>
              </div>
            </div>
          </Card>

          {/* Statutory Hospital Operational Registers */}
          <div>
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2 mb-4">
              <Layers size={16} className="text-sky-400" />
              Statutory Hospital Operational Registers (1-Click CSV Stream)
            </h2>

            <div className="space-y-3">
              {registers.map((reg) => (
                <Card
                  key={reg.code}
                  className="p-4 bg-slate-900 border-slate-800 flex items-center justify-between hover:border-slate-700 transition-colors"
                >
                  <div className="flex items-start gap-4">
                    <div className="p-2 rounded-lg bg-sky-950/60 border border-sky-800/60 text-sky-400 mt-0.5">
                      <FileText size={18} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-slate-200 text-sm">{reg.name}</span>
                        <span className="font-mono text-xs text-sky-400 bg-sky-950 px-1.5 py-0.2 rounded border border-sky-900/60">
                          {reg.code}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400 mt-1 max-w-2xl">{reg.description}</p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[11px] font-mono text-slate-500 mr-2">{reg.format}</span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={isPreviewLoading}
                      onClick={() => handlePreviewRegister(reg)}
                      className="flex items-center gap-1.5 text-xs"
                    >
                      <Eye size={13} className={isPreviewLoading ? "animate-spin" : ""} /> Preview
                    </Button>

                    <a
                      href={reg.endpoint}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md bg-sky-500 hover:bg-sky-400 text-slate-950 transition-colors"
                    >
                      <Download size={13} /> Download CSV
                    </a>
                  </div>
                </Card>
              ))}
            </div>
          </div>

          {/* DPDP Digital Personal Data Protection Act Compliance Ledger */}
          <div className="mt-8 pb-8">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Lock size={16} className="text-amber-400" />
                DPDP Digital Personal Data Protection Act — Consent Audit Ledger
              </h2>
              <Badge variant="neutral" size="sm" className="font-mono">
                SHA-256 Tamper Evident
              </Badge>
            </div>

            <Card className="p-4 bg-slate-900 border-slate-800">
              <div className="text-xs text-slate-400 mb-3">
                Real-time immutable audit trace of data fiduciary consent grants, purposes, and patient withdrawal requests under Section 6 of DPDP Act 2023.
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase">
                      <th className="pb-2">Consent ID</th>
                      <th className="pb-2">Data Principal (Patient)</th>
                      <th className="pb-2">Specified Purpose</th>
                      <th className="pb-2">Status</th>
                      <th className="pb-2">Timestamp (UTC)</th>
                      <th className="pb-2">Integrity Proof</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {dpdpConsents.map((c) => (
                      <tr key={c.id} className="text-slate-300">
                        <td className="py-2.5 text-sky-400 font-bold">{c.id}</td>
                        <td className="py-2.5">{c.patient}</td>
                        <td className="py-2.5">{c.purpose}</td>
                        <td className="py-2.5">
                          <Badge variant={c.status === "ACTIVE" ? "success" : "danger"} size="sm">
                            {c.status}
                          </Badge>
                        </td>
                        <td className="py-2.5 text-slate-400">{c.timestamp}</td>
                        <td className="py-2.5 text-slate-500">{c.hash}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          </div>
        </div>
      )}

      {/* TAB 4: HOSPITAL MASTER & FACILITY BUILDER */}
      {activeTab === "customization" && (
        <div className="space-y-6 mt-6">
          {/* Sub-tab navigation */}
          <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
            <button
              type="button"
              onClick={() => setCustomSubTab("facility")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                customSubTab === "facility"
                  ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Building size={14} /> Campus Facility &amp; Bed Builder ({beds.length} Beds)
            </button>

            <button
              type="button"
              onClick={() => setCustomSubTab("doctors")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                customSubTab === "doctors"
                  ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Stethoscope size={14} /> Doctor Roster &amp; OPD Pricing ({doctors.length} Doctors)
            </button>

            <button
              type="button"
              onClick={() => setCustomSubTab("branding")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                customSubTab === "branding"
                  ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <ShieldCheck size={14} /> Hospital Identity &amp; Print Letterhead
            </button>

            <button
              type="button"
              onClick={() => setCustomSubTab("policies")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                customSubTab === "policies"
                  ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Settings size={14} /> Workflow &amp; Policy Rules
            </button>

            <button
              type="button"
              onClick={() => setCustomSubTab("printTemplates")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                customSubTab === "printTemplates"
                  ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Printer size={14} /> Statutory Print Layouts &amp; Templates
            </button>

            <button
              type="button"
              onClick={() => setCustomSubTab("printers")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                customSubTab === "printers"
                  ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Cpu size={14} /> Hardware Printers &amp; Network Devices ({printers.length} Devices)
            </button>

            <div className="flex-1 text-right">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  if (confirm("Reset hospital facility configuration to factory defaults?")) {
                    resetToDefaultCatalog();
                  }
                }}
                className="text-xs text-rose-400 hover:bg-rose-950 flex items-center gap-1 ml-auto"
              >
                <RotateCcw size={12} /> Reset to Defaults
              </Button>
            </div>
          </div>

          {/* Sub-tab 1: Facility & Bed Inventory Builder */}
          {customSubTab === "facility" && (
            <div className="space-y-6">
              {/* Form: Add Operational Bed */}
              <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <Plus size={14} className="text-emerald-400" /> Add New Operational Bed to Campus Matrix
                  </h3>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setBatchModalOpen(true)}
                      className="flex items-center gap-1.5 text-xs text-sky-400 border-sky-500/40 hover:bg-sky-500/10"
                    >
                      <Zap size={13} className="text-amber-400" /> Batch Provision Beds (Commission Wing)
                    </Button>
                    {bedSuccessMsg && (
                      <span className="text-xs text-emerald-400 font-mono flex items-center gap-1">
                        <CheckCircle2 size={12} /> {bedSuccessMsg}
                      </span>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-3">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Bed Number *</label>
                    <input
                      type="text"
                      placeholder="e.g. B-305, ICU-12"
                      value={newBedNumber}
                      onChange={(e) => setNewBedNumber(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Room Number *</label>
                    <input
                      type="text"
                      placeholder="e.g. R-305, BAY-A"
                      value={newRoomNumber}
                      onChange={(e) => setNewRoomNumber(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Building / Tower *</label>
                    <select
                      value={newTower}
                      onChange={(e) => setNewTower(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    >
                      <option value="Main Tower">Main Tower</option>
                      <option value="Surgical Wing">Surgical Wing</option>
                      <option value="Trauma Center">Trauma Center</option>
                      <option value="Women & Child">Women &amp; Child Pavilion</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Floor *</label>
                    <select
                      value={newFloor}
                      onChange={(e) => setNewFloor(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    >
                      <option value="Ground Floor">Ground Floor</option>
                      <option value="Floor 2">Floor 2</option>
                      <option value="Floor 3">Floor 3</option>
                      <option value="Floor 4">Floor 4</option>
                      <option value="Floor 5">Floor 5</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Ward Name *</label>
                    <input
                      type="text"
                      placeholder="e.g. Cardiology HDU, Surgical Step-Down"
                      value={newWardName}
                      onChange={(e) => setNewWardName(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Category *</label>
                    <select
                      value={newCategory}
                      onChange={(e) => setNewCategory(e.target.value as any)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    >
                      <option value="General">General</option>
                      <option value="Semi-Private">Semi-Private</option>
                      <option value="Private">Private</option>
                      <option value="ICU">ICU</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Daily Tariff (₹) *</label>
                    <input
                      type="number"
                      placeholder="e.g. 3500"
                      value={newTariff}
                      onChange={(e) => setNewTariff(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-[11px] text-slate-400 mb-1">Features / Equipment Tags (comma separated)</label>
                  <input
                    type="text"
                    placeholder="e.g. Ventilator Ready, Cardiac Telemetry, O2 Wall Outlet"
                    value={newFeatures}
                    onChange={(e) => setNewFeatures(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                  />
                </div>

                <div className="flex justify-end pt-2">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => {
                      if (!newBedNumber.trim() || !newRoomNumber.trim()) {
                        alert("Bed Number and Room Number are required.");
                        return;
                      }
                      const feats = newFeatures.split(",").map((s) => s.trim()).filter(Boolean);
                      addBed({
                        bedNumber: newBedNumber.trim(),
                        roomNumber: newRoomNumber.trim(),
                        tower: newTower,
                        floor: newFloor,
                        wardName: newWardName.trim() || "General Ward",
                        category: newCategory,
                        status: "VACANT_CLEAN",
                        dailyTariffRupees: parseInt(newTariff || "2500", 10),
                        features: feats,
                      });
                      setNewBedNumber("");
                      setNewRoomNumber("");
                      setBedSuccessMsg("Bed successfully added to campus inventory!");
                      setTimeout(() => setBedSuccessMsg(""), 3000);
                    }}
                    className="flex items-center gap-1.5"
                  >
                    <Plus size={13} /> Add Bed to Campus Matrix
                  </Button>
                </div>
              </Card>

              {/* Table: Configured Beds Inventory */}
              <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                    Configured Campus Beds ({beds.length} Total Registered)
                  </h3>
                  <span className="text-[11px] font-mono text-slate-400">
                    Live Beds dynamically ingested by Inpatient Admission ADT
                  </span>
                </div>

                <div className="max-h-96 overflow-y-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-950 text-slate-400 text-[10px] uppercase sticky top-0">
                      <tr>
                        <th className="p-2">Bed / Room</th>
                        <th className="p-2">Tower &amp; Floor</th>
                        <th className="p-2">Ward Name</th>
                        <th className="p-2">Category</th>
                        <th className="p-2">Daily Tariff</th>
                        <th className="p-2">Features</th>
                        <th className="p-2">Status</th>
                        <th className="p-2 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/80 text-slate-300">
                      {beds.map((b) => (
                        <tr key={b.bedId} className="hover:bg-slate-950/60">
                          <td className="p-2 font-bold text-slate-100">
                            {b.bedNumber} ({b.roomNumber})
                          </td>
                          <td className="p-2 text-[11px] text-slate-400">
                            {b.tower} • {b.floor}
                          </td>
                          <td className="p-2 text-slate-200">{b.wardName}</td>
                          <td className="p-2">
                            <span className="px-1.5 py-0.5 rounded text-[10px] bg-slate-950 border border-slate-800 text-sky-400">
                              {b.category}
                            </span>
                          </td>
                          <td className="p-2 font-bold text-emerald-400">₹{b.dailyTariffRupees.toLocaleString()}</td>
                          <td className="p-2 text-[10px] text-slate-400 max-w-xs truncate">
                            {b.features.join(", ")}
                          </td>
                          <td className="p-2">
                            <span
                              className={`px-1.5 py-0.5 rounded text-[10px] ${
                                b.status === "VACANT_CLEAN"
                                  ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                                  : "bg-rose-950 text-rose-300 border border-rose-900"
                              }`}
                            >
                              {b.status}
                            </span>
                          </td>
                          <td className="p-2 text-right">
                            <button
                              type="button"
                              onClick={() => deleteBed(b.bedId)}
                              title="Delete Bed from Facility"
                              className="text-rose-400 hover:text-rose-300 p-1 hover:bg-slate-800 rounded transition-colors"
                            >
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {/* Sub-tab 2: Doctor Roster & OPD Clinic Pricing */}
          {customSubTab === "doctors" && (
            <div className="space-y-6">
              {/* Form: Add Consultant */}
              <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                    <Plus size={14} className="text-emerald-400" /> Add Doctor to Clinic Roster
                  </h3>
                  {docSuccessMsg && (
                    <span className="text-xs text-emerald-400 font-mono flex items-center gap-1">
                      <CheckCircle2 size={12} /> {docSuccessMsg}
                    </span>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Doctor Legal Name *</label>
                    <input
                      type="text"
                      placeholder="e.g. Dr. Priya Nair, MD"
                      value={newDocName}
                      onChange={(e) => setNewDocName(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Clinical Specialty *</label>
                    <input
                      type="text"
                      placeholder="e.g. Endocrinology & Diabetology"
                      value={newDocSpecialty}
                      onChange={(e) => setNewDocSpecialty(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Department *</label>
                    <select
                      value={newDocDept}
                      onChange={(e) => setNewDocDept(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    >
                      <option value="General Medicine">General Medicine</option>
                      <option value="Cardiology">Cardiology</option>
                      <option value="General Surgery">General Surgery</option>
                      <option value="Pediatrics">Pediatrics</option>
                      <option value="Orthopedics">Orthopedics</option>
                      <option value="Obstetrics & Gynecology">Obstetrics &amp; Gynecology</option>
                      <option value="Pulmonology">Pulmonology</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-4 gap-3">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Cabin Room *</label>
                    <input
                      type="text"
                      placeholder="e.g. OPD Cabin 205"
                      value={newDocRoom}
                      onChange={(e) => setNewDocRoom(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Consultation Fee (₹) *</label>
                    <input
                      type="number"
                      placeholder="e.g. 700"
                      value={newDocFee}
                      onChange={(e) => setNewDocFee(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Free Revisit Window (Days)</label>
                    <input
                      type="number"
                      placeholder="7"
                      value={newDocRevisitDays}
                      onChange={(e) => setNewDocRevisitDays(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Max Free Follow-ups</label>
                    <input
                      type="number"
                      placeholder="1"
                      value={newDocMaxFreeVisits}
                      onChange={(e) => setNewDocMaxFreeVisits(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Fee Waived (%)</label>
                    <input
                      type="number"
                      placeholder="100"
                      value={newDocDiscountPct}
                      onChange={(e) => setNewDocDiscountPct(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-2">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => {
                      if (!newDocName.trim() || !newDocSpecialty.trim()) {
                        alert("Doctor Name and Specialty are required.");
                        return;
                      }
                      addDoctor({
                        name: newDocName.trim(),
                        specialty: newDocSpecialty.trim(),
                        department: newDocDept,
                        roomNumber: newDocRoom.trim() || "OPD Cabin 101",
                        consultationFee: parseInt(newDocFee || "500", 10),
                        currentWaitMins: 10,
                        patientsWaiting: 0,
                        isActive: true,
                        revisitFreeWindowDays: parseInt(newDocRevisitDays || "7", 10),
                        revisitMaxFreeVisits: parseInt(newDocMaxFreeVisits || "1", 10),
                        revisitDiscountPercent: parseInt(newDocDiscountPct || "100", 10),
                      });
                      setNewDocName("");
                      setNewDocSpecialty("");
                      setDocSuccessMsg("Doctor successfully added to live roster!");
                      setTimeout(() => setDocSuccessMsg(""), 3000);
                    }}
                    className="flex items-center gap-1.5"
                  >
                    <Plus size={13} /> Add Doctor to Live Clinic Roster
                  </Button>
                </div>
              </Card>

              {/* Table: Configured Doctors */}
              <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                  <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                    Active Doctor Roster ({doctors.length} Consultants Configured)
                  </h3>
                  <span className="text-[11px] font-mono text-slate-400">
                    Live consultants auto-populated during Front Desk Patient Registration
                  </span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-950 text-slate-400 text-[10px] uppercase">
                      <tr>
                        <th className="p-2">Doctor Name</th>
                        <th className="p-2">Specialty</th>
                        <th className="p-2">Department</th>
                        <th className="p-2">Cabin Room</th>
                        <th className="p-2">Consultation Fee</th>
                        <th className="p-2">Revisit / Follow-up Policy</th>
                        <th className="p-2 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/80 text-slate-300">
                      {doctors.map((d) => (
                        <tr key={d.id} className="hover:bg-slate-950/60">
                          <td className="p-2 font-bold text-slate-100">{d.name}</td>
                          <td className="p-2 text-slate-300">{d.specialty}</td>
                          <td className="p-2 text-sky-400">{d.department}</td>
                          <td className="p-2 text-amber-300">{d.roomNumber}</td>
                          <td className="p-2 font-bold text-emerald-400">₹{d.consultationFee}.00</td>
                          <td className="p-2">
                            <span className="px-2 py-0.5 rounded text-[10px] bg-purple-950 text-purple-300 border border-purple-800 font-semibold">
                              {d.revisitFreeWindowDays || 7} Days Free ({d.revisitMaxFreeVisits || 1} Revisit)
                            </span>
                          </td>
                          <td className="p-2 text-right">
                            <button
                              type="button"
                              onClick={() => deleteDoctor(d.id)}
                              title="Remove Doctor from Roster"
                              className="text-rose-400 hover:text-rose-300 p-1 hover:bg-slate-800 rounded transition-colors"
                            >
                              <Trash2 size={13} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </div>
          )}

          {/* Sub-tab 3: Hospital Identity & Branding */}
          {customSubTab === "branding" && (
            <Card className="p-5 bg-slate-900 border-slate-800 space-y-4 max-w-3xl">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                  <ShieldCheck size={14} className="text-sky-400" /> Hospital Identity &amp; Letterhead Metadata
                </h3>
                {profileSavedMsg && (
                  <span className="text-xs text-emerald-400 font-mono flex items-center gap-1">
                    <CheckCircle2 size={12} /> {profileSavedMsg}
                  </span>
                )}
              </div>

              <div className="rounded-xl border border-slate-700 bg-slate-950/70 p-4 space-y-4">
                <div>
                  <h4 className="text-sm font-semibold text-slate-100">Application branding</h4>
                  <p className="mt-1 text-xs text-slate-400">These settings are stored centrally for this tenant and shared with its authorized users.</p>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Application display name</label>
                    <input value={brandDisplayName} onChange={(e) => setBrandDisplayName(e.target.value)} maxLength={150} className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Tagline (optional)</label>
                    <input value={brandTagline} onChange={(e) => setBrandTagline(e.target.value)} maxLength={160} className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Logo URL (HTTPS or same-origin path)</label>
                    <input value={brandLogoUrl} onChange={(e) => setBrandLogoUrl(e.target.value)} placeholder="/assets/tenant-logo.svg" className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Upload logo (PNG, JPEG, WebP)</label>
                    <input type="file" accept="image/png,image/jpeg,image/webp" disabled={brandAssetUploading !== null} onChange={(e) => { const file = e.currentTarget.files?.[0]; e.currentTarget.value = ""; void handleBrandAssetUpload("logo", file); }} className="w-full text-xs text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-slate-700 file:px-3 file:py-2 file:text-xs file:text-slate-100" />
                    {brandAssetUploading === "logo" && <p className="mt-1 text-[10px] text-sky-400">Uploading and scanning logo…</p>}
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Favicon URL (optional)</label>
                    <input value={brandFaviconUrl} onChange={(e) => setBrandFaviconUrl(e.target.value)} placeholder="/assets/favicon.ico" className="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-100" />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Upload favicon (PNG, JPEG, WebP)</label>
                    <input type="file" accept="image/png,image/jpeg,image/webp" disabled={brandAssetUploading !== null} onChange={(e) => { const file = e.currentTarget.files?.[0]; e.currentTarget.value = ""; void handleBrandAssetUpload("favicon", file); }} className="w-full text-xs text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-slate-700 file:px-3 file:py-2 file:text-xs file:text-slate-100" />
                    {brandAssetUploading === "favicon" && <p className="mt-1 text-[10px] text-sky-400">Uploading and scanning favicon…</p>}
                  </div>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {[
                    { label: "Primary", value: brandPrimaryColor, setter: setBrandPrimaryColor },
                    { label: "Secondary", value: brandSecondaryColor, setter: setBrandSecondaryColor },
                    { label: "Accent", value: brandAccentColor, setter: setBrandAccentColor },
                  ].map((color) => (
                    <label key={color.label} className="flex items-center gap-3 rounded-lg border border-slate-700 p-3 text-xs text-slate-300">
                      <input type="color" value={color.value} onChange={(e) => color.setter(e.target.value)} className="h-8 w-10 cursor-pointer bg-transparent" />
                      <span>{color.label}<span className="block text-[10px] text-slate-500 font-mono">{color.value}</span></span>
                    </label>
                  ))}
                </div>
                {brandError && <p role="alert" className="text-xs text-rose-400">{brandError}</p>}
                {brandSavedMsg && <p role="status" className="text-xs text-emerald-400">{brandSavedMsg}</p>}
                <div className="flex justify-end">
                  <Button size="sm" variant="primary" onClick={handleSaveTenantBranding} disabled={brandSaving}>
                    {brandSaving ? "Saving…" : "Save application branding"}
                  </Button>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Hospital Official Legal Name
                  </label>
                  <input
                    type="text"
                    value={editHospName}
                    onChange={(e) => setEditHospName(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-100 font-bold"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Registered Physical Address (Printed on Invoices &amp; Slips)
                  </label>
                  <input
                    type="text"
                    value={editHospAddress}
                    onChange={(e) => setEditHospAddress(e.target.value)}
                    className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Main Landline Phone</label>
                    <input
                      type="text"
                      value={editHospPhone}
                      onChange={(e) => setEditHospPhone(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 font-mono"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Accreditation String</label>
                    <input
                      type="text"
                      value={editHospAccreditation}
                      onChange={(e) => setEditHospAccreditation(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200"
                    />
                  </div>
                </div>

                <div className="flex justify-end pt-3 border-t border-slate-800">
                  <Button
                    size="sm"
                    variant="primary"
                    onClick={() => {
                      updateHospitalProfile({
                        name: editHospName,
                        address: editHospAddress,
                        phone: editHospPhone,
                        accreditation: editHospAccreditation,
                      });
                      setProfileSavedMsg("Hospital Profile & Print Letterhead Updated!");
                      setTimeout(() => setProfileSavedMsg(""), 3000);
                    }}
                    className="flex items-center gap-1.5"
                  >
                    <CheckCircle2 size={13} /> Save Hospital Profile &amp; Letterhead
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* Sub-tab 4: Workflow & Policy Rules */}
          {customSubTab === "policies" && (
            <Card className="p-5 bg-slate-900 border-slate-800 space-y-4 max-w-2xl">
              <div className="pb-2 border-b border-slate-800">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                  <Settings size={14} className="text-amber-400" /> Hospital Operational Policies &amp; Consent Rules
                </h3>
              </div>

              <div className="space-y-3 text-xs">
                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                  <div>
                    <div className="font-semibold text-slate-200">Require Upfront Payment for OPD Queue Token</div>
                    <div className="text-[11px] text-slate-400">Tokens will not enter doctor queue until cashier records receipt.</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={policies.requireUpfrontPaymentForToken}
                    onChange={(e) => updatePolicies({ requireUpfrontPaymentForToken: e.target.checked })}
                    className="h-4 w-4 rounded bg-slate-900 border-slate-700 text-sky-500"
                  />
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                  <div>
                    <div className="font-semibold text-slate-200">Enforce Statutory DPDP Act 2023 Consent</div>
                    <div className="text-[11px] text-slate-400">Requires explicit checkbox consent grants before MRN generation.</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={policies.enforceDpdpConsent}
                    onChange={(e) => updatePolicies({ enforceDpdpConsent: e.target.checked })}
                    className="h-4 w-4 rounded bg-slate-900 border-slate-700 text-sky-500"
                  />
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                  <div>
                    <div className="font-semibold text-slate-200">Automated MLC Police Intimation Certificate</div>
                    <div className="text-[11px] text-slate-400">Generates formal Section 39 CrPC intimation upon tagging any admission as MLC.</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={policies.autoAlertMlcToPolice}
                    onChange={(e) => updatePolicies({ autoAlertMlcToPolice: e.target.checked })}
                    className="h-4 w-4 rounded bg-slate-900 border-slate-700 text-sky-500"
                  />
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                  <div className="font-semibold text-slate-200">Hospital Default Free Follow-up Revisit Period (Days)</div>
                  <div className="text-[11px] text-slate-400">Baseline number of days within which a patient is eligible for free follow-up consults across OPD.</div>
                  <input
                    type="number"
                    value={policies.defaultRevisitFreeDays || 7}
                    onChange={(e) => updatePolicies({ defaultRevisitFreeDays: parseInt(e.target.value || "7", 10) })}
                    className="w-32 bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-sky-400 font-mono"
                  />
                </div>

                <div className="flex items-center justify-between p-3 rounded-lg bg-slate-950 border border-slate-800">
                  <div>
                    <div className="font-semibold text-slate-200">Allow Doctor-Specific Revisit Limit Overrides</div>
                    <div className="text-[11px] text-slate-400">Permits individual specialists (e.g. surgeons, cardiologists) to configure custom revisit windows beyond the hospital baseline.</div>
                  </div>
                  <input
                    type="checkbox"
                    checked={policies.allowDoctorSpecificRevisitRules}
                    onChange={(e) => updatePolicies({ allowDoctorSpecificRevisitRules: e.target.checked })}
                    className="h-4 w-4 rounded bg-slate-900 border-slate-700 text-sky-500"
                  />
                </div>
              </div>
            </Card>
          )}

          {/* Sub-tab 5: Statutory Print Layouts & Templates Studio */}
          {customSubTab === "printTemplates" && (
            <div className="space-y-6">
              {/* Document Selector Pills */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {[
                    { id: "thermal", label: "80mm Thermal Receipt (OPD Token)" },
                    { id: "wristband", label: "Patient ID Wristband (Barcode Strip)" },
                    { id: "bht", label: "A4 Bed Head Ticket (BHT Face Sheet)" },
                    { id: "discharge", label: "A4 Statutory Discharge Summary" },
                  ].map((doc) => (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() => setActiveDocTemplate(doc.id as any)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                        activeDocTemplate === doc.id
                          ? "bg-sky-600 text-white shadow"
                          : "bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800"
                      }`}
                    >
                      {doc.label}
                    </button>
                  ))}
                </div>

                {templateSavedMsg && (
                  <span className="text-xs text-emerald-400 font-mono flex items-center gap-1">
                    <CheckCircle2 size={13} /> {templateSavedMsg}
                  </span>
                )}
              </div>

              {/* Template Editor Grid: Left = Controls, Right = Live Visual Preview */}
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                {/* 1. Thermal Receipt Form & Preview */}
                {activeDocTemplate === "thermal" && (
                  <>
                    <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                      <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                        <Printer size={14} className="text-sky-400" /> Configure 80mm Thermal Receipt
                      </h4>
                      <div className="space-y-3 text-xs">
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Header Title (Hospital Branding)</label>
                          <input
                            type="text"
                            value={thermalTitle}
                            onChange={(e) => setThermalTitle(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-100 font-bold"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Thermal Paper Roll Width</label>
                          <select
                            value={thermalRollWidth}
                            onChange={(e) => setThermalRollWidth(e.target.value as any)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          >
                            <option value="58mm">58mm (2-inch Compact / Mobile POS)</option>
                            <option value="80mm">80mm (3-inch Standard Hospital POS)</option>
                            <option value="112mm">112mm (4-inch Desktop Slip Printer)</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Sub-Header Slogan</label>
                          <input
                            type="text"
                            value={thermalSubHeader}
                            onChange={(e) => setThermalSubHeader(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          />
                        </div>
                        <div className="space-y-2 pt-1 border-t border-slate-800">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={thermalShowWait}
                              onChange={(e) => setThermalShowWait(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Show Estimated Wait Time (Live Queue SLA)</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={thermalShowReceipt}
                              onChange={(e) => setThermalShowReceipt(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Include Cashier Fee &amp; Payment Receipt Details</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={thermalShowBarcode}
                              onChange={(e) => setThermalShowBarcode(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Print 2D Barcode Strip on Thermal Slip</span>
                          </label>
                        </div>
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Footer Notice / Instructions</label>
                          <input
                            type="text"
                            value={thermalFooter}
                            onChange={(e) => setThermalFooter(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          />
                        </div>
                        <div className="pt-2">
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => {
                              updatePrintTemplates({
                                thermalToken: {
                                  headerTitle: thermalTitle,
                                  subHeader: thermalSubHeader,
                                  rollWidth: thermalRollWidth,
                                  showEstimatedWait: thermalShowWait,
                                  showCashierReceipt: thermalShowReceipt,
                                  showBarcode: thermalShowBarcode,
                                  footerNotice: thermalFooter,
                                },
                              });
                              setTemplateSavedMsg(`${thermalRollWidth} Thermal Receipt Template Saved!`);
                              setTimeout(() => setTemplateSavedMsg(""), 3000);
                            }}
                          >
                            Save Thermal Layout
                          </Button>
                        </div>
                      </div>
                    </Card>

                    {/* Live Preview */}
                    <Card className="p-4 bg-slate-950 border-slate-800 flex flex-col items-center justify-center">
                      <div className="text-[10px] font-mono text-slate-400 mb-2 uppercase tracking-wider">Live Thermal Preview (80mm)</div>
                      <div className="w-72 bg-white text-slate-950 p-4 border border-slate-400 rounded-sm font-mono text-xs space-y-2 shadow-2xl">
                        <div className="text-center font-black text-sm uppercase">{thermalTitle}</div>
                        <div className="text-center text-[10px] text-slate-600">{thermalSubHeader}</div>
                        <div className="border-t border-dashed border-slate-400 pt-1 text-center font-black text-2xl tracking-widest">
                          CARDIO-14
                        </div>
                        <div className="text-center text-[10px]">Token #14 • Room Cabin 204</div>
                        <div className="border-t border-dashed border-slate-400 pt-1 space-y-0.5 text-[11px]">
                          <div><b>Doctor:</b> Dr. Vikram Seth</div>
                          <div><b>Specialty:</b> Cardiology</div>
                          {thermalShowWait && <div><b>Est. Wait:</b> ~15 mins</div>}
                          <div><b>Patient:</b> RAMESH SHARMA</div>
                          <div><b>UHID:</b> MRN-2026-0091</div>
                        </div>
                        {thermalShowReceipt && (
                          <div className="border-t border-dashed border-slate-400 pt-1 space-y-0.5 text-[10px]">
                            <div><b>Receipt:</b> RCPT-2026-0914</div>
                            <div><b>Mode:</b> UPI • <b>Fee Paid:</b> ₹800.00</div>
                          </div>
                        )}
                        {thermalShowBarcode && (
                          <div className="border-t border-dashed border-slate-400 pt-2 text-center">
                            <div className="bg-slate-900 text-white text-[9px] py-1 tracking-widest font-mono">|||| | |||| ||| |||</div>
                          </div>
                        )}
                        <div className="border-t border-dashed border-slate-400 pt-1 text-center text-[9px] text-slate-600">
                          {thermalFooter}
                        </div>
                      </div>
                    </Card>
                  </>
                )}

                {/* 2. Patient ID Wristband Form & Preview */}
                {activeDocTemplate === "wristband" && (
                  <>
                    <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                      <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                        <Printer size={14} className="text-sky-400" /> Configure Patient Wristband
                      </h4>
                      <div className="space-y-3 text-xs">
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Hospital / Clinic Name</label>
                          <input
                            type="text"
                            value={wristbandName}
                            onChange={(e) => setWristbandName(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-100 font-bold"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Dedicated Wristband Printer Hardware</label>
                          <select
                            value={wristbandPrinterType}
                            onChange={(e) => setWristbandPrinterType(e.target.value as any)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          >
                            <option value="DIRECT_THERMAL_ROLL">Direct Thermal Roll Printer (Zebra ZD410 / SATO WS2 / TSC)</option>
                            <option value="ZEBRA_HC100">Zebra ZD510-HC / HC100 Cartridge Printer (Vertical / Narrow-Edge Feed)</option>
                            <option value="LASER_SHEETLET">A4 Sheet-Fed Laser with Peel-Off Wristband (Avery / PDC)</option>
                            <option value="STANDARD_POS">Standard Direct Thermal Desktop</option>
                          </select>
                        </div>

                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Wristband Size &amp; Patient Demographic Preset</label>
                          <select
                            value={wristbandPreset}
                            onChange={(e) => handleWristbandPresetChange(e.target.value as any)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          >
                            <option value="ADULT_STANDARD_280x25">Adult Standard (280mm × 25mm / 11" × 1")</option>
                            <option value="ADULT_WIDE_280x28">Adult Wide (280mm × 28mm)</option>
                            <option value="ADULT_SLIM_250x19">Adult Slim / Clip (250mm × 19mm / 10" × 0.75")</option>
                            <option value="PEDIATRIC_180x19">Pediatric / Child (180mm × 19mm / 7" × 0.75")</option>
                            <option value="INFANT_NICU_150x15">Infant / NICU Ultra-Soft (150mm × 15mm / 6" × 0.6")</option>
                            <option value="NEONATE_MICRO_100x12">Neonate Micro-Premature (100mm × 12mm)</option>
                            <option value="CUSTOM">Custom Dimensions (Manual Millimeter Configuration)</option>
                          </select>
                        </div>

                        <div className="grid grid-cols-3 gap-2 bg-slate-950 p-2.5 rounded border border-slate-800">
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">Total Length (mm)</label>
                            <input
                              type="number"
                              value={wristbandWidthMm}
                              onChange={(e) => setWristbandWidthMm(Number(e.target.value))}
                              className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">Band Width (mm)</label>
                            <input
                              type="number"
                              value={wristbandHeightMm}
                              onChange={(e) => setWristbandHeightMm(Number(e.target.value))}
                              className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-white font-mono"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-0.5">Printable Face (mm)</label>
                            <input
                              type="number"
                              value={wristbandPrintableLengthMm}
                              onChange={(e) => setWristbandPrintableLengthMm(Number(e.target.value))}
                              className="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-white font-mono"
                            />
                          </div>
                        </div>

                        <div className="flex items-center gap-4">
                          <label className="text-[11px] text-slate-400">Print Feed Orientation:</label>
                          <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                            <input
                              type="radio"
                              name="wbOrientation"
                              value="LANDSCAPE"
                              checked={wristbandOrientation === "LANDSCAPE"}
                              onChange={() => setWristbandOrientation("LANDSCAPE")}
                            />
                            <span>Landscape (Along Band)</span>
                          </label>
                          <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer">
                            <input
                              type="radio"
                              name="wbOrientation"
                              value="PORTRAIT"
                              checked={wristbandOrientation === "PORTRAIT"}
                              onChange={() => setWristbandOrientation("PORTRAIT")}
                            />
                            <span>Portrait (Zebra HC100 Cartridge)</span>
                          </label>
                        </div>
                        <div className="space-y-2 pt-1 border-t border-slate-800">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={wristbandBlood}
                              onChange={(e) => setWristbandBlood(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Show Blood Group prominently on Wristband</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={wristbandPhone}
                              onChange={(e) => setWristbandPhone(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Show Contact Phone Number</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={wristbandAllergy}
                              onChange={(e) => setWristbandAllergy(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Print Critical Allergy Alert Tag (e.g. Red Highlight)</span>
                          </label>
                        </div>
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Barcode Standard</label>
                          <select
                            value={wristbandBarcode}
                            onChange={(e) => setWristbandBarcode(e.target.value as any)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          >
                            <option value="CODE128">Linear Barcode (Code 128)</option>
                            <option value="QR">2D Matrix / QR Code</option>
                          </select>
                        </div>
                        <div className="pt-2">
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => {
                              updatePrintTemplates({
                                wristband: {
                                  hospitalName: wristbandName,
                                  preset: wristbandPreset,
                                  widthMm: wristbandWidthMm,
                                  heightMm: wristbandHeightMm,
                                  printableLengthMm: wristbandPrintableLengthMm,
                                  orientation: wristbandOrientation,
                                  printerType: wristbandPrinterType,
                                  wristbandType: wristbandType,
                                  showBloodGroup: wristbandBlood,
                                  showEmergencyPhone: wristbandPhone,
                                  showAllergyWarning: wristbandAllergy,
                                  barcodeFormat: wristbandBarcode,
                                },
                              });
                              setTemplateSavedMsg(`Wristband Template (${wristbandWidthMm}x${wristbandHeightMm}mm) Saved!`);
                              setTimeout(() => setTemplateSavedMsg(""), 3000);
                            }}
                          >
                            Save Wristband Layout
                          </Button>
                        </div>
                      </div>
                    </Card>

                    {/* Wristband Preview */}
                    <Card className="p-4 bg-slate-950 border-slate-800 flex flex-col items-center justify-center">
                      <div className="text-[10px] font-mono text-slate-400 mb-2 uppercase tracking-wider">Live Wristband Preview</div>
                      <div className="w-full max-w-md bg-white text-slate-950 p-3 border-2 border-dashed border-slate-800 rounded-lg flex items-center justify-between shadow-2xl">
                        <div>
                          <div className="font-black text-xs uppercase">{wristbandName}</div>
                          <div className="font-bold text-sm uppercase mt-0.5">SIDDHARTH VERMA</div>
                          <div className="text-[10px] text-slate-600 font-mono">
                            MALE • 38y {wristbandBlood && "• Blood: B+"}
                          </div>
                          {wristbandPhone && <div className="text-[9px] text-slate-500 font-mono">Ph: 9876543210</div>}
                          {wristbandAllergy && (
                            <div className="text-[9px] font-bold text-rose-700 bg-rose-50 px-1 py-0.5 rounded border border-rose-300 mt-1 inline-block">
                              ALLERGIES: PENICILLIN G
                            </div>
                          )}
                        </div>
                        <div className="text-center font-mono">
                          <div className="bg-slate-900 text-white text-[9px] px-3 py-1.5 tracking-widest font-black">
                            ||||| | |||| ||
                          </div>
                          <div className="text-[10px] font-bold mt-0.5">MRN-2026-0001</div>
                        </div>
                      </div>
                    </Card>
                  </>
                )}

                {/* 3. A4 Bed Head Ticket (BHT) Form & Preview */}
                {activeDocTemplate === "bht" && (
                  <>
                    <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                      <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                        <Printer size={14} className="text-sky-400" /> Configure Bed Head Ticket (BHT Face Sheet)
                      </h4>
                      <div className="space-y-3 text-xs">
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Hospital Title</label>
                          <input
                            type="text"
                            value={bhtTitle}
                            onChange={(e) => setBhtTitle(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-100 font-bold"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Docket Sub-Title</label>
                          <input
                            type="text"
                            value={bhtSubTitle}
                            onChange={(e) => setBhtSubTitle(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          />
                        </div>
                        <div className="space-y-2 pt-1 border-t border-slate-800">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={bhtFinancial}
                              onChange={(e) => setBhtFinancial(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Show Financial Classification &amp; TPA Pre-Auth</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={bhtNurseChecklist}
                              onChange={(e) => setBhtNurseChecklist(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Include Station Nurse Intake Handover Checklist</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={bhtSignatures}
                              onChange={(e) => setBhtSignatures(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Print Formal ADT Officer &amp; Guardian Signature Lines</span>
                          </label>
                        </div>
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Custom Seal / Accreditation Text</label>
                          <input
                            type="text"
                            value={bhtSeal}
                            onChange={(e) => setBhtSeal(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          />
                        </div>
                        <div className="pt-2">
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => {
                              updatePrintTemplates({
                                bedHeadTicket: {
                                  hospitalTitle: bhtTitle,
                                  subTitle: bhtSubTitle,
                                  showFinancialInfo: bhtFinancial,
                                  showNurseChecklist: bhtNurseChecklist,
                                  showSignatureBlock: bhtSignatures,
                                  customSealText: bhtSeal,
                                },
                              });
                              setTemplateSavedMsg("Bed Head Ticket Template Saved!");
                              setTimeout(() => setTemplateSavedMsg(""), 3000);
                            }}
                          >
                            Save BHT Layout
                          </Button>
                        </div>
                      </div>
                    </Card>

                    {/* BHT Preview */}
                    <Card className="p-4 bg-slate-950 border-slate-800 flex flex-col items-center justify-center">
                      <div className="text-[10px] font-mono text-slate-400 mb-2 uppercase tracking-wider">Live BHT Face Sheet Preview</div>
                      <div className="w-full max-w-sm bg-white text-slate-950 p-4 border border-slate-300 rounded text-[11px] font-sans space-y-2 shadow-2xl">
                        <div className="text-center border-b pb-1">
                          <div className="font-bold text-xs uppercase">{bhtTitle}</div>
                          <div className="text-[9px] text-slate-600 font-mono">{bhtSubTitle}</div>
                          <div className="text-[8px] text-slate-500">{bhtSeal}</div>
                        </div>
                        <div className="flex justify-between font-mono text-[10px]">
                          <div><b>DOCKET:</b> ADM-101</div>
                          <div><b>BED:</b> B-101 (R-101)</div>
                        </div>
                        <div className="bg-slate-50 p-2 rounded border border-slate-200 text-[10px] space-y-0.5">
                          <div><b>Patient:</b> SIDDHARTH VERMA (38y • MALE)</div>
                          <div><b>MRN:</b> MRN-2026-0001</div>
                          <div><b>Ward:</b> General Inpatient Ward 2A</div>
                          <div><b>Consultant:</b> Dr. Vikram Seth</div>
                          {bhtFinancial && <div><b>TPA:</b> Star Health Insurance (Auth: ₹1,50,000)</div>}
                        </div>
                        {bhtNurseChecklist && (
                          <div className="p-1.5 bg-slate-50 rounded border text-[9px] font-mono">
                            <div>[✓] Wristband Verified • [✓] Vitals Logged • [✓] Allergy Band Checked</div>
                          </div>
                        )}
                        {bhtSignatures && (
                          <div className="pt-4 flex justify-between text-[9px] border-t">
                            <div>ADT Officer Signature</div>
                            <div>Guardian Signature</div>
                          </div>
                        )}
                      </div>
                    </Card>
                  </>
                )}

                {/* 4. A4 Discharge Summary Form & Preview */}
                {activeDocTemplate === "discharge" && (
                  <>
                    <Card className="p-4 bg-slate-900 border-slate-800 space-y-3">
                      <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-1.5">
                        <Printer size={14} className="text-sky-400" /> Configure Discharge Summary Template
                      </h4>
                      <div className="space-y-3 text-xs">
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Header Title</label>
                          <input
                            type="text"
                            value={dischargeHeader}
                            onChange={(e) => setDischargeHeader(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-100 font-bold"
                          />
                        </div>
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Document Sub-Title</label>
                          <input
                            type="text"
                            value={dischargeSubTitle}
                            onChange={(e) => setDischargeSubTitle(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          />
                        </div>
                        <div className="space-y-2 pt-1 border-t border-slate-800">
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={dischargeMeds}
                              onChange={(e) => setDischargeMeds(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Include Medication Reconciliation Table</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={dischargeDiet}
                              onChange={(e) => setDischargeDiet(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Include Dietary &amp; Activity Instructions</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={dischargeWarnings}
                              onChange={(e) => setDischargeWarnings(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Include Red-Flag Warning Signs (Emergency Protocols)</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={dischargeSeal}
                              onChange={(e) => setDischargeSeal(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Include Treating Consultant Seal Block</span>
                          </label>
                          <label className="flex items-center gap-2 cursor-pointer">
                            <input
                              type="checkbox"
                              checked={dischargeSuperintendent}
                              onChange={(e) => setDischargeSuperintendent(e.target.checked)}
                              className="rounded bg-slate-900 border-slate-700 text-sky-500"
                            />
                            <span className="text-slate-300">Include Medical Superintendent Counter-Sign Line</span>
                          </label>
                        </div>
                        <div>
                          <label className="block text-[11px] text-slate-400 mb-1">Legal Disclaimer / NABH Notice</label>
                          <input
                            type="text"
                            value={dischargeDisclaimer}
                            onChange={(e) => setDischargeDisclaimer(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                          />
                        </div>
                        <div className="pt-2">
                          <Button
                            size="sm"
                            variant="primary"
                            onClick={() => {
                              updatePrintTemplates({
                                dischargeSummary: {
                                  hospitalHeader: dischargeHeader,
                                  subTitle: dischargeSubTitle,
                                  showMedicationReconciliation: dischargeMeds,
                                  showDietaryInstructions: dischargeDiet,
                                  showWarningSigns: dischargeWarnings,
                                  showDoctorSealBlock: dischargeSeal,
                                  showSuperintendentSign: dischargeSuperintendent,
                                  disclaimerText: dischargeDisclaimer,
                                },
                              });
                              setTemplateSavedMsg("Discharge Summary Template Saved!");
                              setTimeout(() => setTemplateSavedMsg(""), 3000);
                            }}
                          >
                            Save Discharge Template
                          </Button>
                        </div>
                      </div>
                    </Card>

                    {/* Discharge Preview */}
                    <Card className="p-4 bg-slate-950 border-slate-800 flex flex-col items-center justify-center">
                      <div className="text-[10px] font-mono text-slate-400 mb-2 uppercase tracking-wider">Live Discharge Summary Preview</div>
                      <div className="w-full max-w-sm bg-white text-slate-950 p-4 border border-slate-300 rounded text-[11px] font-sans space-y-2 shadow-2xl">
                        <div className="text-center border-b pb-1">
                          <div className="font-bold text-xs uppercase">{dischargeHeader}</div>
                          <div className="text-[9px] text-slate-700 font-bold">{dischargeSubTitle}</div>
                        </div>
                        <div className="flex justify-between text-[10px] border-b pb-1">
                          <div><b>Patient:</b> SIDDHARTH VERMA</div>
                          <div><b>UHID:</b> MRN-2026-0001</div>
                        </div>
                        <div className="text-[10px] space-y-1">
                          <div><b>Diagnosis:</b> Acute Coronary Syndrome • Unstable Angina</div>
                          <div><b>Clinical Course:</b> Patient hemodynamically stable. Nil acute chest pain.</div>
                          {dischargeMeds && (
                            <div className="bg-slate-50 p-1.5 rounded border text-[9px]">
                              <b>Medications:</b> Tab. Aspirin 75mg OD • Tab. Atorvastatin 40mg HS
                            </div>
                          )}
                          {dischargeDiet && (
                            <div className="text-[9px] text-slate-700"><b>Diet:</b> Low salt, low fat cardiac diet.</div>
                          )}
                          {dischargeWarnings && (
                            <div className="text-[9px] text-rose-700 font-bold"><b>Warning Signs:</b> In case of recurrence of chest pain, call emergency immediately.</div>
                          )}
                        </div>
                        <div className="pt-4 flex justify-between text-[9px] border-t">
                          {dischargeSeal && <div>Treating Consultant Seal</div>}
                          {dischargeSuperintendent && <div>Medical Superintendent</div>}
                        </div>
                        <div className="text-[8px] text-slate-500 text-center pt-1 border-t">
                          {dischargeDisclaimer}
                        </div>
                      </div>
                    </Card>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Sub-tab 6: Hardware Printers & Network Devices */}
          {customSubTab === "printers" && (
            <div className="space-y-6">
              {/* Header Info Card */}
              <Card className="p-5 bg-slate-900 border-slate-800 space-y-4">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-3 border-b border-slate-800">
                  <div className="flex items-center gap-3">
                    <div className="p-2.5 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400">
                      <Cpu size={24} />
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-slate-100 flex items-center gap-2">
                        Departmental Hardware Printers &amp; JetDirect / RAW Network Sockets
                        <Badge variant="purple" size="sm">Zero Hardcoded Sizes</Badge>
                      </h3>
                      <p className="text-xs text-slate-400">
                        Configure physical printer dimensions (mm), margins, feed orientation, and network endpoints (TCP Port 9100 RAW, USB, WiFi, ESC/POS, ZPL) across hospital departments.
                      </p>
                    </div>
                  </div>
                  {printerSuccessMsg && (
                    <div className="px-3 py-1.5 rounded-lg bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 text-xs font-semibold animate-pulse">
                      {printerSuccessMsg}
                    </div>
                  )}
                </div>

                {/* Quick Hardware Presets */}
                <div className="space-y-1.5">
                  <label className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block">
                    Quick Hardware Presets &amp; Cartridge Autofill
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => applyPrinterHardwarePreset("ZEBRA_ZD510_HC")}
                      className="px-2.5 py-1 text-xs bg-slate-950 hover:bg-slate-800 text-sky-300 border border-slate-800 rounded flex items-center gap-1 transition-all"
                    >
                      <Zap size={11} className="text-amber-400" /> Zebra ZD510-HC (Vertical 25×280mm Portrait)
                    </button>
                    <button
                      type="button"
                      onClick={() => applyPrinterHardwarePreset("DIRECT_THERMAL_WRISTBAND")}
                      className="px-2.5 py-1 text-xs bg-slate-950 hover:bg-slate-800 text-sky-300 border border-slate-800 rounded flex items-center gap-1 transition-all"
                    >
                      <Zap size={11} className="text-amber-400" /> Desktop Direct Thermal (Wide 280×25mm Landscape)
                    </button>
                    <button
                      type="button"
                      onClick={() => applyPrinterHardwarePreset("EPSON_80MM_THERMAL")}
                      className="px-2.5 py-1 text-xs bg-slate-950 hover:bg-slate-800 text-sky-300 border border-slate-800 rounded flex items-center gap-1 transition-all"
                    >
                      <Zap size={11} className="text-amber-400" /> POS 80mm Token Slip (Continuous ESC/POS)
                    </button>
                    <button
                      type="button"
                      onClick={() => applyPrinterHardwarePreset("COMPACT_58MM_THERMAL")}
                      className="px-2.5 py-1 text-xs bg-slate-950 hover:bg-slate-800 text-sky-300 border border-slate-800 rounded flex items-center gap-1 transition-all"
                    >
                      <Zap size={11} className="text-amber-400" /> Compact 58mm Thermal Roll (Continuous)
                    </button>
                    <button
                      type="button"
                      onClick={() => applyPrinterHardwarePreset("WARD_LASER_A4")}
                      className="px-2.5 py-1 text-xs bg-slate-950 hover:bg-slate-800 text-sky-300 border border-slate-800 rounded flex items-center gap-1 transition-all"
                    >
                      <Zap size={11} className="text-amber-400" /> Ward LaserJet (A4 210×297mm 600 DPI)
                    </button>
                    <button
                      type="button"
                      onClick={() => applyPrinterHardwarePreset("LAB_TUBE_LABELER")}
                      className="px-2.5 py-1 text-xs bg-slate-950 hover:bg-slate-800 text-sky-300 border border-slate-800 rounded flex items-center gap-1 transition-all"
                    >
                      <Zap size={11} className="text-amber-400" /> Diagnostics Tube Labeler (50×25mm)
                    </button>
                  </div>
                </div>
              </Card>

              {/* Form: Add New Hardware Printer */}
              <Card className="p-5 bg-slate-900 border-slate-800 space-y-4">
                <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <Plus size={14} className="text-sky-400" /> Add / Configure Physical Printer Device
                </h4>

                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    if (!prnName.trim()) return;

                    addPrinter({
                      name: prnName,
                      location: prnLocation || "Main Admission Desk",
                      connectionType: prnConnType,
                      targetCategory: prnCategory,
                      protocol: prnProtocol,
                      ipAddress: (prnConnType === "NETWORK_IP" || prnConnType === "WIFI") ? prnIp : undefined,
                      port: (prnConnType === "NETWORK_IP" || prnConnType === "WIFI") ? prnPort : undefined,
                      isDefault: prnIsDefault,
                      mediaWidthMm: Number(prnWidthMm) || 80,
                      mediaHeightMm: Number(prnHeightMm) || 0,
                      printableWidthMm: Number(prnPrintableWidthMm) || Number(prnWidthMm) || 75,
                      printableHeightMm: Number(prnPrintableHeightMm) || (Number(prnHeightMm) > 0 ? Number(prnHeightMm) : 0),
                      marginTopMm: Number(prnMarginTop) || 0,
                      marginBottomMm: Number(prnMarginBottom) || 0,
                      marginLeftMm: Number(prnMarginLeft) || 0,
                      marginRightMm: Number(prnMarginRight) || 0,
                      orientation: prnOrientation,
                      dpi: Number(prnDpi) || 203,
                      status: "ONLINE",
                    });

                    setPrinterSuccessMsg(`Printer "${prnName}" registered successfully!`);
                    setPrnName("");
                    setPrnLocation("");
                    setTimeout(() => setPrinterSuccessMsg(""), 3500);
                  }}
                  className="space-y-4"
                >
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                    <div>
                      <label className="text-[11px] text-slate-400 block mb-1">Printer Device Name *</label>
                      <input
                        type="text"
                        placeholder="e.g. Zebra ZD510-HC Admission Desk"
                        value={prnName}
                        onChange={(e) => setPrnName(e.target.value)}
                        required
                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] text-slate-400 block mb-1">Hospital Location / Station</label>
                      <input
                        type="text"
                        placeholder="e.g. Counter 1, ED Trauma Bay 2, Ward 3A"
                        value={prnLocation}
                        onChange={(e) => setPrnLocation(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] text-slate-400 block mb-1">Target Document Category *</label>
                      <select
                        value={prnCategory}
                        onChange={(e) => setPrnCategory(e.target.value as PrinterTargetCategory)}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                      >
                        <option value="WRISTBAND">Patient Wristbands (Barcoded Strap)</option>
                        <option value="THERMAL_TOKEN">Thermal Token &amp; Cashier Slips (Roll)</option>
                        <option value="CLINICAL_A4">Clinical BHT &amp; Discharge Reports (A4)</option>
                        <option value="LAB_LABEL">Diagnostics Specimen Tube Labels</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
                    <div>
                      <label className="text-[11px] text-slate-400 block mb-1">Connectivity *</label>
                      <select
                        value={prnConnType}
                        onChange={(e) => setPrnConnType(e.target.value as PrinterConnectionType)}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                      >
                        <option value="NETWORK_IP">Network Ethernet (TCP Port 9100 RAW / JetDirect)</option>
                        <option value="WIFI">Hospital Secure WiFi (IP Socket)</option>
                        <option value="USB">Direct USB / POS Thermal Interface</option>
                        <option value="SYSTEM_DRIVER">OS Spooled System Driver</option>
                      </select>
                    </div>
                    <div>
                      <label className="text-[11px] text-slate-400 block mb-1">Print Protocol</label>
                      <select
                        value={prnProtocol}
                        onChange={(e) => setPrnProtocol(e.target.value as PrinterProtocol)}
                        className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                      >
                        <option value="RAW_ZPL">RAW ZPL (Zebra HC100 / ZD Series)</option>
                        <option value="RAW_ESCPOS">RAW ESC/POS (Epson / Star / POS)</option>
                        <option value="HTML_DRIVER">Browser HTML Engine / Spooler</option>
                      </select>
                    </div>
                    {(prnConnType === "NETWORK_IP" || prnConnType === "WIFI") ? (
                      <>
                        <div>
                          <label className="text-[11px] text-slate-400 block mb-1">IP Address</label>
                          <input
                            type="text"
                            placeholder="192.168.1.182"
                            value={prnIp}
                            onChange={(e) => setPrnIp(e.target.value)}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                          />
                        </div>
                        <div>
                          <label className="text-[11px] text-slate-400 block mb-1">Port (Default 9100)</label>
                          <input
                            type="number"
                            value={prnPort}
                            onChange={(e) => setPrnPort(Number(e.target.value))}
                            className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                          />
                        </div>
                      </>
                    ) : (
                      <div className="col-span-2 flex items-center text-xs text-slate-500 pt-5">
                        <HardDrive size={14} className="mr-1.5" /> Direct attached USB / driver endpoint auto-negotiated by host
                      </div>
                    )}
                  </div>

                  {/* Millimeter Dimensions & Margins */}
                  <div className="p-3 bg-slate-950 rounded-lg border border-slate-800/80 space-y-3">
                    <div className="text-[11px] font-semibold text-slate-300 flex items-center justify-between">
                      <span>Exact Media Physical Millimeters (Zero Hardcoded Boundaries)</span>
                      <span className="text-[10px] text-slate-500 font-mono">Set 0mm Height for Continuous Thermal Rolls</span>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Width (mm)</label>
                        <input
                          type="number"
                          value={prnWidthMm}
                          onChange={(e) => setPrnWidthMm(Number(e.target.value))}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Height (mm)</label>
                        <input
                          type="number"
                          value={prnHeightMm}
                          onChange={(e) => setPrnHeightMm(Number(e.target.value))}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Printable W (mm)</label>
                        <input
                          type="number"
                          value={prnPrintableWidthMm}
                          onChange={(e) => setPrnPrintableWidthMm(Number(e.target.value))}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Printable H (mm)</label>
                        <input
                          type="number"
                          value={prnPrintableHeightMm}
                          onChange={(e) => setPrnPrintableHeightMm(Number(e.target.value))}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Feed Orientation</label>
                        <select
                          value={prnOrientation}
                          onChange={(e) => setPrnOrientation(e.target.value as "PORTRAIT" | "LANDSCAPE")}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                        >
                          <option value="PORTRAIT">PORTRAIT (Vertical Feed)</option>
                          <option value="LANDSCAPE">LANDSCAPE (Wide Feed)</option>
                        </select>
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-1">Resolution (DPI)</label>
                        <select
                          value={prnDpi}
                          onChange={(e) => setPrnDpi(Number(e.target.value))}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1.5 text-xs text-slate-200 font-mono"
                        >
                          <option value="203">203 DPI (Standard Thermal)</option>
                          <option value="300">300 DPI (Zebra Wristband HD)</option>
                          <option value="600">600 DPI (High-Res Laser A4)</option>
                        </select>
                      </div>
                    </div>

                    {/* Margins */}
                    <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-slate-800/60">
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-0.5">Top Margin (mm)</label>
                        <input
                          type="number"
                          value={prnMarginTop}
                          onChange={(e) => setPrnMarginTop(Number(e.target.value))}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-0.5">Bottom Margin (mm)</label>
                        <input
                          type="number"
                          value={prnMarginBottom}
                          onChange={(e) => setPrnMarginBottom(Number(e.target.value))}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-0.5">Left Margin (mm)</label>
                        <input
                          type="number"
                          value={prnMarginLeft}
                          onChange={(e) => setPrnMarginLeft(Number(e.target.value))}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-xs text-slate-200 font-mono"
                        />
                      </div>
                      <div>
                        <label className="text-[10px] text-slate-400 block mb-0.5">Right Margin (mm)</label>
                        <input
                          type="number"
                          value={prnMarginRight}
                          onChange={(e) => setPrnMarginRight(Number(e.target.value))}
                          className="w-full bg-slate-900 border border-slate-800 rounded p-1 text-xs text-slate-200 font-mono"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2">
                    <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={prnIsDefault}
                        onChange={(e) => setPrnIsDefault(e.target.checked)}
                        className="rounded border-slate-700 bg-slate-900 text-sky-500"
                      />
                      <span>Set as Default Device for this Document Category</span>
                    </label>

                    <Button size="sm" variant="primary" type="submit" className="flex items-center gap-1.5">
                      <Plus size={14} /> Register Printer Device
                    </Button>
                  </div>
                </form>
              </Card>

              {/* Hardware Device Inventory List */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                    <Printer size={14} className="text-sky-400" /> Configured Departmental Devices ({printers.length})
                  </h4>
                  <span className="text-[11px] text-slate-500">
                    Live hardware status monitored via raw socket handshake
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-3">
                  {printers.map((prn) => (
                    <Card key={prn.id} className="p-4 bg-slate-900 border-slate-800 hover:border-slate-700 transition-all">
                      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
                        <div className="space-y-1.5 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-bold text-sm text-slate-100">{prn.name}</span>
                            <Badge
                              variant={prn.targetCategory === "WRISTBAND" ? "purple" : prn.targetCategory === "THERMAL_TOKEN" ? "info" : prn.targetCategory === "CLINICAL_A4" ? "success" : "warning"}
                              size="sm"
                            >
                              {prn.targetCategory}
                            </Badge>
                            {prn.isDefault && (
                              <Badge variant="success" size="sm" className="font-bold">
                                ★ DEFAULT
                              </Badge>
                            )}
                            <Badge variant={prn.status === "ONLINE" ? "success" : "neutral"} size="sm">
                              {prn.status}
                            </Badge>
                          </div>

                          <div className="flex flex-wrap items-center gap-3 text-xs text-slate-400 font-mono">
                            <span className="flex items-center gap-1 text-slate-300">
                              <Building size={12} className="text-slate-500" /> {prn.location}
                            </span>
                            <span>•</span>
                            <span className="flex items-center gap-1">
                              {prn.connectionType === "NETWORK_IP" ? <Network size={12} className="text-sky-400" /> : prn.connectionType === "WIFI" ? <Wifi size={12} className="text-emerald-400" /> : <HardDrive size={12} className="text-amber-400" />}
                              {prn.connectionType} {prn.ipAddress ? `(${prn.ipAddress}:${prn.port || 9100})` : "(Direct Hardware)"}
                            </span>
                            <span>•</span>
                            <span>Protocol: <b className="text-slate-200">{prn.protocol}</b></span>
                          </div>

                          <div className="text-[11px] text-slate-400 flex flex-wrap items-center gap-2 pt-1 font-mono">
                            <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                              Media: <b className="text-sky-300">{prn.mediaWidthMm}mm × {prn.mediaHeightMm > 0 ? `${prn.mediaHeightMm}mm` : "Continuous Roll"}</b>
                            </span>
                            <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                              Feed: <b className="text-slate-300">{prn.orientation}</b>
                            </span>
                            <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                              Printable: <b>{prn.printableWidthMm || prn.mediaWidthMm}mm × {prn.printableHeightMm || prn.mediaHeightMm || "Full"}mm</b>
                            </span>
                            <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                              Margins: <b>T:{prn.marginTopMm} B:{prn.marginBottomMm} L:{prn.marginLeftMm} R:{prn.marginRightMm} mm</b>
                            </span>
                            <span className="bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                              Density: <b>{prn.dpi} DPI</b>
                            </span>
                          </div>
                        </div>

                        {/* Action buttons */}
                        <div className="flex items-center gap-2 self-end lg:self-center">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleTestPrint(prn)}
                            className="text-xs flex items-center gap-1.5 text-sky-400 hover:text-sky-300 border-sky-500/30"
                          >
                            <Zap size={13} className="text-amber-400" /> Test Print / Ping Slip
                          </Button>

                          {!prn.isDefault && (
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => setDefaultPrinter(prn.id)}
                              className="text-xs text-slate-400 hover:text-emerald-400"
                            >
                              Make Default
                            </Button>
                          )}

                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => {
                              if (confirm(`Remove printer device "${prn.name}"?`)) {
                                deletePrinter(prn.id);
                              }
                            }}
                            className="text-xs text-rose-400 hover:bg-rose-950/30"
                          >
                            <Trash2 size={13} />
                          </Button>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {activePreviewRegister && (
        <Modal
          isOpen={true}
          onClose={() => setActivePreviewRegister(null)}
          title={`Register Stream Preview — ${activePreviewRegister.name} (${activePreviewRegister.code})`}
        >
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Standard schema formatted under RFC 4180 with UTF-8 BOM encoding:</span>
              <Badge variant={activePreviewRegister.isLive ? "success" : "neutral"} size="sm">
                {activePreviewRegister.isLive ? "Live Database Query" : "Standard Schema Preview"}
              </Badge>
            </div>

            <div className="overflow-x-auto rounded-lg border border-slate-800 bg-slate-950 p-2">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-[11px] uppercase bg-slate-900/60">
                    {activePreviewRegister.headers.map((h, i) => (
                      <th key={i} className="p-2">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/40">
                  {activePreviewRegister.rows.map((row, rIdx) => (
                    <tr key={rIdx} className="text-slate-300 hover:bg-slate-900/40">
                      {row.map((cell, cIdx) => (
                        <td key={cIdx} className="p-2">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <a
                href={activePreviewRegister.endpoint}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-md bg-sky-500 hover:bg-sky-400 text-slate-950 transition-colors"
              >
                <Download size={13} /> Download RFC 4180 CSV
              </a>

              <Button
                variant="outline"
                size="sm"
                onClick={() => setActivePreviewRegister(null)}
              >
                Close Preview
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Batch Bed Provisioner Modal */}
      {batchModalOpen && (
        <Modal
          isOpen={batchModalOpen}
          onClose={() => setBatchModalOpen(false)}
          title="⚡ Batch Provision Ward Beds (Commission New Wing / Ward)"
        >
          <div className="space-y-4 max-w-xl">
            <p className="text-xs text-slate-400">
              Rapidly commission multiple beds for a new wing or ward. Automatically generates sequenced bed numbers and links them into the campus matrix.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Ward Name *</label>
                <input
                  type="text"
                  value={batchWardName}
                  onChange={(e) => setBatchWardName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                  placeholder="e.g. Surgical ICU Wing B"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Building / Tower *</label>
                <select
                  value={batchTower}
                  onChange={(e) => setBatchTower(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                >
                  <option value="Main Tower">Main Tower</option>
                  <option value="Super Specialty Block">Super Specialty Block</option>
                  <option value="Mother & Child Block">Mother &amp; Child Block</option>
                  <option value="Trauma Centre">Trauma Centre</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Floor *</label>
                <select
                  value={batchFloor}
                  onChange={(e) => setBatchFloor(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                >
                  <option value="Ground Floor">Ground Floor</option>
                  <option value="Floor 1">Floor 1</option>
                  <option value="Floor 2">Floor 2</option>
                  <option value="Floor 3">Floor 3</option>
                  <option value="Floor 4">Floor 4</option>
                  <option value="Floor 5">Floor 5</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Bed Category *</label>
                <select
                  value={batchCategory}
                  onChange={(e) => setBatchCategory(e.target.value as "General" | "Semi-Private" | "Private" | "ICU")}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                >
                  <option value="General">General Ward</option>
                  <option value="Semi-Private">Semi-Private Bay</option>
                  <option value="Private">Private AC Room</option>
                  <option value="ICU">Intensive Care Unit (ICU)</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Room Prefix *</label>
                <input
                  type="text"
                  value={batchRoomPrefix}
                  onChange={(e) => setBatchRoomPrefix(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                  placeholder="e.g. R-40"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Bed Prefix *</label>
                <input
                  type="text"
                  value={batchBedPrefix}
                  onChange={(e) => setBatchBedPrefix(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                  placeholder="e.g. ICU-"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Start Number *</label>
                <input
                  type="number"
                  min="1"
                  value={batchStartNum}
                  onChange={(e) => setBatchStartNum(Math.max(1, parseInt(e.target.value || "1", 10)))}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Number of Beds to Create *</label>
                <input
                  type="number"
                  min="1"
                  max="50"
                  value={batchCount}
                  onChange={(e) => setBatchCount(Math.min(50, Math.max(1, parseInt(e.target.value || "1", 10))))}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Daily Tariff (₹) *</label>
                <input
                  type="number"
                  value={batchTariff}
                  onChange={(e) => setBatchTariff(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                  placeholder="e.g. 5500"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Preview Sequencing</label>
                <div className="p-2 rounded bg-slate-950 border border-slate-800 text-xs font-mono text-emerald-400">
                  {batchBedPrefix}{batchStartNum.toString().padStart(2, "0")} → {batchBedPrefix}{(batchStartNum + batchCount - 1).toString().padStart(2, "0")} ({batchCount} beds)
                </div>
              </div>
            </div>

            <div>
              <label className="block text-[11px] text-slate-400 mb-1">Equipment &amp; Facilities (comma separated)</label>
              <input
                type="text"
                value={batchFeatures}
                onChange={(e) => setBatchFeatures(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                placeholder="e.g. Multi-Para Monitor, Ventilator Ready, O2 Wall Outlet"
              />
            </div>

            <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setBatchModalOpen(false)}
              >
                Cancel
              </Button>

              <Button
                variant="primary"
                size="sm"
                onClick={handleBatchAddBeds}
                className="flex items-center gap-1.5"
              >
                <Zap size={13} /> Provision {batchCount} Beds Now
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Emergency Code Drill Simulator Modal */}
      {drillModalOpen && (
        <Modal
          isOpen={drillModalOpen}
          onClose={() => setDrillModalOpen(false)}
          title="🚨 Statutory Hospital Emergency Code Drill & Roster Evaluator"
        >
          <div className="space-y-4 max-w-xl">
            <p className="text-xs text-slate-400">
              Log mandatory unannounced emergency code drills per NABH Standard FMS.4 and OSHA standards. Evaluates team response times and audit compliance.
            </p>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Emergency Code *</label>
                <select
                  value={selectedDrillCode}
                  onChange={(e) => setSelectedDrillCode(e.target.value as typeof selectedDrillCode)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-bold"
                >
                  <option value="CODE_RED">🔴 CODE RED (Fire / Smoke)</option>
                  <option value="CODE_BLUE">🔵 CODE BLUE (Cardiac Arrest)</option>
                  <option value="CODE_PINK">🌸 CODE PINK (Infant Abduction)</option>
                  <option value="CODE_ORANGE">🟠 CODE ORANGE (Mass Casualty / MCI)</option>
                  <option value="CODE_YELLOW">🟡 CODE YELLOW (Hazardous Spill)</option>
                  <option value="CODE_BLACK">⚫ CODE BLACK (Armed Threat / Bomb)</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Drill Staging Location *</label>
                <input
                  type="text"
                  value={drillLocation}
                  onChange={(e) => setDrillLocation(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
                  placeholder="e.g. Ward 3B Corridor, ICU Bay 2"
                />
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">Observed Response Time (Seconds) *</label>
                <input
                  type="number"
                  value={drillResponseSecs}
                  onChange={(e) => setDrillResponseSecs(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                  placeholder="e.g. 102"
                />
                <span className="text-[10px] text-slate-500 mt-0.5 block">
                  NABH Benchmark: Code Blue &lt; 180s, Code Red &lt; 120s
                </span>
              </div>

              <div>
                <label className="block text-[11px] text-slate-400 mb-1">First Responders Headcount *</label>
                <input
                  type="number"
                  value={drillStaffCount}
                  onChange={(e) => setDrillStaffCount(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200 font-mono"
                  placeholder="e.g. 14"
                />
              </div>
            </div>

            {/* Recent Drills History */}
            <div className="pt-2">
              <label className="block text-[11px] text-slate-400 uppercase font-mono mb-1.5">
                Recent Statutory Drill Logs ({recentDrills.length} on Record)
              </label>
              <div className="border border-slate-800 rounded-lg overflow-hidden bg-slate-950">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 text-[10px] uppercase bg-slate-900/60">
                      <th className="p-2">Code</th>
                      <th className="p-2">Location</th>
                      <th className="p-2">Date</th>
                      <th className="p-2">Response</th>
                      <th className="p-2">Verdict</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/40">
                    {recentDrills.map((d) => (
                      <tr key={d.id} className="text-slate-300">
                        <td className="p-2 font-bold text-sky-400">{d.code.replace("_", " ")}</td>
                        <td className="p-2">{d.location}</td>
                        <td className="p-2 text-slate-400">{d.date}</td>
                        <td className="p-2 text-emerald-400">{d.responseTime}</td>
                        <td className="p-2">
                          <Badge variant="success" size="sm">
                            {d.result}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrintEmergencyPlacard}
                className="flex items-center gap-1.5 text-xs text-amber-400 border-amber-500/40"
              >
                <Flame size={13} /> Print Wall Placard (CLINICAL_A4)
              </Button>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setDrillModalOpen(false)}
                >
                  Close
                </Button>

                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleRecordEmergencyDrill}
                  className="flex items-center gap-1.5"
                >
                  <CheckCircle2 size={13} /> Commit Drill to Statutory Log
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
