"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  assignLeadBatch,
  enrichLeadBatch,
  exportExcelForScope,
  getLatestImportBatch,
  resolveLeadScope,
} from "@/lib/api/leads";
import type {
  LeadBatchAssignmentResponse,
  LeadBatchEnrichmentResponse,
  LeadListParams,
  LeadScopeRequest,
} from "@/lib/api/types";

type ActionScope = "selected" | "current" | "latest";
type ActionKind = "enrich" | "assign" | "export";
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
          throw new Error("No leads were found for this scope.");
        }
        const response = await enrichLeadBatch(resolvedScope.leadIds);
        return {
          kind,
          scopeLabel: resolvedScope.scopeLabel,
          requested: resolvedScope.requested,
          summary: response.summary,
        } satisfies ActionResult;
      }

      if (kind === "assign") {
        if (scopeAtClick === "latest") {
          throw new Error("Assignment is available for selected leads or the current filtered set.");
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
        throw new Error("No leads were found for this scope.");
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
          <p className="text-xs font-semibold uppercase text-cyan-700">Batch actions</p>
          <h2 className="mt-1 text-base font-semibold text-neutral-950">Run operator actions</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Choose a scope, then enrich, assign, or export without leaving the queue.
          </p>
          {searchActive ? (
            <p className="mt-2 text-xs text-neutral-500">
              Search is local to the loaded table. Current filtered set uses the filters above.
            </p>
          ) : null}
        </div>

        <div className="grid gap-3 lg:grid-cols-[220px_150px_minmax(0,1fr)] xl:min-w-[780px]">
          <label className="block">
            <span className="text-xs font-medium text-neutral-600">Scope</span>
            <select
              value={scope}
              onChange={(event) => {
                setScope(event.target.value as ActionScope);
                setLastResult(null);
              }}
              className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-2 py-2 text-sm text-neutral-950"
            >
              <option value="selected">Selected leads ({selectedLeadIds.length})</option>
              <option value="current">Current filtered set ({currentTotal})</option>
              <option value="latest">Latest import batch{latestBatchQuery.data ? ` (${latestBatchQuery.data.lead_count})` : ""}</option>
            </select>
          </label>

          <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2">
            <p className="text-xs font-medium text-neutral-500">Action count</p>
            <p className="mt-1 text-xl font-semibold text-neutral-950">
              {actionCount === null ? "..." : actionCount.toLocaleString()}
            </p>
          </div>

          <div className="grid gap-2 sm:grid-cols-3">
            <ActionButton disabled={scopedActionDisabled} onClick={() => requestAction("enrich")}>
              Enrich
            </ActionButton>
            <ActionButton disabled={assignDisabled} onClick={() => requestAction("assign")}>
              Assign
            </ActionButton>
            <ActionButton disabled={scopedActionDisabled} onClick={() => requestAction("export")}>
              Export
            </ActionButton>
          </div>
        </div>
      </div>

      {selectedDisabled ? (
        <p className="mt-3 rounded-md bg-neutral-50 px-3 py-2 text-sm text-neutral-600">
          Select one or more rows to run actions on selected leads, or choose Current filtered set deliberately.
        </p>
      ) : null}

      {scope === "latest" ? (
        <p className="mt-3 rounded-md bg-neutral-50 px-3 py-2 text-sm text-neutral-600">
          Latest import batch is available for enrichment and export. Assignment stays scoped to selected/current leads.
          {latestBatchQuery.isLoading ? " Loading latest batch count." : ""}
          {latestBatchQuery.isError ? " Latest batch count is unavailable." : ""}
        </p>
      ) : null}

      {confirmation ? (
        <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3">
          <p className="text-sm font-semibold text-amber-950">
            You are about to {confirmation.label.toLowerCase()} {confirmation.count.toLocaleString()} leads.
          </p>
          <p className="mt-1 text-sm text-amber-900">
            Confirm this broad {confirmation.scope === "latest" ? "latest-batch" : "filtered-set"} action before it runs.
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
              Confirm {confirmation.label}
            </button>
            <button
              type="button"
              onClick={() => setConfirmation(null)}
              className="rounded-md border border-amber-300 bg-white px-3 py-2 text-sm font-medium text-amber-950"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : null}

      {actionMutation.isPending ? (
        <p className="mt-3 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm text-cyan-800">
          Running action. Larger enrichment scopes can take a moment.
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
      <ResultBox title={`${hasErrors ? "Enrichment finished with errors" : "Enrichment complete"} - ${result.scopeLabel}`}>
        <ResultNarrative text={buildEnrichmentNarrative(result.summary)} />
        <ResultMetric label="Requested" value={result.requested} />
        <ResultMetric label="Processed" value={result.summary.processed} />
        <ResultMetric label="Successful runs" value={result.summary.success_count} />
        <ResultMetric label="New contacts found" value={result.summary.contacts_added} />
        <ResultMetric label="Public channels" value={newPublicChannelCount} />
        <ResultMetric label="Emails" value={result.summary.emails_found} />
        <ResultMetric label="Instagrams" value={result.summary.instagrams_found} />
        <ResultMetric label="WhatsApps" value={result.summary.whatsapps_found} />
        <ResultMetric label="Forms" value={result.summary.contact_forms_found} />
        <ResultMetric label="Skipped" value={result.summary.skipped} />
        <ResultMetric label="Errors" value={result.summary.errors} />
        {hasErrors ? <FailedLeadSummary summary={result.summary} /> : null}
      </ResultBox>
    );
  }

  if (result.kind === "assign") {
    return (
      <ResultBox title={`Assignment complete - ${result.scopeLabel}`}>
        <ResultMetric label="Requested" value={result.requested} />
        <ResultMetric label="Processed" value={result.summary.processed} />
        <ResultMetric label="Changed" value={result.summary.changed} />
        <ResultMetric label="Missing IDs" value={result.summary.missing_lead_ids.length} />
      </ResultBox>
    );
  }

  return (
    <ResultBox title={`Export ready - ${result.scopeLabel}`}>
      <ResultMetric label="Leads" value={result.requested} />
      <div className="rounded-md border border-neutral-200 bg-white px-3 py-2">
        <p className="text-xs font-medium text-neutral-500">File</p>
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
      <p className="text-xs font-semibold uppercase text-amber-900">Failed leads</p>
      <p className="mt-1 text-sm text-amber-950">
        {summary.failed_lead_ids.length
          ? `IDs: ${summary.failed_lead_ids.join(", ")}`
          : "Some leads failed, but the backend did not return lead IDs."}
      </p>
      {summary.error_messages.length ? (
        <ul className="mt-2 space-y-1 text-sm text-amber-900">
          {summary.error_messages.slice(0, 3).map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function buildScopeRequest(scope: ActionScope, selectedLeadIds: number[], currentFilters: LeadListParams): LeadScopeRequest {
  if (scope === "selected") {
    if (selectedLeadIds.length === 0) {
      throw new Error("Select at least one lead first.");
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
    return "Enrich";
  }
  if (kind === "assign") {
    return "Assign";
  }
  return "Export";
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

function formatError(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }

  if (error instanceof Error) {
    return error.message;
  }

  return "The action could not be completed.";
}

function buildEnrichmentNarrative(summary: LeadBatchEnrichmentResponse["summary"]) {
  const newPublicChannelCount =
    summary.emails_found +
    summary.instagrams_found +
    summary.whatsapps_found +
    summary.contact_forms_found;

  if (summary.success_count === 0) {
    return `Processed ${summary.processed.toLocaleString()} leads, but none completed enrichment successfully.`;
  }

  if (newPublicChannelCount === 0) {
    return `Processed ${summary.processed.toLocaleString()} leads. ${summary.success_count.toLocaleString()} completed successfully, but no additional public contact channels were found.`;
  }

  return `Processed ${summary.processed.toLocaleString()} leads and found ${summary.contacts_added.toLocaleString()} new contact records across ${newPublicChannelCount.toLocaleString()} public contact channels.`;
}
