"use client";

import { Building2, CheckCircle2, Clock3, Database, FilePlus2, RefreshCw, TriangleAlert } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "@/components/page-header";
import { ErrorState, Loading } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { ProviderCoverage } from "@/features/sources/components/provider-coverage";
import { SpatialContext } from "@/features/sources/components/spatial-context";
import { getHousingProviders, getRentalCoverage, getRentalProjects, getSourceRuns, getSources, getSpatialFeatures } from "@/lib/api/sources";
import { formatDate, humanize } from "@/lib/utils";

export function SourcesPage() {
  const sources = useQuery({ queryKey: ["sources"], queryFn: getSources, refetchInterval: 30_000 });
  const runs = useQuery({ queryKey: ["source-runs"], queryFn: getSourceRuns, refetchInterval: 30_000 });
  const spatial = useQuery({ queryKey: ["spatial-features"], queryFn: getSpatialFeatures, refetchInterval: 30_000 });
  const providers = useQuery({ queryKey: ["housing-providers"], queryFn: getHousingProviders });
  const coverage = useQuery({ queryKey: ["rental-coverage"], queryFn: getRentalCoverage, refetchInterval: 30_000 });
  const projects = useQuery({ queryKey: ["rental-projects"], queryFn: getRentalProjects, refetchInterval: 30_000 });
  if (sources.isLoading || runs.isLoading || spatial.isLoading || providers.isLoading || coverage.isLoading || projects.isLoading) return <Loading label="Kontrollerar källhälsa…" />;
  if (sources.error) return <ErrorState error={sources.error} />;
  if (runs.error) return <ErrorState error={runs.error} />;
  if (spatial.error) return <ErrorState error={spatial.error} />;
  if (providers.error) return <ErrorState error={providers.error} />;
  if (coverage.error) return <ErrorState error={coverage.error} />;
  if (projects.error) return <ErrorState error={projects.error} />;

  return (
    <>
      <PageHeader eyebrow="Driftövervakning" title="Källhälsa" description="Senaste insamlingskörning, schemaläggning och felstatus per adapter." icon={Database} />
      <div className="grid gap-5">
        {sources.data?.map((source) => {
          const run = runs.data?.find((item) => item.source_id === source.id);
          const healthy = source.status === "HEALTHY";
          return (
            <Card className="overflow-hidden" key={source.id}>
              <div className="flex flex-col justify-between gap-4 border-b border-border p-5 sm:flex-row sm:items-start sm:p-6">
                <div className="flex gap-4"><span className={`grid size-11 shrink-0 place-items-center rounded-xl border ${healthy ? "border-success/20 bg-success/10 text-success" : "border-warning/20 bg-warning/10 text-warning"}`}>{healthy ? <CheckCircle2 className="size-5" /> : <TriangleAlert className="size-5" />}</span><div><h2 className="text-lg font-semibold text-foreground">{source.name}</h2><p className="mt-1 text-sm text-muted-foreground">{humanize(source.source_type)} · {source.scope} · {humanize(source.access_method)}</p></div></div>
                <Badge variant={healthy ? "success" : "warning"}>{healthy ? "Frisk" : humanize(source.status)}</Badge>
              </div>
              <div className="grid gap-px bg-white/[0.06] sm:grid-cols-2 lg:grid-cols-5 xl:grid-cols-10">
                <Metric icon={Clock3} label="Senaste körning" value={formatDate(source.last_run_at, true)} />
                <Metric icon={RefreshCw} label="Nästa körning" value={formatDate(source.next_run_at, true)} />
                <Metric icon={Clock3} label="Intervall" value={`${source.poll_interval_minutes} min`} />
                <Metric icon={Database} label="Sedda" value={run?.items_seen ?? 0} />
                <Metric icon={FilePlus2} label="Nya" value={run?.items_new ?? 0} />
                <Metric icon={RefreshCw} label="Ändrade" value={run?.items_changed ?? 0} />
                <Metric icon={CheckCircle2} label="Oförändrade" value={run?.items_unchanged ?? 0} />
                <Metric icon={TriangleAlert} label="Borttagna" value={run?.items_removed ?? 0} />
                <Metric icon={Clock3} label="Tid" value={run?.duration_ms == null ? "—" : `${run.duration_ms} ms`} />
                <Metric icon={TriangleAlert} label="Fel" value={run?.error_message ? 1 : 0} alert={Boolean(run?.error_message)} />
              </div>
            </Card>
          );
        })}
        <Card className="p-5 sm:p-6"><div className="mb-4 flex items-center gap-3"><span className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary"><Building2 className="size-5" /></span><div><div className="label">HomeQ-projekt</div><h2 className="mt-1 text-lg font-semibold">Projekt och verkligt importerade objekt</h2></div></div><div className="grid gap-3 lg:grid-cols-2">{projects.data?.items.map((project) => <a key={project.id} href={project.canonical_url} target="_blank" rel="noreferrer" className="rounded-xl border border-border bg-muted/40 p-4 hover:border-primary/30"><div className="flex items-start justify-between gap-3"><div><div className="font-semibold text-foreground">{project.name}</div><div className="mt-1 text-sm text-muted-foreground">{project.address} · {project.upstream_provider_name}</div></div><Badge variant={project.active_listing_count === project.imported_listing_count ? "success" : "warning"}>{project.imported_listing_count}/{project.active_listing_count} importerade</Badge></div><div className="mt-3 text-xs text-muted-foreground">{project.planned_unit_count ?? "—"} planerade bostäder · inflytt {formatDate(project.available_from)}</div></a>)}</div></Card>
        <SpatialContext features={spatial.data?.items ?? []} />
      </div>
      <ProviderCoverage providers={providers.data?.items ?? []} coverage={coverage.data!} />
    </>
  );
}

function Metric({ icon: Icon, label, value, alert = false }: { icon: typeof Clock3; label: string; value: string | number; alert?: boolean }) {
  return <div className="rounded-lg bg-muted/50 p-4"><div className="flex items-center gap-2 text-muted-foreground"><Icon className="size-3.5" /><span className="label">{label}</span></div><div className={`mt-2 text-sm font-medium ${alert ? "text-destructive" : "text-foreground"}`}>{value}</div></div>;
}
