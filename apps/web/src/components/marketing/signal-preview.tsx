import { AtSign, MapPin, Search } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"

export function SignalPreview() {
  return (
    <div className="lead-radar-wrap lead-radar-minimal" aria-label="Prévia ilustrativa da busca de leads na Kiara">
      <div className="lead-radar-halo" aria-hidden="true" />
      <div className="lead-radar-console">
        <div className="lead-radar-toolbar">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-white/86"><Search className="size-3.5 text-primary" />Dentistas em Porto Alegre</div>
          <span className="lead-radar-live"><i /> Buscando</span>
        </div>
        <div className="lead-radar-stage">
          <div className="lead-grid-floor" aria-hidden="true" />
          <div className="lead-orbit orbit-one" aria-hidden="true" />
          <div className="lead-orbit orbit-two" aria-hidden="true" />
          <div className="lead-orb-shell"><KiaraOrb size="lg" active /><span className="lead-orb-glow" /></div>
          <div className="radar-sweep" aria-hidden="true" />

          <div className="lead-float-card lead-a">
            <span className="lead-float-icon"><MapPin className="size-3.5" /></span>
            <span className="min-w-0"><strong>Clínica Aurora</strong><small>Porto Alegre</small></span>
          </div>
          <div className="lead-float-card lead-c">
            <span className="lead-float-icon"><AtSign className="size-3.5" /></span>
            <span className="min-w-0"><strong>Studio Sorriso</strong><small>Instagram disponível</small></span>
          </div>
        </div>
        <div className="lead-minimal-status"><span>Resultados organizados</span><strong>Hunter → Leads → Pipeline</strong></div>
      </div>
    </div>
  )
}
