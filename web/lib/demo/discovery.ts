import type {
  DiscoveryImportRequest,
  DiscoveryImportResponse,
  DiscoveryLeadCandidate,
  DiscoveryPreviewEnrichmentRequest,
  DiscoveryPreviewEnrichmentResponse,
  DiscoveryPreviewItem,
  DiscoveryPreviewResponse,
  DiscoveryPreviewWebsiteRecoveryRequest,
  DiscoveryPreviewWebsiteRecoveryResponse,
  DiscoverySearchRequest,
  EnrichmentExtractedContact,
  ExclusionRuleCreateRequest,
  ExclusionRuleCreateResponse,
} from "@/lib/api/types";
import { lead, normalize } from "@/lib/demo/fixtures";
import { matchDemoScenario } from "@/lib/demo/scenarios";
import { addDemoImportBatch, getDemoLeads, nextDemoBatchId, nextDemoLeadId, saveDemoLeads } from "@/lib/demo/storage";

export async function previewDemoDiscovery(request: DiscoverySearchRequest): Promise<DiscoveryPreviewResponse> {
  const rawQuery = request.raw_query ?? request.search_terms.join(" ");
  const scenario = matchDemoScenario(rawQuery, request.location_query);
  const locationLabel = scenario ? `${scenario.city}, ${scenario.state}` : request.location_query ?? "Guided demo searches";
  const templates = scenario?.candidates ?? [];
  const existingLeads = getDemoLeads();
  const items = templates.slice(0, Math.max(1, request.max_results_per_term * Math.max(1, request.search_terms.length))).map((candidate, index) => {
    const existing = existingLeads.find((leadItem) =>
      leadItem.normalized_business_name === normalize(candidate.business_name) ||
      Boolean(candidate.domain && leadItem.domain === candidate.domain)
    );
    return previewItem(candidate, request.search_terms[index % Math.max(1, request.search_terms.length)] ?? "demo search", index, existing?.id ?? null);
  });

  return {
    provider: "demo",
    resolved_location: {
      label: locationLabel,
      latitude: request.latitude ?? scenario?.latitude ?? -23.5505,
      longitude: request.longitude ?? scenario?.longitude ?? -46.6333,
    },
    total_provider_results: items.length,
    duplicates_removed: items.length > 0 ? 1 : 0,
    existing_leads_hidden_count: items.filter((item) => item.is_existing_lead).length,
    items,
  };
}

export async function evaluateDemoDiscoveryExclusions(preview: DiscoveryPreviewResponse): Promise<DiscoveryPreviewResponse> {
  return preview;
}

export async function importDemoDiscoveryPreview(payload: DiscoveryImportRequest): Promise<DiscoveryImportResponse> {
  const selectedIds = new Set(payload.selected_client_result_ids);
  const now = new Date().toISOString();
  const existing = getDemoLeads();
  let nextId = nextDemoLeadId();
  const created = payload.preview.items
    .filter((item) => item.client_result_id && selectedIds.has(item.client_result_id))
    .filter((item) => !item.exclusion.is_blocked && !item.is_existing_lead)
    .map((item) => leadFromCandidate(nextId++, item.candidate, now));

  saveDemoLeads([...created, ...existing]);

  const batchId = nextDemoBatchId();
  const batch = {
    id: batchId,
    batch_type: "demo_import",
    status: "completed",
    source_provider: "demo",
    source_query: payload.request.raw_query ?? payload.request.search_terms.join(", "),
    location_label: payload.preview.resolved_location.label,
    record_count: payload.preview.items.length,
    lead_count: created.length,
    lead_ids: created.map((item) => item.id),
    started_at: now,
    completed_at: now,
    created_at: now,
    updated_at: now,
  };
  addDemoImportBatch(batch);

  return {
    batch,
    batch_id: batchId,
    provider: "demo",
    resolved_location: payload.preview.resolved_location,
    total_preview_items: payload.preview.items.length,
    selected_items: selectedIds.size,
    saved_items: created.length,
    skipped_blocked: payload.preview.items.filter((item) => selectedIds.has(item.client_result_id ?? "") && item.exclusion.is_blocked).length,
    skipped_existing_count: payload.preview.items.filter((item) => selectedIds.has(item.client_result_id ?? "") && item.is_existing_lead).length,
    merged_existing_count: 0,
    created_count: created.length,
    created_leads: created.length,
    updated_leads: 0,
    saved_lead_ids: created.map((item) => item.id),
    leads: created,
    skipped_items: [],
  };
}

