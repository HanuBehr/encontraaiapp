import { getJson } from "@/lib/api/client";
import type { SettingsSummary } from "@/lib/api/types";

export function getSettingsSummary() {
  return getJson<SettingsSummary>("/settings/summary");
}
