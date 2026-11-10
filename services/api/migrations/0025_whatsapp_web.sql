BEGIN;
CREATE TABLE whatsapp_web_config (
 organization_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE CASCADE,
 config jsonb NOT NULL CHECK(jsonb_typeof(config)='object'),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE whatsapp_web_events (
 organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
 id text NOT NULL CHECK(length(id) BETWEEN 1 AND 160),
 phone text NOT NULL DEFAULT '',
 kind text NOT NULL CHECK(kind IN ('inbound','outbound','heartbeat','error','unknown','handoff','followup','cancelled')),
 text text NOT NULL DEFAULT '' CHECK(length(text)<=10000),
 occurred_at timestamptz NOT NULL,
 status text NOT NULL DEFAULT '' CHECK(length(status)<=80),
 received_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(organization_id,id)
);
CREATE INDEX whatsapp_web_events_history_idx ON whatsapp_web_events(organization_id,received_at DESC);
CREATE INDEX whatsapp_web_events_heartbeat_idx ON whatsapp_web_events(organization_id,received_at DESC) WHERE kind='heartbeat';
DO $rls$
DECLARE table_name text;
BEGIN
 FOREACH table_name IN ARRAY ARRAY['whatsapp_web_config','whatsapp_web_events'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',table_name);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',table_name);
  EXECUTE format('CREATE POLICY %I ON %I FOR ALL USING (organization_id=kiara.current_organization_id()) WITH CHECK (organization_id=kiara.current_organization_id())',table_name||'_tenant_policy',table_name);
 END LOOP;
END
$rls$;
COMMIT;
