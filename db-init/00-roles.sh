#!/bin/bash
# Runs once, as superuser, on first container init. Creates the least-privilege
# roles and makes bussola_owner own the database (so it can run DDL migrations).
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE ROLE bussola_owner   LOGIN PASSWORD '${BUSSOLA_OWNER_PASSWORD}';
    CREATE ROLE bussola_app     LOGIN PASSWORD '${BUSSOLA_APP_PASSWORD}';
    CREATE ROLE bussola_auditor LOGIN PASSWORD '${BUSSOLA_AUDITOR_PASSWORD}';
    ALTER DATABASE ${POSTGRES_DB} OWNER TO bussola_owner;
    GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO bussola_app, bussola_auditor;
EOSQL
