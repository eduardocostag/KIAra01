BEGIN;

-- Remove only the analyses produced by the retired HTML-link heuristic.
DELETE FROM competition_analyses
WHERE provider = 'kiara_public';

ALTER TABLE integration_credentials
  DROP CONSTRAINT IF EXISTS integration_credentials_provider_check;
ALTER TABLE integration_credentials
  ADD CONSTRAINT integration_credentials_provider_check
  CHECK (provider IN ('google', 'instagram', 'instagram_session', 'hermes', 'mailerfind')) NOT VALID;
ALTER TABLE integration_credentials
  VALIDATE CONSTRAINT integration_credentials_provider_check;

ALTER TABLE competition_analyses
  DROP CONSTRAINT IF EXISTS competition_analyses_provider_check;
ALTER TABLE competition_analyses
  ADD CONSTRAINT competition_analyses_provider_check
  CHECK (provider IN ('mailerfind', 'kiara_instagram')) NOT VALID;
ALTER TABLE competition_analyses
  VALIDATE CONSTRAINT competition_analyses_provider_check;

COMMIT;
