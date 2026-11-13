import { mkdir, copyFile, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const project=fileURLToPath(new URL('../',import.meta.url));
const templates=join(project,'templates');
const generated='C:/Users/EduardoGonçalves/.codex/generated_images/01a05783-9e38-7190-b5d0-a79c0ad8b895';
const items=[
 {slug:'nutricionista-template-1',base:1,name:'Essência Nutri',title:'Alimentação possível para uma vida que acontece de verdade.',eyebrow:'Nutrição clínica',lead:'Estratégia alimentar individual, escuta e acompanhamento para construir mudanças sustentáveis.',services:['Consulta nutricional','Plano individual','Acompanhamento'],method:'Ciência, escuta e escolhas que cabem na sua rotina.',accent:'#7b8c55',paper:'#f2eee4',ink:'#273025',photo:'exec-d0f42cec-da1b-483e-b6f7-05808c550bd4.png'},
 {slug:'nutricionista-template-2',base:2,name:'Fuel Lab',title:'Nutrição que acompanha a sua performance.',eyebrow:'Nutrição esportiva',lead:'Planejamento alimentar para treinar, recuperar e competir com estratégia.',services:['Avaliação esportiva','Estratégia de prova','Monitoramento'],method:'Dados orientam o plano. Sua rotina determina como ele funciona.',accent:'#9cc63b',paper:'#18201d',ink:'#f0f3e9',photo:'exec-7b45534e-0e5e-4692-b3b9-74aeeebf92db.png'},
 {slug:'nutricionista-template-3',base:3,name:'Ciclo',title:'Nutrição para respeitar seu corpo em cada fase.',eyebrow:'Saúde da mulher',lead:'Acompanhamento nutricional atento ao ciclo, à saúde hormonal e à relação com a comida.',services:['Saúde hormonal','Fertilidade e ciclo','Comportamento alimentar'],method:'Cuidado sem culpa, com contexto, evidência e autonomia.',accent:'#b65e45',paper:'#efe2d8',ink:'#3b211e',photo:'exec-f081b66f-200a-46b2-8ed7-89505f7fc8a9.png'},
 {slug:'nutricionista-template-4',base:4,name:'Crescer Bem',title:'Boas relações com a comida começam em família.',eyebrow:'Nutrição materno-infantil',lead:'Orientação acolhedora para introdução alimentar, seletividade e rotina familiar.',services:['Introdução alimentar','Seletividade alimentar','Rotina da família'],method:'Menos pressão à mesa. Mais segurança para crescer.',accent:'#e19a55',paper:'#eef1e7',ink:'#27362e',photo:'exec-ab7e2b23-622c-4de7-9ad3-759bae745398.png'},
 {slug:'nutricionista-template-5',base:5,name:'Nutri Online',title:'Seu acompanhamento nutricional, onde você estiver.',eyebrow:'Consulta online',lead:'Um processo próximo e organizado para cuidar da alimentação sem complicar a agenda.',services:['Consulta por vídeo','Plano digital','Check-ins'],method:'Distância não precisa significar um cuidado distante.',accent:'#ef765a',paper:'#e9f1ef',ink:'#183337',photo:'exec-dc6ef342-dc77-4bd9-a613-aeee9760864d.png'},
 {slug:'advogado-template-1',base:4,name:'Vértice Legal',title:'Decisões empresariais com base jurídica sólida.',eyebrow:'Direito empresarial',lead:'Assessoria estratégica para prevenir riscos, organizar contratos e apoiar o crescimento.',services:['Contratos empresariais','Consultivo preventivo','Societário'],method:'Clareza jurídica para decidir antes que o risco se torne problema.',accent:'#b39560',paper:'#111719',ink:'#f2efe8',photo:'exec-a99af4b6-4d5f-40c4-8f63-b2910e1e0523.png'},
 {slug:'advogado-template-2',base:1,name:'Acordo Humano',title:'Cuidado jurídico para decisões que envolvem toda a família.',eyebrow:'Direito de família',lead:'Orientação clara, discreta e responsável em momentos sensíveis.',services:['Divórcio e acordos','Guarda e convivência','Planejamento sucessório'],method:'Técnica para proteger direitos. Escuta para compreender pessoas.',accent:'#8a6d5b',paper:'#efe9e1',ink:'#30251f',photo:'exec-b29c551d-da61-43a5-85e2-bfd4add209ec.png'},
 {slug:'advogado-template-3',base:2,name:'Direito Próximo',title:'Seus direitos explicados de um jeito claro.',eyebrow:'Direito previdenciário',lead:'Análise cuidadosa de benefícios, documentos e possibilidades, sem promessas de resultado.',services:['Planejamento previdenciário','Benefícios e revisões','Atendimento digital'],method:'Informação acessível para escolhas juridicamente responsáveis.',accent:'#3f7186',paper:'#e9eef0',ink:'#183039',photo:'exec-d1f27d46-9933-4981-8b7b-0b769cbe28e0.png'},
 {slug:'advogado-template-4',base:5,name:'Marco Imobiliário',title:'Segurança jurídica para patrimônios e negócios imobiliários.',eyebrow:'Direito imobiliário',lead:'Análise documental, contratos e regularização com visão técnica e objetiva.',services:['Due diligence','Contratos imobiliários','Regularização'],method:'Cada detalhe documental importa antes de assinar ou investir.',accent:'#9b7d4d',paper:'#e7e5df',ink:'#202728',photo:'exec-d16698e4-e5fb-4d41-8b15-28f5850204b6.png'},
 {slug:'advogado-template-5',base:3,name:'Alba Advocacia',title:'Estratégia jurídica com discrição e presença.',eyebrow:'Escritório boutique',lead:'Atendimento personalizado para questões patrimoniais, empresariais e familiares complexas.',services:['Consultoria estratégica','Contencioso selecionado','Planejamento patrimonial'],method:'Poucos casos. Atenção profunda. Estratégia sob medida.',accent:'#ad7a68',paper:'#211516',ink:'#f3e8e3',photo:'exec-3d9784c3-ff8b-4e99-a379-8b7d4f1d5cd8.png'}
];

for(const p of items){
 const source=join(templates,`psicologo-template-${p.base}`,'index.html');
 let html=await readFile(source,'utf8');
 const dir=join(templates,p.slug),assets=join(dir,'assets'); await mkdir(assets,{recursive:true});
 await copyFile(join(generated,p.photo),join(assets,'professional-hero-v1.png'));
 await copyFile(join(templates,'character-motion.js'),join(dir,'character-motion.js'));
 html=html
  .replace(/<title>[\s\S]*?<\/title>/,`<title>${p.name} — ${p.slug.startsWith('advogado')?'Advocacia':'Nutrição'}</title>`)
  .replace(/--accent:[^;]+;--paper:[^;]+;--ink:[^";]+/,`--accent:${p.accent};--paper:${p.paper};--ink:${p.ink}`)
  .replace(/<nav class="nav"><b>[^<]+<\/b>/,`<nav class="nav"><b>${p.name}</b>`)
  .replace(/<span class="eyebrow">[^<]+<\/span><h1>[^<]+<\/h1><p class="lead">[^<]+<\/p>/,`<span class="eyebrow">${p.eyebrow}</span><h1>${p.title}</h1><p class="lead">${p.lead}</p>`)
  .replace('assets/psychologist-hero-v1.webp','assets/professional-hero-v1.png')
  .replace('Retrato demonstrativo de profissional de psicologia',`Retrato demonstrativo de profissional de ${p.slug.startsWith('advogado')?'advocacia':'nutrição'}`)
  .replace(/<blockquote class="reveal">[^<]+<\/blockquote>/,`<blockquote class="reveal">${p.method}</blockquote>`)
  .replace(/<article class="card reveal">[\s\S]*?<\/article><article class="card reveal">[\s\S]*?<\/article><article class="card reveal">[\s\S]*?<\/article>/,p.services.map((s,i)=>`<article class="card reveal"><small>0${i+1}</small><h3>${s}</h3><p>${p.slug.startsWith('advogado')?'Atuação definida após análise do caso, documentos e limites profissionais.':'Estratégia individual definida após avaliação e acompanhamento profissional.'}</p></article>`).join(''))
  .replace(/Este espaço apresentará[^<]+/,`Este espaço apresentará formação, experiência, especialidades e ${p.slug.startsWith('advogado')?'OAB':'CRN'} reais do profissional antes da publicação.`)
  .replace(/Nome, CRP, especializações/,`Nome, ${p.slug.startsWith('advogado')?'OAB':'CRN'}, especializações`)
  .replace(/<footer class="footer"><span>[^<]+<\/span>/,`<footer class="footer"><span>${p.name}</span>`);
 const legal=p.slug.startsWith('advogado');
 html=html
  .replace('Modelo de landing page para psicologia e psicoterapia.',legal?'Modelo de landing page para advocacia e atendimento jurídico.':'Modelo de landing page para nutrição e acompanhamento nutricional.')
  .replace('O processo terapêutico não oferece promessas prontas. Ele cria condições para compreender experiências, ampliar possibilidades e construir mudanças possíveis.',legal?'A atuação jurídica depende da análise individual dos fatos e documentos. Nenhum resultado é garantido e toda estratégia respeita os limites éticos profissionais.':'O acompanhamento nutricional não oferece soluções universais. Condutas, metas e frequência dependem de avaliação individual e acompanhamento responsável.')
  .replace('Antes da primeira sessão.',legal?'Antes da análise do caso.':'Antes da primeira consulta.')
  .replace('O atendimento pode ser online?',legal?'O atendimento pode ser digital?':'A consulta pode ser online?')
  .replace('Qual a duração das sessões?',legal?'Como funcionam honorários e prazos?':'Como funcionam retorno e acompanhamento?')
  .replace('Psicoterapia é indicada para mim?',legal?'Existe garantia de resultado?':'Receberei uma dieta pronta?')
  .replace('O primeiro encontro ajuda a compreender a demanda e avaliar, com responsabilidade, o melhor encaminhamento.',legal?'Não. O resultado depende de fatos, provas, legislação e decisões de terceiros; a proposta deve explicar riscos e possibilidades.':'O plano é construído após avaliação, considerando necessidades, preferências, rotina e condições de saúde.')
  .replace('Duração, frequência, honorários e política de cancelamento serão informados pelo profissional.',legal?'Honorários, escopo, documentos e prazos estimados serão formalizados pelo escritório.':'Frequência, retornos, investimento e política de cancelamento serão informados pelo profissional.');
 await writeFile(join(dir,'index.html'),html,'utf8');
}
console.log(`Created ${items.length} nutrition and law templates.`);
