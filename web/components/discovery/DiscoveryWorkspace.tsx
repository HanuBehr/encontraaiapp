"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useState } from "react";

import { ApiError } from "@/lib/api/client";
import {
  createExclusionRule,
  enrichDiscoveryPreview,
  evaluateDiscoveryExclusions,
  importDiscoveryPreview,
  previewDiscovery,
} from "@/lib/api/discovery";
import type {
  DiscoveryImportResponse,
  DiscoveryLeadCandidate,
  DiscoveryPreviewEnrichmentResponse,
  DiscoveryPreviewItem,
  DiscoveryPreviewResponse,
  DiscoverySearchRequest,
  ExclusionRuleType,
  LeadBlockedFilter,
} from "@/lib/api/types";

type LocationMode = "area" | "coordinates";
type WebsiteFilter = "all" | "has_website" | "no_website";

type DiscoveryFormState = {
  locationMode: LocationMode;
  city: string;
  neighborhood: string;
  postalCode: string;
  locationLabel: string;
  latitude: string;
  longitude: string;
  radiusM: number;
  maxResultsPerTerm: number;
  selectedTerms: string[];
  customTerms: string;
};

type BlockDraft = {
  item: DiscoveryPreviewItem;
  mode: "company" | "domain";
  ruleType: ExclusionRuleType;
  pattern: string;
  reason: string;
};

const defaultForm: DiscoveryFormState = {
  locationMode: "area",
  city: "",
  neighborhood: "",
  postalCode: "",
  locationLabel: "",
  latitude: "",
  longitude: "",
  radiusM: 3000,
  maxResultsPerTerm: 10,
  selectedTerms: ["materiais de construcao", "loja de tintas"],
  customTerms: "",
};

const searchTermOptions = [
  "materiais de construcao",
  "loja de tintas",
  "ferragistas",
  "construtoras",
  "incorporadoras",
  "marmorarias",
  "vidracarias",
  "madeireiras",
  "loja de material eletrico",
  "equipamentos de construcao",
];

const blockedOptions: Array<{ value: LeadBlockedFilter; label: string }> = [
  { value: "exclude", label: "Exclude blocked" },
  { value: "include", label: "Include blocked" },
  { value: "only", label: "Only blocked" },
];
const websiteOptions: Array<{ value: WebsiteFilter; label: string }> = [
  { value: "all", label: "All rows" },
  { value: "has_website", label: "Has website" },
  { value: "no_website", label: "No website" },
];

const ENRICH_VISIBLE_CONFIRMATION_THRESHOLD = 10;

