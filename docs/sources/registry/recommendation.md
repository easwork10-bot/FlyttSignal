# Milestone 2 source decision

Reviewed: 2026-08-28
Status updated: 2026-08-28 after M2.3 rental-source verification

## Recommendation

Build **SCB PxWebApi 2** as the first real-data adapter in M2.2A, using table `TAB6640` and Uppsala municipality `0380` solely for `BENCHMARK`/`VALIDATION` data.

Why:

- it is an official documented API with access to all Statistics Database tables;
- its limits are explicit: 150,000 cells per request and 30 calls per 10 seconds per IP;
- it avoids personal and property-level lead data;
- it exercises real HTTP, schema mapping, provenance, freshness and operational metrics without pretending to be a move signal.

The adapter must target PxWebApi 2. PxWebApi 1 is scheduled to remain only until the turn of 2026/2027.

## Selected municipal context candidate

Use Uppsala Open Data **Byggnader** (ArcGIS item `fbceff62d4b3439c88f118ee67e796c9`, layer `1`) for M2.2C. Dataset-specific verification on 2026-08-28 confirmed a public GeoJSON-capable Feature Layer with building-purpose, status, modification-time and activity codes. Implement it fixture-first through a separate score-neutral spatial-feature contract; do not build a generic portal scraper or force it through the rental-listing pipeline.

The layer is a current snapshot rather than an event log. Fixture verification and one bounded five-feature live run are complete and idempotent with zero event, signal and score-component delta. Recurring collection remains disabled while the object-ID lifecycle and modification-time cursor are observed. See `docs/milestones/milestone-2-uppsala-buildings-plan.md`.

## Signal-source decision

Uppsala Bostadsförmedling is the first M2.3 aggregate rental channel. Its public application exposes broad regional inventory and stable object URLs without login. The exact anonymous GraphQL query used by the public application returned 307 objects in a bounded verification. A separate live adapter and disabled database source now exist; fixture and live identities are isolated, the query is field-minimal, and removals stay disabled. Recurring execution remains default-off because request limits and an integration SLA are not published.

Use Hyresgästföreningen's municipality-indexed landlord directory as a recurring **coverage audit**, not as an availability signal. The 2026-08-28 Uppsala review expanded the inventory to twelve major landlords and verified each distribution route against first-party material.

Do not build separate public Uppsalahem, Rikshem, Victoriahem or Newsec adapters: their reviewed Uppsala inventory is upstreamed through Uppsala Bostadsförmedling. Stena's public Uppsala distribution is mainly the same source, with a separate internal-tenant queue that is out of scope. Preserve the displayed landlord as upstream provenance.

The Heimstaden complementary adapter and bounded live parser are verified. HomeQ and HSB have separate live source identities: HomeQ uses the anonymous search request used by its public page, expands only real project ad IDs and stores project metadata separately, while HSB uses its server-rendered direct Uppsala cards. On 2026-08-29 the controlled project-aware batch stored 190 UBF, 3 Heimstaden, 53 HomeQ and 2 HSB listings. A supported HomeQ relationship remains a future reliability upgrade, not a blocker for public development testing. ByggVesta remains partner-gated, and Nationsgårdarna requires an approved authenticated route.

Other reviewed listing interfaces remain gated:

- HomeQ partner API: keep as a future reliability and lifecycle upgrade; the separate minimal public-search adapter is active in development.
- Hemnet BostadsAPI: `WAIT`; documentation targets brokers and authenticated integration users.
- Booli business housing-data API: `REJECT` for now because Booli states access is generally not allowed for other companies; reopen only after written approval.

## Exit gate before M2.2A

1. Confirm the exact SCB table and stable API v2 identifiers. **Done: `TAB6640`.**
2. Capture the applicable SCB reuse terms and SHA-256 snapshot metadata. **Done.**
3. Write captured response fixtures before enabling live fetches. **Done.**
4. Define a conservative poll schedule below published limits. **Done.**
5. Add per-source enablement, timeout, retry/backoff and kill-switch behavior. **Done.**
6. Record and verify the first controlled live run. **Done: one snapshot and nine benchmark observations; the unchanged rerun produced no duplicates.**

No Signal Engine weights or listing-removal behavior change as part of this decision.

M2.2A was implemented on 2026-08-27 with the source disabled by default. Enabling live collection requires both the database source flag and `SCB_LIVE_ENABLED=true`.

## M2.2B implementation status

The Belägenhetsadress Direkt 4.2 fixture-first adapter is implemented. It has a separate enrichment contract, exact Uppsala matching, selected `basinformation,berorkrets` requests, OAuth support, schema-drift tests, attribution and two independent kill switches. Address facts and register-unit links use separate tables. The database fixture verification is idempotent and produces no events or signals. Geotorget requires an FRL purpose/access review for the account; the question has been sent. A controlled live verification run waits for that response, issued OAuth credentials and deliberate activation of both switches.

In parallel, prepare and technically sample a public rental-listing source under `docs/sources/access-policy.md`. Broader recurring or production collection receives its own terms decision, but fixture-first development does not need to stop.
