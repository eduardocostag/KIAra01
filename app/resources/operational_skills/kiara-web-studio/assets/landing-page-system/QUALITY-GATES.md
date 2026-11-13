# Quality Gates

## P0 — bloqueia publicação

- Brief validado e nenhuma prova fictícia.
- CTA primário funciona e gera evento de analytics.
- Conteúdo essencial acessível sem JavaScript de animação.
- Sem overflow horizontal em 320, 375, 390, 414, 768, 1024, 1440 e 1920 px.
- Navegação, menu, formulário e foco funcionam por teclado.
- Contraste WCAG AA, landmarks semânticos, nomes acessíveis e foco visível.
- `prefers-reduced-motion` remove movimento não essencial.
- TypeScript, lint, testes e build de produção passam.
- Nenhum erro no console nos fluxos principais.
- Links externos, WhatsApp, formulário, metadata, OG e favicon verificados.
- Todo site profissional inclui serviços com imagens, apresentação, localização, horários, canais de contato, FAQ e CTA final.
- Telefones, endereços, registros profissionais, depoimentos e resultados permanecem configuráveis; nenhum dado fictício pode ser publicado como real.
- Segredos ausentes do bundle e do repositório.

## Budgets automáticos

- Lighthouse mobile: Performance ≥ 90, Accessibility ≥ 95, Best Practices ≥ 95, SEO ≥ 95.
- Core Web Vitals alvo em campo: LCP p75 ≤ 2,5 s, INP p75 ≤ 200 ms, CLS ≤ 0,1.
- JavaScript inicial do projeto: alvo ≤ 180 KB gzip; exceções exigem justificativa.
- Imagem hero responsiva, dimensões reservadas e sem bytes desnecessários.
- Zero violações críticas ou sérias no axe.

Os números são defaults. Um projeto pode torná-los mais rigorosos; relaxamento exige registro explícito de risco.

## Regressão visual

Capturar ao menos:

- 390 × 844;
- 768 × 1024;
- 1440 × 900;
- modo normal e reduced motion;
- hero, menu aberto, seção de prova, formulário e CTA final.

Diferenças intencionais atualizam o baseline com aprovação humana. Não aceitar snapshots automaticamente.

## Testes de interação

- CTA hero → destino correto;
- menu mobile abre, mantém foco e fecha por Escape;
- formulário cobre sucesso, validação, erro e reenvio;
- WhatsApp usa número e mensagem configurados;
- animações não bloqueiam clique, leitura ou histórico do navegador;
- todo template com foto ou vídeo de profissional carrega `character-motion.js`: entrada, respiração, parallax, resposta à rolagem e fallback para `prefers-reduced-motion`;
- “movimento do personagem” significa vídeo IA com mudança real de pose: começa natural, cruza os braços, vira levemente de lado e termina olhando para a câmera;
- para este projeto, o usuário autorizou o envio das imagens dos profissionais ao Hugging Face quando solicitar movimento real do personagem;
- a troca da foto real do profissional preserva as classes do contêiner (`portrait`, `photo` ou `visual`) para ativar o movimento automaticamente;
- links internos respeitam header fixo;
- mídia falha de forma elegante em rede lenta.

## Revisão visual humana

Pontuar de 0 a 2; mínimo 16/20 e nenhum zero:

1. clareza da proposta;
2. hierarquia e ritmo;
3. identidade própria;
4. qualidade tipográfica;
5. coerência de cor e imagem;
6. motion com propósito;
7. acabamento mobile;
8. prova e credibilidade;
9. força do CTA;
10. ausência de padrões genéricos.

## Evidência de conclusão

Anexar ao handoff:

- saída do build e testes;
- relatório Lighthouse;
- relatório axe;
- screenshots dos viewports alvo;
- lista dos eventos de analytics verificados;
- limitações conhecidas e decisões registradas.
