BEGIN;
-- Security: the browser roles of Supabase (anon = the public key shipped in the site, authenticated = any
-- logged-in browser) never touch Kiara tables directly. The site and the API reach the database only from the
-- server. Older tables still had Supabase's default grants (ALL, even TRUNCATE) for those roles, and the policy
-- for global integration credentials applied to PUBLIC, so anyone with the public key could read the encrypted
-- global Mailerfind credential through the REST API. This migration:
--   1. revokes every table, sequence and function privilege of anon/authenticated in public and kiara;
--   2. stops future tables from getting those grants by default;
--   3. limits the global-credential policy to the server roles.

DO $lock$
DECLARE browser_role text; target_schema text;
BEGIN
  FOREACH browser_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = browser_role) THEN
      CONTINUE;
    END IF;
    FOREACH target_schema IN ARRAY ARRAY['public', 'kiara'] LOOP
      IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = target_schema) THEN
        CONTINUE;
      END IF;
      EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA %I FROM %I', target_schema, browser_role);
      EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA %I FROM %I', target_schema, browser_role);
      EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA %I FROM %I', target_schema, browser_role);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL ON TABLES FROM %I', target_schema, browser_role);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL ON SEQUENCES FROM %I', target_schema, browser_role);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA %I REVOKE ALL ON FUNCTIONS FROM %I', target_schema, browser_role);
      BEGIN
        -- Tables created from the Supabase dashboard belong to supabase_admin; only possible when we may act for it.
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA %I REVOKE ALL ON TABLES FROM %I', target_schema, browser_role);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA %I REVOKE ALL ON SEQUENCES FROM %I', target_schema, browser_role);
        EXECUTE format('ALTER DEFAULT PRIVILEGES FOR ROLE supabase_admin IN SCHEMA %I REVOKE ALL ON FUNCTIONS FROM %I', target_schema, browser_role);
      EXCEPTION WHEN insufficient_privilege OR undefined_object THEN
        NULL;
      END;
    END LOOP;
  END LOOP;
END
$lock$;

DO $policy$
DECLARE server_roles text;
BEGIN
  SELECT string_agg(quote_ident(rolname), ', ') INTO server_roles
  FROM pg_roles WHERE rolname IN ('kiara_app', 'kiara_runtime', 'service_role');
  IF server_roles IS NOT NULL AND EXISTS (
    SELECT 1 FROM pg_policies WHERE tablename = 'integration_credentials' AND policyname = 'integration_credentials_global_read_policy'
  ) THEN
    EXECUTE 'ALTER POLICY integration_credentials_global_read_policy ON integration_credentials TO ' || server_roles;
  END IF;
END
$policy$;
COMMIT;
