# Chapter 12: Enterprise Hospital UI, Workspaces & Dynamic Customization

**Document Version:** `5.0.0-APEX-ENTERPRISE`  
**Application Tier:** Client Clinical Operating System (`hospital-ui/`)  
**Core Stack:** React 18, TypeScript 5, Vite 6, Tailwind CSS 3, Lucide React  
**Reference Specification:** [`docs/ENTERPRISE_HOSPITAL_UI_SPECIFICATION_AND_AUDIT.md`](../ENTERPRISE_HOSPITAL_UI_SPECIFICATION_AND_AUDIT.md)  
**Metrics & KPI Inventory:** [`docs/ENTERPRISE_METRICS_AND_KPI_INVENTORY.md`](../ENTERPRISE_METRICS_AND_KPI_INVENTORY.md)  

---

## 1. Executive Overview & UI Architectural Principles

The Avinya HMS Client UI (`hospital-ui`) is an industrial-strength, responsive clinical workstation designed for multi-tier healthcare facilities ranging from 50-bed community clinics to 1,500+ bed tertiary academic medical centers and healthcare conglomerates.

Unlike traditional static web forms that create cognitive overload, navigation fragmentation, and medical error risks, the UI operates on six uncompromising enterprise tenets:

1. **Persistent Patient Safety Context (CCOW C-83 Pattern):** A persistent Global Patient Banner anchors the active patient context across all clinical screens, displaying critical safety indicators (Allergies, Blood Group, Active Admission, Fall Risk, Resuscitation Status) to prevent wrong-patient order entry errors.
2. **Unified High-Velocity Intake & Revisit Radar:** When a patient enters the hospital, front-desk staff can register demographics, generate a unique Master Patient Index (MPI) UHID, evaluate doctor-specific free follow-up revisit eligibility, assign an attending physician, and issue a thermal consultation token in a single screen.
3. **Multi-Scale Bed Matrix (500+ Bed Scale):** Inpatient ADT and Nursing workspaces utilize a 4-tier structural hierarchy (`Campus/Tower -> Floor -> Ward/Unit -> Bed`) with real-time operational status filters (`VACANT_CLEAN`, `OCCUPIED`, `HOUSEKEEPING`, `RESERVED`) capable of managing massive bed counts without infinite-scrolling or UI freezing.
4. **Hardware-Isolated Scoped Statutory Printing:** Standard browser `window.print()` cascades dark backgrounds, sidebars, and navbars. Avinya HMS enforces an isolated `@media print` style engine via `printDocument.ts` that strips all application chrome, rendering only the formatted document for 80mm thermal rolls, 280x28mm wristbands, or standard A4 statutory dockets.
5. **Doctor-Tied Revisit Rules & Fee Automation:** Follow-up consult grace periods are physician-dependent (`revisitFreeWindowDays`, `revisitMaxFreeVisits`, `revisitDiscountPercent`). If within the doctor's free window, fees are automatically waived to **₹0.00**, tagging tokens as `FREE REVISIT (Day X/Y)`.
6. **Cryptographic RBAC & Session Binding:** Operational capabilities are cryptographically bound to authenticated JWT identity claims (`user.roles` and `is_superuser`). The UI enforces strict role-gating via `<PermissionGate>`. Arbitrary role switching is completely locked out in production builds and demoted to a clearly marked, isolated simulator active only in local development (`import.meta.env.DEV`).

---

## 2. Global Shell & Navigation Topology

The UI shell consists of four synchronized architectural components:

```
+--------------------------------------------------------------------------------------------------------------------+
|  [AVINYA HMS] | Apollo Main Tower | Morning Shift | 12ms Sync    [Cmd+K Search...]     [ROLE: DOCTOR] [?] [Profile] [Logout] |
+--------------------------------------------------------------------------------------------------------------------+
| PATIENT SAFETY BANNER: Doe, John (42M) | MRN: AV-2026-00412 | O+ | ALLERGIES: PENICILLIN (ANAPHYLAXIS) | FULL CODE  |
+-------------------+------------------------------------------------------------------------------------------------+
| [PATIENT INTAKE]  |                                                                                                |
| [PATIENT 360]     |                                                                                                |
| [OPD COMMAND & TV]|                                                                                                |
| [INPATIENT ADT]   |                                                                                                |
| [DOCTOR COCKPIT]  |                                                                                                |
| [WARD NURSING]    |                                                                                                |
| [EMERGENCY ED]    |                       ACTIVE CLINICAL / OPERATIONAL WORKSPACE                                  |
| [SURGERY & OT]    |                                                                                                |
| [BLOOD BANK]      |                                                                                                |
| [PHARMACY & NDPS] |                                                                                                |
| [DIAGNOSTICS LIS] |                                                                                                |
| [CASHIER BILLING] |                                                                                                |
| [INFECTION & ASP] |                                                                                                |
| [BIOMEDICAL BME]  |                                                                                                |
| [ADMIN HUD & BHT] |                                                                                                |
+-------------------+------------------------------------------------------------------------------------------------+
| FOOTER: Avinya Clinical OS v5.0.0-APEX | DPDP Act 2023 / NABH 5th Ed Compliant | Real-Time Sync Active (12ms)       |
+--------------------------------------------------------------------------------------------------------------------+
```

