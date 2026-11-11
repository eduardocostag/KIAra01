import { SettingsSectionNav } from "@/components/app-shell/workspace-section-nav"

export default function SettingsLayout({ children }: { children: React.ReactNode }) {
  return <div className="mx-auto w-full max-w-7xl space-y-5">
    <SettingsSectionNav />
    {children}
  </div>
}
