# Draft — FRL purpose review and API access for Belägenhetsadress Direkt 4.2

Use this general description when Lantmäteriet asks about the intended processing. It intentionally omits the application's name and business-specific logic while accurately describing the selected data and processing. Replace every bracketed item before submitting it.

## Proposed purpose text

> The purpose is technical development and testing of a digital service for validating, normalising and geographically linking addresses and properties. Initial use is limited to Uppsala municipality. The service will not retrieve or process owner names, personal identity numbers, contact details, mortgages or person profiles. The selected Lantmäteriet data is used for address validation and address-to-register-unit linking, not for automated person decisions.

## Requested scope

- Product: Belägenhetsadress Direkt 4.2
- Geography: Uppsala municipality (`0380`)
- Information subset: `basinformation,berorkrets`
- Selected `berorkrets` fields: register-unit UUID, designation and type (`Fastighet`/`Samfällighet`)
- Excluded: register-unit batch lookup, owner names, personal identity numbers and person-level attributes
- Query pattern: one exact/free-text address or point lookup for an existing permitted observation; low volume; no bulk harvesting
- Derived storage: address object identifier, normalised address components, municipality, postcode/postal town where supplied, status, coordinates and provenance
- Raw responses: retained only for `[PROPOSED RETENTION PERIOD]` for technical audit and then deleted
- External availability: no raw Lantmäteriet response or bulk dataset is exposed to third parties
- Attribution: product name, Lantmäteriet and retrieval/update date will accompany displayed or exported derived data
- Authentication: OAuth 2.0 client credentials preferred; secrets stored outside source control

## Organisation details to complete

- Legal organisation/name: `[NAME]`
- Organisation number, if applicable: `[NUMBER]`
- Commercial or non-commercial use: `[CATEGORY]`
- Responsible contact: `[NAME AND EMAIL]`
- Controller/legal-responsibility role: `[ROLE]`
- Development hosting country: Sweden
- Production hosting provider and region: `[PROVIDER AND EU/EEA REGION]`
- Any US-owned cloud provider involved: `[YES/NO AND PROVIDER]`
- Proposed retention period and deletion process: `[DETAILS]`

## Questions for Lantmäteriet

1. Which usage category applies to the purpose and selected field scope above?
2. Is any additional information required for the FRL purpose review?
3. Can verification-environment access be provisioned after the review?
4. What service-wide request-rate limit and credential lifecycle apply?

Save the complete response, allowed scope, issued endpoints, non-secret account metadata and operational limits alongside the source review before the controlled live run. Keep credentials only in the private `.env`.
