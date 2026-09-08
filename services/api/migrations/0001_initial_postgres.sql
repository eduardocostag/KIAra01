BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS kiara;

CREATE OR REPLACE FUNCTION kiara.current_organization_id()
RETURNS uuid
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
  SELECT NULLIF(current_setting('app.organization_id', true), '')::uuid
$$;

CREATE OR REPLACE FUNCTION kiara.current_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
PARALLEL SAFE
AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;

CREATE TABLE organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
  name text NOT NULL CHECK (length(btrim(name)) BETWEEN 1 AND 160),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'closed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identity_provider text NOT NULL CHECK (length(identity_provider) BETWEEN 1 AND 80),
  external_subject text NOT NULL CHECK (length(external_subject) BETWEEN 1 AND 255),
  email text,
  display_name text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (identity_provider, external_subject)
);

CREATE TABLE memberships (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  role text NOT NULL CHECK (role IN ('owner', 'admin', 'operator', 'viewer')),
  status text NOT NULL DEFAULT 'active' CHECK (status IN ('invited', 'active', 'revoked')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  UNIQUE (organization_id, user_id)
);
CREATE INDEX memberships_user_idx ON memberships (user_id, organization_id);

CREATE TABLE consumers (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  display_name text,
  instagram_username text,
  consent_status text NOT NULL DEFAULT 'unknown'
    CHECK (consent_status IN ('unknown', 'observed_inbound', 'granted', 'revoked', 'opted_out')),
  lifecycle_status text NOT NULL DEFAULT 'active'
    CHECK (lifecycle_status IN ('active', 'blocked', 'deleted')),
  attributes jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(attributes) = 'object'),
  version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  UNIQUE (organization_id, instagram_username)
);
CREATE INDEX consumers_updated_idx ON consumers (organization_id, updated_at DESC, id);

CREATE TABLE conversation_threads (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  consumer_id uuid NOT NULL,
  channel text NOT NULL CHECK (channel IN ('instagram')),
  provider_thread_id text NOT NULL,
  status text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'closed', 'blocked')),
  last_message_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, consumer_id)
    REFERENCES consumers (organization_id, id) ON DELETE RESTRICT,
  UNIQUE (organization_id, channel, provider_thread_id)
);
CREATE INDEX conversation_threads_inbox_idx
  ON conversation_threads (organization_id, status, last_message_at DESC, id);

CREATE TABLE messages (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  thread_id uuid NOT NULL,
  direction text NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  provider_message_id text,
  body text NOT NULL CHECK (length(body) <= 20000),
  sent_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, thread_id)
    REFERENCES conversation_threads (organization_id, id) ON DELETE RESTRICT
);
CREATE INDEX messages_thread_idx ON messages (organization_id, thread_id, sent_at, id);
CREATE UNIQUE INDEX messages_provider_id_unique_idx
  ON messages (organization_id, provider_message_id)
  WHERE provider_message_id IS NOT NULL;

CREATE TABLE message_drafts (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  thread_id uuid NOT NULL,
  body text NOT NULL CHECK (length(btrim(body)) BETWEEN 1 AND 20000),
  content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
  version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
  status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft', 'approved', 'queued', 'sent', 'rejected', 'expired', 'invalidated')),
  created_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, thread_id)
    REFERENCES conversation_threads (organization_id, id) ON DELETE RESTRICT
);
CREATE INDEX message_drafts_thread_idx
  ON message_drafts (organization_id, thread_id, updated_at DESC, id);

CREATE TABLE approvals (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  draft_id uuid NOT NULL,
  draft_version bigint NOT NULL CHECK (draft_version > 0),
  content_hash text NOT NULL CHECK (content_hash ~ '^[0-9a-f]{64}$'),
  decision text NOT NULL CHECK (decision IN ('approved', 'rejected', 'revoked')),
  decided_by uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  decided_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz,
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, draft_id)
    REFERENCES message_drafts (organization_id, id) ON DELETE RESTRICT,
  UNIQUE (organization_id, draft_id, draft_version, decision),
  CHECK (expires_at IS NULL OR expires_at > decided_at)
);
CREATE INDEX approvals_draft_idx ON approvals (organization_id, draft_id, decided_at DESC);

