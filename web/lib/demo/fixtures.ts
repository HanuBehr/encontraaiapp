import type { LeadDetail, LeadImportBatchResponse } from "@/lib/api/types";

export const demoSalesReps = [
  { id: 1, name: "Marina Costa", email: "marina@example.com" },
  { id: 2, name: "Rafael Lima", email: "rafael@example.com" },
  { id: 3, name: "Ana Torres", email: "ana@example.com" },
];

export const demoSalesRegions = [
  { id: 1, name: "São Paulo Metro", region_type: "state", state: "SP", code: "SP-METRO" },
  { id: 2, name: "Interior SP", region_type: "state", state: "SP", code: "SP-INT" },
  { id: 3, name: "Rio de Janeiro", region_type: "state", state: "RJ", code: "RJ" },
];

export const demoMarketSegments = [
  { id: 1, key: "healthcare", name: "Healthcare" },
  { id: 2, key: "food_service", name: "Food service" },
  { id: 3, key: "beauty_wellness", name: "Beauty & wellness" },
  { id: 4, key: "construction", name: "Construction" },
];

export const demoMarketSubsegments = [
  { id: 1, key: "dental_clinic", name: "Dental clinics", market_segment_id: 1 },
  { id: 2, key: "restaurant", name: "Restaurants", market_segment_id: 2 },
  { id: 3, key: "aesthetic_clinic", name: "Aesthetic clinics", market_segment_id: 3 },
  { id: 4, key: "material_store", name: "Building materials", market_segment_id: 4 },
];

const now = "2026-06-01T12:00:00.000Z";

