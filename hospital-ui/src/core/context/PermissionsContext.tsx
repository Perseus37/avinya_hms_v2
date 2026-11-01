import React, { createContext, useContext, useState, useEffect } from "react";
import { WorkspaceId, UserProfile } from "../../types";
import { useAuth } from "./AuthContext";

export type RoleCode =
  | "HOSPITAL_ADMIN"
  | "ATTENDING_PHYSICIAN"
  | "FRONT_DESK"
  | "ADT_OFFICER"
  | "WARD_NURSE"
  | "TRIAGE_NURSE"
  | "BILLING_CLERK";

export type PermissionCode =
  // Patient & Registration
  | "patient.register"
  | "patient.view_mpi"
  | "patient.edit_demographics"
  | "appointment.book"
  | "token.issue"
  | "token.call_queue"
  // ADT & Bed Operations
  | "bed.view_matrix"
  | "bed.allocate"
  | "bed.transfer"
  | "bed.override_tariff"
  | "bed.configure"
  | "adt.confirm_admission"
  // Clinical Doctor
  | "doctor.cockpit_view"
  | "order.cpoe_prescribe"
  | "order.order_lab"
  | "clinical.sign_notes"
  | "discharge.clinical_sign"
  // Nursing
  | "nurse.view_station"
  | "nurse.administer_emar"
  | "nurse.record_vitals"
  | "nurse.bcma_scan"
  // Emergency Triage
  | "triage.view_board"
  | "triage.assign_esi"
  | "triage.code_red"
  // Billing & Cashier
  | "billing.view_counter"
  | "billing.collect_fee"
  | "billing.tpa_approve"
  | "billing.override_discount"
  // Admin & System Configuration
  | "config.facility_manage"
  | "config.roster_manage"
  | "config.policies_manage"
  | "system.view_audit_logs";

export interface RoleDefinition {
  code: RoleCode;
  label: string;
  badge: string;
  description: string;
  defaultWorkspace: WorkspaceId;
  allowedWorkspaces: WorkspaceId[];
  permissions: PermissionCode[];
}

export const ROLE_DEFINITIONS: Record<RoleCode, RoleDefinition> = {
  HOSPITAL_ADMIN: {
    code: "HOSPITAL_ADMIN",
    label: "Hospital Administrator",
    badge: "Super Admin",
    description: "Full access to facility master, doctor roster, audit logs, and all clinical workspaces.",
    defaultWorkspace: "admin",
    allowedWorkspaces: [
      "registration",
      "patient-record",
      "opd-queue",
      "adt",
      "doctor",
      "nursing",
      "triage",
      "surgery",
      "blood-bank",
      "pharmacy",
      "diagnostics",
      "billing",
      "admin",
    ],
    permissions: [
      "patient.register",
      "patient.view_mpi",
      "patient.edit_demographics",
      "appointment.book",
      "token.issue",
      "token.call_queue",
      "bed.view_matrix",
      "bed.allocate",
      "bed.transfer",
      "bed.override_tariff",
      "bed.configure",
      "adt.confirm_admission",
      "doctor.cockpit_view",
      "order.cpoe_prescribe",
      "order.order_lab",
      "clinical.sign_notes",
      "discharge.clinical_sign",
      "nurse.view_station",
      "nurse.administer_emar",
      "nurse.record_vitals",
      "nurse.bcma_scan",
      "triage.view_board",
      "triage.assign_esi",
      "triage.code_red",
      "billing.view_counter",
      "billing.collect_fee",
      "billing.tpa_approve",
      "billing.override_discount",
      "config.facility_manage",
      "config.roster_manage",
      "config.policies_manage",
      "system.view_audit_logs",
    ],
  },
  FRONT_DESK: {
    code: "FRONT_DESK",
    label: "Front Desk & Receptionist",
    badge: "Registration",
    description: "Registers patients, looks up MPI, books OPD appointments, issues clinic queue tokens, and collects consultation fees.",
    defaultWorkspace: "registration",
    allowedWorkspaces: ["registration", "patient-record", "opd-queue", "billing"],
    permissions: [
      "patient.register",
      "patient.view_mpi",
      "patient.edit_demographics",
      "appointment.book",
      "token.issue",
      "token.call_queue",
      "billing.view_counter",
      "billing.collect_fee",
    ],
  },
  ATTENDING_PHYSICIAN: {
    code: "ATTENDING_PHYSICIAN",
    label: "Attending Physician / Surgeon",
    badge: "Doctor Cockpit",
    description: "Access to Doctor Cockpit, longitudinal EMR, CPOE electronic prescription, CDS safety alerts, and clinical discharge signing.",
    defaultWorkspace: "doctor",
    allowedWorkspaces: ["doctor", "surgery", "blood-bank", "patient-record", "opd-queue", "diagnostics", "adt", "registration"],
    permissions: [
      "doctor.cockpit_view",
      "order.cpoe_prescribe",
      "order.order_lab",
      "clinical.sign_notes",
      "discharge.clinical_sign",
      "patient.view_mpi",
      "bed.view_matrix",
    ],
  },
  ADT_OFFICER: {
    code: "ADT_OFFICER",
    label: "Inpatient ADT & Bed Manager",
    badge: "Bed Allocation",
    description: "Manages 500+ campus bed hierarchy, allocates admissions, executes bed transfers, and manages housekeeping status.",
    defaultWorkspace: "adt",
    allowedWorkspaces: ["adt", "patient-record", "registration", "billing"],
    permissions: [
      "bed.view_matrix",
      "bed.allocate",
      "bed.transfer",
      "adt.confirm_admission",
      "patient.view_mpi",
      "billing.view_counter",
      "billing.tpa_approve",
    ],
  },
  WARD_NURSE: {
    code: "WARD_NURSE",
    label: "Ward Nursing Officer",
    badge: "eMAR & Vitals",
    description: "Bed census matrix, eMAR medication administration schedule, BCMA barcode validation, and NEWS2 vitals monitoring.",
    defaultWorkspace: "nursing",
    allowedWorkspaces: ["nursing", "patient-record", "adt", "doctor"],
    permissions: [
      "nurse.view_station",
      "nurse.administer_emar",
      "nurse.record_vitals",
      "nurse.bcma_scan",
      "patient.view_mpi",
      "bed.view_matrix",
      "bed.transfer",
    ],
  },
  TRIAGE_NURSE: {
    code: "TRIAGE_NURSE",
    label: "Emergency Triage Nurse",
    badge: "ED Triage",
    description: "Emergency Department intake, ESI 1-5 acuity triage, GCS calculator, Code Red resuscitation alert, and MLC intimation.",
    defaultWorkspace: "triage",
    allowedWorkspaces: ["triage", "patient-record", "nursing", "registration"],
    permissions: [
      "triage.view_board",
      "triage.assign_esi",
      "triage.code_red",
      "patient.register",
      "patient.view_mpi",
      "nurse.record_vitals",
    ],
  },
  BILLING_CLERK: {
    code: "BILLING_CLERK",
    label: "Cashier & Billing Officer",
    badge: "Cashier Billing",
    description: "TPA insurance pre-authorization settlement, itemized folio charges, co-pay split, and tax invoice generation.",
    defaultWorkspace: "billing",
    allowedWorkspaces: ["billing", "patient-record", "registration", "adt"],
    permissions: [
      "billing.view_counter",
      "billing.collect_fee",
      "billing.tpa_approve",
      "billing.override_discount",
      "patient.view_mpi",
      "bed.view_matrix",
    ],
  },
};

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

