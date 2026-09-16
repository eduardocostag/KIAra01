import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { AuthProvider } from "@/components/auth-provider";
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
  colorScheme: "dark",
  themeColor: "#151421",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      data-scroll-behavior="smooth"
      data-theme="dark"
      className={`${geistSans.variable} ${geistMono.variable} dark h-full antialiased`}
    >
      <body className={`${geistSans.className} flex min-h-full flex-col`}>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
