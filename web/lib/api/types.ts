export type LeadStatus =
  | "new"
  | "reviewed"
  | "approved"
  | "contacted"
  | "replied"
  | "interested"
  | "closed"
  | "not_interested"
  | "do_not_contact";

export type LeadSourceType = "google_places" | "website" | "manual_import" | "demo_seed" | "merged";
export type CompanySizeFit = "ideal_sme" | "possible_sme" | "large_enterprise" | "unknown";
export type TradeType =
  | "varejo"
  | "atacado"
  | "distribuidora"
  | "ecommerce"
  | "industria"
  | "construcao_civil"
  | "unknown";

export type LeadSortBy =
  | "id"
  | "business_name"
  | "city"
  | "state"
  | "status"
  | "lead_score"
  | "created_at"
  | "updated_at"
  | "last_enriched_at"
  | "assigned_at"
  | "company_size_fit"
  | "trade_type";

export type LeadSortDir = "asc" | "desc";
export type LeadBlockedFilter = "exclude" | "include" | "only";
export type ExclusionRuleType = "exact_name" | "business_name_contains" | "domain";

export type SalesRegionRead = {
  id: number;
  name: string;
  region_type: string;
  state: string | null;
  code: string | null;
};

export type MarketSegmentRead = {
  id: number;
  key: string;
  name: string;
};

export type MarketSubsegmentRead = {
  id: number;
  key: string;
  name: string;
};

export type SalesRepRead = {
  id: number;
  name: string;
  email: string | null;
};

export type AssignmentRuleRead = {
  id: number;
  name: string;
  priority: number;
};

export type LeadSummary = {
  id: number;
  business_name: string;
  normalized_business_name: string;
  category: string | null;
  neighborhood: string | null;
  city: string | null;
  state: string | null;
  email: string | null;
  phone: string | null;
  whatsapp: string | null;
  instagram: string | null;
  website: string | null;
  lead_score: number;
  status: LeadStatus;
  lead_source_type: LeadSourceType;
  do_not_contact: boolean;
  approved_for_send: boolean;
  last_enriched_at: string | null;
  last_contacted_at: string | null;
  follow_up_date: string | null;
  is_duplicate: boolean;
  duplicate_of_lead_id: number | null;
  duplicate_reason: string | null;
  sales_region_id: number | null;
  market_segment_id: number | null;
  market_subsegment_id: number | null;
  assigned_sales_rep_id: number | null;
  assignment_rule_id: number | null;
  assigned_at: string | null;
  is_blocked: boolean;
  blocked_reason: string | null;
  blocked_rule_id: number | null;
  blocked_at: string | null;
  company_size_fit: CompanySizeFit;
  company_size_fit_explanation: string | null;
  trade_type: TradeType;
  trade_type_explanation: string | null;
  quality_classified_at: string | null;
  sales_region: SalesRegionRead | null;
  market_segment: MarketSegmentRead | null;
  market_subsegment: MarketSubsegmentRead | null;
  assigned_sales_rep: SalesRepRead | null;
  assignment_rule: AssignmentRuleRead | null;
  created_at: string;
  updated_at: string;
};

export type LeadContactRead = {
  id: number;
  contact_type: string;
  raw_value: string;
  normalized_value: string | null;
  label: string | null;
  source_url: string | null;
  source_kind: string | null;
  source_record_type: string | null;
  source_record_id: number | null;
  confidence: number;
  is_primary: boolean;
  note: string | null;
  created_at: string;
  updated_at: string;
};

export type LeadEnrichmentRecordRead = {
  id: number;
  source_url: string;
  page_type: string | null;
  http_status: number | null;
  robots_allowed: boolean;
  extracted_fields: Record<string, unknown>;
  confidence_scores: Record<string, unknown>;
  inferred_material_signals: Record<string, unknown>;
  note: string | null;
  fetched_at: string;
  created_at: string;
};

