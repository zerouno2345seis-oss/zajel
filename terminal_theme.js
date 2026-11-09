(() => {
  'use strict';
  if (window.ZajelTermTheme) return;

  const PRESETS = {
    'calm-dark': {
      name: 'داكن هادئ',
      dark: true,
      bg: '#141a26',
      fg: '#c9d1dc',
      a: '#d8f0e0',
      q: '#ffe7a3',
      qbg: 'rgba(212,170,60,.10)',
      qborder: '#d4aa3c',
      palette: [
        '#3b4252', '#ef5350', '#4ade80', '#eab308',
        '#60a5fa', '#c084fc', '#38bdf8', '#c9d1dc',
        '#64748b', '#f87171', '#86efac', '#fde047',
        '#93c5fd', '#d8b4fe', '#7dd3fc', '#f8fafc'
      ]
    },
    'comfy-light': {
      name: 'فاتح مريح',
      dark: false,
      bg: '#fbf7ee',
      fg: '#3b3b3b',
      a: '#1c1c1c',
      q: '#123a7a',
      qbg: 'rgba(37,99,235,.07)',
      qborder: '#2563eb',
      palette: [
        '#1f2937', '#b91c1c', '#15803d', '#b45309',
        '#1d4ed8', '#7e22ce', '#0e7490', '#475569',
        '#64748b', '#dc2626', '#16a34a', '#d97706',
        '#2563eb', '#9333ea', '#0891b2', '#334155'
      ]
    },
    'warm-night': {
      name: 'ليلي دافئ',
      dark: true,
      bg: '#1e1712',
      fg: '#d9c7ad',
      a: '#ecd9bb',
      q: '#ffc66d',
      qbg: 'rgba(255,170,60,.10)',
      qborder: '#e0953a',
      palette: [
        '#3d2f24', '#e06c5a', '#8eb365', '#e5ad58',
        '#7aa2b8', '#c77ca7', '#73b8a3', '#d9c7ad',
        '#634f3e', '#f08270', '#a3c97b', '#f5be6e',
        '#8fb8cf', '#dc91bd', '#8aced7', '#faede0'
      ]
    },
    'high-contrast': {
      name: 'تباين عالٍ',
      dark: true,
      bg: '#000000',
      fg: '#ffffff',
      a: '#ffffff',
      q: '#ffff00',
      qbg: 'rgba(255,255,0,.12)',
      qborder: '#ffff00',
      palette: [
        '#333333', '#ff4d4d', '#4dff4d', '#ffff4d',
        '#4d94ff', '#ff4dff', '#4dffff', '#e0e0e0',
        '#777777', '#ff6666', '#66ff66', '#ffff66',
        '#66a3ff', '#ff66ff', '#66ffff', '#ffffff'
      ]
    }
  };

  const HEX_RE = /^#[0-9a-f]{6}$/i;
  const ALLOWED_CUSTOM = ['bg', 'fg', 'a', 'q', 'qborder'];

  let cfg = {
    preset: 'calm-dark',
    custom: {},
    keep: true
  };

  const listeners = new Set();
  const fgCache = new Map();
  const bgCache = new Map();
  let activePanel = null;

  function clearCaches() {
    fgCache.clear();
    bgCache.clear();
  }

  // --- Color Helpers ---
  function parseRgb(color) {
    if (!color) return null;
    if (typeof color === 'object' && 'r' in color && 'g' in color && 'b' in color) {
      return color;
    }
    if (typeof color !== 'string') return null;
    const s = color.trim().toLowerCase();
    if (s.startsWith('#')) {
      const hex = s.slice(1);
      if (hex.length === 3) {
        const r = parseInt(hex[0] + hex[0], 16);
        const g = parseInt(hex[1] + hex[1], 16);
        const b = parseInt(hex[2] + hex[2], 16);
        return isNaN(r) || isNaN(g) || isNaN(b) ? null : { r, g, b };
      }
      if (hex.length === 6) {
        const r = parseInt(hex.slice(0, 2), 16);
        const g = parseInt(hex.slice(2, 4), 16);
        const b = parseInt(hex.slice(4, 6), 16);
        return isNaN(r) || isNaN(g) || isNaN(b) ? null : { r, g, b };
      }
      return null;
    }
    const m = s.match(/^rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/);
    if (m) {
      return {
        r: Math.min(255, Math.max(0, parseInt(m[1], 10))),
        g: Math.min(255, Math.max(0, parseInt(m[2], 10))),
        b: Math.min(255, Math.max(0, parseInt(m[3], 10)))
      };
    }
    return null;
  }

  function relLum(rgb) {
    if (!rgb) return 0;
    const a = [rgb.r, rgb.g, rgb.b].map(v => {
      const c = v / 255;
      return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2];
  }

  function contrast(c1, c2) {
    const rgb1 = typeof c1 === 'string' ? parseRgb(c1) : c1;
    const rgb2 = typeof c2 === 'string' ? parseRgb(c2) : c2;
    if (!rgb1 || !rgb2) return 1;
    const l1 = relLum(rgb1);
    const l2 = relLum(rgb2);
    const max = Math.max(l1, l2);
    const min = Math.min(l1, l2);
    return (max + 0.05) / (min + 0.05);
  }

  function rgbToHsl(rgb) {
    const r = rgb.r / 255;
    const g = rgb.g / 255;
    const b = rgb.b / 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    let h = 0, s = 0;
    const l = (max + min) / 2;
    if (max !== min) {
      const d = max - min;
      s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
      switch (max) {
        case r: h = (g - b) / d + (g < b ? 6 : 0); break;
        case g: h = (b - r) / d + 2; break;
        case b: h = (r - g) / d + 4; break;
      }
      h *= 60;
    }
    return { h, s, l };
  }

  function hslToRgb(h, s, l) {
    h = ((h % 360) + 360) % 360;
    s = Math.max(0, Math.min(1, s));
    l = Math.max(0, Math.min(1, l));
    let r, g, b;
    if (s === 0) {
      r = g = b = l;
    } else {
      const q = l < 0.5 ? l * (1 + s) : l + s - l * s;
      const p = 2 * l - q;
      const hue2rgb = t => {
        let val = t;
        if (val < 0) val += 1;
        if (val > 1) val -= 1;
        if (val < 1 / 6) return p + (q - p) * 6 * val;
        if (val < 1 / 2) return q;
        if (val < 2 / 3) return p + (q - p) * (2 / 3 - val) * 6;
        return p;
      };
      r = hue2rgb(h / 360 + 1 / 3);
      g = hue2rgb(h / 360);
      b = hue2rgb(h / 360 - 1 / 3);
    }
    return {
      r: Math.round(r * 255),
      g: Math.round(g * 255),
      b: Math.round(b * 255)
    };
  }

  function rgbToHex(rgb) {
    if (!rgb) return '#000000';
    const hx = n => Math.max(0, Math.min(255, Math.round(n))).toString(16).padStart(2, '0');
    return `#${hx(rgb.r)}${hx(rgb.g)}${hx(rgb.b)}`;
  }

  function rgbToCss(rgb) {
    return `rgb(${rgb.r}, ${rgb.g}, ${rgb.b})`;
  }

  function toHexColor(color) {
    if (typeof color === 'string' && HEX_RE.test(color)) return color;
    const rgb = parseRgb(color);
    return rgb ? rgbToHex(rgb) : '#000000';
  }

  // --- Core Theme API ---
  function get() {
    return {
      preset: cfg.preset,
      custom: { ...cfg.custom },
      keep: cfg.keep
    };
  }

  function resolved() {
    const base = PRESETS[cfg.preset] || PRESETS['calm-dark'];
    const res = {
      name: base.name,
      dark: base.dark,
      bg: base.bg,
      fg: base.fg,
      a: base.a,
      q: base.q,
      qbg: base.qbg,
      qborder: base.qborder,
      palette: base.palette.slice()
    };

    const custom = cfg.custom || {};
    if (custom.bg) {
      res.bg = custom.bg;
      const rgb = parseRgb(custom.bg);
      if (rgb) {
        res.dark = relLum(rgb) < 0.4;
      }
    }
    if (custom.fg) res.fg = custom.fg;
    if (custom.a) res.a = custom.a;
    if (custom.q) res.q = custom.q;
    if (custom.qborder) {
      res.qborder = custom.qborder;
      const rgb = parseRgb(custom.qborder);
      if (rgb) {
        res.qbg = `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.10)`;
      }
    }
    return res;
  }

  function palette() {
    return resolved().palette;
  }

  function notifyListeners() {
    const cur = resolved();
    listeners.forEach(fn => {
      try {
        fn(cur);
      } catch (e) {}
    });
  }

  function onChange(fn) {
    if (typeof fn === 'function') {
      listeners.add(fn);
    }
    return () => {
      listeners.delete(fn);
    };
  }

  function set(partial) {
    try {
      if (!partial || typeof partial !== 'object') return;

      if ('preset' in partial && typeof partial.preset === 'string' && PRESETS[partial.preset]) {
        cfg.preset = partial.preset;
      }

      if ('keep' in partial) {
        cfg.keep = Boolean(partial.keep);
      }

      if ('custom' in partial) {
        const nextCustom = {};
        if (partial.custom && typeof partial.custom === 'object') {
          for (const k of ALLOWED_CUSTOM) {
            const val = partial.custom[k];
            if (typeof val === 'string' && HEX_RE.test(val)) {
              nextCustom[k] = val.toLowerCase();
            }
          }
        }
        cfg.custom = nextCustom;
      }

      clearCaches();

      try {
        localStorage.setItem('zajel_term_theme', JSON.stringify(cfg));
      } catch (e) {}

      const payload = { term_theme: cfg };
      try {
        if (typeof window.api === 'function') {
          window.api('/api/assistant/settings', payload).catch(() => {});
        } else {
          fetch('/api/assistant/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          }).catch(() => {});
        }
      } catch (e) {}

      notifyListeners();
    } catch (e) {
      // Never throw
    }
  }

  function apply(el) {
    if (!el || !el.style) return;
    const t = resolved();
    el.style.setProperty('--tt-bg', t.bg);
    el.style.setProperty('--tt-fg', t.fg);
    el.style.setProperty('--tt-a', t.a);
    el.style.setProperty('--tt-q', t.q);
    el.style.setProperty('--tt-qbg', t.qbg);
    el.style.setProperty('--tt-qborder', t.qborder);
    el.dataset.ttDark = t.dark ? 'true' : 'false';
  }

  function fixFg(color) {
    if (color == null) return null;
    if (fgCache.has(color)) return fgCache.get(color);

    const rgb = parseRgb(color);
    if (!rgb) {
      fgCache.set(color, color);
      return color;
    }

    const t = resolved();
    const hsl = rgbToHsl(rgb);
    const isMeaningful = hsl.s >= 0.45 && (
      (hsl.h >= 0 && hsl.h <= 60) ||
      (hsl.h >= 330 && hsl.h <= 360) ||
      (hsl.h >= 90 && hsl.h <= 160)
    );

    let result;
    if (!cfg.keep && !isMeaningful) {
      result = null;
    } else if (contrast(rgb, t.bg) >= 3) {
      result = color;
    } else {
      const flippedRgb = hslToRgb(hsl.h, hsl.s, 1 - hsl.l);
      if (contrast(flippedRgb, t.bg) >= 3) {
        result = rgbToCss(flippedRgb);
      } else {
        result = t.fg;
      }
    }

    fgCache.set(color, result);
    return result;
  }

  function fixBg(color) {
    if (color == null) return null;
    if (bgCache.has(color)) return bgCache.get(color);

    const rgb = parseRgb(color);
    if (!rgb) {
      bgCache.set(color, color);
      return color;
    }

    const t = resolved();
    let result;
    if (contrast(rgb, t.bg) < 1.25) {
      result = null;
    } else {
      const lum = relLum(rgb);
      const isLight = !t.dark;
      const isDark = !!t.dark;
      if ((isLight && lum < 0.35) || (isDark && lum > 0.6)) {
        const bgRgb = parseRgb(t.bg) || { r: 0, g: 0, b: 0 };
        const fgRgb = parseRgb(t.fg) || { r: 255, g: 255, b: 255 };
        const r = Math.round(0.85 * bgRgb.r + 0.15 * fgRgb.r);
        const g = Math.round(0.85 * bgRgb.g + 0.15 * fgRgb.g);
        const b = Math.round(0.85 * bgRgb.b + 0.15 * fgRgb.b);
        result = `rgb(${r}, ${g}, ${b})`;
      } else {
        result = color;
      }
    }

    bgCache.set(color, result);
    return result;
  }

  // --- Storage & Sync ---
  function initStorage() {
    try {
      const raw = localStorage.getItem('zajel_term_theme');
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === 'object') {
          if (typeof parsed.preset === 'string' && PRESETS[parsed.preset]) {
            cfg.preset = parsed.preset;
          }
          if ('keep' in parsed) {
            cfg.keep = Boolean(parsed.keep);
          }
          if (parsed.custom && typeof parsed.custom === 'object') {
            const custom = {};
            for (const k of ALLOWED_CUSTOM) {
              const val = parsed.custom[k];
              if (typeof val === 'string' && HEX_RE.test(val)) {
                custom[k] = val.toLowerCase();
              }
            }
            cfg.custom = custom;
          }
        }
      }
    } catch (e) {}

    (async () => {
      try {
        const url = '/api/assistant/agents';
        let res;
        if (typeof window.api === 'function') {
          res = await window.api(url);
        } else {
          const r = await fetch(url);
          res = await r.json();
        }
        if (res && res.settings && typeof res.settings.term_theme === 'object' && res.settings.term_theme !== null) {
          const t = res.settings.term_theme;
          if (typeof t.preset === 'string' && PRESETS[t.preset]) {
            cfg.preset = t.preset;
          }
          if ('keep' in t) {
            cfg.keep = Boolean(t.keep);
          }
          const custom = {};
          if (t.custom && typeof t.custom === 'object') {
            for (const k of ALLOWED_CUSTOM) {
              const val = t.custom[k];
              if (typeof val === 'string' && HEX_RE.test(val)) {
                custom[k] = val.toLowerCase();
              }
            }
          }
          cfg.custom = custom;
          clearCaches();
          try {
            localStorage.setItem('zajel_term_theme', JSON.stringify(cfg));
          } catch (e) {}
          notifyListeners();
        }
      } catch (e) {
        // Silently ignore
      }
    })();
  }

  initStorage();

  // --- Panel UI ---
  function injectStyles() {
    if (document.getElementById('tt-panel-styles')) return;
    const style = document.createElement('style');
    style.id = 'tt-panel-styles';
    style.textContent = `
      .tt-panel {
        position: fixed;
        z-index: 100000;
        direction: rtl;
        width: 310px;
        max-width: calc(100vw - 20px);
        max-height: 80vh;
        overflow-y: auto;
        background: var(--card, #fff);
        color: var(--txt, #111);
        border: 1px solid var(--line, #ddd);
        border-radius: 10px;
        box-shadow: 0 10px 25px -5px rgba(0,0,0,0.2), 0 8px 10px -6px rgba(0,0,0,0.15);
        padding: 14px;
        box-sizing: border-box;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        font-size: 13px;
        line-height: 1.5;
      }
      .tt-panel * {
        box-sizing: border-box;
      }
      .tt-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--line, #ddd);
      }
      .tt-title {
        font-size: 14px;
        font-weight: 700;
        color: var(--txt, #111);
        margin: 0;
      }
      .tt-presets-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        margin-bottom: 14px;
      }
      .tt-preset-btn {
        background: var(--card, #fff);
        border: 1px solid var(--line, #ddd);
        border-radius: 8px;
        padding: 6px;
        cursor: pointer;
        text-align: right;
        transition: border-color 0.15s, outline 0.15s;
        outline: 2px solid transparent;
        outline-offset: 1px;
      }
      .tt-preset-btn:hover {
        border-color: var(--acc, #2563eb);
      }
      .tt-preset-btn.tt-selected {
        outline: 2px solid var(--acc, #2563eb);
        border-color: var(--acc, #2563eb);
      }
      .tt-preset-name {
        font-size: 11px;
        font-weight: 600;
        margin-bottom: 4px;
        color: var(--txt, #111);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .tt-preset-preview {
        border-radius: 6px;
        padding: 6px 8px;
        font-size: 10px;
        line-height: 1.3;
        border: 1px solid rgba(128,128,128,0.2);
      }
      .tt-preview-q {
        border-radius: 3px;
        padding: 2px 4px;
        margin-bottom: 4px;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .tt-preview-a {
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .tt-section-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--txt, #111);
        margin: 10px 0 8px;
      }
      .tt-custom-rows {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-bottom: 12px;
      }
      .tt-custom-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
      }
      .tt-custom-label {
        font-size: 12px;
        color: var(--txt, #111);
      }
      .tt-color-input {
        -webkit-appearance: none;
        -moz-appearance: none;
        appearance: none;
        width: 34px;
        height: 24px;
        padding: 0;
        border: 1px solid var(--line, #ddd);
        border-radius: 4px;
        cursor: pointer;
        background: none;
      }
      .tt-color-input::-webkit-color-swatch-wrapper {
        padding: 0;
      }
      .tt-color-input::-webkit-color-swatch {
        border: none;
        border-radius: 3px;
      }
      .tt-color-input::-moz-color-swatch {
        border: none;
        border-radius: 3px;
      }
      .tt-keep-wrap {
        display: flex;
        align-items: flex-start;
        gap: 8px;
        margin-bottom: 12px;
        cursor: pointer;
      }
      .tt-keep-checkbox {
        margin-top: 3px;
        cursor: pointer;
      }
      .tt-keep-label {
        display: flex;
        flex-direction: column;
        gap: 2px;
        cursor: pointer;
      }
      .tt-keep-title {
        font-size: 12px;
        font-weight: 600;
        color: var(--txt, #111);
      }
      .tt-keep-hint {
        font-size: 11px;
        color: var(--mut, #666);
        line-height: 1.4;
      }
      .tt-reset-btn {
        width: 100%;
        padding: 7px 12px;
        background: var(--card, #fff);
        color: var(--txt, #111);
        border: 1px solid var(--line, #ddd);
        border-radius: 6px;
        font-size: 12px;
        font-weight: 500;
        cursor: pointer;
        transition: background 0.15s, border-color 0.15s;
      }
      .tt-reset-btn:hover {
        background: rgba(0,0,0,0.03);
        border-color: var(--mut, #666);
      }
    `;
    document.head.appendChild(style);
  }

  function positionPanel(panel, anchorEl) {
    if (!anchorEl || typeof anchorEl.getBoundingClientRect !== 'function') {
      panel.style.top = '60px';
      panel.style.left = '20px';
      return;
    }
    const rect = anchorEl.getBoundingClientRect();
    const panelWidth = panel.offsetWidth || 310;
    const panelHeight = panel.offsetHeight || 420;

    let top = rect.bottom + 6;
    if (top + panelHeight > window.innerHeight - 10) {
      if (rect.top - panelHeight - 6 >= 10) {
        top = rect.top - panelHeight - 6;
      } else {
        top = Math.max(10, window.innerHeight - panelHeight - 10);
      }
    }

    let left = rect.right - panelWidth;
    if (left < 10) left = 10;
    if (left + panelWidth > window.innerWidth - 10) {
      left = Math.max(10, window.innerWidth - panelWidth - 10);
    }

    panel.style.top = `${Math.round(top)}px`;
    panel.style.left = `${Math.round(left)}px`;
  }

  function openPanel(anchorEl) {
    if (activePanel) {
      activePanel.close();
      return;
    }

    injectStyles();

    const panel = document.createElement('div');
    panel.className = 'tt-panel';

    // 1. Title
    const header = document.createElement('div');
    header.className = 'tt-header';
    const title = document.createElement('div');
    title.className = 'tt-title';
    title.textContent = 'ألوان الطرفية';
    header.appendChild(title);
    panel.appendChild(header);

    // 2. Preset buttons (2x2 grid)
    const presetsGrid = document.createElement('div');
    presetsGrid.className = 'tt-presets-grid';
    const presetBtnMap = {};

    Object.keys(PRESETS).forEach(id => {
      const p = PRESETS[id];
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'tt-preset-btn';
      if (cfg.preset === id) btn.classList.add('tt-selected');

      const nameEl = document.createElement('div');
      nameEl.className = 'tt-preset-name';
      nameEl.textContent = p.name;
      btn.appendChild(nameEl);

      const preview = document.createElement('div');
      preview.className = 'tt-preset-preview';
      preview.style.background = p.bg;
      preview.style.color = p.fg;

      const qLine = document.createElement('div');
      qLine.className = 'tt-preview-q';
      qLine.style.borderColor = p.qborder;
      qLine.style.background = p.qbg;
      qLine.style.color = p.q;
      qLine.textContent = 'سؤالك';
      preview.appendChild(qLine);

      const aLine = document.createElement('div');
      aLine.className = 'tt-preview-a';
      aLine.style.color = p.a;
      aLine.textContent = 'إجابة الوكيل';
      preview.appendChild(aLine);

      btn.appendChild(preview);

      btn.addEventListener('click', () => {
        set({ preset: id, custom: {} });
      });

      presetsGrid.appendChild(btn);
      presetBtnMap[id] = btn;
    });
    panel.appendChild(presetsGrid);

    // 3. Section «أختار بنفسي»
    const customTitle = document.createElement('div');
    customTitle.className = 'tt-section-title';
    customTitle.textContent = 'أختار بنفسي';
    panel.appendChild(customTitle);

    const customRows = document.createElement('div');
    customRows.className = 'tt-custom-rows';

    const colorConfig = [
      { key: 'bg', label: 'الخلفية' },
      { key: 'fg', label: 'النص العادي' },
      { key: 'q', label: 'لون السؤال' },
      { key: 'qborder', label: 'إطار السؤال' },
      { key: 'a', label: 'لون الإجابة' }
    ];

    const colorInputMap = {};
    let debounceTimer = null;

    const t = resolved();
    colorConfig.forEach(({ key, label }) => {
      const row = document.createElement('div');
      row.className = 'tt-custom-row';

      const lbl = document.createElement('span');
      lbl.className = 'tt-custom-label';
      lbl.textContent = label;
      row.appendChild(lbl);

      const inp = document.createElement('input');
      inp.type = 'color';
      inp.className = 'tt-color-input';
      inp.value = toHexColor(t[key]);

      inp.addEventListener('input', e => {
        const val = e.target.value;
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
          set({ custom: { ...cfg.custom, [key]: val } });
        }, 150);
      });

      row.appendChild(inp);
      customRows.appendChild(row);
      colorInputMap[key] = inp;
    });
    panel.appendChild(customRows);

    // 4. Checkbox «أبقِ ألوان الوكيل الخاصة»
    const keepWrap = document.createElement('label');
    keepWrap.className = 'tt-keep-wrap';

    const keepCb = document.createElement('input');
    keepCb.type = 'checkbox';
    keepCb.className = 'tt-keep-checkbox';
    keepCb.checked = Boolean(cfg.keep);
    keepCb.addEventListener('change', () => {
      set({ keep: keepCb.checked });
    });
    keepWrap.appendChild(keepCb);

    const keepLabelBody = document.createElement('div');
    keepLabelBody.className = 'tt-keep-label';

    const keepTitle = document.createElement('span');
    keepTitle.className = 'tt-keep-title';
    keepTitle.textContent = 'أبقِ ألوان الوكيل الخاصة';
    keepLabelBody.appendChild(keepTitle);

    const keepHint = document.createElement('span');
    keepHint.className = 'tt-keep-hint';
    keepHint.textContent = 'مثل الأحمر للأخطاء والأخضر للنجاح؛ إن أطفأته صار كل الرد بلون الإجابة، وتبقى ألوان التحذير';
    keepLabelBody.appendChild(keepHint);

    keepWrap.appendChild(keepLabelBody);
    panel.appendChild(keepWrap);

    // 5. Button «رجوع إلى ألوان الشكل الجاهز»
    const resetBtn = document.createElement('button');
    resetBtn.type = 'button';
    resetBtn.className = 'tt-reset-btn';
    resetBtn.textContent = 'رجوع إلى ألوان الشكل الجاهز';
    resetBtn.addEventListener('click', () => {
      set({ custom: {} });
    });
    panel.appendChild(resetBtn);

    // داخل نافذة الطرفية: في «طرفية زاجل» يُخفى كل ما خارجها
    (document.getElementById('zajel-term-window') || document.body).appendChild(panel);
    positionPanel(panel, anchorEl);

    // Refresh inputs & presets when config changes
    const renderPanelState = () => {
      const cur = resolved();
      Object.keys(presetBtnMap).forEach(id => {
        if (cfg.preset === id) {
          presetBtnMap[id].classList.add('tt-selected');
        } else {
          presetBtnMap[id].classList.remove('tt-selected');
        }
      });
      colorConfig.forEach(({ key }) => {
        const inp = colorInputMap[key];
        if (inp && document.activeElement !== inp) {
          inp.value = toHexColor(cur[key]);
        }
      });
      keepCb.checked = Boolean(cfg.keep);
    };

    const unsub = onChange(renderPanelState);

    let justOpened = true;
    const onDocClick = e => {
      if (justOpened) return;
      if (panel.contains(e.target)) return;
      if (anchorEl && typeof anchorEl.contains === 'function' && anchorEl.contains(e.target)) return;
      close();
    };

    const onKeyDown = e => {
      if (e.key === 'Escape') {
        close();
      }
    };

    setTimeout(() => {
      justOpened = false;
      document.addEventListener('click', onDocClick, true);
      document.addEventListener('keydown', onKeyDown, true);
    }, 0);

    const close = () => {
      unsub();
      clearTimeout(debounceTimer);
      document.removeEventListener('click', onDocClick, true);
      document.removeEventListener('keydown', onKeyDown, true);
      if (panel.parentNode) {
        panel.parentNode.removeChild(panel);
      }
      if (activePanel && activePanel.panel === panel) {
        activePanel = null;
      }
    };

    activePanel = { panel, close };
  }

  // --- Export ---
  window.ZajelTermTheme = {
    PRESETS,
    get,
    set,
    resolved,
    palette,
    apply,
    fixFg,
    fixBg,
    onChange,
    openPanel
  };
})();
