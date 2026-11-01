# Avinya HMS — Enterprise KPI & Metric Inventory Master Catalog

> **Scope**: Master reference catalog defining the full metric universe (700+ metrics across 32 hospital domains and SaaS infrastructure) for Avinya Hospital Management System.
> **Dimensional Cube Coordinates**: `Time × Branch × Department × Specialty × Doctor × Ward × Service × Payer × Patient Type × Encounter Type × Shift`

---

## Dimensional Cube Architecture

Every metric in this inventory is designed to be queryable and slice-and-diceable across the following **11 standardized dimensions**:

| Dimension | Description & Levels of Granularity |
| :--- | :--- |
| **1. Time** | Real-time (10s) $\to$ Minute $\to$ Hour $\to$ Shift $\to$ Day $\to$ Week $\to$ Month (MTD) $\to$ Quarter $\to$ Year (YTD) |
| **2. Branch** | Enterprise Federation Root $\to$ Hospital Network $\to$ Multi-Branch Institution $\to$ Hospital Unit / Facility |
| **3. Department** | Clinical (Cardiology, Oncology, Ortho, etc.) / Para-clinical (Lab, Radiology) / Support (Pharmacy, Stores, Bio-waste) / Admin |
| **4. Specialty** | Super-specialty $\to$ Broad specialty $\to$ Sub-specialty clinic (e.g. Interventional Cardiology vs Electrophysiology) |
| **5. Doctor / Clinician** | Senior Consultant $\to$ Attending Physician $\to$ Resident $\to$ Fellow $\to$ Medical Officer |
| **6. Ward / Unit** | ICU / CCU / NICU / PICU $\to$ HDU $\to$ Post-Op Recovery $\to$ Private Deluxe $\to$ Semi-Private $\to$ General Ward $\to$ Daycare |
| **7. Service / Charge Item** | Consultation $\to$ Investigation Panel $\to$ Bed Stay Tariff $\to$ OR / OT Procedure $\to$ Pharmacy Formulation |
| **8. Payer / Tender** | Self-Pay (Cash / UPI / Card / Wire) $\to$ Private TPA Insurer $\to$ Corporate Panel $\to$ Government Social Scheme (PM-JAY, CGHS) |
| **9. Patient Type** | Pediatric $\to$ Adult $\to$ Geriatric $\to$ Maternity $\to$ High-Risk / Immunocompromised |
| **10. Encounter Type** | Outpatient (OPD) $\to$ Inpatient (IPD) $\to$ Emergency Department (ED/Trauma) $\to$ Daycare $\to$ Telehealth |
| **11. Shift** | Morning (08:00–16:00) $\to$ Evening (16:00–00:00) $\to$ Night / Grave (00:00–08:00) $\to$ Split Shift |

---

## 1. Executive / Hospital

- Total Revenue
- Net Revenue
- Gross Revenue
- Total Collections
- Collection Rate
- Outstanding Receivables
- AR Days
- Revenue Growth %
- EBITDA / Operating Margin
- Revenue per Patient
- Revenue per Encounter
- Revenue per Bed
- Revenue per Occupied Bed
- Revenue by Branch
- Revenue by Department
- Revenue by Specialty
- Revenue by Doctor
- Revenue by Service
- Revenue by Payer
- Revenue by Payment Method
- Patient Volume
- New Patients
- Returning Patients
- Unique Patients
- OPD Volume
- IPD Admissions
- IPD Discharges
- ED Visits
- Surgeries
- Lab Orders
- Radiology Orders
- Pharmacy Prescriptions
- Average Length of Stay (ALOS)
- Bed Occupancy Rate (BOR %)
- Bed Turnover
- Patient Satisfaction
- Complaint Rate
- Complaint Resolution Rate
- Overall Mortality
- Readmission Rate
- Incident Rate
- Staff Utilization

---

## 2. Patient Access

