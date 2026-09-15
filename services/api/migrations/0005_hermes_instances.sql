BEGIN;

ALTER TABLE integration_credentials DROP CONSTRAINT integration_credentials_provider_check;
ALTER TABLE integration_credentials ADD CONSTRAINT integration_credentials_provider_check
  CHECK (provider IN ('google', 'instagram', 'hermes'));

ALTER TABLE integration_credentials ADD COLUMN hermes_instance_id text;
ALTER TABLE integration_credentials ADD COLUMN hermes_endpoint_fingerprint text;
CREATE UNIQUE INDEX integration_credentials_hermes_instance_unique
  ON integration_credentials (hermes_instance_id) WHERE provider = 'hermes';
CREATE UNIQUE INDEX integration_credentials_hermes_endpoint_unique
  ON integration_credentials (hermes_endpoint_fingerprint) WHERE provider = 'hermes';

COMMIT;
