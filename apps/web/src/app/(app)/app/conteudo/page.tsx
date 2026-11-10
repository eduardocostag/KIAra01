import { redirect } from "next/navigation";
import { Sparkles } from "lucide-react";
import { ContentWorkspace } from "@/components/content/content-workspace";
import { PageHeader } from "@/components/app-shell/page-header";
import { Badge } from "@/components/ui/badge";
import { AuthenticationRequiredError, requireWorkspace } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const metadata = { title: "Conteúdo | Kiara", description: "Planejamento e publicação com a Kiara Social API." };

export default async function ContentPage() {
  try { await requireWorkspace(); }
  catch (error) { if (error instanceof AuthenticationRequiredError) redirect("/sign-in"); throw error; }

  return <div className="mx-auto w-full max-w-7xl space-y-6"><PageHeader eyebrow="Kiara Social API" title="Conteúdo" description="Planeje conteúdo, agende publicações com Postiz e acompanhe seus canais." actions={<Badge className="gap-1.5"><Sparkles className="size-3" />Publicação e planejamento</Badge>} /><ContentWorkspace /></div>;
}
