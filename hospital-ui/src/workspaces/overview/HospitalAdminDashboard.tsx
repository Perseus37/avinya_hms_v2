import React from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BedDouble,
  CalendarDays,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  Download,
  FlaskConical,
  LayoutDashboard,
  RefreshCw,
  Siren,
  Users,
  WalletCards,
} from "lucide-react";

interface MetricProps {
  label: string;
  value: string;
  detail: string;
  trend?: string;
  direction?: "up" | "down" | "neutral";
  icon: React.ReactNode;
  tone?: "default" | "positive" | "warning" | "critical";
}

const metrics: MetricProps[] = [
  { label: "Patients today", value: "486", detail: "vs 452 yesterday", trend: "+7.5%", direction: "up", icon: <Users size={18} />, tone: "default" },
  { label: "OPD visits", value: "312", detail: "268 completed", trend: "+9.2%", direction: "up", icon: <Activity size={18} />, tone: "positive" },
  { label: "Admissions", value: "34", detail: "11 pending bed", trend: "+3", direction: "up", icon: <BedDouble size={18} />, tone: "default" },
  { label: "Occupancy", value: "82%", detail: "41 beds available", trend: "-2.0%", direction: "down", icon: <BedDouble size={18} />, tone: "warning" },
  { label: "Revenue", value: "₹18.6L", detail: "today · ₹22.4L target", trend: "83%", direction: "neutral", icon: <CircleDollarSign size={18} />, tone: "default" },
  { label: "Collections", value: "₹14.8L", detail: "79.6% of revenue", trend: "+5.4%", direction: "up", icon: <WalletCards size={18} />, tone: "positive" },
  { label: "Outstanding", value: "₹6.2L", detail: "₹1.4L overdue", trend: "-3.1%", direction: "down", icon: <CircleDollarSign size={18} />, tone: "positive" },
  { label: "OPD wait P90", value: "42 min", detail: "target ≤ 30 min", trend: "+12 min", direction: "up", icon: <Clock3 size={18} />, tone: "critical" },
];

const exceptions = [
  { severity: "critical", title: "OPD wait SLA breached", detail: "24 patients waiting over 45 minutes", action: "Open OPD queue" },
  { severity: "critical", title: "ED capacity pressure", detail: "3 ESI-2 patients awaiting monitored beds", action: "Open emergency" },
  { severity: "warning", title: "Pending discharges", detail: "8 patients clinically ready; 5 blocked by billing", action: "Review discharges" },
  { severity: "warning", title: "Critical lab results", detail: "4 results awaiting clinician acknowledgement", action: "Review diagnostics" },
  { severity: "warning", title: "Pharmacy stock-out risk", detail: "7 high-volume medicines below reorder level", action: "Open inventory" },
];

const branches = [
  { name: "Main Campus", patients: 286, occupancy: 86, revenue: "₹11.4L", wait: "38m", status: "Watch" },
  { name: "North Branch", patients: 121, occupancy: 78, revenue: "₹4.6L", wait: "26m", status: "Healthy" },
  { name: "South Branch", patients: 79, occupancy: 74, revenue: "₹2.6L", wait: "31m", status: "Watch" },
];

const flow = [
  ["Registration", 486],
  ["Payment", 452],
  ["Token", 431],
  ["Waiting", 318],
  ["Consultation", 268],
  ["Diagnostics", 146],
  ["Pharmacy / Billing", 109],
] as const;

const trend = [72, 88, 81, 103, 96, 117, 126, 119, 137, 131, 148, 156, 162, 171];

