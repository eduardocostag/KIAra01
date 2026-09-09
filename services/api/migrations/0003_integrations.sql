BEGIN;

CREATE TABLE integration_credentials (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  provider text NOT NULL CHECK (provider IN ('google', 'instagram')),
  encrypted_credentials text NOT NULL,
  configured_fields text[] NOT NULL DEFAULT '{}',
  status text NOT NULL DEFAULT 'configured' CHECK (status IN ('configured', 'connected', 'error', 'disabled')),
  last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  UNIQUE (organization_id, provider)
);

ALTER TABLE integration_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE integration_credentials FORCE ROW LEVEL SECURITY;
CREATE POLICY integration_credentials_tenant_policy ON integration_credentials
  FOR ALL USING (organization_id = kiara.current_organization_id())
  WITH CHECK (organization_id = kiara.current_organization_id());

COMMIT;
