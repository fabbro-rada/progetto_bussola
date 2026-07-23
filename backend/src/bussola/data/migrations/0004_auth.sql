-- Operator accounts + server-side sessions. Run as bussola_owner.
CREATE SCHEMA IF NOT EXISTS auth AUTHORIZATION bussola_owner;
-- app manages accounts/sessions; fine-grained who-can-do-what is enforced in
-- the application via RBAC. auditor gets NO access (absence of grant).
GRANT USAGE ON SCHEMA auth TO bussola_app;

CREATE TABLE auth.operator (
    id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    username             text NOT NULL UNIQUE,
    display_name         text NOT NULL,
    password_hash        text NOT NULL,
    role                 text NOT NULL,
    is_active            boolean NOT NULL DEFAULT true,
    must_change_password boolean NOT NULL DEFAULT true,
    failed_attempts      integer NOT NULL DEFAULT 0,
    locked_until         timestamptz,
    created_at           timestamptz NOT NULL DEFAULT now(),
    created_by           text,
    disabled_at          timestamptz,
    disabled_by          text
);

CREATE TABLE auth.session (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    token_hash    text NOT NULL UNIQUE,
    operator_id   bigint NOT NULL REFERENCES auth.operator(id),
    created_at    timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz NOT NULL,
    last_seen_at  timestamptz NOT NULL DEFAULT now(),
    revoked_at    timestamptz
);
CREATE INDEX session_operator_idx ON auth.session (operator_id);

-- No DELETE: accounts are disabled (not deleted), sessions revoked (not deleted).
GRANT SELECT, INSERT, UPDATE ON auth.operator TO bussola_app;
GRANT SELECT, INSERT, UPDATE ON auth.session TO bussola_app;
