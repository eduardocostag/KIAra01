/* Landing Cinema Engine v0.1
   Scroll driver + declarative CSS tracks + future video/sequence adapters. */
(() => {
  const clamp = (value, min = 0, max = 1) => Math.min(max, Math.max(min, value));
  const mix = (from, to, progress) => from + (to - from) * progress;
  const easings = {
    linear: value => value,
    smooth: value => value * value * (3 - 2 * value),
    out: value => 1 - Math.pow(1 - value, 3),
    inOut: value => value < .5 ? 4 * value ** 3 : 1 - Math.pow(-2 * value + 2, 3) / 2
  };

  class CapabilityDetector {
    constructor() {
      const connection = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
      this.reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
      this.coarsePointer = matchMedia('(pointer: coarse)').matches;
      this.saveData = Boolean(connection?.saveData);
      this.slowConnection = /(^|-)2g$/.test(connection?.effectiveType || '');
      this.lowMemory = Boolean(navigator.deviceMemory && navigator.deviceMemory <= 4);
    }
    get mode() {
      if (this.reducedMotion) return 'static';
      if (this.saveData || this.slowConnection) return 'lite';
      if (this.coarsePointer || this.lowMemory) return 'mobile';
      return 'full';
    }
  }

  class CSSVariableRenderer {
    constructor(scene, tracks = []) {
      this.scene = scene;
      this.tracks = tracks.map(track => ({
        ...track,
        target: track.target ? scene.querySelector(track.target) : scene
      }));
    }
    render(progress) {
      this.tracks.forEach(track => {
        if (!track.target) return;
        const local = clamp((progress - (track.start ?? 0)) / Math.max(.0001, (track.end ?? 1) - (track.start ?? 0)));
        const eased = (easings[track.ease] || easings.smooth)(local);
        const value = mix(track.from, track.to, eased);
        track.target.style.setProperty(track.property, `${value}${track.unit || ''}`);
      });
    }
  }

  class VideoScrubRenderer {
    constructor(video) {
      this.video = video;
      this.ready = false;
      video?.addEventListener('loadedmetadata', () => { this.ready = true; }, { once: true });
    }
    render(progress) {
      if (!this.video || !this.ready || !Number.isFinite(this.video.duration)) return;
      const next = clamp(progress) * Math.max(0, this.video.duration - .04);
      if (Math.abs(this.video.currentTime - next) > .035) this.video.currentTime = next;
    }
  }

  class ImageSequenceRenderer {
    constructor(canvas, source = {}) {
      this.canvas = canvas;
      this.context = canvas?.getContext('2d', { alpha: true });
      this.frames = new Array(source.frames || 0);
      this.template = source.template || '';
      this.pad = source.pad || 3;
      this.loaded = new Set();
      this.loading = new Set();
      this.poster = source.poster || '';
      this.focusX = clamp(source.focusX ?? 0.5);
      this.focusY = clamp(source.focusY ?? 0.5);
      this.concurrency = source.concurrency || 3;
      this.queue = [];
      this.lastFrame = -1;
      if (canvas && this.frames.length) this.preloadAnchors();
    }
    frameURL(index) {
      return this.template.replace('{frame}', String(index + 1).padStart(this.pad, '0'));
    }
    enqueue(index) {
      if (index < 0 || index >= this.frames.length || this.loaded.has(index) || this.loading.has(index) || this.queue.includes(index)) return;
      this.queue.push(index);
      this.pump();
    }
    pump() {
      while (this.loading.size < this.concurrency && this.queue.length) {
        const index = this.queue.shift();
        const image = new Image();
        this.loading.add(index);
        image.decoding = 'async';
        image.onload = () => { this.frames[index] = image; this.loaded.add(index); this.loading.delete(index); this.pump(); if (index === this.lastFrame) this.draw(index); };
        image.onerror = () => { this.loading.delete(index); this.pump(); };
        image.src = this.frameURL(index);
      }
    }
    preloadAnchors() {
      [0, Math.floor((this.frames.length - 1) / 2), this.frames.length - 1].forEach(index => this.enqueue(index));
    }
    draw(index) {
      const image = this.frames[index];
      if (!image || !this.context) return;
      const canvas = this.canvas, dpr = Math.min(devicePixelRatio || 1, 1.5);
      const width = canvas.clientWidth, height = canvas.clientHeight;
      if (canvas.width !== Math.floor(width * dpr) || canvas.height !== Math.floor(height * dpr)) {
        canvas.width = Math.max(1, Math.floor(width * dpr));
        canvas.height = Math.max(1, Math.floor(height * dpr));
      }
      const scale = Math.max(canvas.width / image.naturalWidth, canvas.height / image.naturalHeight);
      const drawWidth = image.naturalWidth * scale, drawHeight = image.naturalHeight * scale;
      const drawX = -(drawWidth - canvas.width) * this.focusX;
      const drawY = -(drawHeight - canvas.height) * this.focusY;
      this.context.clearRect(0, 0, canvas.width, canvas.height);
      this.context.drawImage(image, drawX, drawY, drawWidth, drawHeight);
    }
    render(progress) {
      if (!this.frames.length) return;
      const index = Math.round(clamp(progress) * (this.frames.length - 1));
      this.lastFrame = index;
      for (let offset = 0; offset <= 5; offset++) {
        this.enqueue(index + offset);
        this.enqueue(index - offset);
      }
      if (this.loaded.has(index)) this.draw(index);
    }
  }

  class CinematicScene {
    constructor(config, capabilities) {
      this.config = config;
      this.root = document.querySelector(config.root);
      this.capabilities = capabilities;
      this.visible = false;
      this.progress = 0;
      this.renderers = [];
      if (!this.root) return;
      this.root.dataset.cinemaMode = capabilities.mode;
      this.renderers.push(new CSSVariableRenderer(this.root, config.tracks || []));
      const media = config.media?.[capabilities.mode] || config.media?.full;
      if (media?.type === 'video') this.renderers.push(new VideoScrubRenderer(this.root.querySelector(media.target)));
      if (media?.type === 'sequence') this.renderers.push(new ImageSequenceRenderer(this.root.querySelector(media.target), media));
    }
    measure() {
      if (!this.root) return;
      const debugProgress = new URLSearchParams(location.search).get('cinemaProgress');
      if (debugProgress !== null && Number.isFinite(Number(debugProgress))) {
        this.progress = clamp(Number(debugProgress));
        return;
      }
      const rect = this.root.getBoundingClientRect();
      const distance = Math.max(1, this.root.offsetHeight - innerHeight);
      this.progress = clamp(-rect.top / distance);
    }
    render() {
      if (!this.root) return;
      if (this.capabilities.mode === 'static') return;
      this.renderers.forEach(renderer => renderer.render(this.progress));
      this.root.style.setProperty('--cinema-progress', `${this.progress * 100}%`);
      this.root.dispatchEvent(new CustomEvent('cinema:progress', { detail: { progress: this.progress, mode: this.capabilities.mode } }));
    }
  }

  class LandingCinemaEngine {
    constructor(configs = []) {
      this.capabilities = new CapabilityDetector();
      this.scenes = configs.map(config => new CinematicScene(config, this.capabilities)).filter(scene => scene.root);
      this.frame = 0;
      this.observer = new IntersectionObserver(entries => entries.forEach(entry => {
        const scene = this.scenes.find(item => item.root === entry.target);
        if (scene) scene.visible = entry.isIntersecting;
      }), { rootMargin: '100% 0px' });
      this.scenes.forEach(scene => this.observer.observe(scene.root));
      this.request = this.request.bind(this);
      addEventListener('scroll', this.request, { passive: true });
      addEventListener('resize', this.request, { passive: true });
      this.request();
      document.documentElement.dataset.cinema = this.capabilities.mode;
    }
    request() {
      if (this.frame) return;
      this.frame = requestAnimationFrame(() => {
        this.scenes.forEach(scene => { if (scene.visible || scene.progress === 0) { scene.measure(); scene.render(); } });
        this.frame = 0;
      });
    }
  }

  const boot = () => {
    window.landingCinema = new LandingCinemaEngine(window.CINEMATIC_SCENES || []);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', boot, { once: true }); else boot();
  window.LandingCinemaEngine = LandingCinemaEngine;
})();