### High-Speed Hotkey Navigation Matrix
Hospital workstations demand rapid keyboard-first throughput. Avinya HMS implements zero-mouse hotkeys:

| Key Binding | Target Clinical Destination | Primary Operational Workflow |
|---|---|---|
| **Cmd+K / Ctrl+K** | Universal Command Palette | Global MPI Patient Search & Fast Workspace Navigation |
| **Alt + 1** | Patient Intake & Front Desk | Demographic intake, ABHA lookup, Fast-Track OPD Token |
| **Alt + P** | Patient 360 & Timeline | Longitudinal EMR timeline, Doctor Revisit Radar |
| **Alt + Q** | OPD Command & TV Display | Multi-chamber queues, Audio chime calling, 4K Waiting TV |
| **Alt + 2** | Inpatient ADT & Bed Matrices | 500+ Bed allocation, transfer, MLC Section 39 CrPC intimation |
| **Alt + 3** | Doctor Clinical Cockpit | Longitudinal EMR, SOAP notes, CPOE e-Prescription |
| **Alt + 4** | Ward Nursing Station | eMAR bedside administration, NEWS2 deterioration scoring |
| **Alt + 5** | Emergency Triage Board | ESI 1–5 triage Kanban, Glasgow Coma Scale, Code Red |
| **Alt + S** | Surgery & OT Suite | Modular 6-OT suite, WHO 3-phase checklist, sponge counts |
| **Alt + B** | Blood Bank & Transfusion | 8-group stock, TTI screening, Form 27C crossmatching |
| **Alt + 6** | Central Pharmacy & Vault | Formulary dispensing, NDPS Schedule H1 double-witness vault |
| **Alt + 7** | Diagnostic Laboratory (LIS) | Specimen accessioning, Panic Delta read-back protocol |
| **Alt + 8** | Cashier Counter & Finance | Categorized folio charges, TPA insurance split, GST billing |
| **Alt + I** | Infection Control & ASP | CLABSI/CAUTI surveillance, reserve antibiotic ASP gate |
| **Alt + M** | Biomedical Engineering (BME) | Life-support register, IEC 62353 safety tests, PPM calib |
| **Alt + 9** | Executive Command HUD | 700+ Metric cube explorer, Facility Builder & Print Studio |
| **Esc** | Universal Modal Escape | Closes any active modal or drawer without committing changes |

---

## 3. The 15 Dedicated Clinical & Operational Workspaces

### Workspace 1: Patient Registration & Front-Desk Intake (`registration`)
- **Master Patient Index (MPI):** Instant deduplication across National ID, ABHA number, phone number, and demographic fuzzy matching.
- **Unified Fast-Track Consultation Token:** Single-screen transition from demographic entry to selecting attending physician, appointment slot, collecting initial registration fees, and issuing an OPD queue token.
- **DPDP Act 2023 Consent Collection:** Mandatory digital consent recording under Section 6 of India's DPDP Act with explicit consent purpose tracking and data principal rights notifications.
- **Doctor Revisit Fee Automation:** Automatically checks treating doctor's revisit rules. If valid, fee waives to **₹0.00**.

### Workspace 2: Patient 360 & Longitudinal Care Timeline (`patient-record`)
- **Longitudinal Care Timeline:** Chronological visual timeline rendering every milestone (Registration $\rightarrow$ Token $\rightarrow$ Triage $\rightarrow$ Vitals $\rightarrow$ Consultation $\rightarrow$ CPOE Orders $\rightarrow$ Critical Lab Panic Delta $\rightarrow$ Admission $\rightarrow$ Surgery $\rightarrow$ Discharge).
- **Doctor Revisit Radar:** Live status cards for every consulting specialist showing last visit date, days elapsed, days remaining, and an active **"Issue Free Revisit Token (₹0.00)"** action.

