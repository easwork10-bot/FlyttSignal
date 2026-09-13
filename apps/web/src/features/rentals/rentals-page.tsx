"use client";

import { useQuery } from "@tanstack/react-query";
import { Building2, CalendarClock, ExternalLink, House, WalletCards } from "lucide-react";

import { PageHeader } from "@/components/page-header";
import { Empty, ErrorState, Loading } from "@/components/states";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { getRentalListings } from "@/lib/api/rentals";
import { formatDate } from "@/lib/utils";

const kronor = new Intl.NumberFormat("sv-SE", { maximumFractionDigits: 0 });

export function RentalsPage() {
  const query = useQuery({ queryKey: ["rental-listings"], queryFn: getRentalListings });
  if (query.isLoading) return <Loading label="Hämtar hyresrätter…" />;
  if (query.error) return <ErrorState error={query.error} />;
  const items = query.data?.items ?? [];

  return (
    <>
      <PageHeader
        eyebrow="Observerade annonser"
        title="Hyresrätter i Uppsala"
        description="Publiceringskanal och faktisk hyresvärd hålls isär. Fixture-data är tydligt märkt och påverkar inte källoberoendet felaktigt."
        icon={Building2}
      />
      {!items.length ? <Empty title="Inga aktiva hyresrätter" /> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {items.map((item) => (
            <Card key={item.id} className="p-5 sm:p-6">
              <div className="flex items-start justify-between gap-4">
                <div><h2 className="text-lg font-semibold text-foreground">{item.property.address}</h2><p className="mt-1 text-sm text-muted-foreground">{item.upstream_provider_name} · via {item.publisher}</p></div>
                <Badge variant={item.data_mode === "live" ? "success" : "warning"}>{item.data_mode === "live" ? "Live" : "Fixture"}</Badge>
              </div>
              <div className="mt-5 grid gap-3 text-sm sm:grid-cols-3">
                <Fact icon={House} label="Storlek" value={[item.property.rooms && `${item.property.rooms} rum`, item.property.area_m2 && `${item.property.area_m2} m²`].filter(Boolean).join(" · ") || "Saknas"} />
                <Fact icon={WalletCards} label="Hyra" value={item.monthly_rent ? `${kronor.format(Number(item.monthly_rent))} kr/mån` : "Saknas"} />
                <Fact icon={CalendarClock} label="Sök senast" value={formatDate(item.application_deadline)} />
              </div>
              <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
                <div className="flex flex-wrap gap-2">{item.categories.map((category) => <Badge key={category}>{category}</Badge>)}</div>
                {item.canonical_url && <a className="inline-flex items-center gap-1.5 text-sm text-primary hover:text-primary/80" href={item.canonical_url} target="_blank" rel="noreferrer">Öppna källa <ExternalLink className="size-3.5" /></a>}
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}

function Fact({ icon: Icon, label, value }: { icon: typeof House; label: string; value: string }) {
  return <div className="rounded-xl border border-border bg-muted/50 p-3"><div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-foreground"><Icon className="size-3.5" />{label}</div><div className="mt-2 text-foreground">{value}</div></div>;
}
