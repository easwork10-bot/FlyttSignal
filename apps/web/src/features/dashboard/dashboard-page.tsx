"use client";

import { Activity, ArrowRight, CalendarClock, RadioTower } from "lucide-react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";

import { MetricCard } from "@/components/metric-card";
import { PageHeader } from "@/components/page-header";
import { Empty, ErrorState, Loading } from "@/components/states";
import { buttonVariants } from "@/components/ui/button";
import { SignalMapWorkspace } from "@/features/signals/components/signal-map-workspace";
import { getMapCoordinate } from "@/features/signals/components/signal-map-data";
import { SignalTable } from "@/features/signals/components/signal-table";
import { getSignals } from "@/lib/api/signals";
import { cn } from "@/lib/utils";
import { availableFrom } from "@/features/signals/timing";

export function DashboardPage() {
  const query = useQuery({ queryKey: ["signals", "dashboard"], queryFn: () => getSignals() });
  if (query.isLoading) return <Loading />;
  if (query.error) return <ErrorState error={query.error} />;

  const items = query.data?.items ?? [];
  const now = new Date();
  const inThirtyDays = new Date(now);
  inThirtyDays.setDate(now.getDate() + 30);
  const mapped = items.filter((signal) => getMapCoordinate(signal));

  return (
    <>
      <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
        <PageHeader eyebrow="Operativ översikt" title="FlyttRadar / Uppsala" description="Prioriterade och spårbara indikationer om kommande flyttar." icon={Activity} />
        <Link href="/signals" className={cn(buttonVariants({ variant: "outline" }), "mb-7 w-fit lg:mb-9")}>Utforska alla signaler <ArrowRight className="size-4" /></Link>
      </div>

      <section aria-label="Nyckeltal" className="mb-9 grid gap-4 sm:grid-cols-3">
        <MetricCard label="Aktiva signaler" value={items.filter((signal) => signal.status === "ACTIVE").length} hint="Alla aktiva inferenser" icon={RadioTower} />
        <MetricCard label="Starka signaler" value={items.filter((signal) => signal.active_dimensions.signal_strength >= 60).length} hint="Signalstyrka 60 eller högre" icon={Activity} tone="emerald" />
        <MetricCard label="Tillgängliga inom 30 dagar" value={items.filter((signal) => { const date = availableFrom(signal); return date && new Date(date) >= now && new Date(date) <= inThirtyDays; }).length} hint="Annonserat tillträde" icon={CalendarClock} tone="amber" />
      </section>

      <section className="mb-10">
        <div className="mb-4 flex items-end justify-between"><div><div className="label">Geografisk lägesbild</div><h2 className="mt-1 text-xl font-semibold tracking-tight">Signaler på kartan</h2></div><span className="hidden text-xs text-muted-foreground sm:block">Klicka på en markör för detaljer</span></div>
        {mapped.length ? <SignalMapWorkspace signals={items} compact /> : <Empty title="Inga koordinatsatta signaler" />}
      </section>

      <section>
        <div className="mb-4 flex items-end justify-between"><div><div className="label">Senaste observationer</div><h2 className="mt-1 text-xl font-semibold tracking-tight">Prioriterade signaler</h2></div><Link href="/signals" className="text-sm font-medium text-primary hover:text-primary/80">Visa alla</Link></div>
        {items.length ? <SignalTable signals={items.slice(0, 8)} /> : <Empty />}
      </section>
    </>
  );
}
