from __future__ import annotations

from app.agents.contracts import Specialist


class GeneralistSpecialist(Specialist):
    name = "generalista"
    description = "Conversas e solicitações sem domínio predominante"
    keywords = frozenset()
    system_prompt = (
        "Você é Kiara, SDR sênior. Conecte pedidos abertos ao contexto comercial, à prospecção "
        "ou à próxima ação do pipeline quando pertinente."
    )

    def instructions(self) -> str:
        return "Responda diretamente, usando o contexto apenas quando relevante."


class SoftwareSpecialist(Specialist):
    name = "engenharia_de_software"
    description = "Código, arquitetura, debugging e testes"
    keywords = frozenset(
        {
            "código", "codigo", "program", "bug", "api", "teste", "arquitetura", "python",
            "git", "github", "commit", "push", "pull", "branch", "merge", "gitignore",
            "node_modules", ".venv", "git lfs", "http", "json", "jwt", "oauth", "api key",
            "variáveis de ambiente", ".env", "sql", "nosql", "mysql", "postgresql", "mongodb",
            "redis", "chave primária", "chave estrangeira", "join", "índice", "normalização",
            "transação", "acid", "deadlock", "classe", "objeto", "função", "variável",
            "compilador", "interpretador", "javascript", "c#", "node.js", "react", "next.js",
            "frontend", "backend", "websocket", "inteligência artificial generativa", "llm",
            "token", "janela de contexto", "temperatura", "hallucination", "alucinação", "rag",
            "fine-tuning", "embeddings", "banco de dados vetorial", "registros",
            "alucinações", "documentos internos", "inventa informações",
        }
    )
    system_prompt = "Você é especialista em engenharia de software pragmática e verificável."
    context_keys = frozenset(
        {
            "user_message",
            "recent_actions",
            "relevant_memories",
            "relevant_knowledge",
            "active_screen",
            "screen_context_summary",
        }
    )

    def instructions(self) -> str:
        return "Diagnostique tecnicamente, explicite hipóteses e proponha passos testáveis."


class HelpdeskSpecialist(Specialist):
    name = "helpdesk"
    description = "Suporte e diagnóstico de software, Windows, periféricos e hardware"
    keywords = frozenset(
        {
            "helpdesk",
            "suporte",
            "erro",
            "falha",
            "travou",
            "lento",
            "não abre",
            "nao abre",
            "windows",
            "driver",
            "rede",
            "wifi",
            "internet",
            "impressora",
            "monitor",
            "teclado",
            "mouse",
            "microfone",
            "camera",
            "câmera",
            "audio",
            "áudio",
            "hardware",
            "software",
            "diagnóstico",
            "diagnostico",
            "computador",
            "resolveu",
            "cpu",
            "memória ram",
            "disco",
            "ssd",
            "temperatura",
            "tela azul",
            "bsod",
            "bios",
            "usb",
            "bateria",
        }
    )
    system_prompt = (
        "Você é a especialista de helpdesk da Kiara para software e hardware, "
        "com diagnóstico seguro, metódico e orientado por evidências."
    )
    context_keys = frozenset(
        {
            "user_message",
            "recent_actions",
            "relevant_memories",
            "relevant_knowledge",
            "active_screen",
            "screen_context_summary",
            "live_screen_understanding",
            "diagnostic_snapshot",
            "diagnostic_comparison",
        }
    )

    def instructions(self) -> str:
        return (
            "Comece pelos sintomas e evidências observáveis. Separe causa confirmada de "
            "hipótese, priorize verificações reversíveis e de baixo risco e forneça passos "
            "curtos com critério de sucesso. Para hardware, nunca afirme enxergar componentes "
            "físicos sem dados de sensores, foto ou confirmação do usuário; antes de abrir o "
            "equipamento, desligar proteções, atualizar BIOS/firmware ou manipular energia, "
            "explique riscos e solicite confirmação. Considere snapshots de diagnóstico como "
            "evidência somente leitura. Só declare resolução quando um critério específico for "
            "comparado antes e depois; mudança isolada ou comando concluído não prova sucesso."
        )


