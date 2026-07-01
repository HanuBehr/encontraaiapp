"use client";

import { useMutation } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { type ReactNode, useMemo, useRef, useState } from "react";

import { GlassSelect } from "@/components/ui/GlassSelect";
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
} from "@/lib/ui/messages";
import { useI18n } from "@/lib/i18n/client";
import { formatNumber } from "@/lib/i18n/format";
import { isDemoMode } from "@/lib/demo/mode";
import { getDemoGuidedSearches, type DemoGuidedSearch } from "@/lib/demo/scenarios";
import type { Locale } from "@/lib/i18n/translations";

type LocationMode = "area" | "coordinates";
type WebsiteFilter = "all" | "has_website" | "no_website";
type AdvancedPanel = "location" | "terms" | null;

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

const localizedSearchTermGroups = {
  "pt-BR": [
    {
      category: "Saúde / Clínicas",
      terms: [
        "Clínica odontológica",
        "Clínica de estética",
        "Clínica médica",
        "Fisioterapia",
        "Laboratório de análises",
        "Ótica",
        "Farmácia de manipulação",
        "Consultório veterinário",
      ],
    },
    {
      category: "Alimentação / Hospitalidade",
      terms: [
        "Restaurante",
        "Cafeteria",
        "Padaria",
        "Hamburgueria",
        "Pizzaria",
        "Hotel",
        "Pousada",
        "Buffet para eventos",
      ],
    },
    {
      category: "Beleza / Bem-estar",
      terms: [
        "Salão de beleza",
        "Barbearia",
        "Spa urbano",
        "Academia",
        "Estúdio de pilates",
        "Clínica de massagem",
        "Centro de bem-estar",
      ],
    },
    {
      category: "Serviços locais",
      terms: [
        "Imobiliária",
        "Escola de idiomas",
        "Contabilidade",
        "Assistência técnica",
        "Autoescola",
        "Lavanderia",
        "Pet shop",
      ],
    },
    {
      category: "B2B / Operações",
      terms: [
        "Software house",
        "Agência de marketing",
        "Consultoria empresarial",
        "Transportadora",
        "Distribuidora",
        "Fornecedor industrial",
        "Empresa de logística",
      ],
    },
  ],
  en: [
    {
      category: "Healthcare / Clinics",
      terms: [
        "Dental clinic",
        "Aesthetic clinic",
        "Medical clinic",
        "Physical therapy",
        "Diagnostic lab",
        "Optical store",
        "Compounding pharmacy",
        "Veterinary clinic",
      ],
    },
    {
      category: "Food / Hospitality",
      terms: [
        "Restaurant",
        "Cafe",
        "Bakery",
        "Burger restaurant",
        "Pizza restaurant",
        "Hotel",
        "Guesthouse",
        "Event catering",
      ],
    },
    {
      category: "Beauty / Wellness",
      terms: [
        "Beauty salon",
        "Barbershop",
        "Urban spa",
        "Gym",
        "Pilates studio",
        "Massage clinic",
        "Wellness center",
      ],
    },
    {
      category: "Local services",
      terms: [
        "Real estate agency",
        "Language school",
        "Accounting firm",
        "Repair service",
        "Driving school",
        "Laundry service",
        "Pet shop",
      ],
    },
    {
      category: "B2B / Operations",
      terms: [
        "Software house",
        "Marketing agency",
        "Business consulting",
        "Transport company",
        "Distributor",
        "Industrial supplier",
        "Logistics company",
      ],
    },
  ],
} as const;
const ENRICH_VISIBLE_CONFIRMATION_THRESHOLD = 10;
const WEBSITE_RECOVERY_MAX_ROWS = 25;
const DISCOVERY_PREVIEW_ENRICHMENT_BATCH_SIZE = 3;

const DiscoveryPreviewTable = dynamic(
  () => import("@/components/discovery/DiscoveryPreviewTable").then((module) => module.DiscoveryPreviewTable),
  { loading: () => <PreviewTableFallback /> },
);