- Appointment Requests
- Appointment Bookings
- Appointment Conversion Rate
- Available Slots
- Booked Slots
- Consumed Slots
- Slot Utilization
- Unused Slots
- Walk-ins
- Same-day Appointments
- New-patient Appointments
- Follow-up Appointments
- Referral Appointments
- Appointment Cancellation Rate
- No-show Rate
- Reschedule Rate
- Average Booking Lead Time
- Median Booking Lead Time
- P90 Booking Lead Time
- Average Days to Next Appointment
- Median Days to Next Appointment
- P90 Days to Next Appointment
- Appointment Waitlist
- Waitlist Aging
- Abandoned Booking Rate
- Access SLA Compliance
- Peak Booking Period
- Peak Arrival Period

---

## 3. Registration & Master Patient Index (MPI)

- Registrations
- New Registrations
- Returning Registrations
- Registration Rate
- Registration TAT
- Registration Queue
- Registration Waiting Time
- Registration SLA Breach
- Duplicate Patient Rate
- Duplicate MRN Rate
- Patient Merge Count
- Patient Demographic Completeness
- Contact Information Completeness
- ABHA Linkage Rate
- Consent Completion Rate (DPDP Act 2023)

---

## 4. Outpatient Department (OPD)

- Scheduled Appointments
- Arrived Patients
- Waiting Patients
- Patients in Consultation
- Completed Consultations
- Cancelled Consultations
- No-shows
- Walk-ins
- OPD Volume
- Patients per Doctor
- Patients per Hour
- Slot Utilization
- Doctor Utilization
- Average Waiting Time
- Median Waiting Time
- P90 Waiting Time
- P95 Waiting Time
- Consultation Duration
- Median Consultation Duration
- P90 Consultation Duration
- Waiting SLA Compliance
- Waiting SLA Breach
- Follow-up Rate
- New Patient Rate
- Referral Conversion
- OPD Revenue
- Revenue per Consultation

---

## 5. Inpatient Department (IPD)

- Current Inpatients
- Admissions
- Discharges
- Transfers
- Admission Rate
- Discharge Rate
- Average LOS
- Median LOS
- P90 LOS
- Long-stay Patients (> 21 days)
- Expected Discharges
- Delayed Discharges
- Discharge Delay Rate
- Admission TAT
- Bed Assignment TAT
- Transfer TAT
- Discharge TAT
- Discharge Summary Pending
- Discharge Billing Pending
- Pharmacy Clearance Pending
- Insurance Clearance Pending
- Discharge Completion Rate
- Readmission Rate (30-day)
- Mortality Rate

---

## 6. Emergency Department (ED & Trauma)

- ED Arrivals
- Arrivals per Hour
- Current ED Patients
- Waiting Patients
- Triage Queue
- Treatment Queue
- Critical Patients
- Resuscitation Patients (ESI-1)
- ED Admissions
- ED Discharges
- ED Transfers
- Left Without Being Seen (LWBS)
- LWBS Rate
- ED Mortality
- Door-to-Triage Time
- Door-to-Doctor Time
- Door-to-Treatment Time
- Door-to-Disposition Time
- ED Length of Stay (LOS)
- Admission Decision TAT
- Transfer TAT
- ED Bed Occupancy
- ED Crowding
- ED Capacity Utilization
- Emergency Procedure Volume
- Ambulance Arrivals

---

## 7. Patient Flow & Throughput

- Registration $\to$ Arrival TAT
- Arrival $\to$ Triage TAT
- Arrival $\to$ Consultation TAT
- Consultation $\to$ Order TAT
- Order $\to$ Sample Collection TAT
- Collection $\to$ Result TAT
- Result $\to$ Doctor Acknowledgement TAT
- Admission $\to$ Bed Assignment TAT
- Bed Assignment $\to$ Transfer TAT
- Discharge Order $\to$ Billing TAT
- Billing $\to$ Payment TAT
- Payment $\to$ Physical Discharge TAT
- End-to-End Patient Journey Time
- Queue Length
- Queue Waiting Time
- SLA Compliance
- SLA Breach Rate
- Bottleneck Rate
- Abandonment Rate
- Patient Flow Throughput

---

## 8. Bed & Facility Capacity

