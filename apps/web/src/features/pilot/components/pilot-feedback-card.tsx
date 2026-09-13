"use client";

import { Check, MessageSquareText } from "lucide-react";
import { FormEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { normalizePilotKey } from "@/features/pilot/pilot-session";
import {
  getPilotFeedback,
  type PilotFeedbackContext,
  savePilotFeedback,
} from "@/lib/api/pilot-feedback";
import type { PilotFeedbackUpsert } from "@/lib/api/types";

type Verdict = PilotFeedbackUpsert["verdict"];
type Reason = PilotFeedbackUpsert["reason"];

const VERDICTS: { value: Verdict; label: string }[] = [
  { value: "USEFUL", label: "Användbar" },
  { value: "MAYBE", label: "Kanske" },
  { value: "NOT_USEFUL", label: "Inte användbar" },
];

const REASONS: Record<Verdict, { value: Reason; label: string }[]> = {
  USEFUL: [{ value: "GOOD_OPPORTUNITY", label: "Bra möjlighet" }],
  MAYBE: [
    { value: "TOO_EARLY", label: "För tidig" },
    { value: "TOO_LATE", label: "För sen" },
    { value: "INSUFFICIENT_CONTEXT", label: "För lite information" },
  ],
  NOT_USEFUL: [
    { value: "TOO_EARLY", label: "För tidig" },
    { value: "TOO_LATE", label: "För sen" },
    { value: "WRONG_PROPERTY", label: "Fel bostad" },
    { value: "WEAK_SIGNAL", label: "För svag signal" },
    { value: "DUPLICATE", label: "Dubblett" },
    { value: "OUTSIDE_SERVICE_AREA", label: "Utanför serviceområdet" },
    { value: "INSUFFICIENT_CONTEXT", label: "För lite information" },
  ],
};

export function PilotFeedbackCard({
  signalId,
  context,
  initialPilotKey = "",
}: {
  signalId: string;
  context: PilotFeedbackContext;
  initialPilotKey?: string;
}) {
  const queryClient = useQueryClient();
  const [pilotKey, setPilotKey] = useState(initialPilotKey);
  const [lookupKey, setLookupKey] = useState(initialPilotKey);
  const [verdict, setVerdict] = useState<Verdict | "">("");
  const [reason, setReason] = useState<Reason | "">("");
  const [note, setNote] = useState<string | null>(null);

  const feedbackQuery = useQuery({
    queryKey: ["pilot-feedback", signalId, lookupKey, context],
    queryFn: () => getPilotFeedback(signalId, lookupKey, context),
    enabled: Boolean(lookupKey),
  });

  const mutation = useMutation({
    mutationFn: (payload: PilotFeedbackUpsert) => savePilotFeedback(signalId, payload),
    onSuccess: (feedback) => {
      setLookupKey(feedback.pilot_key);
      queryClient.setQueryData(
        ["pilot-feedback", signalId, feedback.pilot_key, context],
        feedback,
      );
      void queryClient.invalidateQueries({ queryKey: ["pilot-signals", "filtered"] });
      void queryClient.invalidateQueries({ queryKey: ["pilot-metrics"] });
    },
  });

  const normalizedPilotKey = normalizePilotKey(pilotKey);
  const selectedVerdict = verdict || feedbackQuery.data?.verdict || "";
  const selectedReason = reason || feedbackQuery.data?.reason || "";
  const selectedNote = note ?? feedbackQuery.data?.note ?? "";
  const availableReasons = selectedVerdict ? REASONS[selectedVerdict] : [];

  function identifyPilot() {
    setPilotKey(normalizedPilotKey);
    setLookupKey(normalizedPilotKey);
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (!normalizedPilotKey || !selectedVerdict || !selectedReason) return;
    mutation.mutate({
      pilot_key: normalizedPilotKey,
      ...context,
      verdict: selectedVerdict,
      reason: selectedReason,
      note: selectedNote.trim() || null,
    });
  }

  return (
    <Card className="p-6">
      <div className="flex items-center gap-3">
        <span className="grid size-9 place-items-center rounded-lg bg-success/10 text-success">
          <MessageSquareText className="size-4" />
        </span>
        <div>
          <h2 className="font-semibold text-foreground">Pilotbedömning</h2>
          <p className="text-xs text-muted-foreground">Hjälp oss mäta verklig nytta</p>
        </div>
      </div>

      <form className="mt-6 space-y-5" onSubmit={submit}>
        <label>
          <span className="label mb-2 block">Pilotkod</span>
          <Input
            value={pilotKey}
            disabled={Boolean(initialPilotKey)}
            placeholder="exempel: pilot-uppsala-01"
            onChange={(event) => setPilotKey(event.target.value)}
            onBlur={identifyPilot}
          />
          <span className="mt-2 block text-xs leading-5 text-muted-foreground">
            {initialPilotKey
              ? "Koden följer pilotsessionens länk och kan inte ändras här."
              : "Använd en kod, inte ett personnamn. Koden är inte inloggning."}
          </span>
        </label>

        <fieldset>
          <legend className="label mb-2">Var signalen användbar?</legend>
          <div className="grid grid-cols-3 gap-2">
            {VERDICTS.map((option) => (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={selectedVerdict === option.value ? "outline" : "ghost"}
                onClick={() => {
                  setVerdict(option.value);
                  setReason(REASONS[option.value][0].value);
                }}
              >
                {option.label}
              </Button>
            ))}
          </div>
        </fieldset>

        <label>
          <span className="label mb-2 block">Huvudorsak</span>
          <Select
            value={selectedReason}
            disabled={!selectedVerdict}
            onChange={(event) => setReason(event.target.value as Reason)}
          >
            <option value="">Välj bedömning först</option>
            {availableReasons.map((option) => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </Select>
        </label>

        <label>
          <span className="label mb-2 block">Kommentar (valfri)</span>
          <textarea
            className="min-h-24 w-full resize-y rounded-xl border border-input bg-background px-3 py-2.5 text-sm text-foreground outline-none transition placeholder:text-muted-foreground focus:border-primary"
            maxLength={1000}
            value={selectedNote}
            placeholder="Vad gjorde signalen användbar eller svår att använda?"
            onChange={(event) => setNote(event.target.value)}
          />
        </label>

        {feedbackQuery.data && !mutation.isSuccess && (
          <p className="text-xs text-primary">Tidigare bedömning laddad. Du kan uppdatera den.</p>
        )}
        {mutation.isSuccess && (
          <p className="flex items-center gap-2 text-sm text-success">
            <Check className="size-4" /> Bedömningen är sparad med versionsproveniens.
          </p>
        )}
        {(feedbackQuery.error || mutation.error) && (
          <p className="text-sm text-destructive">Feedbacken kunde inte sparas eller hämtas.</p>
        )}

        <Button
          className="w-full"
          type="submit"
          disabled={!normalizedPilotKey || !selectedVerdict || !selectedReason || mutation.isPending}
        >
          {mutation.isPending ? "Sparar…" : "Spara bedömning"}
        </Button>
      </form>
    </Card>
  );
}
