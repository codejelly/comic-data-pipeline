## Core Architecture Baseline

This PR establishes the foundational backend engine, data models, scraper modules, and testing suite.

### Included Modules
* **Fetcher (`src/fetch/`)**: `cached_scraper.py` and `html_fetcher.py` for DOM rendering and local caching.
* **Parser & Classifier (`src/parse/`)**: `comic_parser.py` and multi-factor `classifier.py` handling ratio incentives, annuals, and open variants.
* **Data Layer (`src/persistence/`)**: Supabase/PostgreSQL connection engine and JSON logging handlers.
* **Pipelines & Runners (`src/pipelines/`)**: Universal batch ingestion and harvest execution entry points.
* **Test Harness (`tests/`)**: Fixtures and classifier test matrices verifying DOM extraction.

### Verification
- [x] All Pytest execution suites passing (`pytest tests/`)
- [x] Confirmed zero dead code or unhandled exception returns in classifier logic
- [x] Verified local disk caching to `data/cache/`
