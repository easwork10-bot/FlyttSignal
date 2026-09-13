import { Building2, ExternalLink, Network } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { HousingProvider, RentalCoverage } from "@/lib/api/types";
import { humanize } from "@/lib/utils";

export function ProviderCoverage({ providers, coverage }: { providers: HousingProvider[]; coverage: RentalCoverage }) {
  const liveByKey = new Map(coverage.providers.map((provider) => [provider.key, provider]));
  return (
    <section className="mt-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div><div className="label">Marknadstäckning</div><h2 className="mt-1 text-xl font-semibold">Hyresvärdar och distributionskanaler</h2></div>
        <div className="text-sm text-muted-foreground"><span className="font-semibold text-foreground">{coverage.represented_known_provider_count}/{coverage.known_provider_count}</span> har objekt i faktisk liveinventering · {coverage.observed_provider_count} observerade totalt</div>
      </div>
      <div className="grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
        {providers.map((provider) => {
          const live = liveByKey.get(provider.key);
          return (
          <Card key={provider.id} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="flex gap-3"><span className="grid size-9 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary"><Building2 className="size-4" /></span><div><a href={provider.official_url} target="_blank" rel="noreferrer" className="font-semibold text-foreground hover:text-primary">{provider.name}</a><p className="mt-1 text-xs text-muted-foreground">{humanize(provider.provider_type)}</p></div></div>
              <div className="flex items-center gap-2"><Badge variant={live?.live_listing_count ? "success" : "warning"}>{live?.live_listing_count ?? 0} live</Badge><a href={provider.evidence_url} target="_blank" rel="noreferrer" title="Täckningskälla"><ExternalLink className="size-4 text-muted-foreground hover:text-primary" /></a></div>
            </div>
            <div className="mt-4 space-y-2">
              {provider.channels.map((channel) => {
                const nextAction = channel.next_action;
                return <div key={channel.channel_key} className="rounded-lg border border-border bg-muted/40 px-3 py-2">
                  <a href={channel.url} target="_blank" rel="noreferrer" className="flex items-center justify-between gap-3 hover:text-primary">
                    <span className="flex min-w-0 items-center gap-2 text-sm text-foreground"><Network className="size-3.5 shrink-0 text-muted-foreground" /><span className="truncate">{channel.publisher_name}</span></span>
                    <Badge variant={channel.requires_auth || channel.requires_agreement ? "warning" : channel.source_key ? "success" : "default"}>{humanize(channel.collection_status)}</Badge>
                  </a>
                  {nextAction ? <p className="mt-2 text-xs leading-5 text-muted-foreground">{nextAction}</p> : null}
                </div>;
              })}
            </div>
            {live?.gap_reason ? <p className="mt-3 text-xs leading-5 text-warning">{live.gap_reason}</p> : null}
          </Card>
        )})}
      </div>
      {coverage.providers.some((provider) => !provider.known_provider) ? <div className="mt-4 rounded-xl border border-primary/20 bg-primary/5 p-4 text-sm text-foreground">Liveupptäckta hyresvärdar utanför katalogen: {coverage.providers.filter((provider) => !provider.known_provider).map((provider) => `${provider.name} (${provider.live_listing_count})`).join(", ")}</div> : null}
    </section>
  );
}
