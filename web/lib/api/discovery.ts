import { postJson } from "@/lib/api/client";
import type {
  DiscoveryImportRequest,
  DiscoveryImportResponse,
  DiscoveryPreviewEnrichmentRequest,
  DiscoveryPreviewEnrichmentResponse,
  DiscoveryPreviewResponse,
  DiscoverySearchRequest,
  ExclusionRuleCreateRequest,
  ExclusionRuleCreateResponse,
} from "@/lib/api/types";

export function previewDiscovery(request: DiscoverySearchRequest) {
  return postJson<DiscoveryPreviewResponse, DiscoverySearchRequest>("/discovery/preview", request);
}

export function evaluateDiscoveryExclusions(preview: DiscoveryPreviewResponse) {
  return postJson<DiscoveryPreviewResponse, { preview: DiscoveryPreviewResponse }>(
    "/discovery/evaluate-exclusions",
    { preview },
  );
}

export function importDiscoveryPreview(payload: DiscoveryImportRequest) {
  return postJson<DiscoveryImportResponse, DiscoveryImportRequest>("/discovery/import", payload);
}

export function enrichDiscoveryPreview(payload: DiscoveryPreviewEnrichmentRequest) {
  return postJson<DiscoveryPreviewEnrichmentResponse, DiscoveryPreviewEnrichmentRequest>(
    "/discovery/enrich-preview",
    payload,
  );
}

export function createExclusionRule(payload: ExclusionRuleCreateRequest) {
  return postJson<ExclusionRuleCreateResponse, ExclusionRuleCreateRequest>("/exclusion-rules", payload);
}