- Total Beds
- Operational Beds
- Available Beds
- Occupied Beds
- Blocked Beds
- Cleaning Beds (Housekeeping)
- Maintenance Beds
- Reserved Beds
- Isolation Beds
- ICU Beds
- HDU Beds
- NICU Beds
- PICU Beds
- General Beds
- Private Beds
- Semi-private Beds
- Emergency Beds
- Maternity Beds
- Bed Occupancy %
- Bed Utilization %
- Bed Turnover
- Bed Turnover Interval
- Average Bed LOS
- Bed Assignment TAT
- Bed Cleaning TAT
- Bed Blocking Duration
- Bed Availability Rate
- Expected Admissions
- Expected Discharges
- Expected Occupancy
- Capacity Shortage
- Capacity Surplus

---

## 9. Doctor & Clinical Cockpit

- Scheduled Patients
- Arrived Patients
- Completed Patients
- No-shows
- Cancellations
- Walk-ins
- Patients per Day
- Patients per Hour
- Consultation Duration
- Waiting Time
- Slot Utilization
- Doctor Utilization
- Overtime
- Active Inpatients
- Active OPD Patients
- Pending Notes
- Pending Orders
- Pending Results
- Pending Prescriptions
- Critical Results
- Pending Consultations
- Pending Discharge Summaries
- Documentation Completion %
- Follow-up Rate
- New Patient Rate
- Patient Satisfaction
- Complaints
- Clinical Incidents
- Readmission Rate
- Revenue per Encounter
- Procedure Volume

---

## 10. Nursing & Ward Station

- Patients Assigned
- Patients per Nurse
- Acuity Distribution
- High-risk Patients
- Critical Patients
- Medication Tasks
- Medication Due
- Medication Overdue
- Medication Completion %
- Vitals Due
- Vitals Overdue
- Assessment Due
- Assessment Overdue
- Procedure Tasks
- Procedure Overdue
- Pending Specimen Collection
- Pending Transfers
- Pending Discharges
- Fall-risk Patients (Morse Scale)
- Pressure-injury-risk Patients (Braden Scale)
- Deteriorating Patients (NEWS2 $\ge$ 5)
- Escalations
- Nursing Documentation Completion
- Shift Workload
- Staffing Ratio
- Overtime

---

## 11. ICU & Critical Care

- ICU Occupancy
- ICU Available Beds
- ICU Admissions
- ICU Discharges
- ICU Transfers
- ICU LOS
- ICU Mortality
- ICU Readmission
- Ventilated Patients
- Ventilator Utilization
- Ventilator Days
- Non-Invasive Ventilation (NIV) Patients
- High-acuity Patients
- Critical Patients
- Deterioration Alerts
- Code Events (Code Blue)
- Emergency Interventions
- Central-line Days
- Catheter Days
- ICU Nurse/Patient Ratio
- ICU Doctor/Patient Ratio
- ICU Infection Rate
- Unplanned ICU Admission
- Unplanned ICU Readmission
- ICU Bed Demand
- ICU Capacity Forecast

---

## 12. Surgery & Operation Theatres (OT)

- Scheduled Surgeries
- Completed Surgeries
- Cancelled Surgeries
- Emergency Surgeries
- Elective Surgeries
- OT Utilization
- OT Available Hours
- OT Used Hours
- OT Idle Hours
- First-case On-time %
- Case Start Delay
- Case Turnaround Time
- Procedure Duration
- Recovery Duration (PACU)
- Cancellation Rate
- Cancellation Reasons
- Surgery Volume
- Surgery Revenue
- Surgeon Utilization
- OT Utilization by Theatre
- Complication Rate
- Surgical Site Infection (SSI) Rate
- Unplanned Return to OT
- 24-hour Return to OT
- Implant Usage
- Implant Cost
- Checklist Compliance (WHO Surgical Safety Checklist)

---

## 13. Laboratory Information System (LIS)

