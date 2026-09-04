-- ====================================================================
-- SYSTEM SCHEMA: COMIC BOOK METRIC TRACKING PIPELINE (V2 COMPLETE)
-- TARGET DATABASE: PostgreSQL (Supabase) / SQLite
-- ====================================================================

-- --------------------------------------------------------------------
-- TABLE 1A: MASTER CATALOG TRUNK
-- --------------------------------------------------------------------
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
    
    CONSTRAINT unique_series_release UNIQUE (series_id, sort_order)
);

CREATE INDEX IF NOT EXISTS idx_master_street_date ON issue_master(street_date);
CREATE INDEX IF NOT EXISTS idx_master_publisher ON issue_master(publisher);

-- --------------------------------------------------------------------
-- TABLE 1B: VARIANT / COVER REGISTRY (Source of Truth per Cover)
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issue_variants (
    variant_id          SERIAL PRIMARY KEY,
    master_issue_id     INTEGER NOT NULL,     
    locg_issue_id       INTEGER UNIQUE NOT NULL, -- Platform-specific scraping anchor
    variant_type        VARCHAR(50) NOT NULL,    -- COVER_A, VARIANT, RATIO, etc.
    cover_info          TEXT,                    -- Artist names, store retailer labels
    retail_price        NUMERIC(6, 2),           
    image_url           TEXT,                    
    current_pull_count  INTEGER NOT NULL DEFAULT 0,
    days_to_street_date INTEGER NOT NULL,    
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_master_issue 
        FOREIGN KEY (master_issue_id) 
        REFERENCES issue_master(master_issue_id) 
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_variants_master_id ON issue_variants(master_issue_id);
CREATE INDEX IF NOT EXISTS idx_variants_pull_velocity ON issue_variants(current_pull_count DESC);

-- --------------------------------------------------------------------
-- TABLE 2: TIME-SERIES SNAPSHOT LEDGER (Append-Only Historical Log)
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issue_snapshots (
    snapshot_id         BIGSERIAL PRIMARY KEY,
    locg_issue_id       INTEGER NOT NULL,
    pull_count          INTEGER NOT NULL,
    days_to_street_date INTEGER NOT NULL,
    recorded_at         TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_snapshot_variant 
        FOREIGN KEY (locg_issue_id) 
        REFERENCES issue_variants(locg_issue_id) 
        ON DELETE CASCADE
);

-- Crucial index: powers fast ORDER BY recorded_at DESC for 3D delta & acceleration queries
CREATE INDEX IF NOT EXISTS idx_snapshots_lookup 
    ON issue_snapshots (locg_issue_id, recorded_at DESC);

-- --------------------------------------------------------------------
-- TABLE 3: DERIVED READ MODEL (Disposable / Real-Time Flagged State)
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issue_velocity_flags (
    locg_issue_id              INTEGER PRIMARY KEY,
    evaluation_mode            VARCHAR(100) NOT NULL, -- e.g., EARLY_ISSUE_ONE_ACCELERATION
    current_pull_count         INTEGER NOT NULL,
    net_growth_since_discovery INTEGER NOT NULL DEFAULT 0,
    delta_3d                   INTEGER NOT NULL DEFAULT 0,
    acceleration_3d            INTEGER NOT NULL DEFAULT 0,
    is_early_breakout          BOOLEAN NOT NULL DEFAULT FALSE,
    peak_spike_grade           VARCHAR(50) NOT NULL DEFAULT 'UNFLAGGED',
    velocity_state             VARCHAR(50) NOT NULL DEFAULT 'STABLE', -- HOT_ACCELERATING, COOLING, STABLE
    last_evaluated_at          TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_flags_variant 
        FOREIGN KEY (locg_issue_id) 
        REFERENCES issue_variants(locg_issue_id) 
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_velocity_state ON issue_velocity_flags(velocity_state);
CREATE INDEX IF NOT EXISTS idx_early_breakout ON issue_velocity_flags(is_early_breakout);