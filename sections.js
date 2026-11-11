// قسما «الخوادم» و«الجوال» في القائمة العليا. يعتمدان على أدوات app.js (el, btn, api, fsize, note, promptModal).
(() => {
  const $$ = s => document.querySelector(s);
  const ago = s => s || '—';

  /* ============ الخوادم ============ */
  let svTimer = null, svBusy = false, svFilter = '';
  const svOpen = new Set();

  function chip(txt, cls) { return el('span', txt, 'sy-badge ' + (cls || 'cat')); }

  async function loadServers() {
    if (svBusy) return; svBusy = true;
    const body = $$('#sv-body');
    let d;
    try { d = await api('/api/assistant/servers'); } catch (e) { body.replaceChildren(el('div', e.message, 'empty err')); svBusy = false; return; }
    svBusy = false;
    $$('#sv-upd').textContent = 'آخر تحديث: ' + new Date().toLocaleTimeString('en-GB');
    const q = svFilter.trim().toLowerCase();
    const match = p => !q || (p.name + ' ' + p.cmd + ' ' + p.kind + ' ' + p.ports.map(x => x.port).join(' ')).toLowerCase().includes(q);
    const mine = d.servers.filter(p => !p.protected && match(p)), prot = d.servers.filter(p => p.protected && match(p));
    body.replaceChildren();

    const sum = el('div', undefined, 'sy-sum');
    [[d.servers.filter(p => !p.protected).length, 'خوادم قابلة للتحكم'], [d.servers.length, 'كل ما يستمع'], [d.servers.filter(p => p.ports.some(x => !x.local_only) && !p.protected).length, 'مكشوفة للشبكة'], [d.saved.length, 'محفوظة للتشغيل']]
      .forEach(([v, l]) => { const c = el('div', undefined, 'sy-stat'); c.append(el('b', String(v)), el('small', l)); sum.append(c); });
    body.append(sum);

    if (!mine.length) body.append(el('div', q ? 'لا نتائج مطابقة.' : 'لا خوادم تعمل الآن من برامجك.', 'empty'));
    mine.forEach(p => body.append(serverCard(p)));

    if (prot.length) {
      const h = el('h4', (svOpen.has('prot') ? '▾ ' : '▸ ') + `خدمات محمية (${prot.length}) — للعرض فقط`);
      h.style.cursor = 'pointer'; h.onclick = () => { svOpen.has('prot') ? svOpen.delete('prot') : svOpen.add('prot'); loadServers(); };
      body.append(h);
      if (svOpen.has('prot')) prot.forEach(p => body.append(serverCard(p)));
    }

    const hs = el('h4', 'خوادم محفوظة للتشغيل'); body.append(hs);
    if (!d.saved.length) body.append(el('small', 'حين توقف خادمًا من هنا يُحفظ أمره تلقائيًا لتعيد تشغيله بنقرة. ويمكنك إضافة خادم بنفسك بزر «＋ خادم».', 'muted'));
    d.saved.forEach(s => {
      const card = el('div', undefined, 'sy-card'), head = el('div', undefined, 'sy-head');
      head.append(el('b', s.name), chip(s.running ? 'يعمل' : 'متوقف', s.running ? 'ok' : 'waiting'));
      const cmd = el('code', s.cmd, 'sv-cmd'); cmd.title = s.cmd + '\n' + s.cwd;
      const acts = el('div', undefined, 'sy-acts');
      if (!s.running) acts.append(btn('▶ تشغيل', async () => {
        if (!confirm('تشغيل هذا الأمر على حاسوبك؟\n\n' + s.cmd + '\n\nفي المجلد: ' + s.cwd)) return;
        try { const r = await api('/api/assistant/servers/start', { id: s.id }); note('بدأ ' + s.name + (r.listening ? ' وهو يستمع الآن' : '')); } catch (e) { note('تعذّر التشغيل: ' + e.message); alert('تعذّر التشغيل:\n' + e.message); }
        setTimeout(loadServers, 600);
      }, 'btn pri'));
      acts.append(btn('حذف التعريف', async () => { if (!confirm('حذف تعريف «' + s.name + '»؟ لا يؤثر على أي ملف.')) return; await api('/api/assistant/servers/forget', { id: s.id }); loadServers(); }, 'btn'));
      card.append(head, cmd, el('small', 'المجلد: ' + s.cwd + (s.port ? ' · المنفذ ' + s.port : ''), 'muted'), acts); body.append(card);
    });
  }

  function serverCard(p) {
    const card = el('div', undefined, 'sy-card' + (p.protected ? ' off' : '')), head = el('div', undefined, 'sy-head');
    head.append(el('b', p.name), chip(p.kind), ...p.ports.slice(0, 4).map(x => chip(':' + x.port + (x.local_only ? '' : ' 🌐'), x.local_only ? 'ok' : 'waiting')));
    if (p.ports.length > 4) head.append(chip('+' + (p.ports.length - 4)));
    if (p.protected) head.append(chip('🔒 ' + p.protected, 'cat'));
    const meta = el('div', undefined, 'sy-meta');
    meta.append(el('span', '⏱ ' + ago(p.etime)), el('span', '💾 ' + (p.rss_mb ?? '—') + ' MB'), el('span', '⚙ ' + (p.cpu ?? 0) + '% معالج'), el('span', 'عملية ' + p.pid));
    const cmd = el('code', p.cmd || '', 'sv-cmd'); cmd.title = p.cmd;
    card.append(head, meta, cmd);
    if (!p.protected) {
      const acts = el('div', undefined, 'sy-acts');
      const port = p.ports[0]?.port;
      if (port) acts.append(btn('📋 نسخ الرابط', () => { copyToClipboard('http://127.0.0.1:' + port); note('نُسخ http://127.0.0.1:' + port); }, 'btn'));
      acts.append(btn('⏹ إيقاف', async () => {
        if (!confirm('إيقاف «' + p.name + '» (المنفذ ' + p.ports.map(x => x.port).join('، ') + ')؟\n\n' + p.cmd.slice(0, 300) + '\n\nيُحفظ أمره لتعيد تشغيله لاحقًا.')) return;
        try { const r = await api('/api/assistant/servers/stop', { pid: p.pid }); note(r.stopped ? 'أُوقف ' + p.name : r.note || 'لم يتوقف بعد'); if (!r.stopped && confirm('لم يستجب للإنهاء اللطيف. إيقاف قسري؟')) await api('/api/assistant/servers/stop', { pid: p.pid, force: true }); }
        catch (e) { alert('تعذّر الإيقاف:\n' + e.message); }
        setTimeout(loadServers, 400);
      }, 'btn'));
      card.append(acts);
    }
    return card;
  }

  window.loadServersView = () => { loadServers(); clearInterval(svTimer); svTimer = setInterval(() => { if ($$('#v-servers').classList.contains('on') && $$('#sv-auto').checked) loadServers(); else if (!$$('#v-servers').classList.contains('on')) clearInterval(svTimer); }, 5000); };

  /* ============ الجوال ============ */
  let phBusy = false, phTimer = null;

  async function loadPhone() {
    if (phBusy) return; phBusy = true;
    const body = $$('#ph-body');
    let d;
    try { d = await api('/api/assistant/phone/details'); } catch (e) { body.replaceChildren(el('div', e.message, 'empty err')); phBusy = false; return; }
    phBusy = false; body.replaceChildren();
    const dev = d.device, card = el('div', undefined, 'sy-card ph-hero');
    const head = el('div', undefined, 'sy-head');
    head.append(el('b', dev ? `${dev.brand ? dev.brand + ' ' : ''}${dev.model}` : 'لا جهاز متصل'), chip(dev ? (d.wireless ? '📶 لاسلكي' : '🔌 كابل') : 'غير متصل', dev ? 'ok' : 'waiting'));
    card.append(head);
    if (dev) {
      const grid = el('div', undefined, 'sy-sum');
      const stat = (v, l) => { const c = el('div', undefined, 'sy-stat'); c.append(el('b', v), el('small', l)); grid.append(c); };
      stat((dev.battery >= 0 ? dev.battery + '%' : '—') + (dev.charging ? ' ⚡' : ''), 'البطارية');
      stat('Android ' + (dev.android || '—'), 'الإصدار');
      const st = dev.storage || {}, used = st.total ? st.total - st.free : 0;
      stat(st.total ? fsize(st.free) : '—', 'مساحة فارغة');
      stat(dev.temp_c ? dev.temp_c.toFixed(1) + '°' : '—', 'الحرارة');
      card.append(grid);
      if (st.total) { const bar = el('div', undefined, 'bar'), i = document.createElement('i'); i.style.width = (used / st.total * 100).toFixed(1) + '%'; bar.append(i); card.append(bar, el('small', `${fsize(used)} مستخدم من ${fsize(st.total)}`, 'muted')); }
      card.append(el('small', 'العنوان: ' + (d.wireless || dev.serial), 'muted'));
    } else {
      card.append(el('small', 'قم بتوصيل الهاتف بالكابل مرة، أو اقترن لاسلكيًا من الأسفل؛ بعدها يتصل زاجل تلقائيًا كل 20 ثانية.', 'muted'));
    }
    body.append(card);

    const go = el('div', undefined, 'sy-acts');
    const jump = (v, src) => () => { document.querySelector(`[data-v="${v}"]`)?.click(); if (src) setTimeout(() => window.P?.openSource?.('phone'), 150); };
    go.append(btn('📁 ملفات الهاتف', jump('files', true), 'btn pri'), btn('📦 التطبيقات', jump('apps'), 'btn'), btn('🔒 بيانات التطبيقات', jump('data'), 'btn'), btn('🔁 المزامنات', jump('sync'), 'btn'));
    body.append(el('h4', 'اذهب إلى'), go);

    if (dev) {
      const scr = el('div', undefined, 'sy-card'), sh = el('div', undefined, 'sy-head');
      sh.append(el('b', 'شاشة الهاتف على الماك'));
      const sm = el('small', 'تفتح شاشة الهاتف في نافذة تضغط عليها بالفأرة وتكتب بلوحة المفاتيح، ويبقى الهاتف في يدك أو على الطاولة.', 'muted');
      const sa = el('div', undefined, 'sy-acts');
      sa.append(btn('🖥️ افتح شاشة الهاتف', async (ev) => {
        const b = ev.currentTarget; b.disabled = true; b.textContent = 'جارٍ الفتح…';
        try { const r = await api('/api/assistant/phone/screen', { action: 'start' }); note(r.note || 'فُتحت الشاشة'); } catch (e) { alert('تعذّر فتح الشاشة:\n' + e.message); }
        b.disabled = false; b.textContent = '🖥️ افتح شاشة الهاتف';
      }, 'btn pri'), btn('✕ أغلق النافذة', async () => {
        try { const r = await api('/api/assistant/phone/screen', { action: 'stop' }); note(r.note || 'أُغلقت'); } catch (e) { alert(e.message); }
      }, 'btn'));
      const ctl = async (action, extra, b) => {
        const old = b && b.textContent; if (b) { b.disabled = true; }
        try { const r = await api('/api/assistant/phone/control', Object.assign({ action }, extra || {})); note(r.note || 'تم'); if (r.path) alert(r.note + '\n' + r.path); } catch (e) { alert(e.message); }
        if (b) { b.disabled = false; b.textContent = old; }
      };
      const row = (title, items) => { const r = el('div', undefined, 'sy-acts'); r.append(el('small', title, 'muted')); items.forEach(([label, fn, tip]) => { const b = btn(label, ev => fn(ev.currentTarget), 'btn'); if (tip) b.title = tip; r.append(b); }); return r; };
      const key = n => b => ctl('key', { name: n }, b);
      scr.append(sh, sm, sa,
        row('التقاط:', [['📸 لقطة شاشة', b => ctl('screenshot', {}, b), 'تُحفظ في التنزيلات'], ['⏺️ ابدأ تسجيل الشاشة', b => ctl('record_start', {}, b)], ['⏹️ أوقف التسجيل واحفظه', b => ctl('record_stop', {}, b)]]),
        row('الأزرار:', [['◀ رجوع', key('back')], ['⭕ الرئيسية', key('home')], ['▢ التطبيقات الأخيرة', key('recents')], ['⏻ قفل/تشغيل', key('power')], ['🔊 +', key('vol_up')], ['🔉 −', key('vol_down')], ['🔇', key('mute')]]),
        row('اللوحات:', [['🔔 الإشعارات', b => ctl('notifications', {}, b)], ['⚙️ الإعدادات السريعة', b => ctl('quick_settings', {}, b)], ['✕ إغلاقها', b => ctl('collapse', {}, b)], ['🔄 تدوير الشاشة', b => ctl('rotate', { rotation: 1 }, b)], ['💡 أبقِ الشاشة مضاءة', b => ctl('keep_awake', { on: true }, b)]]),
        row('الوسائط:', [['⏯️', key('play_pause')], ['⏭️', key('next')], ['⏮️', key('prev')], ['📷 الكاميرا', key('camera')]]),
        row('كتابة:', [['⌨️ اكتب نصًا إنجليزيًا في الحقل المحدد', () => promptModal('كتابة على الهاتف', 'اكتب النص (حروف إنجليزية وأرقام فقط):', '', 'أرسل', t => ctl('text', { text: t }))]]));
      body.append(scr);
    }

    const conn = el('div', undefined, 'sy-card'), ch = el('div', undefined, 'sy-head');
    ch.append(el('b', 'الاتصال اللاسلكي'));
    const msg = el('small', d.last_note || (dev ? 'يُعاد الاتصال تلقائيًا إن انقطع.' : ''), 'muted');
    const acts = el('div', undefined, 'sy-acts');
    acts.append(btn('↻ اتصل الآن', async (ev) => {
      const b = ev.currentTarget; b.disabled = true; b.textContent = 'جارٍ الاتصال…';
      try { const r = await api('/api/assistant/phone', {}); note('اتصل الهاتف: ' + (r.connected || '')); } catch (e) { note('تعذّر الاتصال: ' + e.message); alert('تعذّر الاتصال:\n' + e.message); }
      b.disabled = false; loadPhone();
    }, 'btn pri'), btn('اقتران جديد (مرة واحدة)', () => {
      promptModal('اقتران لاسلكي', 'في الهاتف: الإعدادات ← خيارات المطور ← التصحيح اللاسلكي ← الاقتران برمز الاقتران. اكتب العنوان الظاهر (مثل 192.168.1.20:37099):', '', 'التالي', addr =>
        promptModal('رمز الاقتران', 'اكتب الرمز المكوّن من ست خانات الظاهر في الهاتف:', '', 'اقترن', async code => {
          try { const r = await api('/api/assistant/phone', { pair_addr: addr, pair_code: code }); note('تم الاقتران: ' + (r.connected || '')); } catch (e) { alert('فشل الاقتران:\n' + e.message); }
          loadPhone();
        }));
    }, 'btn'));
    conn.append(ch, msg, acts); body.append(conn);
  }

  window.loadPhoneView = () => { loadPhone(); clearInterval(phTimer); phTimer = setInterval(() => { if ($$('#v-phone').classList.contains('on')) loadPhone(); else clearInterval(phTimer); }, 15000); };


  /* ============ نقل وإنقاذ المساحات ============ */
  const RS = { src: '', sel: new Set(), an: null, dst: '', dstDir: '', mode: 'move', place: [], tab: 'top', browse: null, bpath: '', timer: null, anTimer: null, yellow: false, rule: null, dbrowse: null };
  const CATS = { green: ['🟢', 'ok', 'قابل للنقل'], green_old: ['🟢', 'ok', 'القديم فقط'], yellow: ['🟡', 'waiting', 'يحتاج قرارك'], red: ['🔴', 'error', 'محمي'] };
  const dur = s => s == null ? '—' : s < 90 ? s + ' ث' : s < 5400 ? Math.round(s / 60) + ' د' : (s / 3600).toFixed(1) + ' س';
  const STATE_AR = { queued: 'في الانتظار', running: 'جارٍ', paused: 'متوقف مؤقتًا', done: 'اكتمل', cancelled: 'أُلغي', error: 'خطأ', interrupted: 'انقطع — يمكن استئنافه' };
  const label = id => (RS.place.find(p => p.id === id) || {}).label || id;
  const rsBody = () => $$('#rs-page');

  async function loadRescueView() {
    const pg = rsBody();
    if (!pg.dataset.init) {
      pg.dataset.init = '1';
      pg.replaceChildren(el('h2', '🛟 نقل وإنقاذ المساحات'),
        el('small', 'حين تمتلئ مساحة iCloud أو ينتهي اشتراك درايف: اختر مكانًا، حدّد ما تنقله، واختر وجهة. يعمل في الخلفية، ويتحقق من كل ملف قبل أي حذف، وما يُحذف يذهب إلى السلة فيمكن استرجاعه.', 'muted'));
      const jobs = el('div'); jobs.id = 'rs-jobs'; const wiz = el('div'); wiz.id = 'rs-wiz';
      pg.append(el('h4', 'المهام'), jobs, el('h4', 'مهمة جديدة'), wiz);
      try { RS.place = (await api('/api/rescue/places')).places; } catch (e) { wiz.append(el('div', e.message, 'empty err')); }
      try { const al = await api('/api/rescue/alert'); if (al.alert) pg.prepend(el('div', al.message, 'sy-card')); } catch (_) {}
      drawWizard();
    }
    refreshJobs();
    clearInterval(RS.timer);
    RS.timer = setInterval(() => { if ($$('#v-rescue').classList.contains('on')) refreshJobs(); else clearInterval(RS.timer); }, 2000);
  }
  window.loadRescueView = loadRescueView;

  async function refreshJobs() {
    let d; try { d = await api('/api/rescue/jobs'); } catch (_) { return; }
    const box = $$('#rs-jobs'); if (!box) return;
    box.replaceChildren();
    if (!d.jobs.length) { box.append(el('div', 'لا مهام بعد.', 'empty')); return; }
    d.jobs.forEach(j => box.append(jobCard(j)));
  }

  function jobCard(j) {
    const card = el('div', undefined, 'sy-card'), head = el('div', undefined, 'sy-head');
    const live = j.state === 'running' || j.state === 'paused';
    head.append(el('b', j.title), chip(STATE_AR[j.state] || j.state, j.state === 'done' ? 'ok' : j.state === 'error' ? 'error' : live ? 'running' : 'waiting'),
      chip(j.mode === 'move' ? 'نقل' : 'نسخ'));
    const pct = j.bytes_total ? Math.min(100, j.bytes_done / j.bytes_total * 100) : (j.state === 'done' ? 100 : 0);
    const prog = el('div', undefined, 'sy-prog'), bar = el('div', undefined, 'bar'), i = document.createElement('i'); i.style.width = pct.toFixed(1) + '%'; bar.append(i);
    prog.append(bar);
    const c = j.counts || {};
    prog.append(el('small', `${fsize(j.bytes_done)} من ${fsize(j.bytes_total)} · ${c.deleted + c.verified || 0}/${j.file_total} ملف` + (c.failed ? ` · ❌ ${c.failed} فاشل` : '') + (live && j.speed ? ` · ${fsize(j.speed)}/ث · متبقٍ ${dur(j.eta)}` : ''), 't'));
    if (live && j.current) prog.append(el('small', '… ' + j.current, 't'));
    const meta = el('div', `${label(j.src_root)} ← إلى → ${label(j.dst_root)}${j.dst_dir ? ' / ' + j.dst_dir : ''}`, 'sy-meta');
    card.append(head, meta, prog);
    if (j.error) card.append(el('small', 'خطأ: ' + j.error, 'muted'));
    const acts = el('div', undefined, 'sy-acts');
    const post = (path, extra) => async () => { try { await api(path, { id: j.id, ...extra }); } catch (e) { alert(e.message); } refreshJobs(); };
    if (live) {
      acts.append(btn(j.state === 'paused' ? '▶ متابعة' : '⏸ إيقاف مؤقت', post('/api/rescue/pause', { paused: j.state !== 'paused' }), 'btn'));
      acts.append(btn('✖ إلغاء', () => { if (confirm('إلغاء المهمة؟ ما نُقل وتُحقّق منه يبقى في الوجهة.')) post('/api/rescue/cancel')(); }, 'btn'));
    }
    if (j.state === 'interrupted' || j.state === 'cancelled' || j.state === 'error') acts.append(btn('▶ استئناف', post('/api/rescue/resume'), 'btn pri'));
    if (!live && c.failed) acts.append(btn('↻ إعادة الفاشل', post('/api/rescue/retry'), 'btn'));
    acts.append(btn('📄 التقرير', () => showReport(j.id), 'btn'));
    if (!live) acts.append(btn('إزالة من القائمة', () => { if (confirm('إزالة سجل المهمة؟ لا يمسّ أي ملف.')) post('/api/rescue/forget')(); }, 'btn'));
    card.append(acts);
    return card;
  }

  async function showReport(id) {
    let j; try { j = await api('/api/rescue/job?id=' + encodeURIComponent(id)); } catch (e) { alert(e.message); return; }
    const r = j.report, box = el('div');
    box.append(el('h3', j.title));
    box.append(el('p', `من: ${label(j.src_root)} ← إلى: ${label(j.dst_root)}${j.dst_dir ? ' / ' + j.dst_dir : ''}`));
    box.append(el('p', `المنقول والمتحقَّق منه: ${j.counts.deleted + j.counts.verified} من ${j.file_total} ملف (${fsize(r ? r.bytes : j.bytes_done)})`));
    if (j.mode === 'move') box.append(el('p', `المساحة المحرَّرة من المصدر: ${fsize(j.freed)}`));
    if (r && r.note) box.append(el('small', r.note, 'muted'));
    if (r && r.failed.length) { box.append(el('h4', 'ملفات فشلت (لم يُحذف أصلها)')); r.failed.slice(0, 30).forEach(f => box.append(el('div', f.rel + ' — ' + f.error, 'sy-meta'))); }
    if (r && r.where.length) { box.append(el('h4', 'أين ذهب كل عنصر')); r.where.slice(0, 40).forEach(w => box.append(el('div', w.from + '  ←  ' + w.to, 'sy-meta'))); }
    const acts = el('div', undefined, 'sy-acts');
    if (j.mode === 'move' && (j.ledger || []).some(e => e.op === 'trash' && !e.undone))
      acts.append(btn('↩ تراجع: أعد الملفات من السلة إلى مكانها', async () => { try { const u = await api('/api/rescue/undo', { id }); alert('أُعيد ' + u.restored + ' ملف' + (u.skipped ? ' (تعذّر ' + u.skipped + ')' : '')); } catch (e) { alert(e.message); } refreshJobs(); closeModal(); }, 'btn'));
    box.append(acts);
    const close = btn('إغلاق', closeModal, 'btn'); box.append(close);
    openModal(m => m.append(box));
  }

  /* ---- المعالج: المصدر ← التحليل ← الاختيار ← الوجهة ---- */
  function drawWizard() {
    const w = $$('#rs-wiz'); if (!w) return;
    w.replaceChildren();
    const row = el('div', undefined, 'bar2'); row.style.cssText = 'border:0;padding:0 0 8px;gap:8px;flex-wrap:wrap';
    const sel = document.createElement('select'); sel.className = 'search'; sel.style.maxWidth = '340px';
    sel.append(new Option('١) اختر المكان المراد تفريغه…', ''));
    RS.place.forEach(p => sel.append(new Option(p.label, p.id)));
    sel.value = RS.src;
    sel.onchange = () => { RS.src = sel.value; RS.sel = new Set(); RS.an = null; RS.rule = null; RS.browse = null; RS.bpath = ''; drawWizard(); if (RS.src) startAnalysis(false); };
    row.append(sel);
    if (RS.src) row.append(btn('↻ إعادة التحليل', () => startAnalysis(true), 'btn'));
    w.append(row);
    if (!RS.src) return;
    const body = el('div'); body.id = 'rs-an'; w.append(body);
    drawAnalysis();
    if (RS.sel.size || RS.rule) drawDest(w);
  }

  async function startAnalysis(refresh) {
    clearTimeout(RS.anTimer);
    const src = RS.src;
    let a; try { a = await api('/api/rescue/analysis?root=' + encodeURIComponent(src) + (refresh ? '&refresh=1' : '')); } catch (e) { RS.an = { state: 'error', error: e.message }; drawAnalysis(); return; }
    if (src !== RS.src) return;
    RS.an = a; drawAnalysis();
    if (a.state === 'running') RS.anTimer = setTimeout(() => startAnalysis(false), 1500);
  }

  function selBox(rel, size) {
    const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = RS.sel.has(rel);
    cb.onchange = () => { cb.checked ? RS.sel.add(rel) : RS.sel.delete(rel); RS.rule = null; drawDestOnly(); };
    return cb;
  }
  function drawDestOnly() { const w = $$('#rs-wiz'); if (!w) return; w.querySelector('#rs-dest')?.remove(); if (RS.sel.size || RS.rule) drawDest(w); }

  function drawAnalysis() {
    const b = $$('#rs-an'); if (!b) return;
    if (!RS.an) { b.replaceChildren(el('div', 'اضغط على «إعادة التحليل» أو اختر المكان.', 'empty')); startAnalysis(false); return; }
    const a = RS.an;
    b.replaceChildren();
    if (a.state === 'running') { b.append(el('div', `جارٍ تحليل المكان… ${a.scanned || 0} ملف حتى الآن (قد يستغرق دقائق للأماكن الكبيرة).`, 'empty')); return; }
    if (a.state === 'error') { b.append(el('div', 'تعذّر التحليل: ' + a.error, 'empty err')); return; }
    const sum = el('div', undefined, 'sy-sum');
    const stats = [[fsize(a.total_bytes), 'حجم المحتوى'], [a.files, 'ملف'], [fsize((a.older_than_year || {}).bytes || 0), 'أقدم من سنة']];
    if (a.evicted) stats.push([a.evicted, 'ملف مبعد في السحابة (يُنزَّل عند النقل)']);
    if (a.quota && a.quota.remaining != null && a.quota.total == null) stats.push([fsize(a.quota.remaining), 'المتبقي في iCloud']);
    if (a.quota && a.quota.total) stats.push([fsize(a.quota.free), 'المتبقي من ' + fsize(a.quota.total)]);
    stats.forEach(([v, l]) => { const c = el('div', undefined, 'sy-stat'); c.append(el('b', String(v)), el('small', l)); sum.append(c); });
    b.append(sum);
    (a.notes || []).forEach(n => b.append(el('small', 'ℹ️ ' + n, 'muted')));

    if ((a.suggestions || []).length) {
      b.append(el('h4', 'اقتراحات'));
      const bx = el('div', undefined, 'sy-acts');
      a.suggestions.forEach(s => bx.append(btn(`${s.title} (${fsize(s.bytes)}، ${s.files} ملف)`, () => {
        if (s.rule.older_than_days) { RS.rule = s.rule; RS.sel = new Set(); } else { RS.rule = null; RS.sel = new Set(s.rule.items); }
        drawWizard(); document.querySelector('#rs-dest')?.scrollIntoView({ behavior: 'smooth' });
      }, 'btn pri')));
      b.append(bx);
    }

    const tabs = el('div', undefined, 'sy-acts');
    [['top', 'المجلدات الكبرى'], ['browse', 'تصفح واختيار'], ['largest', 'الأكبر حجمًا'], ['oldest', 'الأقدم']].forEach(([k, t]) => tabs.append(btn(t, () => { RS.tab = k; if (k === 'browse' && !RS.browse) loadBrowse(''); drawAnalysis(); }, 'btn' + (RS.tab === k ? ' pri' : ''))));
    b.append(tabs);
    if (RS.tab === 'top') {
      const mx = Math.max(1, ...a.top.map(t => t.bytes));
      a.top.slice(0, 60).forEach(t => {
        const r = el('div', undefined, 'sy-bar'), cat = CATS[t.cat] || CATS.green;
        const blocked = t.cat === 'red';
        if (!blocked) {
          const cb = selBox(t.name); r.append(cb);
          if (t.cat === 'yellow') cb.onchange = () => { if (cb.checked && !confirm(t.note + '\n\nهل تريد فعلًا اختياره؟')) { cb.checked = false; return; } cb.checked ? (RS.sel.add(t.name), RS.yellow = true) : RS.sel.delete(t.name); RS.rule = null; drawDestOnly(); };
          if (t.cat === 'green_old') cb.disabled = true;
        }
        const nm = el('span', `${cat[0]} ${t.label || t.name}`, 'nm'); nm.title = t.note || t.name;
        const tr = el('div', undefined, 'tr'), i = document.createElement('i'); i.style.width = (t.bytes / mx * 100).toFixed(1) + '%'; tr.append(i);
        r.append(nm, tr, el('span', fsize(t.bytes), 'v')); b.append(r);
        if (t.note && t.cat !== 'green') b.append(el('small', '   ' + t.note, 'muted'));
      });
    } else if (RS.tab === 'browse') drawBrowse(b);
    else (RS.tab === 'largest' ? a.largest : a.oldest).forEach(f => {
      const r = el('div', undefined, 'sy-bar'); r.append(selBox(f.rel));
      const nm = el('span', f.rel, 'nm'); nm.title = f.rel; nm.style.flex = '1';
      r.append(nm, el('span', fsize(f.size) + (f.mtime ? ' · ' + new Date(f.mtime * 1000).toLocaleDateString('en-GB') : ''), 'v')); b.append(r);
    });
  }

  async function loadBrowse(path) {
    try { RS.browse = await api('/api/rescue/browse?root=' + encodeURIComponent(RS.src) + '&path=' + encodeURIComponent(path)); RS.bpath = path; } catch (e) { RS.browse = { entries: [], err: e.message }; }
    drawAnalysis();
  }
  function drawBrowse(b) {
    const d = RS.browse; if (!d) return;
    const up = RS.bpath.split('/').filter(Boolean).slice(0, -1).join('/');
    const bar = el('div', undefined, 'sy-acts');
    if (RS.bpath) bar.append(btn('⬆ ' + (up || 'الجذر'), () => loadBrowse(up), 'btn'));
    bar.append(el('small', '/' + RS.bpath, 'muted')); b.append(bar);
    if (d.err) b.append(el('div', d.err, 'empty err'));
    d.entries.forEach(e => {
      const r = el('div', undefined, 'sy-bar'); r.dir = 'rtl'; r.append(selBox(e.path));      // كل الصفوف من اليمين، ولو كان الاسم لاتينيًّا
      const nm = el('span', (e.is_dir ? '📁 ' : '') + e.name + (e.evicted ? ' ☁︎' : ''), 'nm'); nm.style.flex = '1'; nm.dir = 'auto'; nm.style.textAlign = 'right'; nm.style.unicodeBidi = 'plaintext';
      if (e.is_dir) { nm.style.cursor = 'pointer'; nm.onclick = () => loadBrowse(e.path); }
      r.append(nm, el('span', e.size != null ? fsize(e.size) : '', 'v')); b.append(r);
    });
  }

  function drawDest(w) {
    const box = el('div', undefined, 'sy-card'); box.id = 'rs-dest';
    const n = RS.rule ? 'كل الملفات الأقدم من سنة' : RS.sel.size + ' عنصر مختار';
    box.append(el('b', '٢) الوجهة — ' + n));
    const row = el('div', undefined, 'bar2'); row.style.cssText = 'border:0;padding:8px 0;gap:8px;flex-wrap:wrap';
    const sel = document.createElement('select'); sel.className = 'search'; sel.style.maxWidth = '340px';
    sel.append(new Option('اختر مكان الوجهة…', ''));
    RS.place.filter(p => p.id !== RS.src).forEach(p => sel.append(new Option(p.label, p.id)));
    sel.value = RS.dst;
    sel.onchange = () => { RS.dst = sel.value; RS.dstDir = ''; RS.dbrowse = null; drawDestOnly(); if (RS.dst) loadDestDirs(''); };
    row.append(sel); box.append(row);
    if (RS.dst) {
      const dd = el('div'); dd.append(el('small', 'المجلد في الوجهة: /' + RS.dstDir, 'muted'));
      const nav = el('div', undefined, 'sy-acts');
      if (RS.dstDir) nav.append(btn('⬆', () => loadDestDirs(RS.dstDir.split('/').slice(0, -1).join('/')), 'btn'));
      (RS.dbrowse || []).forEach(e => nav.append(btn('📁 ' + e.name, () => loadDestDirs(e.path), 'btn')));
      nav.append(btn('＋ مجلد جديد', () => promptModal('مجلد جديد', 'اسم المجلد داخل الوجهة (يُنشأ عند النقل):', '', 'موافق', nm => { RS.dstDir = [RS.dstDir, nm.trim().replace(/[\\/]/g, '-')].filter(Boolean).join('/'); RS.dbrowse = []; drawDestOnly(); }), 'btn'));
      dd.append(nav); box.append(dd);
    }
    const mrow = el('div', undefined, 'sy-acts');
    [['move', 'نقل (يحرّر المساحة بعد التحقق، والأصل يذهب إلى السلة)'], ['copy', 'نسخ فقط (الأصل يبقى)']].forEach(([v, t]) => {
      const lb = document.createElement('label'); lb.className = 'muted';
      const rd = document.createElement('input'); rd.type = 'radio'; rd.name = 'rs-mode'; rd.checked = RS.mode === v; rd.onchange = () => { RS.mode = v; };
      lb.append(rd, ' ' + t); mrow.append(lb);
    });
    box.append(mrow);
    const go = btn('▶ ابدأ في الخلفية', async () => {
      if (!RS.dst) { alert('اختر الوجهة أولًا.'); return; }
      if (!confirm(`${RS.mode === 'move' ? 'نقل' : 'نسخ'} ${n} من «${label(RS.src)}» إلى «${label(RS.dst)}/${RS.dstDir}»؟\n\n` + (RS.mode === 'move' ? 'لا يُحذف أي ملف إلا بعد التحقق من نسخته، ويذهب إلى السلة.' : ''))) return;
      go.disabled = true;
      try {
        await api('/api/rescue/start', { src_root: RS.src, dst_root: RS.dst, dst_dir: RS.dstDir, mode: RS.mode, items: [...RS.sel], rule: RS.rule || undefined, allow_yellow: RS.yellow });
        note('بدأت المهمة'); RS.sel = new Set(); RS.rule = null; RS.yellow = false; drawWizard();
      } catch (e) { alert('تعذّر البدء:\n' + e.message); }
      go.disabled = false; refreshJobs();
    }, 'btn pri');
    box.append(go); w.append(box);
    if (RS.dst && !RS.dbrowse) loadDestDirs(RS.dstDir);
  }
  async function loadDestDirs(path) {
    try { const d = await api('/api/rescue/browse?root=' + encodeURIComponent(RS.dst) + '&path=' + encodeURIComponent(path)); RS.dbrowse = d.entries.filter(e => e.is_dir).slice(0, 40); RS.dstDir = path; } catch (_) { RS.dbrowse = []; }
    drawDestOnly();
  }

  document.addEventListener('DOMContentLoaded', () => {
    $$('#sv-refresh').onclick = () => loadServers();
    $$('#sv-q').oninput = e => { svFilter = e.target.value; loadServers(); };
    $$('#sv-add').onclick = () => promptModal('خادم جديد', 'اسم الخادم:', '', 'التالي', name =>
      promptModal('أمر التشغيل', 'الأمر كما تكتبه في الطرفية (مثل: npm run dev):', '', 'التالي', cmd =>
        promptModal('المجلد', 'مجلد التشغيل (فارغ = مجلدك الرئيسي):', '', 'التالي', cwd =>
          promptModal('المنفذ', 'رقم المنفذ الذي يستمع عليه (اختياري):', '', 'احفظ', async port => {
            try { await api('/api/assistant/servers/define', { name, cmd, cwd, port }); note('حُفظ التعريف'); } catch (e) { alert(e.message); }
            loadServers();
          }))));
    $$('#ph-refresh').onclick = () => loadPhone();
  });
})();
