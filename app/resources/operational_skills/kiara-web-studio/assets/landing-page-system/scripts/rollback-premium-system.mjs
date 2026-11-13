import { readdir, readFile, writeFile, copyFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const templates = fileURLToPath(new URL('../templates/', import.meta.url));
const entries = await readdir(templates, { withFileTypes: true });
const slugs = entries
  .filter((entry) => entry.isDirectory() && /^(beleza-template-|dentista-template-|educador-fisico-template-|personal-trainer)/.test(entry.name))
  .map((entry) => entry.name);

for (const slug of slugs) {
  const directory = join(templates, slug);
  const file = join(directory, 'index.html');
  let html = await readFile(file, 'utf8');

  html = html
    .replace(/<!-- premium-content:start -->[\s\S]*?<!-- premium-content:end -->/g, '')
    .replace(/<link rel="stylesheet" href="\.\.\/system\/premium-(?:core|families|content)\.css">/g, '')
    .replace(/<script src="\.\.\/system\/premium-design\.js"><\/script>/g, '')
    .replace(/<a class="skip-link" href="#conteudo-premium">Pular para o conteúdo<\/a>/g, '')
    .replace(/href="#conteudo-premium"/g, 'href="#"');

  if (!html.includes('commercial-sections.js')) {
    html = html.replace('</body>', '<script src="commercial-sections.js" defer></script></body>');
  }

  await copyFile(join(templates, 'commercial-sections.js'), join(directory, 'commercial-sections.js'));
  await writeFile(file, html, 'utf8');
}

console.log(`Previous visual version restored in ${slugs.length} templates.`);
