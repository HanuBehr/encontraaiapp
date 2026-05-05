"use client";

import { useQuery } from "@tanstack/react-query";

import { formatLeadLabel } from "@/lib/format/lead-labels";
import { getLeadDetail } from "@/lib/api/leads";
import type {
  EnrichmentAttemptedPage,
  EnrichmentExtractedContact,
  LeadContactRead,
  LeadDetail,
} from "@/lib/api/types";
import { formatUserFacingError } from "@/lib/ui/messages";

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
        <p className="text-sm font-medium text-neutral-950">Selecione um lead</p>
        <p className="mt-1 text-sm text-neutral-500">
          Os detalhes da empresa, contatos, enriquecimento e histórico aparecem aqui.
        </p>
      </aside>
    );
  }

  if (detailQuery.isLoading) {
    return (
      <aside className="rounded-md border border-neutral-200 bg-white p-6">
        <p className="text-sm text-neutral-500">Carregando detalhes do lead...</p>
      </aside>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <aside className="rounded-md border border-rose-200 bg-white p-6">
        <p className="text-sm font-medium text-rose-800">Não foi possível carregar este lead</p>
        <p className="mt-1 text-sm text-neutral-500">
          {formatUserFacingError(detailQuery.error, "Tente novamente em instantes.")}
        </p>
      </aside>
    );
  }

  const lead = detailQuery.data;
  const latestEnrichment = lead.enrichments[0];
  const latestEnrichmentAudit = getLatestEnrichmentAudit(lead);
  const cnpjStatusHint = getCnpjStatusHint(lead);

  return (
    <aside className="rounded-md border border-neutral-200 bg-white">
      <div className="border-b border-neutral-200 p-4">
        <p className="text-xs font-semibold uppercase text-cyan-700">Detalhes do lead</p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-neutral-950">{lead.business_name}</h2>
          {lead.is_blocked ? <BlockedBadge /> : null}
        </div>
        <p className="mt-1 text-sm text-neutral-500">
          {[lead.category, lead.city, lead.state].filter(Boolean).join(" - ") || "Local não informado"}
        </p>
        {lead.is_blocked ? (
          <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {lead.blocked_reason ?? "Corresponde a uma regra de exclusão ativa."}
          </p>
        ) : null}
      </div>

      <div className="divide-y divide-neutral-200">
        <DetailSection title="Empresa">
          <InfoGrid>
            <InfoItem label="Website" value={lead.website} />
            <InfoItem label="Domínio" value={lead.domain} />
            <InfoItem label="Endereço" value={compact([lead.address, lead.neighborhood, lead.postal_code])} />
            <InfoItem label="Status" value={labelToken(lead.status)} />
            <InfoItem label="Score" value={String(lead.lead_score)} />
            <InfoItem label="Origem" value={labelToken(lead.lead_source_type)} />
          </InfoGrid>
        </DetailSection>

        <DetailSection title="Cadastro">
          <InfoGrid>
            <InfoItem label="CNPJ" value={lead.cnpj ?? "Sem CNPJ"} />
            <InfoItem label="Razão Social" value={lead.legal_name} />
            <InfoItem label="Status CNPJ" value={cnpjStatusLabel(lead.cnpj_match_status)} />
            <InfoItem label="Confiança" value={formatConfidence(lead.cnpj_match_confidence)} />
            <InfoItem label="Última consulta" value={formatDateTime(lead.cnpj_last_enriched_at)} />
            <InfoItem label="Provedor" value={labelToken(lead.cnpj_source_provider)} />
          </InfoGrid>
          {cnpjStatusHint ? (
            <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {cnpjStatusHint}
            </p>
          ) : null}
          <p className="mt-3 text-xs text-neutral-500">
            Busca CNPJ já informado, tenta encontrar CNPJ no site da empresa e, se configurado, usa busca cadastral paga.
          </p>
        </DetailSection>

        <DetailSection title="Melhores contatos">
          <div className="grid gap-2">
            <ContactLine label="Email" value={lead.email} />
            <ContactLine label="WhatsApp" value={lead.whatsapp} />
            <ContactLine label="Telefone" value={lead.phone} />
            <ContactLine label="Instagram" value={lead.instagram} />
          </div>
          <ContactEvidence contacts={lead.contacts} />
        </DetailSection>

        <DetailSection title="Responsável e classificação">
          <InfoGrid>
            <InfoItem label="Responsável" value={lead.assigned_sales_rep?.name} />
            <InfoItem label="Região" value={lead.sales_region?.name} />
            <InfoItem label="Segmento" value={lead.market_segment?.name} />
            <InfoItem label="Subsegmento" value={lead.market_subsegment?.name} />
            <InfoItem label="Regra de atribuição" value={lead.assignment_rule?.name} />
            <InfoItem label="Atribuído em" value={formatDateTime(lead.assigned_at)} />
          </InfoGrid>
          {lead.assignment_explanation ? (
            <p className="mt-3 rounded-md bg-neutral-50 p-3 text-sm text-neutral-700">{lead.assignment_explanation}</p>
          ) : null}
        </DetailSection>

        <DetailSection title="Qualidade do lead">
          <InfoGrid>
            <InfoItem label="Perfil" value={labelToken(lead.company_size_fit)} />
            <InfoItem label="Operação" value={labelToken(lead.trade_type)} />
            <InfoItem label="Classificado em" value={formatDateTime(lead.quality_classified_at)} />
          </InfoGrid>
          <div className="mt-3 grid gap-2 text-sm text-neutral-700">
            <p>{lead.company_size_fit_explanation ?? "Ainda não há uma explicação de perfil."}</p>
            <p>{lead.trade_type_explanation ?? "Ainda não há uma explicação de operação."}</p>
          </div>
        </DetailSection>

        <DetailSection title="Enriquecimento">
          <InfoGrid>
            <InfoItem label="Último enriquecimento" value={formatDateTime(lead.last_enriched_at)} />
            <InfoItem label="Registros" value={String(lead.enrichments.length)} />
            <InfoItem label="Última página" value={labelToken(latestEnrichment?.page_type)} />
            <InfoItem
              label="Último status"
              value={latestEnrichment?.http_status ? String(latestEnrichment.http_status) : null}
            />
          </InfoGrid>
          {latestEnrichment?.source_url ? (
            <p className="mt-3 break-words text-sm text-neutral-600">{latestEnrichment.source_url}</p>
          ) : null}
          <EnrichmentAudit audit={latestEnrichmentAudit} />
        </DetailSection>

        <DetailSection title="Notas">
          <p className="whitespace-pre-wrap text-sm text-neutral-700">{lead.notes || "Nenhuma nota registrada."}</p>
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

        <DetailSection title="Duplicidade">
          <InfoGrid>
            <InfoItem label="Duplicado" value={lead.is_duplicate ? "Sim" : "Não"} />
            <InfoItem label="Duplicado de" value={lead.duplicate_of_lead_id ? String(lead.duplicate_of_lead_id) : null} />
          </InfoGrid>
          <p className="mt-3 text-sm text-neutral-700">{lead.duplicate_reason ?? "Nenhum motivo de duplicidade registrado."}</p>
        </DetailSection>

        <DetailSection title="Histórico">
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
            <p className="text-sm text-neutral-500">Nenhuma atividade registrada.</p>
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
      <dd className="mt-1 break-words text-sm text-neutral-900">{value || "Não informado"}</dd>
    </div>
  );
}

