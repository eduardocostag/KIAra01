BEGIN;

ALTER TABLE integration_credentials
  DROP CONSTRAINT IF EXISTS integration_credentials_provider_check;
ALTER TABLE integration_credentials
  ADD CONSTRAINT integration_credentials_provider_check
  CHECK (provider IN ('google', 'instagram', 'instagram_session', 'hermes', 'mailerfind', 'postiz')) NOT VALID;
ALTER TABLE integration_credentials
  VALIDATE CONSTRAINT integration_credentials_provider_check;

COMMIT;
