/**
 * Kiara Automation building blocks. `run` says how a block executes today:
 * - "browser": runs for real in this page (AI, code, logic, CRM read, notices);
 * - a connection id: needs that account/executor connected and is NOT simulated.
 */

export type CategoryId = "trigger" | "ai" | "logic" | "crm" | "messages" | "calendar" | "web" | "machine" | "code" | "social" | "ads"
export type FieldType = "text" | "textarea" | "number" | "select" | "time"
export type Field = { key: string; label: string; type: FieldType; placeholder?: string; options?: { value: string; label: string }[]; hint?: string; min?: number; max?: number }
export type Connection = "executor" | "whatsapp" | "email" | "google-calendar" | "postiz" | "meta-ads" | "google-ads" | "linkedin-ads" | "server"
export type NodeKind = {
  type: string
  category: CategoryId
  label: string
  description: string
  icon: string
  fields: Field[]
  defaults: Record<string, string | number>
  run: "browser" | Connection
  /** Two outputs ("Sim"/"Não") instead of one. */
  branches?: boolean
  trigger?: boolean
  ads?: "meta" | "google" | "linkedin"
}

export const categories: Record<CategoryId, { label: string; color: string }> = {
  trigger: { label: "Gatilhos", color: "#f5a524" },
  ai: { label: "Inteligência", color: "#a78bfa" },
  logic: { label: "Lógica", color: "#94a3b8" },
  crm: { label: "CRM", color: "#38bdf8" },
  messages: { label: "Mensagens", color: "#34d399" },
  calendar: { label: "Agenda", color: "#fb923c" },
  web: { label: "Sites", color: "#22d3ee" },
  machine: { label: "Computador", color: "#f472b6" },
  code: { label: "Código", color: "#e2e8f0" },
  social: { label: "Redes sociais", color: "#e879f9" },
  ads: { label: "Anúncios", color: "#facc15" },
}

export const connectionLabels: Record<Connection, string> = {
  executor: "Executor da Kiara neste computador (ou no servidor)",
  whatsapp: "WhatsApp conectado com o executor de envio",
  email: "Conta de e-mail",
  "google-calendar": "Google Agenda",
  postiz: "Contas sociais no Postiz (Integrações)",
  "meta-ads": "Conta de anúncios da Meta",
  "google-ads": "Conta do Google Ads",
  "linkedin-ads": "Conta de anúncios do LinkedIn",
  server: "Servidor da Kiara (agendamentos e eventos)",
}

const cadence = [{ value: "daily", label: "Todo dia" }, { value: "weekdays", label: "Dias úteis" }, { value: "weekly", label: "Toda semana" }]
const weekdays = ["Domingo", "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"].map((label, index) => ({ value: String(index), label }))
const objectives = [{ value: "traffic", label: "Tráfego para o site" }, { value: "leads", label: "Geração de leads" }, { value: "messages", label: "Mensagens no WhatsApp" }, { value: "awareness", label: "Reconhecimento" }]
const budgetFields: Field[] = [
  { key: "objective", label: "Objetivo", type: "select", options: objectives },
  { key: "daily", label: "Orçamento por dia (R$)", type: "number", min: 1 },
  { key: "days", label: "Duração (dias)", type: "number", min: 1, max: 365 },
  { key: "audience", label: "Público", type: "textarea", placeholder: "Ex.: donos de clínicas, 30-55 anos, Porto Alegre e região" },
]

