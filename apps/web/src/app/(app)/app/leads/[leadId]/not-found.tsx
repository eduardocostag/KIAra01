import Link from "next/link"
import { Button } from "@/components/ui/button"
export default function NotFound(){return <div className="grid min-h-[60vh] place-items-center text-center"><div><p className="text-sm font-semibold text-primary">Lead não encontrado</p><h1 className="mt-2 text-3xl font-semibold">Este dossiê não existe na demonstração.</h1><Button className="mt-6" asChild><Link href="/app/inbox">Voltar para Inbox</Link></Button></div></div>}
