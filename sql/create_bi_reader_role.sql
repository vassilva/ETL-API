-- Read-only database access for the Power BI consumer of the bi views.
--
-- Two roles, privileges only (NO password in this file, never in Git):
--   bi_reader       NOLOGIN group role that holds the read privileges
--   powerbi_reader  LOGIN role used by Power BI; member of bi_reader
--
-- bi_reader may only: connect to this database, use schema bi and SELECT the
-- three approved views. It gets no privilege on the public base tables: the
-- views run with their owner's rights (not security_invoker), so none is
-- needed. It cannot write, create, alter or drop anything (only the owner
-- can), and cannot write through the auto-updatable dimension views
-- because it has no INSERT/UPDATE/DELETE privilege on them.
--
-- Database hardening: TEMPORARY is revoked from PUBLIC on this database, so
-- the BI login cannot create temporary objects either (the ETL owner is not
-- affected). As defense in depth the BI login starts every transaction
-- read-only (default_transaction_read_only).
--
-- Idempotent. Run as the owner of the database and of the bi objects (or a
-- superuser), after sql/create_bi_views.sql:
--   psql -h <host> -p <port> -d <database> -U <owner> -f sql/create_bi_reader_role.sql
--
-- Password provisioning is a separate LOCAL step (see README). Until a
-- password is set, powerbi_reader cannot log in with password
-- authentication. Set it interactively, so it is never stored or echoed:
--   psql ... -U <owner> -c "\password powerbi_reader"

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bi_reader') THEN
        CREATE ROLE bi_reader NOLOGIN;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'powerbi_reader') THEN
        CREATE ROLE powerbi_reader LOGIN;
    END IF;
END
$$;

-- Attributes re-asserted on every run: no elevated capability of any kind
ALTER ROLE bi_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE powerbi_reader LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
ALTER ROLE powerbi_reader SET default_transaction_read_only = on;

GRANT bi_reader TO powerbi_reader;

-- Database level: connect only (explicit, so a future REVOKE CONNECT FROM
-- PUBLIC keeps Power BI working); no temporary objects for PUBLIC
DO $$
BEGIN
    EXECUTE format('GRANT CONNECT ON DATABASE %I TO bi_reader', current_database());
    EXECUTE format('REVOKE TEMPORARY ON DATABASE %I FROM PUBLIC', current_database());
END
$$;

-- Schema and views: exactly SELECT on the three approved views
GRANT USAGE ON SCHEMA bi TO bi_reader;
REVOKE ALL ON bi.fact_cart_item, bi.dim_product, bi.dim_customer FROM bi_reader;
GRANT SELECT ON bi.fact_cart_item, bi.dim_product, bi.dim_customer TO bi_reader;

COMMIT;
