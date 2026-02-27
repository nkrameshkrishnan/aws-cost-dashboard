-- Migration: Add webhook_type column to teams_webhooks table
-- Date: 2026-02-10
-- Description: Adds support for both Microsoft Teams and Power Automate webhooks

-- Add webhook_type column with default value 'teams'
ALTER TABLE teams_webhooks
ADD COLUMN IF NOT EXISTS webhook_type VARCHAR(50) DEFAULT 'teams' NOT NULL;

-- Optional: Add a check constraint to ensure only valid types are used
-- ALTER TABLE teams_webhooks
-- ADD CONSTRAINT teams_webhooks_webhook_type_check
-- CHECK (webhook_type IN ('teams', 'power_automate'));

-- Update any existing rows to have 'teams' as webhook_type (already done by DEFAULT)
UPDATE teams_webhooks SET webhook_type = 'teams' WHERE webhook_type IS NULL;
