import type { Metadata } from "next";

import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { Providers } from "./providers";
import { Shell } from "@/components/layout/shell";

export const metadata: Metadata = {
  title: { default: "FlyttRadar", template: "%s · FlyttRadar" },
  description: "Förklarbara flyttsignaler för Uppsala",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="sv"><body><Providers><Shell>{children}</Shell></Providers></body></html>;
}
