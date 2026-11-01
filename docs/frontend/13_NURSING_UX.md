# Avinya HMS – Ward Nursing Station & Bedside eMAR UX
## Document `13_NURSING_UX.md`
### "My Shift" Ward Station, Bedside Patient View, Optical BCMA 5-Rights & NEWS2 Rapid Escalation

**Document Version:** `3.0.0-ENTERPRISE-SPEC`  
**Classification:** Enterprise Multi-Tenant Hospital Operating System  
**Parent Document:** [`00_FRONTEND_MASTER_SPEC.md`](00_FRONTEND_MASTER_SPEC.md)  

---

## 1. Executive Summary & Nursing UX Philosophy

Nurses are the frontline guardians of patient safety in a hospital. Unlike physicians who review longitudinal histories and author diagnostic notes, a staff nurse's workflow is **shift-driven, task-oriented, highly interrupt-driven, and physically tied to the patient's bedside**.

Forcing nurses to navigate a doctor's EMR layout creates fatal medication administration delays and charting omissions.

Avinya HMS delivers a dedicated **Nursing Workstation Ecosystem** centered around:
1. **The "My Shift" Ward Dashboard (`/nursing/station`)**
2. **The Bedside Patient Care Cockpit (`/nursing/patient/:bed_id`)**
3. **The Optical BCMA 5-Rights Bedside Administration Scanner (`/nursing/bcma`)**

---

## 2. The "My Shift" Ward Dashboard (`/nursing/station`)

```
┌ MY SHIFT: ICU-1 (CORONARY CARE UNIT) │ Shift: 07:00–15:00 Morning │ Nurse: Sister Anjali (RN) ────────┐
├───────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ASSIGNED PATIENTS: 6  │  CRITICAL (NEWS2 ≥7): 1  │  HIGH RISK: 2  │  STABLE: 3                        │
├───────────────────────┴──────────────────────────┴────────────────┴───────────────────────────────────┤
│ SHIFT TASK SUMMARY                                                                                    │
│ • Medications Due: 8      • Medications Overdue: 1 (STAT)   • Vitals Checks Due: 4                    │
│ • Lab Specimens to Draw: 3• Bed Transfers: 1                 • Discharges in Progress: 1              │
├───────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ASSIGNED PATIENT ROSTER                                                                               │
│                                                                                                       │
│ ┌ BED CCU-204 ──────────────────┐  ┌ BED CCU-201 ──────────────────┐  ┌ BED CCU-202 ──────────────────┐│
│ │ DOE, JOHN (42M)               │  │ RAO, K. (62M)                 │  │ MEHTA, S. (54F)               ││
│ │ [!] CRITICAL NEWS2: 8 (CODE)  │  │ NEWS2: 3 (Moderate)           │  │ NEWS2: 1 (Low)                ││
│ │ Allergies: Penicillin (Anaph) │  │ Allergies: None Known         │  │ Allergies: Sulfa              ││
│ │ Attending: Dr. Ramesh Gupta   │  │ Attending: Dr. Ramesh Gupta   │  │ Attending: Dr. Anita Roy      ││
│ │ • Med Overdue: IV Furosemide  │  │ • 12:00 Meds: 3 Due           │  │ • Vitals Due: 11:30           ││
│ │ • Vitals Check: OVERDUE       │  │ • Specimen: Serum K+ due      │  │ • Discharge: Pharmacy Clear   ││
│ │ [eMAR] [Record Vitals] [BCMA] │  │ [eMAR] [Record Vitals] [BCMA] │  │ [eMAR] [Record Vitals] [BCMA] ││
│ └───────────────────────────────┘  └───────────────────────────────┘  └───────────────────────────────┘│
└───────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Bedside Patient Care View (`/nursing/patient/:bed_id`)

When a nurse clicks into an assigned patient, the interface shifts into a bedside task cockpit:
- **Patient Identifier & Acuity Strip:** Name, MRN, Bed, Biological Sex, Age, Blood Group, Fall Risk, Resuscitation Status.
- **Visual eMAR Administration Timetable:** Time-slotted grid displaying scheduled medications across the shift (`08:00`, `12:00`, `16:00`, `20:00`):
  - `Green Pill (Administered)` — Shows nurse timestamp and verified barcode match.
  - `Blue Pill (Due Now)` — Active round window (±30 minutes of scheduled time).
  - `Red Flashing Pill (Overdue)` — Past grace period; triggers supervisor escalation alert.
  - `Amber Pill (Held / Refused)` — Displays documented clinical rationale (e.g., Systolic BP $<90$ mmHg held for anti-hypertensives).
- **Fluid Balance (Intake & Output / I&O):** Rapid tally of oral fluids, IV infusions, blood transfusions vs urine output, surgical drains, and emesis.

---

## 4. Bedside Barcode Medication Administration (BCMA 5-Rights Scanner)

The BCMA module enforces the **Joint Commission / NABH 5 Rights of Medication Administration** via optical barcode scanner before any drug can be administered:

```
┌ OPTICAL BCMA 5-RIGHTS BEDSIDE SCANNER ────────────────────────────────────────────────────────┐
│ TARGET PATIENT: Doe, John | BED: CCU-204 | MRN: AV-2026-00412                                 │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 1: SCAN PATIENT WRISTBAND                                                                │
│ [ Barcode Scanner Active...                                               ] [✓ VERIFIED]      │
│ Scanned: AV-2026-00412 ➔ 100% Match: DOE, JOHN (Right Patient Verified)                      │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ STEP 2: SCAN MEDICATION AMPOULE / VIAL BARCODE                                                │
│ [ Barcode Scanner Active...                                               ] [✓ VERIFIED]      │
│ Scanned: 8901234567890 ➔ Furosemide 20mg/2mL Injection (Right Drug & Dose Verified)          │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ THE 5 RIGHTS VERIFICATION MATRIX                                                              │
│ 1. Right Patient:  ✓ DOE, JOHN (AV-2026-00412)                                                │
│ 2. Right Drug:     ✓ Furosemide Injection                                                     │
│ 3. Right Dose:     ✓ 20 mg (1 ampoule)                                                        │
│ 4. Right Route:    ✓ Intravenous (IV Push)                                                    │
│ 5. Right Time:     ✓ Scheduled 12:00 (Administering at 12:04 - Within Grace Window)          │
├───────────────────────────────────────────────────────────────────────────────────────────────┤
│ [CANCEL]                                             [CONFIRM & RECORD ADMINISTRATION (Enter)]│
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

