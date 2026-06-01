import type { LeadScopeRequest } from "@/lib/api/types";
import { filterDemoLeads } from "@/lib/demo/leads";
import { getDemoImportBatches, getDemoLeads } from "@/lib/demo/storage";

export async function exportDemoExcelForScope(scope: LeadScopeRequest): Promise<{ blob: Blob; filename: string }> {
  const leads = resolveExportLeads(scope);
  const header = ["Business name", "City", "State", "Category", "Website", "Email", "WhatsApp", "Status", "Score"];
  const rows = leads.map((lead) => [
    lead.business_name,
    lead.city ?? "",
    lead.state ?? "",
    lead.category ?? "",
    lead.website ?? "",
    lead.email ?? "",
    lead.whatsapp ?? lead.phone ?? "",
    lead.status,
    String(lead.lead_score),
  ]);
  const csv = [header, ...rows].map((row) => row.map(escapeCsv).join(",")).join("\n");
  return {
    blob: new Blob([csv], { type: "text/csv;charset=utf-8" }),
    filename: `encontraai-demo-leads-${new Date().toISOString().slice(0, 10)}.csv`,
  };
}

function resolveExportLeads(scope: LeadScopeRequest) {
  const leads = getDemoLeads();
  if ("lead_ids" in scope && scope.lead_ids) {
    const ids = new Set(scope.lead_ids);
    return leads.filter((lead) => ids.has(lead.id));
  }
  if ("latest_import_batch" in scope && scope.latest_import_batch) {
    const batch = getDemoImportBatches()[0];
    const ids = new Set(batch?.lead_ids ?? []);
    return leads.filter((lead) => ids.has(lead.id));
  }
  return filterDemoLeads(leads, scope.filters ?? {});
}

function escapeCsv(value: string) {
  return `"${value.replace(/"/g, '""')}"`;
}
