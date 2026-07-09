"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { GlassSelect } from "@/components/ui/GlassSelect";
import {
  assignLeadBatch,
  enrichLeadBatchCnpj,
  enrichLeadBatch,
  exportExcelForScope,
  getLatestImportBatch,
  resolveLeadScope,
} from "@/lib/api/leads";
import type {
  LeadBatchAssignmentResponse,
  LeadBatchCNPJEnrichmentResponse,
  LeadBatchEnrichmentResponse,
  LeadListParams,
  LeadScopeRequest,
} from "@/lib/api/types";
import { formatUserFacingError, sanitizeUserFacingMessage } from "@/lib/ui/messages";
import { useI18n } from "@/lib/i18n/client";
import { formatNumber } from "@/lib/i18n/format";
import { translateLooseText } from "@/lib/i18n/loose";
import type { Locale } from "@/lib/i18n/translations";

type ActionScope = "selected" | "current" | "latest";
type ActionKind = "enrich" | "cnpj" | "assign" | "export";
type ActionMutationInput = {
  kind: ActionKind;
  scope: ActionScope;
};

type ConfirmationState = {
  kind: ActionKind;
  scope: ActionScope;
  count: number;
  label: string;
};

type LeadBatchActionsProps = {
  selectedLeadIds: number[];
  currentFilters: LeadListParams;
  currentTotal: number;
  searchActive: boolean;
  cnpjEnabled: boolean;
};

type ActionResult =
  | {
      kind: "enrich";
      scopeLabel: string;
      requested: number;
      summary: LeadBatchEnrichmentResponse["summary"];
    }
  | {
      kind: "cnpj";
      scopeLabel: string;
      requested: number;
      summary: LeadBatchCNPJEnrichmentResponse["summary"];
    }
  | {
      kind: "assign";
      scopeLabel: string;
      requested: number;
      summary: LeadBatchAssignmentResponse["summary"];
    }
  | {
      kind: "export";
      scopeLabel: string;
      requested: number;
      filename: string;
    };

const BROAD_SCOPE_CONFIRMATION_THRESHOLD = 25;

