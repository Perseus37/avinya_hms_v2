# Avinya HMS – Repository-Driven Frontend Gap Audit
## Document `39_BACKEND_GAP_ANALYSIS.md`
### Systematic Mapping: Backend Domain ➔ Clinical Workflow ➔ Persona ➔ Screen ➔ Action ➔ State ➔ API Contract ➔ Identified Backend Gaps

**Document Version:** `3.0.0-ENTERPRISE-SPEC`  
**Classification:** Enterprise Multi-Tenant Hospital Operating System  
**Parent Document:** [`00_FRONTEND_MASTER_SPEC.md`](00_FRONTEND_MASTER_SPEC.md)  

---

## 1. Executive Summary & Audit Methodology

This gap analysis bridges the gap between the Avinya HMS backend architecture and the user-facing clinical application. Instead of guessing UI requirements, we analyze the actual backend models, routes, and database constraints in `backend/domains/` to determine:
1. What the backend already supports.
2. What frontline hospital workflows require.
3. Where the existing REST endpoints fail to deliver consolidated data, causing frontend request storms, race conditions, or unhandled states.

---

## 2. Systematic Gap Audit Matrix (Domain-by-Domain)

### Gap Audit 1: Outpatient Department (OPD) & Queue Flow
- **Backend Domain:** `backend/domains/opd/`, `backend/domains/appointments/`
- **Documented Workflow:** Patient arrives ➔ Check-in ➔ Triage vitals ➔ Queue insertion ➔ Doctor call-in ➔ Consultation.
- **Operating Personas:** Front Desk Receptionist, Triage Nurse, Attending Physician.
- **Target Screens:** `/opd/today`, `/opd/queue`, `/opd/display`, `/opd/check-in`.
- **Required Actions:** Issue token, call next patient, transfer chamber, mark no-show, display on waiting room TV.
- **Required States:** `SCHEDULED`, `ARRIVED`, `TRIAGED`, `IN_CONSULTATION`, `COMPLETED`, `NO_SHOW`, `CANCELLED`.
- **Existing Backend APIs:** `GET /v1/api/appointments`, `POST /v1/api/appointments`, `POST /v1/api/opd/tokens/issue`.
- **Identified Backend Gaps:**
  1. *Request Storm Risk (Defect C-05):* Currently requires fetching each waiting patient's status history individually (40+ requests per 20 seconds).
  2. *Missing Aggregate Endpoint:* Backend needs `GET /v1/api/opd/queue-summary?department_id=...` returning consolidated chamber assignments, wait times, and SLA breach flags in one payload.
  3. *Shallow Collision Detection (Defect C-06):* Existing appointment booking checks fixed $\pm15$ minutes rather than `[start_time, start_time + doctor_duration]`.
  4. *TV Display Endpoint:* Needs unauthenticated public endpoint `GET /v1/api/opd/display-tokens` delivering active tokens with masked patient names (`DOE, J***`).

---

### Gap Audit 2: Inpatient Admission, Bed Allocation & Discharge Gate (ADT)
- **Backend Domain:** `backend/domains/admissions/`, `backend/domains/wards/`, `backend/domains/billing/`
- **Documented Workflow:** Doctor admission order ➔ MPI hydrate ➔ Bed requirement ➔ Bed search ➔ Atomic lock ➔ TPA pre-auth ➔ Bed allocation ➔ Nursing care ➔ 3-Key Discharge.
- **Operating Personas:** Admission Officer, Ward Nurse, Ward Pharmacist, Cashier Clerk.
- **Target Screens:** `/ipd/beds`, `/ipd/admissions/new`, `/ipd/discharge-board`, `/ipd/discharges/:id`.
- **Required Actions:** Bed search, atomic lock, bed transfer, request housekeeping clean, sign clinical discharge, verify drug return, clear billing folio.
- **Required States:** Bed: `AVAILABLE`, `OCCUPIED`, `CLEANING`, `MAINTENANCE`, `RESERVED`, `ISOLATION`. Discharge: `ACTIVE`, `CLINICAL_CLEARED`, `PHARMACY_CLEARED`, `BILLING_CLEARED`, `DISCHARGED`.
- **Existing Backend APIs:** `GET /v1/api/wards/beds`, `POST /v1/api/admissions`, `POST /v1/api/admissions/:id/transfer`.
- **Identified Backend Gaps:**
  1. *Missing Multi-Tier Bed Matrix Hierarchy:* `GET /v1/api/wards/beds` returns a flat list. Needs hierarchical grouping: `Campus -> Tower -> Floor -> Ward -> Bed` with room tariffs and equipment flags.
  2. *Missing Consolidated Discharge Pipeline Endpoint:* Currently requires querying clinical encounter notes, pharmacy returns, and billing balances independently. Backend needs `GET /v1/api/admissions/discharge-pipeline` returning the 3-key status for all pending discharges.
  3. *Atomic Lock Recovery:* When `FOR UPDATE NOWAIT` returns 409 Conflict, backend should suggest next available alternative beds of identical specialty and tariff.

