import type { LucideIcon } from "lucide-react";

import { Card } from "@/components/ui/card";

export function MetricCard({ label, value, hint, icon: Icon, tone = "cyan" }: { label: string; value: number | string; hint: string; icon: LucideIcon; tone?: "cyan" | "emerald" | "violet" | "amber" }) {
  const tones = {
    cyan: "bg-primary/10 text-primary border-primary/20",
    emerald: "bg-success/10 text-success border-success/20",
    violet: "bg-secondary text-secondary-foreground border-border",
    amber: "bg-warning/10 text-warning border-warning/20",
  };
  return (
    <Card className="group relative overflow-hidden p-5">
      <div className="flex items-start justify-between gap-4">
        <div><div className="label">{label}</div><div className="mt-3 text-3xl font-semibold tabular-nums tracking-tight">{value}</div></div>
        <span className={`grid size-10 place-items-center rounded-xl border ${tones[tone]}`}><Icon className="size-5" /></span>
      </div>
      <p className="mt-4 text-xs text-muted-foreground">{hint}</p>
    </Card>
  );
}