export function LeadBatchActions({
  selectedLeadIds,
  currentFilters,
  currentTotal,
  searchActive,
  cnpjEnabled,
}: LeadBatchActionsProps) {
  const { locale, t } = useI18n();
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<ActionScope>("selected");
  const [lastResult, setLastResult] = useState<ActionResult | null>(null);
  const [confirmation, setConfirmation] = useState<ConfirmationState | null>(null);
  const [deliverySearchMode, setDeliverySearchMode] = useState(false);
  const [forcePaidSearch, setForcePaidSearch] = useState(false);
  const previousSelectedCount = useRef(selectedLeadIds.length);

  useEffect(() => {
    if (previousSelectedCount.current === 0 && selectedLeadIds.length > 0) {
      setScope("selected");
    }
    previousSelectedCount.current = selectedLeadIds.length;
  }, [selectedLeadIds.length]);

  useEffect(() => {
    setConfirmation(null);
  }, [scope, selectedLeadIds.length, currentTotal]);

  const latestBatchQuery = useQuery({
    queryKey: ["latest-import-batch", locale],
    queryFn: getLatestImportBatch,
    enabled: scope === "latest",
    retry: 1,
  });

  const actionMutation = useMutation({
    mutationFn: async ({ kind, scope: scopeAtClick }: ActionMutationInput) => {
      if (kind === "export") {
        const exportScope = await buildDirectActionScope(
          scopeAtClick,
          selectedLeadIds,
          currentFilters,
          currentTotal,
        );
        if (exportScope.requested === 0) {
          throw new Error(t("error.noLeadsInScope"));
        }
        const exported = await exportExcelForScope(exportScope.request);
        downloadBlob(exported.blob, exported.filename);
        return {
          kind,
          scopeLabel: exportScope.scopeLabel,
          requested: exportScope.requested,
          filename: exported.filename,
        } satisfies ActionResult;
      }

      if (kind === "assign") {
        if (scopeAtClick === "latest") {
          throw new Error(t("error.assignLatestScope"));
        }
        const response = await assignLeadBatch(buildScopeRequest(scopeAtClick, selectedLeadIds, currentFilters));
        return {
          kind,
          scopeLabel: response.summary.scope_label,
          requested: response.summary.requested,
          summary: response.summary,
        } satisfies ActionResult;
      }

      const resolvedScope = await resolveActionScope(scopeAtClick, selectedLeadIds, currentFilters);

      if (kind === "enrich") {
        if (resolvedScope.leadIds.length === 0) {
          throw new Error(t("error.noLeadsInScope"));
        }
        const response = await enrichLeadBatch(resolvedScope.leadIds);
        return {
          kind,
          scopeLabel: resolvedScope.scopeLabel,
          requested: resolvedScope.requested,
          summary: response.summary,
        } satisfies ActionResult;
      }

      if (kind === "cnpj") {
        if (!cnpjEnabled) {
          throw new Error(t("error.cnpjDisabled"));
        }
        if (resolvedScope.leadIds.length === 0) {
          throw new Error(t("error.noLeadsInScope"));
        }
        const response = await enrichLeadBatchCnpj(resolvedScope.leadIds, {
          searchMode: deliverySearchMode ? "delivery" : "balanced",
          forcePaidSearch,
        });
        return {
          kind,
          scopeLabel: resolvedScope.scopeLabel,
          requested: resolvedScope.requested,
          summary: response.summary,
        } satisfies ActionResult;
      }

      throw new Error(t("error.unknownBatchAction"));
    },
    onSuccess: (result) => {
      setLastResult(result);
      if (result.kind !== "export") {
        void queryClient.invalidateQueries({ queryKey: ["leads"] });
        void queryClient.invalidateQueries({ queryKey: ["lead-detail"] });
        void queryClient.invalidateQueries({ queryKey: ["lead-options"] });
      }
    },
  });

  const actionCount = useMemo(() => {
    if (scope === "selected") {
      return selectedLeadIds.length;
    }
    if (scope === "current") {
      return currentTotal;
    }
    return latestBatchQuery.data?.lead_count ?? null;
  }, [currentTotal, latestBatchQuery.data?.lead_count, scope, selectedLeadIds.length]);

  const selectedDisabled = scope === "selected" && selectedLeadIds.length === 0;
  const currentDisabled = scope === "current" && currentTotal === 0;
  const latestDisabled = scope === "latest" && (latestBatchQuery.isLoading || latestBatchQuery.isError || (latestBatchQuery.data?.lead_count ?? 0) === 0);
  const assignDisabled = actionMutation.isPending || selectedDisabled || currentDisabled || latestDisabled || scope === "latest";
  const scopedActionDisabled = actionMutation.isPending || selectedDisabled || currentDisabled || latestDisabled;
  const scopeOptions = [
    { value: "selected", label: t("batch.selectedScope", { count: formatNumber(selectedLeadIds.length, locale) }) },
    { value: "current", label: t("batch.currentScope", { count: formatNumber(currentTotal, locale) }) },
    {
      value: "latest",
      label: t("batch.latestScope", { count: latestBatchQuery.data ? ` (${formatNumber(latestBatchQuery.data.lead_count, locale)})` : "" }),
    },
  ];

  return (
    <section className="rounded-[1.5rem] border border-brand-orchid/10 bg-white/[0.36] p-3 shadow-[0_10px_28px_rgba(29,22,48,0.06),inset_0_1px_0_rgba(255,255,255,0.50)] backdrop-blur-xl">
      <div className="flex flex-col gap-3 2xl:flex-row 2xl:items-end 2xl:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="ea-kicker">{t("batch.kicker")}</p>
            {searchActive ? <ToolbarPill>{t("batch.quickSearchScope")}</ToolbarPill> : null}
          </div>
          <h2 className="mt-1 text-sm font-semibold text-brand-graphite">{t("batch.title")}</h2>
        </div>

        <div className="grid gap-3 lg:grid-cols-[minmax(220px,0.9fr)_100px_minmax(360px,1.45fr)] lg:items-end 2xl:min-w-[760px]">
          <div className="block">
            <span className="text-xs font-medium text-brand-muted">{t("batch.scope")}</span>
            <GlassSelect
              value={scope}
              options={scopeOptions}
              ariaLabel={t("batch.scope")}
              className="mt-1"
              onChange={(value) => {
                setScope(value as ActionScope);
                setLastResult(null);
              }}
            />
          </div>

          <div className="rounded-[0.95rem] border border-brand-orchid/10 bg-white/[0.28] px-3 py-2">
            <p className="text-[0.68rem] font-bold uppercase tracking-[0.12em] text-brand-muted">{t("batch.count")}</p>
            <p className="text-lg font-semibold text-brand-graphite">
              {actionCount === null ? "..." : formatNumber(actionCount, locale)}
            </p>
          </div>

          <div className={`grid gap-2 sm:grid-cols-2 ${cnpjEnabled ? "xl:grid-cols-4" : "xl:grid-cols-3"}`}>
            <ActionButton disabled={scopedActionDisabled} onClick={() => requestAction("enrich")}>
              {t("batch.enrich")}
            </ActionButton>
            {cnpjEnabled ? (
              <ActionButton disabled={scopedActionDisabled} onClick={() => requestAction("cnpj")}>
                {t("batch.cnpj")}
              </ActionButton>
            ) : null}
            <ActionButton disabled={assignDisabled} onClick={() => requestAction("assign")}>
              {t("batch.assign")}
            </ActionButton>
            <ActionButton disabled={scopedActionDisabled} onClick={() => requestAction("export")}>
              {t("batch.export")}
            </ActionButton>
          </div>
        </div>
      </div>

      {cnpjEnabled ? (
        <div className="mt-3 flex flex-col gap-2 border-t border-brand-orchid/10 pt-3 sm:flex-row sm:flex-wrap sm:items-center">
          <label className="flex items-start gap-2 text-xs text-brand-muted">
            <input
              type="checkbox"
              checked={deliverySearchMode}
              onChange={(event) => setDeliverySearchMode(event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-neutral-300"
            />
            <span>{t("batch.deliverySearchMode")}</span>
          </label>
          <label className="flex items-start gap-2 text-xs text-brand-muted">
            <input
              type="checkbox"
              checked={forcePaidSearch}
              onChange={(event) => setForcePaidSearch(event.target.checked)}
              className="mt-0.5 h-4 w-4 rounded border-neutral-300"
            />
            <span>{t("batch.forcePaidSearch")}</span>
          </label>
          {deliverySearchMode ? <span className="text-xs font-medium text-amber-700">{t("batch.deliverySearchWarning")}</span> : null}
        </div>
      ) : null}

      {selectedDisabled ? (
        <p className="mt-3 rounded-2xl border border-brand-orchid/10 bg-brand-orchid/[0.06] px-3 py-2 text-sm text-brand-muted">
          {t("batch.selectedRequired")}
        </p>
      ) : null}

      {scope === "latest" ? (
        <p className="mt-3 rounded-2xl border border-brand-orchid/10 bg-brand-orchid/[0.06] px-3 py-2 text-sm text-brand-muted">
          {t("batch.latestScopeNotice")}
          {latestBatchQuery.isLoading ? ` ${t("batch.latestScopeLoading")}` : ""}
          {latestBatchQuery.isError ? ` ${t("batch.latestScopeError")}` : ""}
        </p>
      ) : null}

      {confirmation ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-amber-950">
            {locale === "en"
              ? `You are about to ${confirmation.label.toLowerCase()} ${formatNumber(confirmation.count, locale)} leads.`
              : `Você está prestes a ${confirmation.label.toLowerCase()} ${formatNumber(confirmation.count, locale)} leads.`}
          </p>
          <p className="mt-1 text-sm text-amber-900">
            {locale === "en" ? "Confirm this bulk action before continuing." : "Confirme esta ação em massa antes de continuar."}
          </p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row">
            <button
              type="button"
              onClick={() => {
                const confirmed = confirmation;
                setConfirmation(null);
                actionMutation.mutate({ kind: confirmed.kind, scope: confirmed.scope });
              }}
              className="rounded-md border border-amber-900 bg-amber-900 px-3 py-2 text-sm font-medium text-white"
            >
              {t("common.confirm")} {confirmation.label.toLowerCase()}
            </button>
            <button
              type="button"
              onClick={() => setConfirmation(null)}
              className="rounded-md border border-amber-300 bg-white px-3 py-2 text-sm font-medium text-amber-950"
            >
              {t("common.cancel")}
            </button>
          </div>
        </div>
      ) : null}

      {actionMutation.isPending ? (
        <p className="mt-3 rounded-2xl border border-brand-olive/70 bg-brand-olive/20 px-3 py-2 text-sm text-brand-graphite">
          {t("batch.processing")}
        </p>
      ) : null}

      {actionMutation.isError ? (
        <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {formatError(actionMutation.error, locale)}
        </p>
      ) : null}

      {lastResult ? <ActionResultSummary result={lastResult} /> : null}
    </section>
  );

  function requestAction(kind: ActionKind) {
    const count = actionCount ?? 0;
    if (requiresConfirmation(scope, count)) {
      setConfirmation({
        kind,
        scope,
        count,
        label: actionLabel(kind, locale),
      });
      return;
    }

    actionMutation.mutate({ kind, scope });
  }
}

function ActionButton({
  disabled,
  onClick,
  children,
}: {
  disabled: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="ea-button-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function ToolbarPill({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full border border-brand-orchid/10 bg-brand-orchid/[0.055] px-2.5 py-1 text-xs font-semibold text-brand-muted">
      {children}
    </span>
  );
}

function ActionResultSummary({ result }: { result: ActionResult }) {
  const { locale } = useI18n();

  if (result.kind === "enrich") {
    const hasErrors = result.summary.errors > 0;
    const newPublicChannelCount =
      result.summary.emails_found +
      result.summary.instagrams_found +
      result.summary.whatsapps_found +
      result.summary.contact_forms_found;
    return (
      <ResultBox
        title={`${hasErrors ? batchCopy(locale).enrichDoneWithWarnings : batchCopy(locale).enrichDone} - ${formatScopeLabel(result.scopeLabel, locale)}`}
      >
        <ResultNarrative text={buildEnrichmentNarrative(result.summary, locale)} />
        <ResultMetric label={batchCopy(locale).requested} value={result.requested} />
        <ResultMetric label={batchCopy(locale).processed} value={result.summary.processed} />
        <ResultMetric label={batchCopy(locale).completed} value={result.summary.success_count} />
        <ResultMetric label={batchCopy(locale).newContacts} value={result.summary.contacts_added} />
        <ResultMetric label={batchCopy(locale).publicChannels} value={newPublicChannelCount} />
        <ResultMetric label="Emails" value={result.summary.emails_found} />
        <ResultMetric label="Instagrams" value={result.summary.instagrams_found} />
        <ResultMetric label="WhatsApps" value={result.summary.whatsapps_found} />
        <ResultMetric label={batchCopy(locale).forms} value={result.summary.contact_forms_found} />
        <ResultMetric label={batchCopy(locale).skipped} value={result.summary.skipped} />
        <ResultMetric label={batchCopy(locale).errors} value={result.summary.errors} />
        {hasErrors ? <FailedLeadSummary summary={result.summary} locale={locale} /> : null}
      </ResultBox>
    );
  }

  if (result.kind === "cnpj") {
    const hasErrors = result.summary.error_count > 0;
    return (
      <ResultBox
        title={`${hasErrors ? batchCopy(locale).cnpjDoneWithWarnings : batchCopy(locale).cnpjDone} - ${formatScopeLabel(result.scopeLabel, locale)}`}
      >
        <ResultNarrative text={buildCnpjNarrativeV2(result.summary, locale)} />
        <ResultMetric label={batchCopy(locale).requested} value={result.requested} />
        <ResultMetric label={batchCopy(locale).processed} value={result.summary.processed} />
        <ResultMetric label={batchCopy(locale).filled} value={result.summary.matched_count} />
        <ResultMetric label={batchCopy(locale).needsReview} value={result.summary.needs_review_count} />
        <ResultMetric label={batchCopy(locale).notFound} value={result.summary.not_found_count} />
        <ResultMetric label={batchCopy(locale).alreadyHadCnpj} value={result.summary.skipped_known_count} />
        <ResultMetric label={batchCopy(locale).waitingReview} value={result.summary.skipped_review_candidate_count} />
        <ResultMetric label={batchCopy(locale).recentPaidSearch} value={result.summary.paid_search_recently_attempted_count} />
        <ResultMetric label={batchCopy(locale).checkedNow} value={result.summary.company_search_consulted_now_count} />
        <ResultMetric label={batchCopy(locale).paidCalls} value={result.summary.paid_calls_made} />
        <ResultMetric label={batchCopy(locale).duplicateCallsSkipped} value={result.summary.paid_calls_skipped_duplicate} />
        <ResultMetric label={batchCopy(locale).errors} value={result.summary.error_count} />
        {hasErrors ? (
          <div className="basis-full border-l-2 border-amber-300/80 bg-amber-50/45 px-3 py-2">
            <p className="text-xs font-semibold uppercase text-amber-900">{batchCopy(locale).batchErrors}</p>
            <ul className="mt-2 space-y-1 text-sm text-amber-900">
              {result.summary.errors.slice(0, 3).map((message) => (
                <li key={message}>{sanitizeUserFacingMessage(message, batchCopy(locale).cnpjPartialFailure)}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </ResultBox>
    );
  }

  if (result.kind === "assign") {
    return (
      <ResultBox title={`${batchCopy(locale).assignmentDone} - ${formatScopeLabel(result.scopeLabel, locale)}`}>
        <ResultMetric label={batchCopy(locale).requested} value={result.requested} />
        <ResultMetric label={batchCopy(locale).processed} value={result.summary.processed} />
        <ResultMetric label={batchCopy(locale).updated} value={result.summary.changed} />
        <ResultMetric label={batchCopy(locale).missingIds} value={result.summary.missing_lead_ids.length} />
      </ResultBox>
    );
  }

  return (
    <ResultBox title={`${batchCopy(locale).spreadsheetDownloaded} - ${formatScopeLabel(result.scopeLabel, locale)}`}>
      <ResultNarrative text={batchCopy(locale).exportReady} />
      <ResultMetric label="Leads" value={result.requested} />
      <div className="basis-full border-l border-brand-orchid/14 px-3 py-1.5 sm:basis-auto sm:flex-1">
        <p className="text-xs font-medium text-neutral-500">{batchCopy(locale).file}</p>
        <p className="mt-1 break-all text-sm font-semibold text-neutral-950">{result.filename}</p>
      </div>
    </ResultBox>
  );
}

function ResultBox({ title, children }: { title: string; children: React.ReactNode }) {
  const { locale } = useI18n();
  const translatedTitle = translateLooseText(title, locale);
  const [heading, ...scopeParts] = translatedTitle.split(" - ");
  const scope = scopeParts.join(" - ");
  return (
    <div className="mt-3 rounded-[1.25rem] border border-brand-orchid/10 bg-white/[0.30] px-3.5 py-3 shadow-[0_10px_26px_rgba(29,22,48,0.045),inset_0_1px_0_rgba(255,255,255,0.52)] backdrop-blur-xl">
      <div className="flex min-w-0 flex-col gap-1 sm:flex-row sm:items-baseline sm:gap-2">
        <p className="text-sm font-bold text-brand-graphite">{heading}</p>
        {scope ? <p className="truncate text-xs font-semibold text-brand-muted">{scope}</p> : null}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-5 gap-y-2 border-t border-brand-orchid/10 pt-2.5">{children}</div>
    </div>
  );
}

function ResultNarrative({ text }: { text: string }) {
  const { locale } = useI18n();
  return (
    <p className="basis-full text-sm leading-6 text-brand-graphite">
      {translateLooseText(text, locale)}
    </p>
  );
}

function ResultMetric({ label, value }: { label: string; value: number }) {
  const { locale } = useI18n();
  return (
    <div className="min-w-[5.8rem] border-l border-brand-orchid/12 pl-3 first:border-l-0 first:pl-0">
      <p className="text-[0.66rem] font-bold uppercase tracking-[0.10em] text-brand-muted">{translateLooseText(label, locale)}</p>
      <p className="mt-0.5 text-base font-bold text-brand-graphite">{formatNumber(value, locale)}</p>
    </div>
  );
}

function FailedLeadSummary({ summary, locale }: { summary: LeadBatchEnrichmentResponse["summary"]; locale: Locale }) {
  return (
    <div className="basis-full border-l-2 border-amber-300/80 bg-amber-50/45 px-3 py-2">
      <p className="text-xs font-semibold uppercase text-amber-900">{batchCopy(locale).failedLeads}</p>
      <p className="mt-1 text-sm text-amber-950">
        {summary.failed_lead_ids.length
          ? `IDs: ${summary.failed_lead_ids.join(", ")}`
          : batchCopy(locale).failedWithoutIds}
      </p>
      {summary.error_messages.length ? (
        <ul className="mt-2 space-y-1 text-sm text-amber-900">
          {summary.error_messages.slice(0, 3).map((message) => (
            <li key={message}>{sanitizeUserFacingMessage(message, batchCopy(locale).enrichPartialFailure)}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

async function buildDirectActionScope(
  scope: ActionScope,
  selectedLeadIds: number[],
  currentFilters: LeadListParams,
  currentTotal: number,
): Promise<{ request: LeadScopeRequest; requested: number; scopeLabel: string }> {
  const request = buildScopeRequest(scope, selectedLeadIds, currentFilters);
  if (scope === "selected") {
    return { request, requested: selectedLeadIds.length, scopeLabel: "Selected leads" };
  }
  if (scope === "latest") {
    const latestBatch = await getLatestImportBatch();
    return { request, requested: latestBatch.lead_count, scopeLabel: `Latest import batch #${latestBatch.id}` };
  }
  return { request, requested: currentTotal, scopeLabel: "Current filtered set" };
}

function buildScopeRequest(scope: ActionScope, selectedLeadIds: number[], currentFilters: LeadListParams): LeadScopeRequest {
  if (scope === "selected") {
    return { lead_ids: selectedLeadIds };
  }

  if (scope === "latest") {
    return { latest_import_batch: true };
  }

  return { filters: currentScopeFilters(currentFilters) };
}

function requiresConfirmation(scope: ActionScope, count: number) {
  return scope !== "selected" && count >= BROAD_SCOPE_CONFIRMATION_THRESHOLD;
}

function actionLabel(kind: ActionKind, locale: Locale) {
  if (kind === "enrich") {
    return locale === "en" ? "Enrich" : "Enriquecer";
  }
  if (kind === "cnpj") {
    return locale === "en" ? "Enrich CNPJ" : "Enriquecer CNPJ";
  }
  if (kind === "assign") {
    return locale === "en" ? "Assign" : "Atribuir";
  }
  return locale === "en" ? "Export" : "Exportar";
}

async function resolveActionScope(
  scope: ActionScope,
  selectedLeadIds: number[],
  currentFilters: LeadListParams,
): Promise<{
  request: LeadScopeRequest;
  leadIds: number[];
  requested: number;
  scopeLabel: string;
}> {
  const request = buildScopeRequest(scope, selectedLeadIds, currentFilters);

  if (scope === "latest") {
    const latestBatch = await getLatestImportBatch();
    const resolved = await resolveLeadScope({ latest_import_batch: true });
    return {
      request,
      leadIds: resolved.lead_ids,
      requested: resolved.total || latestBatch.lead_count,
      scopeLabel: resolved.scope_label || `Latest import batch #${latestBatch.id}`,
    };
  }

  const resolved = await resolveLeadScope(request);
  return {
    request,
    leadIds: resolved.lead_ids,
    requested: resolved.total,
    scopeLabel: resolved.scope_label,
  };
}

function currentScopeFilters(filters: LeadListParams): LeadListParams {
  const { limit: _limit, offset: _offset, ...scopeFilters } = filters;
  return scopeFilters;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function formatError(error: unknown, locale: Locale) {
  return formatUserFacingError(error, "Não foi possível concluir a ação em lote.", locale);
}

function buildEnrichmentNarrative(summary: LeadBatchEnrichmentResponse["summary"], locale: Locale) {
  const newPublicChannelCount =
    summary.emails_found +
    summary.instagrams_found +
    summary.whatsapps_found +
    summary.contact_forms_found;

  if (summary.success_count === 0) {
    return locale === "en"
      ? `Processed ${summary.processed.toLocaleString()} leads, but none completed enrichment successfully.`
      : `Processamos ${summary.processed.toLocaleString()} leads, mas nenhum concluiu o enriquecimento com sucesso.`;
  }

  if (newPublicChannelCount === 0) {
    return locale === "en"
      ? `Processed ${summary.processed.toLocaleString()} leads. ${summary.success_count.toLocaleString()} completed successfully, but no new public channel was found.`
      : `Processamos ${summary.processed.toLocaleString()} leads. ${summary.success_count.toLocaleString()} concluíram com sucesso, mas nenhum novo canal público foi encontrado.`;
  }

  return locale === "en"
    ? `Processed ${summary.processed.toLocaleString()} leads and found ${summary.contacts_added.toLocaleString()} new contacts across ${newPublicChannelCount.toLocaleString()} public channels.`
    : `Processamos ${summary.processed.toLocaleString()} leads e encontramos ${summary.contacts_added.toLocaleString()} novos contatos em ${newPublicChannelCount.toLocaleString()} canais públicos.`;
}

function buildCnpjNarrative(summary: LeadBatchCNPJEnrichmentResponse["summary"], locale: Locale) {
  if (summary.processed === 0) {
    return locale === "en" ? "No leads were processed in this CNPJ lookup." : "Nenhum lead foi processado nesta consulta de CNPJ.";
  }

  if (
    summary.matched_count === 0 &&
    summary.needs_review_count === 0 &&
    summary.not_found_count === 0 &&
    summary.company_search_pending_retry_count > 0
  ) {
    return locale === "en"
      ? `CNPJ search is provider-limited. ${summary.company_search_pending_retry_count.toLocaleString()} companies were left for retry in about 1 minute.`
      : `Busca CNPJ limitada pelo provedor. ${summary.company_search_pending_retry_count.toLocaleString()} empresa(s) ficaram para tentar novamente em cerca de 1 minuto.`;
  }

  if (summary.error_count > 0 && summary.matched_count === 0 && summary.needs_review_count === 0 && summary.not_found_count === 0) {
    if (summary.provider_rate_limited_count > 0) {
      return locale === "en"
        ? "The public CNPJ lookup hit the provider limit. Retry with fewer companies at a time."
        : "A consulta pública de CNPJ atingiu o limite de uso. Tente novamente com menos empresas por vez.";
    }
    if (summary.company_search_rate_limited_count > 0) {
      return locale === "en"
        ? "The paid registry search hit the provider limit. Retry shortly."
        : "A busca cadastral paga atingiu o limite do provedor. Tente novamente em alguns instantes.";
    }
    if (summary.company_search_pending_retry_count > 0) {
      return locale === "en"
        ? "CNPJ search is provider-limited. Wait about 1 minute and retry."
        : "Busca CNPJ limitada pelo provedor. Aguarde cerca de 1 minuto e tente novamente.";
    }
    return locale === "en"
      ? "The CNPJ lookup hit a provider error for part of the batch. Retry shortly."
      : "A consulta CNPJ encontrou erro de provedor em parte do lote. Tente novamente em alguns instantes.";
  }

  if (summary.matched_count === 0 && summary.needs_review_count === 0 && summary.not_found_count > 0) {
    const genericCompanySearchNoCandidateCount = Math.max(
      0,
      summary.company_search_no_candidates_count - summary.company_search_zero_candidates_count,
    );
    const reasons = [
      summary.no_website_count ? `${summary.no_website_count.toLocaleString()} ${locale === "en" ? "without website" : "sem site"}` : null,
      summary.no_cnpj_on_website_count
        ? `${summary.no_cnpj_on_website_count.toLocaleString()} ${locale === "en" ? "without visible CNPJ on the site" : "sem CNPJ visível no site"}`
        : null,
      summary.website_timeout_count
        ? `${summary.website_timeout_count.toLocaleString()} ${locale === "en" ? "sites timed out" : "sites demoraram demais"}`
        : null,
      summary.website_unreachable_count
        ? `${summary.website_unreachable_count.toLocaleString()} ${locale === "en" ? "sites did not respond" : "sites sem resposta"}`
        : null,
      summary.validation_failed_count
        ? `${summary.validation_failed_count.toLocaleString()} ${locale === "en" ? "with CNPJ that failed public validation" : "com CNPJ sem validação pública"}`
        : null,
      summary.low_confidence_count
        ? `${summary.low_confidence_count.toLocaleString()} ${locale === "en" ? "low-confidence matches" : "com baixa confiança"}`
        : null,
      summary.provider_rate_limited_count
        ? `${summary.provider_rate_limited_count.toLocaleString()} ${locale === "en" ? "limited by public lookup" : "limitados pela consulta pública"}`
        : null,
      summary.provider_error_count
        ? `${summary.provider_error_count.toLocaleString()} ${locale === "en" ? "with provider errors" : "com erro de provedor"}`
        : null,
      summary.company_search_not_configured_count
        ? `${summary.company_search_not_configured_count.toLocaleString()} ${locale === "en" ? "without paid search configured" : "com busca paga não configurada"}`
        : null,
      summary.company_search_zero_candidates_count
        ? `${summary.company_search_zero_candidates_count.toLocaleString()} ${locale === "en" ? "with no candidates returned by CNPJá" : "sem candidatos retornados pela CNPJá"}`
        : null,
      genericCompanySearchNoCandidateCount
        ? `${genericCompanySearchNoCandidateCount.toLocaleString()} ${locale === "en" ? "without registry candidates" : "sem candidatos na busca cadastral"}`
        : null,
      summary.company_search_low_confidence_count
        ? `${summary.company_search_low_confidence_count.toLocaleString()} ${locale === "en" ? "low-confidence registry matches" : "com baixa confiança na busca cadastral"}`
        : null,
      summary.company_search_pending_retry_count
        ? `${summary.company_search_pending_retry_count.toLocaleString()} ${locale === "en" ? "waiting for retry because of provider limits" : "aguardando nova tentativa por limite do provedor"}`
        : null,
      summary.company_search_rate_limited_count
        ? `${summary.company_search_rate_limited_count.toLocaleString()} ${locale === "en" ? "limited by registry search" : "limitados pela busca cadastral"}`
        : null,
      summary.company_search_provider_error_count
        ? `${summary.company_search_provider_error_count.toLocaleString()} ${locale === "en" ? "with registry provider errors" : "com erro na busca cadastral"}`
        : null,
    ].filter(Boolean);

    if (reasons.length === 0) {
      return locale === "en"
        ? "0 CNPJs confirmed. No CNPJ was found on the checked websites."
        : "0 CNPJs confirmados. Nenhum CNPJ foi encontrado nos sites verificados.";
    }

    return locale === "en"
      ? `0 CNPJs confirmed. ${summary.not_found_count.toLocaleString()} unmatched: ${reasons.join(", ")}.`
      : `0 CNPJs confirmados. ${summary.not_found_count.toLocaleString()} sem correspondência: ${reasons.join(", ")}.`;
  }

  const paidSearchParts = [
    Math.max(0, summary.matched_count - summary.company_search_matched_count)
      ? `${Math.max(0, summary.matched_count - summary.company_search_matched_count).toLocaleString()} ${locale === "en" ? "confirmed from existing CNPJ or website" : "confirmados por CNPJ já informado ou site"}`
      : null,
    summary.company_search_matched_count
      ? `${summary.company_search_matched_count.toLocaleString()} ${locale === "en" ? "found through registry search" : "encontrados via busca cadastral"}`
      : null,
    summary.company_search_needs_review_count
      ? `${summary.company_search_needs_review_count.toLocaleString()} ${locale === "en" ? "registry candidates need review" : "candidatos da busca cadastral precisam revisão"}`
      : null,
  ].filter(Boolean);

  const paidSearchSuffix = paidSearchParts.length ? ` ${paidSearchParts.join(", ")}.` : "";
  return locale === "en"
    ? `${summary.matched_count.toLocaleString()} filled automatically, ${summary.needs_review_count.toLocaleString()} candidates need review, ${summary.skipped_known_count.toLocaleString()} already had CNPJ, and ${summary.not_found_count.toLocaleString()} stayed unmatched.${paidSearchSuffix}`
    : `${summary.matched_count.toLocaleString()} preenchidos automaticamente, ${summary.needs_review_count.toLocaleString()} candidatos encontrados precisam revisão, ${summary.skipped_known_count.toLocaleString()} já tinham CNPJ e ${summary.not_found_count.toLocaleString()} ficaram sem correspondência.${paidSearchSuffix}`;
}

function buildCnpjNarrativeV2(summary: LeadBatchCNPJEnrichmentResponse["summary"], locale: Locale) {
  const baseNarrative = buildCnpjNarrative(summary, locale);
  const extras = [
    summary.skipped_review_candidate_count
      ? `${summary.skipped_review_candidate_count.toLocaleString()} ${locale === "en" ? "candidates waiting for review" : "candidatos aguardando revisão"}`
      : null,
    summary.paid_search_recently_attempted_count
      ? `${summary.paid_search_recently_attempted_count.toLocaleString()} ${locale === "en" ? "paid searches skipped because of recent attempts" : "buscas pagas puladas por tentativa recente"}`
      : null,
    summary.company_search_consulted_now_count
      ? `${summary.company_search_consulted_now_count.toLocaleString()} ${locale === "en" ? "checked now" : "consultados agora"}`
      : null,
    summary.paid_calls_made ? `${summary.paid_calls_made.toLocaleString()} ${locale === "en" ? "paid calls made" : "consultas pagas feitas"}` : null,
    summary.paid_calls_skipped_duplicate
      ? `${summary.paid_calls_skipped_duplicate.toLocaleString()} ${locale === "en" ? "duplicate calls avoided" : "consultas duplicadas evitadas"}`
      : null,
  ].filter(Boolean);

  if (extras.length === 0) {
    return baseNarrative;
  }

  return `${baseNarrative} ${extras.join(", ")}.`;
}

function formatScopeLabel(scopeLabel: string, locale: Locale) {
  if (locale === "en") {
    return scopeLabel
      .replace(/^Leads selecionados$/i, "Selected leads")
      .replace(/^Lista filtrada(?: atual)?$/i, "Current filtered set")
      .replace(/^Última importação$/i, "Latest import batch")
      .replace(/^Última importação #/i, "Latest import batch #");
  }

  return scopeLabel
    .replace(/^Selected leads$/i, "Leads selecionados")
    .replace(/^Current filtered set$/i, "Lista filtrada")
    .replace(/^Latest import batch$/i, "Última importação")
    .replace(/^Latest import batch #/i, "Última importação #");
}

function batchCopy(locale: Locale) {
  return locale === "en"
    ? {
        enrichDone: "Enrichment completed",
        enrichDoneWithWarnings: "Enrichment completed with warnings",
        cnpjDone: "CNPJ enrichment completed",
        cnpjDoneWithWarnings: "CNPJ enrichment completed with warnings",
        assignmentDone: "Assignment completed",
        spreadsheetDownloaded: "Spreadsheet downloaded",
        requested: "Requested",
        processed: "Processed",
        completed: "Completed",
        newContacts: "New contacts",
        publicChannels: "Public channels",
        forms: "Forms",
        skipped: "Skipped",
        errors: "Errors",
        filled: "Filled",
        needsReview: "Need review",
        notFound: "No match",
        alreadyHadCnpj: "Already had CNPJ",
        waitingReview: "Waiting review",
        recentPaidSearch: "Recent paid search",
        checkedNow: "Checked now",
        paidCalls: "Paid calls",
        duplicateCallsSkipped: "Duplicate calls skipped",
        batchErrors: "Batch errors",
        cnpjPartialFailure: "CNPJ enrichment failed for part of the batch.",
        updated: "Updated",
        missingIds: "Missing IDs",
        exportReady: "Export ready for prospecting. The Excel file has already been downloaded in your browser.",
        file: "File",
        failedLeads: "Failed leads",
        failedWithoutIds: "Some leads failed, but the API did not return their IDs.",
        enrichPartialFailure: "Failed to enrich part of the batch.",
      }
    : {
        enrichDone: "Enriquecimento concluído",
        enrichDoneWithWarnings: "Enriquecimento concluído com alertas",
        cnpjDone: "Enriquecimento CNPJ concluído",
        cnpjDoneWithWarnings: "Enriquecimento CNPJ concluído com alertas",
        assignmentDone: "Atribuição concluída",
        spreadsheetDownloaded: "Planilha baixada",
        requested: "Solicitados",
        processed: "Processados",
        completed: "Concluídos",
        newContacts: "Novos contatos",
        publicChannels: "Canais públicos",
        forms: "Formulários",
        skipped: "Ignorados",
        errors: "Erros",
        filled: "Preenchidos",
        needsReview: "Precisam revisão",
        notFound: "Sem correspondência",
        alreadyHadCnpj: "Já tinham CNPJ",
        waitingReview: "Aguardando revisão",
        recentPaidSearch: "Busca paga recente",
        checkedNow: "Consultados agora",
        paidCalls: "Consultas pagas",
        duplicateCallsSkipped: "Duplicadas evitadas",
        batchErrors: "Erros do lote",
        cnpjPartialFailure: "Falha ao enriquecer CNPJ em parte do lote.",
        updated: "Atualizados",
        missingIds: "IDs ausentes",
        exportReady: "Exportação pronta para prospecção. O arquivo Excel já foi baixado no seu navegador.",
        file: "Arquivo",
        failedLeads: "Leads com falha",
        failedWithoutIds: "Alguns leads falharam, mas a API não retornou os IDs.",
        enrichPartialFailure: "Falha ao enriquecer parte do lote.",
      };
}
