import type { Metadata } from "next";

import { AppShell } from "@/components/app-shell/AppShell";
import { Providers } from "@/app/providers";
import "@/styles/globals.css";

export const metadata: Metadata = {
  title: "Encontra.ai | Descoberta de leads",
  description: "Busque empresas por nicho e cidade, enriqueça contatos, salve leads e exporte planilhas prontas.",
};

type RootLayoutProps = {
  children: React.ReactNode;
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="pt-BR">
      <body>
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
