# AUD-004 disposable PostgreSQL ACL proof

This is an opt-in, isolated test fixture, not a production deployment template. It uses synthetic marker rows only. It does not exercise application federation, secret-manager policy, network egress controls, credential rotation, connection-pool draining, or source-owned disclosure. Passing this suite is only a bounded PostgreSQL database CONNECT/role and per-container credential-separation proof.

## Safety boundary

- Do not run from a production host or against a shared/developer PostgreSQL server.
- Do not use a production or normal HMS .env file.
- The Compose project, volume and network are explicitly named aud004-proof, aud004-proof-pgdata, and aud004-proof-only.
- PostgreSQL is not published to the host; probe containers connect over the private Compose network only.
- The setup password is supplied at runtime; the tenant passwords in init.sql and Compose are fixed, synthetic test-only values. Never reuse them.
- Each probe container receives exactly one runtime login in its environment. No probe container receives another workload's username or password.
- The Compose source itself contains all disposable fixture passwords; this is not a secret-provider integration test.
- The initialization SQL runs only when PostgreSQL initializes an empty volume. Existing volumes are not reset automatically.
- No patient or real tenant data is permitted.

## Start

Use a disposable local machine with Docker Compose installed. First confirm the dedicated names are unused. If any command reports an existing resource, stop and investigate; do not attach this harness to or delete that resource:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml ps -a
    docker volume inspect aud004-proof-pgdata
    docker network inspect aud004-proof-only

A missing-resource response from the volume and network inspect commands is expected on first use. Use a throwaway setup password in the current shell, then run:

    export AUD004_SETUP_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml up -d --wait postgres

PowerShell:

    $env:AUD004_SETUP_PASSWORD = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml up -d --wait postgres

The explicit project name is required. Do not omit -p aud004-proof.

## Run tests

Build and run each identity in a separate container. Each process has one login only and independently proves own-database access plus explicit CONNECT denial to the other two databases:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml run --build --rm --no-deps tenant_a_probe
    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml run --build --rm --no-deps tenant_b_probe
    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml run --build --rm --no-deps control_plane_probe

The runner connects to the PostgreSQL service as postgres:5432; there is no host-published database port. It fails if the server is unreachable; it does not substitute SQLite. For denied startup connections, PostgreSQL sends an explicit FATAL response containing permission denied for database "<name>" and User does not have CONNECT privilege. psycopg2 exposes this startup-time denial as OperationalError without a populated pgcode, so the test asserts both exact server-message fragments. DNS, server, missing-database, and password failures do not satisfy the assertion.

## Run through GitHub Actions

The existing **On-demand validation** workflow contains the AUD-004 proof job on this PR branch. To run it without changing application code or provisioning any shared infrastructure:

1. Open the repository's **Actions** tab and select **On-demand validation**.
2. Choose **Run workflow**.
3. Select branch security/aud004-disposable-postgres-proof.
4. Select scope reconciliation.
5. Start the workflow and inspect the **AUD-004 disposable PostgreSQL ACL proof** job.

The reconciliation scope runs both the reconciliation regression tests and this isolated PostgreSQL proof. The proof job creates its own disposable PostgreSQL service and tears down only its explicitly named Compose project and volume after its preflight succeeds. A skipped Release-gates job is not evidence that this proof ran. Treat the proof as pending until the AUD-004 job itself completes successfully. Do not select a release/deployment workflow or use production credentials.

## Teardown

First verify the active Compose project is the dedicated harness:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml ps

Only after confirming that output identifies the disposable AUD-004 PostgreSQL service, remove that project and its explicitly named volume:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml down --volumes --remove-orphans

This command is scoped to the dedicated project file and project name. Never substitute the default HMS Compose file or use a broad volume-prune command.

## Current proof limitations

The current slice tests each identity from a separate container with only that identity's single login: tenant A, tenant B, and control plane. It proves synthetic own-DB reads, explicit cross-database CONNECT denials, restricted runtime role attributes, no setup-role assumption, no PUBLIC CONNECT/TEMPORARY grants, and no predefined/elevated role membership. It does not prove that a real secret provider grants only one tenant secret, because the synthetic fixture credentials are visible in the Compose definition and repository. It also does not prove real application workload identity, network egress policy beyond the isolated Compose network, source-service authorization, credential rotation/revocation, or connection-pool draining. Those remain required before any production role/bootstrap/runtime change.
