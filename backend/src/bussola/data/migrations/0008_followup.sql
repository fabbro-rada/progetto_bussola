-- Follow-up interview tokens (Fase 2·A, §5): re-link a returning person to
-- their pseudonymized profile without ever storing identity/anagraphic data.
-- Stores ONLY the token hash + pseudonym + timestamps. Run as bussola_owner.
CREATE SCHEMA IF NOT EXISTS followup AUTHORIZATION bussola_owner;
GRANT USAGE ON SCHEMA followup TO bussola_app;
-- auditor gets NO access to the followup schema (absence of grant).

CREATE TABLE followup.followup_token (
    token_hash   text PRIMARY KEY,
    pseudonym_id text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    expires_at   timestamptz NOT NULL,
    used_at      timestamptz
);

GRANT SELECT, INSERT, UPDATE ON followup.followup_token TO bussola_app;