export async function enrichDemoDiscoveryPreview(payload: DiscoveryPreviewEnrichmentRequest): Promise<DiscoveryPreviewEnrichmentResponse> {
  const requested = new Set(payload.client_result_ids);
  const items = payload.preview.items.map((item) => {
    if (!item.client_result_id || !requested.has(item.client_result_id) || !hasWebsite(item.candidate)) {
      return item;
    }
    const extractedContacts: EnrichmentExtractedContact[] = [];
    if (item.candidate.email) {
      extractedContacts.push(extractedContact("email", item.candidate.email, item.candidate.website));
    }
    if (item.candidate.instagram) {
      extractedContacts.push(extractedContact("instagram", item.candidate.instagram, item.candidate.website));
    }
    if (item.candidate.website) {
      extractedContacts.push(extractedContact("contact_form", `${item.candidate.website}/contact`, item.candidate.website));
    }
    return {
      ...item,
      enrichment: {
        success: true,
        attempted_pages: [],
        fetched_page_urls: item.candidate.website ? [item.candidate.website] : [],
        extracted_contacts: extractedContacts,
        email_found: Boolean(item.candidate.email),
        instagram_found: Boolean(item.candidate.instagram),
        contact_form_found: Boolean(item.candidate.website),
        no_email_found: !item.candidate.email,
        skipped_reason: null,
        error_message: null,
      },
    } satisfies DiscoveryPreviewItem;
  });
  const processed = items.filter((item) => item.client_result_id && requested.has(item.client_result_id) && hasWebsite(item.candidate));
  return {
    preview: { ...payload.preview, items },
    summary: {
      requested: requested.size,
      processed: processed.length,
      success_count: processed.length,
      emails_found: processed.filter((item) => item.candidate.email).length,
      instagrams_found: processed.filter((item) => item.candidate.instagram).length,
      contact_forms_found: processed.filter((item) => item.candidate.website).length,
      no_email_found: processed.filter((item) => !item.candidate.email).length,
      skipped_no_website: payload.client_result_ids.length - processed.length,
      blocked_after_enrichment: 0,
      errors: 0,
      error_messages: [],
    },
  };
}

export async function recoverDemoDiscoveryWebsites(payload: DiscoveryPreviewWebsiteRecoveryRequest): Promise<DiscoveryPreviewWebsiteRecoveryResponse> {
  const requested = new Set(payload.client_result_ids);
  let recoveredCount = 0;
  const items = payload.preview.items.map((item) => {
    if (!item.client_result_id || !requested.has(item.client_result_id) || hasWebsite(item.candidate)) {
      return item;
    }
    recoveredCount += 1;
    const domain = `${normalize(item.candidate.business_name).replace(/\s+/g, "")}.example`;
    return {
      ...item,
      candidate: {
        ...item.candidate,
        website: `https://${domain}`,
        domain,
      },
    };
  });
  return {
    preview: { ...payload.preview, items },
    summary: {
      requested: requested.size,
      processed: requested.size,
      recovered_count: recoveredCount,
      no_website_found: Math.max(0, requested.size - recoveredCount),
      skipped_existing_website: 0,
      skipped_missing_place_id: 0,
      skipped_blocked: 0,
      blocked_after_recovery: 0,
      errors: 0,
      error_messages: [],
    },
  };
}

