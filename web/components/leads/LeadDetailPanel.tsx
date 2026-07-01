"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { formatLeadLabel } from "@/lib/format/lead-labels";
import { useI18n } from "@/lib/i18n/client";
import { formatDateTime as formatLocalizedDateTime } from "@/lib/i18n/format";
import { translateLooseText } from "@/lib/i18n/loose";
import {
  approveLeadCnpjCandidateByValue,
  getLeadDetail,
  rejectLeadCnpjCandidate,
} from "@/lib/api/leads";
import type {
  EnrichmentAttemptedPage,
  EnrichmentExtractedContact,
  LeadCnpjCandidateSummary,
  LeadCnpjSearchDiagnostics,
  LeadContactRead,
  LeadDetail,
} from "@/lib/api/types";
import { formatUserFacingError } from "@/lib/ui/messages";

type LeadDetailPanelProps = {
  leadId: number | null;
};

export function LeadDetailPanel({ leadId }: LeadDetailPanelProps) {
  const { locale, t } = useI18n();
  const queryClient = useQueryClient();
  const detailQuery = useQuery({
    queryKey: ["lead-detail", leadId],
    queryFn: () => getLeadDetail(leadId as number),
    enabled: leadId !== null,
  });
  const approveCnpjMutation = useMutation({
    mutationFn: ({
      currentLeadId,
      candidateCnpj,
    }: {
      currentLeadId: number;
      candidateCnpj?: string | null;
    }) => approveLeadCnpjCandidateByValue(currentLeadId, candidateCnpj),
    onSuccess: (updatedLead) => {
      queryClient.setQueryData(["lead-detail", updatedLead.id], updatedLead);
      void queryClient.invalidateQueries({ queryKey: ["lead-detail", updatedLead.id] });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: ["leads-cnpj-review"] });
    },
  });
  const rejectCnpjMutation = useMutation({
    mutationFn: ({
      currentLeadId,
      candidateCnpj,
    }: {
      currentLeadId: number;
      candidateCnpj?: string | null;
    }) => rejectLeadCnpjCandidate(currentLeadId, candidateCnpj),
    onSuccess: (updatedLead) => {
      queryClient.setQueryData(["lead-detail", updatedLead.id], updatedLead);
      void queryClient.invalidateQueries({ queryKey: ["lead-detail", updatedLead.id] });
      void queryClient.invalidateQueries({ queryKey: ["leads"] });
      void queryClient.invalidateQueries({ queryKey: ["leads-cnpj-review"] });
    },
  });

  if (leadId === null) {
    return (
      <aside className="ea-card p-6">
        <p className="text-sm font-semibold text-brand-graphite">{t("leads.selectLead")}</p>
        <p className="mt-1 text-sm leading-6 text-brand-muted">
          {t("leads.selectLeadDescription")}
        </p>
      </aside>
    );
  }

  if (detailQuery.isLoading) {
    return (
      <aside className="ea-card p-6">
        <p className="text-sm text-brand-muted">{t("leads.loadingDetails")}</p>
      </aside>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <aside className="rounded-md border border-rose-200 bg-white p-6">
        <p className="text-sm font-medium text-rose-800">{t("leads.detailsErrorTitle")}</p>
        <p className="mt-1 text-sm text-neutral-500">
          {formatUserFacingError(detailQuery.error, "Tente novamente em instantes.", locale)}
        </p>
      </aside>
    );
  }

  const lead = detailQuery.data;
  const cnpjMetadata = asRecord(lead.cnpj_metadata_json);
  const latestEnrichment = lead.enrichments[0];
  const latestEnrichmentAudit = getLatestEnrichmentAudit(lead);
  const rawCnpjStatusHint = getCnpjStatusHintV2(lead);
  const cnpjStatusHint = rawCnpjStatusHint ? translateLooseText(rawCnpjStatusHint, locale) : null;
  const cnpjCandidateSummaries = getCnpjCandidateSummaries(lead);
  const cnpjCandidateSummary = cnpjCandidateSummaries[0] ?? null;
  const cnpjSearchDiagnostics = getCnpjSearchDiagnostics(lead);
  const cnpjApprovedManually = Boolean(cnpjMetadata?.approved_manually);
  const hasMultipleReviewCandidates = cnpjCandidateSummaries.length > 1;
  const canRejectCnpjCandidate =
    lead.cnpj_match_status === "needs_review" && cnpjCandidateSummaries.length > 0;

  return (
    <aside className="ea-card overflow-hidden">
      <div className="border-b border-brand-mist/80 p-4">
        <p className="ea-kicker">{t("leads.detailsTitle")}</p>
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-brand-graphite">{lead.business_name}</h2>
          {lead.is_blocked ? <BlockedBadge /> : null}
        </div>
        <p className="mt-1 text-sm text-brand-muted">
          {[lead.category, lead.city, lead.state].filter(Boolean).join(" - ") || t("leads.localMissing")}
        </p>
        {lead.is_blocked ? (
          <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
            {lead.blocked_reason ?? (locale === "en" ? "Matches an active exclusion rule." : "Corresponde a uma regra de exclusão ativa.")}
          </p>
        ) : null}
      </div>

      <div className="divide-y divide-brand-mist/80">
        <DetailSection title={t("leads.companySection")}>
          <InfoGrid>
            <InfoItem label="Website" value={lead.website} />
            <InfoItem label={t("leads.domain")} value={lead.domain} />
            <InfoItem label={t("leads.address")} value={compact([lead.address, lead.neighborhood, lead.postal_code])} />
            <InfoItem label={t("common.status")} value={formatLeadLabel(lead.status, locale)} />
            <InfoItem label={t("common.score")} value={String(lead.lead_score)} />
            <InfoItem label={t("leads.source")} value={formatLeadLabel(lead.lead_source_type, locale)} />
          </InfoGrid>
        </DetailSection>

        <DetailSection title={t("leads.registrationSection")}>
          <InfoGrid>
            <InfoItem label="CNPJ" value={lead.cnpj ?? t("leads.noCnpj")} />
            <InfoItem label={t("leads.legalName")} value={lead.legal_name} />
            <InfoItem label={t("leads.cnpjStatus")} value={cnpjClientStatusLabel(lead, locale)} />
            <InfoItem label={t("leads.confidence")} value={formatConfidence(lead.cnpj_match_confidence, locale)} />
            <InfoItem label={t("leads.lastLookup")} value={formatLocalizedDateTime(lead.cnpj_last_enriched_at, locale)} />
            <InfoItem label={t("leads.provider")} value={formatLeadLabel(lead.cnpj_source_provider, locale)} />
          </InfoGrid>
          {cnpjStatusHint ? (
            <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {cnpjStatusHint}
            </p>
          ) : null}
          {cnpjApprovedManually ? (
            <p className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-900">
              {locale === "en" ? "Approved manually." : "Aprovado manualmente."}
            </p>
          ) : null}
          {cnpjSearchDiagnostics && lead.cnpj_match_status !== "matched" ? (
            <CnpjSearchDiagnosticsPanel
              diagnostics={cnpjSearchDiagnostics}
              matchStatus={lead.cnpj_match_status}
            />
          ) : null}
          {cnpjCandidateSummary ? (
            <div className="mt-3 rounded-md border border-neutral-200 bg-neutral-50 p-3">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase text-neutral-500">
                    {locale === "en"
                      ? lead.cnpj_match_status === "needs_review" ? "Candidate under review" : "Best candidate found"
                      : lead.cnpj_match_status === "needs_review" ? "Candidato em revisão" : "Melhor candidato encontrado"}
                  </p>
                  <p className="mt-1 text-sm text-neutral-700">
                    {hasMultipleReviewCandidates
                      ? locale === "en" ? "More than one strong candidate was found. Choose the correct registration." : "Mais de um candidato forte encontrado. Escolha o cadastro correto."
                      : lead.cnpj_match_status === "needs_review"
                        ? locale === "en" ? "Review the data before confirming this lead's CNPJ." : "Confira os dados encontrados antes de confirmar o CNPJ deste lead."
                        : locale === "en" ? "The lookup found a candidate, but it has not been confirmed automatically." : "A busca encontrou um candidato, mas ele ainda não foi confirmado automaticamente."}
                  </p>
                </div>
                {canRejectCnpjCandidate ? (
                  <button
                    type="button"
                    onClick={() =>
                      rejectCnpjMutation.mutate({
                        currentLeadId: lead.id,
                        candidateCnpj: cnpjCandidateSummary.cnpj,
                      })
                    }
                    disabled={rejectCnpjMutation.isPending}
                    className="inline-flex items-center justify-center rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-800 transition hover:bg-neutral-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {rejectCnpjMutation.isPending
                      ? locale === "en" ? "Updating..." : "Atualizando..."
                      : locale === "en" ? "Keep without CNPJ" : "Manter sem CNPJ"}
                  </button>
                ) : null}
              </div>
              <div className="mt-3">
                <InfoGrid>
                  <InfoItem label="Possível CNPJ" value={cnpjCandidateSummary.cnpj ?? (locale === "en" ? "Not available" : "Não disponível")} />
                  <InfoItem label="Razão Social" value={cnpjCandidateSummary.legal_name} />
                  <InfoItem label="Nome Fantasia" value={cnpjCandidateSummary.trade_name} />
                  <InfoItem label="Modo da busca" value={cnpjCandidateSummary.query_mode_label} />
                  <InfoItem
                    label="Cidade/UF"
                    value={compact([cnpjCandidateSummary.city, cnpjCandidateSummary.state])}
                  />
                  <InfoItem label="Atividade/CNAE" value={cnpjCandidateSummary.primary_activity} />
                  <InfoItem label="Telefone(s)" value={joinList(cnpjCandidateSummary.phones)} />
                  <InfoItem label="Email(s)" value={joinList(cnpjCandidateSummary.emails)} />
                  <InfoItem label="Endereço" value={cnpjCandidateSummary.address} />
                  <InfoItem label="Confiança" value={formatConfidence(cnpjCandidateSummary.match_confidence, locale)} />
                  <InfoItem label="Pontuação" value={formatScore(cnpjCandidateSummary.score, locale)} />
                  <InfoItem label="Motivo" value={cnpjCandidateSummary.review_reason} />
                  <InfoItem label="Provedor" value={labelToken(cnpjCandidateSummary.provider)} />
                </InfoGrid>
                {lead.cnpj_match_status === "needs_review" &&
                hasFullCnpj(cnpjCandidateSummary.cnpj) &&
                cnpjCandidateSummary.manual_review_approvable ? (
                  <div className="mt-3 flex justify-end">
                    <button
                      type="button"
                      onClick={() =>
                        approveCnpjMutation.mutate({
                          currentLeadId: lead.id,
                          candidateCnpj: cnpjCandidateSummary.cnpj,
                        })
                      }
                      disabled={approveCnpjMutation.isPending}
                      className="ea-button-primary inline-flex items-center justify-center px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {approveCnpjMutation.isPending
                        ? locale === "en" ? "Approving..." : "Aprovando..."
                        : locale === "en" ? "Approve this CNPJ" : "Aprovar este CNPJ"}
                    </button>
                  </div>
                ) : null}
                {cnpjCandidateSummary.legal_name_note ? (
                  <p className="mt-3 rounded-2xl border border-brand-olive/70 bg-brand-olive/20 px-3 py-2 text-sm text-brand-graphite">
                    {cnpjCandidateSummary.legal_name_note}
                  </p>
                ) : null}
                {(Object.keys(cnpjCandidateSummary.evidence).length > 0 || cnpjCandidateSummary.penalties.length > 0) ? (
                  <div className="mt-3 rounded-md border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-700">
                    <p className="text-xs font-semibold uppercase text-neutral-500">{locale === "en" ? "Match criteria" : "Critérios do match"}</p>
                    <p className="mt-1">{formatEvidenceSummary(cnpjCandidateSummary.evidence, locale)}</p>
                    {cnpjCandidateSummary.penalties.length > 0 ? (
                      <p className="mt-1 text-xs text-amber-700">
                        {locale === "en" ? "Penalties" : "Penalidades"}: {cnpjCandidateSummary.penalties.map((penalty) => labelPenalty(penalty, locale)).join(", ")}
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {cnpjCandidateSummaries.length > 1 ? (
                  <div className="mt-3 space-y-3">
                    {cnpjCandidateSummaries.slice(1).map((candidate, index) => (
                      <div
                        key={`${candidate.cnpj ?? candidate.legal_name ?? "candidate"}-${index + 1}`}
                        className="rounded-md border border-neutral-200 bg-white px-3 py-3"
                      >
                        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                          <div>
                            <p className="text-xs font-semibold uppercase text-neutral-500">
                              {locale === "en" ? "Candidate" : "Candidato"} {index + 2}
                            </p>
                            <p className="mt-1 text-sm font-medium text-neutral-950">
                              {candidate.trade_name || candidate.legal_name || (locale === "en" ? "Registration found" : "Cadastro encontrado")}
                            </p>
                          </div>
                          {lead.cnpj_match_status === "needs_review" &&
                          hasFullCnpj(candidate.cnpj) &&
                          candidate.manual_review_approvable ? (
                            <button
                              type="button"
                              onClick={() =>
                                approveCnpjMutation.mutate({
                                  currentLeadId: lead.id,
                                  candidateCnpj: candidate.cnpj,
                                })
                              }
                              disabled={approveCnpjMutation.isPending}
                              className="ea-button-primary inline-flex items-center justify-center px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {approveCnpjMutation.isPending
                                ? locale === "en" ? "Approving..." : "Aprovando..."
                                : locale === "en" ? "Approve this CNPJ" : "Aprovar este CNPJ"}
                            </button>
                          ) : null}
                        </div>
                        <div className="mt-3">
                          <InfoGrid>
                            <InfoItem label="Possível CNPJ" value={candidate.cnpj ?? (locale === "en" ? "Not available" : "Não disponível")} />
                            <InfoItem label="Razão Social" value={candidate.legal_name} />
                            <InfoItem label="Nome Fantasia" value={candidate.trade_name} />
                            <InfoItem label="Modo da busca" value={candidate.query_mode_label} />
                            <InfoItem label="Cidade/UF" value={compact([candidate.city, candidate.state])} />
                            <InfoItem label="Atividade/CNAE" value={candidate.primary_activity} />
                            <InfoItem label="Telefone(s)" value={joinList(candidate.phones)} />
                            <InfoItem label="Email(s)" value={joinList(candidate.emails)} />
                            <InfoItem label="Endereço" value={candidate.address} />
                            <InfoItem label="Confiança" value={formatConfidence(candidate.match_confidence, locale)} />
                            <InfoItem label="Pontuação" value={formatScore(candidate.score, locale)} />
                            <InfoItem label="Motivo" value={candidate.review_reason} />
                            <InfoItem label="Provedor" value={labelToken(candidate.provider)} />
                          </InfoGrid>
                          {(Object.keys(candidate.evidence).length > 0 || candidate.penalties.length > 0) ? (
                            <div className="mt-3 rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-700">
                              <p className="text-xs font-semibold uppercase text-neutral-500">{locale === "en" ? "Match criteria" : "Critérios do match"}</p>
                              <p className="mt-1">{formatEvidenceSummary(candidate.evidence, locale)}</p>
                              {candidate.penalties.length > 0 ? (
                                <p className="mt-1 text-xs text-amber-700">
                                  {locale === "en" ? "Penalties" : "Penalidades"}: {candidate.penalties.map((penalty) => labelPenalty(penalty, locale)).join(", ")}
                                </p>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
              {approveCnpjMutation.isError ? (
                <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
                  {formatUserFacingError(
                    approveCnpjMutation.error,
                    locale === "en" ? "Could not approve this CNPJ right now." : "Não foi possível aprovar este CNPJ agora.",
                  )}
                </p>
              ) : null}
              {rejectCnpjMutation.isError ? (
                <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
                  {formatUserFacingError(
                    rejectCnpjMutation.error,
                    locale === "en" ? "Could not keep this lead without CNPJ right now." : "Não foi possível manter este lead sem CNPJ agora.",
                  )}
                </p>
              ) : null}
            </div>
          ) : null}
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
                <li key={activity.id} className="border-l-2 border-brand-olive pl-3">
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
  const { locale } = useI18n();
  return (
    <section className="p-4">
      <h3 className="text-sm font-semibold text-neutral-950">{translateLooseText(title, locale)}</h3>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function InfoGrid({ children }: { children: React.ReactNode }) {
  return <dl className="grid gap-3 sm:grid-cols-2">{children}</dl>;
}

function InfoItem({ label, value }: { label: string; value?: string | null }) {
  const { locale, t } = useI18n();
  return (
    <div>
      <dt className="text-xs font-medium text-neutral-500">{translateLooseText(label, locale)}</dt>
      <dd className="mt-1 break-words text-sm text-neutral-900">{value ? translateLooseText(value, locale) : t("common.notInformed")}</dd>
    </div>
  );
}

function BlockedBadge() {
  const { t } = useI18n();
  return (
    <span className="inline-flex rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-800">
      {t("common.blocked")}
    </span>
  );
}

function ContactLine({ label, value }: { label: string; value?: string | null }) {
  const { locale, t } = useI18n();
  return (
    <div className="flex items-center justify-between gap-3 rounded-md border border-neutral-200 px-3 py-2">
      <span className="text-sm font-medium text-neutral-700">{translateLooseText(label, locale)}</span>
      <span className="break-all text-right text-sm text-neutral-950">{value ? translateLooseText(value, locale) : t("common.notInformed")}</span>
    </div>
  );
}

function ContactEvidence({ contacts }: { contacts: LeadContactRead[] }) {
  const { locale } = useI18n();
  if (!contacts.length) {
    return <p className="mt-3 text-sm text-neutral-500">{locale === "en" ? "No contact evidence recorded." : "Nenhuma evidência de contato registrada."}</p>;
  }

  return (
    <div className="mt-4">
      <p className="text-xs font-medium uppercase text-neutral-500">{locale === "en" ? "Evidence" : "Evidências"}</p>
      <div className="mt-2 space-y-2">
        {contacts.slice(0, 6).map((contact) => (
          <div key={contact.id} className="rounded-md bg-neutral-50 px-3 py-2 text-sm">
            <p className="font-medium text-neutral-900">
              {labelToken(contact.contact_type)}: {contact.normalized_value || contact.raw_value}
            </p>
            <p className="text-xs text-neutral-500">
              {locale === "en" ? "Confidence" : "Confiança"} {Math.round(contact.confidence * 100)}%
              {contact.is_primary ? locale === "en" ? " - Primary" : " - Principal" : ""}
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}

function CnpjSearchDiagnosticsPanel({
  diagnostics,
  matchStatus,
}: {
  diagnostics: LeadCnpjSearchDiagnostics;
  matchStatus: LeadDetail["cnpj_match_status"];
}) {
  const { locale } = useI18n();
  const rawPrimaryMessage = buildCnpjDiagnosticsMessageV2(diagnostics, matchStatus);
  const primaryMessage = rawPrimaryMessage ? translateLooseText(rawPrimaryMessage, locale) : null;
  const triedModes = diagnostics.search_attempts
    .map((attempt) => attempt.query_mode_label)
    .filter((value): value is string => Boolean(value));
  const secondaryFacts = [
    diagnostics.searched_municipality_code
      ? `${locale === "en" ? "IBGE municipality" : "Município IBGE"}: ${diagnostics.searched_municipality_code}`
      : null,
    diagnostics.searched_zip
      ? `${locale === "en" ? "ZIP used" : "CEP usado"}: ${diagnostics.searched_zip}${diagnostics.extracted_zip_from_address ? locale === "en" ? " (from address)" : " (extraído do endereço)" : ""}`
      : null,
    diagnostics.searched_phone_area ? `${locale === "en" ? "Area code used" : "DDD usado"}: ${diagnostics.searched_phone_area}` : null,
    diagnostics.search_attempts_count ? `${locale === "en" ? "Attempts" : "Tentativas"}: ${diagnostics.search_attempts_count}` : null,
    diagnostics.search_mode ? `${locale === "en" ? "Mode" : "Modo"}: ${diagnostics.search_mode}` : null,
    typeof diagnostics.paid_calls_made === "number" ? `${locale === "en" ? "Paid calls" : "Consultas pagas"}: ${diagnostics.paid_calls_made}` : null,
    typeof diagnostics.paid_calls_skipped_duplicate === "number" && diagnostics.paid_calls_skipped_duplicate > 0
      ? `${locale === "en" ? "Duplicates avoided" : "Duplicadas evitadas"}: ${diagnostics.paid_calls_skipped_duplicate}`
      : null,
    typeof diagnostics.paid_calls_skipped_recent === "number" && diagnostics.paid_calls_skipped_recent > 0
      ? `${locale === "en" ? "Skipped by cooldown" : "Puladas por cooldown"}: ${diagnostics.paid_calls_skipped_recent}`
      : null,
    typeof diagnostics.candidates_returned_count === "number"
      ? `${locale === "en" ? "Candidates returned" : "Candidatos retornados"}: ${diagnostics.candidates_returned_count}`
      : null,
    triedModes.length ? `${locale === "en" ? "Modes" : "Modos"}: ${triedModes.join(" -> ")}` : null,
  ].filter(Boolean);

  if (!primaryMessage && secondaryFacts.length === 0) {
    return null;
  }

  return (
    <div className="mt-3 rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-700">
      {primaryMessage ? <p>{primaryMessage}</p> : null}
      {secondaryFacts.length ? (
        <p className="mt-1 text-xs text-neutral-500">{secondaryFacts.join(" - ")}</p>
      ) : null}
      {diagnostics.search_attempts.length ? (
        <div className="mt-2 space-y-1 text-xs text-neutral-600">
          {diagnostics.search_attempts.slice(0, 4).map((attempt, index) => (
            <p key={`${attempt.query_mode ?? "attempt"}-${index}`}>
              {[
                attempt.query_mode_label ?? (locale === "en" ? "Attempt" : "Tentativa"),
                attempt.searched_values.length ? attempt.searched_values.join(", ") : null,
                typeof attempt.candidates_returned_count === "number"
                  ? `${attempt.candidates_returned_count} ${locale === "en" ? "candidates" : "candidatos"}`
                  : null,
                attempt.status ? `status: ${attempt.status}` : null,
              ]
                .filter(Boolean)
                .join(" - ")}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function EnrichmentAudit({ audit }: { audit: EnrichmentAuditData | null }) {
  const { locale } = useI18n();
  if (!audit) {
    return <p className="mt-4 text-sm text-neutral-500">{locale === "en" ? "No enrichment history recorded." : "Nenhum histórico de enriquecimento registrado."}</p>;
  }

  return (
    <div className="mt-4 space-y-3 rounded-md border border-neutral-200 bg-neutral-50 p-3">
      <div className={`rounded-md px-3 py-2 text-sm ${audit.noEmailFound ? "border border-amber-200 bg-amber-50 text-amber-950" : "border border-emerald-200 bg-emerald-50 text-emerald-950"}`}>
        <p className="font-medium">
          {audit.noEmailFound
            ? locale === "en" ? "The last run found no public email." : "A última execução terminou sem encontrar um email público."
            : locale === "en" ? "The last run found new public contact signals." : "A última execução encontrou novos sinais públicos de contato."}
        </p>
        <p className="mt-1 text-xs opacity-80">{formatDateTime(audit.createdAt, locale) ?? (locale === "en" ? "Time unavailable" : "Horário indisponível")}</p>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        <AuditList
          title={locale === "en" ? "Checked pages" : "Páginas verificadas"}
          emptyMessage={locale === "en" ? "No checked page was recorded." : "Nenhuma página verificada foi registrada."}
          items={audit.attemptedPages.map((page) => ({
            key: `${page.url}-${page.page_type ?? "page"}`,
            title: labelToken(page.page_type) ?? "Página",
            value: page.url,
            meta: compact([
              page.fetched ? `${locale === "en" ? "Fetched" : "Coletada"}${page.http_status ? ` (${page.http_status})` : ""}` : locale === "en" ? "Not fetched" : "Não coletada",
              page.discovered_from_url ? `${locale === "en" ? "Discovered from" : "Descoberta a partir de"} ${page.discovered_from_url}` : null,
              page.note,
            ]),
          }))}
        />
        <AuditList
          title={locale === "en" ? "Fetched pages" : "Páginas coletadas"}
          emptyMessage={locale === "en" ? "No fetched page was recorded." : "Nenhuma página coletada foi registrada."}
          items={audit.fetchedPageUrls.map((url) => ({
            key: url,
            title: locale === "en" ? "Fetched" : "Coletada",
            value: url,
            meta: null,
          }))}
        />
      </div>

      <AuditList
        title={locale === "en" ? "Extracted contacts" : "Contatos extraídos"}
        emptyMessage={locale === "en" ? "No extracted contact was recorded in the last run." : "Nenhum contato extraído foi registrado na última execução."}
        items={audit.extractedContacts.map((contact, index) => ({
          key: `${contact.source_url}-${contact.normalized_value ?? contact.raw_value}-${index}`,
          title: `${labelToken(contact.contact_type) ?? "Contato"}: ${contact.normalized_value || contact.raw_value}`,
          value: contact.source_url,
          meta: compact([
            `${locale === "en" ? "Confidence" : "Confiança"} ${Math.round(contact.confidence * 100)}%`,
            contact.addedToLead ? locale === "en" ? "Added to lead" : "Adicionado ao lead" : locale === "en" ? "Already known" : "Já conhecido",
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
  const { locale } = useI18n();
  return (
    <div>
      <p className="text-xs font-medium uppercase text-neutral-500">{translateLooseText(title, locale)}</p>
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
            <p className="text-xs text-neutral-500">
              {locale === "en" ? `${items.length - 6} additional items not shown.` : `${items.length - 6} itens adicionais não exibidos.`}
            </p>
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

function cnpjClientStatusLabel(lead: LeadDetail, locale: "pt-BR" | "en") {
  const metadata = asRecord(lead.cnpj_metadata_json);
  const reasonCode = asNullableString(metadata?.reason_code);
  const candidateSummaries = getCnpjCandidateSummaries(lead);

  if (!lead.cnpj_match_status || lead.cnpj_match_status === "unknown") {
    return locale === "en" ? "Not checked" : "Não consultado";
  }
  if (lead.cnpj_match_status === "matched") {
    return metadata?.approved_manually
      ? locale === "en" ? "Manually confirmed" : "Confirmado manualmente"
      : locale === "en" ? "Automatically confirmed" : "Confirmado automaticamente";
  }
  if (lead.cnpj_match_status === "needs_review") {
    return candidateSummaries.length > 1
      ? locale === "en" ? "Multiple candidates found" : "Múltiplos candidatos encontrados"
      : locale === "en" ? "Candidate found" : "Candidato encontrado";
  }
  if (reasonCode === "company_search_rate_limited" || reasonCode === "cnpj_provider_rate_limited") {
    return locale === "en" ? "Provider limit reached" : "Limite do provedor, tente novamente";
  }
  if (lead.cnpj_match_status === "not_found") {
    return candidateSummaries.length > 0
      ? locale === "en" ? "Low-confidence candidates" : "Candidatos fracos"
      : locale === "en" ? "Not found" : "Não encontrado";
  }
  return labelToken(lead.cnpj_match_status) ?? (locale === "en" ? "Not checked" : "Não consultado");
}

function formatConfidence(value?: number | null, locale: "pt-BR" | "en" = "pt-BR") {
  if (typeof value !== "number") {
    return locale === "en" ? "Not provided" : "Não informado";
  }
  return `${Math.round(value * 100)}%`;
}

function formatScore(value?: number | null, locale: "pt-BR" | "en" = "pt-BR") {
  if (typeof value !== "number") {
    return locale === "en" ? "Not provided" : "Não informado";
  }
  return `${Math.round(value)} / 100`;
}

function joinList(values: string[] | null | undefined) {
  if (!values?.length) {
    return null;
  }
  return values.join(", ");
}

function formatEvidenceSummary(evidence: Record<string, number>, locale: "pt-BR" | "en" = "pt-BR") {
  const entries = Object.entries(evidence);
  if (entries.length === 0) {
    return locale === "en" ? "No relevant positive criterion was recorded." : "Nenhum critério positivo relevante foi registrado.";
  }
  return entries
    .map(([key, value]) => `${labelEvidence(key, locale)} (+${value})`)
    .join(", ");
}

function labelEvidence(key: string, locale: "pt-BR" | "en" = "pt-BR") {
  const labels: Record<string, { en: string; pt: string }> = {
    domain: { en: "Domain", pt: "Domínio" },
    phone: { en: "Phone", pt: "Telefone" },
    alias_name: { en: "Trade name", pt: "Nome fantasia" },
    legal_name: { en: "Legal name", pt: "Razão social" },
    address: { en: "Address", pt: "Endereço" },
    postal_code: { en: "Postal code", pt: "CEP" },
    city: { en: "City", pt: "Cidade" },
    state: { en: "State", pt: "UF" },
    activity: { en: "Activity", pt: "Atividade" },
  };
  const label = labels[key];
  return label ? (locale === "en" ? label.en : label.pt) : key;
}

function labelPenalty(key: string, locale: "pt-BR" | "en" = "pt-BR") {
  const labels: Record<string, { en: string; pt: string }> = {
    different_number: { en: "different number", pt: "número diferente" },
    different_city: { en: "different city", pt: "cidade diferente" },
    different_state: { en: "different state", pt: "UF diferente" },
  };
  const label = labels[key];
  return label ? (locale === "en" ? label.en : label.pt) : key;
}

function formatDateTime(value?: string | null, locale: "pt-BR" | "en" = "pt-BR") {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return new Intl.DateTimeFormat(locale === "en" ? "en-US" : "pt-BR", {
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
  const candidateSummary = getCnpjCandidateSummary(lead);

  if (lead.cnpj_match_status === "needs_review" && candidateSummary) {
    return candidateSummary.review_reason ?? "A busca encontrou um candidato, mas precisa de revisão manual.";
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
  if (reasonCode === "cnpja_zero_candidates") {
    return "A CNPJá não retornou candidatos para este lead.";
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
  if (reasonCode === "company_search_pending_retry") {
    return "Busca cadastral pausada por limite do provedor. Tente novamente em cerca de 1 minuto.";
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

function getCnpjStatusHintV2(lead: LeadDetail) {
  const metadata = asRecord(lead.cnpj_metadata_json);
  const reasonCode = typeof metadata?.reason_code === "string" ? metadata.reason_code : null;
  const candidateSummary = getCnpjCandidateSummary(lead);
  const candidateSummaries = getCnpjCandidateSummaries(lead);

  if (metadata?.approved_manually) {
    return "Aprovado manualmente.";
  }

  if (reasonCode === "paid_search_recently_attempted") {
    return "Busca paga já feita recentemente para este lead. Resultado anterior preservado para evitar gastar créditos de novo.";
  }

  if (lead.cnpj_match_status === "needs_review" && candidateSummary) {
    if (candidateSummaries.length > 1) {
      return "Mais de um candidato forte encontrado. Escolha o cadastro correto.";
    }
    if (reasonCode === "skipped_review_candidate_exists") {
      return "Candidato encontrado. Revise e aprove antes de consultar novamente.";
    }
    return candidateSummary.review_reason ?? "A busca encontrou um candidato, mas precisa de revisão manual.";
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
  if (reasonCode === "cnpja_zero_candidates") {
    return "A CNPJá não retornou candidatos para este lead.";
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
  if (reasonCode === "company_search_pending_retry") {
    return "Busca cadastral pausada por limite do provedor. Tente novamente em cerca de 1 minuto.";
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

function getCnpjCandidateSummaries(lead: LeadDetail): LeadCnpjCandidateSummary[] {
  const metadata = asRecord(lead.cnpj_metadata_json);
  const candidates = Array.isArray(metadata?.candidate_summaries) ? metadata.candidate_summaries : [];
  const parsedCandidates = candidates
    .map((candidate) => parseCnpjCandidateSummary(candidate))
    .filter((candidate): candidate is LeadCnpjCandidateSummary => candidate !== null);

  if (parsedCandidates.length > 0) {
    return parsedCandidates;
  }

  const primaryCandidate = parseCnpjCandidateSummary(metadata?.candidate_summary);
  return primaryCandidate ? [primaryCandidate] : [];
}

function getCnpjCandidateSummary(lead: LeadDetail): LeadCnpjCandidateSummary | null {
  return getCnpjCandidateSummaries(lead)[0] ?? null;
}

function parseCnpjCandidateSummary(value: unknown): LeadCnpjCandidateSummary | null {
  const candidate = asRecord(value);
  if (!candidate) {
    return null;
  }
  return {
    cnpj: asNullableString(candidate.cnpj),
    legal_name: normalizeMojibakeText(asNullableString(candidate.legal_name)),
    trade_name: normalizeMojibakeText(asNullableString(candidate.trade_name)),
    address: normalizeMojibakeText(asNullableString(candidate.address)),
    city: normalizeMojibakeText(asNullableString(candidate.city)),
    state: normalizeMojibakeText(asNullableString(candidate.state)),
    postal_code: normalizeMojibakeText(asNullableString(candidate.postal_code)),
    phones: asStringArray(candidate.phones),
    emails: asStringArray(candidate.emails),
    primary_activity: normalizeMojibakeText(asNullableString(candidate.primary_activity)),
    provider: normalizeMojibakeText(asNullableString(candidate.provider)),
    score: asNullableNumber(candidate.score),
    match_confidence: asNullableNumber(candidate.match_confidence),
    evidence: asNumberRecord(candidate.evidence),
    penalties: asStringArray(candidate.penalties),
    query_mode: normalizeMojibakeText(asNullableString(candidate.query_mode)),
    query_mode_label: normalizeMojibakeText(asNullableString(candidate.query_mode_label)),
    blocked_from_autofill_reason: normalizeMojibakeText(asNullableString(candidate.blocked_from_autofill_reason)),
    review_reason:
      normalizeMojibakeText(asNullableString(candidate.review_reason)) ??
      reviewReasonFromCode(asNullableString(candidate.blocked_from_autofill_reason)),
    person_like_legal_name: Boolean(candidate.person_like_legal_name),
    legal_name_note: normalizeMojibakeText(asNullableString(candidate.legal_name_note)),
    manual_review_approvable:
      candidate.manual_review_approvable === false ? false : hasFullCnpj(asNullableString(candidate.cnpj)),
  };
}

function getCnpjSearchDiagnostics(lead: LeadDetail): LeadCnpjSearchDiagnostics | null {
  const metadata = asRecord(lead.cnpj_metadata_json);
  const crawlSummary = asRecord(metadata?.crawl_summary);
  const companySearch = asRecord(crawlSummary?.company_search);
  if (!companySearch) {
    return null;
  }

  return {
    provider: asNullableString(companySearch.provider),
    searched_alias_names: asStringArray(companySearch.searched_alias_names),
    searched_names: asStringArray(companySearch.searched_names),
    searched_legal_names: asStringArray(companySearch.searched_legal_names),
    searched_city: asNullableString(companySearch.searched_city),
    searched_state: asNullableString(companySearch.searched_state),
    searched_municipality_code: asNullableString(companySearch.searched_municipality_code),
    searched_zip: asNullableString(companySearch.searched_zip),
    searched_district: asNullableString(companySearch.searched_district),
    searched_phone_area: asNullableString(companySearch.searched_phone_area),
    searched_email_domain: asNullableString(companySearch.searched_email_domain),
    search_mode: asNullableString(companySearch.search_mode),
    search_attempts_count: asNullableNumber(companySearch.search_attempts_count),
    search_attempts: asSearchAttempts(companySearch.search_attempts),
    candidates_returned_count: asNullableNumber(companySearch.candidates_returned_count),
    extracted_zip_from_address: Boolean(companySearch.extracted_zip_from_address),
    cnpja_zero_candidates: Boolean(companySearch.cnpja_zero_candidates),
    paid_calls_made: asNullableNumber(companySearch.paid_calls_made),
    paid_calls_skipped_duplicate: asNullableNumber(companySearch.paid_calls_skipped_duplicate),
    paid_calls_skipped_recent: asNullableNumber(companySearch.paid_calls_skipped_recent),
    top_candidate_score: asNullableNumber(companySearch.top_candidate_score),
    top_candidate_rejection_reason: asNullableString(companySearch.top_candidate_rejection_reason),
    recent_search_skipped: Boolean(companySearch.recent_search_skipped),
    repeat_cooldown_hours: asNullableNumber(companySearch.repeat_cooldown_hours),
    last_result_status: asNullableString(companySearch.last_result_status),
  };
}

function hasFullCnpj(value?: string | null) {
  if (!value) {
    return false;
  }
  const digits = value.replace(/\D/g, "");
  return digits.length === 14;
}

function reviewReasonFromCode(code?: string | null) {
  if (code === "missing_full_cnpj") {
    return "O provedor não retornou um CNPJ completo para confirmação automática.";
  }
  if (code === "city_state_conflict") {
    return "Cidade ou UF do candidato conflita com o lead.";
  }
  if (code === "ambiguous_top_candidates") {
    return "Mais de um candidato forte foi encontrado.";
  }
  if (code === "provider_preview_masked") {
    return "O provedor retornou dados em modo prévia ou mascarados.";
  }
  if (code === "insufficient_identity_support") {
    return "Os sinais de identidade ainda não são suficientes para preencher automaticamente.";
  }
  if (code === "below_autofill_threshold") {
    return "O candidato ficou abaixo do limite de confirmação automática.";
  }
  if (code === "below_review_threshold") {
    return "O melhor candidato ficou abaixo do limite mínimo para revisão.";
  }
  return null;
}

function buildCnpjDiagnosticsMessage(
  diagnostics: LeadCnpjSearchDiagnostics,
  matchStatus: LeadDetail["cnpj_match_status"],
) {
  const providerLabel = diagnostics.provider === "cnpja_commercial" ? "CNPJá" : "A busca cadastral";
  const searchedNames = diagnostics.searched_names.filter(Boolean).slice(0, 4).join(", ");

  if (diagnostics.cnpja_zero_candidates) {
    return searchedNames
      ? `${providerLabel} retornou 0 candidatos para: ${searchedNames}.`
      : `${providerLabel} retornou 0 candidatos para esta empresa.`;
  }

  if (matchStatus === "not_found" && (diagnostics.candidates_returned_count ?? 0) > 0) {
    return `${providerLabel} retornou candidatos, mas o melhor ficou com baixa confiança.`;
  }

  if (matchStatus === "needs_review" && (diagnostics.candidates_returned_count ?? 0) > 0) {
    return `${providerLabel} encontrou um candidato promissor, mas ele ainda precisa de revisão manual.`;
  }

  return null;
}

function buildCnpjDiagnosticsMessageV2(
  diagnostics: LeadCnpjSearchDiagnostics,
  matchStatus: LeadDetail["cnpj_match_status"],
) {
  if (diagnostics.recent_search_skipped) {
    return "Busca paga já feita recentemente para este lead. Resultado anterior preservado para evitar gastar créditos de novo.";
  }
  return buildCnpjDiagnosticsMessage(diagnostics, matchStatus);
}

function normalizeMojibakeText(value?: string | null) {
  if (!value || (!value.includes("\u00c3") && !value.includes("\u00c2"))) {
    return value ?? null;
  }

  const replacements: Array<[string, string]> = [
    ["\u00c3\u0192\u00c2\u00a3", "?"],
    ["\u00c3\u0192\u00c2\u00a1", "?"],
    ["\u00c3\u0192\u00c2\u00a2", "?"],
    ["\u00c3\u0192\u00c2\u00aa", "?"],
    ["\u00c3\u0192\u00c2\u00a9", "?"],
    ["\u00c3\u0192\u00c2\u00ad", "?"],
    ["\u00c3\u0192\u00c2\u00b3", "?"],
    ["\u00c3\u0192\u00c2\u00b4", "?"],
    ["\u00c3\u0192\u00c2\u00ba", "?"],
    ["\u00c3\u0192\u00c2\u00a7", "?"],
    ["\u00c3\u0192\u00c2\u00b5", "?"],
    ["\u00c3\u00a3", "?"],
    ["\u00c3\u00a1", "?"],
    ["\u00c3\u00a2", "?"],
    ["\u00c3\u00aa", "?"],
    ["\u00c3\u00a9", "?"],
    ["\u00c3\u00ad", "?"],
    ["\u00c3\u00b3", "?"],
    ["\u00c3\u00b4", "?"],
    ["\u00c3\u00ba", "?"],
    ["\u00c3\u00a7", "?"],
    ["\u00c3\u00b5", "?"],
    ["\u00c2\u00ba", "?"],
    ["\u00c2\u00aa", "?"],
  ];

  let normalized = value;
  for (const [source, target] of replacements) {
    normalized = normalized.replaceAll(source, target);
  }
  return normalized;
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

function asSearchAttempts(value: unknown): LeadCnpjSearchDiagnostics["search_attempts"] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .map((item) => asRecord(item))
    .filter((item): item is Record<string, unknown> => item !== null)
    .map((item) => ({
      attempt_index: asNullableNumber(item.attempt_index),
      query_mode: asNullableString(item.query_mode),
      query_mode_label: asNullableString(item.query_mode_label),
      query_param: asNullableString(item.query_param),
      status: asNullableString(item.status) ?? asNullableString(item.provider_status),
      reason: asNullableString(item.reason),
      searched_values: asStringArray(item.searched_values),
      candidate_count: asNullableNumber(item.candidate_count),
      candidates_returned_count: asNullableNumber(item.candidates_returned_count),
      municipality_code: asNullableString(item.municipality_code),
      postal_code: asNullableString(item.postal_code),
      district: asNullableString(item.district),
      phone_area: asNullableString(item.phone_area),
      email_domain: asNullableString(item.email_domain),
    }));
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
