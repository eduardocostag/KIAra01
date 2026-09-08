import { OrganizationList } from "@clerk/nextjs"
import { auth } from "@clerk/nextjs/server"
import { redirect } from "next/navigation"

export default async function OnboardingPage() {
  const session = await auth()
  if (!session.userId) redirect("/sign-in")
  if (session.orgId) redirect("/app")

  return (
    <main className="grid min-h-screen place-items-center bg-slate-950 px-6 py-16 text-white">
      <section className="w-full max-w-xl rounded-3xl border border-white/10 bg-white/5 p-6 shadow-2xl shadow-cyan-950/30 backdrop-blur sm:p-8">
        <p className="mb-2 text-sm font-semibold tracking-[0.24em] text-cyan-300">KIARA</p>
        <h1 className="text-3xl font-semibold tracking-tight">Prepare seu workspace</h1>
        <p className="mb-8 mt-3 text-sm leading-6 text-slate-300">
          Crie sua empresa ou selecione uma organização existente para manter leads, conversas e permissões separados.
        </p>
        <div className="flex justify-center">
          <OrganizationList
            afterCreateOrganizationUrl="/app"
            afterSelectOrganizationUrl="/app"
            hidePersonal
            skipInvitationScreen
          />
        </div>
      </section>
    </main>
  )
}