### Workspace 3: Outpatient (OPD) Command Center & 4K Lounge Display (`opd-queue`)
- **Doctor Chamber Presence Radar:** Live toggles (`IN_CHAMBER`, `ON_ROUNDS`, `IN_OT`, `PAUSED`).
- **Acoustic Two-Tone Chime & Voice Calling:** Web Audio API generates a two-tone bell chime (587.33 Hz $\rightarrow$ 440.00 Hz) followed by Web Speech API voice announcements.
- **4K Public Lounge TV Display Mode:** High-contrast display for waiting room monitors with multi-chamber status grid, pulsing calling card, and scrolling health notice marquee.

### Workspace 4: Inpatient Admission & Bed Allocation (ADT) (`adt`)
- **MPI Autocomplete Search:** Front-desk and admission officers enter patient MRN or name to instantly hydrate demographic history, active admissions, and insurance profiles.
- **500+ Bed Scale Hierarchy:** Multi-tier filtering across Campuses, Towers, Floors, and Specialty Wards (ICU, CCU, NICU, General Male/Female, Private Deluxe, Isolation).
- **Medico-Legal Case (MLC) Protocol:** Automated police intimation generation under Section 39 CrPC for road traffic accidents (RTA), gunshot/assault injuries, burns, and poisoning cases.
- **TPA Pre-Authorization Tracker:** Tracks insurer approval limits, cashless eligibility, deductible limits, and co-pay percentages prior to room allocation.

### Workspace 5: Doctor Clinical Cockpit & CPOE Consultation (`doctor`)
- **Subjective / Objective / Assessment / Plan (SOAP):** Structured clinical note editor with rich templates, ICD-10 diagnosis search, and longitudinal EMR timeline.
- **Clinical Decision Support (CDS) Radar:** Real-time drug-drug interaction (DDI) and drug-allergy conflict detection with severity classification and mandatory clinical override reason logging.
- **CPOE 1-Click Order Sets:** Pre-configured clinical order bundles (e.g. Acute Coronary Syndrome Bundle, Sepsis Resuscitation Set, Diabetic Ketoacidosis Protocol) allowing comprehensive lab, imaging, and medication ordering in under 5 seconds.

### Workspace 6: Ward Nursing Station, eMAR & Bedside Safety (`nursing`)
- **Electronic Medication Administration Record (eMAR):** Time-slotted visual administration grid with color-coded drug schedules (Given, Due, Overdue, Held, Refused).
- **BCMA 2D Barcode Verification:** Enforces the Joint Commission / NABH **"5 Rights of Medication Administration"** via bedside optical scanner before syringe or infusion delivery.
- **NEWS2 Deterioration Escalation:** Automated National Early Warning Score 2 computation based on 6 physiological parameters. High scores ($\ge 7$) trigger immediate Code Blue alerts.
- **SBAR Shift Handover Kardex:** Structured Situation, Background, Assessment, Recommendation Kardex for seamless inter-shift nursing handoffs.

### Workspace 7: Emergency Department Triage Board (`triage`)
- **Emergency Severity Index (ESI 1–5) Kanban:** Visual triage categorization (ESI 1 Resuscitation to ESI 5 Non-Urgent).
- **Glasgow Coma Scale (GCS) Calculator:** Objective 3-part neurological assessment (Eye Opening 1-4, Verbal Response 1-5, Motor Response 1-6).
- **Code Red Resuscitation Beacon:** Single-button cardiac arrest alarm and trauma team dispatch.

### Workspace 8: Operating Theatre (OT) & Surgical Suite (`surgery`)
- **Modular 6-Theatre Suite:** Status monitoring across Cardiac Hybrid, Neurosurgery, Ortho Joint Replacement, Laparoscopy, Obstetrics, and STAT Poly-Trauma.
- **WHO 3-Phase Surgical Safety Checklist:** Digital verification for Sign In (before induction), Time Out (before incision), and Sign Out (before leaving OT).
- **Sterile Sponge & Needle Count Reconciliation:** Tracks initial, intra-op added, and post-closure counts with automatic deficit alerts preventing retained surgical items.
- **PACU Aldrete Scoring (/10):** Recovery tracking across Activity, Respiration, Circulation, Consciousness, and O2 Saturation.

