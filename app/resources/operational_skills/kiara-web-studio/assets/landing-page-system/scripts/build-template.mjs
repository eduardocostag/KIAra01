#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const args = process.argv.slice(2);
const value = (flag) => { const i = args.indexOf(flag); return i >= 0 ? args[i + 1] : undefined; };
const mode = value('--mode') || 'preview';
const configFile = value('--config');
if (!configFile) throw new Error('Use --config <arquivo.json>.');
const config = JSON.parse(fs.readFileSync(path.resolve(configFile), 'utf8'));
if (mode === 'production') {
  const child = await import('node:child_process');
  child.execFileSync(process.execPath, [path.join(root, 'scripts', 'template-quality.mjs'), '--mode', 'production', '--config', path.resolve(configFile)], { stdio: 'inherit' });
}
const source = path.join(root, 'templates', config.template);
const destination = path.join(root, 'dist', config.template);
if (!fs.existsSync(path.join(source, 'index.html'))) throw new Error(`Template não encontrado: ${config.template}`);
fs.rmSync(destination, { recursive: true, force: true });
fs.mkdirSync(path.dirname(destination), { recursive: true });
fs.cpSync(source, destination, { recursive: true });

let html = fs.readFileSync(path.join(destination, 'index.html'), 'utf8');
const escape = (text) => String(text || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;');
const robots = mode === 'production' ? 'index, follow, max-image-preview:large' : 'noindex, nofollow, noarchive';
const metadata = [
  `<meta name="robots" content="${robots}">`,
  `<meta name="description" content="${escape(config.site?.description || 'Demonstração de landing page premium para profissionais.')}">`,
  `<meta property="og:type" content="website">`,
  `<meta property="og:title" content="${escape(config.site?.name || 'Landing page premium')}">`,
  `<meta property="og:description" content="${escape(config.site?.description || 'Demonstração de landing page premium para profissionais.')}">`,
  `<meta name="twitter:card" content="summary_large_image">`
];
if (mode === 'production') {
  metadata.push(`<link rel="canonical" href="${escape(config.site.canonicalUrl)}">`);
  metadata.push(`<meta property="og:url" content="${escape(config.site.canonicalUrl)}">`);
}
html = html.replace(/<meta[^>]+name=["'](?:robots|description)["'][^>]*>/gi, '')
  .replace(/<link[^>]+rel=["']canonical["'][^>]*>/gi, '')
  .replace(/<\/head>/i, `${metadata.join('')}\n</head>`);
fs.writeFileSync(path.join(destination, 'index.html'), html);
console.log(`Build ${mode} criada em ${path.relative(root, destination)}`);
