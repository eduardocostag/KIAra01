import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
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
    default: "Kiara Intelligence",
    template: "%s | Kiara",
  },
  description:
    "Kiara: a IA que encontra clientes, transforma cartões de visita em leads e acompanha cada venda no CRM e no WhatsApp.",
  applicationName: "Kiara Intelligence",
  category: "business",
  // Installed on the iPhone home screen: full screen, named "Kiara". A solid status bar, so no screen ends up
  // under the clock and the notch (only the module bar pads for it).
  appleWebApp: { capable: true, title: "Kiara", statusBarStyle: "black" },
  formatDetection: { telephone: false },
};

export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#151421",
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      data-scroll-behavior="smooth"
      data-theme="dark"
      className={`${geistSans.variable} ${geistMono.variable} dark h-full antialiased`}
    >
      <body className={`${geistSans.className} flex min-h-full flex-col`}>{children}</body>
    </html>
  );
}