- Lab Orders
- Tests Ordered
- Samples Collected
- Samples Pending
- Samples Processing
- Tests Completed
- Rejected Samples (Hemolysis / Clotted / Insufficient)
- Rejection Rate
- Critical Results
- Unacknowledged Critical Results
- Result Acknowledgement Rate
- Lab TAT
- Median TAT
- P90 TAT
- P95 TAT
- TAT SLA Compliance
- TAT Breach Rate
- Repeat Tests
- Analyzer Utilization
- Analyzer Downtime
- Reagent Consumption
- Reagent Stock
- Reagent Stock-out
- QC Failures (Westgard Rules)
- Test Volume by Category
- Test Revenue

---

## 14. Radiology & Imaging (RIS / PACS)

- Imaging Orders
- Scheduled Studies
- Completed Studies
- Pending Studies
- Reporting Queue
- Reported Studies
- Critical Findings
- Unacknowledged Critical Findings
- Report TAT
- P50 Report TAT
- P90 Report TAT
- P95 Report TAT
- Modality Utilization
- CT Utilization
- MRI Utilization
- X-ray Utilization
- Ultrasound Utilization
- Equipment Downtime
- Repeat Imaging
- Cancellation Rate
- Radiologist Workload
- Imaging Revenue

---

## 15. Pharmacy & Dispensary

- Prescriptions
- Prescriptions Dispensed
- Pending Prescriptions
- Dispensing TAT
- Sales
- Revenue
- Gross Margin
- Net Margin
- Average Prescription Value
- Prescription Volume
- Returns
- Refunds
- Substitutions
- Stock Value
- Stock Turnover
- Days of Stock
- Stock-out Items
- Near-expiry Items
- Expired Items
- Dead Stock
- Slow-moving Stock
- Fast-moving Stock
- Reorder Items
- Wastage
- Controlled-drug Variance (NDPS)
- Purchase Value
- Purchase Price Variance
- Supplier Fill Rate

---

## 16. Blood Bank & Transfusion Services

- Total Units
- Available Units
- Reserved Units
- Issued Units
- Returned Units
- Expired Units
- Wasted Units
- Units by Blood Group (A+, A-, B+, B-, AB+, AB-, O+, O-)
- Crossmatch Requests
- Crossmatch Completion
- Blood Requests
- Pending Requests
- Emergency Requests
- Emergency Fulfillment Time
- Issue TAT
- Return Rate
- Wastage Rate
- Stock-out Risk
- Transfusion Reactions
- Transfusion Reaction Rate
- Blood Inventory Days

---

## 17. Materials Management & Inventory

- Inventory Value
- Inventory Quantity
- Stock Turnover
- Days of Inventory
- Stock-out Items
- Stock-out Rate
- Below Reorder Items
- Near-expiry Items
- Expired Items
- Dead Stock
- Slow-moving Stock
- Fast-moving Stock
- Wastage
- Shrinkage
- Stock Adjustment
- Adjustment Value
- Inventory Accuracy
- Cycle Count Accuracy
- Consumption Rate
- Consumption Trend
- Reorder Value

---

## 18. Procurement & Vendor Management

- Purchase Orders (PO)
- PO Value
- Purchase Value
- Pending POs
- Completed POs
- Cancelled POs
- PO Cycle Time
- Supplier Lead Time
- On-time Delivery %
- Fill Rate
- Supplier Rejection Rate
- Purchase Price Variance
- Contract Compliance
- Supplier Performance Score
- Supplier Concentration
- Pending Deliveries
- Purchase Returns
- Purchase Return Value
- Procurement Savings
- Procurement Cost Trend

---

## 19. Hospital Finance & Accounting

- Gross Revenue
- Net Revenue
- Collections
- Collection Rate
- Outstanding
- Accounts Receivable (AR)
- Accounts Payable (AP)
- AR Days
- AP Days
- Cash Balance
- Daily Collections
- MTD Revenue
- YTD Revenue
- Revenue Growth
- Expense
- Operating Expense (OPEX)
- Operating Margin
- Discount Value
- Discount Rate
- Refund Value
- Refund Rate
- Credit Notes
- Write-offs
- Write-off Rate
- Revenue per Patient
- Revenue per Encounter
- Revenue per Bed
- Revenue per Department
- Revenue per Specialty
- Revenue by Payer
- Revenue by Payment Method

