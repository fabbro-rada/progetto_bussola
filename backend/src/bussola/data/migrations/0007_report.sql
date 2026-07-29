-- Aggregate matching outcomes (per-run, NO pseudonym / NO per-person rows, §5)
-- and a kind discriminator on export requests to reuse the S16 approval workflow.
-- Run as bussola_owner.

CREATE TABLE matching.match_run (
    id               bigserial PRIMARY KEY,
    created_at       timestamptz NOT NULL DEFAULT now(),
    job_request_id   bigint,
    evaluated_count  int NOT NULL,
    compatible_count int NOT NULL,
    gaps             jsonb NOT NULL DEFAULT '{}'::jsonb
);
-- auditor gets NO access to match_run: the matching schema already has no
-- USAGE grant to bussola_auditor (0005_job_requests.sql), so absence of
-- grant here is sufficient — consistent with S16.
GRANT SELECT, INSERT ON matching.match_run TO bussola_app;
GRANT USAGE, SELECT ON SEQUENCE matching.match_run_id_seq TO bussola_app;

ALTER TABLE export.export_request
    ADD COLUMN kind text NOT NULL DEFAULT 'profiles'
    CHECK (kind IN ('profiles', 'report'));
