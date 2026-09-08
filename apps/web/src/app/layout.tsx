import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/components/auth-provider";
import { resolveAuthMode } from "@/lib/auth-config";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "Kiara Lead Intelligence",
    template: "%s | Kiara",
  },
  description:
    "Transforme conversas inbound do Instagram em próximas ações claras, com qualificação assistida e aprovação humana.",
  applicationName: "Kiara Lead Intelligence",
  category: "business",
};

export const viewport: Viewport = {
  colorScheme: "light dark",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f8f7fb" },
    { media: "(prefers-color-scheme: dark)", color: "#151421" },
  ],
};

const themeBootScript = `
(function () {
  try {
    var stored = localStorage.getItem("kiara-theme") || "system";
    var dark = stored === "dark" || (stored === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.dataset.theme = stored;
  } catch (_) {}
})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // Resolve once on the server so client and server cannot disagree about
  // truthy demo values (for example `1` or `yes`). No secret is serialized.
  const authMode = resolveAuthMode();
  return (
    <html
      lang="pt-BR"
      data-scroll-behavior="smooth"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script id="kiara-theme-boot" dangerouslySetInnerHTML={{ __html: themeBootScript }} />
      </head>
      <body className={`${geistSans.className} flex min-h-full flex-col`}>
        <AuthProvider mode={authMode}>{children}</AuthProvider>
      </body>
    </html>
  );
}
