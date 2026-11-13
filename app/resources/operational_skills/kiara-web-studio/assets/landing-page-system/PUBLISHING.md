# Publicação segura dos templates

Os arquivos em `templates/` são fontes de demonstração. Eles não devem ser publicados diretamente como sites finais.

## Preview seguro

Copie `config/site.example.json`, escolha o template e execute:

```powershell
node scripts/build-template.mjs --mode preview --config config/site.example.json
```

A saída em `dist/<template>` recebe `noindex, nofollow, noarchive`, description e metadados sociais. Assim, uma demonstração não é indexada como se representasse um profissional real.

## Produção

Preencha nome, descrição, HTTPS canônica, profissional, WhatsApp com DDI, endereço e registro profissional quando aplicável. Depois execute:

```powershell
node scripts/build-template.mjs --mode production --config config/cliente.json
```

A build para se houver campo obrigatório vazio, link vazio, placeholder, URL insegura, contato inválido, template inexistente ou ausência de registro CRO/CREF quando aplicável.

## Auditoria contínua

```powershell
node scripts/template-quality.mjs --mode preview
node scripts/template-quality.mjs --mode preview --strict
node scripts/template-quality.mjs --mode production --config config/cliente.json
```

O modo normal bloqueia erros estruturais. `--strict` também transforma avisos de mídia e SEO em falha, recomendado no CI. Para integração, use `--json`.

## Orçamentos iniciais

- imagem individual: 750 KB;
- vídeo individual: 6 MB;
- diretório publicável: 9 MB.

Imagens de hero devem preferir AVIF/WebP responsivo, com dimensões explícitas e preload somente para o LCP. Vídeos devem ter poster, MP4/WebM, reprodução sem áudio, fallback estático, política para economia de dados e respeito a `prefers-reduced-motion`.
