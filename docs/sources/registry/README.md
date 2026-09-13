# Source Registry

This directory is the Milestone 2 research registry. It records candidate data sources before any live collector is implemented or enabled.

The registry is intentionally separate from the runtime `sources` table. A research decision applies to one source interface, purpose and data use—not to an organisation forever. Only an approved use case may later be promoted through an Alembic migration.

## Decision meanings

- `GO`: evidence is sufficient for the stated use case and the next implementation phase may start.
- `WAIT`: potentially useful, but permission, contract, access, terms or a technical fact must be resolved first.
- `REJECT`: do not implement the stated use case under the reviewed conditions.
- `INVENTORY`: broad-discovery candidate that has not received a deep review.

`decision` is not the same as `legal_status`. A legally clear source can still be rejected because it is technically unsuitable or has little signal value.

## Workflow

1. Add a broad candidate to `registry.yaml` with `review_depth: inventory`.
2. Select high-value candidates for a dated review under `docs/sources/reviews/<source-key>/`.
3. Record official evidence URLs, unresolved questions and review expiry.
4. Store any permitted terms snapshot separately and record its path and SHA-256 hash. A review note is not a substitute for the original terms.
5. Promote only a `GO` use case. Live collection still requires fixtures, parser tests, rate limiting and an operational kill switch.

Research tools such as Firecrawl may help discover pages. They are not evidence by themselves and are not FlyttSignal runtime dependencies.

The 2026-08-27 inventory contains 35 candidates and eight deep reviews. See the [review index](../reviews/README.md) and the [first-source recommendation](recommendation.md).