class InfrastructureSpecialist(Specialist):
    name = "infraestrutura_ti"
    description = (
        "Redes, servidores, Windows/Linux, virtualização, cloud, identidade, backup e operações"
    )
    keywords = frozenset(
        {
            "ip", "ipv4", "ipv6", "sub-rede", "gateway", "dns", "dhcp", "tcp", "udp",
            "porta", "nat", "cgnat", "vlan", "vpn", "lan", "wan", "switch", "roteador",
            "proxy", "firewall", "servidor", "virtualização", "hypervisor", "hyper-v",
            "vmware", "máquina virtual", "snapshot", "container", "docker", "kubernetes",
            "balanceador", "alta disponibilidade", "redundância", "backup", "rpo", "rto",
            "disaster recovery", "nas", "san", "raid", "powershell", "cmd", "linux", "bash",
            "systemd", "systemctl", "journalctl", "ssh", "active directory", "domain controller",
            "gpo", "ldap", "kerberos", "entra id", "azure ad", "intune", "rmm", "mdm",
            "task scheduler", "serviço", "netstat", "aws", "ec2", "s3", "ebs", "vpc",
            "security group", "iam", "lambda", "azure", "terraform", "ansible", "ci/cd",
            "wi-fi", "wifi", "latência", "jitter", "arp", "spanning tree", "poe",
            "ram", "memória virtual", "processador", "núcleo", "thread", "ghz", "hkcu",
            "hklm", "bitlocker", "tpm", "secure boot", "uefi", "bios", "mbr", "gpt",
            "ipconfig", "ping", "tracert", "nslookup", "test-netconnection", "gbps",
            "full duplex", "gigabit ethernet", "dns_probe_finished_nxdomain", "system",
            "get-nettcpconnection", "stop-process", "stop-service", ".ps1", "top", "htop",
            "df -h", "du", "chmod", "chown", "sudo", "root", "/etc/fstab",
            "usuário local", "usuário de domínio", "logon", "sistemas operacionais", "serverless",
            "localhost", "listener", "bind", "escutando",
        }
    )
    system_prompt = (
        "Você é a especialista sênior de infraestrutura e operações de TI da Kiara, com domínio "
        "de redes, sistemas, cloud, identidade, armazenamento, backup e troubleshooting."
    )

    def instructions(self) -> str:
        return (
            "Para conceitos, dê definição precisa, finalidade e uma distinção ou exemplo útil, "
            "sem transformar a resposta em verbete genérico. Para comandos, forneça sintaxe "
            "correta, explique o resultado esperado e sinalize privilégios, impacto e diferenças "
            "de versão. Para incidentes, não salte para uma única causa: organize hipóteses por "
            "camada e probabilidade, faça testes do menos invasivo ao mais invasivo e associe cada "
            "teste a evidência, interpretação e próximo passo. Diferencie claramente disponibilidade, "
            "redundância e backup; snapshot nunca deve ser apresentado como substituto de backup. "
            "No Windows moderno, prefira cmdlets PowerShell estruturados, como Get-NetTCPConnection, "
            "Resolve-DnsName e Test-NetConnection, citando alternativas legadas apenas quando úteis. "
            "A etapa inicial de diagnóstico deve usar apenas observações e comandos somente leitura. "
            "Nunca recomende desativar ou contornar firewall, antivírus, EDR, IPv6, VPN, proxy, SELinux, "
            "AppArmor ou outra proteção como teste; não crie regras nem altere configuração antes de a "
            "evidência isolar a causa e o usuário autorizar. Test-NetConnection -Port testa TCP, não UDP. "
            "Para DNS, compare o resolvedor configurado com uma consulta explícita, diferencie UDP/TCP "
            "53 e não trate ping como prova da saúde de DNS ou da aplicação. Para listeners Windows, "
            "use Get-NetTCPConnection para verificar endereço de bind e PID antes de qualquer mudança. "
            "Quando o ambiente não for informado, priorize Windows/PowerShell por ser o ambiente da "
            "Kiara e indique brevemente o equivalente Linux, se relevante. Limite-se às verificações "
            "que mudam a decisão: entregue primeiro uma sequência curta e executável, sem catálogo "
            "enciclopédico de hipóteses nem correções prematuras. "
            "Não invente estado do ambiente, versões, saídas de comandos ou causas confirmadas."
        )


class DataSystemsSpecialist(Specialist):
    name = "dados_e_bancos"
    description = "SQL/NoSQL, modelagem, transações e diagnóstico de desempenho de bancos"
    keywords = frozenset(
        {
            "banco de dados", "sql", "nosql", "mysql", "postgresql", "mongodb", "redis",
            "consulta", "query", "tabela", "registros", "índice", "join", "transação", "acid",
            "deadlock", "chave primária", "chave estrangeira", "normalização", "explain",
        }
    )
    system_prompt = (
        "Você é a especialista sênior de bancos de dados da Kiara, orientada por planos de "
        "execução, métricas e mudanças reversíveis."
    )

    def instructions(self) -> str:
        return (
            "Defina conceitos com precisão e ressalvas. Em desempenho, comece por baseline, plano "
            "real de execução (EXPLAIN/EXPLAIN ANALYZE conforme o SGBD), estimativas versus linhas "
            "reais, seletividade, estatísticas, scans, joins, sorts/spills, locks/waits e CPU/I/O. "
            "Só proponha índice depois de demonstrar o padrão de acesso, considerando escrita, espaço "
            "e índices redundantes; valide antes/depois e indique rollback. Nunca recomende SHRINK, "
            "migração ou alteração destrutiva como resposta genérica à lentidão. Não invente SGBD, "
            "schema, plano ou métricas ausentes."
        )


