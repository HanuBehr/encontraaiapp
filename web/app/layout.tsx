import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell/AppShell";
import { Providers } from "@/app/providers";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Encontra.ai Lead Workspace",
  description: "Lead discovery and operations workspace for Encontra.ai teams.",
};

type RootLayoutProps = {
  children: React.ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
