BEGIN;

CREATE TABLE sales_profiles (
  organization_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE RESTRICT,
  business_name text NOT NULL DEFAULT '' CHECK (length(business_name) <= 160),
  sender_name text NOT NULL DEFAULT '' CHECK (length(sender_name) <= 160),
  offer text NOT NULL DEFAULT '' CHECK (length(offer) <= 4000),
  tone text NOT NULL DEFAULT 'consultivo, acolhedor e objetivo' CHECK (length(tone) <= 500),
  follow_up_hours integer NOT NULL DEFAULT 48 CHECK (follow_up_hours BETWEEN 1 AND 720),
  contact_start time NOT NULL DEFAULT '09:00',
  contact_end time NOT NULL DEFAULT '18:00',
  templates jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(templates) = 'object'),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE outreach_activities (
  organization_id uuid NOT NULL,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  pipeline_entry_id uuid NOT NULL,
  actor_user_id uuid NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
  channel text NOT NULL CHECK (channel IN ('whatsapp', 'instagram', 'phone')),
  status text NOT NULL CHECK (status IN ('opened', 'sent', 'replied', 'no_response')),
  body text NOT NULL DEFAULT '' CHECK (length(body) <= 20000),
  next_follow_up_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id),
  FOREIGN KEY (organization_id, pipeline_entry_id)
    REFERENCES pipeline_entries (organization_id, id) ON DELETE RESTRICT
);
CREATE INDEX outreach_activities_entry_idx
  ON outreach_activities (organization_id, pipeline_entry_id, created_at DESC, id);
CREATE INDEX outreach_activities_follow_up_idx
  ON outreach_activities (organization_id, next_follow_up_at)
  WHERE next_follow_up_at IS NOT NULL AND status = 'sent';

ALTER TABLE sales_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_profiles FORCE ROW LEVEL SECURITY;
CREATE POLICY sales_profiles_tenant_policy ON sales_profiles
  FOR ALL USING (organization_id = kiara.current_organization_id())
  WITH CHECK (organization_id = kiara.current_organization_id());

ALTER TABLE outreach_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE outreach_activities FORCE ROW LEVEL SECURITY;
CREATE POLICY outreach_activities_tenant_policy ON outreach_activities
  FOR ALL USING (organization_id = kiara.current_organization_id())
  WITH CHECK (organization_id = kiara.current_organization_id());

COMMIT;
