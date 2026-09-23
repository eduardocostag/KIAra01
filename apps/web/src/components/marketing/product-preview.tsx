import { AtSign, Check, ChevronRight, Globe2, MapPin, MessageCircle, Search, SlidersHorizontal } from "lucide-react"

const leads = [
  { initials: "CA", name: "Clínica Aurora", source: "Google Maps", status: "Novo", color: "sky" },
  { initials: "SS", name: "Studio Sorriso", source: "Instagram", status: "Qualificado", color: "violet" },
  { initials: "OP", name: "Odonto Prime", source: "Web", status: "Contato", color: "amber" },
  { initials: "DB", name: "Dental Blanc", source: "Google Maps", status: "Oportunidade", color: "fuchsia" },
]

export function ProductPreview() {
  return (
    <div className="product-window" role="group" aria-label="Prévia ilustrativa da área de Leads da Kiara">
      <div className="product-window-bar">
        <div className="flex items-center gap-2"><span className="product-window-dot" /><strong>Leads</strong></div>
        <div className="product-window-search"><Search className="size-3" />Buscar lead...</div>
        <SlidersHorizontal className="size-3.5 text-white/35" />
      </div>
      <div className="product-window-body">
        <div className="product-lead-list">
          {leads.map((lead, index) => (
            <div className={`product-lead-row ${index === 1 ? "is-active" : ""}`} key={lead.name}>
              <span className="product-lead-avatar">{lead.initials}</span>
              <span className="min-w-0 flex-1"><strong>{lead.name}</strong><small>{lead.source}</small></span>
              <span className={`product-status ${lead.color}`}>{lead.status}</span>
              <ChevronRight className="size-3.5 text-white/28" />
            </div>
          ))}
        </div>
        <aside className="product-inspector">
          <div className="flex items-start gap-3"><span className="product-lead-avatar large">SS</span><span><strong className="block text-xs text-white">Studio Sorriso</strong><small className="mt-1 flex items-center gap-1 text-[9px] text-white/38"><MapPin className="size-2.5" />Porto Alegre</small></span></div>
          <div className="product-contact-grid">
            <span><MessageCircle />WhatsApp<Check /></span>
            <span><AtSign />Instagram<Check /></span>
            <span><Globe2 />Site<Check /></span>
          </div>
          <div className="product-stage-label">Etapa do pipeline</div>
          <div className="product-stage-select"><i />Qualificado<ChevronRight /></div>
          <div className="product-note"><strong>Próximo passo</strong><span>Revisar contato e preparar abordagem</span></div>
        </aside>
      </div>
    </div>
  )
}
