-- Disposable synthetic-only AUD-004 test cluster. Passwords are test fixtures, never reuse.
CREATE ROLE tenant_a_api_test LOGIN PASSWORD 'aud004-a-api-test-only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE tenant_b_api_test LOGIN PASSWORD 'aud004-b-api-test-only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
CREATE ROLE control_plane_test LOGIN PASSWORD 'aud004-cp-test-only' NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

CREATE DATABASE aud004_tenant_a;
CREATE DATABASE aud004_tenant_b;
CREATE DATABASE aud004_control_plane;

REVOKE CONNECT, TEMPORARY ON DATABASE aud004_tenant_a FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE aud004_tenant_b FROM PUBLIC;
REVOKE CONNECT, TEMPORARY ON DATABASE aud004_control_plane FROM PUBLIC;
GRANT CONNECT ON DATABASE aud004_tenant_a TO tenant_a_api_test;
GRANT CONNECT ON DATABASE aud004_tenant_b TO tenant_b_api_test;
GRANT CONNECT ON DATABASE aud004_control_plane TO control_plane_test;

\connect aud004_tenant_a
CREATE SCHEMA synthetic AUTHORIZATION aud004_setup;
CREATE TABLE synthetic.tenant_marker (marker text PRIMARY KEY);
INSERT INTO synthetic.tenant_marker VALUES ('TENANT_A_SYNTHETIC_ONLY');
GRANT USAGE ON SCHEMA synthetic TO tenant_a_api_test;
GRANT SELECT ON synthetic.tenant_marker TO tenant_a_api_test;

\connect aud004_tenant_b
CREATE SCHEMA synthetic AUTHORIZATION aud004_setup;
CREATE TABLE synthetic.tenant_marker (marker text PRIMARY KEY);
INSERT INTO synthetic.tenant_marker VALUES ('TENANT_B_SYNTHETIC_ONLY');
GRANT USAGE ON SCHEMA synthetic TO tenant_b_api_test;
GRANT SELECT ON synthetic.tenant_marker TO tenant_b_api_test;

\connect aud004_control_plane
CREATE SCHEMA synthetic AUTHORIZATION aud004_setup;
CREATE TABLE synthetic.control_marker (marker text PRIMARY KEY);
INSERT INTO synthetic.control_marker VALUES ('CONTROL_PLANE_SYNTHETIC_ONLY');
GRANT USAGE ON SCHEMA synthetic TO control_plane_test;
GRANT SELECT ON synthetic.control_marker TO control_plane_test;