### Workspace 9: Blood Bank & Transfusion Medicine (`blood-bank`)
- **Component Requisitions Queue:** Real-time crossmatch requests from ED, OT, and ICUs.
- **Serological Crossmatch Compatibility:** Major, Minor, DAT, and IAT serology with verified bag reservations.
- **8-Group Inventory Matrix:** Continuous stock tracking across PRBC, FFP, Platelets (RDP/SDP), and Cryoprecipitate.
- **Mandatory 5-Parameter TTI Screening:** Negative certification for HIV 1/2, HBsAg, HCV, Syphilis, and Malaria.

### Workspace 10: Pharmacy Dispensing & Controlled Substances Vault (`pharmacy`)
- **Formulary Order Processing:** Real-time synchronization with doctor CPOE orders with stock availability indicators and generic substitute recommendations.
- **NDPS Schedule H1 & X Narcotics Vault:** Perpetual double-custody digital register for controlled substances (Morphine, Fentanyl, Pethidine). Dispensing requires dual-witness authentication and automatic balance reconciliation.

### Workspace 11: Diagnostic Laboratory Information System (LIS) (`diagnostics`)
- **Specimen Accessioning & Barcoding:** Generates Code-128 barcode specimen labels across Hematology, Biochemistry, and Microbiology.
- **Panic Critical Value Protocol:** Automated detection of panic delta thresholds with mandatory documented telephone read-back logging.
- **NABL Accredited Reports:** ISO 15189 compliant formatting with reference intervals and pathologist sign-off.

### Workspace 12: Cashier Counter & TPA Insurance Billing (`billing`)
- **Categorized Inpatient Folio:** Real-time aggregation of Bed Rent, Nursing Charges, Doctor Consultation Fees, OT Surgeries, Pharmacy Dispensing, and Diagnostic Investigations.
- **TPA / Cashless Split Allocator:** Seamless separation between Insurance Approved Amount, Statutory Non-Payable Items, Co-pay/Deductibles, and Patient Payable Balances.
- **Multi-Tender Receipting & GST Tax Invoicing:** Supports Split Payments (Cash + UPI + Credit Card + NEFT) with automated GST calculation.

### Workspace 13: Infection Prevention & Control (HICC) & Antimicrobial Stewardship (`infection-control`)
- **CDC NHSN & NABH HAI Surveillance:** CLABSI, CAUTI, VAP, and SSI benchmarks per 1,000 device-days.
- **Antimicrobial Stewardship Program (ASP) Queue:** Pre-authorization review for high-reserve antibiotics (Colistin, Meropenem, Ceftazidime-Avibactam).
- **Cumulative Antibiogram & Hand Hygiene:** 6-month susceptibility matrix and WHO 5 Moments audits.

### Workspace 14: Biomedical Engineering & Clinical Asset Management (`biomedical`)
- **Life-Support Equipment Register:** Tier 1 Life Support (Ventilators, Defibrillators, Anesthesia machines) with PPM calibration countdowns.
- **Electrical Safety Testing (EST):** IEC 60601-1 / IEC 62353 chassis leakage ($\mu\text{A}$) and earth bond ($\Omega$) verification.
- **Breakdown Work Orders:** Incident triage (`STAT_CRITICAL`, `URGENT`) with MTTR tracking.

### Workspace 15: Executive Command HUD & Master Administration (`admin`)
- **Executive Operational Metrics:** Occupancy rate, ALOS, RevPOB, unbilled folio WIP, and ED LWBS.
- **700+ Metric Enterprise Cube Explorer:** Interactive multidimensional KPI navigator.
- **Statutory Registers HUD:** RFC 4180 CSV exports for Midnight Census, Cashier Shift, and NDPS ledgers.
- **Interactive Print Template Studio (WYSIWYG):** Live controls for 80mm Thermal Receipt, Barcode Wristband, A4 Bed Head Ticket, and A4 Statutory Discharge Summary.

---

## 4. Statutory Print Layout Master Catalog

Avinya HMS eliminates raw `window.print()` application chrome leakage via the scoped `printDocument.ts` engine:

```ts
// Example: Scoped Print Invocation
printDocument(documentHtml, {
  docType: "CLINICAL_SUMMARY",
  title: "Formal_Discharge_Summary_AV-2026-00412",
});
```

