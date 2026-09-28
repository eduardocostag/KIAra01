import { redirect } from "next/navigation";
import { Construction, Sparkles } from "lucide-react";
import { ContentConsole } from "@/components/content/content-console";
import { PageHeader } from "@/components/app-shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { AuthenticationRequiredError, requireWorkspace } from "@/lib/auth";

export const dynamic = "force-dynamic";
export const metadata = { title: "Conteúdo | Kiara", description: "Planejamento e publicação com a Kiara Social API." };

export default async function ContentPage() {
  let isSystemAdmin = false;
  try {
    isSystemAdmin = (await requireWorkspace()).isSystemAdmin;
  } catch (error) {
    if (error instanceof AuthenticationRequiredError) redirect("/sign-in");
    throw error;
  }

  if (!isSystemAdmin) {
    return <div className="mx-auto w-full max-w-5xl space-y-6"><PageHeader eyebrow="Conteúdo social" title="Conteúdo" description="Planeje, aprove e acompanhe publicações da sua operação." actions={<Badge variant="outline">Em breve</Badge>} /><Card className="overflow-hidden"><CardContent className="grid min-h-[440px] place-items-center bg-[radial-gradient(circle_at_50%_20%,color-mix(in_oklab,var(--primary)_16%,transparent),transparent_42%)] p-8 text-center"><div className="max-w-lg"><span className="mx-auto grid size-14 place-items-center rounded-2xl border border-primary/20 bg-primary/10 text-primary"><Construction className="size-6" /></span><p className="mt-6 text-xs font-semibold uppercase tracking-[.16em] text-primary">Em construção</p><h2 className="mt-2 text-2xl font-semibold tracking-tight">O calendário de conteúdo está sendo preparado</h2><p className="mt-3 text-sm leading-6 text-muted-foreground">Em breve será possível criar rascunhos, agendar publicações, acompanhar canais e consultar métricas sem sair da Kiara.</p></div></CardContent></Card></div>;
  }

  return <div className="mx-auto w-full max-w-7xl space-y-6"><PageHeader eyebrow="Kiara Social API" title="Conteúdo" description="Crie, aprove, agende e prepare publicações sem depender de uma API paga ou não oficial." actions={<Badge className="gap-1.5"><Sparkles className="size-3" />Modo assistido gratuito</Badge>} /><ContentConsole /></div>;
}
