BEGIN;

CREATE POLICY users_self_insert_policy ON users
  FOR INSERT WITH CHECK (id = kiara.current_user_id());
CREATE POLICY users_self_update_policy ON users
  FOR UPDATE USING (id = kiara.current_user_id())
  WITH CHECK (id = kiara.current_user_id());

COMMIT;
