import type { MetadataRoute } from "next"

/** Kiara as an installable app (PWA): home-screen icon, full screen, no browser bar. Free, on iPhone and Android. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    id: "/app",
    name: "Kiara Intelligence",
    short_name: "Kiara",
    description: "Kiara: leads, captação e CRM com IA em um só app.",
    lang: "pt-BR",
    dir: "ltr",
    start_url: "/app?source=app",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#0d0b18",
    theme_color: "#151421",
    categories: ["business", "productivity"],
    icons: [
      { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
    shortcuts: [
      { name: "Contato presencial", short_name: "Presencial", url: "/app/presencial?source=app", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
      { name: "Buscar leads", short_name: "Leads", url: "/app/leads?source=app", icons: [{ src: "/icons/icon-192.png", sizes: "192x192" }] },
    ],
  }
}
