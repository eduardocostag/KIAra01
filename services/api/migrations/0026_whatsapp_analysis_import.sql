BEGIN;

CREATE TABLE whatsapp_web_analysis_jobs (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  status text NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  result jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(result) = 'object'),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  lease_until timestamptz,
  PRIMARY KEY (organization_id, id)
);
CREATE INDEX whatsapp_web_analysis_queue_idx
  ON whatsapp_web_analysis_jobs (organization_id, created_at)
  WHERE status IN ('queued', 'running');
CREATE UNIQUE INDEX whatsapp_web_one_active_analysis_idx
  ON whatsapp_web_analysis_jobs (organization_id)
  WHERE status IN ('queued', 'running');

CREATE UNIQUE INDEX consumers_whatsapp_phone_idx
  ON consumers (organization_id, (attributes->'whatsapp'->>'phone'))
  WHERE attributes->'whatsapp'->>'phone' IS NOT NULL;

ALTER TABLE whatsapp_web_analysis_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE whatsapp_web_analysis_jobs FORCE ROW LEVEL SECURITY;
CREATE POLICY whatsapp_web_analysis_jobs_tenant_policy
  ON whatsapp_web_analysis_jobs
  FOR ALL
  USING (organization_id = kiara.current_organization_id())
  WITH CHECK (organization_id = kiara.current_organization_id());

COMMIT;
