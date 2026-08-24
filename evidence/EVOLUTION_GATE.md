# Kiara - gate das evolucoes 2 a 7

Data: 2026-08-24 (America/Sao_Paulo)

## Implementado

- Inteligencia visual: verificacao perceptual efemera antes/depois, opt-in.
- Voz: endpointing adaptativo, wake word no inicio, protecao por turno e escolha SAPI.
- Memoria: tipos e perfis, proveniencia, expiracao, revisao, consolidacao e explicacao.
- Planejamento: objetivos SQLite persistentes, checkpoints, pausa/retomada e risco.
- Automacoes: previa, modo ensinar em rascunho, modelos, historico e retry idempotente.
- Painel: timeline de auditoria e exportacao redigida, com melhorias de acessibilidade.

## Gates

- Testes finais: 150 aprovados; 4 ignorados por exigirem hardware/sessao interativa.
- Ruff: aprovado.
- AppSec: nenhum P0/P1 aberto apos corrigir migracao de memoria e recursao de falha.
- Code review: nenhum P0/P1 aberto apos serializar acesso concorrente a memoria SQLite.
- Acessibilidade automatizada: 9 testes direcionados aprovados.
- Executavel portatil: smoke test de 5 segundos aprovado, sem processo filho residual.
- Instalador: instalacao silenciosa, smoke test instalado e desinstalacao aprovados; codigo 0
  e pasta temporaria removida.

Resultado detalhado: `evidence/pytest-evolution-final.xml`.

## Limites honestos

- Wake word usa STT local; nao ha keyword spotting acustico dedicado nem biometria de locutor.
- Validacao visual e evidencia auxiliar; a pos-condicao semantica/UIA continua autoritativa.
- NVDA/JAWS, contraste e zoom ainda exigem validacao manual em sessao interativa.
- Integracoes remotas continuam dependentes de credenciais reais.

## Artefatos regenerados

- `dist/Kiara.exe` - SHA-256
  `FACDD14B9538D9C0423FE680439A498078D370BD401657BB2B0EF28A6B336B25`
- `dist/installer/Kiara-Setup-0.1.0.exe` - SHA-256
  `73D8EB6630EEFD03D8B266EB6D86094AD85B256211B60DFEF892E6774D01C7BD`
- Authenticode: ambos `NotSigned`; builds locais, nao destinados a distribuicao publica.
