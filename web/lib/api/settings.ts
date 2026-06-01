import { getJson } from "@/lib/api/client";
import type { SettingsSummary } from "@/lib/api/types";
import { getDemoSettingsSummary } from "@/lib/demo/settings";
import { isDemoMode } from "@/lib/demo/mode";

export function getSettingsSummary() {
  if (isDemoMode()) {
    return getDemoSettingsSummary();
  }
  return getJson<SettingsSummary>("/settings/summary");
}
