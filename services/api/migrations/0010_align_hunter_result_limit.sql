BEGIN;

ALTER TABLE hunter_searches
  DROP CONSTRAINT IF EXISTS hunter_searches_result_limit_check;

ALTER TABLE hunter_searches
  ADD CONSTRAINT hunter_searches_result_limit_check
  CHECK (result_limit BETWEEN 1 AND 100) NOT VALID;

ALTER TABLE hunter_searches
  VALIDATE CONSTRAINT hunter_searches_result_limit_check;

COMMIT;
