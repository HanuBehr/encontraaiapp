"use client";

import {
  flexRender,
  getCoreRowModel,
  type ColumnDef,
  type OnChangeFn,
  type RowSelectionState,
  type SortingState,
  useReactTable,
} from "@tanstack/react-table";
import { useMemo } from "react";

import { GlassSelect } from "@/components/ui/GlassSelect";
import { formatLeadLabel } from "@/lib/format/lead-labels";
import type { LeadSummary } from "@/lib/api/types";
import { useI18n } from "@/lib/i18n/client";
import { formatDate as formatLocalizedDate, formatNumber } from "@/lib/i18n/format";

type LeadQueueTableProps = {
  leads: LeadSummary[];
  total: number;
  pageIndex: number;
  pageSize: number;
  sorting: SortingState;
  rowSelection: RowSelectionState;
  activeLeadId: number | null;
  isLoading: boolean;
  onSortingChange: OnChangeFn<SortingState>;
  onRowSelectionChange: OnChangeFn<RowSelectionState>;
  onActivateLead: (leadId: number) => void;
  onPageChange: (pageIndex: number) => void;
  onPageSizeChange: (pageSize: number) => void;
};

export function LeadQueueTable({
  leads,
  total,
  pageIndex,
  pageSize,
  sorting,
  rowSelection,
  activeLeadId,
  isLoading,
  onSortingChange,
  onRowSelectionChange,
  onActivateLead,
  onPageChange,
  onPageSizeChange,
}: LeadQueueTableProps) {
  const { locale, t } = useI18n();
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const pageSizeOptions = [10, 25, 50, 100].map((size) => ({ value: String(size), label: String(size) }));
  const columns = useMemo<ColumnDef<LeadSummary>[]>(
    () => [
      {
        id: "select",
        enableSorting: false,
        header: ({ table }) => (
          <input
            type="checkbox"
            aria-label={t("common.selected")}
            checked={table.getIsAllPageRowsSelected()}
            onChange={table.getToggleAllPageRowsSelectedHandler()}
            className="h-4 w-4 rounded border-neutral-300"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            aria-label={`${t("common.selected")} ${row.original.business_name}`}
            checked={row.getIsSelected()}
            onClick={(event) => event.stopPropagation()}
            onChange={row.getToggleSelectedHandler()}
            className="h-4 w-4 rounded border-neutral-300"
          />
        ),
      },
      {
        accessorKey: "business_name",
        header: ({ column }) => <SortHeader column={column} label={t("common.company")} />,
        cell: ({ row }) => (
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium text-neutral-950">{row.original.business_name}</p>
              {row.original.is_blocked ? <BlockedBadge /> : null}
            </div>
            <p className="text-xs text-neutral-500">{row.original.category ?? t("common.noCategory")}</p>
            {row.original.is_blocked ? (
              <p className="mt-1 line-clamp-2 text-xs text-rose-700">
                {locale === "en" ? "Reason" : "Motivo"}: {row.original.blocked_reason ?? (locale === "en" ? "Matches an active exclusion rule." : "Corresponde a uma regra de exclusão ativa.")}
              </p>
            ) : null}
          </div>
        ),
      },
      {
        accessorKey: "city",
        header: ({ column }) => <SortHeader column={column} label={t("common.location")} />,
        cell: ({ row }) => (
          <span>
            {[row.original.city, row.original.state].filter(Boolean).join(", ") || t("common.notInformed")}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: ({ column }) => <SortHeader column={column} label={t("common.status")} />,
        cell: ({ getValue }) => <Badge>{formatLeadLabel(String(getValue()), locale)}</Badge>,
      },
      {
        id: "assignment",
        enableSorting: false,
        header: t("leads.assignee"),
        cell: ({ row }) => (
          <div>
            <p>{row.original.assigned_sales_rep?.name ?? t("leads.withoutAssignee")}</p>
            <p className="text-xs text-neutral-500">{row.original.sales_region?.name ?? t("leads.noRegion")}</p>
          </div>
        ),
      },
      {
        accessorKey: "company_size_fit",
        header: ({ column }) => <SortHeader column={column} label={t("common.profile")} />,
        cell: ({ row }) => (
          <div>
            <p>{formatLeadLabel(row.original.company_size_fit, locale)}</p>
            <p className="text-xs text-neutral-500">{formatLeadLabel(row.original.trade_type, locale)}</p>
          </div>
        ),
      },
      {
        id: "contacts",
        enableSorting: false,
        header: t("common.channels"),
        cell: ({ row }) => (
          <div className="flex items-center gap-2 whitespace-nowrap">
            <ContactPill active={Boolean(row.original.email)} channel="email" label="Email" />
            <ContactPill active={Boolean(row.original.whatsapp)} channel="whatsapp" label="WhatsApp" />
            <ContactPill active={Boolean(row.original.instagram)} channel="instagram" label="Instagram" />
          </div>
        ),
      },
      {
        accessorKey: "lead_score",
        header: ({ column }) => <SortHeader column={column} label={t("common.score")} />,
        cell: ({ getValue }) => <span className="inline-flex h-6 items-center font-semibold">{String(getValue())}</span>,
      },
      {
        accessorKey: "updated_at",
        header: ({ column }) => <SortHeader column={column} label={t("common.updated")} />,
        cell: ({ getValue }) => <span>{formatLocalizedDate(String(getValue()), locale)}</span>,
      },
    ],
    [locale, t],
  );

  const table = useReactTable({
    data: leads,
    columns,
    getRowId: (row) => String(row.id),
    state: {
      sorting,
      rowSelection,
    },
    enableRowSelection: true,
    manualSorting: true,
    onSortingChange,
    onRowSelectionChange,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <section className="overflow-hidden rounded-[1.5rem] border border-brand-orchid/10 bg-white/[0.58] shadow-[0_14px_38px_rgba(29,22,48,0.08),inset_0_1px_0_rgba(255,255,255,0.62)] backdrop-blur-xl">
      <div className="flex flex-col gap-3 border-b border-brand-mist/80 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-brand-graphite">{t("leads.listTitle")}</h2>
          <p className="text-sm text-brand-muted">
            {isLoading ? t("leads.loadingList") : t("leads.inCurrentList", { count: formatNumber(total, locale) })}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-brand-muted">
          <span>{t("common.rows")}</span>
          <GlassSelect
            value={String(pageSize)}
            options={pageSizeOptions}
            ariaLabel={t("common.rowsPerPage")}
            className="w-20"
            onChange={(value) => onPageSizeChange(Number(value))}
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
          <thead className="bg-white/[0.34] text-xs font-semibold uppercase tracking-wide text-brand-muted">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="border-b border-brand-orchid/10 px-3 py-3">
                    {header.isPlaceholder ? null : flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.length ? (
              table.getRowModel().rows.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => onActivateLead(row.original.id)}
                  className={
                    row.original.id === activeLeadId
                      ? "cursor-pointer bg-brand-orchid/[0.11]"
                      : "cursor-pointer bg-white/[0.14] hover:bg-brand-orchid/[0.07]"
                  }
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="border-b border-brand-orchid/[0.08] px-3 py-3 align-top text-neutral-800">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-neutral-500">
                  {t("leads.noFiltered")}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-brand-muted">
          {t("common.page")} {formatNumber(pageIndex + 1, locale)} {t("common.of")} {formatNumber(pageCount, locale)}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={pageIndex === 0}
            onClick={() => onPageChange(Math.max(0, pageIndex - 1))}
            className="ea-button-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("common.previous")}
          </button>
          <button
            type="button"
            disabled={pageIndex + 1 >= pageCount}
            onClick={() => onPageChange(Math.min(pageCount - 1, pageIndex + 1))}
            className="ea-button-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("common.next")}
          </button>
        </div>
      </div>
    </section>
  );
}

type SortHeaderProps = {
  column: {
    getCanSort: () => boolean;
    getIsSorted: () => false | "asc" | "desc";
    getToggleSortingHandler: () => ((event: unknown) => void) | undefined;
  };
  label: string;
};

function SortHeader({ column, label }: SortHeaderProps) {
  const sorted = column.getIsSorted();
  const marker = sorted === "asc" ? "Up" : sorted === "desc" ? "Down" : "";
  return (
    <button
      type="button"
      disabled={!column.getCanSort()}
      onClick={column.getToggleSortingHandler()}
      className="flex items-center gap-1 font-semibold uppercase text-brand-muted disabled:cursor-default"
    >
      <span>{label}</span>
      {marker ? <span className="text-[10px] text-brand-signal">{marker}</span> : null}
    </button>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex rounded-md border border-brand-olive/70 bg-brand-olive/20 px-2 py-1 text-xs font-medium text-brand-graphite">
      {children}
    </span>
  );
}

function BlockedBadge() {
  const { t } = useI18n();
  return (
    <span className="inline-flex rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-800">
      {t("common.blocked")}
    </span>
  );
}

function ContactPill({ active, channel, label }: { active: boolean; channel: "email" | "whatsapp" | "instagram"; label: string }) {
  return (
    <span
      aria-label={label}
      title={label}
      className={
        active
          ? "inline-flex h-6 w-6 items-center justify-center"
          : "inline-flex h-6 w-6 items-center justify-center opacity-45"
      }
    >
      {channel === "email" ? <EmailIcon active={active} className="h-[21px] w-[21px]" /> : null}
      {channel === "whatsapp" ? <WhatsAppIcon active={active} className="h-[21px] w-[21px]" /> : null}
      {channel === "instagram" ? <InstagramIcon active={active} className="h-[21px] w-[21px]" /> : null}
    </span>
  );
}

function EmailIcon({ active, className }: { active: boolean; className?: string }) {
  if (!active) {
    return (
      <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="3.5" y="5.5" width="17" height="13" rx="2.5" className="text-brand-muted" />
        <path d="m5 8 7 5 7-5" className="text-brand-muted" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="#EA4335" d="M4.5 6.8 12 12.4l7.5-5.6v10.1c0 .9-.7 1.6-1.6 1.6H6.1c-.9 0-1.6-.7-1.6-1.6V6.8Z" />
      <path fill="#FBBC04" d="M4.5 6.8 12 12.4 4.5 17V6.8Z" />
      <path fill="#34A853" d="M19.5 6.8 12 12.4l7.5 4.6V6.8Z" />
      <path fill="#4285F4" d="M6.1 5.5h11.8c.5 0 .9.2 1.2.6L12 11.4 4.9 6.1c.3-.4.7-.6 1.2-.6Z" />
      <path fill="#FFFFFF" d="M5.7 6.1 12 10.8l6.3-4.7.7.9-7 5.2L5 7l.7-.9Z" opacity="0.92" />
    </svg>
  );
}

function WhatsAppIcon({ active, className }: { active: boolean; className?: string }) {
  if (!active) {
    return (
      <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M12 4a8 8 0 0 0-6.8 12.2L4.4 20l3.9-1A8 8 0 1 0 12 4Z" className="text-brand-muted" />
        <path d="M9 8.9c.2 2.7 2.4 5 5.1 5.5l1.2-1.1" className="text-brand-muted" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="#25D366" d="M12 3.2a8.6 8.6 0 0 0-7.3 13.2L3.8 20.8l4.5-1.1A8.6 8.6 0 1 0 12 3.2Z" />
      <path fill="#FFFFFF" d="M16.9 14.2c-.2-.1-1.3-.6-1.5-.7-.2-.1-.4-.1-.5.1-.2.2-.6.7-.7.9-.1.1-.3.2-.5.1a7 7 0 0 1-2.1-1.3 7.8 7.8 0 0 1-1.4-1.8c-.1-.2 0-.4.1-.5l.4-.5c.1-.1.1-.3.2-.4.1-.1 0-.3 0-.4l-.7-1.6c-.2-.4-.4-.4-.6-.4h-.5c-.2 0-.4.1-.6.3-.2.2-.8.8-.8 1.9s.8 2.2.9 2.3c.1.2 1.6 2.5 3.9 3.5.5.2 1 .4 1.3.5.6.2 1.1.2 1.5.1.5-.1 1.3-.5 1.5-1 .2-.5.2-1 .1-1.1Z" />
    </svg>
  );
}

function InstagramIcon({ active, className }: { active: boolean; className?: string }) {
  if (!active) {
    return (
      <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <rect x="4" y="4" width="16" height="16" rx="5" className="text-brand-muted" />
        <circle cx="12" cy="12" r="3.5" className="text-brand-muted" />
        <circle cx="16.6" cy="7.4" r="0.8" fill="currentColor" className="text-brand-muted" stroke="none" />
      </svg>
    );
  }

  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <defs>
        <radialGradient id="instagram-gradient" cx="30%" cy="107%" r="130%">
          <stop offset="0" stopColor="#FEDA75" />
          <stop offset="0.35" stopColor="#FA7E1E" />
          <stop offset="0.58" stopColor="#D62976" />
          <stop offset="0.78" stopColor="#962FBF" />
          <stop offset="1" stopColor="#4F5BD5" />
        </radialGradient>
      </defs>
      <rect x="3.5" y="3.5" width="17" height="17" rx="5" fill="url(#instagram-gradient)" />
      <circle cx="12" cy="12" r="4" fill="none" stroke="#FFFFFF" strokeWidth="1.8" />
      <circle cx="16.9" cy="7.1" r="1.2" fill="#FFFFFF" />
    </svg>
  );
}
