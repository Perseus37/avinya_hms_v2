import React, { useState, useEffect } from "react";
import {
  UserPlus,
  Search,
  Printer,
  MapPin,
  ShieldCheck,
  Stethoscope,
  RefreshCw,
  User,
  Edit3,
  Clock,
  Sparkles,
} from "lucide-react";
import { Card } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Modal } from "../../components/ui/Modal";
import { patientApi, PatientCreatedResponse } from "../../api/patientApi";
import { useActivePatient } from "../../core/context/ActivePatientContext";

interface OpdDoctor {
  id: string;
  name: string;
  specialty: string;
  department: string;
  roomNumber: string;
  consultationFee: number;
  currentWaitMins: number;
  patientsWaiting: number;
}

const OPD_DOCTOR_ROSTER: OpdDoctor[] = [
  { id: "doc-1", name: "Dr. Vikram Seth", specialty: "Interventional Cardiology", department: "Cardiology", roomNumber: "OPD Cabin 204", consultationFee: 800, currentWaitMins: 15, patientsWaiting: 4 },
  { id: "doc-2", name: "Dr. Rajesh Sharma", specialty: "Internal Medicine", department: "General Medicine", roomNumber: "OPD Cabin 102", consultationFee: 500, currentWaitMins: 10, patientsWaiting: 6 },
  { id: "doc-3", name: "Dr. Radhika Sen", specialty: "General & Laparoscopic Surgery", department: "General Surgery", roomNumber: "OPD Cabin 210", consultationFee: 800, currentWaitMins: 20, patientsWaiting: 3 },
  { id: "doc-4", name: "Dr. Sunita Rao", specialty: "Pediatrics & Neonatology", department: "Pediatrics", roomNumber: "OPD Cabin 105", consultationFee: 600, currentWaitMins: 5, patientsWaiting: 2 },
  { id: "doc-5", name: "Dr. Harish Patel", specialty: "Orthopedics & Joint Replacement", department: "Orthopedics", roomNumber: "OPD Cabin 215", consultationFee: 700, currentWaitMins: 25, patientsWaiting: 5 },
  { id: "doc-6", name: "Dr. Anjali Nair", specialty: "Obstetrics & Gynecology", department: "Obstetrics & Gynecology", roomNumber: "OPD Cabin 112", consultationFee: 750, currentWaitMins: 12, patientsWaiting: 3 },
  { id: "doc-7", name: "Dr. Sameer Joshi", specialty: "Critical Care & Pulmonology", department: "Pulmonology", roomNumber: "OPD Cabin 208", consultationFee: 750, currentWaitMins: 18, patientsWaiting: 4 },
];

interface GeneratedTokenDetails {
  tokenNumber: number;
  tokenCode: string;
  department: string;
  doctorName: string;
  roomNumber: string;
  consultationFee: number;
  paymentMode: string;
  priority: string;
  issuedAt: string;
  estimatedWaitMins: number;
  receiptNumber: string;
}

