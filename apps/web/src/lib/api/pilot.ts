import { api } from "./client";
import type { PilotSignalList } from "./types";

export type PilotSignalFilters = {
  asOf?: string;
  addressQuery?: string;
  pilotKey?: string;
  reviewStatus?: "ALL" | "REVIEWED" | "UNREVIEWED";
  strengthBand?: "LOW" | "MEDIUM" | "HIGH";
  signalType?: string;
  dateFrom?: string;
  dateTo?: string;
  propertyType?: string;
  minRooms?: number;
  maxRooms?: number;
  minAreaM2?: number;
  maxAreaM2?: number;
  centerLatitude?: number;
  centerLongitude?: number;
  radiusKm?: number;
  sort?: "PRIORITY" | "MOVE_WINDOW" | "NEWEST";
  limit?: number;
  offset?: number;
};

export function getPilotSignals(filters: PilotSignalFilters = {}) {
  const params = new URLSearchParams();
  if (filters.asOf) params.set("as_of", filters.asOf);
  if (filters.addressQuery) params.set("address_query", filters.addressQuery);
  if (filters.pilotKey) params.set("pilot_key", filters.pilotKey);
  if (filters.reviewStatus && filters.reviewStatus !== "ALL") {
    params.set("review_status", filters.reviewStatus);
  }
  if (filters.strengthBand) params.set("strength_band", filters.strengthBand);
  if (filters.signalType) params.set("signal_type", filters.signalType);
  if (filters.dateFrom) params.set("from", filters.dateFrom);
  if (filters.dateTo) params.set("to", filters.dateTo);
  if (filters.propertyType) params.set("property_type", filters.propertyType);
  if (filters.minRooms !== undefined) params.set("min_rooms", String(filters.minRooms));
  if (filters.maxRooms !== undefined) params.set("max_rooms", String(filters.maxRooms));
  if (filters.minAreaM2 !== undefined) params.set("min_area_m2", String(filters.minAreaM2));
  if (filters.maxAreaM2 !== undefined) params.set("max_area_m2", String(filters.maxAreaM2));
  if (filters.centerLatitude !== undefined) params.set("center_latitude", String(filters.centerLatitude));
  if (filters.centerLongitude !== undefined) params.set("center_longitude", String(filters.centerLongitude));
  if (filters.radiusKm !== undefined) params.set("radius_km", String(filters.radiusKm));
  if (filters.sort) params.set("sort", filters.sort);
  if (filters.limit) params.set("limit", String(filters.limit));
  if (filters.offset) params.set("offset", String(filters.offset));
  return api<PilotSignalList>(`/pilot/signals?${params}`);
}
