"use client"

import { useEffect, useState } from "react"
import { Download, Share, SquarePlus, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/** "Instalar a Kiara": the site as a home-screen app (PWA), free on iPhone and Android.
 *  Android/Chrome: the browser's own install dialog. iPhone: Safari has no install button for sites, so the two
 *  taps are shown (Compartilhar → Adicionar à Tela de Início). Nothing shows once the app is installed. */

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: "accepted" | "dismissed" }> }
type Platform = "android" | "iphone" | "iphone-other-browser" | null

const OPEN_EVENT = "kiara:install-app"
const DISMISSED_KEY = "kiara-install-dismissed"
const DISMISS_DAYS = 14
let deferred: InstallEvent | null = null

/** Opens the install card from anywhere (e.g. the "Instalar app" item of the mobile menu). */
export function openInstallApp() { window.dispatchEvent(new Event(OPEN_EVENT)) }

function installed() {
  return window.matchMedia("(display-mode: standalone)").matches || (navigator as Navigator & { standalone?: boolean }).standalone === true
}

function detect(): Platform {
  const ua = navigator.userAgent
  const iOS = /iPhone|iPad|iPod/i.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)
  if (iOS) return /CriOS|FxiOS|EdgiOS|OPiOS/i.test(ua) ? "iphone-other-browser" : "iphone"
  return deferred ? "android" : null
}

function recentlyDismissed() {
  try {
    const at = Number(localStorage.getItem(DISMISSED_KEY) || 0)
    return Date.now() - at < DISMISS_DAYS * 86_400_000
  } catch { return false }
}

/** Whether the "Instalar app" menu item makes sense here (not installed yet, and a phone or an install prompt). */
export function useCanInstall() {
  const [can, setCan] = useState(false)
  useEffect(() => {
    const update = () => setCan(!installed() && detect() !== null)
    update()
    window.addEventListener("beforeinstallprompt", update)
    window.addEventListener("appinstalled", update)
    return () => { window.removeEventListener("beforeinstallprompt", update); window.removeEventListener("appinstalled", update) }
  }, [])
  return can
}

export function InstallApp({ aboveTabBar = false }: { aboveTabBar?: boolean }) {
  const [platform, setPlatform] = useState<Platform>(null)
  const [open, setOpen] = useState(false)

  useEffect(() => {
    // The service worker only shows a "sem conexão" screen; it keeps no data (public/sw.js).
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {})
    if (installed()) return

    const phone = window.matchMedia("(max-width: 767px)").matches
    const onPrompt = (event: Event) => {
      event.preventDefault()
      deferred = event as InstallEvent
      setPlatform("android")
      if (phone && !recentlyDismissed()) setOpen(true)
    }
    const onInstalled = () => { deferred = null; setOpen(false) }
    const onOpen = () => { const found = detect(); if (found) { setPlatform(found); setOpen(true) } }
    window.addEventListener("beforeinstallprompt", onPrompt)
    window.addEventListener("appinstalled", onInstalled)
    window.addEventListener(OPEN_EVENT, onOpen)

    // iPhone: no install event exists, so the card shows the steps after a moment (phones only, once per 14 days).
    const found = detect()
    const timer = found?.startsWith("iphone") && phone && !recentlyDismissed()
      ? window.setTimeout(() => { setPlatform(found); setOpen(true) }, 2500)
      : undefined
    return () => {
      window.removeEventListener("beforeinstallprompt", onPrompt)
      window.removeEventListener("appinstalled", onInstalled)
      window.removeEventListener(OPEN_EVENT, onOpen)
      window.clearTimeout(timer)
    }
  }, [])

  function dismiss() {
    setOpen(false)
    try { localStorage.setItem(DISMISSED_KEY, String(Date.now())) } catch { /* private mode: just close */ }
  }

  async function install() {
    if (!deferred) return
    await deferred.prompt()
    const { outcome } = await deferred.userChoice
    deferred = null
    if (outcome === "accepted") setOpen(false)
  }

  if (!open || !platform) return null
  return (
    <div
      role="dialog"
      aria-label="Instalar a Kiara"
      className={cn(
        "fixed inset-x-3 z-50 mx-auto max-w-md rounded-[22px] border border-white/10 p-4 text-sm shadow-[0_18px_44px_-10px_rgb(0_0_0/.85),0_0_34px_-14px_rgb(124_77_255/.6)] backdrop-blur-xl fx-rise",
        "bg-[linear-gradient(160deg,rgb(30_24_54/.96),rgb(12_11_22/.97))]",
        aboveTabBar ? "bottom-[calc(5.6rem+env(safe-area-inset-bottom))] md:bottom-5" : "bottom-[calc(1rem+env(safe-area-inset-bottom))]",
      )}
    >
      <div className="flex items-start gap-3">
        {/* eslint-disable-next-line @next/next/no-img-element -- tiny static icon */}
        <img src="/icons/icon-192.png" alt="" className="size-11 shrink-0 rounded-xl" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold">Instale a Kiara no seu celular</p>
          {platform === "android" && <p className="mt-0.5 text-muted-foreground">Abre em tela cheia, direto do ícone, como um app. Grátis.</p>}
          {platform === "iphone" && (
            <ol className="mt-1.5 space-y-1.5 text-muted-foreground">
              <li>1. Toque em <span className="whitespace-nowrap font-medium text-foreground"><Share className="mr-0.5 inline size-4 align-[-3px]" aria-hidden="true" />Compartilhar</span> na barra do Safari</li>
              <li>2. Escolha <span className="whitespace-nowrap font-medium text-foreground"><SquarePlus className="mr-0.5 inline size-4 align-[-3px]" aria-hidden="true" />Adicionar à Tela de Início</span></li>
            </ol>
          )}
          {platform === "iphone-other-browser" && <p className="mt-0.5 text-muted-foreground">No iPhone, abra este site no <span className="text-foreground">Safari</span> e toque em Compartilhar → Adicionar à Tela de Início.</p>}
        </div>
        <Button type="button" variant="ghost" size="icon" className="-mr-1 -mt-1 size-8 shrink-0" onClick={dismiss} aria-label="Fechar"><X /></Button>
      </div>
      {platform === "android" && (
        <div className="mt-3 flex justify-end gap-2">
          <Button type="button" variant="ghost" onClick={dismiss}>Agora não</Button>
          <Button type="button" onClick={() => void install()}><Download />Instalar</Button>
        </div>
      )}
    </div>
  )
}
