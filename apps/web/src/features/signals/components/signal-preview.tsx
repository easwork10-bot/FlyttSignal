import { ArrowUpRight, Building2, CalendarRange, Layers3, MapPin, type LucideIcon } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import type { Signal } from "@/lib/api/types";
import { cn, humanize } from "@/lib/utils";
import { applicationDeadline, availableFrom } from "@/features/signals/timing";

export function SignalPreview({ signal, onClose, detailHref }: { signal: Signal | null; onClose?: () => void; detailHref?: string }) {
  if (!signal) {
    return (
      <Card className="flex min-h-56 flex-col items-center justify-center p-7 text-center lg:min-h-full">
        <span className="grid size-12 place-items-center rounded-2xl bg-muted text-muted-foreground"><MapPin className="size-5" /></span>
        <h3 className="mt-4 font-medium text-foreground">Välj en signal på kartan</h3>
        <p className="mt-2 max-w-xs text-sm leading-6 text-muted-foreground">Markören och detaljpanelen är kopplade till samma signaldata.</p>
      </Card>
    );
  }

  return (
    <Card className="relative flex min-h-full flex-col overflow-hidden p-6">
      {onClose && <Button variant="ghost" size="sm" className="absolute right-3 top-3 lg:hidden" onClick={onClose}>Stäng</Button>}
      <div className="flex items-center justify-between gap-4 pr-12 lg:pr-0">
        <Badge variant={signal.active_dimensions.signal_strength >= 60 ? "success" : "warning"}>{signal.status === "ACTIVE" ? "Aktiv signal" : humanize(signal.status)}</Badge>
        <span className="score">{signal.active_dimensions.signal_strength}/100</span>
      </div>
      <h3 className="mt-6 text-xl font-semibold tracking-tight text-foreground">{signal.property.address}</h3>
      <p className="mt-1 text-sm text-muted-foreground">{signal.property.city} · {humanize(signal.property.property_type)}</p>

      <dl className="mt-6 grid grid-cols-2 gap-3">
        <Fact icon={Building2} label="Yta / rum" value={`${signal.property.area_m2 ?? "–"} m² · ${signal.property.rooms ?? "–"} rum`} />
        <Fact icon={Layers3} label="Evidens" value={`${signal.evidence_count} händelser`} />
        <Fact icon={CalendarRange} label="Tillgänglig från" value={availableFrom(signal) ?? "Ej angivet"} />
        <Fact icon={CalendarRange} label="Ansökan stänger" value={applicationDeadline(signal) ?? "Ej angivet"} />
      </dl>

      <div className="mt-auto pt-7">
        <div className="mb-4 grid grid-cols-2 gap-2 text-xs text-muted-foreground"><span>Datatillit {signal.active_dimensions.data_confidence}/100</span><span>Timing {signal.active_dimensions.timing}/100</span></div>
        <p className="mb-4 text-sm leading-6 text-muted-foreground">{humanize(signal.signal_type)}. Signalstyrka är prioritering – inte sannolikhet.</p>
        <Link href={detailHref ?? `/signals/${signal.id}`} className={cn(buttonVariants(), "w-full")}>Öppna signaldetalj <ArrowUpRight className="size-4" /></Link>
      </div>
    </Card>
  );
}

function Fact({ icon: Icon, label, value }: { icon: LucideIcon; label: string; value: string }) {
  return <div className="rounded-xl border border-border bg-muted/60 p-3"><Icon className="mb-3 size-4 text-primary" /><dt className="label">{label}</dt><dd className="mt-1 text-sm font-medium text-foreground">{value}</dd></div>;
}
