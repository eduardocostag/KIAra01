BEGIN;
-- Configurar atendimento: niche, services and prices, hours, goal, handoff rules, tone and limits, filled in by the
-- client (kiara_api/service_setup.py). One JSON object per workspace, beside the sales profile it complements.
-- Covered by the existing sales_profiles grants and tenant policy (RLS).
ALTER TABLE sales_profiles ADD COLUMN IF NOT EXISTS service jsonb NOT NULL DEFAULT '{}'::jsonb;
DO $check$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'sales_profiles_service_object') THEN
    ALTER TABLE sales_profiles ADD CONSTRAINT sales_profiles_service_object
      CHECK (jsonb_typeof(service) = 'object' AND pg_column_size(service) <= 65536);
  END IF;
END
$check$;
COMMIT;
