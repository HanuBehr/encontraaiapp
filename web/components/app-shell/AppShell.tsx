"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-brand-canvas text-brand-graphite">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-72 border-r border-brand-mist/80 bg-brand-surface/90 px-5 py-6 shadow-card backdrop-blur lg:flex lg:flex-col">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl border border-brand-mist bg-brand-sand/60 text-sm font-semibold text-brand-graphite">
            E
          </div>
          <div>
            <p className="text-sm font-semibold tracking-tight text-brand-graphite">Encontra.ai</p>
            <p className="text-xs text-brand-muted">Lead operations system</p>
          </div>
        </div>

        <div className="mt-8 rounded-3xl border border-brand-mist/80 bg-brand-canvas/70 p-4">
          <p className="ea-kicker">Workspace</p>
          <h1 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-brand-graphite">
            Clear systems for lead discovery.
          </h1>
          <p className="mt-3 text-sm leading-6 text-brand-muted">
            Descubra, revise, enriqueça e exporte listas com uma operação mais organizada.
          </p>
        </div>

        <nav aria-label="Primary navigation" className="mt-7 space-y-2">
          {navItems.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            return <NavItem key={item.href} item={item} active={active} />;
          })}
        </nav>

        <div className="mt-auto rounded-3xl border border-brand-mist/80 bg-white/45 p-4">
          <p className="ea-kicker">Operations</p>
          <p className="mt-2 text-sm leading-6 text-brand-muted">
            Calm workflows for preview, enrichment, CNPJ review and clean Excel exports.
          </p>
        </div>
      </aside>

      <header className="sticky top-0 z-20 border-b border-brand-mist/80 bg-brand-canvas/90 px-4 py-3 backdrop-blur lg:hidden">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-sm font-semibold text-brand-graphite">Encontra.ai</p>
            <p className="text-xs text-brand-muted">Descoberta e Leads</p>
          </div>
          <nav aria-label="Primary navigation" className="flex items-center gap-2">
            {navItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={
                    active
                      ? "rounded-full border border-brand-graphite bg-brand-graphite px-3 py-2 text-xs font-semibold text-brand-surface"
                      : "rounded-full border border-brand-mist bg-brand-surface/70 px-3 py-2 text-xs font-semibold text-brand-graphite"
                  }
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="w-full px-4 py-5 sm:px-6 lg:pl-[19.5rem] lg:pr-8 lg:py-8">
        <div className="mx-auto w-full max-w-[1560px]">{children}</div>
      </main>
    </div>
  );
}

const navItems = [
  { href: "/discovery", label: "Descoberta", description: "Buscar e importar empresas" },
  { href: "/leads", label: "Leads", description: "Operar listas salvas" },
];

type NavItemConfig = (typeof navItems)[number];

function NavItem({ item, active }: { item: NavItemConfig; active: boolean }) {
  return (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={
        active
          ? "group flex items-center justify-between rounded-2xl border border-brand-graphite bg-brand-graphite px-4 py-3 text-brand-surface shadow-sm"
          : "group flex items-center justify-between rounded-2xl border border-transparent px-4 py-3 text-brand-graphite transition hover:border-brand-mist hover:bg-brand-canvas/70"
      }
    >
      <span>
        <span className="block text-sm font-semibold">{item.label}</span>
        <span className={active ? "mt-0.5 block text-xs text-brand-mist" : "mt-0.5 block text-xs text-brand-muted"}>
          {item.description}
        </span>
      </span>
      <span
        className={
          active
            ? "h-2 w-2 rounded-full bg-brand-sage"
            : "h-2 w-2 rounded-full bg-brand-mist transition group-hover:bg-brand-olive"
        }
      />
    </Link>
  );
}
