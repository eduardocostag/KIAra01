BEGIN;

CREATE TABLE social_channels (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  provider text NOT NULL CHECK (provider IN ('simulated')),
  name text NOT NULL CHECK (length(name) BETWEEN 1 AND 160),
  handle text CHECK (handle IS NULL OR length(handle) <= 160),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled','disconnected','error')),
  capabilities jsonb NOT NULL DEFAULT '{"drafts":true,"scheduling":true,"publishing":"simulated","analytics":false}'::jsonb CHECK (jsonb_typeof(capabilities)='object'),
  configuration jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(configuration)='object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id,id)
);
CREATE INDEX social_channels_status_idx ON social_channels (organization_id,status,updated_at DESC);

CREATE TABLE social_media (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  original_name text NOT NULL CHECK (length(original_name) BETWEEN 1 AND 255),
  content_type text NOT NULL CHECK (content_type IN ('image/jpeg','image/png','image/gif','image/webp','video/mp4')),
  byte_size bigint NOT NULL CHECK (byte_size BETWEEN 1 AND 52428800),
  checksum_sha256 text CHECK (checksum_sha256 IS NULL OR checksum_sha256 ~ '^[a-f0-9]{64}$'),
  storage_kind text NOT NULL DEFAULT 'metadata_only' CHECK (storage_kind='metadata_only'),
  status text NOT NULL DEFAULT 'registered' CHECK (status IN ('registered','available','unavailable')),
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id,id)
);
CREATE INDEX social_media_created_idx ON social_media (organization_id,created_at DESC);

CREATE TABLE social_posts (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  content text NOT NULL DEFAULT '' CHECK (length(content) <= 10000),
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','pending_approval','approved','scheduled','publishing','simulated','published','failed','cancelled')),
  scheduled_at timestamptz,
  approved_by uuid,
  approved_at timestamptz,
  published_at timestamptz,
  version integer NOT NULL DEFAULT 1 CHECK (version > 0),
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id,id),
  CHECK (status <> 'scheduled' OR scheduled_at IS NOT NULL),
  CHECK (status <> 'published' OR published_at IS NOT NULL)
);
CREATE INDEX social_posts_timeline_idx ON social_posts (organization_id,created_at DESC,id);
CREATE INDEX social_posts_schedule_idx ON social_posts (organization_id,status,scheduled_at) WHERE status='scheduled';

CREATE TABLE social_post_targets (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  post_id uuid NOT NULL,
  channel_id uuid NOT NULL,
  status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','approved','scheduled','simulated','publishing','published','failed','cancelled')),
  provider_post_id text CHECK (provider_post_id IS NULL OR length(provider_post_id) <= 200),
  release_url text CHECK (release_url IS NULL OR length(release_url) <= 2000),
  last_error_code text CHECK (last_error_code IS NULL OR length(last_error_code) <= 120),
  provider_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(provider_snapshot)='object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id,id),
  FOREIGN KEY (organization_id,post_id) REFERENCES social_posts(organization_id,id) ON DELETE CASCADE,
  FOREIGN KEY (organization_id,channel_id) REFERENCES social_channels(organization_id,id) ON DELETE RESTRICT,
  UNIQUE (organization_id,post_id,channel_id)
);
CREATE INDEX social_post_targets_post_idx ON social_post_targets (organization_id,post_id,created_at,id);

CREATE TABLE social_post_media (
  organization_id uuid NOT NULL,
  post_id uuid NOT NULL,
  media_id uuid NOT NULL,
  position integer NOT NULL CHECK (position BETWEEN 0 AND 19),
  PRIMARY KEY (organization_id,post_id,media_id),
  UNIQUE (organization_id,post_id,position),
  FOREIGN KEY (organization_id,post_id) REFERENCES social_posts(organization_id,id) ON DELETE CASCADE,
  FOREIGN KEY (organization_id,media_id) REFERENCES social_media(organization_id,id) ON DELETE RESTRICT
);

CREATE TABLE social_publication_attempts (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  post_id uuid NOT NULL,
  target_id uuid NOT NULL,
  mode text NOT NULL CHECK (mode IN ('simulated','live')),
  outcome text NOT NULL CHECK (outcome IN ('simulated','succeeded','failed','unknown')),
  error_code text CHECK (error_code IS NULL OR length(error_code) <= 120),
  response_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(response_snapshot)='object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id,id),
  FOREIGN KEY (organization_id,post_id) REFERENCES social_posts(organization_id,id) ON DELETE RESTRICT,
  FOREIGN KEY (organization_id,target_id) REFERENCES social_post_targets(organization_id,id) ON DELETE RESTRICT
);
CREATE INDEX social_publication_attempts_post_idx ON social_publication_attempts (organization_id,post_id,created_at DESC);

DO $rls$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['social_channels','social_media','social_posts','social_post_targets','social_post_media','social_publication_attempts']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
    EXECUTE format('CREATE POLICY %I ON %I FOR ALL USING (organization_id=kiara.current_organization_id()) WITH CHECK (organization_id=kiara.current_organization_id())',table_name||'_tenant_policy',table_name);
  END LOOP;
END
$rls$;

COMMIT;
