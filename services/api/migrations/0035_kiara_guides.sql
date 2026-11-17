BEGIN;
-- Notes the Kiara team writes in Obsidian ("Ensinar a Kiara" folder of the vault on Debian). The learning worker
-- uploads them and the chat reads them as general guidance for every workspace. Admin-written content only:
-- no workspace data, no secrets (the API refuses notes that look like credentials).

CREATE TABLE kiara_guides (
  path text PRIMARY KEY CHECK (path ~ '^Ensinar a Kiara/[^/].{0,150}\.md$' AND path !~ '\.\.'),
  title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 120),
  body text NOT NULL CHECK (length(body) BETWEEN 1 AND 4000),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE kiara_guides ENABLE ROW LEVEL SECURITY;
ALTER TABLE kiara_guides FORCE ROW LEVEL SECURITY;
REVOKE ALL ON kiara_guides FROM PUBLIC;

DO $browser_access$
DECLARE browser_role text;
BEGIN
  FOREACH browser_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = browser_role) THEN
      EXECUTE format('REVOKE ALL ON kiara_guides FROM %I', browser_role);
    END IF;
  END LOOP;
END
$browser_access$;

DO $server_access$
DECLARE server_role text;
BEGIN
  FOREACH server_role IN ARRAY ARRAY['kiara_app', 'kiara_runtime'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = server_role) THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON kiara_guides TO %I', server_role);
      EXECUTE format('CREATE POLICY %I ON kiara_guides FOR ALL TO %I USING (true) WITH CHECK (true)', 'kiara_guides_' || server_role, server_role);
    END IF;
  END LOOP;
END
$server_access$;
COMMIT;
