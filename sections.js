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
