import { AcceptInvite } from "@/components/app-shell/team-plan"

export default async function InvitePage({ searchParams }: { searchParams: Promise<{ token?: string }> }) {
  const { token } = await searchParams
  return <div className="flex min-h-[70vh] items-center justify-center p-4"><AcceptInvite token={(token ?? "").slice(0, 200)} /></div>
}
