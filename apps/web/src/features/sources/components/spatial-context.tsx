import { Building2, MapPinned, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { SpatialFeature } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

export function SpatialContext({ features }: { features: SpatialFeature[] }) {
  const attribution = features[0]?.attribution ?? "Uppsala kommun, Öppna data";

  return (
    <Card className="overflow-hidden">
      <div className="flex flex-col justify-between gap-4 border-b border-border p-5 sm:flex-row sm:items-start sm:p-6">
        <div className="flex gap-4">
          <span className="grid size-11 shrink-0 place-items-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
            <MapPinned className="size-5" />
          </span>
          <div>
            <div className="label">Kommunal byggkontext</div>
            <h2 className="mt-1 text-lg font-semibold text-foreground">Uppsala Open Data — Byggnader</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-muted-foreground">
              Geografiska byggnadsobservationer med spårbar proveniens. De ger kontext men är inte bevis på en flytt.
            </p>
          </div>
        </div>
        <Badge variant="muted">Poängneutral</Badge>
      </div>

      {features.length ? (
        <div className="grid gap-px bg-border lg:grid-cols-3">
          {features.map((feature) => (
            <div className="bg-muted/40 p-5" key={feature.id}>
              <div className="flex items-start justify-between gap-3">
                <span className="grid size-9 place-items-center rounded-lg bg-primary/10 text-primary">
                  <Building2 className="size-4" />
                </span>
                <Badge variant={feature.data_mode === "live" ? "success" : "muted"}>
                  {feature.data_mode === "live" ? "Verifierad livedata" : "Testdata"}
                </Badge>
              </div>
              <div className="mt-4 font-medium text-foreground">{feature.subtype_label}</div>
              <div className="mt-1 text-sm text-muted-foreground">
                {feature.activity_label ?? "Ingen registrerad aktivitet"} · {feature.status_label}
              </div>
              <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground">
                <ShieldCheck className="size-3.5" />
                <span>
                  {feature.is_baseline ? "Säker baseline" : "Ändrad efter baseline"} · {formatDate(feature.source_modified_at, true)}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="p-6 text-sm text-muted-foreground">
          Ingen fixture-baseline har lagrats ännu. Livekällan är fortsatt avstängd.
        </div>
      )}

      <div className="border-t border-border px-5 py-3 text-xs text-muted-foreground">
        Källa: {attribution}. Kontexten påverkar inte signaldimensionerna.
      </div>
    </Card>
  );
}
