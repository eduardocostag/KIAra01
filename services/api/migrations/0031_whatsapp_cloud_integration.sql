-- Official WhatsApp (Meta Cloud API) per client, connected through Embedded Signup.
-- Credentials stay encrypted in integration_credentials like every other provider.
BEGIN;

ALTER TABLE integration_credentials
  DROP CONSTRAINT IF EXISTS integration_credentials_provider_check;
ALTER TABLE integration_credentials
  ADD CONSTRAINT integration_credentials_provider_check
  CHECK (provider IN ('google', 'instagram', 'instagram_session', 'hermes', 'mailerfind', 'postiz', 'chatwoot', 'whatsapp_cloud')) NOT VALID;
ALTER TABLE integration_credentials
  VALIDATE CONSTRAINT integration_credentials_provider_check;

COMMIT;
