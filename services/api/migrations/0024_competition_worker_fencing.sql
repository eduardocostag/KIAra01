BEGIN;

ALTER TABLE competition_analysis_jobs
  ADD COLUMN lease_owner text;

ALTER TABLE competition_analysis_jobs
  ADD CONSTRAINT competition_analysis_jobs_lease_owner_check
  CHECK ((lease_expires_at IS NULL) = (lease_owner IS NULL));

COMMIT;
