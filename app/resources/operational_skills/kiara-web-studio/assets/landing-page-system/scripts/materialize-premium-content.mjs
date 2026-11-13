import { readFile, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { join } from 'node:path';

const project = fileURLToPath(new URL('../', import.meta.url));
const templates = join(project, 'templates');
const data = JSON.parse(await readFile(join(templates, 'content', 'site-profiles.json'), 'utf8'));
const esc = (value='') => String(value).replace(/[&<>"']/g,(char)=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const marker = /<!-- premium-content:start -->[\s\S]*?<!-- premium-content:end -->/;

for (const profile of data.profiles) {
  const file = join(templates, profile.slug, 'index.html');
  let html = await readFile(file, 'utf8');
  const serviceCards = profile.services.map((service,index)=>`<article class="premium-content__card" data-premium-card><small>0${index+1}</small><h3>${esc(service.name)}</h3><p>${esc(service.forWhom)}</p><ul>${service.includes.map(item=>`<li>${esc(item)}</li>`).join('')}</ul><div class="premium-content__meta">${esc(service.duration)} · ${esc(service.modality)}</div></article>`).join('');
  const steps = profile.process.map(step=>`<article class="premium-content__step"><h3>${esc(step.title)}</h3><p>${esc(step.description)}</p></article>`).join('');
  const faqs = profile.faq.map((item,index)=>`<details${index===0?' open':''}><summary>${esc(item.question)}<span aria-hidden="true">+</span></summary><p>${esc(item.answer)}</p></details>`).join('');
  const proof = profile.proof.map(item=>`<p class="premium-content__demo"><strong>Área de prova em demonstração</strong><br>${esc(item.demoLabel)}</p>`).join('');
  const block = `<!-- premium-content:start --><section class="premium-content" id="conteudo-premium"><section class="premium-content__section"><div class="premium-content__shell premium-content__intro"><div><span class="premium-content__eyebrow">${esc(profile.hero.eyebrow)}</span><h2>${esc(profile.hero.headline)}</h2></div><p class="premium-content__lead">${esc(profile.hero.subheadline)}</p></div></section><section class="premium-content__section" id="servicos"><div class="premium-content__shell"><span class="premium-content__eyebrow">Serviços</span><h2>Escolha a experiência ideal.</h2><div class="premium-content__grid">${serviceCards}</div></div></section><section class="premium-content__section"><div class="premium-content__shell"><span class="premium-content__eyebrow">Como funciona</span><h2>Uma jornada clara do início ao acompanhamento.</h2><div class="premium-content__steps">${steps}</div></div></section><section class="premium-content__section"><div class="premium-content__shell premium-content__trust"><div><span class="premium-content__eyebrow">Confiança</span><h2>Provas reais entram antes da publicação.</h2>${proof}</div><div><span class="premium-content__eyebrow">Atendimento local</span><h2>Contato e localização.</h2><p class="premium-content__lead">Este modelo está em modo demonstração. Endereço, registro profissional, agenda e canais reais serão ativados na personalização.</p><div class="premium-content__contact"><span class="premium-content__disabled">WhatsApp <b>configurar</b></span><span class="premium-content__disabled">Localização <b>configurar</b></span></div></div></div></section><section class="premium-content__section"><div class="premium-content__shell"><span class="premium-content__eyebrow">Dúvidas frequentes</span><h2>Antes de começar.</h2>${faqs}</div></section><section class="premium-content__section premium-content__final"><div class="premium-content__shell"><span class="premium-content__eyebrow">Próximo passo</span><h2>${esc(profile.hero.primaryCta)}</h2><p>O botão será ativado com o canal oficial do profissional.</p><span class="premium-content__disabled">Contato em configuração</span></div></section></section><!-- premium-content:end -->`;
  html = html.replace(/<script src="commercial-sections\.js" defer><\/script>/g, '');
  html = html.replace(/href="#"/g, 'href="#conteudo-premium"');
  if (!html.includes('../system/premium-content.css')) html = html.replace('</head>', '<link rel="stylesheet" href="../system/premium-content.css"></head>');
  if (!html.includes('class="skip-link"')) html = html.replace(/<body([^>]*)>/i, '<body$1><a class="skip-link" href="#conteudo-premium">Pular para o conteúdo</a>');
  html = marker.test(html) ? html.replace(marker, block) : html.replace('</body>', `${block}</body>`);
  if (!html.includes('name="description"')) html = html.replace('</title>', `</title><meta name="description" content="${esc(profile.hero.subheadline)}">`);
  await writeFile(file, html, 'utf8');
}
console.log(`Static premium content materialized in ${data.profiles.length} templates.`);