export const demoSeedLeads: LeadDetail[] = [
  lead({ id: 101, business_name: "Aurora Dental Studio", category: "Dental clinic", city: "São Paulo", state: "SP", website: "https://auroradental.example", domain: "auroradental.example", email: "hello@auroradental.example", phone: "+55 11 4002-1001", whatsapp: "+55 11 94002-1001", instagram: "https://instagram.com/auroradental", status: "approved", lead_score: 88, assigned_sales_rep_id: 1, sales_region_id: 1, market_segment_id: 1, market_subsegment_id: 1, company_size_fit: "ideal_sme", trade_type: "varejo", cnpj: "12.345.678/0001-90", legal_name: "Aurora Dental Studio Ltda", cnpj_match_status: "matched", cnpj_match_confidence: 0.94 }),
  lead({ id: 102, business_name: "Clínica Sorriso Vila Mariana", category: "Dental clinic", city: "São Paulo", state: "SP", website: "https://sorrisovm.example", domain: "sorrisovm.example", email: "contato@sorrisovm.example", phone: "+55 11 4002-1002", whatsapp: "+55 11 94002-1002", status: "reviewed", lead_score: 81, assigned_sales_rep_id: 1, sales_region_id: 1, market_segment_id: 1, market_subsegment_id: 1, company_size_fit: "ideal_sme", trade_type: "varejo", cnpj_match_status: "needs_review", cnpj_match_confidence: 0.72 }),
  lead({ id: 103, business_name: "Implant Care Paulista", category: "Dental implants", city: "São Paulo", state: "SP", website: "https://implantcare.example", domain: "implantcare.example", email: "agenda@implantcare.example", phone: "+55 11 4002-1003", status: "new", lead_score: 75, sales_region_id: 1, market_segment_id: 1, market_subsegment_id: 1, company_size_fit: "possible_sme", trade_type: "varejo" }),
  lead({ id: 104, business_name: "Bistrô Jardim Campinas", category: "Restaurant", city: "Campinas", state: "SP", website: "https://bistrojardim.example", domain: "bistrojardim.example", email: "eventos@bistrojardim.example", whatsapp: "+55 19 94002-2001", instagram: "https://instagram.com/bistrojardim", status: "contacted", lead_score: 83, assigned_sales_rep_id: 2, sales_region_id: 2, market_segment_id: 2, market_subsegment_id: 2, company_size_fit: "ideal_sme", trade_type: "varejo", cnpj_match_status: "matched", cnpj: "23.456.789/0001-10", legal_name: "Bistrô Jardim Campinas Ltda", cnpj_match_confidence: 0.91 }),
  lead({ id: 105, business_name: "Cantina Bella Ponte", category: "Italian restaurant", city: "Campinas", state: "SP", website: "https://bellaponte.example", domain: "bellaponte.example", phone: "+55 19 4002-2002", instagram: "https://instagram.com/bellaponte", status: "interested", lead_score: 79, assigned_sales_rep_id: 2, sales_region_id: 2, market_segment_id: 2, market_subsegment_id: 2, company_size_fit: "possible_sme", trade_type: "varejo" }),
  lead({ id: 106, business_name: "Café Distrito 19", category: "Cafe", city: "Campinas", state: "SP", website: null, domain: null, phone: "+55 19 4002-2003", status: "new", lead_score: 64, sales_region_id: 2, market_segment_id: 2, market_subsegment_id: 2, company_size_fit: "possible_sme", trade_type: "varejo" }),
  lead({ id: 107, business_name: "Luma Estética Avançada", category: "Aesthetic clinic", city: "Rio de Janeiro", state: "RJ", website: "https://lumaestetica.example", domain: "lumaestetica.example", email: "contato@lumaestetica.example", whatsapp: "+55 21 94002-3001", instagram: "https://instagram.com/lumaestetica", status: "replied", lead_score: 86, assigned_sales_rep_id: 3, sales_region_id: 3, market_segment_id: 3, market_subsegment_id: 3, company_size_fit: "ideal_sme", trade_type: "varejo", cnpj_match_status: "matched", cnpj: "34.567.890/0001-11", legal_name: "Luma Estética Avançada Ltda", cnpj_match_confidence: 0.89 }),
  lead({ id: 108, business_name: "Dermal Rio Clinic", category: "Skin care clinic", city: "Rio de Janeiro", state: "RJ", website: "https://dermalrio.example", domain: "dermalrio.example", email: "agenda@dermalrio.example", phone: "+55 21 4002-3002", status: "approved", lead_score: 82, assigned_sales_rep_id: 3, sales_region_id: 3, market_segment_id: 3, market_subsegment_id: 3, company_size_fit: "ideal_sme", trade_type: "varejo", cnpj_match_status: "needs_review", cnpj_match_confidence: 0.68 }),
  lead({ id: 109, business_name: "Forma & Pele Botafogo", category: "Beauty clinic", city: "Rio de Janeiro", state: "RJ", website: null, domain: null, phone: "+55 21 4002-3003", instagram: "https://instagram.com/formaepelerio", status: "new", lead_score: 70, sales_region_id: 3, market_segment_id: 3, market_subsegment_id: 3, company_size_fit: "possible_sme", trade_type: "varejo" }),
  lead({ id: 110, business_name: "Constrular Norte", category: "Building materials", city: "São Paulo", state: "SP", website: "https://constrularnorte.example", domain: "constrularnorte.example", email: "vendas@constrularnorte.example", whatsapp: "+55 11 94002-4001", status: "approved", lead_score: 84, assigned_sales_rep_id: 1, sales_region_id: 1, market_segment_id: 4, market_subsegment_id: 4, company_size_fit: "ideal_sme", trade_type: "distribuidora" }),
  lead({ id: 111, business_name: "Materiais Ponte Verde", category: "Construction supplier", city: "Campinas", state: "SP", website: "https://ponteverde.example", domain: "ponteverde.example", phone: "+55 19 4002-4002", status: "reviewed", lead_score: 76, assigned_sales_rep_id: 2, sales_region_id: 2, market_segment_id: 4, market_subsegment_id: 4, company_size_fit: "possible_sme", trade_type: "atacado" }),
  lead({ id: 112, business_name: "Blocked Demo Supplier", category: "Supplier", city: "São Paulo", state: "SP", website: "https://blocked-demo.example", domain: "blocked-demo.example", phone: "+55 11 4002-9999", status: "do_not_contact", lead_score: 20, sales_region_id: 1, market_segment_id: 4, market_subsegment_id: 4, company_size_fit: "unknown", trade_type: "unknown", is_blocked: true, blocked_reason: "Demo exclusion rule: competitor / do not contact." }),
];

