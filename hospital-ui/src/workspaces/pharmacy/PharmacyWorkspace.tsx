import React, { useEffect, useState } from "react";
import { AlertTriangle, Boxes, ClipboardList, RefreshCw, ShieldCheck } from "lucide-react";
import {
  pharmacyApi,
  type ControlledSubstanceMovement,
  type ControlledSubstanceVault,
  type InventoryBatch,
  type Prescription,
  type PrescriptionItem,
} from "../../api/pharmacyApi";

const LASA_REGISTRY: Record<string, { tallMan: string; confusedWith: string; alertRisk: string }> = {
  hydralazine: { tallMan: "hydrALAZINE", confusedWith: "hydrOXYzine (antihistamine)", alertRisk: "Vasodilator vs antihistamine" },
  hydroxyzine: { tallMan: "hydrOXYzine", confusedWith: "hydrALAZINE (antihypertensive)", alertRisk: "Antihistamine vs vasodilator" },
  dopamine: { tallMan: "dopAMINE", confusedWith: "dobUTAMINE (inotrope)", alertRisk: "Vasopressor vs inotrope" },
  dobutamine: { tallMan: "dobUTAMINE", confusedWith: "dopAMINE (vasopressor)", alertRisk: "Inotrope vs vasopressor" },
  metformin: { tallMan: "metFORMIN", confusedWith: "metOPROLOL (beta blocker)", alertRisk: "Oral hypoglycemic vs beta blocker" },
  metoprolol: { tallMan: "metOPROLOL", confusedWith: "metFORMIN (oral hypoglycemic)", alertRisk: "Beta blocker vs oral hypoglycemic" },
  cefazoline: { tallMan: "cefaZOLIN", confusedWith: "cefTRIAXONE (3rd generation cephalosporin)", alertRisk: "1st vs 3rd generation cephalosporin" },
  ceftriaxone: { tallMan: "cefTRIAXONE", confusedWith: "cefaZOLIN (1st generation cephalosporin)", alertRisk: "3rd vs 1st generation cephalosporin" },
};

function checkLasaDrug(drugName: string) {
  const normalized = drugName.toLowerCase();
  return Object.entries(LASA_REGISTRY).find(([key]) => normalized.includes(key))?.[1] ?? null;
}

type WorkspaceTab = "prescriptions" | "inventory" | "controlled";

const formatMoney = (paise: number) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" }).format(paise / 100);

const formatDate = (value: string) =>
  new Date(value).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" });

const remainingQuantity = (item: PrescriptionItem) =>
  Math.max(0, item.requested_quantity - item.dispensed_quantity);

const fefoBatchFor = (item: PrescriptionItem, batches: InventoryBatch[]) =>
  batches
    .filter((batch) =>
      batch.medication_id === item.medication_id &&
      batch.stock_quantity > 0 &&
      new Date(batch.expiry_date).getTime() > Date.now()
    )
    .sort((a, b) =>
      new Date(a.expiry_date).getTime() - new Date(b.expiry_date).getTime() || a.id - b.id
    )[0];

