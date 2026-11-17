BEGIN;
-- Kiara keeps learning from what happens in each workspace and, without personal data, from all of them.
--
-- 1. Per workspace: the learning worker writes short lessons from the lead searches (which niches and regions
--    turn into conversations and deals, which ones waste searches) into kiara_memories with source 'learned'.
--    They show on "O que a Kiara lembra" and reach the chat like the other memories.
-- 2. General patterns: per niche and city, only counts (searches, results, leads added, leads that advanced) and
--    how many workspaces contributed. No names, phones, messages or workspace ids are stored there.

ALTER TABLE kiara_memories DROP CONSTRAINT IF EXISTS kiara_memories_source_check;
ALTER TABLE kiara_memories ADD CONSTRAINT kiara_memories_source_check CHECK (source IN ('chat', 'manual', 'learned'));

-- Workspaces with recent activity (the worker cannot list tenants itself: every tenant table forces RLS).
CREATE TABLE learning_workspaces (
  organization_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
  last_activity_at timestamptz NOT NULL DEFAULT now(),
  learned_at timestamptz
);

CREATE TABLE kiara_patterns (
  niche text NOT NULL CHECK (length(btrim(niche)) BETWEEN 2 AND 80),
  city text NOT NULL DEFAULT '' CHECK (length(city) <= 80),
  searches integer NOT NULL DEFAULT 0 CHECK (searches >= 0),
  results integer NOT NULL DEFAULT 0 CHECK (results >= 0),
  with_whatsapp integer NOT NULL DEFAULT 0 CHECK (with_whatsapp >= 0),
  without_website integer NOT NULL DEFAULT 0 CHECK (without_website >= 0),
  added integer NOT NULL DEFAULT 0 CHECK (added >= 0),
  advanced integer NOT NULL DEFAULT 0 CHECK (advanced >= 0),
  won integer NOT NULL DEFAULT 0 CHECK (won >= 0),
  workspaces integer NOT NULL DEFAULT 0 CHECK (workspaces >= 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (niche, city)
);

ALTER TABLE learning_workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE learning_workspaces FORCE ROW LEVEL SECURITY;
ALTER TABLE kiara_patterns ENABLE ROW LEVEL SECURITY;
ALTER TABLE kiara_patterns FORCE ROW LEVEL SECURITY;
REVOKE ALL ON learning_workspaces, kiara_patterns FROM PUBLIC;

DO $browser_access$
DECLARE browser_role text;
BEGIN
  FOREACH browser_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = browser_role) THEN
      EXECUTE format('REVOKE ALL ON learning_workspaces, kiara_patterns FROM %I', browser_role);
    END IF;
  END LOOP;
END
$browser_access$;

DO $server_access$
DECLARE server_role text;
BEGIN
  FOREACH server_role IN ARRAY ARRAY['kiara_app', 'kiara_runtime'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = server_role) THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON learning_workspaces, kiara_patterns TO %I', server_role);
      EXECUTE format('CREATE POLICY %I ON learning_workspaces FOR ALL TO %I USING (true) WITH CHECK (true)', 'learning_workspaces_' || server_role, server_role);
      EXECUTE format('CREATE POLICY %I ON kiara_patterns FOR ALL TO %I USING (true) WITH CHECK (true)', 'kiara_patterns_' || server_role, server_role);
    END IF;
  END LOOP;
END
$server_access$;
-- Existing workspaces start in the registry (only rows the migration role can see; activity adds the rest).
INSERT INTO learning_workspaces (organization_id) SELECT id FROM organizations ON CONFLICT DO NOTHING;
COMMIT;
