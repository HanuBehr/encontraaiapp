"use client";

import { useQuery } from "@tanstack/react-query";
import type { RowSelectionState, SortingState } from "@tanstack/react-table";
import Link from "next/link";
import { useMemo, useState } from "react";

import { LeadBatchActions } from "@/components/leads/LeadBatchActions";
import { LeadCnpjReviewQueue } from "@/components/leads/LeadCnpjReviewQueue";
import { LeadDetailPanel } from "@/components/leads/LeadDetailPanel";
import { LeadQueueFilters } from "@/components/leads/LeadQueueFilters";
import { LeadQueueTable } from "@/components/leads/LeadQueueTable";
import { getLeadOptions, listLeads } from "@/lib/api/leads";
import type { LeadListParams, LeadSortBy, LeadSummary } from "@/lib/api/types";
import {
  booleanFilterValue,
  defaultQueueFilters,
  numericFilterValue,
  type QueueFilters,
} from "@/lib/state/lead-workspace";
import { formatUserFacingError } from "@/lib/ui/messages";

const SEARCH_FETCH_LIMIT = 500;

type LeadOperationsWorkspaceProps = {
  initialImportBatchId?: number | null;
};

export function LeadOperationsWorkspace({ initialImportBatchId = null }: LeadOperationsWorkspaceProps) {
  const importBatchId = initialImportBatchId;
  const [filters, setFilters] = useState<QueueFilters>(defaultQueueFilters);
  const [search, setSearch] = useState("");
  const [pageIndex, setPageIndex] = useState(0);
  const [pageSize, setPageSize] = useState(25);
  const [sorting, setSorting] = useState<SortingState>([{ id: "updated_at", desc: true }]);
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [activeLeadId, setActiveLeadId] = useState<number | null>(null);

  const optionsQuery = useQuery({
    queryKey: ["lead-options"],
    queryFn: getLeadOptions,
  });

  const queryParams = useMemo<LeadListParams>(() => {
    const sort = sorting[0];
    const sortBy = (sort?.id as LeadSortBy | undefined) ?? "updated_at";
    const sortDir = sort ? (sort.desc ? "desc" : "asc") : "desc";
    const searchMode = search.trim().length > 0;

    return {
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
      limit: searchMode ? SEARCH_FETCH_LIMIT : pageSize,
      offset: searchMode ? 0 : pageIndex * pageSize,
    };
  }, [filters, importBatchId, pageIndex, pageSize, search, sorting]);

  const leadsQuery = useQuery({
    queryKey: ["leads", queryParams],
    queryFn: () => listLeads(queryParams),
  });

  const searchTerm = search.trim().toLowerCase();
  const searchedItems = useMemo(() => {
    const items = leadsQuery.data?.items ?? [];
    if (!searchTerm) {
      return items;
    }
    return items.filter((lead) => leadMatchesSearch(lead, searchTerm));
  }, [leadsQuery.data?.items, searchTerm]);

  const pageItems = searchTerm
    ? searchedItems.slice(pageIndex * pageSize, pageIndex * pageSize + pageSize)
    : searchedItems;
  const currentFilteredTotal = leadsQuery.data?.total ?? 0;
  const total = searchTerm ? searchedItems.length : currentFilteredTotal;
  const selectedCount = Object.values(rowSelection).filter(Boolean).length;
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
      <div className="ea-card flex flex-col gap-4 p-5 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="ea-kicker">Leads</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-[-0.03em] text-brand-graphite">Leads</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-brand-muted">
            Revise, filtre, selecione e exporte os leads salvos a partir da descoberta.
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center sm:min-w-[360px]">
          <Metric label="Lista atual" value={total.toLocaleString()} />
          <Metric label="Selecionados" value={selectedCount.toLocaleString()} />
          <Metric label="Linhas por página" value={String(pageSize)} />
        </div>
      </div>

      {importBatchId ? (
        <section className="flex flex-col gap-3 rounded-3xl border border-brand-olive/70 bg-brand-olive/20 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-semibold text-brand-graphite">Visualizando o lote salvo {importBatchId}</p>
            <p className="mt-1 text-sm text-brand-muted">
              Você pode enriquecer, revisar e exportar este lote sem sair da área de leads.
            </p>
          </div>
          <Link
            href="/leads"
            className="ea-button-secondary px-3 py-2 text-center text-sm font-semibold"
          >
            Ver todos os leads
          </Link>
        </section>
      ) : null}

      <LeadQueueSearch
        value={search}
        onChange={updateSearch}
        resultCount={total}
        searchActive={Boolean(searchTerm)}
      />

      <LeadQueueFilters
        filters={filters}
        options={optionsQuery.data}
        onFiltersChange={updateFilters}
        onReset={resetFilters}
      />

      {optionsQuery.isError ? (
        <p className="rounded-2xl border border-rose-300/30 bg-rose-950/35 p-3 text-sm text-rose-100">
          {formatUserFacingError(optionsQuery.error, "Não foi possível carregar os filtros agora.")}
        </p>
      ) : null}

      {leadsQuery.isError ? (
        <p className="rounded-2xl border border-rose-300/30 bg-rose-950/35 p-3 text-sm text-rose-100">
          {formatUserFacingError(leadsQuery.error, "Não foi possível carregar os leads agora.")}
        </p>
      ) : null}

      {showEmptyWorkspaceState ? (
        <section className="ea-card border-dashed p-5">
          <p className="text-sm font-semibold text-brand-graphite">Nenhum lead salvo ainda</p>
          <p className="mt-2 text-sm text-brand-muted">
            Os leads que você salvar em <span className="font-medium">/discovery</span> aparecem aqui para revisão,
            enriquecimento e exportação.
          </p>
          <Link
            href="/discovery"
            className="ea-button-primary mt-4 inline-flex px-4 py-2 text-sm font-semibold"
          >
            Ir para descoberta
          </Link>
        </section>
      ) : null}

      <LeadBatchActions
        selectedLeadIds={selectedLeadIds}
        currentFilters={queryParams}
        currentTotal={currentFilteredTotal}
        searchActive={Boolean(searchTerm)}
      />

      <LeadCnpjReviewQueue
        currentFilters={queryParams}
        onActivateLead={setActiveLeadId}
        activeLeadId={detailLeadId}
      />

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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-brand-mist/80 bg-brand-sand/70 px-3 py-2">
      <p className="text-xs font-medium text-brand-muted">{label}</p>
      <p className="mt-1 text-lg font-semibold text-brand-graphite">{value}</p>
    </div>
  );
}

