# GHCR Release Artifacts

## Image repositories

Avinya HMS publishes these production images to GitHub Container Registry:

- `ghcr.io/perseus37/avinya-hms-api`
- `ghcr.io/perseus37/avinya-hospital-ui`
- `ghcr.io/perseus37/avinya-clamav`

The workflow derives the namespace from the repository owner and normalizes it to lowercase.

## Publishing policy

The Release gates workflow publishes only after all required validation jobs and all three image scans succeed, and only for successful pushes to:

- `main`
- `release/**`

Pull requests, scheduled scans, and manual workflow dispatches validate but do not publish. Publishing uses the workflow's short-lived `GITHUB_TOKEN` with job-scoped `packages: write`; no personal access token or long-lived registry password is required.

## Tags and identity

Each published image receives:

- A full 40-character source commit SHA tag, for example `<commit-sha>`.
- A channel tag: `main` or the normalized release branch name.

Channel tags are convenience pointers and are mutable. They are not deployment identities. Deployment configuration must use the immutable manifest digest recorded in the successful workflow run's **GHCR image digests** job summary, for example:

```text
ghcr.io/perseus37/avinya-hms-api@sha256:<digest>
```

All three digests must be recorded together as one release set, alongside the source commit SHA and workflow run URL. Never combine images from different source commits unless an explicit compatibility decision is documented.

## Package visibility and access

The first successful publish creates or updates the three GHCR packages. Verify package visibility and access in GitHub Packages before any deployment:

- Keep packages private unless public distribution is an explicit product decision.
- Grant the production pull identity read-only access.
- Keep write access limited to the repository Actions workflow and authorized maintainers.
- Do not grant production hosts package write permissions.

For private packages, configure the production host's read-only registry authentication out of band. Do not place registry credentials in the repository or in the Compose file.

## Deployment boundary

This workflow does not deploy to staging or production and does not modify production Compose image references. The current Compose deployment remains unchanged until a separate reviewed change introduces digest-pinned image references, registry pull authentication, deployment health checks, migration sequencing, approval gates, and rollback procedures.

A successful image scan is limited to the configured Trivy policy (fixable HIGH/CRITICAL vulnerabilities). It is not a complete security certification or a substitute for runtime, configuration, and infrastructure controls.

## Release evidence

For every release candidate, retain:

1. Source commit SHA.
2. Successful release-gates workflow run URL.
3. API, Hospital UI, and ClamAV image digests.
4. Trivy scan results from that run.
5. The release/change approval and deployment record, when deployment is separately authorized.
