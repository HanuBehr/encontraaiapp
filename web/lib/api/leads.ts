import { getJson, postBlob, postJson } from "@/lib/api/client";
import { exportDemoExcelForScope } from "@/lib/demo/export";
import {
  approveDemoLeadCnpjCandidate,
  assignDemoLeadBatch,
  enrichDemoLeadBatch,
  enrichDemoLeadBatchCnpj,
  getDemoLatestImportBatch,
  getDemoLeadDetail,
  getDemoLeadOptions,
  listDemoLeads,
  rejectDemoLeadCnpjCandidate,
  resolveDemoLeadScope,
} from "@/lib/demo/leads";
import { isDemoMode } from "@/lib/demo/mode";
import type {
  LeadBatchApproveCNPJCandidatesResponse,
  LeadBatchAssignmentResponse,
  LeadBatchCNPJEnrichmentResponse,
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
  if (isDemoMode()) {
    return listDemoLeads(params);
  }
  return getJson<LeadListResponse>("/leads", params);
}

export function getLeadOptions() {
  if (isDemoMode()) {
    return getDemoLeadOptions();
  }
  return getJson<LeadOptionsResponse>("/leads/options");
}

export function getLeadDetail(leadId: number) {
  if (isDemoMode()) {
    return getDemoLeadDetail(leadId);
  }
  return getJson<LeadDetail>(`/leads/${leadId}`);
}

export function getLatestImportBatch() {
  if (isDemoMode()) {
    return getDemoLatestImportBatch();
  }
  return getJson<LeadImportBatchResponse>("/leads/import-batches/latest");
}

export function resolveLeadScope(scope: LeadScopeRequest) {
  if (isDemoMode()) {
    return resolveDemoLeadScope(scope);
  }
  return postJson<LeadScopeResolveResponse, LeadScopeRequest>("/leads/resolve-scope", scope);
}

export function enrichLeadBatch(leadIds: number[]) {
  if (isDemoMode()) {
    return enrichDemoLeadBatch(leadIds);
  }
  return postJson<LeadBatchEnrichmentResponse, { lead_ids: number[] }>("/leads/batch/enrich", {
    lead_ids: leadIds,
  });
}

export function enrichLeadBatchCnpj(
  leadIds: number[],
  options: {
    force?: boolean;
    searchMode?: "cheap" | "balanced" | "delivery";
    forcePaidSearch?: boolean;
  } = {},
) {
  if (isDemoMode()) {
    return enrichDemoLeadBatchCnpj(leadIds);
  }
  return postJson<
    LeadBatchCNPJEnrichmentResponse,
    {
      lead_ids: number[];
      force: boolean;
      search_mode?: "cheap" | "balanced" | "delivery";
      force_paid_search?: boolean;
    }
  >(
    "/leads/batch/enrich-cnpj",
    {
      lead_ids: leadIds,
      force: options.force ?? false,
      search_mode: options.searchMode,
      force_paid_search: options.forcePaidSearch ?? false,
    },
  );
}

export function approveLeadCnpjCandidate(leadId: number) {
  if (isDemoMode()) {
    return approveDemoLeadCnpjCandidate(leadId);
  }
  return postJson<LeadDetail, { candidate_cnpj?: string }>(`/leads/${leadId}/approve-cnpj-candidate`, {});
}

export function approveLeadCnpjCandidateByValue(leadId: number, candidateCnpj?: string | null) {
  if (isDemoMode()) {
    return approveDemoLeadCnpjCandidate(leadId);
  }
  return postJson<LeadDetail, { candidate_cnpj?: string }>(`/leads/${leadId}/approve-cnpj-candidate`, {
    ...(candidateCnpj ? { candidate_cnpj: candidateCnpj } : {}),
  });
}

export function rejectLeadCnpjCandidate(leadId: number, candidateCnpj?: string | null) {
  if (isDemoMode()) {
    return rejectDemoLeadCnpjCandidate(leadId);
  }
  return postJson<LeadDetail, { candidate_cnpj?: string }>(`/leads/${leadId}/reject-cnpj-candidate`, {
    ...(candidateCnpj ? { candidate_cnpj: candidateCnpj } : {}),
  });
}

export function approveLeadBatchCnpjCandidates(leadIds: number[]) {
  if (isDemoMode()) {
    return Promise.resolve({
      summary: {
        requested: leadIds.length,
        processed: 0,
        approved_count: 0,
        skipped_ambiguous_count: 0,
        skipped_no_candidate_count: 0,
        skipped_low_confidence_count: 0,
        skipped_already_matched_count: 0,
        errors: [],
      },
    });
  }
  return postJson<LeadBatchApproveCNPJCandidatesResponse, { lead_ids: number[] }>(
    "/leads/batch/approve-cnpj-candidates",
    { lead_ids: leadIds },
  );
}

export function assignLeadBatch(scope: LeadScopeRequest) {
  if (isDemoMode()) {
    return assignDemoLeadBatch(scope);
  }
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
  if (isDemoMode()) {
    return exportDemoExcelForScope(scope);
  }
  return postBlob("/exports/excel", scope);
}
