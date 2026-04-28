"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { useMemo, useRef, useState } from "react";

import {
  createExclusionRule,
  enrichDiscoveryPreview,
  evaluateDiscoveryExclusions,
  importDiscoveryPreview,
  previewDiscovery,
  recoverDiscoveryWebsites,
} from "@/lib/api/discovery";
import type {
  DiscoveryImportResponse,
  DiscoveryLeadCandidate,
  DiscoveryPreviewEnrichmentResponse,
  DiscoveryPreviewItem,
  DiscoveryPreviewResponse,
  DiscoveryPreviewWebsiteRecoveryResponse,
  DiscoverySearchRequest,
  ExclusionRuleType,
  LeadBlockedFilter,
} from "@/lib/api/types";
import {
  parseNaturalLanguageDiscoveryQuery,
  type ParsedDiscoveryQuery,
} from "@/lib/discovery/query-parser";
import {
  formatUserFacingError,
  NO_DISCOVERY_RESULTS_UI_MESSAGE,
  sanitizeUserFacingMessage,
} from "@/lib/ui/messages";

type LocationMode = "area" | "coordinates";
type WebsiteFilter = "all" | "has_website" | "no_website";

type DiscoveryFormState = {
  naturalLanguageQuery: string;
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

type DiscoveryRequestContext = {
  queryCategorySequence: number;
  queryLocationSequence: number;
  manualTermsSequence: number;
  manualAreaLocationSequence: number;
  manualCoordinateLabelSequence: number;
};

type DiscoveryRequestPreviewSummary = {
  searchTerms: string[];
  locationLabel: string | null;
  radiusM: number;
  maxResultsPerTerm: number;
  maxPotentialResults: number;
};

const defaultForm: DiscoveryFormState = {
  naturalLanguageQuery: "",
  locationMode: "area",
  city: "",
  neighborhood: "",
  postalCode: "",
  locationLabel: "",
  latitude: "",
  longitude: "",
  radiusM: 3000,
  maxResultsPerTerm: 10,
  selectedTerms: [],
  customTerms: "",
};

const searchTermOptions = [
  "dentistas",
  "restaurantes",
  "clínicas de estética",
  "academias",
  "lojas de móveis",
  "oficinas mecânicas",
  "fornecedores de embalagens",
  "pet shops",
  "escritórios de contabilidade",
  "clínicas veterinárias",
];
const discoveryExampleQueries = [
  "dentistas em São Paulo",
  "restaurantes em Campinas",
  "clínicas de estética no Rio de Janeiro",
];

const blockedOptions: Array<{ value: LeadBlockedFilter; label: string }> = [
  { value: "exclude", label: "Ocultar bloqueados" },
  { value: "include", label: "Incluir bloqueados" },
  { value: "only", label: "Somente bloqueados" },
];
const websiteOptions: Array<{ value: WebsiteFilter; label: string }> = [
  { value: "all", label: "Todas" },
  { value: "has_website", label: "Com site" },
  { value: "no_website", label: "Sem site" },
];

const ENRICH_VISIBLE_CONFIRMATION_THRESHOLD = 10;
const WEBSITE_RECOVERY_MAX_ROWS = 25;
const DISCOVERY_PREVIEW_ENRICHMENT_BATCH_SIZE = 3;

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
  const latestPreviewRequestIdRef = useRef(0);
  const editSequenceRef = useRef(0);
  const queryCategorySequenceRef = useRef(0);
  const queryLocationSequenceRef = useRef(0);
  const manualTermsSequenceRef = useRef(0);
  const manualAreaLocationSequenceRef = useRef(0);
  const manualCoordinateLabelSequenceRef = useRef(0);
  const [previewError, setPreviewError] = useState<unknown>(null);
  const [isPreviewPending, setIsPreviewPending] = useState(false);

  function applyPreviewResponse(data: DiscoveryPreviewResponse) {
    const totalCount = data.items.length;
    const websiteReadyCount = data.items.filter((item) => hasWebsiteForCandidate(item.candidate)).length;
    const noWebsiteCount = Math.max(totalCount - websiteReadyCount, 0);
    const recoverableNoWebsiteCount = data.items.filter(
      (item) => !item.exclusion.is_blocked && !hasWebsiteForCandidate(item.candidate) && hasWebsiteRecoveryLookupId(item),
    ).length;
    setPreview(data);
    setSelectedIds(selectAllUnblocked(data.items));
    setNewlyBlockedIds({});
    setLastImport(null);
    setPreviewError(null);
    setActionMessage(
      totalCount === 0
        ? NO_DISCOVERY_RESULTS_UI_MESSAGE
        : buildPreviewReadyMessage({
            totalCount,
            websiteReadyCount,
            noWebsiteCount,
            recoverableNoWebsiteCount,
            duplicatesRemoved: data.duplicates_removed,
          }),
    );
  }

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

  const recoverMutation = useMutation({
    mutationFn: recoverDiscoveryWebsites,
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
      setActionMessage(buildWebsiteRecoveryMessage(response));
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
      setActionMessage(`Regra salva. ${blockedCount.toLocaleString()} lead(s) existente(s) foram bloqueados agora.`);
    },
  });

  const importMutation = useMutation({
    mutationFn: importDiscoveryPreview,
    onSuccess: (response) => {
      setLastImport(response);
      setActionMessage(
        `Lote ${response.batch_id} salvo. ${response.created_leads} lead(s) criados, ${response.updated_leads} atualizados e ${response.skipped_blocked} ignorados por bloqueio.`,
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

  const selectedNoWebsiteClientResultIds = useMemo(() => {
    return (preview?.items ?? [])
      .filter(
        (item) =>
          item.client_result_id &&
          selectedIds[item.client_result_id] &&
          !item.exclusion.is_blocked &&
          !hasWebsiteForCandidate(item.candidate),
      )
      .map((item) => item.client_result_id as string);
  }, [preview?.items, selectedIds]);

  const selectedRecoverableClientResultIds = useMemo(() => {
    return (preview?.items ?? [])
      .filter(
        (item) =>
          item.client_result_id &&
          selectedIds[item.client_result_id] &&
          !item.exclusion.is_blocked &&
          !hasWebsiteForCandidate(item.candidate) &&
          hasWebsiteRecoveryLookupId(item),
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
  const recoverySelectionMissingLookupCount =
    selectedNoWebsiteClientResultIds.length - selectedRecoverableClientResultIds.length;
  const parsedNaturalLanguageQuery = useMemo(
    () => parseNaturalLanguageDiscoveryQuery(form.naturalLanguageQuery),
    [form.naturalLanguageQuery],
  );
  const discoveryRequestContext: DiscoveryRequestContext = {
    queryCategorySequence: queryCategorySequenceRef.current,
    queryLocationSequence: queryLocationSequenceRef.current,
    manualTermsSequence: manualTermsSequenceRef.current,
    manualAreaLocationSequence: manualAreaLocationSequenceRef.current,
    manualCoordinateLabelSequence: manualCoordinateLabelSequenceRef.current,
  };
  const interpretedLocationLabel =
    form.locationMode === "area"
      ? resolveAreaLocationQuery(form, parsedNaturalLanguageQuery, discoveryRequestContext)
      : resolveCoordinateLocationQuery(form, parsedNaturalLanguageQuery, discoveryRequestContext);
  const requestPreviewSummary = buildDiscoveryRequestPreviewSummary(
    form,
    parsedNaturalLanguageQuery,
    discoveryRequestContext,
  );
  const optionalTermsCount = Math.max(
    requestPreviewSummary.searchTerms.length - (parsedNaturalLanguageQuery?.searchTerms.length ?? 0),
    0,
  );

  function updateForm<Key extends keyof DiscoveryFormState>(key: Key, value: DiscoveryFormState[Key]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function nextEditSequence() {
    editSequenceRef.current += 1;
    return editSequenceRef.current;
  }

  function updateNaturalLanguageQuery(value: string) {
    const nextParsedQuery = parseNaturalLanguageDiscoveryQuery(value);
    if (queryCategoryKey(parsedNaturalLanguageQuery, form.naturalLanguageQuery) !== queryCategoryKey(nextParsedQuery, value)) {
      queryCategorySequenceRef.current = nextEditSequence();
    }
    if (queryLocationKey(parsedNaturalLanguageQuery) !== queryLocationKey(nextParsedQuery)) {
      queryLocationSequenceRef.current = nextEditSequence();
    }
    updateForm("naturalLanguageQuery", value);
  }

  function updateAreaLocationField(key: "city" | "neighborhood" | "postalCode", value: string) {
    manualAreaLocationSequenceRef.current = nextEditSequence();
    updateForm(key, value);
  }

  function updateCoordinateLabel(value: string) {
    manualCoordinateLabelSequenceRef.current = nextEditSequence();
    updateForm("locationLabel", value);
  }

  function updateCustomTerms(value: string) {
    manualTermsSequenceRef.current = nextEditSequence();
    updateForm("customTerms", value);
  }

  function applySuggestedQuery(query: string) {
    const nextParsedQuery = parseNaturalLanguageDiscoveryQuery(query);
    if (queryCategoryKey(parsedNaturalLanguageQuery, form.naturalLanguageQuery) !== queryCategoryKey(nextParsedQuery, query)) {
      queryCategorySequenceRef.current = nextEditSequence();
    }
    if (queryLocationKey(parsedNaturalLanguageQuery) !== queryLocationKey(nextParsedQuery)) {
      queryLocationSequenceRef.current = nextEditSequence();
    }
    setForm((current) => ({
      ...current,
      naturalLanguageQuery: query,
      locationMode: "area",
    }));
    setFormError(null);
    setPreviewError(null);
    setActionMessage(null);
  }

  function toggleSearchTerm(term: string) {
    setForm((current) => {
      manualTermsSequenceRef.current = nextEditSequence();
      const selectedTerms = current.selectedTerms.includes(term)
        ? current.selectedTerms.filter((selectedTerm) => selectedTerm !== term)
        : [...current.selectedTerms, term];
      return { ...current, selectedTerms };
    });
  }

  async function runPreview(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setActionMessage(null);
    setPreviewError(null);

    const result = buildDiscoveryRequest(form, parsedNaturalLanguageQuery, discoveryRequestContext);
    if ("error" in result) {
      setFormError(result.error);
      return;
    }

    setSearchRequest(result.request);
    const requestId = latestPreviewRequestIdRef.current + 1;
    latestPreviewRequestIdRef.current = requestId;
    setIsPreviewPending(true);

    try {
      const response = await previewDiscovery(result.request);
      if (requestId !== latestPreviewRequestIdRef.current) {
        return;
      }
      applyPreviewResponse(response);
    } catch (error) {
      if (requestId !== latestPreviewRequestIdRef.current) {
        return;
      }
      setPreviewError(error);
    } finally {
      if (requestId === latestPreviewRequestIdRef.current) {
        setIsPreviewPending(false);
      }
    }
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
      reason: "Bloqueado durante a descoberta",
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
      reason: "Bloqueado durante a descoberta",
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
    const batchCount = Math.ceil(selectedEnrichableClientResultIds.length / DISCOVERY_PREVIEW_ENRICHMENT_BATCH_SIZE);
    if (batchCount > 1) {
      setActionMessage(
        `Enriquecendo ${selectedEnrichableClientResultIds.length.toLocaleString()} empresa(s) selecionadas em ${batchCount.toLocaleString()} lote(s) menores para evitar timeout no proxy.${skippedNoWebsite > 0 ? ` ${skippedNoWebsite.toLocaleString()} selecionada(s) ainda não têm site ou domínio.` : ""}`,
      );
    } else if (skippedNoWebsite > 0) {
      setActionMessage(
        `Enriquecendo ${selectedEnrichableClientResultIds.length.toLocaleString()} empresa(s) selecionadas com site. ${skippedNoWebsite.toLocaleString()} selecionada(s) ainda não têm site ou domínio.`,
      );
    }
    enrichMutation.mutate({
      preview,
      client_result_ids: selectedEnrichableClientResultIds,
      skip_blocked: true,
    });
  }

  function recoverSelected() {
    if (!preview) {
      return;
    }
    if (selectedNoWebsiteClientResultIds.length === 0) {
      setActionMessage("Selecione pelo menos uma empresa sem site para tentar a recuperação.");
      return;
    }
    if (selectedRecoverableClientResultIds.length === 0) {
      setActionMessage(
        "As empresas selecionadas sem site não têm um Google place id recuperável. Escolha outras linhas ou salve assim mesmo.",
      );
      return;
    }
    if (selectedRecoverableClientResultIds.length > WEBSITE_RECOVERY_MAX_ROWS) {
      setActionMessage(
        `A recuperação de sites funciona em até ${WEBSITE_RECOVERY_MAX_ROWS.toLocaleString()} empresas sem site por vez. Reduza a seleção e tente novamente.`,
      );
      return;
    }
    if (recoverySelectionMissingLookupCount > 0) {
      setActionMessage(
        `Recuperando site de ${selectedRecoverableClientResultIds.length.toLocaleString()} empresa(s) selecionadas. ${recoverySelectionMissingLookupCount.toLocaleString()} linha(s) seguem sem place id recuperável e não serão alteradas.`,
      );
    }
    recoverMutation.mutate({
      preview,
      client_result_ids: selectedRecoverableClientResultIds,
      skip_blocked: true,
    });
  }

  function enrichVisible() {
    if (!preview || visibleEnrichableIds.length === 0) {
      return;
    }
    const skippedNoWebsite = visibleSelectableIds.length - visibleEnrichableIds.length;
    const batchCount = Math.ceil(visibleEnrichableIds.length / DISCOVERY_PREVIEW_ENRICHMENT_BATCH_SIZE);
    if (
      visibleEnrichableIds.length >= ENRICH_VISIBLE_CONFIRMATION_THRESHOLD &&
      !window.confirm(
        `Enriquecer ${visibleEnrichableIds.length.toLocaleString()} empresa(s) visíveis com site? Isso pode levar alguns instantes.`,
      )
    ) {
      return;
    }
    if (batchCount > 1) {
      setActionMessage(
        `Enriquecendo ${visibleEnrichableIds.length.toLocaleString()} empresa(s) visíveis em ${batchCount.toLocaleString()} lote(s) menores para evitar timeout no proxy.${skippedNoWebsite > 0 ? ` ${skippedNoWebsite.toLocaleString()} linha(s) visíveis ainda não têm site ou domínio.` : ""}`,
      );
    } else if (skippedNoWebsite > 0) {
      setActionMessage(
        `Enriquecendo ${visibleEnrichableIds.length.toLocaleString()} empresa(s) visíveis com site. ${skippedNoWebsite.toLocaleString()} linha(s) visíveis ainda não têm site ou domínio.`,
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
          <p className="text-xs font-semibold uppercase text-cyan-700">Descoberta</p>
          <h1 className="mt-1 text-2xl font-semibold text-neutral-950">Buscar empresas</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Pesquise empresas públicas por nicho e cidade, revise a prévia e salve apenas os leads que fazem sentido.
          </p>
        </div>
        <div className="grid grid-cols-2 gap-2 text-center sm:min-w-[480px] sm:grid-cols-4">
          <Metric label="Prévia" value={previewCount.toLocaleString()} />
          <Metric label="Com site" value={websiteReadyCount.toLocaleString()} />
          <Metric label="Bloqueadas" value={blockedCount.toLocaleString()} />
          <Metric label="Selecionadas" value={selectedClientResultIds.length.toLocaleString()} />
        </div>
      </section>

      <form onSubmit={runPreview} className="rounded-xl border border-neutral-200 bg-white p-5 shadow-sm">
        <div className="rounded-xl border border-neutral-200 bg-gradient-to-br from-white to-cyan-50/70 p-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl">
              <h2 className="text-2xl font-semibold text-neutral-950">Encontre leads por nicho e cidade</h2>
              <p className="mt-2 text-sm text-neutral-600">
                Digite o tipo de empresa, escolha a região e gere uma prévia antes de salvar os leads.
              </p>
              <div className="mt-4 flex flex-wrap gap-2">
                {discoveryExampleQueries.map((query) => (
                  <button
                    key={query}
                    type="button"
                    onClick={() => applySuggestedQuery(query)}
                    className="rounded-full border border-neutral-300 bg-white px-3 py-1.5 text-xs font-medium text-neutral-700 hover:border-neutral-500"
                  >
                    {query}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex flex-col items-start gap-2">
              <span className="text-xs font-medium uppercase tracking-wide text-neutral-500">Modo de localização</span>
              <div className="flex flex-wrap gap-2">
                <ToggleButton
                  active={form.locationMode === "area"}
                  onClick={() => updateForm("locationMode", "area")}
                >
                  Cidade / região
                </ToggleButton>
                <ToggleButton
                  active={form.locationMode === "coordinates"}
                  onClick={() => updateForm("locationMode", "coordinates")}
                >
                  Coordenadas
                </ToggleButton>
              </div>
            </div>
          </div>

          <div className="mt-6 grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
            <label className="block">
              <span className="text-xs font-medium text-neutral-600">Nicho ou busca</span>
              <input
                value={form.naturalLanguageQuery}
                onChange={(event) => updateNaturalLanguageQuery(event.target.value)}
                placeholder="Ex: dentistas, reparos de celular, lojas de móveis"
                className="mt-1 w-full rounded-lg border border-neutral-300 bg-white px-4 py-3 text-sm text-neutral-950 shadow-sm"
              />
              <p className="mt-1 text-xs text-neutral-500">
                Você pode digitar só o nicho ou uma busca completa como &quot;dentistas em São Paulo&quot;.
              </p>
            </label>

            {form.locationMode === "area" ? (
              <label className="block">
                <span className="text-xs font-medium text-neutral-600">Cidade ou região</span>
                <input
                  value={form.city}
                  onChange={(event) => updateAreaLocationField("city", event.target.value)}
                  placeholder="Ex: São Paulo, Campinas, Santana de Parnaíba"
                  className="mt-1 w-full rounded-lg border border-neutral-300 bg-white px-4 py-3 text-sm text-neutral-950 shadow-sm"
                />
                <p className="mt-1 text-xs text-neutral-500">
                  Se a cidade já estiver na busca principal, este campo pode ficar em branco.
                </p>
              </label>
            ) : (
              <div className="rounded-lg border border-neutral-200 bg-white p-4 shadow-sm">
                <p className="text-xs font-medium uppercase tracking-wide text-neutral-500">Coordenadas ativas</p>
                <p className="mt-1 text-sm text-neutral-700">
                  Use latitude e longitude quando quiser montar a busca a partir de um ponto específico.
                </p>
              </div>
            )}
          </div>

          {form.locationMode === "area" ? (
            <details className="mt-4 rounded-lg border border-neutral-200 bg-white/80 p-4">
              <summary className="cursor-pointer list-item text-sm font-medium text-neutral-800">
                Refinar localização
              </summary>
              <p className="mt-2 text-xs text-neutral-500">
                Opcional. Use bairro ou CEP quando quiser restringir melhor a região da busca.
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-2">
                <TextField
                  label="Bairro"
                  value={form.neighborhood}
                  onChange={(value) => updateAreaLocationField("neighborhood", value)}
                  placeholder="Opcional"
                />
                <TextField
                  label="CEP"
                  value={form.postalCode}
                  onChange={(value) => updateAreaLocationField("postalCode", value)}
                  placeholder="Opcional"
                />
              </div>
            </details>
          ) : (
            <div className="mt-4 rounded-lg border border-neutral-200 bg-white/80 p-4">
              <div className="grid gap-3 md:grid-cols-[1fr_1fr_1.3fr]">
                <TextField
                  label="Latitude"
                  value={form.latitude}
                  onChange={(value) => updateForm("latitude", value)}
                  placeholder="-23.5505"
                />
                <TextField
                  label="Longitude"
                  value={form.longitude}
                  onChange={(value) => updateForm("longitude", value)}
                  placeholder="-46.6333"
                />
                <TextField
                  label="Rótulo do local"
                  value={form.locationLabel}
                  onChange={(value) => updateCoordinateLabel(value)}
                  placeholder="Opcional"
                />
              </div>
            </div>
          )}

          <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] lg:items-end">
            <div className="rounded-lg border border-neutral-200 bg-white px-4 py-3 shadow-sm">
              <NumberField
                label="Raio"
                min={100}
                max={50000}
                value={form.radiusM}
                onChange={(value) => updateForm("radiusM", value)}
              />
              <p className="mt-1 text-xs text-neutral-500">Aumente o raio para buscar mais longe.</p>
            </div>
            <div className="rounded-lg border border-neutral-200 bg-white px-4 py-3 shadow-sm">
              <NumberField
                label="Máximo por termo"
                min={1}
                max={20}
                value={form.maxResultsPerTerm}
                onChange={(value) => updateForm("maxResultsPerTerm", value)}
              />
              <p className="mt-1 text-xs text-neutral-500">
                É um limite máximo; a busca pode retornar menos resultados.
              </p>
            </div>
            <button
              type="submit"
              disabled={isPreviewPending}
              className="min-w-[180px] rounded-lg border border-neutral-900 bg-neutral-950 px-5 py-3 text-sm font-medium text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isPreviewPending ? "Buscando..." : "Gerar prévia"}
            </button>
          </div>

          <div className="mt-4 rounded-lg border border-cyan-200 bg-cyan-50 px-4 py-3">
            <p className="text-sm font-medium text-cyan-950">
              {buildDiscoverySummaryLine({
                primaryTerm: parsedNaturalLanguageQuery?.category ?? requestPreviewSummary.searchTerms[0] ?? null,
                locationLabel: requestPreviewSummary.locationLabel,
                radiusM: requestPreviewSummary.radiusM,
                maxResultsPerTerm: requestPreviewSummary.maxResultsPerTerm,
              })}
            </p>
            {buildDiscoveryRelatedTermsSummary(
              parsedNaturalLanguageQuery?.category ?? requestPreviewSummary.searchTerms[0] ?? null,
              requestPreviewSummary.searchTerms,
            ) ? (
              <p className="mt-1 text-xs text-cyan-900">
                Termos relacionados:{" "}
                {buildDiscoveryRelatedTermsSummary(
                  parsedNaturalLanguageQuery?.category ?? requestPreviewSummary.searchTerms[0] ?? null,
                  requestPreviewSummary.searchTerms,
                )}
              </p>
            ) : null}
            <p className="mt-1 text-xs text-cyan-900">Duplicatas serão consolidadas automaticamente.</p>
          </div>

          <details className="mt-4 rounded-lg border border-neutral-200 bg-white p-4">
            <summary className="cursor-pointer list-item text-sm font-medium text-neutral-900">
              Adicionar termos relacionados
            </summary>
            <p className="mt-2 text-xs text-neutral-500">
              Opcional. Use para buscar variações do mesmo nicho. A prévia remove duplicatas automaticamente.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
              {searchTermOptions.map((term) => (
                <label key={term} className="flex items-center gap-2 rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-700">
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
            <label className="mt-4 block">
              <span className="text-xs font-medium text-neutral-600">Termos livres</span>
              <textarea
                value={form.customTerms}
                onChange={(event) => updateCustomTerms(event.target.value)}
                placeholder="Um por linha ou separados por vírgula"
                className="mt-1 min-h-24 w-full rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm text-neutral-950"
              />
            </label>
            <p className="mt-2 text-xs text-neutral-500">
              {optionalTermsCount > 0
                ? `${optionalTermsCount.toLocaleString()} termo(s) relacionado(s) entram na próxima prévia.`
                : "Se você não adicionar nada aqui, a busca usa só o nicho principal."}
            </p>
          </details>
        </div>

        {formError ? <InlineMessage tone="danger">{formError}</InlineMessage> : null}
        {previewError ? <InlineMessage tone="danger">{errorMessage(previewError)}</InlineMessage> : null}
      </form>

      <section className="rounded-md border border-neutral-200 bg-white p-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-neutral-950">Prévia da busca</p>
            <p className="mt-1 text-sm text-neutral-500">
              Resultados bloqueados ficam ocultos por padrão. Só os itens selecionados serão salvos em Leads.
            </p>
          </div>
          <div className="flex w-full flex-col gap-3 lg:w-auto lg:flex-row lg:items-end">
            <label className="block w-full lg:w-44">
              <span className="text-xs font-medium text-neutral-600">Filtro de bloqueio</span>
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
              <span className="text-xs font-medium text-neutral-600">Filtro de site</span>
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
            <div className="grid gap-2 sm:grid-cols-3">
              <button
                type="button"
                disabled={!preview || selectedNoWebsiteClientResultIds.length === 0 || enrichMutation.isPending || recoverMutation.isPending}
                onClick={recoverSelected}
                className="rounded-md border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {recoverMutation.isPending ? "Recuperando..." : "Recuperar sites"}
              </button>
              <button
                type="button"
                disabled={
                  !preview || selectedEnrichableClientResultIds.length === 0 || enrichMutation.isPending || recoverMutation.isPending
                }
                onClick={enrichSelected}
                className="rounded-md border border-neutral-900 bg-neutral-950 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
              >
                {enrichMutation.isPending ? "Enriquecendo..." : "Enriquecer selecionadas"}
              </button>
              <button
                type="button"
                disabled={!preview || visibleEnrichableIds.length === 0 || enrichMutation.isPending || recoverMutation.isPending}
                onClick={enrichVisible}
                className="rounded-md border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
              >
                Enriquecer visíveis
              </button>
            </div>
          </div>
        </div>

        {actionMessage ? <InlineMessage tone="info">{actionMessage}</InlineMessage> : null}
        {recoverMutation.isError ? <InlineMessage tone="danger">{errorMessage(recoverMutation.error)}</InlineMessage> : null}
        {enrichMutation.isError ? <InlineMessage tone="danger">{errorMessage(enrichMutation.error)}</InlineMessage> : null}
        {blockMutation.isError ? <InlineMessage tone="danger">{errorMessage(blockMutation.error)}</InlineMessage> : null}
        {importMutation.isError ? <InlineMessage tone="danger">{errorMessage(importMutation.error)}</InlineMessage> : null}
        {preview ? (
          <p className="mt-3 text-xs text-neutral-500">
            O enriquecimento roda apenas em empresas com site ou domínio. Selecionadas prontas:{" "}
            {selectedEnrichableClientResultIds.length.toLocaleString()}. Visíveis prontas:{" "}
            {visibleEnrichableIds.length.toLocaleString()}. A recuperação de sites verifica até{" "}
            {WEBSITE_RECOVERY_MAX_ROWS.toLocaleString()} empresas sem site por vez. Recuperáveis agora:{" "}
            {selectedRecoverableClientResultIds.length.toLocaleString()}.
          </p>
        ) : null}

        {preview ? (
          <DiscoveryPreviewTable
            items={visibleItems}
            emptyMessage={
              (preview.items?.length ?? 0) === 0
                ? NO_DISCOVERY_RESULTS_UI_MESSAGE
                : "Nenhuma empresa corresponde aos filtros atuais de bloqueio e site."
            }
            selectedIds={selectedIds}
            newlyBlockedIds={newlyBlockedIds}
            allVisibleSelected={allVisibleSelected}
            visibleSelectableCount={visibleSelectableIds.length}
            onToggleSelection={toggleSelection}
            onToggleVisibleSelection={toggleVisibleSelection}
            onBlockCompany={openCompanyBlock}
            onBlockDomain={openDomainBlock}
            actionDisabled={blockMutation.isPending || enrichMutation.isPending || recoverMutation.isPending}
          />
        ) : (
          <div className="mt-4 rounded-md border border-dashed border-neutral-300 bg-neutral-50 px-4 py-10 text-center text-sm text-neutral-500">
            <p className="font-medium text-neutral-800">Busque por nicho + cidade para montar sua prévia.</p>
            <p className="mt-2">
              Exemplos: dentistas em São Paulo, restaurantes em Campinas ou clínicas de estética no Rio de Janeiro.
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {discoveryExampleQueries.map((query) => (
                <button
                  key={query}
                  type="button"
                  onClick={() => applySuggestedQuery(query)}
                  className="rounded-full border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-800 hover:border-neutral-500"
                >
                  {query}
                </button>
              ))}
            </div>
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
  emptyMessage,
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
  emptyMessage: string;
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
                aria-label="Selecionar empresas visíveis"
                checked={allVisibleSelected}
                disabled={visibleSelectableCount === 0}
                onChange={(event) => onToggleVisibleSelection(event.target.checked)}
                className="h-4 w-4 rounded border-neutral-300 disabled:cursor-not-allowed"
              />
            </th>
            <th className="border-b border-neutral-200 px-3 py-3">Empresa</th>
            <th className="border-b border-neutral-200 px-3 py-3">Localização</th>
            <th className="border-b border-neutral-200 px-3 py-3">Contato</th>
            <th className="border-b border-neutral-200 px-3 py-3">Exclusão</th>
            <th className="border-b border-neutral-200 px-3 py-3">Ações</th>
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
                        <OutcomeBadge tone="info">Com site</OutcomeBadge>
                      ) : (
                        <OutcomeBadge tone="muted">Sem site</OutcomeBadge>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-neutral-500">{item.candidate.category ?? "Sem categoria"}</p>
                    <p className="mt-1 text-xs text-neutral-500">{previewSearchTermsLabel(item)}</p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {item.candidate.website ? (
                        <a
                          href={item.candidate.website}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-medium text-cyan-700 hover:text-cyan-900"
                        >
                          Site
                        </a>
                      ) : null}
                      {item.candidate.google_maps_url || item.source_url ? (
                        <a
                          href={item.candidate.google_maps_url ?? item.source_url ?? ""}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-medium text-cyan-700 hover:text-cyan-900"
                        >
                          Google Maps
                        </a>
                      ) : null}
                    </div>
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top text-neutral-800">
                    <p>{[item.candidate.city, item.candidate.state].filter(Boolean).join(", ") || "Não informado"}</p>
                    <p className="mt-1 text-xs text-neutral-500">{item.candidate.neighborhood ?? item.candidate.address ?? ""}</p>
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top text-neutral-800">
                    <p>{item.candidate.whatsapp ?? item.candidate.phone ?? "Sem telefone"}</p>
                    <p className="mt-1 text-xs text-neutral-500">{domain ?? "Sem domínio"}</p>
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
                          Formulário
                        </a>
                      ) : null}
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1">
                      {item.enrichment?.email_found ? <OutcomeBadge tone="info">Email encontrado</OutcomeBadge> : null}
                      {item.enrichment?.instagram_found ? (
                        <OutcomeBadge tone="info">Instagram encontrado</OutcomeBadge>
                      ) : null}
                      {item.enrichment?.contact_form_found ? (
                        <OutcomeBadge tone="info">Formulário encontrado</OutcomeBadge>
                      ) : null}
                      {item.enrichment?.no_email_found ? (
                        <OutcomeBadge tone="muted">Sem email público</OutcomeBadge>
                      ) : null}
                      {item.enrichment?.skipped_reason === "No public website." ? (
                        <OutcomeBadge tone="warning">Sem site para enriquecer</OutcomeBadge>
                      ) : null}
                      {clientResultId && newlyBlockedIds[clientResultId] ? (
                        <OutcomeBadge tone="danger">Bloqueada após nova checagem</OutcomeBadge>
                      ) : null}
                    </div>
                    {item.enrichment?.error_message ? (
                      <p className="mt-2 max-w-xs text-xs text-rose-700">
                        {sanitizeUserFacingMessage(item.enrichment.error_message, "Falha ao enriquecer esta empresa.")}
                      </p>
                    ) : null}
                  </td>
                  <td className="border-b border-neutral-100 px-3 py-3 align-top">
                    {blocked ? (
                      <div>
                        <p className="font-medium text-rose-800">Bloqueada</p>
                        <p className="mt-1 max-w-xs text-xs text-rose-700">
                          {item.exclusion.reason ?? "Corresponde a uma regra de exclusão ativa."}
                        </p>
                      </div>
                    ) : (
                      <span className="inline-flex rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800">
                        Pronta para salvar
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
                        Bloquear empresa
                      </button>
                      <button
                        type="button"
                        disabled={actionDisabled || !domain}
                        onClick={() => onBlockDomain(item)}
                        className="rounded-md border border-neutral-300 bg-white px-3 py-2 text-xs font-medium text-neutral-800 hover:border-neutral-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Bloquear domínio
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })
          ) : (
            <tr>
              <td colSpan={6} className="px-4 py-10 text-center text-sm text-neutral-500">
                {emptyMessage}
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
          <p className="text-xs font-semibold uppercase text-cyan-700">Salvar em leads</p>
          <h2 className="mt-1 text-base font-semibold text-neutral-950">Salvar leads selecionados</h2>
          <p className="mt-1 text-sm text-neutral-500">
            Linhas bloqueadas são ignoradas automaticamente. Depois de salvar, o lote abre direto em Leads.
          </p>
        </div>
        <div className="grid gap-2 sm:grid-cols-[140px_180px]">
          <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-center">
            <p className="text-xs font-medium text-neutral-500">Selecionadas</p>
            <p className="mt-1 text-lg font-semibold text-neutral-950">{selectedCount.toLocaleString()}</p>
          </div>
          <button
            type="button"
            disabled={!preview || selectedCount === 0 || isSaving}
            onClick={onSave}
            className="rounded-md border border-neutral-900 bg-neutral-950 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? "Salvando..." : "Salvar selecionadas"}
          </button>
        </div>
      </div>

      {lastImport ? (
        <div className="mt-4 flex flex-col gap-3 rounded-md border border-emerald-200 bg-emerald-50 p-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-emerald-950">Lote {lastImport.batch_id} salvo</p>
            <p className="mt-1 text-sm text-emerald-800">
              {lastImport.created_leads} criado(s), {lastImport.updated_leads} atualizado(s) e {lastImport.skipped_blocked} ignorado(s).
            </p>
          </div>
          <Link
            href={`/leads?import_batch_id=${lastImport.batch_id}`}
            className="rounded-md border border-emerald-900 bg-emerald-900 px-4 py-2 text-center text-sm font-medium text-white"
          >
            Abrir lote salvo
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
          {isCompany ? "Bloquear empresa" : "Bloquear domínio"}
        </p>
        <h2 className="mt-1 text-lg font-semibold text-neutral-950">{draft.item.candidate.business_name}</h2>
        <p className="mt-1 text-sm text-neutral-500">
          Salve uma regra de exclusão ativa e aplique a checagem novamente nesta prévia.
        </p>

        <div className="mt-4 space-y-3">
          {isCompany ? (
            <label className="block">
              <span className="text-xs font-medium text-neutral-600">Tipo de regra</span>
              <select
                value={draft.ruleType}
                onChange={(event) =>
                  onChange({ ...draft, ruleType: event.target.value as "exact_name" | "business_name_contains" })
                }
                className="mt-1 w-full rounded-md border border-neutral-300 bg-white px-2 py-2 text-sm text-neutral-950"
              >
                <option value="exact_name">Nome exato da empresa</option>
                <option value="business_name_contains">Nome da empresa contém</option>
              </select>
            </label>
          ) : (
            <div className="rounded-md border border-neutral-200 bg-neutral-50 px-3 py-2 text-sm text-neutral-700">
              Regra por domínio
            </div>
          )}

          <TextField
            label="Padrão"
            value={draft.pattern}
            onChange={(value) => onChange({ ...draft, pattern: value })}
          />
          <TextField
            label="Motivo"
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
            Cancelar
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSaving || !draft.pattern.trim()}
            className="rounded-md border border-rose-900 bg-rose-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? "Salvando regra..." : "Salvar regra de bloqueio"}
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
      Bloqueada
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
  parsedQuery: ParsedDiscoveryQuery | null,
  context: DiscoveryRequestContext,
): { request: DiscoverySearchRequest } | { error: string } {
  const searchTerms = mergeDiscoveryTerms(parsedQuery?.searchTerms ?? [], resolveManualDiscoveryTerms(form, parsedQuery, context));
  if (searchTerms.length === 0) {
    return { error: "Digite uma busca como 'dentistas em São Paulo' ou adicione pelo menos um termo." };
  }

  const radiusM = clampNumber(form.radiusM, 100, 50000);
  const maxResultsPerTerm = clampNumber(form.maxResultsPerTerm, 1, 20);

  if (form.locationMode === "area") {
    const locationQuery = resolveAreaLocationQuery(form, parsedQuery, context);
    const baseLocation = locationQuery ?? "";
    if (!baseLocation) {
      return { error: "Informe uma cidade ou use uma busca como 'dentistas em São Paulo' antes de continuar." };
    }
    return {
      request: {
        raw_query: parsedQuery?.rawQuery ?? null,
        search_terms: searchTerms,
        location_query: baseLocation,
        radius_m: radiusM,
        max_results_per_term: maxResultsPerTerm,
      },
    };
  }

  const latitude = parseCoordinate(form.latitude);
  const longitude = parseCoordinate(form.longitude);
  if (latitude === null || longitude === null) {
    return { error: "Informe latitude e longitude antes de rodar a descoberta por coordenadas." };
  }

  return {
    request: {
      raw_query: parsedQuery?.rawQuery ?? null,
      search_terms: searchTerms,
      location_query: resolveCoordinateLocationQuery(form, parsedQuery, context),
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
    .map(normalizeFreeText)
    .filter((term) => {
      if (!term || seen.has(term.toLowerCase())) {
        return false;
      }
      seen.add(term.toLowerCase());
      return true;
    });
}

function mergeDiscoveryTerms(...groups: string[][]) {
  const seen = new Set<string>();
  return groups
    .flat()
    .map(normalizeFreeText)
    .filter((term) => {
      if (!term || seen.has(term.toLowerCase())) {
        return false;
      }
      seen.add(term.toLowerCase());
      return true;
    });
}

function resolveManualDiscoveryTerms(
  form: DiscoveryFormState,
  parsedQuery: ParsedDiscoveryQuery | null,
  context: DiscoveryRequestContext,
) {
  const manualTerms = parseDiscoveryTerms(form.selectedTerms, form.customTerms);
  if (manualTerms.length === 0 || !parsedQuery) {
    return manualTerms;
  }
  return context.manualTermsSequence >= context.queryCategorySequence ? manualTerms : [];
}

function resolveAreaLocationQuery(
  form: DiscoveryFormState,
  parsedQuery: ParsedDiscoveryQuery | null,
  context: DiscoveryRequestContext,
) {
  const manualLocation = buildManualAreaLocationQuery(form);
  if (!manualLocation) {
    return parsedQuery?.locationQuery ?? null;
  }
  if (!parsedQuery?.locationQuery) {
    return manualLocation;
  }
  return context.manualAreaLocationSequence >= context.queryLocationSequence ? manualLocation : parsedQuery.locationQuery;
}

function resolveCoordinateLocationQuery(
  form: DiscoveryFormState,
  parsedQuery: ParsedDiscoveryQuery | null,
  context: DiscoveryRequestContext,
) {
  const manualLocation = normalizeFreeText(form.locationLabel);
  if (!manualLocation) {
    return parsedQuery?.locationQuery ?? null;
  }
  if (!parsedQuery?.locationQuery) {
    return manualLocation;
  }
  return context.manualCoordinateLabelSequence >= context.queryLocationSequence
    ? manualLocation
    : parsedQuery.locationQuery;
}

function buildDiscoveryRequestPreviewSummary(
  form: DiscoveryFormState,
  parsedQuery: ParsedDiscoveryQuery | null,
  context: DiscoveryRequestContext,
): DiscoveryRequestPreviewSummary {
  const searchTerms = mergeDiscoveryTerms(
    parsedQuery?.searchTerms ?? [],
    resolveManualDiscoveryTerms(form, parsedQuery, context),
  );
  const radiusM = clampNumber(form.radiusM, 100, 50000);
  const maxResultsPerTerm = clampNumber(form.maxResultsPerTerm, 1, 20);

  if (form.locationMode === "area") {
    return {
      searchTerms,
      locationLabel: resolveAreaLocationQuery(form, parsedQuery, context),
      radiusM,
      maxResultsPerTerm,
      maxPotentialResults: searchTerms.length * maxResultsPerTerm,
    };
  }

  const latitude = parseCoordinate(form.latitude);
  const longitude = parseCoordinate(form.longitude);
  const coordinateLabel = resolveCoordinateLocationQuery(form, parsedQuery, context);
  const coordinateText =
    latitude !== null && longitude !== null ? `${latitude.toFixed(4)}, ${longitude.toFixed(4)}` : null;

  return {
    searchTerms,
    locationLabel: coordinateLabel ?? coordinateText,
    radiusM,
    maxResultsPerTerm,
    maxPotentialResults: searchTerms.length * maxResultsPerTerm,
  };
}

function buildDiscoverySummaryLine({
  primaryTerm,
  locationLabel,
  radiusM,
  maxResultsPerTerm,
}: {
  primaryTerm: string | null;
  locationLabel: string | null;
  radiusM: number;
  maxResultsPerTerm: number;
}) {
  const nicheLabel = primaryTerm ?? "defina o nicho";
  const locationText = locationLabel ? `em ${locationLabel}` : "sem região definida";
  return `Prévia: ${nicheLabel} ${locationText} · raio ${formatRadiusKm(radiusM)} · até ${maxResultsPerTerm.toLocaleString()} por termo`;
}

function buildDiscoveryRelatedTermsSummary(primaryTerm: string | null, searchTerms: string[]) {
  const normalizedPrimary = primaryTerm?.trim().toLowerCase() ?? null;
  const relatedTerms = searchTerms.filter((term, index) => {
    if (index === 0 && !normalizedPrimary) {
      return false;
    }
    return term.trim().toLowerCase() !== normalizedPrimary;
  });
  return relatedTerms.length ? relatedTerms.join(", ") : null;
}

function formatRadiusKm(radiusM: number) {
  const km = radiusM / 1000;
  return Number.isInteger(km)
    ? `${km.toLocaleString("pt-BR")} km`
    : `${km.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} km`;
}

function buildManualAreaLocationQuery(form: DiscoveryFormState) {
  return [form.neighborhood.trim(), form.city.trim(), form.postalCode.trim()].filter(Boolean).join(", ") || null;
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
    parts.push(`${response.summary.emails_found.toLocaleString()} email(s)`);
  }
  if (response.summary.instagrams_found) {
    parts.push(`${response.summary.instagrams_found.toLocaleString()} Instagram(s)`);
  }
  if (response.summary.contact_forms_found) {
    parts.push(`${response.summary.contact_forms_found.toLocaleString()} formulário(s)`);
  }

  let message = `Enriquecimento concluído em ${response.summary.processed.toLocaleString()} empresa(s) da prévia.`;
  if (parts.length) {
    message += ` Encontramos ${parts.join(", ")}.`;
  } else if (response.summary.no_email_found > 0) {
    message += " Nenhum novo email público foi encontrado nessas empresas.";
  } else {
    message += " Nenhum novo contato público foi encontrado.";
  }
  if (response.summary.skipped_no_website > 0) {
    message += ` ${response.summary.skipped_no_website.toLocaleString()} estavam sem site para enriquecer.`;
  }
  if (response.summary.blocked_after_enrichment > 0) {
    message += ` ${response.summary.blocked_after_enrichment.toLocaleString()} foram bloqueadas após a nova checagem de exclusões.`;
  }
  if (response.summary.errors > 0) {
    message += ` ${response.summary.errors.toLocaleString()} falharam durante o processo.`;
  }
  return message;
}

function buildPreviewReadyMessage({
  totalCount,
  websiteReadyCount,
  noWebsiteCount,
  recoverableNoWebsiteCount,
  duplicatesRemoved,
}: {
  totalCount: number;
  websiteReadyCount: number;
  noWebsiteCount: number;
  recoverableNoWebsiteCount: number;
  duplicatesRemoved: number;
}) {
  let message = `Prévia pronta. ${totalCount.toLocaleString()} empresa(s) encontradas: ${websiteReadyCount.toLocaleString()} com site ou domínio e ${noWebsiteCount.toLocaleString()} sem site.`;
  if (duplicatesRemoved > 0) {
    message += ` ${duplicatesRemoved.toLocaleString()} duplicata(s) removida(s) da prévia.`;
  }
  if (noWebsiteCount > 0 && recoverableNoWebsiteCount > 0) {
    message += ` ${recoverableNoWebsiteCount.toLocaleString()} sem site podem passar por recuperação agora.`;
  }
  return message;
}

function buildWebsiteRecoveryMessage(response: DiscoveryPreviewWebsiteRecoveryResponse) {
  let message = `Verificamos ${response.summary.processed.toLocaleString()} empresa(s) sem site em busca de um endereço recuperável.`;
  if (response.summary.recovered_count > 0) {
    message += ` Recuperamos ${response.summary.recovered_count.toLocaleString()} site(s) ou domínio(s).`;
  } else if (response.summary.no_website_found > 0) {
    message += " Nenhum site público foi recuperado a partir dos dados do provedor.";
  } else {
    message += " Nenhum novo detalhe de site foi recuperado.";
  }
  if (response.summary.skipped_missing_place_id > 0) {
    message += ` ${response.summary.skipped_missing_place_id.toLocaleString()} estavam sem place id recuperável.`;
  }
  if (response.summary.blocked_after_recovery > 0) {
    message += ` ${response.summary.blocked_after_recovery.toLocaleString()} foram bloqueadas após a nova checagem de exclusões.`;
  }
  if (response.summary.errors > 0) {
    message += ` ${response.summary.errors.toLocaleString()} falharam durante a recuperação.`;
  }
  return message;
}

function hasWebsiteForCandidate(candidate: DiscoveryLeadCandidate) {
  return Boolean(candidate.website || domainForCandidate(candidate));
}

function previewSearchTermsLabel(item: DiscoveryPreviewItem) {
  const terms = Array.from(new Set([...(item.matched_search_terms ?? []), item.search_term].filter(Boolean)));
  if (terms.length <= 1) {
    return `Busca: ${terms[0] ?? item.search_term}`;
  }
  return `Encontrada por ${terms.length.toLocaleString()} termos: ${terms.join(", ")}`;
}

function hasWebsiteRecoveryLookupId(item: DiscoveryPreviewItem) {
  if (item.candidate.google_place_id?.trim()) {
    return true;
  }
  if (item.provider_record_id?.trim()) {
    return true;
  }
  const rawId = item.raw_payload["id"];
  return typeof rawId === "string" && rawId.trim().length > 0;
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

function normalizeFreeText(value: string) {
  return value.replace(/\s+/g, " ").trim();
}

function normalizeDiscoveryKey(value: string | null | undefined) {
  const normalized = normalizeFreeText(value ?? "");
  return normalized ? normalized.toLocaleLowerCase("pt-BR") : null;
}

function queryCategoryKey(parsedQuery: ParsedDiscoveryQuery | null, rawQuery: string) {
  return normalizeDiscoveryKey(parsedQuery?.category ?? rawQuery);
}

function queryLocationKey(parsedQuery: ParsedDiscoveryQuery | null) {
  return normalizeDiscoveryKey(parsedQuery?.locationQuery);
}

function clampNumber(value: number, min: number, max: number) {
  if (!Number.isFinite(value)) {
    return min;
  }
  return Math.min(max, Math.max(min, Math.round(value)));
}

function errorMessage(error: unknown) {
  return formatUserFacingError(error, "Não foi possível concluir a busca.");
}
