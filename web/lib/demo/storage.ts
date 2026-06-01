import type { LeadDetail, LeadImportBatchResponse } from "@/lib/api/types";
import { demoInitialImportBatch, demoSeedLeads } from "@/lib/demo/fixtures";

const LEADS_KEY = "encontraai.demo.leads";
const BATCHES_KEY = "encontraai.demo.importBatches";

export function getDemoLeads(): LeadDetail[] {
  return readJson<LeadDetail[]>(LEADS_KEY, demoSeedLeads);
}

export function saveDemoLeads(leads: LeadDetail[]) {
  writeJson(LEADS_KEY, leads);
}

export function getDemoImportBatches(): LeadImportBatchResponse[] {
  return readJson<LeadImportBatchResponse[]>(BATCHES_KEY, [demoInitialImportBatch]);
}

export function addDemoImportBatch(batch: LeadImportBatchResponse) {
  writeJson(BATCHES_KEY, [batch, ...getDemoImportBatches()]);
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
  const rawValue = window.localStorage.getItem(key);
  if (!rawValue) {
    writeJson(key, fallback);
    return fallback;
  }
  try {
    return JSON.parse(rawValue) as T;
  } catch {
    writeJson(key, fallback);
    return fallback;
  }
}

function writeJson(key: string, value: unknown) {
  if (typeof window === "undefined") {
    return;
  }
  window.localStorage.setItem(key, JSON.stringify(value));
}
