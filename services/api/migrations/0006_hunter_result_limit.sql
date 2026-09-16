BEGIN;

ALTER TABLE hunter_searches
  DROP CONSTRAINT hunter_searches_result_limit_check,
  ADD CONSTRAINT hunter_searches_result_limit_check CHECK (result_limit BETWEEN 1 AND 100);

COMMIT;
