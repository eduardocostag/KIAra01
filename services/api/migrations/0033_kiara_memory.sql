BEGIN;
-- Kiara's memory of the workspace: short durable facts the owner shared in the chat (who they are, how the
-- business works, how they like answers). Shown on "Minha empresa", where the owner can remove any of them.
-- Facts about each WhatsApp contact live with the contact (consumers.attributes.sdr.memory), not here.
CREATE TABLE kiara_memories (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  fact text NOT NULL CHECK (length(btrim(fact)) BETWEEN 3 AND 300),
  source text NOT NULL DEFAULT 'chat' CHECK (source IN ('chat', 'manual')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id)
);
CREATE UNIQUE INDEX kiara_memories_fact_idx ON kiara_memories (organization_id, lower(btrim(fact)));
CREATE INDEX kiara_memories_updated_idx ON kiara_memories (organization_id, updated_at DESC);

ALTER TABLE kiara_memories ENABLE ROW LEVEL SECURITY;
ALTER TABLE kiara_memories FORCE ROW LEVEL SECURITY;
CREATE POLICY kiara_memories_tenant_policy ON kiara_memories FOR ALL
  USING (organization_id = kiara.current_organization_id())
  WITH CHECK (organization_id = kiara.current_organization_id());

DO $server_access$
DECLARE server_role text;
BEGIN
  FOREACH server_role IN ARRAY ARRAY['kiara_app', 'kiara_runtime'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = server_role) THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON kiara_memories TO %I', server_role);
    END IF;
  END LOOP;
END
$server_access$;
COMMIT;
