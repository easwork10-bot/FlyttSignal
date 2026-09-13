import { api } from "./client";
import type { HousingProviderList, RentalCoverage, RentalProjectList, Source, SourceRun, SpatialFeatureList } from "./types";
export const getSources = () => api<Source[]>("/sources");
export const getSourceRuns = () => api<SourceRun[]>("/source-runs");
export const getSpatialFeatures = () => api<SpatialFeatureList>("/spatial-features?limit=12");
export const getHousingProviders = () => api<HousingProviderList>("/housing-providers");
export const getRentalCoverage = () => api<RentalCoverage>("/rental-coverage");
export const getRentalProjects = () => api<RentalProjectList>("/rental-projects");
