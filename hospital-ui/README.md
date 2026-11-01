# Avinya HMS — Clinical & Operational Workspace Frontend

A high-density, zero-latency clinical workspace shell designed for hospitals, outpatient clinics, intensive care units, and diagnostic centers. Built with **React 18/19**, **TypeScript**, **Vite 6**, and **Tailwind CSS**.

---

## 1. Workspaces & Perspectives

The frontend provides dedicated, role-tailored perspectives for 7 critical hospital domains:

1. **Doctor Cockpit (`/doctor`)**
   - Live OPD consultation queue with status transitions (`BOOKED`, `CHECKED_IN`, `IN_CONSULTATION`, `COMPLETED`).
   - Integrated CCOW-style Patient Safety Banner with allergies, blood group, and vital surveillance.
   - SOAP notes documentation with primary diagnosis selection from ICD-10-CM.
   - e-Prescriptions (eRx) with real-time Drug-Drug Interaction (DDI) screening.
   - Diagnostic test ordering with routine and STAT priorities.
   - Consultation summary slip generation and digital sign-off.

2. **Ward Nursing Station (`/nursing`)**
   - Real-time Inpatient Bed Census Matrix across wards and rooms.
   - Occupancy tracking (`AVAILABLE`, `OCCUPIED`, `CLEANING`).
   - Interactive **NEWS2 Vital Signs Scoring Calculator** (Respiration, SpO2, Oxygen Therapy, Systolic BP, Heart Rate, Consciousness Alert/CVPU, Temp).
   - Bed sanitization workflow management.

3. **Emergency Department (ED) Triage & Trauma Board (`/triage`)**
   - 5-column **Emergency Severity Index (ESI 1 to 5)** Kanban board.
   - Bedside emergency patient intake with **Glasgow Coma Scale (GCS 3–15)** calculation.
   - Medico-Legal Case (MLC) flagging and tracking.
   - One-click **Hospital Code Red (Trauma Team Activation)** trigger.

4. **Central Pharmacy & Controlled Substances Vault (`/pharmacy`)**
   - Pending e-Prescription dispensing queue.
   - **2D DataMatrix GS1 Barcode Scanner simulator** for batch number and expiry date verification.
   - **NDPS Schedule H1 Narcotics Vault** with dual-custody mandatory witness sign-off under Rule 66 / Form 3C.

5. **Diagnostics & Laboratory Information System (LIS) (`/diagnostics`)**
   - Specimen accessioning lifecycle (`COLLECTED` $\to$ `IN_ANALYSIS` $\to$ `AUTHORIZED`).
   - Analyte numerical result entry with physiological reference range bounds checking.
   - **Panic Critical Delta Callout documentation** with attending physician verbal read-back recording.

6. **Cashier Billing Counter & Reconciliation (`/billing`)**
   - Counter shift open/close lifecycle and starting cash float management.
   - Split tender tracking (Cash, UPI with QR simulator, Card, NetBanking).
   - Invoice generator and printable cashier shift handover reconciliation receipts.

7. **Executive HUD & Statutory Registers (`/admin`)**
   - Live database record inventory across all operational tables.
   - 1-click RFC 4180 UTF-8 BOM CSV exports and live preview modals:
     - Daily Midnight ADT Bed Census Register
     - Cashier Shift Handover & Reconciliation Ledger
     - NDPS Schedule H1 Controlled Substances Register
     - Accounts Receivable (AR) Aging Ledger
     - Bio-Medical Waste (BMW) Management Statutory Register
   - **DPDP Digital Personal Data Protection Act (2023)** Consent Audit Ledger with SHA-256 tamper-evident integrity hashes.

---

## 2. Running Locally for Development

### Prerequisites
- Node.js 18+ or 20+
- npm 9+
- Backend API running on `http://127.0.0.1:8000` (optional for mock preview)

### Quick Start
```bash
# Navigate to the frontend directory
cd hospital-ui

# Install dependencies
npm install

# Start Vite development server with Hot Module Replacement (HMR)
npm run dev
```

The app will start at `http://localhost:5174/`.
API calls to `/api/*` and `/v1/*` are automatically proxied to `http://127.0.0.1:8000`.

### Scripts
- `npm run dev`: Starts Vite dev server on port `5174` (bound to `0.0.0.0`).
- `npm run build`: Type-checks with `tsc` and builds production bundle to `dist/`.
- `npm run preview`: Previews the production build locally on port `4174`.
- `npm run lint`: Runs TypeScript validation without emitting files.

---

## 3. Running with Docker (Development Mode)

The development stack in the project root includes `hospital-ui` configured for live development with volume-mounted source code:

```bash
# Start the full development stack including PostgreSQL, Redis, API, and Hospital UI
docker compose up hospital-ui

# Or start all development services
docker compose up
```

- Accessible at: `http://localhost:5174`
- Changes in `hospital-ui/src/` hot-reload instantly.

---

## 4. Running with Docker (Production Mode)

The production stack uses the multi-stage `Dockerfile` with a hardened Nginx Alpine image and Traefik reverse-proxy:

```bash
# Build and deploy the production stack
docker compose -f docker-compose.prod.yml up -d hospital-ui
```

- Traefik routes: `https://app.${BASE_DOMAIN}` or `https://clinical.${BASE_DOMAIN}`
- Container runs as unprivileged user with dropped capabilities and health checks enabled on `/healthz`.

---

## 5. Direct Backend Unified Serving (Monolithic / Local)

When running the backend server locally or in staging:
```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```
Visiting `http://localhost:8000/app/` serves the built `hospital-ui/dist` bundle directly, providing a complete all-in-one endpoint.

---

## 6. Global Shortcuts & Navigation

- `Ctrl + K` or `Cmd + K`: Open Patient Quick Search command palette.
- Workspace switcher on the left sidebar: Select between any of the 7 clinical/operational workspaces.
