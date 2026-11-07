/**
 * Resolve backend role codes to the Hospital UI's supported role model.
 *
 * This module is intentionally framework-free so it can be tested directly
 * with Node's built-in test runner. Unknown roles fail closed.
 */
export function resolveRoleFromUser(user) {
  if (!user) return "RESTRICTED";
  if (user.is_superuser) return "HOSPITAL_ADMIN";

  const roleCodes = new Set(
    (user.roles || []).map((role) => (role.code || "").trim().toUpperCase())
  );

  // Exact matching avoids accidentally elevating custom roles whose names
  // merely contain words such as ADMIN, DOCTOR, or FINANCE.
  const exactRoleMap = [
    { codes: ["ROLE_ADMIN"], role: "HOSPITAL_ADMIN" },
    { codes: ["ROLE_DOCTOR", "ATTENDING_PHYSICIAN"], role: "ATTENDING_PHYSICIAN" },
    { codes: ["ROLE_NURSE", "WARD_NURSE"], role: "WARD_NURSE" },
    { codes: ["ROLE_BILLING", "BILLING_CLERK"], role: "BILLING_CLERK" },
    { codes: ["ROLE_FRONT_DESK", "FRONT_DESK", "ROLE_RECEPTIONIST"], role: "FRONT_DESK" },
    { codes: ["ROLE_ADT_OFFICER", "ADT_OFFICER"], role: "ADT_OFFICER" },
    { codes: ["ROLE_TRIAGE_NURSE", "TRIAGE_NURSE"], role: "TRIAGE_NURSE" },
    { codes: ["ROLE_PHARMACIST", "PHARMACIST"], role: "PHARMACIST" },
  ];

  for (const mapping of exactRoleMap) {
    if (mapping.codes.some((code) => roleCodes.has(code))) return mapping.role;
  }

  // Read-only auditor access remains restricted until its dedicated workspace
  // and audit-specific data controls are implemented and tested.
  return "RESTRICTED";
}
