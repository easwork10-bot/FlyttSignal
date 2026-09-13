# Source access policy

FlyttSignal separates engineering permission from live-data access. Uncertainty about a future production use must not unnecessarily block fixture-first development against public documentation.

## Access tiers

### 1. Official open API or downloadable open data

May be implemented and used when the published licence, attribution rules and technical limits are recorded. Examples: SCB open statistics under CC0.

### 2. Public pages without authentication

May be researched and sampled during development without bypassing controls. Collection must be low-volume, identify the client where practical, avoid personal data, preserve source provenance, respect technical limits, and have a kill switch. A successful HTTP response is not by itself a production licence; broader recurring or commercial operation receives a separate terms review.

### 3. Public specification for an authenticated API

Adapters, fixtures, parsers, migrations and tests may be built immediately from public schemas and examples. Live requests use only legitimately issued credentials and only within the account's approved scope. Example: Lantmäteriet Belägenhetsadress Direkt.

### 4. Login, partner or contracted source

Development may use mocks and sanitized fixtures. Never bypass authentication or access controls. Live testing starts only with a legitimate account or credential supplied for that purpose.

## Common engineering rules

- No person profiling, names or personal identity numbers unless explicitly designed and legally reviewed.
- No authentication bypass, CAPTCHA bypass or hidden-endpoint discovery intended to defeat access controls.
- Default-off live collectors, bounded retries, conservative rate limits and immediate kill switches.
- Raw evidence and derived fields are minimized and retained only as long as needed.
- Public development testing and production/commercial rollout are separate decisions.
- Source attribution, transformation notices and licence metadata travel with exported or displayed data.

This policy is an engineering risk framework, not legal advice. It keeps development moving while making live access and production decisions explicit.
