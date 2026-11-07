# CI/CD Operations Runbook

## Purpose and operating model

This repository uses two GitHub Actions workflows:

- **Release gates** (`.github/workflows/release-gates.yml`) provides full validation for selected pull requests, integration/release branch pushes, manual runs, and a weekly scheduled scan.
- **On-demand validation** (`.github/workflows/on-demand-validation.yml`) provides narrower validation scopes for development work without running the full release gate on every feature-branch commit.

A successful CI run proves only that the configured automated checks passed for the tested commit. It does not prove production deployment succeeded, backups are restorable, a migration is safe for every tenant, or that the deployment is compliant with healthcare regulations.

## Workflow selection

### Release gates

| Trigger | Expected behavior |
|---|---|
| PR receives `ci:full` label | Runs full PR validation, including the production image job when the PR targets `main` or `release/**` |
| PR receives a new commit while `ci:full` remains present | Re-runs the selected full PR gates |
| Push to `main` or `release/**` | Runs integration/release validation |
| Manual dispatch | Runs the release workflow for the selected branch |
| Weekly schedule | Runs the scheduled drift/security validation |

The workflow currently validates:
1. Python tests, dependency audits, and PostgreSQL 17 migration integration.
2. Onboarding UI dependency audit, utility tests, and production build.
3. Hospital UI role-mapping regression tests and production build.
4. Development/production Compose and Prometheus/Alertmanager configuration.
5. Production API, Hospital UI, and patched ClamAV image builds and Trivy scans for fixable HIGH/CRITICAL vulnerabilities.
6. CycloneDX SBOM generation for all three images, upload of the scanned image/SBOM artifacts, and a separate artifact-handoff verification job.

### On-demand validation

Use **Actions → On-demand validation → Run workflow** and select the branch and scope:

| Scope | What runs |
|---|---|
| `reconciliation` | Reconciliation governance regression tests |
| `backend` | Python backend test suite |
| `frontend` | Hospital UI build plus onboarding UI tests/build |
| `full` | Backend with PostgreSQL 17 integration, frontend builds, and Compose validation |

Use a narrow scope for fast feedback during implementation. Use the release gate before merging a high-impact change or preparing a release.

## Pull request procedure

1. Create a feature branch from the current integration base.
2. Make a focused change and run the relevant local tests.
3. Open a pull request and explain behavior changes, migration impact, security impact, and rollback considerations.
4. Add `ci:full` when the change is ready for full validation.
5. Wait for all applicable checks to finish. A skipped job is not equivalent to a passed job; confirm that the job was intentionally skipped for the event/target branch.
6. Review the diff and workflow logs, especially migration, dependency-audit, Compose, and image-scan output.
7. Merge only after required repository protection rules and review requirements are satisfied.
8. Confirm the post-merge `main` run succeeds. If it fails, treat the integration as not validated and fix or revert the offending change.

Do not merge solely because a feature-branch or manual run passed. Verify that the tested SHA is the current PR head and that the post-merge run tests the resulting integration commit.

## Failure handling

1. Open the failed workflow run and identify the first failing step in each failed job.
2. Distinguish code/configuration failures from transient infrastructure failures (registry outage, runner issue, rate limit).
3. For a transient failure, rerun only the failed job when safe; otherwise rerun the workflow.
4. For deterministic failures, fix the source and push a new commit. Keep `ci:full` on the PR so the synchronize event triggers validation.
5. Never disable a test, suppress a vulnerability, or broaden an ignore rule merely to obtain a green build. Any exception must be narrowly scoped, justified, time-bound, and reviewed.
6. Record the root cause and corrective action in the PR.

## Dependency and image security

- Python dependencies are pinned and audited with `pip-audit` for the configured requirement sets.
- The onboarding UI runs `npm audit`; the hospital UI currently has a build gate but no equivalent explicit `npm audit` step in the release workflow.
- Production API, Hospital UI, and ClamAV images are scanned by Trivy for fixable HIGH/CRITICAL vulnerabilities. The configured gate fails on findings meeting that policy; do not add suppressions simply to make CI green.
- SBOMs are generated for the exact scanned images in CycloneDX format. The verifier checks the SBOM format and reloads/inspects the scanned image bundle before publication.
- Third-party GitHub Actions in the release workflow are pinned to commit SHAs.
- Review dependency and base-image updates through pull requests. Do not silently float production image tags or remove digest pins without a documented reason.

