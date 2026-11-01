import React, { useEffect, useState } from "react";
import { uiApi } from "../../api/uiApi";
import { CashierShiftStatus } from "../../types";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Modal } from "../../components/ui/Modal";
import { CreditCard, DollarSign, Receipt, Lock, Unlock, Download, RefreshCw, Printer } from "lucide-react";

export const CashierCounterWorkspace: React.FC = () => {
  const [shift, setShift] = useState<CashierShiftStatus | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpenModalActive, setIsOpenModalActive] = useState(false);
  const [isCloseModalActive, setIsCloseModalActive] = useState(false);

  const [counterId, setCounterId] = useState("COUNTER-MAIN-01");
  const [startingFloatRupees, setStartingFloatRupees] = useState("5000");
  const [physicalCashRupees, setPhysicalCashRupees] = useState("");
  const [handoverNotes, setHandoverNotes] = useState("");

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

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
      {/* Header & Shift Controls */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <CreditCard className="text-sky-400" />
            Cashier Billing Counter & Reconciliation
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            {shift?.is_open
              ? `COUNTER ACTIVE: ${shift.counter_id} • Opened at: ${new Date(shift.opened_at || "").toLocaleTimeString()}`
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
          <div className="text-[11px] text-slate-500 mt-1">Opening counter balance</div>
        </Card>

        <Card className="p-4 bg-slate-900 border-slate-800">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Current Shift Collections</span>
            <Receipt size={16} className="text-emerald-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-emerald-400 mt-2">
            ₹{((shift?.total_collected_paise || 0) / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-slate-500 mt-1">{shift?.total_receipts_count || 0} vouchers processed</div>
        </Card>

        <Card className="p-4 bg-slate-900 border-slate-800 col-span-2">
          <div className="text-xs text-slate-400 mb-2">Tender Breakdown (Live Split)</div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-2 rounded bg-slate-950 border border-slate-800">
              <div className="text-[10px] text-slate-500 uppercase">Cash In Drawer</div>
              <div className="text-sm font-bold font-mono text-slate-200 mt-1">
                ₹{((shift?.by_payment_method?.CASH || 0) / 100).toLocaleString("en-IN")}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-950 border border-slate-800">
              <div className="text-[10px] text-slate-500 uppercase">UPI / QR Codes</div>
              <div className="text-sm font-bold font-mono text-sky-400 mt-1">
                ₹{((shift?.by_payment_method?.UPI || 0) / 100).toLocaleString("en-IN")}
              </div>
            </div>
            <div className="p-2 rounded bg-slate-950 border border-slate-800">
              <div className="text-[10px] text-slate-500 uppercase">Card POS</div>
              <div className="text-sm font-bold font-mono text-purple-400 mt-1">
                ₹{((shift?.by_payment_method?.CARD || 0) / 100).toLocaleString("en-IN")}
              </div>
            </div>
          </div>
        </Card>
      </div>

      {/* Quick Settlement Workspace & Thermal Print Trigger */}
      <div className="mt-8 grid grid-cols-3 gap-6">
        <Card className="col-span-2 p-6 bg-slate-900 border-slate-800">
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider mb-4">
            Patient Bill Settlement & Direct Receipt
          </h3>
          <div className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 mb-1">Select Invoice / Patient ID</label>
              <input
                type="text"
                placeholder="Enter Invoice # or search patient (Cmd+K)"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>
            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Payment Method</label>
                <select className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-sky-500">
                  <option value="CASH">CASH</option>
                  <option value="UPI">UPI / QR</option>
                  <option value="CARD">CREDIT/DEBIT CARD</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 mb-1">Amount to Tender (₹)</label>
                <input
                  type="number"
                  placeholder="0.00"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>
              <div className="flex items-end">
                <Button variant="primary" className="w-full flex items-center justify-center gap-2">
                  <Printer size={15} /> Settle & Print Receipt
                </Button>
              </div>
            </div>
          </div>
        </Card>

        {/* Shift Handover Guidelines */}
        <Card className="p-6 bg-slate-900 border-slate-800">
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider mb-3">Statutory SOP</h3>
          <ul className="text-xs text-slate-400 space-y-2 list-disc list-inside">
            <li>Verify physical currency count against expected drawer cash before ending shift.</li>
            <li>All UPI transactions must be reconciled against gateway terminal transaction IDs.</li>
            <li>Double-signature required on physical shift handover sheet for cash deficits &gt; ₹500.</li>
          </ul>
        </Card>
      </div>

      {/* Modal: Open Shift */}
      <Modal isOpen={isOpenModalActive} onClose={() => setIsOpenModalActive(false)} title="Open Cashier Counter Shift">
        <form onSubmit={handleOpenShift} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Counter Identifier</label>
            <input
              type="text"
              value={counterId}
              onChange={(e) => setCounterId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Starting Cash Float (₹)</label>
            <input
              type="number"
              value={startingFloatRupees}
              onChange={(e) => setStartingFloatRupees(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
              required
            />
          </div>
          <div className="pt-4 flex justify-end gap-3">
            <Button type="button" variant="ghost" onClick={() => setIsOpenModalActive(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" isLoading={isLoading}>
              Confirm Open Shift
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Close Shift */}
      <Modal isOpen={isCloseModalActive} onClose={() => setIsCloseModalActive(false)} title="Close & Reconcile Counter Shift">
        <form onSubmit={handleCloseShift} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Physical Cash Counted (₹)</label>
            <input
              type="number"
              value={physicalCashRupees}
              onChange={(e) => setPhysicalCashRupees(e.target.value)}
              placeholder="Enter counted physical currency"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
              required
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1">Handover Notes / Discrepancy Reason</label>
            <textarea
              value={handoverNotes}
              onChange={(e) => setHandoverNotes(e.target.value)}
              placeholder="Notes on handover to next cashier or supervisor..."
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-sm text-slate-200 focus:outline-none focus:border-sky-500"
              rows={3}
            />
          </div>
          <div className="pt-4 flex justify-end gap-3">
            <Button type="button" variant="ghost" onClick={() => setIsCloseModalActive(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="danger" isLoading={isLoading}>
              Confirm Shift Close & Lock
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

