"use client";

import { useMemo, useState } from "react";

import { SignalMap } from "@/features/signals/components/signal-map";
import { getMapCoordinate } from "@/features/signals/components/signal-map-data";
import { SignalPreview } from "@/features/signals/components/signal-preview";
import type { Signal } from "@/lib/api/types";

export function SignalMapWorkspace({ signals, compact = false, detailHref }: { signals: Signal[]; compact?: boolean; detailHref?: (signal: Signal) => string }) {
  const firstMappedId = useMemo(() => signals.find((signal) => getMapCoordinate(signal))?.id ?? null, [signals]);
  const [selectedId, setSelectedId] = useState<string | null>(firstMappedId);

  const effectiveSelectedId = signals.some((signal) => signal.id === selectedId) ? selectedId : firstMappedId;
  const selected = signals.find((signal) => signal.id === effectiveSelectedId) ?? null;

  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
      <SignalMap signals={signals} selectedId={effectiveSelectedId} onSelect={setSelectedId} className={compact ? "h-[390px]" : "h-[520px]"} />
      <SignalPreview signal={selected} detailHref={selected && detailHref ? detailHref(selected) : undefined} />
    </div>
  );
}
