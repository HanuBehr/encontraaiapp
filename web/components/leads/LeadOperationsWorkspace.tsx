"use client";

import { useQuery } from "@tanstack/react-query";
import type { RowSelectionState, SortingState } from "@tanstack/react-table";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useDeferredValue, useMemo, useState } from "react";

import { LeadQueueFilters } from "@/components/leads/LeadQueueFilters";
import { LeadQueueTable } from "@/components/leads/LeadQueueTable";
import { getLeadOptions, listLeads } from "@/lib/api/leads";
import { getSettingsSummary } from "@/lib/api/settings";
import type { LeadListParams, LeadSortBy } from "@/lib/api/types";
import {
  booleanFilterValue,
  defaultQueueFilters,
  numericFilterValue,
  type QueueFilters,
} from "@/lib/state/lead-workspace";
import { useI18n } from "@/lib/i18n/client";
import { formatUserFacingError } from "@/lib/ui/messages";
import type { TranslationKey } from "@/lib/i18n/translations";

const LeadBatchActions = dynamic(
  () => import("@/components/leads/LeadBatchActions").then((module) => module.LeadBatchActions),
  { loading: () => <DeferredPanel labelKey="common.loadingActions" /> },
);
const LeadCnpjReviewQueue = dynamic(
  () => import("@/components/leads/LeadCnpjReviewQueue").then((module) => module.LeadCnpjReviewQueue),
  { loading: () => <DeferredPanel labelKey="common.loadingCnpjReview" /> },
);
const LeadDetailPanel = dynamic(
  () => import("@/components/leads/LeadDetailPanel").then((module) => module.LeadDetailPanel),
  { loading: () => <DeferredPanel labelKey="common.loadingDetailsPanel" /> },
);

type LeadOperationsWorkspaceProps = {
  initialImportBatchId?: number | null;
};

