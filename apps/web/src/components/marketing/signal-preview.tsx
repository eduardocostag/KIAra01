import { ArrowRight, AtSign, Building2, Check, MapPin, Search, Sparkles, Workflow } from "lucide-react"
import { KiaraOrb } from "@/components/brand/kiara-orb"

const leads = [
  ["CA", "Clínica Aurora", "Porto Alegre", "Alta"],
  ["SS", "Studio Sorriso", "Porto Alegre", "Média"],
  ["OP", "Odonto Prime", "Porto Alegre", "Alta"],
]

export function SignalPreview() {
  return (
    <div className="reference-hero-scene" role="group" aria-label="Prévia ilustrativa da Kiara encontrando e organizando leads">
      <div className="reference-main-orb"><span className="reference-main-ring ring-a" /><span className="reference-main-ring ring-b" /><KiaraOrb size="lg" active /></div>

      <div className="reference-skill skill-a"><Building2 /><span>Identifica empresas<strong>com alto potencial</strong></span></div>
      <div className="reference-skill skill-b"><Sparkles /><span>Organiza dados<strong>encontrados</strong></span></div>
      <div className="reference-skill skill-c"><Workflow /><span>Organiza no<strong>Pipeline</strong></span></div>

      <div className="reference-search-window">
        <div className="reference-window-brand"><span className="size-2 rounded-full bg-primary shadow-[0_0_10px_var(--primary)]" />KIARA</div>
        <div className="reference-window-search"><Search />Dentistas em Porto Alegre<button type="button">Buscar</button></div>
        <div className="reference-window-tabs"><span className="is-active">Leads</span><span>Empresas</span><span>Contatos</span></div>
        <div className="reference-window-leads">{leads.map(([initials, name, city, score], index) => <div className={index === 0 ? "is-active" : ""} key={name}><i /><span className="reference-lead-avatar">{initials}</span><p><strong>{name}</strong><small><MapPin />{city}</small></p><em>{score}</em></div>)}</div>
      </div>

      <div className="reference-company-card">
        <div className="flex items-center gap-2"><span className="reference-lead-avatar">CA</span><p><strong>Clínica Aurora</strong><small>Clínica odontológica</small></p></div>
        <div className="reference-company-tabs"><b>Visão geral</b><span>Contatos</span><span>Atividades</span></div>
        <ul><li><MapPin />Porto Alegre - RS</li><li><AtSign />clinicaaurora.com.br</li></ul>
        <button type="button">Adicionar ao Pipeline <ArrowRight /></button>
      </div>

      <div className="reference-intelligence"><Check /><span>INTELIGÊNCIA<strong>QUE ORGANIZA RESULTADOS</strong></span></div>
    </div>
  )
}
