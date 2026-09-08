BEGIN;

CREATE TABLE hunter_searches (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  requested_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  market text NOT NULL CHECK (market IN ('b2c', 'b2b')),
  query text NOT NULL CHECK (length(btrim(query)) BETWEEN 2 AND 300),
  location text CHECK (location IS NULL OR length(location) <= 160),
  sources text[] NOT NULL CHECK (cardinality(sources) BETWEEN 1 AND 4),
  result_limit integer NOT NULL CHECK (result_limit BETWEEN 1 AND 20),
  status text NOT NULL DEFAULT 'pending_confirmation'
    CHECK (status IN ('pending_confirmation', 'running', 'completed', 'failed', 'cancelled')),
  confirmed_by uuid REFERENCES users(id) ON DELETE RESTRICT,
  confirmed_at timestamptz,
  error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  CHECK ((confirmed_by IS NULL) = (confirmed_at IS NULL))
);
CREATE INDEX hunter_searches_timeline_idx
  ON hunter_searches (organization_id, created_at DESC, id);

CREATE TABLE hunter_results (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  search_id uuid NOT NULL,
  source text NOT NULL CHECK (source IN ('web', 'google_maps', 'instagram', 'linkedin')),
  title text NOT NULL CHECK (length(title) BETWEEN 1 AND 500),
  url text NOT NULL CHECK (length(url) BETWEEN 8 AND 3000),
  summary text,
  public_data jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(public_data) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, search_id)
    REFERENCES hunter_searches (organization_id, id) ON DELETE CASCADE,
  UNIQUE (organization_id, search_id, url)
);
CREATE INDEX hunter_results_search_idx
  ON hunter_results (organization_id, search_id, created_at, id);

DO $rls$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['hunter_searches', 'hunter_results']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
    EXECUTE format(
      'CREATE POLICY %I ON %I FOR ALL USING (organization_id = kiara.current_organization_id()) WITH CHECK (organization_id = kiara.current_organization_id())',
      table_name || '_tenant_policy', table_name
    );
  END LOOP;
END
$rls$;

COMMIT;