function BlockedBadge() {
  return (
    <span className="inline-flex rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-800">
      Bloqueado
    </span>
  );
}

function ContactLine({ label, value }: { label: string; value?: string | null }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-neutral-200 px-3 py-2">
      <span className="text-sm font-medium text-neutral-700">{label}</span>
      <span className="break-all text-right text-sm text-neutral-950">{value || "Não informado"}</span>
    </div>
  );
}

function ContactEvidence({ contacts }: { contacts: LeadContactRead[] }) {
  if (!contacts.length) {
    return <p className="mt-3 text-sm text-neutral-500">Nenhuma evidência de contato registrada.</p>;
  }

  return (
    <div className="mt-4">
      <p className="text-xs font-medium uppercase text-neutral-500">Evidências</p>
      <div className="mt-2 space-y-2">
        {contacts.slice(0, 6).map((contact) => (
          <div key={contact.id} className="rounded-md bg-neutral-50 px-3 py-2 text-sm">
            <p className="font-medium text-neutral-900">
              {labelToken(contact.contact_type)}: {contact.normalized_value || contact.raw_value}
            </p>
            <p className="text-xs text-neutral-500">
              Confiança {Math.round(contact.confidence * 100)}%
              {contact.is_primary ? " - Principal" : ""}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function EnrichmentAudit({ audit }: { audit: EnrichmentAuditData | null }) {
  if (!audit) {
    return <p className="mt-4 text-sm text-neutral-500">Nenhum histórico de enriquecimento registrado.</p>;
  }

  return (
    <div className="mt-4 space-y-3 rounded-md border border-neutral-200 bg-neutral-50 p-3">
      <div className={`rounded-md px-3 py-2 text-sm ${audit.noEmailFound ? "border border-amber-200 bg-amber-50 text-amber-950" : "border border-emerald-200 bg-emerald-50 text-emerald-950"}`}>
        <p className="font-medium">
          {audit.noEmailFound
            ? "A última execução terminou sem encontrar um email público."
            : "A última execução encontrou novos sinais públicos de contato."}
        </p>
        <p className="mt-1 text-xs opacity-80">{formatDateTime(audit.createdAt) ?? "Horário indisponível"}</p>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <AuditList
          title="Páginas verificadas"
          emptyMessage="Nenhuma página verificada foi registrada."
          items={audit.attemptedPages.map((page) => ({
            key: `${page.url}-${page.page_type ?? "page"}`,
            title: labelToken(page.page_type) ?? "Página",
            value: page.url,
            meta: compact([
              page.fetched ? `Coletada${page.http_status ? ` (${page.http_status})` : ""}` : "Não coletada",
              page.discovered_from_url ? `Descoberta a partir de ${page.discovered_from_url}` : null,
              page.note,
            ]),
          }))}
        />
        <AuditList
          title="Páginas coletadas"
          emptyMessage="Nenhuma página coletada foi registrada."
          items={audit.fetchedPageUrls.map((url) => ({
            key: url,
            title: "Coletada",
            value: url,
            meta: null,
          }))}
        />
      </div>

      <AuditList
        title="Contatos extraídos"
        emptyMessage="Nenhum contato extraído foi registrado na última execução."
        items={audit.extractedContacts.map((contact, index) => ({
          key: `${contact.source_url}-${contact.normalized_value ?? contact.raw_value}-${index}`,
          title: `${labelToken(contact.contact_type) ?? "Contato"}: ${contact.normalized_value || contact.raw_value}`,
          value: contact.source_url,
          meta: compact([
            `Confiança ${Math.round(contact.confidence * 100)}%`,
            contact.addedToLead ? "Adicionado ao lead" : "Já conhecido",
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
            <p className="text-xs text-neutral-500">{items.length - 6} itens adicionais não exibidos.</p>
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
  return formatLeadLabel(value);
}

function cnpjStatusLabel(value?: string | null) {
  if (!value || value === "unknown") {
    return "Não consultado";
  }
  return labelToken(value);
}

function formatConfidence(value?: number | null) {
  if (typeof value !== "number") {
    return "Não informado";
  }
  return `${Math.round(value * 100)}%`;
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat("pt-BR", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function getCnpjStatusHint(lead: LeadDetail) {
  const metadata = asRecord(lead.cnpj_metadata_json);
  const reasonCode = typeof metadata?.reason_code === "string" ? metadata.reason_code : null;
  const hasCandidateSummary = Boolean(asRecord(metadata?.candidate_summary));

  if (lead.cnpj_match_status === "needs_review" && hasCandidateSummary) {
    return "Possível CNPJ encontrado, precisa revisão.";
  }

  if (reasonCode === "no_cnpj_on_website") {
    return "CNPJ não encontrado no site.";
  }
  if (reasonCode === "skipped_no_website") {
    return "Este lead não tem site público para consulta de CNPJ.";
  }
  if (reasonCode === "website_unreachable") {
    return "Site sem resposta.";
  }
  if (reasonCode === "website_timeout") {
    return "O site demorou demais para responder.";
  }
  if (reasonCode === "cnpj_provider_rate_limited") {
    return "Consulta pública limitada/rate limit.";
  }
  if (reasonCode === "company_search_not_configured") {
    return "Busca cadastral paga não configurada.";
  }
  if (reasonCode === "company_search_no_candidates") {
    return "Nenhum candidato encontrado na busca cadastral.";
  }
  if (reasonCode === "company_search_low_confidence") {
    return "A busca cadastral encontrou candidatos, mas sem confiança suficiente para preencher automaticamente.";
  }
  if (reasonCode === "company_search_needs_review") {
    return "Possível CNPJ encontrado na busca cadastral, precisa revisão.";
  }
  if (reasonCode === "company_search_rate_limited") {
    return "Busca cadastral temporariamente limitada pelo provedor.";
  }
  if (reasonCode === "company_search_provider_error") {
    return "Falha temporária na busca cadastral paga.";
  }
  if (reasonCode === "provider_error") {
    return "Falha temporária na consulta pública de CNPJ.";
  }
  if (reasonCode === "cnpj_validation_failed") {
    return "Um CNPJ foi encontrado, mas a validação pública não confirmou a empresa.";
  }
  if (reasonCode === "low_confidence") {
    return "Um possível CNPJ foi encontrado, mas sem confiança suficiente para preencher automaticamente.";
  }

  return null;
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
