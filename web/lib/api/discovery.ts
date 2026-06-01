import { postJson } from "@/lib/api/client";
import {
  createDemoExclusionRule,
  enrichDemoDiscoveryPreview,
  evaluateDemoDiscoveryExclusions,
  importDemoDiscoveryPreview,
  previewDemoDiscovery,
  recoverDemoDiscoveryWebsites,
} from "@/lib/demo/discovery";
import { isDemoMode } from "@/lib/demo/mode";
import type {
  DiscoveryImportRequest,
  DiscoveryImportResponse,
  DiscoveryPreviewEnrichmentRequest,
  DiscoveryPreviewEnrichmentResponse,
  DiscoveryPreviewResponse,
  DiscoveryPreviewWebsiteRecoveryRequest,
  DiscoveryPreviewWebsiteRecoveryResponse,
  DiscoverySearchRequest,
  ExclusionRuleCreateRequest,
  ExclusionRuleCreateResponse,
} from "@/lib/api/types";

const DISCOVERY_PREVIEW_ENRICHMENT_BATCH_SIZE = 3;

export function previewDiscovery(request: DiscoverySearchRequest) {
  if (isDemoMode()) {
    return previewDemoDiscovery(request);
  }
  return postJson<DiscoveryPreviewResponse, DiscoverySearchRequest>("/discovery/preview", request);
}

export function evaluateDiscoveryExclusions(preview: DiscoveryPreviewResponse) {
  if (isDemoMode()) {
    return evaluateDemoDiscoveryExclusions(preview);
  }
  return postJson<DiscoveryPreviewResponse, { preview: DiscoveryPreviewResponse }>(
    "/discovery/evaluate-exclusions",
    { preview },
  );
}

export function importDiscoveryPreview(payload: DiscoveryImportRequest) {
  if (isDemoMode()) {
    return importDemoDiscoveryPreview(payload);
  }
  return postJson<DiscoveryImportResponse, DiscoveryImportRequest>("/discovery/import", payload);
}

export async function enrichDiscoveryPreview(payload: DiscoveryPreviewEnrichmentRequest) {
  if (isDemoMode()) {
    return enrichDemoDiscoveryPreview(payload);
  }
  const requestedIds = Array.from(new Set(payload.client_result_ids));
  if (requestedIds.length <= DISCOVERY_PREVIEW_ENRICHMENT_BATCH_SIZE) {
    return postJson<DiscoveryPreviewEnrichmentResponse, DiscoveryPreviewEnrichmentRequest>(
      "/discovery/enrich-preview",
      {
        ...payload,
        client_result_ids: requestedIds,
      },
    );
  }

  let currentPreview = payload.preview;
  let combinedResponse: DiscoveryPreviewEnrichmentResponse | null = null;

  for (const clientResultIds of chunkClientResultIds(requestedIds, DISCOVERY_PREVIEW_ENRICHMENT_BATCH_SIZE)) {
    const response = await postJson<DiscoveryPreviewEnrichmentResponse, DiscoveryPreviewEnrichmentRequest>(
      "/discovery/enrich-preview",
      {
        ...payload,
        preview: currentPreview,
        client_result_ids: clientResultIds,
      },
    );
    currentPreview = response.preview;
    combinedResponse = combinedResponse
      ? mergeEnrichmentResponses(combinedResponse, response)
      : response;
  }

  return (
    combinedResponse ?? {
      preview: payload.preview,
      summary: {
        requested: 0,
        processed: 0,
        success_count: 0,
        emails_found: 0,
        instagrams_found: 0,
        contact_forms_found: 0,
        no_email_found: 0,
        skipped_no_website: 0,
        blocked_after_enrichment: 0,
        errors: 0,
        error_messages: [],
      },
    }
  );
}

export function recoverDiscoveryWebsites(payload: DiscoveryPreviewWebsiteRecoveryRequest) {
  if (isDemoMode()) {
    return recoverDemoDiscoveryWebsites(payload);
  }
  return postJson<DiscoveryPreviewWebsiteRecoveryResponse, DiscoveryPreviewWebsiteRecoveryRequest>(
    "/discovery/recover-websites",
    payload,
  );
}

export function createExclusionRule(payload: ExclusionRuleCreateRequest) {
  if (isDemoMode()) {
    return createDemoExclusionRule(payload);
  }
  return postJson<ExclusionRuleCreateResponse, ExclusionRuleCreateRequest>("/exclusion-rules", payload);
}

function chunkClientResultIds(clientResultIds: string[], batchSize: number) {
  const chunks: string[][] = [];
  for (let index = 0; index < clientResultIds.length; index += batchSize) {
    chunks.push(clientResultIds.slice(index, index + batchSize));
  }
  return chunks;
}

function mergeEnrichmentResponses(
  current: DiscoveryPreviewEnrichmentResponse,
  next: DiscoveryPreviewEnrichmentResponse,
): DiscoveryPreviewEnrichmentResponse {
  return {
    preview: next.preview,
    summary: {
      requested: current.summary.requested + next.summary.requested,
      processed: current.summary.processed + next.summary.processed,
      success_count: current.summary.success_count + next.summary.success_count,
      emails_found: current.summary.emails_found + next.summary.emails_found,
      instagrams_found: current.summary.instagrams_found + next.summary.instagrams_found,
      contact_forms_found: current.summary.contact_forms_found + next.summary.contact_forms_found,
      no_email_found: current.summary.no_email_found + next.summary.no_email_found,
      skipped_no_website: current.summary.skipped_no_website + next.summary.skipped_no_website,
      blocked_after_enrichment:
        current.summary.blocked_after_enrichment + next.summary.blocked_after_enrichment,
      errors: current.summary.errors + next.summary.errors,
      error_messages: [...current.summary.error_messages, ...next.summary.error_messages],
    },
  };
}
