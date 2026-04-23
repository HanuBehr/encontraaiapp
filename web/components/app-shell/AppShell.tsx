"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type AppShellProps = {
  children: React.ReactNode;
};

export function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-[#f7f8fa] text-neutral-950">
      <header className="border-b border-neutral-200 bg-white">
        <div className="mx-auto flex min-h-16 w-full max-w-[1500px] items-center justify-between gap-4 px-4 py-3 sm:px-6">
          <div>
            <p className="text-xs font-semibold uppercase text-cyan-700">Garin</p>
            <h1 className="text-lg font-semibold text-neutral-950">Lead Operations</h1>
          </div>
          <nav aria-label="Primary navigation" className="flex items-center gap-2">
            {navItems.map((item) => {
              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={
                    active
                      ? "rounded-md border border-neutral-900 bg-neutral-950 px-3 py-2 text-sm font-medium text-white"
                      : "rounded-md border border-neutral-300 bg-white px-3 py-2 text-sm font-medium text-neutral-800 hover:border-neutral-500"
                  }
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
      </header>
      <main className="mx-auto w-full max-w-[1500px] px-4 py-4 sm:px-6">{children}</main>
    </div>
  );
}

const navItems = [
  { href: "/discovery", label: "Discovery" },
  { href: "/leads", label: "Leads" },
];
