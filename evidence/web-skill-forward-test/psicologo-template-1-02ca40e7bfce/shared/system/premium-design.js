(function () {
  'use strict';

  const themes = Object.freeze({
    'beleza-template-1': { family: 'editorial-luxury', tone: 'champagne', concept: 'Quiet Luxury Studio' },
    'beleza-template-2': { family: 'local-service', tone: 'barber-oxide', concept: 'Distrito Ritual' },
    'beleza-template-3': { family: 'portfolio-first', tone: 'rose-noir', concept: 'Atelier Cromatico' },
    'beleza-template-4': { family: 'portfolio-first', tone: 'pearl', concept: 'Nail Object Gallery' },
    'beleza-template-5': { family: 'editorial-luxury', tone: 'terracotta', concept: 'Skin Journal' },
    'beleza-template-6': { family: 'local-service', tone: 'soft-sage', concept: 'Beauty Neighbourhood' },
    'beleza-template-7': { family: 'clinical-trust', tone: 'blush-clinic', concept: 'Aesthetic Protocol' },
    'dentista-template-1': { family: 'clinical-trust', tone: 'aura-green', concept: 'Precision Smile System' },
    'dentista-template-2': { family: 'editorial-luxury', tone: 'ivory-gold', concept: 'Smile Atelier' },
    'dentista-template-3': { family: 'family-care', tone: 'sky-coral', concept: 'Small Courage Club' },
    'dentista-template-4': { family: 'performance-system', tone: 'navy-cyan', concept: 'Digital Dentistry Lab' },
    'dentista-template-5': { family: 'local-service', tone: 'warm-clay', concept: 'Neighbourhood Dental' },
    'educador-fisico-template-1': { family: 'performance-system', tone: 'graphite-lime', concept: 'Human Performance Journal' },
    'educador-fisico-template-2': { family: 'local-service', tone: 'sand-orange', concept: 'Movement Club' },
    'educador-fisico-template-3': { family: 'performance-system', tone: 'midnight-blue', concept: 'Athlete Operating System' },
    'educador-fisico-template-4': { family: 'editorial-luxury', tone: 'plum-rose', concept: 'Strong Feminine' },
    'educador-fisico-template-5': { family: 'family-care', tone: 'forest-sun', concept: 'Everyday Vitality' },
    'personal-trainer': { family: 'performance-system', tone: 'deep-emerald', concept: 'Personal Performance' }
  });

  function currentSlug() {
    const parts = location.pathname.split('/').filter(Boolean);
    return parts.find((part) => themes[part]) || '';
  }

  function loadStyle(href, id) {
    if (document.getElementById(id)) return;
    const link = document.createElement('link');
    link.id = id;
    link.rel = 'stylesheet';
    link.href = href;
    document.head.appendChild(link);
  }

  const slug = currentSlug();
  const theme = themes[slug];
  if (!theme) return;

  const root = document.documentElement;
  root.dataset.premiumFamily = theme.family;
  root.dataset.premiumTone = theme.tone;
  root.dataset.template = slug;
  root.style.colorScheme = theme.family === 'performance-system' ? 'dark' : 'light';

  const script = document.currentScript;
  const base = script && script.src ? new URL('.', script.src).href : './system/';
  loadStyle(new URL('premium-core.css', base).href, 'premium-core');
  loadStyle(new URL('premium-families.css', base).href, 'premium-families');

  window.LandingPremiumDesign = Object.freeze({ slug, ...theme, themes });
})();
