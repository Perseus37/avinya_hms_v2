# Architecture and knowledge transfer

This file is the stable landing page for architecture and KT material. Detailed
source maps live in [Project Report and KT](PROJECT_REPORT_AND_KT.md);
operational commands and safety procedures live in
[Operations Runbook](OPERATIONS_RUNBOOK.md).

## Read these documents

1. [Enterprise Hospital UI Elemental Specification & Audit](ENTERPRISE_HOSPITAL_UI_SPECIFICATION_AND_AUDIT.md) — exhaustive wireframes, data dictionaries, interaction models, and AI audit for all 9 clinical workspaces, dynamic facility customization, and production RBAC session security.
2. [Master System Architecture and Technical Specification](SYSTEM_ARCHITECTURE_AND_DESIGN.md) — comprehensive high-level and low-level design (HLD & LLD), covering multi-tenancy, all 26 healthcare domains, envelope encryption, background queues, and disaster recovery.
3. [Enterprise Metrics & KPI Inventory](ENTERPRISE_METRICS_AND_KPI_INVENTORY.md) — complete catalog of the 700+ multidimensional metric cubes, clinical quality indicators, and statutory registers.
4. [Complete Enterprise Guide](complete_guide/README.md) — 12-chapter comprehensive documentation suite covering concepts, architecture, clinical workflows, operations, and frontend workspaces.
5. [System Inventory and Boundaries Specification](SYSTEM_INVENTORY_AND_BOUNDARIES.md) — complete inventory of system capabilities, database schemas, and external API boundaries.
6. [Project Report and KT](PROJECT_REPORT_AND_KT.md) — system topology, responsibilities, database boundaries, backend/frontend file map, tests, and limitations.
7. [Operations Runbook](OPERATIONS_RUNBOOK.md) — local/production checks, releases, schema migrations, backups/restores, and troubleshooting.
8. [Project Structure](PROJECT_STRUCTURE.md) — current repository layout across `backend/`, `hospital-ui/`, and `onboarding-ui/`.
6. [Production Deployment](PRODUCTION_DEPLOYMENT.md) — provider, networking,
   secrets, cost and VM deployment guidance.
7. [Migration Studio](MIGRATION_STUDIO.md) — import workflow, ETL blocks,
   duplicate policies, and safety limitations.
8. [Onboarding Improvements](ONBOARDING_IMPROVEMENTS.md) — existing analytics,
   audit-field inventory and improvement backlog.

The earlier content of this Markdown file contained implementation claims
that no longer matched the repository and has been replaced. The companion
`ARCHITECTURE_AND_KT.docx` is a legacy artifact and has not been regenerated;
prefer the Markdown documents above until it is reviewed.
