BEGIN;

ALTER TABLE integration_credentials
  ADD COLUMN IF NOT EXISTS is_global boolean NOT NULL DEFAULT false;

CREATE UNIQUE INDEX IF NOT EXISTS integration_credentials_one_global_provider
  ON integration_credentials (provider) WHERE is_global;

DROP POLICY IF EXISTS integration_credentials_global_read_policy ON integration_credentials;
CREATE POLICY integration_credentials_global_read_policy ON integration_credentials
  FOR SELECT USING (is_global AND provider = 'mailerfind' AND status != 'disabled');

COMMIT;
