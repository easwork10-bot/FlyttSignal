# Source Registry schema

## Decision identity

A decision is scoped as:

```text
source + interface + dataset + purpose + data use = assessment
```

This prevents a decision about public HTML polling from being incorrectly reused for a future contracted partner API from the same organisation.

## Conceptual entities

### Source

- `source_key`: stable internal identifier.
- `name`, `owner`: human-readable identity.
- `scope`, `cities`: geographic coverage.
- `roles`: one or more of `SIGNAL`, `ENRICHMENT`, `VALIDATION`, `BENCHMARK`, `GROUND_TRUTH`.
- `upstream_source_keys`: known original data providers. Empty means unknown, not independent.

### Interface

- `interface_key`: stable identifier within the source.
- `url`, `access_method`, `parser_type`.
- `requires_auth`, `requires_contract`.
- `api_documentation_url`, `rate_limits`.
- `dataset`: the specific feed, page, table or product being assessed.

### Assessment

- `purpose`, `data_use`: exact intended use.
- `legal_status`: `CLEAR`, `NEEDS_PERMISSION`, `RESTRICTED`, `UNKNOWN`.
- `privacy_class`: `NON_PERSONAL`, `POTENTIALLY_PERSONAL`, `PERSONAL`, `UNKNOWN`.
- `redistribution_rights`: `ALLOWED`, `ATTRIBUTION_REQUIRED`, `NOT_ALLOWED`, `UNKNOWN`.
- `technical_status`: `GOOD`, `CONSTRAINED`, `POOR`, `UNKNOWN`.
- `signal_value`: `NONE`, `LOW`, `MEDIUM`, `HIGH`, `VERY_HIGH`.
- `decision`: `GO`, `WAIT`, `REJECT`, `INVENTORY`.
- `decision_reason`, `unresolved_questions`.
- `review_depth`: `inventory` or `deep`.
- `reviewed_at`, `reviewed_by`, `review_expires_at`.
- `evidence_urls`.

### Terms review

- `terms_url`, `terms_checked_at`.
- `terms_snapshot_path`, `terms_hash`, `terms_version`.
- `review_path`.

`terms_hash` is calculated from the archived original content, not from the analyst's summary. If archiving is not permitted or has not been performed, the snapshot path and hash remain `null` and this is stated explicitly.

### Provenance dependency

Source independence is a graph, not a boolean. A dependency edge contains:

- `from_source_key`, `to_source_key`.
- `relationship_type`: for example `OWNED_BY`, `SYNDICATED_FROM`, `COPIED_FROM`, `SUBMITTED_BY`.
- `evidence_url`, `confidence`.

Signal scoring must not award an independent-source bonus merely because two observations came from different domains.

## Promotion rule

The YAML registry is a governance artifact, not runtime configuration. Promotion to the database requires a separate reviewed implementation with an Alembic migration. No collector may infer permission from `robots.txt`, a successful HTTP response or the existence of an undocumented endpoint.