function MetricCard({ label, value, detail, trend: trendValue, direction, icon, tone = "default" }: MetricProps) {
  const toneClass = {
    default: "bg-white border-slate-200 text-slate-900",
    positive: "bg-white border-emerald-200 text-slate-900",
    warning: "bg-white border-amber-200 text-slate-900",
    critical: "bg-white border-red-200 text-slate-900",
  }[tone];

  return (
    <article className={`rounded-xl border p-4 shadow-[0_1px_2px_rgba(15,23,42,0.03)] ${toneClass}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">{label}</p>
          <p className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</p>
        </div>
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${tone === "critical" ? "bg-red-50 text-red-600" : tone === "warning" ? "bg-amber-50 text-amber-600" : tone === "positive" ? "bg-emerald-50 text-emerald-600" : "bg-slate-100 text-slate-600"}`}>
          {icon}
        </span>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2 text-[11px]">
        <span className="truncate text-slate-500">{detail}</span>
        {trendValue && (
          <span className={`inline-flex items-center gap-0.5 font-medium ${direction === "up" ? tone === "critical" ? "text-red-600" : "text-emerald-600" : direction === "down" ? "text-emerald-600" : "text-slate-500"}`}>
            {direction === "up" ? <ArrowUpRight size={12} /> : direction === "down" ? <ArrowDownRight size={12} /> : null}
            {trendValue}
          </span>
        )}
      </div>
    </article>
  );
}

function Panel({ title, subtitle, action, children, className = "" }: { title: string; subtitle?: string; action?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`rounded-xl border border-slate-200 bg-white shadow-[0_1px_2px_rgba(15,23,42,0.03)] ${className}`}>
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>}
        </div>
        {action && <button className="inline-flex items-center gap-1 text-xs font-medium text-slate-600 hover:text-slate-950">{action}<ChevronRight size={13} /></button>}
      </div>
      {children}
    </section>
  );
}

function TrendChart() {
  const width = 720;
  const height = 190;
  const max = Math.max(...trend) + 10;
  const min = Math.min(...trend) - 10;
  const points = trend.map((value, index) => {
    const x = (index / (trend.length - 1)) * width;
    const y = height - ((value - min) / (max - min)) * height;
    return `${x},${y}`;
  }).join(" ");

  return (
    <div className="px-5 pb-5 pt-4">
      <div className="relative h-[190px] overflow-hidden rounded-lg bg-slate-50">
        {[0, 1, 2, 3].map((line) => <div key={line} className="absolute inset-x-0 border-t border-slate-200" style={{ top: `${line * 33.33}%` }} />)}
        <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
          <polyline points={points} fill="none" stroke="currentColor" strokeWidth="3" vectorEffect="non-scaling-stroke" className="text-slate-700" />
          {trend.map((value, index) => {
            const x = (index / (trend.length - 1)) * width;
            const y = height - ((value - min) / (max - min)) * height;
            return <circle key={index} cx={x} cy={y} r="4" className="fill-white stroke-slate-700" strokeWidth="2" vectorEffect="non-scaling-stroke" />;
          })}
        </svg>
        <div className="absolute bottom-2 left-3 right-3 flex justify-between text-[10px] text-slate-400"><span>08:00</span><span>10:00</span><span>12:00</span><span>14:00</span><span>16:00</span><span>18:00</span></div>
      </div>
      <div className="mt-3 flex items-center justify-between text-xs">
        <span className="text-slate-500">Patient arrivals per 30 minutes</span>
        <span className="font-medium text-slate-700">Peak: 171 · 17:30</span>
      </div>
    </div>
  );
}

