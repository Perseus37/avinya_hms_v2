# Avinya HMS – Complete Application Documentation
## Comprehensive Technical & Operational Manual

**Document Version:** `2.1.0-ENTERPRISE`  
**Classification:** Enterprise Healthcare Operating System (HMS / EMR / LIS / RIS / RCM)  
**Target Environments:** Cloud Native (AWS / GCP / Azure), Hybrid Cloud, Air-Gapped Hospital Clusters  
**Compliance & Regulatory Mandates:** India DPDP Act 2023, ABDM M1–M3, NHCX, NABH 5th Edition, JCI 7th Edition  

---

## 1. System Architecture & Multi-Tier Topology

Avinya HMS is structured as a **Modular Monolith with an Autonomous SaaS Fleet Control Plane** and a **Dedicated Client Clinical Workstation SPA**:

1. **Hospital Engine Backend (`backend/main.py`):** FastAPI application mounted at `:8000` providing 26 clinical and administrative domain modules (`/v1/api/*`), multi-tenant dynamic connection pooling, column-level AES-256-GCM envelope encryption, and Clinical Decision Support (CDS).
2. **Nexus SaaS Control Plane (`backend/control_plane/app.py`):** Autonomous fleet orchestration engine mounted at `:8080` for tenant lifecycle provisioning, database migrations, catalog seeding, and synthetic sandbox sanitization.
3. **Clinical Workstation SPA (`hospital-ui/`):** React 18, TypeScript, Tailwind CSS single-page application providing 9 unified hospital workspaces, CCOW patient safety banner, dynamic facility matrix builder, and zero-chrome isolated thermal printing.
4. **Onboarding & Migration Console (`onboarding-ui/`):** Vite/React console for platform operators and hospital IT directors to execute data imports and migration scripts.

---

## 2. Clinical & Operational Workspaces

The hospital frontend provides 9 specialized workstations engineered for maximum clinical safety and velocity:

### 2.1 Patient Registration & Front-Desk Intake (`PatientRegistrationWorkspace.tsx`)
- **Master Patient Index (MPI):** Deduplicated cross-encounter demographic identification with ABHA and National ID verification.
- **Unified Fast-Track Intake:** Eliminates navigation fragmentation by allowing front-desk receptionists to register demographics, select an attending physician, collect initial consultation fees, and generate an OPD queue token in one action.
- **DPDP Act 2023 Consent Collection:** Mandatory digital consent recording under Section 6 of India's DPDP Act with granular purpose binding.
- **Isolated Wristband Printing:** Immediate generation of thermal barcode patient wristbands isolating `.print-wristband` without application chrome.

### 2.2 Inpatient Admission & Bed Allocation ADT (`InpatientAdmissionWorkspace.tsx`)
- **MPI Autocomplete Search:** Instant demographic auto-population by typing patient MRN or name.
- **500+ Bed Scale Hierarchy:** Multi-tier navigation across Campuses, Towers, Floors, Wards, and Beds with real-time occupancy status indicators (Available, Occupied, Cleaning, Maintenance, Isolation).
- **Medico-Legal Case (MLC) Protocol:** Automated Section 39 CrPC intimation generation for RTAs, trauma, burns, and poisonings.
- **TPA Pre-Authorization:** Tracks insurer pre-auth approval numbers, cashless limits, and co-payment obligations before bed allocation.

### 2.3 Doctor Clinical Cockpit & CPOE Consultation (`DoctorCockpit.tsx`)
- **Longitudinal EMR Timeline:** Continuous clinical encounter history, previous vitals, allergies, and diagnostic reports.
- **SOAP Clinical Note Editor:** Structured Subjective, Objective, Assessment, and Plan documentation with ICD-10 diagnosis integration.
- **Clinical Decision Support (CDS) Radar:** Real-time drug-drug interaction (DDI) and allergy conflict alerts with mandatory clinical override logging.
- **1-Click CPOE Order Sets:** Instant ordering of disease-specific medication, laboratory, and imaging bundles (e.g. ACS Chest Pain Protocol, Stroke Bundle).

