import { redirect } from "next/navigation";
import { ContentWorkspace } from "@/components/content/content-workspace";
import { PageHeader } from "@/components/app-shell/page-header";
import { AuthenticationRequiredError, requireWorkspace } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const metadata = { title: "Conteúdo | Kiara", description: "Planejamento e publicação com a Kiara Social API." };

export default async function ContentPage() {
  try { await requireWorkspace(); }
  catch (error) { if (error instanceof AuthenticationRequiredError) redirect("/sign-in"); throw error; }

  return <div className="mx-auto w-full max-w-7xl space-y-5"><PageHeader title="Conteúdo" description="Crie, organize e acompanhe suas publicações." /><ContentWorkspace /></div>;
}