export const nodeKinds: NodeKind[] = [
  { type: "trigger.manual", category: "trigger", label: "Executar agora", description: "Inicia o fluxo quando você clica em Executar.", icon: "Play", fields: [], defaults: {}, run: "browser", trigger: true },
  { type: "trigger.schedule", category: "trigger", label: "Agendamento", description: "Inicia o fluxo em dias e horários definidos. Agendamentos rodam no servidor da Kiara; ao executar aqui, o fluxo roda uma vez.", icon: "CalendarClock", fields: [{ key: "cadence", label: "Frequência", type: "select", options: cadence }, { key: "weekday", label: "Dia da semana", type: "select", options: weekdays, hint: "Usado na frequência semanal." }, { key: "time", label: "Horário", type: "time" }], defaults: { cadence: "weekly", weekday: "1", time: "09:00" }, run: "browser", trigger: true },
  { type: "trigger.lead", category: "trigger", label: "Novo lead no CRM", description: "Inicia quando um lead entra no CRM. Eventos rodam no servidor; ao executar aqui, usa o lead mais recente.", icon: "UserPlus", fields: [], defaults: {}, run: "browser", trigger: true },
  { type: "trigger.whatsapp", category: "trigger", label: "Mensagem no WhatsApp", description: "Inicia quando um contato autorizado envia mensagem.", icon: "MessageCircle", fields: [], defaults: {}, run: "server", trigger: true },

  { type: "ai.generate", category: "ai", label: "Kiara escreve", description: "A IA da Kiara gera um texto a partir das instruções. Use {{entrada}} para o resultado do bloco anterior.", icon: "Sparkles", fields: [{ key: "prompt", label: "Instruções", type: "textarea", placeholder: "Escreva uma legenda curta para Instagram sobre…" }], defaults: { prompt: "Resuma em tópicos curtos: {{entrada}}" }, run: "browser" },
  { type: "ai.classify", category: "ai", label: "Kiara decide", description: "A IA responde apenas SIM ou NÃO para a pergunta; use antes de uma condição.", icon: "BrainCircuit", fields: [{ key: "question", label: "Pergunta", type: "textarea", placeholder: "Esta mensagem demonstra interesse em comprar?" }], defaults: { question: "O texto a seguir demonstra interesse em comprar? {{entrada}}" }, run: "browser" },

  { type: "logic.condition", category: "logic", label: "Condição", description: "Segue pelo caminho Sim quando a entrada contém o texto informado.", icon: "GitBranch", fields: [{ key: "contains", label: "Contém o texto", type: "text", placeholder: "SIM" }], defaults: { contains: "SIM" }, run: "browser", branches: true },
  { type: "logic.delay", category: "logic", label: "Esperar", description: "Pausa antes do próximo passo. Execuções manuais esperam no máximo 60 segundos.", icon: "Timer", fields: [{ key: "seconds", label: "Segundos", type: "number", min: 1, max: 86400 }], defaults: { seconds: 5 }, run: "browser" },
  { type: "logic.notify", category: "logic", label: "Notificar", description: "Mostra o resultado no histórico da execução e como notificação do navegador.", icon: "Bell", fields: [{ key: "title", label: "Título", type: "text" }], defaults: { title: "Kiara Automation" }, run: "browser" },

  { type: "crm.read", category: "crm", label: "Ler leads do CRM", description: "Busca os leads ativos, com etapa e próxima ação.", icon: "Users", fields: [{ key: "stage", label: "Etapa", type: "select", options: [{ value: "active", label: "Em andamento" }, { value: "new", label: "Novos" }, { value: "qualified", label: "Qualificados" }, { value: "contacted", label: "Em contato" }, { value: "opportunity", label: "Oportunidades" }] }, { key: "limit", label: "Quantidade", type: "number", min: 1, max: 50 }], defaults: { stage: "active", limit: 10 }, run: "browser" },

  { type: "messages.whatsapp", category: "messages", label: "Enviar WhatsApp", description: "Envia a mensagem a um contato autorizado, respeitando horário, limite diário e opt-out.", icon: "Send", fields: [{ key: "to", label: "Para", type: "text", placeholder: "(11) 99999-9999 ou {{lead}}" }, { key: "text", label: "Mensagem", type: "textarea", placeholder: "{{entrada}}" }], defaults: { text: "{{entrada}}" }, run: "whatsapp" },
  { type: "messages.email", category: "messages", label: "Enviar e-mail", description: "Envia um e-mail pela conta conectada.", icon: "Mail", fields: [{ key: "to", label: "Para", type: "text" }, { key: "subject", label: "Assunto", type: "text" }, { key: "body", label: "Mensagem", type: "textarea", placeholder: "{{entrada}}" }], defaults: { body: "{{entrada}}" }, run: "email" },

  { type: "calendar.event", category: "calendar", label: "Criar evento", description: "Cria um compromisso na agenda conectada.", icon: "CalendarPlus", fields: [{ key: "title", label: "Título", type: "text" }, { key: "when", label: "Quando", type: "text", placeholder: "Amanhã às 10h" }, { key: "minutes", label: "Duração (min)", type: "number", min: 5 }], defaults: { minutes: 30 }, run: "google-calendar" },

  { type: "web.http", category: "web", label: "Consultar API", description: "Faz uma requisição GET e passa a resposta adiante. Muitos sites bloqueiam chamadas do navegador (CORS); nesses casos use o executor.", icon: "Globe", fields: [{ key: "url", label: "Endereço (https)", type: "text", placeholder: "https://…" }], defaults: {}, run: "browser" },
  { type: "web.browse", category: "web", label: "Navegar em site", description: "Abre um site, preenche e clica conforme as instruções, com confirmação para ações sensíveis.", icon: "MousePointerClick", fields: [{ key: "url", label: "Site", type: "text" }, { key: "steps", label: "O que fazer", type: "textarea" }], defaults: {}, run: "executor" },

  { type: "machine.command", category: "machine", label: "Ação no computador", description: "Executa uma ação permitida no computador (abrir programa, diagnóstico, comando da lista permitida), com confirmação.", icon: "Monitor", fields: [{ key: "action", label: "Ação", type: "textarea", placeholder: "Abrir o Excel com o relatório de vendas" }], defaults: {}, run: "executor" },
  { type: "machine.files", category: "machine", label: "Organizar arquivos", description: "Move, renomeia ou cria arquivos em pastas autorizadas.", icon: "FolderSync", fields: [{ key: "folder", label: "Pasta", type: "text" }, { key: "rule", label: "Regra", type: "textarea" }], defaults: {}, run: "executor" },

  { type: "code.js", category: "code", label: "Código JavaScript", description: "Transforma dados com JavaScript isolado (sem acesso à rede ou à página). Use a variável entrada e retorne o resultado.", icon: "Code", fields: [{ key: "code", label: "Código", type: "textarea" }], defaults: { code: "return String(entrada).toUpperCase()" }, run: "browser" },

  { type: "social.instagram", category: "social", label: "Postar no Instagram", description: "Publica ou agenda o post na conta conectada.", icon: "Camera", fields: [{ key: "caption", label: "Legenda", type: "textarea", placeholder: "{{entrada}}" }, { key: "media", label: "Imagem ou vídeo (URL)", type: "text" }], defaults: { caption: "{{entrada}}" }, run: "postiz" },
  { type: "social.facebook", category: "social", label: "Postar no Facebook", description: "Publica ou agenda na página conectada.", icon: "ThumbsUp", fields: [{ key: "text", label: "Texto", type: "textarea", placeholder: "{{entrada}}" }], defaults: { text: "{{entrada}}" }, run: "postiz" },
  { type: "social.linkedin", category: "social", label: "Postar no LinkedIn", description: "Publica no perfil ou página conectada.", icon: "Building2", fields: [{ key: "text", label: "Texto", type: "textarea", placeholder: "{{entrada}}" }], defaults: { text: "{{entrada}}" }, run: "postiz" },
  { type: "social.google", category: "social", label: "Post no Google (Perfil da Empresa)", description: "Publica novidade no Perfil da Empresa no Google.", icon: "MapPin", fields: [{ key: "text", label: "Texto", type: "textarea", placeholder: "{{entrada}}" }], defaults: { text: "{{entrada}}" }, run: "postiz" },

  { type: "ads.meta", category: "ads", label: "Anúncio Meta (Instagram/Facebook)", description: "Cria a campanha com orçamento, público e criativo.", icon: "Megaphone", fields: budgetFields, defaults: { objective: "messages", daily: 20, days: 7 }, run: "meta-ads", ads: "meta" },
  { type: "ads.google", category: "ads", label: "Anúncio Google", description: "Cria a campanha de pesquisa com palavras-chave e orçamento.", icon: "Search", fields: [...budgetFields, { key: "keywords", label: "Palavras-chave", type: "textarea", placeholder: "site para clínica, dentista porto alegre" }], defaults: { objective: "traffic", daily: 30, days: 7 }, run: "google-ads", ads: "google" },
  { type: "ads.linkedin", category: "ads", label: "Anúncio LinkedIn", description: "Cria a campanha B2B por cargo, setor e empresa.", icon: "Briefcase", fields: budgetFields, defaults: { objective: "leads", daily: 60, days: 7 }, run: "linkedin-ads", ads: "linkedin" },
]

