import { AtSign, Check, MapPin, MessageCircleMore, Search, Sparkles, Workflow } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"

const leads = [
  { name: "Clínica Aurora", place: "Porto Alegre", channel: "WhatsApp", icon: MessageCircleMore, className: "lead-a" },
  { name: "Studio Sorriso", place: "Canoas", channel: "Instagram", icon: AtSign, className: "lead-b" },
  { name: "Odonto Prime", place: "Novo Hamburgo", channel: "Site", icon: MapPin, className: "lead-c" },
]

export function SignalPreview() {
  return (
    <div className="lead-radar-wrap" aria-label="Prévia ilustrativa da busca e organização de leads na Kiara">
      <div className="lead-radar-halo" aria-hidden="true" />
      <div className="lead-radar-console">
        <div className="lead-radar-toolbar">
          <div className="flex items-center gap-2 text-[11px] font-semibold text-white"><Search className="size-3.5 text-primary" />Dentistas em Porto Alegre</div>
          <span className="lead-radar-live"><i /> Busca ilustrativa</span>
        </div>

        <div className="lead-radar-stage">
          <div className="lead-grid-floor" aria-hidden="true" />
          <div className="lead-orbit orbit-one" aria-hidden="true" />
          <div className="lead-orbit orbit-two" aria-hidden="true" />
          <div className="lead-orb-shell"><KiaraOrb size="lg" active /><span className="lead-orb-glow" /></div>
          <div className="radar-sweep" aria-hidden="true" />

          {leads.map(({ name, place, channel, icon: Icon, className }) => (
            <div className={`lead-float-card ${className}`} key={name}>
              <span className="lead-float-icon"><Icon className="size-3.5" /></span>
              <span className="min-w-0"><strong>{name}</strong><small><MapPin className="size-2.5" />{place}</small></span>
              <span className="lead-channel">{channel}</span>
            </div>
          ))}

          <div className="lead-scan-chip"><Sparkles className="size-3.5" /><span><strong>Kiara analisando</strong><small>Organizando resultados</small></span></div>
        </div>

        <div className="lead-radar-bottom">
          <div><span className="lead-stat-icon"><Check className="size-3.5" /></span><p><strong>Resultados</strong><small>Dados reunidos em uma lista</small></p></div>
          <div><span className="lead-stat-icon"><Workflow className="size-3.5" /></span><p><strong>Pipeline</strong><small>Prontos para organizar</small></p></div>
        </div>
      </div>
      <div className="lead-depth-card lead-depth-one" aria-hidden="true" />
      <div className="lead-depth-card lead-depth-two" aria-hidden="true" />
    </div>
  )
}
