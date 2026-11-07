import test from "node:test";
import assert from "node:assert/strict";
import { resolveRoleFromUser } from "../src/core/context/roleMapping.js";

const userWithRole = (code) => ({
  is_superuser: false,
  roles: [{ code }],
});

test("maps the seeded hospital administrator role", () => {
  assert.equal(resolveRoleFromUser(userWithRole("ROLE_ADMIN")), "HOSPITAL_ADMIN");
});

test("maps seeded clinical and operational roles exactly", () => {
  assert.equal(resolveRoleFromUser(userWithRole("ROLE_DOCTOR")), "ATTENDING_PHYSICIAN");
  assert.equal(resolveRoleFromUser(userWithRole("ROLE_NURSE")), "WARD_NURSE");
  assert.equal(resolveRoleFromUser(userWithRole("ROLE_BILLING")), "BILLING_CLERK");
  assert.equal(resolveRoleFromUser(userWithRole("ROLE_PHARMACIST")), "PHARMACIST");
});

test("keeps the read-only auditor role restricted", () => {
  assert.equal(resolveRoleFromUser(userWithRole("ROLE_AUDITOR_READONLY")), "RESTRICTED");
});

test("does not elevate unknown custom roles containing privileged words", () => {
  assert.equal(resolveRoleFromUser(userWithRole("CUSTOM_ADMIN_ASSISTANT")), "RESTRICTED");
  assert.equal(resolveRoleFromUser(userWithRole("FINANCE_DIRECTOR")), "RESTRICTED");
  assert.equal(resolveRoleFromUser(userWithRole("SUPER_DOCTOR")), "RESTRICTED");
});

test("restricts missing users and users without assigned roles", () => {
  assert.equal(resolveRoleFromUser(null), "RESTRICTED");
  assert.equal(resolveRoleFromUser({ is_superuser: false, roles: [] }), "RESTRICTED");
});

test("recognizes superuser status independently of role assignments", () => {
  assert.equal(resolveRoleFromUser({ is_superuser: true, roles: [] }), "HOSPITAL_ADMIN");
});

test("normalizes whitespace and case without using substring matching", () => {
  assert.equal(resolveRoleFromUser(userWithRole(" role_doctor ")), "ATTENDING_PHYSICIAN");
});