CREATE TABLE pipeline_entries (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  consumer_id uuid NOT NULL,
  stage text NOT NULL DEFAULT 'new'
    CHECK (stage IN ('new', 'qualified', 'contacted', 'opportunity', 'won', 'lost')),
  owner_membership_id uuid,
  next_action text,
  next_action_at timestamptz,
  version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, consumer_id)
    REFERENCES consumers (organization_id, id) ON DELETE RESTRICT,
  FOREIGN KEY (organization_id, owner_membership_id)
    REFERENCES memberships (organization_id, id) ON DELETE RESTRICT,
  UNIQUE (organization_id, consumer_id)
);
CREATE INDEX pipeline_stage_idx
  ON pipeline_entries (organization_id, stage, updated_at DESC, id);

CREATE TABLE pipeline_stage_events (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  pipeline_entry_id uuid NOT NULL,
  from_stage text,
  to_stage text NOT NULL,
  actor_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, pipeline_entry_id)
    REFERENCES pipeline_entries (organization_id, id) ON DELETE RESTRICT
);
CREATE INDEX pipeline_stage_events_entry_idx
  ON pipeline_stage_events (organization_id, pipeline_entry_id, created_at DESC, id);

CREATE TABLE qualifications (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  thread_id uuid NOT NULL,
  score integer NOT NULL CHECK (score BETWEEN 0 AND 100),
  temperature text NOT NULL CHECK (temperature IN ('cold', 'warm', 'hot')),
  recommendation text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, thread_id)
    REFERENCES conversation_threads (organization_id, id) ON DELETE CASCADE
);
CREATE INDEX qualifications_thread_idx
  ON qualifications (organization_id, thread_id, created_at DESC, id);

CREATE TABLE jobs (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  kind text NOT NULL CHECK (length(kind) BETWEEN 1 AND 100),
  state text NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'needs_review')),
  payload jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(payload) = 'object'),
  idempotency_key text NOT NULL,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts BETWEEN 1 AND 100),
  available_at timestamptz NOT NULL DEFAULT now(),
  lease_owner text,
  lease_expires_at timestamptz,
  last_error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  UNIQUE (organization_id, idempotency_key),
  CHECK ((lease_owner IS NULL) = (lease_expires_at IS NULL))
);
CREATE INDEX jobs_claim_idx
  ON jobs (organization_id, state, available_at, created_at)
  WHERE state IN ('queued', 'running');

CREATE TABLE outbox_events (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  aggregate_type text NOT NULL,
  aggregate_id uuid NOT NULL,
  event_type text NOT NULL,
  payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
  occurred_at timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz,
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error_code text,
  PRIMARY KEY (organization_id, id)
);
CREATE INDEX outbox_pending_idx
  ON outbox_events (organization_id, occurred_at, id) WHERE published_at IS NULL;

CREATE TABLE audit_events (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  actor_user_id uuid REFERENCES users(id) ON DELETE RESTRICT,
  action text NOT NULL CHECK (length(action) BETWEEN 1 AND 160),
  resource_type text NOT NULL,
  resource_id uuid,
  correlation_id text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
  occurred_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id)
);
CREATE INDEX audit_events_timeline_idx
  ON audit_events (organization_id, occurred_at DESC, id);
CREATE INDEX audit_events_correlation_idx
  ON audit_events (organization_id, correlation_id);

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY organizations_tenant_policy ON organizations
  FOR ALL USING (id = kiara.current_organization_id())
  WITH CHECK (id = kiara.current_organization_id());

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
CREATE POLICY users_current_identity_policy ON users
  FOR SELECT USING (
    id = kiara.current_user_id()
    AND EXISTS (
      SELECT 1 FROM memberships m
      WHERE m.organization_id = kiara.current_organization_id()
        AND m.user_id = users.id AND m.status = 'active'
    )
  );

DO $rls$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'memberships', 'consumers', 'conversation_threads', 'messages',
    'message_drafts', 'approvals', 'pipeline_entries', 'pipeline_stage_events', 'qualifications',
    'jobs', 'outbox_events', 'audit_events'
  ]
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
    EXECUTE format(
      'CREATE POLICY %I ON %I FOR ALL USING (organization_id = kiara.current_organization_id()) WITH CHECK (organization_id = kiara.current_organization_id())',
      table_name || '_tenant_policy', table_name
    );
  END LOOP;
END
$rls$;

COMMIT;
