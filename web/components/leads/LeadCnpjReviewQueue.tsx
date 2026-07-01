"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";

import {
  approveLeadBatchCnpjCandidates,
  approveLeadCnpjCandidateByValue,
  listLeads,
  rejectLeadCnpjCandidate,
} from "@/lib/api/leads";
import { useI18n } from "@/lib/i18n/client";
import type {
  LeadBatchApproveCNPJCandidatesResponse,
  LeadCnpjCandidateSummary,
  LeadListParams,
  LeadSummary,
} from "@/lib/api/types";
import { formatUserFacingError } from "@/lib/ui/messages";

type LeadCnpjReviewQueueProps = {
  currentFilters: LeadListParams;
  onActivateLead: (leadId: number) => void;
  activeLeadId: number | null;
};

export function LeadCnpjReviewQueue({
  currentFilters,
  onActivateLead,
  activeLeadId,
}: LeadCnpjReviewQueueProps) {
  const { locale } = useI18n();
  const queryClient = useQueryClient();
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [lastBulkSummary, setLastBulkSummary] = useState<LeadBatchApproveCNPJCandidatesResponse["summary"] | null>(
    null,
  );

  const reviewParams = useMemo<LeadListParams>(
    () => ({
      ...currentScopeFilters(currentFilters),
      limit: 200,
      offset: 0,
    }),
    [currentFilters],
  );

  const reviewQuery = useQuery({
    queryKey: ["leads-cnpj-review", reviewParams],
    queryFn: () => listLeads(reviewParams),
  });

  const reviewItems = useMemo(
    () =>
      (reviewQuery.data?.items ?? []).filter((lead) => {
        const candidates = getCandidateSummaries(lead);
        if (candidates.length === 0) {
          return false;
        }
        if (lead.cnpj_match_status === "needs_review") {
          return true;
        }
        return candidates.some((candidate) => candidate.manual_review_approvable);
      }),
    [reviewQuery.data?.items],
  );

  useEffect(() => {
    const allowed = new Set(
      reviewItems
        .filter((lead) => isSingleBulkApprovableLead(lead))
        .map((lead) => lead.id),
    );
    setSelectedIds((current) => current.filter((leadId) => allowed.has(leadId)));
  }, [reviewItems]);

  const approveMutation = useMutation({
    mutationFn: ({ leadId, candidateCnpj }: { leadId: number; candidateCnpj: string | null }) =>
      approveLeadCnpjCandidateByValue(leadId, candidateCnpj),
    onSuccess: () => {
      setLastBulkSummary(null);
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: ["lead-detail"] });
      void queryClient.invalidateQueries({ queryKey: ["leads-cnpj-review"] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ leadId, candidateCnpj }: { leadId: number; candidateCnpj: string | null }) =>
      rejectLeadCnpjCandidate(leadId, candidateCnpj),
    onSuccess: () => {
      setLastBulkSummary(null);
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: ["lead-detail"] });
      void queryClient.invalidateQueries({ queryKey: ["leads-cnpj-review"] });
    },
  });

  const bulkApproveMutation = useMutation({
    mutationFn: (leadIds: number[]) => approveLeadBatchCnpjCandidates(leadIds),
    onSuccess: (response) => {
      setSelectedIds([]);
      setLastBulkSummary(response.summary);
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: ["lead-detail"] });
      void queryClient.invalidateQueries({ queryKey: ["leads-cnpj-review"] });
    },
  });

  return (
    <section className="ea-card overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-brand-mist/80 px-4 py-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="ea-kicker">CNPJ</p>
          <h2 className="mt-2 text-base font-semibold text-brand-graphite">
            {locale === "en" ? "CNPJ candidates" : "Candidatos CNPJ"}
          </h2>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="rounded-full border border-brand-orchid/10 bg-brand-orchid/[0.055] px-3 py-2 text-sm font-semibold text-brand-muted">
            {locale === "en" ? `${reviewItems.length.toLocaleString()} in review` : `${reviewItems.length.toLocaleString()} na fila`}
          </div>
          <button
            type="button"
            disabled={selectedIds.length === 0 || bulkApproveMutation.isPending}
            onClick={() => bulkApproveMutation.mutate(selectedIds)}
            className="ea-button-primary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:border-neutral-200 disabled:bg-neutral-100 disabled:text-neutral-400"
          >
            {bulkApproveMutation.isPending
              ? locale === "en" ? "Approving..." : "Aprovando..."
              : locale === "en" ? "Approve selected" : "Aprovar selecionados"}
          </button>
        </div>
      </div>

      {reviewQuery.isLoading ? (
        <p className="px-4 py-4 text-sm text-neutral-500">{locale === "en" ? "Loading review queue..." : "Carregando fila de revisão..."}</p>
      ) : null}

      {reviewQuery.isError ? (
        <p className="px-4 py-4 text-sm text-rose-800">
          {formatUserFacingError(reviewQuery.error, locale === "en" ? "Could not load the review queue right now." : "Não foi possível carregar a fila de revisão agora.")}
        </p>
      ) : null}

      {bulkApproveMutation.isError ? (
        <p className="mx-4 mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {formatUserFacingError(
            bulkApproveMutation.error,
            locale === "en" ? "Could not approve the selected CNPJs right now." : "Não foi possível aprovar os CNPJs selecionados agora.",
          )}
        </p>
      ) : null}

      {lastBulkSummary ? (
        <div className="mx-4 mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
          {buildBulkApprovalNarrative(lastBulkSummary, locale)}
        </div>
      ) : null}

      {!reviewQuery.isLoading && !reviewQuery.isError && reviewItems.length === 0 ? (
        <p className="px-4 py-4 text-sm text-neutral-500">
          {locale === "en" ? "No CNPJ candidates pending review with the current filters." : "Nenhum candidato CNPJ pendente de revisão com os filtros atuais."}
        </p>
      ) : null}

      {reviewItems.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="min-w-[1180px] border-separate border-spacing-0 text-left text-sm 2xl:min-w-full">
            <thead className="bg-white/[0.34] text-xs font-semibold uppercase tracking-wide text-brand-muted">
              <tr>
                <th className="border-b border-neutral-200 px-3 py-3">{locale === "en" ? "Select" : "Seleção"}</th>
                <th className="border-b border-neutral-200 px-3 py-3">Lead</th>
                <th className="border-b border-neutral-200 px-3 py-3">{locale === "en" ? "Current address" : "Endereço atual"}</th>
                <th className="border-b border-neutral-200 px-3 py-3">{locale === "en" ? "Candidate(s)" : "Candidato(s)"}</th>
                <th className="border-b border-neutral-200 px-3 py-3">Status</th>
                <th className="border-b border-neutral-200 px-3 py-3">{locale === "en" ? "Actions" : "Ações"}</th>
              </tr>
            </thead>
            <tbody>
              {reviewItems.map((lead) => {
                const candidates = getCandidateSummaries(lead);
                const bulkApprovable = isSingleBulkApprovableLead(lead);
                const checked = selectedIds.includes(lead.id);
                const diagnostics = getLeadReviewStatusLabel(lead, candidates, locale);
                return (
                  <tr key={lead.id} className={lead.id === activeLeadId ? "bg-brand-olive/10" : "bg-white/[0.16]"}>
                    <td className="border-b border-neutral-100 px-3 py-3 align-top">
                      <input
                        type="checkbox"
                        aria-label={`${locale === "en" ? "Select" : "Selecionar"} ${lead.business_name}`}
                        checked={checked}
                        disabled={!bulkApprovable}
                        onChange={(event) => {
                          setSelectedIds((current) =>
                            event.target.checked
                              ? [...current, lead.id]
                              : current.filter((item) => item !== lead.id),
                          );
                        }}
                        className="h-4 w-4 rounded border-neutral-300"
                      />
                    </td>
                    <td className="border-b border-neutral-100 px-3 py-3 align-top">
                      <button
                        type="button"
                        onClick={() => onActivateLead(lead.id)}
                        className="text-left"
                      >
                        <p className="font-medium text-neutral-950">{lead.business_name}</p>
                        <p className="mt-1 text-xs text-neutral-500">
                          {[lead.city, lead.state].filter(Boolean).join("/") || (locale === "en" ? "Location missing" : "Local não informado")}
                        </p>
                      </button>
                    </td>
                    <td className="border-b border-neutral-100 px-3 py-3 align-top text-neutral-700">
                      {compact([lead.address, lead.neighborhood, lead.postal_code]) || (locale === "en" ? "Not informed" : "Não informado")}
                    </td>
                    <td className="border-b border-neutral-100 px-3 py-3 align-top">
                      <div className="space-y-2">
                        {candidates.map((candidate) => {
                          const isPrimary = normalizeCnpj(candidate.cnpj) === normalizeCnpj(getPrimaryCandidate(lead)?.cnpj);
                          return (
                            <div
                              key={`${lead.id}-${candidate.cnpj ?? candidate.legal_name ?? "candidate"}`}
                              className="rounded-2xl border border-brand-mist/80 bg-white/[0.34] p-2"
                            >
                              <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                                <div className="space-y-1">
                                  <p className="font-medium text-neutral-950">
                                    {candidate.trade_name || candidate.legal_name || (locale === "en" ? "Candidate" : "Candidato")}
                                    {isPrimary ? (locale === "en" ? " · primary" : " · principal") : ""}
                                  </p>
                                  <p className="text-xs text-neutral-600">
                                    CNPJ: {candidate.cnpj || (locale === "en" ? "Unavailable" : "Não disponível")}
                                  </p>
                                  <p className="text-xs text-neutral-600">
                                    {locale === "en" ? "Legal name" : "Razão social"}: {candidate.legal_name || (locale === "en" ? "Not informed" : "Não informada")}
                                  </p>
                                  {candidate.trade_name ? (
                                    <p className="text-xs text-neutral-600">{locale === "en" ? "Trade name" : "Nome fantasia"}: {candidate.trade_name}</p>
                                  ) : null}
                                  <p className="text-xs text-neutral-600">
                                    {[candidate.city, candidate.state].filter(Boolean).join("/") || (locale === "en" ? "City/state missing" : "Cidade/UF não informadas")}
                                  </p>
                                  <p className="text-xs text-neutral-600">{candidate.address || (locale === "en" ? "Address missing" : "Endereço não informado")}</p>
                                  <p className="text-xs text-neutral-600">
                                    {locale === "en" ? "Confidence" : "Confiança"}: {formatConfidence(candidate.match_confidence, locale)} · {locale === "en" ? "Score" : "Pontuação"}: {formatScore(candidate.score, locale)}
                                  </p>
                                  <p className="text-xs text-neutral-500">
                                    {candidate.query_mode_label || (locale === "en" ? "Company registry search" : "Busca cadastral")} · {candidate.provider || (locale === "en" ? "Provider missing" : "Provedor não informado")}
                                  </p>
                                </div>
                                {candidate.manual_review_approvable ? (
                                  <button
                                    type="button"
                                    onClick={() =>
                                      approveMutation.mutate({
                                        leadId: lead.id,
                                        candidateCnpj: candidate.cnpj,
                                      })
                                    }
                                    disabled={approveMutation.isPending}
                                     className="ea-button-primary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:border-neutral-200 disabled:bg-neutral-100 disabled:text-neutral-400"
                                  >
                                    {locale === "en" ? "Approve this CNPJ" : "Aprovar este CNPJ"}
                                  </button>
                                ) : null}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    </td>
                    <td className="border-b border-neutral-100 px-3 py-3 align-top text-neutral-700">
                      <p className="font-medium text-neutral-950">{diagnostics.label}</p>
                      <p className="mt-1 text-xs text-neutral-600">{diagnostics.reason}</p>
                    </td>
                    <td className="border-b border-neutral-100 px-3 py-3 align-top">
                      <button
                        type="button"
                        onClick={() =>
                          rejectMutation.mutate({
                            leadId: lead.id,
                            candidateCnpj: getPrimaryCandidate(lead)?.cnpj ?? null,
                          })
                        }
                        disabled={rejectMutation.isPending}
                        className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-800 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {locale === "en" ? "Keep without CNPJ" : "Manter sem CNPJ"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function getCandidateSummaries(lead: Pick<LeadSummary, "cnpj_metadata_json">): LeadCnpjCandidateSummary[] {
  const metadata = asRecord(lead.cnpj_metadata_json);
  const items = Array.isArray(metadata?.candidate_summaries) ? metadata.candidate_summaries : [];
  const parsed = items
    .map((candidate) => parseCandidateSummary(candidate))
    .filter((candidate): candidate is LeadCnpjCandidateSummary => candidate !== null);
  if (parsed.length > 0) {
    return parsed;
  }
  const singleCandidate = parseCandidateSummary(metadata?.candidate_summary);
  return singleCandidate ? [singleCandidate] : [];
}

function getPrimaryCandidate(lead: Pick<LeadSummary, "cnpj_metadata_json">) {
  return getCandidateSummaries(lead)[0] ?? null;
}

function parseCandidateSummary(value: unknown): LeadCnpjCandidateSummary | null {
  const candidate = asRecord(value);
  if (!candidate) {
    return null;
  }
  return {
    cnpj: asNullableString(candidate.cnpj),
    legal_name: asNullableString(candidate.legal_name),
    trade_name: asNullableString(candidate.trade_name),
    address: asNullableString(candidate.address),
    city: asNullableString(candidate.city),
    state: asNullableString(candidate.state),
    postal_code: asNullableString(candidate.postal_code),
    phones: asStringArray(candidate.phones),
    emails: asStringArray(candidate.emails),
    primary_activity: asNullableString(candidate.primary_activity),
    provider: asNullableString(candidate.provider),
    score: asNullableNumber(candidate.score),
    match_confidence: asNullableNumber(candidate.match_confidence),
    evidence: asNumberRecord(candidate.evidence),
    penalties: asStringArray(candidate.penalties),
    query_mode: asNullableString(candidate.query_mode),
    query_mode_label: asNullableString(candidate.query_mode_label),
    blocked_from_autofill_reason: asNullableString(candidate.blocked_from_autofill_reason),
    review_reason: asNullableString(candidate.review_reason),
    person_like_legal_name: Boolean(candidate.person_like_legal_name),
    legal_name_note: asNullableString(candidate.legal_name_note),
    manual_review_approvable: candidate.manual_review_approvable === false ? false : hasFullCnpj(asNullableString(candidate.cnpj)),
  };
}

function isSingleBulkApprovableLead(lead: Pick<LeadSummary, "cnpj_metadata_json">) {
  const candidates = getCandidateSummaries(lead);
  return candidates.length === 1 && candidates[0]?.manual_review_approvable && hasFullCnpj(candidates[0].cnpj);
}

function getLeadReviewStatusLabel(
  lead: Pick<LeadSummary, "cnpj_match_status" | "cnpj_metadata_json">,
  candidates: LeadCnpjCandidateSummary[],
  locale: "pt-BR" | "en",
) {
  const metadata = asRecord(lead.cnpj_metadata_json);
  const reasonCode = asNullableString(metadata?.reason_code);
  if (reasonCode === "company_search_rate_limited" || reasonCode === "cnpj_provider_rate_limited") {
    return {
      label: locale === "en" ? "Provider limit reached" : "Limite do provedor, tente novamente",
      reason: locale === "en" ? "The provider limited this lookup. Try again later." : "A consulta foi limitada pelo provedor e pode ser tentada novamente depois.",
    };
  }
  if (lead.cnpj_match_status === "needs_review" && candidates.length > 1) {
    return {
      label: locale === "en" ? "Multiple candidates found" : "Múltiplos candidatos encontrados",
      reason: locale === "en" ? "More than one strong candidate was found. Choose the correct registration." : "Mais de um candidato forte encontrado. Escolha o cadastro correto.",
    };
  }
  if (lead.cnpj_match_status === "needs_review") {
    return {
      label: locale === "en" ? "Candidate found" : "Candidato encontrado",
      reason: candidates[0]?.review_reason || (locale === "en" ? "The lookup found a candidate that needs manual review." : "A busca encontrou um candidato, mas precisa de revisão manual."),
    };
  }
  if (reasonCode === "company_search_low_confidence" && candidates.length > 0) {
    return {
      label: locale === "en" ? "Low-confidence candidates" : "Candidatos fracos",
      reason: locale === "en" ? "The candidates found were not confident enough for automatic confirmation." : "Os candidatos encontrados não atingiram confiança suficiente para confirmação automática.",
    };
  }
  return {
    label: locale === "en" ? "Not found" : "Não encontrado",
    reason: locale === "en" ? "No reviewable candidate is available for approval." : "Nenhum candidato revisável ficou disponível para aprovação.",
  };
}

function buildBulkApprovalNarrative(summary: LeadBatchApproveCNPJCandidatesResponse["summary"], locale: "pt-BR" | "en") {
  const parts = [
    locale === "en" ? `${summary.approved_count.toLocaleString()} approved` : `${summary.approved_count.toLocaleString()} aprovado(s)`,
    summary.skipped_ambiguous_count
      ? locale === "en" ? `${summary.skipped_ambiguous_count.toLocaleString()} ambiguous skipped` : `${summary.skipped_ambiguous_count.toLocaleString()} ambíguo(s) pulado(s)`
      : null,
    summary.skipped_no_candidate_count
      ? locale === "en" ? `${summary.skipped_no_candidate_count.toLocaleString()} without candidate skipped` : `${summary.skipped_no_candidate_count.toLocaleString()} sem candidato pulado(s)`
      : null,
    summary.skipped_low_confidence_count
      ? locale === "en" ? `${summary.skipped_low_confidence_count.toLocaleString()} below threshold skipped` : `${summary.skipped_low_confidence_count.toLocaleString()} abaixo do mínimo pulado(s)`
      : null,
    summary.skipped_already_matched_count
      ? locale === "en" ? `${summary.skipped_already_matched_count.toLocaleString()} already confirmed` : `${summary.skipped_already_matched_count.toLocaleString()} já confirmado(s)`
      : null,
  ].filter(Boolean);
  return locale === "en" ? `Bulk approval complete: ${parts.join(", ")}.` : `Aprovação em lote concluída: ${parts.join(", ")}.`;
}

function currentScopeFilters(filters: LeadListParams): LeadListParams {
  const { limit: _limit, offset: _offset, cnpj_match_status: _cnpjMatchStatus, ...scopeFilters } = filters;
  return scopeFilters;
}

function compact(values: Array<string | null | undefined>) {
  const parts = values.filter((value): value is string => Boolean(value && value.trim()));
  return parts.length ? parts.join(" · ") : null;
}

function formatConfidence(value?: number | null, locale: "pt-BR" | "en" = "pt-BR") {
  if (typeof value !== "number") {
    return locale === "en" ? "Not informed" : "Não informado";
  }
  return `${Math.round(value * 100)}%`;
}

function formatScore(value?: number | null, locale: "pt-BR" | "en" = "pt-BR") {
  if (typeof value !== "number") {
    return locale === "en" ? "Not informed" : "Não informado";
  }
  return `${Math.round(value)} / 100`;
}

function hasFullCnpj(value?: string | null) {
  return normalizeCnpj(value) !== null;
}

function normalizeCnpj(value?: string | null) {
  if (!value) {
    return null;
  }
  const digits = value.replace(/\D/g, "");
  return digits.length === 14 ? digits : null;
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

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
}

function asNumberRecord(value: unknown): Record<string, number> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value).filter((entry): entry is [string, number] => typeof entry[1] === "number"),
  );
}
