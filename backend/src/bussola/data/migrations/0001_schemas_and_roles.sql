-- Segregated schemas + least-privilege schema grants. Run as bussola_owner.
CREATE SCHEMA IF NOT EXISTS profiles AUTHORIZATION bussola_owner;
CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION bussola_owner;

-- app uses both schemas; auditor only the audit schema.
GRANT USAGE ON SCHEMA profiles TO bussola_app;
GRANT USAGE ON SCHEMA audit TO bussola_app;
GRANT USAGE ON SCHEMA audit TO bussola_auditor;
-- auditor gets NO privilege on the profiles schema (absence of grant = no access).
