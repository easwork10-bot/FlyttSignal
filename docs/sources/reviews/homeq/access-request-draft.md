# HomeQ — partner data-access request

This is a technical scope checklist for a future conversation, not a sent request and not an assumption that access is available.

## Short request

We are developing a service that observes public rental-market availability in Uppsala. We would like to discuss an approved read-only integration for active rental listings and lifecycle changes. We do not need applicant profiles, applications, credit information, messages or other personal data.

Could HomeQ confirm whether a supported public feed or partner interface exists for this use case and which contractual and technical conditions apply? We have verified that anonymous search/detail pages expose the necessary non-personal facts, but we prefer a supported interface for recurring use.

## Minimum data contract

- stable HomeQ listing identifier and canonical public URL;
- upstream landlord identifier and display name;
- municipality, area and public address or the coarsest approved location;
- rooms, area, rent, availability date and application deadline when published;
- listing state plus created, updated and withdrawn timestamps;
- explicit snapshot completeness or event/cursor semantics.

## Questions that must be answered before activation

1. Is listing read access available to a non-landlord data partner?
2. May approved fields be retained as historical lifecycle observations and combined into aggregate/inferred signals?
3. Which attribution, canonical-link and redistribution requirements apply?
4. Is the original landlord always identified, including syndicated listings?
5. Are changes delivered by webhook/event stream, cursor-based polling or complete snapshots?
6. What are the rate limits, retry rules, deletion obligations and test-environment options?
7. Can the scope be restricted to Uppsala and to non-personal listing fields?

## Engineering acceptance gate

Credentials are added only after the endpoint, field scope and use terms are confirmed. The adapter must map into the existing `RentalListing` contract, preserve the landlord as `upstream_provider_key`, store raw provenance, treat incomplete snapshots as non-removing, and ship disabled by default with a kill switch.
