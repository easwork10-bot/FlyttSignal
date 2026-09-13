import { Suspense } from "react";

import { Loading } from "@/components/states";
import { PilotPage } from "@/features/pilot/pilot-page";

export default function PilotRoute() {
  return (
    <Suspense fallback={<Loading label="Öppnar pilotvyn…" />}>
      <PilotPage />
    </Suspense>
  );
}
