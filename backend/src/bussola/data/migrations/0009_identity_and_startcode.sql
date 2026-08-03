-- Segregated identity register + one-time interview start codes (§5). Run as bussola_owner.
-- identity.pseudonym_identity: the ONLY link between a pseudonym and a real person
-- (matricola). No name/anagraphic. Readable only via the supervisor-gated app path;
-- the auditor gets NO grant on this schema (absence of grant = no access).
CREATE SCHEMA IF NOT EXISTS identity AUTHORIZATION bussola_owner;
GRANT USAGE ON SCHEMA identity TO bussola_app;

CREATE TABLE identity.pseudonym_identity (
    pseudonym_id text PRIMARY KEY REFERENCES profiles.work_profile(pseudonym_id),
    matricola    text NOT NULL UNIQUE,
    created_at   timestamptz NOT NULL DEFAULT now(),
    created_by   text NOT NULL
);
-- No extra index on matricola: the UNIQUE constraint above already creates one.
GRANT SELECT, INSERT ON identity.pseudonym_identity TO bussola_app;

-- startcode.start_code: one-time, expiring code that launches a FIRST interview on a
-- pre-created (empty) pseudonym. Stores ONLY the code hash + pseudonym + timestamps.
CREATE SCHEMA IF NOT EXISTS startcode AUTHORIZATION bussola_owner;
GRANT USAGE ON SCHEMA startcode TO bussola_app;

CREATE TABLE startcode.start_code (
    code_hash    text PRIMARY KEY,
    pseudonym_id text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    used_at      timestamptz
);
GRANT SELECT, INSERT, UPDATE ON startcode.start_code TO bussola_app;