| Document Code | Name & Statutory Standard | Form Factor | Workspace Trigger |
|---|---|---|---|
| **DOC-01** | OPD Consultation Token & Payment Receipt | 80mm Continuous Thermal | `registration`, `opd-queue` |
| **DOC-02** | Patient Identification Wristband (Code-128 / QR) | 280mm x 28mm Landscape Thermal | `patient-record`, `adt` |
| **DOC-03** | Inpatient Bed Head Ticket (BHT Face Sheet) | A4 Portrait Document | `adt` |
| **DOC-04** | Formal Inpatient Discharge Summary | A4 Portrait Document | `adt` |
| **DOC-05** | Form 39 CrPC Medico-Legal Police Intimation | A4 Portrait Legal Docket | `triage` |
| **DOC-06** | Rapid Emergency Triage Acuity Slip | 80mm Continuous Thermal | `triage` |
| **DOC-07** | Official Doctor e-Prescription & CPOE Orders | A4 Portrait Prescription Slip | `doctor` |
| **DOC-08** | NABH SBAR Nursing Shift Handover Kardex | A4 Landscape Shift Sheet | `nursing` |
| **DOC-09** | Intra-Operative Surgical Docket & WHO Checklist | A4 Portrait Surgical Docket | `surgery` |
| **DOC-10** | Form 27C Blood Compatibility Certificate | A4 Portrait Certificate | `blood-bank` |
| **DOC-11** | Form 3C NDPS Controlled Substances Handover | A4 Portrait Handover Docket | `pharmacy` |
| **DOC-12** | Form BME-QC-08 Medical Calibration Certificate | A4 Portrait Certificate | `biomedical` |

---

## 5. Enterprise RBAC & Security Session Architecture

### Cryptographic Role Binding
In production builds, the client UI does not allow users to select or switch their operational role. Staff roles are cryptographically derived from the verified user session token:

```ts
// Enforced in hospital-ui/src/core/context/PermissionsContext.tsx
export function resolveRoleFromUser(user: UserProfile | null): RoleCode {
  if (!user) return "FRONT_DESK";
  if (user.is_superuser) return "HOSPITAL_ADMIN";

  const roleCodes = (user.roles || []).map((r) => (r.code || "").toUpperCase());
  if (roleCodes.some((c) => c.includes("ADMIN") || c.includes("DIRECTOR"))) return "HOSPITAL_ADMIN";
  if (roleCodes.some((c) => c.includes("DOCTOR") || c.includes("PHYSICIAN") || c.includes("CLINICIAN"))) return "ATTENDING_PHYSICIAN";
  if (roleCodes.some((c) => c.includes("TRIAGE") || c.includes("EMERGENCY"))) return "TRIAGE_NURSE";
  if (roleCodes.some((c) => c.includes("NURSE") || c.includes("SISTER"))) return "WARD_NURSE";
  if (roleCodes.some((c) => c.includes("ADT") || c.includes("ADMISSION"))) return "ADT_OFFICER";
  if (roleCodes.some((c) => c.includes("BILLING") || c.includes("CASHIER") || c.includes("FINANCE"))) return "BILLING_CLERK";
  if (roleCodes.some((c) => c.includes("FRONT_DESK") || c.includes("RECEPTION"))) return "FRONT_DESK";

  return "HOSPITAL_ADMIN"; // Fallback safe default
}
```

### Granular Capability Permission Gates
Every sensitive button, tab, and input in the UI is gated by `<PermissionGate>`:
- `patient.register`
- `bed.allocate` / `bed.transfer`
- `order.cpoe_prescribe`
- `clinical.sign_notes`
- `discharge.clinical_sign`
- `nurse.administer_emar`
- `billing.tpa_approve`
- `config.facility_manage`

Unauthorized actions are cleanly removed or disabled with tooltip explanation, preventing unauthorized state mutations.

---

## 5. Hardware Printer Management & Physical Media Dimensions

### Zero Hardcoded Paper Dimensions
In enterprise hospitals, printing hardware varies widely across wings:
- **Zebra ZD510-HC / HC100 Vertical Cartridges:** Narrow-edge feed ($25\text{mm} \times 280\text{mm}$ in portrait orientation).
- **Direct Thermal Wristband Desktop Units:** Wide-edge feed ($280\text{mm} \times 25\text{mm}$ in landscape orientation).
- **Reception POS Slips:** Continuous rolls ($80\text{mm}$ or $58\text{mm}$ width, $0\text{mm}$ continuous length).
- **Central Ward Laser Multi-Function Devices:** Standard ISO 216 ($210\text{mm} \times 297\text{mm}$ A4 portrait).
- **Phlebotomy Tube Labelers:** Die-cut label rolls ($50\text{mm} \times 25\text{mm}$ landscape).

