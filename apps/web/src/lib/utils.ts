import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function humanize(value: string) {
  const translations: Record<string, string> = {
    ACTIVE: "Aktiv",
    FAILED: "Misslyckad",
    FAKE: "Fiktiv källa",
    FILE: "Fil",
    HEALTHY: "Frisk",
    "Existing rental listed": "Hyresannons publicerad",
    "Known effective or move date": "Känt tillgänglighetsdatum",
    "Move expected within 60 days": "Flyttfönster inom 60 dagar",
    "Second independent observation": "Andra oberoende observationen",
    "New-build move-in announced": "Inflyttning i nyproduktion annonserad",
    LIKELY_TENANT_MOVE_OUT: "Trolig hyresgästutflytt",
    POTENTIAL_RENTAL_TENANCY_CHANGE: "Möjlig förändring av hyresgäst",
    POTENTIAL_NEW_BUILD_MOVE_IN: "Möjlig inflyttning i nyproduktion",
    LIKELY_HOMEOWNER_MOVE: "Trolig ägarflytt",
    NEW_BUILD_MOVE_IN: "Inflyttning i nyproduktion",
    PARTNER_API: "Partner-API",
    RENTAL_LISTED: "Hyresobjekt publicerat",
    RUNNING: "Pågår",
    SUCCESS: "Lyckad",
    rental: "Hyresrätt",
  };
  if (translations[value]) return translations[value];
  const normalized = value.replaceAll("_", " ").toLowerCase();
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

export function formatDate(value: string | null, withTime = false) {
  if (!value) return "Okänt";
  return new Intl.DateTimeFormat("sv-SE", {
    dateStyle: "medium",
    ...(withTime ? { timeStyle: "short" as const } : {}),
  }).format(new Date(value));
}
