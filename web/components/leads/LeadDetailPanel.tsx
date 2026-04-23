"use client";

import { useQuery } from "@tanstack/react-query";

import { getLeadDetail } from "@/lib/api/leads";
import type {
  EnrichmentAttemptedPage,
  EnrichmentExtractedContact,
  LeadContactRead,
  LeadDetail,
} from "@/lib/api/types";

type LeadDetailPanelProps = {
  leadId: number | null;
};

export function LeadDetailPanel({ leadId }: LeadDetailPanelProps) {
  const detailQuery = useQuery({
    queryKey: ["lead-detail", leadId],
    queryFn: () => getLeadDetail(leadId as number),
    enabled: leadId !== null,
  });

  if (leadId === null) {
    return (
      <aside className="rounded-md border border-neutral-200 bg-white p-6">
        <p className="text-sm font-medium text-neutral-950">Choose a lead</p>
        <p className="mt-1 text-sm text-neutral-500">Company details, contacts, enrichment, and history are ready here.</p>
      </aside>
    );
  }

  if (detailQuery.isLoading) {
    return (
      <aside className="rounded-md border border-neutral-200 bg-white p-6">
        <p className="text-sm text-neutral-500">Loading lead detail</p>
      </aside>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <aside className="rounded-md border border-rose-200 bg-white p-6">
        <p className="text-sm font-medium text-rose-800">Lead detail unavailable</p>
        <p className="mt-1 text-sm text-neutral-500">The backend did not return this lead.</p>
      </aside>
    );
  }

  const lead = detailQuery.data;
  const latestEnrichment = lead.enrichments[0];
  const latestEnrichmentAudit = getLatestEnrichmentAudit(lead);

  return (
    <aside className="rounded-md border border-neutral-200 bg-white">
      <div className="border-b border-neutral-200 p-4">
        <p className="text-xs font-semibold uppercase text-cyan-700">Lead detail</p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-neutral-950">{lead.business_name}</h2>
          {lead.is_blocked ? <BlockedBadge /> : null}
        </div>
        <p className="mt-1 text-sm text-neutral-500">
          {[lead.category, lead.city, lead.state].filter(Boolean).join(" - ") || "No location"}
        </p>
        {lead.is_blocked ? (
          <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {lead.blocked_reason ?? "Matched an active exclusion rule."}
          </p>
        ) : null}
      </div>

      <div className="divide-y divide-neutral-200">
        <DetailSection title="Company">
          <InfoGrid>
            <InfoItem label="Website" value={lead.website} />
            <InfoItem label="Domain" value={lead.domain} />
            <InfoItem label="Address" value={compact([lead.address, lead.neighborhood, lead.postal_code])} />
            <InfoItem label="Status" value={labelToken(lead.status)} />
            <InfoItem label="Score" value={String(lead.lead_score)} />
            <InfoItem label="Source" value={labelToken(lead.lead_source_type)} />
          </InfoGrid>
        </DetailSection>

        <DetailSection title="Best contacts">
          <div className="grid gap-2">
            <ContactLine label="Email" value={lead.email} />
            <ContactLine label="WhatsApp" value={lead.whatsapp} />
            <ContactLine label="Phone" value={lead.phone} />
            <ContactLine label="Instagram" value={lead.instagram} />
          </div>
          <ContactEvidence contacts={lead.contacts} />
        </DetailSection>

        <DetailSection title="Assignment and classification">
          <InfoGrid>
            <InfoItem label="Assigned rep" value={lead.assigned_sales_rep?.name} />
            <InfoItem label="Sales region" value={lead.sales_region?.name} />
            <InfoItem label="Segment" value={lead.market_segment?.name} />
            <InfoItem label="Subsegment" value={lead.market_subsegment?.name} />
            <InfoItem label="Assignment rule" value={lead.assignment_rule?.name} />
            <InfoItem label="Assigned at" value={formatDateTime(lead.assigned_at)} />
          </InfoGrid>
          {lead.assignment_explanation ? (
            <p className="mt-3 rounded-md bg-neutral-50 p-3 text-sm text-neutral-700">{lead.assignment_explanation}</p>
          ) : null}
        </DetailSection>

        <DetailSection title="Lead quality">
          <InfoGrid>
            <InfoItem label="Target fit" value={labelToken(lead.company_size_fit)} />
            <InfoItem label="Trade type" value={labelToken(lead.trade_type)} />
            <InfoItem label="Classified at" value={formatDateTime(lead.quality_classified_at)} />
          </InfoGrid>
          <div className="mt-3 grid gap-2 text-sm text-neutral-700">
            <p>{lead.company_size_fit_explanation ?? "No target fit explanation yet."}</p>
            <p>{lead.trade_type_explanation ?? "No trade type explanation yet."}</p>
          </div>
        </DetailSection>

        <DetailSection title="Enrichment">
          <InfoGrid>
            <InfoItem label="Last enriched" value={formatDateTime(lead.last_enriched_at)} />
            <InfoItem label="Records" value={String(lead.enrichments.length)} />
            <InfoItem label="Latest page" value={latestEnrichment?.page_type} />
            <InfoItem label="Latest status" value={latestEnrichment?.http_status ? String(latestEnrichment.http_status) : null} />
          </InfoGrid>
          {latestEnrichment?.source_url ? (
            <p className="mt-3 break-words text-sm text-neutral-600">{latestEnrichment.source_url}</p>
          ) : null}
          <EnrichmentAudit audit={latestEnrichmentAudit} />
        </DetailSection>

        <DetailSection title="Notes">
          <p className="whitespace-pre-wrap text-sm text-neutral-700">{lead.notes || "No notes yet."}</p>
          {lead.tags.length ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {lead.tags.map((tag) => (
                <span key={tag} className="rounded-md border border-neutral-200 px-2 py-1 text-xs text-neutral-600">
                  {tag}
                </span>
              ))}
            </div>
          ) : null}
        </DetailSection>

        <DetailSection title="Duplicate summary">
          <InfoGrid>
            <InfoItem label="Duplicate" value={lead.is_duplicate ? "Yes" : "No"} />
            <InfoItem label="Duplicate of" value={lead.duplicate_of_lead_id ? String(lead.duplicate_of_lead_id) : null} />
          </InfoGrid>
          <p className="mt-3 text-sm text-neutral-700">{lead.duplicate_reason ?? "No duplicate reason recorded."}</p>
        </DetailSection>

        <DetailSection title="Activity history">
          {lead.activity_logs.length ? (
            <ol className="space-y-3">
              {lead.activity_logs.slice(0, 8).map((activity) => (
                <li key={activity.id} className="border-l-2 border-cyan-200 pl-3">
                  <p className="text-sm font-medium text-neutral-900">{labelToken(activity.action)}</p>
                  <p className="text-sm text-neutral-600">{activity.message ?? activity.actor}</p>
                  <p className="text-xs text-neutral-500">{formatDateTime(activity.created_at)}</p>
                </li>
              ))}
            </ol>
          ) : (
            <p className="text-sm text-neutral-500">No activity yet.</p>
          )}
        </DetailSection>
      </div>
    </aside>
  );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="p-4">
      <h3 className="text-sm font-semibold text-neutral-950">{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function InfoGrid({ children }: { children: React.ReactNode }) {
  return <dl className="grid gap-3 sm:grid-cols-2">{children}</dl>;
}

function InfoItem({ label, value }: { label: string; value?: string | null }) {
  return (
    <div>
      <dt className="text-xs font-medium text-neutral-500">{label}</dt>
      <dd className="mt-1 break-words text-sm text-neutral-900">{value || "None"}</dd>
    </div>
  );
}

function BlockedBadge() {
  return (
    <span className="inline-flex rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-800">
      Blocked
    </span>
  );
}

function ContactLine({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-neutral-200 px-3 py-2">
      <span className="text-sm font-medium text-neutral-700">{label}</span>
      <span className="break-all text-right text-sm text-neutral-950">{value || "None"}</span>
    </div>
  );
}

function ContactEvidence({ contacts }: { contacts: LeadContactRead[] }) {
  if (!contacts.length) {
    return <p className="mt-3 text-sm text-neutral-500">No contact evidence recorded.</p>;
  }

  return (
    <div className="mt-4">
      <p className="text-xs font-medium uppercase text-neutral-500">Evidence</p>
      <div className="mt-2 space-y-2">
        {contacts.slice(0, 6).map((contact) => (
          <div key={contact.id} className="rounded-md bg-neutral-50 px-3 py-2 text-sm">
            <p className="font-medium text-neutral-900">
              {labelToken(contact.contact_type)}: {contact.normalized_value || contact.raw_value}
            </p>
            <p className="text-xs text-neutral-500">
              Confidence {Math.round(contact.confidence * 100)}%
              {contact.is_primary ? " - Primary" : ""}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function EnrichmentAudit({ audit }: { audit: EnrichmentAuditData | null }) {
  if (!audit) {
    return <p className="mt-4 text-sm text-neutral-500">No enrichment audit recorded yet.</p>;
  }

  return (
    <div className="mt-4 space-y-3 rounded-md border border-neutral-200 bg-neutral-50 p-3">
      <div className={`rounded-md px-3 py-2 text-sm ${audit.noEmailFound ? "border border-amber-200 bg-amber-50 text-amber-950" : "border border-emerald-200 bg-emerald-50 text-emerald-950"}`}>
        <p className="font-medium">{audit.noEmailFound ? "Latest run finished without finding a public email." : "Latest run captured public contact evidence."}</p>
        <p className="mt-1 text-xs opacity-80">{formatDateTime(audit.createdAt) ?? "Audit time unavailable"}</p>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <AuditList
          title="Attempted pages"
          emptyMessage="No attempted pages were recorded."
          items={audit.attemptedPages.map((page) => ({
            key: `${page.url}-${page.page_type ?? "page"}`,
            title: labelToken(page.page_type) ?? "Page",
            value: page.url,
            meta: compact([
              page.fetched ? `Fetched${page.http_status ? ` (${page.http_status})` : ""}` : "Not fetched",
              page.discovered_from_url ? `From ${page.discovered_from_url}` : null,
              page.note,
            ]),
          }))}
        />
        <AuditList
          title="Fetched pages"
          emptyMessage="No fetched pages were recorded."
          items={audit.fetchedPageUrls.map((url) => ({
            key: url,
            title: "Fetched",
            value: url,
            meta: null,
          }))}
        />
      </div>

      <AuditList
        title="Extracted contacts"
        emptyMessage="No extracted contacts were recorded for the latest run."
        items={audit.extractedContacts.map((contact, index) => ({
          key: `${contact.source_url}-${contact.normalized_value ?? contact.raw_value}-${index}`,
          title: `${labelToken(contact.contact_type) ?? "Contact"}: ${contact.normalized_value || contact.raw_value}`,
          value: contact.source_url,
          meta: compact([
            `Confidence ${Math.round(contact.confidence * 100)}%`,
            contact.addedToLead ? "Added to lead" : "Already known",
            contact.note,
          ]),
        }))}
      />
    </div>
  );
}

function AuditList({
  title,
  items,
  emptyMessage,
}: {
  title: string;
  items: Array<{ key: string; title: string; value: string; meta: string | null }>;
  emptyMessage: string;
}) {
  return (
    <div>
      <p className="text-xs font-medium uppercase text-neutral-500">{title}</p>
      {items.length ? (
        <div className="mt-2 space-y-2">
          {items.slice(0, 6).map((item) => (
            <div key={item.key} className="rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm">
              <p className="font-medium text-neutral-900">{item.title}</p>
              <p className="mt-1 break-all text-xs text-neutral-600">{item.value}</p>
              {item.meta ? <p className="mt-1 text-xs text-neutral-500">{item.meta}</p> : null}
            </div>
          ))}
          {items.length > 6 ? (
            <p className="text-xs text-neutral-500">{items.length - 6} more not shown.</p>
          ) : null}
        </div>
      ) : (
        <p className="mt-2 text-sm text-neutral-500">{emptyMessage}</p>
      )}
    </div>
  );
}

function compact(values: Array<string | null | undefined>) {
  const text = values.filter(Boolean).join(" - ");
  return text || null;
}

function labelToken(value?: string | null) {
  if (!value) {
    return null;
  }
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

type EnrichmentAuditData = {
  attemptedPages: EnrichmentAttemptedPage[];
  fetchedPageUrls: string[];
  extractedContacts: Array<EnrichmentExtractedContact & { addedToLead: boolean }>;
  noEmailFound: boolean;
  createdAt: string | null;
};

function getLatestEnrichmentAudit(lead: LeadDetail): EnrichmentAuditData | null {
  const activity = lead.activity_logs.find((item) => item.action === "enriched");
  if (!activity) {
    return null;
  }

  const metadata = asRecord(activity.metadata_json);
  if (!metadata) {
    return null;
  }
  const attemptedPages = parseAttemptedPages(metadata.attempted_pages);
  const fetchedPageUrls = parseStringArray(metadata.fetched_page_urls);
  const extractedContacts = parseExtractedContacts(metadata.extracted_contacts);

  return {
    attemptedPages,
    fetchedPageUrls,
    extractedContacts,
    noEmailFound: Boolean(metadata.no_email_found),
    createdAt: activity.created_at,
  };
}

function parseAttemptedPages(value: unknown): EnrichmentAttemptedPage[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null && typeof item.url === "string")
    .map((item) => ({
      url: String(item.url),
      page_type: asNullableString(item.page_type),
      discovered_from_url: asNullableString(item.discovered_from_url),
      fetched: Boolean(item.fetched),
      http_status: asNullableNumber(item.http_status),
      robots_allowed: item.robots_allowed !== false,
      note: asNullableString(item.note),
    }));
}

function parseExtractedContacts(
  value: unknown,
): Array<EnrichmentExtractedContact & { addedToLead: boolean }> {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => asRecord(item))
    .filter(
      (item): item is Record<string, unknown> =>
        item !== null && typeof item.contact_type === "string" && typeof item.source_url === "string",
    )
    .map((item) => ({
      contact_type: String(item.contact_type),
      raw_value: asNullableString(item.raw_value) ?? "",
      normalized_value: asNullableString(item.normalized_value),
      source_url: String(item.source_url),
      confidence: typeof item.confidence === "number" ? item.confidence : 0,
      label: asNullableString(item.label),
      note: asNullableString(item.note),
      added_to_lead: Boolean(item.added_to_lead),
      addedToLead: Boolean(item.added_to_lead),
    }));
}

function parseStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string");
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function asNullableString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asNullableNumber(value: unknown): number | null {
  return typeof value === "number" ? value : null;
}
