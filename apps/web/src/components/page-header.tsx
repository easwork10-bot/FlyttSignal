import type { LucideIcon } from "lucide-react";

export function PageHeader({ eyebrow, title, description, icon: Icon }: { eyebrow: string; title: string; description?: string; icon?: LucideIcon }) {
  return (
    <div className="mb-7 flex items-start gap-4 lg:mb-9">
      {Icon && <div className="hidden size-11 place-items-center rounded-xl border border-primary/20 bg-primary/10 text-primary sm:grid"><Icon className="size-5" /></div>}
      <div>
        <div className="label">{eyebrow}</div>
        <h1 className="mt-1.5 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">{title}</h1>
        {description && <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">{description}</p>}
      </div>
    </div>
  );
}
