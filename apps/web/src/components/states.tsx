import { AlertTriangle, Inbox, LoaderCircle } from "lucide-react";

import { Card } from "@/components/ui/card";

export function Loading({ label = "Hämtar signaldata…" }: { label?: string }) {
  return <Card className="grid min-h-48 place-items-center p-8 text-center"><div><LoaderCircle className="mx-auto size-6 animate-spin text-primary" /><p className="mt-4 text-sm text-muted-foreground">{label}</p></div></Card>;
}

export function ErrorState({ error }: { error: Error }) {
  return <div role="alert" className="rounded-2xl border border-destructive/20 bg-destructive/[0.06] p-6 text-destructive"><AlertTriangle className="mb-3 size-5" /><div className="font-medium">Data kunde inte hämtas</div><p className="mt-1 text-sm text-destructive/80">{error.message}</p></div>;
}

export function Empty({ title = "Inga signaler i urvalet", description = "Justera filtren eller invänta nästa källkörning." }: { title?: string; description?: string }) {
  return <Card className="grid min-h-48 place-items-center p-8 text-center"><div><Inbox className="mx-auto size-7 text-muted-foreground/60" /><div className="mt-4 font-medium text-foreground">{title}</div><p className="mt-1 text-sm text-muted-foreground">{description}</p></div></Card>;
}