export const PharmacyWorkspace: React.FC = () => {
  const [tab, setTab] = useState<WorkspaceTab>("prescriptions");
  const [prescriptions, setPrescriptions] = useState<Prescription[]>([]);
  const [batches, setBatches] = useState<InventoryBatch[]>([]);
  const [vaults, setVaults] = useState<ControlledSubstanceVault[]>([]);
  const [movements, setMovements] = useState<ControlledSubstanceMovement[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activePrescription, setActivePrescription] = useState<Prescription | null>(null);
  const [dispenseQuantities, setDispenseQuantities] = useState<Record<number, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const loadWorkspace = async (quiet = false) => {
    if (quiet) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const [active, partial, inventory, vaultData, movementData] = await Promise.all([
        pharmacyApi.listPrescriptions("ACTIVE"),
        pharmacyApi.listPrescriptions("PARTIAL"),
        pharmacyApi.listInventoryBatches(),
        pharmacyApi.listControlledSubstanceVaults(),
        pharmacyApi.listControlledSubstanceMovements(),
      ]);
      setPrescriptions([...active.items, ...partial.items].sort((a, b) => b.id - a.id));
      setBatches(inventory.items);
      setVaults(vaultData);
      setMovements(movementData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load pharmacy data.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void loadWorkspace();
  }, []);

  const openDispense = (prescription: Prescription) => {
    if (!prescription.patient_name || !prescription.patient_mrn) {
      setError("Patient name and MRN are unavailable. Dispensing is blocked until the privacy-gated patient identity is returned.");
      return;
    }
    setActivePrescription(prescription);
    const initial: Record<number, string> = {};
    for (const item of prescription.items) {
      const available = fefoBatchFor(item, batches);
      initial[item.id] = available
        ? String(Math.min(remainingQuantity(item), available.stock_quantity))
        : "0";
    }
    setDispenseQuantities(initial);
    setError(null);
    setNotice(null);
  };

  const submitDispense = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activePrescription) return;

    const items = activePrescription.items.flatMap((item) => {
      const quantity = Number(dispenseQuantities[item.id] ?? 0);
      if (!Number.isInteger(quantity) || quantity <= 0) return [];
      const batch = fefoBatchFor(item, batches);
      if (!batch) return [];
      return [{
        prescription_item_id: item.id,
        batch_id: batch.id,
        quantity_to_dispense: quantity,
      }];
    });

    if (items.length === 0) {
      setError("Enter a positive dispense quantity for at least one item with available, unexpired stock.");
      return;
    }

    for (const line of items) {
      const rxItem = activePrescription.items.find((item) => item.id === line.prescription_item_id);
      const batch = batches.find((entry) => entry.id === line.batch_id);
      if (!rxItem || !batch || line.quantity_to_dispense > remainingQuantity(rxItem) || line.quantity_to_dispense > batch.stock_quantity) {
        setError("A quantity exceeds the remaining prescription or available batch stock. Refresh and review the order.");
        return;
      }
    }

    setSubmitting(true);
    setError(null);
    try {
      const result = await pharmacyApi.dispensePrescription(activePrescription.id, { items });
      setNotice(`Dispensing recorded. Prescription status: ${result.prescription_status}. Draft invoice: ${result.billed_to_invoice}.`);
      setActivePrescription(null);
      await loadWorkspace(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Dispensing failed. No success was recorded.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <div className="p-6 text-sm text-slate-500">Loading live pharmacy records…</div>;
  }

  return (
    <div className="space-y-5 p-4 md:p-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-slate-900 dark:text-slate-100">Pharmacy & Inventory</h1>
          <p className="mt-1 text-sm text-slate-500">Live formulary, prescription queue, stock and controlled-substance ledger</p>
        </div>
        <button
          type="button"
          onClick={() => void loadWorkspace(true)}
          disabled={refreshing}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium text-slate-700 disabled:opacity-50 dark:border-slate-700 dark:text-slate-200"
        >
          <RefreshCw size={15} className={refreshing ? "animate-spin" : ""} />
          Refresh
        </button>
      </header>

      {error && <div role="alert" className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">{error}</div>}
      {notice && <div role="status" className="rounded-lg border border-emerald-300 bg-emerald-50 p-3 text-sm text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-200">{notice}</div>}

      <nav className="flex flex-wrap gap-2 border-b border-slate-200 pb-3 dark:border-slate-800" aria-label="Pharmacy sections">
        {([
          ["prescriptions", "Prescription queue", ClipboardList],
          ["inventory", "Inventory batches", Boxes],
          ["controlled", "Controlled substances", ShieldCheck],
        ] as const).map(([key, label, Icon]) => (
          <button
            key={key}
            type="button"
            onClick={() => setTab(key)}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${tab === key ? "bg-slate-900 text-white dark:bg-slate-100 dark:text-slate-900" : "bg-slate-100 text-slate-700 dark:bg-slate-900 dark:text-slate-300"}`}
          >
            <Icon size={16} /> {label}
          </button>
        ))}
      </nav>

      {tab === "prescriptions" && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold text-slate-900 dark:text-slate-100">Active and partially dispensed prescriptions</h2>
            <span className="text-xs text-slate-500">{prescriptions.length} records</span>
          </div>
          {prescriptions.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">No active prescriptions are waiting for pharmacy dispensing.</div>
          ) : prescriptions.map((prescription) => (
            <article key={prescription.id} className="rounded-xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-semibold text-slate-900 dark:text-slate-100">Prescription #{prescription.id}</div>
                  <div className="mt-1 text-sm text-slate-700 dark:text-slate-300">{prescription.patient_name || "Patient identity unavailable"}</div>
                  <div className="mt-1 text-xs text-slate-500">MRN: {prescription.patient_mrn || "Unavailable"} · Encounter #{prescription.encounter_id} · Prescriber user #{prescription.prescribing_doctor_id}</div>
                </div>
                <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-200">{prescription.status}</span>
              </div>
              <div className="mt-3 divide-y divide-slate-100 dark:divide-slate-800">
                {prescription.items.map((item) => {
                  const lasa = checkLasaDrug(`${item.medication.brand_name} ${item.medication.generic_name}`);
                  return (
                    <div key={item.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                      <div>
                        <div className="font-medium text-slate-800 dark:text-slate-200">{item.medication.brand_name} {item.medication.strength}</div>
                        <div className="text-xs text-slate-500">{item.dosage_instruction} · {item.medication.generic_name}</div>
                        {lasa && <div className="mt-1 text-xs font-semibold text-amber-700 dark:text-amber-300" role="note">LASA alert: {lasa.tallMan} may be confused with {lasa.confusedWith}. {lasa.alertRisk}. Verify the product carefully.</div>}
                      </div>
                      <div className="text-right text-xs text-slate-600 dark:text-slate-400">{item.dispensed_quantity} / {item.requested_quantity} dispensed</div>
                    </div>
                  );
                })}
              </div>
              <div className="mt-3 flex justify-end">
                <button type="button" onClick={() => openDispense(prescription)} disabled={!prescription.patient_name || !prescription.patient_mrn} className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-40">Review & dispense</button>
              </div>
            </article>
          ))}
        </section>
      )}

      {tab === "inventory" && (
        <section className="space-y-3">
          <h2 className="font-semibold text-slate-900 dark:text-slate-100">Available inventory batches</h2>
          {batches.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">No active inventory batches found.</div>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
              <table className="min-w-full text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900">
                  <tr><th className="px-3 py-3">Medication</th><th className="px-3 py-3">Batch</th><th className="px-3 py-3">Expiry</th><th className="px-3 py-3 text-right">Stock</th><th className="px-3 py-3 text-right">Unit cost</th></tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {batches.map((batch) => (
                    <tr key={batch.id}>
                      <td className="px-3 py-3"><div className="font-medium">{batch.medication.brand_name}</div><div className="text-xs text-slate-500">{batch.medication.code} · {batch.medication.strength}</div></td>
                      <td className="px-3 py-3 font-mono text-xs">{batch.batch_number}</td>
                      <td className="px-3 py-3">{formatDate(batch.expiry_date)}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{batch.stock_quantity}</td>
                      <td className="px-3 py-3 text-right tabular-nums">{formatMoney(batch.unit_price_paise)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {tab === "controlled" && (
        <section className="space-y-4">
          <div className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
            <div className="flex items-center gap-2 font-semibold"><AlertTriangle size={16} /> Read-only controlled-substance view</div>
            <p className="mt-1">Movement actions require dual-witness credentials and are intentionally not simulated in this workspace.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {vaults.map((vault) => (
              <article key={vault.id} className="rounded-xl border border-slate-200 p-4 dark:border-slate-800">
                <div className="font-semibold">{vault.medication.brand_name} {vault.medication.strength}</div>
                <div className="mt-1 text-xs text-slate-500">{vault.vault_location} · {vault.is_locked ? "Locked" : "Unlocked"}</div>
                <div className="mt-3 text-2xl font-bold tabular-nums">{vault.current_balance_units} <span className="text-sm font-normal text-slate-500">{vault.unit_of_measure}</span></div>
                <div className="mt-1 text-xs text-slate-500">Seal: {vault.tamper_seal_number || "Not recorded"}</div>
              </article>
            ))}
          </div>
          <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500 dark:bg-slate-900"><tr><th className="px-3 py-3">Time</th><th className="px-3 py-3">Vault</th><th className="px-3 py-3">Movement</th><th className="px-3 py-3 text-right">Qty</th><th className="px-3 py-3">Witness</th></tr></thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                {movements.map((movement) => (
                  <tr key={movement.id}>
                    <td className="px-3 py-3 text-xs">{new Date(movement.created_at).toLocaleString("en-IN")}</td>
                    <td className="px-3 py-3">#{movement.vault_id}</td>
                    <td className="px-3 py-3">{movement.movement_type}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{movement.quantity_units}</td>
                    <td className="px-3 py-3">{movement.witness_verified ? "Verified" : "Not verified"}</td>
                  </tr>
                ))}
                {movements.length === 0 && <tr><td colSpan={5} className="px-3 py-5 text-center text-slate-500">No movement records.</td></tr>}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {activePrescription && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="presentation">
          <section role="dialog" aria-modal="true" aria-labelledby="dispense-title" className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-5 shadow-xl dark:bg-slate-950">
            <div className="flex items-start justify-between gap-3">
              <div><h2 id="dispense-title" className="text-lg font-bold">Dispense prescription #{activePrescription.id}</h2><p className="text-xs text-slate-500">{activePrescription.patient_name} · MRN {activePrescription.patient_mrn} · Encounter #{activePrescription.encounter_id} · FEFO batch selection</p></div>
              <button type="button" onClick={() => setActivePrescription(null)} className="rounded px-2 py-1 text-slate-500 hover:bg-slate-100 dark:hover:bg-slate-900" aria-label="Close">✕</button>
            </div>
            <form onSubmit={submitDispense} className="mt-4 space-y-3">
              {activePrescription.items.map((item) => {
                const availableBatch = fefoBatchFor(item, batches);
                const remaining = remainingQuantity(item);
                const max = availableBatch ? Math.min(remaining, availableBatch.stock_quantity) : 0;
                const lasa = checkLasaDrug(`${item.medication.brand_name} ${item.medication.generic_name}`);
                return (
                  <div key={item.id} className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                    <div className="font-semibold">{item.medication.brand_name} {item.medication.strength}</div>
                    <div className="mt-1 text-xs text-slate-500">{item.dosage_instruction} · Remaining: {remaining}</div>
                    {lasa && <div className="mt-2 rounded-md border border-amber-300 bg-amber-50 p-2 text-xs text-amber-900 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-200" role="alert">LASA safety alert: use tall-man label {lasa.tallMan}. Potential confusion: {lasa.confusedWith}. {lasa.alertRisk}. Verify medication identity against the prescription and barcode.</div>}
                    {availableBatch ? (
                      <div className="mt-3 grid gap-3 md:grid-cols-3">
                        <div className="md:col-span-2 text-xs text-slate-600 dark:text-slate-300">
                          <div>FEFO batch: <strong>{availableBatch.batch_number}</strong></div>
                          <div>Expiry {formatDate(availableBatch.expiry_date)} · Stock {availableBatch.stock_quantity}</div>
                        </div>
                        <label className="text-xs font-medium">Quantity to dispense
                          <input
                            type="number"
                            min={0}
                            max={max}
                            step={1}
                            value={dispenseQuantities[item.id] ?? "0"}
                            onChange={(event) => setDispenseQuantities((current) => ({ ...current, [item.id]: event.target.value }))}
                            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
                          />
                        </label>
                      </div>
                    ) : <p className="mt-2 text-xs text-red-600">No unexpired stock is available for this medication.</p>}
                  </div>
                );
              })}
              <div className="flex flex-wrap justify-end gap-2 border-t border-slate-200 pt-3 dark:border-slate-800">
                <button type="button" onClick={() => setActivePrescription(null)} className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700">Cancel</button>
                <button type="submit" disabled={submitting} className="rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{submitting ? "Submitting…" : "Confirm dispensing"}</button>
              </div>
            </form>
          </section>
        </div>
      )}
    </div>
  );
};
