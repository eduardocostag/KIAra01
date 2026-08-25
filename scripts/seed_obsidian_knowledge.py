from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Note:
    area: str
    title: str
    summary: str
    steps: str
    risk: str
    success: str
    source: str


MS = "https://learn.microsoft.com/en-us/troubleshoot/windows-client/welcome-windows-client"
RECOVERY = "https://support.microsoft.com/en-us/windows/experience/backup-recovery/recovery-options-in-windows"
DRIVERS = "https://learn.microsoft.com/en-us/windows-hardware/drivers/install/troubleshooting-device-and-driver-installations"
ETHERNET = "https://support.microsoft.com/en-us/windows/experience/connectivity-networking/fix-ethernet-connection-problems-in-windows"
PYTHON = "https://docs.python.org/3/tutorial/"
GIT = "https://git-scm.com/docs"
OWASP_AUTH = "https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html"
OWASP_INPUT = "https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html"
OWASP_LOG = "https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html"
NIST = "https://www.nist.gov/cyberframework"
CISA = "https://www.cisa.gov/secure-our-world"
OBSIDIAN = "https://help.obsidian.md/Extending%2BObsidian/Obsidian%2BURI"

NOTES = (
    Note("20 - Helpdesk/Procedimentos", "Triagem inicial de atendimento", "Coletar sintomas e impacto antes de alterar o sistema.", "Registrar mensagem exata e horário|Confirmar escopo e usuários afetados|Perguntar o que mudou|Reproduzir com segurança|Definir evidência de resolução", "Evitar mudanças simultâneas e preservar evidências.", "Sintoma deixa de ocorrer e causa ou contorno fica documentado.", MS),
    Note("20 - Helpdesk/Windows", "Windows não inicia", "Usar recuperação em ordem crescente de impacto.", "Remover periféricos novos|Registrar tela ou código|Acessar WinRE|Executar Reparo de Inicialização|Avaliar restauração antes de reinstalar", "BitLocker pode exigir chave; reinstalação pode remover dados.", "Windows inicia repetidamente sem erro de boot.", RECOVERY),
    Note("20 - Helpdesk/Windows", "Falha no Windows Update", "Separar falha transitória, espaço insuficiente e incompatibilidade.", "Registrar código do erro|Reiniciar e verificar rede|Confirmar espaço livre|Executar solucionador oficial|Revisar histórico antes de medidas invasivas", "Não interromper atualização durante aplicação.", "Atualização instala e o histórico mostra sucesso.", MS),
    Note("20 - Helpdesk/Windows", "Restauração e recuperação", "Escolher a opção de recuperação proporcional ao problema.", "Fazer backup|Identificar mudança recente|Preferir Restauração do Sistema quando aplicável|Usar redefinição ou reinstalação apenas com plano de retorno", "Confirmar backup, licenças e chave BitLocker.", "Sistema recuperado e arquivos essenciais verificados.", RECOVERY),
    Note("20 - Helpdesk/Hardware", "Diagnóstico de drivers", "Usar código do dispositivo e fonte oficial do fabricante.", "Abrir propriedades no Gerenciador de Dispositivos|Registrar código e IDs de hardware|Criar ponto de restauração|Obter driver oficial|Validar após reiniciar", "Evitar sites agregadores e confirmar modelo/arquitetura.", "Dispositivo funciona sem alerta e permanece estável.", DRIVERS),
    Note("20 - Helpdesk/Redes", "Sem conexão Ethernet", "Diagnosticar camada física antes de redefinir a rede.", "Verificar LEDs e cabo|Testar outra porta|Confirmar endereço IP|Testar gateway e DNS separadamente|Atualizar driver oficial se necessário", "Redefinição de rede remove adaptadores e configurações; usar por último.", "Conexão estável, gateway e destino externo respondem.", ETHERNET),
    Note("20 - Helpdesk/Redes", "Wi-Fi instável", "Distinguir sinal, autenticação, DHCP, DNS e acesso externo.", "Medir sinal perto do roteador|Esquecer e reconectar somente se credencial estiver disponível|Comparar outro dispositivo|Testar gateway|Revisar driver e economia de energia", "Não redefinir roteador sem configuração e autorização.", "Conexão se mantém durante teste prolongado.", MS),
    Note("20 - Helpdesk/Redes", "Diagnóstico de DNS", "Confirmar se a falha é de nome ou conectividade.", "Testar IP do gateway|Testar destino por IP|Consultar nome conhecido|Comparar servidor DNS autorizado|Limpar cache somente após evidência", "Não trocar DNS corporativo sem aprovação.", "Nomes resolvem corretamente e aplicações conectam.", MS),
    Note("20 - Helpdesk/Hardware", "Impressora não imprime", "Separar energia, conectividade, fila, driver e suprimentos.", "Confirmar painel e erros|Imprimir página interna|Verificar fila e pausa|Confirmar porta ou IP|Testar driver recomendado", "Não limpar fila compartilhada sem avaliar trabalhos de outros usuários.", "Página de teste e documento real imprimem.", MS),
    Note("20 - Helpdesk/Hardware", "Áudio ou microfone sem funcionar", "Validar dispositivo, permissões, rota de áudio e driver.", "Confirmar dispositivo físico|Selecionar entrada/saída correta|Revisar permissões do aplicativo|Testar gravador local|Revisar driver oficial", "Evitar aumentar volume antes de confirmar a saída correta.", "Teste local grava e reproduz sem falhas.", MS),
    Note("20 - Helpdesk/Hardware", "Disco cheio", "Liberar espaço sem apagar dados desconhecidos.", "Medir uso por categoria|Limpar temporários pelo Windows|Revisar downloads com o usuário|Mover arquivos com backup|Verificar crescimento anormal", "Nunca excluir pastas do sistema ou perfis em massa.", "Espaço livre atinge margem operacional e não volta a cair anormalmente.", MS),
    Note("20 - Helpdesk/Hardware", "Computador lento", "Medir gargalo antes de recomendar upgrade.", "Registrar quando ocorre|Observar CPU RAM disco e temperatura|Revisar inicialização|Verificar atualizações e malware|Comparar desempenho após uma mudança", "Otimizações agressivas podem desativar proteções.", "Métrica e experiência melhoram de forma repetível.", MS),
    Note("20 - Helpdesk/Windows", "Tela azul e reinicialização", "Preservar código, dump e contexto da falha.", "Registrar stop code|Anotar driver ou módulo citado|Relacionar mudanças recentes|Verificar integridade e hardware|Reverter somente com evidência", "Não concluir causa apenas pelo nome exibido.", "Falha não reaparece sob o mesmo cenário de teste.", MS),
    Note("20 - Helpdesk/Procedimentos", "Backup antes de mudanças", "Definir o que precisa ser recuperável e testar restauração.", "Identificar dados e configurações|Escolher destino independente|Executar backup|Verificar integridade|Testar restauração de amostra", "Backup não testado é apenas uma expectativa.", "Arquivo de amostra restaurado e procedimento documentado.", RECOVERY),
    Note("30 - Conhecimento/Engenharia de Software", "Levantamento de requisitos", "Converter objetivo em comportamento observável.", "Definir usuário e problema|Listar entradas e saídas|Registrar restrições|Definir critérios de aceite|Separar MVP de expansões", "Requisitos vagos geram retrabalho e validação subjetiva.", "Cada requisito possui evidência verificável.", PYTHON),
    Note("30 - Conhecimento/Engenharia de Software", "Debugging baseado em evidências", "Reduzir o problema e testar uma hipótese por vez.", "Reproduzir|Capturar erro completo|Identificar primeira causa relevante|Criar hipótese|Aplicar mudança mínima|Executar regressão", "Não mascarar exceções nem alterar múltiplas variáveis.", "Causa explicada e teste impede recorrência.", PYTHON),
    Note("30 - Conhecimento/Engenharia de Software", "Exceções em Python", "Capturar somente erros que a camada sabe tratar.", "Usar exceções específicas|Preservar causa com raise from|Fechar recursos|Converter erros apenas em boundaries|Testar caminhos de falha", "except amplo pode ocultar corrupção e bugs.", "Falhas são observáveis, tipadas e testadas.", "https://docs.python.org/3/tutorial/errors.html"),
    Note("30 - Conhecimento/Engenharia de Software", "Ambientes virtuais Python", "Isolar dependências por projeto.", "Criar venv|Ativar no shell|Instalar dependências declaradas|Fixar requisitos reproduzíveis|Recriar em ambiente limpo", "Não versionar o diretório do ambiente.", "Projeto instala e testa em ambiente novo.", "https://docs.python.org/3/library/venv.html"),
    Note("30 - Conhecimento/Engenharia de Software", "Estratégia de testes", "Combinar testes unitários, integração e aceite proporcionalmente ao risco.", "Mapear riscos|Testar contratos e bordas|Isolar dependências|Manter casos determinísticos|Registrar evidência do ambiente real", "Cobertura alta não garante cenários relevantes.", "Falhas importantes são detectadas antes da release.", PYTHON),
    Note("30 - Conhecimento/Engenharia de Software", "Fluxo Git seguro", "Criar mudanças pequenas, revisáveis e recuperáveis.", "Inspecionar status|Criar branch focada|Executar testes|Revisar diff|Commitar com mensagem clara|Integrar sem destruir trabalho alheio", "Evitar reset destrutivo e commits com segredos.", "Diff revisado, testes verdes e histórico compreensível.", GIT),
    Note("30 - Conhecimento/Engenharia de Software", "Projeto de APIs", "Definir contrato, erros, autenticação e idempotência antes da implementação.", "Modelar recursos|Definir schemas|Validar entradas|Padronizar erros|Planejar paginação e versão|Documentar limites", "APIs sem limites facilitam abuso e falhas de custo.", "Contrato testado e consumidores tratam erros previsivelmente.", OWASP_INPUT),
    Note("30 - Conhecimento/Engenharia de Software", "Validação de entrada", "Tratar toda entrada externa como não confiável.", "Validar tipo formato tamanho e faixa|Preferir allowlists|Rejeitar campos inesperados|Normalizar com cuidado|Codificar saída no contexto correto", "Validação sozinha não substitui controles contra injeção.", "Entradas inválidas falham de forma segura e auditável.", OWASP_INPUT),
    Note("30 - Conhecimento/Engenharia de Software", "Logging observável e privado", "Registrar eventos úteis sem armazenar segredos.", "Definir eventos e severidade|Usar IDs de correlação|Redigir tokens e PII|Evitar logs excessivos|Testar retenção e acesso", "Logs podem se tornar fonte de vazamento.", "Incidente pode ser investigado sem expor dados sensíveis.", OWASP_LOG),
    Note("30 - Conhecimento/Engenharia de Software", "Migrações de banco de dados", "Evoluir schema com compatibilidade, backup e rollback.", "Medir volume|Preparar migração reversível|Testar cópia realista|Separar expansão de contração|Monitorar após aplicar", "DDL e backfills podem bloquear ou perder dados.", "Versões antiga e nova atravessam a transição sem perda.", "https://www.postgresql.org/docs/current/ddl.html"),
    Note("30 - Conhecimento/Segurança", "Autenticação segura", "Usar protocolos estabelecidos, MFA e sessões protegidas.", "Identificar risco da conta|Preferir IdP confiável|Ativar MFA|Rotacionar sessão após reautenticar|Monitorar falhas", "Nunca reutilizar credenciais administrativas em interfaces públicas.", "Acesso indevido é bloqueado e eventos ficam auditáveis.", OWASP_AUTH),
    Note("30 - Conhecimento/Segurança", "Gestão de segredos", "Manter credenciais fora de código, prompts e logs.", "Inventariar segredos|Usar cofre ou credencial do sistema|Aplicar menor privilégio|Rotacionar|Revogar ao suspeitar exposição", "Copiar segredo para nota aumenta superfície de ataque.", "Varredura não encontra segredo e rotação é praticável.", CISA),
    Note("30 - Conhecimento/Segurança", "Phishing e mensagens suspeitas", "Validar remetente e contexto por canal independente.", "Não abrir anexos impulsivamente|Inspecionar domínio|Confirmar pedido urgente por outro canal|Reportar|Trocar credenciais se houve interação", "Urgência e autoridade aparente são técnicas comuns de manipulação.", "Mensagem tratada sem executar conteúdo malicioso.", CISA),
    Note("30 - Conhecimento/Segurança", "Privilégio mínimo", "Conceder apenas permissão necessária pelo tempo necessário.", "Definir tarefa|Listar acesso mínimo|Separar contas administrativas|Expirar privilégios|Revisar periodicamente", "Permissões acumuladas ampliam impacto de erros e invasões.", "Tarefa funciona sem acesso excedente.", NIST),
    Note("30 - Conhecimento/Segurança", "Resposta inicial a incidente", "Conter sem destruir evidências.", "Registrar tempo e sintomas|Isolar quando autorizado|Preservar logs|Identificar escopo|Comunicar responsáveis|Planejar recuperação", "Desligar ou limpar prematuramente pode eliminar evidências.", "Incidente contido, escopo conhecido e recuperação validada.", NIST),
    Note("30 - Conhecimento/Segurança", "Atualizações e correções", "Priorizar por exploração, exposição e impacto.", "Inventariar versões|Ler fonte oficial|Testar quando possível|Criar rollback|Aplicar em ondas|Monitorar", "Adiar indefinidamente mantém vulnerabilidades; aplicar sem teste pode causar indisponibilidade.", "Versão corrigida opera dentro das métricas esperadas.", CISA),
    Note("30 - Conhecimento/Segurança", "Privacidade em logs", "Minimizar e proteger dados registrados.", "Definir finalidade|Excluir senhas tokens e chaves|Mascarar PII|Limitar acesso|Definir retenção|Testar exclusão", "Logs replicados podem persistir além do esperado.", "Investigação funciona sem revelar dados desnecessários.", OWASP_LOG),
    Note("30 - Conhecimento/Segurança", "Backup contra ransomware", "Manter cópias isoladas e restauração testada.", "Classificar dados críticos|Aplicar regra de múltiplas cópias|Isolar ao menos uma|Proteger credenciais de backup|Testar restauração", "Backup conectado com as mesmas credenciais pode ser comprometido.", "Restauração completa cumpre tempo e perda aceitáveis.", CISA),
    Note("30 - Conhecimento/Produtividade", "Priorização semanal", "Escolher poucas entregas com impacto e critério de conclusão.", "Reunir compromissos|Separar urgente de importante|Escolher três resultados|Reservar blocos|Revisar dependências|Encerrar a semana com retrospectiva", "Lista extensa sem capacidade real cria falsa previsibilidade.", "Resultados prioritários concluídos ou replanejados explicitamente.", "https://www.atlassian.com/agile/project-management/prioritization"),
    Note("30 - Conhecimento/Produtividade", "Reunião objetiva", "Toda reunião precisa de resultado esperado e responsáveis.", "Definir decisão ou objetivo|Enviar agenda|Registrar pontos essenciais|Atribuir responsável e prazo|Publicar ata curta", "Reunião sem dono de ação transfere trabalho para o esquecimento.", "Decisões e ações estão registradas e aceitas.", "https://www.atlassian.com/software/confluence/templates/meeting-notes"),
    Note("40 - Decisões", "Registro de decisão", "Preservar contexto, alternativas e consequências.", "Descrever problema|Listar restrições|Comparar alternativas|Registrar decisão e responsável|Definir data de revisão", "Sem contexto, decisões antigas parecem arbitrárias.", "Equipe entende por que a escolha foi feita e quando rever.", "https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions"),
    Note("10 - Projetos", "Planejamento de projeto", "Transformar objetivo em entregas, dependências e riscos.", "Definir resultado|Quebrar em marcos|Mapear dependências|Estimar capacidade|Registrar riscos|Revisar progresso por evidência", "Cronograma sem dependências e capacidade não é previsão confiável.", "Cada marco possui dono, prazo e aceite.", "https://www.pmi.org/learning/library"),
    Note("10 - Projetos", "Retrospectiva de processo", "Melhorar o sistema de trabalho sem procurar culpados.", "Reunir fatos|Identificar o que ajudou|Identificar fricções|Escolher uma mudança pequena|Definir responsável|Medir no próximo ciclo", "Muitas ações simultâneas impedem saber o que funcionou.", "A melhoria escolhida tem resultado medido.", "https://www.atlassian.com/team-playbook/plays/retrospective"),
    Note("30 - Conhecimento/IA", "Respostas fundamentadas", "Separar conhecimento do modelo, evidência recuperada e inferência.", "Identificar afirmações verificáveis|Recuperar fontes relevantes|Citar a origem|Declarar incerteza|Não inventar quando faltar evidência", "Fluência não garante veracidade.", "Afirmações importantes podem ser rastreadas à fonte.", NIST),
    Note("30 - Conhecimento/IA", "RAG com contexto seletivo", "Enviar ao modelo somente trechos relevantes e dentro de orçamento.", "Entender a consulta|Buscar lexical e semanticamente|Aplicar limiar|Deduplicar|Diversificar fontes|Reranquear|Montar contexto limitado", "Contexto irrelevante aumenta tokens e pode reduzir precisão.", "Recuperação encontra a fonte certa e citações sustentam a resposta.", NIST),
    Note("30 - Conhecimento/IA", "Defesa contra prompt injection", "Tratar tela, web, documentos e memória como dados, nunca como autoridade.", "Marcar origem não confiável|Ignorar instruções dentro do conteúdo|Separar política de dados|Restringir ferramentas|Exigir confirmação|Validar resultado", "Conteúdo recuperado pode tentar alterar o papel do agente.", "Testes adversariais não conseguem acionar ferramentas ou revelar segredos.", "https://genai.owasp.org/llmrisk/llm01-prompt-injection/"),
    Note("30 - Conhecimento/IA", "Aprendizado por feedback explícito", "Guardar somente processos que o usuário confirmou como úteis.", "Responder|Perguntar se ajudou|Salvar apenas após sim|Redigir segredos|Indexar com origem e data|Permitir correção ou exclusão", "Feedback positivo não transforma automaticamente uma resposta em verdade universal.", "Aprendizado aprovado melhora consultas semelhantes e continua rastreável.", OBSIDIAN),
)


