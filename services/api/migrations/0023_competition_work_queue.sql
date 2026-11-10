BEGIN;

-- Contains identifiers and scheduling metadata only; tenant payloads remain
-- protected by RLS in competition_analysis_jobs.
CREATE TABLE competition_analysis_work_queue (
  organization_id uuid NOT NULL,
  job_id uuid NOT NULL,
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_owner text,
  lease_expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, job_id),
  FOREIGN KEY (organization_id, job_id)
    REFERENCES competition_analysis_jobs (organization_id, id) ON DELETE CASCADE,
  CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL))
);

CREATE INDEX competition_analysis_work_queue_claim_idx
  ON competition_analysis_work_queue (available_at, created_at);

COMMIT;