### Safety Hard Stops during BCMA:
- **Wrong Patient Wristband Scanned:** Immediate loud audio buzzer + full-screen red warning modal: `"PATIENT MISMATCH: Wristband scanned does not match Bed CCU-204. Do not administer."`
- **Wrong Drug Scanned:** Blocks administration. Explains discrepancy (e.g. `"Scanned Potassium Chloride instead of Sodium Chloride"`).
- **Controlled Substances (Schedule H1 / X Narcotics):**
  - Prompt requires a second licensed nurse or physician to scan their employee badge and provide digital co-signature before morphine or fentanyl can be dispensed.

---

## 5. National Early Warning Score 2 (NEWS2) & Rapid Escalation

The bedside vitals entry form automatically calculates the aggregate NEWS2 score based on 6 physiological parameters:

| Physiological Parameter | Value Range | NEWS2 Score Contribution |
|---|---|---|
| **Respiratory Rate** | $\le 8$ or $\ge 25$ bpm | $+3$ points |
| **SpO2 (Room Air)** | $\le 91\%$ | $+3$ points |
| **Systolic BP** | $\le 90$ mmHg or $\ge 220$ mmHg | $+3$ points |
| **Pulse Rate** | $\le 40$ or $\ge 131$ bpm | $+3$ points |
| **Consciousness (AVPU)**| Voice, Pain, or Unresponsive | $+3$ points |
| **Temperature** | $\le 35.0^\circ\text{C}$ ($95.0^\circ\text{F}$) | $+3$ points |

### Automated Clinical Escalation Thresholds:
- **Low Risk (Score 1–4):** Ward nurse continues 4-hour vital checks.
- **Medium Risk (Score 5–6):** Nurse alerts Attending Resident Doctor; increases vital frequency to 1 hour.
- **High Risk / Critical (Score $\ge 7$):**
  - Triggers **Emergency Rapid Response Team (RRT) / Code Blue alert**.
  - System automatically broadcasts push notification to ICU Registrar and Duty Cardiologist.
  - Opens clinical intervention documentation modal on bedside workstation.