export const PatientRegistrationWorkspace: React.FC = () => {
  const { selectPatient } = useActivePatient();
  const [isLoading, setIsLoading] = useState(false);
  const [successPatient, setSuccessPatient] = useState<PatientCreatedResponse | null>(null);
  const [isSuccessModalOpen, setIsSuccessModalOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  // Recent patients list
  const [recentPatients, setRecentPatients] = useState<PatientCreatedResponse[]>([]);
  const [searchTerm, setSearchTerm] = useState("");

  // Form Fields
  const [fullName, setFullName] = useState("");
  const [gender, setGender] = useState<"MALE" | "FEMALE" | "OTHER">("MALE");
  const [dob, setDob] = useState("1995-05-15");
  const [ageYears, setAgeYears] = useState("31");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [bloodGroup, setBloodGroup] = useState<"A+" | "A-" | "B+" | "B-" | "AB+" | "AB-" | "O+" | "O-">("O+");
  const [abhaNumber, setAbhaNumber] = useState("");
  
  // Address
  const [address, setAddress] = useState("");
  const [pincode, setPincode] = useState("");
  const [city, setCity] = useState("");
  const [district, setDistrict] = useState("");
  const [state, setState] = useState("");
  const [isPincodeLoading, setIsPincodeLoading] = useState(false);

  // Emergency Contact
  const [emergencyName, setEmergencyName] = useState("");
  const [emergencyPhone, setEmergencyPhone] = useState("");

  // DPDP Consent Checkboxes
  const [consentTreatment, setConsentTreatment] = useState(true);
  const [consentTelehealth, setConsentTelehealth] = useState(true);
  const [consentInsurance, setConsentInsurance] = useState(true);

  // Instant OPD Consultation Token & Appointment Booking
  const [bookOpdConsult, setBookOpdConsult] = useState(true);
  const [selectedDept, setSelectedDept] = useState("General Medicine");
  const [selectedDoctorId, setSelectedDoctorId] = useState("doc-2");
  const [consultationType, setConsultationType] = useState<"NEW" | "FOLLOWUP" | "SECOND_OPINION">("NEW");
  const [priority, setPriority] = useState<"NORMAL" | "SENIOR_CITIZEN" | "EMERGENCY">("NORMAL");
  const [paymentMode, setPaymentMode] = useState<"CASH" | "UPI" | "CARD" | "PMJAY">("UPI");
  const [generatedToken, setGeneratedToken] = useState<GeneratedTokenDetails | null>(null);
  const [printDocType, setPrintDocType] = useState<"WRISTBAND" | "OPD_TOKEN">("OPD_TOKEN");

  // Edit Demographic Profile Modal State
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editingPatient, setEditingPatient] = useState<PatientCreatedResponse | null>(null);
  const [editFullName, setEditFullName] = useState("");
  const [editPhone, setEditPhone] = useState("");
  const [editBloodGroup, setEditBloodGroup] = useState<string>("O+");
  const [editAddress, setEditAddress] = useState("");
  const [editPincode, setEditPincode] = useState("");
  const [editCity, setEditCity] = useState("");
  const [editState, setEditState] = useState("");
  const [editEmergencyName, setEditEmergencyName] = useState("");
  const [editEmergencyPhone, setEditEmergencyPhone] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);

  const handleOpenEdit = (patient: PatientCreatedResponse, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingPatient(patient);
    setEditFullName(patient.full_name);
    setEditPhone(patient.phone_number || "");
    setEditBloodGroup(patient.blood_group || "O+");
    setEditAddress(patient.address || "");
    setEditPincode(patient.pincode || "");
    setEditCity(patient.city || "");
    setEditState(patient.state || "");
    setEditEmergencyName("");
    setEditEmergencyPhone("");
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPatient) return;
    setIsUpdating(true);
    try {
      const updated = await patientApi.updatePatient(editingPatient.id, {
        full_name: editFullName,
        phone_number: editPhone,
        blood_group: editBloodGroup as any,
        address: editAddress,
        pincode: editPincode || undefined,
        city: editCity,
        state: editState,
        emergency_contact_name: editEmergencyName || undefined,
        emergency_contact_phone: editEmergencyPhone || undefined,
      });
      setIsEditModalOpen(false);
      setEditingPatient(null);
      await loadRecentPatients();
      selectPatient(updated.id);
    } catch (err: unknown) {
      if (err instanceof Error) {
        alert(`Update failed: ${err.message}`);
      } else {
        alert("Update failed. Please check inputs.");
      }
    } finally {
      setIsUpdating(false);
    }
  };

  // Synchronize DOB and Age
  const handleAgeChange = (ageStr: string) => {
    setAgeYears(ageStr);
    const age = parseInt(ageStr, 10);
    if (!isNaN(age) && age >= 0 && age < 125) {
      const year = new Date().getFullYear() - age;
      setDob(`${year}-01-01`);
    }
  };

  const handleDobChange = (dobStr: string) => {
    setDob(dobStr);
    const birthDate = new Date(dobStr);
    if (!isNaN(birthDate.getTime())) {
      const today = new Date();
      let age = today.getFullYear() - birthDate.getFullYear();
      const m = today.getMonth() - birthDate.getMonth();
      if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
        age--;
      }
      setAgeYears(Math.max(0, age).toString());
    }
  };

  const lookupPincode = async () => {
    if (!pincode || pincode.length !== 6) return;
    setIsPincodeLoading(true);
    try {
      const res = await patientApi.getPincodeSuggestions(pincode);
      if (res.suggestions && res.suggestions.length > 0) {
        const first = res.suggestions[0];
        setCity(first.division || first.region || "");
        setDistrict(first.district || "");
        setState(first.state || "");
      }
    } catch (err) {
      console.warn("Pincode lookup fallback:", err);
    } finally {
      setIsPincodeLoading(false);
    }
  };

  const loadRecentPatients = async () => {
    try {
      const res = await patientApi.listPatients(searchTerm || undefined);
      if (res.items) {
        setRecentPatients(res.items);
      }
    } catch {
      // Fallback sample patients
      setRecentPatients([
        {
          id: 1,
          mrn: "MRN-2026-0001",
          full_name: "Siddharth Verma",
          date_of_birth: "1988-04-12T00:00:00Z",
          gender: "MALE",
          phone_number: "9876543210",
          blood_group: "B+",
          city: "Hyderabad",
          state: "Telangana",
        },
        {
          id: 2,
          mrn: "MRN-2026-0002",
          full_name: "Ananya Deshmukh",
          date_of_birth: "1994-09-20T00:00:00Z",
          gender: "FEMALE",
          phone_number: "9123456780",
          blood_group: "O+",
          city: "Hyderabad",
          state: "Telangana",
        },
      ]);
    }
  };

  useEffect(() => {
    loadRecentPatients();
  }, [searchTerm]);

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage("");
    setIsLoading(true);

    try {
      const isoDob = new Date(dob).toISOString();
      const patient = await patientApi.createPatient({
        full_name: fullName,
        gender,
        date_of_birth: isoDob,
        phone_number: phone || "9999999999",
        email: email || undefined,
        blood_group: bloodGroup,
        abha_number: abhaNumber || undefined,
        address: address || undefined,
        pincode: pincode || undefined,
        city: city || undefined,
        district: district || undefined,
        state: state || undefined,
        emergency_contact_name: emergencyName || undefined,
        emergency_contact_phone: emergencyPhone || undefined,
        allow_network_sharing: consentInsurance,
      });

      setSuccessPatient(patient);

      if (bookOpdConsult) {
        const chosenDoc = OPD_DOCTOR_ROSTER.find((d) => d.id === selectedDoctorId) || OPD_DOCTOR_ROSTER[0];
        const tokenNum = Math.floor(Math.random() * 15) + 10;
        const deptPrefix = chosenDoc.department.slice(0, 3).toUpperCase();
        const tokenCode = `${deptPrefix}-${String(tokenNum).padStart(3, "0")}`;
        const fee = consultationType === "FOLLOWUP" ? 0 : chosenDoc.consultationFee;
        const priorityLabels = {
          NORMAL: "Standard Walk-in",
          SENIOR_CITIZEN: "Senior Citizen (Priority)",
          EMERGENCY: "Urgent Fast-Track",
        };

        const tokenDetails: GeneratedTokenDetails = {
          tokenNumber: tokenNum,
          tokenCode,
          department: chosenDoc.department,
          doctorName: chosenDoc.name,
          roomNumber: chosenDoc.roomNumber,
          consultationFee: fee,
          paymentMode: fee === 0 ? "Complimentary Follow-up" : paymentMode,
          priority: priorityLabels[priority],
          issuedAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          estimatedWaitMins: chosenDoc.currentWaitMins + 5,
          receiptNumber: `REC-${new Date().getFullYear()}-${Math.floor(100000 + Math.random() * 900000)}`,
        };
        setGeneratedToken(tokenDetails);
        setPrintDocType("OPD_TOKEN");
      } else {
        setGeneratedToken(null);
        setPrintDocType("WRISTBAND");
      }

      setIsSuccessModalOpen(true);
      selectPatient(patient.id);

      // Reset form
      setFullName("");
      setPhone("");
      setEmail("");
      setAddress("");
      setPincode("");
      setCity("");
      setAbhaNumber("");
      setEmergencyName("");
      setEmergencyPhone("");

      loadRecentPatients();
    } catch (err: unknown) {
      if (err instanceof Error) {
        setErrorMessage(err.message);
      } else {
        setErrorMessage("Registration failed. Please check required fields.");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex-1 flex overflow-hidden bg-slate-950">
      {/* Left Column: Comprehensive Registration Form */}
      <div className="flex-1 flex flex-col p-6 overflow-y-auto border-r border-slate-800">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800 mb-6">
          <div>
            <h1 className="text-xl font-bold text-slate-100 flex items-center gap-2">
              <UserPlus className="text-sky-400" />
              Patient Registration & Front Desk Intake
            </h1>
            <p className="text-xs text-slate-400 mt-0.5 font-mono">
              Master Patient Index (MPI) • ABHA Integration • Fast-Track Demographic Registration
            </p>
          </div>
        </div>

        {errorMessage && (
          <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-900/60 text-xs text-rose-300 font-mono mb-4">
            {errorMessage}
          </div>
        )}

        <form onSubmit={handleFormSubmit} className="space-y-6 max-w-4xl">
          {/* Section 1: Core Demographics */}
          <Card className="p-4 bg-slate-900/70 border-slate-800 space-y-4">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <User size={14} className="text-sky-400" /> 1. Primary Demographics
            </h2>

            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2">
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Full Legal Name <span className="text-rose-500">*</span>
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Ramesh Chandra Sharma"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Gender <span className="text-rose-500">*</span>
                </label>
                <select
                  value={gender}
                  onChange={(e) => setGender(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                >
                  <option value="MALE">Male</option>
                  <option value="FEMALE">Female</option>
                  <option value="OTHER">Other / Transgender</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Date of Birth <span className="text-rose-500">*</span>
                </label>
                <input
                  type="date"
                  required
                  value={dob}
                  onChange={(e) => handleDobChange(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Age (Years)</label>
                <input
                  type="number"
                  min="0"
                  max="125"
                  value={ageYears}
                  onChange={(e) => handleAgeChange(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Blood Group</label>
                <select
                  value={bloodGroup}
                  onChange={(e) => setBloodGroup(e.target.value as any)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                >
                  <option value="A+">A Positive (A+)</option>
                  <option value="A-">A Negative (A-)</option>
                  <option value="B+">B Positive (B+)</option>
                  <option value="B-">B Negative (B-)</option>
                  <option value="AB+">AB Positive (AB+)</option>
                  <option value="AB-">AB Negative (AB-)</option>
                  <option value="O+">O Positive (O+)</option>
                  <option value="O-">O Negative (O-)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Primary Mobile #</label>
                <input
                  type="tel"
                  placeholder="10-digit mobile"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  maxLength={10}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Email Address</label>
                <input
                  type="email"
                  placeholder="patient@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  ABHA ID (Ayushman Bharat Digital Mission)
                </label>
                <input
                  type="text"
                  placeholder="14-digit ABHA (e.g. 91-4821-9921-0021)"
                  value={abhaNumber}
                  onChange={(e) => setAbhaNumber(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>
          </Card>

          {/* Section 2: Residential Address & PIN Code Auto-Fill */}
          <Card className="p-4 bg-slate-900/70 border-slate-800 space-y-4">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <MapPin size={14} className="text-emerald-400" /> 2. Address & Residence
            </h2>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Residential Street Address</label>
              <input
                type="text"
                placeholder="House #, Street name, Landmark, Colony"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div className="grid grid-cols-4 gap-4">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-semibold text-slate-300">PIN Code</label>
                  <button
                    type="button"
                    onClick={lookupPincode}
                    className="text-[10px] text-sky-400 hover:underline flex items-center gap-0.5"
                  >
                    <RefreshCw size={9} className={isPincodeLoading ? "animate-spin" : ""} /> Lookup
                  </button>
                </div>
                <input
                  type="text"
                  maxLength={6}
                  placeholder="6-digit PIN"
                  value={pincode}
                  onChange={(e) => setPincode(e.target.value)}
                  onBlur={lookupPincode}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">City / Town</label>
                <input
                  type="text"
                  placeholder="City"
                  value={city}
                  onChange={(e) => setCity(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">District</label>
                <input
                  type="text"
                  placeholder="District"
                  value={district}
                  onChange={(e) => setDistrict(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">State</label>
                <input
                  type="text"
                  placeholder="State"
                  value={state}
                  onChange={(e) => setState(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>
          </Card>

          {/* Section 3: Emergency Contact & DPDP Consent */}
          <Card className="p-4 bg-slate-900/70 border-slate-800 space-y-4">
            <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
              <ShieldCheck size={14} className="text-amber-400" /> 3. Emergency Contact & DPDP Consents
            </h2>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Emergency Contact Person</label>
                <input
                  type="text"
                  placeholder="Full Name (Next of Kin)"
                  value={emergencyName}
                  onChange={(e) => setEmergencyName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Emergency Contact Phone</label>
                <input
                  type="tel"
                  placeholder="10-digit mobile"
                  value={emergencyPhone}
                  onChange={(e) => setEmergencyPhone(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2.5 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>

            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
              <div className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">
                DPDP Act 2023 Statutory Consent Grants
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="consent-med"
                  checked={consentTreatment}
                  onChange={(e) => setConsentTreatment(e.target.checked)}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-sky-500"
                />
                <label htmlFor="consent-med" className="text-xs text-slate-300 cursor-pointer">
                  Consent for Medical Treatment, Clinical Diagnostics, and Electronic Medical Record (EMR) retention.
                </label>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="consent-tele"
                  checked={consentTelehealth}
                  onChange={(e) => setConsentTelehealth(e.target.checked)}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-sky-500"
                />
                <label htmlFor="consent-tele" className="text-xs text-slate-300 cursor-pointer">
                  Consent for Telemedicine consultations and SMS/WhatsApp appointment notifications.
                </label>
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="consent-ins"
                  checked={consentInsurance}
                  onChange={(e) => setConsentInsurance(e.target.checked)}
                  className="rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-sky-500"
                />
                <label htmlFor="consent-ins" className="text-xs text-slate-300 cursor-pointer">
                  Consent to share relevant clinical summaries with TPA Insurance providers for cashless claims.
                </label>
              </div>
            </div>
          </Card>

          {/* Section 4: Fast-Track OPD Consultation & Token Issuance */}
          <Card className="p-4 bg-sky-950/20 border-sky-800/60 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-sky-900/40">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  id="book-opd"
                  checked={bookOpdConsult}
                  onChange={(e) => setBookOpdConsult(e.target.checked)}
                  className="h-4 w-4 rounded bg-slate-900 border-slate-700 text-sky-500 focus:ring-sky-500 cursor-pointer"
                />
                <div>
                  <label htmlFor="book-opd" className="text-xs font-bold text-sky-300 cursor-pointer flex items-center gap-1.5">
                    <Stethoscope size={15} /> Fast-Track: Issue OPD Consultation Token & Book Appointment
                  </label>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Combines patient registration with instant OPD clinic routing. Avoids redundant navigation between front desk & booking desk.
                  </p>
                </div>
              </div>

              {bookOpdConsult && (
                <span className="px-2.5 py-1 rounded bg-sky-900/40 text-sky-300 border border-sky-700/60 font-mono text-[11px] font-semibold flex items-center gap-1">
                  <Sparkles size={12} className="text-sky-400" /> Instant Token Generator Active
                </span>
              )}
            </div>

            {bookOpdConsult && (
              <div className="space-y-4 pt-1">
                {/* Department Selection */}
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Select Clinical Specialty / Department
                  </label>
                  <div className="grid grid-cols-4 gap-2">
                    {[
                      "General Medicine",
                      "Cardiology",
                      "Orthopedics",
                      "Pediatrics",
                      "General Surgery",
                      "Obstetrics & Gynecology",
                      "Pulmonology",
                    ].map((dept) => {
                      const isSelected = selectedDept === dept;
                      return (
                        <button
                          key={dept}
                          type="button"
                          onClick={() => {
                            setSelectedDept(dept);
                            const matchingDoc = OPD_DOCTOR_ROSTER.find((d) => d.department === dept);
                            if (matchingDoc) setSelectedDoctorId(matchingDoc.id);
                          }}
                          className={`p-2 rounded-lg text-xs font-semibold text-left transition-all border ${
                            isSelected
                              ? "bg-sky-500/20 text-sky-300 border-sky-500/60 shadow-sm"
                              : "bg-slate-950/80 text-slate-400 border-slate-800 hover:text-slate-200 hover:border-slate-700"
                          }`}
                        >
                          {dept}
                        </button>
                      );
                    })}
                  </div>
                </div>

                {/* Attending Doctor Selection */}
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Select Attending Consultant & Clinic Room
                  </label>
                  <div className="grid grid-cols-2 gap-2.5">
                    {OPD_DOCTOR_ROSTER.filter((d) => d.department === selectedDept || selectedDept === "ALL").map((doc) => {
                      const isSelected = selectedDoctorId === doc.id;
                      return (
                        <div
                          key={doc.id}
                          onClick={() => setSelectedDoctorId(doc.id)}
                          className={`p-3 rounded-xl border cursor-pointer transition-all ${
                            isSelected
                              ? "bg-sky-950/80 border-sky-400 ring-2 ring-sky-500/40 shadow-md"
                              : "bg-slate-950 border-slate-800 hover:border-slate-700"
                          }`}
                        >
                          <div className="flex items-center justify-between mb-1">
                            <span className="font-bold text-xs text-slate-100">{doc.name}</span>
                            <span className="font-mono text-xs font-bold text-emerald-400">₹{doc.consultationFee}</span>
                          </div>
                          <div className="text-[11px] text-slate-400">{doc.specialty}</div>
                          <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono mt-2 pt-1.5 border-t border-slate-800/80">
                            <span className="text-sky-300 font-semibold">{doc.roomNumber}</span>
                            <span className="flex items-center gap-1 text-amber-400">
                              <Clock size={10} /> ~{doc.currentWaitMins}m wait ({doc.patientsWaiting} in queue)
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Consultation Type, Priority, and Payment Details */}
                <div className="grid grid-cols-3 gap-3 pt-2 border-t border-sky-900/30">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Visit Type</label>
                    <select
                      value={consultationType}
                      onChange={(e) => setConsultationType(e.target.value as any)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                    >
                      <option value="NEW">New Consultation</option>
                      <option value="FOLLOWUP">Follow-up Review (Within 7 Days - Free)</option>
                      <option value="SECOND_OPINION">Second Clinical Opinion</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Queue Priority</label>
                    <select
                      value={priority}
                      onChange={(e) => setPriority(e.target.value as any)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                    >
                      <option value="NORMAL">Normal Walk-in</option>
                      <option value="SENIOR_CITIZEN">Senior Citizen (Priority Call)</option>
                      <option value="EMERGENCY">Urgent Fast-Track Triage</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Consultation Fee Payment</label>
                    <select
                      value={paymentMode}
                      onChange={(e) => setPaymentMode(e.target.value as any)}
                      className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                    >
                      <option value="UPI">UPI / Instant QR Code</option>
                      <option value="CASH">Cash at Front Desk</option>
                      <option value="CARD">Debit / Credit POS Card</option>
                      <option value="PMJAY">PMJAY / Ayushman Bharat Cashless</option>
                    </select>
                  </div>
                </div>
              </div>
            )}
          </Card>

          <div className="flex items-center justify-end gap-3 pt-2">
            <Button
              type="submit"
              variant="primary"
              size="lg"
              disabled={isLoading}
              className="flex items-center gap-2 font-bold px-6"
            >
              <UserPlus size={16} /> {isLoading ? "Registering Patient..." : "Register Patient & Generate UHID"}
            </Button>
          </div>
        </form>
      </div>

      {/* Right Column: Recent Registrations & Quick Search */}
      <div className="w-96 flex flex-col bg-slate-900/40 p-4 border-l border-slate-800 overflow-hidden">
        <div className="mb-4">
          <h2 className="text-xs font-bold text-slate-300 uppercase tracking-wider mb-2">
            Registered Patients Directory
          </h2>
          <div className="relative">
            <Search size={14} className="absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search by name, MRN, mobile..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto space-y-2 pr-1">
          {recentPatients.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs">No registered patients found.</div>
          ) : (
            recentPatients.map((p) => (
              <Card
                key={p.id}
                onClick={() => selectPatient(p.id)}
                className="p-3 bg-slate-900 border-slate-800 hover:border-sky-500/50 cursor-pointer transition-all shadow-sm"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="font-semibold text-xs text-slate-200">{p.full_name}</span>
                  <span className="font-mono text-[10px] text-sky-400 bg-sky-950 px-1.5 py-0.5 rounded border border-sky-800/60">
                    {p.mrn}
                  </span>
                </div>
                <div className="text-[11px] text-slate-400 font-mono">
                  {p.gender} • {p.phone_number || "--"}
                </div>
                <div className="flex items-center justify-between text-[10px] text-slate-500 mt-1.5 pt-1.5 border-t border-slate-800/60">
                  <span>Blood: {p.blood_group || "--"}</span>
                  <div className="flex items-center gap-2">
                    <span>{p.city ? `${p.city}, ${p.state}` : ""}</span>
                    <button
                      type="button"
                      onClick={(e) => handleOpenEdit(p, e)}
                      title="Edit Demographic Profile"
                      className="p-1 hover:bg-slate-800 text-sky-400 hover:text-sky-300 rounded transition-colors"
                    >
                      <Edit3 size={12} />
                    </button>
                  </div>
                </div>
              </Card>
            ))
          )}
        </div>
      </div>

      {/* Modal: Edit Patient Demographic Details */}
      {editingPatient && (
        <Modal
          isOpen={isEditModalOpen}
          onClose={() => setIsEditModalOpen(false)}
          title={`Edit Demographic Profile — ${editingPatient.mrn}`}
        >
          <form onSubmit={handleSaveEdit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={editFullName}
                  onChange={(e) => setEditFullName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Mobile Number</label>
                <input
                  type="tel"
                  required
                  value={editPhone}
                  onChange={(e) => setEditPhone(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Blood Group</label>
                <select
                  value={editBloodGroup}
                  onChange={(e) => setEditBloodGroup(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                >
                  <option value="A+">A+ (A Positive)</option>
                  <option value="A-">A- (A Negative)</option>
                  <option value="B+">B+ (B Positive)</option>
                  <option value="B-">B- (B Negative)</option>
                  <option value="AB+">AB+ (AB Positive)</option>
                  <option value="AB-">AB- (AB Negative)</option>
                  <option value="O+">O+ (O Positive)</option>
                  <option value="O-">O- (O Negative)</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Postal PIN Code</label>
                <input
                  type="text"
                  maxLength={6}
                  value={editPincode}
                  onChange={(e) => setEditPincode(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">Residential Address</label>
              <input
                type="text"
                value={editAddress}
                onChange={(e) => setEditAddress(e.target.value)}
                placeholder="Door / Flat / Street address"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">City / Town</label>
                <input
                  type="text"
                  value={editCity}
                  onChange={(e) => setEditCity(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">State</label>
                <input
                  type="text"
                  value={editState}
                  onChange={(e) => setEditState(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3 pt-2 border-t border-slate-800/80">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Emergency Contact Name</label>
                <input
                  type="text"
                  value={editEmergencyName}
                  onChange={(e) => setEditEmergencyName(e.target.value)}
                  placeholder="Kin / Guardian Name"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Emergency Contact Mobile</label>
                <input
                  type="tel"
                  value={editEmergencyPhone}
                  onChange={(e) => setEditEmergencyPhone(e.target.value)}
                  placeholder="10-digit phone"
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg p-2 text-xs text-slate-200 font-mono"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-800">
              <Button type="button" variant="outline" size="sm" onClick={() => setIsEditModalOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" disabled={isUpdating}>
                {isUpdating ? "Saving..." : "Save Demographic Changes"}
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {/* Modal: Patient Registered Confirmation, OPD Slip & Wristband Print */}
      {successPatient && (
        <Modal
          isOpen={isSuccessModalOpen}
          onClose={() => setIsSuccessModalOpen(false)}
          title="Patient Intake & Registration Confirmed"
        >
          <div className="space-y-4">
            {/* View Selector Tabs */}
            <div className="flex items-center gap-2 border-b border-slate-800 pb-2">
              {generatedToken && (
                <button
                  type="button"
                  onClick={() => setPrintDocType("OPD_TOKEN")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                    printDocType === "OPD_TOKEN"
                      ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                      : "text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <Stethoscope size={13} /> OPD Consultation Slip & Receipt
                </button>
              )}
              <button
                type="button"
                onClick={() => setPrintDocType("WRISTBAND")}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  printDocType === "WRISTBAND"
                    ? "bg-sky-500/20 text-sky-400 border border-sky-500/40"
                    : "text-slate-400 hover:text-slate-200"
                }`}
              >
                <User size={13} /> UHID Card & Barcode Wristband
              </button>
            </div>

            {/* Document 1: OPD Consultation Slip & Thermal Cashier Receipt (ISOLATED PRINT AREA) */}
            {printDocType === "OPD_TOKEN" && generatedToken && (
              <div className="print-area p-5 rounded-xl bg-white text-slate-900 border border-slate-200 shadow-sm font-sans space-y-3">
                {/* Hospital Header */}
                <div className="text-center border-b border-slate-200 pb-2.5">
                  <div className="font-bold text-sm tracking-wide text-slate-900 uppercase">
                    Avinya Super-Specialty Hospital
                  </div>
                  <div className="text-[10px] text-slate-600 font-mono">
                    Outpatient Department (OPD) Consultation Slip • Token & Cashier Receipt
                  </div>
                  <div className="text-[9px] text-slate-500">
                    Plot 12, Health City, Gachibowli, Hyderabad • Tel: +91 40 8829 0000
                  </div>
                </div>

                {/* Hero Token Badge */}
                <div className="p-3 bg-slate-50 rounded-lg border border-slate-200 text-center">
                  <div className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                    Live OPD Queue Token
                  </div>
                  <div className="text-3xl font-black text-sky-700 font-mono my-0.5">
                    #{generatedToken.tokenNumber}
                  </div>
                  <div className="text-xs font-bold text-slate-800 font-mono">
                    Token ID: {generatedToken.tokenCode}
                  </div>
                </div>

                {/* Doctor & Clinic Cabin */}
                <div className="grid grid-cols-2 gap-2 text-xs border-y border-slate-200 py-2">
                  <div>
                    <span className="text-[10px] text-slate-500 block uppercase font-mono">Attending Consultant</span>
                    <span className="font-bold text-slate-900">{generatedToken.doctorName}</span>
                    <span className="text-[11px] text-slate-600 block">{generatedToken.department}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] text-slate-500 block uppercase font-mono">Consultation Cabin</span>
                    <span className="font-bold text-sky-700 text-sm">{generatedToken.roomNumber}</span>
                    <span className="text-[10px] text-amber-700 block font-medium">
                      ~{generatedToken.estimatedWaitMins} mins est. wait
                    </span>
                  </div>
                </div>

                {/* Patient Information */}
                <div className="text-xs space-y-1 bg-slate-50 p-2.5 rounded border border-slate-200">
                  <div className="flex justify-between">
                    <span className="text-slate-600">Patient:</span>
                    <span className="font-bold text-slate-900">{successPatient.full_name}</span>
                  </div>
                  <div className="flex justify-between font-mono text-[11px]">
                    <span className="text-slate-600">UHID / MRN:</span>
                    <span className="font-bold text-slate-900">{successPatient.mrn}</span>
                  </div>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-600">Gender / Blood:</span>
                    <span>{successPatient.gender} • {successPatient.blood_group || "O+"}</span>
                  </div>
                  <div className="flex justify-between text-[11px]">
                    <span className="text-slate-600">Queue Priority:</span>
                    <span className="font-semibold text-slate-900">{generatedToken.priority}</span>
                  </div>
                </div>

                {/* Cashier Payment Receipt */}
                <div className="text-[11px] font-mono border-t border-slate-200 pt-2 space-y-1">
                  <div className="flex justify-between">
                    <span className="text-slate-600">Receipt No:</span>
                    <span className="text-slate-900 font-semibold">{generatedToken.receiptNumber}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Payment Mode:</span>
                    <span className="text-slate-900">{generatedToken.paymentMode}</span>
                  </div>
                  <div className="flex justify-between text-xs font-bold pt-1 border-t border-slate-200">
                    <span className="text-slate-900">Total Consultation Fee Paid:</span>
                    <span className="text-emerald-700 font-mono">₹{generatedToken.consultationFee}.00</span>
                  </div>
                </div>

                {/* Thermal Slip Footer */}
                <div className="text-center text-[9px] text-slate-500 font-mono pt-1">
                  Issued at {generatedToken.issuedAt} • Please proceed to {generatedToken.roomNumber} waiting lounge.
                </div>
              </div>
            )}

            {/* Document 2: UHID Barcode Wristband / Patient ID Card (ISOLATED PRINT AREA) */}
            {printDocType === "WRISTBAND" && (
              <div className="print-area print-wristband p-4 rounded-xl bg-white text-slate-950 border-2 border-dashed border-slate-400 space-y-3 font-sans shadow-sm">
                <div className="flex items-center justify-between border-b border-slate-300 pb-1.5">
                  <div>
                    <div className="font-black text-xs uppercase tracking-wider text-slate-900">
                      Avinya Healthcare Apex
                    </div>
                    <div className="text-[9px] text-slate-600 font-mono">UHID Wristband & Patient ID</div>
                  </div>
                  <span className="font-bold text-xs text-sky-800 font-mono bg-sky-50 px-2 py-0.5 rounded border border-sky-300">
                    {successPatient.mrn}
                  </span>
                </div>

                <div className="space-y-1 text-xs">
                  <div className="font-bold text-sm text-slate-950 uppercase">{successPatient.full_name}</div>
                  <div className="text-[11px] text-slate-700 font-mono">
                    {successPatient.gender} • Blood: {successPatient.blood_group || "O+"} • Ph: {successPatient.phone_number || "--"}
                  </div>
                  <div className="text-[10px] text-slate-600">
                    {successPatient.city || "Hyderabad"}, {successPatient.state || "Telangana"}
                  </div>
                </div>

                {/* 2D Barcode Strip */}
                <div className="pt-2 border-t border-slate-300 flex flex-col items-center justify-center">
                  <div className="h-8 w-56 bg-slate-900 flex items-center justify-center text-[10px] text-white font-mono tracking-widest">
                    ||||| | |||| || ||| | |||
                  </div>
                  <div className="text-[9px] font-mono text-slate-600 mt-1">*{successPatient.mrn}*</div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex items-center justify-between pt-3 border-t border-slate-800">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.print()}
                className="flex items-center gap-1.5 font-semibold"
              >
                <Printer size={14} className="text-sky-400" /> Print {printDocType === "OPD_TOKEN" ? "OPD Consultation Slip" : "Wristband"}
              </Button>

              <div className="flex items-center gap-2">
                {generatedToken && (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => {
                      setIsSuccessModalOpen(false);
                      selectPatient(successPatient.id);
                    }}
                    className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold"
                  >
                    <Stethoscope size={13} /> Call Doctor Cockpit ({generatedToken.doctorName.split(" ")[1]})
                  </Button>
                )}

                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsSuccessModalOpen(false)}
                >
                  Done
                </Button>
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  );
};
