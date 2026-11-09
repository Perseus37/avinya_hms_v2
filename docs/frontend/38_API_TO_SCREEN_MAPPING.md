# Avinya HMS – Screen to API Mapping Directory
## Document `38_API_TO_SCREEN_MAPPING.md`
### Comprehensive Mapping of All 84 Hospital Screens to FastAPI Domain Endpoints

**Document Version:** `3.0.0-ENTERPRISE-SPEC`  
**Classification:** Enterprise Multi-Tenant Hospital Operating System  
**Parent Document:** [`00_FRONTEND_MASTER_SPEC.md`](00_FRONTEND_MASTER_SPEC.md)  

---

## 1. Mapping Overview

This directory provides the definitive technical link between the frontend clinical workstation (`hospital-ui/`) and the 26 backend domain modules (`backend/domains/`). 

Every screen is mapped to its primary REST API endpoints, HTTP verbs, payload schemas, and required permissions.

---

## 2. Complete Screen to Endpoint Matrix

### Module 1: Authentication & Public Surface
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/login` | Staff Sign-In Portal | `POST /v1/api/auth/login` | `domains/identity` | Public |
| `/mfa` | MFA TOTP Challenge | `POST /v1/api/auth/mfa/verify-login` | `domains/identity` | Public (Challenge) |
| `/forgot-password` | Password Recovery Request | `POST /v1/api/auth/password-reset/request` | `domains/identity` | Public |
| `/reset-password` | Set New Password | `POST /v1/api/auth/password-reset/confirm` | `domains/identity` | Public (Reset Token) |
| `/session-expired` | In-Place Re-Auth Modal | `POST /v1/api/auth/refresh` | `domains/identity` | Bearer Refresh |

### Module 2: Role Workspaces & Personal Cockpits
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/home` | Role-Specific Home Cockpit | `GET /v1/api/identity/me` | `domains/identity` | Authenticated |
| `/tasks` | "My Work" Unified Task Center | `GET /v1/api/tasks/my-work` | `domains/ui` | Authenticated |
| `/notifications` | Clinical & System Alerts | `GET /v1/api/realtime/alerts/active` | `domains/realtime` | Authenticated |

### Module 3: Universal Patient Spine & Longitudinal Record
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/patients` | Master Patient Index (MPI) | `GET /v1/api/patients?search=...&limit=50` | `domains/patients` | `patients:read` |
| `/patients/new` | Patient Registration Wizard | `POST /v1/api/patients` | `domains/patients` | `patients:write` |
| `/patients/new` | PIN Code Suggestion Lookup | `GET /v1/api/patients/pincode-suggestions?pincode=...` | `domains/patients` | `patients:write` |
| `/patients/:mrn` | Patient 360 Header & Overview | `GET /v1/api/patients/:id/summary` | `domains/patients` | `patients:read` |
| `/patients/:mrn/timeline`| Longitudinal Care Timeline | `GET /v1/api/patients/:id/timeline` | `domains/clinical` | `clinical:read` |
| `/patients/:mrn/clinical`| Problem List & Diagnoses | `GET /v1/api/patients/:id/diagnoses` | `domains/clinical` | `clinical:read` |
| `/patients/:mrn/vitals` | Vital Signs & NEWS2 Graph | `GET /v1/api/patients/:id/vitals-history` | `domains/clinical` | `vitals:read` |
| `/patients/:mrn/medications`| Active Medication Profile | `GET /v1/api/pharmacy/patient-profile/:id` | `domains/pharmacy` | `pharmacy:read` |
| `/patients/:mrn/orders` | CPOE Diagnostic Orders | `GET /v1/api/diagnostics/orders/patient/:id` | `domains/diagnostics`| `cpoe:read` |
| `/patients/:mrn/results`| Lab & Radiology Reports | `GET /v1/api/diagnostics/results/patient/:id`| `domains/diagnostics`| `diagnostics:read` |
| `/patients/:mrn/encounters`| Past Encounters History | `GET /v1/api/encounters/patient/:id` | `domains/clinical` | `encounters:read` |
| `/patients/:mrn/billing`| Patient Folio & Statement | `GET /v1/api/billing/folios/patient/:id` | `domains/billing` | `billing:read` |
| `/patients/:mrn/consents`| DPDP Consent Artifacts | `GET /v1/api/privacy/consents/patient/:id` | `domains/privacy` | `privacy:read` |
| `/patients/:mrn/audit` | Chart Access Audit Trail | `GET /v1/api/audit/logs/patient/:id` | `domains/audit` | `audit:read` |

### Module 4: Outpatient Department (OPD) Workflows
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/opd/today` | OPD Command Dashboard | `GET /v1/api/opd/queue-summary` | `domains/ui` | `opd:read` |
| `/opd/queue` | Live Multi-Doctor Queue Board | `GET /v1/api/opd/queues?dept_id=...` | `domains/opd` | `opd:read` |
| `/opd/appointments` | Appointment Schedule Grid | `GET /v1/api/appointments?doctor_id=...` | `domains/appointments`| `opd:read` |
| `/opd/appointments/new` | Appointment Booking Wizard | `POST /v1/api/appointments` | `domains/appointments`| `opd:write` |
| `/opd/check-in` | Fast-Track Arrival Desk | `POST /v1/api/opd/tokens/issue` | `domains/opd` | `opd:write` |
| `/opd/walk-in` | Walk-In Triage & Allocation | `POST /v1/api/opd/walk-in` | `domains/opd` | `opd:write` |
| `/opd/waitlist` | Waitlist Management | `GET /v1/api/appointments/waitlist` | `domains/appointments`| `opd:read` |
| `/opd/leaves` | Doctor Leave Ledger | `GET /v1/api/appointments/doctor-leaves` | `domains/appointments`| `opd:read` |
| `/opd/unmet-demand` | Service Demand Backlog | `GET /v1/api/appointments/unmet-demand` | `domains/appointments`| `analytics:read` |
| `/opd/display` | Waiting Room Public Display | `GET /v1/api/opd/display-tokens` | `domains/opd` | Public / Reception |

