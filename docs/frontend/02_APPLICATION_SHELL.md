# Avinya HMS – Enterprise Application Shell Specification
## Document `02_APPLICATION_SHELL.md`
### The Application Chrome, Duty Context, Global Patient Spine, Omnibox & Universal Work Queues

**Document Version:** `3.0.0-ENTERPRISE-SPEC`  
**Classification:** Enterprise Multi-Tenant Hospital Operating System  
**Parent Document:** [`00_FRONTEND_MASTER_SPEC.md`](00_FRONTEND_MASTER_SPEC.md)  

---

## 1. Master Shell Architecture & Layout Regions

The application shell establishes the structural foundation for all 84 hospital screens. It guarantees that clinical users always know **who they are, which facility/shift they are operating in, which patient is active, and what urgent tasks require immediate action**:

```
┌────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ [TOP NAVIGATION BAR: Identity, Duty Context, Omnibox Search, Alerts, Tasks, User Card]                 │
├────────────────────┬───────────────────────────────────────────────────────────────────────────────────┤
│ [LEFT NAVIGATION]  │ [GLOBAL PATIENT SAFETY SPINE (Persistent when a patient is actively loaded)]       │
│ Grouped by duty    ├───────────────────────────────────────────────────────────────────────────────────┤
│ Collapsible rail   │ [PAGE HEADER: Breadcrumbs, Screen Title, Quick Filters, Primary Action Button]    │
│ Role-gated items   ├────────────────────────────────────────────────────────────────┬──────────────────┤
│                    │ [MAIN CONTENT REGION]                                          │ [CONTEXT DRAWER] │
│                    │ High-density clinical table, Kanban board, or consultation     │ Collapsible      │
│                    │ workspace (Virtual scroll, 60fps rendering)                    │ Audit history    │
│                    │                                                                │ Clinical notes   │
│                    │                                                                │ Help & hotkeys   │
├────────────────────┴────────────────────────────────────────────────────────────────┴──────────────────┤
│ [STATUS BAR: Node Status ● | WebSocket Active ● | Time Zone (Asia/Kolkata) | X-Request-ID | v3.0.0]    │
└────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Region-by-Region Elemental Specification

### 2.1 Top Navigation Bar (Height: 56px / `h-14`)

```
+--------------------------------------------------------------------------------------------------------+
| [LOGO] AVINYA | Apollo Hospitals - Jubilee Hills v | Cardiology v | Morning v | [Cmd+K Search...] | [7] | [3] | [Dr. Gupta] [v] |
+--------------------------------------------------------------------------------------------------------+
```

1. **Brand & Enterprise Emblem:**
   - Display: Hospital brand mark + `AVINYA HMS`.
   - Tooltip: Displays software version, build hash, and tenant node health.
2. **Hospital & Multi-Branch Duty Context Switcher:**
   - **Hospital / Branch Dropdown:** Allows physicians or administrators with multi-facility privileges to switch location:
     - Group: `Apollo Hospitals Group`
     - Hospital: `Apollo Hyderabad`
     - Branch: `Jubilee Hills Campus` (Active) vs `Secunderabad Clinic`
   - **Department Selector:** Sets current clinical scope (`Cardiology`, `Emergency`, `General Surgery`).
   - **Shift Selector:** Displays active working shift (`☀️ Morning: 07:00–15:00`, `⛅ Evening: 15:00–23:00`, `🌙 Night: 23:00–07:00`).
3. **Universal Omnibox Search Trigger:**
   - Keyboard Shortcut: `Cmd+K` (macOS) or `Ctrl+K` (Windows/Linux).
   - Placeholder: `"Search patient by MRN, name, phone, bed, invoice, or jump to screen..."`.
4. **Global Task Center ("My Work") Pill:**
   - Visual Badge: Count of pending tasks assigned to current user (e.g. `[7]`).
   - Click Action: Opens the slide-over My Work Drawer.
5. **Clinical Notification Radar Bell:**
   - Visual Badge: Count of unread clinical alerts (e.g. `[3]`).
   - Color Coding: Amber for warnings; flashing red for critical panic values / Code Blue.
6. **User Identity & Cryptographic Role Chip:**
   - Displays authenticated clinician's title and name (`Dr. Ramesh Gupta, MD`).
   - Verified Role Chip: `[ATTENDING PHYSICIAN]` (Derived from JWT claims; immutable in production).
   - In local development mode (`import.meta.env.DEV`), shows the amber `[DEV SIMULATOR]` dropdown.

---

### 2.2 Global Patient Safety Spine (Height: 48px / `h-12`)

When a patient is actively selected anywhere in the hospital, the **Global Patient Spine** locks into position immediately below the top navigation bar. It remains sticky across all page transitions until explicitly dismissed:

```
+-----------------------------------------------------------------------------------------------------------------------------+
| PATIENT: Doe, John (42y/M) | MRN: AV-2026-00412 | ABHA: 91-4829-1029-41 | O+ | Bed: ICU-A-104 | Attending: Dr. Gupta       |
| [!] ALLERGIES: Penicillin (Anaphylaxis) | FALL RISK: HIGH | CODE STATUS: FULL CODE | Payer: Star Health Cashless    [Close X] |
+-----------------------------------------------------------------------------------------------------------------------------+
```

#### Patient Spine Field Catalog:
| Data Element | Visual Format | Clinical Safety Rationale |
|---|---|---|
| **Patient Full Name** | High-contrast bold (`text-slate-100 font-bold`) | Prevents misidentification during cross-bed orders. |
| **Age & Biological Sex** | E.g., `42y / Male` | Vital for pediatric/geriatric dosage checks. |
| **Medical Record Number (MRN)** | Monospace chip (`font-mono bg-slate-900 px-1.5`) | Canonical institutional patient identifier. |
| **National ABHA ID** | Verified checkmark icon + formatted ID | National ABDM health record synchronization. |
| **Blood Group** | Prominent red badge (`bg-rose-950 text-rose-300`) | Immediate blood transfusion safety. |
| **Active Location / Bed** | E.g. `Ward: ICU-A / Bed: 104` or `OPD Waiting` | Real-time physical location of patient. |
| **Attending Consultant** | Clinician full name & specialty | Accountability for active medical decision making. |
| **Severe Allergy Strip** | Flashing amber/red chip with tooltip | Instant visibility of lethal drug contraindications. |
| **Clinical Risk Flags** | Fall Risk, Aspiration Risk, Isolation Tag | Nursing safety protocols. |
| **Code Status** | `FULL CODE` vs `DNR / DNI` | Critical emergency resuscitation orders. |
| **Payer & Pre-Auth Status** | E.g. `Star Health (Cashless ₹2.5L Approved)` | Financial clearance visibility. |
| **Dismiss Action Button** | Clear `[Close X]` button | Unloads active patient context to prevent order cross-contamination. |

---

### 2.3 Left Navigation Menu (Width: 240px / Collapsible to 64px Rail)

The left navigation adapts dynamically based on the user's role and licensed modules. It groups capabilities into 7 logical clinical and administrative domains:

```text
┌ Left Navigation ───────────────────────┐
│ [WORKSPACE]                            │
│   Home Cockpit                         │
│   My Tasks (7)                         │
│   Notification Radar                   │
│                                        │
│ [PATIENTS & VISITS]                    │
│   Master Patient Index                 │
│   Registration & Intake                │
│   OPD Today & Queues                   │
│   Appointment Scheduler                │
│   Inpatient ADT & Bed Board            │
│   Emergency Triage                     │
│                                        │
│ [CLINICAL CARE]                        │
│   Doctor Cockpit                       │
│   Ward Nursing Station                 │
│   eMAR Medication Grid                 │
│   Operating Theatre                    │
│                                        │
│ [DIAGNOSTICS & DRUGS]                  │
│   Laboratory LIS                       │
│   Radiology & PACS                     │
│   Central Pharmacy                     │
│   Controlled Substances Vault          │
│   Blood Bank                           │
│                                        │
│ [FINANCE & SUPPLY]                     │
│   Cashier & Billing                    │
│   TPA Insurance & Claims               │
│   Procurement & POs                    │
│   Inventory & Stores                   │
│                                        │
│ [QUALITY & COMPLIANCE]                 │
│   Incident Register (CAPA)             │
│   NABH/JCI Quality Radar               │
│   DPDP Privacy Portal                  │
│   Audit Vault                          │
│                                        │
│ [ADMINISTRATION]                       │
│   Facility Master & Beds               │
│   Doctor Roster & Tariffs              │
│   Staff Access & Roles                 │
└────────────────────────────────────────┘
```

- **Collapsible Rail Mode:** On tablet viewports or by clicking the collapse toggle, the sidebar minimizes to an icon rail (`w-16`), expanding tooltips on hover.
- **Badge Indicators:** Real-time counter pills showing pending counts (e.g. `OPD Queues (14)`, `Panic Labs (2)`).

---

### 2.4 Context Drawer (Width: 380px Slide-Over)

The Context Drawer slides in from the right edge without displacing or re-rendering the active workspace:
- **Clinical Fast-Notes:** Allows nurses or doctors to review past notes while authoring a new order.
- **Patient Chart Audit Trail:** Shows which staff members recently viewed or edited the active record.
- **Keyboard Shortcuts Reference:** Instant hotkey cheatsheet (`Cmd+K`, `Alt+1` to `Alt+9`, `Esc`).

---

### 2.5 Global Omnibox Search Specification (`Cmd+K` / `Ctrl+K`)

Pressing `Cmd+K` opens an instantaneous, keyboard-navigable modal overlay that performs deep unified search across 8 hospital entities:

```
┌ Search Hospital Records & Navigation (Cmd+K) ────────────────────────────────────────────────────────┐
│ > 9812304918                                                                                         │
├──────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ PATIENT MATCHES                                                                                      │
│ [User] Sharma, Sunita (58F) | MRN-2026-00319 | Ph: +91 98123 04918 | OPD Wait (Cardio)              │
│                                                                                                      │
│ INPATIENT ADMISSIONS                                                                                 │
│ [Bed]  Sharma, Sunita | Bed: ICU-A-102 | Tower: Main Block | Admitted: 29-Oct-2026                  │
│                                                                                                      │
│ BILLING INVOICES                                                                                     │
│ [Bill] INV-2026-09142 | Sharma, Sunita | Amount: ₹48,250 | Status: PENDING TPA PRE-AUTH             │
│                                                                                                      │
│ WORKSPACE NAVIGATION                                                                                 │
│ [Jump] Go to Outpatient Queue Board                                                Alt+1             │
│ [Jump] Go to Emergency Triage Board                                                Alt+5             │
│ [Jump] Go to Ward Nursing Station                                                  Alt+4             │
└──────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

