-- ====================================================================
-- SYSTEM SCHEMA: COMIC BOOK METRIC TRACKING PIPELINE (UPDATED V2)
-- TARGET DATABASE: PostgreSQL (Supabase) / SQLite
-- ====================================================================

CREATE TABLE IF NOT EXISTS issue_master (
    master_issue_id    SERIAL PRIMARY KEY,
    series_id          INTEGER NOT NULL,
    issue_number       VARCHAR(100) NOT NULL,
    sort_order         NUMERIC(8, 2) NOT NULL,
    type               VARCHAR(40) NOT NULL DEFAULT 'MAIN_RELEASE',
    status             VARCHAR(30) NOT NULL DEFAULT 'UPCOMING',
    street_date        DATE NOT NULL,
    publisher          VARCHAR(100) NOT NULL DEFAULT 'Unknown',
    created_at         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevents duplicate master entries for the same issue order slot within a series
    CONSTRAINT unique_series_release UNIQUE (series_id, sort_order)
);

-- Indexing for rapid frontend schedule/publisher filtering
CREATE INDEX IF NOT EXISTS idx_master_street_date ON issue_master(street_date);
CREATE INDEX IF NOT EXISTS idx_master_publisher ON issue_master(publisher);

CREATE TABLE IF NOT EXISTS issue_variants (
    variant_id          SERIAL PRIMARY KEY,
    master_issue_id     INTEGER NOT NULL,     
    locg_issue_id       INTEGER UNIQUE NOT NULL, -- Platform-specific scraping anchor
    variant_type        VARCHAR(50) NOT NULL,    -- Evaluated via dynamic_issue_classifier
    cover_info          TEXT,                    -- Holds verbose text (e.g., Artists, Store Names)
    retail_price        NUMERIC(6, 2),           -- Float MSRP (Allows NULL for missing data safety)
    image_url           TEXT,                    -- AWS hosted cover artwork thumbnail path
    current_pull_count  INTEGER NOT NULL DEFAULT 0,
    days_to_street_date INTEGER NOT NULL,    
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Enforces cascading safety: removing a master trunk issue automatically purges its variant branches
    CONSTRAINT fk_master_issue 
        FOREIGN KEY (master_issue_id) 
        REFERENCES issue_master(master_issue_id) 
        ON DELETE CASCADE
);

-- Indexing for frontend analytics dashboards and query routing
CREATE INDEX IF NOT EXISTS idx_variants_master_id ON issue_variants(master_issue_id);
CREATE INDEX IF NOT EXISTS idx_variants_pull_velocity ON issue_variants(current_pull_count DESC);