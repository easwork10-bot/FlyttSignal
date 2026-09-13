import { api } from "./client";
import type {
  PilotActivityRecorded,
  PilotActivityUpsert,
  PilotContext,
  PilotMetrics,
} from "./types";

export function recordPilotActivity(payload: PilotActivityUpsert) {
  return api<PilotActivityRecorded>("/pilot/activity", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function getPilotMetrics(context: PilotContext) {
  const params = new URLSearchParams({
    pilot_key: context.pilot_key,
    cohort_version: context.cohort_version,
    cohort_as_of_date: context.cohort_as_of_date,
    dimension_scope_key: context.dimension_scope_key,
    score_run_id: context.score_run_id,
    score_as_of_date: context.score_as_of_date,
    definition_set_hash: context.definition_set_hash,
  });
  return api<PilotMetrics>(`/pilot/metrics?${params}`);
}
