param(
    [switch]$SkipAgentsMd,
    [switch]$SkipVisualOperationsCopilot
)

$ErrorActionPreference = "Stop"
$CodexHome = Join-Path $HOME ".codex"
$AgentsDir = Join-Path $CodexHome "agents"
$GlobalAgentsMd = Join-Path $CodexHome "AGENTS.md"
$RepoZipUrl = "https://github.com/msitarzewski/agency-agents/archive/refs/heads/main.zip"
$RawBaseUrl = "https://raw.githubusercontent.com/msitarzewski/agency-agents/main"

New-Item -ItemType Directory -Force $CodexHome | Out-Null
New-Item -ItemType Directory -Force $AgentsDir | Out-Null

$agents = @(
    @{ Category = "Coordenação e Engenharia"; Slug = "agents-orchestrator"; Path = "specialized/agents-orchestrator.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "software-architect"; Path = "engineering/engineering-software-architect.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "senior-developer"; Path = "engineering/engineering-senior-developer.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "incident-response-commander"; Path = "engineering/engineering-incident-response-commander.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "rag-pipeline-engineer"; Path = "engineering/engineering-rag-pipeline-engineer.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "multi-agent-systems-architect"; Path = "engineering/engineering-multi-agent-systems-architect.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "technical-writer"; Path = "engineering/engineering-technical-writer.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "evidence-collector"; Path = "testing/testing-evidence-collector.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "project-manager-senior"; Path = "project-management/project-manager-senior.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "project-shepherd"; Path = "project-management/project-management-project-shepherd.md" }
    @{ Category = "Coordenação e Engenharia"; Slug = "jira-workflow-steward"; Path = "project-management/project-management-jira-workflow-steward.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "code-reviewer"; Path = "engineering/engineering-code-reviewer.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "appsec-engineer"; Path = "security/security-appsec-engineer.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "frontend-developer"; Path = "engineering/engineering-frontend-developer.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "test-automation-engineer"; Path = "testing/testing-test-automation-engineer.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "reality-checker"; Path = "testing/testing-reality-checker.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "devops-automator"; Path = "engineering/engineering-devops-automator.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "data-visualization-engineer"; Path = "engineering/engineering-data-visualization-engineer.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "api-tester"; Path = "testing/testing-api-tester.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "database-optimizer"; Path = "engineering/engineering-database-optimizer.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "identity-access-engineer"; Path = "engineering/engineering-identity-access-engineer.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "minimal-change-engineer"; Path = "engineering/engineering-minimal-change-engineer.md" }
    @{ Category = "Desenvolvimento e Qualidade"; Slug = "codebase-onboarding-engineer"; Path = "engineering/engineering-codebase-onboarding-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "ai-engineer"; Path = "engineering/engineering-ai-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "prompt-engineer"; Path = "engineering/engineering-prompt-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "autonomous-optimization-architect"; Path = "engineering/engineering-autonomous-optimization-architect.md" }
    @{ Category = "IA e Automação"; Slug = "automation-governance-architect"; Path = "specialized/automation-governance-architect.md" }
    @{ Category = "IA e Automação"; Slug = "workflow-optimizer"; Path = "testing/testing-workflow-optimizer.md" }
    @{ Category = "IA e Automação"; Slug = "email-intelligence-engineer"; Path = "engineering/engineering-email-intelligence-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "ai-data-remediation-engineer"; Path = "engineering/engineering-ai-data-remediation-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "voice-ai-integration-engineer"; Path = "engineering/engineering-voice-ai-integration-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "data-engineer"; Path = "engineering/engineering-data-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "data-consolidation-agent"; Path = "specialized/data-consolidation-agent.md" }
    @{ Category = "IA e Automação"; Slug = "api-platform-engineer"; Path = "engineering/engineering-api-platform-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "developer-tooling-engineer"; Path = "engineering/engineering-developer-tooling-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "agentic-identity-trust"; Path = "specialized/agentic-identity-trust.md" }
    @{ Category = "IA e Automação"; Slug = "sre"; Path = "engineering/engineering-sre.md" }
    @{ Category = "IA e Automação"; Slug = "threat-detection-engineer"; Path = "security/security-threat-detection-engineer.md" }
    @{ Category = "IA e Automação"; Slug = "it-service-manager"; Path = "engineering/engineering-it-service-manager.md" }
    @{ Category = "IA e Automação"; Slug = "support-analytics-reporter"; Path = "support/support-analytics-reporter.md" }
    @{ Category = "IA e Automação"; Slug = "executive-summary-generator"; Path = "support/support-executive-summary-generator.md" }
    @{ Category = "Assistente Operacional"; Slug = "desktop-app-engineer"; Path = "engineering/engineering-desktop-app-engineer.md" }
    @{ Category = "Assistente Operacional"; Slug = "mcp-builder"; Path = "specialized/specialized-mcp-builder.md" }
    @{ Category = "Assistente Operacional"; Slug = "realtime-collaboration-engineer"; Path = "engineering/engineering-realtime-collaboration-engineer.md" }
    @{ Category = "Assistente Operacional"; Slug = "video-streaming-engineer"; Path = "engineering/engineering-video-streaming-engineer.md" }
    @{ Category = "Assistente Operacional"; Slug = "mobile-app-builder"; Path = "engineering/engineering-mobile-app-builder.md" }
    @{ Category = "Assistente Operacional"; Slug = "privacy-engineer"; Path = "engineering/engineering-privacy-engineer.md" }
    @{ Category = "Assistente Operacional"; Slug = "secrets-credential-hygiene-engineer"; Path = "security/security-secrets-credential-engineer.md" }
    @{ Category = "Assistente Operacional"; Slug = "model-qa-specialist"; Path = "specialized/specialized-model-qa.md" }
    @{ Category = "Assistente Operacional"; Slug = "search-relevance-engineer"; Path = "engineering/engineering-search-relevance-engineer.md" }
    @{ Category = "Assistente Operacional"; Slug = "database-reliability-engineer"; Path = "engineering/engineering-database-reliability-engineer.md" }
    @{ Category = "Assistente Operacional"; Slug = "network-engineer"; Path = "engineering/engineering-network-engineer.md" }
    @{ Category = "Assistente Operacional"; Slug = "rapid-prototyper"; Path = "engineering/engineering-rapid-prototyper.md" }
    @{ Category = "Assistente Operacional"; Slug = "data-privacy-officer"; Path = "specialized/data-privacy-officer.md" }
    @{ Category = "Aplicações Complexas"; Slug = "product-manager"; Path = "product/product-manager.md" }
    @{ Category = "Aplicações Complexas"; Slug = "ux-researcher"; Path = "design/design-ux-researcher.md" }
    @{ Category = "Aplicações Complexas"; Slug = "ux-architect"; Path = "design/design-ux-architect.md" }
    @{ Category = "Aplicações Complexas"; Slug = "ui-designer"; Path = "design/design-ui-designer.md" }
    @{ Category = "Aplicações Complexas"; Slug = "ui-finish-gate-reviewer"; Path = "design/design-ui-finish-gate-reviewer.md" }
    @{ Category = "Aplicações Complexas"; Slug = "backend-architect"; Path = "engineering/engineering-backend-architect.md" }
    @{ Category = "Aplicações Complexas"; Slug = "workflow-architect"; Path = "specialized/specialized-workflow-architect.md" }
    @{ Category = "Aplicações Complexas"; Slug = "security-architect"; Path = "security/security-architect.md" }
    @{ Category = "Aplicações Complexas"; Slug = "cloud-security-architect"; Path = "security/security-cloud-security-architect.md" }
    @{ Category = "Aplicações Complexas"; Slug = "penetration-tester"; Path = "security/security-penetration-tester.md" }
    @{ Category = "Aplicações Complexas"; Slug = "performance-benchmarker"; Path = "testing/testing-performance-benchmarker.md" }
    @{ Category = "Aplicações Complexas"; Slug = "accessibility-auditor"; Path = "testing/testing-accessibility-auditor.md" }
    @{ Category = "Aplicações Complexas"; Slug = "git-workflow-master"; Path = "engineering/engineering-git-workflow-master.md" }
    @{ Category = "Aplicações Complexas"; Slug = "finops-engineer"; Path = "engineering/engineering-finops-engineer.md" }
    @{ Category = "Extras Essenciais"; Slug = "ai-generated-code-auditor"; Path = "security/security-ai-generated-code-auditor.md" }
    @{ Category = "Extras Essenciais"; Slug = "test-results-analyzer"; Path = "testing/testing-test-results-analyzer.md" }
    @{ Category = "Extras Essenciais"; Slug = "tool-evaluator"; Path = "testing/testing-tool-evaluator.md" }
    @{ Category = "Extras Essenciais"; Slug = "product-sprint-prioritizer"; Path = "product/product-sprint-prioritizer.md" }
    @{ Category = "Extras Essenciais"; Slug = "compliance-auditor"; Path = "security/security-compliance-auditor.md" }
    @{ Category = "Extras Essenciais"; Slug = "mobile-release-engineer"; Path = "engineering/engineering-mobile-release-engineer.md" }
    @{ Category = "Extras Essenciais"; Slug = "payments-billing-engineer"; Path = "engineering/engineering-payments-billing-engineer.md" }
)

function Write-Utf8NoBom {
    param([string]$Path,[string]$Content)
    $enc = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path,$Content,$enc)
}

function Convert-ToTomlString {
    param([string]$Value)
    if ($null -eq $Value) { return '""' }
    $v = $Value.Replace('\','\\').Replace('"','\"')
    $v = $v.Replace("`r`n",'\n').Replace("`n",'\n').Replace("`r",'\n').Replace("`t",'\t')
    return '"' + $v + '"'
}

function Convert-AgentMarkdownToToml {
    param([string]$Markdown,[string]$Destination)
    $n = $Markdown -replace "`r`n","`n" -replace "`r","`n"
    if (-not $n.StartsWith("---`n")) { throw "Frontmatter YAML nao encontrado." }
    $end = $n.IndexOf("`n---`n",4)
    if ($end -lt 0) { throw "Fim do frontmatter nao encontrado." }
    $front = $n.Substring(4,$end-4)
    $body = $n.Substring($end+5).TrimStart("`n")
    $nameM = [regex]::Match($front,'(?m)^name:\s*(.+?)\s*$')
    $descM = [regex]::Match($front,'(?m)^description:\s*(.+?)\s*$')
    if (-not $nameM.Success -or -not $descM.Success) { throw "name/description ausente." }
    $name = $nameM.Groups[1].Value.Trim().Trim('"').Trim("'")
    $desc = $descM.Groups[1].Value.Trim().Trim('"').Trim("'")
    $toml = @(
      "name = $(Convert-ToTomlString $name)"
      "description = $(Convert-ToTomlString $desc)"
      "developer_instructions = $(Convert-ToTomlString $body)"
      ""
    ) -join "`r`n"
    Write-Utf8NoBom $Destination $toml
}

function Write-CustomAgent {
    param([string]$Name,[string]$Description,[string]$Instructions,[string]$Destination)
    $toml = @(
      "name = $(Convert-ToTomlString $Name)"
      "description = $(Convert-ToTomlString $Description)"
      "developer_instructions = $(Convert-ToTomlString $Instructions)"
      ""
    ) -join "`r`n"
    Write-Utf8NoBom $Destination $toml
}

Write-Host ""
Write-Host "======================================================================"
Write-Host " CODEX MASTER TEAM - 75 agentes + Visual Operations Copilot"
Write-Host "======================================================================"
Write-Host "Destino: $AgentsDir"
Write-Host ""

$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("codex-master-" + [guid]::NewGuid().ToString("N"))
$zipPath = Join-Path $tempRoot "agency-agents.zip"
$extractPath = Join-Path $tempRoot "repo"
$repoRoot = $null
New-Item -ItemType Directory -Force $tempRoot | Out-Null

try {
    try {
        Write-Host "[REPO] Baixando agency-agents..."
        Invoke-WebRequest -Uri $RepoZipUrl -OutFile $zipPath -UseBasicParsing -Headers @{"User-Agent"="Codex-Master-Team-Installer"}
        Expand-Archive -LiteralPath $zipPath -DestinationPath $extractPath -Force
        $repoRoot = (Get-ChildItem $extractPath -Directory | Select-Object -First 1).FullName
        Write-Host "[OK] Repositorio preparado."
    } catch {
        Write-Host "[AVISO] Falha no ZIP; usando fallback por arquivo." -ForegroundColor Yellow
        $repoRoot = $null
    }

    $new = 0
    $updated = 0
    $failed = @()

    foreach ($agent in $agents) {
        $dest = Join-Path $AgentsDir "$($agent.Slug).toml"
        try {
            $md = $null
            if ($repoRoot) {
                $src = Join-Path $repoRoot ($agent.Path.Replace('/',[IO.Path]::DirectorySeparatorChar))
                if (Test-Path -LiteralPath $src) { $md = [IO.File]::ReadAllText($src) }
            }
            if ([string]::IsNullOrWhiteSpace($md)) {
                $resp = Invoke-WebRequest -Uri "$RawBaseUrl/$($agent.Path)" -UseBasicParsing -Headers @{"User-Agent"="Codex-Master-Team-Installer"}
                $md = $resp.Content
            }
            $exists = Test-Path -LiteralPath $dest
            Convert-AgentMarkdownToToml $md $dest
            $check = [IO.File]::ReadAllText($dest)
            if ($check -notmatch '(?m)^name\s*=' -or $check -notmatch '(?m)^description\s*=' -or $check -notmatch '(?m)^developer_instructions\s*=') {
                throw "TOML invalido."
            }
            if ($exists) { $updated++; Write-Host "[ATUALIZADO] $($agent.Slug)" }
            else { $new++; Write-Host "[INSTALADO]  $($agent.Slug)" }
        } catch {
            $failed += $agent.Slug
            Write-Host "[ERRO] $($agent.Slug) -> $($_.Exception.Message)" -ForegroundColor Red
        }
    }

    if (-not $SkipVisualOperationsCopilot) {
        $dest = Join-Path $AgentsDir "visual-operations-copilot.toml"
        $exists = Test-Path -LiteralPath $dest
        $instructions = @'
Você é o Visual Operations Copilot, coordenador especializado de um assistente operacional multimodal.

Coordene, quando necessário: Desktop App Engineer, Voice AI Integration Engineer, Realtime Collaboration Engineer,
AI Engineer, RAG Pipeline Engineer, Search Relevance Engineer, MCP Builder, Agentic Identity & Trust,
Privacy Engineer, Secrets & Credential Hygiene Engineer e Automation Governance Architect.

Sua missão é projetar e evoluir sistemas capazes de observar somente o ambiente autorizado do usuário,
conversar em tempo real, recuperar memória/contexto, consultar ferramentas e executar ações controladas.

Sempre diferencie: observar, recomendar, preparar, executar e validar.
Para ações sensíveis, destrutivas, financeiras, administrativas ou irreversíveis, exija controles adicionais e,
quando apropriado, aprovação humana explícita.
Minimize coleta e retenção de tela/áudio.
Ferramentas devem usar privilégio mínimo, entradas tipadas, auditoria, idempotência e rollback quando aplicável.
Use Evidence Collector para validar resultados e Reality Checker para gate final.
Nunca afirme que uma ação ocorreu sem evidência de execução e validação.
'@
        Write-CustomAgent "Visual Operations Copilot" `
          "Coordena assistente operacional multimodal com tela, voz, memoria, ferramentas, execucao controlada, validacao e auditoria." `
          $instructions $dest
        if ($exists) { $updated++; Write-Host "[ATUALIZADO] visual-operations-copilot" }
        else { $new++; Write-Host "[INSTALADO]  visual-operations-copilot" }
    }

    if (-not $SkipAgentsMd) {
        Write-Host ""
        if (Test-Path -LiteralPath $GlobalAgentsMd) {
            $backup = "$GlobalAgentsMd.backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            Copy-Item $GlobalAgentsMd $backup -Force
            Write-Host "[BACKUP] $backup"
            $existing = [IO.File]::ReadAllText($GlobalAgentsMd)
        } else { $existing = "" }

        $legacy = @(
          @("<!-- BEGIN MANAGED: agency-agents-extra-team -->","<!-- END MANAGED: agency-agents-extra-team -->"),
          @("<!-- BEGIN MANAGED: agency-agents-ai-automation -->","<!-- END MANAGED: agency-agents-ai-automation -->"),
          @("<!-- BEGIN MANAGED: operational-assistant-core -->","<!-- END MANAGED: operational-assistant-core -->")
        )
        foreach ($m in $legacy) {
            $existing = [regex]::Replace($existing,"(?s)$([regex]::Escape($m[0])).*?$([regex]::Escape($m[1]))\s*","")
        }

        $block = @'
<!-- BEGIN MANAGED: codex-master-team -->

# Codex Master Team

Política global da equipe de agentes personalizados.

## Regras gerais
- O agente principal coordena a sessão.
- Não acione todos os agentes em toda tarefa; use somente os relevantes.
- Prefira paralelismo quando tarefas forem independentes.
- Não altere arquivos quando o usuário pedir somente análise ou planejamento.
- Não declare testes executados ou funcionalidades validadas sem evidência.
- Quando o usuário nomear explicitamente um agente, use-o se estiver disponível.

## Aplicação complexa do zero
Quando o usuário pedir uma aplicação nova e complexa, não comece direto pelo código. Considere esta sequência:
Product Manager -> UX Researcher -> UX Architect -> UI Designer -> Software Architect -> Backend Architect -> Workflow Architect -> Security Architect -> especialistas de dados/IA -> implementação -> revisão -> testes -> segurança -> performance -> acessibilidade -> evidências -> gate final -> documentação -> release.

Use Product Manager para problema, público, MVP, requisitos e métricas.
Use Product Sprint Prioritizer para priorização.
Use Project Manager Senior e Project Shepherd para execução, dependências e acompanhamento.
Use Software Architect para arquitetura global.
Use Backend Architect para APIs, módulos, eventos, filas, cache e escalabilidade.
Use Frontend Developer, Senior Developer, Mobile App Builder ou Desktop App Engineer conforme a plataforma.
Use Database Optimizer e Database Reliability Engineer para dados.
Use DevOps Automator para CI/CD, containers e deploy.
Use Git Workflow Master para branches, commits e integração.
Use FinOps Engineer para custos.
Use Payments & Billing Engineer quando houver cobrança, assinatura ou pagamentos.
Use Mobile Release Engineer quando houver distribuição mobile.

## IA e automação
Use AI Engineer para funcionalidades com LLMs/modelos.
Use Prompt Engineer para prompts e outputs estruturados.
Use RAG Pipeline Engineer para embeddings, retrieval e conhecimento.
Use Search Relevance Engineer para busca lexical, vetorial e híbrida.
Use Multi-Agent Systems Architect para sistemas multiagentes.
Use Model QA Specialist para avaliação independente de modelos.
Use AI Generated Code Auditor para código produzido por IA.
Use Workflow Optimizer antes de automatizar processos existentes.
Use Automation Governance Architect para autonomia, aprovações, auditoria, idempotência, retries, rollback e kill switch.
Use MCP Builder, API Platform Engineer e Developer Tooling Engineer para ferramentas e integrações.
Use Tool Evaluator para avaliar ferramentas usadas por agentes.

## Assistente operacional
Use Visual Operations Copilot como coordenador quando o objetivo for um assistente com tela, voz, memória e execução controlada.
Use Desktop App Engineer para captura de tela, overlay e integração com o sistema operacional.
Use Voice AI Integration Engineer para voz.
Use Realtime Collaboration Engineer para sessões e comunicação em tempo real.
Use Video Streaming Engineer quando transporte/processamento de mídia for relevante.
Use RAG Pipeline Engineer + Search Relevance Engineer para memória e recuperação.
Use MCP Builder para ferramentas locais e corporativas.
Use Privacy Engineer + Data Privacy Officer para privacidade.
Use Secrets & Credential Hygiene Engineer para credenciais.
Use Agentic Identity & Trust + Identity & Access Engineer para identidade/autorização.
Use Automation Governance Architect para limites de autonomia.
Use Evidence Collector e Reality Checker para validação.

Níveis de autonomia:
0 conversa;
1 observa e orienta;
2 observa e consulta;
3 prepara ações e pede aprovação;
4 executa ações previamente autorizadas;
5 executa workflows limitados;
6 monitora continuamente;
7 detecta, investiga, propõe, executa dentro da política e valida.
Não avance autonomia só porque é tecnicamente possível.

## Segurança
Use Security Architect para desenho.
Use AppSec Engineer para implementação.
Use Cloud Security Architect para cloud.
Use Secrets & Credential Hygiene Engineer para credenciais.
Use Compliance Auditor para controles e conformidade.
Use Penetration Tester apenas para validação ofensiva autorizada.
Para ações sensíveis: privilégio mínimo, preview/dry-run quando possível, aprovação humana quando apropriado, auditoria, rollback e validação do estado final.

## Gates recomendados
Implementação
-> AI Generated Code Auditor quando aplicável
-> Code Reviewer
-> AppSec Engineer quando aplicável
-> Test Automation Engineer / API Tester
-> Test Results Analyzer
-> Performance Benchmarker quando aplicável
-> Accessibility Auditor quando houver UI
-> Model QA Specialist quando houver IA/modelos
-> Evidence Collector
-> Reality Checker
-> UI Finish Gate Reviewer quando houver interface
-> concluído.

<!-- END MANAGED: codex-master-team -->
'@
        $b = [regex]::Escape("<!-- BEGIN MANAGED: codex-master-team -->")
        $e = [regex]::Escape("<!-- END MANAGED: codex-master-team -->")
        if ($existing -match "(?s)$b.*?$e") {
            $existing = [regex]::Replace($existing,"(?s)$b.*?$e",$block)
        } elseif ([string]::IsNullOrWhiteSpace($existing)) {
            $existing = $block + "`r`n"
        } else {
            $existing = $existing.TrimEnd() + "`r`n`r`n" + $block + "`r`n"
        }
        Write-Utf8NoBom $GlobalAgentsMd $existing
        Write-Host "[OK] AGENTS.md consolidado: $GlobalAgentsMd"
    }

    $selected = @($agents | ForEach-Object {$_.Slug})
    if (-not $SkipVisualOperationsCopilot) { $selected += "visual-operations-copilot" }
    $present = 0
    foreach ($slug in $selected) {
        if (Test-Path (Join-Path $AgentsDir "$slug.toml")) { $present++ }
    }
    $total = (Get-ChildItem $AgentsDir -Filter "*.toml" -File -ErrorAction SilentlyContinue).Count

    Write-Host ""
    Write-Host "======================================================================"
    Write-Host " RESULTADO"
    Write-Host "======================================================================"
    Write-Host "Novos nesta execucao       : $new"
    Write-Host "Atualizados                 : $updated"
    Write-Host "Equipe selecionada presente : $present/$($selected.Count)"
    Write-Host "Total de TOMLs              : $total"
    if ($failed.Count -gt 0) {
        Write-Host "Falharam: $($failed -join ', ')" -ForegroundColor Yellow
        exit 1
    }
    Write-Host ""
    Write-Host "CODEX MASTER TEAM instalado com sucesso." -ForegroundColor Green
    Write-Host "Abra uma nova sessao do Codex/VS Code para recarregar as instrucoes."
}
finally {
    if (Test-Path $tempRoot) { Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue }
}
