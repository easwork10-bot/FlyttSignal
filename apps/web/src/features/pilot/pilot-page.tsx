"use client";

import {
  ArrowUpRight,
  CalendarClock,
  ChevronLeft,
  ChevronRight,
  List,
  Map,
  MapPinned,
  Search,
  Sparkles,
  Target,
} from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { Empty, ErrorState, Loading } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { SignalMapWorkspace } from "@/features/signals/components/signal-map-workspace";
import { normalizePilotKey } from "@/features/pilot/pilot-session";
import { getPilotMetrics, recordPilotActivity } from "@/lib/api/pilot-activity";
import { getPilotSignals } from "@/lib/api/pilot";
import type { PilotSignal, PilotSignalList } from "@/lib/api/types";
import { humanize } from "@/lib/utils";
import { applicationDeadline, availableFrom } from "@/features/signals/timing";

type TimeWindow = "ALL" | "OPEN" | "NEXT_30" | "DAYS_31_60" | "DAYS_61_90";
type PilotSort = "PRIORITY" | "MOVE_WINDOW" | "NEWEST";
type ReviewStatus = "ALL" | "REVIEWED" | "UNREVIEWED";

const UPPSALA_CENTER = { latitude: 59.8586, longitude: 17.6389 };
const PAGE_SIZE = 50;