export async function createDemoExclusionRule(payload: ExclusionRuleCreateRequest): Promise<ExclusionRuleCreateResponse> {
  const now = new Date().toISOString();
  const normalizedPattern = normalize(payload.pattern);
  const leads = getDemoLeads();
  const updated = leads.map((leadItem) => {
    const matchesName = normalize(leadItem.business_name).includes(normalizedPattern);
    const matchesDomain = Boolean(leadItem.domain && normalize(leadItem.domain).includes(normalizedPattern));
    if (!matchesName && !matchesDomain) {
      return leadItem;
    }
    return {
      ...leadItem,
      is_blocked: true,
      blocked_reason: payload.reason ?? "Demo exclusion rule.",
      blocked_rule_id: 999,
      blocked_at: now,
      updated_at: now,
    };
  });
  const blocked = updated.filter((leadItem, index) => !leads[index].is_blocked && leadItem.is_blocked).length;
  saveDemoLeads(updated);
  return {
    rule: {
      id: 999,
      organization_id: 1,
      rule_type: payload.rule_type,
      pattern: payload.pattern,
      normalized_pattern: normalizedPattern,
      reason: payload.reason ?? null,
      is_active: payload.is_active ?? true,
      created_at: now,
      updated_at: now,
    },
    reapply_summary: payload.reapply_existing_leads ? { evaluated: leads.length, blocked, unblocked: 0, unchanged: leads.length - blocked } : null,
  };
}

function previewItem(candidateValue: DiscoveryLeadCandidate, searchTerm: string, index: number, existingLeadId: number | null): DiscoveryPreviewItem {
  return {
    client_result_id: `demo-preview-${normalize(candidateValue.business_name).replace(/\s+/g, "-")}-${index}`,
    search_term: searchTerm,
    matched_search_terms: [searchTerm],
    provider_record_id: candidateValue.google_place_id,
    source_url: candidateValue.source_url,
    raw_payload: { demo: true },
    candidate: candidateValue,
    exclusion: {
      is_blocked: false,
      rule_id: null,
      rule_type: null,
      pattern: null,
      reason: null,
    },
    is_existing_lead: existingLeadId !== null,
    existing_lead_id: existingLeadId,
    matched_existing_by: existingLeadId !== null ? "name_city" : null,
    enrichment: null,
  };
}

function leadFromCandidate(id: number, candidateValue: DiscoveryLeadCandidate, now: string) {
  const isRestaurant = /restaurant|cafe|bistr/i.test(candidateValue.category ?? "");
  const isBeauty = /esthetic|aesthetic|beauty|skin|clinic/i.test(candidateValue.category ?? "");
  const isB2BOperations = /logistics|logística|transport|transportadora|fulfillment|software|agency|consulting|distribuidora|supplier/i.test(candidateValue.category ?? "");
  return lead({
    id,
    business_name: candidateValue.business_name,
    category: candidateValue.category,
    city: candidateValue.city ?? "São Paulo",
    state: candidateValue.state ?? "SP",
    website: candidateValue.website,
    domain: candidateValue.domain,
    email: candidateValue.email,
    phone: candidateValue.phone,
    whatsapp: candidateValue.whatsapp,
    instagram: candidateValue.instagram,
    address: candidateValue.address,
    status: "new",
    lead_score: candidateValue.website ? 78 : 62,
    sales_region_id: regionIdForCandidate(candidateValue),
    market_segment_id: isRestaurant ? 2 : isBeauty ? 3 : isB2BOperations ? 4 : 1,
    market_subsegment_id: isRestaurant ? 2 : isBeauty ? 3 : isB2BOperations ? 4 : 1,
    company_size_fit: candidateValue.website ? "ideal_sme" : "possible_sme",
    trade_type: "varejo",
    created_at: now,
    updated_at: now,
  });
}

function regionIdForCandidate(candidateValue: DiscoveryLeadCandidate) {
  if (["San Francisco", "Melbourne"].includes(candidateValue.city ?? "")) return candidateValue.city === "Melbourne" ? 5 : 1;
  if (["New York", "Toronto"].includes(candidateValue.city ?? "")) return 2;
  if (candidateValue.city === "London") return 3;
  if (["Berlin", "Amsterdam", "Dublin"].includes(candidateValue.city ?? "")) return 4;
  if (["Campinas", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Porto Alegre"].includes(candidateValue.city ?? "")) return 4;
  return 1;
}

function extractedContact(contactType: string, value: string, sourceUrl: string | null): EnrichmentExtractedContact {
  return {
    contact_type: contactType,
    raw_value: value,
    normalized_value: value,
    source_url: sourceUrl ?? "demo",
    confidence: 0.9,
    label: "Demo extracted contact",
    note: null,
    added_to_lead: true,
  };
}

function hasWebsite(candidateValue: DiscoveryLeadCandidate) {
  return Boolean(candidateValue.website || candidateValue.domain);
}
