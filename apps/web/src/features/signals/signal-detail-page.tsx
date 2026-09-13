"use client";

import { ArrowLeft, Building2, CheckCircle2, Database, MapPin, Ruler, Sparkles } from "lucide-react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { ErrorState, Loading } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { LantmaterietEnrichmentCard } from "@/features/signals/components/lantmateriet-enrichment-card";
import { PilotFeedbackCard } from "@/features/pilot/components/pilot-feedback-card";
import { normalizePilotKey } from "@/features/pilot/pilot-session";
import { recordPilotActivity } from "@/lib/api/pilot-activity";
import { getSignal } from "@/lib/api/signals";
import { cn, formatDate, humanize } from "@/lib/utils";
import { applicationDeadline, availableFrom, timingState } from "@/features/signals/timing";

export function SignalDetailPage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const pilotContext = useMemo(() => getPilotContext(searchParams), [searchParams]);
  const pilotReturnHref = getPilotReturnHref(searchParams, pilotContext?.pilot_key ?? "");
  const query = useQuery({ queryKey: ["signal", id], queryFn: () => getSignal(id) });
  useEffect(() => {
    if (!pilotContext?.pilot_key) return;
    void recordPilotActivity({
      ...pilotContext,
      activity_type: "OPENED",
      signal_ids: [id],
    }).catch(() => undefined);
  }, [id, pilotContext]);
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;
  const signal = query.data!;
  const firstObservedAt = signal.evidence.reduce<string | null>(
    (earliest, evidence) => !earliest || evidence.observed_at < earliest ? evidence.observed_at : earliest,
    null,
  );
  const dimensions = [
    ["Signalstyrka", signal.active_dimensions.signal_strength],
    ["Datatillit", signal.active_dimensions.data_confidence],
    ["Timing", signal.active_dimensions.timing],
  ] as const;

  return (
    <>
      <Link href={pilotContext ? pilotReturnHref : "/signals"} className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "mb-6 -ml-2")}><ArrowLeft className="size-4" />{pilotContext ? "Till piloturvalet" : "Till signalregistret"}</Link>
      <div className="mb-8 flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div><div className="mb-3 flex flex-wrap items-center gap-2"><Badge variant="success">Aktiv signal</Badge><span className="text-xs text-muted-foreground">Uppdaterad {formatDate(signal.updated_at, true)}</span>{firstObservedAt && <span className="text-xs text-muted-foreground">· först observerad {formatDate(firstObservedAt, true)}</span>}</div><h1 className="text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">{signal.property.address}</h1><p className="mt-2 text-muted-foreground">{humanize(signal.signal_type)} · {signal.property.city}</p></div>
        <div className="rounded-2xl border border-primary/20 bg-primary/10 px-5 py-4"><div className="label text-primary/70">Signalstyrka</div><div className="mt-1 text-3xl font-semibold tabular-nums text-primary">{signal.active_dimensions.signal_strength}<span className="text-base font-normal text-primary/60">/100</span></div></div>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="space-y-6">
          <Card className="p-6"><div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary"><Sparkles className="size-4" /></span><div><h2 className="font-semibold text-foreground">Signaldimensioner</h2><p className="text-xs text-muted-foreground">Tre separata prioriteringsmått, inte sannolikhet</p></div></div><div className="mt-6 grid gap-3 sm:grid-cols-3">{dimensions.map(([label, value]) => <div key={label} className="rounded-xl border border-border bg-muted/60 p-4"><span className="label">{label}</span><span className="mt-2 block text-xl font-semibold tabular-nums text-foreground">{value}<span className="text-sm font-normal text-muted-foreground">/100</span></span></div>)}</div><p className="mt-4 text-xs text-muted-foreground">Snapshot {signal.active_dimensions.as_of_date} · definition {signal.active_dimensions.definition_set_hash.slice(0, 10)}</p></Card>

          <Card className="p-6"><div className="flex items-center gap-3"><span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary"><Database className="size-4" /></span><div><h2 className="font-semibold text-foreground">Evidenshändelser</h2><p className="text-xs text-muted-foreground">{signal.evidence.length} spårbara observationer</p></div></div><div className="relative mt-6 space-y-5 before:absolute before:bottom-3 before:left-[15px] before:top-3 before:w-px before:bg-border">{signal.evidence.map((evidence) => <div key={evidence.event_id} className="relative flex gap-4"><span className="z-10 mt-1 grid size-8 shrink-0 place-items-center rounded-full border border-success/20 bg-card text-success"><CheckCircle2 className="size-4" /></span><div className="min-w-0 flex-1 rounded-xl border border-border bg-muted/40 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><div className="font-medium text-foreground">{humanize(evidence.event_type)}</div><Badge variant="muted">{evidence.source}</Badge></div><p className="mt-2 text-sm leading-6 text-muted-foreground">{evidence.reason}</p><div className="mt-3 text-xs text-muted-foreground">Observerad {formatDate(evidence.observed_at, true)} · effektiv {formatDate(evidence.effective_date)}</div></div></div>)}</div></Card>
        </div>

        <aside className="space-y-6">
          {pilotContext && <PilotFeedbackCard signalId={id} initialPilotKey={pilotContext.pilot_key} context={{ cohort_version: pilotContext.cohort_version, cohort_as_of_date: pilotContext.cohort_as_of_date, dimension_scope_key: pilotContext.dimension_scope_key, score_run_id: pilotContext.score_run_id, score_as_of_date: pilotContext.score_as_of_date, definition_set_hash: pilotContext.definition_set_hash }} />}
          <Card className="p-6"><h2 className="font-semibold text-foreground">Fastighet</h2><dl className="mt-5 space-y-4"><Fact icon={MapPin} label="Plats" value={`${signal.property.address}, ${signal.property.city}`} /><Fact icon={Ruler} label="Yta / rum" value={`${signal.property.area_m2 ?? "–"} m² · ${signal.property.rooms ?? "–"} rum`} /><Fact icon={Building2} label="Objekt" value={`${humanize(signal.property.property_type)}${signal.property.unit_identifier ? ` · lgh ${signal.property.unit_identifier}` : ""}`} /></dl></Card>
          <LantmaterietEnrichmentCard enrichments={signal.property.address_enrichments} />
          <Card className="p-6"><h2 className="font-semibold text-foreground">Annonserad timing</h2><div className="mt-5 grid gap-3 sm:grid-cols-2"><DateBlock label="Tillgänglig från" value={availableFrom(signal)} state={timingState(signal, "ADVERTISED_AVAILABLE_FROM")} /><DateBlock label="Ansökan stänger" value={applicationDeadline(signal)} state={timingState(signal, "APPLICATION_DEADLINE")} /></div><p className="mt-4 text-xs text-muted-foreground">Datum kommer från källans annons. Systemet härleder inte ett flyttfönster.</p></Card>
          <div className="rounded-2xl border border-warning/20 bg-warning/10 p-5 text-xs leading-5 text-warning">FlyttRadar visar en regelbaserad indikator. Kontrollera alltid underliggande evidens innan signalen används operativt.</div>
        </aside>
      </div>
    </>
  );
}