#### Defect Fix Enforcement (B-01):
- Typing partial phone numbers (e.g. `98123`) **never** automatically opens the patient record or erases the search input.
- Automatic navigation only occurs if the user explicitly presses `Enter` on a highlighted result or types a 100% complete MRN (`MRN-YYYYMM-XXXXXX`).

---

### 2.6 Global Task Center ("My Work")

The "My Work" drawer organizes assigned clinical and administrative tasks into 4 urgent buckets:

1. **Overdue / Breached:**
   - Overdue medications past scheduled round time.
   - Unsigned clinical encounter notes older than 24 hours.
   - Panic laboratory results awaiting documented telephone read-back (>15 minutes).
2. **Due Today:**
   - Scheduled outpatient consultations remaining in queue.
   - Planned surgical cases for the active shift.
   - Inpatient discharge summaries awaiting consultant sign-off.
3. **Pending Actions / Approvals:**
   - Ward medication return credits awaiting pharmacist verification.
   - High-cost purchase requisitions awaiting Medical Director sign-off.
   - TPA insurance pre-auth query letters from insurers.
4. **Delegated & Watchlist:**
   - High-fall-risk patients flagged for 2-hour neurological observation checks.

---

### 2.7 Persistent Status Bar (Height: 28px / `h-7`)

The bottom bar provides continuous operational telemetry:
- **Hospital Sync Status:** `● 12ms Sync (PostgreSQL Pool Healthy)`.
- **Real-Time WebSocket Feed:** `● Live Telemetry Active` (Redis Pub/Sub).
- **Hospital Time Zone:** `Asia/Kolkata (IST UTC+05:30)`.
- **Request Correlation ID:** E.g. `X-Request-ID: f47ac10b-58cc-4372-a567-0e02b2c3d479` (1-click copy for IT helpdesk).
- **Software Build:** `Avinya HMS v3.0.0-ENTERPRISE (Release e2fbd09)`.
