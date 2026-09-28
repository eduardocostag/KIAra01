BEGIN;

ALTER TABLE social_channels DROP CONSTRAINT IF EXISTS social_channels_provider_check;
ALTER TABLE social_channels ADD CONSTRAINT social_channels_provider_check
  CHECK (provider IN ('instagram','facebook','threads','linkedin','tiktok','youtube','generic','simulated')) NOT VALID;
ALTER TABLE social_channels VALIDATE CONSTRAINT social_channels_provider_check;

ALTER TABLE social_media DROP CONSTRAINT IF EXISTS social_media_storage_kind_check;
ALTER TABLE social_media ADD CONSTRAINT social_media_storage_kind_check
  CHECK (storage_kind IN ('local','metadata_only')) NOT VALID;
ALTER TABLE social_media VALIDATE CONSTRAINT social_media_storage_kind_check;
ALTER TABLE social_media ADD COLUMN IF NOT EXISTS storage_key text;
ALTER TABLE social_media ADD CONSTRAINT social_media_storage_key_safe
  CHECK (storage_key IS NULL OR storage_key ~ '^[a-f0-9/-]{10,300}$') NOT VALID;
ALTER TABLE social_media VALIDATE CONSTRAINT social_media_storage_key_safe;

ALTER TABLE social_posts DROP CONSTRAINT IF EXISTS social_posts_status_check;
ALTER TABLE social_posts ADD CONSTRAINT social_posts_status_check
  CHECK (status IN ('draft','pending_approval','approved','scheduled','ready_to_publish','publishing','simulated','published','failed','cancelled')) NOT VALID;
ALTER TABLE social_posts VALIDATE CONSTRAINT social_posts_status_check;

ALTER TABLE social_post_targets DROP CONSTRAINT IF EXISTS social_post_targets_status_check;
ALTER TABLE social_post_targets ADD CONSTRAINT social_post_targets_status_check
  CHECK (status IN ('draft','approved','scheduled','ready_to_publish','simulated','publishing','published','failed','cancelled')) NOT VALID;
ALTER TABLE social_post_targets VALIDATE CONSTRAINT social_post_targets_status_check;

COMMIT;