### Hardware Device Registry & Direct Network Dispatch
Administrators configure physical devices in [`AdminWorkspace.tsx`](file:///v:/avinya_hms/hospital-ui/src/workspaces/admin/AdminWorkspace.tsx) under the **Hardware Printers & Network Devices** sub-tab:
- **Connection Type:** `NETWORK_IP` (Port 9100 RAW / JetDirect TCP socket), `USB` (direct POS interface), `WIFI` (secure wireless roaming), `SYSTEM_DRIVER` (OS spooled).
- **Print Protocols:** `RAW_ZPL` (Zebra Programming Language for barcode straps), `RAW_ESCPOS` (ESC/POS command set for receipt rolls), `HTML_DRIVER` (isolated browser DOM print).
- **Physical Millimeter Adjustments:** Custom media width, height, printable area, and 4-way margins ($T, B, L, R$).
- **Calibration Slip Utility:** Built-in test print engine generates physical margin validation slips with alignment marks to verify print registration prior to live clinical deployment.
- **Dynamic Selection in Workspaces:** All 15 hospital workspaces query `getPrinterForCategory()` (`WRISTBAND`, `THERMAL_TOKEN`, `CLINICAL_A4`, `LAB_LABEL`) to automatically route jobs to the designated departmental printer matching exact configured millimeter dimensions:
  - **Emergency Department:** Red-Tag Trauma Wristband & ESI Triage slip.
  - **Diagnostics / Phlebotomy:** Specimen Barcode Tube Label ($50\text{mm} \times 25\text{mm}$) & NABL A4 Report.
  - **Blood Bank:** Form 27C Compatibility Certificate & Blood Bag Tie-On Tag.
  - **Cashier Counter:** Quick POS $80\text{mm}$ Settlement Receipt & Formal A4 GST Tax Invoice.
  - **OPD Queue & Registration:** Walk-in OPD Consultation Token Slip & Revisit Voucher.
  - **Doctor Consultation Cockpit:** CPOE Prescription Slip & Diagnostic Order Docket.
  - **Ward & Inpatient Care:** eMAR BCMA Dual-Witness Administration & SBAR Shift Kardex.
  - **Operating Theatres:** Intra-Operative WHO Surgical Safety Docket & Implant Registry.
  - **Biomedical Engineering:** IEC 62353 Electrical Safety & Calibration Certificate.

---

## 6. Multi-Tenant Backend REST API Integration

The frontend workspaces communicate directly with backend domain services in [`backend/domains/ui/router.py`](file:///v:/avinya_hms/backend/domains/ui/router.py) through [`hospital-ui/src/api/uiApi.ts`](file:///v:/avinya_hms/hospital-ui/src/api/uiApi.ts):

1. **Patient Care Longitudinal Timeline (`GET /api/ui/patients/{patient_id}/timeline`):**
   - Combines 7 clinical event sources (registrations, triage vitals with NEWS2 triggers, doctor SOAP consults, CPOE diagnostic orders, CPOE electronic prescriptions, inpatient admissions, and cashier payment receipts) chronologically.
   - Powers the Patient 360 overview tab and standalone longitudinal stream in [`PatientRecordWorkspace.tsx`](file:///v:/avinya_hms/hospital-ui/src/workspaces/patient/PatientRecordWorkspace.tsx).

2. **Doctor-Tied Revisit Eligibility Calculator (`GET /api/ui/patients/{patient_id}/revisit-eligibility?doctor_id={id}`):**
   - Automatically determines whether a returning patient qualifies for a complimentary consultation ($100\%$ fee waiver) based on the attending doctor's individual grace window (default 7 days) or applies the concession follow-up tariff.

3. **Facility Hardware Printers & Network Registry (`GET & POST /api/ui/facility/printers`):**
   - Persists all campus-wide physical printer profiles (IP address, port, orientation, millimeters, margins, DPI, connection type, protocol) in Redis keyed by tenant subdomain.
   - Automatically hydrates [`HospitalConfigContext.tsx`](file:///v:/avinya_hms/hospital-ui/src/core/context/HospitalConfigContext.tsx) on startup with automatic debounced cloud persistence when configurations are updated.

---

## 7. Mission-Critical Clinical Problem Resolution Matrix

| Clinical Workspace | Real-World Operational Challenge | Architectural Solution & Statutory Implementation |
|---|---|---|
| **Patient Registration** | Duplicate MRN creation causing longitudinal patient record fragmentation | **Real-Time Duplicate Detection:** Matches primary mobile against active MPI with 1-click historical record selection; captures PMJAY Golden Card and NFSA Family IDs. |
| **Inpatient ADT** | Uncontrolled ward entry & lost visitor traceability | **Attendant & Visitor Security Pass Printing:** Emits thermal gate passes (`THERMAL_TOKEN`) with barcode verification, family relationship, and ward visiting hours. |
| **Blood Bank** | Critical exsanguinating trauma cannot wait 45 mins for Coombs test | **STAT Emergency Uncrossmatched O-Negative Protocol:** Instant allocation of Universal Donor PRBC with signed clinician justification and statutory Form 27C alert docket. |
| **Diagnostics Lab** | Hemolyzed or clotted tubes discarded without nurse recollection | **Pre-Analytical Specimen Rejection Workflow:** Flags codified NABL rejection reasons (`HEMOLYZED`, `CLOTTED_EDTA`, `QNS`) and triggers 1-click STAT recollection tube label re-print. |
| **Pharmacy** | Look-Alike / Sound-Alike (LASA) dispensing medication errors | **Tall Man Lettering & LASA Risk Banners:** ISMP-codified Tall Man strings (`hydrALAZINE` vs `hydrOXYzine`, `metFORMIN` vs `metOPROLOL`) with forced double-check confirmation. |
| **Ward Nursing Station** | Fluid overload in renal/cardiac patients & delayed arrest alerting | **24-Hour Bedside Fluid Balance (I/O) & STAT Code Blue:** Tracks hourly IV/Oral vs Urine/Drain with cumulative net balance, plus 1-click bedside Code Blue cardiac arrest broadcast. |
| **Emergency Department** | Mass casualty influx overwhelm & missed hyper-acute intervention windows | **MCI Code Orange Intake & Door-to-Device Timers:** 1-click batch disaster intake (START Red/Yellow/Green), automated Section 39 CrPC MLC police intimation notices, and Door-to-Balloon/Door-to-Needle countdown timers. |
| **Infection Control (HICC)** | Ward cross-contamination of MDR pathogens (CRE, MRSA) | **Statutory Isolation Precaution Door Placards:** Color-coded bedside/door warning signs (Contact, Droplet, Airborne) enforcing strict barrier PPE, hand hygiene, and dedicated equipment before patient room entry. |
| **Operating Theatre (OT)** | Retained foreign objects & untracked implanted prostheses | **RSI Count Deficit Lock & UDI Implant Cards:** Active closure halt with emergency C-arm fluoroscopy trigger on count mismatch, plus statutory UDI implant identification cards with MRI safety parameters. |
| **Doctor Cockpit** | Disjointed OPD-to-IPD admission pathways & manual sick leave disputes | **IPD Bed Requisition & Statutory Medical Certificates:** 1-click issuance of Form ADT-01 bed booking orders (Emergency STAT/High-Acuity) with pre-transfer care directives, plus NMC-compliant statutory sick leave certificates. |
| **Biomedical Engineering** | Inadvertent patient connection to broken/uncalibrated life support | **Physical Lockout Tagout (LOTO) Danger Placards:** Instant Form BME-LOTO-01 hazard notices tagged to defective assets prohibiting patient use under NABH FMS.6/OSHA. |
| **Cashier Billing Counter** | Long payment settlement queues & unrecorded charity concessions | **EWS Concession Engine & Quick-Tender Presets:** Multi-tier waiver approvals (Senior Citizen, Staff, EWS 100% Free Bed) codified on GST receipts, plus 1-click Cash/UPI/Card presets. |
| **Patient Record (EMR)** | Unverified data disclosure & statutory privacy non-compliance | **DPDP Act 2023 Consent Disclosure Certificates:** Form DPDP-CERT-01 specifying purpose-specific consent statuses, cryptographic SHA-256 hash, and DPO rights contact. |
| **OPD Queue & QMS** | Sudden doctor absence for emergency surgery stalls lobby queues | **Bulk Doctor Queue Transfer & Emergency OT Advisory:** 1-click bulk rerouting of waiting patients to available peer consultants, live status sync, and 4K display alerts. |


