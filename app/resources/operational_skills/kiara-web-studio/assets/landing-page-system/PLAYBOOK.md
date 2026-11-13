# Playbook de Landing Pages Premium

## 1. Resultado esperado

Cada página deve:

- comunicar oferta, público e próximo passo em até 5 segundos;
- possuir uma ideia visual própria, reconhecível sem o logotipo;
- conduzir uma narrativa clara: tensão → promessa → prova → mecanismo → ação;
- usar movimento para orientar atenção e explicar relações;
- permanecer rápida, acessível e funcional em mobile;
- converter por meio de um CTA primário inequívoco.

## 2. Papéis e gates

| Etapa | Responsável | Saída obrigatória | Gate |
|---|---|---|---|
| Estratégia | Product/Marketing | brief, público, oferta, objeções, KPI | brief sem campos críticos vazios |
| UX | UX Architect | narrativa, seções, hierarquia, CTA | fluxo compreensível sem animação |
| Visual | UI Designer | moodboard, tokens, 2 direções de hero | identidade não genérica aprovada |
| Motion | Motion Designer | motion map e fallback | propósito e custo de cada efeito definidos |
| Arquitetura | Software Architect | componentes, dados, budgets | sem dependências redundantes |
| Implementação | Frontend | página responsiva e semântica | typecheck, lint e build verdes |
| Qualidade | QA/A11y/Performance | relatório e evidências | gates P0 aprovados |
| Final | Reality Checker | URLs, screenshots e métricas | afirmações sustentadas por evidência |

## 3. Contrato de entrada

Não iniciar implementação sem:

- produto/oferta e público prioritário;
- uma ação de conversão primária;
- promessa principal e três provas reais;
- tom de voz e restrições de marca;
- conteúdo, assets e integrações disponíveis;
- métrica principal e baseline, se existir;
- referências acompanhadas de “o que aproveitar” e “o que evitar”.

Ausência de conteúdo real deve gerar placeholders explicitamente marcados, nunca números, clientes ou depoimentos inventados.

## 4. Arquitetura narrativa

Use módulos, não uma sequência fixa. A escolha depende do estágio de consciência do visitante.

1. **Hero:** promessa específica, contexto, CTA e sinal de confiança.
2. **Problema/tensão:** demonstra entendimento da situação atual.
3. **Transformação:** descreve o estado desejado e o valor.
4. **Mecanismo:** explica como a solução funciona.
5. **Prova:** cases, métricas, logos ou demonstração verificável.
6. **Oferta:** escopo, entregáveis, planos ou próximos passos.
7. **Objeções:** FAQ, risco, prazo, segurança, integração.
8. **CTA final:** repete a decisão com contexto suficiente.

Regra: cada seção deve responder a uma pergunta real do visitante. Se não responder, remover.

## 5. Sistema visual variável

Cada projeto escolhe uma opção por eixo e registra a decisão no brief:

- composição: editorial, modular, canvas imersivo ou produto-first;
- contraste: dark luminous, light technical, chromatic ou monochrome;
- geometria: precisa, orgânica, brutalista ou suave;
- imagem: fotografia, 3D, produto, tipografia ou ilustração;
- movimento: cinematográfico, físico, minimalista ou orientado a dados.

### Tokens mínimos

- cores semânticas: canvas, surface, text, muted, accent, success, warning;
- escala tipográfica fluida com `clamp()`;
- espaçamento em escala coerente de 4/8 px;
- raios, bordas, sombras e glows limitados;
- durações: instantânea 120–180 ms, UI 180–300 ms, narrativa 500–900 ms;
- easings nomeados e reutilizados.

Evitar a assinatura genérica de IA: excesso de cards iguais, todos os textos centralizados, gradiente roxo/cyan sem relação com a marca, copy vaga, ícones decorativos repetidos e animação em todo elemento.

## 6. Motion map

Antes de animar, registrar para cada efeito: elemento, gatilho, propriedade, duração, propósito, custo e fallback.

- **Framer Motion:** entrada/saída de componentes, menu, hover, press, stagger curto e estados de UI.
- **GSAP + ScrollTrigger:** timelines longas, scrub, pin, parallax e narrativa controlada pelo scroll.
- **CSS:** loops ambientes simples, shimmer, glow e microinterações baratas.
- **Lenis:** apenas quando agrega ao conceito; não é requisito automático.

Regras:

- animar prioritariamente `transform` e `opacity`;
- no máximo uma sequência dominante por viewport;
- conteúdo e CTA nunca dependem da animação para existir;
- desativar pin, scrub pesado, cursor customizado e efeitos de ponteiro em telas pequenas quando degradarem a experiência;
- `prefers-reduced-motion` deve produzir uma experiência completa, não uma página quebrada.

## 7. Arquitetura técnica recomendada

```text
src/
  app/                 rotas, metadata e composição
  components/
    sections/          seções de negócio
    ui/                primitivos visuais
    motion/            Reveal, Parallax, Counter, MotionProvider
  content/             conteúdo tipado por projeto
  lib/                 analytics, motion e utilitários
  styles/              tokens e estilos globais
public/                mídia otimizada
tests/                 unit, a11y e e2e
```

Preferências:

- Next.js + TypeScript estrito + Tailwind;
- conteúdo separado da apresentação e validado por schema;
- Server Components por padrão; Client Components somente onde há interação;
- uma biblioteca principal por responsabilidade;
- imagens dimensionadas e formatos modernos; vídeo com poster e estratégia mobile;
- analytics para CTA, formulário, WhatsApp, scroll útil e erros.

## 8. Loop de IA com especialistas

1. **Product/UX:** critica clareza, promessa, objeções e ordem narrativa.
2. **UI/Motion:** propõe duas direções distintas e justifica uma.
3. **Arquitetura:** define componentes, budgets e riscos antes do código.
4. **Implementação:** trabalha apenas sobre brief e direção aprovados.
5. **Revisores independentes:** código, acessibilidade, segurança, performance e realidade.

O implementador não deve ser o único aprovador. Toda revisão deve citar arquivo/tela, gravidade, evidência e correção sugerida.

## 9. Aprendizado contínuo

Após publicar, registrar semanalmente:

- conversão do CTA e conclusão de formulário;
- origem, dispositivo e velocidade por percentil;
- abandono antes da prova e antes do CTA;
- resultados de experimentos;
- componentes e padrões que funcionaram ou falharam.

Promover um padrão ao sistema somente após repetição bem-sucedida; não transformar uma preferência isolada em regra global.

