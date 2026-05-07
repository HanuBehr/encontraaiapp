"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

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
}: LeadBatchActionsProps) {
  const queryClient = useQueryClient();
  const [scope, setScope] = useState<ActionScope>("selected");
  const [lastResult, setLastResult] = useState<ActionResult | null>(null);
  const [confirmation, setConfirmation] = useState<ConfirmationState | null>(null);
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
    queryKey: ["latest-import-batch"],
    queryFn: getLatestImportBatch,
    enabled: scope === "latest",
    retry: 1,
  });

  const actionMutation = useMutation({
    mutationFn: async ({ kind, scope: scopeAtClick }: ActionMutationInput) => {
      const resolvedScope = await resolveActionScope(scopeAtClick, selectedLeadIds, currentFilters);

      if (kind === "enrich") {
        if (resolvedScope.leadIds.length === 0) {
          throw new Error("Nenhum lead encontrado nesse escopo.");
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
        if (resolvedScope.leadIds.length === 0) {
          throw new Error("Nenhum lead encontrado nesse escopo.");
        }
        const response = await enrichLeadBatchCnpj(resolvedScope.leadIds);
        return {
          kind,
          scopeLabel: resolvedScope.scopeLabel,
          requested: resolvedScope.requested,
          summary: response.summary,
        } satisfies ActionResult;
      }

      if (kind === "assign") {
        if (scopeAtClick === "latest") {
          throw new Error("A atribuição está disponível apenas para leads selecionados ou para a lista filtrada.");
        }
        const response = await assignLeadBatch(resolvedScope.request);
        return {
          kind,
          scopeLabel: response.summary.scope_label,
          requested: response.summary.requested,
          summary: response.summary,
        } satisfies ActionResult;
      }

      if (resolvedScope.leadIds.length === 0) {
        throw new Error("Nenhum lead encontrado nesse escopo.");
      }
      const exported = await exportExcelForScope(resolvedScope.request);
      downloadBlob(exported.blob, exported.filename);
      return {
        kind,
        scopeLabel: resolvedScope.scopeLabel,
        requested: resolvedScope.requested,
        filename: exported.filename,
      } satisfies ActionResult;
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
  const latestDisabled = scope === "latest" && (latestBatchQuery.isLoading || latestBatchQuery.isError);
  const assignDisabled = actionMutation.isPending || selectedDisabled || currentDisabled || latestDisabled || scope === "latest";
  const scopedActionDisabled = actionMutation.isPending || selectedDisabled || currentDisabled || latestDisabled;

  return (
    <section className="rounded-md border border-neutral-200 bg-white p-4">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-cyan-700">Ações em lote</p>
          <h2 className="mt-1 text-base font-semibold text-neutral-950">Enriquecer, revisar e exportar</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Escolha um escopo para enriquecer contatos, consultar CNPJ, atribuir ou exportar os leads sem sair da lista.
          </p>
          <p className="mt-1 text-xs text-neutral-500">
            Busca CNPJ já informado, tenta encontrar CNPJ no site da empresa e, se configurado, usa busca cadastral paga.
          </p>
          <p className="mt-1 text-xs text-neutral-500">
            O Excel é o formato principal para baixar uma planilha limpa e pronta para prospecção.
          </p>
          {searchActive ? (
            <p className="mt-2 text-xs text-neutral-500">
              A busca rápida atua só sobre a tabela carregada. A lista filtrada usa os filtros acima.
            </p>
          ) : null}
        </div>

        <div className="grid gap-3 lg:grid-cols-[220px_150px_minmax(0,1fr)] xl:min-w-[780px]">
          <label className="block">
            <span className="text-xs font-medium text-neutral-600">Escopo</span>
            <select
              value={scope}
              onChange={(event) => {
                setScope(event.target.value as ActionScope);
                setLastResult(null);
              }}
              className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-2 py-2 text-sm text-neutral-950"
            >
              <option value="selected">Leads selecionados ({selectedLeadIds.length})</option>
              <option value="current">Lista filtrada ({currentTotal})</option>
              <option value="latest">
                Última importação{latestBatchQuery.data ? ` (${latestBatchQuery.data.lead_count})` : ""}
              </option>
            </select>
          </label>

          <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2">
            <p className="text-xs font-medium text-neutral-500">Total no escopo</p>
            <p className="mt-1 text-xl font-semibold text-neutral-950">
              {actionCount === null ? "..." : actionCount.toLocaleString()}
            </p>
          </div>

          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <ActionButton disabled={scopedActionDisabled} onClick={() => requestAction("enrich")}>
              Enriquecer
            </ActionButton>
            <ActionButton disabled={scopedActionDisabled} onClick={() => requestAction("cnpj")}>
              Enriquecer CNPJ
            </ActionButton>
            <ActionButton disabled={assignDisabled} onClick={() => requestAction("assign")}>
              Atribuir
            </ActionButton>
            <ActionButton disabled={scopedActionDisabled} onClick={() => requestAction("export")}>
              Exportar Excel
            </ActionButton>
          </div>
        </div>
      </div>

      {selectedDisabled ? (
        <p className="mt-3 rounded-md bg-neutral-50 px-3 py-2 text-sm text-neutral-600">
          Selecione um ou mais leads para agir sobre os itens marcados ou mude o escopo para a lista filtrada.
        </p>
      ) : null}

      {scope === "latest" ? (
        <p className="mt-3 rounded-md bg-neutral-50 px-3 py-2 text-sm text-neutral-600">
          A última importação pode ser enriquecida e exportada. A atribuição continua restrita aos leads selecionados
          ou à lista filtrada.
          {latestBatchQuery.isLoading ? " Carregando a contagem do lote." : ""}
          {latestBatchQuery.isError ? " Não foi possível carregar a contagem do lote." : ""}
        </p>
      ) : null}

      {confirmation ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-amber-950">
            Você está prestes a {confirmation.label.toLowerCase()} {confirmation.count.toLocaleString()} leads.
          </p>
          <p className="mt-1 text-sm text-amber-900">
            Confirme esta ação em massa antes de continuar.
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
              Confirmar {confirmation.label.toLowerCase()}
            </button>
            <button
              type="button"
              onClick={() => setConfirmation(null)}
              className="rounded-md border border-amber-300 bg-white px-3 py-2 text-sm font-medium text-amber-950"
            >
              Cancelar
            </button>
          </div>
        </div>
      ) : null}

      {actionMutation.isPending ? (
        <p className="mt-3 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm text-cyan-800">
          Processando sua ação. Escopos maiores podem levar alguns instantes.
        </p>
      ) : null}

      {actionMutation.isError ? (
        <p className="mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">
          {formatError(actionMutation.error)}
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
        label: actionLabel(kind),
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
      className="rounded-md border border-neutral-900 bg-neutral-950 px-3 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:border-neutral-200 disabled:bg-neutral-100 disabled:text-neutral-400"
    >
      {children}
    </button>
  );
}

function ActionResultSummary({ result }: { result: ActionResult }) {
  if (result.kind === "enrich") {
    const hasErrors = result.summary.errors > 0;
    const newPublicChannelCount =
      result.summary.emails_found +
      result.summary.instagrams_found +
      result.summary.whatsapps_found +
      result.summary.contact_forms_found;
    return (
      <ResultBox
        title={`${hasErrors ? "Enriquecimento concluído com alertas" : "Enriquecimento concluído"} - ${formatScopeLabel(result.scopeLabel)}`}
      >
        <ResultNarrative text={buildEnrichmentNarrative(result.summary)} />
        <ResultMetric label="Solicitados" value={result.requested} />
        <ResultMetric label="Processados" value={result.summary.processed} />
        <ResultMetric label="Concluídos" value={result.summary.success_count} />
        <ResultMetric label="Novos contatos" value={result.summary.contacts_added} />
        <ResultMetric label="Canais públicos" value={newPublicChannelCount} />
        <ResultMetric label="Emails" value={result.summary.emails_found} />
        <ResultMetric label="Instagrams" value={result.summary.instagrams_found} />
        <ResultMetric label="WhatsApps" value={result.summary.whatsapps_found} />
        <ResultMetric label="Formulários" value={result.summary.contact_forms_found} />
        <ResultMetric label="Ignorados" value={result.summary.skipped} />
        <ResultMetric label="Erros" value={result.summary.errors} />
        {hasErrors ? <FailedLeadSummary summary={result.summary} /> : null}
      </ResultBox>
    );
  }

  if (result.kind === "cnpj") {
    const hasErrors = result.summary.error_count > 0;
    return (
      <ResultBox
        title={`${hasErrors ? "Enriquecimento CNPJ concluído com alertas" : "Enriquecimento CNPJ concluído"} - ${formatScopeLabel(result.scopeLabel)}`}
      >
        <ResultNarrative text={buildCnpjNarrativeV2(result.summary)} />
        <ResultMetric label="Solicitados" value={result.requested} />
        <ResultMetric label="Processados" value={result.summary.processed} />
        <ResultMetric label="Preenchidos" value={result.summary.matched_count} />
        <ResultMetric label="Precisam revisão" value={result.summary.needs_review_count} />
        <ResultMetric label="Sem correspondência" value={result.summary.not_found_count} />
        <ResultMetric label="Já tinham CNPJ" value={result.summary.skipped_known_count} />
        <ResultMetric label="Aguardando revisão" value={result.summary.skipped_review_candidate_count} />
        <ResultMetric label="Busca paga recente" value={result.summary.paid_search_recently_attempted_count} />
        <ResultMetric label="Consultados agora" value={result.summary.company_search_consulted_now_count} />
        <ResultMetric label="Erros" value={result.summary.error_count} />
        {hasErrors ? (
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 sm:col-span-2 lg:col-span-4">
            <p className="text-xs font-semibold uppercase text-amber-900">Erros do lote</p>
            <ul className="mt-2 space-y-1 text-sm text-amber-900">
              {result.summary.errors.slice(0, 3).map((message) => (
                <li key={message}>{sanitizeUserFacingMessage(message, "Falha ao enriquecer CNPJ em parte do lote.")}</li>
              ))}
            </ul>
          </div>
        ) : null}
      </ResultBox>
    );
  }

  if (result.kind === "assign") {
    return (
      <ResultBox title={`Atribuição concluída - ${formatScopeLabel(result.scopeLabel)}`}>
        <ResultMetric label="Solicitados" value={result.requested} />
        <ResultMetric label="Processados" value={result.summary.processed} />
        <ResultMetric label="Atualizados" value={result.summary.changed} />
        <ResultMetric label="IDs ausentes" value={result.summary.missing_lead_ids.length} />
      </ResultBox>
    );
  }

  return (
    <ResultBox title={`Planilha baixada - ${formatScopeLabel(result.scopeLabel)}`}>
      <ResultNarrative text="Exportação pronta para prospecção. O arquivo Excel já foi baixado no seu navegador." />
      <ResultMetric label="Leads" value={result.requested} />
      <div className="rounded-md border border-neutral-200 bg-white px-3 py-2">
        <p className="text-xs font-medium text-neutral-500">Arquivo</p>
        <p className="mt-1 break-all text-sm font-semibold text-neutral-950">{result.filename}</p>
      </div>
    </ResultBox>
  );
}

function ResultBox({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mt-3 rounded-md border border-emerald-200 bg-emerald-50 p-3">
      <p className="text-sm font-semibold text-emerald-900">{title}</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">{children}</div>
    </div>
  );
}

function ResultNarrative({ text }: { text: string }) {
  return (
    <div className="rounded-md border border-emerald-100 bg-white px-3 py-2 text-sm text-neutral-800 sm:col-span-2 lg:col-span-4">
      {text}
    </div>
  );
}

function ResultMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border border-emerald-100 bg-white px-3 py-2">
      <p className="text-xs font-medium text-neutral-500">{label}</p>
      <p className="mt-1 text-base font-semibold text-neutral-950">{value.toLocaleString()}</p>
    </div>
  );
}

function FailedLeadSummary({ summary }: { summary: LeadBatchEnrichmentResponse["summary"] }) {
  return (
    <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 sm:col-span-2 lg:col-span-4">
      <p className="text-xs font-semibold uppercase text-amber-900">Leads com falha</p>
      <p className="mt-1 text-sm text-amber-950">
        {summary.failed_lead_ids.length
          ? `IDs: ${summary.failed_lead_ids.join(", ")}`
          : "Alguns leads falharam, mas a API não retornou os IDs."}
      </p>
      {summary.error_messages.length ? (
        <ul className="mt-2 space-y-1 text-sm text-amber-900">
          {summary.error_messages.slice(0, 3).map((message) => (
            <li key={message}>{sanitizeUserFacingMessage(message, "Falha ao enriquecer parte do lote.")}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function buildScopeRequest(scope: ActionScope, selectedLeadIds: number[], currentFilters: LeadListParams): LeadScopeRequest {
  if (scope === "selected") {
    if (selectedLeadIds.length === 0) {
      throw new Error("Selecione pelo menos um lead.");
    }
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

function actionLabel(kind: ActionKind) {
  if (kind === "enrich") {
    return "Enriquecer";
  }
  if (kind === "cnpj") {
    return "Enriquecer CNPJ";
  }
  if (kind === "assign") {
    return "Atribuir";
  }
  return "Exportar";
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
      scopeLabel: resolved.scope_label || `Última importação #${latestBatch.id}`,
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

function formatError(error: unknown) {
  return formatUserFacingError(error, "Não foi possível concluir a ação em lote.");
}

function buildEnrichmentNarrative(summary: LeadBatchEnrichmentResponse["summary"]) {
  const newPublicChannelCount =
    summary.emails_found +
    summary.instagrams_found +
    summary.whatsapps_found +
    summary.contact_forms_found;

  if (summary.success_count === 0) {
    return `Processamos ${summary.processed.toLocaleString()} leads, mas nenhum concluiu o enriquecimento com sucesso.`;
  }

  if (newPublicChannelCount === 0) {
    return `Processamos ${summary.processed.toLocaleString()} leads. ${summary.success_count.toLocaleString()} concluíram com sucesso, mas nenhum novo canal público foi encontrado.`;
  }

  return `Processamos ${summary.processed.toLocaleString()} leads e encontramos ${summary.contacts_added.toLocaleString()} novos contatos em ${newPublicChannelCount.toLocaleString()} canais públicos.`;
}

function buildCnpjNarrative(summary: LeadBatchCNPJEnrichmentResponse["summary"]) {
  if (summary.processed === 0) {
    return "Nenhum lead foi processado nesta consulta de CNPJ.";
  }

  if (
    summary.matched_count === 0 &&
    summary.needs_review_count === 0 &&
    summary.not_found_count === 0 &&
    summary.company_search_pending_retry_count > 0
  ) {
    return `Busca CNPJ limitada pelo provedor. ${summary.company_search_pending_retry_count.toLocaleString()} empresa(s) ficaram para tentar novamente em cerca de 1 minuto.`;
  }

  if (summary.error_count > 0 && summary.matched_count === 0 && summary.needs_review_count === 0 && summary.not_found_count === 0) {
    if (summary.provider_rate_limited_count > 0) {
      return "A consulta pública de CNPJ atingiu o limite de uso. Tente novamente com menos empresas por vez.";
    }
    if (summary.company_search_rate_limited_count > 0) {
      return "A busca cadastral paga atingiu o limite do provedor. Tente novamente em alguns instantes.";
    }
    if (summary.company_search_pending_retry_count > 0) {
      return "Busca CNPJ limitada pelo provedor. Aguarde cerca de 1 minuto e tente novamente.";
    }
    return "A consulta CNPJ encontrou erro de provedor em parte do lote. Tente novamente em alguns instantes.";
  }

  if (summary.matched_count === 0 && summary.needs_review_count === 0 && summary.not_found_count > 0) {
    const genericCompanySearchNoCandidateCount = Math.max(
      0,
      summary.company_search_no_candidates_count - summary.company_search_zero_candidates_count,
    );
    const reasons = [
      summary.no_website_count ? `${summary.no_website_count.toLocaleString()} sem site` : null,
      summary.no_cnpj_on_website_count
        ? `${summary.no_cnpj_on_website_count.toLocaleString()} sem CNPJ visível no site`
        : null,
      summary.website_timeout_count
        ? `${summary.website_timeout_count.toLocaleString()} sites demoraram demais`
        : null,
      summary.website_unreachable_count
        ? `${summary.website_unreachable_count.toLocaleString()} sites sem resposta`
        : null,
      summary.validation_failed_count
        ? `${summary.validation_failed_count.toLocaleString()} com CNPJ sem validação pública`
        : null,
      summary.low_confidence_count
        ? `${summary.low_confidence_count.toLocaleString()} com baixa confiança`
        : null,
      summary.provider_rate_limited_count
        ? `${summary.provider_rate_limited_count.toLocaleString()} limitados pela consulta pública`
        : null,
      summary.provider_error_count
        ? `${summary.provider_error_count.toLocaleString()} com erro de provedor`
        : null,
      summary.company_search_not_configured_count
        ? `${summary.company_search_not_configured_count.toLocaleString()} com busca paga não configurada`
        : null,
      summary.company_search_zero_candidates_count
        ? `${summary.company_search_zero_candidates_count.toLocaleString()} sem candidatos retornados pela CNPJá`
        : null,
      genericCompanySearchNoCandidateCount
        ? `${genericCompanySearchNoCandidateCount.toLocaleString()} sem candidatos na busca cadastral`
        : null,
      summary.company_search_low_confidence_count
        ? `${summary.company_search_low_confidence_count.toLocaleString()} com baixa confiança na busca cadastral`
        : null,
      summary.company_search_pending_retry_count
        ? `${summary.company_search_pending_retry_count.toLocaleString()} aguardando nova tentativa por limite do provedor`
        : null,
      summary.company_search_rate_limited_count
        ? `${summary.company_search_rate_limited_count.toLocaleString()} limitados pela busca cadastral`
        : null,
      summary.company_search_provider_error_count
        ? `${summary.company_search_provider_error_count.toLocaleString()} com erro na busca cadastral`
        : null,
    ].filter(Boolean);

    if (reasons.length === 0) {
      return "0 CNPJs confirmados. Nenhum CNPJ foi encontrado nos sites verificados.";
    }

    return `0 CNPJs confirmados. ${summary.not_found_count.toLocaleString()} sem correspondência: ${reasons.join(", ")}.`;
  }

  const paidSearchParts = [
    Math.max(0, summary.matched_count - summary.company_search_matched_count)
      ? `${Math.max(0, summary.matched_count - summary.company_search_matched_count).toLocaleString()} confirmados por CNPJ já informado ou site`
      : null,
    summary.company_search_matched_count
      ? `${summary.company_search_matched_count.toLocaleString()} encontrados via busca cadastral`
      : null,
    summary.company_search_needs_review_count
      ? `${summary.company_search_needs_review_count.toLocaleString()} candidatos da busca cadastral precisam revisão`
      : null,
  ].filter(Boolean);

  const paidSearchSuffix = paidSearchParts.length ? ` ${paidSearchParts.join(", ")}.` : "";
  return `${summary.matched_count.toLocaleString()} preenchidos automaticamente, ${summary.needs_review_count.toLocaleString()} candidatos encontrados precisam revisão, ${summary.skipped_known_count.toLocaleString()} já tinham CNPJ e ${summary.not_found_count.toLocaleString()} ficaram sem correspondência.${paidSearchSuffix}`;
}

function buildCnpjNarrativeV2(summary: LeadBatchCNPJEnrichmentResponse["summary"]) {
  const baseNarrative = buildCnpjNarrative(summary);
  const extras = [
    summary.skipped_review_candidate_count
      ? `${summary.skipped_review_candidate_count.toLocaleString()} candidatos aguardando revisão`
      : null,
    summary.paid_search_recently_attempted_count
      ? `${summary.paid_search_recently_attempted_count.toLocaleString()} buscas pagas puladas por tentativa recente`
      : null,
    summary.company_search_consulted_now_count
      ? `${summary.company_search_consulted_now_count.toLocaleString()} consultados agora`
      : null,
  ].filter(Boolean);

  if (extras.length === 0) {
    return baseNarrative;
  }

  return `${baseNarrative} ${extras.join(", ")}.`;
}

function formatScopeLabel(scopeLabel: string) {
  return scopeLabel
    .replace(/^Selected leads$/i, "Leads selecionados")
    .replace(/^Current filtered set$/i, "Lista filtrada")
    .replace(/^Latest import batch$/i, "Última importação")
    .replace(/^Latest import batch #/i, "Última importação #");
}
