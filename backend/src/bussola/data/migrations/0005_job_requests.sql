-- Job requests (positions offered by companies). Run as bussola_owner.
CREATE SCHEMA IF NOT EXISTS matching AUTHORIZATION bussola_owner;
GRANT USAGE ON SCHEMA matching TO bussola_app;
-- auditor gets NO access to the matching schema (absence of grant).

CREATE TABLE matching.job_request (
    id                     bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    title                  text NOT NULL,
    sector                 text NOT NULL,
    description            text NOT NULL DEFAULT '',
    required_skills        text[] NOT NULL DEFAULT '{}',
    required_languages     jsonb NOT NULL DEFAULT '[]'::jsonb,
    required_availability  text,
    involves_night_shifts  boolean NOT NULL DEFAULT false,
    training_prerequisites text[] NOT NULL DEFAULT '{}',
    created_by             text NOT NULL,
    created_at             timestamptz NOT NULL DEFAULT now(),
    updated_at             timestamptz NOT NULL DEFAULT now()
);

-- No DELETE (positions are closed by convention, not deleted, in Fase 1).
GRANT SELECT, INSERT, UPDATE ON matching.job_request TO bussola_app;