---

### Gap Audit 3: Clinical Decision Support (CDS) & Doctor Cockpit
- **Backend Domain:** `backend/domains/clinical/`, `backend/domains/cpoe/`, `backend/domains/pharmacy/`
- **Documented Workflow:** Chart review ➔ SOAP documentation ➔ ICD-10 diagnosis ➔ CPOE order set ➔ CDS safety evaluation ➔ Digital signature.
- **Operating Personas:** Attending Physician, Surgeon, Clinical Resident.
- **Target Screens:** `/clinical/cockpit`, `/clinical/encounters/:id`, `/clinical/cpoe`.
- **Required Actions:** Insert diagnosis, select order set, evaluate DDI radar, override hard stop with justification, sign and finalize encounter.
- **Required States:** `DRAFT`, `CDS_EVALUATING`, `SAFETY_WARNING`, `BLOCKED_CONTRAINDICATION`, `SIGNED`, `AMENDED`.
- **Existing Backend APIs:** `POST /v1/api/encounters`, `POST /v1/api/prescriptions`, `POST /v1/api/cpoe/orders`.
- **Identified Backend Gaps:**
  1. *Live CDS Evaluation Endpoint:* Currently, DDI checks run only at prescription commit time. The frontend needs `POST /v1/api/clinical/cds/evaluate` to evaluate drug drafts in real-time as the physician types, before final submission.
  2. *Structured Override Audit Table:* Overrides for severe contraindications currently log to application text. Backend requires structured table `clinical_override_audits` capturing `prescribing_doctor_id`, `patient_id`, `clashing_medication_a`, `clashing_medication_b`, `severity_tier`, `override_rationale`, and `timestamp`.
  3. *1-Click CPOE Bundle Presets:* Backend needs API `GET /v1/api/cpoe/order-sets` delivering standard protocol bundles (ACS, Stroke, Sepsis).

---

### Gap Audit 4: Ward Nursing Station, eMAR & Bedside BCMA
- **Backend Domain:** `backend/domains/nursing/`, `backend/domains/pharmacy/`, `backend/domains/clinical/`
- **Documented Workflow:** Shift sign-in ➔ Patient roster ➔ Vitals check ➔ NEWS2 score ➔ eMAR schedule ➔ Optical BCMA scan ➔ Dual-witness co-signature ➔ SBAR handover.
- **Operating Personas:** Ward Staff Nurse, Head Nurse, Rapid Response Team (RRT).
- **Target Screens:** `/nursing/station`, `/nursing/emar`, `/nursing/bcma`, `/nursing/sbar`.
- **Required Actions:** View shift roster, scan wristband, scan drug barcode, log refusal/hold reason, calculate NEWS2, trigger Code Blue alert.
- **Required States:** Dose: `SCHEDULED`, `DUE_NOW`, `ADMINISTERED`, `OVERDUE`, `HELD`, `REFUSED`, `WASTED`.
- **Existing Backend APIs:** `POST /v1/api/pharmacy/bcma/verify`, `POST /v1/api/clinical/vitals`.
- **Identified Backend Gaps:**
  1. *Missing "My Shift" Aggregation Endpoint:* Backend needs `GET /v1/api/nursing/shift-roster/my-ward?ward_id=...&shift=...` delivering assigned beds, critical NEWS2 scores, overdue medications count, and scheduled specimen draws in one call.
  2. *BCMA Hardware Barcode Normalizer:* Barcode scanners output raw strings (Code-128, Datamatrix). Backend needs API accepting raw scanner payload and returning tokenized drug verification.
  3. *Automated Rapid Response Team (RRT) Webhook:* When NEWS2 score $\ge 7$, backend should automatically push WebSocket broadcast to ICU team without requiring manual phone call.