### Module 5: Inpatient ADT, Bed Matrix & Discharges
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/ipd/beds` | Visual Bed Board Matrix | `GET /v1/api/wards/beds/matrix` | `domains/wards` | `adt:read` |
| `/ipd/admissions` | Inpatient Census List | `GET /v1/api/admissions/active` | `domains/admissions` | `adt:read` |
| `/ipd/admissions/new` | Admission Wizard | `POST /v1/api/admissions` | `domains/admissions` | `adt:write` |
| `/ipd/transfers` | Bed & Ward Transfer Desk | `POST /v1/api/admissions/:id/transfer` | `domains/admissions` | `adt:write` |
| `/ipd/discharge-board` | 3-Tier Discharge Clearance Gate | `GET /v1/api/admissions/discharge-pipeline` | `domains/ui` | `adt:read` |
| `/ipd/discharges/:id` | Discharge Clearance Console | `POST /v1/api/admissions/:id/discharge-clear`| `domains/admissions` | `discharge:write` |
| `/ipd/census-runner` | Midnight Census Audit | `POST /v1/api/billing/midnight-census/execute`| `domains/billing` | `billing:admin` |

### Module 6: Emergency Department (ED / Triage)
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/emergency/board` | Emergency Triage Board | `GET /v1/api/emergency/triage-board` | `domains/clinical` | `emergency:read` |
| `/emergency/triage/new` | Rapid Triage Intake | `POST /v1/api/emergency/triage-assessment` | `domains/clinical` | `emergency:write` |
| `/emergency/trauma-flow` | Trauma Resuscitation Flowsheet | `POST /v1/api/emergency/trauma-flowsheet` | `domains/clinical` | `emergency:write` |
| `/emergency/mlc` | Medico-Legal Case (MLC) Desk | `POST /v1/api/clinical/mlc-cases` | `domains/clinical` | `mlc:write` |
| `/emergency/code-red` | Mass Casualty Disaster Console | `POST /v1/api/emergency/code-red/activate` | `domains/emergency` | `emergency:admin` |

