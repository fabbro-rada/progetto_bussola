-- Work profiles, keyed by pseudonym; the validated profile is stored as JSONB.
CREATE TABLE profiles.work_profile (
    pseudonym_id text PRIMARY KEY,
    profile      jsonb NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

-- app may read and write profiles; never DELETE.
GRANT SELECT, INSERT, UPDATE ON profiles.work_profile TO bussola_app;