export const demoInitialImportBatch: LeadImportBatchResponse = {
  id: 1,
  batch_type: "demo_seed",
  status: "completed",
  source_provider: "demo",
  source_query: "Recruiter demo seed leads",
  location_label: "Demo workspace",
  record_count: demoSeedLeads.length,
  lead_count: demoSeedLeads.length,
  lead_ids: demoSeedLeads.map((lead) => lead.id),
  started_at: now,
  completed_at: now,
  created_at: now,
  updated_at: now,
};

type LeadOverrides = Partial<LeadDetail> & Pick<LeadDetail, "id" | "business_name" | "city" | "state">;

export function lead(overrides: LeadOverrides): LeadDetail {
  const rep = demoSalesReps.find((item) => item.id === overrides.assigned_sales_rep_id) ?? null;
  const region = demoSalesRegions.find((item) => item.id === overrides.sales_region_id) ?? null;
  const segment = demoMarketSegments.find((item) => item.id === overrides.market_segment_id) ?? null;
  const subsegment = demoMarketSubsegments.find((item) => item.id === overrides.market_subsegment_id) ?? null;
  const domain = overrides.domain ?? domainFromWebsite(overrides.website ?? null);
  const base: LeadDetail = {
    id: overrides.id,
    business_name: overrides.business_name,
    normalized_business_name: normalize(overrides.business_name),
    category: overrides.category ?? null,
    address: overrides.address ?? `${100 + overrides.id} Demo Avenue`,
    postal_code: overrides.postal_code ?? null,
    neighborhood: overrides.neighborhood ?? null,
    city: overrides.city,
    state: overrides.state,
    email: overrides.email ?? null,
    phone: overrides.phone ?? null,
    whatsapp: overrides.whatsapp ?? null,
    instagram: overrides.instagram ?? null,
    website: overrides.website ?? null,
    cnpj: overrides.cnpj ?? null,
    legal_name: overrides.legal_name ?? null,
    cnpj_match_status: overrides.cnpj_match_status ?? "unknown",
    cnpj_match_confidence: overrides.cnpj_match_confidence ?? null,
    cnpj_last_enriched_at: overrides.cnpj_last_enriched_at ?? null,
    cnpj_source_provider: overrides.cnpj_source_provider ?? null,
    cnpj_metadata_json: overrides.cnpj_metadata_json ?? {},
    lead_score: overrides.lead_score ?? 70,
    status: overrides.status ?? "new",
    lead_source_type: overrides.lead_source_type ?? "demo_seed",
    do_not_contact: overrides.do_not_contact ?? false,
    approved_for_send: overrides.approved_for_send ?? false,
    last_enriched_at: overrides.last_enriched_at ?? now,
    last_contacted_at: overrides.last_contacted_at ?? null,
    follow_up_date: overrides.follow_up_date ?? null,
    is_duplicate: overrides.is_duplicate ?? false,
    duplicate_of_lead_id: overrides.duplicate_of_lead_id ?? null,
    duplicate_reason: overrides.duplicate_reason ?? null,
    sales_region_id: overrides.sales_region_id ?? null,
    market_segment_id: overrides.market_segment_id ?? null,
    market_subsegment_id: overrides.market_subsegment_id ?? null,
    assigned_sales_rep_id: overrides.assigned_sales_rep_id ?? null,
    assignment_rule_id: overrides.assignment_rule_id ?? null,
    assigned_at: overrides.assigned_at ?? (overrides.assigned_sales_rep_id ? now : null),
    is_blocked: overrides.is_blocked ?? false,
    blocked_reason: overrides.blocked_reason ?? null,
    blocked_rule_id: overrides.blocked_rule_id ?? null,
    blocked_at: overrides.blocked_at ?? null,
    company_size_fit: overrides.company_size_fit ?? "possible_sme",
    company_size_fit_explanation: overrides.company_size_fit_explanation ?? "Demo scoring based on category, public web presence, and contact coverage.",
    trade_type: overrides.trade_type ?? "varejo",
    trade_type_explanation: overrides.trade_type_explanation ?? "Demo classification inferred from the business category.",
    quality_classified_at: overrides.quality_classified_at ?? now,
    sales_region: region,
    market_segment: segment,
    market_subsegment: subsegment,
    assigned_sales_rep: rep,
    assignment_rule: overrides.assignment_rule ?? null,
    created_at: overrides.created_at ?? now,
    updated_at: overrides.updated_at ?? now,
    latitude: overrides.latitude ?? null,
    longitude: overrides.longitude ?? null,
    domain,
    google_maps_url: overrides.google_maps_url ?? `https://maps.google.com/?q=${encodeURIComponent(overrides.business_name)}`,
    google_place_id: overrides.google_place_id ?? `demo-place-${overrides.id}`,
    source_provider: overrides.source_provider ?? "demo",
    source_url: overrides.source_url ?? null,
    material_profile: overrides.material_profile ?? {},
    score_breakdown: overrides.score_breakdown ?? {},
    assignment_explanation: overrides.assignment_explanation ?? null,
    assignment_metadata_json: overrides.assignment_metadata_json ?? {},
    company_size_fit_metadata_json: overrides.company_size_fit_metadata_json ?? {},
    trade_type_metadata_json: overrides.trade_type_metadata_json ?? {},
    notes: overrides.notes ?? "Fictional recruiter demo lead. The full project supports live provider data when backend keys are configured.",
    tags: overrides.tags ?? ["demo"],
    owner: overrides.owner ?? null,
    contacts: overrides.contacts ?? demoContacts(overrides.id, overrides.email ?? null, overrides.whatsapp ?? overrides.phone ?? null, overrides.instagram ?? null, overrides.website ?? null),
    enrichments: overrides.enrichments ?? [],
    activity_logs: overrides.activity_logs ?? [
      {
        id: overrides.id * 10,
        entity_type: "lead",
        entity_id: overrides.id,
        action: "imported",
        actor: "demo",
        message: "Lead loaded from recruiter demo fixture.",
        metadata_json: {},
        created_at: now,
      },
    ],
  };
  return base;
}

export function normalize(value: string) {
  return value.toLocaleLowerCase("pt-BR").replace(/[^a-z0-9\s]/gi, "").replace(/\s+/g, " ").trim();
}

function domainFromWebsite(website: string | null) {
  if (!website) {
    return null;
  }
  try {
    return new URL(website).hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function demoContacts(id: number, email: string | null, phone: string | null, instagram: string | null, website: string | null) {
  const contacts = [];
  let contactId = id * 100;
  if (email) {
    contacts.push(contact(++contactId, "email", email, website));
  }
  if (phone) {
    contacts.push(contact(++contactId, "whatsapp", phone, website));
  }
  if (instagram) {
    contacts.push(contact(++contactId, "instagram", instagram, website));
  }
  return contacts;
}

function contact(id: number, type: string, value: string, website: string | null) {
  return {
    id,
    contact_type: type,
    raw_value: value,
    normalized_value: value,
    label: "Demo public contact",
    source_url: website,
    source_kind: "demo_fixture",
    source_record_type: "lead",
    source_record_id: id,
    confidence: 0.9,
    is_primary: true,
    note: null,
    created_at: now,
    updated_at: now,
  };
}