---

### Gap Audit 5: Cashier Counter, Folio Aggregation & TPA Split
- **Backend Domain:** `backend/domains/billing/`, `backend/domains/insurance/`
- **Documented Workflow:** Charges accumulate (room, nursing, labs, surgery) ➔ TPA cashless pre-auth verification ➔ Non-payable item segregation ➔ Co-pay collection ➔ GST tax invoice.
- **Operating Personas:** Cashier Clerk, Billing Supervisor, TPA Desk Officer.
- **Target Screens:** `/billing/invoices`, `/billing/cashier`, `/billing/closing`, `/billing/insurance`.
- **Required Actions:** Open folio, aggregate line items, allocate insurance split, collect multi-tender payment, print thermal receipt, close cashier shift.
- **Required States:** Folio: `OPEN`, `PRE_AUTH_PENDING`, `ESTIMATED`, `FINALIZED`, `PARTIALLY_PAID`, `SETTLED`, `DISPUTED`.
- **Existing Backend APIs:** `POST /v1/api/billing/invoices`, `POST /v1/api/billing/payments`.
- **Identified Backend Gaps:**
  1. *Two-Step Billing Hand-off Bug (Defect C-02):* Currently requires creating invoice and adding items across two unlinked calls, risking orphan invoices. Backend needs atomic endpoint `POST /v1/api/billing/folios/finalize-and-pay`.
  2. *TPA Cashless Split Model:* Backend models need clear fields on invoice line-items: `is_insurance_payable: bool`, `insurance_approved_amount: int`, `non_payable_reason: str`, `patient_copay_amount: int`.
  3. *Blind Cashier Closing:* Shift closing endpoint `POST /v1/api/billing/cashier-shift/close` must accept cashier's physical cash count without revealing system total until submission (preventing cashier theft/skimming).

---

## 3. Prioritized Backend Remediation Worklist

| Priority | Required Backend Change | Impacted Frontend Screen | Target Domain Module |
|---|---|---|---|
| **P0** | Add `GET /v1/api/opd/queue-summary` (Aggregated queue, chamber rooms, SLA breaches) | `/opd/today`, `/opd/queue` | `domains/opd` |
| **P0** | Add `GET /v1/api/admissions/discharge-pipeline` (Consolidated 3-key clearance status) | `/ipd/discharge-board` | `domains/admissions` |
| **P0** | Add `GET /v1/api/tasks/my-work` (Consolidated role task inbox) | Application Shell (`/tasks`) | `domains/ui` |
| **P1** | Add `POST /v1/api/clinical/cds/evaluate` (Real-time DDI & allergy clash evaluation) | `/clinical/encounters/:id` | `domains/clinical` |
| **P1** | Add `POST /v1/api/billing/folios/finalize-and-pay` (Atomic folio settlement to fix C-02) | `/billing/cashier` | `domains/billing` |
| **P1** | Multi-factor weighted fuzzy matching in duplicate patient detection (Fix C-04) | `/patients/new` | `domains/patients` |
| **P2** | Real-duration overlap collision check in appointment booking (Fix C-06) | `/opd/appointments/new` | `domains/appointments`|
| **P2** | Add `GET /v1/api/nursing/shift-roster/my-ward` (Shift roster, bed acuity, tasks summary) | `/nursing/station` | `domains/nursing` |
