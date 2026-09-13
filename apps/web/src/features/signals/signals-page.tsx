"use client";

import { List, Map, RotateCcw, Search, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "@/components/page-header";
import { Empty, ErrorState, Loading } from "@/components/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { SignalMapWorkspace } from "@/features/signals/components/signal-map-workspace";
import { SignalTable } from "@/features/signals/components/signal-table";
import { getCities } from "@/lib/api/cities";
import { getSignals } from "@/lib/api/signals";

export function SignalsPage() {
  const [minStrength, setMinStrength] = useState(0);
  const [type, setType] = useState("");
  const [city, setCity] = useState(1);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [search, setSearch] = useState("");
  const [showMap, setShowMap] = useState(true);
  const query = useQuery({
    queryKey: ["signals", minStrength, type, city, from, to],
    queryFn: () => getSignals({ minStrength, signalType: type || undefined, cityId: city, from: from || undefined, to: to || undefined }),
  });
  const cities = useQuery({ queryKey: ["cities"], queryFn: getCities });
  const items = useMemo(() => {
    const all = query.data?.items ?? [];
    const needle = search.trim().toLocaleLowerCase("sv");
    return needle ? all.filter((signal) => signal.property.address.toLocaleLowerCase("sv").includes(needle)) : all;
  }, [query.data?.items, search]);

  const reset = () => { setMinStrength(0); setType(""); setCity(1); setFrom(""); setTo(""); setSearch(""); };

  return (
    <>
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <PageHeader eyebrow="Signalregister" title="Flyttsignaler" description="Filtrera, jämför och öppna evidensen bakom varje signal." icon={SlidersHorizontal} />
        <div className="mb-7 flex w-fit rounded-xl border border-border bg-card p-1 shadow-sm sm:mb-9">
          <Button size="sm" variant={showMap ? "outline" : "ghost"} onClick={() => setShowMap(true)}><Map className="size-3.5" />Karta</Button>
          <Button size="sm" variant={!showMap ? "outline" : "ghost"} onClick={() => setShowMap(false)}><List className="size-3.5" />Lista</Button>
        </div>
      </div>

      <Card className="mb-6 p-4 sm:p-5">
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
          <Field label="Sök adress" className="xl:col-span-2"><div className="relative"><Search className="pointer-events-none absolute left-3 top-3 size-4 text-muted-foreground" /><Input className="pl-9" placeholder="Exempelvis Testgatan" value={search} onChange={(event) => setSearch(event.target.value)} /></div></Field>
          <Field label="Minsta signalstyrka"><Input type="number" min="0" max="100" value={minStrength} onChange={(event) => setMinStrength(Number(event.target.value))} /></Field>
          <Field label="Signaltyp"><Select value={type} onChange={(event) => setType(event.target.value)}><option value="">Alla typer</option><option value="POTENTIAL_RENTAL_TENANCY_CHANGE">Möjlig förändring av hyresgäst</option><option value="POTENTIAL_NEW_BUILD_MOVE_IN">Möjlig inflyttning i nyproduktion</option></Select></Field>
          <Field label="Stad"><Select value={city} onChange={(event) => setCity(Number(event.target.value))}>{cities.data?.map((item) => <option value={item.id} key={item.id}>{item.name}</option>)}</Select></Field>
          <div className="flex items-end"><Button variant="ghost" className="w-full" onClick={reset}><RotateCcw className="size-4" />Återställ</Button></div>
          <Field label="Från"><Input type="date" value={from} onChange={(event) => setFrom(event.target.value)} /></Field>
          <Field label="Till"><Input type="date" value={to} onChange={(event) => setTo(event.target.value)} /></Field>
        </div>
      </Card>

      <div className="mb-4 flex items-center justify-between"><div className="text-sm text-muted-foreground"><span className="font-semibold tabular-nums text-foreground">{items.length}</span> signaler i urvalet</div>{query.isFetching && !query.isLoading && <span className="text-xs text-primary">Uppdaterar…</span>}</div>
      {query.isLoading ? <Loading /> : query.error ? <ErrorState error={query.error} /> : !items.length ? <Empty /> : showMap ? <div className="space-y-7"><SignalMapWorkspace signals={items} /><SignalTable signals={items} /></div> : <SignalTable signals={items} />}
    </>
  );
}

function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return <label className={className}><span className="label mb-2 block">{label}</span>{children}</label>;
}