export function LeadOperationsWorkspace({ initialImportBatchId = null }: LeadOperationsWorkspaceProps) {
  const { locale, t } = useI18n();
  const searchParams = useSearchParams();
  const importBatchId = initialImportBatchId ?? parsePositiveInteger(searchParams.get("import_batch_id"));
  const [filters, setFilters] = useState<QueueFilters>(defaultQueueFilters);
  const [search, setSearch] = useState("");
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sorting, setSorting] = useState<SortingState>([{ id: "updated_at", desc: true }]);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [activeLeadId, setActiveLeadId] = useState<number | null>(null);
  const deferredSearch = useDeferredValue(search);

  const optionsQuery = useQuery({
    queryKey: ["lead-options"],
    queryFn: getLeadOptions,
  });
  const settingsQuery = useQuery({
    queryKey: ["settings-summary"],
    queryFn: getSettingsSummary,
  });

  const queryParams = useMemo<LeadListParams>(() => {
    const sort = sorting[0];
    const sortBy = (sort?.id as LeadSortBy | undefined) ?? "updated_at";
    const sortDir = sort ? (sort.desc ? "desc" : "asc") : "desc";
    const searchTerm = deferredSearch.trim();

    return {
      search: searchTerm || undefined,
      city: filters.city || undefined,
      state: filters.state || undefined,
      status: filters.status || undefined,
      assigned_sales_rep_id: numericFilterValue(filters.assignedSalesRepId),
      sales_region_id: numericFilterValue(filters.salesRegionId),
      market_segment_id: numericFilterValue(filters.marketSegmentId),
      market_subsegment_id: numericFilterValue(filters.marketSubsegmentId),
      company_size_fit: filters.companySizeFit || undefined,
      trade_type: filters.tradeType || undefined,
      has_assignment: booleanFilterValue(filters.hasAssignment),
      has_email: booleanFilterValue(filters.hasEmail),
      has_whatsapp: booleanFilterValue(filters.hasWhatsapp),
      has_instagram: booleanFilterValue(filters.hasInstagram),
      import_batch_id: importBatchId ?? undefined,
      blocked: filters.blocked,
      sort_by: sortBy,
      sort_dir: sortDir,
      limit: pageSize,
      offset: pageIndex * pageSize,
    };
  }, [deferredSearch, filters, importBatchId, pageIndex, pageSize, sorting]);

  const leadsQuery = useQuery({
    queryKey: ["leads", queryParams],
    queryFn: () => listLeads(queryParams),
    placeholderData: (previousData) => previousData,
  });

  const searchTerm = deferredSearch.trim();
  const pageItems = leadsQuery.data?.items ?? [];
  const currentFilteredTotal = leadsQuery.data?.total ?? 0;
  const total = currentFilteredTotal;
  const selectedLeadIds = selectedLeadIdsFromSelection(rowSelection);
  const selectedLeadId = firstSelectedLeadId(rowSelection);
  const detailLeadId = activeLeadId ?? selectedLeadId;
  const showEmptyWorkspaceState =
    !importBatchId &&
    !searchTerm &&
    !leadsQuery.isLoading &&
    !leadsQuery.isError &&
    currentFilteredTotal === 0 &&
    !hasActiveQueueFilters(filters);
  const cnpjEnabled = Boolean(settingsQuery.data?.providers.cnpj_company_search_configured);

  function updateFilters(nextFilters: QueueFilters) {
    setFilters(nextFilters);
    setPageIndex(0);
  }

  function updateSearch(value: string) {
    setSearch(value);
    setPageIndex(0);
  }

  function updatePageSize(value: number) {
    setPageSize(value);
    setPageIndex(0);
  }

  function updateSorting(updater: SortingState | ((old: SortingState) => SortingState)) {
    setSorting((current) => (typeof updater === "function" ? updater(current) : updater));
    setPageIndex(0);
  }

  function resetFilters() {
    setFilters(defaultQueueFilters);
    setSearch("");
    setPageIndex(0);
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-1.5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="ea-kicker">{t("leads.kicker")}</p>
          <h1 className="mt-1 text-3xl font-bold tracking-[-0.045em] text-brand-graphite sm:text-[2.35rem]">{t("leads.title")}</h1>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-brand-muted">
            {t("leads.description")}
          </p>
        </div>
      </div>

      {importBatchId ? (
        <section className="flex flex-col gap-3 rounded-3xl border border-brand-olive/70 bg-brand-olive/20 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-brand-graphite">{t("leads.viewingBatch", { id: importBatchId })}</p>
            <p className="mt-1 text-sm text-brand-muted">{t("leads.batchDescription")}</p>
          </div>
          <Link
            href="/leads"
            className="ea-button-secondary px-3 py-2 text-center text-sm font-semibold"
          >
            {t("leads.viewAll")}
          </Link>
        </section>
      ) : null}

      <LeadQueueSearch
        value={search}
        onChange={updateSearch}
      />

      <LeadQueueFilters
        filters={filters}
        options={optionsQuery.data}
        onFiltersChange={updateFilters}
        onReset={resetFilters}
      />

      {optionsQuery.isError ? (
        <p className="rounded-2xl border border-rose-300/30 bg-rose-950/35 p-3 text-sm text-rose-100">
          {formatUserFacingError(optionsQuery.error, "Não foi possível carregar os filtros agora.", locale)}
        </p>
      ) : null}

      {leadsQuery.isError ? (
        <p className="rounded-2xl border border-rose-300/30 bg-rose-950/35 p-3 text-sm text-rose-100">
          {formatUserFacingError(leadsQuery.error, "Não foi possível carregar os leads agora.", locale)}
        </p>
      ) : null}

      {showEmptyWorkspaceState ? (
        <section className="ea-card border-dashed p-5">
          <p className="text-sm font-semibold text-brand-graphite">{t("leads.noSavedTitle")}</p>
          <p className="mt-2 text-sm text-brand-muted">{t("leads.noSavedDescription")}</p>
          <Link
            href="/discovery"
            className="ea-button-primary mt-4 inline-flex px-4 py-2 text-sm font-semibold"
          >
            {t("leads.goDiscovery")}
          </Link>
        </section>
      ) : null}

      <LeadBatchActions
        selectedLeadIds={selectedLeadIds}
        currentFilters={queryParams}
        currentTotal={currentFilteredTotal}
        searchActive={Boolean(searchTerm)}
        cnpjEnabled={cnpjEnabled}
      />

      {cnpjEnabled ? (
        <LeadCnpjReviewQueue
          currentFilters={queryParams}
          onActivateLead={setActiveLeadId}
          activeLeadId={detailLeadId}
        />
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_440px]">
        <LeadQueueTable
          leads={pageItems}
          total={total}
          pageIndex={pageIndex}
          pageSize={pageSize}
          sorting={sorting}
          rowSelection={rowSelection}
          activeLeadId={detailLeadId}
          isLoading={leadsQuery.isLoading}
          onSortingChange={updateSorting}
          onRowSelectionChange={setRowSelection}
          onActivateLead={setActiveLeadId}
          onPageChange={setPageIndex}
          onPageSizeChange={updatePageSize}
        />
        <LeadDetailPanel leadId={detailLeadId} />
      </div>
    </div>
  );
}

