/* طبقة الصقل: أيقونات خطية موحّدة بدل الرموز التعبيرية، سهولة الوصول، تنبيهات منبثقة،
   حالات فارغة وهياكل تحميل، أشرطة المساحة، شريط المسار القابل للكتابة، واختصارات لوحة المفاتيح.
   تعمل فوق app.js دون تغيير منطقه: تراقب ما يُرسم وتحسّنه. */
(() => {
  /* ---------- ١) طقم الأيقونات الكلاسيكي (خط واحد 1.7، زوايا مستديرة، شبكة 24) ---------- */
  const IC = {
    folder: '<path d="M3 7.5A2.5 2.5 0 0 1 5.5 5h3.6l2 2.2h7.4A2.5 2.5 0 0 1 21 9.7v7.8a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z" fill="currentColor" fill-opacity=".14"/>',
    folderOpen: '<path d="M3 17.5V7.5A2.5 2.5 0 0 1 5.5 5h3.6l2 2.2h6.4A2.5 2.5 0 0 1 20 9.7V11"/><path d="M3.3 18.4 5.6 12a2 2 0 0 1 1.9-1.3h12.7a1.3 1.3 0 0 1 1.2 1.8L19 18.6a2 2 0 0 1-1.9 1.4H5.1a1.9 1.9 0 0 1-1.8-1.6z" fill="currentColor" fill-opacity=".14"/>',
    folders: '<path d="M7 9.2A2.2 2.2 0 0 1 9.2 7h3l1.7 1.8h5.9A2.2 2.2 0 0 1 22 11v6.8A2.2 2.2 0 0 1 19.8 20H9.2A2.2 2.2 0 0 1 7 17.8z" fill="currentColor" fill-opacity=".14"/><path d="M4 15.5V6.2A2.2 2.2 0 0 1 6.2 4h3l1.6 1.7"/>',
    file: '<path d="M14 3H7.5A2.5 2.5 0 0 0 5 5.5v13A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V8z" fill="currentColor" fill-opacity=".08"/><path d="M14 3v5h5"/>',
    fileText: '<path d="M14 3H7.5A2.5 2.5 0 0 0 5 5.5v13A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.5-2.5V8z"/><path d="M14 3v5h5M9 13h6M9 16.5h6"/>',
    image: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5" fill="currentColor" fill-opacity=".08"/><circle cx="9" cy="10" r="1.7"/><path d="m20.5 16-4.6-4.6L7 20"/>',
    film: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="M8 4.5v15M16 4.5v15M3.5 9.5H8M3.5 14.5H8M16 9.5h4.5M16 14.5h4.5"/>',
    music: '<path d="M9 18V6l11-2v12"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    headphones: '<path d="M4 15v-3a8 8 0 0 1 16 0v3"/><rect x="3.5" y="14" width="4" height="6" rx="1.5"/><rect x="16.5" y="14" width="4" height="6" rx="1.5"/>',
    archive: '<rect x="3.5" y="4" width="17" height="4.5" rx="1.2"/><path d="M5 8.5v9A2.5 2.5 0 0 0 7.5 20h9a2.5 2.5 0 0 0 2.5-2.5v-9M10 12h4"/>',
    phone: '<rect x="6.5" y="2.5" width="11" height="19" rx="2.6"/><path d="M10.5 18.5h3"/>',
    watch: '<rect x="6.5" y="6.5" width="11" height="11" rx="3"/><path d="M9 6.5 9.6 3h4.8l.6 3.5M9 17.5l.6 3.5h4.8l.6-3.5M12 10v2.2l1.4 1"/>',
    cloud: '<path d="M7.5 19h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.6 9.5 4.75 4.75 0 0 0 7.5 19z" fill="currentColor" fill-opacity=".12"/>',
    drive: '<rect x="3" y="13" width="18" height="7" rx="2"/><path d="M5.2 13 7.6 5.6A2 2 0 0 1 9.5 4.2h5a2 2 0 0 1 1.9 1.4l2.4 7.4M16.5 16.5h.01M13.5 16.5h.01"/>',
    globe: '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5a13 13 0 0 1 0 17M12 3.5a13 13 0 0 0 0 17"/>',
    monitor: '<rect x="3" y="4" width="18" height="12.5" rx="2"/><path d="M8.5 20.5h7M12 16.5v4"/>',
    home: '<path d="m3.5 11 8.5-7 8.5 7"/><path d="M5.5 9.5V19a1 1 0 0 0 1 1H10v-5.5h4V20h3.5a1 1 0 0 0 1-1V9.5"/>',
    star: '<path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z"/>',
    starFill: '<path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z" fill="currentColor"/>',
    info: '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5M12 7.6h.01"/>',
    alert: '<path d="M10.3 4.3 2.9 17.2A2 2 0 0 0 4.6 20h14.8a2 2 0 0 0 1.7-2.8L13.7 4.3a2 2 0 0 0-3.4 0z"/><path d="M12 9.5v4.2M12 16.8h.01"/>',
    gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 14.6a1.6 1.6 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.6 1.6 0 0 0-2.7 1.1V20.6a2 2 0 1 1-4 0v-.2a1.6 1.6 0 0 0-2.7-1.1l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.6 1.6 0 0 0-1.1-2.7H3.4a2 2 0 1 1 0-4h.2a1.6 1.6 0 0 0 1.1-2.7l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.6 1.6 0 0 0 2.7-1.1V3.4a2 2 0 1 1 4 0v.2a1.6 1.6 0 0 0 2.7 1.1l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.6 1.6 0 0 0 1.1 2.7h.2a2 2 0 1 1 0 4h-.2a1.6 1.6 0 0 0-1.5.4z"/>',
    pencil: '<path d="M4 20h4l10.5-10.5a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>',
    trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
    eject: '<path d="M12 4 4.5 13h15z"/><path d="M5 18h14"/>',
    clipboard: '<rect x="5.5" y="4.5" width="13" height="16" rx="2"/><path d="M9 4.5V3.6c0-.3.3-.6.6-.6h4.8c.3 0 .6.3.6.6v.9M9 10h6M9 14h4"/>',
    scissors: '<circle cx="6" cy="6.5" r="2.5"/><circle cx="6" cy="17.5" r="2.5"/><path d="M8 8 20 18M8 16 20 6"/>',
    paste: '<rect x="5.5" y="4.5" width="13" height="16" rx="2"/><path d="M9 4.5V3.6c0-.3.3-.6.6-.6h4.8c.3 0 .6.3.6.6v.9M12 9v6.5M9.2 12.8 12 15.6l2.8-2.8"/>',
    refresh: '<path d="M20 11a8 8 0 0 0-14.6-4.4L4 8.5M4 13a8 8 0 0 0 14.6 4.4L20 15.5"/><path d="M4 4v4.5h4.5M20 20v-4.5h-4.5"/>',
    download: '<path d="M12 4v11M7.5 10.5 12 15l4.5-4.5M5 20h14"/>',
    upload: '<path d="M12 15V4M7.5 8.5 12 4l4.5 4.5M5 20h14"/>',
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.3-4.3"/>',
    chart: '<path d="M12 3.5a8.5 8.5 0 1 0 8.5 8.5H12z"/><path d="M15 3.8A8.5 8.5 0 0 1 20.2 9H15z"/>',
    lock: '<rect x="5" y="10.5" width="14" height="10" rx="2.2"/><path d="M8.5 10.5V7.5a3.5 3.5 0 0 1 7 0v3"/>',
    sparkles: '<path d="M10 3.5 11.6 8 16 9.5l-4.4 1.6L10 15.5l-1.6-4.4L4 9.5 8.4 8zM17.5 14l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    pause: '<rect x="6.5" y="5" width="3.8" height="14" rx="1.2"/><rect x="13.7" y="5" width="3.8" height="14" rx="1.2"/>',
    play: '<path d="M8 5.5v13a1 1 0 0 0 1.5.86l10.2-6.5a1 1 0 0 0 0-1.72L9.5 4.64A1 1 0 0 0 8 5.5z"/>',
    clock: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    x: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
    checkSquare: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="m8 12 3 3 5-6"/>',
    square: '<rect x="4" y="4" width="16" height="16" rx="3"/>',
    columns2: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="M12 4.5v15"/>',
    grid: '<rect x="4" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.5"/><rect x="4" y="13.5" width="6.5" height="6.5" rx="1.5"/><rect x="13.5" y="13.5" width="6.5" height="6.5" rx="1.5"/>',
    list: '<path d="M9 6.5h11M9 12h11M9 17.5h11M4.5 6.5h.01M4.5 12h.01M4.5 17.5h.01"/>',
    columns3: '<rect x="3.5" y="4.5" width="17" height="15" rx="2.5"/><path d="M9.2 4.5v15M14.8 4.5v15"/>',
    camera: '<path d="M4 8.5A2.5 2.5 0 0 1 6.5 6h1.8l1.5-2h4.4l1.5 2h1.8A2.5 2.5 0 0 1 20 8.5v8a2.5 2.5 0 0 1-2.5 2.5h-11A2.5 2.5 0 0 1 4 16.5z"/><circle cx="12" cy="12.5" r="3.3"/>',
    mic: '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
    book: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20v3H6.5"/>',
    box: '<path d="m12 3 8 4.5v9L12 21l-8-4.5v-9z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9"/>',
    hourglass: '<path d="M7 3.5h10M7 20.5h10M8 3.5c0 4 8 4.5 8 8.5s-8 4.5-8 8.5M16 3.5c0 4-8 4.5-8 8.5s8 4.5 8 8.5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    app: '<rect x="4" y="4" width="16" height="16" rx="4.5"/><path d="M9 12h6M12 9v6"/>',
    code: '<path d="m8.5 8-4 4 4 4M15.5 8l4 4-4 4M13.5 5.5l-3 13"/>',
    sheet: '<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="M4 9.5h16M4 14.5h16M10 4v16"/>',
    slides: '<rect x="3.5" y="4.5" width="17" height="12" rx="2"/><path d="M12 16.5V20M8.5 20h7M7.5 12.5l3-3 2 2 4-4"/>',
    tablet: '<rect x="4.5" y="2.5" width="15" height="19" rx="2.4"/><path d="M11 18.5h2"/>',
    keyboard: '<rect x="2.5" y="6" width="19" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7.5 14h9"/>'
  };
  const svg = (n, s = 16) => `<svg class="i i-${n}" width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${IC[n] || ''}</svg>`;
  window.uiIcon = svg;
  try { Object.assign(ICONS, IC); } catch (_) {}

  // الرمز التعبيري ← الأيقونة الموحّدة (واللون الكلاسيكي لكل نوع)
  const MAP = [
    ['🗂️', 'folders'], ['🗂', 'folders'], ['📁', 'folder'], ['📂', 'folderOpen'], ['📄', 'file'], ['📝', 'fileText'], ['📑', 'fileText'],
    ['🖼️', 'image'], ['🖼', 'image'], ['🎬', 'film'], ['🎞️', 'film'], ['🎵', 'music'], ['🎶', 'music'], ['🎧', 'headphones'], ['📦', 'archive'],
    ['📱', 'phone'], ['⌚', 'watch'], ['☁️', 'cloud'], ['☁', 'cloud'], ['💾', 'drive'], ['🌐', 'globe'], ['🖥️', 'monitor'], ['🖥', 'monitor'], ['💻', 'monitor'],
    ['🏠', 'home'], ['⭐', 'starFill'], ['★', 'starFill'], ['☆', 'star'], ['ⓘ', 'info'], ['ℹ️', 'info'], ['⚠️', 'alert'], ['⚠', 'alert'],
    ['⚙️', 'gear'], ['⚙', 'gear'], ['✏️', 'pencil'], ['✏', 'pencil'], ['🗑️', 'trash'], ['🗑', 'trash'], ['⏏️', 'eject'], ['⏏', 'eject'],
    ['📋', 'clipboard'], ['✂️', 'scissors'], ['✂', 'scissors'], ['📥', 'paste'], ['🔄', 'refresh'], ['⬇️', 'download'], ['⬇', 'download'], ['⬆️', 'upload'], ['⬆', 'upload'],
    ['⌕', 'search'], ['🔍', 'search'], ['🔎', 'search'], ['📊', 'chart'], ['🔒', 'lock'], ['🧹', 'sparkles'], ['⏹', 'stop'], ['⏸', 'pause'], ['▶', 'play'], ['⏳', 'hourglass'],
    ['☑', 'checkSquare'], ['☐', 'square'], ['⫿', 'columns2'], ['▦', 'grid'], ['☰', 'list'], ['▥', 'columns3'], ['📸', 'camera'], ['📷', 'camera'],
    ['🎙️', 'mic'], ['🎙', 'mic'], ['📚', 'book'], ['📖', 'book'], ['🧩', 'box'], ['🍎', 'cloud'], ['🟢', 'cloud'], ['🔵', 'cloud'], ['🟦', 'cloud'], ['📲', 'phone'], ['📟', 'tablet'], ['⌨️', 'keyboard']
  ];
  const BRAND = { '🟢': 'gdrive', '🔵': 'onedrive', '🟦': 'dropbox', '🍎': 'icloud' };
  const RE = new RegExp('(' + MAP.map(([e]) => e.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|') + ')️?', 'u');
  const LOOK = Object.fromEntries(MAP);
  const SKIP = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION', 'TITLE', 'svg', 'SVG']);
  const isName = n => n.parentElement?.closest('.nm b, .gc b, .ci b, .kv span:last-child, .det h3, #summary');
  function swapText(node) {
    const t = node.nodeValue; if (!t || !RE.test(t)) return;
    const pe = node.parentElement; if (!pe || SKIP.has(pe.tagName) || pe.closest('svg') || isName(node)) return;
    const frag = document.createDocumentFragment(); let rest = t, m;
    while ((m = rest.match(RE))) {
      if (m.index) frag.append(rest.slice(0, m.index));
      const sp = document.createElement('span'); sp.className = 'ii' + (BRAND[m[1]] ? ' b-' + BRAND[m[1]] : ''); sp.innerHTML = svg(LOOK[m[1]], 16); frag.append(sp);
      rest = rest.slice(m.index + m[0].length);
    }
    if (rest) frag.append(rest);
    node.replaceWith(frag);
  }
  function sweep(root) {
    if (root.nodeType === 3) return swapText(root);
    if (root.nodeType !== 1 || SKIP.has(root.tagName)) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); const list = []; let n;
    while ((n = w.nextNode())) if (RE.test(n.nodeValue)) list.push(n);
    list.forEach(swapText);
  }

  /* ---------- ٢) سهولة الوصول ---------- */
  const CLICKABLE = '.chip,.tab,.src,a.q,.ci,.gc,.mbtn,[data-v]';
  function a11y(root) {
    if (root.nodeType !== 1) return;
    const els = root.matches?.(CLICKABLE + ',button') ? [root, ...root.querySelectorAll(CLICKABLE + ',button')] : root.querySelectorAll(CLICKABLE + ',button');
    els.forEach(e => {
      if (!e.matches('button')) { if (!e.hasAttribute('role')) e.setAttribute('role', 'button'); if (!e.hasAttribute('tabindex')) e.tabIndex = 0; }
      if (!e.hasAttribute('aria-label')) { const l = (e.title || e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 90); if (l) e.setAttribute('aria-label', l); }
    });
    (root.tagName === 'IMG' ? [root] : []).concat([...(root.querySelectorAll?.('img:not([alt])') || [])]).forEach(i => { const n = i.closest('[data-path]'); if (i.hasAttribute('alt')) return; i.alt = n ? (n.dataset.path.split('/').pop() || '') : ''; });
  }
  document.addEventListener('keydown', ev => {
    const t = ev.target; if ((ev.key === 'Enter' || ev.key === ' ') && t?.getAttribute?.('role') === 'button' && !t.matches('button,[data-path]') && !t.closest('[data-path]')) { ev.preventDefault(); ev.stopPropagation(); t.click(); }
  }, true);
  document.addEventListener('mousedown', () => document.body.classList.remove('kbd'), true);
  document.addEventListener('keydown', ev => { if (ev.key === 'Tab') document.body.classList.add('kbd'); }, true);

  /* ---------- ٣) تنبيهات منبثقة بدل سطر السجل وحده ---------- */
  const toasts = document.createElement('div'); toasts.className = 'toasts'; toasts.setAttribute('role', 'status'); toasts.setAttribute('aria-live', 'polite'); document.body.append(toasts);
  let lastToast = '', lastAt = 0;
  function toast(msg) {
    msg = (msg || '').trim(); if (!msg || /^جار[ٍِ]?\s/.test(msg) || (msg === lastToast && Date.now() - lastAt < 2500)) return; lastToast = msg; lastAt = Date.now();
    const bad = /تعذّر|تعذر|فشل|خطأ|غير صالح|لا يمكن|مرفوض|Errno|not permitted/i.test(msg), good = /^✓|أُضيف|اكتمل|تم |تمت|أُخرج|نجح/.test(msg);
    const t = document.createElement('div'); t.className = 'toast' + (bad ? ' bad' : good ? ' good' : '');
    t.innerHTML = svg(bad ? 'alert' : good ? 'check' : 'info', 16); const s = document.createElement('span'); s.textContent = msg.replace(/^[✓⏏]\s*/, ''); t.append(s);
    t.onclick = () => t.remove(); toasts.append(t); while (toasts.children.length > 3) toasts.firstChild.remove();
    setTimeout(() => { t.classList.add('out'); setTimeout(() => t.remove(), 300); }, bad ? 6500 : 3600);
  }
  window.uiToast = toast;
  const logEl = document.getElementById('log');
  if (logEl) new MutationObserver(() => toast(logEl.textContent)).observe(logEl, { childList: true, characterData: true, subtree: true });

  /* ---------- ٤) هياكل التحميل والحالات الفارغة ---------- */
  const of = window.fetch.bind(window);
  window.fetch = function (url, opt) {
    const u = String(url); const slow = /\/api\/(cloud\/browse|browse)\b/.test(u);
    let pane = null, tm = null;
    if (slow) { try { pane = P?.root; } catch (_) {} pane = pane || document.querySelector('.pane'); tm = setTimeout(() => pane?.classList.add('loading'), 220); }
    const done = () => { clearTimeout(tm); pane?.classList.remove('loading'); };
    return of(url, opt).then(r => { done(); return r; }, e => { done(); throw e; });
  };
  function emptyStates() {
    document.querySelectorAll('.pane').forEach(p => {
      const st = p.querySelector('.pstate.on'); let e = p.querySelector('.emptyhint');
      const rows = p.querySelectorAll('[data-path]').length, searching = p.querySelector('.pq')?.value;
      const show = !st && !rows && !p.classList.contains('loading');
      if (show && !e) { e = document.createElement('div'); e.className = 'emptyhint'; e.innerHTML = svg(searching ? 'search' : 'folderOpen', 44) + `<b>${searching ? 'لا نتائج' : 'المجلد فارغ'}</b><span>${searching ? 'جرّب كلمة أقصر أو ابحث في كل المصدر.' : 'اسحب ملفات إلى هنا، أو أنشئ مجلدًا جديدًا (⇧⌘N).'}</span>`; p.querySelector('.pbody')?.append(e); }
      else if (!show && e) e.remove();
    });
  }

  /* ---------- ٥) أشرطة المساحة تحت الأقراص والحسابات ---------- */
  const SPACE = {}; let spaceAt = 0;
  async function refreshSpace() {
    let srcs = []; try { srcs = sources || []; } catch (_) {}
    if (!srcs.length || Date.now() - spaceAt < 45000) return; spaceAt = Date.now();
    for (const s of srcs) {
      try {
        if (s.type === 'adb' && s.online && s.serial) { const r = await (await of('/api/storage?serial=' + encodeURIComponent(s.serial))).json(); if (r.total) SPACE[s.id] = { total: r.total, used: r.total - r.free }; }
        else if (s.id === 'home') { const r = await (await of('/api/space?root=' + encodeURIComponent(s.id))).json(); if (r.total) SPACE[s.id] = r; }
      } catch (_) {}
    }
    spaceBars();
  }
  function spaceBars() {
    let vols = []; try { vols = phone?.volumes || []; } catch (_) {}
    let roots = []; try { roots = cloudRoots || []; } catch (_) {}
    refreshSpace();
    document.querySelectorAll('.side .src[data-sid]').forEach(row => {
      const id = row.dataset.sid; let used = null, total = null;
      if (id.startsWith('vol:')) { const v = vols.find(x => 'vol:' + x.name === id); if (v?.total) { total = v.total; used = v.total - v.free; } }
      else if (id.startsWith('rc:')) { const r = roots.find(x => x.id === id); if (r?.total) { total = r.total; used = r.used; } }
      else if (id.startsWith('GoogleDrive-')) { const em = id.slice(12), r = roots.find(x => x.email && x.email.toLowerCase() === em.toLowerCase() && x.total); if (r) { total = r.total; used = r.used; } }
      else if (id.startsWith('ios:')) { let s = null; try { s = sources.find(x => x.id === id); } catch (_) {} if (s?.total) { total = s.total; used = s.total - s.free; } }
      else if (SPACE[id] && (id === 'home' || id === 'phone' || id === 'watch')) { total = SPACE[id].total; used = SPACE[id].used; }
      const tx = row.querySelector('.tx'); if (!tx) return; let b = tx.querySelector('.space');
      if (total == null || used == null) { b?.remove(); return; }
      const pct = Math.min(100, used / total * 100);
      if (!b) { b = document.createElement('div'); b.className = 'space'; b.innerHTML = '<i></i>'; tx.append(b); }
      b.firstChild.style.width = pct.toFixed(1) + '%'; b.classList.toggle('full', pct > 90); b.classList.toggle('warn', pct > 75 && pct <= 90);
      b.title = `مستخدم ${fsize(used)} من ${fsize(total)} — متاح ${fsize(total - used)}`;
    });
  }

  /* ---------- ٦) شريط المسار القابل للكتابة (⌘L / ⇧⌘G / نقر مزدوج) ---------- */
  function goToPath() {
    const p = P;
    if (!p?.src) return;
    promptModal('الانتقال إلى مسار', `داخل «${p.src.label}». اكتب المسار أو الصقه (مثل Documents/رسالة).`, p.cur || '', 'انتقال', v => {
      let path = v.trim(); if (p.src.type === 'local' && p.src.root === 'home') path = path.replace(/^~\/?/, '').replace(new RegExp('^' + '/Users/[^/]+/?'), '');
      p.go(p.src.id, path.replace(/\/+$/, ''));
    });
  }
  document.addEventListener('dblclick', ev => { if (ev.target.closest('.crumbs') && !ev.target.closest('span')) goToPath(); });

  /* ---------- ٧) اختصارات لوحة المفاتيح ولوحتها ---------- */
  const KEYS = [
    ['التنقل', [['↑ ↓', 'التحرك بين العناصر'], ['Enter', 'فتح المجلد'], ['⌫ / ⌘↑', 'المجلد الأب'], ['⌥→ / ⌥←', 'رجوع / أمام'], ['⌘L', 'الانتقال إلى مسار'], ['Tab', 'التبديل بين اللوحتين']]],
    ['التحديد', [['⌘A', 'تحديد الكل'], ['⇧↑ ⇧↓', 'تحديد متصل'], ['⇧ Space', 'تحديد عنصر'], ['Esc', 'إلغاء التحديد']]],
    ['الملفات', [['Space', 'معاينة سريعة'], ['F2', 'إعادة تسمية'], ['F5', 'نسخ إلى اللوحة الأخرى'], ['F6', 'نقل إلى اللوحة الأخرى'], ['F7 / ⇧⌘N', 'مجلد جديد'], ['F8 / Delete', 'حذف'], ['⌘C ⌘X ⌘V', 'نسخ، قص، لصق']]],
    ['النوافذ', [['⌘T', 'تبويب جديد'], ['⌘W', 'إغلاق التبويب'], ['⌘F', 'بحث'], ['⌘/', 'هذه اللوحة']]]
  ];
  function showKeys() {
    openModal(m => {
      m.classList.add('keysheet'); const h = document.createElement('h3'); h.innerHTML = svg('keyboard', 18) + ' اختصارات لوحة المفاتيح'; m.append(h);
      const g = document.createElement('div'); g.className = 'keysgrid';
      KEYS.forEach(([t, rows]) => { const c = document.createElement('div'); c.innerHTML = `<h4>${t}</h4>` + rows.map(([k, d]) => `<div class="kr"><span>${d}</span><kbd>${k}</kbd></div>`).join(''); g.append(c); });
      const acts = document.createElement('div'); acts.className = 'acts'; const ok = document.createElement('button'); ok.className = 'btn pri'; ok.textContent = 'تم'; ok.onclick = closeModal; acts.append(ok);
      m.append(g, acts);
    });
    const md = document.getElementById('modal'); const obs = new MutationObserver(() => { if (!document.getElementById('ov').classList.contains('on')) { md.classList.remove('keysheet'); obs.disconnect(); } }); obs.observe(document.getElementById('ov'), { attributes: true });
  }
  const otherSide = () => { try { if (ws.panes.length !== 2) return null; const [a, b] = ws.panes, right = a.root.getBoundingClientRect().left > b.root.getBoundingClientRect().left ? a : b; return P === right ? 'left' : 'right'; } catch (_) { return null; } };
  document.addEventListener('keydown', ev => {
    if (ev.target.closest?.('input,select,textarea') || document.getElementById('ov').classList.contains('on')) return;
    const mod = ev.metaKey || ev.ctrlKey;
    if (mod && (ev.key === '/' || ev.key === '؟')) { ev.preventDefault(); showKeys(); return; }
    if ((mod && ev.key.toLowerCase() === 'l') || (mod && ev.shiftKey && ev.key.toLowerCase() === 'g')) { ev.preventDefault(); ev.stopPropagation(); goToPath(); return; }
    if (ev.key === 'F5' || ev.key === 'F6') { const s = otherSide(); ev.preventDefault(); if (s) xferTo(s, ev.key === 'F5' ? 'copy' : 'move'); else note('افتح لوحتين (⫿) لاستعمال F5 و F6.'); return; }
    if (ev.key === 'F7') { ev.preventDefault(); try { newFolder(); } catch (_) {} return; }
    if (ev.key === 'F8') { ev.preventDefault(); document.getElementById('delfiles')?.click(); }
  }, true);

  /* ---------- ٨) شريط علوي واحد مدمج: «الحفظ إلى» ينتقل إلى قائمة الخيارات ---------- */
  function compactTop() {
    const dest = document.getElementById('dest'), lbl = document.querySelector('.top .dlbl'), pop = document.querySelector('#optbtn + .menupop');
    if (dest && pop && !pop.contains(dest)) { const l = document.createElement('label'); l.className = 'destrow'; l.append(document.createTextNode('الحفظ إلى ')); l.append(dest); pop.prepend(l); lbl?.remove(); }
    const ib = document.getElementById('installbtn'), sm = document.querySelector('#secMenu .menupop');
    if (ib && sm && !sm.contains(ib)) { ib.classList.add('tab', 'instrow'); ib.classList.remove('btn'); sm.append(ib); }
    const kb = document.querySelector('.top .kbtn');
    if (!kb) { const b = document.createElement('button'); b.className = 'btn nav kbtn'; b.title = 'اختصارات لوحة المفاتيح (⌘/)'; b.innerHTML = svg('keyboard', 17); b.onclick = showKeys; document.querySelector('.top')?.append(b); }
  }


  /* ---------- ٩) زر واحد للتبديل بين قائمة وشبكة وأعمدة، وشريط مسار كامل، وتمييز المخفيات ---------- */
  const VIEWS = [['.pvlist', 'list', 'قائمة'], ['.pvgrid', 'grid', 'شبكة'], ['.pvcols', 'columns3', 'أعمدة']];
  function viewCycle(pane) {
    const tool = pane.querySelector('.phead'); if (!tool || tool.querySelector('.pvcycle')) return;
    const b = document.createElement('button'); b.className = 'btn nav pvcycle';
    const paint = () => { const i = Math.max(0, VIEWS.findIndex(([c]) => pane.querySelector(c)?.classList.contains('on'))), nx = VIEWS[(i + 1) % 3];
      b.innerHTML = svg(VIEWS[i][1], 17); b.title = `العرض: ${VIEWS[i][2]} — انقر للتبديل إلى ${nx[2]}`; b.setAttribute('aria-label', b.title); };
    b.onclick = ev => { ev.stopPropagation(); const i = Math.max(0, VIEWS.findIndex(([c]) => pane.querySelector(c)?.classList.contains('on'))); pane.querySelector(VIEWS[(i + 1) % 3][0])?.click(); setTimeout(paint, 30); };
    VIEWS.forEach(([c]) => pane.querySelector(c)?.addEventListener('click', () => setTimeout(paint, 30)));
    const anchor = tool.querySelector('.pcrumbs'); anchor ? anchor.before(b) : tool.prepend(b); paint(); // بجوار أزرار التنقل: يبقى ظاهرًا دائمًا
  }
  function pathBars() {
    document.querySelectorAll('.pane').forEach(pane => {
      viewCycle(pane);
      const cr = pane.querySelector('.pcrumbs'); if (cr && cr.dataset.sig !== cr.textContent) { cr.dataset.sig = cr.textContent; requestAnimationFrame(() => { cr.scrollLeft = getComputedStyle(cr).direction === 'rtl' ? -cr.scrollWidth : cr.scrollWidth; }); }
      pane.querySelectorAll('[data-path]').forEach(r => { const n = r.dataset.path.replace(/\/+$/, '').split(/[\/:]/).pop(); r.classList.toggle('hid', n.startsWith('.')); });
    });
  }


  /* ---------- ١٠) معاينة كل الصيغ بلا حد للحجم: صوت، فيديو، PDF، نصوص ---------- */
  const MEDIA = { aud: /\.(mp3|m4a|aac|wav|ogg|oga|opus|flac|amr|3ga|aiff?|caf)$/i, vid: /\.(mp4|m4v|mov|webm|mkv|avi|3gp|mpe?g)$/i, pdf: /\.pdf$/i,
    txt: /\.(txt|text|md|markdown|log|csv|tsv|json|xml|py|js|ts|sh|ini|conf|cfg|yaml|yml|toml|env|srt|vtt|ass|ssa|sub|lrc|m3u8?|pls|cue|nfo|opml|tex|bib|ris|sql|java|kt|swift|c|h|cpp|rb|go|rs|php|bat|ps1|plist|gitignore|html?|css)$/i };
  // يقرأ النص بترميزه الصحيح: UTF-8، أو UTF-16 بعلامته، أو العربي القديم (Windows-1256) لملفات البرامج القديمة
  const decodeText = buf => {
    const b = new Uint8Array(buf);
    if (b[0] === 0xFF && b[1] === 0xFE) return new TextDecoder('utf-16le').decode(b);
    if (b[0] === 0xFE && b[1] === 0xFF) return new TextDecoder('utf-16be').decode(b);
    for (const cut of [0, 1, 2, 3]) { try { return new TextDecoder('utf-8', { fatal: true }).decode(b.subarray(0, b.length - cut)); } catch (_) {} }
    try { return new TextDecoder('windows-1256').decode(b); } catch (_) { return new TextDecoder('utf-8').decode(b); }
  };
  const streamUrl = (pane, e) => { const s = e?._src || pane?.src; if (!s || !e || e.is_dir) return null;
    if (s.type === 'ios') return `/api/stream?udid=${encodeURIComponent(s.udid)}&path=${encodeURIComponent(e.path)}&v=${e.mod || ''}`;
    return s.type === 'adb' ? `/api/stream?serial=${encodeURIComponent(s.serial || '')}&path=${encodeURIComponent(e.path)}&v=${e.mod || ''}` : `/api/stream?root=${encodeURIComponent(s.root)}&path=${encodeURIComponent(e.path)}`; };
  const mediaKind = n => Object.keys(MEDIA).find(k => MEDIA[k].test(n || ''));
  const box = () => document.getElementById('lbimg');
  function clearMedia() { box()?.querySelectorAll('.lbmedia').forEach(x => { x.querySelectorAll('audio,video').forEach(m => { m.pause(); m.removeAttribute('src'); m.load(); }); x.remove(); }); }
  if (typeof showLb === 'function') {
    const orig = showLb;
    showLb = function () {
      clearMedia(); const it = lb.items[lb.i], e = it?.entry, k = e && mediaKind(e.name), url = k && streamUrl(lb.pane, e);
      if (!url) { document.getElementById('lbpic').style.display = ''; return orig.apply(this, arguments); }
      const img = document.getElementById('lbpic'); img.removeAttribute('src'); img.style.display = 'none';
      const spin = document.getElementById('lbspin'); spin.style.display = 'none';
      document.getElementById('lbcap').textContent = `${it.title}${it.meta ? '  ·  ' + it.meta : ''}  ·  ${lb.i + 1} / ${lb.items.length}`;
      const w = document.createElement('div'); w.className = 'lbmedia lbm-' + k;
      if (k === 'aud') { w.innerHTML = svg('music', 64) + `<b></b>`; w.querySelector('b').textContent = e.name; const a = document.createElement('audio'); a.controls = true; a.autoplay = true; a.preload = 'auto'; a.src = url; w.append(a); }
      else if (k === 'vid') { const v = document.createElement('video'); v.controls = true; v.autoplay = true; v.playsInline = true; v.preload = 'metadata'; v.src = url;
        v.onerror = () => { w.innerHTML = svg('film', 56) + '<b>لا يستطيع البرنامج تشغيل هذه الصيغة.</b>'; const o = document.createElement('button'); o.className = 'btn'; o.textContent = 'فتح في QuickTime'; o.onclick = () => window.open(url); w.append(o); }; w.append(v); }
      else if (k === 'pdf') { const f = document.createElement('iframe'); f.src = url; w.append(f); }
      else { const pre = document.createElement('pre'); pre.dir = 'auto'; pre.className = 'lbtext'; pre.textContent = 'جارٍ التحميل…'; w.append(pre);
        fetch(url, { headers: { Range: 'bytes=0-1048575' } }).then(r => r.arrayBuffer()).then(buf => { let t = decodeText(buf);
          if (/\.m3u8?$/i.test(e.name)) t = t.split(/\r?\n/).filter(l => l.trim() && !/^#EXTM3U/i.test(l)).map(l => l.startsWith('#EXTINF') ? '🎵 ' + l.replace(/^#EXTINF:[^,]*,/, '') : '     ' + l).join('\n');
          pre.textContent = t + (e.size > 1048576 ? '\n\n… (أول ميغابايت فقط)' : ''); }).catch(() => { pre.textContent = 'تعذّرت القراءة.'; }); }
      box().append(w);
      [lb.i + 1, lb.i - 1].forEach(j => { const n = lb.items[j]; if (n?.url && !mediaKind(n.entry?.name)) { const q = new Image(); q.src = n.url; } });
    };
    if (typeof closeLightbox === 'function') { const oc = closeLightbox; closeLightbox = function () { clearMedia(); document.getElementById('lbpic').style.display = ''; return oc.apply(this, arguments); }; }
  }


  /* ---------- ١١) نافذة البحث الذكي: ترتيب احترافي ---------- */
  const TYPE_IC = { 'Word': 'fileText', 'PDF': 'file', 'Excel': 'sheet', 'PowerPoint': 'slides', 'نصوص': 'fileText', 'صور': 'image', 'فيديو': 'film', 'صوت': 'music', 'أرشيف': 'archive', 'تطبيقات': 'app', 'برمجة': 'code', 'كتب': 'book' };
  function polishSearch() {
    document.querySelectorAll('.psearch').forEach(pop => {
      if (pop.querySelector('.slab')) return; const g = pop.querySelector('.sgroups'), sc = pop.querySelector('.sscope'), btns = pop.querySelector('.sbtns'), inp = pop.querySelector('.pcustom'); if (!g || !sc || !btns) return;
      g.querySelectorAll('.chip').forEach(c => { const n = c.textContent.trim(); if (!c.querySelector('svg')) c.insertAdjacentHTML('afterbegin', svg(TYPE_IC[n] || 'file', 15)); });
      const lab = t => { const d = document.createElement('div'); d.className = 'slab'; d.textContent = t; return d; };
      pop.querySelector('h4')?.after(sc);
      sc.after(lab('النوع')); pop.querySelector('.slab').after(g);
      g.after(lab('لاحقات أخرى')); pop.querySelectorAll('.slab')[1].after(inp);
      if (inp) inp.placeholder = 'epub, log, …';
      const [clr, go] = btns.children; if (clr) { clr.className = 'btn link'; clr.textContent = 'مسح'; }
      // نطاق ثالث: عدة مصادر (الهاتف، السحابات، الأقراص…)
      const r0 = sc.querySelector('input'); const l3 = document.createElement('label'), r3 = document.createElement('input'); r3.type = 'radio'; r3.name = r0?.name || 'sc'; r3.value = 'multi'; l3.append(r3, document.createTextNode('عدة مصادر')); sc.append(l3);
      const ms = document.createElement('div'); ms.className = 'msrc sgroups'; ms.hidden = true; sc.after(ms);
      const fill = () => { ms.replaceChildren(); let srcs = []; try { srcs = sources.filter(s => s.online); } catch (_) {}
        srcs.forEach(s => { const c = document.createElement('span'); c.className = 'chip'; c.dataset.sid = s.id; c.textContent = s.label; c.title = s.email || s.label; c.onclick = () => c.classList.toggle('on'); ms.append(c); }); };
      sc.addEventListener('change', () => { ms.hidden = !r3.checked; if (r3.checked) fill(); });
    });
  }


  /* ---------- ١٢) الشريط الجانبي ظاهر في كل الأقسام ---------- */
  function globalSidebar() {
    const side = document.getElementById('sources'); if (!side || side.parentElement?.classList.contains('mainrow')) return;
    const row = document.createElement('div'); row.className = 'mainrow';
    const views = [...document.querySelectorAll('body > .view')]; if (!views.length) return;
    views[0].before(row); row.append(side, ...views);
    // اختيار مصدر من قسم آخر يعيدك إلى «الملفات»
    side.addEventListener('click', ev => { if (ev.target.closest('.src,.q:not(.conn)') && document.body.dataset.sec !== 'files' && !ev.target.closest('a.q')?.textContent.includes('التطبيقات') && !ev.target.closest('a.q')?.textContent.includes('ترحيل'))
      document.querySelector('[data-v="files"]')?.click(); }, true);
  }


  /* ---------- ١٣) أحجام المجلدات في عمود «الحجم» (تُحسب تدريجيًا وتُحفظ) ---------- */
  const DSZ = {}, DST = {}, DERR = {}, dq = []; let dsortT = 0, dBusy = 0, dForce = new Set();
  const dtxt = k => (DST[k] === 'done' ? '' : '≈ ') + fsize(DSZ[k]);   // ≈ = رقم مؤقت يُحدَّث أثناء الحساب
  const dTag = k => String(DSZ[k]) + DST[k];
  function folderSizes() {
    let panes = []; try { panes = allPanes(); } catch (_) {}
    panes.filter(p => p.root?.offsetParent).forEach(p => {
      const s = p.src; if (!s?.online || p.search || s.type === 'ios' || s.type === 'kindle' || (s.type === 'local' && String(s.root).startsWith('rc:') && !dForce.has(p))) return;
      // عرض الأعمدة: الحجم بجوار سهم المجلد
      const colEnts = (p.colData || []).flatMap(c => c.entries || []);
      p.root.querySelectorAll('.ci[data-path]').forEach(row => {
        const e = colEnts.find(x => x.path === row.dataset.path); if (!e?.is_dir) return; const k = s.id + '|' + e.path;
        if (DSZ[k] != null) { let z = row.querySelector('.csz'); if (!z) { z = document.createElement('span'); z.className = 'num csz'; row.querySelector('.ar')?.before(z); } e.dsize = DSZ[k]; const t = dtxt(k); if (z.textContent !== t) z.textContent = t; return; }
        if (!(DERR[k] > Date.now()) && !dq.some(x => x.k === k)) (p === P ? dq.unshift.bind(dq) : dq.push.bind(dq))({ k, s, path: e.path });
      });
      const ths = [...p.root.querySelectorAll('.pthead th')], ci = ths.findIndex(t => t.textContent.trim().startsWith('الحجم'));
      // الشبكة: «مجلد · الحجم» تحت اسم البطاقة
      p.root.querySelectorAll('.pgrid .gc[data-path]').forEach(c => {
        const e = p.entries.find(x => x.path === c.dataset.path); if (!e?.is_dir) return; const k = s.id + '|' + e.path, sm = c.querySelector('small'); if (!sm) return;
        if (DSZ[k] != null) { e.dsize = DSZ[k]; const t = 'مجلد · ' + dtxt(k); if (sm.textContent !== t) sm.textContent = t; return; }
        if (!(DERR[k] > Date.now()) && !dq.some(x => x.k === k)) (p === P ? dq.unshift.bind(dq) : dq.push.bind(dq))({ k, s, path: e.path });
      });
      if (ci < 0) return;
      p.root.querySelectorAll('.prows tr[data-path]').forEach(tr => {
        const e = p.entries.find(x => x.path === tr.dataset.path); if (!e?.is_dir) return;
        const k = s.id + '|' + e.path, td = tr.children[ci]; if (!td) return;
        if (DSZ[k] != null) { if (td.dataset.dsz !== dTag(k)) { td.textContent = dtxt(k); td.dataset.dsz = dTag(k); td.classList.add('dszv'); } e.dsize = DSZ[k]; return; }
        if (!(DERR[k] > Date.now()) && !dq.some(x => x.k === k)) (p === P ? dq.unshift.bind(dq) : dq.push.bind(dq))({ k, s, path: e.path });
      });
    });
    const vis = new Set(); panes.filter(p => p.root?.offsetParent).forEach(p => p.root.querySelectorAll('.prows tr[data-path], .pgrid .gc[data-path], .ci[data-path]').forEach(tr => vis.add(p.src?.id + '|' + tr.dataset.path)));
    for (let i = dq.length - 1; i >= 0; i--) if (!vis.has(dq[i].k)) dq.splice(i, 1);
    pump();
  }
  function pump() {
    while (dBusy < 4 && dq.length) {
      const j = dq.shift(); dBusy++;
      const q = j.s.type === 'adb' ? `serial=${encodeURIComponent(j.s.serial || '')}` : `root=${encodeURIComponent(j.s.root)}`;
      const fresh = dForce.has(j.k) ? '&fresh=1' : ''; dForce.delete(j.k);
      of(`/api/dirsize?${q}&path=${encodeURIComponent(j.path)}${fresh}`).then(r => r.json()).then(r => {
        if (r && r.size != null) { DSZ[j.k] = r.size; DST[j.k] = r.done ? 'done' : 'part'; }
        else if (r && r.done) { DERR[j.k] = Date.now() + 30000; if (DSZ[j.k] == null) DSZ[j.k] = null; }
        if (r && !r.done) setTimeout(() => { if (DST[j.k] === 'part') { DST[j.k] = 'poll'; dq.push(j); folderSizes(); } }, 2500);
      }).catch(() => { DERR[j.k] = Date.now() + 30000; })
        .finally(() => { dBusy--; folderSizes(); if (!dq.length && !dBusy) clearTimeout(dsortT), dsortT = setTimeout(() => { try { allPanes().filter(p => p.skey === 'size' && p.root?.offsetParent && !p.search).forEach(p => p.rerender()); } catch (_) {} }, 1200); });
    }
  }
  /* زر 📏: يعيد حساب كل المجلدات الظاهرة من جديد (ويشمل الحسابات السحابية) */
  window.recalcFolderSizes = p => {
    dForce.add(p); const s = p.src; if (!s) return;
    const ents = p.viewMode === 'cols' ? (p.colData || []).flatMap(c => c.entries || []) : (p.entries || []);
    ents.filter(e => e.is_dir).forEach(e => { const k = s.id + '|' + e.path; dForce.add(k); delete DERR[k]; DST[k] = 'poll'; if (!dq.some(x => x.k === k)) dq.push({ k, s, path: e.path }); });
    pump(); folderSizes();
  };
  /* ---------- المراقِب العام: يُطبّق كل ما سبق على ما يُرسم ---------- */
  let queued = new Set(), raf = 0;
  const flush = () => { raf = 0; const q = [...queued]; queued.clear(); q.forEach(n => { if (n.isConnected || n.nodeType === 3) { sweep(n); if (n.nodeType === 1) a11y(n); } }); emptyStates(); spaceBars(); pathBars(); polishSearch(); folderSizes(); };
  new MutationObserver(ms => { ms.forEach(m => { m.addedNodes.forEach(n => queued.add(n)); if (m.type === 'characterData') queued.add(m.target); }); if (!raf) raf = requestAnimationFrame(flush); })
    .observe(document.body, { childList: true, subtree: true, characterData: true });
  // داخل البرنامج الأصلي: لا حاجة لزر «تثبيت» تطبيق الويب
  if (/PhoneBackupDesktop/.test(navigator.userAgent)) { document.documentElement.classList.add('desktop'); document.getElementById('installbtn')?.remove(); }
  globalSidebar(); compactTop(); sweep(document.body); a11y(document.body); emptyStates(); spaceBars(); pathBars(); polishSearch();
  setInterval(spaceBars, 15000); window.PBspace = spaceBars;
})();
