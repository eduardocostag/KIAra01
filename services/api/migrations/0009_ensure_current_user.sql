BEGIN;

CREATE OR REPLACE FUNCTION kiara.ensure_current_user(
  requested_identity_provider text,
  requested_external_subject text
)
RETURNS uuid
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, kiara
AS $$
DECLARE
  authenticated_user_id uuid := kiara.current_user_id();
BEGIN
  IF authenticated_user_id IS NULL THEN
    RAISE EXCEPTION 'app.user_id is required' USING ERRCODE = '42501';
  END IF;
  IF length(requested_identity_provider) NOT BETWEEN 1 AND 80 THEN
    RAISE EXCEPTION 'invalid identity provider' USING ERRCODE = '22023';
  END IF;
  IF length(requested_external_subject) NOT BETWEEN 1 AND 255 THEN
    RAISE EXCEPTION 'invalid external subject' USING ERRCODE = '22023';
  END IF;

  INSERT INTO public.users (id, identity_provider, external_subject)
  VALUES (authenticated_user_id, requested_identity_provider, requested_external_subject)
  ON CONFLICT (id) DO NOTHING;

  RETURN authenticated_user_id;
END;
$$;

REVOKE ALL ON FUNCTION kiara.ensure_current_user(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kiara.ensure_current_user(text, text) TO kiara_app;

COMMIT;