function DeferredPanel({ labelKey }: { labelKey: TranslationKey }) {
  const { t } = useI18n();
  return (
    <section className="ea-card p-5">
      <p className="text-sm text-brand-muted">{t(labelKey)}</p>
    </section>
  );
}

function LeadQueueSearch({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  const { t } = useI18n();
  return (
    <section className="ea-card p-4">
      <div className="max-w-3xl">
        <label className="block" htmlFor="lead-search">
          <span className="text-sm font-semibold text-brand-graphite">{t("leads.quickSearch")}</span>
          <input
            id="lead-search"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder={t("leads.searchPlaceholder")}
            autoComplete="off"
            className="ea-input mt-2 w-full px-3 py-2 text-sm"
          />
        </label>
      </div>
      <p className="mt-2 text-xs text-brand-muted">
        {t("leads.searchHelp")}
      </p>
    </section>
  );
}

function hasActiveQueueFilters(filters: QueueFilters) {
  return (
    filters.city !== defaultQueueFilters.city ||
    filters.state !== defaultQueueFilters.state ||
    filters.status !== defaultQueueFilters.status ||
    filters.assignedSalesRepId !== defaultQueueFilters.assignedSalesRepId ||
    filters.salesRegionId !== defaultQueueFilters.salesRegionId ||
    filters.marketSegmentId !== defaultQueueFilters.marketSegmentId ||
    filters.marketSubsegmentId !== defaultQueueFilters.marketSubsegmentId ||
    filters.companySizeFit !== defaultQueueFilters.companySizeFit ||
    filters.tradeType !== defaultQueueFilters.tradeType ||
    filters.hasAssignment !== defaultQueueFilters.hasAssignment ||
    filters.hasEmail !== defaultQueueFilters.hasEmail ||
    filters.hasWhatsapp !== defaultQueueFilters.hasWhatsapp ||
    filters.hasInstagram !== defaultQueueFilters.hasInstagram ||
    filters.blocked !== defaultQueueFilters.blocked
  );
}

function firstSelectedLeadId(rowSelection: RowSelectionState) {
  const selectedId = selectedLeadIdsFromSelection(rowSelection)[0];
  if (!selectedId) {
    return null;
  }
  return selectedId;
}

function selectedLeadIdsFromSelection(rowSelection: RowSelectionState) {
  return Object.entries(rowSelection)
    .filter(([, selected]) => selected)
    .map(([leadId]) => Number(leadId))
    .filter((leadId) => Number.isFinite(leadId));
}

function parsePositiveInteger(value: string | null) {
  if (!value) {
    return null;
  }
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}
