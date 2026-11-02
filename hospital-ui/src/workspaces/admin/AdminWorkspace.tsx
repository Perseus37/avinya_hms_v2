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
import { useHospitalConfig, WristbandPreset, ThermalRollWidth } from "../../core/context/HospitalConfigContext";
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
} from "lucide-react";

interface AdminWorkspaceProps {
  onSelectWorkspace?: (workspace: WorkspaceId) => void;
}

export const AdminWorkspace: React.FC<AdminWorkspaceProps> = ({ onSelectWorkspace }) => {
  const [activeTab, setActiveTab] = useState<"overview" | "metrics" | "registers" | "customization">("overview");
  const [customSubTab, setCustomSubTab] = useState<"facility" | "doctors" | "branding" | "policies" | "printTemplates">("facility");
  const [activeDocTemplate, setActiveDocTemplate] = useState<"thermal" | "wristband" | "bht" | "discharge">("thermal");

  const {
    hospitalProfile,
    policies,
    doctors,
    beds,
    printTemplates,
    updateHospitalProfile,
    updatePolicies,
    updatePrintTemplates,
    addBed,
    deleteBed,
    addDoctor,
    deleteDoctor,
    resetToDefaultCatalog,
  } = useHospitalConfig();

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
                  {bedSuccessMsg && (
                    <span className="text-xs text-emerald-400 font-mono flex items-center gap-1">
                      <CheckCircle2 size={12} /> {bedSuccessMsg}
                    </span>
                  )}
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
        </div>
      )}

      {/* Modal: Register Preview */}
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
    </div>
  );
};
