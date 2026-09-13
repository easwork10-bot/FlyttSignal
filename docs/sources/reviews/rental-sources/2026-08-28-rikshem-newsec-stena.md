# Rikshem, Newsec and Stena — Uppsala channel verification

Reviewed: 2026-08-28

## Decision

Do not create separate public collectors for these providers. Their reviewed public Uppsala inventory is already distributed by Uppsala Bostadsförmedling, which FlyttSignal models as the publisher. Preserve the upstream provider or manager on every listing.

## Rikshem

Rikshem says that Uppsala and Knivsta rentals are mediated through Uppsala Bostadsförmedling. The broker's provider page confirms that it handles Rikshem's Uppsala/Knivsta letting and exposes current objects with stable listing URLs.

- Channel: `uppsala-bostadsformedling`
- Coverage: `FULL` for the reviewed public Uppsala route
- Separate adapter: rejected as a duplicate
- Verified fixture object: `200062438843`, Sköldmövägen 19 C

## Newsec

Newsec is a property manager, not necessarily the owner of each advertised property. Uppsala Bostadsförmedling exposes the managed vacancies and states that ownership can belong to another party. The fixture therefore records `Newsec (förvaltning)` and does not infer ownership.

- Channel: `uppsala-bostadsformedling`
- Coverage: `FULL` for the reviewed Newsec-managed public route
- Separate adapter: rejected as a duplicate
- Verified fixture object: `200062521232`, Johannesbäcksgatan 49

## Stena Fastigheter

Stena states that Uppsala rentals are sought through Uppsala Bostadsförmedling. Existing Stena tenants may also use an authenticated internal queue on Mina sidor. That queue is a different audience and remains explicitly out of collection scope.

- Public channel: `uppsala-bostadsformedling`, `FULL`
- Internal channel: `stena-internal-queue`, authenticated and restricted
- Separate public adapter: rejected as a duplicate
- Verified fixture object: `200062359330`, Thorildsgatan 10

## Fixture and lifecycle boundary

The controlled UBF fixture now contains one dated, publicly verified example for each route. It stores listing identifiers, canonical public URLs, address, rooms, area, rent, publisher and upstream provenance. It excludes descriptions, images, contact information, application data and user-account data.

The fixture is a complete controlled test snapshot, not a claim that three objects represent the complete live Uppsala market. M3.1 can classify it `COMPLETE` only for deterministic fixture scope; snapshot status does not control lifecycle behavior.

## Evidence

- Rikshem area statement: https://www.rikshem.se/bo-hos-oss/vara-omraden/rikshem-i-uppsala-knivsta/
- Rikshem at Uppsala Bostadsförmedling: https://www.bostad.uppsala.se/for-hyresvardar/vara-hyresvardar/rikshem
- Newsec at Uppsala Bostadsförmedling: https://www.bostad.uppsala.se/for-hyresvardar/vara-hyresvardar/newsec
- Stena letting routes: https://www.stenafastigheter.se/bostader/hyra-bostad/
- Stena at Uppsala Bostadsförmedling: https://www.bostad.uppsala.se/for-hyresvardar/vara-hyresvardar/stena-fastigheter
