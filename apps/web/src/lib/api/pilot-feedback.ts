import { api } from "./client";
import type { PilotContext, PilotFeedback, PilotFeedbackUpsert } from "./types";

export type PilotFeedbackContext = Omit<PilotContext, "pilot_key">;

export function getPilotFeedback(
  signalId: string,
  pilotKey: string,
  context: PilotFeedbackContext,
) {
  const params = new URLSearchParams({
    pilot_key: pilotKey,
    cohort_version: context.cohort_version,
    cohort_as_of_date: context.cohort_as_of_date,
    dimension_scope_key: context.dimension_scope_key,
    score_run_id: context.score_run_id,
    score_as_of_date: context.score_as_of_date,
    definition_set_hash: context.definition_set_hash,
  });
  return api<PilotFeedback | null>(`/pilot/signals/${signalId}/feedback?${params}`);
}

export function savePilotFeedback(signalId: string, payload: PilotFeedbackUpsert) {
  return api<PilotFeedback>(`/pilot/signals/${signalId}/feedback`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}
