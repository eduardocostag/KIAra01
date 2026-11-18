BEGIN;
-- Administração → Usuários → "Desconectar de todos os aparelhos".
-- The API connects as kiara_app, which (correctly) has no access to the auth schema. This one function, owned by
-- the migration role, ends the sessions of one user and nothing else; only kiara_app may call it, and the API
-- only calls it for the system administrators (kiara_api/admin_users.py).

CREATE OR REPLACE FUNCTION kiara.admin_end_user_sessions(target uuid)
RETURNS integer
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, auth
AS $$
DECLARE ended integer;
BEGIN
  IF target IS NULL THEN
    RETURN 0;
  END IF;
  DELETE FROM auth.refresh_tokens WHERE user_id = target::text;
  DELETE FROM auth.sessions WHERE user_id = target;
  GET DIAGNOSTICS ended = ROW_COUNT;
  RETURN ended;
END
$$;

REVOKE ALL ON FUNCTION kiara.admin_end_user_sessions(uuid) FROM PUBLIC;
DO $grant$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kiara_app') THEN
    GRANT USAGE ON SCHEMA kiara TO kiara_app;
    GRANT EXECUTE ON FUNCTION kiara.admin_end_user_sessions(uuid) TO kiara_app;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON FUNCTION kiara.admin_end_user_sessions(uuid) FROM anon;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    REVOKE ALL ON FUNCTION kiara.admin_end_user_sessions(uuid) FROM authenticated;
  END IF;
END
$grant$;
COMMIT;
