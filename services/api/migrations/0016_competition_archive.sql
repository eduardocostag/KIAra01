BEGIN;

CREATE TABLE competition_analyses (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  provider text NOT NULL DEFAULT 'mailerfind' CHECK (provider = 'mailerfind'),
  provider_analysis_id text NOT NULL CHECK (length(provider_analysis_id) BETWEEN 1 AND 160),
  mode text CHECK (mode IS NULL OR mode IN ('followers', 'account_audience', 'account_commenters', 'commenters')),
  target text CHECK (target IS NULL OR length(target) <= 500),
  name text CHECK (name IS NULL OR length(name) <= 200),
  status text NOT NULL DEFAULT 'created' CHECK (length(status) BETWEEN 1 AND 40),
  prospect_count integer NOT NULL DEFAULT 0 CHECK (prospect_count >= 0),
  provider_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(provider_snapshot) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  last_synced_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  UNIQUE (organization_id, provider, provider_analysis_id)
);
CREATE INDEX competition_analyses_timeline_idx
  ON competition_analyses (organization_id, updated_at DESC, id);

CREATE TABLE competition_prospects (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  analysis_id uuid NOT NULL,
  provider_prospect_id text NOT NULL CHECK (length(provider_prospect_id) BETWEEN 1 AND 200),
  instagram_username text CHECK (instagram_username IS NULL OR length(instagram_username) <= 160),
  display_name text CHECK (display_name IS NULL OR length(display_name) <= 500),
  public_email text CHECK (public_email IS NULL OR length(public_email) <= 320),
  phone text CHECK (phone IS NULL OR length(phone) <= 80),
  provider_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(provider_snapshot) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, analysis_id)
    REFERENCES competition_analyses (organization_id, id) ON DELETE CASCADE,
  UNIQUE (organization_id, analysis_id, provider_prospect_id)
);
CREATE INDEX competition_prospects_analysis_idx
  ON competition_prospects (organization_id, analysis_id, created_at, id);

DO $rls$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['competition_analyses', 'competition_prospects']
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
