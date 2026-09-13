import type { Signal } from "@/lib/api/types";

const SWEDEN_BOUNDS = { south: 55, west: 10, north: 70, east: 25 } as const;

export function getMapCoordinate(signal: Signal): [number, number] | null {
  if (signal.property.latitude === null || signal.property.longitude === null) return null;
  const latitude = Number(signal.property.latitude);
  const longitude = Number(signal.property.longitude);
  if (
    !Number.isFinite(latitude) ||
    !Number.isFinite(longitude) ||
    latitude < SWEDEN_BOUNDS.south ||
    latitude > SWEDEN_BOUNDS.north ||
    longitude < SWEDEN_BOUNDS.west ||
    longitude > SWEDEN_BOUNDS.east
  ) return null;
  return [longitude, latitude];
}
