import type { LeadDetail, LeadImportBatchResponse } from "@/lib/api/types";
import { getActiveLocale } from "@/lib/i18n/locale-session";

const STORAGE_PREFIX = "encontraai.demo.v3";

export function getDemoLeads(): LeadDetail[] {
  return readJson<LeadDetail[]>(storageKey("leads"), []);
}

export function saveDemoLeads(leads: LeadDetail[]) {
  writeJson(storageKey("leads"), leads);
}

export function getDemoImportBatches(): LeadImportBatchResponse[] {
  return readJson<LeadImportBatchResponse[]>(storageKey("importBatches"), []);
}

export function addDemoImportBatch(batch: LeadImportBatchResponse) {
  writeJson(storageKey("importBatches"), [batch, ...getDemoImportBatches()]);
}

export function nextDemoLeadId() {
  return Math.max(...getDemoLeads().map((lead) => lead.id), 100) + 1;
}

export function nextDemoBatchId() {
  return Math.max(...getDemoImportBatches().map((batch) => batch.id), 0) + 1;
}

function readJson<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") {
    return fallback;
  }
  const rawValue = window.sessionStorage.getItem(key);
  if (!rawValue) {
    return fallback;
  }
  try {
    return JSON.parse(rawValue) as T;
  } catch {
    return fallback;
  }
}

function writeJson(key: string, value: unknown) {
  if (typeof window === "undefined") {
    return;
  }
  window.sessionStorage.setItem(key, JSON.stringify(value));
}

function storageKey(kind: "leads" | "importBatches") {
  return `${STORAGE_PREFIX}.${getActiveLocale()}.${kind}`;
}
