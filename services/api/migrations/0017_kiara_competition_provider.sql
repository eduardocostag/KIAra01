BEGIN;

ALTER TABLE competition_analyses
  DROP CONSTRAINT IF EXISTS competition_analyses_provider_check;
ALTER TABLE competition_analyses
  ADD CONSTRAINT competition_analyses_provider_check
  CHECK (provider IN ('mailerfind', 'kiara_public'));

ALTER TABLE competition_prospects
  ADD COLUMN IF NOT EXISTS profile_url text,
  ADD COLUMN IF NOT EXISTS whatsapp_url text;

COMMIT;
