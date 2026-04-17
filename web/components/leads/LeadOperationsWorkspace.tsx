"use client";

import { useQuery } from "@tanstack/react-query";
import type { RowSelectionState, SortingState } from "@tanstack/react-table";
import { useMemo, useState } from "react";

import { LeadBatchActions } from "@/components/leads/LeadBatchActions";
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

const SEARCH_FETCH_LIMIT = 500;

export function LeadOperationsWorkspace() {
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
      blocked: filters.blocked,
      sort_by: sortBy,
      sort_dir: sortDir,
      limit: searchMode ? SEARCH_FETCH_LIMIT : pageSize,
      offset: searchMode ? 0 : pageIndex * pageSize,
    };
  }, [filters, pageIndex, pageSize, search, sorting]);

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
    <div className="space-y-4">
      <div className="flex flex-col gap-3 rounded-md border border-neutral-200 bg-white p-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-cyan-700">Lead Operations Workspace</p>
          <h1 className="mt-1 text-2xl font-semibold text-neutral-950">Leads</h1>
          <p className="mt-1 text-sm text-neutral-500">Review, filter, select, and inspect companies already in Garin.</p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center sm:min-w-[360px]">
          <Metric label="Current set" value={total.toLocaleString()} />
          <Metric label="Selected" value={selectedCount.toLocaleString()} />
          <Metric label="Page size" value={String(pageSize)} />
        </div>
      </div>

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
        <p className="rounded-md border border-rose-200 bg-white p-3 text-sm text-rose-800">
          Filter options are unavailable.
        </p>
      ) : null}

      {leadsQuery.isError ? (
        <p className="rounded-md border border-rose-200 bg-white p-3 text-sm text-rose-800">
          Leads are unavailable. Check that the FastAPI backend is running.
        </p>
      ) : null}

      <LeadBatchActions
        selectedLeadIds={selectedLeadIds}
        currentFilters={queryParams}
        currentTotal={currentFilteredTotal}
        searchActive={Boolean(searchTerm)}
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
    <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2">
      <p className="text-xs font-medium text-neutral-500">{label}</p>
      <p className="mt-1 text-lg font-semibold text-neutral-950">{value}</p>
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
    <section className="rounded-md border border-cyan-200 bg-white p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <label className="block w-full lg:max-w-2xl" htmlFor="lead-search">
          <span className="text-sm font-semibold text-neutral-950">Search leads</span>
          <input
            id="lead-search"
            value={value}
            onChange={(event) => onChange(event.target.value)}
            placeholder="Company, city, contact, rep, region, segment, blocked reason"
            className="mt-2 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-950"
          />
        </label>
        <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 lg:min-w-[180px]">
          <p className="text-xs font-medium text-neutral-500">{searchActive ? "Search results" : "Visible set"}</p>
          <p className="mt-1 text-lg font-semibold text-neutral-950">{resultCount.toLocaleString()}</p>
        </div>
      </div>
      <p className="mt-2 text-xs text-neutral-500">
        Search uses the loaded queue window for the current filters.
      </p>
    </section>
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
