"use client";

import type { LeadOptionsResponse } from "@/lib/api/types";
import type { QueueFilters } from "@/lib/state/lead-workspace";

type LeadQueueFiltersProps = {
  search: string;
  filters: QueueFilters;
  options?: LeadOptionsResponse;
  onSearchChange: (value: string) => void;
  onFiltersChange: (filters: QueueFilters) => void;
  onReset: () => void;
};

export function LeadQueueFilters({
  search,
  filters,
  options,
  onSearchChange,
  onFiltersChange,
  onReset,
}: LeadQueueFiltersProps) {
  function updateFilter<Key extends keyof QueueFilters>(key: Key, value: QueueFilters[Key]) {
    onFiltersChange({ ...filters, [key]: value });
  }

  return (
    <section className="rounded-md border border-neutral-200 bg-white p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="w-full lg:max-w-md">
          <label className="block text-sm font-medium text-neutral-800" htmlFor="lead-search">
            Search
          </label>
          <input
            id="lead-search"
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Company, city, contact, assignment"
            className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-950"
          />
          {search ? (
            <p className="mt-1 text-xs text-neutral-500">
              Searching the loaded queue window for the current filters.
            </p>
          ) : null}
        </div>
        <button
          type="button"
          onClick={onReset}
          className="w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-800 hover:border-neutral-500 lg:w-auto"
        >
          Clear filters
        </button>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
        <SelectField
          label="City"
          value={filters.city}
          onChange={(value) => updateFilter("city", value)}
          options={(options?.cities ?? []).map((value) => ({ value, label: value }))}
        />
        <SelectField
          label="State"
          value={filters.state}
          onChange={(value) => updateFilter("state", value)}
          options={(options?.states ?? []).map((value) => ({ value, label: value }))}
        />
        <SelectField
          label="Status"
          value={filters.status}
          onChange={(value) => updateFilter("status", value as QueueFilters["status"])}
          options={(options?.statuses ?? []).map((value) => ({ value, label: labelToken(value) }))}
        />
        <SelectField
          label="Assigned rep"
          value={filters.assignedSalesRepId}
          onChange={(value) => updateFilter("assignedSalesRepId", value)}
          options={(options?.assigned_reps ?? []).map((rep) => ({ value: String(rep.id), label: rep.name }))}
        />
        <SelectField
          label="Sales region"
          value={filters.salesRegionId}
          onChange={(value) => updateFilter("salesRegionId", value)}
          options={(options?.sales_regions ?? []).map((region) => ({ value: String(region.id), label: region.name }))}
        />
        <SelectField
          label="Market segment"
          value={filters.marketSegmentId}
          onChange={(value) => updateFilter("marketSegmentId", value)}
          options={(options?.market_segments ?? []).map((segment) => ({ value: String(segment.id), label: segment.name }))}
        />
        <SelectField
          label="Subsegment"
          value={filters.marketSubsegmentId}
          onChange={(value) => updateFilter("marketSubsegmentId", value)}
          options={(options?.market_subsegments ?? []).map((subsegment) => ({
            value: String(subsegment.id),
            label: subsegment.name,
          }))}
        />
        <SelectField
          label="Target fit"
          value={filters.companySizeFit}
          onChange={(value) => updateFilter("companySizeFit", value as QueueFilters["companySizeFit"])}
          options={(options?.target_fit_values ?? []).map((value) => ({ value, label: labelToken(value) }))}
        />
        <SelectField
          label="Trade type"
          value={filters.tradeType}
          onChange={(value) => updateFilter("tradeType", value as QueueFilters["tradeType"])}
          options={(options?.trade_type_values ?? []).map((value) => ({ value, label: labelToken(value) }))}
        />
        <SelectField
          label="Has assignment"
          value={filters.hasAssignment}
          onChange={(value) => updateFilter("hasAssignment", value as QueueFilters["hasAssignment"])}
          options={booleanOptions}
        />
        <SelectField
          label="Has email"
          value={filters.hasEmail}
          onChange={(value) => updateFilter("hasEmail", value as QueueFilters["hasEmail"])}
          options={booleanOptions}
        />
        <SelectField
          label="Has WhatsApp"
          value={filters.hasWhatsapp}
          onChange={(value) => updateFilter("hasWhatsapp", value as QueueFilters["hasWhatsapp"])}
          options={booleanOptions}
        />
        <SelectField
          label="Has Instagram"
          value={filters.hasInstagram}
          onChange={(value) => updateFilter("hasInstagram", value as QueueFilters["hasInstagram"])}
          options={booleanOptions}
        />
      </div>
    </section>
  );
}

type SelectFieldProps = {
  label: string;
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
};

function SelectField({ label, value, options, onChange }: SelectFieldProps) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-neutral-600">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-2 py-2 text-sm text-neutral-950"
      >
        <option value="">Any</option>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

const booleanOptions = [
  { value: "any", label: "Any" },
  { value: "yes", label: "Yes" },
  { value: "no", label: "No" },
];

function labelToken(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
