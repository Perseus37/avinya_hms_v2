import React, { useState } from "react";
import { Card } from "../ui/Card";
import { Badge } from "../ui/Badge";
import {
  TrendingUp,
  BedDouble,
  CreditCard,
  Siren,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Layers,
} from "lucide-react";

interface OperationalTrendsDashboardProps {
  totalBeds?: number;
  occupiedBeds?: number;
  totalCollectionsPaise?: number;
}

export const OperationalTrendsDashboard: React.FC<OperationalTrendsDashboardProps> = ({
  totalBeds = 120,
  occupiedBeds = 105,
  totalCollectionsPaise = 34865000,
}) => {
  const [selectedDayIndex, setSelectedDayIndex] = useState<number>(6); // Default: Today

  // 7-day trend sample data
  const trendData = [
    { day: "Mon", date: "Oct 26", opd: 118, ipd: 12, er: 18, total: 148 },
    { day: "Tue", date: "Oct 27", opd: 135, ipd: 16, er: 22, total: 173 },
    { day: "Wed", date: "Oct 28", opd: 124, ipd: 14, er: 19, total: 157 },
    { day: "Thu", date: "Oct 29", opd: 142, ipd: 18, er: 25, total: 185 },
    { day: "Fri", date: "Oct 30", opd: 139, ipd: 15, er: 21, total: 175 },
    { day: "Sat", date: "Oct 31", opd: 128, ipd: 11, er: 27, total: 166 },
    { day: "Sun (Today)", date: "Nov 01", opd: 142, ipd: 17, er: 24, total: 183 },
  ];

  const maxVolume = Math.max(...trendData.map((d) => d.total));
  const activeDay = trendData[selectedDayIndex];

  // Ward Occupancy Breakdown
  const wardBreakdown = [
    { name: "Intensive Care Unit (ICU)", occupied: 18, total: 20, pct: 90, status: "critical" },
    { name: "High Dependency Unit (HDU)", occupied: 14, total: 15, pct: 93.3, status: "critical" },
    { name: "General Medical & Surgical Ward", occupied: 42, total: 50, pct: 84, status: "optimal" },
    { name: "Emergency & Trauma Observation", occupied: 9, total: 12, pct: 75, status: "optimal" },
    { name: "Maternity & Neonatal Wing", occupied: 14, total: 15, pct: 93.3, status: "critical" },
    { name: "Day Care & Short Stay", occupied: 8, total: 10, pct: 80, status: "optimal" },
  ];

  // Revenue Collection Split
  const totalRupees = totalCollectionsPaise / 100;
  const paymentBreakdown = [
    { method: "UPI Instant QR", pct: 48, amount: totalRupees * 0.48, color: "bg-emerald-500", text: "text-emerald-400" },
    { method: "Credit / Debit POS", pct: 32, amount: totalRupees * 0.32, color: "bg-sky-500", text: "text-sky-400" },
    { method: "Cash Desk Settlement", pct: 15, amount: totalRupees * 0.15, color: "bg-amber-500", text: "text-amber-400" },
    { method: "TPA / Insurance Pre-Auth", pct: 5, amount: totalRupees * 0.05, color: "bg-purple-500", text: "text-purple-400" },
  ];

  // Emergency Triage Acuity Funnel
  const triageAcuity = [
    { level: "ESI-1", label: "Resuscitation / Immediate", count: 2, avgTriage: "0m", color: "bg-rose-500 text-rose-100" },
    { level: "ESI-2", label: "Emergent (High Risk)", count: 7, avgTriage: "3.5m", color: "bg-amber-500 text-amber-950" },
    { level: "ESI-3", label: "Urgent (Multi-Resource)", count: 19, avgTriage: "12m", color: "bg-yellow-500 text-yellow-950" },
    { level: "ESI-4", label: "Less Urgent (Single-Resource)", count: 12, avgTriage: "24m", color: "bg-sky-500 text-sky-950" },
    { level: "ESI-5", label: "Non-Urgent (No-Resource)", count: 4, avgTriage: "38m", color: "bg-slate-600 text-slate-100" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
            <TrendingUp size={16} className="text-sky-400" />
            Operational Velocity &amp; Departmental Saturation Trends
          </h2>
          <p className="text-xs text-slate-400 mt-0.5 font-mono">
            7-Day Footfall Trends • Ward Occupancy Saturation • Payment Reconciliation Mix • ESI Triage Funnel
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs font-mono text-slate-400 bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-md">
          <Calendar size={13} className="text-sky-400" />
          <span>Rolling 7-Day Window</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 1. 7-Day Patient Volume & Footfall Trend */}
        <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Layers size={14} className="text-sky-400" /> 7-Day Patient Volume Trend
              </span>
              <div className="flex items-center gap-3 text-[11px] font-mono">
                <span className="flex items-center gap-1 text-sky-400">
                  <span className="w-2 h-2 rounded-full bg-sky-400 inline-block" /> OPD
                </span>
                <span className="flex items-center gap-1 text-emerald-400">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" /> IPD
                </span>
                <span className="flex items-center gap-1 text-rose-400">
                  <span className="w-2 h-2 rounded-full bg-rose-400 inline-block" /> ER
                </span>
              </div>
            </div>

            {/* Interactive Bar Chart Canvas */}
            <div className="pt-4 pb-2 border-b border-slate-800/80">
              <div className="h-40 flex items-end justify-between gap-2 px-2">
                {trendData.map((d, idx) => {
                  const isSelected = selectedDayIndex === idx;
                  const totalHeightPct = Math.round((d.total / maxVolume) * 100);
                  const opdHeightPct = Math.round((d.opd / d.total) * totalHeightPct);
                  const ipdHeightPct = Math.round((d.ipd / d.total) * totalHeightPct);
                  const erHeightPct = totalHeightPct - opdHeightPct - ipdHeightPct;

                  return (
                    <button
                      key={d.day}
                      type="button"
                      onClick={() => setSelectedDayIndex(idx)}
                      className={`flex-1 flex flex-col items-center h-full justify-end group transition-all rounded p-1 ${
                        isSelected ? "bg-slate-800/80 ring-1 ring-sky-500" : "hover:bg-slate-800/40"
                      }`}
                    >
                      <span className="text-[10px] font-mono text-slate-400 mb-1 group-hover:text-slate-200">
                        {d.total}
                      </span>
                      <div className="w-full flex flex-col items-center rounded overflow-hidden max-w-[28px]">
                        <div
                          style={{ height: `${erHeightPct}%` }}
                          className="w-full bg-rose-500 hover:brightness-110"
                          title={`ER: ${d.er}`}
                        />
                        <div
                          style={{ height: `${ipdHeightPct}%` }}
                          className="w-full bg-emerald-500 hover:brightness-110"
                          title={`IPD Admissions: ${d.ipd}`}
                        />
                        <div
                          style={{ height: `${opdHeightPct}%` }}
                          className="w-full bg-sky-500 hover:brightness-110"
                          title={`OPD Visits: ${d.opd}`}
                        />
                      </div>
                      <span className={`text-[10px] mt-2 font-mono ${isSelected ? "text-sky-400 font-bold" : "text-slate-400"}`}>
                        {d.day.split(" ")[0]}
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Selected Day Breakdown Pill */}
          <div className="bg-slate-950/60 rounded-lg p-2.5 border border-slate-800 flex items-center justify-between text-xs font-mono">
            <span className="text-slate-300 font-semibold">
              {activeDay.day} ({activeDay.date}):
            </span>
            <div className="flex items-center gap-4">
              <span className="text-sky-400 font-semibold">{activeDay.opd} OPD</span>
              <span className="text-emerald-400 font-semibold">{activeDay.ipd} IPD Admissions</span>
              <span className="text-rose-400 font-semibold">{activeDay.er} ER Trauma</span>
              <span className="text-slate-100 font-bold bg-slate-800 px-2 py-0.5 rounded">
                Total: {activeDay.total}
              </span>
            </div>
          </div>
        </Card>

        {/* 2. Ward Capacity Saturation & Occupancy Distribution */}
        <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <BedDouble size={14} className="text-emerald-400" /> Ward Saturation Breakdown
            </span>
            <div className="flex items-center gap-2">
              <Badge variant="success" size="sm">
                Overall: {((occupiedBeds / totalBeds) * 100).toFixed(1)}% BOR
              </Badge>
              <span className="text-[10px] font-mono text-slate-400">Target: 85%</span>
            </div>
          </div>

          <div className="space-y-2.5 pt-1">
            {wardBreakdown.map((w) => {
              const isCritical = w.pct >= 90;
              return (
                <div key={w.name} className="space-y-1">
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-slate-300 font-medium truncate max-w-[260px]">{w.name}</span>
                    <div className="flex items-center gap-2 font-mono text-[11px]">
                      <span className="text-slate-400">
                        {w.occupied}/{w.total} Beds
                      </span>
                      <span className={`font-bold ${isCritical ? "text-amber-400" : "text-emerald-400"}`}>
                        {w.pct.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <div className="h-2 w-full bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                    <div
                      style={{ width: `${w.pct}%` }}
                      className={`h-full rounded-full transition-all ${
                        isCritical ? "bg-amber-500" : "bg-emerald-500"
                      }`}
                    />
                  </div>
                </div>
              );
            })}
          </div>

          <div className="flex items-center justify-between text-[11px] text-slate-500 font-mono pt-1 border-t border-slate-800/80">
            <span className="flex items-center gap-1">
              <CheckCircle2 size={12} className="text-emerald-400" /> Optimal Bed Flow: &lt; 85%
            </span>
            <span className="flex items-center gap-1 text-amber-400">
              <AlertTriangle size={12} /> Critical Saturation: &ge; 90%
            </span>
          </div>
        </Card>

        {/* 3. Revenue Cycle & Settlement Tender Mix */}
        <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <CreditCard size={14} className="text-amber-400" /> Revenue Collection Tender Split
            </span>
            <Badge variant="warning" size="sm">Audited Gross</Badge>
          </div>

          {/* Segmented Progress Bar */}
          <div>
            <div className="h-4 w-full bg-slate-950 rounded-lg overflow-hidden flex border border-slate-800">
              {paymentBreakdown.map((item) => (
                <div
                  key={item.method}
                  style={{ width: `${item.pct}%` }}
                  className={`h-full ${item.color} transition-all`}
                  title={`${item.method}: ${item.pct}%`}
                />
              ))}
            </div>

            <div className="grid grid-cols-2 gap-3 mt-3">
              {paymentBreakdown.map((item) => (
                <div key={item.method} className="bg-slate-950/60 p-2 rounded-lg border border-slate-800/80">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400 text-[11px] truncate">{item.method}</span>
                    <span className={`font-mono font-bold ${item.text}`}>{item.pct}%</span>
                  </div>
                  <div className="text-sm font-bold font-mono text-slate-100 mt-0.5">
                    ₹{item.amount.toLocaleString("en-IN", { maximumFractionDigits: 0 })}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between text-[11px] font-mono text-slate-400 pt-1 border-t border-slate-800/80">
            <span>AR Days: <strong className="text-emerald-400">18.4d</strong> (Bench: &lt;30d)</span>
            <span>Clean Claim Rate: <strong className="text-sky-400">98.2%</strong></span>
          </div>
        </Card>

        {/* 4. ED Triage Acuity & Door-to-Doctor Velocity */}
        <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Siren size={14} className="text-rose-400" /> Emergency Triage Acuity Funnel
            </span>
            <div className="flex items-center gap-1.5 text-xs font-mono text-slate-400">
              <Clock size={12} className="text-rose-400" />
              <span>Avg ED LOS: <strong>142m</strong></span>
            </div>
          </div>

          <div className="space-y-2 pt-1">
            {triageAcuity.map((t) => (
              <div key={t.level} className="flex items-center justify-between p-2 rounded-lg bg-slate-950/60 border border-slate-800/80 text-xs font-mono">
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${t.color}`}>
                    {t.level}
                  </span>
                  <span className="text-slate-300 text-[11px]">{t.label}</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-slate-400 text-[11px]">Door-to-Doc: {t.avgTriage}</span>
                  <span className="font-bold text-slate-100 bg-slate-800 px-2 py-0.5 rounded text-[11px]">
                    {t.count} Cases
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="text-[11px] text-slate-500 font-mono text-center pt-1 border-t border-slate-800/80">
            Trauma Fast-Track SLA: Resuscitation (0m) • STEMI (Door-to-Balloon &lt; 90m)
          </div>
        </Card>
      </div>
    </div>
  );
};