### 2.4 Ward Nursing Station & Bedside eMAR (`WardNursingStation.tsx`)
- **Electronic Medication Administration Record (eMAR):** Visual time-grid tracking medication administration schedules across morning, afternoon, evening, and night rounds.
- **BCMA 2D Barcode Verification:** Enforces the Joint Commission / NABH **"5 Rights"** (Right Patient, Right Drug, Right Dose, Right Route, Right Time) via optical scanner prior to administration.
- **NEWS2 Deterioration Escalation:** Automated National Early Warning Score 2 computation triggering Rapid Response Team (RRT) / Code Blue alerts for scores $\ge 7$.
- **SBAR Shift Handover:** Structured Situation, Background, Assessment, Recommendation handover Kardex.

### 2.5 Emergency Department Triage Board (`EmergencyTriageBoard.tsx`)
- **Emergency Severity Index (ESI 1–5):** Visual Kanban board categorizing emergency admissions by clinical urgency.
- **Glasgow Coma Scale (GCS) Calculator:** Objective 3-part neurological motor, verbal, and eye assessment.
- **Code Red Mass Casualty Protocol:** One-click disaster activation unlocking anonymous rapid triage tags (`DISASTER-TRIAGE-001` to `999`) and overriding bed reservations.

### 2.6 Central Pharmacy & NDPS Vault (`PharmacyWorkspace.tsx`)
- **Real-Time Formulary Dispensing:** Direct synchronization with doctor CPOE orders with stock availability indicators and generic substitution hints.
- **Schedule H1 & X Narcotics Vault:** Perpetual double-witness digital ledger for controlled substances requiring dual staff authorization and automated count verification.

### 2.7 Diagnostic Laboratory Information System (`DiagnosticsWorkspace.tsx`)
- **Specimen Accessioning & Barcoding:** Generates Code-128 specimen labels with draw-time and phlebotomy tracking.
- **Panic Critical Value Protocol:** Automated detection of panic delta results enforcing documented telephone read-back with attending clinician within 15 minutes.
- **DICOM PACS Viewer:** Integrated medical imaging viewer with window-leveling, pan, zoom, and radiologist report editor.

### 2.8 Cashier Counter & TPA Insurance Billing (`BillingWorkspace.tsx`)
- **Categorized Folio Aggregation:** Automated accumulation of Bed Rent, Nursing Care, Doctor Visits, Lab Tests, OT Charges, and Pharmacy Drugs.
- **TPA / Cashless Split Allocator:** Segregates Insurance Approved amounts, Non-Payable consumable items, and Patient Co-pay balances.
- **Multi-Tender Receipting:** Supports split tenders (Cash, Card, UPI, Bank Transfer) with automated GST calculation and thermal receipt generation.

### 2.9 Executive Command HUD & Master Administration (`AdminWorkspace.tsx`)
- **Operational Metrics:** Hospital Occupancy %, Average Length of Stay (ALOS), Bed Turnover Interval, and Unbilled Folio WIP.
- **700+ Metric Cube Explorer:** Interactive multidimensional KPI explorer covering Clinical Quality, Utilization, Finance, Pharmacy, and Compliance.
- **Hospital Master & Facility Builder:** Live configuration console for Facility Bed Matrix (Towers, Floors, Wards, Beds), Doctor Rostering & Pricing, Hospital Identity/Letterhead, and Policy Rules.

---

## 3. Dynamic Hospital Customization & Policy Engine

