"use client"

import { Laptop, Moon, Sun } from "lucide-react"
import { useEffect, useSyncExternalStore } from "react"
import { Button } from "@/components/ui/button"

type Theme = "light" | "dark" | "system"

const themes: Theme[] = ["system", "light", "dark"]
const labels: Record<Theme, string> = {
  system: "Tema do sistema",
  light: "Tema claro",
  dark: "Tema escuro",
}

function applyTheme(theme: Theme) {
  const dark = theme === "dark" || (theme === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)
  document.documentElement.classList.toggle("dark", dark)
  document.documentElement.dataset.theme = theme
  localStorage.setItem("kiara-theme", theme)
}

export function ThemeToggle() {
  const theme = useSyncExternalStore(
    (notify) => {
      window.addEventListener("kiara-theme-change", notify)
      return () => window.removeEventListener("kiara-theme-change", notify)
    },
    () => {
      const stored = localStorage.getItem("kiara-theme")
      return themes.includes(stored as Theme) ? (stored as Theme) : "system"
    },
    () => "system" as Theme,
  )

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)")
    const syncSystem = () => theme === "system" && applyTheme("system")
    media.addEventListener("change", syncSystem)
    return () => media.removeEventListener("change", syncSystem)
  }, [theme])

  const next = themes[(themes.indexOf(theme) + 1) % themes.length]
  const Icon = theme === "dark" ? Moon : theme === "light" ? Sun : Laptop

  return (
    <Button type="button" variant="ghost" size="icon" aria-label={`${labels[theme]}. Alterar para ${labels[next].toLowerCase()}`} title={labels[theme]} onClick={() => { applyTheme(next); window.dispatchEvent(new Event("kiara-theme-change")) }}>
      <Icon aria-hidden="true" />
    </Button>
  )
}
