"use client";

import { formatLeadLabel } from "@/lib/format/lead-labels";
import type { LeadOptionsResponse } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/client";
import type { QueueFilters } from "@/lib/state/lead-workspace";

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
  function updateFilter<Key extends keyof QueueFilters>(key: Key, value: QueueFilters[Key]) {
    onFiltersChange({ ...filters, [key]: value });
  }

  return (
    <section className="ea-card p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-semibold text-brand-graphite">{t("leads.filtersTitle")}</p>
          <p className="mt-1 text-sm leading-6 text-brand-muted">
            {t("leads.filtersDescription")}
          </p>
        </div>
        <button
          type="button"
          onClick={onReset}
          className="ea-button-secondary w-full px-3 py-2 text-sm font-semibold lg:w-auto"
        >
          {t("leads.clearFilters")}
        </button>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6">
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
    </section>
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
  return (
    <label className="block">
      <span className="text-xs font-medium text-brand-muted">{label}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="ea-input mt-1 w-full px-2 py-2 text-sm"
      >
        {resolvedEmptyLabel === null ? null : <option value="">{resolvedEmptyLabel}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
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
