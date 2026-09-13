import { ArrowUpRight, Building2, CalendarDays, Layers3 } from "lucide-react";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { Signal } from "@/lib/api/types";
import { humanize } from "@/lib/utils";
import { availableFrom } from "@/features/signals/timing";

export function SignalTable({ signals }: { signals: Signal[] }) {
  return (
    <Card className="overflow-hidden">
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-border bg-muted/60 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
            <tr><th className="px-5 py-3.5">Fastighet</th><th className="px-5 py-3.5">Signal</th><th className="px-5 py-3.5">Flyttfönster</th><th className="px-5 py-3.5">Evidens</th><th className="px-5 py-3.5 text-right">Signalstyrka</th></tr>
          </thead>
          <tbody className="divide-y divide-border">
            {signals.map((signal) => (
              <tr key={signal.id} className="group transition hover:bg-muted/50">
                <td className="px-5 py-4">
                  <Link className="inline-flex items-center gap-1.5 font-medium text-foreground hover:text-primary" href={`/signals/${signal.id}`}>{signal.property.address}<ArrowUpRight className="size-3.5 opacity-0 transition group-hover:opacity-100" /></Link>
                  <div className="mt-1 text-xs text-muted-foreground">{signal.property.area_m2 ? `${signal.property.area_m2} m²` : "Yta saknas"}{signal.property.unit_identifier ? ` · lgh ${signal.property.unit_identifier}` : ""}</div>
                </td>
                <td className="px-5 py-4"><Badge variant="muted">{humanize(signal.signal_type)}</Badge></td>
                <td className="px-5 py-4 text-muted-foreground"><span className="whitespace-nowrap">{availableFrom(signal) ?? "Okänt"}</span></td>
                <td className="px-5 py-4 tabular-nums text-muted-foreground">{signal.evidence_count}</td>
                <td className="px-5 py-4 text-right"><span className="score">{signal.active_dimensions.signal_strength}/100</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="divide-y divide-border md:hidden">
        {signals.map((signal) => (
          <Link key={signal.id} href={`/signals/${signal.id}`} className="block p-4 transition active:bg-muted/60">
            <div className="flex items-start justify-between gap-3"><div><div className="font-medium text-foreground">{signal.property.address}</div><div className="mt-1 text-xs text-muted-foreground">{humanize(signal.signal_type)}</div></div><span className="score text-xs">{signal.active_dimensions.signal_strength}/100</span></div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
              <span className="flex items-center gap-1.5"><Building2 className="size-3.5" />{signal.property.area_m2 ?? "–"} m²</span>
              <span className="flex items-center gap-1.5"><Layers3 className="size-3.5" />{signal.evidence_count} evidens</span>
              <span className="flex items-center gap-1.5"><CalendarDays className="size-3.5" />{availableFrom(signal) ?? "Okänt"}</span>
            </div>
          </Link>
        ))}
      </div>
    </Card>
  );
}
