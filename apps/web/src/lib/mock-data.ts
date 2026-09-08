export type LeadStage = "Novo" | "Em qualificação" | "Qualificado" | "Em conversa" | "Proposta"

export const demoLeads = [
  { id: "ana-costa", name: "Ana Costa", handle: "@anacosta.arq", intent: "Consultoria de interiores", score: 92, confidence: "Alta", stage: "Qualificado" as LeadStage, owner: "Eduardo", next: "Enviar briefing aprovado", due: "Hoje, 15:30", last: "há 8 min" },
  { id: "marina-lima", name: "Marina Lima", handle: "@marinaemcasa", intent: "Projeto para apartamento", score: 84, confidence: "Alta", stage: "Em conversa" as LeadStage, owner: "Eduardo", next: "Confirmar metragem", due: "Hoje, 17:00", last: "há 24 min" },
  { id: "lucas-rocha", name: "Lucas Rocha", handle: "@lucasrocha", intent: "Orçamento inicial", score: 71, confidence: "Média", stage: "Em qualificação" as LeadStage, owner: "Camila", next: "Perguntar prazo", due: "Amanhã, 09:00", last: "há 1 h" },
  { id: "bia-martins", name: "Beatriz Martins", handle: "@biamartins", intent: "Reforma residencial", score: 65, confidence: "Média", stage: "Novo" as LeadStage, owner: "Não atribuído", next: "Revisar contexto", due: "Amanhã, 11:00", last: "há 3 h" },
  { id: "rafa-souza", name: "Rafael Souza", handle: "@rafasouza", intent: "Projeto comercial", score: 88, confidence: "Alta", stage: "Proposta" as LeadStage, owner: "Camila", next: "Follow-up da proposta", due: "6 set, 10:00", last: "ontem" },
]

export const demoConversations = [
  {
    id: "ana-costa", name: "Ana Costa", handle: "@anacosta.arq", excerpt: "Queria entender como funciona a consultoria...", time: "14:22", unread: 2, status: "Nova", score: 92,
    intent: "Consultoria de interiores", confidence: "Alta", owner: "Eduardo", qualifiedAt: "hoje, 14:23",
    facts: ["Apartamento de 68 m²", "Localização: São Paulo", "Prazo: este semestre"],
    gaps: ["Ambientes prioritários", "Faixa de investimento"],
    nextAction: "Confirmar escopo e investimento antes de avançar para proposta.",
    suggestedDraft: "Oi, Ana! Obrigada por chamar. Para entender se a consultoria faz sentido, posso confirmar quais ambientes você quer priorizar e qual é a faixa de investimento prevista?",
    messages: [
      { id: "ana-1", from: "lead" as const, text: "Oi! Vi o projeto de vocês para apartamentos pequenos e adorei. Queria entender como funciona a consultoria.", time: "14:18" },
      { id: "ana-2", from: "lead" as const, text: "Meu apartamento tem 68 m², em São Paulo, e queria começar ainda este semestre.", time: "14:22" },
    ],
  },
  {
    id: "marina-lima", name: "Marina Lima", handle: "@marinaemcasa", excerpt: "O apartamento tem 82 m² e fica em Campinas.", time: "14:06", unread: 0, status: "Aguardando cliente", score: 84,
    intent: "Projeto completo de apartamento", confidence: "Alta", owner: "Eduardo", qualifiedAt: "hoje, 14:08",
    facts: ["Apartamento de 82 m²", "Localização: Campinas", "Imóvel recém-entregue"],
    gaps: ["Data desejada para início", "Referências de estilo"],
    nextAction: "Aguardar a confirmação da data de início antes de preparar o briefing.",
    suggestedDraft: "Oi, Marina! Perfeito, já registrei os 82 m² e a localização em Campinas. Quando você gostaria de iniciar o projeto? Se quiser, também pode me enviar referências do estilo que imagina.",
    messages: [
      { id: "marina-1", from: "lead" as const, text: "Olá! Comprei um apartamento e queria ajuda com o projeto completo.", time: "13:52" },
      { id: "marina-2", from: "operator" as const, text: "Que ótima notícia, Marina. Você consegue me contar a metragem e a cidade?", time: "13:57" },
      { id: "marina-3", from: "lead" as const, text: "O apartamento tem 82 m² e fica em Campinas.", time: "14:06" },
    ],
  },
  {
    id: "lucas-rocha", name: "Lucas Rocha", handle: "@lucasrocha", excerpt: "Vocês atendem projetos com prazo curto?", time: "13:18", unread: 1, status: "Aprovação", score: 71,
    intent: "Orçamento para reforma rápida", confidence: "Média", owner: "Camila", qualifiedAt: "hoje, 13:21",
    facts: ["Busca projeto residencial", "Prazo é o principal critério"],
    gaps: ["Prazo exato", "Metragem do imóvel", "Cidade do projeto"],
    nextAction: "Revisar o rascunho e solicitar aprovação antes de responder.",
    suggestedDraft: "Oi, Lucas! Atendemos projetos com cronogramas mais curtos após avaliar escopo e disponibilidade. Qual é o prazo que você precisa, a metragem e a cidade do imóvel?",
    messages: [
      { id: "lucas-1", from: "lead" as const, text: "Boa tarde! Vocês atendem projetos com prazo curto?", time: "13:18" },
    ],
  },
  {
    id: "bia-martins", name: "Beatriz Martins", handle: "@biamartins", excerpt: "Vi o trabalho de vocês no Instagram.", time: "11:42", unread: 0, status: "Nova", score: 65,
    intent: "Interesse inicial em reforma", confidence: "Média", owner: "Não atribuído", qualifiedAt: "hoje, 11:44",
    facts: ["Chegou por conteúdo publicado no Instagram", "Demonstrou interesse em reforma residencial"],
    gaps: ["Tipo de imóvel", "Localização", "Objetivo da reforma"],
    nextAction: "Entender o imóvel e o objetivo antes de qualificar a oportunidade.",
    suggestedDraft: "Oi, Beatriz! Que bom saber disso. Para eu te orientar melhor, você pode me contar qual é o tipo de imóvel, onde ele fica e o que pretende transformar na reforma?",
    messages: [
      { id: "bia-1", from: "lead" as const, text: "Oi! Vi o trabalho de vocês no Instagram e gostei muito.", time: "11:40" },
      { id: "bia-2", from: "lead" as const, text: "Estou pensando em fazer uma reforma, mas ainda estou organizando as ideias.", time: "11:42" },
    ],
  },
]

export const demoMessages = demoConversations[0].messages

export const hunterSignals = [
  { type: "Contatável", title: "Carolina Mendes", source: "DM inbound · Instagram", intent: "Pediu detalhes sobre consultoria", score: 89, freshness: "12 min", action: "Qualificar na Inbox", allowed: true },
  { type: "Sinal público", title: "Comentário em publicação", source: "Post público · Instagram", intent: "Demonstrou interesse em reforma", score: 67, freshness: "2 h", action: "Revisar para resposta pública", allowed: false },
  { type: "Bloqueado", title: "Contato com opt-out", source: "Histórico de atendimento", intent: "Sem finalidade permitida", score: 0, freshness: "3 dias", action: "Manter bloqueio", allowed: false },
]

export const funnelData = [
  { stage: "Novos", leads: 18 }, { stage: "Qualificação", leads: 12 }, { stage: "Qualificados", leads: 8 }, { stage: "Proposta", leads: 4 }, { stage: "Ganhos", leads: 2 },
]
