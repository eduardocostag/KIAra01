# Google Maps Scraper na Kiara

O adapter usa a CLI oficial de [gosom/google-maps-scraper](https://github.com/gosom/google-maps-scraper)
para pesquisar fichas públicas e devolver nome, telefone, site, endereço e reputação ao contrato
`google_maps_business_search` existente. A execução passa pelo registro, permissões e auditoria.

## Preparação no Windows

```powershell
powershell -NoProfile -File scripts/install_maps_scraper.ps1
$env:KIARA_MAPS_SCRAPER_EXECUTABLE = (Resolve-Path 'data/tools/google-maps-scraper/google-maps-scraper.exe').Path
python -m app --console
```

O instalador fixa a release Windows amd64 **v1.18.2** e verifica o SHA-256 publicado pelo GitHub:
`6609e9638ee303b6d419a329f629efcd9ed5d083f86ad6b93f92a21d59c2aca5`.
Embora publicado nessa release, o asset imprime a versão embutida
`v1.18.3-0.20261108092509-146aefe83844-146aefe`; o instalador identifica o asset pelo hash.
A primeira pesquisa pode precisar baixar os componentes Playwright usados pelo executável.
O binário é um recurso local e não deve entrar no Git. A CLI pode também ser compilada a partir
do código upstream; configure a variável com o caminho absoluto do executável resultante.

## Operação

O YAML do projeto habilita o scraper nativo quando o executável está instalado.
Sem o arquivo, a Kiara inicia com a pesquisa pelo navegador existente.
Na API Hunter, configure `KIARA_MAPS_SCRAPER_EXECUTABLE` no servidor que executa
os jobs; o executável Windows local não fica disponível automaticamente no servidor.

Peça leads pelo nicho e cidade no fluxo comercial habitual. Cada execução recebe uma única consulta,
usa profundidade 1 e concorrência 1, sem email, reviews extras ou proxies, e retorna no máximo
50 fichas. O limite de fichas restringe a importação; a CLI pode coletar mais fichas no CSV local.
Cada chamada tem timeout de 600 segundos e participa do kill switch da Kiara. A telemetria upstream
é desativada com `DISABLE_TELEMETRY=1`.

Entradas e resultados ficam em subpastas únicas de `data/maps-scraper/`. Saídas parciais são
preservadas em falhas e timeout, sem importar fichas incompletas. Remova esses arquivos localmente
quando não forem mais necessários. Consultas não são interpoladas em comandos de shell.

O Hunter do site também reconhece `KIARA_MAPS_SCRAPER_EXECUTABLE` no processo do worker local
que executa `maps_search`. Configure a variável nesse worker; a aplicação precisa ter o pacote
Python `app` da Kiara disponível. A chamada limita a importação a 50 resultados e a execução a
110 segundos, respeitando a janela do Hunter; cancelamento encerra os subprocessos. Se a CLI não
estiver configurada, retornar vazia ou falhar, os provedores existentes continuam disponíveis.
Uma implantação cloud sem esse executável local mantém os provedores habituais.

Telefone de Maps não comprova WhatsApp: o campo `whatsapp` só é preenchido quando o verificador
do navegador confirma o número. Falhas de verificação mantêm o campo vazio. Nenhuma mensagem é enviada.

## Skill e utilidades upstream

O pacote completo de skill foi incorporado em
`app/resources/operational_skills/google-maps-scraper`, com scripts Node/Bash, referências e licença
MIT, a partir do commit `e0c1d501e49cdcd5c6b2cecd2a032831f6ee9ba8`.
O workflow Docker da skill requer Docker, Node.js e WSL no Windows; o adapter nativo da Kiara
usa a CLI Windows e não depende desse workflow. Scripts upstream não são executados ao iniciar
a aplicação. Atualizações da skill devem passar por revisão e troca explícita do commit incorporado.
