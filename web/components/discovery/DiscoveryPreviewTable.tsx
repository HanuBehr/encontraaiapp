"use client";

import type { DiscoveryLeadCandidate, DiscoveryPreviewItem } from "@/lib/api/types";
import { sanitizeUserFacingMessage } from "@/lib/ui/messages";

type DiscoveryPreviewTableProps = {
  items: DiscoveryPreviewItem[];
  emptyMessage: string;
  selectedIds: Record<string, boolean>;
  newlyBlockedIds: Record<string, boolean>;
  allVisibleSelected: boolean;
  visibleSelectableCount: number;
  actionDisabled: boolean;
  onToggleSelection: (clientResultId: string, checked: boolean) => void;
  onToggleVisibleSelection: (checked: boolean) => void;
  onBlockCompany: (item: DiscoveryPreviewItem) => void;
  onBlockDomain: (item: DiscoveryPreviewItem) => void;
};

export function DiscoveryPreviewTable({
  items,
  emptyMessage,
  selectedIds,
  newlyBlockedIds,
  allVisibleSelected,
  visibleSelectableCount,
  actionDisabled,
  onToggleSelection,
  onToggleVisibleSelection,
  onBlockCompany,
  onBlockDomain,
}: DiscoveryPreviewTableProps) {
  return (
    <div className="mt-4 overflow-x-auto rounded-2xl border border-brand-mist/80 bg-brand-surface/70">
      <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
        <thead className="bg-brand-sand/80 text-xs font-semibold uppercase tracking-wide text-brand-muted">
          <tr>
            <th className="border-b border-neutral-200 px-3 py-3">
              <input
                type="checkbox"
                aria-label="Selecionar empresas visíveis"
                checked={allVisibleSelected}
                disabled={visibleSelectableCount === 0}
                onChange={(event) => onToggleVisibleSelection(event.target.checked)}
                className="h-4 w-4 rounded border-neutral-300 disabled:cursor-not-allowed"
              />
            </th>
            <th className="border-b border-neutral-200 px-3 py-3">Empresa</th>
            <th className="border-b border-neutral-200 px-3 py-3">Localização</th>
            <th className="border-b border-neutral-200 px-3 py-3">Contato</th>
            <th className="border-b border-neutral-200 px-3 py-3">Exclusão</th>
            <th className="border-b border-neutral-200 px-3 py-3">Ações</th>
          </tr>
        </thead>
        <tbody>
          {items.length ? (
            items.map((item) => {
              const clientResultId = item.client_result_id ?? "";
              const blocked = item.exclusion.is_blocked;
              const existing = item.is_existing_lead;
              const domain = domainForCandidate(item.candidate);
              const hasWebsite = hasWebsiteForCandidate(item.candidate);
              const contactFormUrl = firstExtractedContactUrl(item, "contact_form");
              return (
                <tr key={clientResultId || `${item.search_term}-${item.candidate.business_name}`} className="bg-brand-surface transition hover:bg-brand-sand/70">
                  <td className="border-b border-neutral-100 px-3 py-3 align-top">
                    <input
                      type="checkbox"
                      aria-label={`Select ${item.candidate.business_name}`}
                      checked={Boolean(clientResultId && selectedIds[clientResultId])}
                      disabled={!clientResultId || !isSavablePreviewItem(item)}
                      onChange={(event) => onToggleSelection(clientResultId, event.target.checked)}
                      className="h-4 w-4 rounded border-neutral-300 disabled:cursor-not-allowed disabled:opacity-40"
                    />
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-neutral-950">{item.candidate.business_name}</p>
                      {blocked ? <BlockedBadge /> : null}
                      {existing ? <OutcomeBadge tone="warning">Já salvo</OutcomeBadge> : null}
                      {hasWebsite ? <OutcomeBadge tone="info">Com site</OutcomeBadge> : <OutcomeBadge tone="muted">Sem site</OutcomeBadge>}
                    </div>
                    <p className="mt-1 text-xs text-neutral-500">{item.candidate.category ?? "Sem categoria"}</p>
                    <p className="mt-1 text-xs text-neutral-500">{previewSearchTermsLabel(item)}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {item.candidate.website ? (
                        <a href={item.candidate.website} target="_blank" rel="noreferrer" className="text-xs font-semibold text-brand-signal hover:text-brand-core">
                          Site
                        </a>
                      ) : null}
                      {item.candidate.google_maps_url || item.source_url ? (
                        <a href={item.candidate.google_maps_url ?? item.source_url ?? ""} target="_blank" rel="noreferrer" className="text-xs font-semibold text-brand-signal hover:text-brand-core">
                          Google Maps
                        </a>
                      ) : null}
                    </div>
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top text-neutral-800">
                    <p>{[item.candidate.city, item.candidate.state].filter(Boolean).join(", ") || "Não informado"}</p>
                    <p className="mt-1 text-xs text-neutral-500">{item.candidate.neighborhood ?? item.candidate.address ?? ""}</p>
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top text-neutral-800">
                    <p>{item.candidate.whatsapp ?? item.candidate.phone ?? "Sem telefone"}</p>
                    <p className="mt-1 text-xs text-neutral-500">{domain ?? "Sem domínio"}</p>
                    {item.candidate.email ? (
                      <a href={`mailto:${item.candidate.email}`} className="mt-2 block break-all text-xs font-semibold text-brand-signal hover:text-brand-core">
                        {item.candidate.email}
                      </a>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-2">
                      {item.candidate.instagram ? (
                        <a href={item.candidate.instagram} target="_blank" rel="noreferrer" className="text-xs font-semibold text-brand-signal hover:text-brand-core">
                          Instagram
                        </a>
                      ) : null}
                      {contactFormUrl ? (
                        <a href={contactFormUrl} target="_blank" rel="noreferrer" className="text-xs font-semibold text-brand-signal hover:text-brand-core">
                          Formulário
                        </a>
                      ) : null}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {item.enrichment?.email_found ? <OutcomeBadge tone="info">Email encontrado</OutcomeBadge> : null}
                      {item.enrichment?.instagram_found ? <OutcomeBadge tone="info">Instagram encontrado</OutcomeBadge> : null}
                      {item.enrichment?.contact_form_found ? <OutcomeBadge tone="info">Formulário encontrado</OutcomeBadge> : null}
                      {item.enrichment?.no_email_found ? <OutcomeBadge tone="muted">Sem email público</OutcomeBadge> : null}
                      {item.enrichment?.skipped_reason === "No public website." ? <OutcomeBadge tone="warning">Sem site para enriquecer</OutcomeBadge> : null}
                      {clientResultId && newlyBlockedIds[clientResultId] ? <OutcomeBadge tone="danger">Bloqueada após nova checagem</OutcomeBadge> : null}
                    </div>
                    {item.enrichment?.error_message ? (
                      <p className="mt-2 max-w-xs text-xs text-rose-700">
                        {sanitizeUserFacingMessage(item.enrichment.error_message, "Falha ao enriquecer esta empresa.")}
                      </p>
                    ) : null}
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top">
                    {blocked ? (
                      <div>
                        <p className="font-medium text-rose-800">Bloqueada</p>
                        <p className="mt-1 max-w-xs text-xs text-rose-700">{item.exclusion.reason ?? "Corresponde a uma regra de exclusão ativa."}</p>
                      </div>
                    ) : existing ? (
                      <div>
                        <p className="font-medium text-amber-900">Já salvo</p>
                        <p className="mt-1 max-w-xs text-xs text-amber-800">Encontrado antes e mantido fora do save. Match por {existingLeadMatchLabel(item.matched_existing_by)}.</p>
                      </div>
                    ) : (
                      <span className="inline-flex rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800">
                        Pronta para salvar
                      </span>
                    )}
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top">
                    <div className="flex min-w-36 flex-col gap-2">
                      <button type="button" disabled={actionDisabled} onClick={() => onBlockCompany(item)} className="ea-button-secondary px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50">
                        Bloquear empresa
                      </button>
                      <button type="button" disabled={actionDisabled || !domain} onClick={() => onBlockDomain(item)} className="ea-button-secondary px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50">
                        Bloquear domínio
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={6} className="px-4 py-10 text-center text-sm text-neutral-500">
                {emptyMessage}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function BlockedBadge() {
  return <span className="inline-flex rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-800">Bloqueada</span>;
}

function OutcomeBadge({ tone, children }: { tone: "danger" | "info" | "muted" | "warning"; children: string }) {
  const className =
    tone === "danger"
      ? "inline-flex rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[11px] font-medium text-rose-800"
      : tone === "warning"
        ? "inline-flex rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-medium text-amber-900"
        : tone === "info"
          ? "inline-flex rounded-md border border-brand-olive/70 bg-brand-olive/20 px-2 py-1 text-[11px] font-medium text-brand-graphite"
          : "inline-flex rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-medium text-neutral-700";
  return <span className={className}>{children}</span>;
}

function hasWebsiteForCandidate(candidate: DiscoveryLeadCandidate) {
  return Boolean(candidate.website || domainForCandidate(candidate));
}

function isSavablePreviewItem(item: DiscoveryPreviewItem) {
  return !item.exclusion.is_blocked && !item.is_existing_lead;
}

function previewSearchTermsLabel(item: DiscoveryPreviewItem) {
  const terms = Array.from(new Set([...(item.matched_search_terms ?? []), item.search_term].filter(Boolean)));
  if (terms.length <= 1) {
    return `Busca: ${terms[0] ?? item.search_term}`;
  }
  return `Encontrada por ${terms.length.toLocaleString()} termos: ${terms.join(", ")}`;
}

function domainForCandidate(candidate: DiscoveryLeadCandidate) {
  if (candidate.domain) {
    return candidate.domain;
  }
  if (!candidate.website) {
    return null;
  }
  try {
    const url = new URL(candidate.website.startsWith("http") ? candidate.website : `https://${candidate.website}`);
    return url.hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function firstExtractedContactUrl(item: DiscoveryPreviewItem, contactType: string) {
  const contact = item.enrichment?.extracted_contacts.find((entry) => entry.contact_type === contactType);
  return contact?.normalized_value ?? contact?.raw_value ?? null;
}

function existingLeadMatchLabel(matchedExistingBy: string | null) {
  switch (matchedExistingBy) {
    case "google_place_id":
      return "place id do Google";
    case "google_maps_url":
      return "Google Maps";
    case "domain":
      return "domínio";
    case "phone":
      return "telefone";
    case "name_address":
      return "nome + endereço";
    case "name_neighborhood_city":
      return "nome + bairro + cidade";
    case "name_city":
      return "nome + cidade";
    default:
      return "dados da empresa";
  }
}