export const HospitalAdminDashboard: React.FC = () => {
  const [range, setRange] = React.useState<"Today" | "7 days" | "30 days">("Today");
  const [lastRefresh, setLastRefresh] = React.useState("Just now");

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col overflow-hidden bg-[#f5f7fa]">
      <header className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-slate-500"><LayoutDashboard size={14} /> Operations overview</div>
            <h1 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">Hospital Administrator</h1>
            <p className="mt-0.5 text-xs text-slate-500">Main Campus · Monday, 2 November 2026 · Live operational view</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex rounded-lg border border-slate-200 bg-slate-50 p-0.5">
              {(["Today", "7 days", "30 days"] as const).map((item) => <button key={item} onClick={() => setRange(item)} className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${range === item ? "bg-white text-slate-900 shadow-sm" : "text-slate-500 hover:text-slate-900"}`}>{item}</button>)}
            </div>
            <button onClick={() => setLastRefresh("Just now")} className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 hover:bg-slate-50"><RefreshCw size={14} /> Refresh</button>
            <button className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-medium text-slate-600 hover:bg-slate-50"><Download size={14} /> Export</button>
          </div>
        </div>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        <div className="mx-auto max-w-[1600px] space-y-5">
          <div className="flex items-center justify-between">
            <p className="text-xs text-slate-500">Updated {lastRefresh} · Data window: {range}</p>
            <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-emerald-700"><span className="h-1.5 w-1.5 rounded-full bg-emerald-500" /> Systems operational</span>
          </div>

          <div className="grid grid-cols-2 gap-3 xl:grid-cols-4 2xl:grid-cols-8">
            {metrics.map((metric) => <MetricCard key={metric.label} {...metric} />)}
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
            <Panel title="Operational exceptions" subtitle="Issues that need an owner or decision now" action="View all">
              <div className="divide-y divide-slate-100">
                {exceptions.map((item) => <button key={item.title} className="flex w-full items-center gap-3 px-5 py-3 text-left hover:bg-slate-50">
                  <span className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full ${item.severity === "critical" ? "bg-red-50 text-red-600" : "bg-amber-50 text-amber-600"}`}><AlertTriangle size={16} /></span>
                  <span className="min-w-0 flex-1"><span className="block text-xs font-semibold text-slate-800">{item.title}</span><span className="mt-0.5 block text-[11px] text-slate-500">{item.detail}</span></span>
                  <span className="hidden text-[11px] font-medium text-slate-500 sm:block">{item.action}</span><ChevronRight size={15} className="text-slate-400" />
                </button>)}
              </div>
            </Panel>

            <Panel title="Bed capacity" subtitle="Current inpatient capacity" action="Open bed matrix">
              <div className="p-5">
                <div className="flex items-end justify-between"><div><p className="text-3xl font-semibold tracking-tight text-slate-950">82%</p><p className="mt-1 text-xs text-slate-500">318 / 389 beds occupied</p></div><span className="rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-semibold text-amber-700">Watch</span></div>
                <div className="mt-5 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full w-[82%] rounded-full bg-slate-700" /></div>
                <div className="mt-4 grid grid-cols-3 gap-3 text-center"><div><p className="text-sm font-semibold text-slate-900">41</p><p className="text-[10px] text-slate-500">Available</p></div><div><p className="text-sm font-semibold text-amber-700">18</p><p className="text-[10px] text-slate-500">Cleaning</p></div><div><p className="text-sm font-semibold text-slate-900">12</p><p className="text-[10px] text-slate-500">Reserved</p></div></div>
                <div className="mt-5 rounded-lg bg-slate-50 p-3"><div className="flex items-center gap-2 text-xs font-medium text-slate-700"><BedDouble size={14} /> ICU capacity</div><div className="mt-2 flex items-center justify-between text-[11px]"><span className="text-slate-500">31 / 36 occupied</span><span className="font-semibold text-red-600">86%</span></div></div>
              </div>
            </Panel>
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.35fr_0.65fr]">
            <Panel title="Patient flow" subtitle="Where today's patients are in the journey">
              <div className="space-y-4 p-5">
                {flow.map(([label, value], index) => <div key={label} className="flex items-center gap-3"><div className="w-32 shrink-0 text-xs text-slate-600">{label}</div><div className="h-7 flex-1 overflow-hidden rounded-md bg-slate-100"><div className="flex h-full items-center rounded-md bg-slate-700 px-2 text-[10px] font-medium text-white" style={{ width: `${Math.max(22, (value / 486) * 100)}%` }}>{value}</div></div><div className="w-10 text-right text-xs font-semibold text-slate-700">{value}</div>{index < flow.length - 1 && <span className="hidden text-[10px] text-slate-400 2xl:block">{Math.round((flow[index + 1][1] / value) * 100)}%</span>}</div>)}
              </div>
            </Panel>

            <Panel title="Department pressure" subtitle="Current operational load">
              <div className="p-5 space-y-4">
                {[['OPD', 78, '312 patients'], ['Emergency', 91, '23 active'], ['Diagnostics', 64, '146 orders'], ['Pharmacy', 72, '109 pending']].map(([name, percent, detail]) => <div key={String(name)}><div className="mb-1.5 flex items-center justify-between text-xs"><span className="font-medium text-slate-700">{name}</span><span className="text-slate-500">{detail}</span></div><div className="h-2 rounded-full bg-slate-100"><div className={`h-full rounded-full ${Number(percent) >= 85 ? 'bg-red-500' : Number(percent) >= 75 ? 'bg-amber-500' : 'bg-slate-600'}`} style={{ width: `${percent}%` }} /></div></div>)}
              </div>
            </Panel>
          </div>

          <div className="grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
            <Panel title="Patient volume trend" subtitle="Arrivals through the day" action="Open analytics">
              <TrendChart />
            </Panel>
            <Panel title="Branch performance" subtitle="Today across active branches" action="Compare branches">
              <div className="overflow-x-auto"><table className="w-full text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3 font-medium">Branch</th><th className="px-3 py-3 font-medium">Patients</th><th className="px-3 py-3 font-medium">Occupancy</th><th className="px-3 py-3 font-medium">Revenue</th><th className="px-3 py-3 font-medium">Wait</th></tr></thead><tbody className="divide-y divide-slate-100">{branches.map((branch) => <tr key={branch.name} className="hover:bg-slate-50"><td className="px-5 py-3.5"><div className="font-medium text-slate-800">{branch.name}</div><div className={`mt-0.5 text-[10px] ${branch.status === 'Healthy' ? 'text-emerald-600' : 'text-amber-600'}`}>{branch.status}</div></td><td className="px-3 py-3.5 text-slate-700">{branch.patients}</td><td className="px-3 py-3.5 text-slate-700">{branch.occupancy}%</td><td className="px-3 py-3.5 font-medium text-slate-800">{branch.revenue}</td><td className={`px-3 py-3.5 font-medium ${branch.wait === '38m' ? 'text-amber-600' : 'text-slate-700'}`}>{branch.wait}</td></tr>)}</tbody></table></div>
            </Panel>
          </div>

          <div className="grid gap-5 md:grid-cols-3">
            <button className="group rounded-xl border border-slate-200 bg-white p-4 text-left shadow-[0_1px_2px_rgba(15,23,42,0.03)] hover:border-slate-300"><div className="flex items-center justify-between"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-600"><CalendarDays size={17} /></span><ChevronRight size={15} className="text-slate-400 transition group-hover:translate-x-0.5" /></div><p className="mt-3 text-sm font-semibold text-slate-800">Patient flow workspace</p><p className="mt-1 text-xs text-slate-500">Registration, OPD queue, admissions and discharge bottlenecks.</p></button>
            <button className="group rounded-xl border border-slate-200 bg-white p-4 text-left shadow-[0_1px_2px_rgba(15,23,42,0.03)] hover:border-slate-300"><div className="flex items-center justify-between"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-600"><FlaskConical size={17} /></span><ChevronRight size={15} className="text-slate-400 transition group-hover:translate-x-0.5" /></div><p className="mt-3 text-sm font-semibold text-slate-800">Clinical exceptions</p><p className="mt-1 text-xs text-slate-500">Critical results, safety events and unresolved clinical work.</p></button>
            <button className="group rounded-xl border border-slate-200 bg-white p-4 text-left shadow-[0_1px_2px_rgba(15,23,42,0.03)] hover:border-slate-300"><div className="flex items-center justify-between"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-100 text-slate-600"><Siren size={17} /></span><ChevronRight size={15} className="text-slate-400 transition group-hover:translate-x-0.5" /></div><p className="mt-3 text-sm font-semibold text-slate-800">Emergency command view</p><p className="mt-1 text-xs text-slate-500">ED acuity, monitored beds, waiting patients and escalation.</p></button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HospitalAdminDashboard;
