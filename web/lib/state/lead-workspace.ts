import type { CompanySizeFit, LeadBlockedFilter, LeadStatus, TradeType } from "@/lib/api/types";

export type BooleanFilter = "any" | "yes" | "no";

export type QueueFilters = {
  city: string;
  state: string;
  status: LeadStatus | "";
  assignedSalesRepId: string;
  salesRegionId: string;
  marketSegmentId: string;
  marketSubsegmentId: string;
  companySizeFit: CompanySizeFit | "";
  tradeType: TradeType | "";
  hasAssignment: BooleanFilter;
  hasEmail: BooleanFilter;
  hasWhatsapp: BooleanFilter;
  hasInstagram: BooleanFilter;
  blocked: LeadBlockedFilter;
};

export const defaultQueueFilters: QueueFilters = {
  city: "",
  state: "",
  status: "",
  assignedSalesRepId: "",
  salesRegionId: "",
  marketSegmentId: "",
  marketSubsegmentId: "",
  companySizeFit: "",
  tradeType: "",
  hasAssignment: "any",
  hasEmail: "any",
  hasWhatsapp: "any",
  hasInstagram: "any",
  blocked: "exclude",
};

export function booleanFilterValue(value: BooleanFilter): boolean | undefined {
  if (value === "yes") {
    return true;
  }
  if (value === "no") {
    return false;
  }
  return undefined;
}

export function numericFilterValue(value: string): number | undefined {
  if (!value) {
    return undefined;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}
