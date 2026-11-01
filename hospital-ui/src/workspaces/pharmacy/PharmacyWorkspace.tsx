import React, { useState } from "react";
import { Pill, ShieldAlert, Download, Barcode, CheckCircle2, UserCheck, ShieldCheck, PlusCircle } from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";

interface PrescriptionItem {
  id: number;
  rxNumber: string;
  patientName: string;
  mrn: string;
  medications: Array<{
    name: string;
    dosage: string;
    batchNumber: string;
    quantity: number;
    status: "PENDING" | "VERIFIED";
  }>;
  ddiPassed: boolean;
  dispensed: boolean;
}

interface VaultItem {
  id: string;
  name: string;
  schedule: string;
  amps: number;
  batch: string;
}

export const PharmacyWorkspace: React.FC = () => {
  const [prescriptions, setPrescriptions] = useState<PrescriptionItem[]>([
    {
      id: 1,
      rxNumber: "Rx #9021",
      patientName: "Siddharth Verma",
      mrn: "MRN-2026-0001",
      medications: [
        {
          name: "Amoxicillin + Clavulanate 625mg",
          dosage: "1 tab PO BD x 5 days",
          batchNumber: "AMC-2026-B1",
          quantity: 10,
          status: "PENDING",
        },
        {
          name: "Paracetamol 500mg Tablet",
          dosage: "1 tab PO TDS x 3 days",
          batchNumber: "PCM-2026-X4",
          quantity: 15,
          status: "PENDING",
        },
      ],
      ddiPassed: true,
      dispensed: false,
    },
    {
      id: 2,
      rxNumber: "Rx #9024",
      patientName: "Ananya Deshmukh",
      mrn: "ER-0914",
      medications: [
        {
          name: "Aspirin 75mg Gastro-resistant",
          dosage: "1 tab PO OD x 30 days",
          batchNumber: "ASP-2026-C3",
          quantity: 30,
          status: "PENDING",
        },
        {
          name: "Atorvastatin 40mg Tablet",
          dosage: "1 tab PO HS x 30 days",
          batchNumber: "ATV-2026-M8",
          quantity: 30,
          status: "PENDING",
        },
      ],
      ddiPassed: true,
      dispensed: false,
    },
  ]);

  const [vaultItems, setVaultItems] = useState<VaultItem[]>([
    { id: "morphine", name: "Morphine Sulfate 10mg/mL", schedule: "NDPS Form 3C", amps: 42, batch: "MOR-9982-A" },
    { id: "fentanyl", name: "Fentanyl Citrate 50mcg/mL", schedule: "NDPS Form 3C", amps: 18, batch: "FEN-7741-C" },
    { id: "midazolam", name: "Midazolam 5mg/mL", schedule: "Schedule H1", amps: 35, batch: "MDZ-4410-X" },
  ]);

  // Dispense modal state
  const [activeRxForDispense, setActiveRxForDispense] = useState<PrescriptionItem | null>(null);
  const [scannedBarcode, setScannedBarcode] = useState("");
  const [scanMessage, setScanMessage] = useState<{ text: string; success: boolean } | null>(null);

  // NDPS Vault Movement modal state
  const [isNdpsModalOpen, setIsNdpsModalOpen] = useState(false);
  const [selectedSubstance, setSelectedSubstance] = useState("morphine");
  const [moveQuantity, setMoveQuantity] = useState("2");
  const [moveReason, setMoveReason] = useState("Patient Dose Administration (ICU / OT)");
  const [witnessName, setWitnessName] = useState("Dr. Radhika Sen (Reg #WB-4921)");
  const [witnessPin, setWitnessPin] = useState("");
  const [ndpsLogMessage, setNdpsLogMessage] = useState<string | null>(null);

  // Walk-in Dispense Form State
  const [isWalkInModalOpen, setIsWalkInModalOpen] = useState(false);
  const [walkInPatientName, setWalkInPatientName] = useState("Rajesh Gupta");
  const [walkInMrn, setWalkInMrn] = useState("MRN-2026-0012");
  const [walkInMedName, setWalkInMedName] = useState("Azithromycin 500mg Tablet");
  const [walkInDosage, setWalkInDosage] = useState("1 tab PO OD x 3 days");
  const [walkInBatch, setWalkInBatch] = useState("AZM-2026-X1");
  const [walkInQty, setWalkInQty] = useState("3");

  const handleCreateWalkInRx = (e: React.FormEvent) => {
    e.preventDefault();
    const newRx: PrescriptionItem = {
      id: Date.now(),
      rxNumber: `Rx #${Math.floor(9100 + Math.random() * 800)}`,
      patientName: walkInPatientName,
      mrn: walkInMrn,
      medications: [
        {
          name: walkInMedName,
          dosage: walkInDosage,
          batchNumber: walkInBatch,
          quantity: parseInt(walkInQty, 10) || 1,
          status: "PENDING",
        },
      ],
      ddiPassed: true,
      dispensed: false,
    };
    setPrescriptions([newRx, ...prescriptions]);
    setIsWalkInModalOpen(false);
  };

  const handleOpenDispenseModal = (rx: PrescriptionItem) => {
    setActiveRxForDispense(rx);
    setScannedBarcode("");
    setScanMessage(null);
  };

  const handleSimulateScan = (batchToScan: string) => {
    setScannedBarcode(batchToScan);
    setScanMessage({
      text: `GS1 Barcode Verified: [01]0890123456789[10]${batchToScan}[17]281231. Batch & Expiry Match!`,
      success: true,
    });
  };

  const handleConfirmDispense = () => {
    if (!activeRxForDispense) return;

    setPrescriptions((prev) =>
      prev.map((rx) =>
        rx.id === activeRxForDispense.id ? { ...rx, dispensed: true } : rx
      )
    );
    setActiveRxForDispense(null);
    alert(`Prescription ${activeRxForDispense.rxNumber} dispensed successfully with barcode validation.`);
  };

  const handleNdpsMovementSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!witnessPin) {
      alert("Please enter witness PIN or password for double-custody compliance.");
      return;
    }

    const qty = parseInt(moveQuantity) || 1;
    setVaultItems((prev) =>
      prev.map((v) => (v.id === selectedSubstance ? { ...v, amps: Math.max(0, v.amps - qty) } : v))
    );

    const substanceName = vaultItems.find((v) => v.id === selectedSubstance)?.name;
    setNdpsLogMessage(
      `Logged: Dispensed ${qty} amps of ${substanceName}. Witness: ${witnessName}. Verified under NDPS Rule 66.`
    );
    setIsNdpsModalOpen(false);
    setWitnessPin("");
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <Pill className="text-emerald-400" />
            Central Pharmacy & Controlled Substances Vault
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            eRx Verification • 2D DataMatrix Batch Scanner • Schedule H1 & NDPS Dual-Custody Ledger
          </p>
        </div>

        <div className="flex items-center gap-3">
          <a
            href="/api/registers/ndps-ledger?format=csv"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 px-3 py-1.5 text-xs font-semibold rounded-md bg-slate-900 border border-slate-700 hover:bg-slate-800 text-slate-200 transition-colors"
          >
            <Download size={13} /> Export NDPS Ledger CSV
          </a>
        </div>
      </div>

      {/* Real-time notification if NDPS movement was logged */}
      {ndpsLogMessage && (
        <div className="mt-4 p-3 rounded-lg bg-amber-950/40 border border-amber-800 text-amber-300 text-xs font-mono flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck size={16} className="text-amber-400" />
            <span>{ndpsLogMessage}</span>
          </div>
          <button
            onClick={() => setNdpsLogMessage(null)}
            className="text-amber-400 hover:text-amber-200 text-xs font-bold"
          >
            ✕
          </button>
        </div>
      )}

      {/* Main Grid */}
      <div className="grid grid-cols-3 gap-6 mt-6">
        {/* Prescription Verification Queue */}
        <div className="col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
              Pending e-Prescriptions for Dispense ({prescriptions.filter((p) => !p.dispensed).length})
            </h2>
            <div className="flex items-center gap-2">
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsWalkInModalOpen(true)}
                className="flex items-center gap-1.5 text-xs font-semibold"
              >
                <PlusCircle size={14} /> Intake Walk-in Prescription
              </Button>
              <Badge variant="neutral" size="sm">
                Pharmacist Station 1
              </Badge>
            </div>
          </div>

          <div className="space-y-3">
            {prescriptions.map((rx) => (
              <Card
                key={rx.id}
                className={`p-4 border transition-all ${
                  rx.dispensed
                    ? "bg-slate-950/60 border-slate-900 opacity-60"
                    : "bg-slate-900 border-slate-800"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <span className="font-semibold text-sm text-slate-100">
                      {rx.rxNumber} — {rx.patientName}
                    </span>
                    <span className="text-xs text-slate-400 ml-2 font-mono">{rx.mrn}</span>
                  </div>
                  <Badge variant={rx.dispensed ? "success" : "warning"} size="sm">
                    {rx.dispensed ? "Dispensed & Billed" : "Awaiting Barcode Dispense"}
                  </Badge>
                </div>

                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2 mb-3">
                  {rx.medications.map((med, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between text-xs pb-2 border-b border-slate-900 last:border-0 last:pb-0"
                    >
                      <div>
                        <div className="font-semibold text-slate-200">{med.name}</div>
                        <div className="text-[11px] text-slate-400">{med.dosage}</div>
                      </div>
                      <div className="text-right">
                        <span className="font-mono text-emerald-400">
                          Batch: {med.batchNumber}
                        </span>
                        <div className="text-[11px] text-slate-400">Qty: {med.quantity} units</div>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="flex items-center justify-between pt-1">
                  <span className="text-xs text-emerald-400 flex items-center gap-1 font-mono">
                    <CheckCircle2 size={13} /> DDI Screening: Passed (0 Major Interactions)
                  </span>

                  {!rx.dispensed && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() => handleOpenDispenseModal(rx)}
                      className="flex items-center gap-1.5"
                    >
                      <Barcode size={14} /> Scan Batch & Dispense
                    </Button>
                  )}
                </div>
              </Card>
            ))}
          </div>
        </div>

        {/* NDPS Narcotics Double-Custody Vault Status */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldAlert size={16} /> NDPS Schedule H1 Vault
            </h2>
            <Badge variant="warning" size="sm">
              Double-Custody
            </Badge>
          </div>

          <Card className="p-4 bg-slate-900 border-amber-900/40 space-y-4">
            <div className="text-xs text-slate-400 leading-relaxed">
              Narcotic and psychotropic substances require dual-witness sign-off for inventory decrement in accordance with NDPS Form 3C.
            </div>

            <div className="space-y-2 font-mono text-xs">
              {vaultItems.map((v) => (
                <div
                  key={v.id}
                  className="flex items-center justify-between p-3 rounded bg-slate-950 border border-slate-800"
                >
                  <div>
                    <div className="font-semibold text-slate-200">{v.name}</div>
                    <div className="text-[10px] text-slate-500">
                      {v.schedule} • Batch: {v.batch}
                    </div>
                  </div>
                  <span
                    className={`font-bold text-sm px-2 py-0.5 rounded border ${
                      v.amps < 20
                        ? "bg-rose-950 text-rose-400 border-rose-800"
                        : "bg-amber-950 text-amber-400 border-amber-800"
                    }`}
                  >
                    {v.amps} amps
                  </span>
                </div>
              ))}
            </div>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsNdpsModalOpen(true)}
              className="w-full flex items-center justify-center gap-1.5"
            >
              <UserCheck size={14} /> Record Vault Movement (Witness Auth)
            </Button>
          </Card>
        </div>
      </div>

      {/* Modal: Barcode Scan & Dispense */}
      {activeRxForDispense && (
        <Modal
          isOpen={true}
          onClose={() => setActiveRxForDispense(null)}
          title={`Barcode Dispensing Verification — ${activeRxForDispense.rxNumber}`}
        >
          <div className="space-y-4">
            <div className="text-xs text-slate-300">
              Scan medicine package GS1 DataMatrix or select a batch to verify packaging integrity:
            </div>

            <div className="space-y-2">
              {activeRxForDispense.medications.map((m, i) => (
                <div
                  key={i}
                  className="p-3 rounded-lg bg-slate-950 border border-slate-800 flex items-center justify-between"
                >
                  <div>
                    <div className="text-xs font-semibold text-slate-200">{m.name}</div>
                    <div className="text-[11px] text-slate-400 font-mono">
                      Target Batch: {m.batchNumber} • Qty: {m.quantity}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => handleSimulateScan(m.batchNumber)}
                    className="text-xs font-mono"
                  >
                    Simulate Scan [{m.batchNumber}]
                  </Button>
                </div>
              ))}
            </div>

            {scannedBarcode && (
              <div className="p-3 rounded-lg bg-sky-950/40 border border-sky-800 text-xs font-mono text-sky-300">
                Scanned Value: <span className="font-bold">{scannedBarcode}</span>
              </div>
            )}

            {scanMessage && (
              <div
                className={`p-3 rounded-lg border text-xs font-mono ${
                  scanMessage.success
                    ? "bg-emerald-950/40 border-emerald-800 text-emerald-300"
                    : "bg-rose-950/40 border-rose-800 text-rose-300"
                }`}
              >
                {scanMessage.text}
              </div>
            )}

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setActiveRxForDispense(null)}
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={!scannedBarcode}
                onClick={handleConfirmDispense}
              >
                Authorize & Dispense Items
              </Button>
            </div>
          </div>
        </Modal>
      )}

      {/* Modal: NDPS Double-Witness Sign-off */}
      <Modal
        isOpen={isNdpsModalOpen}
        onClose={() => setIsNdpsModalOpen(false)}
        title="NDPS Schedule H1 Double-Witness Movement Authorization"
      >
        <form onSubmit={handleNdpsMovementSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">
              Controlled Substance
            </label>
            <select
              value={selectedSubstance}
              onChange={(e) => setSelectedSubstance(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
            >
              {vaultItems.map((v) => (
                <option key={v.id} value={v.id}>
                  {v.name} (Stock: {v.amps} amps)
                </option>
              ))}
            </select>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Quantity (Amps/Vials)
              </label>
              <input
                type="number"
                min="1"
                max="20"
                required
                value={moveQuantity}
                onChange={(e) => setMoveQuantity(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-amber-500"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Purpose / Destination
              </label>
              <select
                value={moveReason}
                onChange={(e) => setMoveReason(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-amber-500"
              >
                <option value="Patient Dose Administration (ICU / OT)">Patient Dose (ICU / OT)</option>
                <option value="Breakage / Ampoule Wastage">Breakage / Ampoule Wastage</option>
                <option value="Inter-Departmental Transfer">Inter-Departmental Transfer</option>
              </select>
            </div>
          </div>

          {/* Dual Witness Verification Credentials */}
          <div className="p-3 bg-amber-950/20 border border-amber-800/60 rounded-lg space-y-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-amber-400 flex items-center gap-1.5">
              <ShieldAlert size={13} /> Mandatory Double-Sign Witness
            </div>
            <div>
              <label className="text-[10px] text-slate-400 block mb-0.5">Witness Doctor / Registered Nurse</label>
              <input
                type="text"
                value={witnessName}
                onChange={(e) => setWitnessName(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
              />
            </div>
            <div>
              <label className="text-[10px] text-slate-400 block mb-0.5">Witness Security PIN / Password</label>
              <input
                type="password"
                required
                placeholder="Enter witness PIN (e.g. 1234)"
                value={witnessPin}
                onChange={(e) => setWitnessPin(e.target.value)}
                className="w-full bg-slate-900 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setIsNdpsModalOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm">
              Authorize Dual-Signature Decrement
            </Button>
          </div>
        </form>
      </Modal>

      {/* Modal: Intake Walk-in Prescription */}
      <Modal
        isOpen={isWalkInModalOpen}
        onClose={() => setIsWalkInModalOpen(false)}
        title="Intake Walk-in Prescription / Direct Dispensary Order"
      >
        <form onSubmit={handleCreateWalkInRx} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Patient Full Name</label>
              <input
                type="text"
                required
                value={walkInPatientName}
                onChange={(e) => setWalkInPatientName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500 font-semibold"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">UHID / MRN</label>
              <input
                type="text"
                required
                value={walkInMrn}
                onChange={(e) => setWalkInMrn(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-emerald-500"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Medication Name & Strength</label>
            <input
              type="text"
              required
              value={walkInMedName}
              onChange={(e) => setWalkInMedName(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1">Dosage Frequency & Route</label>
            <input
              type="text"
              required
              value={walkInDosage}
              onChange={(e) => setWalkInDosage(e.target.value)}
              placeholder="e.g. 1 tab PO BD x 5 days"
              className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Batch Number</label>
              <input
                type="text"
                required
                value={walkInBatch}
                onChange={(e) => setWalkInBatch(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Quantity (Units / Tabs)</label>
              <input
                type="number"
                min="1"
                required
                value={walkInQty}
                onChange={(e) => setWalkInQty(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
            <Button type="button" variant="outline" size="sm" onClick={() => setIsWalkInModalOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" size="sm" className="flex items-center gap-1.5 font-semibold">
              <Pill size={14} /> Queue for Barcode Dispense
            </Button>
          </div>
        </form>
      </Modal>

    </div>
  );
};
