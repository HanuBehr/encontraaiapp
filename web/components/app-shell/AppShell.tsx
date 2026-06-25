"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useI18n } from "@/lib/i18n/client";
import { isDemoMode } from "@/lib/demo/mode";
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
        className={`relative flex items-center overflow-hidden rounded-[13px] border px-1 motion-reduce:transition-none ${
          expanded ? "w-full justify-start min-h-[52px]" : "h-9 w-9 justify-center"
        } ${
          active
            ? "border-white/55 bg-white/38 text-brand-orchid shadow-[inset_0_1px_0_rgba(255,255,255,0.34),0_12px_28px_rgba(109,40,217,0.18)]"
            : "border-white/20 bg-white/[0.08] text-brand-graphite/74 hover:border-white/45 hover:bg-white/24 hover:text-brand-graphite hover:translate-x-px"
        }`}
        style={{
          gap: expanded ? "12px" : "0px",
          transition: "width 210ms cubic-bezier(0.22, 1, 0.36, 1), min-height 210ms cubic-bezier(0.22, 1, 0.36, 1), gap 190ms cubic-bezier(0.22, 1, 0.36, 1), transform 170ms cubic-bezier(0.22, 1, 0.36, 1), border-color 170ms ease, background-color 170ms ease, color 170ms ease, box-shadow 210ms cubic-bezier(0.22, 1, 0.36, 1)",
          willChange: "width, transform",
        }}
      >
        <span
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[10px]"
        >
          <item.Icon className={`h-[17px] w-[17px] ${active ? "text-brand-orchid" : "text-brand-graphite/78"}`} />
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
        <span className="pointer-events-none absolute left-full ml-2 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-xl border border-white/45 bg-white/70 px-3 py-1.5 text-xs font-bold text-brand-graphite opacity-0 shadow-[0_10px_28px_rgba(47,38,61,0.12)] backdrop-blur-2xl transition-opacity duration-120 motion-reduce:transition-none group-hover:opacity-100">
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
  const expanded = false;
  const navItems = navItemConfigs.map((item) => ({
    href: item.href,
    label: t(item.labelKey),
    description: t(item.descriptionKey),
    Icon: item.Icon,
  }));

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
    <div className="relative min-h-screen overflow-x-hidden bg-brand-canvas text-brand-graphite">
      <div className="ea-ambient-noise pointer-events-none fixed inset-0 z-0 opacity-50" />
      <div className="pointer-events-none fixed inset-0 z-0 bg-[radial-gradient(circle_at_78%_10%,rgba(139,92,246,0.16),transparent_28rem),radial-gradient(circle_at_18%_82%,rgba(96,165,250,0.12),transparent_30rem)]" />
      {isDemoMode() ? (
        <div className="fixed bottom-20 right-4 z-50 rounded-full border border-brand-orchid/20 bg-white/65 px-2.5 py-1 text-[11px] font-bold text-brand-muted shadow-[0_10px_28px_rgba(47,38,61,0.08)] backdrop-blur-xl lg:bottom-5 lg:right-6">
          {t("app.demoBadge")}
        </div>
      ) : null}

      {/* Desktop floating dock */}
      <aside
        className="fixed left-4 top-1/2 z-40 hidden -translate-y-1/2 flex-col rounded-[22px] border border-white/45 bg-white/[0.16] px-1 py-2 shadow-[0_20px_54px_rgba(45,36,62,0.14),inset_0_1px_0_rgba(255,255,255,0.36)] backdrop-blur-3xl lg:flex"
        style={{
          width: "46px",
        }}
      >
        <div className="relative flex flex-col items-center">
          {/* Logo */}
          <div className="group relative flex items-center justify-center">
            <Link
              href="/"
              prefetch
              onMouseEnter={() => router.prefetch("/")}
              onFocus={() => router.prefetch("/")}
              aria-label="Home"
              className="relative flex h-9 w-9 items-center justify-center rounded-[13px] transition hover:bg-white/24 focus:outline-none focus:ring-2 focus:ring-brand-orchid/25 motion-reduce:transition-none"
              style={{ minHeight: "36px" }}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[12px] border border-white/35 bg-white/[0.18] shadow-[inset_0_1px_0_rgba(255,255,255,0.28),0_10px_22px_rgba(76,29,149,0.08)]">
                <svg aria-hidden="true" viewBox="0 0 40 40" className="h-5 w-5">
                  <path d="M22.2 3.7C31.1 8 36.1 16.2 36.4 27.9c-4.5-5.2-11.7-6.7-19.3-2.8 4.2-7.2 4.5-14.4 5.1-21.4Z" fill="#FFFFFF" />
                  <path d="M18.3 15.3c1.8 4.7 1.1 10.3-2.2 17.2 2.9-1.8 5.9-2.7 9.1-3.1-2.5-3.3-3.8-8.1-6.9-14.1Z" fill="#6D28D9" />
                </svg>
              </div>
            </Link>
            <span className="pointer-events-none absolute left-full ml-2 top-1/2 -translate-y-1/2 whitespace-nowrap rounded-xl border border-white/45 bg-white/70 px-3 py-1.5 text-xs font-bold text-brand-graphite opacity-0 shadow-[0_10px_28px_rgba(47,38,61,0.12)] backdrop-blur-2xl transition-opacity duration-120 motion-reduce:transition-none group-hover:opacity-100">
              Home
            </span>
          </div>

          {/* Navigation */}
          <nav className="mt-2.5 flex flex-col items-center space-y-1.5">
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
      <main className="relative z-10 w-full px-4 py-5 pb-16 sm:px-6 lg:pl-[78px] lg:pr-7 lg:py-7 lg:pb-7">
        <div className="w-full max-w-[1540px]">{children}</div>
      </main>
    </div>
  );
}
