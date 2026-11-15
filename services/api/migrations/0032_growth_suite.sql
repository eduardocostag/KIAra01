BEGIN;
-- Growth suite: results dashboard, first-contact queue, business knowledge, daily summary,
-- segment presets, plans with usage limits and teams. Additive only: no existing column changes.

-- Results: what a deal is worth (per lead, or the average from the sales profile).
ALTER TABLE pipeline_entries ADD COLUMN IF NOT EXISTS deal_value_cents bigint
  CHECK (deal_value_cents IS NULL OR deal_value_cents BETWEEN 0 AND 100000000000);
ALTER TABLE sales_profiles ADD COLUMN IF NOT EXISTS average_deal_cents bigint NOT NULL DEFAULT 0
  CHECK (average_deal_cents BETWEEN 0 AND 100000000000);
ALTER TABLE sales_profiles ADD COLUMN IF NOT EXISTS segment text NOT NULL DEFAULT ''
  CHECK (length(segment) <= 40);
-- Daily summary sent to the owner's own WhatsApp.
ALTER TABLE sales_profiles ADD COLUMN IF NOT EXISTS owner_whatsapp text NOT NULL DEFAULT ''
  CHECK (owner_whatsapp ~ '^(\+?[0-9]{10,15})?$');
ALTER TABLE sales_profiles ADD COLUMN IF NOT EXISTS daily_summary boolean NOT NULL DEFAULT false;
ALTER TABLE sales_profiles ADD COLUMN IF NOT EXISTS daily_summary_hour smallint NOT NULL DEFAULT 8
  CHECK (daily_summary_hour BETWEEN 5 AND 12);
ALTER TABLE sales_profiles ADD COLUMN IF NOT EXISTS daily_summary_sent_on date;
-- The SDR may answer people who write outside contact hours (24h attendance).
ALTER TABLE sales_profiles ADD COLUMN IF NOT EXISTS answer_anytime boolean NOT NULL DEFAULT false;

-- What Kiara knows about the client's business: catalog, prices, FAQ, site pages, policies.
CREATE TABLE business_knowledge (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  id uuid NOT NULL DEFAULT gen_random_uuid(),
  title text NOT NULL CHECK (length(btrim(title)) BETWEEN 1 AND 200),
  kind text NOT NULL CHECK (kind IN ('text', 'file', 'site')),
  content text NOT NULL CHECK (length(content) BETWEEN 1 AND 60000),
  source_url text CHECK (source_url IS NULL OR length(source_url) <= 1000),
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (organization_id, id)
);
CREATE INDEX business_knowledge_updated_idx ON business_knowledge (organization_id, updated_at DESC);

-- Plans and monthly usage (limits per plan are in code; billing provider is optional).
CREATE TABLE subscriptions (
  organization_id uuid PRIMARY KEY REFERENCES organizations(id) ON DELETE RESTRICT,
  plan text NOT NULL DEFAULT 'trial' CHECK (plan IN ('trial', 'starter', 'pro', 'business')),
  status text NOT NULL DEFAULT 'trialing' CHECK (status IN ('trialing', 'active', 'past_due', 'canceled')),
  trial_ends_at timestamptz NOT NULL DEFAULT (now() + interval '14 days'),
  current_period_end timestamptz,
  provider text CHECK (provider IS NULL OR length(provider) <= 40),
  provider_customer_id text CHECK (provider_customer_id IS NULL OR length(provider_customer_id) <= 200),
  provider_subscription_id text CHECK (provider_subscription_id IS NULL OR length(provider_subscription_id) <= 200),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE usage_counters (
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE RESTRICT,
  metric text NOT NULL CHECK (metric ~ '^[a-z_]{1,40}$'),
  period date NOT NULL,
  used integer NOT NULL DEFAULT 0 CHECK (used >= 0),
  PRIMARY KEY (organization_id, metric, period)
);

DO $rls$
DECLARE table_name text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['business_knowledge', 'subscriptions', 'usage_counters']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', table_name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', table_name);
    EXECUTE format('CREATE POLICY %I ON %I FOR ALL USING (organization_id = kiara.current_organization_id()) WITH CHECK (organization_id = kiara.current_organization_id())', table_name || '_tenant_policy', table_name);
  END LOOP;
END
$rls$;

-- Teams: a person signs in with their own account and works inside the owner's workspace.
-- Seats are looked up by the signed-in subject before the workspace is known, so (like the worker
-- queues) they span tenants and are reachable only by the API's server roles, never by browsers.
CREATE TABLE team_seats (
  subject text PRIMARY KEY CHECK (length(subject) BETWEEN 1 AND 200),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('admin', 'operator', 'viewer')),
  email text CHECK (email IS NULL OR length(email) <= 320),
  display_name text CHECK (display_name IS NULL OR length(display_name) <= 160),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX team_seats_organization_idx ON team_seats (organization_id, created_at);
CREATE TABLE team_invites (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email text NOT NULL CHECK (email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$' AND length(email) <= 320),
  role text NOT NULL CHECK (role IN ('admin', 'operator', 'viewer')),
  token_hash text NOT NULL UNIQUE CHECK (length(token_hash) = 64),
  invited_by text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  expires_at timestamptz NOT NULL DEFAULT (now() + interval '7 days'),
  accepted_at timestamptz,
  revoked_at timestamptz
);
CREATE INDEX team_invites_organization_idx ON team_invites (organization_id, created_at DESC);
ALTER TABLE team_seats ENABLE ROW LEVEL SECURITY;
ALTER TABLE team_invites ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON team_seats, team_invites FROM PUBLIC;
DO $browser_roles$
DECLARE browser_role text;
BEGIN
  FOREACH browser_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = browser_role) THEN
      EXECUTE format('REVOKE ALL ON team_seats, team_invites FROM %I', browser_role);
    END IF;
  END LOOP;
END
$browser_roles$;
DO $server_access$
DECLARE server_role text;
BEGIN
  FOREACH server_role IN ARRAY ARRAY['kiara_app', 'kiara_runtime'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = server_role) THEN
      EXECUTE format('GRANT SELECT, INSERT, UPDATE, DELETE ON business_knowledge, subscriptions, usage_counters, team_seats, team_invites TO %I', server_role);
      EXECUTE format('CREATE POLICY %I ON team_seats FOR ALL TO %I USING (true) WITH CHECK (true)', 'team_seats_' || server_role, server_role);
      EXECUTE format('CREATE POLICY %I ON team_invites FOR ALL TO %I USING (true) WITH CHECK (true)', 'team_invites_' || server_role, server_role);
    END IF;
  END LOOP;
END
$server_access$;
COMMIT;