## Database migration release gate

Production tenant migrations are an explicit operation, not an automatic side effect of restarting the application.

Before a production migration:
1. Review the Alembic revision and its upgrade/downgrade behavior.
2. Test on the supported PostgreSQL version and representative data volume.
3. Confirm a recent backup exists and that restore evidence is current.
4. Apply the migration to staging and validate application behavior.
5. Apply to the designated default/canary tenant and run health and domain smoke tests.
6. Obtain explicit approval for fleet rollout; record tenant scope, operator, start/end time, and outcome.
7. Verify tenant schema revisions and application health after rollout.
8. Keep a rollback/forward-fix plan. Do not assume every schema change is safely reversible.

A green PostgreSQL migration parity test is necessary but does not replace staged, canary, backup/restore, and fleet rollout evidence.

## Production release and deployment

The release workflow publishes the already-scanned image artifacts to GHCR only on pushes to `main` or `release/**`; pull-request runs build, scan, and verify artifacts but do not publish. It publishes API, Hospital UI, and ClamAV images under `ghcr.io/perseus37/` with an immutable source-commit SHA tag and a channel tag. The publish job uses `GITHUB_TOKEN` with `packages: write`; package-level Actions access must also grant this repository write access. Keep packages private and verify visibility in GHCR package settings.

The publish job records image digests, creates signed SLSA provenance and CycloneDX SBOM attestations for each image digest, and runs `gh attestation verify` against the source repository. A successful build/scan alone is not evidence that publishing or attestation verification succeeded; inspect the publisher job and digest summary.

These release artifacts do not constitute a complete production deployment pipeline. Production deployment must remain a separate, explicitly approved operation until environment protection, deployment credentials, digest-based artifact promotion, health verification, and rollback are implemented and tested.

For each production release, record:
- source commit and release identifier;
- image digest(s), not just mutable tags;
- migration revision(s) and canary/fleet approval evidence;
- backup reference and restore readiness;
- approver, operator, deployment time, and target environment;
- post-deployment health/smoke-test results;
- rollback or forward-fix decision.

## Repository administration checklist

These controls must be configured and verified by a repository administrator in GitHub settings. They are not established merely by the workflow YAML:

- Protect `main` and release branches; block force pushes and branch deletion.
- Require pull requests and the selected required checks before merge.
- Require at least one independent approval where staffing permits; dismiss stale approvals after new commits.
- Require CODEOWNERS review for workflow, deployment, and database migration changes after the owner map is agreed.
- Restrict who can bypass protections and who can approve production deployments.
- Enable dependency update automation and review its pull requests.
- Review Actions permissions and environment secrets periodically.

Required check names must be selected from actual checks on representative PRs. Do not make a conditionally skipped job mandatory for PR classes where it is intentionally skipped. Confirm the protection configuration with a test PR after enabling it.

## Current verified baseline

As of 2026-11-07:
- PR #4 was merged into `main` at `e2bd416472b9b32911f302d32860cdd40ad624fc`; post-merge run [#42261887116](https://github.com/Perseus37/avinya_hms_v2/actions/runs/42261887116) passed the then-current five jobs.
- PR #7 introduced GHCR publication and scanned artifact handoff; PR #9 added signed provenance and SBOM attestations; PR #8 added OCI source-repository labels.
- Main run [#42376894583](https://github.com/Perseus37/avinya_hms_v2/actions/runs/42376894583) successfully published and verified all three release images and their attestations.
- A later image scan identified two HIGH zlib findings in the Debian 13.7 API image (`CVE-2026-76844`, `CVE-2026-85091`). PR #13 updates inherited Debian packages; its full release-gates validation must pass before that remediation is considered complete.

This is a verified CI/release-artifact baseline, not evidence that repository branch protection, GHCR private visibility, production deployment approvals, backup restoration, or regulatory compliance are configured or proven.
