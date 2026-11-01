import React, { useEffect, useState } from "react";
import { registersApi } from "../../api/registersApi";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Database, Download, FileText, ShieldCheck, RefreshCw, Layers } from "lucide-react";

export const AdminWorkspace: React.FC = () => {
  const [inventory, setInventory] = useState<{
    tenant_id: number;
    total_hospital_records: number;
    timestamp_utc: string;
    tables: Record<string, number>;
  } | null>(null);
  const [isLoading, setIsLoading] = useState(false);

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
    },
    {
      name: "Cashier Shift Handover & Reconciliation Ledger",
      code: "CASHIER-RECON",
      description: "Counter collections by tender (Cash, UPI, Card, NetBanking), shift variances.",
      endpoint: "/api/registers/cashier-shift-reconciliation?format=csv",
      format: "RFC 4180 CSV (BOM)",
    },
    {
      name: "NDPS Schedule H1 Narcotics Controlled Substances Register",
      code: "NDPS-LEDGER",
      description: "Perpetual double-custody ledger with batch numbers, movements, and witness sign-offs.",
      endpoint: "/api/registers/ndps-ledger?format=csv",
      format: "RFC 4180 CSV (BOM)",
    },
    {
      name: "Accounts Receivable (AR) Aging Ledger",
      code: "AR-AGING",
      description: "Outstanding dues bucketed into 0-30, 31-60, 61-90, and >90 days by TPA and Self-Pay.",
      endpoint: "/api/registers/ar-aging?format=csv",
      format: "RFC 4180 CSV (BOM)",
    },
    {
      name: "Bio-Medical Waste (BMW) Management Statutory Register",
      code: "BMW-REGISTER",
      description: "CPCB/SPCB daily color-coded manifests (Yellow, Red, White, Blue) in kg.",
      endpoint: "/api/registers/biomedical-waste?format=csv",
      format: "RFC 4180 CSV (BOM)",
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
      <div className="mt-10">
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

              <div className="flex items-center gap-3">
                <span className="text-[11px] font-mono text-slate-500">{reg.format}</span>
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
    </div>
  );
};

