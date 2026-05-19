"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, useCallback, useRef } from "react";

type AppShellProps = {
  children: React.ReactNode;
};

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <circle cx="11" cy="11" r="7" />
      <path d="M16.5 16.5L21 21" />
    </svg>
  );
}

function GridIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  );
}

const navItems = [
  { href: "/discovery", label: "Descoberta", description: "Buscar empresas", Icon: SearchIcon },
  { href: "/leads", label: "Leads", description: "Listas salvas", Icon: GridIcon },
];

type NavItemConfig = (typeof navItems)[number];

function NavItem({ item, active, expanded }: { item: NavItemConfig; active: boolean; expanded: boolean }) {
  return (
    <div className="group relative flex items-center justify-center">
      <Link
        href={item.href}
        aria-current={active ? "page" : undefined}
        aria-label={item.label}
        className={`relative flex items-center rounded-[16px] border px-[10px] transition-all duration-160 motion-reduce:transition-none ${
          expanded ? "w-full justify-start gap-3 min-h-[56px]" : "w-[48px] h-[48px] justify-center"
        } ${
          active
            ? "border-white/[0.34] bg-[linear-gradient(135deg,rgba(255,255,255,0.24),rgba(139,92,246,0.24))] text-white/98 shadow-[inset_0_1px_0_rgba(255,255,255,0.26),0_14px_32px_rgba(76,29,149,0.16)]"
            : "border-transparent text-white/76 hover:border-white/[0.18] hover:bg-white/[0.10] hover:text-white/96 hover:translate-x-[2px]"
        }`}
      >
        {active && (
          <span className="absolute left-[-7px] top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full bg-white/92 shadow-[0_0_14px_rgba(221,214,254,0.64)]" />
        )}

        <span
          className={`flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-[14px] border ${
            active ? "border-white/[0.26] bg-white/[0.18]" : "border-white/[0.16] bg-white/[0.11]"
          }`}
        >
          <item.Icon className={`h-[20px] w-[20px] ${active ? "text-white/98" : "text-white/78"}`} />
        </span>

        <div
          className={`flex flex-col whitespace-nowrap transition-all duration-140 motion-reduce:transition-none ${
            expanded ? "opacity-100 translate-x-0 pointer-events-auto" : "opacity-0 translate-x-[-4px] pointer-events-none absolute"
          }`}
          style={expanded ? {} : { left: "calc(42px + 12px + 10px)", top: "50%", transform: "translateY(-50%) translateX(-4px)" }}
        >
          <span className="text-sm font-bold leading-tight text-white/96">{item.label}</span>
          <span className="mt-0.5 text-xs font-medium leading-tight text-white/66">{item.description}</span>
        </div>
      </Link>

      {!expanded && (
        <span className="pointer-events-none absolute left-full ml-2 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-xl border border-white/[0.12] bg-[#554A64]/[0.94] px-3 py-1.5 text-xs font-medium text-white/88 opacity-0 shadow-[0_8px_24px_rgba(0,0,0,0.28)] backdrop-blur-xl transition-opacity duration-120 motion-reduce:transition-none group-hover:opacity-100 group-focus-within:opacity-100">
          {item.label}
        </span>
      )}
    </div>
  );
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const [expanded, setExpanded] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);

  const handleMouseEnter = useCallback(() => setExpanded(true), []);
  const handleMouseLeave = useCallback(() => {
    if (sidebarRef.current && !sidebarRef.current.contains(document.activeElement)) {
      setExpanded(false);
    }
  }, []);
  const handleFocusCapture = useCallback(() => setExpanded(true), []);
  const handleBlurCapture = useCallback((e: React.FocusEvent) => {
    if (sidebarRef.current && !sidebarRef.current.contains(e.relatedTarget as Node)) {
      setExpanded(false);
    }
  }, []);

  return (
    <div className="relative min-h-screen overflow-hidden bg-brand-canvas text-brand-graphite">
      <div className="ea-ambient-noise pointer-events-none fixed inset-0 z-0 opacity-50" />
      <div className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(circle_at_78%_10%,rgba(139,92,246,0.16),transparent_28rem),radial-gradient(circle_at_18%_82%,rgba(96,165,250,0.12),transparent_30rem)]" />

      {/* Desktop Adaptive Dock */}
      <aside
        ref={sidebarRef}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onFocusCapture={handleFocusCapture}
        onBlurCapture={handleBlurCapture}
        className="fixed inset-y-0 left-0 z-40 hidden flex-col px-3 py-[18px] lg:flex"
        style={{
          width: expanded ? "244px" : "78px",
          transition: "width 180ms ease, box-shadow 180ms ease",
          background: "radial-gradient(circle at 50% 0%, rgba(255,255,255,0.30), transparent 34%),radial-gradient(circle at 50% 100%, rgba(167,139,250,0.08), transparent 44%),linear-gradient(180deg, rgba(160,151,174,0.64) 0%, rgba(128,118,145,0.58) 48%, rgba(96,86,116,0.62) 100%)",
          backdropFilter: "blur(30px) saturate(145%)",
          WebkitBackdropFilter: "blur(30px) saturate(145%)",
          boxShadow: expanded
            ? "inset -1px 0 0 rgba(255,255,255,0.10), 18px 0 48px rgba(45,36,62,0.10)"
            : "inset -1px 0 0 rgba(255,255,255,0.10), 12px 0 34px rgba(45,36,62,0.08)",
        }}
      >
        {/* Soft edge fade */}
        <div className="pointer-events-none absolute top-0 right-[-76px] h-full w-[76px] bg-[linear-gradient(90deg,rgba(244,241,251,0.55),rgba(244,241,251,0.18),rgba(244,241,251,0))] blur-[18px]" />

        {/* Ambient glow */}
        <div className="pointer-events-none absolute -top-16 left-1/2 h-36 w-36 -translate-x-1/2 rounded-full bg-brand-orchid/4 blur-3xl" />

        <div className="relative flex h-full flex-col">
          {/* Logo */}
          <div className="relative flex items-center px-1" style={{ minHeight: "44px" }}>
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[16px] border border-white/[0.28] bg-[linear-gradient(180deg,rgba(255,255,255,0.24),rgba(255,255,255,0.12))] shadow-[inset_0_1px_0_rgba(255,255,255,0.26),0_12px_28px_rgba(76,29,149,0.12)]">
              <svg aria-hidden="true" viewBox="0 0 40 40" className="h-6 w-6">
                <path d="M22.2 3.7C31.1 8 36.1 16.2 36.4 27.9c-4.5-5.2-11.7-6.7-19.3-2.8 4.2-7.2 4.5-14.4 5.1-21.4Z" fill="#FFFFFF" />
                <path d="M18.3 15.3c1.8 4.7 1.1 10.3-2.2 17.2 2.9-1.8 5.9-2.7 9.1-3.1-2.5-3.3-3.8-8.1-6.9-14.1Z" fill="#6D28D9" />
              </svg>
            </div>

            <div
              className="whitespace-nowrap transition-all duration-140 motion-reduce:transition-none"
              style={{
                opacity: expanded ? 1 : 0,
                transform: expanded ? "translateX(0)" : "translateX(-4px)",
                pointerEvents: expanded ? "auto" : "none",
                marginLeft: expanded ? "12px" : "0",
              }}
            >
              <p className="text-[14px] font-bold tracking-tight text-white/96">Encontra.ai</p>
              <p className="text-xs font-medium text-white/68">Lead operations</p>
            </div>
          </div>

          {/* Workspace row (expanded only) */}
          <div
            className="overflow-hidden transition-all duration-140 motion-reduce:transition-none"
            style={{
              opacity: expanded ? 1 : 0,
              pointerEvents: expanded ? "auto" : "none",
              height: expanded ? "42px" : "0px",
              marginTop: expanded ? "20px" : "0px",
            }}
          >
            <div className="flex min-h-[42px] items-center gap-[10px] rounded-[16px] border border-white/[0.14] bg-white/[0.10] px-[10px]">
              <span className="text-xs font-semibold text-white/82">Lead operations</span>
              <span className="ml-auto text-[10px] font-medium text-white/58">Ativo</span>
            </div>
          </div>

          {/* Navigation */}
          <nav className={`mt-5 space-y-[6px] ${expanded ? "" : "flex flex-col items-center"}`}>
            {navItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return <NavItem key={item.href} item={item} active={active} expanded={expanded} />;
            })}
          </nav>

          {/* Spacer */}
          <div className="flex-1" />

          {/* Bottom status */}
          {expanded ? (
            <div className="flex min-h-[44px] items-center gap-[10px] rounded-[16px] border border-white/[0.16] bg-white/[0.11] px-[10px] transition-all duration-140 motion-reduce:transition-none">
              <span className="relative flex h-2.5 w-2.5 shrink-0">
                <span className="absolute inset-0 animate-ping rounded-full bg-brand-success/40 motion-reduce:animate-none" />
                <span className="relative h-2.5 w-2.5 rounded-full bg-[#10B981] shadow-[0_0_12px_rgba(16,185,129,0.48)]" />
              </span>
              <div>
                <p className="text-sm font-semibold text-white/92">Sistema ativo</p>
                <p className="text-xs text-white/66">Pronto para descoberta</p>
              </div>
            </div>
          ) : (
            <div className="flex justify-center">
              <div className="flex h-[42px] w-[42px] items-center justify-center rounded-[14px] border border-white/[0.16] bg-white/[0.11]">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="absolute inset-0 animate-ping rounded-full bg-brand-success/40 motion-reduce:animate-none" />
                  <span className="relative h-2.5 w-2.5 rounded-full bg-[#10B981] shadow-[0_0_12px_rgba(16,185,129,0.48)]" />
                </span>
              </div>
            </div>
          )}
        </div>
      </aside>

      {/* Mobile bottom nav */}
      <nav className="fixed bottom-0 left-0 right-0 z-50 flex items-center justify-around border-t border-white/[0.12] bg-[#554A64]/[0.94] px-4 py-2 backdrop-blur-xl lg:hidden">
        {navItems.map((item) => {
          const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={
                active
                  ? "flex flex-col items-center gap-0.5 rounded-[16px] px-5 py-2 text-[10px] font-semibold text-white/96"
                  : "flex flex-col items-center gap-0.5 rounded-[16px] px-5 py-2 text-[10px] font-medium text-white/62 transition hover:text-white/88 motion-reduce:transition-none"
              }
            >
              <item.Icon className="mb-0.5 h-5 w-5" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Main */}
      <main className="relative z-10 w-full px-4 py-5 pb-16 sm:px-6 lg:pl-[108px] lg:pr-8 lg:py-8 lg:pb-8">
        <div className="mx-auto w-full max-w-[1560px]">{children}</div>
      </main>
    </div>
  );
}
