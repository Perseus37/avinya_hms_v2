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

Pull requests, scheduled scans, and manual workflow dispatches validate but do not publish. The build-and-scan job has only `contents: read` and exports the exact scanned images as a short-retention workflow artifact. A separate push-only publishing job downloads those images and receives the short-lived `GITHUB_TOKEN` with job-scoped `packages: write`. Pull-request, scheduled, and manual validation jobs never receive registry write permission. The push-only publisher also receives `id-token: write` and `attestations: write` solely to create signed supply-chain evidence. No personal access token or long-lived registry password is required.

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

The first successful publish creates or updates the three GHCR packages. The validated image set is handed from the scan job to the publish job as a workflow artifact retained for three days; the publisher loads and tags those same image contents rather than rebuilding them after the scans. The workflow also generates one CycloneDX SBOM per scanned image and retains the three-file SBOM artifact for 90 days. A downstream verification job checks that all three files are valid CycloneDX documents before the publish job can run. After publishing, the workflow creates signed SLSA build-provenance attestations and signed CycloneDX SBOM attestations for each exact image digest using GitHub Artifact Attestations/Sigstore. It then verifies the image provenance attestations with `gh attestation verify`. These steps run only in the push-only publisher; they are not exercised by pull-request validation. Verify package visibility and access in GitHub Packages before any deployment:

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
5. The API, Hospital UI, and ClamAV CycloneDX SBOM artifact from that run.
6. Verified provenance and SBOM attestation evidence for each image digest.
7. The release/change approval and deployment record, when deployment is separately authorized.


SBOMs describe the components detected in each image at build time. Signed SBOM attestations bind each CycloneDX document to the corresponding image digest; SLSA provenance attestations bind the image digest to its GitHub Actions build identity. These attestations provide verifiable supply-chain evidence, not a claim that an image is vulnerability-free or that the application has been independently security-certified. Verification depends on access to the GitHub attestation service and, for registry referrers, the private GHCR package.
