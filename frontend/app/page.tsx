import { Suspense } from "react";

import { SearchConsole } from "@/components/search-console";

export default function HomePage() {
  return (
    <Suspense fallback={<div className="empty-state">Booting search surface...</div>}>
      <SearchConsole />
    </Suspense>
  );
}
