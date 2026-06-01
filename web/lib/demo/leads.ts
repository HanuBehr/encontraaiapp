import type {
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
import {
  demoInitialImportBatch,
  demoMarketSegments,
  demoMarketSubsegments,
  demoSalesRegions,
  demoSalesReps,
} from "@/lib/demo/fixtures";
import { getDemoImportBatches, getDemoLeads, saveDemoLeads } from "@/lib/demo/storage";

export async function listDemoLeads(params: LeadListParams = {}): Promise<LeadListResponse> {
  const filtered = filterDemoLeads(getDemoLeads(), params);
  const sorted = sortDemoLeads(filtered, params);
  const offset = params.offset ?? 0;
  const limit = params.limit ?? sorted.length;
  return {
    total: sorted.length,
    items: sorted.slice(offset, offset + limit),
  };
}

export async function getDemoLeadOptions(): Promise<LeadOptionsResponse> {
  const leads = getDemoLeads();
  return {
    cities: unique(leads.map((lead) => lead.city).filter(Boolean) as string[]),
    states: unique(leads.map((lead) => lead.state).filter(Boolean) as string[]),
    statuses: ["new", "reviewed", "approved", "contacted", "replied", "interested", "closed", "not_interested", "do_not_contact"],
    assigned_reps: demoSalesReps.map(({ id, name }) => ({ id, name })),
    sales_regions: demoSalesRegions,
    market_segments: demoMarketSegments,
    market_subsegments: demoMarketSubsegments,
    target_fit_values: ["ideal_sme", "possible_sme", "large_enterprise", "unknown"],
    trade_type_values: ["varejo", "atacado", "distribuidora", "ecommerce", "industria", "construcao_civil", "unknown"],
  };
}

export async function getDemoLeadDetail(leadId: number): Promise<LeadDetail> {
  const lead = getDemoLeads().find((item) => item.id === leadId);
  if (!lead) {
    throw new Error("Demo lead not found.");
  }
  return lead;
}

export async function getDemoLatestImportBatch(): Promise<LeadImportBatchResponse> {
  return getDemoImportBatches()[0] ?? demoInitialImportBatch;
}

export async function resolveDemoLeadScope(scope: LeadScopeRequest): Promise<LeadScopeResolveResponse> {
  if ("lead_ids" in scope && scope.lead_ids) {
    const existingIds = new Set(getDemoLeads().map((lead) => lead.id));
    const leadIds = scope.lead_ids.filter((leadId) => existingIds.has(leadId));
    return {
      scope_type: "selected",
      scope_label: "Selected demo leads",
      total: leadIds.length,
      lead_ids: leadIds,
      missing_lead_ids: scope.lead_ids.filter((leadId) => !existingIds.has(leadId)),
      import_batch: null,
    };
  }

  if ("latest_import_batch" in scope && scope.latest_import_batch) {
    const latestBatch = await getDemoLatestImportBatch();
    return {
      scope_type: "latest_import_batch",
      scope_label: `Latest import batch #${latestBatch.id}`,
      total: latestBatch.lead_ids.length,
      lead_ids: latestBatch.lead_ids,
      missing_lead_ids: [],
      import_batch: latestBatch,
    };
  }

  const filtered = filterDemoLeads(getDemoLeads(), scope.filters ?? {});
  return {
    scope_type: "filters",
    scope_label: "Current filtered demo list",
    total: filtered.length,
    lead_ids: filtered.map((lead) => lead.id),
    missing_lead_ids: [],
    import_batch: null,
  };
}

export async function enrichDemoLeadBatch(leadIds: number[]): Promise<LeadBatchEnrichmentResponse> {
  const now = new Date().toISOString();
  const leads = getDemoLeads();
  const selected = leads.filter((lead) => leadIds.includes(lead.id));
  const updated = leads.map((lead) => leadIds.includes(lead.id) ? { ...lead, last_enriched_at: now, updated_at: now } : lead);
  saveDemoLeads(updated);
  const emailsFound = selected.filter((lead) => lead.email).length;
  const instagramsFound = selected.filter((lead) => lead.instagram).length;
  const whatsappsFound = selected.filter((lead) => lead.whatsapp).length;

  return {
    processed: selected.length,
    results: selected.map((lead) => ({
      lead_id: lead.id,
      business_name: lead.business_name,
      success: true,
      pages_attempted: lead.website ? 2 : 0,
      pages_fetched: lead.website ? 2 : 0,
      attempted_pages: [],
      fetched_page_urls: lead.website ? [lead.website] : [],
      extracted_contacts: [],
      contacts_added: 0,
      contacts_added_by_type: {},
      fields_updated: ["last_enriched_at"],
      last_enriched_at: now,
      material_profile: {},
      skipped_reason: lead.website ? null : "No public website.",
      no_email_found: !lead.email,
      error_message: null,
    })),
    summary: {
      scope_label: "Demo enrichment",
      requested: leadIds.length,
      processed: selected.length,
      success_count: selected.length,
      contacts_added: 0,
      emails_found: emailsFound,
      instagrams_found: instagramsFound,
      whatsapps_found: whatsappsFound,
      contact_forms_found: selected.filter((lead) => lead.website).length,
      skipped: Math.max(0, leadIds.length - selected.length),
      skipped_no_website: selected.filter((lead) => !lead.website).length,
      errors: 0,
      error_messages: [],
      failed_lead_ids: [],
      pages_attempted: selected.filter((lead) => lead.website).length * 2,
      pages_fetched: selected.filter((lead) => lead.website).length * 2,
    },
  };
}

export async function enrichDemoLeadBatchCnpj(leadIds: number[]): Promise<LeadBatchCNPJEnrichmentResponse> {
  return {
    processed: leadIds.length,
    results: [],
    summary: {
      scope_label: "Demo CNPJ enrichment disabled",
      requested: leadIds.length,
      processed: 0,
      matched_count: 0,
      needs_review_count: 0,
      not_found_count: 0,
      skipped_known_count: 0,
      skipped_review_candidate_count: 0,
      paid_search_recently_attempted_count: 0,
      no_website_count: 0,
      no_cnpj_on_website_count: 0,
      website_timeout_count: 0,
      website_unreachable_count: 0,
      validation_failed_count: 0,
      low_confidence_count: 0,
      company_search_matched_count: 0,
      company_search_needs_review_count: 0,
      company_search_no_candidates_count: 0,
      company_search_zero_candidates_count: 0,
      company_search_low_confidence_count: 0,
      company_search_not_configured_count: 0,
      company_search_pending_retry_count: 0,
      company_search_rate_limited_count: 0,
      company_search_provider_error_count: 0,
      company_search_consulted_now_count: 0,
      paid_calls_made: 0,
      paid_calls_skipped_duplicate: 0,
      paid_calls_skipped_recent: 0,
      provider_rate_limited_count: 0,
      provider_error_count: 0,
      error_count: 0,
      errors: [],
    },
  };
}

export async function assignDemoLeadBatch(scope: LeadScopeRequest): Promise<LeadBatchAssignmentResponse> {
  const resolved = await resolveDemoLeadScope(scope);
  const now = new Date().toISOString();
  const leads = getDemoLeads();
  const updated = leads.map((lead) => {
    if (!resolved.lead_ids.includes(lead.id) || lead.assigned_sales_rep_id) {
      return lead;
    }
    return {
      ...lead,
      assigned_sales_rep_id: 1,
      assigned_sales_rep: demoSalesReps[0],
      sales_region_id: lead.sales_region_id ?? 1,
      sales_region: lead.sales_region ?? demoSalesRegions[0],
      assigned_at: now,
      updated_at: now,
    };
  });
  saveDemoLeads(updated);
  const changed = updated.filter((lead) => resolved.lead_ids.includes(lead.id) && lead.assigned_sales_rep_id === 1).length;
  return {
    processed: resolved.lead_ids.length,
    changed,
    dry_run: false,
    results: resolved.lead_ids.map((leadId) => ({
      lead_id: leadId,
      changed_fields: ["assigned_sales_rep_id"],
      suggestion: {
        sales_region_id: 1,
        market_segment_id: null,
        market_subsegment_id: null,
        assigned_sales_rep_id: 1,
        assignment_rule_id: null,
        explanation: "Demo assignment suggestion.",
        metadata: {},
      },
    })),
    summary: {
      scope_type: resolved.scope_type,
      scope_label: resolved.scope_label,
      requested: resolved.total,
      processed: resolved.total,
      changed,
      overwrite: false,
      dry_run: false,
      missing_lead_ids: resolved.missing_lead_ids,
    },
  };
}

export async function approveDemoLeadCnpjCandidate(leadId: number): Promise<LeadDetail> {
  return getDemoLeadDetail(leadId);
}

export async function rejectDemoLeadCnpjCandidate(leadId: number): Promise<LeadDetail> {
  return getDemoLeadDetail(leadId);
}

export function filterDemoLeads(leads: LeadDetail[], params: LeadListParams) {
  let filtered = leads;
  if (params.blocked === "exclude" || !params.blocked) {
    filtered = filtered.filter((lead) => !lead.is_blocked);
  } else if (params.blocked === "only") {
    filtered = filtered.filter((lead) => lead.is_blocked);
  }
  if (params.search) {
    const search = params.search.toLocaleLowerCase("pt-BR");
    filtered = filtered.filter((lead) => [
      lead.business_name,
      lead.city,
      lead.state,
      lead.category,
      lead.email,
      lead.phone,
      lead.whatsapp,
      lead.instagram,
      lead.assigned_sales_rep?.name,
      lead.market_segment?.name,
      lead.blocked_reason,
    ].filter(Boolean).some((value) => String(value).toLocaleLowerCase("pt-BR").includes(search)));
  }
  if (params.city) filtered = filtered.filter((lead) => lead.city === params.city);
  if (params.state) filtered = filtered.filter((lead) => lead.state === params.state);
  if (params.status) filtered = filtered.filter((lead) => lead.status === params.status);
  if (params.assigned_sales_rep_id) filtered = filtered.filter((lead) => lead.assigned_sales_rep_id === params.assigned_sales_rep_id);
  if (params.sales_region_id) filtered = filtered.filter((lead) => lead.sales_region_id === params.sales_region_id);
  if (params.market_segment_id) filtered = filtered.filter((lead) => lead.market_segment_id === params.market_segment_id);
  if (params.market_subsegment_id) filtered = filtered.filter((lead) => lead.market_subsegment_id === params.market_subsegment_id);
  if (params.company_size_fit) filtered = filtered.filter((lead) => lead.company_size_fit === params.company_size_fit);
  if (params.trade_type) filtered = filtered.filter((lead) => lead.trade_type === params.trade_type);
  if (params.has_assignment !== undefined) filtered = filtered.filter((lead) => Boolean(lead.assigned_sales_rep_id) === params.has_assignment);
  if (params.has_email !== undefined) filtered = filtered.filter((lead) => Boolean(lead.email) === params.has_email);
  if (params.has_whatsapp !== undefined) filtered = filtered.filter((lead) => Boolean(lead.whatsapp) === params.has_whatsapp);
  if (params.has_instagram !== undefined) filtered = filtered.filter((lead) => Boolean(lead.instagram) === params.has_instagram);
  if (params.import_batch_id) {
    const batch = getDemoImportBatches().find((item) => item.id === params.import_batch_id);
    const ids = new Set(batch?.lead_ids ?? []);
    filtered = filtered.filter((lead) => ids.has(lead.id));
  }
  return filtered;
}

function sortDemoLeads(leads: LeadDetail[], params: LeadListParams) {
  const sortBy = params.sort_by ?? "updated_at";
  const dir = params.sort_dir ?? "desc";
  return [...leads].sort((a, b) => {
    const left = a[sortBy as keyof LeadDetail];
    const right = b[sortBy as keyof LeadDetail];
    const comparison = String(left ?? "").localeCompare(String(right ?? ""), undefined, { numeric: true });
    return dir === "asc" ? comparison : -comparison;
  });
}

function unique(values: string[]) {
  return Array.from(new Set(values)).sort();
}
