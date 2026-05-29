import { Suspense } from "react";

import { LeadOperationsWorkspace } from "@/components/leads/LeadOperationsWorkspace";

export default function LeadsPage() {
  return (
    <Suspense fallback={<LeadsPageFallback />}>
      <LeadOperationsWorkspace />
    </Suspense>
  );
}

function LeadsPageFallback() {
  return (
    <section className="ea-card p-5">
      <p className="text-sm text-brand-muted">Loading leads...</p>
    </section>
  );
}
