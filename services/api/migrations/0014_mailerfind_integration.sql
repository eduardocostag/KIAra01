BEGIN;

ALTER TABLE integration_credentials
  DROP CONSTRAINT IF EXISTS integration_credentials_provider_check;

ALTER TABLE integration_credentials
  ADD CONSTRAINT integration_credentials_provider_check
  CHECK (provider IN ('google', 'instagram', 'hermes', 'mailerfind')) NOT VALID;

ALTER TABLE integration_credentials
  VALIDATE CONSTRAINT integration_credentials_provider_check;

COMMIT;
