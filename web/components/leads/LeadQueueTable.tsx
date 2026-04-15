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

import type { LeadSummary } from "@/lib/api/types";

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
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const columns = useMemo<ColumnDef<LeadSummary>[]>(
    () => [
      {
        id: "select",
        enableSorting: false,
        header: ({ table }) => (
          <input
            type="checkbox"
            aria-label="Select page"
            checked={table.getIsAllPageRowsSelected()}
            onChange={table.getToggleAllPageRowsSelectedHandler()}
            className="h-4 w-4 rounded border-neutral-300"
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            aria-label={`Select ${row.original.business_name}`}
            checked={row.getIsSelected()}
            onClick={(event) => event.stopPropagation()}
            onChange={row.getToggleSelectedHandler()}
            className="h-4 w-4 rounded border-neutral-300"
          />
        ),
      },
      {
        accessorKey: "business_name",
        header: ({ column }) => <SortHeader column={column} label="Company" />,
        cell: ({ row }) => (
          <div>
            <p className="font-medium text-neutral-950">{row.original.business_name}</p>
            <p className="text-xs text-neutral-500">{row.original.category ?? "No category"}</p>
          </div>
        ),
      },
      {
        accessorKey: "city",
        header: ({ column }) => <SortHeader column={column} label="Location" />,
        cell: ({ row }) => (
          <span>
            {[row.original.city, row.original.state].filter(Boolean).join(", ") || "Unknown"}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: ({ column }) => <SortHeader column={column} label="Status" />,
        cell: ({ getValue }) => <Badge>{labelToken(String(getValue()))}</Badge>,
      },
      {
        id: "assignment",
        enableSorting: false,
        header: "Assignment",
        cell: ({ row }) => (
          <div>
            <p>{row.original.assigned_sales_rep?.name ?? "Unassigned"}</p>
            <p className="text-xs text-neutral-500">{row.original.sales_region?.name ?? "No region"}</p>
          </div>
        ),
      },
      {
        accessorKey: "company_size_fit",
        header: ({ column }) => <SortHeader column={column} label="Fit" />,
        cell: ({ row }) => (
          <div>
            <p>{labelToken(row.original.company_size_fit)}</p>
            <p className="text-xs text-neutral-500">{labelToken(row.original.trade_type)}</p>
          </div>
        ),
      },
      {
        id: "contacts",
        enableSorting: false,
        header: "Contacts",
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            <ContactPill active={Boolean(row.original.email)}>Email</ContactPill>
            <ContactPill active={Boolean(row.original.whatsapp)}>WA</ContactPill>
            <ContactPill active={Boolean(row.original.instagram)}>IG</ContactPill>
          </div>
        ),
      },
      {
        accessorKey: "lead_score",
        header: ({ column }) => <SortHeader column={column} label="Score" />,
        cell: ({ getValue }) => <span className="font-medium">{String(getValue())}</span>,
      },
      {
        accessorKey: "updated_at",
        header: ({ column }) => <SortHeader column={column} label="Updated" />,
        cell: ({ getValue }) => <span>{formatDate(String(getValue()))}</span>,
      },
    ],
    [],
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
    <section className="rounded-md border border-neutral-200 bg-white">
      <div className="flex flex-col gap-3 border-b border-neutral-200 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-neutral-950">Leads queue</h2>
          <p className="text-sm text-neutral-500">
            {isLoading ? "Loading leads" : `${total.toLocaleString()} leads in current set`}
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-neutral-700">
          Rows
          <select
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            className="rounded-md border border-neutral-300 bg-white px-2 py-1"
          >
            {[10, 25, 50, 100].map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
          <thead className="bg-neutral-50 text-xs font-semibold uppercase text-neutral-500">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id} className="border-b border-neutral-200 px-3 py-3">
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
                      ? "cursor-pointer bg-cyan-50"
                      : "cursor-pointer bg-white hover:bg-neutral-50"
                  }
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="border-b border-neutral-100 px-3 py-3 align-top text-neutral-800">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-sm text-neutral-500">
                  No leads match the current queue.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-neutral-500">
          Page {pageIndex + 1} of {pageCount}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={pageIndex === 0}
            onClick={() => onPageChange(Math.max(0, pageIndex - 1))}
            className="rounded-md border border-neutral-300 px-3 py-2 text-sm font-medium text-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Previous
          </button>
          <button
            type="button"
            disabled={pageIndex + 1 >= pageCount}
            onClick={() => onPageChange(Math.min(pageCount - 1, pageIndex + 1))}
            className="rounded-md border border-neutral-300 px-3 py-2 text-sm font-medium text-neutral-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Next
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
      className="flex items-center gap-1 font-semibold uppercase text-neutral-500 disabled:cursor-default"
    >
      <span>{label}</span>
      {marker ? <span className="text-[10px] text-cyan-700">{marker}</span> : null}
    </button>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-800">
      {children}
    </span>
  );
}

function ContactPill({ active, children }: { active: boolean; children: React.ReactNode }) {
  return (
    <span
      className={
        active
          ? "rounded-md border border-cyan-200 bg-cyan-50 px-2 py-1 text-xs font-medium text-cyan-800"
          : "rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-xs text-neutral-400"
      }
    >
      {children}
    </span>
  );
}

function labelToken(value: string) {
  return value.replace(/_/g, " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Unknown";
  }
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}