export const nodeKind = (type: string) => nodeKinds.find((kind) => kind.type === type)

/**
 * How each ad platform charges. Rules here are the platforms' published billing
 * mechanics, not performance estimates; prices come from an auction and vary.
 */
export const adsBilling: Record<"meta" | "google" | "linkedin", { name: string; how: string[]; minimum: string; monthlyCap?: number }> = {
  meta: {
    name: "Meta Ads",
    how: ["Leilão: você paga por mil impressões (CPM) ou por clique, conforme o objetivo.", "A Meta distribui o orçamento ao longo dos dias e pode gastar um pouco mais em dias melhores, dentro do total da semana.", "Cobrança no cartão ou saldo pré-pago (Pix/boleto); impostos podem ser somados à fatura."],
    minimum: "O mínimo diário é baixo e varia por objetivo e moeda; o próprio Gerenciador avisa se o valor estiver abaixo.",
  },
  google: {
    name: "Google Ads",
    how: ["Leilão por clique (CPC): você paga quando alguém clica no anúncio.", "Em um dia o gasto pode chegar a 2× o orçamento diário médio, mas no mês não passa de 30,4× esse valor.", "Cobrança automática no cartão ou pagamentos manuais antecipados."],
    minimum: "Não há orçamento mínimo.",
    monthlyCap: 30.4,
  },
  linkedin: {
    name: "LinkedIn Ads",
    how: ["Leilão por clique, impressão ou envio, com segmentação por cargo, setor e empresa.", "Costuma ter custo por clique mais alto que Meta e Google, compensado pelo público B2B.", "Cobrança no cartão de crédito."],
    minimum: "Mínimo de US$ 10 por dia por campanha (convertido para a moeda da conta).",
  },
}

