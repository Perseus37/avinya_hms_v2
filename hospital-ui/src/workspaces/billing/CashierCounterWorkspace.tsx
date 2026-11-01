import React, { useEffect, useState } from "react";
import { uiApi } from "../../api/uiApi";
import { CashierShiftStatus } from "../../types";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Modal } from "../../components/ui/Modal";
import { Badge } from "../../components/ui/Badge";
import {
  CreditCard,
  DollarSign,
  Receipt,
  Lock,
  Unlock,
  Download,
  RefreshCw,
  Printer,
  PlusCircle,
  Trash2,
  QrCode,
  ShieldCheck,
} from "lucide-react";
import { useActivePatient } from "../../core/context/ActivePatientContext";

interface BillItem {
  id: string;
  description: string;
  category: "Consultation" | "Bed Charge" | "Diagnostics" | "Pharmacy" | "Procedure";
  unitPrice: number;
  quantity: number;
  gstRate: number; // e.g. 0, 5, 12, 18
}

export const CashierCounterWorkspace: React.FC = () => {
  const { patientSummary } = useActivePatient();
  const [shift, setShift] = useState<CashierShiftStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpenModalActive, setIsOpenModalActive] = useState(false);
  const [isCloseModalActive, setIsCloseModalActive] = useState(false);

  // Shift Management Form State
  const [counterId, setCounterId] = useState("COUNTER-MAIN-01");
  const [startingFloatRupees, setStartingFloatRupees] = useState("5000");
  const [physicalCashRupees, setPhysicalCashRupees] = useState("");
  const [handoverNotes, setHandoverNotes] = useState("");

  // Charge Entry & Bill Items State
  const [billItems, setBillItems] = useState<BillItem[]>([
    {
      id: "item-1",
      description: "Specialist OPD Consultation — Cardiology",
      category: "Consultation",
      unitPrice: 1200,
      quantity: 1,
      gstRate: 0,
    },
    {
      id: "item-2",
      description: "Complete Blood Count (CBC) with Differential",
      category: "Diagnostics",
      unitPrice: 650,
      quantity: 1,
      gstRate: 0,
    },
    {
      id: "item-3",
      description: "ECG 12-Lead Rhythm Strip",
      category: "Diagnostics",
      unitPrice: 450,
      quantity: 1,
      gstRate: 0,
    },
    {
      id: "item-4",
      description: "Paracetamol 650mg + Cetirizine 10mg (Dispensary)",
      category: "Pharmacy",
      unitPrice: 180,
      quantity: 1,
      gstRate: 12,
    },
  ]);

  // Add Item Modal
  const [isAddItemModalOpen, setIsAddItemModalOpen] = useState(false);
  const [newItemDesc, setNewItemDesc] = useState("Chest X-Ray PA View");
  const [newItemCategory, setNewItemCategory] = useState<"Consultation" | "Bed Charge" | "Diagnostics" | "Pharmacy" | "Procedure">("Diagnostics");
  const [newItemPrice, setNewItemPrice] = useState("850");
  const [newItemQty, setNewItemQty] = useState("1");
  const [folioFilter, setFolioFilter] = useState<"ALL" | "Consultation" | "Bed Charge" | "Diagnostics" | "Pharmacy" | "Procedure">("ALL");

  // Payment Settlement State
  const [isSettlementModalOpen, setIsSettlementModalOpen] = useState(false);
  const [isInvoicePrintModalOpen, setIsInvoicePrintModalOpen] = useState(false);
  const [cashTendered, setCashTendered] = useState("0");
  const [upiTendered, setUpiTendered] = useState("0");
  const [cardTendered, setCardTendered] = useState("0");
  const [tpaClaimTendered, setTpaClaimTendered] = useState("0");
  const [isUpiQrVisible, setIsUpiQrVisible] = useState(false);
  const [lastSettledInvoice, setLastSettledInvoice] = useState<{
    invoiceNumber: string;
    patientName: string;
    mrn: string;
    totalAmount: number;
    paidAmount: number;
    breakdown: Record<string, number>;
  } | null>(null);

  const calculateSubtotal = () => {
    return billItems.reduce((acc, item) => acc + item.unitPrice * item.quantity, 0);
  };

  const calculateGst = () => {
    return billItems.reduce(
      (acc, item) => acc + (item.unitPrice * item.quantity * item.gstRate) / 100,
      0
    );
  };

  const totalBillAmount = calculateSubtotal() + calculateGst();

  const totalTendered =
    (parseFloat(cashTendered) || 0) +
    (parseFloat(upiTendered) || 0) +
    (parseFloat(cardTendered) || 0) +
    (parseFloat(tpaClaimTendered) || 0);

  const remainingBalance = Math.max(0, totalBillAmount - totalTendered);
  const changeDue = Math.max(0, totalTendered - totalBillAmount);

  const loadShift = async () => {
    setIsLoading(true);
    try {
      const data = await uiApi.getCashierShiftStatus();
      setShift(data);
    } catch (err) {
      console.error("Failed to load shift status:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadShift();
  }, []);

  const handleOpenShift = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const floatPaise = Math.round(parseFloat(startingFloatRupees || "0") * 100);
      await uiApi.openCashierShift(counterId, floatPaise);
      setIsOpenModalActive(false);
      await loadShift();
    } catch (err) {
      alert(`Failed to open shift: ${err}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCloseShift = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    try {
      const cashPaise = Math.round(parseFloat(physicalCashRupees || "0") * 100);
      await uiApi.closeCashierShift(cashPaise, handoverNotes);
      setIsCloseModalActive(false);
      await loadShift();
      alert("Shift successfully closed & reconciled.");
    } catch (err) {
      alert(`Failed to close shift: ${err}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddBillItem = (e: React.FormEvent) => {
    e.preventDefault();
    const price = parseFloat(newItemPrice) || 0;
    const qty = parseInt(newItemQty, 10) || 1;
    const newItem: BillItem = {
      id: `item-${Date.now()}`,
      description: newItemDesc,
      category: newItemCategory,
      unitPrice: price,
      quantity: qty,
      gstRate: newItemCategory === "Pharmacy" ? 12 : 0,
    };
    setBillItems((prev) => [...prev, newItem]);
    setIsAddItemModalOpen(false);
  };

  const handleRemoveBillItem = (id: string) => {
    setBillItems((prev) => prev.filter((item) => item.id !== id));
  };

  const handleOpenSettlement = () => {
    // Pre-populate cash or UPI with full balance
    setCashTendered("0");
    setUpiTendered(totalBillAmount.toString());
    setCardTendered("0");
    setTpaClaimTendered("0");
    setIsSettlementModalOpen(true);
  };

  const handleConfirmPayment = () => {
    if (totalTendered < totalBillAmount) {
      alert("Tendered amount is less than total bill. Please reconcile full amount or add TPA credit.");
      return;
    }

    const invoiceNum = `INV-2026-${Math.floor(100000 + Math.random() * 900000)}`;
    setLastSettledInvoice({
      invoiceNumber: invoiceNum,
      patientName: patientSummary?.full_name || "Siddharth Verma",
      mrn: patientSummary?.mrn || "MRN-2026-0001",
      totalAmount: totalBillAmount,
      paidAmount: totalTendered,
      breakdown: {
        Cash: parseFloat(cashTendered) || 0,
        UPI: parseFloat(upiTendered) || 0,
        Card: parseFloat(cardTendered) || 0,
        TPA_Insurance: parseFloat(tpaClaimTendered) || 0,
      },
    });

    setIsSettlementModalOpen(false);
    setIsInvoicePrintModalOpen(true);
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
      {/* Header & Shift Controls */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <CreditCard className="text-sky-400" />
            Cashier Billing Counter & Split-Tender Settlement
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            {shift?.is_open
              ? `COUNTER ACTIVE: ${shift.counter_id} • Shift Opened: ${new Date(
                  shift.opened_at || ""
                ).toLocaleTimeString()} • FIPS 140-2 Validated`
              : "COUNTER SHIFT CLOSED • Please open shift to accept patient settlements"}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {shift?.is_open ? (
            <Button
              variant="danger"
              size="sm"
              onClick={() => setIsCloseModalActive(true)}
              className="flex items-center gap-1.5"
            >
              <Lock size={14} /> Close & Reconcile Shift
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsOpenModalActive(true)}
              className="flex items-center gap-1.5"
            >
              <Unlock size={14} /> Open Counter Shift
            </Button>
          )}

          <a
            href="/api/registers/cashier-shift-reconciliation?format=csv"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-md bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-200 transition-colors"
          >
            <Download size={13} /> Export Ledger CSV
          </a>

          <button
            onClick={loadShift}
            disabled={isLoading}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
          >
            <RefreshCw size={15} className={isLoading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="grid grid-cols-4 gap-4 mt-6">
        <Card className="p-4 bg-slate-900 border-slate-800">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Starting Cash Float</span>
            <DollarSign size={16} className="text-sky-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-slate-100 mt-2">
            ₹{((shift?.starting_float_paise || 0) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">Opening drawer cash balance</div>
        </Card>

        <Card className="p-4 bg-slate-900 border-slate-800">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Shift Collections</span>
            <Receipt size={16} className="text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-2">
            ₹{((shift?.total_collected_paise || 0) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">{shift?.total_receipts_count || 0} vouchers settled</div>
        </Card>

        <Card className="p-4 bg-slate-900 border-slate-800 col-span-2">
          <div className="text-xs text-slate-400 mb-2">Tender Breakdown (Live Shift Split)</div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-2 rounded bg-slate-950 border border-slate-800">
              <div className="text-[10px] text-slate-500 uppercase">Cash In Drawer</div>
              <div className="text-sm font-bold font-mono text-slate-200 mt-1">
                ₹{((shift?.by_payment_method?.CASH || 0) / 100).toLocaleString("en-IN")}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-950 border border-slate-800">
              <div className="text-[10px] text-slate-500 uppercase">UPI / BharatQR</div>
              <div className="text-sm font-bold font-mono text-sky-400 mt-1">
                ₹{((shift?.by_payment_method?.UPI || 0) / 100).toLocaleString("en-IN")}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-950 border border-slate-800">
              <div className="text-[10px] text-slate-500 uppercase">POS Card / NetBank</div>
              <div className="text-sm font-bold font-mono text-purple-400 mt-1">
                ₹{((shift?.by_payment_method?.CARD || 0) / 100).toLocaleString("en-IN")}
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* TPA Insurance Pre-Authorization & Co-Pay Card */}
      <Card className="p-4 bg-slate-900/90 border-slate-800 space-y-3 mt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-emerald-400" />
            <span className="text-xs font-bold text-slate-200 uppercase tracking-wider">
              TPA Insurance Pre-Authorization &amp; Co-Pay Allocation
            </span>
          </div>
          <Badge variant="success" size="sm">Pre-Auth Sanctioned</Badge>
        </div>

        <div className="grid grid-cols-4 gap-4 text-xs font-mono">
          <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
            <span className="text-slate-400 block text-[10px] uppercase">Insurance TPA</span>
            <span className="text-slate-100 font-bold">Star Health &amp; Allied</span>
            <div className="text-[10px] text-slate-500">Claim #TPA-2026-9812</div>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
            <span className="text-slate-400 block text-[10px] uppercase">Sanctioned Limit</span>
            <span className="text-emerald-400 font-bold text-sm">₹1,50,000.00</span>
            <div className="text-[10px] text-slate-500">Cashless Approved</div>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800">
            <span className="text-slate-400 block text-[10px] uppercase">Policy Co-Pay (10%)</span>
            <span className="text-amber-400 font-bold text-sm">₹15,000.00</span>
            <div className="text-[10px] text-slate-500">Patient Share Payable</div>
          </div>
          <div className="bg-slate-950 p-2.5 rounded-lg border border-slate-800 flex flex-col justify-between">
            <span className="text-slate-400 block text-[10px] uppercase">Net Insurer Liability</span>
            <span className="text-sky-400 font-bold text-sm">₹1,35,000.00</span>
            <button
              type="button"
              onClick={() => {
                const total = totalBillAmount;
                const tpaCoverage = Math.min(135000, total * 0.9);
                setTpaClaimTendered(tpaCoverage.toFixed(2));
                setCashTendered((total - tpaCoverage).toFixed(2));
              }}
              className="mt-1 text-[10px] font-bold text-sky-400 hover:text-sky-300 underline text-left"
            >
              Auto-Split to Folio
            </button>
          </div>
        </div>
      </Card>

      {/* Main Billing Workspace: Charge Entry & Folio */}
      <div className="mt-6 grid grid-cols-3 gap-6">
        {/* Left 2 Cols: Charge Entry Table */}
        <div className="col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                Patient Bill Folio &amp; Charge Items
              </h2>
              <Badge variant="neutral" size="sm">
                Patient: {patientSummary?.full_name || "Siddharth Verma"} ({patientSummary?.mrn || "MRN-2026-0001"})
              </Badge>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsAddItemModalOpen(true)}
              className="flex items-center gap-1.5 text-xs text-sky-400"
            >
              <PlusCircle size={14} /> Add Service Charge
            </Button>
          </div>

          {/* Folio Category Filter Tabs */}
          <div className="flex items-center gap-1.5">
            {(["ALL", "Consultation", "Bed Charge", "Diagnostics", "Pharmacy", "Procedure"] as const).map((cat) => {
              const count = cat === "ALL" ? billItems.length : billItems.filter((i) => i.category === cat).length;
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setFolioFilter(cat)}
                  className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all ${
                    folioFilter === cat
                      ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                      : "bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800"
                  }`}
                >
                  {cat} ({count})
                </button>
              );
            })}
          </div>

          <Card className="p-0 bg-slate-900 border-slate-800 overflow-hidden">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-slate-800 bg-slate-950/60 text-slate-400 text-[11px] uppercase">
                  <th className="p-3">Item / Service Description</th>
                  <th className="p-3">Discipline</th>
                  <th className="p-3 text-right">Rate (₹)</th>
                  <th className="p-3 text-center">Qty</th>
                  <th className="p-3 text-right">GST</th>
                  <th className="p-3 text-right">Amount (₹)</th>
                  <th className="p-3 text-center">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {(folioFilter === "ALL" ? billItems : billItems.filter((i) => i.category === folioFilter)).map((item) => {
                  const lineTotal = item.unitPrice * item.quantity * (1 + item.gstRate / 100);
                  return (
                    <tr key={item.id} className="hover:bg-slate-950/40">
                      <td className="p-3 text-slate-200 font-medium font-sans">{item.description}</td>
                      <td className="p-3 text-slate-400">
                        <Badge variant="neutral" size="sm" className="text-[10px]">
                          {item.category}
                        </Badge>
                      </td>
                      <td className="p-3 text-right text-slate-300">₹{item.unitPrice.toLocaleString("en-IN")}</td>
                      <td className="p-3 text-center text-slate-300">{item.quantity}</td>
                      <td className="p-3 text-right text-slate-500">{item.gstRate > 0 ? `${item.gstRate}%` : "Nil"}</td>
                      <td className="p-3 text-right font-bold text-slate-100">
                        ₹{lineTotal.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                      </td>
                      <td className="p-3 text-center">
                        <button
                          onClick={() => handleRemoveBillItem(item.id)}
                          className="text-slate-500 hover:text-rose-400 p-1 transition-colors"
                        >
                          <Trash2 size={13} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </Card>
        </div>

        {/* Right Col: Bill Summary & Settlement Terminal */}
        <div className="space-y-4">
          <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">Settlement Summary</h2>

          <Card className="p-5 bg-slate-900 border-slate-800 space-y-4 font-mono text-xs">
            <div className="flex justify-between text-slate-400">
              <span>Subtotal:</span>
              <span className="text-slate-200 font-bold">₹{calculateSubtotal().toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
            </div>

            <div className="flex justify-between text-slate-400">
              <span>Healthcare GST / Cess:</span>
              <span className="text-slate-200">₹{calculateGst().toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
            </div>

            <div className="flex justify-between text-slate-400">
              <span>Hospital Concession / Discount:</span>
              <span className="text-emerald-400">₹0.00</span>
            </div>

            <div className="pt-3 border-t border-slate-800 flex justify-between items-center text-sm font-bold">
              <span className="text-slate-100 uppercase tracking-wide">Net Payable:</span>
              <span className="text-xl text-emerald-400">
                ₹{totalBillAmount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>

            <Button
              variant="primary"
              size="lg"
              onClick={handleOpenSettlement}
              className="w-full mt-4 flex items-center justify-center gap-2 font-bold"
            >
              <CreditCard size={16} /> Proceed to Split Settlement
            </Button>
          </Card>

          {/* Quick Tariff Reference */}
          <Card className="p-4 bg-slate-950 border-slate-800 space-y-2 text-xs">
            <span className="font-bold text-slate-300 block uppercase text-[10px]">Statutory Guidelines</span>
            <p className="text-slate-500 text-[11px] leading-relaxed">
              All in-hospital diagnostic tests are exempt from GST under Notification 12/2017-Central Tax. Pharmacy supplies retain statutory GST tariffs.
            </p>
          </Card>
        </div>
      </div>

      {/* Modal: Add Service Charge */}
      <Modal
        isOpen={isAddItemModalOpen}
        onClose={() => setIsAddItemModalOpen(false)}
        title="Add Hospital Service / Procedure Charge"
      >
        <form onSubmit={handleAddBillItem} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Service / Item Name</label>
            <input
              type="text"
              required
              value={newItemDesc}
              onChange={(e) => setNewItemDesc(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Department</label>
              <select
                value={newItemCategory}
                onChange={(e) => setNewItemCategory(e.target.value as any)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
              >
                <option value="Diagnostics">Diagnostics / Lab</option>
                <option value="Consultation">OPD Consultation</option>
                <option value="Bed Charge">IPD Bed Charge</option>
                <option value="Pharmacy">Pharmacy Meds</option>
                <option value="Procedure">Surgical Procedure</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Rate (₹)</label>
              <input
                type="number"
                required
                value={newItemPrice}
                onChange={(e) => setNewItemPrice(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Quantity</label>
              <input
                type="number"
                min="1"
                required
                value={newItemQty}
                onChange={(e) => setNewItemQty(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsAddItemModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm">
              Add to Patient Folio
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Split Tender Settlement */}
      <Modal
        isOpen={isSettlementModalOpen}
        onClose={() => setIsSettlementModalOpen(false)}
        title="Split Tender Payment Settlement"
      >
        <div className="space-y-4">
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg flex justify-between items-center font-mono">
            <div>
              <span className="text-[10px] text-slate-500 uppercase block">Total Due</span>
              <span className="text-base font-bold text-slate-100">
                ₹{totalBillAmount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>
            <div className="text-right">
              <span className="text-[10px] text-slate-500 uppercase block">Balance Unpaid</span>
              <span className={`text-base font-bold ${remainingBalance > 0 ? "text-amber-400" : "text-emerald-400"}`}>
                ₹{remainingBalance.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
              </span>
            </div>
          </div>

          {/* Tender Inputs */}
          <div className="space-y-3 font-mono text-xs">
            <div className="flex items-center gap-3">
              <span className="w-28 text-slate-300">Cash:</span>
              <input
                type="number"
                value={cashTendered}
                onChange={(e) => setCashTendered(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
              />
            </div>

            <div className="flex items-center gap-3">
              <span className="w-28 text-slate-300">UPI / BharatQR:</span>
              <input
                type="number"
                value={upiTendered}
                onChange={(e) => setUpiTendered(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setIsUpiQrVisible(!isUpiQrVisible)}
                className="text-[11px] flex items-center gap-1"
              >
                <QrCode size={13} /> {isUpiQrVisible ? "Hide QR" : "Show QR"}
              </Button>
            </div>

            {isUpiQrVisible && (
              <div className="p-3 rounded-lg bg-white text-slate-950 flex flex-col items-center justify-center font-sans space-y-1">
                <div className="font-bold text-xs uppercase">Scan to Pay via UPI</div>
                <div className="h-28 w-28 bg-slate-900 rounded p-2 flex items-center justify-center text-white text-[10px] font-mono">
                  [DYNAMIC UPI QR]
                </div>
                <div className="text-[10px] text-slate-600 font-mono">UPI ID: apollo.hospital@icici</div>
              </div>
            )}

            <div className="flex items-center gap-3">
              <span className="w-28 text-slate-300">Card (POS):</span>
              <input
                type="number"
                value={cardTendered}
                onChange={(e) => setCardTendered(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
              />
            </div>

            <div className="flex items-center gap-3">
              <span className="w-28 text-slate-300">TPA Insurance:</span>
              <input
                type="number"
                value={tpaClaimTendered}
                onChange={(e) => setTpaClaimTendered(e.target.value)}
                className="flex-1 bg-slate-950 border border-slate-800 rounded p-2 text-xs text-slate-200"
              />
            </div>
          </div>

          {changeDue > 0 && (
            <div className="p-2 rounded bg-amber-950/40 border border-amber-800 text-xs font-mono text-amber-300 flex justify-between">
              <span>Change to Return Patient:</span>
              <span className="font-bold">₹{changeDue.toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
            </div>
          )}

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
            <Button variant="outline" size="sm" onClick={() => setIsSettlementModalOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={totalTendered < totalBillAmount}
              onClick={handleConfirmPayment}
            >
              Confirm Settlement & Generate Invoice
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modal: Official Tax Invoice & Thermal Receipt */}
      {lastSettledInvoice && (
        <Modal
          isOpen={isInvoicePrintModalOpen}
          onClose={() => setIsInvoicePrintModalOpen(false)}
          title="Payment Settled — GST Tax Invoice"
        >
          <div className="space-y-4">
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-3 font-mono text-xs">
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <div>
                  <span className="font-bold text-slate-100 text-sm">AVINYA HEALTHCARE LTD.</span>
                  <div className="text-[10px] text-slate-400">GSTIN: 36AAAAA0000A1Z5 • NABH Accredited</div>
                </div>
                <div className="text-right">
                  <div className="text-emerald-400 font-bold">{lastSettledInvoice.invoiceNumber}</div>
                  <div className="text-[10px] text-slate-500">{new Date().toLocaleString()}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div>
                  <span className="text-slate-500 block">Patient Name:</span>
                  <span className="text-slate-200 font-semibold">{lastSettledInvoice.patientName}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">UHID / MRN:</span>
                  <span className="text-slate-200">{lastSettledInvoice.mrn}</span>
                </div>
              </div>

              <div className="border-t border-b border-slate-800 py-2 space-y-1">
                {billItems.map((item, idx) => (
                  <div key={idx} className="flex justify-between text-[11px] text-slate-300">
                    <span>
                      {item.description} (x{item.quantity})
                    </span>
                    <span>₹{(item.unitPrice * item.quantity).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</span>
                  </div>
                ))}
              </div>

              <div className="flex justify-between text-xs font-bold pt-1">
                <span>Total Amount Paid:</span>
                <span className="text-emerald-400">
                  ₹{lastSettledInvoice.totalAmount.toLocaleString("en-IN", { minimumFractionDigits: 2 })}
                </span>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.print()}
                className="flex items-center gap-1.5"
              >
                <Printer size={13} /> Print Tax Invoice (80mm / A4)
              </Button>

              <Button variant="primary" size="sm" onClick={() => setIsInvoicePrintModalOpen(false)}>
                Done
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal: Open Shift */}
      <Modal isOpen={isOpenModalActive} onClose={() => setIsOpenModalActive(false)} title="Open Cashier Counter Shift">
        <form onSubmit={handleOpenShift} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Counter Identifier</label>
            <input
              type="text"
              value={counterId}
              onChange={(e) => setCounterId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500 font-mono"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Starting Cash Float (₹)</label>
            <input
              type="number"
              value={startingFloatRupees}
              onChange={(e) => setStartingFloatRupees(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500 font-mono"
              required
            />
          </div>
          <div className="pt-4 flex justify-end gap-3">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsOpenModalActive(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm">
              Open Shift
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Close Shift */}
      <Modal
        isOpen={isCloseModalActive}
        onClose={() => setIsCloseModalActive(false)}
        title="Close & Reconcile Cashier Shift"
      >
        <form onSubmit={handleCloseShift} className="space-y-4">
          <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-900/60 text-xs text-amber-300 font-mono">
            Mandatory: Count physical cash in counter drawer before submitting closing balance.
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Physical Cash Count in Drawer (₹)</label>
            <input
              type="number"
              value={physicalCashRupees}
              onChange={(e) => setPhysicalCashRupees(e.target.value)}
              placeholder="e.g. 19500"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500 font-mono"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Shift Handover Notes / Deficit Reason</label>
            <textarea
              rows={3}
              value={handoverNotes}
              onChange={(e) => setHandoverNotes(e.target.value)}
              placeholder="Notes on cash variances, void vouchers, or handover to incoming cashier..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
            />
          </div>
          <div className="pt-4 flex justify-end gap-3">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsCloseModalActive(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="danger" size="sm">
              Confirm Close & Reconcile
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};
