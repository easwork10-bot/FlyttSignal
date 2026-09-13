"use client";

import { Activity, Building2, Database, LayoutDashboard, RadioTower, Target } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const navigation = [
  { href: "/", label: "Översikt", icon: LayoutDashboard },
  { href: "/signals", label: "Signaler", icon: RadioTower },
  { href: "/pilot", label: "Pilot", icon: Target },
  { href: "/rentals", label: "Hyresrätter", icon: Building2 },
  { href: "/sources", label: "Källor", icon: Database },
];

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-border bg-card/95 backdrop-blur-xl">
        <div className="mx-auto grid h-16 max-w-[1680px] grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 sm:px-6 lg:px-8">
          <Link href="/" className="flex items-center gap-2.5" aria-label="FlyttRadar startsida">
            <span className="grid size-9 place-items-center rounded-xl bg-primary text-primary-foreground shadow-glow">
              <Activity className="size-5" strokeWidth={2.5} />
            </span>
            <span className="text-base font-semibold tracking-tight text-foreground">Flytt<span className="text-primary">Radar</span></span>
          </Link>

          <nav aria-label="Huvudnavigation" className="hidden items-center justify-self-center md:flex">
            <NavigationLinks pathname={pathname} mobile={false} />
          </nav>

          <Badge variant="success" className="hidden justify-self-end sm:inline-flex">
            <span className="mr-1.5 size-1.5 rounded-full bg-success" /> Uppsala · aktiv
          </Badge>
        </div>
      </header>
      <nav aria-label="Mobilnavigation" className="fixed inset-x-0 bottom-0 z-50 flex h-16 items-center justify-around border-t border-border bg-card/95 px-3 backdrop-blur-xl md:hidden">
        <NavigationLinks pathname={pathname} mobile />
      </nav>
      <main className="mx-auto max-w-[1680px] px-4 py-7 pb-24 sm:px-6 lg:px-8 lg:py-10 md:pb-10">{children}</main>
    </div>
  );
}

function NavigationLinks({ pathname, mobile }: { pathname: string; mobile: boolean }) {
  return navigation.map(({ href, label, icon: Icon }) => {
    const active = href === "/" ? pathname === href : pathname.startsWith(href);
    return (
      <Link key={href} href={href} className={cn("flex items-center gap-1 rounded-lg px-3 py-2 transition", mobile ? "min-w-16 flex-col text-xs" : "text-sm", active ? "bg-primary/10 text-foreground" : "text-muted-foreground hover:bg-muted hover:text-foreground")}>
        <Icon className={cn("size-4", active && "text-primary")} />
        {label}
      </Link>
    );
  });
}
