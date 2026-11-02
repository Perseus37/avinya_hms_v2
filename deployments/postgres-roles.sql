-- =========================================================================
-- Avinya HMS Production PostgreSQL Role-Based Access Control (RBAC)
-- Enforces Principle of Least Privilege across Application, Migrator, Backup, and Monitoring
-- =========================================================================

-- 1. Create dedicated system roles if they do not exist
DO $$
BEGIN
    -- Application Runtime Role (DML only: SELECT, INSERT, UPDATE, DELETE)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hms_app') THEN
        CREATE ROLE hms_app WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;

    -- Migration Runner Role (DDL allowed: CREATE, ALTER, DROP within schema)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hms_migrator') THEN
        CREATE ROLE hms_migrator WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT;
    END IF;

    -- Automated Backup Role (Read-only on all database objects)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hms_backup') THEN
        CREATE ROLE hms_backup WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;

    -- Observability & Metrics Exporter Role (Access to pg_stat views)
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hms_exporter') THEN
        CREATE ROLE hms_exporter WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END $$;

-- 2. Grant PostgreSQL standard predefined roles
GRANT pg_read_all_data TO hms_backup;
GRANT pg_monitor TO hms_exporter;

-- 3. Schema-level grants for application runtime (hms_app)
GRANT CONNECT ON DATABASE postgres TO hms_app;
GRANT USAGE ON SCHEMA public TO hms_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO hms_app;
GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO hms_app;

-- Ensure future tables and sequences created by migrations inherit these grants
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO hms_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO hms_app;

-- 4. Schema-level grants for migration runner (hms_migrator)
GRANT CONNECT, TEMPORARY ON DATABASE postgres TO hms_migrator;
GRANT ALL PRIVILEGES ON SCHEMA public TO hms_migrator;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO hms_migrator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO hms_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON TABLES TO hms_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL PRIVILEGES ON SEQUENCES TO hms_migrator;