---

## 20. Revenue Cycle Management (RCM)

- Charge Volume
- Expected Charges
- Captured Charges
- Missed Charges
- Charge Capture Rate
- Unbilled Services
- Unbilled Value
- Billing TAT
- Invoice Volume
- Invoice Value
- Paid Invoices
- Partial Payments
- Pending Payments
- Collection Rate
- Accounts Receivable (AR)
- AR Aging (0–30, 31–60, 61–90, > 90 days)
- Days in AR
- Claim Volume
- Claim Value
- Claim Submission Rate
- Claim Acceptance Rate
- Claim Rejection Rate
- Claim Denial Rate
- Denied Value
- Approved Value
- Settled Value
- Pending Settlement
- Settlement TAT
- Revenue Leakage
- Revenue Leakage Rate

---

## 21. Insurance & TPA Operations

- Insured Patients
- Insurance Revenue
- Preauthorization Requests
- Pending Preauthorizations
- Approved Preauthorizations
- Rejected Preauthorizations
- Preauthorization Approval Rate
- Preauthorization TAT
- Claims Submitted
- Claims Accepted
- Claims Rejected
- Claims Denied
- Claim Denial Rate
- Claimed Amount
- Approved Amount
- Deducted Amount
- Settled Amount
- Pending Amount
- Settlement Rate
- Settlement TAT
- Deduction Rate
- Denial Value
- Denial Reasons
- Payer Performance
- Payer-wise AR

---

## 22. Patient Safety & Incident Management

- Safety Incidents
- Near Misses
- Sentinel Events
- Medication Errors
- Wrong Medication
- Wrong Dose
- Allergy Incidents
- Patient Identification Errors
- Falls
- Fall Rate
- Pressure Injuries
- Pressure Injury Rate
- Transfusion Reactions
- Procedure Errors
- Incident Severity
- Incident Closure Rate
- Incident Resolution Time
- Repeat Incident Rate

---

## 23. Infection Control & Hospital Hygiene

- Total Infections
- Hospital-Acquired Infections (HAI)
- CAUTI (Catheter-Associated UTI)
- CAUTI Rate
- CLABSI (Central Line-Associated Bloodstream Infection)
- CLABSI Rate
- VAP (Ventilator-Associated Pneumonia)
- VAP Rate
- SSI (Surgical Site Infection)
- SSI Rate
- Device Days
- Infection Density
- Patient Days
- Hand Hygiene Compliance
- Isolation Compliance
- Antimicrobial Utilization
- Resistant Organism Cases (MRSA, VRE, CRE)
- Outbreak Alerts
- Infection Trend

---

## 24. Clinical Quality & Accreditation (NABH / JCI)

- Mortality Rate
- Readmission Rate
- 7-day Readmission
- 30-day Readmission
- Complication Rate
- ICU Transfer Rate
- Unexpected ICU Transfer
- Length of Stay
- Excess LOS
- Unplanned Return to OT
- Critical Result Acknowledgement
- Documentation Completion
- Clinical Protocol Compliance
- Care Bundle Compliance
- Discharge Summary Completion
- Medication Reconciliation Rate
- Follow-up Compliance

---

## 25. Patient Experience & Feedback

- Feedback Volume
- Satisfaction Score
- CSAT (Customer Satisfaction Score)
- NPS (Net Promoter Score)
- Complaints
- Complaint Rate
- Complaint Resolution Rate
- Complaint Resolution TAT
- Escalated Complaints
- Unresolved Complaints
- Service Recovery Cases
- Waiting-related Complaints
- Billing Complaints
- Pharmacy Complaints
- Nursing Complaints
- Doctor Complaints
- Department Satisfaction
- Patient Experience Trend

---

## 26. Workforce, HR & Staffing