export type FlowNode = { id: string; type: string; x: number; y: number; config: Record<string, string | number> }
export type FlowEdge = { id: string; from: string; to: string; port?: "yes" | "no" }
export type Workflow = { id: string; name: string; nodes: FlowNode[]; edges: FlowEdge[]; updatedAt: number }

let counter = 0
export const newId = (prefix: string) => `${prefix}-${Date.now().toString(36)}-${(counter++).toString(36)}`

function node(type: string, x: number, y: number, config: Record<string, string | number> = {}): FlowNode {
  return { id: newId("n"), type, x, y, config: { ...nodeKind(type)?.defaults, ...config } }
}

function chain(name: string, nodes: FlowNode[], extra: FlowEdge[] = []): Workflow {
  const edges = nodes.slice(1).map((current, index) => ({ id: newId("e"), from: nodes[index].id, to: current.id }))
  return { id: newId("w"), name, nodes, edges: [...edges, ...extra], updatedAt: Date.now() }
}

export const templates: { id: string; title: string; description: string; build: () => Workflow }[] = [
  { id: "crm-digest", title: "Resumo diário do CRM", description: "Todo dia às 8h a Kiara lê seus leads e resume o que fazer primeiro.", build: () => chain("Resumo diário do CRM", [
    node("trigger.schedule", 60, 160, { cadence: "daily", time: "08:00" }), node("crm.read", 330, 160), node("ai.generate", 600, 160, { prompt: "Com base nestes leads, diga em 5 tópicos curtos o que priorizar hoje e por quê:\n{{entrada}}" }), node("logic.notify", 870, 160, { title: "Prioridades de hoje" }),
  ]) },
  { id: "instagram-weekly", title: "Post semanal no Instagram", description: "Toda segunda a Kiara escreve a legenda e publica no Instagram.", build: () => chain("Post semanal no Instagram", [
    node("trigger.schedule", 60, 160, { cadence: "weekly", weekday: "1", time: "10:00" }), node("ai.generate", 330, 160, { prompt: "Escreva uma legenda de Instagram com até 600 caracteres e 5 hashtags sobre: sites para clínicas que trazem pacientes pelo Google." }), node("social.instagram", 600, 160),
  ]) },
  { id: "lead-welcome", title: "Boas-vindas no WhatsApp", description: "Quando entra um lead, a Kiara decide se vale abordar e envia a primeira mensagem.", build: () => {
    const nodes = [node("trigger.lead", 60, 200), node("ai.classify", 330, 200, { question: "Este lead parece adequado para receber uma primeira abordagem comercial? {{entrada}}" }), node("logic.condition", 600, 200), node("ai.generate", 870, 110, { prompt: "Escreva uma primeira mensagem curta e cordial de WhatsApp para este lead, sem parecer automática: {{entrada}}" }), node("messages.whatsapp", 1140, 110), node("logic.notify", 870, 300, { title: "Lead descartado para abordagem" })]
    const [trigger, classify, condition, write, send, skip] = nodes
    return { id: newId("w"), name: "Boas-vindas no WhatsApp", updatedAt: Date.now(), nodes, edges: [
      { id: newId("e"), from: trigger.id, to: classify.id }, { id: newId("e"), from: classify.id, to: condition.id },
      { id: newId("e"), from: condition.id, to: write.id, port: "yes" }, { id: newId("e"), from: write.id, to: send.id },
      { id: newId("e"), from: condition.id, to: skip.id, port: "no" },
    ] }
  } },
  { id: "ads-launch", title: "Campanha Meta + Google", description: "A Kiara cria os textos e monta campanhas com orçamento e custo total visíveis.", build: () => chain("Campanha Meta + Google", [
    node("trigger.manual", 60, 160), node("ai.generate", 330, 160, { prompt: "Crie 3 títulos e 2 textos curtos de anúncio para: sites profissionais para clínicas, com chamada para WhatsApp." }), node("ads.meta", 600, 160), node("ads.google", 870, 160, { keywords: "site para clínica\ncriação de site odontologia" }),
  ]) },
]

export function emptyWorkflow(): Workflow {
  return { id: newId("w"), name: "Novo fluxo", nodes: [node("trigger.manual", 80, 180)], edges: [], updatedAt: Date.now() }
}
