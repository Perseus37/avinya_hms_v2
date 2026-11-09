# Avinya HMS – Patient Experience & Longitudinal Record
## Document `08_PATIENT_EXPERIENCE.md`
### The Central Patient Entity, Longitudinal Care Timeline, Demographic MDM & Patient 360 Workspace

**Document Version:** `3.0.0-ENTERPRISE-SPEC`  
**Classification:** Enterprise Multi-Tenant Hospital Operating System  
**Parent Document:** [`00_FRONTEND_MASTER_SPEC.md`](00_FRONTEND_MASTER_SPEC.md)  

---

## 1. The Patient as the Core Organizing Primitive

In legacy hospital systems, patients are treated as disconnected records created independently by registration, re-searched by pharmacy, and re-created by billing. In Avinya HMS, the **Patient is the permanent, central anchor** of the entire platform:

```
                                  ┌───────────────────────────────┐
                                  │      MASTER PATIENT INDEX     │
                                  │   MRN-2026-00412 | Doe, John  │
                                  └───────────────┬───────────────┘
                                                  │
         ┌───────────────────┬────────────────────┼───────────────────┬───────────────────┐
         ▼                   ▼                    ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ CLINICAL RECORD │ │ LONGITUDINAL    │  │ ACTIVE CARE     │ │ FINANCIAL FOLIO │ │ PRIVACY & CONSENT│
│ • Problem List  │ │ TIMELINE        │  │ • Ward / Bed    │ │ • Folio Ledger  │ │ • DPDP Consents  │
│ • Allergies     │ │ • All Encounters│  │ • Acuity / Risk │ │ • Advance Deps  │ │ • ABDM M1-M3     │
│ • Vitals Trend  │ │ • Prescriptions │  │ • Nurse Station │ │ • TPA Pre-Auth  │ │ • Access Audit   │
│ • Lab / PACS    │ │ • Diagnostic Hx │  │ • Attending MD  │ │ • GST Receipts  │ │ • Breach Log     │
└─────────────────┘ └─────────────────┘  └─────────────────┘ └─────────────────┘ └─────────────────┘
```

---

## 2. Master Patient Index (MPI) & Multi-Factor Deduplication

To eliminate duplicate records while avoiding false-positive collisions among family members sharing mobile numbers (resolving defect **C-04**), Avinya HMS implements a multi-factor weighted matching algorithm:

### Multi-Factor Match Scoring Matrix:
```
Total Similarity Score = (Phone_Match * 0.40) + (Name_Levenshtein * 0.30) + (DOB_Match * 0.20) + (Gender_Match * 0.10)
```

| Match Threshold | System Action | User Interface Behavior |
|---|---|---|
| **$\text{Score} \ge 0.90$** | Definite Duplicate Match | Modal prompts front-desk staff: `"Patient already exists with MRN-2026-00412. Proceed with existing record?"` |
| **$0.70 \le \text{Score} < 0.90$** | Suspected Duplicate | Yellow alert strip displays top 3 matching patients with similarity percentage and primary addresses. |
| **$\text{Score} < 0.70$** | New Patient Unique | Proceeds cleanly to new MRN issuance (`MRN-YYYYMM-XXXXXX`). |

---

## 3. The Longitudinal Patient Care Timeline

The **Longitudinal Care Timeline** (`/patients/:mrn/timeline`) unifies disparate encounters into a single, cohesive vertical stream:

```
TODAY (01-NOV-2026)
───────────────────────────────────────────────────────────────────────────────────────────────────────
● 09:02   REGISTRATION DESK
          Patient registered as Outpatient by Clerk Priya Nair.
          UHID: AV-2026-00412 | OPD Token Issued: TOKEN-CARDIO-14 | Fee: ₹800 (Paid via UPI)
          Thermal wristband printed.

● 09:18   NURSING TRIAGE (OPD TRIAGE STATION 2)
          Vital signs recorded by Staff Nurse Anjali:
          BP: 148/92 mmHg | HR: 88 bpm | SpO2: 97% on room air | Temp: 98.4°F | NEWS2 Score: 1 (Low)

● 09:42   DOCTOR CONSULTATION (CHAMBER 4 - CARDIOLOGY)
          Consultation initiated by Dr. Ramesh Gupta (MD, DM Cardiology).
          Chief Complaint: Retrosternal chest discomfort on exertion x 3 days.
          Diagnosis Assigned: I20.9 (Angina pectoris, unspecified).

● 09:50   CPOE DIAGNOSTIC ORDERS PLACED
          1. 12-Lead Electrocardiogram (STAT)
          2. Serum Troponin-I (High Sensitivity)
          3. Complete Blood Count (CBC) with Platelets

● 09:54   PHLEBOTOMY SPECIMEN COLLECTION (CENTRAL LAB)
          Blood specimens collected by Phlebotomist Kiran.
          Barcode Accessions: EDTA: LAB-2026-04182 | Serum: LAB-2026-04183.

● 10:28   LABORATORY RESULT FILED & DELTA CHECKED
          Serum Troponin-I: 0.12 ng/mL [CRITICAL HIGH - REF < 0.04]
          Delta check: 300% elevation over 6-month baseline (0.03 ng/mL).
          Panic Critical Value Alert generated. Documented telephone read-back with Dr. Gupta logged.

● 10:35   INPATIENT ADMISSION ORDERED (EMERGENCY)
          Dr. Gupta placed urgent inpatient admission order.
          Target Unit: Coronary Care Unit (CCU) | Priority: STAT Emergent.

● 10:48   BED RESERVATION & ALLOCATION (ADT DESK)
          Bed allocated: Main Tower -> Floor 2 -> CCU -> Bed CCU-204.
          TPA Insurance Pre-Authorization initiated for Star Health (Cashless claim: ₹1,50,000).
```

---

## 4. Patient 360 Workspace Layout (`/patients/:mrn`)

When viewing a patient, the screen presents a unified 3-tier view:

```
+-------------------------------------------------------------------------------------------------------+
| Doe, John | 42y/M | MRN: AV-2026-00412 | ABHA: 91-4829-1029-41 | O+ | [!] Penicillin (Anaphylaxis)    |
+-------------------------------------------------------------------------------------------------------+
| [Overview] [Timeline] [Clinical] [Vitals] [Meds] [Orders] [Results] [Encounters] [Billing] [Consents] |
+-------------------------------------------------------------------------------------------------------+
| ACTIVE ENCOUNTER CARD: Inpatient CCU (Bed CCU-204) | Admitted: 01-Nov-2026 | Dr. Ramesh Gupta         |
| ┌───────────────────────────────────────────────┐ ┌─────────────────────────────────────────────────┐ │
| │ Active Diagnoses                              │ │ Active Medications                              │ │
| │ • I20.9 Angina pectoris (01-Nov-2026)         │ │ • Aspirin 75mg PO OD (Due 12:00)                │ │
| │ • I10 Essential Hypertension (2024)           │ │ • Atorvastatin 40mg PO QHS (Due 20:00)          │ │
| │ • E11.9 Type 2 Diabetes Mellitus (2022)       │ │ • Clopidogrel 75mg PO OD (Due 12:00)            │ │
| └───────────────────────────────────────────────┘ └─────────────────────────────────────────────────┘ │
| ┌───────────────────────────────────────────────┐ ┌─────────────────────────────────────────────────┐ │
| │ Recent Vitals & Hemodynamics                  │ │ Recent Diagnostic Investigations                │ │
| │ BP: 148/92 | HR: 88 | SpO2: 97% | Temp: 98.4°F│ │ • Troponin-I: 0.12 ng/mL (CRITICAL HIGH) [View] │ │
| │ NEWS2 Score: 1 (Calculated 09:18 Today)       │ │ • ECG 12-Lead: Sinus Rhythm, ST depression V4-V6│ │
| └───────────────────────────────────────────────┘ └─────────────────────────────────────────────────┘ │
+-------------------------------------------------------------------------------------------------------+
```

### Action Bar (Patient-Level Fast Actions):
- `[+ New Encounter / Visit]`
- `[+ Order CPOE Investigation]`
- `[+ Prescribe Medication]`
- `[+ Record Bedside Vitals]`
- `[Print Patient Wristband]` (Isolated thermal output)
- `[Print Clinical Summary]` (A4 Letterhead)

