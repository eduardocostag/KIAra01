BEGIN;

CREATE TABLE competition_analysis_jobs (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  idempotency_key text NOT NULL CHECK (length(idempotency_key) BETWEEN 16 AND 128),
  request_fingerprint text NOT NULL CHECK (length(request_fingerprint) = 64),
  provider_analysis_id text NOT NULL CHECK (length(provider_analysis_id) BETWEEN 1 AND 160),
  mode text NOT NULL CHECK (mode IN ('followers', 'commenters', 'likers', 'post_audience')),
  target text NOT NULL CHECK (length(target) BETWEEN 1 AND 500),
  normalized_target text NOT NULL CHECK (length(normalized_target) BETWEEN 1 AND 500),
  media_id text CHECK (media_id IS NULL OR length(media_id) <= 100),
  name text NOT NULL CHECK (length(name) BETWEEN 1 AND 120),
  state text NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued', 'running', 'paused', 'completed', 'failed')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
  checkpoint jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(checkpoint) = 'object'),
  error_code text CHECK (error_code IS NULL OR length(error_code) <= 100),
  error_message text CHECK (error_message IS NULL OR length(error_message) <= 500),
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  PRIMARY KEY (organization_id, id),
  UNIQUE (organization_id, idempotency_key),
  UNIQUE (organization_id, provider_analysis_id),
  CHECK ((state = 'running') = (lease_expires_at IS NOT NULL)),
  CHECK ((state = 'completed') = (completed_at IS NOT NULL))
);

ALTER TABLE competition_analysis_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE competition_analysis_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY competition_analysis_jobs_tenant_policy
  ON competition_analysis_jobs FOR ALL
  USING (organization_id = kiara.current_organization_id())
  WITH CHECK (organization_id = kiara.current_organization_id());

COMMIT;
