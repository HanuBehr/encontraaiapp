"use client";

import { useState } from "react";

import { GlassSelect } from "@/components/ui/GlassSelect";
import { formatLeadLabel } from "@/lib/format/lead-labels";
import type { LeadOptionsResponse } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/client";
import { defaultQueueFilters, type QueueFilters } from "@/lib/state/lead-workspace";

type LeadQueueFiltersProps = {
  filters: QueueFilters;
  options?: LeadOptionsResponse;
  onFiltersChange: (filters: QueueFilters) => void;
  onReset: () => void;
};

export function LeadQueueFilters({
  filters,
  options,
  onFiltersChange,
  onReset,
}: LeadQueueFiltersProps) {
  const { locale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const activeFilterCount = countActiveFilters(filters);

  function updateFilter<Key extends keyof QueueFilters>(key: Key, value: QueueFilters[Key]) {
    onFiltersChange({ ...filters, [key]: value });
  }

  return (
    <div className="relative z-50">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <button
          type="button"
          onClick={() => setOpen((current) => !current)}
          aria-expanded={open}
          className="group flex h-11 min-w-0 flex-1 items-center gap-3 rounded-[1.05rem] text-left transition focus:outline-none focus:ring-2 focus:ring-brand-orchid/25"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.8rem] border border-brand-orchid/12 bg-brand-orchid/[0.06] text-brand-orchid">
            <FilterIcon className="h-4 w-4" />
          </span>
          <span className="flex min-w-0 flex-1 flex-wrap items-center gap-2 text-base font-bold text-brand-graphite">
            {t("leads.filtersTitle")}
            {activeFilterCount > 0 ? (
              <span className="rounded-full bg-brand-orchid/10 px-2 py-0.5 text-xs font-bold text-brand-orchid">
                {activeFilterCount}
              </span>
            ) : null}
          </span>
          <span className="ml-auto flex h-8 w-8 shrink-0 items-center justify-center rounded-[0.8rem] border border-brand-orchid/12 bg-white/[0.28] text-brand-muted transition group-hover:text-brand-orchid">
            <ChevronIcon className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
          </span>
        </button>

        {activeFilterCount > 0 ? (
          <button
            type="button"
            onClick={onReset}
            className="ea-button-secondary w-full px-3 py-2 text-sm font-semibold lg:w-auto"
          >
            {t("leads.clearFilters")}
          </button>
        ) : null}
      </div>

      <div
        className={`absolute inset-x-0 top-[calc(100%+1.5rem)] z-50 px-0.5 transition-[opacity,transform] duration-200 ease-out sm:px-1 ${
          open ? "pointer-events-auto translate-y-0 opacity-100" : "pointer-events-none -translate-y-1 opacity-0"
        }`}
      >
        <div className="ea-card ea-scroll-panel isolate max-h-[min(31rem,48vh)] overflow-y-auto overscroll-contain rounded-[1.25rem] bg-white/[0.72] p-3.5 shadow-[0_16px_42px_rgba(47,38,61,0.10),inset_0_1px_0_rgba(255,255,255,0.58)] backdrop-blur-[44px]">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6">
            <SelectField
              label={t("leads.blockStatus")}
              value={filters.blocked}
              onChange={(value) => updateFilter("blocked", value as QueueFilters["blocked"])}
              options={blockedOptions(t)}
              emptyLabel={null}
            />
            <SelectField
              label={t("leads.city")}
              value={filters.city}
              onChange={(value) => updateFilter("city", value)}
              options={(options?.cities ?? []).map((value) => ({ value, label: value }))}
            />
            <SelectField
              label={t("leads.state")}
              value={filters.state}
              onChange={(value) => updateFilter("state", value)}
              options={(options?.states ?? []).map((value) => ({ value, label: value }))}
            />
            <SelectField
              label="Status"
              value={filters.status}
              onChange={(value) => updateFilter("status", value as QueueFilters["status"])}
              options={(options?.statuses ?? []).map((value) => ({ value, label: formatLeadLabel(value, locale) ?? value }))}
            />
            <SelectField
              label={t("leads.assignee")}
              value={filters.assignedSalesRepId}
              onChange={(value) => updateFilter("assignedSalesRepId", value)}
              options={(options?.assigned_reps ?? []).map((rep) => ({ value: String(rep.id), label: rep.name }))}
            />
            <SelectField
              label={t("leads.region")}
              value={filters.salesRegionId}
              onChange={(value) => updateFilter("salesRegionId", value)}
              options={(options?.sales_regions ?? []).map((region) => ({ value: String(region.id), label: region.name }))}
            />
            <SelectField
              label={t("leads.segment")}
              value={filters.marketSegmentId}
              onChange={(value) => updateFilter("marketSegmentId", value)}
              options={(options?.market_segments ?? []).map((segment) => ({ value: String(segment.id), label: segment.name }))}
            />
            <SelectField
              label={t("leads.subsegment")}
              value={filters.marketSubsegmentId}
              onChange={(value) => updateFilter("marketSubsegmentId", value)}
              options={(options?.market_subsegments ?? []).map((subsegment) => ({
                value: String(subsegment.id),
                label: subsegment.name,
              }))}
            />
            <SelectField
              label={t("common.profile")}
              value={filters.companySizeFit}
              onChange={(value) => updateFilter("companySizeFit", value as QueueFilters["companySizeFit"])}
              options={(options?.target_fit_values ?? []).map((value) => ({
                value,
                label: formatLeadLabel(value, locale) ?? value,
              }))}
            />
            <SelectField
              label={t("leads.operation")}
              value={filters.tradeType}
              onChange={(value) => updateFilter("tradeType", value as QueueFilters["tradeType"])}
              options={(options?.trade_type_values ?? []).map((value) => ({
                value,
                label: formatLeadLabel(value, locale) ?? value,
              }))}
            />
            <SelectField
              label={t("leads.withAssignee")}
              value={filters.hasAssignment}
              onChange={(value) => updateFilter("hasAssignment", value as QueueFilters["hasAssignment"])}
              options={booleanOptions(t)}
            />
            <SelectField
              label={t("leads.withEmail")}
              value={filters.hasEmail}
              onChange={(value) => updateFilter("hasEmail", value as QueueFilters["hasEmail"])}
              options={booleanOptions(t)}
            />
            <SelectField
              label={t("leads.withWhatsapp")}
              value={filters.hasWhatsapp}
              onChange={(value) => updateFilter("hasWhatsapp", value as QueueFilters["hasWhatsapp"])}
              options={booleanOptions(t)}
            />
            <SelectField
              label={t("leads.withInstagram")}
              value={filters.hasInstagram}
              onChange={(value) => updateFilter("hasInstagram", value as QueueFilters["hasInstagram"])}
              options={booleanOptions(t)}
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function FilterIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M4 6h16" />
      <path d="M7 12h10" />
      <path d="M10 18h4" />
    </svg>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="m6 9 6 6 6-6" />
    </svg>
  );
}

