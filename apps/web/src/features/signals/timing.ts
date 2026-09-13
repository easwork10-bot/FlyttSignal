import type { Signal } from "@/lib/api/types";

export const AVAILABLE_FROM = "ADVERTISED_AVAILABLE_FROM";
export const APPLICATION_DEADLINE = "APPLICATION_DEADLINE";

export function timingDate(signal: Signal, type: string): string | null {
  const fact = signal.timing?.facts.find((item) => item.type === type);
  return fact?.state === "PRESENT" ? fact.date : null;
}

export function availableFrom(signal: Signal): string | null {
  return timingDate(signal, AVAILABLE_FROM);
}

export function applicationDeadline(signal: Signal): string | null {
  return timingDate(signal, APPLICATION_DEADLINE);
}

export function timingState(signal: Signal, type: string): string {
  return signal.timing?.facts.find((item) => item.type === type)?.state ?? "UNAVAILABLE";
}