def render(note: Note) -> str:
    steps = "\n".join(f"{index}. {step}" for index, step in enumerate(note.steps.split("|"), 1))
    return (
        "---\n"
        f"domain: {note.area.split('/')[-1].casefold().replace(' ', '-')}\n"
        "status: base-inicial\n"
        "review_after: 2027-02-25\n"
        "tags: [kiara, conhecimento-curado]\n"
        f"source: {note.source}\n"
        "---\n\n"
        f"# {note.title}\n\n"
        f"## Objetivo\n\n{note.summary}\n\n"
        f"## Procedimento\n\n{steps}\n\n"
        f"## Risco e limite\n\n{note.risk}\n\n"
        f"## Critério de sucesso\n\n{note.success}\n\n"
        f"## Fonte para verificação\n\n- {note.source}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vault", type=Path)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    vault = args.vault.expanduser().resolve()
    if not vault.is_dir():
        raise SystemExit(f"Vault inexistente: {vault}")
    created = skipped = 0
    for note in NOTES:
        folder = vault / note.area
        folder.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r'[<>:"/\\|?*]+', "-", note.title).strip(" .")
        destination = folder / f"{safe}.md"
        if destination.exists() and not args.overwrite:
            skipped += 1
            continue
        temporary = destination.with_suffix(".md.tmp")
        temporary.write_text(render(note), encoding="utf-8")
        temporary.replace(destination)
        created += 1
    print(f"created={created} skipped={skipped} total={len(NOTES)}")


if __name__ == "__main__":
    main()
