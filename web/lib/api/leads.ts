import { getJson, postBlob, postJson } from "@/lib/api/client";
import type {
  LeadBatchAssignmentResponse,
  LeadBatchEnrichmentResponse,
  LeadDetail,
  LeadImportBatchResponse,
  LeadListParams,
  LeadListResponse,
  LeadOptionsResponse,
  LeadScopeRequest,
  LeadScopeResolveResponse,
} from "@/lib/api/types";

export function listLeads(params: LeadListParams = {}) {
  return getJson<LeadListResponse>("/leads", params);
}

export function getLeadOptions() {
  return getJson<LeadOptionsResponse>("/leads/options");
}

export function getLeadDetail(leadId: number) {
  return getJson<LeadDetail>(`/leads/${leadId}`);
}

export function getLatestImportBatch() {
  return getJson<LeadImportBatchResponse>("/leads/import-batches/latest");
}

export function resolveLeadScope(scope: LeadScopeRequest) {
  return postJson<LeadScopeResolveResponse, LeadScopeRequest>("/leads/resolve-scope", scope);
}

export function enrichLeadBatch(leadIds: number[]) {
  return postJson<LeadBatchEnrichmentResponse, { lead_ids: number[] }>("/leads/batch/enrich", {
    lead_ids: leadIds,
  });
}

export function assignLeadBatch(scope: LeadScopeRequest) {
  return postJson<LeadBatchAssignmentResponse, LeadScopeRequest & { overwrite: boolean; dry_run: boolean }>(
    "/leads/batch/assign",
    {
      ...scope,
      overwrite: false,
      dry_run: false,
    },
  );
}

export function exportExcelForScope(scope: LeadScopeRequest) {
  return postBlob("/exports/excel", scope);
}
