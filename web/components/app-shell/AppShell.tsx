"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, useCallback, useEffect, useRef } from "react";

import { useI18n } from "@/lib/i18n/client";
import type { TranslationKey } from "@/lib/i18n/translations";

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

function CogIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className}>
      <path d="M12 15.5A3.5 3.5 0 1 0 12 8a3.5 3.5 0 0 0 0 7.5Z" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21a2 2 0 1 1-4 0v-.09A1.7 1.7 0 0 0 8.6 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1.1-.4H3a2 2 0 1 1 0-4h.09A1.7 1.7 0 0 0 4.6 8.6a1.7 1.7 0 0 0-.34-1.88l-.06-.06A2 2 0 1 1 7.03 3.83l.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V3a2 2 0 1 1 4 0v.09A1.7 1.7 0 0 0 15.4 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.7 1.7 0 0 0 19.4 9c.12.36.34.69.6 1a1.7 1.7 0 0 0 1.1.4H21a2 2 0 1 1 0 4h-.09A1.7 1.7 0 0 0 19.4 15Z" />
    </svg>
  );
}

type NavItemConfigEntry = {
  href: string;
  labelKey: TranslationKey;
  descriptionKey: TranslationKey;
  Icon: (props: { className?: string }) => React.ReactNode;
};

const navItemConfigs: NavItemConfigEntry[] = [
  { href: "/discovery", labelKey: "nav.discovery", descriptionKey: "nav.discoveryDescription", Icon: SearchIcon },
  { href: "/leads", labelKey: "nav.leads", descriptionKey: "nav.leadsDescription", Icon: GridIcon },
  { href: "/settings", labelKey: "nav.settings", descriptionKey: "nav.settingsDescription", Icon: CogIcon },
];

type NavItemConfig = {
  href: string;
  label: string;
  description: string;
  Icon: (props: { className?: string }) => React.ReactNode;
};

