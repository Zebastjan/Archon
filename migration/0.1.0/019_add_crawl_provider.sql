-- Migration 019: Add Crawl Provider Support
-- Adds support for multiple crawl providers (Tavily, Crawl4AI)
-- Tracks provider usage and provider-specific metadata

-- Add crawl provider tracking to sources
ALTER TABLE archon_sources
ADD COLUMN IF NOT EXISTS crawl_provider TEXT DEFAULT 'crawl4ai';

-- Index for filtering by provider
CREATE INDEX IF NOT EXISTS idx_archon_sources_crawl_provider
ON archon_sources(crawl_provider);

-- Add provider-specific metadata (separate from existing metadata JSONB)
-- This stores provider-specific data like credits_used, pages_crawled, etc.
ALTER TABLE archon_sources
ADD COLUMN IF NOT EXISTS provider_metadata JSONB DEFAULT '{}';

-- Index for querying provider metadata
CREATE INDEX IF NOT EXISTS idx_archon_sources_provider_metadata
ON archon_sources USING GIN(provider_metadata);

-- Add Tavily API key setting (encrypted)
INSERT INTO archon_settings (key, encrypted_value, is_encrypted, category, description)
VALUES (
    'TAVILY_API_KEY',
    NULL,
    true,
    'api_keys',
    'Tavily API key for web crawling. Get from: https://tavily.com/dashboard'
) ON CONFLICT (key) DO NOTHING;

-- Add default crawl provider setting
INSERT INTO archon_settings (key, value, is_encrypted, category, description)
VALUES (
    'DEFAULT_CRAWL_PROVIDER',
    'tavily',
    false,
    'crawling',
    'Default web crawl provider: tavily or crawl4ai'
) ON CONFLICT (key) DO NOTHING;

-- Add Tavily limits settings
INSERT INTO archon_settings (key, value, is_encrypted, category, description)
VALUES
    ('TAVILY_MAX_PAGES', '100', false, 'crawling', 'Maximum pages per Tavily crawl (Stage 1 conservative limit)'),
    ('TAVILY_MAX_DEPTH', '3', false, 'crawling', 'Maximum crawl depth for Tavily (1-3, clamped from 1-5 supported)')
ON CONFLICT (key) DO NOTHING;

-- Record migration
INSERT INTO archon_migrations (version, migration_name)
VALUES ('0.1.0', '019_add_crawl_provider')
ON CONFLICT (version, migration_name) DO NOTHING;