type SelectFieldProps = {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
  emptyLabel?: string | null;
};

function SelectField({ label, value, options, onChange, emptyLabel }: SelectFieldProps) {
  const { t } = useI18n();
  const resolvedEmptyLabel = emptyLabel === undefined ? t("common.all") : emptyLabel;
  const resolvedOptions = [
    ...(resolvedEmptyLabel === null ? [] : [{ value: "", label: resolvedEmptyLabel }]),
    ...options,
  ];

  return (
    <div className="block">
      <span className="text-xs font-medium text-brand-muted">{label}</span>
      <GlassSelect
        value={value}
        options={resolvedOptions}
        ariaLabel={label}
        className="mt-1"
        onChange={onChange}
      />
    </div>
  );
}

function booleanOptions(t: ReturnType<typeof useI18n>["t"]) {
  return [
    { value: "any", label: t("common.all") },
    { value: "yes", label: t("common.yes") },
    { value: "no", label: t("common.no") },
  ];
}

function blockedOptions(t: ReturnType<typeof useI18n>["t"]) {
  return [
    { value: "exclude", label: t("discovery.blockedHidden") },
    { value: "include", label: t("discovery.blockedInclude") },
    { value: "only", label: t("discovery.blockedOnly") },
  ];
}

function countActiveFilters(filters: QueueFilters) {
  return (Object.keys(defaultQueueFilters) as Array<keyof QueueFilters>).filter(
    (key) => filters[key] !== defaultQueueFilters[key],
  ).length;
}
