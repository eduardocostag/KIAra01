# Landing Page System

Sistema operacional para criar landing pages premium com consistência, sem repetir um layout único.

## Como usar

1. Preencha `templates/brief.yaml` antes de qualquer código.
2. Defina a direção visual e a narrativa com `PLAYBOOK.md`.
3. Entregue o brief preenchido e `prompts/master-prompt.md` ao agente implementador.
4. Execute os gates de `QUALITY-GATES.md` em cada pull request.
5. Só publique quando todos os itens P0 da Definition of Done estiverem aprovados.

## Princípio central

O padrão não é “fundo preto + glow cyan”. O padrão é: mensagem específica, identidade própria, composição forte, movimento com propósito, mobile impecável e evidência objetiva de qualidade.

## Artefatos

- `PLAYBOOK.md`: processo, decisões e responsabilidades.
- `QUALITY-GATES.md`: critérios mensuráveis de aprovação.
- `templates/brief.yaml`: contrato de entrada para cada projeto.
- `prompts/master-prompt.md`: prompt reutilizável de planejamento e implementação.

## Fluxo resumido

Brief validado → conceito e narrativa → wireframe → direção visual → motion map → implementação → revisão → testes → evidências → publicação.

