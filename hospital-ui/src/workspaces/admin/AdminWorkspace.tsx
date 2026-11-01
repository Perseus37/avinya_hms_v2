import React, { useEffect, useState } from "react";
import { registersApi } from "../../api/registersApi";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { Badge } from "../../components/ui/Badge";
import { WorkspaceId } from "../../types";
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
} from "lucide-react";

interface AdminWorkspaceProps {
  onSelectWorkspace?: (workspace: WorkspaceId) => void;
}

export const AdminWorkspace: React.FC<AdminWorkspaceProps> = ({ onSelectWorkspace }) => {

  const [inventory, setInventory] = useState<{
    tenant_id: number;
    total_hospital_records: number;
    timestamp_utc: string;
    tables: Record<string, number>;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Register Preview Modal
  const [activePreviewRegister, setActivePreviewRegister] = useState<{
    name: string;
    code: string;
    headers: string[];
    rows: string[][];
  } | null>(null);

  const loadDataInventory = async () => {
    setIsLoading(true);
    try {
      const data = await registersApi.getDataInventory();
      setInventory(data);
    } catch (err) {
      console.error("Failed to load data inventory:", err);
    } finally {
      setIsLoading(false);
    }
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
            Tenant ID: #{inventory?.tenant_id || 1} • Live Database Footprint & Statutory Regulatory Exports
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
            <span className="text-2xl font-bold font-mono text-slate-100">142</span>
            <span className="text-xs text-emerald-400 font-mono flex items-center">
              <TrendingUp size={12} className="mr-0.5" /> +12% vs avg
            </span>
          </div>
          <div className="text-[11px] text-slate-500 font-mono">General Med: 54 • Cardio: 38 • Ortho: 50</div>
        </Card>

        <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <BedDouble size={14} className="text-emerald-400" /> Bed Occupancy (BOR)
            </span>
            <Badge variant="success" size="sm">87.5%</Badge>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-slate-100">105 / 120</span>
            <span className="text-xs text-slate-400 font-mono">15 Available</span>
          </div>
          <div className="text-[11px] text-slate-500 font-mono">ICU: 92% • Semi-Private: 85% • Ward: 88%</div>
        </Card>

        <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1.5">
              <Siren size={14} className="text-rose-400" /> Emergency Trauma (ESI-1/2)
            </span>
            <Badge variant="danger" size="sm">Priority</Badge>
          </div>
          <div className="flex items-baseline justify-between">
            <span className="text-2xl font-bold font-mono text-rose-400">3 Cases</span>
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
            <span className="text-2xl font-bold font-mono text-emerald-400">₹3,48,650</span>
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

      {/* Statutory Hospital Operational Registers */}
      <div className="mt-8">
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
                  onClick={() =>
                    setActivePreviewRegister({
                      name: reg.name,
                      code: reg.code,
                      headers: reg.previewHeaders,
                      rows: reg.previewRows,
                    })
                  }
                  className="flex items-center gap-1.5 text-xs"
                >
                  <Eye size={13} /> Preview
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

      {/* Modal: Register Preview */}
      {activePreviewRegister && (
        <Modal
          isOpen={true}
          onClose={() => setActivePreviewRegister(null)}
          title={`Register Stream Preview — ${activePreviewRegister.name} (${activePreviewRegister.code})`}
        >
          <div className="space-y-4">
            <div className="text-xs text-slate-400">
              Live schema sample formatted under RFC 4180 with UTF-8 BOM encoding:
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

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
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
