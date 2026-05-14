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

import { formatLeadLabel } from "@/lib/format/lead-labels";
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
        header: ({ column }) => <SortHeader column={column} label="Empresa" />,
        cell: ({ row }) => (
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <p className="font-medium text-neutral-950">{row.original.business_name}</p>
              {row.original.is_blocked ? <BlockedBadge /> : null}
            </div>
            <p className="text-xs text-neutral-500">{row.original.category ?? "Sem categoria"}</p>
            {row.original.is_blocked ? (
              <p className="mt-1 line-clamp-2 text-xs text-rose-700">
                Motivo: {row.original.blocked_reason ?? "Corresponde a uma regra de exclusão ativa."}
              </p>
            ) : null}
          </div>
        ),
      },
      {
        accessorKey: "city",
        header: ({ column }) => <SortHeader column={column} label="Localização" />,
        cell: ({ row }) => (
          <span>
            {[row.original.city, row.original.state].filter(Boolean).join(", ") || "Não informado"}
          </span>
        ),
      },
      {
        accessorKey: "status",
        header: ({ column }) => <SortHeader column={column} label="Status" />,
        cell: ({ getValue }) => <Badge>{formatLeadLabel(String(getValue()))}</Badge>,
      },
      {
        id: "assignment",
        enableSorting: false,
        header: "Responsável",
        cell: ({ row }) => (
          <div>
            <p>{row.original.assigned_sales_rep?.name ?? "Sem responsável"}</p>
            <p className="text-xs text-neutral-500">{row.original.sales_region?.name ?? "Sem região"}</p>
          </div>
        ),
      },
      {
        accessorKey: "company_size_fit",
        header: ({ column }) => <SortHeader column={column} label="Perfil" />,
        cell: ({ row }) => (
          <div>
            <p>{formatLeadLabel(row.original.company_size_fit)}</p>
            <p className="text-xs text-neutral-500">{formatLeadLabel(row.original.trade_type)}</p>
          </div>
        ),
      },
      {
        id: "contacts",
        enableSorting: false,
        header: "Canais",
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
        header: ({ column }) => <SortHeader column={column} label="Atualizado" />,
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
    <section className="ea-card overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-brand-mist/80 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-brand-graphite">Lista de leads</h2>
          <p className="text-sm text-brand-muted">
            {isLoading ? "Carregando leads..." : `${total.toLocaleString()} leads na lista atual`}
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-brand-muted">
          Linhas
          <select
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            className="ea-input px-2 py-1"
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
          <thead className="bg-brand-canvas/80 text-xs font-semibold uppercase tracking-wide text-brand-muted">
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
                      ? "cursor-pointer bg-brand-olive/25"
                      : "cursor-pointer bg-brand-surface hover:bg-brand-canvas/70"
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
                  Nenhum lead encontrado com os filtros atuais.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-brand-muted">
          Página {pageIndex + 1} de {pageCount}
        </p>
        <div className="flex gap-2">
          <button
            type="button"
            disabled={pageIndex === 0}
            onClick={() => onPageChange(Math.max(0, pageIndex - 1))}
            className="ea-button-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
          >
            Anterior
          </button>
          <button
            type="button"
            disabled={pageIndex + 1 >= pageCount}
            onClick={() => onPageChange(Math.min(pageCount - 1, pageIndex + 1))}
            className="ea-button-secondary px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
          >
            Próxima
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
      {marker ? <span className="text-[10px] text-[#667568]">{marker}</span> : null}
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
  return (
    <span className="inline-flex rounded-md border border-rose-200 bg-rose-50 px-2 py-1 text-xs font-medium text-rose-800">
      Bloqueado
    </span>
  );
}

function ContactPill({ active, children }: { active: boolean; children: React.ReactNode }) {
  return (
    <span
      className={
        active
          ? "rounded-md border border-brand-olive/70 bg-brand-olive/20 px-2 py-1 text-xs font-medium text-brand-graphite"
          : "rounded-md border border-neutral-200 bg-neutral-50 px-2 py-1 text-xs text-neutral-400"
      }
    >
      {children}
    </span>
  );
}

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Não informado";
  }
  return new Intl.DateTimeFormat("pt-BR", {
    month: "short",
    day: "numeric",
    year: "numeric",
  }).format(date);
}
