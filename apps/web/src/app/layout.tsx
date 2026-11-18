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
    "Kiara Intelligence: prospecção, atendimento, criação de sites, vídeos e automação em uma plataforma integrada.",
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
