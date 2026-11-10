BEGIN;

-- Worker indexes deliberately span tenants, but are never exposed to browser roles.
ALTER TABLE hunter_work_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE competition_analysis_work_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE kiara_schema_migrations ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON hunter_work_queue,competition_analysis_work_queue,kiara_schema_migrations
 FROM PUBLIC,anon,authenticated;

DO $worker_access$
DECLARE worker_role text;
BEGIN
 FOREACH worker_role IN ARRAY ARRAY['kiara_app','kiara_runtime'] LOOP
  IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname=worker_role) THEN
   EXECUTE format('GRANT SELECT,INSERT,UPDATE,DELETE ON competition_analysis_jobs,competition_analysis_work_queue,hunter_work_queue TO %I',worker_role);
   EXECUTE format('CREATE POLICY %I ON hunter_work_queue FOR ALL TO %I USING(true) WITH CHECK(true)',
                  'hunter_queue_'||worker_role,worker_role);
   EXECUTE format('CREATE POLICY %I ON competition_analysis_work_queue FOR ALL TO %I USING(true) WITH CHECK(true)',
                  'competition_queue_'||worker_role,worker_role);
  END IF;
 END LOOP;
END $worker_access$;

ALTER FUNCTION kiara.current_organization_id() SET search_path=pg_catalog,kiara;
ALTER FUNCTION kiara.current_user_id() SET search_path=pg_catalog,kiara;

COMMIT;