export type ActivityLogRead = {
  id: number;
  entity_type: string;
  entity_id: number | null;
  action: string;
  actor: string;
  message: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type LeadDetail = LeadSummary & {
  address: string | null;
  postal_code: string | null;
  latitude: number | null;
  longitude: number | null;
  domain: string | null;
  google_maps_url: string | null;
  google_place_id: string | null;
  source_provider: string | null;
  source_url: string | null;
  material_profile: Record<string, unknown>;
  score_breakdown: Record<string, unknown>;
  assignment_explanation: string | null;
  assignment_metadata_json: Record<string, unknown>;
  company_size_fit_metadata_json: Record<string, unknown>;
  trade_type_metadata_json: Record<string, unknown>;
  notes: string | null;
  tags: string[];
  owner: string | null;
  contacts: LeadContactRead[];
  enrichments: LeadEnrichmentRecordRead[];
  activity_logs: ActivityLogRead[];
};

export type LeadListParams = {
  city?: string;
  state?: string;
  status?: LeadStatus;
  has_email?: boolean;
  has_whatsapp?: boolean;
  has_instagram?: boolean;
  sales_region_id?: number;
  market_segment_id?: number;
  market_subsegment_id?: number;
  assigned_sales_rep_id?: number;
  has_assignment?: boolean;
  company_size_fit?: CompanySizeFit;
  trade_type?: TradeType;
  import_batch_id?: number;
  blocked?: LeadBlockedFilter;
  sort_by?: LeadSortBy;
  sort_dir?: LeadSortDir;
  limit?: number;
  offset?: number;
};

export type LeadListResponse = {
  total: number;
  items: LeadSummary[];
};

export type LeadScopeRequest =
  | {
      lead_ids: number[];
      filters?: never;
      latest_import_batch?: false;
    }
  | {
      lead_ids?: never;
      filters: LeadListParams;
      latest_import_batch?: false;
    }
  | {
      lead_ids?: never;
      filters?: never;
      latest_import_batch: true;
    };

export type LeadImportBatchResponse = {
  id: number;
  batch_type: string;
  status: string;
  source_provider: string | null;
  source_query: string | null;
  location_label: string | null;
  record_count: number;
  lead_count: number;
  lead_ids: number[];
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LeadScopeResolveResponse = {
  scope_type: string;
  scope_label: string;
  total: number;
  lead_ids: number[];
  missing_lead_ids: number[];
  import_batch: LeadImportBatchResponse | null;
};

export type LeadBatchEnrichmentSummary = {
  scope_label: string | null;
  requested: number;
  processed: number;
  success_count: number;
  contacts_added: number;
  emails_found: number;
  instagrams_found: number;
  whatsapps_found: number;
  contact_forms_found: number;
  skipped: number;
  skipped_no_website: number;
  errors: number;
  error_messages: string[];
  failed_lead_ids: number[];
  pages_attempted: number;
  pages_fetched: number;
};

export type EnrichmentAttemptedPage = {
  url: string;
  page_type: string | null;
  discovered_from_url: string | null;
  fetched: boolean;
  http_status: number | null;
  robots_allowed: boolean;
  note: string | null;
};

export type EnrichmentExtractedContact = {
  contact_type: string;
  raw_value: string;
  normalized_value: string | null;
  source_url: string;
  confidence: number;
  label: string | null;
  note: string | null;
  added_to_lead: boolean;
};

export type LeadBatchEnrichmentResponse = {
  processed: number;
  results: Array<{
    lead_id: number;
    business_name: string | null;
    success: boolean;
    pages_attempted: number;
    pages_fetched: number;
    attempted_pages: EnrichmentAttemptedPage[];
    fetched_page_urls: string[];
    extracted_contacts: EnrichmentExtractedContact[];
    contacts_added: number;
    contacts_added_by_type: Record<string, number>;
    fields_updated: string[];
    last_enriched_at: string | null;
    material_profile: Record<string, unknown>;
    skipped_reason: string | null;
    no_email_found: boolean;
    error_message: string | null;
  }>;
  summary: LeadBatchEnrichmentSummary;
};

export type LeadBatchAssignmentResponse = {
  processed: number;
  changed: number;
  dry_run: boolean;
  results: Array<{
    lead_id: number;
    changed_fields: string[];
    suggestion: {
      sales_region_id: number | null;
      market_segment_id: number | null;
      market_subsegment_id: number | null;
      assigned_sales_rep_id: number | null;
      assignment_rule_id: number | null;
      explanation: string | null;
      metadata: Record<string, unknown>;
    };
  }>;
  summary: {
    scope_type: string;
    scope_label: string;
    requested: number;
    processed: number;
    changed: number;
    overwrite: boolean;
    dry_run: boolean;
    missing_lead_ids: number[];
  };
};

export type LeadNamedOption = {
  id: number;
  name: string;
};

export type LeadSalesRegionOption = LeadNamedOption & {
  region_type: string;
  state: string | null;
  code: string | null;
};

export type LeadMarketSegmentOption = LeadNamedOption & {
  key: string;
};

export type LeadMarketSubsegmentOption = LeadNamedOption & {
  key: string;
  market_segment_id: number;
};

export type LeadOptionsResponse = {
  cities: string[];
  states: string[];
  statuses: LeadStatus[];
  assigned_reps: LeadNamedOption[];
  sales_regions: LeadSalesRegionOption[];
  market_segments: LeadMarketSegmentOption[];
  market_subsegments: LeadMarketSubsegmentOption[];
  target_fit_values: CompanySizeFit[];
  trade_type_values: TradeType[];
};

export type ResolvedLocation = {
  label: string;
  latitude: number;
  longitude: number;
};

export type DiscoveryLeadCandidate = {
  business_name: string;
  normalized_business_name: string;
  category: string | null;
  address: string | null;
  neighborhood: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  latitude: number | null;
  longitude: number | null;
  website: string | null;
  domain: string | null;
  email: string | null;
  phone: string | null;
  whatsapp: string | null;
  instagram: string | null;
  google_maps_url: string | null;
  google_place_id: string | null;
  source_provider: string;
  source_url: string | null;
  lead_source_type: LeadSourceType;
};

export type DiscoverySearchRequest = {
  search_terms: string[];
  location_query?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  radius_m: number;
  max_results_per_term: number;
};

export type DiscoveryExclusionMetadata = {
  is_blocked: boolean;
  rule_id: number | null;
  rule_type: string | null;
  pattern: string | null;
  reason: string | null;
};

export type DiscoveryPreviewItem = {
  client_result_id: string | null;
  search_term: string;
  provider_record_id: string | null;
  source_url: string | null;
  raw_payload: Record<string, unknown>;
  candidate: DiscoveryLeadCandidate;
  exclusion: DiscoveryExclusionMetadata;
  enrichment: DiscoveryPreviewEnrichmentMetadata | null;
};

export type DiscoveryPreviewResponse = {
  provider: string;
  resolved_location: ResolvedLocation;
  total_provider_results: number;
  items: DiscoveryPreviewItem[];
};

export type DiscoveryPreviewEnrichmentMetadata = {
  success: boolean;
  attempted_pages: EnrichmentAttemptedPage[];
  fetched_page_urls: string[];
  extracted_contacts: EnrichmentExtractedContact[];
  email_found: boolean;
  instagram_found: boolean;
  contact_form_found: boolean;
  no_email_found: boolean;
  skipped_reason: string | null;
  error_message: string | null;
};

export type DiscoveryPreviewEnrichmentRequest = {
  preview: DiscoveryPreviewResponse;
  client_result_ids: string[];
  skip_blocked?: boolean;
};

export type DiscoveryPreviewEnrichmentResponse = {
  preview: DiscoveryPreviewResponse;
  summary: {
    requested: number;
    processed: number;
    success_count: number;
    emails_found: number;
    instagrams_found: number;
    contact_forms_found: number;
    no_email_found: number;
    skipped_no_website: number;
    blocked_after_enrichment: number;
    errors: number;
    error_messages: string[];
  };
};

export type DiscoveryPreviewWebsiteRecoveryRequest = {
  preview: DiscoveryPreviewResponse;
  client_result_ids: string[];
  skip_blocked?: boolean;
};

export type DiscoveryPreviewWebsiteRecoveryResponse = {
  preview: DiscoveryPreviewResponse;
  summary: {
    requested: number;
    processed: number;
    recovered_count: number;
    no_website_found: number;
    skipped_existing_website: number;
    skipped_missing_place_id: number;
    skipped_blocked: number;
    blocked_after_recovery: number;
    errors: number;
    error_messages: string[];
  };
};

export type DiscoveryImportRequest = {
  request: DiscoverySearchRequest;
  preview: DiscoveryPreviewResponse;
  selected_client_result_ids: string[];
  skip_blocked?: boolean;
};

export type DiscoveryImportResponse = {
  batch: {
    id: number;
    status: string;
    source_provider: string | null;
    source_query: string | null;
    location_label: string | null;
    record_count: number;
    lead_count: number;
    started_at: string | null;
    completed_at: string | null;
    created_at: string;
    updated_at: string;
  };
  batch_id: number;
  provider: string;
  resolved_location: ResolvedLocation;
  total_preview_items: number;
  selected_items: number;
  saved_items: number;
  skipped_blocked: number;
  created_leads: number;
  updated_leads: number;
  saved_lead_ids: number[];
  leads: LeadSummary[];
  skipped_items: Array<{
    client_result_id: string;
    business_name: string;
    reason: string;
    exclusion: DiscoveryExclusionMetadata;
  }>;
};

export type ExclusionRuleCreateRequest = {
  rule_type: ExclusionRuleType;
  pattern: string;
  reason?: string | null;
  is_active?: boolean;
  reapply_existing_leads?: boolean;
};

export type ExclusionRuleCreateResponse = {
  rule: {
    id: number;
    organization_id: number;
    rule_type: string;
    pattern: string;
    normalized_pattern: string;
    reason: string | null;
    is_active: boolean;
    created_at: string;
    updated_at: string;
  };
  reapply_summary: {
    evaluated: number;
    blocked: number;
    unblocked: number;
    unchanged: number;
  } | null;
};