### Module 7: Clinical Cockpit & Doctor Consultation
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/clinical/cockpit` | Doctor Consultation Chamber | `GET /v1/api/ui/doctor/queue-today` | `domains/ui` | `clinical:write` |
| `/clinical/encounters/:id` | SOAP Consultation Workspace | `POST /v1/api/encounters/:id/soap-notes` | `domains/clinical` | `clinical:write` |
| `/clinical/encounters/:id` | CDS Radar Safety Evaluation | `POST /v1/api/clinical/cds/evaluate` | `domains/clinical` | `clinical:write` |
| `/clinical/cpoe` | CPOE Fast Order Builder | `POST /v1/api/cpoe/orders/batch` | `domains/clinical` | `cpoe:write` |
| `/clinical/templates` | Clinical Documentation Templates | `GET /v1/api/clinical/templates` | `domains/clinical` | `clinical:write` |

### Module 8: Ward Nursing Station & Bedside eMAR
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/nursing/station` | "My Shift" Nursing Station | `GET /v1/api/nursing/shift-roster/my-ward` | `domains/nursing` | `nursing:read` |
| `/nursing/emar` | Electronic MAR Visual Grid | `GET /v1/api/nursing/emar/patient/:id` | `domains/nursing` | `nursing:write` |
| `/nursing/bcma` | Bedside BCMA Optical Scan | `POST /v1/api/pharmacy/bcma/verify-administer`| `domains/pharmacy` | `nursing:write` |
| `/nursing/vitals-entry` | Bedside Vitals & NEWS2 Entry | `POST /v1/api/clinical/vitals` | `domains/clinical` | `vitals:write` |
| `/nursing/sbar` | Shift Handover Kardex | `POST /v1/api/nursing/sbar-handover` | `domains/nursing` | `nursing:write` |

### Module 9: Central Pharmacy & NDPS Narcotics Vault
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/pharmacy/queue` | Outpatient & Inpatient Rx Queue | `GET /v1/api/pharmacy/dispensing-queue` | `domains/pharmacy` | `pharmacy:read` |
| `/pharmacy/dispense/:id` | Medication Dispensing Desk | `POST /v1/api/pharmacy/prescriptions/:id/dispense`| `domains/pharmacy` | `pharmacy:write` |
| `/pharmacy/returns` | Ward Drug Returns & Credits | `POST /v1/api/pharmacy/returns/process` | `domains/pharmacy` | `pharmacy:write` |
| `/pharmacy/vault` | Schedule H1 & X Narcotics Vault | `POST /v1/api/pharmacy/controlled/dual-witness`| `domains/pharmacy` | `pharmacy:vault` |
| `/pharmacy/stock` | Inventory & Expiry Surveillance | `GET /v1/api/pharmacy/inventory/stock-status`| `domains/pharmacy` | `pharmacy:read` |

### Module 10: Diagnostic Laboratory (LIS) & Radiology (RIS/PACS)
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/diagnostics/phlebotomy` | Phlebotomy Accessioning Desk | `POST /v1/api/diagnostics/accessioning/specimen`| `domains/diagnostics`| `lab:write` |
| `/diagnostics/worklist` | Laboratory Analyzer Worklist | `GET /v1/api/diagnostics/analyzer/worklist` | `domains/diagnostics`| `lab:read` |
| `/diagnostics/verify/:id` | Pathologist Verification | `POST /v1/api/diagnostics/results/:id/verify` | `domains/diagnostics`| `lab:verify` |
| `/diagnostics/panic` | Panic Critical Value Register | `POST /v1/api/diagnostics/panic-alert/acknowledge`| `domains/diagnostics`| `lab:write` |
| `/diagnostics/radiology` | Radiology Modality Worklist | `GET /v1/api/radiology/worklist` | `domains/radiology` | `radiology:read` |
| `/diagnostics/pacs/:id` | Integrated DICOM PACS Viewer | `GET /v1/api/radiology/studies/:id/dicom` | `domains/radiology` | `radiology:read` |

