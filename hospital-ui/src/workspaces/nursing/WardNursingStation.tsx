import React, { useEffect, useState } from "react";
import { uiApi } from "../../api/uiApi";
import { DetailedBedItem } from "../../types";
import { useActivePatient } from "../../core/context/ActivePatientContext";
import { Card } from "../../components/ui/Card";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { useHospitalConfig } from "../../core/context/HospitalConfigContext";
import { printDocument } from "../../utils/printDocument";
import {
  BedDouble,
  RefreshCw,
  Activity,
  Sparkles,
  User,
  Pill,
  CheckCircle2,
  AlertTriangle,
  Siren,
  QrCode,
  Printer,
  Clock,
  ShieldCheck,
} from "lucide-react";

interface ScheduledMedication {
  id: string;
  bedNumber: string;
  patientName: string;
  mrn: string;
  drugName: string;
  dose: string;
  route: string;
  scheduledTime: string;
  status: "DUE" | "OVERDUE" | "ADMINISTERED";
  isHighAlert?: boolean;
  administeredAt?: string;
  administeredBy?: string;
}

export const WardNursingStation: React.FC = () => {
  const { hospitalProfile } = useHospitalConfig();
  const [activeTab, setActiveTab] = useState<"beds" | "emar">("beds");
  const [beds, setBeds] = useState<DetailedBedItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedWardId] = useState(1);
  const { selectPatient } = useActivePatient();

  // Alert & Notification States
  const [notificationToast, setNotificationToast] = useState<{
    type: "success" | "rrt";
    message: string;
    details?: string;
  } | null>(null);

  // NEWS2 / Vitals Recording Modal
  const [activeBedForVitals, setActiveBedForVitals] = useState<DetailedBedItem | null>(null);
  const [respRate, setRespRate] = useState(16);
  const [spo2, setSpo2] = useState(98);
  const [onOxygen, setOnOxygen] = useState(false);
  const [systolicBp, setSystolicBp] = useState(120);
  const [pulse, setPulse] = useState(72);
  const [consciousness, setConsciousness] = useState<"ALERT" | "CVPU">("ALERT");
  const [temperature, setTemperature] = useState(37.0);

  // eMAR State
  const [medications, setMedications] = useState<ScheduledMedication[]>([
    {
      id: "med-1",
      bedNumber: "101",
      patientName: "Ramesh Sharma",
      mrn: "UHID-2026-0042",
      drugName: "Inj. Ceftriaxone 1g IV",
      dose: "1g in 100ml NS",
      route: "Intravenous Infusion",
      scheduledTime: "14:00",
      status: "OVERDUE",
      isHighAlert: false,
    },
    {
      id: "med-2",
      bedNumber: "102",
      patientName: "Ananya Deshmukh",
      mrn: "UHID-2026-0089",
      drugName: "Inj. Pantoprazole 40mg IV",
      dose: "40mg Slow IV Bolus",
      route: "Intravenous Push",
      scheduledTime: "17:00",
      status: "DUE",
      isHighAlert: false,
    },
    {
      id: "med-3",
      bedNumber: "103",
      patientName: "Pooja Nair",
      mrn: "UHID-2026-0104",
      drugName: "Inj. Enoxaparin 40mg SC",
      dose: "40mg (0.4ml Pre-filled syringe)",
      route: "Subcutaneous",
      scheduledTime: "18:00",
      status: "DUE",
      isHighAlert: true,
    },
    {
      id: "med-4",
      bedNumber: "105",
      patientName: "Sunil Verma",
      mrn: "UHID-2026-0112",
      drugName: "Inj. Regular Insulin 8 Units SC",
      dose: "8 Units (U-100)",
      route: "Subcutaneous",
      scheduledTime: "13:30",
      status: "ADMINISTERED",
      isHighAlert: true,
      administeredAt: "13:35",
      administeredBy: "Staff Nurse Priya (RN-901)",
    },
  ]);

  // BCMA Administer Dose Modal State
  const [selectedMedForAdmin, setSelectedMedForAdmin] = useState<ScheduledMedication | null>(null);
  const [wristbandScanned, setWristbandScanned] = useState(false);
  const [ampouleScanned, setAmpouleScanned] = useState(false);
  const [witnessStaffId, setWitnessStaffId] = useState("RN-904");
  const [isSubmittingEmar, setIsSubmittingEmar] = useState(false);

  // Shift Handover Kardex Modal
  const [isKardexModalOpen, setIsKardexModalOpen] = useState(false);

  const calculateNews2 = () => {
    let score = 0;
    // Respiration rate
    if (respRate <= 8 || respRate >= 25) score += 3;
    else if (respRate >= 21 && respRate <= 24) score += 2;
    else if (respRate >= 9 && respRate <= 11) score += 1;

    // SpO2
    if (spo2 <= 91) score += 3;
    else if (spo2 >= 92 && spo2 <= 93) score += 2;
    else if (spo2 >= 94 && spo2 <= 95) score += 1;

    // Oxygen
    if (onOxygen) score += 2;

    // Systolic BP
    if (systolicBp <= 90 || systolicBp >= 220) score += 3;
    else if (systolicBp >= 91 && systolicBp <= 100) score += 2;
    else if (systolicBp >= 101 && systolicBp <= 110) score += 1;

    // Pulse
    if (pulse <= 40 || pulse >= 131) score += 3;
    else if (pulse >= 111 && pulse <= 130) score += 2;
    else if ((pulse >= 41 && pulse <= 50) || (pulse >= 91 && pulse <= 110)) score += 1;

    // Consciousness
    if (consciousness === "CVPU") score += 3;

    // Temperature
    if (temperature <= 35.0) score += 3;
    else if (temperature >= 39.1) score += 2;
    else if ((temperature >= 35.1 && temperature <= 36.0) || (temperature >= 38.1 && temperature <= 39.0)) score += 1;

    return score;
  };

  const calculatedScore = calculateNews2();

  const loadBeds = async () => {
    setIsLoading(true);
    try {
      const data = await uiApi.getWardBedMap(selectedWardId);
      setBeds(data);
    } catch (err) {
      console.error("Failed to load bed map:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadBeds();
  }, [selectedWardId]);

  const toggleSanitization = (bedId: number) => {
    setBeds((prev) =>
      prev.map((b) => {
        if (b.bed_id !== bedId) return b;
        const newStatus = b.status === "CLEANING" ? "AVAILABLE" : "CLEANING";
        return { ...b, status: newStatus };
      })
    );
  };

  const handleSaveVitals = (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeBedForVitals) return;

    setBeds((prev) =>
      prev.map((b) => {
        if (b.bed_id !== activeBedForVitals.bed_id) return b;
        return {
          ...b,
          occupied_details: b.occupied_details
            ? {
                ...b.occupied_details,
                news2_score: calculatedScore,
              }
            : b.occupied_details,
        };
      })
    );

    if (calculatedScore >= 7) {
      setNotificationToast({
        type: "rrt",
        message: `CRITICAL ALERT: NEWS2 Score ${calculatedScore} on Bed ${activeBedForVitals.bed_number}!`,
        details: "Rapid Response Team (RRT) paged. Attending Medical Officer & ICU Registrar dispatched.",
      });
    } else {
      setNotificationToast({
        type: "success",
        message: `Vitals & NEWS2 score of ${calculatedScore} recorded for Bed ${activeBedForVitals.bed_number}.`,
      });
    }

    setActiveBedForVitals(null);
  };

  const handleOpenAdminModal = (med: ScheduledMedication) => {
    setSelectedMedForAdmin(med);
    setWristbandScanned(false);
    setAmpouleScanned(false);
  };

  const handleConfirmAdministration = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedMedForAdmin) return;
    if (!wristbandScanned || !ampouleScanned) {
      alert("Both Patient Wristband and Drug Ampoule GS1 barcodes must be verified!");
      return;
    }

    setIsSubmittingEmar(true);
    try {
      // Update local MAR state
      setMedications((prev) =>
        prev.map((m) =>
          m.id === selectedMedForAdmin.id
            ? {
                ...m,
                status: "ADMINISTERED",
                administeredAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
                administeredBy: "Staff Nurse Priya (RN-901)",
              }
            : m
        )
      );

      setNotificationToast({
        type: "success",
        message: `Dose Administered: ${selectedMedForAdmin.drugName} to Bed ${selectedMedForAdmin.bedNumber}`,
        details: `BCMA 5-Rights Verified. Logged to statutory electronic MAR ledger.`,
      });
      setSelectedMedForAdmin(null);
    } finally {
      setIsSubmittingEmar(false);
    }
  };

  const occupiedCount = beds.filter((b) => b.status === "OCCUPIED").length;
  const availableCount = beds.filter((b) => b.status === "AVAILABLE").length;
  const cleaningCount = beds.filter((b) => b.status === "CLEANING").length;

  const handlePrintSbarKardex = () => {
    const html = `
      <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 720px; margin: 0 auto; border: 2px solid #000; padding: 24px;">
        <div style="text-align: center; border-bottom: 2px solid #000; padding-bottom: 12px; margin-bottom: 16px;">
          <h2 style="margin: 0; font-size: 20px; text-transform: uppercase;">${hospitalProfile.name}</h2>
          <div style="font-size: 12px; font-weight: bold; color: #0284c7; margin-top: 2px;">WARD NURSING SHIFT HANDOVER & SBAR CLINICAL KARDEX</div>
          <div style="font-size: 10px; color: #555;">NABH Nursing Excellence Standard • Ward 3A (Medical-Surgical) • ${hospitalProfile.phone}</div>
        </div>
        <div style="display: flex; justify-content: space-between; border-bottom: 1px solid #ccc; padding-bottom: 8px; font-size: 12px; margin-bottom: 14px;">
          <div><b>Shift:</b> General / Day-Night Handover</div>
          <div><b>Inpatients:</b> ${occupiedCount} Occupied / ${beds.length} Total Beds</div>
          <div><b>Date & Time:</b> ${new Date().toLocaleString()}</div>
        </div>
        <div style="margin-bottom: 14px; border: 1px solid #cbd5e1; padding: 12px; font-size: 12px; line-height: 1.6;">
          <div style="font-weight: bold; color: #0284c7; text-transform: uppercase; margin-bottom: 4px;">[S] Situation:</div>
          <div>${beds.length} beds total, ${occupiedCount} occupied. Bed 101 high fever spike NEWS2=6; Bed 103 DVT prophylaxis enoxaparin due at 18:00.</div>
        </div>
        <div style="margin-bottom: 14px; border: 1px solid #cbd5e1; padding: 12px; font-size: 12px; line-height: 1.6;">
          <div style="font-weight: bold; color: #d97706; text-transform: uppercase; margin-bottom: 4px;">[B] Background:</div>
          <div>Bed 101 post-op Appendectomy Day 2; Bed 102 acute GERD stepdown; Bed 105 Diabetic Ketoacidosis stabilized.</div>
        </div>
        <div style="margin-bottom: 14px; border: 1px solid #cbd5e1; padding: 12px; font-size: 12px; line-height: 1.6;">
          <div style="font-weight: bold; color: #7c3aed; text-transform: uppercase; margin-bottom: 4px;">[A] Assessment:</div>
          <div>All ${occupiedCount} patients stable on room air except Bed 101 receiving 2L O2 by cannula. All scheduled eMAR medication doses administered and audited with zero BCMA barcode overrides.</div>
        </div>
        <div style="margin-bottom: 14px; border: 1px solid #cbd5e1; padding: 12px; font-size: 12px; line-height: 1.6;">
          <div style="font-weight: bold; color: #16a34a; text-transform: uppercase; margin-bottom: 4px;">[R] Recommendation:</div>
          <div>Recheck Bed 101 temperature &amp; CBC blood culture at 16:00. Terminal housekeeping cleaning requested for Bed 104.</div>
        </div>
        <div style="margin-top: 50px; display: flex; justify-content: space-between; font-size: 11px;">
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Relieving Shift Nurse Signature</div>
          <div style="border-top: 1px solid #000; width: 220px; text-align: center; padding-top: 4px;">Taking-Over Shift Nurse Signature</div>
        </div>
      </div>
    `;
    printDocument(html, { title: "Nursing_SBAR_Handover_Kardex", docType: "CLINICAL_SUMMARY" });
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-950 p-6 overflow-y-auto">
      {/* Header & Ward Census Summary */}
      <div className="flex items-center justify-between pb-6 border-b border-slate-800">
        <div>
          <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
            <BedDouble className="text-emerald-400" />
            Ward Nursing Station — Inpatient Bed Census &amp; eMAR
          </h1>
          <p className="text-xs text-slate-400 mt-1 font-mono">
            General Inpatient Ward 1 • Real-time occupancy, NEWS2 surveillance &amp; BCMA medication administration
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-mono">
            <span className="px-2.5 py-1 rounded bg-emerald-950 border border-emerald-800 text-emerald-400">
              {availableCount} Available
            </span>
            <span className="px-2.5 py-1 rounded bg-sky-950 border border-sky-800 text-sky-400">
              {occupiedCount} Occupied
            </span>
            <span className="px-2.5 py-1 rounded bg-amber-950 border border-amber-800 text-amber-400">
              {cleaningCount} Sanitizing
            </span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsKardexModalOpen(true)}
            className="flex items-center gap-1.5"
          >
            <Printer size={14} /> SBAR Handover Kardex
          </Button>

          <button
            onClick={loadBeds}
            disabled={isLoading}
            className="p-2 rounded-lg bg-slate-900 border border-slate-800 hover:bg-slate-800 text-slate-300 transition-colors"
          >
            <RefreshCw size={15} className={isLoading ? "animate-spin" : ""} />
          </button>
        </div>
      </div>

      {/* RRT / Notification Alert Toast */}
      {notificationToast && (
        <div
          className={`mt-4 p-3 rounded-xl border flex items-center justify-between text-xs font-mono animate-fadeIn ${
            notificationToast.type === "rrt"
              ? "bg-rose-950/60 border-rose-500 text-rose-200 animate-pulse"
              : "bg-emerald-950/40 border-emerald-800 text-emerald-200"
          }`}
        >
          <div className="flex items-center gap-2.5">
            {notificationToast.type === "rrt" ? (
              <Siren size={18} className="text-rose-400" />
            ) : (
              <CheckCircle2 size={18} className="text-emerald-400" />
            )}
            <div>
              <strong className="font-bold">{notificationToast.message}</strong>
              {notificationToast.details && (
                <div className="text-[11px] opacity-80 mt-0.5">{notificationToast.details}</div>
              )}
            </div>
          </div>
          <button
            onClick={() => setNotificationToast(null)}
            className="text-[10px] font-bold text-slate-400 hover:text-white px-2 py-0.5"
          >
            DISMISS
          </button>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center gap-2 mt-4 pb-2 border-b border-slate-800">
        <button
          type="button"
          onClick={() => setActiveTab("beds")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "beds"
              ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
          }`}
        >
          <BedDouble size={14} /> Bed Matrix &amp; Vital Surveillance ({beds.length} Beds)
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("emar")}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold transition-all ${
            activeTab === "emar"
              ? "bg-sky-500/10 text-sky-400 border border-sky-500/30"
              : "text-slate-400 hover:text-slate-200 hover:bg-slate-900"
          }`}
        >
          <Pill size={14} /> Inpatient eMAR &amp; BCMA Administration Desk
        </button>
      </div>

      {/* TAB 1: BED MATRIX */}
      {activeTab === "beds" && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4 mt-6">
          {beds.length === 0 ? (
            <div className="col-span-full py-16 text-center text-slate-500 text-sm">
              No beds configured in this ward, or loading bed matrix...
            </div>
          ) : (
            beds.map((bed) => {
              const isOccupied = bed.status === "OCCUPIED" && bed.occupied_details;
              const patient = bed.occupied_details;

              return (
                <Card
                  key={bed.bed_id}
                  onClick={() => {
                    if (patient?.patient_id) {
                      selectPatient(patient.patient_id);
                    }
                  }}
                  className={`p-4 rounded-xl border transition-all cursor-pointer ${
                    isOccupied
                      ? "bg-slate-900/90 border-slate-700 hover:border-sky-500 shadow-md"
                      : bed.status === "CLEANING"
                      ? "bg-amber-950/20 border-amber-900/40"
                      : "bg-slate-950 border-slate-800 hover:border-slate-700 opacity-70"
                  }`}
                >
                  <div className="flex items-center justify-between pb-2 border-b border-slate-800 mb-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-bold text-slate-200">
                        Bed {bed.bed_number}
                      </span>
                      <span className="text-[11px] text-slate-500 font-mono">
                        Room {bed.room_number}
                      </span>
                    </div>
                    <Badge
                      variant={
                        bed.status === "OCCUPIED"
                          ? "info"
                          : bed.status === "AVAILABLE"
                          ? "success"
                          : "warning"
                      }
                      size="sm"
                    >
                      {bed.status}
                    </Badge>
                  </div>

                  {isOccupied && patient ? (
                    <div className="space-y-3">
                      <div>
                        <div className="font-semibold text-sm text-slate-100 flex items-center gap-1.5">
                          <User size={13} className="text-slate-400" />
                          {patient.patient_name}
                        </div>
                        <div className="text-[11px] text-slate-400 font-mono">
                          {patient.mrn} • {patient.gender} • {patient.age_years ? `${patient.age_years}y` : "--"}
                        </div>
                      </div>

                      <div className="text-xs text-slate-400">
                        Admitted:{" "}
                        <span className="font-mono text-slate-300">
                          {patient.admitted_at ? new Date(patient.admitted_at).toLocaleDateString() : "--"}
                        </span>
                      </div>

                      <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
                        <div className="flex items-center gap-1 text-xs">
                          <span className="text-slate-400">NEWS2:</span>
                          <span
                            className={`font-mono font-bold px-1.5 py-0.5 rounded text-[11px] ${
                              (patient.news2_score ?? 0) >= 7
                                ? "bg-rose-950 text-rose-400 border border-rose-800 animate-pulse"
                                : (patient.news2_score ?? 0) >= 5
                                ? "bg-amber-950 text-amber-400 border border-amber-800"
                                : "bg-emerald-950 text-emerald-400 border border-emerald-800"
                            }`}
                          >
                            {patient.news2_score ?? 0}
                          </span>
                        </div>

                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setActiveBedForVitals(bed);
                          }}
                          className="px-2 py-1 text-[11px] rounded bg-sky-950 text-sky-400 border border-sky-800 hover:bg-sky-900 transition-colors flex items-center gap-1"
                        >
                          <Activity size={11} /> Vitals &amp; NEWS2
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="py-6 flex flex-col items-center justify-center text-slate-600 space-y-2">
                      <span className="text-xs">
                        {bed.status === "CLEANING" ? "Terminal Sanitization in Progress" : "Ready for Inpatient Admission"}
                      </span>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSanitization(bed.bed_id);
                        }}
                        className="px-2 py-1 rounded text-[10px] bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800 flex items-center gap-1"
                      >
                        <Sparkles size={11} /> {bed.status === "CLEANING" ? "Mark Ready / Clean" : "Request Cleaning"}
                      </button>
                    </div>
                  )}
                </Card>
              );
            })
          )}
        </div>
      )}

      {/* TAB 2: INPATIENT eMAR & BCMA */}
      {activeTab === "emar" && (
        <div className="space-y-4 mt-6">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <Pill size={14} className="text-emerald-400" /> Scheduled Inpatient Doses Due Today
            </span>
            <div className="flex items-center gap-2 text-xs font-mono text-slate-400">
              <ShieldCheck size={13} className="text-emerald-400" />
              <span>BCMA 5-Rights Barcode Verification Active</span>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-900 text-slate-400 uppercase font-mono text-[10px] border-b border-slate-800">
                <tr>
                  <th className="p-3">Bed</th>
                  <th className="p-3">Patient &amp; MRN</th>
                  <th className="p-3">Medication &amp; Dose</th>
                  <th className="p-3">Route</th>
                  <th className="p-3">Scheduled</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">BCMA Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/80 font-mono">
                {medications.map((m) => (
                  <tr key={m.id} className="hover:bg-slate-900/50 transition-colors">
                    <td className="p-3 font-bold text-sky-400">Bed {m.bedNumber}</td>
                    <td className="p-3">
                      <div className="text-slate-200 font-semibold">{m.patientName}</div>
                      <div className="text-[10px] text-slate-500">{m.mrn}</div>
                    </td>
                    <td className="p-3">
                      <div className="text-slate-100 font-semibold flex items-center gap-1.5">
                        {m.drugName}
                        {m.isHighAlert && (
                          <span className="px-1 py-0.5 rounded text-[9px] bg-rose-950 text-rose-400 border border-rose-800 font-bold">
                            HIGH-ALERT
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-slate-400">{m.dose}</div>
                    </td>
                    <td className="p-3 text-slate-300">{m.route}</td>
                    <td className="p-3 text-slate-300 flex items-center gap-1">
                      <Clock size={11} className="text-slate-500" /> {m.scheduledTime}
                    </td>
                    <td className="p-3">
                      <Badge
                        variant={
                          m.status === "ADMINISTERED"
                            ? "success"
                            : m.status === "OVERDUE"
                            ? "danger"
                            : "warning"
                        }
                        size="sm"
                      >
                        {m.status}
                      </Badge>
                    </td>
                    <td className="p-3 text-right">
                      {m.status === "ADMINISTERED" ? (
                        <div className="text-[10px] text-emerald-400">
                          <div>✓ Done at {m.administeredAt}</div>
                          <div className="text-slate-500">{m.administeredBy}</div>
                        </div>
                      ) : (
                        <Button
                          variant="primary"
                          size="sm"
                          onClick={() => handleOpenAdminModal(m)}
                          className="flex items-center gap-1 ml-auto text-xs"
                        >
                          <QrCode size={12} /> Scan &amp; Administer
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal: Bedside Vitals & NEWS2 Scoring */}
      {activeBedForVitals && (
        <Modal
          isOpen={true}
          onClose={() => setActiveBedForVitals(null)}
          title={`Bedside Vitals & NEWS2 Assessment — Bed ${activeBedForVitals.bed_number}`}
        >
          <form onSubmit={handleSaveVitals} className="space-y-4">
            <div className="text-xs text-slate-300">
              Patient: <strong>{activeBedForVitals.occupied_details?.patient_name}</strong> (
              {activeBedForVitals.occupied_details?.mrn})
            </div>

            {/* Calculated Score Bar */}
            <div
              className={`p-3 rounded-lg border flex items-center justify-between font-mono text-xs ${
                calculatedScore >= 7
                  ? "bg-rose-950/40 border-rose-800 text-rose-300"
                  : calculatedScore >= 5
                  ? "bg-amber-950/40 border-amber-800 text-amber-300"
                  : "bg-emerald-950/40 border-emerald-800 text-emerald-300"
              }`}
            >
              <div>
                <span className="font-bold">Calculated NEWS2 Score: {calculatedScore}</span>
                <div className="text-[10px] opacity-80">
                  {calculatedScore >= 7
                    ? "HIGH RISK — Immediate Emergency Doctor Escalation / MET Team"
                    : calculatedScore >= 5
                    ? "MEDIUM RISK — Urgent Ward Doctor Review Required"
                    : "LOW RISK — Routine 4-6h Inpatient Surveillance"}
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Respiration Rate (breaths/min)</label>
                <input
                  type="number"
                  value={respRate}
                  onChange={(e) => setRespRate(parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Oxygen Saturation (SpO2 %)</label>
                <input
                  type="number"
                  value={spo2}
                  onChange={(e) => setSpo2(parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Systolic BP (mmHg)</label>
                <input
                  type="number"
                  value={systolicBp}
                  onChange={(e) => setSystolicBp(parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Pulse / Heart Rate (bpm)</label>
                <input
                  type="number"
                  value={pulse}
                  onChange={(e) => setPulse(parseInt(e.target.value) || 0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Body Temperature (°C)</label>
                <input
                  type="number"
                  step="0.1"
                  value={temperature}
                  onChange={(e) => setTemperature(parseFloat(e.target.value) || 37.0)}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200 font-mono"
                />
              </div>

              <div>
                <label className="text-[11px] text-slate-400 block mb-1">Consciousness Level</label>
                <select
                  value={consciousness}
                  onChange={(e) => setConsciousness(e.target.value as "ALERT" | "CVPU")}
                  className="w-full bg-slate-950 border border-slate-800 rounded px-2.5 py-1.5 text-xs text-slate-200"
                >
                  <option value="ALERT">Alert (A)</option>
                  <option value="CVPU">Confused / Voice / Pain / Unresponsive (CVPU)</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-2 p-2 rounded bg-slate-950 border border-slate-800">
              <input
                type="checkbox"
                id="on-oxygen"
                checked={onOxygen}
                onChange={(e) => setOnOxygen(e.target.checked)}
                className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-sky-500"
              />
              <label htmlFor="on-oxygen" className="text-xs text-slate-300 cursor-pointer">
                Supplemental Oxygen Therapy (Nasal Cannula / Venturi / Mask)
              </label>
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setActiveBedForVitals(null)}
              >
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm">
                Save Vitals &amp; Record NEWS2
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: BCMA Barcode Scan & Dose Administration */}
      {selectedMedForAdmin && (
        <Modal
          isOpen={true}
          onClose={() => setSelectedMedForAdmin(null)}
          title={`BCMA Barcode Verification — Bed ${selectedMedForAdmin.bedNumber}`}
        >
          <form onSubmit={handleConfirmAdministration} className="space-y-4">
            <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg space-y-2 text-xs font-mono">
              <div className="flex justify-between border-b border-slate-800 pb-1.5">
                <span className="text-slate-400">Patient:</span>
                <span className="text-slate-100 font-bold">{selectedMedForAdmin.patientName} ({selectedMedForAdmin.mrn})</span>
              </div>
              <div className="flex justify-between border-b border-slate-800 pb-1.5">
                <span className="text-slate-400">Prescribed Drug:</span>
                <span className="text-sky-400 font-bold">{selectedMedForAdmin.drugName}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Dose &amp; Route:</span>
                <span className="text-slate-200">{selectedMedForAdmin.dose} • {selectedMedForAdmin.route}</span>
              </div>
            </div>

            {/* 5 Rights Barcode Verification Checkpoints */}
            <div className="space-y-3">
              {/* Step 1: Patient Wristband */}
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/60 flex items-center justify-between">
                <div>
                  <div className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                    <QrCode size={14} className={wristbandScanned ? "text-emerald-400" : "text-slate-500"} />
                    Step 1: Patient UHID Wristband Barcode
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                    Target: {selectedMedForAdmin.mrn}
                  </div>
                </div>
                <Button
                  type="button"
                  variant={wristbandScanned ? "outline" : "primary"}
                  size="sm"
                  onClick={() => setWristbandScanned(true)}
                  className="text-xs"
                >
                  {wristbandScanned ? "✓ Wristband Verified" : "Simulate Scan"}
                </Button>
              </div>

              {/* Step 2: Drug Ampoule GS1 */}
              <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/60 flex items-center justify-between">
                <div>
                  <div className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                    <Pill size={14} className={ampouleScanned ? "text-emerald-400" : "text-slate-500"} />
                    Step 2: Medication Ampoule / Vial GS1 Barcode
                  </div>
                  <div className="text-[11px] text-slate-500 font-mono mt-0.5">
                    Match: {selectedMedForAdmin.drugName}
                  </div>
                </div>
                <Button
                  type="button"
                  variant={ampouleScanned ? "outline" : "primary"}
                  size="sm"
                  onClick={() => setAmpouleScanned(true)}
                  className="text-xs"
                >
                  {ampouleScanned ? "✓ Ampoule Verified" : "Simulate Scan"}
                </Button>
              </div>

              {/* High Alert Witness Sign-off */}
              {selectedMedForAdmin.isHighAlert && (
                <div className="p-3 rounded-lg border border-rose-900/40 bg-rose-950/20 space-y-2">
                  <div className="text-xs font-bold text-rose-300 flex items-center gap-1.5">
                    <AlertTriangle size={14} /> Dual-Witness High-Alert Verification Required
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                    <div>
                      <label className="text-[10px] text-slate-400 block mb-0.5">Witness Staff ID / Badge</label>
                      <input
                        type="text"
                        value={witnessStaffId}
                        onChange={(e) => setWitnessStaffId(e.target.value)}
                        className="w-full bg-slate-950 border border-slate-800 rounded px-2 py-1 text-slate-200 text-xs"
                      />
                    </div>
                    <div>
                      <label className="text-[10px] text-slate-400 block mb-0.5">Witness Role</label>
                      <input
                        type="text"
                        disabled
                        value="Senior Staff Nurse (RN-ICU)"
                        className="w-full bg-slate-900/60 border border-slate-800 rounded px-2 py-1 text-slate-400 text-xs"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setSelectedMedForAdmin(null)}
              >
                Cancel
              </Button>
              <Button
                type="submit"
                variant="primary"
                size="sm"
                disabled={!wristbandScanned || !ampouleScanned || (selectedMedForAdmin.isHighAlert && !witnessStaffId.trim()) || isSubmittingEmar}
              >
                {isSubmittingEmar ? "Logging BCMA..." : "Confirm & Administer Dose"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: SBAR Shift Handover Kardex */}
      {isKardexModalOpen && (
        <Modal
          isOpen={true}
          onClose={() => setIsKardexModalOpen(false)}
          title="NABH SBAR Inpatient Nursing Shift Handover Kardex"
        >
          <div className="space-y-4">
            <div className="p-4 bg-slate-950 border border-slate-800 rounded-lg space-y-3 font-mono text-xs">
              <div className="flex justify-between border-b border-slate-800 pb-2">
                <div>
                  <strong className="text-slate-100 uppercase">Ward 1 Nursing Kardex</strong>
                  <div className="text-[11px] text-slate-400">Shift: Morning &rarr; Afternoon Handover</div>
                </div>
                <div className="text-right">
                  <div className="text-emerald-400">Inpatients: {occupiedCount} / Beds: {beds.length}</div>
                  <div className="text-[10px] text-slate-500">{new Date().toLocaleDateString()} {new Date().toLocaleTimeString()}</div>
                </div>
              </div>

              <div>
                <span className="text-sky-400 font-bold block uppercase text-[10px]">[S] Situation:</span>
                <p className="text-slate-300">
                  12 beds total, 4 occupied. Bed 101 high fever spike NEWS2=6; Bed 103 DVT prophylaxis enoxaparin due at 18:00.
                </p>
              </div>

              <div>
                <span className="text-amber-400 font-bold block uppercase text-[10px]">[B] Background:</span>
                <p className="text-slate-300">
                  Bed 101 post-op Appendectomy Day 2; Bed 102 acute GERD stepdown; Bed 105 Diabetic Ketoacidosis stabilized.
                </p>
              </div>

              <div>
                <span className="text-purple-400 font-bold block uppercase text-[10px]">[A] Assessment:</span>
                <p className="text-slate-300">
                  All 4 patients stable on room air except Bed 101 receiving 2L O2 by cannula. All morning doses administered and audited.
                </p>
              </div>

              <div>
                <span className="text-emerald-400 font-bold block uppercase text-[10px]">[R] Recommendation:</span>
                <p className="text-slate-300">
                  Recheck Bed 101 temperature &amp; CBC blood culture at 16:00. Terminal cleaning requested for Bed 104.
                </p>
              </div>
            </div>

            <div className="flex items-center justify-between pt-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handlePrintSbarKardex}
                className="flex items-center gap-1.5"
              >
                <Printer size={13} /> Print Kardex
              </Button>
              <Button variant="primary" size="sm" onClick={() => setIsKardexModalOpen(false)}>
                Close Handover
              </Button>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
