import { Building2, Database, MapPinned, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { AddressEnrichment } from "@/lib/api/types";
import { formatDate } from "@/lib/utils";

type Props = { enrichments: AddressEnrichment[] };

export function LantmaterietEnrichmentCard({ enrichments }: Props) {
  const enrichment = enrichments.find((item) => item.source.includes("Lantmäteriet"));

  if (!enrichment) {
    return (
      <Card className="overflow-hidden">
        <div className="p-6">
          <div className="flex items-start justify-between gap-4">
            <Heading />
            <Badge variant="muted">Inte verifierad</Badge>
          </div>
          <p className="mt-5 text-sm leading-6 text-muted-foreground">
            Ingen adressberikning från Lantmäteriet är lagrad för fastigheten ännu.
          </p>
        </div>
      </Card>
    );
  }

  const isLive = enrichment.data_mode === "live";
  const registerUnit = enrichment.register_unit;
  const postAddress = [enrichment.postal_code, enrichment.postal_town]
    .filter(Boolean)
    .join(" ");

  return (
    <Card className="overflow-hidden border-primary/20">
      <div className="p-6">
        <div className="flex items-start justify-between gap-4">
          <Heading />
          <Badge variant={isLive ? "success" : "warning"}>
            {isLive ? "Verifierad livedata" : "Testdata"}
          </Badge>
        </div>

        <div className="mt-5 rounded-xl border border-primary/15 bg-primary/5 p-4">
          <div className="flex gap-3">
            <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" />
            <div>
              <div className="text-sm font-medium text-foreground">
                {enrichment.canonical_address}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {postAddress || "Postuppgift saknas"} · {enrichment.status}
              </div>
            </div>
          </div>
        </div>

        <dl className="mt-5 space-y-4">
          <Fact
            icon={Building2}
            label="Registerenhet"
            value={
              registerUnit
                ? `${registerUnit.designation} · ${registerUnit.register_unit_type}`
                : "Ingen registerenhet returnerad"
            }
          />
          <Fact
            icon={MapPinned}
            label={`Koordinat · EPSG:${enrichment.source_srid}`}
            value={`${formatCoordinate(enrichment.source_northing)}, ${formatCoordinate(enrichment.source_easting)}`}
          />
          <Fact
            icon={Database}
            label="Senast behandlad"
            value={formatDate(enrichment.updated_at, true)}
          />
        </dl>
      </div>

      <div className="border-t border-border bg-muted/50 px-6 py-4 text-[11px] leading-5 text-muted-foreground">
        {enrichment.attribution}
      </div>
    </Card>
  );
}

function Heading() {
  return (
    <div>
      <div className="label">Adress- och fastighetskoppling</div>
      <h2 className="mt-1 font-semibold text-foreground">Lantmäteriet</h2>
    </div>
  );
}

function Fact({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof Building2;
  label: string;
  value: string;
}) {
  return (
    <div className="flex gap-3">
      <Icon className="mt-0.5 size-4 shrink-0 text-primary" />
      <div className="min-w-0">
        <dt className="label">{label}</dt>
        <dd className="mt-1 break-words text-sm text-foreground">{value}</dd>
      </div>
    </div>
  );
}

function formatCoordinate(value: string) {
  return new Intl.NumberFormat("sv-SE", { maximumFractionDigits: 3 }).format(Number(value));
}