- Total Employees
- Active Employees
- New Hires
- Separations
- Attrition Rate
- Vacancy Rate
- Open Positions
- Attendance Rate
- Absenteeism Rate
- Leave Utilization
- Overtime Hours
- Overtime Cost
- Agency Staff
- Staff Utilization
- Staff/Patient Ratio
- Nurse/Patient Ratio
- Doctor/Patient Ratio
- Staffing Requirement
- Staffing Gap
- Training Completion
- Mandatory Training Compliance
- License Expiry
- Credential Expiry
- Certification Expiry
- Workforce Cost
- Payroll Cost

---

## 27. Regulatory Compliance & Governance

- Open Compliance Issues
- Overdue Compliance Issues
- Audit Findings
- Open Audit Findings
- Overdue CAPA (Corrective and Preventive Actions)
- CAPA Closure Rate
- CAPA Resolution Time
- Policy Acknowledgement Rate
- Consent Exceptions
- Documentation Exceptions
- Privacy Requests
- Privacy Request SLA
- Legal Holds
- Retention Exceptions
- License Expiries
- Accreditation Readiness Score

---

## 28. Security, Identity & Audit Logging

- Login Attempts
- Failed Logins
- MFA Failures
- Suspicious Logins
- Privileged Logins
- Privilege Changes
- Role Changes
- Permission Changes
- Break-glass Events
- Patient Record Access
- Unusual Record Access
- Bulk Record Access
- Data Exports
- Failed API Requests
- Authentication Failures
- Authorization Failures
- High-risk Audit Events
- Security Incidents
- Audit Exceptions

---

## 29. ABDM, FHIR & National Health Stack Interoperability

- ABHA Registrations
- ABHA Linkage Rate
- Consent Requests
- Consent Approvals
- Consent Rejections
- Consent Revocations
- Health Record Exchanges
- Exchange Success Rate
- Exchange Failure Rate
- FHIR Resources Generated
- FHIR Resources Exchanged
- FHIR Validation Failures
- Synchronization Failures
- Synchronization Lag
- Federation Transfers
- Federation Transfer Success Rate
- Federation Transfer Failures
- Federation Transfer TAT
- Active Federation Partners
- Revoked Federation Credentials

---

## 30. SaaS & Multi-Tenant Platform

- Total Tenants
- Active Tenants
- Trial Tenants
- Provisioning Tenants
- Suspended Tenants
- Expired Tenants
- Tenant Growth
- Tenant Churn
- Monthly Recurring Revenue (MRR)
- Annual Recurring Revenue (ARR)
- New MRR
- Expansion MRR
- Churned MRR
- Renewal Rate
- License Utilization
- License Expiry
- Module Adoption
- User Adoption
- Daily Active Users (DAU)
- Weekly Active Users (WAU)
- Monthly Active Users (MAU)
- Tenant Activity
- Tenant Health Score
- Tenant API Usage
- Tenant Storage
- Tenant Error Rate

---

## 31. SaaS Cloud Infrastructure & Reliability

- API Availability
- API Latency
- P50 API Latency
- P95 API Latency
- P99 API Latency
- Error Rate
- 4xx Rate
- 5xx Rate
- Database Availability
- Database Connections
- Database Latency
- Query Latency
- Queue Depth
- Queue Processing Time
- Failed Jobs
- Job Retry Rate
- Backup Success Rate
- Backup Failure Rate
- Backup Age
- Restore Test Success
- Storage Usage
- Storage Growth
- Integration Availability
- Integration Failure Rate
- Deployment Failure Rate
- Migration Failure Rate

---

## 32. Predictive & Forecast Metrics

- Forecast Patient Volume
- Forecast OPD Demand
- Forecast ED Demand
- Forecast Admissions
- Forecast Discharges
- Forecast Bed Occupancy
- Forecast ICU Occupancy
- Forecast Pharmacy Demand
- Forecast Lab Demand
- Forecast Staffing Demand
- Forecast Revenue
- Forecast Collections
- Forecast Cash Flow
- Stock-out Prediction
- Expiry Risk
- Capacity Shortage Prediction
- SLA Breach Prediction
- Readmission Risk
- Patient Deterioration Risk (NEWS2 AI-enhanced)
- Discharge Delay Prediction
- No-show Prediction
- Claim Denial Prediction
- Revenue Leakage Prediction
