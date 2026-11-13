#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const policy = JSON.parse(fs.readFileSync(path.join(projectRoot, 'config', 'publishing-policy.json'), 'utf8'));
const args = process.argv.slice(2);
const mode = value('--mode') || 'preview';
const configPath = value('--config');
const strict = args.includes('--strict');
const jsonOutput = args.includes('--json');
const templateRoot = path.join(projectRoot, policy.templateRoot);

function value(flag) {
  const index = args.indexOf(flag);
  return index >= 0 ? args[index + 1] : undefined;
}

function get(object, dottedPath) {
  return dottedPath.split('.').reduce((current, key) => current?.[key], object);
}

function classify(slug) {
  if (slug.startsWith('dentista-')) return 'dentista';
  if (slug.startsWith('educador-fisico-')) return 'educador-fisico';
  if (slug === 'personal-trainer') return 'personal-trainer';
  if (slug.startsWith('beleza-')) return 'beleza';
  if (slug.startsWith('psicologo-')) return 'psicologo';
  if (slug.startsWith('nutricionista-')) return 'nutricionista';
  if (slug.startsWith('advogado-')) return 'advogado';
  return 'outro';
}

function walk(directory) {
  const result = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) result.push(...walk(absolute));
    else result.push(absolute);
  }
  return result;
}

const templateDirs = fs.readdirSync(templateRoot, { withFileTypes: true })
  .filter((entry) => entry.isDirectory() && fs.existsSync(path.join(templateRoot, entry.name, 'index.html')))
  .map((entry) => ({ slug: entry.name, directory: path.join(templateRoot, entry.name) }));

const siteConfig = configPath
  ? JSON.parse(fs.readFileSync(path.resolve(configPath), 'utf8'))
  : null;
const findings = [];
const add = (severity, slug, code, message) => findings.push({ severity, slug, code, message });

for (const template of templateDirs) {
  const html = fs.readFileSync(path.join(template.directory, 'index.html'), 'utf8');
  const files = walk(template.directory);
  const totalBytes = files.reduce((sum, file) => sum + fs.statSync(file).size, 0);
  if (!/<html[^>]+lang=["']pt-BR["']/i.test(html)) add('error', template.slug, 'html-lang', 'Defina lang="pt-BR".');
  if (!/<meta[^>]+name=["']viewport["']/i.test(html)) add('error', template.slug, 'viewport', 'Meta viewport ausente.');
  if (!/<title>[^<]{8,}<\/title>/i.test(html)) add('error', template.slug, 'title', 'Título ausente ou curto.');
  if (!/<meta[^>]+name=["']description["']/i.test(html)) add('warning', template.slug, 'description', 'A build deve receber uma descrição específica.');
  if (!/<meta[^>]+name=["']robots["']/i.test(html)) add('warning', template.slug, 'robots', 'Fonte sem robots; preview build aplicará noindex.');
  if (!/<main(?:\s|>)/i.test(html)) add('error', template.slug, 'landmark-main', 'Landmark main ausente.');
  if (!/<h1(?:\s|>)/i.test(html)) add('error', template.slug, 'heading-h1', 'H1 ausente.');
  if (/href\s*=\s*["']#["']/i.test(html)) add('error', template.slug, 'empty-link', 'Link vazio href="#" encontrado.');
  if (totalBytes > policy.assetBudgets.totalPageBytes) add('warning', template.slug, 'page-weight', `Diretório tem ${(totalBytes / 1048576).toFixed(1)} MB; orçamento ${Math.round(policy.assetBudgets.totalPageBytes / 1048576)} MB.`);
  for (const file of files) {
    const bytes = fs.statSync(file).size;
    const extension = path.extname(file).toLowerCase();
    if (['.png', '.jpg', '.jpeg', '.webp', '.avif'].includes(extension) && bytes > policy.assetBudgets.imageBytes) {
      add('warning', template.slug, 'image-weight', `${path.relative(template.directory, file)} tem ${Math.round(bytes / 1024)} KB.`);
    }
    if (['.mp4', '.webm'].includes(extension) && bytes > policy.assetBudgets.videoBytes) {
      add('warning', template.slug, 'video-weight', `${path.relative(template.directory, file)} tem ${(bytes / 1048576).toFixed(1)} MB.`);
    }
  }
}

if (mode === 'production') {
  if (!siteConfig) add('error', 'publication', 'config-required', 'Produção exige --config <arquivo.json>.');
  else {
    for (const field of policy.productionRequired) {
      if (!String(get(siteConfig, field) ?? '').trim()) add('error', siteConfig.template || 'publication', 'required-field', `Campo obrigatório vazio: ${field}.`);
    }
    const category = classify(siteConfig.template || '');
    if (policy.credentialRequiredFor.includes(category) && !String(get(siteConfig, 'professional.credential') ?? '').trim()) {
      add('error', siteConfig.template || 'publication', 'credential-required', 'Registro profissional obrigatório para publicação.');
    }
    if (!/^https:\/\//i.test(get(siteConfig, 'site.canonicalUrl') || '')) add('error', siteConfig.template || 'publication', 'canonical-url', 'canonicalUrl deve usar HTTPS.');
    if (!/^\d{12,13}$/.test(String(get(siteConfig, 'contact.whatsapp') || '').replace(/\D/g, ''))) add('error', siteConfig.template || 'publication', 'whatsapp', 'WhatsApp deve conter DDI, DDD e número.');
    const selected = templateDirs.find((entry) => entry.slug === siteConfig.template);
    if (!selected) add('error', siteConfig.template || 'publication', 'template-missing', 'Template informado não existe.');
    else {
      const combined = walk(selected.directory).filter((file) => /\.(html|js|json|css)$/i.test(file)).map((file) => fs.readFileSync(file, 'utf8')).join('\n');
      for (const pattern of policy.forbiddenProductionPatterns) {
        if (combined.includes(pattern)) add('error', selected.slug, 'placeholder', `Placeholder proibido encontrado: ${pattern}.`);
      }
    }
  }
}

const counts = findings.reduce((acc, item) => ({ ...acc, [item.severity]: (acc[item.severity] || 0) + 1 }), {});
if (jsonOutput) console.log(JSON.stringify({ mode, templates: templateDirs.length, counts, findings }, null, 2));
else {
  console.log(`Template Quality Gate | modo=${mode} | templates=${templateDirs.length}`);
  for (const item of findings) console.log(`${item.severity.toUpperCase()} [${item.slug}] ${item.code}: ${item.message}`);
  console.log(`Resumo: ${counts.error || 0} erro(s), ${counts.warning || 0} aviso(s).`);
}
process.exit((counts.error || 0) > 0 || (strict && (counts.warning || 0) > 0) ? 1 : 0);