function LeadQueueSearch({
  value,
  onChange,
  resultCount,
  searchActive,
}: {
  value: string;
  onChange: (value: string) => void;
  resultCount: number;
  searchActive: boolean;
}) {
  return (
    <section className="ea-card p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <label className="block w-full lg:max-w-2xl" htmlFor="lead-search">
          <span className="text-sm font-semibold text-brand-graphite">Busca rápida</span>
          <input
            id="lead-search"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Empresa, cidade, contato, responsável, segmento ou motivo do bloqueio"
            className="ea-input mt-2 w-full px-3 py-2 text-sm"
          />
        </label>
        <div className="ea-card-flat px-3 py-2 lg:min-w-[180px]">
          <p className="text-xs font-medium text-brand-muted">{searchActive ? "Resultados" : "Lista visível"}</p>
          <p className="mt-1 text-lg font-semibold text-brand-graphite">{resultCount.toLocaleString()}</p>
        </div>
      </div>
      <p className="mt-2 text-xs text-brand-muted">
        A busca rápida filtra os leads já carregados na lista com os filtros atuais.
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

function leadMatchesSearch(lead: LeadSummary, searchTerm: string) {
  const haystack = [
    lead.business_name,
    lead.normalized_business_name,
    lead.category,
    lead.city,
    lead.state,
    lead.email,
    lead.phone,
    lead.whatsapp,
    lead.instagram,
    lead.website,
    lead.assigned_sales_rep?.name,
    lead.sales_region?.name,
    lead.market_segment?.name,
    lead.market_subsegment?.name,
    lead.company_size_fit,
    lead.trade_type,
    lead.is_blocked ? "blocked" : "unblocked",
    lead.blocked_reason,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

  return haystack.includes(searchTerm);
}
