"""Independent local forward test; writes only beside this script."""
import importlib.util
import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent
repo = root.parents[1]
spec = importlib.util.spec_from_file_location('landing_preview', repo / 'app/web_studio/landing_system.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

brief = {
    'request': 'Prévia de landing page para psicóloga, para avaliar direção visual clara.',
    'mode': 'preview',
    'offer': 'Psicologia; modalidades, público e abordagem ainda a confirmar.',
    'primary_audience': 'Hipótese reversível para layout: pessoas adultas buscando atendimento.',
    'primary_cta': 'Conhecer a proposta; âncora local, sem envio ou agendamento real.',
    'proofs': [],
    'missing': ['nome', 'telefone', 'cidade', 'registro profissional', 'formação', 'modalidades', 'fotografia autorizada'],
    'direction_options': [
        'Recomendada: papel claro, sálvia, serifas e formas suaves; família psicologo-template-1.',
        'Alternativa: editorial rosé com vinho e tipografia em itálico; família psicologo-template-3.'
    ],
    'direction_reason': 'A primeira favorece acolhimento, leitura e hierarquia simples para avaliar o conceito.',
    'sections': ['hero: qual é a proposta?', 'temas: como organizar possíveis demandas?', 'percurso: como explicar o primeiro contato?', 'sobre: quem atende?', 'FAQ: quais informações faltam?', 'contato: quais dados fornecer?'],
    'motion_map': 'Sem animações nesta prévia; conteúdo integral disponível sem JavaScript.',
    'architecture': 'HTML estático com CSS embutido e imagem local demonstrativa; sem analytics ou integrações.',
    'acceptance': ['robots noindex, nofollow, noarchive', 'sem contatos ou credenciais inventados', 'sem chamadas externas', 'identificação explícita de demonstração'],
    'risks': ['Responsividade, teclado e contraste precisam de inspeção em navegador.', 'Copy e público ainda são hipóteses.'],
}
(root / 'brief.json').write_text(json.dumps(brief, ensure_ascii=False, indent=2), encoding='utf-8')
destination = module.build_template_preview('psicologo-template-1', root)
page = destination / 'index.html'
html = page.read_text(encoding='utf-8')
html = re.sub(r'<script\b.*?</script>', '', html, flags=re.S | re.I)
html = html.replace('Clara Mente', '[Nome da psicóloga]')
html = html.replace('Agendar conversa', 'Ver proposta')
html = html.replace('Como funciona</a>', 'Conhecer a proposta</a>')
html = html.replace('Conhecer abordagem', 'Explorar a página')
html = html.replace('Psicologia para adultos', 'Conceito demonstrativo · Psicologia')
html = html.replace('Demandas acolhidas', 'Temas ilustrativos · a confirmar')
html = html.replace('WhatsApp <b>configurar</b>', 'Telefone <b>não informado</b>')
html = html.replace('Localização <b>configurar</b>', 'Cidade <b>não informada</b>')
html = html.replace('Atendimento <b>configurar</b>', 'Registro profissional <b>não informado</b>')
html = html.replace('</head>', '''<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' data:; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<style>.reveal{opacity:1;transform:none}.nav{position:relative}.hero{padding-top:2rem}aside[role=note]{padding:1rem 5vw;background:#20251f;color:#eee9df;line-height:1.5}.btn.primary,.contact{background:#46583e;color:#fff}.eyebrow,.card small{color:#46583e}.contact .eyebrow{color:inherit}a:focus-visible,summary:focus-visible{outline:3px solid currentColor;outline-offset:5px}.portrait:after{content:'Imagem demonstrativa · não representa a profissional';position:absolute;bottom:0;left:0;right:0;padding:1rem;background:#20251f;color:#fff;font: .8rem/1.4 Arial,sans-serif}@media(max-width:420px){.contact-list span{gap:1rem;flex-wrap:wrap}.nav b{letter-spacing:0}.footer{gap:1rem;flex-wrap:wrap}}</style></head>''')
html = html.replace('Prévia de template: conteúdo demonstrativo. Personalize e valide os dados antes de publicar.', 'PRÉVIA VISUAL · Texto, público e imagem demonstrativos. Nome, telefone, cidade e registro profissional pendentes. Sem agendamento real.')
page.write_text(html, encoding='utf-8')
metadata = {'template': 'psicologo-template-1', 'published': False, 'personalized': 'visual concept only', 'quality_verified': False, 'robots': 'noindex, nofollow, noarchive', 'missing_real_data': brief['missing']}
(destination / 'kiara-preview.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding='utf-8')
checks = {
    'robots': 'noindex, nofollow, noarchive' in html,
    'scripts_removed': '<script' not in html.lower(),
    'network_isolation_csp': 'default-src &#39;none&#39;' in html or "default-src 'none'" in html,
    'no_contact_links': not re.search(r'(?:href|src)=["\'](?:https?:|tel:|mailto:)', html, re.I),
    'anchors_resolve': all(f'id="{anchor}"' in html for anchor in re.findall(r'href="#([^"]+)"', html)),
    'local_images_exist': all((destination / src).is_file() for src in re.findall(r'<img[^>]+src="([^"]+)"', html)),
    'page_budget': sum(p.stat().st_size for p in destination.rglob('*') if p.is_file()) <= 9000000,
    'image_budget': all(p.stat().st_size <= 750000 for p in destination.rglob('*.webp')),
}
result = {'artifact': str(page.relative_to(root)), 'checks': checks, 'browser_verified': False, 'external_calls': False, 'published': False}
(root / 'checks.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