export function DiscoveryWorkspace() {
  const [form, setForm] = useState<DiscoveryFormState>(defaultForm);
  const [searchRequest, setSearchRequest] = useState<DiscoverySearchRequest | null>(null);
  const [preview, setPreview] = useState<DiscoveryPreviewResponse | null>(null);
  const [blockedFilter, setBlockedFilter] = useState<LeadBlockedFilter>("exclude");
  const [websiteFilter, setWebsiteFilter] = useState<WebsiteFilter>("all");
  const [selectedIds, setSelectedIds] = useState<Record<string, boolean>>({});
  const [newlyBlockedIds, setNewlyBlockedIds] = useState<Record<string, boolean>>({});
  const [blockDraft, setBlockDraft] = useState<BlockDraft | null>(null);
  const [lastImport, setLastImport] = useState<DiscoveryImportResponse | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const previewMutation = useMutation({
    mutationFn: previewDiscovery,
    onSuccess: (data) => {
      const websiteReadyCount = data.items.filter((item) => hasWebsiteForCandidate(item.candidate)).length;
      setPreview(data);
      setSelectedIds(selectAllUnblocked(data.items));
      setNewlyBlockedIds({});
      setLastImport(null);
      setActionMessage(
        `Preview ready. ${websiteReadyCount.toLocaleString()} row(s) already have a website or domain and can be enriched.`,
      );
    },
  });

  const enrichMutation = useMutation({
    mutationFn: enrichDiscoveryPreview,
    onSuccess: (response) => {
      const previousBlocked = Object.fromEntries(
        (preview?.items ?? [])
          .filter((item) => item.client_result_id)
          .map((item) => [item.client_result_id as string, item.exclusion.is_blocked]),
      );
      setPreview(response.preview);
      setSelectedIds((current) => pruneBlockedSelection(current, response.preview.items));
      setNewlyBlockedIds(collectNewlyBlockedIds(response.preview.items, previousBlocked));
      setLastImport(null);
      setActionMessage(buildEnrichmentMessage(response));
    },
  });

  const blockMutation = useMutation({
    mutationFn: async ({ draft, currentPreview }: { draft: BlockDraft; currentPreview: DiscoveryPreviewResponse }) => {
      const response = await createExclusionRule({
        rule_type: draft.ruleType,
        pattern: draft.pattern.trim(),
        reason: draft.reason.trim() || null,
        reapply_existing_leads: true,
      });
      const reevaluatedPreview = await evaluateDiscoveryExclusions(currentPreview);
      return { response, preview: reevaluatedPreview };
    },
    onSuccess: ({ response, preview: nextPreview }) => {
      setPreview(nextPreview);
      setSelectedIds((current) => pruneBlockedSelection(current, nextPreview.items));
      setNewlyBlockedIds({});
      setBlockDraft(null);
      const blockedCount = response.reapply_summary?.blocked ?? 0;
      setActionMessage(`Rule saved. ${blockedCount.toLocaleString()} existing lead(s) newly blocked.`);
    },
  });

  const importMutation = useMutation({
    mutationFn: importDiscoveryPreview,
    onSuccess: (response) => {
      setLastImport(response);
      setActionMessage(
        `Saved batch ${response.batch_id}. Created ${response.created_leads}, updated ${response.updated_leads}, skipped ${response.skipped_blocked}.`,
      );
      setSelectedIds({});
    },
  });

  const visibleItems = useMemo(() => {
    const items = preview?.items ?? [];
    const blockedFiltered =
      blockedFilter === "include"
        ? items
        : blockedFilter === "only"
          ? items.filter((item) => item.exclusion.is_blocked)
          : items.filter((item) => !item.exclusion.is_blocked);

    if (websiteFilter === "has_website") {
      return blockedFiltered.filter((item) => hasWebsiteForCandidate(item.candidate));
    }
    if (websiteFilter === "no_website") {
      return blockedFiltered.filter((item) => !hasWebsiteForCandidate(item.candidate));
    }
    return blockedFiltered;
  }, [blockedFilter, preview?.items, websiteFilter]);

  const selectedClientResultIds = useMemo(() => {
    return (preview?.items ?? [])
      .filter((item) => item.client_result_id && selectedIds[item.client_result_id] && !item.exclusion.is_blocked)
      .map((item) => item.client_result_id as string);
  }, [preview?.items, selectedIds]);

  const selectedEnrichableClientResultIds = useMemo(() => {
    return (preview?.items ?? [])
      .filter(
        (item) =>
          item.client_result_id &&
          selectedIds[item.client_result_id] &&
          !item.exclusion.is_blocked &&
          hasWebsiteForCandidate(item.candidate),
      )
      .map((item) => item.client_result_id as string);
  }, [preview?.items, selectedIds]);

  const visibleSelectableIds = visibleItems
    .filter((item) => !item.exclusion.is_blocked && item.client_result_id)
    .map((item) => item.client_result_id as string);
  const visibleEnrichableIds = visibleItems
    .filter((item) => !item.exclusion.is_blocked && item.client_result_id && hasWebsiteForCandidate(item.candidate))
    .map((item) => item.client_result_id as string);
  const allVisibleSelected =
    visibleSelectableIds.length > 0 && visibleSelectableIds.every((clientId) => selectedIds[clientId]);
  const previewCount = preview?.items.length ?? 0;
  const blockedCount = preview?.items.filter((item) => item.exclusion.is_blocked).length ?? 0;
  const websiteReadyCount = preview?.items.filter((item) => hasWebsiteForCandidate(item.candidate)).length ?? 0;

  function updateForm<Key extends keyof DiscoveryFormState>(key: Key, value: DiscoveryFormState[Key]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function toggleSearchTerm(term: string) {
    setForm((current) => {
      const selectedTerms = current.selectedTerms.includes(term)
        ? current.selectedTerms.filter((selectedTerm) => selectedTerm !== term)
        : [...current.selectedTerms, term];
      return { ...current, selectedTerms };
    });
  }

  function runPreview(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setActionMessage(null);

    const result = buildDiscoveryRequest(form);
    if ("error" in result) {
      setFormError(result.error);
      return;
    }

    setSearchRequest(result.request);
    previewMutation.mutate(result.request);
  }

  function toggleSelection(clientResultId: string, checked: boolean) {
    setSelectedIds((current) => ({ ...current, [clientResultId]: checked }));
  }

  function toggleVisibleSelection(checked: boolean) {
    setSelectedIds((current) => {
      const next = { ...current };
      visibleSelectableIds.forEach((clientId) => {
        next[clientId] = checked;
      });
      return next;
    });
  }

  function openCompanyBlock(item: DiscoveryPreviewItem) {
    setBlockDraft({
      item,
      mode: "company",
      ruleType: "exact_name",
      pattern: item.candidate.business_name,
      reason: "Blocked during discovery",
    });
  }

  function openDomainBlock(item: DiscoveryPreviewItem) {
    const domain = domainForCandidate(item.candidate);
    if (!domain) {
      return;
    }
    setBlockDraft({
      item,
      mode: "domain",
      ruleType: "domain",
      pattern: domain,
      reason: "Blocked during discovery",
    });
  }

  function confirmBlockRule() {
    if (!blockDraft || !preview || !blockDraft.pattern.trim()) {
      return;
    }
    blockMutation.mutate({ draft: blockDraft, currentPreview: preview });
  }

  function enrichSelected() {
    if (!preview || selectedEnrichableClientResultIds.length === 0) {
      return;
    }
    const skippedNoWebsite = selectedClientResultIds.length - selectedEnrichableClientResultIds.length;
    if (skippedNoWebsite > 0) {
      setActionMessage(
        `Enriching ${selectedEnrichableClientResultIds.length.toLocaleString()} selected row(s) with a website. ${skippedNoWebsite.toLocaleString()} selected row(s) still have no website or domain.`,
      );
    }
    enrichMutation.mutate({
      preview,
      client_result_ids: selectedEnrichableClientResultIds,
      skip_blocked: true,
    });
  }

  function enrichVisible() {
    if (!preview || visibleEnrichableIds.length === 0) {
      return;
    }
    const skippedNoWebsite = visibleSelectableIds.length - visibleEnrichableIds.length;
    if (
      visibleEnrichableIds.length >= ENRICH_VISIBLE_CONFIRMATION_THRESHOLD &&
      !window.confirm(
        `Enrich ${visibleEnrichableIds.length.toLocaleString()} visible preview row(s) with a website? This can take a moment.`,
      )
    ) {
      return;
    }
    if (skippedNoWebsite > 0) {
      setActionMessage(
        `Enriching ${visibleEnrichableIds.length.toLocaleString()} visible row(s) with a website. ${skippedNoWebsite.toLocaleString()} visible row(s) still have no website or domain.`,
      );
    }
    enrichMutation.mutate({
      preview,
      client_result_ids: visibleEnrichableIds,
      skip_blocked: true,
    });
  }

  function saveSelected() {
    if (!searchRequest || !preview || selectedClientResultIds.length === 0) {
      return;
    }

    importMutation.mutate({
      request: searchRequest,
      preview,
      selected_client_result_ids: selectedClientResultIds,
      skip_blocked: true,
    });
  }

  return (
    <div className="space-y-4">
      <section className="flex flex-col gap-3 rounded-md border border-neutral-200 bg-white p-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-cyan-700">Discovery Workspace</p>
          <h1 className="mt-1 text-2xl font-semibold text-neutral-950">Discovery</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Search public businesses, suppress blocked brands, and save the useful results into Garin.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-center sm:min-w-[480px] sm:grid-cols-4">
          <Metric label="Preview" value={previewCount.toLocaleString()} />
          <Metric label="Website-ready" value={websiteReadyCount.toLocaleString()} />
          <Metric label="Blocked" value={blockedCount.toLocaleString()} />
          <Metric label="Selected" value={selectedClientResultIds.length.toLocaleString()} />
        </div>
      </section>

      <form onSubmit={runPreview} className="rounded-md border border-neutral-200 bg-white p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-neutral-950">Search setup</p>
            <p className="mt-1 text-sm text-neutral-500">
              Preview first. Leads are only created when selected results are saved.
            </p>
          </div>
          <button
            type="submit"
            disabled={previewMutation.isPending}
            className="rounded-md border border-neutral-900 bg-neutral-950 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {previewMutation.isPending ? "Searching" : "Run preview"}
          </button>
        </div>

        <div className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            <div>
              <span className="text-xs font-medium text-neutral-600">Location mode</span>
              <div className="mt-2 flex flex-wrap gap-2">
                <ToggleButton
                  active={form.locationMode === "area"}
                  onClick={() => updateForm("locationMode", "area")}
                >
                  City / area
                </ToggleButton>
                <ToggleButton
                  active={form.locationMode === "coordinates"}
                  onClick={() => updateForm("locationMode", "coordinates")}
                >
                  Coordinates
                </ToggleButton>
              </div>
            </div>

            {form.locationMode === "area" ? (
              <div className="grid gap-3 md:grid-cols-[1.3fr_1fr_0.9fr]">
                <TextField
                  label="City"
                  value={form.city}
                  onChange={(value) => updateForm("city", value)}
                  placeholder="Campinas, SP"
                />
                <TextField
                  label="Neighborhood"
                  value={form.neighborhood}
                  onChange={(value) => updateForm("neighborhood", value)}
                  placeholder="Optional"
                />
                <TextField
                  label="CEP"
                  value={form.postalCode}
                  onChange={(value) => updateForm("postalCode", value)}
                  placeholder="Optional"
                />
              </div>
            ) : (
              <div className="grid gap-3 md:grid-cols-[1fr_1fr_1.4fr]">
                <TextField
                  label="Latitude"
                  value={form.latitude}
                  onChange={(value) => updateForm("latitude", value)}
                  placeholder="-22.9056"
                />
                <TextField
                  label="Longitude"
                  value={form.longitude}
                  onChange={(value) => updateForm("longitude", value)}
                  placeholder="-47.0608"
                />
                <TextField
                  label="Location label"
                  value={form.locationLabel}
                  onChange={(value) => updateForm("locationLabel", value)}
                  placeholder="Optional"
                />
              </div>
            )}

            <div className="grid gap-3 sm:grid-cols-2">
              <NumberField
                label="Radius meters"
                min={100}
                max={50000}
                value={form.radiusM}
                onChange={(value) => updateForm("radiusM", value)}
              />
              <NumberField
                label="Max results per term"
                min={1}
                max={20}
                value={form.maxResultsPerTerm}
                onChange={(value) => updateForm("maxResultsPerTerm", value)}
              />
            </div>
          </div>

          <div className="rounded-md border border-neutral-200 bg-neutral-50 p-3">
            <p className="text-sm font-semibold text-neutral-950">Target terms</p>
            <div className="mt-3 grid gap-2">
              {searchTermOptions.map((term) => (
                <label key={term} className="flex items-center gap-2 text-sm text-neutral-700">
                  <input
                    type="checkbox"
                    checked={form.selectedTerms.includes(term)}
                    onChange={() => toggleSearchTerm(term)}
                    className="h-4 w-4 rounded border-neutral-300"
                  />
                  <span>{term}</span>
                </label>
              ))}
            </div>
            <label className="mt-3 block">
              <span className="text-xs font-medium text-neutral-600">Extra terms</span>
              <textarea
                value={form.customTerms}
                onChange={(event) => updateForm("customTerms", event.target.value)}
                placeholder="One per line, or comma-separated"
                className="mt-1 min-h-20 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-950"
              />
            </label>
          </div>
        </div>

        {formError ? <InlineMessage tone="danger">{formError}</InlineMessage> : null}
        {previewMutation.isError ? <InlineMessage tone="danger">{errorMessage(previewMutation.error)}</InlineMessage> : null}
      </form>

      <section className="rounded-md border border-neutral-200 bg-white p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-neutral-950">Preview results</p>
            <p className="mt-1 text-sm text-neutral-500">
              Blocked results are hidden by default. Save writes only selected unblocked rows.
            </p>
          </div>
          <div className="flex w-full flex-col gap-3 lg:w-auto lg:flex-row lg:items-end">
            <label className="block w-full lg:w-44">
              <span className="text-xs font-medium text-neutral-600">Blocked filter</span>
              <select
                value={blockedFilter}
                onChange={(event) => setBlockedFilter(event.target.value as LeadBlockedFilter)}
                className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-2 py-2 text-sm text-neutral-950"
              >
                {blockedOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
                </select>
            </label>
            <label className="block w-full lg:w-44">
              <span className="text-xs font-medium text-neutral-600">Website filter</span>
              <select
                value={websiteFilter}
                onChange={(event) => setWebsiteFilter(event.target.value as WebsiteFilter)}
                className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-2 py-2 text-sm text-neutral-950"
              >
                {websiteOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <div className="grid gap-2 sm:grid-cols-2">
              <button
                type="button"
                disabled={!preview || selectedEnrichableClientResultIds.length === 0 || enrichMutation.isPending}
                onClick={enrichSelected}
                className="rounded-md border border-neutral-900 bg-neutral-950 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {enrichMutation.isPending ? "Enriching" : "Enrich selected"}
              </button>
              <button
                type="button"
                disabled={!preview || visibleEnrichableIds.length === 0 || enrichMutation.isPending}
                onClick={enrichVisible}
                className="rounded-md border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Enrich visible
              </button>
            </div>
          </div>
        </div>

        {actionMessage ? <InlineMessage tone="info">{actionMessage}</InlineMessage> : null}
        {enrichMutation.isError ? <InlineMessage tone="danger">{errorMessage(enrichMutation.error)}</InlineMessage> : null}
        {blockMutation.isError ? <InlineMessage tone="danger">{errorMessage(blockMutation.error)}</InlineMessage> : null}
        {importMutation.isError ? <InlineMessage tone="danger">{errorMessage(importMutation.error)}</InlineMessage> : null}
        {preview ? (
          <p className="mt-3 text-xs text-neutral-500">
            Enrichment only runs on rows with a website or domain. Selected ready:{" "}
            {selectedEnrichableClientResultIds.length.toLocaleString()}. Visible ready:{" "}
            {visibleEnrichableIds.length.toLocaleString()}.
          </p>
        ) : null}

        {preview ? (
          <DiscoveryPreviewTable
            items={visibleItems}
            selectedIds={selectedIds}
            newlyBlockedIds={newlyBlockedIds}
            allVisibleSelected={allVisibleSelected}
            visibleSelectableCount={visibleSelectableIds.length}
            onToggleSelection={toggleSelection}
            onToggleVisibleSelection={toggleVisibleSelection}
            onBlockCompany={openCompanyBlock}
            onBlockDomain={openDomainBlock}
            actionDisabled={blockMutation.isPending || enrichMutation.isPending}
          />
        ) : (
          <div className="mt-4 rounded-md border border-dashed border-neutral-300 bg-neutral-50 px-4 py-10 text-center text-sm text-neutral-500">
            Run a preview to inspect companies before saving them as leads.
          </div>
        )}
      </section>

      <SaveBar
        preview={preview}
        lastImport={lastImport}
        selectedCount={selectedClientResultIds.length}
        isSaving={importMutation.isPending}
        onSave={saveSelected}
      />

      {blockDraft ? (
        <BlockRuleDialog
          draft={blockDraft}
          isSaving={blockMutation.isPending}
          onChange={setBlockDraft}
          onCancel={() => setBlockDraft(null)}
          onConfirm={confirmBlockRule}
        />
      ) : null}
    </div>
  );
}

function DiscoveryPreviewTable({
  items,
  selectedIds,
  newlyBlockedIds,
  allVisibleSelected,
  visibleSelectableCount,
  actionDisabled,
  onToggleSelection,
  onToggleVisibleSelection,
  onBlockCompany,
  onBlockDomain,
}: {
  items: DiscoveryPreviewItem[];
  selectedIds: Record<string, boolean>;
  newlyBlockedIds: Record<string, boolean>;
  allVisibleSelected: boolean;
  visibleSelectableCount: number;
  actionDisabled: boolean;
  onToggleSelection: (clientResultId: string, checked: boolean) => void;
  onToggleVisibleSelection: (checked: boolean) => void;
  onBlockCompany: (item: DiscoveryPreviewItem) => void;
  onBlockDomain: (item: DiscoveryPreviewItem) => void;
}) {
  return (
    <div className="mt-4 overflow-x-auto">
      <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
        <thead className="bg-neutral-50 text-xs font-semibold uppercase text-neutral-500">
          <tr>
            <th className="border-b border-neutral-200 px-3 py-3">
              <input
                type="checkbox"
                aria-label="Select visible unblocked rows"
                checked={allVisibleSelected}
                disabled={visibleSelectableCount === 0}
                onChange={(event) => onToggleVisibleSelection(event.target.checked)}
                className="h-4 w-4 rounded border-neutral-300 disabled:cursor-not-allowed"
              />
            </th>
            <th className="border-b border-neutral-200 px-3 py-3">Company</th>
            <th className="border-b border-neutral-200 px-3 py-3">Location</th>
            <th className="border-b border-neutral-200 px-3 py-3">Contact</th>
            <th className="border-b border-neutral-200 px-3 py-3">Exclusion</th>
            <th className="border-b border-neutral-200 px-3 py-3">Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.length ? (
            items.map((item) => {
              const clientResultId = item.client_result_id ?? "";
              const blocked = item.exclusion.is_blocked;
              const domain = domainForCandidate(item.candidate);
              const hasWebsite = hasWebsiteForCandidate(item.candidate);
              const contactFormUrl = firstExtractedContactUrl(item, "contact_form");
              return (
                <tr key={clientResultId || `${item.search_term}-${item.candidate.business_name}`} className="bg-white">
                  <td className="border-b border-neutral-100 px-3 py-3 align-top">
                    <input
                      type="checkbox"
                      aria-label={`Select ${item.candidate.business_name}`}
                      checked={Boolean(clientResultId && selectedIds[clientResultId])}
                      disabled={blocked || !clientResultId}
                      onChange={(event) => onToggleSelection(clientResultId, event.target.checked)}
                      className="h-4 w-4 rounded border-neutral-300 disabled:cursor-not-allowed disabled:opacity-40"
                    />
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="font-medium text-neutral-950">{item.candidate.business_name}</p>
                      {blocked ? <BlockedBadge /> : null}
                      {hasWebsite ? (
                        <OutcomeBadge tone="info">Has website</OutcomeBadge>
                      ) : (
                        <OutcomeBadge tone="muted">No website</OutcomeBadge>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-neutral-500">{item.candidate.category ?? "No category"}</p>
                    <p className="mt-1 text-xs text-neutral-500">Term: {item.search_term}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {item.candidate.website ? (
                        <a
                          href={item.candidate.website}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-medium text-cyan-700 hover:text-cyan-900"
                        >
                          Website
                        </a>
                      ) : null}
                      {item.candidate.google_maps_url || item.source_url ? (
                        <a
                          href={item.candidate.google_maps_url ?? item.source_url ?? ""}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-medium text-cyan-700 hover:text-cyan-900"
                        >
                          Maps
                        </a>
                      ) : null}
                    </div>
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top text-neutral-800">
                    <p>{[item.candidate.city, item.candidate.state].filter(Boolean).join(", ") || "Unknown"}</p>
                    <p className="mt-1 text-xs text-neutral-500">{item.candidate.neighborhood ?? item.candidate.address ?? ""}</p>
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top text-neutral-800">
                    <p>{item.candidate.whatsapp ?? item.candidate.phone ?? "No phone"}</p>
                    <p className="mt-1 text-xs text-neutral-500">{domain ?? "No domain"}</p>
                    {item.candidate.email ? (
                      <a
                        href={`mailto:${item.candidate.email}`}
                        className="mt-2 block break-all text-xs font-medium text-cyan-700 hover:text-cyan-900"
                      >
                        {item.candidate.email}
                      </a>
                    ) : null}
                    <div className="mt-2 flex flex-wrap gap-2">
                      {item.candidate.instagram ? (
                        <a
                          href={item.candidate.instagram}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-medium text-cyan-700 hover:text-cyan-900"
                        >
                          Instagram
                        </a>
                      ) : null}
                      {contactFormUrl ? (
                        <a
                          href={contactFormUrl}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-medium text-cyan-700 hover:text-cyan-900"
                        >
                          Contact form
                        </a>
                      ) : null}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {item.enrichment?.email_found ? <OutcomeBadge tone="info">Email found</OutcomeBadge> : null}
                      {item.enrichment?.instagram_found ? (
                        <OutcomeBadge tone="info">Instagram found</OutcomeBadge>
                      ) : null}
                      {item.enrichment?.contact_form_found ? <OutcomeBadge tone="info">Form found</OutcomeBadge> : null}
                      {item.enrichment?.no_email_found ? (
                        <OutcomeBadge tone="muted">No public email found</OutcomeBadge>
                      ) : null}
                      {item.enrichment?.skipped_reason === "No public website." ? (
                        <OutcomeBadge tone="warning">No website to enrich</OutcomeBadge>
                      ) : null}
                      {clientResultId && newlyBlockedIds[clientResultId] ? (
                        <OutcomeBadge tone="danger">Blocked after enrichment</OutcomeBadge>
                      ) : null}
                    </div>
                    {item.enrichment?.error_message ? (
                      <p className="mt-2 max-w-xs text-xs text-rose-700">{item.enrichment.error_message}</p>
                    ) : null}
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top">
                    {blocked ? (
                      <div>
                        <p className="font-medium text-rose-800">Blocked</p>
                        <p className="mt-1 max-w-xs text-xs text-rose-700">
                          {item.exclusion.reason ?? "Matched an active exclusion rule."}
                        </p>
                      </div>
                    ) : (
                      <span className="inline-flex rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800">
                        Eligible
                      </span>
                    )}
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top">
                    <div className="flex min-w-36 flex-col gap-2">
                      <button
                        type="button"
                        disabled={actionDisabled}
                        onClick={() => onBlockCompany(item)}
                        className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-800 hover:border-neutral-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Block company
                      </button>
                      <button
                        type="button"
                        disabled={actionDisabled || !domain}
                        onClick={() => onBlockDomain(item)}
                        className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-800 hover:border-neutral-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Block domain
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={6} className="px-4 py-10 text-center text-sm text-neutral-500">
                No preview rows match the current blocked and website filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

function SaveBar({
  preview,
  lastImport,
  selectedCount,
  isSaving,
  onSave,
}: {
  preview: DiscoveryPreviewResponse | null;
  lastImport: DiscoveryImportResponse | null;
  selectedCount: number;
  isSaving: boolean;
  onSave: () => void;
}) {
  return (
    <section className="rounded-md border border-neutral-200 bg-white p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase text-cyan-700">Save and handoff</p>
          <h2 className="mt-1 text-base font-semibold text-neutral-950">Save selected results</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Selected blocked rows are skipped by the backend. The saved batch opens directly in Leads.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-[140px_180px]">
          <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-center">
            <p className="text-xs font-medium text-neutral-500">Selected</p>
            <p className="mt-1 text-lg font-semibold text-neutral-950">{selectedCount.toLocaleString()}</p>
          </div>
          <button
            type="button"
            disabled={!preview || selectedCount === 0 || isSaving}
            onClick={onSave}
            className="rounded-md border border-neutral-900 bg-neutral-950 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? "Saving" : "Save selected"}
          </button>
        </div>
      </div>

      {lastImport ? (
        <div className="mt-4 flex flex-col gap-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-emerald-950">Batch {lastImport.batch_id} saved</p>
            <p className="mt-1 text-sm text-emerald-800">
              Created {lastImport.created_leads}, updated {lastImport.updated_leads}, skipped {lastImport.skipped_blocked}.
            </p>
          </div>
          <Link
            href={`/leads?import_batch_id=${lastImport.batch_id}`}
            className="rounded-md border border-emerald-900 bg-emerald-900 px-4 py-2 text-center text-sm font-medium text-white"
          >
            Open saved batch
          </Link>
        </div>
      ) : null}
    </section>
  );
}

function BlockRuleDialog({
  draft,
  isSaving,
  onChange,
  onCancel,
  onConfirm,
}: {
  draft: BlockDraft;
  isSaving: boolean;
  onChange: (draft: BlockDraft) => void;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const isCompany = draft.mode === "company";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-neutral-950/40 px-4 py-6">
      <div className="w-full max-w-lg rounded-md border border-neutral-200 bg-white p-4 shadow-lg">
        <p className="text-xs font-semibold uppercase text-cyan-700">
          {isCompany ? "Block company" : "Block domain"}
        </p>
        <h2 className="mt-1 text-lg font-semibold text-neutral-950">{draft.item.candidate.business_name}</h2>
        <p className="mt-1 text-sm text-neutral-500">
          Save an active exclusion rule and re-check the current preview.
        </p>

        <div className="mt-4 space-y-3">
          {isCompany ? (
            <label className="block">
              <span className="text-xs font-medium text-neutral-600">Rule type</span>
              <select
                value={draft.ruleType}
                onChange={(event) =>
                  onChange({ ...draft, ruleType: event.target.value as "exact_name" | "business_name_contains" })
                }
                className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-2 py-2 text-sm text-neutral-950"
              >
                <option value="exact_name">Exact company name</option>
                <option value="business_name_contains">Company name contains</option>
              </select>
            </label>
          ) : (
            <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-700">
              Domain rule
            </div>
          )}

          <TextField
            label="Pattern"
            value={draft.pattern}
            onChange={(value) => onChange({ ...draft, pattern: value })}
          />
          <TextField
            label="Reason"
            value={draft.reason}
            onChange={(value) => onChange({ ...draft, reason: value })}
          />
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSaving}
            className="rounded-md border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSaving || !draft.pattern.trim()}
            className="rounded-md border border-rose-900 bg-rose-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? "Saving rule" : "Save block rule"}
          </button>
        </div>
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

function TextField({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-neutral-600">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-950"
      />
    </label>
  );
}

function NumberField({
  label,
  min,
  max,
  value,
  onChange,
}: {
  label: string;
  min: number;
  max: number;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-neutral-600">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-950"
      />
    </label>
  );
}

function ToggleButton({
  active,
  children,
  onClick,
}: {
  active: boolean;
  children: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        active
          ? "rounded-md border border-cyan-700 bg-cyan-50 px-3 py-2 text-sm font-medium text-cyan-900"
          : "rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-700"
      }
    >
      {children}
    </button>
  );
}

function InlineMessage({ tone, children }: { tone: "danger" | "info"; children: string }) {
  const className =
    tone === "danger"
      ? "mt-3 rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800"
      : "mt-3 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-sm text-cyan-900";
  return <p className={className}>{children}</p>;
}

function BlockedBadge() {
  return (
    <span className="inline-flex rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-800">
      Blocked
    </span>
  );
}

function OutcomeBadge({
  tone,
  children,
}: {
  tone: "danger" | "info" | "muted" | "warning";
  children: string;
}) {
  const className =
    tone === "danger"
      ? "inline-flex rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-[11px] font-medium text-rose-800"
      : tone === "warning"
        ? "inline-flex rounded-md border border-amber-200 bg-amber-50 px-2 py-1 text-[11px] font-medium text-amber-900"
        : tone === "info"
          ? "inline-flex rounded-md border border-cyan-200 bg-cyan-50 px-2 py-1 text-[11px] font-medium text-cyan-900"
          : "inline-flex rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-[11px] font-medium text-neutral-700";
  return <span className={className}>{children}</span>;
}

function buildDiscoveryRequest(
  form: DiscoveryFormState,
): { request: DiscoverySearchRequest } | { error: string } {
  const searchTerms = parseDiscoveryTerms(form.selectedTerms, form.customTerms);
  if (searchTerms.length === 0) {
    return { error: "Choose at least one target term before running discovery." };
  }

  const radiusM = clampNumber(form.radiusM, 100, 50000);
  const maxResultsPerTerm = clampNumber(form.maxResultsPerTerm, 1, 20);

  if (form.locationMode === "area") {
    const city = form.city.trim();
    if (!city) {
      return { error: "Enter a city before running discovery." };
    }
    return {
      request: {
        search_terms: searchTerms,
        location_query: [form.neighborhood, city, form.postalCode]
          .map((part) => part.trim())
          .filter(Boolean)
          .join(", "),
        radius_m: radiusM,
        max_results_per_term: maxResultsPerTerm,
      },
    };
  }

  const latitude = parseCoordinate(form.latitude);
  const longitude = parseCoordinate(form.longitude);
  if (latitude === null || longitude === null) {
    return { error: "Enter both latitude and longitude before running discovery." };
  }

  return {
    request: {
      search_terms: searchTerms,
      location_query: form.locationLabel.trim() || null,
      latitude,
      longitude,
      radius_m: radiusM,
      max_results_per_term: maxResultsPerTerm,
    },
  };
}

function parseDiscoveryTerms(selectedTerms: string[], customTerms: string) {
  const terms = [...selectedTerms, ...customTerms.split(/[,\n]/)];
  const seen = new Set<string>();
  return terms
    .map((term) => term.trim())
    .filter((term) => {
      if (!term || seen.has(term.toLowerCase())) {
        return false;
      }
      seen.add(term.toLowerCase());
      return true;
    });
}

function selectAllUnblocked(items: DiscoveryPreviewItem[]) {
  return items.reduce<Record<string, boolean>>((selection, item) => {
    if (item.client_result_id && !item.exclusion.is_blocked) {
      selection[item.client_result_id] = true;
    }
    return selection;
  }, {});
}

function pruneBlockedSelection(selection: Record<string, boolean>, items: DiscoveryPreviewItem[]) {
  const allowedIds = new Set(
    items.filter((item) => item.client_result_id && !item.exclusion.is_blocked).map((item) => item.client_result_id),
  );
  return Object.entries(selection).reduce<Record<string, boolean>>((next, [clientId, selected]) => {
    if (selected && allowedIds.has(clientId)) {
      next[clientId] = true;
    }
    return next;
  }, {});
}

function collectNewlyBlockedIds(items: DiscoveryPreviewItem[], previousBlocked: Record<string, boolean>) {
  return items.reduce<Record<string, boolean>>((next, item) => {
    if (item.client_result_id && item.exclusion.is_blocked && !previousBlocked[item.client_result_id]) {
      next[item.client_result_id] = true;
    }
    return next;
  }, {});
}

function buildEnrichmentMessage(response: DiscoveryPreviewEnrichmentResponse) {
  const parts: string[] = [];
  if (response.summary.emails_found) {
    parts.push(`${response.summary.emails_found.toLocaleString()} email result(s)`);
  }
  if (response.summary.instagrams_found) {
    parts.push(`${response.summary.instagrams_found.toLocaleString()} Instagram result(s)`);
  }
  if (response.summary.contact_forms_found) {
    parts.push(`${response.summary.contact_forms_found.toLocaleString()} form result(s)`);
  }

  let message = `Enriched ${response.summary.processed.toLocaleString()} preview row(s).`;
  if (parts.length) {
    message += ` Found ${parts.join(", ")}.`;
  } else if (response.summary.no_email_found > 0) {
    message += " No additional public email was found on the enriched rows.";
  } else {
    message += " No additional public contact details were found.";
  }
  if (response.summary.skipped_no_website > 0) {
    message += ` ${response.summary.skipped_no_website.toLocaleString()} had no website to enrich.`;
  }
  if (response.summary.blocked_after_enrichment > 0) {
    message += ` ${response.summary.blocked_after_enrichment.toLocaleString()} became blocked after re-checking exclusions.`;
  }
  if (response.summary.errors > 0) {
    message += ` ${response.summary.errors.toLocaleString()} row(s) failed.`;
  }
  return message;
}

function hasWebsiteForCandidate(candidate: DiscoveryLeadCandidate) {
  return Boolean(candidate.website || domainForCandidate(candidate));
}

function domainForCandidate(candidate: DiscoveryLeadCandidate) {
  if (candidate.domain) {
    return candidate.domain;
  }
  if (!candidate.website) {
    return null;
  }
  try {
    const url = new URL(candidate.website.startsWith("http") ? candidate.website : `https://${candidate.website}`);
    return url.hostname.replace(/^www\./, "");
  } catch {
    return null;
  }
}

function firstExtractedContactUrl(item: DiscoveryPreviewItem, contactType: string) {
  const contact = item.enrichment?.extracted_contacts.find((entry) => entry.contact_type === contactType);
  return contact?.normalized_value ?? contact?.raw_value ?? null;
}

function parseCoordinate(value: string) {
  const parsed = Number(value.trim().replace(",", "."));
  return Number.isFinite(parsed) ? parsed : null;
}

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, Math.round(value)));
}

function errorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.detail ?? error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "The request could not be completed.";
}