function Fact({ icon: Icon, label, value }: { icon: typeof MapPin; label: string; value: string }) { return <div className="flex gap-3"><Icon className="mt-0.5 size-4 shrink-0 text-primary" /><div><dt className="label">{label}</dt><dd className="mt-1 text-sm text-foreground">{value}</dd></div></div>; }
function DateBlock({ label, value, state }: { label: string; value: string | null; state: string }) { return <div className="rounded-xl border border-border bg-muted/60 p-3 text-center"><div className="label">{label}</div><div className="mt-2 text-sm font-medium text-foreground">{value ?? (state === "UNAVAILABLE" ? "Ej tillgängligt" : "Ej angivet")}</div></div>; }

function getPilotContext(params: ReturnType<typeof useSearchParams>) {
  const cohort = params.get("cohort");
  const cohortAsOf = params.get("cohort_as_of");
  const dimensionScope = params.get("dimension_scope");
  const scoreRun = params.get("score_run");
  const scoreAsOf = params.get("score_as_of");
  const definitionSet = params.get("definition_set");
  const pilotKey = normalizePilotKey(params.get("pilot") ?? "");
  if (
    params.get("from") !== "pilot" ||
    !cohort ||
    !cohortAsOf ||
    !dimensionScope ||
    !scoreRun ||
    !scoreAsOf ||
    !definitionSet
  ) return null;
  return {
    cohort_version: cohort,
    cohort_as_of_date: cohortAsOf,
    dimension_scope_key: dimensionScope,
    score_run_id: scoreRun,
    score_as_of_date: scoreAsOf,
    definition_set_hash: definitionSet,
    pilot_key: pilotKey,
  };
}

function getPilotReturnHref(params: ReturnType<typeof useSearchParams>, pilotKey: string) {
  const returnTo = params.get("return_to");
  if (returnTo === "/pilot" || returnTo?.startsWith("/pilot?")) return returnTo;
  return pilotKey ? `/pilot?pilot=${encodeURIComponent(pilotKey)}` : "/pilot";
}
