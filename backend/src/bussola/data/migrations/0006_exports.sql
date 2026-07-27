-- Export requests (authorized data egress, §7.3). Run as bussola_owner.
CREATE SCHEMA IF NOT EXISTS export AUTHORIZATION bussola_owner;
GRANT USAGE ON SCHEMA export TO bussola_app;
-- auditor gets NO access to the export schema (absence of grant).

CREATE TABLE export.export_request (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    requested_by    text NOT NULL,
    filters         jsonb NOT NULL DEFAULT '{}'::jsonb,
    reason          text NOT NULL,
    status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'approved', 'denied')),
    decided_by      text,
    decided_at      timestamptz,
    decision_reason text,
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- No DELETE: export requests remain traceable (§7.3).
GRANT SELECT, INSERT, UPDATE ON export.export_request TO bussola_app;
