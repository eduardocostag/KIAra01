BEGIN;

ALTER TABLE hunter_results
  DROP CONSTRAINT IF EXISTS hunter_results_source_check;

ALTER TABLE hunter_results
  ADD CONSTRAINT hunter_results_source_check
  CHECK (source IN ('web', 'google_maps', 'instagram', 'facebook', 'linkedin')) NOT VALID;

ALTER TABLE hunter_results
  VALIDATE CONSTRAINT hunter_results_source_check;

COMMIT;
