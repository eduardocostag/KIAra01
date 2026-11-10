BEGIN;
ALTER TABLE conversation_threads DROP CONSTRAINT IF EXISTS conversation_threads_channel_check;
ALTER TABLE conversation_threads ADD CONSTRAINT conversation_threads_channel_check
 CHECK (channel IN ('instagram','whatsapp','chatwoot','email','facebook')) NOT VALID;
ALTER TABLE conversation_threads VALIDATE CONSTRAINT conversation_threads_channel_check;
ALTER TABLE conversation_threads ADD COLUMN IF NOT EXISTS automation_enabled boolean NOT NULL DEFAULT false;
ALTER TABLE conversation_threads ADD COLUMN IF NOT EXISTS handoff boolean NOT NULL DEFAULT false;
ALTER TABLE conversation_threads ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE conversation_threads ADD COLUMN IF NOT EXISTS last_read_at timestamptz;
ALTER TABLE qualifications ADD COLUMN IF NOT EXISTS reasons jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE qualifications ADD COLUMN IF NOT EXISTS confidence double precision NOT NULL DEFAULT 0;
CREATE TABLE IF NOT EXISTS commercial_outbox (
 organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 id uuid NOT NULL DEFAULT gen_random_uuid(), thread_id uuid NOT NULL,
 phone text NOT NULL, body text NOT NULL CHECK(length(btrim(body)) BETWEEN 1 AND 4000),
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','sending','sent','unknown','failed','cancelled')),
 request_key text NOT NULL CHECK(length(request_key) BETWEEN 1 AND 160),
 provider_message_id text, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(), lease_until timestamptz,
 PRIMARY KEY(organization_id,id), UNIQUE(organization_id,request_key),
 FOREIGN KEY(organization_id,thread_id) REFERENCES conversation_threads(organization_id,id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS commercial_outbox_queue_idx ON commercial_outbox(organization_id,created_at)
 WHERE status='queued';
ALTER TABLE commercial_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE commercial_outbox FORCE ROW LEVEL SECURITY;
CREATE POLICY commercial_outbox_tenant_policy ON commercial_outbox FOR ALL
 USING(organization_id=kiara.current_organization_id()) WITH CHECK(organization_id=kiara.current_organization_id());
DO $grants$ BEGIN
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='kiara_app') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON commercial_outbox TO kiara_app;
 END IF;
 IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='kiara_runtime') THEN
  GRANT SELECT,INSERT,UPDATE,DELETE ON commercial_outbox TO kiara_runtime;
 END IF;
END $grants$;
COMMIT;