export function PilotPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const activePilotKey = normalizePilotKey(searchParams.get("pilot") ?? "");
  const [pilotDraft, setPilotDraft] = useState(activePilotKey);
  const initialAddressQuery = normalizeAddressQuery(searchParams.get("q") ?? "");
  const [searchDraft, setSearchDraft] = useState(initialAddressQuery);
  const [addressQuery, setAddressQuery] = useState(initialAddressQuery);
  const [strengthBand, setStrengthBand] = useState<string>(
    choice(searchParams.get("priority"), ["", "HIGH", "MEDIUM", "LOW"] as const, ""),
  );
  const [timeWindow, setTimeWindow] = useState<TimeWindow>(
    choice(
      searchParams.get("window"),
      ["ALL", "OPEN", "NEXT_30", "DAYS_31_60", "DAYS_61_90"] as const,
      "ALL",
    ),
  );
  const [minRooms, setMinRooms] = useState<string>(
    choice(searchParams.get("rooms"), ["", "2", "3", "4"] as const, ""),
  );
  const [minArea, setMinArea] = useState<string>(
    choice(searchParams.get("area"), ["", "40", "60", "80"] as const, ""),
  );
  const [radiusKm, setRadiusKm] = useState<string>(
    choice(searchParams.get("radius"), ["", "5", "10", "20"] as const, ""),
  );
  const [sort, setSort] = useState<PilotSort>(
    choice(searchParams.get("sort"), ["PRIORITY", "MOVE_WINDOW", "NEWEST"] as const, "PRIORITY"),
  );
  const [reviewStatus, setReviewStatus] = useState<ReviewStatus>(
    activePilotKey
      ? choice(
          searchParams.get("review"),
          ["ALL", "REVIEWED", "UNREVIEWED"] as const,
          "ALL",
        )
      : "ALL",
  );
  const [showMap, setShowMap] = useState(searchParams.get("view") !== "list");
  const [offset, setOffset] = useState(() => pageOffset(searchParams.get("page")));
  const cohortQuery = useQuery({
    queryKey: ["pilot-signals", "cohort"],
    queryFn: () => getPilotSignals({ limit: 1 }),
  });
  const cohortAsOf = cohortQuery.data?.cohort_as_of_date;
  const dateRange = useMemo(
    () => pilotDateRange(timeWindow, cohortAsOf),
    [cohortAsOf, timeWindow],
  );
  const query = useQuery({
    queryKey: [
      "pilot-signals",
      "filtered",
      cohortAsOf,
      addressQuery,
      strengthBand,
      timeWindow,
      minRooms,
      minArea,
      radiusKm,
      sort,
      reviewStatus,
      offset,
    ],
    queryFn: () =>
      getPilotSignals({
        asOf: cohortAsOf,
        addressQuery: addressQuery || undefined,
        pilotKey: activePilotKey || undefined,
        reviewStatus,
        strengthBand: strengthBand
          ? (strengthBand as PilotSignal["strength_band"])
          : undefined,
        dateFrom: dateRange.from,
        dateTo: dateRange.to,
        minRooms: minRooms ? Number(minRooms) : undefined,
        minAreaM2: minArea ? Number(minArea) : undefined,
        centerLatitude: radiusKm ? UPPSALA_CENTER.latitude : undefined,
        centerLongitude: radiusKm ? UPPSALA_CENTER.longitude : undefined,
        radiusKm: radiusKm ? Number(radiusKm) : undefined,
        sort,
        limit: PAGE_SIZE,
        offset,
      }),
    enabled: Boolean(cohortAsOf),
  });
  const signals = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const trackingContext = useMemo(
    () =>
      query.data && activePilotKey
        ? {
            pilot_key: activePilotKey,
            cohort_version: query.data.cohort_version,
            cohort_as_of_date: query.data.cohort_as_of_date,
            dimension_scope_key: query.data.dimension_scope_key,
            score_run_id: query.data.score_run_id,
            score_as_of_date: query.data.score_as_of_date,
            definition_set_hash: query.data.definition_set_hash,
          }
        : null,
    [activePilotKey, query.data],
  );
  const metricsQuery = useQuery({
    queryKey: ["pilot-metrics", trackingContext],
    queryFn: () => getPilotMetrics(trackingContext!),
    enabled: Boolean(trackingContext),
  });
  const shownSignalIds = useMemo(() => signals.map((signal) => signal.id), [signals]);
  const workspaceHref = useMemo(
    () =>
      pilotWorkspaceHref({
        pilotKey: activePilotKey,
        addressQuery,
        strengthBand,
        timeWindow,
        minRooms,
        minArea,
        radiusKm,
        sort,
        reviewStatus,
        showMap,
        offset,
      }),
    [
      activePilotKey,
      addressQuery,
      minArea,
      minRooms,
      offset,
      radiusKm,
      reviewStatus,
      showMap,
      sort,
      strengthBand,
      timeWindow,
    ],
  );

  useEffect(() => {
    const current = `/pilot${window.location.search}`;
    if (current !== workspaceHref) router.replace(workspaceHref, { scroll: false });
  }, [router, workspaceHref]);

  useEffect(() => {
    if (!trackingContext || !shownSignalIds.length) return;
    void recordPilotActivity({
      ...trackingContext,
      activity_type: "SHOWN",
      signal_ids: shownSignalIds,
    })
      .then(() => queryClient.invalidateQueries({ queryKey: ["pilot-metrics"] }))
      .catch(() => undefined);
  }, [queryClient, shownSignalIds, trackingContext]);

  function startPilotSession(event: FormEvent) {
    event.preventDefault();
    const pilotKey = normalizePilotKey(pilotDraft);
    setPilotDraft(pilotKey);
    if (!pilotKey) setReviewStatus("ALL");
    const params = new URLSearchParams(workspaceHref.split("?")[1] ?? "");
    if (pilotKey) params.set("pilot", pilotKey);
    else params.delete("pilot");
    router.replace(params.size ? `/pilot?${params}` : "/pilot", { scroll: false });
  }

  function searchAddresses(event: FormEvent) {
    event.preventDefault();
    const normalized = searchDraft.trim().replace(/\s+/g, " ");
    if (normalized.length === 1) return;
    setSearchDraft(normalized);
    setAddressQuery(normalized);
    setOffset(0);
  }

  function resetPage(action: () => void) {
    action();
    setOffset(0);
  }

  return (
    <>
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
        <PageHeader
          eyebrow="Kommersiell pilot · Uppsala"
          title="Prioriterade flyttmöjligheter"
          description="Ett arbetsurval av färska, förklarbara livesignaler – byggt för att hitta relevanta möjligheter i rätt tid."
          icon={Target}
        />
        {query.data && (
          <Badge variant="success" className="w-fit whitespace-nowrap">
            <span className="mr-1.5 size-1.5 rounded-full bg-success" />
            {query.data.cohort_version} · live
          </Badge>
        )}
      </div>

      <Card className="mt-6 p-4 sm:p-5">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
          <div>
            <div className="label">Pilotsession</div>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
              Ange en pseudonym kod för att mäta visade, öppnade och bedömda signaler. Ingen kod
              betyder intern förhandsvisning utan aktivitetsmätning.
            </p>
          </div>
          <form className="flex w-full gap-2 lg:max-w-md" onSubmit={startPilotSession}>
            <Input
              aria-label="Pilotkod för session"
              value={pilotDraft}
              placeholder="pilot-uppsala-01"
              onChange={(event) => setPilotDraft(event.target.value)}
            />
            <Button type="submit">{activePilotKey ? "Byt kod" : "Starta"}</Button>
          </form>
        </div>
        {activePilotKey && (
          <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4 text-xs text-muted-foreground">
            <Badge variant="success">Mätning aktiv</Badge>
            <span className="font-mono text-foreground">{activePilotKey}</span>
            <span>· Koden identifierar pilotsessionen, inte en person.</span>
          </div>
        )}
      </Card>

      {query.isLoading || cohortQuery.isLoading ? (
        <Loading label="Bygger piloturvalet…" />
      ) : query.error || cohortQuery.error ? (
        <ErrorState error={(query.error ?? cohortQuery.error)!} />
      ) : !query.data || !cohortQuery.data ? null : (
        <>
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Pilotöversikt">
            <MetricCard label="I piloturvalet" value={cohortQuery.data.summary.total} hint="Aktiva livesignaler med annonserad timing" icon={Target} />
            <MetricCard label="Hög prioritet" value={cohortQuery.data.summary.high} hint="Signalstyrka 60 eller högre" icon={Sparkles} tone="emerald" />
            <MetricCard label="Nu–30 dagar" value={cohortQuery.data.summary.next_30_days} hint="Fönstret har startat eller börjar inom 30 dagar" icon={CalendarClock} tone="amber" />
            <MetricCard label="På kartan" value={cohortQuery.data.summary.mapped} hint="Signaler med verifierbara koordinater" icon={MapPinned} tone="violet" />
          </section>

          {trackingContext && (
            <Card className="mt-6 p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div><div className="label">Pilotaktivitet</div><p className="mt-1 text-sm text-muted-foreground">Unika signaler i denna cohort-snapshot</p></div>
                <span className="text-xs text-muted-foreground">{trackingContext.cohort_as_of_date}</span>
              </div>
              <div className="mt-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
                <PilotMetric label="Visade" value={metricsQuery.data?.shown ?? 0} />
                <PilotMetric label="Öppnade" value={metricsQuery.data?.opened ?? 0} />
                <PilotMetric label="Bedömda" value={metricsQuery.data?.reviewed ?? 0} />
                <PilotMetric label="Användbara" value={formatRate(metricsQuery.data?.useful_rate)} />
              </div>
              {metricsQuery.data && metricsQuery.data.reviewed > 0 && (
                <div className="mt-5 border-t border-border pt-4 text-xs text-muted-foreground">
                  <div className="flex flex-wrap gap-2">
                    <Badge variant="success">Användbar {metricsQuery.data.useful}</Badge>
                    <Badge variant="warning">Kanske {metricsQuery.data.maybe}</Badge>
                    <Badge variant="muted">Inte användbar {metricsQuery.data.not_useful}</Badge>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1">
                    {Object.entries(metricsQuery.data.reason_counts).map(([reason, count]) => (
                      <span key={reason}>{humanize(reason)}: <strong className="text-foreground">{count}</strong></span>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          )}

          <Card className="my-6 p-4 sm:p-5">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
              <Field label="Sök adress">
                <form className="flex gap-2" onSubmit={searchAddresses}>
                  <div className="relative min-w-0 flex-1">
                    <Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" />
                    <Input
                      aria-label="Sök gata eller adress"
                      className="pl-9"
                      placeholder="Gata eller adress"
                      value={searchDraft}
                      onChange={(event) => setSearchDraft(event.target.value)}
                    />
                  </div>
                  <Button
                    type="submit"
                    size="sm"
                    disabled={searchDraft.trim().length === 1}
                  >
                    Sök
                  </Button>
                </form>
              </Field>
              <Field label="Prioritet">
              <Select value={strengthBand} onChange={(event) => resetPage(() => setStrengthBand(event.target.value))}>
                  <option value="">Alla nivåer</option>
                  <option value="HIGH">Hög</option>
                  <option value="MEDIUM">Medel</option>
                  <option value="LOW">Låg</option>
                </Select>
              </Field>
              <Field label="Flyttfönster">
                <Select value={timeWindow} onChange={(event) => resetPage(() => setTimeWindow(event.target.value as TimeWindow))}>
                  <option value="ALL">Alla tidpunkter</option>
                  <option value="OPEN">Pågående idag</option>
                  <option value="NEXT_30">Överlappar 0–30 dagar</option>
                  <option value="DAYS_31_60">Överlappar 31–60 dagar</option>
                  <option value="DAYS_61_90">Överlappar 61–90 dagar</option>
                </Select>
              </Field>
              <Field label="Minst rum">
                <Select value={minRooms} onChange={(event) => resetPage(() => setMinRooms(event.target.value))}>
                  <option value="">Alla</option><option value="2">2 rum</option><option value="3">3 rum</option><option value="4">4 rum</option>
                </Select>
              </Field>
              <Field label="Minst yta">
                <Select value={minArea} onChange={(event) => resetPage(() => setMinArea(event.target.value))}>
                  <option value="">Alla</option><option value="40">40 m²</option><option value="60">60 m²</option><option value="80">80 m²</option>
                </Select>
              </Field>
              <Field label="Radie från centrum">
                <Select value={radiusKm} onChange={(event) => resetPage(() => setRadiusKm(event.target.value))}>
                  <option value="">Hela Uppsala</option><option value="5">5 km</option><option value="10">10 km</option><option value="20">20 km</option>
                </Select>
              </Field>
              <Field label="Sortera">
                <Select value={sort} onChange={(event) => resetPage(() => setSort(event.target.value as PilotSort))}>
                  <option value="PRIORITY">Högst prioritet</option>
                  <option value="MOVE_WINDOW">Tidigast tillträde</option>
                  <option value="NEWEST">Nyaste signal</option>
                </Select>
              </Field>
              <Field label="Bedömning">
                <Select
                  value={reviewStatus}
                  disabled={!activePilotKey}
                  onChange={(event) => resetPage(() => setReviewStatus(event.target.value as ReviewStatus))}
                >
                  <option value="ALL">Alla</option>
                  <option value="UNREVIEWED">Obedömda</option>
                  <option value="REVIEWED">Bedömda</option>
                </Select>
              </Field>
              <div className="flex items-end">
                <div className="flex w-full rounded-xl border border-border bg-muted/50 p-1">
                  <Button className="flex-1" size="sm" variant={showMap ? "outline" : "ghost"} onClick={() => setShowMap(true)}><Map className="size-3.5" />Karta</Button>
                  <Button className="flex-1" size="sm" variant={!showMap ? "outline" : "ghost"} onClick={() => setShowMap(false)}><List className="size-3.5" />Lista</Button>
                </div>
              </div>
            </div>
          </Card>

          <div className="mb-4 flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <span><strong className="tabular-nums text-foreground">{pageRange(query.data)}</strong> av {query.data.total} matchande möjligheter</span>
            <span className="text-xs">Tre separata mått – prioritering, inte sannolikhet · urval {query.data.cohort_as_of_date}</span>
          </div>

          {!signals.length ? (
            <Empty title="Inga möjligheter matchar filtren" description="Bredda prioritet, tid eller adressökning." />
          ) : showMap ? (
            <div className="space-y-7">
              <SignalMapWorkspace
                signals={signals}
                detailHref={(signal) => pilotSignalHref(signal.id, query.data, activePilotKey, workspaceHref)}
              />
              <PilotSignalTable signals={signals} context={query.data} pilotKey={activePilotKey} workspaceHref={workspaceHref} />
            </div>
          ) : (
            <PilotSignalTable signals={signals} context={query.data} pilotKey={activePilotKey} workspaceHref={workspaceHref} />
          )}

          {query.data.total > 0 && (
            <div className="mt-5 flex items-center justify-between gap-4">
              <Button
                variant="outline"
                disabled={!query.data.pagination.has_previous || query.isFetching}
                onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
              >
                <ChevronLeft className="size-4" /> Föregående
              </Button>
              <span className="text-xs text-muted-foreground">
                Sida {Math.floor(query.data.pagination.offset / PAGE_SIZE) + 1} av{" "}
                {Math.max(1, Math.ceil(query.data.total / PAGE_SIZE))}
              </span>
              <Button
                variant="outline"
                disabled={!query.data.pagination.has_next || query.isFetching}
                onClick={() => setOffset(offset + PAGE_SIZE)}
              >
                Nästa <ChevronRight className="size-4" />
              </Button>
            </div>
          )}
        </>
      )}
    </>
  );
}

function PilotSignalTable({ signals, context, pilotKey, workspaceHref }: { signals: PilotSignal[]; context: PilotSignalList; pilotKey: string; workspaceHref: string }) {
  return (
    <Card className="overflow-hidden">
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-muted/50 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            <tr><th className="px-5 py-3.5">Möjlighet</th><th className="px-5 py-3.5">Tid</th><th className="px-5 py-3.5">Varför visas den?</th><th className="px-5 py-3.5">Prioritet</th><th className="px-5 py-3.5 text-right">Dimensioner</th></tr>
          </thead>
          <tbody className="divide-y divide-border">
            {signals.map((signal) => (
              <tr key={signal.id} className="group transition hover:bg-white/[0.035]">
                <td className="px-5 py-4">
                  <Link className="inline-flex items-center gap-1.5 font-medium text-foreground hover:text-primary" href={pilotSignalHref(signal.id, context, pilotKey, workspaceHref)}>{signal.property.address}<ArrowUpRight className="size-3.5 opacity-0 transition group-hover:opacity-100" /></Link>
                  <div className="mt-1 text-xs text-muted-foreground">{signal.property.rooms ?? "–"} rum · {signal.property.area_m2 ?? "–"} m² · {humanize(signal.signal_type)}</div>
                </td>
                <td className="px-5 py-4"><div className="text-foreground">{leadTimeLabel(signal.days_until_window_start)}</div><div className="mt-1 text-xs text-muted-foreground">Tillträde {availableFrom(signal) ?? "ej angivet"} · ansökan {applicationDeadline(signal) ?? "ej angivet"}</div></td>
                <td className="max-w-md px-5 py-4"><div className="line-clamp-2 text-foreground">{signal.evidence.slice(0, 2).map((item) => humanize(item.reason)).join(" · ")}</div><div className="mt-1 text-xs text-muted-foreground">{uniqueSources(signal).join(" · ")} · {ageLabel(signal.signal_age_days)}</div></td>
                <td className="px-5 py-4"><div className="space-y-2"><PriorityBadge band={signal.strength_band} />{signal.pilot_feedback && <FeedbackBadge verdict={signal.pilot_feedback.verdict} />}</div></td>
                <td className="px-5 py-4 text-right"><DimensionSummary signal={signal} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="divide-y divide-border md:hidden">
        {signals.map((signal) => (
          <Link key={signal.id} href={pilotSignalHref(signal.id, context, pilotKey, workspaceHref)} className="block p-4 transition active:bg-muted">
            <div className="flex items-start justify-between gap-3"><div><div className="font-medium text-foreground">{signal.property.address}</div><div className="mt-1 text-xs text-muted-foreground">{leadTimeLabel(signal.days_until_window_start)} · tillträde {availableFrom(signal) ?? "ej angivet"}</div></div><div className="flex flex-col items-end gap-2"><PriorityBadge band={signal.strength_band} />{signal.pilot_feedback && <FeedbackBadge verdict={signal.pilot_feedback.verdict} />}</div></div>
            <p className="mt-4 line-clamp-2 text-sm leading-6 text-muted-foreground">{signal.evidence.slice(0, 2).map((item) => humanize(item.reason)).join(" · ")}</p>
            <div className="mt-3 flex items-end justify-between gap-3 text-xs text-muted-foreground"><span>{uniqueSources(signal).join(" · ")} · {ageLabel(signal.signal_age_days)}</span><DimensionSummary signal={signal} /></div>
          </Link>
        ))}
      </div>
    </Card>
  );
}

function PriorityBadge({ band }: { band: PilotSignal["strength_band"] }) {
  const variant = band === "HIGH" ? "success" : band === "MEDIUM" ? "warning" : "muted";
  const label = band === "HIGH" ? "Hög" : band === "MEDIUM" ? "Medel" : "Låg";
  return <Badge variant={variant}>{label}</Badge>;
}

function FeedbackBadge({ verdict }: { verdict: NonNullable<PilotSignal["pilot_feedback"]>["verdict"] }) {
  const label = verdict === "USEFUL" ? "Användbar" : verdict === "MAYBE" ? "Kanske" : "Inte användbar";
  return <Badge variant="muted">Bedömd · {label}</Badge>;
}

function DimensionSummary({ signal }: { signal: PilotSignal }) {
  const dimensions = signal.active_dimensions;
  return (
    <div className="inline-grid min-w-[116px] grid-cols-3 gap-3 text-center text-[10px] text-muted-foreground">
      <span><span className="block font-semibold tabular-nums text-primary">{dimensions.signal_strength}</span>styrka</span>
      <span className={dimensions.data_confidence < 40 ? "text-warning" : undefined}><span className="block font-semibold tabular-nums">{dimensions.data_confidence}</span>tillit</span>
      <span><span className="block font-semibold tabular-nums text-primary">{dimensions.timing}</span>timing</span>
    </div>
  );
}

function uniqueSources(signal: PilotSignal) {
  return [...new Set(signal.evidence.map((item) => item.source))];
}

function leadTimeLabel(days: number) {
  if (days < 0) return `Fönstret öppnade för ${Math.abs(days)} dagar sedan`;
  if (days === 0) return "Fönstret öppnar idag";
  return `Fönstret öppnar om ${days} dagar`;
}

function ageLabel(days: number) {
  return days === 1 ? "1 dag gammal" : `${days} dagar gammal`;
}

function pilotDateRange(window: TimeWindow, asOf?: string) {
  if (!asOf) return {};
  const [year, month, day] = asOf.split("-").map(Number);
  const anchor = new Date(Date.UTC(year, month - 1, day));
  const iso = (days: number) => {
    const date = new Date(anchor);
    date.setUTCDate(date.getUTCDate() + days);
    return date.toISOString().slice(0, 10);
  };
  if (window === "OPEN") return { to: iso(0) };
  if (window === "NEXT_30") return { from: iso(0), to: iso(30) };
  if (window === "DAYS_31_60") return { from: iso(31), to: iso(60) };
  if (window === "DAYS_61_90") return { from: iso(61), to: iso(90) };
  return {};
}

function pageRange(context: PilotSignalList) {
  if (!context.count) return "0";
  const first = context.pagination.offset + 1;
  const last = context.pagination.offset + context.count;
  return `${first}–${last}`;
}

function pilotSignalHref(
  signalId: string,
  context: PilotSignalList,
  pilotKey: string,
  workspaceHref: string,
) {
  const params = new URLSearchParams({
    from: "pilot",
    cohort: context.cohort_version,
    cohort_as_of: context.cohort_as_of_date,
    dimension_scope: context.dimension_scope_key,
    score_run: context.score_run_id,
    score_as_of: context.score_as_of_date,
    definition_set: context.definition_set_hash,
  });
  if (pilotKey) params.set("pilot", pilotKey);
  params.set("return_to", workspaceHref);
  return `/signals/${signalId}?${params}`;
}

function normalizeAddressQuery(value: string) {
  const normalized = value.trim().replace(/\s+/g, " ");
  return normalized.length === 1 ? "" : normalized;
}

function choice<const T extends string>(value: string | null, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback;
}

function pageOffset(value: string | null) {
  const page = Number(value);
  return Number.isInteger(page) && page > 1 ? (page - 1) * PAGE_SIZE : 0;
}

function pilotWorkspaceHref(state: {
  pilotKey: string;
  addressQuery: string;
  strengthBand: string;
  timeWindow: TimeWindow;
  minRooms: string;
  minArea: string;
  radiusKm: string;
  sort: PilotSort;
  reviewStatus: ReviewStatus;
  showMap: boolean;
  offset: number;
}) {
  const params = new URLSearchParams();
  if (state.pilotKey) params.set("pilot", state.pilotKey);
  if (state.addressQuery) params.set("q", state.addressQuery);
  if (state.strengthBand) params.set("priority", state.strengthBand);
  if (state.timeWindow !== "ALL") params.set("window", state.timeWindow);
  if (state.minRooms) params.set("rooms", state.minRooms);
  if (state.minArea) params.set("area", state.minArea);
  if (state.radiusKm) params.set("radius", state.radiusKm);
  if (state.sort !== "PRIORITY") params.set("sort", state.sort);
  if (state.reviewStatus !== "ALL") params.set("review", state.reviewStatus);
  if (!state.showMap) params.set("view", "list");
  if (state.offset) params.set("page", String(Math.floor(state.offset / PAGE_SIZE) + 1));
  return params.size ? `/pilot?${params}` : "/pilot";
}

function formatRate(value: number | null | undefined) {
  return value === null || value === undefined ? "–" : `${Math.round(value * 100)} %`;
}

function PilotMetric({ label, value }: { label: string; value: string | number }) {
  return <div className="rounded-xl border border-border bg-muted/50 p-4"><div className="label">{label}</div><div className="mt-2 text-2xl font-semibold tabular-nums text-foreground">{value}</div></div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><span className="label mb-2 block">{label}</span>{children}</div>;
}
