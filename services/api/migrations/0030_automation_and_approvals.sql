BEGIN;

-- Kiara Automation: flows saved per organization and executed by the server.
CREATE TABLE automation_flows (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  client_key text NOT NULL CHECK (client_key ~ '^[A-Za-z0-9_-]{1,80}$'),
  name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 120),
  definition jsonb NOT NULL CHECK (jsonb_typeof(definition) = 'object'),
  enabled boolean NOT NULL DEFAULT false,
  lead_cursor timestamptz,
  version integer NOT NULL DEFAULT 1 CHECK (version > 0),
  created_by uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  UNIQUE (organization_id, client_key)
);
CREATE INDEX automation_flows_updated_idx ON automation_flows (organization_id, updated_at DESC);

CREATE TABLE automation_runs (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  flow_id uuid NOT NULL,
  trigger text NOT NULL CHECK (trigger IN ('manual', 'schedule', 'lead')),
  status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'running', 'waiting', 'done', 'partial', 'failed')),
  input text NOT NULL DEFAULT '' CHECK (length(input) <= 8000),
  steps jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(steps) = 'array'),
  pending jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(pending) = 'array'),
  error text CHECK (error IS NULL OR length(error) <= 500),
  requested_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  started_at timestamptz,
  finished_at timestamptz,
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, flow_id) REFERENCES automation_flows (organization_id, id) ON DELETE CASCADE
);
CREATE INDEX automation_runs_flow_idx ON automation_runs (organization_id, flow_id, created_at DESC);

-- Approval center: every external action (message, post, ad, agenda...) waits for a person.
CREATE TABLE action_requests (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  source text NOT NULL DEFAULT 'automation' CHECK (source IN ('automation', 'kiara')),
  flow_id uuid,
  run_id uuid,
  node_id text CHECK (node_id IS NULL OR length(node_id) <= 80),
  kind text NOT NULL CHECK (kind ~ '^[a-z]+(\.[a-z]+)?$' AND length(kind) <= 40),
  title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload) = 'object'),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'done', 'failed')),
  note text CHECK (note IS NULL OR length(note) <= 500),
  version integer NOT NULL DEFAULT 1 CHECK (version > 0),
  decided_by uuid,
  decided_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, flow_id) REFERENCES automation_flows (organization_id, id) ON DELETE SET NULL (flow_id),
  CHECK (status = 'pending' OR decided_at IS NOT NULL)
);
CREATE INDEX action_requests_status_idx ON action_requests (organization_id, status, created_at DESC);

DO $rls$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['automation_flows', 'automation_runs', 'action_requests']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
    EXECUTE format('CREATE POLICY %I ON %I FOR ALL USING (organization_id = kiara.current_organization_id()) WITH CHECK (organization_id = kiara.current_organization_id())', table_name || '_tenant_policy', table_name);
  END LOOP;
END
$rls$;

-- Worker indexes span tenants (like hunter_work_queue) and are never exposed to browser roles.
CREATE TABLE automation_triggers (
  organization_id uuid NOT NULL,
  flow_id uuid NOT NULL,
  kind text NOT NULL CHECK (kind IN ('schedule', 'lead')),
  next_at timestamptz NOT NULL,
  lease_owner text,
  lease_expires_at timestamptz,
  PRIMARY KEY (organization_id, flow_id, kind),
  FOREIGN KEY (organization_id, flow_id) REFERENCES automation_flows (organization_id, id) ON DELETE CASCADE
);
CREATE INDEX automation_triggers_due_idx ON automation_triggers (next_at);

CREATE TABLE automation_work_queue (
  organization_id uuid NOT NULL,
  run_id uuid NOT NULL,
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_owner text,
  lease_expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, run_id),
  FOREIGN KEY (organization_id, run_id) REFERENCES automation_runs (organization_id, id) ON DELETE CASCADE
);
CREATE INDEX automation_work_queue_due_idx ON automation_work_queue (available_at);

ALTER TABLE automation_triggers ENABLE ROW LEVEL SECURITY;
ALTER TABLE automation_work_queue ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON automation_triggers, automation_work_queue FROM PUBLIC, anon, authenticated;

DO $worker_access$
DECLARE worker_role text;
BEGIN
  FOREACH worker_role IN ARRAY ARRAY['kiara_app', 'kiara_runtime'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = worker_role) THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON automation_flows, automation_runs, action_requests, automation_triggers, automation_work_queue TO %I', worker_role);
      EXECUTE format('CREATE POLICY %I ON automation_triggers FOR ALL TO %I USING (true) WITH CHECK (true)', 'automation_triggers_' || worker_role, worker_role);
      EXECUTE format('CREATE POLICY %I ON automation_work_queue FOR ALL TO %I USING (true) WITH CHECK (true)', 'automation_queue_' || worker_role, worker_role);
    END IF;
  END LOOP;
END
$worker_access$;

COMMIT;
