"use client";

import { useQuery } from "@tanstack/react-query";

import { getLeadDetail } from "@/lib/api/leads";
import type { LeadContactRead, LeadDetail } from "@/lib/api/types";

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