All hospital master data is decoupled from hardcoded source code and managed dynamically via [`HospitalConfigContext.tsx`](file:///v:/avinya_hms/hospital-ui/src/core/context/HospitalConfigContext.tsx):
- **Facility Hierarchy:** Custom creation of Towers, Floors, Specialty Wards, Bed counts, and Room Tariffs.
- **Doctor Roster & Tariffs:** Registration of attending clinicians, NMC registration numbers, department affiliations, OPD consult fees, and IPD round charges.
- **Hospital Identity:** Configurable hospital name, ROHINI/NHCX code, NABH/JCI accreditation numbers, address, and emergency helpline shown across receipts and letterheads.
- **Clinical Policies:** Toggleable statutory requirements including mandatory MLC intimations, mandatory ABHA verification, dual-witness narcotics rules, and 3-tier discharge clearance.

---

## 4. Enterprise RBAC & Security Session Architecture

### Cryptographic Role Binding
In production builds, user roles are derived cryptographically from verified JWT identity claims (`user.roles` and `is_superuser`). Users cannot arbitrarily change roles in the navbar. Role simulation is strictly demoted to local development mode (`import.meta.env.DEV`) and is clearly tagged as a simulator.

### Granular Capability Gating
All operational actions in the UI are protected via `<PermissionGate permission="...">`:
- `patient.register`
- `bed.allocate` / `bed.transfer`
- `order.cpoe_prescribe`
- `clinical.sign_notes`
- `discharge.clinical_sign`
- `nurse.administer_emar`
- `billing.tpa_approve`
- `config.facility_manage`

---

## 5. Isolated Hardware Printing Engine

Standard web printing cascades dark mode styling and application navigation onto physical printers. Avinya HMS implements dedicated `@media print` CSS rules in [`index.css`](file:///v:/avinya_hms/hospital-ui/src/index.css):
- Statically strips top navbars, sidebars, patient safety banners, and modal backdrop chrome.
- Isolates `.print-area` and `.print-wristband` containers with high-contrast pure white background and black text.
- Supports 2-inch thermal continuous roll wristbands and standard A4/A5 clinical case sheets.

---

## 6. Provisioning & Scaling New Instances

* **Horizontal Scaling (Same Environment):** To handle increased hospital traffic, scale the stateless API containers (`docker-compose up -d --scale api=3`). A reverse proxy (NGINX or Traefik) distributes incoming requests across active ports via round-robin or least-connections routing.
* **New Environment Provisioning (New Hospital Tenant):** When onboarding a new hospital client, use the Nexus Control Plane API (`POST /tenants/provision`) or Infrastructure as Code (Terraform) to provision an isolated PostgreSQL database (`hms_{tenant_slug}`), initialize the blank schema via Alembic, seed baseline catalogs, and register tenant routing rules.

---

## 7. Maintenance Procedures

* **Zero-Downtime Rolling Updates:** Orchestrators (Kubernetes or Docker Swarm) perform rolling updates. The load balancer stops sending traffic to Container A, updates it, verifies the `/health` endpoint returns 200, and routes traffic back before updating Container B.
* **Hard Maintenance (Scheduled Downtime):** For structural migrations requiring data freeze:
  1. Route NGINX traffic to serve a static HTTP 503 "Under Scheduled Maintenance" JSON response for `/api/*` routes.
  2. Spin down API and background worker containers to sever active database connections.
  3. Execute core upgrades and Alembic schema migrations.
  4. Run automated regression test suites against the migrated database.
  5. Remove the 503 maintenance block to restore clinical traffic.

---

## 8. Database Migrations (Zero-Downtime Strategies)

Executing `alembic upgrade` on a live Tier-1 database requires strict operational patterns:
* **The Expand and Contract Pattern:** Never rename, change the type of, or delete a column that live traffic is actively querying.
  * **Expand:** Add the new column via Alembic migration.
  * **Dual-Write:** Deploy API code that writes to both old and new columns, with background script backfilling historical data.
  * **Contract:** Deploy API update that reads/writes *only* to the new column, followed by a cleanup migration to drop the legacy column.
* **Separation of Concerns:** Always run migrations in a separate, ephemeral container before newly updated API instances are allowed to boot.

---

## 9. Production Incident Response & Telemetry

* **Correlation Tracking via `X-Request-ID`:** Every HTTP request carries an `X-Request-ID` generated by edge middleware. Searching this ID in log aggregators (Datadog, CloudWatch, ELK) traces the request through middleware, authentication, database locks, and response serializing.
* **Database Deadlock Handling:** The system utilizes `with_for_update(nowait=True)` for sensitive resources (beds, narcotics, medication stock). Concurrent transaction collisions immediately return HTTP 409 Conflict rather than hanging indefinitely, allowing frontend UI to automatically prompt user retry.
* **Disaster Recovery & Rollback:**
  1. Revert container image tags in orchestrator to previous stable release.
  2. If backwards-incompatible database schema changes occurred, execute `alembic downgrade -1`.
  3. In extreme corruption scenarios, utilize PostgreSQL Point-in-Time Recovery (PITR) to restore the cluster to the exact minute preceding deployment.
