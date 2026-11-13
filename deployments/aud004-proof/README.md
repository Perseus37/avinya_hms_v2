# AUD-004 disposable PostgreSQL ACL proof

This is an opt-in, isolated test fixture, not a production deployment template. It uses synthetic marker rows only. It tests PostgreSQL ACLs and per-container secret-mount separation using Docker Compose file-backed secrets. It does not exercise a production secret manager, real application federation, host/network egress policy, credential rotation, connection-pool draining, or source-owned disclosure.

## Safety boundary

- Do not run from a production host or against a shared/developer PostgreSQL server.
- Do not use a production or normal HMS .env file.
- The Compose project, volume and network are explicitly named aud004-proof, aud004-proof-pgdata, and aud004-proof-only.
- PostgreSQL is not published to the host; probe containers connect over the private Compose network only.
- All passwords are generated at runtime and kept in a temporary directory outside the repository. Never reuse them.
- Each probe container receives exactly two read-only secret mounts: its own database username and password. The tests fail if any additional secret file is mounted.
- The PostgreSQL setup container receives the synthetic role passwords only to initialize the disposable fixture; probe containers never receive the setup password or other tenant secrets.
- The Compose file does not contain tenant login passwords. The local secret files are not committed.
- The initialization SQL runs only when PostgreSQL initializes an empty volume. Existing volumes are not reset automatically.
- No patient or real tenant data is permitted.

## Start

Use a disposable local machine with Docker Compose installed. First confirm the dedicated names are unused. If any command reports an existing resource, stop and investigate; do not attach this harness to or delete that resource:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml ps -a
    docker volume inspect aud004-proof-pgdata
    docker network inspect aud004-proof-only

A missing-resource response from the volume and network inspect commands is expected on first use. Create runtime secrets outside the repository:

    export AUD004_SECRETS_DIR="$(mktemp -d)"
    chmod 700 "$AUD004_SECRETS_DIR"
    export AUD004_SETUP_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export AUD004_TENANT_A_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export AUD004_TENANT_B_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    export AUD004_CP_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    printf %s tenant_a_api_test > "$AUD004_SECRETS_DIR/tenant_a_db_user"
    printf %s "$AUD004_TENANT_A_PASSWORD" > "$AUD004_SECRETS_DIR/tenant_a_db_password"
    printf %s tenant_b_api_test > "$AUD004_SECRETS_DIR/tenant_b_db_user"
    printf %s "$AUD004_TENANT_B_PASSWORD" > "$AUD004_SECRETS_DIR/tenant_b_db_password"
    printf %s control_plane_test > "$AUD004_SECRETS_DIR/control_plane_db_user"
    printf %s "$AUD004_CP_PASSWORD" > "$AUD004_SECRETS_DIR/control_plane_db_password"
    chmod 600 "$AUD004_SECRETS_DIR"/*

PowerShell (run from the repository root):

    $env:AUD004_SECRETS_DIR = Join-Path $env:TEMP ("aud004-secrets-" + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $env:AUD004_SECRETS_DIR | Out-Null
    $env:AUD004_SETUP_PASSWORD = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    $env:AUD004_TENANT_A_PASSWORD = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    $env:AUD004_TENANT_B_PASSWORD = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    $env:AUD004_CP_PASSWORD = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    Set-Content -NoNewline -Path (Join-Path $env:AUD004_SECRETS_DIR tenant_a_db_user) -Value tenant_a_api_test
    Set-Content -NoNewline -Path (Join-Path $env:AUD004_SECRETS_DIR tenant_a_db_password) -Value $env:AUD004_TENANT_A_PASSWORD
    Set-Content -NoNewline -Path (Join-Path $env:AUD004_SECRETS_DIR tenant_b_db_user) -Value tenant_b_api_test
    Set-Content -NoNewline -Path (Join-Path $env:AUD004_SECRETS_DIR tenant_b_db_password) -Value $env:AUD004_TENANT_B_PASSWORD
    Set-Content -NoNewline -Path (Join-Path $env:AUD004_SECRETS_DIR control_plane_db_user) -Value control_plane_test
    Set-Content -NoNewline -Path (Join-Path $env:AUD004_SECRETS_DIR control_plane_db_password) -Value $env:AUD004_CP_PASSWORD

Start only the disposable database:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml up -d --wait postgres

The explicit project name is required. Do not omit -p aud004-proof.

## Run tests

Build and run each identity in a separate container. Each process mounts only its own two secret files and proves own-database access plus explicit CONNECT denial to the other two databases:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml run --build --rm --no-deps tenant_a_probe
    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml run --build --rm --no-deps tenant_b_probe
    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml run --build --rm --no-deps control_plane_probe

The runner connects to PostgreSQL as postgres:5432; there is no host-published database port. For denied startup connections, PostgreSQL sends an explicit FATAL response containing permission denied for database "<name>" and User does not have CONNECT privilege. psycopg2 exposes this startup-time denial as OperationalError without a populated pgcode, so the test asserts both exact server-message fragments. DNS, server, missing-database, and password failures do not satisfy the assertion.

## Run through GitHub Actions

The existing **On-demand validation** workflow contains the AUD-004 proof job on this PR branch. To run it without changing application code or provisioning shared infrastructure:

1. Open the repository's **Actions** tab and select **On-demand validation**.
2. Choose **Run workflow**.
3. Select branch security/aud004-disposable-postgres-proof.
4. Select scope reconciliation.
5. Start the workflow and inspect the **AUD-004 disposable PostgreSQL workload-isolation proof** job.

The reconciliation scope runs the reconciliation regression tests and this isolated PostgreSQL proof. The proof job creates a temporary secret directory, runs three independent containers, and removes only the explicitly named Compose project and volume after its preflight succeeds. A skipped Release-gates job is not evidence that this proof ran. Do not select a release/deployment workflow or use production credentials.

## Teardown

First verify the active Compose project is the dedicated harness:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml ps

Only after confirming that output identifies the disposable AUD-004 PostgreSQL service, remove that project and its explicitly named volume:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml down --volumes --remove-orphans
    rm -rf "$AUD004_SECRETS_DIR"

PowerShell cleanup:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml down --volumes --remove-orphans
    Remove-Item -Recurse -Force $env:AUD004_SECRETS_DIR

Never substitute the default HMS Compose file or use a broad volume-prune command.

## Current proof limitations

This slice tests each identity from a separate container with only that identity's two secret mounts. It proves synthetic own-DB reads, explicit cross-database CONNECT denials, restricted runtime role attributes, no setup-role assumption, no PUBLIC CONNECT/TEMPORARY grants, and no predefined/elevated role membership. File-backed Compose secrets demonstrate container mount separation only; they are not a production secret-provider or workload-identity system. The PostgreSQL setup process still receives all three synthetic passwords to create the fixture. The proof does not establish host-level egress restrictions, real application identity, source-service authorization, credential rotation/revocation, or connection-pool draining.
