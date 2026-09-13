import { api } from "./client";
import type { Signal, SignalList } from "./types";
export type SignalFilters = { minStrength?:number; signalType?:string; cityId?:number; from?:string; to?:string };
export function getSignals(filters: SignalFilters = {}) { const p = new URLSearchParams(); if (filters.minStrength) p.set("min_strength", String(filters.minStrength)); if (filters.signalType) p.set("signal_type", filters.signalType); if (filters.cityId) p.set("city_id", String(filters.cityId)); if (filters.from) p.set("from", filters.from); if (filters.to) p.set("to", filters.to); return api<SignalList>(`/signals?${p}`); }
export function getSignal(id:string) { return api<Signal>(`/signals/${id}`); }
