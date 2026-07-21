-- Append-only, tamper-evident audit log.
CREATE TABLE audit.audit_log (
    id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at      timestamptz NOT NULL,
    actor            text,
    action           text NOT NULL,
    target_pseudonym text,
    details          jsonb NOT NULL DEFAULT '{}'::jsonb,
    prev_hash        text,
    record_hash      text NOT NULL
);

-- app may append and read (reading is needed to chain); auditor may only read.
GRANT SELECT, INSERT ON audit.audit_log TO bussola_app;
GRANT SELECT ON audit.audit_log TO bussola_auditor;

-- Append-only: forbid UPDATE/DELETE for everyone via a row-level trigger.
-- Extraordinary maintenance = owner deliberately disables/drops the trigger.
CREATE OR REPLACE FUNCTION audit.forbid_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit.audit_log is append-only: % is not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_append_only
    BEFORE UPDATE OR DELETE ON audit.audit_log
    FOR EACH ROW EXECUTE FUNCTION audit.forbid_mutation();