interface PermissionsContextType {
  activeRole: RoleCode;
  authenticatedRole: RoleCode;
  roleDefinition: RoleDefinition;
  isSimulating: boolean;
  isDev: boolean;
  setActiveRole: (role: RoleCode) => void;
  resetToAuthenticatedRole: () => void;
  hasPermission: (permission: PermissionCode) => boolean;
  hasAnyPermission: (permissions: PermissionCode[]) => boolean;
  hasAllPermissions: (permissions: PermissionCode[]) => boolean;
  isWorkspaceAllowed: (workspace: WorkspaceId) => boolean;
}

const PermissionsContext = createContext<PermissionsContextType | undefined>(undefined);

export const PermissionsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const isDev = Boolean(import.meta.env.DEV);

  const authenticatedRole = resolveRoleFromUser(user);

  const [simulatedRole, setSimulatedRoleState] = useState<RoleCode | null>(() => {
    if (!isDev) return null;
    const saved = localStorage.getItem("avinya_dev_simulated_role");
    return (saved as RoleCode) || null;
  });

  // Keep simulated role clean if dev mode toggles
  useEffect(() => {
    if (!isDev && simulatedRole) {
      setSimulatedRoleState(null);
      localStorage.removeItem("avinya_dev_simulated_role");
    }
  }, [isDev, simulatedRole]);

  const setActiveRole = (role: RoleCode) => {
    if (!isDev) return; // In production, role is cryptographically determined by JWT
    setSimulatedRoleState(role);
    localStorage.setItem("avinya_dev_simulated_role", role);
  };

  const resetToAuthenticatedRole = () => {
    setSimulatedRoleState(null);
    localStorage.removeItem("avinya_dev_simulated_role");
  };

  const activeRole = isDev && simulatedRole ? simulatedRole : authenticatedRole;
  const isSimulating = Boolean(isDev && simulatedRole && simulatedRole !== authenticatedRole);

  const roleDefinition = ROLE_DEFINITIONS[activeRole] || ROLE_DEFINITIONS.HOSPITAL_ADMIN;

  const hasPermission = (permission: PermissionCode): boolean => {
    return roleDefinition.permissions.includes(permission);
  };

  const hasAnyPermission = (permissions: PermissionCode[]): boolean => {
    return permissions.some((p) => roleDefinition.permissions.includes(p));
  };

  const hasAllPermissions = (permissions: PermissionCode[]): boolean => {
    return permissions.every((p) => roleDefinition.permissions.includes(p));
  };

  const isWorkspaceAllowed = (workspace: WorkspaceId): boolean => {
    return roleDefinition.allowedWorkspaces.includes(workspace);
  };

  return (
    <PermissionsContext.Provider
      value={{
        activeRole,
        authenticatedRole,
        roleDefinition,
        isSimulating,
        isDev,
        setActiveRole,
        resetToAuthenticatedRole,
        hasPermission,
        hasAnyPermission,
        hasAllPermissions,
        isWorkspaceAllowed,
      }}
    >
      {children}
    </PermissionsContext.Provider>
  );
};

export const usePermissions = (): PermissionsContextType => {
  const context = useContext(PermissionsContext);
  if (!context) {
    throw new Error("usePermissions must be used within a PermissionsProvider");
  }
  return context;
};
