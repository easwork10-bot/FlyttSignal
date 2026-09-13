# Architecture

FlyttSignal is a modular monolith: one Python codebase and PostgreSQL/PostGIS database, with separate FastAPI and polling-worker processes. FlyttRadar is a Next.js client. No queue or extra service is required for the current workload.

## Responsibilities

```text
source integration → ingestion → typed facts/events → signal inference
                         ↓                 ↓                ↓
                    retained source data and database repositories
                                                         ↓
                              explicit dimension evaluation/activation
                                                         ↓
                                         FastAPI /api → FlyttRadar
```

- `integrations/sources/` owns source protocols, parsing and normalization, grouped into rental listings, rental developments, benchmarks, address enrichment and spatial features.
- `ingestion/contracts.py`, change detection and snapshot-integrity policy provide typed workflow contracts. Pipelines own transactions and orchestration.
- `domains/` owns events, listings, properties, signals, developments and provider identity. Domains have no API, database, worker or integration imports.
- `db/models/` owns persistence mappings; `db/repositories/` owns queries. The model package exports are an actively used import boundary.
- `worker/` claims due sources using `FOR UPDATE SKIP LOCKED`, dispatches the appropriate pipeline, records outcomes and schedules the next attempt.
- `scoring/` orchestrates evaluation and read projections; dimension policy is domain-owned.
- `api/app.py` creates FastAPI; `api/router.py` explicitly composes resource routers. Routes own HTTP handling, schemas own contracts, mappers are pure, repositories own SQL.
- Frontend `app/` routes delegate to `features/`. Shared primitives are in `components/ui/`; the shell is in `components/layout/`. HTTP access and generated types live in `lib/api/`.

The internal API is `/api`, without a URL-version prefix. Stable explicit operation IDs and generated OpenAPI/TypeScript types protect intentional contract changes. Internal rental developments remain exposed at `/rental-projects`. The worker never calls the application's own HTTP API.

## Domain semantics

| Concept | Contract |
| --- | --- |
| Source/publisher | Channel through which an observation is collected. |
| Provider | Housing organization behind the listing; separate from publisher/data owner. |
| Raw item | Source-owned observation and identity/hash, not a verified household fact. |
| Listing | Advertised offer, not the matched property itself. |
| Event | Typed interpretation of observed evidence. |
| Signal | Hypothesis supported by events; not an observed move or signed tenancy. |
| Outcome | Later evidence; only explicit confirmed-household evidence establishes a confirmed move. |
| Development | Project-level context, never synthetic individual listings. |

`POTENTIAL_RENTAL_TENANCY_CHANGE` means a listing suggests a possible change in the rental relationship. It does not prove notice, physical vacancy, a signed contract or actual departure.
`POTENTIAL_NEW_BUILD_MOVE_IN` is an inference about possible future occupancy, never a completed move-in.
`LIKELY_RENTAL_TURNOVER` requires separately qualified same-unit turnover evidence; an ordinary advert is insufficient.
New-construction true/false/unknown remain distinct. Room, short-term, student and senior categories retain explicit reasons rather than silently changing signal identity.

`targetability` describes whether an action can be directed to a unit, building, area or no safe target. It is not a hidden input deciding signal type.

Advertised availability and application deadline are source facts. System first/last observation dates are collection metadata. Neither proves an actual move. Rental timing uses typed facts and explicit missing/unavailable/not-applicable/conflict semantics, not a mechanically fabricated move window.

Current reads exclude superseded signals through `Signal.current()`. Historical reads honor as-of validity; later evidence supersession must not erase an earlier valid observation or an independently observed outcome.

## Ingestion and identity

Collection success and inventory completeness are separate. Completeness requires evidence of scope, pagination, counts and limits; HTTP 200 is not enough. Removal requires the configured source-specific lifecycle gate and eligible scheduled complete runs, not an incomplete, capped, failed or manual fetch. Reobservation alone must not duplicate content revisions.

Deduplication uses provider and upstream identity with source provenance. Two publisher channels syndicating one provider/listing are not independent corroboration. Preserve valid unrelated evidence when replacing an inference.

Only one unambiguous strong property match may merge identities. Known unit identity must agree; missing/conflicting unit identity cannot be promoted to certainty by address alone. Uncertain matching remains explicit. Listing-specific facts must not be overwritten by another publisher's shared property projection.

Classification is multi-label and uses explicit source facts: absence of a new-build flag is not existing-stock evidence, and a project label alone does not establish new construction. Lead time is the Stockholm calendar-day difference between advertised availability and the listing's own first observation; negative values are valid late observations, not values to clamp to zero. Quality ratios retain numerator and denominator, including missing measurements.

Preserve source precision when a display rounds a measurement. "By agreement" is not an exact availability date. A public object number is not automatically a cross-source unit identity; its namespace must be established. Current detail pages cannot certify when an older classification first became true. Threshold crossings after a score-policy change are not evidence that the underlying housing facts became invalid.

SCB aggregates, Lantmäteriet address/register-unit enrichment, Uppsala building geometry and HomeQ project context have separate pipelines. They do not directly create property events or signal evidence. Coordinate reference systems and source attribution remain explicit.

## Scoring and pilot

Signal Strength ranks evidence for relevant housing change; Data Confidence describes identity/provenance/input support; Timing describes temporal relevance. None is a calibrated move probability.
Commercial attributes (area, rooms, rent) cannot strengthen the move hypothesis. Missing data cannot improve confidence. Raw evidence counts do not replace independent evidence counts. Every evaluation is attributable to inputs, explicit as-of date and a typed definition/hash.

Current product prioritization consumes a complete explicitly activated dimension run. Collection does not silently activate new scores. The pilot fails closed with 409 when the activation context is incomplete. Model evaluation, activation authority, signal state and product eligibility are separate.

Pilot feedback/activity preserves exactly the cohort, run, definition hash and dimensions shown. Repeated views do not inflate unique shown/opened counts. Reviews are not confirmed moves or independent ground truth merely because an AI performed them.

## Frontend and operational boundaries

The map and table share signal data. MapLibre/OpenFreeMap is optional presentation; tile failure must not disable other workflows. Raw payloads remain server-side; detail responses expose traceable identifiers and selected facts.

Live adapters are UBF, HomeQ, HSB and Heimstaden. Disabling collection never selects a fixture fallback. Source coverage combines reviewed discovery with actual inventory; a provider directory is not proof of available units. See [source reviews](sources/reviews/README.md).

Add cities as data and mappings, sources through typed contracts and fixtures. Introduce separate services only for measured needs. Do not mix account identity into housing evidence semantics.
