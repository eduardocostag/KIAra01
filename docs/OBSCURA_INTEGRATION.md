# Obscura na Kiara

A Kiara usa o Obscura como um serviço de navegador separado. O binário não é
executado dentro da Function da Vercel: ele mantém V8, sessões e processos de
navegador vivos e, por isso, deve rodar em um serviço de contêiner persistente.

## Arquitetura

1. O enriquecedor nativo da Kiara funciona diretamente na API, sem chave ou contêiner.
2. O Hunter tenta `OBSCURA_CDP_URL` para Google Maps e páginas dinâmicas quando configurado.
3. Se o Obscura estiver indisponível, Google Maps usa Browserbase.
4. O enriquecimento usa Firecrawl/Obscura como aceleradores e o coletor nativo como fallback.
5. Resultados parciais são preservados; falhas externas nunca geram dados fictícios.

## Serviço Obscura

Execute a imagem oficial em um host de contêiner e mantenha a porta CDP privada:

```bash
docker run --name kiara-obscura --restart unless-stopped \
  -p 127.0.0.1:9222:9222 h4ckf0r0day/obscura \
  serve --port 9222 --workers 4 --obey-robots
```

Para a Vercel alcançar esse serviço, coloque-o atrás de um proxy HTTPS/WSS com
autenticação e TLS. Não exponha a porta 9222 diretamente na internet.

## Variáveis exclusivas da API

- `OBSCURA_CDP_URL`: endpoint HTTPS/WSS do proxy autenticado.
- `OBSCURA_AUTH_TOKEN`: token Bearer aceito pelo proxy.

Esses valores pertencem somente ao projeto da API. Nunca use prefixo
`NEXT_PUBLIC_`.

## Limites operacionais

- Coleta apenas informações publicamente acessíveis.
- Mantém confirmação humana antes da pesquisa.
- Respeita os filtros e não interpreta ausência de evidência como fato.
- Use `--obey-robots`, limites de concorrência e termos de cada fonte.
- Não use o motor para contornar login, CAPTCHA, bloqueios de acesso ou áreas privadas.

O Obscura é Apache-2.0. Preserve os avisos de licença ao redistribuir o binário.
