import type { LeadDetail } from "@/lib/api/types";

export const demoSalesReps = [
  { id: 1, name: "Marina Costa", email: "marina@example.com" },
  { id: 2, name: "Rafael Lima", email: "rafael@example.com" },
  { id: 3, name: "Ana Torres", email: "ana@example.com" },
  { id: 4, name: "Sofia Meyer", email: "sofia@example.com" },
];

export const demoSalesRegions = [
  { id: 1, name: "North America West", region_type: "region", state: null, code: "NA-WEST" },
  { id: 2, name: "North America East", region_type: "region", state: null, code: "NA-EAST" },
  { id: 3, name: "United Kingdom", region_type: "region", state: null, code: "UK" },
  { id: 4, name: "Europe", region_type: "region", state: null, code: "EU" },
  { id: 5, name: "Asia Pacific", region_type: "region", state: null, code: "APAC" },
];

export const demoMarketSegments = [
  { id: 1, key: "healthcare", name: "Healthcare" },
  { id: 2, key: "food_service", name: "Food service" },
  { id: 3, key: "beauty_wellness", name: "Beauty & wellness" },
  { id: 4, key: "b2b_operations", name: "B2B operations" },
];

export const demoMarketSubsegments = [
  { id: 1, key: "dental_clinic", name: "Dental clinics", market_segment_id: 1 },
  { id: 2, key: "restaurant", name: "Restaurants", market_segment_id: 2 },
  { id: 3, key: "aesthetic_clinic", name: "Aesthetic clinics", market_segment_id: 3 },
  { id: 4, key: "logistics_provider", name: "Logistics providers", market_segment_id: 4 },
];

const now = "2026-06-01T12:00:00.000Z";

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
    notes: overrides.notes ?? "Fictional demo lead. The full project supports live provider data when backend keys are configured.",
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
        message: "Lead loaded from demo fixture.",
        metadata_json: {},
        created_at: now,
      },
    ],
  };
  return base;
}

export function normalize(value: string) {
  return value.toLocaleLowerCase("en").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z0-9\s]/gi, "").replace(/\s+/g, " ").trim();
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
