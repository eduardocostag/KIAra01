import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('../templates/', import.meta.url));
const entries = await readdir(root, { withFileTypes: true });
const slugs = entries
  .filter((entry) => entry.isDirectory() && /^(beleza-template-|dentista-template-|educador-fisico-template-|personal-trainer)/.test(entry.name))
  .map((entry) => entry.name);

for (const slug of slugs) {
  const file = join(root, slug, 'index.html');
  let html = await readFile(file, 'utf8');

  if (!html.includes('name="robots"')) {
    html = html.replace(/<meta name="viewport"[^>]*>/i, (match) => `${match}<meta name="robots" content="noindex,nofollow,noarchive">`);
  }

  if (!html.includes('../system/premium-core.css')) {
    html = html.replace('</head>', '<link rel="stylesheet" href="../system/premium-core.css"><link rel="stylesheet" href="../system/premium-families.css"></head>');
  }

  if (!html.includes('../system/premium-design.js')) {
    html = html.replace('</body>', '<script src="../system/premium-design.js"></script></body>');
  }

  await writeFile(file, html, 'utf8');
}

console.log(`Premium system applied to ${slugs.length} templates.`);
