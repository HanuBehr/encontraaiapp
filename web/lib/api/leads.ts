import { getJson } from "@/lib/api/client";
import type { LeadDetail, LeadListParams, LeadListResponse, LeadOptionsResponse } from "@/lib/api/types";

export function listLeads(params: LeadListParams = {}) {
  return getJson<LeadListResponse>("/leads", params);
}

export function getLeadOptions() {
  return getJson<LeadOptionsResponse>("/leads/options");
}

export function getLeadDetail(leadId: number) {
  return getJson<LeadDetail>(`/leads/${leadId}`);
}
