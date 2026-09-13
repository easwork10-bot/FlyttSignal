"use client";

import { MapPinned } from "lucide-react";
import { LngLatBounds, Map as MapLibreMap, Marker, NavigationControl } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";

import { Card } from "@/components/ui/card";
import { getMapCoordinate } from "@/features/signals/components/signal-map-data";
import type { Signal } from "@/lib/api/types";
import { availableFrom } from "@/features/signals/timing";

const UPPSALA_CENTER: [number, number] = [17.6389, 59.8586];

export function SignalMap({ signals, selectedId, onSelect, className = "h-[430px]" }: { signals: Signal[]; selectedId: string | null; onSelect: (id: string) => void; className?: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const markersRef = useRef(new Map<string, Marker>());
  const onSelectRef = useRef(onSelect);
  const fittedRef = useRef(false);
  const [failed, setFailed] = useState(false);
  const mappedSignals = useMemo(
    () => signals.flatMap((signal) => {
      const coordinates = getMapCoordinate(signal);
      return coordinates ? [{ signal, coordinates }] : [];
    }),
    [signals],
  );

  useEffect(() => { onSelectRef.current = onSelect; }, [onSelect]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const container = containerRef.current;
    const selectMarkerFromEvent = (event: Event) => {
      const marker = (event.target as HTMLElement).closest<HTMLElement>("[data-signal-id]");
      if (!marker?.dataset.signalId) return;
      event.stopPropagation();
      onSelectRef.current(marker.dataset.signalId);
    };
    container.addEventListener("pointerdown", selectMarkerFromEvent, { capture: true });
    container.addEventListener("click", selectMarkerFromEvent, { capture: true });
    const map = new MapLibreMap({
      container,
      style: "https://tiles.openfreemap.org/styles/liberty",
      center: UPPSALA_CENTER,
      zoom: 11.6,
      attributionControl: {},
    });
    const resizeObserver = new ResizeObserver(() => map.resize());
    resizeObserver.observe(container);
    container.dataset.mapStatus = "mounted";
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.on("error", (event) => {
      if (!event.error?.message?.includes("AbortError")) setFailed(true);
    });
    mapRef.current = map;
    return () => {
      container.removeEventListener("pointerdown", selectMarkerFromEvent, { capture: true });
      container.removeEventListener("click", selectMarkerFromEvent, { capture: true });
      resizeObserver.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((marker) => marker.remove());
    const markers = new Map<string, Marker>();
    markersRef.current = markers;
    mappedSignals.forEach(({ signal, coordinates }) => {
      const element = document.createElement("button");
      element.type = "button";
      element.className = "signal-map-marker";
      element.dataset.selected = "false";
      element.dataset.signalId = signal.id;
      element.ariaLabel = `${signal.property.address}, signalstyrka ${signal.active_dimensions.signal_strength}`;
      element.title = `${signal.property.address} · ${availableFrom(signal) ?? "okänd tillgänglighet"}`;
      markers.set(signal.id, new Marker({ element }).setLngLat(coordinates).addTo(map));
    });
    if (containerRef.current) {
      containerRef.current.dataset.mapStatus = "ready";
      containerRef.current.dataset.featureCount = String(mappedSignals.length);
    }
    if (!fittedRef.current && mappedSignals.length > 1) {
      const bounds = new LngLatBounds();
      mappedSignals.forEach(({ coordinates }) => bounds.extend(coordinates));
      map.fitBounds(bounds, { padding: 65, maxZoom: 13, duration: 0 });
      fittedRef.current = true;
    }
    return () => {
      markers.forEach((marker) => marker.remove());
      if (markersRef.current === markers) markersRef.current = new Map();
    };
  }, [mappedSignals]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    markersRef.current.forEach((marker, id) => {
      marker.getElement().dataset.selected = String(id === selectedId);
    });
    if (selectedId) {
      const signal = signals.find((item) => item.id === selectedId);
      const coordinates = signal ? getMapCoordinate(signal) : null;
      if (coordinates) map.easeTo({ center: coordinates, duration: 500 });
    }
  }, [selectedId, signals]);

  if (!mappedSignals.length) {
    return <Card className={`${className} grid place-items-center p-8 text-center`}><div><MapPinned className="mx-auto size-7 text-muted-foreground/60" /><p className="mt-3 text-sm text-muted-foreground">Inga koordinatsatta signaler i urvalet.</p></div></Card>;
  }

  return (
    <div className={`relative overflow-hidden rounded-2xl border border-border bg-secondary ${className}`}>
      <div ref={containerRef} className="absolute inset-0" aria-label="Karta över flyttsignaler i Uppsala" />
      <div className="pointer-events-none absolute left-3 top-3 rounded-lg border border-border bg-card/95 px-3 py-2 text-xs text-muted-foreground shadow-lg backdrop-blur">
        <span className="font-semibold text-foreground">{mappedSignals.length}</span> koordinatsatta signaler
      </div>
      {failed && <div className="absolute inset-x-4 bottom-4 rounded-lg border border-warning/20 bg-card/95 p-3 text-xs text-warning">Kartbakgrunden kunde inte laddas. Signallistan fungerar fortfarande.</div>}
    </div>
  );
}
