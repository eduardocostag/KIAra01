BEGIN;

-- Global control-plane index for workers. Customer payloads remain in the
-- tenant-scoped jobs table protected by row-level security.
CREATE TABLE hunter_work_queue (
  organization_id uuid NOT NULL,
  search_id uuid NOT NULL,
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_owner text,
  lease_expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, search_id),
  FOREIGN KEY (organization_id, search_id)
    REFERENCES hunter_searches (organization_id, id) ON DELETE CASCADE,
  CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL))
);
CREATE INDEX hunter_work_queue_claim_idx
  ON hunter_work_queue (available_at, created_at);

COMMIT;
