import type { components } from "./generated";

type Schema<Name extends keyof components["schemas"]> = components["schemas"][Name];

export type RegisterUnitReference = Schema<"RegisterUnitReferenceOut">;
export type AddressEnrichment = Schema<"AddressEnrichmentOut">;
export type Property = Schema<"PropertyOut">;
export type Evidence = Schema<"EvidenceOut">;
export type Signal = Schema<"SignalOut">;
export type SignalList = Schema<"SignalList">;
export type PilotCohortCriteria = Schema<"PilotCohortCriteriaOut">;
export type PilotSignal = Schema<"PilotSignalOut">;
export type PilotSignalList = Schema<"PilotSignalListOut">;
export type PilotFeedback = Schema<"PilotFeedbackOut">;
export type PilotFeedbackUpsert = Schema<"PilotFeedbackUpsert">;
export type PilotContext = Pick<
  PilotFeedbackUpsert,
  | "pilot_key"
  | "cohort_version"
  | "cohort_as_of_date"
  | "dimension_scope_key"
  | "score_run_id"
  | "score_as_of_date"
  | "definition_set_hash"
>;
export type PilotActivityUpsert = Schema<"PilotActivityUpsert">;
export type PilotActivityRecorded = Schema<"PilotActivityRecordedOut">;
export type PilotMetrics = Schema<"PilotMetricsOut">;
export type City = Schema<"CityOut">;
export type Source = Schema<"SourceOut">;
export type SourceRun = Schema<"SourceRunOut">;
export type RentalProject = Schema<"RentalProjectOut">;
export type RentalProjectList = Schema<"RentalProjectList">;
export type RentalCoverageProvider = Schema<"RentalCoverageProviderOut">;
export type RentalCoverage = Schema<"RentalCoverageOut">;
export type SpatialFeature = Schema<"SpatialFeatureOut">;
export type SpatialFeatureList = Schema<"SpatialFeatureList">;
export type RentalListing = Schema<"RentalListingOut">;
export type RentalListingList = Schema<"RentalListingList">;
export type ProviderChannel = Schema<"ProviderChannelOut">;
export type HousingProvider = Schema<"HousingProviderOut">;
export type HousingProviderList = Schema<"HousingProviderList">;
