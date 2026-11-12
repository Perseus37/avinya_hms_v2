# AUD-004 disposable PostgreSQL ACL proof

This is an opt-in, isolated test fixture, not a production deployment template. It uses synthetic marker rows only. It does not exercise application federation, secret-manager policy, network egress controls, credential rotation, connection-pool draining, or source-owned disclosure. Passing this suite is only an initial PostgreSQL database CONNECT/role proof.

## Safety boundary

- Do not run from a production host or against a shared/developer PostgreSQL server.
- Do not use a production or normal HMS .env file.
- The Compose project, volume and network are explicitly named aud004-proof, aud004-proof-pgdata, and aud004-proof-only.
- PostgreSQL is published only on loopback port 55439.
- The setup password is supplied at runtime; the tenant passwords in init.sql are fixed, synthetic test-only values. Never reuse them.
- The initialization SQL runs only when PostgreSQL initializes an empty volume. Existing volumes are not reset automatically.
- No patient or real tenant data is permitted.

## Start

Use a disposable local machine with Docker Compose installed. Set a throwaway setup password in the current shell, then run:

    export AUD004_SETUP_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml up -d --wait

PowerShell:

    $env:AUD004_SETUP_PASSWORD = [Convert]::ToBase64String([Security.Cryptography.RandomNumberGenerator]::GetBytes(32))
    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml up -d --wait

The explicit project name is required. Do not omit -p aud004-proof.

## Run tests

Install the repository's pinned psycopg2-binary and pytest in an isolated development environment, then run:

    python -m pytest -q deployments/aud004-proof/test_acl.py

The test suite expects the dedicated service on 127.0.0.1:55439. It fails if the server is unreachable; it does not substitute SQLite. A denied connection passes only when PostgreSQL returns SQLSTATE 42501.

## Teardown

First verify the active Compose project is the dedicated harness:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml ps

Only after confirming that output identifies the disposable AUD-004 PostgreSQL service, remove that project and its explicitly named volume:

    docker compose -p aud004-proof -f deployments/aud004-proof/compose.yaml down --volumes --remove-orphans

This command is scoped to the dedicated project file and project name. Never substitute the default HMS Compose file or use a broad volume-prune command.

## Current proof limitations

The first slice tests per-database CONNECT ACLs, tenant-local synthetic reads, control-plane separation and non-privileged runtime role attributes. It does not yet prove source-service authorization, object-level source grants, secret isolation, role membership closure, PUBLIC/predefined-role inventory, workload container identity, revocation or pool draining. Those remain required before any production role/bootstrap/runtime change.