export function DiscoveryWorkspace() {
  const { locale, t } = useI18n();
  const searchTermGroups = localizedSearchTermGroups[locale];
  const demoMode = isDemoMode();
  const guidedDemoSearches = demoMode ? getDemoGuidedSearches(locale) : [];
  const [form, setForm] = useState<DiscoveryFormState>(defaultForm);
  const [searchRequest, setSearchRequest] = useState<DiscoverySearchRequest | null>(null);
  const [preview, setPreview] = useState<DiscoveryPreviewResponse | null>(null);
  const [blockedFilter, setBlockedFilter] = useState<LeadBlockedFilter>("exclude");
  const [hideExistingLeads, setHideExistingLeads] = useState(true);
  const [websiteFilter, setWebsiteFilter] = useState<WebsiteFilter>("all");
  const [selectedIds, setSelectedIds] = useState<Record<string, boolean>>({});
  const [newlyBlockedIds, setNewlyBlockedIds] = useState<Record<string, boolean>>({});
  const [blockDraft, setBlockDraft] = useState<BlockDraft | null>(null);
  const [lastImport, setLastImport] = useState<DiscoveryImportResponse | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [openAdvancedPanel, setOpenAdvancedPanel] = useState<AdvancedPanel>(null);
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
    const newItems = data.items.filter((item) => !item.is_existing_lead);
    const totalCount = newItems.length;
    const websiteReadyCount = newItems.filter((item) => hasWebsiteForCandidate(item.candidate)).length;
    const noWebsiteCount = Math.max(totalCount - websiteReadyCount, 0);
    const recoverableNoWebsiteCount = newItems.filter(
      (item) =>
        !item.exclusion.is_blocked &&
        !hasWebsiteForCandidate(item.candidate) &&
        hasWebsiteRecoveryLookupId(item),
    ).length;
    setPreview(data);
    setSelectedIds(selectAllSavable(data.items));
    setNewlyBlockedIds({});
    setLastImport(null);
    setPreviewError(null);
    setActionMessage(
      totalCount === 0 && data.existing_leads_hidden_count === 0
        ? demoMode ? t("discovery.demoUnsupported") : t("error.noDiscoveryResults")
        : buildPreviewReadyMessage({
            newCount: totalCount,
            websiteReadyCount,
            noWebsiteCount,
            recoverableNoWebsiteCount,
            duplicatesRemoved: data.duplicates_removed,
            existingLeadsHiddenCount: data.existing_leads_hidden_count,
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
      setSelectedIds((current) => pruneUnsavableSelection(current, response.preview.items));
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
      setSelectedIds((current) => pruneUnsavableSelection(current, response.preview.items));
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
      setSelectedIds((current) => pruneUnsavableSelection(current, nextPreview.items));
      setNewlyBlockedIds({});
      setBlockDraft(null);
      const blockedCount = response.reapply_summary?.blocked ?? 0;
      setActionMessage(
        locale === "en"
          ? `Rule saved. ${blockedCount.toLocaleString()} existing lead(s) were blocked.`
          : `Regra salva. ${blockedCount.toLocaleString()} lead(s) existente(s) foram bloqueados agora.`,
      );
    },
  });

  const importMutation = useMutation({
    mutationFn: importDiscoveryPreview,
    onSuccess: (response) => {
      setLastImport(response);
      const messageParts = [
        locale === "en"
          ? `Batch ${response.batch_id} saved. ${response.created_count} new lead(s) saved.`
          : `Lote ${response.batch_id} salvo. ${response.created_count} lead(s) novo(s) salvos.`,
      ];
      if (response.skipped_existing_count > 0) {
        messageParts.push(
          locale === "en"
            ? `${response.skipped_existing_count} already existed and were skipped.`
            : `${response.skipped_existing_count} já existiam e foram ignorados.`,
        );
      }
      if (response.skipped_blocked > 0) {
        messageParts.push(
          locale === "en"
            ? `${response.skipped_blocked} were skipped because they are blocked.`
            : `${response.skipped_blocked} foram ignorados por bloqueio.`,
        );
      }
      setActionMessage(messageParts.join(" "));
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
    const existingFiltered = hideExistingLeads
      ? blockedFiltered.filter((item) => !item.is_existing_lead)
      : blockedFiltered;

    if (websiteFilter === "has_website") {
      return existingFiltered.filter((item) => hasWebsiteForCandidate(item.candidate));
    }
    if (websiteFilter === "no_website") {
      return existingFiltered.filter((item) => !hasWebsiteForCandidate(item.candidate));
    }
    return existingFiltered;
  }, [blockedFilter, hideExistingLeads, preview?.items, websiteFilter]);

  const selectedPreviewIds = useMemo(() => {
    const selectedClientResultIds: string[] = [];
    const selectedEnrichableClientResultIds: string[] = [];
    const selectedNoWebsiteClientResultIds: string[] = [];
    const selectedRecoverableClientResultIds: string[] = [];

    for (const item of preview?.items ?? []) {
      const clientResultId = item.client_result_id;
      if (!clientResultId || !selectedIds[clientResultId] || !isSavablePreviewItem(item)) {
        continue;
      }
      selectedClientResultIds.push(clientResultId);
      if (hasWebsiteForCandidate(item.candidate)) {
        selectedEnrichableClientResultIds.push(clientResultId);
      } else {
        selectedNoWebsiteClientResultIds.push(clientResultId);
        if (hasWebsiteRecoveryLookupId(item)) {
          selectedRecoverableClientResultIds.push(clientResultId);
        }
      }
    }

    return {
      selectedClientResultIds,
      selectedEnrichableClientResultIds,
      selectedNoWebsiteClientResultIds,
      selectedRecoverableClientResultIds,
    };
  }, [preview?.items, selectedIds]);
  const {
    selectedClientResultIds,
    selectedEnrichableClientResultIds,
    selectedNoWebsiteClientResultIds,
    selectedRecoverableClientResultIds,
  } = selectedPreviewIds;

  const visiblePreviewIds = useMemo(() => {
    const visibleSelectableIds: string[] = [];
    const visibleEnrichableIds: string[] = [];
    for (const item of visibleItems) {
      const clientResultId = item.client_result_id;
      if (!clientResultId || !isSavablePreviewItem(item)) {
        continue;
      }
      visibleSelectableIds.push(clientResultId);
      if (hasWebsiteForCandidate(item.candidate)) {
        visibleEnrichableIds.push(clientResultId);
      }
    }
    return { visibleSelectableIds, visibleEnrichableIds };
  }, [visibleItems]);
  const { visibleSelectableIds, visibleEnrichableIds } = visiblePreviewIds;
  const allVisibleSelected =
    visibleSelectableIds.length > 0 && visibleSelectableIds.every((clientId) => selectedIds[clientId]);
  const previewStats = useMemo(() => {
    let previewCount = 0;
    let existingPreviewCount = 0;
    let blockedCount = 0;
    let websiteReadyCount = 0;
    for (const item of preview?.items ?? []) {
      if (item.is_existing_lead) {
        existingPreviewCount += 1;
      } else {
        previewCount += 1;
        if (hasWebsiteForCandidate(item.candidate)) {
          websiteReadyCount += 1;
        }
      }
      if (item.exclusion.is_blocked) {
        blockedCount += 1;
      }
    }
    return { previewCount, existingPreviewCount, blockedCount, websiteReadyCount };
  }, [preview?.items]);
  const { previewCount, existingPreviewCount, blockedCount, websiteReadyCount } = previewStats;
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

  function applyDemoMarket(search: DemoGuidedSearch) {
    const nextParsedQuery = parseNaturalLanguageDiscoveryQuery(search.query);
    if (queryCategoryKey(parsedNaturalLanguageQuery, form.naturalLanguageQuery) !== queryCategoryKey(nextParsedQuery, search.query)) {
      queryCategorySequenceRef.current = nextEditSequence();
    }
    if (queryLocationKey(parsedNaturalLanguageQuery) !== queryLocationKey(nextParsedQuery)) {
      queryLocationSequenceRef.current = nextEditSequence();
    }
    setForm((current) => ({
      ...current,
      naturalLanguageQuery: search.query,
      locationMode: "area",
      city: search.city,
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

  function resetDiscoveryForm() {
    setForm(defaultForm);
    setSearchRequest(null);
    setPreview(null);
    setSelectedIds({});
    setNewlyBlockedIds({});
    setLastImport(null);
    setFormError(null);
    setPreviewError(null);
    setActionMessage(null);
    editSequenceRef.current += 1;
    queryCategorySequenceRef.current = editSequenceRef.current;
    queryLocationSequenceRef.current = editSequenceRef.current;
    manualTermsSequenceRef.current = editSequenceRef.current;
    manualAreaLocationSequenceRef.current = editSequenceRef.current;
    manualCoordinateLabelSequenceRef.current = editSequenceRef.current;
  }

  const hasFormChanges =
    form.naturalLanguageQuery.trim() !== "" ||
    form.city.trim() !== "" ||
    form.neighborhood.trim() !== "" ||
    form.postalCode.trim() !== "" ||
    form.locationLabel.trim() !== "" ||
    form.latitude.trim() !== "" ||
    form.longitude.trim() !== "" ||
    form.locationMode !== defaultForm.locationMode ||
    form.radiusM !== defaultForm.radiusM ||
    form.maxResultsPerTerm !== defaultForm.maxResultsPerTerm ||
    form.selectedTerms.length > 0 ||
    form.customTerms.trim() !== "";
  const hasSearchActivity = Boolean(searchRequest || preview || isPreviewPending || previewError || actionMessage);
  const localizedBlockedOptions: Array<{ value: LeadBlockedFilter; label: string }> = [
    { value: "exclude", label: t("discovery.blockedHidden") },
    { value: "include", label: t("discovery.blockedInclude") },
    { value: "only", label: t("discovery.blockedOnly") },
  ];
  const localizedWebsiteOptions: Array<{ value: WebsiteFilter; label: string }> = [
    { value: "all", label: t("discovery.websiteAll") },
    { value: "has_website", label: t("discovery.websiteHas") },
    { value: "no_website", label: t("discovery.websiteMissing") },
  ];

  return (
    <div className="space-y-5 lg:max-w-[2200px]">
      <form onSubmit={runPreview} className="space-y-5">
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <p className="ea-kicker">{t("discovery.kicker")}</p>
              <h1 className="mt-1 text-3xl font-bold tracking-[-0.045em] text-brand-graphite sm:text-[2.35rem]">{t("discovery.title")}</h1>
            </div>
            {hasFormChanges ? (
              <button
                type="button"
                onClick={resetDiscoveryForm}
                className="ea-button-secondary self-start rounded-full px-3 py-1.5 text-xs font-semibold lg:self-auto"
              >
                {t("leads.clearFilters")}
              </button>
            ) : null}
          </div>

          <div className="relative z-30 overflow-visible rounded-[1.5rem] border border-brand-orchid/10 bg-white/[0.44] p-3 shadow-[0_12px_34px_rgba(29,22,48,0.07),inset_0_1px_0_rgba(255,255,255,0.58)] backdrop-blur-xl lg:p-3.5">
            <div className="space-y-2.5">
              <div className="grid gap-3 xl:grid-cols-[minmax(220px,0.72fr)_minmax(280px,1.15fr)_minmax(240px,0.9fr)_150px_180px] xl:items-end">
                <div className="block">
                  <span className="text-xs font-semibold uppercase tracking-[0.08em] text-brand-muted">{t("discovery.mode")}</span>
                  <div className="ea-card-flat mt-1.5 grid h-[50px] min-w-[15.5rem] grid-cols-2 p-0.5">
                    <ToggleButton active={form.locationMode === "area"} onClick={() => updateForm("locationMode", "area")}>{t("discovery.areaMode")}</ToggleButton>
                    <ToggleButton active={form.locationMode === "coordinates"} onClick={() => updateForm("locationMode", "coordinates")}>{t("discovery.coordinatesMode")}</ToggleButton>
                  </div>
                </div>

                <label className="block">
                  <span className="text-xs font-semibold uppercase tracking-[0.08em] text-brand-muted">{t("discovery.queryLabel")}</span>
                  <div className="relative mt-1.5">
                    <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-signal" />
                      <input
                        value={form.naturalLanguageQuery}
                        onChange={(event) => updateNaturalLanguageQuery(event.target.value)}
                        placeholder={t("discovery.queryPlaceholder")}
                        autoComplete="off"
                        className="ea-input h-[50px] w-full px-10 py-3 text-sm"
                      />
                  </div>
                </label>

                {form.locationMode === "area" ? (
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.08em] text-brand-muted">{t("discovery.cityLabel")}</span>
                    <div className="relative mt-1.5">
                      <LocationIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-brand-signal" />
                      <input
                        value={form.city}
                        onChange={(event) => updateAreaLocationField("city", event.target.value)}
                        placeholder={t("discovery.cityPlaceholder")}
                        autoComplete="off"
                        className="ea-input h-[50px] w-full px-10 py-3 text-sm"
                      />
                    </div>
                  </label>
                ) : (
                  <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.08em] text-brand-muted">{t("discovery.locationLabel")}</span>
                    <input
                      value={form.locationLabel}
                      onChange={(event) => updateCoordinateLabel(event.target.value)}
                      placeholder={t("discovery.locationLabelPlaceholder")}
                      autoComplete="off"
                      className="ea-input mt-1.5 h-[50px] w-full px-4 py-3 text-sm"
                    />
                  </label>
                )}
                <label className="block">
                    <span className="text-xs font-semibold uppercase tracking-[0.08em] text-brand-muted">{t("discovery.perTerm")}</span>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={form.maxResultsPerTerm}
                    onChange={(event) => updateForm("maxResultsPerTerm", Number(event.target.value))}
                    className="ea-input mt-1.5 h-[50px] w-full px-3 py-3 text-sm"
                    aria-label={t("discovery.maxResultsAria")}
                  />
                </label>
                <button type="submit" disabled={isPreviewPending} className="ea-button-primary flex h-[50px] w-full items-center justify-center px-5 text-sm font-bold disabled:cursor-not-allowed disabled:opacity-50">
                  {isPreviewPending ? `${t("common.search")}...` : t("discovery.title")}
                </button>
              </div>

              {guidedDemoSearches.length > 0 ? (
                <DemoMarketRail
                  activeQuery={form.naturalLanguageQuery}
                  markets={guidedDemoSearches}
                  onSelect={applyDemoMarket}
                />
              ) : null}

              <div className="flex flex-col gap-3 border-t border-brand-orchid/10 pt-2.5 lg:flex-row lg:items-start">
                <div className="relative min-w-0 flex-1">
                  <div className="grid gap-2 sm:grid-cols-2">
                    <AdvancedPanelTrigger
                      active={openAdvancedPanel === "location"}
                      label={form.locationMode === "area" ? t("discovery.addLocation") : t("discovery.coordinatesMode")}
                      onClick={() => setOpenAdvancedPanel((current) => (current === "location" ? null : "location"))}
                    />
                    <AdvancedPanelTrigger
                      active={openAdvancedPanel === "terms"}
                      count={optionalTermsCount > 0 ? formatNumber(optionalTermsCount, locale) : undefined}
                      label={t("discovery.termsTitle")}
                      onClick={() => setOpenAdvancedPanel((current) => (current === "terms" ? null : "terms"))}
                    />
                  </div>

                  <CollapsiblePanel open={openAdvancedPanel === "location"}>
                    {form.locationMode === "area" ? (
                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                        <TextField
                          label={t("discovery.neighborhood")}
                          value={form.neighborhood}
                          onChange={(value) => updateAreaLocationField("neighborhood", value)}
                          placeholder={t("common.optional")}
                        />
                        <TextField
                          label={t("discovery.postalCode")}
                          value={form.postalCode}
                          onChange={(value) => updateAreaLocationField("postalCode", value)}
                          placeholder={t("common.optional")}
                        />
                        <NumberField label={t("discovery.radius")} min={100} max={50000} value={form.radiusM} onChange={(value) => updateForm("radiusM", value)} />
                      </div>
                    ) : (
                      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                        <TextField label="Latitude" value={form.latitude} onChange={(value) => updateForm("latitude", value)} placeholder="-23.5505" />
                        <TextField label="Longitude" value={form.longitude} onChange={(value) => updateForm("longitude", value)} placeholder="-46.6333" />
                        <TextField label={t("discovery.locationLabel")} value={form.locationLabel} onChange={(value) => updateCoordinateLabel(value)} placeholder={t("common.optional")} />
                        <NumberField label={t("discovery.radius")} min={100} max={50000} value={form.radiusM} onChange={(value) => updateForm("radiusM", value)} />
                      </div>
                    )}
                  </CollapsiblePanel>

                  <CollapsiblePanel open={openAdvancedPanel === "terms"}>
                    <div className="space-y-3">
                      {searchTermGroups.map((group) => (
                        <section key={group.category}>
                          <h3 className="ea-kicker">{group.category}</h3>
                          <div className="mt-2 grid auto-rows-[3.5rem] gap-2 sm:grid-cols-2 xl:grid-cols-3">
                            {group.terms.map((term) => (
                              <label key={term} className="ea-card-flat flex h-full items-center gap-3 rounded-[1.05rem] px-3 text-sm text-brand-graphite transition hover:border-brand-orchid">
                                <input type="checkbox" checked={form.selectedTerms.includes(term)} onChange={() => toggleSearchTerm(term)} className="h-4 w-4 shrink-0 rounded border-neutral-300" />
                                <span className="leading-5">{term}</span>
                              </label>
                            ))}
                          </div>
                        </section>
                      ))}
                    </div>
                    <label className="mt-3 block">
                      <span className="text-xs font-semibold uppercase tracking-[0.08em] text-brand-muted">{t("discovery.termsTitle")}</span>
                      <textarea value={form.customTerms} onChange={(event) => updateCustomTerms(event.target.value)} placeholder={t("discovery.customTermsPlaceholder")} autoComplete="off" className="ea-input mt-2 min-h-24 w-full px-3 py-2 text-sm" />
                    </label>
                  </CollapsiblePanel>
                </div>
              </div>
            </div>
          </div>
        </div>

        {formError ? <InlineMessage tone="danger">{formError}</InlineMessage> : null}
        {previewError ? <InlineMessage tone="danger">{errorMessage(previewError, locale)}</InlineMessage> : null}

        <div className="relative z-10 rounded-[1.5rem] border border-brand-orchid/10 bg-white/[0.50] p-3.5 shadow-[0_12px_34px_rgba(29,22,48,0.07),inset_0_1px_0_rgba(255,255,255,0.58)] backdrop-blur-xl lg:p-4">
          {hasSearchActivity ? (
            <div>
              <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-base font-semibold text-brand-graphite">{t("discovery.previewTitle")}</p>
                    {preview ? <StatusPill label={locale === "en" ? "Results" : "Resultados"} value={formatNumber(previewCount, locale)} /> : null}
                    {preview && websiteReadyCount > 0 ? <StatusPill label={locale === "en" ? "With website" : "Com site"} value={formatNumber(websiteReadyCount, locale)} /> : null}
                    {preview && existingPreviewCount > 0 ? <StatusPill label={locale === "en" ? "Already saved" : "Já salvos"} value={formatNumber(existingPreviewCount, locale)} /> : null}
                  </div>
                  {!preview ? <p className="mt-1 text-sm leading-6 text-brand-muted">{t("discovery.previewWaiting")}</p> : null}
                </div>

                <div className="grid w-full gap-2 md:grid-cols-2 xl:w-auto xl:min-w-[520px] xl:grid-cols-[minmax(170px,0.9fr)_minmax(150px,0.8fr)_minmax(150px,0.8fr)] xl:items-end">
                  <label className="flex h-10 items-center gap-2 rounded-[0.95rem] border border-brand-orchid/10 bg-white/[0.32] px-3 text-sm text-brand-graphite">
                    <input
                      type="checkbox"
                      checked={hideExistingLeads}
                      onChange={(event) => setHideExistingLeads(event.target.checked)}
                      className="h-4 w-4 rounded border-neutral-300"
                    />
                    <span>{t("discovery.hideAlreadySaved")}</span>
                  </label>
                  <div className="block">
                    <span className="text-xs font-medium text-brand-muted">{t("discovery.blocking")}</span>
                    <GlassSelect
                      value={blockedFilter}
                      options={localizedBlockedOptions}
                      ariaLabel={t("discovery.blocking")}
                      className="mt-1"
                      onChange={(value) => setBlockedFilter(value as LeadBlockedFilter)}
                    />
                  </div>
                  <div className="block md:col-span-2 xl:col-span-1">
                    <span className="text-xs font-medium text-brand-muted">{t("discovery.websitePresence")}</span>
                    <GlassSelect
                      value={websiteFilter}
                      options={localizedWebsiteOptions}
                      ariaLabel={t("discovery.websitePresence")}
                      className="mt-1"
                      onChange={(value) => setWebsiteFilter(value as WebsiteFilter)}
                    />
                  </div>
                </div>
              </div>

              {preview ? (
                <div className="mt-3 flex flex-col gap-3 border-t border-brand-orchid/10 pt-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex flex-wrap gap-2 text-xs text-brand-muted">
                    {selectedClientResultIds.length > 0 ? <StatusPill label={locale === "en" ? "Selected" : "Selecionados"} value={formatNumber(selectedClientResultIds.length, locale)} /> : null}
                    {selectedEnrichableClientResultIds.length > 0 ? <StatusPill label={locale === "en" ? "Ready to enrich" : "Prontas para enriquecer"} value={formatNumber(selectedEnrichableClientResultIds.length, locale)} /> : null}
                    {selectedRecoverableClientResultIds.length > 0 ? <StatusPill label={locale === "en" ? "Website lookup" : "Busca de site"} value={formatNumber(selectedRecoverableClientResultIds.length, locale)} /> : null}
                    {blockedCount > 0 ? <StatusPill label={locale === "en" ? "Blocked" : "Bloqueadas"} value={formatNumber(blockedCount, locale)} /> : null}
                  </div>
                  <div className="flex flex-wrap gap-2 lg:justify-end">
                    {selectedClientResultIds.length > 0 ? (
                      <button
                        type="button"
                        disabled={importMutation.isPending}
                        onClick={saveSelected}
                        className="ea-button-primary px-3 py-2 text-xs font-bold disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {importMutation.isPending ? t("discovery.savingPending") : t("discovery.importSelected")}
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={selectedNoWebsiteClientResultIds.length === 0 || enrichMutation.isPending || recoverMutation.isPending}
                      onClick={recoverSelected}
                      className="ea-button-secondary px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {recoverMutation.isPending ? t("discovery.recoveryPending") : t("discovery.recoverWebsites")}
                    </button>
                    <button
                      type="button"
                      disabled={selectedEnrichableClientResultIds.length === 0 || enrichMutation.isPending || recoverMutation.isPending}
                      onClick={enrichSelected}
                      className="ea-button-secondary px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {enrichMutation.isPending ? t("discovery.enrichmentPending") : t("discovery.enrichSelected")}
                    </button>
                    <button
                      type="button"
                      disabled={visibleEnrichableIds.length === 0 || enrichMutation.isPending || recoverMutation.isPending}
                      onClick={enrichVisible}
                      className="ea-button-secondary px-3 py-2 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {t("discovery.enrichVisible")}
                    </button>
                  </div>
                </div>
              ) : null}

              {lastImport ? (
                <div className="mt-3 flex flex-col gap-2 rounded-2xl border border-brand-olive/20 bg-brand-olive/10 px-3 py-2 text-sm lg:flex-row lg:items-center lg:justify-between">
                  <p className="text-brand-muted">
                    <span className="font-semibold text-brand-graphite">
                      {locale === "en" ? `Batch ${lastImport.batch_id} saved.` : `Lote ${lastImport.batch_id} salvo.`}
                    </span>{" "}
                    {locale === "en"
                      ? `${lastImport.created_count} created, ${lastImport.skipped_existing_count} already existed, ${lastImport.skipped_blocked} skipped.`
                      : `${lastImport.created_count} criado(s), ${lastImport.skipped_existing_count} já existiam e ${lastImport.skipped_blocked} ignorado(s).`}
                  </p>
                  <Link href={`/leads?import_batch_id=${lastImport.batch_id}`} className="ea-button-primary inline-flex items-center justify-center px-3 py-2 text-sm font-bold">
                    {locale === "en" ? "Open saved batch" : "Abrir lote salvo"}
                  </Link>
                </div>
              ) : null}

              {actionMessage ? <InlineMessage tone="info">{actionMessage}</InlineMessage> : null}
              {recoverMutation.isError ? <InlineMessage tone="danger">{errorMessage(recoverMutation.error, locale)}</InlineMessage> : null}
              {enrichMutation.isError ? <InlineMessage tone="danger">{errorMessage(enrichMutation.error, locale)}</InlineMessage> : null}
              {blockMutation.isError ? <InlineMessage tone="danger">{errorMessage(blockMutation.error, locale)}</InlineMessage> : null}
              {importMutation.isError ? <InlineMessage tone="danger">{errorMessage(importMutation.error, locale)}</InlineMessage> : null}
              {isPreviewPending ? (
                <PreviewSkeleton />
              ) : preview ? (
                <DiscoveryPreviewTable
                  items={visibleItems}
                  emptyMessage={buildPreviewEmptyMessage({
                    preview,
                    hideExistingLeads,
                    blockedFilter,
                    websiteFilter,
                    locale,
                    demoMode,
                  })}
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
                <EmptyResultsScaffold
                  title={t("discovery.noResultsTitle")}
                  description={locale === "en" ? "Try another niche, city, or related terms." : "Teste outro nicho, cidade ou termos relacionados."}
                />
              )}
            </div>
          ) : (
            <div>
              <p className="text-sm font-semibold text-brand-graphite">{t("discovery.previewTitle")}</p>
              <EmptyResultsScaffold
                title={t("discovery.startTitle")}
                description={locale === "en" ? "Found companies will appear here for review and selection." : "As empresas encontradas aparecerão aqui para revisão e seleção."}
              />
            </div>
          )}
        </div>
      </form>

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

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <circle cx="11" cy="11" r="7" />
      <path d="m16.5 16.5 3.5 3.5" />
    </svg>
  );
}

function LocationIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden="true">
      <path d="M12 21s7-5.2 7-11a7 7 0 1 0-14 0c0 5.8 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.5" />
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

function PreviewSkeleton() {
  const { locale } = useI18n();
  return (
    <div className="ea-card-flat mt-4 p-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-brand-graphite">{locale === "en" ? "Generating preview" : "Gerando prévia"}</p>
          <p className="mt-1 text-sm text-brand-muted">{locale === "en" ? "Querying providers and consolidating duplicates." : "Consultando provedores e consolidando duplicatas."}</p>
        </div>
        <div className="ea-card-flat h-9 w-9 rounded-full" />
      </div>
      <div className="mt-5 space-y-3">
        {[0, 1, 2].map((item) => (
          <div key={item} className="ea-card-flat grid gap-3 p-3 md:grid-cols-[1.4fr_0.9fr_0.9fr_120px]">
            <div className="space-y-2">
              <div className="ea-skeleton h-4 w-44 rounded-full" />
              <div className="ea-skeleton h-3 w-28 rounded-full" />
            </div>
            <div className="ea-skeleton h-4 rounded-full" />
            <div className="ea-skeleton h-4 rounded-full" />
            <div className="ea-skeleton h-9 rounded-xl" />
          </div>
        ))}
      </div>
    </div>
  );
}

function EmptyResultsScaffold({ title, description }: { title: string; description: string }) {
  const { t } = useI18n();
  const rows = [t("common.company"), t("leads.city"), t("common.contact"), t("common.status")];

  return (
    <div className="ea-card-flat mt-3 overflow-hidden border-dashed">
      <div className="px-4 py-4 text-center">
        <p className="text-sm font-bold text-brand-graphite">{title}</p>
        <p className="mx-auto mt-1 max-w-xl text-sm leading-6 text-brand-muted">{description}</p>
      </div>
      <div className="overflow-x-auto border-t border-brand-mist/60 px-3 pb-3 pt-2">
        <div className="min-w-[620px]">
          <div className="grid grid-cols-[1.2fr_0.8fr_0.8fr_96px] gap-3 rounded-t-xl border-b border-brand-mist/70 px-3 py-2 text-[11px] font-bold uppercase tracking-[0.08em] text-brand-muted">
            {rows.map((row) => (
              <span key={row}>{row}</span>
            ))}
          </div>
          {[0, 1, 2].map((row) => (
            <div key={row} className="grid grid-cols-[1.2fr_0.8fr_0.8fr_96px] gap-3 border-b border-brand-mist/50 px-3 py-3 last:border-b-0">
              <div className="space-y-2">
                <div className="h-3 w-36 rounded-full bg-brand-mist/70" />
                <div className="h-2.5 w-24 rounded-full bg-brand-mist/45" />
              </div>
              <div className="h-3 w-24 rounded-full bg-brand-mist/55" />
              <div className="h-3 w-28 rounded-full bg-brand-mist/55" />
              <div className="ea-card-flat h-6 rounded-full" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function PreviewTableFallback() {
  const { t } = useI18n();
  return (
    <div className="ea-card-flat mt-4 px-4 py-6">
      <p className="text-sm font-semibold text-brand-graphite">{t("discovery.loadingPreviewTable")}</p>
      <div className="mt-4 space-y-3">
        {[0, 1, 2].map((row) => (
          <div key={row} className="ea-card-flat grid gap-3 p-3 md:grid-cols-[1.2fr_0.8fr_0.8fr_120px]">
            <div className="ea-skeleton h-4 rounded-full" />
            <div className="ea-skeleton h-4 rounded-full" />
            <div className="ea-skeleton h-4 rounded-full" />
            <div className="ea-skeleton h-8 rounded-xl" />
          </div>
        ))}
      </div>
    </div>
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
  const { locale, t } = useI18n();
  const isCompany = draft.mode === "company";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-brand-graphite/45 px-4 py-6 backdrop-blur-sm">
      <div className="ea-card w-full max-w-lg p-5">
        <p className="ea-kicker">
          {isCompany ? t("common.blockCompany") : t("common.blockDomain")}
        </p>
        <h2 className="mt-2 text-lg font-semibold text-brand-graphite">{draft.item.candidate.business_name}</h2>
        <p className="mt-1 text-sm text-brand-muted">
          {locale === "en" ? "Save an active exclusion rule and re-run the check on this preview." : "Salve uma regra de exclusão ativa e aplique a checagem novamente nesta prévia."}
        </p>

        <div className="mt-4 space-y-3">
          {isCompany ? (
            <div className="block">
              <span className="text-xs font-medium text-neutral-600">{locale === "en" ? "Rule type" : "Tipo de regra"}</span>
              <GlassSelect
                value={draft.ruleType}
                options={[
                  { value: "exact_name", label: locale === "en" ? "Exact company name" : "Nome exato da empresa" },
                  { value: "business_name_contains", label: locale === "en" ? "Company name contains" : "Nome da empresa contém" },
                ]}
                ariaLabel={locale === "en" ? "Rule type" : "Tipo de regra"}
                className="mt-1"
                onChange={(value) => onChange({ ...draft, ruleType: value as "exact_name" | "business_name_contains" })}
              />
            </div>
          ) : (
            <div className="ea-card-flat px-3 py-2 text-sm text-brand-muted">
              {locale === "en" ? "Domain rule" : "Regra por domínio"}
            </div>
          )}

          <TextField
            label={locale === "en" ? "Pattern" : "Padrão"}
            value={draft.pattern}
            onChange={(value) => onChange({ ...draft, pattern: value })}
          />
          <TextField
            label={locale === "en" ? "Reason" : "Motivo"}
            value={draft.reason}
            onChange={(value) => onChange({ ...draft, reason: value })}
          />
        </div>

        <div className="mt-5 grid gap-2 sm:grid-cols-2">
          <button
            type="button"
            onClick={onCancel}
            disabled={isSaving}
            className="ea-button-secondary px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("common.cancel")}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={isSaving || !draft.pattern.trim()}
            className="rounded-md border border-rose-900 bg-rose-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? (locale === "en" ? "Saving rule..." : "Salvando regra...") : (locale === "en" ? "Save block rule" : "Salvar regra de bloqueio")}
          </button>
        </div>
      </div>
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
      <span className="text-xs font-semibold uppercase tracking-[0.08em] text-brand-muted">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        className="ea-input mt-1.5 h-10 w-full px-3 py-2 text-sm"
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
      <span className="text-xs font-semibold uppercase tracking-[0.08em] text-brand-muted">{label}</span>
      <input
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="ea-input mt-1.5 h-10 w-full px-3 py-2 text-sm"
      />
    </label>
  );
}

function DemoMarketRail({
  activeQuery,
  markets,
  onSelect,
}: {
  activeQuery: string;
  markets: DemoGuidedSearch[];
  onSelect: (search: DemoGuidedSearch) => void;
}) {
  const { t } = useI18n();
  const normalizedActiveQuery = activeQuery.trim().toLowerCase();

  return (
    <section className="flex items-center gap-2 px-1 text-xs">
      <div className="flex shrink-0 items-center gap-1.5 text-brand-muted">
        <span className="text-[0.68rem] font-black uppercase tracking-[0.13em]">{t("discovery.demoMarketsTitle")}</span>
        <span className="text-brand-muted/60" aria-hidden="true">/</span>
      </div>
      <div className="ea-scroll-panel flex min-w-0 flex-1 gap-1 overflow-x-auto py-0.5">
        {markets.map((market) => {
          const active = normalizedActiveQuery === market.query.toLowerCase();
          return (
            <button
              key={market.query}
              type="button"
              onClick={() => onSelect(market)}
              title={`${market.label}: ${market.description}`}
              className={`shrink-0 rounded-full border px-2.5 py-1 text-[0.72rem] font-bold transition ${
                active
                  ? "border-brand-orchid/38 bg-brand-orchid/[0.08] text-brand-graphite"
                  : "border-transparent text-brand-muted hover:border-brand-orchid/16 hover:bg-brand-orchid/[0.05] hover:text-brand-graphite"
              }`}
            >
              {market.label}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function AdvancedPanelTrigger({
  active,
  count,
  label,
  onClick,
}: {
  active: boolean;
  count?: string;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      aria-expanded={active}
      onClick={onClick}
      className={`ea-card-flat flex h-10 items-center justify-between gap-3 px-3 text-left text-xs font-bold text-brand-graphite transition hover:border-brand-orchid ${
        active ? "border-brand-orchid/32 bg-brand-orchid/[0.07] shadow-[inset_0_1px_0_rgba(255,255,255,0.62),0_10px_24px_rgba(109,40,217,0.10)]" : ""
      }`}
    >
      <span className="min-w-0 truncate">{label}</span>
      <span className="flex shrink-0 items-center gap-2 text-brand-muted">
        {count ? <span className="font-semibold">{count}</span> : null}
        <ChevronIcon className={`h-4 w-4 text-brand-signal transition ${active ? "rotate-180" : ""}`} />
      </span>
    </button>
  );
}

function StatusPill({ label, value }: { label: string; value: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-orchid/10 bg-brand-orchid/[0.055] px-2.5 py-1 font-semibold text-brand-muted">
      <span>{label}</span>
      <span className="font-bold text-brand-graphite">{value}</span>
    </span>
  );
}

function CollapsiblePanel({ children, open }: { children: ReactNode; open: boolean }) {
  return (
    <div
      className={`absolute inset-x-0 top-[calc(100%+1.5rem)] z-30 px-0.5 transition-[opacity,transform] duration-200 ease-out sm:px-1 ${
        open ? "pointer-events-auto translate-y-0 opacity-100" : "pointer-events-none -translate-y-1 opacity-0"
      }`}
    >
      <div className="ea-card ea-scroll-panel isolate max-h-[min(31rem,48vh)] overflow-y-auto overscroll-contain rounded-[1.25rem] bg-white/[0.72] p-3.5 shadow-[0_16px_42px_rgba(47,38,61,0.10),inset_0_1px_0_rgba(255,255,255,0.58)] backdrop-blur-[44px]">
        {children}
      </div>
    </div>
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
          ? "whitespace-nowrap rounded-[12px] border border-brand-signal bg-brand-orchid/[0.08] px-3 py-1.5 text-xs font-bold text-brand-graphite shadow-[0_8px_20px_rgba(124,58,237,0.14)]"
          : "whitespace-nowrap rounded-[12px] border border-transparent px-3 py-1.5 text-xs font-semibold text-brand-muted transition hover:bg-brand-orchid/[0.07] hover:text-brand-graphite"
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
      : "mt-3 rounded-2xl border border-brand-olive/20 bg-brand-olive/10 px-3 py-2 text-sm text-brand-graphite";
  return <p className={className}>{children}</p>;
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

function buildManualAreaLocationQuery(form: DiscoveryFormState) {
  return [form.neighborhood.trim(), form.city.trim(), form.postalCode.trim()].filter(Boolean).join(", ") || null;
}

function selectAllSavable(items: DiscoveryPreviewItem[]) {
  return items.reduce<Record<string, boolean>>((selection, item) => {
    if (item.client_result_id && isSavablePreviewItem(item)) {
      selection[item.client_result_id] = true;
    }
    return selection;
  }, {});
}

function pruneUnsavableSelection(selection: Record<string, boolean>, items: DiscoveryPreviewItem[]) {
  const allowedIds = new Set(
    items.filter((item) => item.client_result_id && isSavablePreviewItem(item)).map((item) => item.client_result_id),
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
  newCount,
  websiteReadyCount,
  noWebsiteCount,
  recoverableNoWebsiteCount,
  duplicatesRemoved,
  existingLeadsHiddenCount,
}: {
  newCount: number;
  websiteReadyCount: number;
  noWebsiteCount: number;
  recoverableNoWebsiteCount: number;
  duplicatesRemoved: number;
  existingLeadsHiddenCount: number;
}) {
  let message = `Prévia pronta. ${newCount.toLocaleString()} empresa(s) nova(s) encontradas: ${websiteReadyCount.toLocaleString()} com site ou domínio e ${noWebsiteCount.toLocaleString()} sem site.`;
  if (duplicatesRemoved > 0) {
    message += ` ${duplicatesRemoved.toLocaleString()} duplicata(s) removida(s) da prévia.`;
  }
  if (existingLeadsHiddenCount > 0) {
    message += ` ${existingLeadsHiddenCount.toLocaleString()} empresa(s) já salvas ocultadas.`;
  }
  if (noWebsiteCount > 0 && recoverableNoWebsiteCount > 0) {
    message += ` ${recoverableNoWebsiteCount.toLocaleString()} sem site podem passar por recuperação agora.`;
  }
  return message;
}

function buildPreviewEmptyMessage({
  preview,
  hideExistingLeads,
  blockedFilter,
  websiteFilter,
  locale,
  demoMode,
}: {
  preview: DiscoveryPreviewResponse;
  hideExistingLeads: boolean;
  blockedFilter: LeadBlockedFilter;
  websiteFilter: WebsiteFilter;
  locale: Locale;
  demoMode: boolean;
}) {
  if ((preview.items?.length ?? 0) === 0) {
    if (demoMode) {
      return locale === "en"
        ? "This demo uses curated sample markets. Pick one of the demo markets above."
        : "Este demo usa mercados curados com dados fictícios. Escolha um dos mercados do demo acima.";
    }
    return locale === "en"
      ? "No companies found for this search. Try another niche, city, or radius."
      : "Nenhuma empresa encontrada para essa busca. Tente outro nicho, cidade ou raio.";
  }
  if (hideExistingLeads && preview.items.every((item) => item.is_existing_lead || item.exclusion.is_blocked)) {
    return locale === "en"
      ? "All companies in this search were already saved or blocked. Disable 'Hide already saved' to review them anyway."
      : "Todas as empresas desta busca já estavam salvas ou bloqueadas. Desative 'Ocultar já salvos' para revisar mesmo assim.";
  }
  if (hideExistingLeads && preview.existing_leads_hidden_count > 0) {
    return locale === "en"
      ? "No new companies match the current filters. Disable 'Hide already saved' to review previously found companies."
      : "Nenhuma empresa nova corresponde aos filtros atuais. Desative 'Ocultar já salvos' para revisar empresas encontradas antes.";
  }
  if (blockedFilter !== "include" || websiteFilter !== "all") {
    return locale === "en"
      ? "No companies match the current blocking and website filters."
      : "Nenhuma empresa corresponde aos filtros atuais de bloqueio e site.";
  }
  return locale === "en" ? "No companies available for this preview." : "Nenhuma empresa disponível para esta prévia.";
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

function isSavablePreviewItem(item: DiscoveryPreviewItem) {
  return !item.exclusion.is_blocked && !item.is_existing_lead;
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

function errorMessage(error: unknown, locale: Locale) {
  return formatUserFacingError(error, "Não foi possível concluir a busca.", locale);
}