function NavItem({ item, active, expanded }: { item: NavItemConfig; active: boolean; expanded: boolean }) {
  const router = useRouter();

  return (
    <div className="group relative flex items-center justify-center">
      <Link
        href={item.href}
        prefetch
        onMouseEnter={() => router.prefetch(item.href)}
        onFocus={() => router.prefetch(item.href)}
        aria-current={active ? "page" : undefined}
        aria-label={item.label}
        className={`relative flex items-center overflow-hidden rounded-[15px] border px-2 motion-reduce:transition-none ${
          expanded ? "w-full justify-start min-h-[52px]" : "h-11 w-11 justify-center"
        } ${
          active
            ? "border-white/[0.34] bg-[linear-gradient(135deg,rgba(255,255,255,0.24),rgba(139,92,246,0.24))] text-white/98 shadow-[inset_0_1px_0_rgba(255,255,255,0.26),0_14px_32px_rgba(76,29,149,0.16)]"
            : "border-transparent text-white/76 hover:border-white/[0.18] hover:bg-white/[0.10] hover:text-white/96 hover:translate-x-px"
        }`}
        style={{
          gap: expanded ? "12px" : "0px",
          transition: "width 210ms cubic-bezier(0.22, 1, 0.36, 1), min-height 210ms cubic-bezier(0.22, 1, 0.36, 1), gap 190ms cubic-bezier(0.22, 1, 0.36, 1), transform 170ms cubic-bezier(0.22, 1, 0.36, 1), border-color 170ms ease, background-color 170ms ease, color 170ms ease, box-shadow 210ms cubic-bezier(0.22, 1, 0.36, 1)",
          willChange: "width, transform",
        }}
      >
        {active && (
          <span className="absolute left-[-7px] top-1/2 h-6 w-[3px] -translate-y-1/2 rounded-r-full bg-white/92 shadow-[0_0_14px_rgba(221,214,254,0.64)]" />
        )}

        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-[13px] border ${
            active ? "border-white/[0.26] bg-white/[0.18]" : "border-white/[0.16] bg-white/[0.11]"
          }`}
        >
          <item.Icon className={`h-[18px] w-[18px] ${active ? "text-white/98" : "text-white/78"}`} />
        </span>

        <div
          className="flex min-w-0 flex-col overflow-hidden whitespace-nowrap motion-reduce:transition-none"
          style={{
            maxWidth: expanded ? "138px" : "0px",
            opacity: expanded ? 1 : 0,
            transform: expanded ? "translateX(0)" : "translateX(-6px)",
            pointerEvents: expanded ? "auto" : "none",
            transition: "max-width 210ms cubic-bezier(0.22, 1, 0.36, 1), opacity 150ms ease-out, transform 190ms cubic-bezier(0.22, 1, 0.36, 1)",
            willChange: "max-width, opacity, transform",
          }}
        >
          <span className="text-sm font-bold leading-tight text-white/96">{item.label}</span>
          <span className="mt-0.5 text-xs font-medium leading-tight text-white/66">{item.description}</span>
        </div>
      </Link>

      {!expanded && (
        <span className="pointer-events-none absolute left-full ml-2 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-xl border border-white/[0.12] bg-[#554A64]/[0.94] px-3 py-1.5 text-xs font-medium text-white/88 opacity-0 shadow-[0_8px_24px_rgba(0,0,0,0.28)] backdrop-blur-xl transition-opacity duration-120 motion-reduce:transition-none group-hover:opacity-100">
          {item.label}
        </span>
      )}
    </div>
  );
}

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const sidebarRef = useRef<HTMLDivElement>(null);
  const navItems = navItemConfigs.map((item) => ({
    href: item.href,
    label: t(item.labelKey),
    description: t(item.descriptionKey),
    Icon: item.Icon,
  }));

  const handleMouseEnter = useCallback(() => setExpanded(true), []);
  const handleMouseLeave = useCallback(() => setExpanded(false), []);
  const handleFocusCapture = useCallback(() => setExpanded(true), []);
  const handleBlurCapture = useCallback((e: React.FocusEvent) => {
    if (sidebarRef.current && !sidebarRef.current.contains(e.relatedTarget as Node)) {
      setExpanded(false);
    }
  }, []);

  useEffect(() => {
    const prefetchRoutes = () => navItemConfigs.forEach((item) => router.prefetch(item.href));
    if ("requestIdleCallback" in window) {
      const idleId = window.requestIdleCallback(prefetchRoutes, { timeout: 1200 });
      return () => window.cancelIdleCallback(idleId);
    }
    const timeoutId = setTimeout(prefetchRoutes, 300);
    return () => clearTimeout(timeoutId);
  }, [router]);

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
        className="fixed inset-y-0 left-0 z-40 hidden flex-col px-2 py-[16px] lg:flex"
        style={{
          width: expanded ? "224px" : "70px",
          transition: "width 220ms cubic-bezier(0.22, 1, 0.36, 1), box-shadow 220ms cubic-bezier(0.22, 1, 0.36, 1)",
          willChange: "width, box-shadow",
          background: "radial-gradient(circle at 50% 0%, rgba(255,255,255,0.24), transparent 34%),radial-gradient(circle at 50% 100%, rgba(167,139,250,0.06), transparent 44%),linear-gradient(180deg, rgba(146,137,162,0.58) 0%, rgba(118,108,137,0.52) 48%, rgba(91,82,110,0.56) 100%)",
          backdropFilter: "blur(30px) saturate(145%)",
          WebkitBackdropFilter: "blur(30px) saturate(145%)",
          boxShadow: expanded
            ? "inset -1px 0 0 rgba(255,255,255,0.10), 14px 0 36px rgba(45,36,62,0.08)"
            : "inset -1px 0 0 rgba(255,255,255,0.10), 8px 0 24px rgba(45,36,62,0.06)",
        }}
      >
        {/* Soft edge fade */}
        <div className="pointer-events-none absolute top-0 right-[-52px] h-full w-[52px] bg-[linear-gradient(90deg,rgba(244,241,251,0.42),rgba(244,241,251,0.12),rgba(244,241,251,0))] blur-[16px]" />

        {/* Ambient glow */}
        <div className="pointer-events-none absolute -top-16 left-1/2 h-36 w-36 -translate-x-1/2 rounded-full bg-brand-orchid/4 blur-3xl" />

        <div className="relative flex h-full flex-col">
          {/* Logo */}
          <div className="relative flex items-center px-1" style={{ minHeight: "40px" }}>
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[15px] border border-white/[0.24] bg-[linear-gradient(180deg,rgba(255,255,255,0.22),rgba(255,255,255,0.11))] shadow-[inset_0_1px_0_rgba(255,255,255,0.22),0_10px_22px_rgba(76,29,149,0.10)]">
              <svg aria-hidden="true" viewBox="0 0 40 40" className="h-[22px] w-[22px]">
                <path d="M22.2 3.7C31.1 8 36.1 16.2 36.4 27.9c-4.5-5.2-11.7-6.7-19.3-2.8 4.2-7.2 4.5-14.4 5.1-21.4Z" fill="#FFFFFF" />
                <path d="M18.3 15.3c1.8 4.7 1.1 10.3-2.2 17.2 2.9-1.8 5.9-2.7 9.1-3.1-2.5-3.3-3.8-8.1-6.9-14.1Z" fill="#6D28D9" />
              </svg>
            </div>

            <div
              className="whitespace-nowrap motion-reduce:transition-none"
              style={{
                opacity: expanded ? 1 : 0,
                transform: expanded ? "translateX(0)" : "translateX(-4px)",
                pointerEvents: expanded ? "auto" : "none",
                marginLeft: expanded ? "12px" : "0",
                transition: "opacity 160ms ease-out, transform 190ms cubic-bezier(0.22, 1, 0.36, 1), margin-left 210ms cubic-bezier(0.22, 1, 0.36, 1)",
                willChange: "opacity, transform",
              }}
            >
              <p className="text-[14px] font-bold tracking-tight text-white/96">Encontra.ai</p>
              <p className="text-xs font-medium text-white/68">{t("app.leadOperations")}</p>
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
      <main className="relative z-10 w-full px-4 py-5 pb-16 sm:px-6 lg:pl-[92px] lg:pr-7 lg:py-7 lg:pb-7">
        <div className="w-full max-w-[1540px]">{children}</div>
      </main>
    </div>
  );
}