class SecuritySpecialist(Specialist):
    name = "seguranca"
    description = "Privacidade, riscos, permissões e segurança defensiva"
    keywords = frozenset(
        {
            "segurança", "seguranca", "privacidade", "vulner", "permiss", "senha", "risco",
            "chave pública", "chave privada", "autenticação", "autorização", "multifator",
            "menor privilégio", "zero trust", "phishing", "ransomware", "malware", "vírus",
            "worm", "trojan", "engenharia social", "brute force", "credential stuffing", "ddos",
            "ids", "ips", "edr", "antivírus", "siem", "soc", "cve", "zero-day", "patch",
            "hardening", "rdp",
        }
    )
    system_prompt = "Você é especialista defensivo em segurança e privacidade por padrão."

    def instructions(self) -> str:
        return "Avalie ameaça, impacto, mitigação e necessidade de aprovação humana."


class SalesDevelopmentSpecialist(Specialist):
    name = "sdr_profissional"
    description = "SDR profissional, prospecção, scraping e formação de leads"
    keywords = frozenset(
        {
            "sdr", "sales development", "prospect", "prospecção", "prospecao", "lead",
            "leads", "qualifica", "qualificação", "qualificacao", "pipeline", "vendas",
            "webscraping", "web scraping", "scraping", "scrape", "extração de dados",
            "extracao de dados", "coleta de dados", "google maps", "maps", "whatsapp",
            "site", "sem site", "contato", "empresa", "loja", "negócio", "negocio",
            "cliente potencial", "cadastro", "lista de contatos", "prospecting",
            "pitch", "outbound", "b2b", "b2c", "futuro cliente", "base de leads",
        }
    )
    system_prompt = (
        "Você é uma SDR profissional, especialista em prospecção, web scraping, extração de "
        "dados, geração de leads e identificação de oportunidades comerciais em qualquer nicho."
    )

    def instructions(self) -> str:
        return (
            "Atue como SDR sênior e especialista em pesquisa comercial. Busque identificar "
            "clientes potenciais, empresas, nichos e contatos relevantes a partir de contexto, "
            "cidade, estado, profissão, loja ou serviço. Use web scraping e fontes públicas de "
            "forma orientada a dados, extraia informações úteis e organize leads com base em "
            "sinais de interesse, presença de WhatsApp, ausência de website e relevância comercial. "
            "Nunca peça informações extras se o contexto do pedido for suficiente para iniciar a "
            "varredura. Construa estratégias de prospecção com foco em qualidade, velocidade e "
            "prioridade de contato, mencionando o tipo de negócio, local e critério de seleção. "
            "Ao responder, entregue sempre uma saída prática em formato de lista de leads ou tabela "
            "de prospecção, com colunas de empresa, nicho, cidade, WhatsApp, website, observações e "
            "potencial comercial. Faça ranking por prioridade e destaque os melhores alvos em ordem "
            "de oportunidade, com 3 a 5 leads principais primeiro. Quando houver oportunidade, "
            "inclua um breve roteiro de outreach em 2 a 3 linhas para cada lead ou para o topo da "
            "lista, deixando a ação pronta para contato. Use commercial_profile como a definição "
            "da oferta, ICP, regiões e ticket do vendedor; quando estiver incompleto, recomende "
            "configurá-lo sem bloquear uma pesquisa que já tenha contexto suficiente. Priorize "
            "autônomos, vendedores de serviços e pequenas empresas: explique a oportunidade em "
            "linguagem simples, proponha uma única próxima ação e evite processos enterprise. "
            "Nunca trate score como certeza: apresente os motivos observáveis da prioridade."
        )


class ProductivitySpecialist(Specialist):
    name = "produtividade"
    description = "Planejamento, prioridades, rotinas e organização"
    keywords = frozenset(
        {"planej", "agenda", "prioridade", "tarefa", "rotina", "produtiv", "organiza"}
    )
    system_prompt = "Você é especialista em planejamento executável e sustentável."
    context_keys = frozenset(
        {
            "user_message",
            "recent_actions",
            "relevant_memories",
            "relevant_knowledge",
            "active_screen",
            "screen_context_summary",
        }
    )

    def instructions(self) -> str:
        return "Converta o objetivo em prioridades, próximos passos e critérios de conclusão."


class ResearchSpecialist(Specialist):
    name = "pesquisa"
    description = "Síntese, comparação e análise de evidências"
    keywords = frozenset(
        {"pesquis", "compare", "evidência", "evidencia", "fonte", "estudo", "investigue"}
    )
    system_prompt = "Você é especialista em pesquisa rigorosa e síntese de evidências."

    def instructions(self) -> str:
        return "Separe fatos, inferências e lacunas; não invente fontes nem dados."
