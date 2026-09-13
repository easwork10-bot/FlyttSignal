# Database

PostgreSQL 17 with PostGIS is the shared persistence layer. Alembic owns schema initialization and changes. Geometry uses explicit SRIDs; application spatial geometry is WGS84/4326, while source-specific coordinates retain their declared reference system.

## Canonical initialization

`backend/migrations/versions/0001_baseline.py` (revision `0001_baseline`) installs `backend/migrations/baseline.sql`. This contains the current schema, constraints, indexes, enums, functions/triggers and necessary reference seeds—not collected live data.

Fresh databases run `alembic upgrade head`. Never stamp an empty database. Required reference data includes Uppsala, source definitions, providers and city/channel relationships. Historical fixture source definitions remain disabled; they are not seeded fictional listings. Installation created/updated timestamps use CURRENT_TIMESTAMP; historical source-verification dates retain their meaning.

The original local database was adopted by verified schema equivalence and an Alembic version-marker stamp, not schema replay. That one-time operation is complete. New installations do not need old migrations, cutover tooling or private backups. Future schema changes use ordinary revisions descending from the current head. The baseline deliberately refuses destructive downgrade.

## Data responsibilities

| Tables / model group | Responsibility and retention |
| --- | --- |
| cities, sources, source_cities, housing_providers, housing_provider_cities, provider_channels | Reference identities, source configuration and reviewed coverage. |
| source_runs, raw_items | Collection provenance and original evidence; mutable current raw items alone cannot reconstruct all past states. |
| rental_listings, rental_listing_revisions | Current source-owned listing projection and immutable source/history boundaries. |
| addresses, properties | Matched identity and spatial projections; preserve lineage before recomputation. |
| events, signal_evidence, signals | Observed event boundary, evidence edges and inferred projections. |
| listing_classifications, listing_measurements | Derived semantic tags and documented metrics with explicit missing inputs. |
| signal_outcomes | Later observed/confirmed evidence, independent of current inference. |
| validation_batches, signal_validations | Sample context and review judgments; reviews are not regenerable from source data. |
| score_definitions, score_runs, signal_dimension_evaluations, signal_feature_snapshots, score_activations | Explicit model experiments/evaluation and serving context; existing references remain valid. |
| pilot_signal_feedback, pilot_signal_activity | Real user judgments and recorded exposure context; preserve. |
| benchmark_observations, address_enrichments, address_register_unit_links, spatial_features, rental_developments | Isolated contextual facts with provenance; never synthetic signal evidence. |

See `backend/src/flyttsignal/db/models/` and the SQL baseline for exact column/constraint contracts.

## What must not be lost

Preserve irreplaceable source observations, unique provenance and actual user feedback/activity. Signals, scores, aggregates and other derived calculations should normally be rebuilt/replaced when all required inputs remain retained. Before adding preservation machinery, ask: **what information would actually be lost?**

No routine execution requires a new backup, snapshot or append-only framework. Use snapshots when reproducibility of an important model/version/experiment actually needs them. Existing evaluation records referenced by pilot/review context must not be deleted merely because scores are derived. Prove reconstructability and absence of required consumers before removing historical data.

## Revision and time contracts

Listing revisions are append-only, with a database trigger rejecting updates/deletes. Every revision preserves its own raw payload; later raw-item mutation cannot rewrite history. Identical observations do not create redundant content revisions. Relisting/removal transitions remain distinct.

Typed revision columns are canonical; normalized hashes verify their content. A reconstructed revision establishes only what was provable at its reconstruction boundary. Never backdate it to first_seen_at or claim direct source observation from reconstructed state.

Current reads use non-superseded evidence/signals. As-of reads select evidence valid at the requested time; later supersession cannot retroactively remove history. Historical timing cannot fall back to mutable listing state. Missing, unavailable, conflicting and not-applicable facts remain distinct.

Current feature capture accepts the current Stockholm calendar date; it is not a time machine for overwritten facts. Historical evaluation reads retained snapshots. Snapshot capture time is metadata, not a source observation. Outcomes such as removal/relisting/date change remain separate from the current signal inference.

## Runtime fields that remain

Some legacy signal enums, score columns, estimated date fields, revision/inference flags and compatibility projections still have database or code consumers. They remain in this schema-equivalent consolidation. Unresolved existing rental lineages are held by ingestion rather than silently rewritten. No new rental cutover is part of initialization.

Historical score tables are not automatically fed by current scoring. Current API prioritization uses activated dimensions. Removing old columns/types later requires an actual consumer/data audit, not a filename cleanup.

## Safe operations

Normal changes: tests → migration when needed → deploy → verify.
Do not delete the Compose volume to troubleshoot an upgrade. `docker compose down` retains it; `down -v` destroys it and is not a routine command.
Use backups only for genuinely destructive/high-risk operations, not every source or code change.