### Module 11: Operating Theatre & Surgical Suite
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/surgery/schedule` | OT Master Schedule Board | `GET /v1/api/surgery/theatre-schedule` | `domains/surgery` | `surgery:read` |
| `/surgery/cases/new` | Surgery Booking & PAC Desk | `POST /v1/api/surgery/bookings` | `domains/surgery` | `surgery:write` |
| `/surgery/cases/:id` | Intra-Operative Surgical Record | `POST /v1/api/surgery/cases/:id/who-checklist`| `domains/surgery` | `surgery:write` |

### Module 12: Blood Bank & Transfusion Medicine
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/blood-bank/donors` | Voluntary Donor Registry | `POST /v1/api/bloodbank/donors` | `domains/bloodbank` | `bloodbank:write` |
| `/blood-bank/inventory` | Blood Component Stock Ledger | `GET /v1/api/bloodbank/inventory` | `domains/bloodbank` | `bloodbank:read` |
| `/blood-bank/crossmatch` | Cross-Matching & Issue Desk | `POST /v1/api/bloodbank/crossmatch/issue` | `domains/bloodbank` | `bloodbank:write` |

### Module 13: Cashier Counter, Billing & Insurance RCM
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/billing/invoices` | Patient Billing & Folios | `GET /v1/api/billing/folios` | `domains/billing` | `billing:read` |
| `/billing/cashier` | Cashier Counter & Payment Desk | `POST /v1/api/billing/payments/collect` | `domains/billing` | `billing:write` |
| `/billing/deposits` | Advance Deposits & Drawdown | `POST /v1/api/billing/deposits` | `domains/billing` | `billing:write` |
| `/billing/closing` | Shift Settlement & Cash Reconcile | `POST /v1/api/billing/cashier-shift/close` | `domains/billing` | `billing:write` |
| `/billing/insurance` | TPA Pre-Authorization Manager | `POST /v1/api/insurance/pre-auth/submit` | `domains/insurance` | `insurance:write` |
| `/billing/claims` | NHCX Electronic Claims Desk | `POST /v1/api/insurance/claims/nhcx/dispatch`| `domains/insurance` | `insurance:write` |

### Module 14: Procurement, Inventory & Supply Chain
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/supply/requisitions` | Purchase Requisition Desk | `POST /v1/api/procurement/requisitions` | `domains/procurement`| `supply:write` |
| `/supply/purchase-orders` | Purchase Order (PO) Manager | `POST /v1/api/procurement/orders` | `domains/procurement`| `supply:write` |
| `/supply/grn` | Goods Receipt Notes (GRN) | `POST /v1/api/procurement/grn/receive` | `domains/procurement`| `supply:write` |
| `/supply/stock-transfers`| Departmental Stock Issues | `POST /v1/api/inventory/transfers` | `domains/inventory` | `supply:write` |

### Module 15: Quality, Compliance & Master Administration
| Route | Screen Name | HTTP Method & Target API Endpoint | Backend Module | Required Permission |
|---|---|---|---|---|
| `/governance/incidents` | Adverse Incident Register | `POST /v1/api/quality/incidents` | `domains/quality` | `quality:write` |
| `/governance/indicators`| NABH & JCI Quality Radar | `GET /v1/api/quality/indicators/benchmarks` | `domains/quality` | `quality:read` |
| `/governance/privacy` | DPDP Act 2023 Privacy Portal | `POST /v1/api/privacy/data-rights/submit` | `domains/privacy` | `privacy:write` |
| `/governance/audit` | Master Security Audit Vault | `GET /v1/api/audit/logs` | `domains/audit` | `audit:read` |
| `/governance/reports` | Statutory Reports & Registers | `GET /v1/api/reports/statutory/export` | `domains/reports` | `reports:read` |
| `/governance/analytics`| Executive KPI Cube Explorer | `GET /v1/api/analytics/cubes/kpis` | `domains/analytics` | `analytics:read` |
| `/admin/facility` | Master Facility Builder | `POST /v1/api/facilities/matrix/update` | `domains/facilities`| `admin:facility` |
| `/admin/doctors` | Doctor Roster & Pricing Master | `POST /v1/api/practitioners/roster/update` | `domains/identity` | `admin:doctors` |
| `/admin/identity` | Hospital Identity & Letterhead | `POST /v1/api/tenants/profile/update` | `domains/tenants` | `admin:identity` |
| `/admin/policies` | Statutory Hospital Policies | `POST /v1/api/tenants/policies/update` | `domains/tenants` | `admin:policies` |
| `/admin/access` | IAM & Role Management | `POST /v1/api/identity/users/manage` | `domains/identity` | `admin:users` |

