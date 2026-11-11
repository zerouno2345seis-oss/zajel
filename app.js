const $ = s => document.querySelector(s);
const el = (tag, text, cls) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (cls) e.className = cls; return e; };
let inflight = 0, barT = null;
function busyBar(on) {
  let b = document.getElementById('busybar'); if (!b) { b = document.createElement('div'); b.id = 'busybar'; document.body.append(b); }
  inflight += on ? 1 : -1; clearTimeout(barT);
  if (inflight > 0) barT = setTimeout(() => b.classList.add('on'), 150); else b.classList.remove('on');
}
async function api(path, payload) {
  const quiet = /^\/api\/(status|health|watch)/.test(path); if (!quiet) busyBar(true);
  try {
    const r = await fetch(path, payload === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    const d = await r.json();
    if (!r.ok || d.error) throw new Error(d.error || 'تعذر تنفيذ الطلب');
    return d;
  } finally { if (!quiet) busyBar(false); }
}
const note = t => { const l = $('#log'); if (l && !(phone && phone.busy)) l.textContent = t; };
const fsize = n => n == null ? '—' : n >= 1e9 ? (n / 1e9).toFixed(1) + ' GB' : n >= 1e6 ? (n / 1e6).toFixed(1) + ' MB' : n >= 1e3 ? Math.round(n / 1e3) + ' KB' : n + ' B';
const fdate = t => t ? new Date(t).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }) : '—';
const store = { get(k, d) { try { return localStorage.getItem(k) ?? d; } catch (_) { return d; } }, set(k, v) { try { localStorage.setItem(k, v); } catch (_) {} } };
const EXT = { img: /\.(jpe?g|png|webp|heic|heif|gif|bmp|tiff?|avif|dng)$/i, aud: /\.(mp3|m4a|aac|wav|ogg|opus|flac|amr|3ga)$/i, vid: /\.(mp4|mkv|mov|avi|webm|3gp|m4v)$/i, arc: /\.(zip|rar|7z|tar|tgz|gz|bz2|xz|iso|cab)$/i };
const kindOf = e => e.is_dir ? 'dir' : EXT.img.test(e.name) ? 'img' : EXT.aud.test(e.name) ? 'aud' : EXT.vid.test(e.name) ? 'vid' : EXT.arc.test(e.name) ? 'arc' : 'doc';
const KIND_AR = { dir: 'مجلد', img: 'صورة', aud: 'صوت', vid: 'فيديو', arc: 'أرشيف', doc: 'مستند' }, KIND_ORDER = ['dir', 'img', 'aud', 'vid', 'arc', 'doc'];
const extOf = e => (e.is_dir || !String(e.name).includes('.')) ? '' : String(e.name).split('.').pop().toLowerCase();
const typeLabel = e => { const k = kindOf(e), x = extOf(e); return KIND_AR[k] + (x && !e.is_dir ? ' · ' + x.toUpperCase() : ''); };
const sortVal = (e, key) => key === 'size' ? (e.is_dir ? (e.dsize ?? -1) : (e.size ?? 0)) : (e[key] ?? 0);
const sortEntries = (list, key, desc) => list.sort((a, b) => {
  if (key === 'size') { const d = sortVal(a, key) - sortVal(b, key); return (d || String(a.name).localeCompare(String(b.name), 'ar', { numeric: true })) * (desc ? -1 : 1); }  // الحجم: مجلدات وملفات معًا بحسب الحجم الفعلي
  if (key === 'kind') { const d = KIND_ORDER.indexOf(kindOf(a)) - KIND_ORDER.indexOf(kindOf(b)); return (d || extOf(a).localeCompare(extOf(b)) || String(a.name).localeCompare(String(b.name), 'ar', { numeric: true })) * (desc ? -1 : 1); }  // النوع: مجلد ثم صورة ثم صوت…، وداخل كل نوع باللاحقة ثم الاسم
  if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1;
  if (key === 'ext') { const ex = x => (x.is_dir || !x.name.includes('.')) ? '' : x.name.split('.').pop().toLowerCase(); return (ex(a).localeCompare(ex(b)) || String(a.name).localeCompare(String(b.name), 'ar', { numeric: true })) * (desc ? -1 : 1); }
  if (key === 'added' || key === 'born') return ((a[key] ?? a.mod ?? 0) - (b[key] ?? b.mod ?? 0)) * (desc ? -1 : 1);   // الهاتف لا يوفّر الإضافة: يُستعمل تاريخ التعديل
  return ((key === 'name' || key === 'folder') ? String(a[key] ?? '').localeCompare(String(b[key] ?? ''), 'ar', { numeric: true }) : (a[key] ?? 0) - (b[key] ?? 0)) * (desc ? -1 : 1);
});

/* ================= المصادر =================
   كل مصدر: { id, type: 'adb' | 'local', label, icon, online, serial | root, quick: [{l, p}], home }
   adb  = جهاز أندرويد (الهاتف عبر USB، الساعة عبر Wi-Fi): يُقرأ مباشرة من الجهاز.
   local = مجلد على هذا الكمبيوتر (السحابة المتزامنة، قرص خارجي، ملفاتك).                              */
let phone = null, polling = false, picking = false, lastResult = '', cloudRoots = [], sources = [], srcSig = '';
const asel = new Set(), cats = new Set();
let watch = null;                         // نتيجة اتصال الساعة (تبويب الساعة)
let dragFlag = false, dragInfo = null;
const workspaces = [];                    // التبويبات: كل تبويب لوحة أو لوحتان
let ws = null, P = null;                  // التبويب النشط واللوحة النشطة
const allPanes = () => workspaces.flatMap(w => w.panes);
const selUnion = id => { const u = new Set(); allPanes().forEach(p => p.selBySrc.get(id)?.forEach(x => u.add(x))); return u; };

const QUICK_PHONE = [['الصور', '/sdcard/DCIM'], ['لقطات الشاشة', '/sdcard/Pictures'], ['الفيديو', '/sdcard/Movies'], ['الصوتيات', '/sdcard/Music'], ['التسجيلات', '/sdcard/Recordings'], ['المستندات', '/sdcard/Documents'], ['التنزيلات', '/sdcard/Download']];
const QUICK_HOME = [['سطح المكتب', 'Desktop'], ['المستندات', 'Documents'], ['التنزيلات', 'Downloads'], ['نسخ احتياطي', 'نسخ احتياطي']];
const EXT_GROUPS = [['Word', ['doc', 'docx', 'odt', 'rtf', 'pages']], ['PDF', ['pdf']], ['Excel', ['xls', 'xlsx', 'csv', 'ods', 'numbers']], ['PowerPoint', ['ppt', 'pptx', 'odp', 'key']], ['نصوص', ['txt', 'md', 'log', 'json', 'xml']], ['صور', ['jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'heif', 'bmp', 'tif', 'tiff', 'dng', 'svg']], ['فيديو', ['mp4', 'mov', 'mkv', 'avi', 'webm', '3gp', 'm4v']], ['صوت', ['mp3', 'm4a', 'aac', 'wav', 'flac', 'ogg', 'opus', 'amr']], ['أرشيف', ['zip', 'rar', '7z', 'tar', 'gz', 'tgz', 'bz2', 'xz', 'iso']], ['تطبيقات', ['apk', 'aab', 'dmg', 'pkg', 'exe', 'msi', 'app', 'ipa']], ['برمجة', ['py', 'js', 'ts', 'java', 'kt', 'swift', 'c', 'h', 'cpp', 'html', 'css', 'sh']], ['كتب', ['epub', 'mobi', 'azw3', 'djvu']]];
const SRC_HELP = {
  network: 'من جهاز آخر على شبكتك المحلية (مشاركة SMB/AFP/NFS موصولة عبر Finder). تُقرأ الملفات عبر الشبكة، فقد تكون أبطأ من القرص المحلي.',
  adb: 'تُقرأ المعلومات مباشرة من الجهاز عبر كابل USB (أو Wi-Fi للساعة). لا يُحفظ شيء على الكمبيوتر إلا عندما تبدأ نسخًا.',
  cloud: 'هذه ملفات مجلد السحابة المتزامن على هذا الكمبيوتر. ما تراه هنا هو نفسه ما في حسابك. ملفات Google الأصلية (Docs وSheets) اختصارات صغيرة لا محتوى.',
  disk: 'من القرص الخارجي الموصول بالكمبيوتر. يظهر ويختفي تلقائيًا عند توصيله وفصله.',
  home: 'من ملفات هذا الكمبيوتر (مجلدك الشخصي).'
};
const srcOf = id => (typeof sources !== 'undefined' ? sources : []).find(s => s.id === id); // مصدر باسمه (للنوافذ كلها)
const devOpen = () => { try { return JSON.parse(store.get('devopen') || '[]'); } catch (_) { return []; } };
function toggleDev(id) { const o = devOpen(); store.set('devopen', JSON.stringify(o.includes(id) ? o.filter(x => x !== id) : [...o, id])); renderSources(); }
function buildSources() {
  const list = [];
  const pOn = !!phone?.connected;
  list.push({ id: 'phone', type: 'adb', label: pOn ? phone.model : 'الهاتف', icon: '📱', online: pOn, serial: phone?.serial, home: '/sdcard', quick: QUICK_PHONE.map(([l, p]) => ({ l, p })), kind: 'adb', sub: pOn ? (phone.wifi ? 'متصل لاسلكيًا (Wi-Fi)' : 'متصل بكابل USB') : 'غير متصل' });
  const w = phone?.watch;
  (iosDevices || []).forEach(d => { const on = (!d.locked || !!d.held) && d.trusted !== false;
    list.push({ id: 'ios:' + d.udid, type: 'ios', udid: d.udid, label: d.name || d.cls, icon: d.cls === 'iPad' ? '📟' : '📱', online: on, home: '/DCIM', kind: 'ios', total: d.total, free: d.free,
      quick: [['الصور والفيديو', '/DCIM'], ['ملفات التطبيقات', '/@apps'], ['التنزيلات', '/Downloads'], ['الكتب', '/Books'], ['التسجيلات', '/Recordings']].map(([l, p]) => ({ l, p })), sub: on && !d.locked ? `${d.cls} · ${d.conn === 'wifi' ? 'واي فاي' : 'كابل'} · iOS ${d.ios}` : d.held ? `${d.cls} · مقفل أو نائم (نفس العنوان) — آخر معلومات محفوظة`: d.asleep ? 'لا يستجيب — مقفل أو نائم' : 'مقفل — افتح القفل' }); });
  // كيندل موصول لكن قرصه لم يُفتح بعد (الشاشة مقفلة غالبًا): يظهر في الأجهزة بتنبيه؛ وحين يُفتح قرصه يحلّ محلّه مصدر القرص
  if (kindleDev && !(cloudRoots || []).some(r => r.group === 'disk' && /kindle/i.test(r.label || r.id))) list.push({ id: 'kindle', type: 'kindle', label: 'Kindle', icon: '📖', online: false, home: '/documents', kind: 'kindle', quick: [], sub: 'افتح قفل شاشة الكيندل' });
  list.push({ id: 'watch', type: 'adb', label: 'ساعة Samsung', icon: '⌚', online: !!w?.connected, serial: w?.addr, home: '/sdcard', quick: [['الصور', '/sdcard/DCIM'], ['التسجيلات', '/sdcard/Recordings'], ['الموسيقى', '/sdcard/Music'], ['التنزيلات', '/sdcard/Download']].map(([l, p]) => ({ l, p })), kind: 'adb', sub: w?.connected ? 'متصلة عبر Wi-Fi' : (w?.ip ? 'غير متصلة' : 'لم تُحفظ بعد') });
  for (const r of cloudRoots) {
    const kind = (r.group === 'cloud' || r.group === 'rclone') ? 'cloud' : r.group === 'disk' ? 'disk' : r.group === 'network' ? 'network' : 'home';
    const vol = (phone?.volumes || []).find(v => 'vol:' + v.name === r.id);
    const kindle = r.group === 'disk' && /kindle/i.test(r.label || r.id);
    if (kindle) { list.push({ id: r.id, type: 'local', root: r.id, label: 'Kindle', icon: '📖', online: true, home: 'documents', kind: 'disk', kindle: true, email: '', acct: null,
      quick: [{ l: 'الكتب', p: 'documents' }, { l: 'كل الملفات', p: '' }], sub: 'قارئ Kindle · كابل' + (vol ? ' · حرة ' + fsize(vol.free) : '') }); continue; }
    list.push({ id: r.id, type: 'local', root: r.id, label: r.group === 'disk' ? r.label.replace('💾 ', '') : r.group === 'network' ? r.label.replace('🌐 ', '') : r.label, icon: kind === 'cloud' ? '☁️' : kind === 'disk' ? '💾' : kind === 'network' ? '🌐' : '🖥️', online: true, home: '', kind, email: r.email || '', used: r.used ?? null, total: r.total ?? vol?.total ?? null, free: r.free ?? vol?.free ?? null, fs: r.fs || '', writable: r.writable, acct: r.group === 'rclone' ? r.id.slice(3) : null,
      quick: kind === 'home' ? QUICK_HOME.map(([l, p]) => ({ l, p })) : [], sub: (kind === 'disk' || kind === 'network') && vol ? `${kind === 'network' ? 'شبكة · ' : ''}حرة ${fsize(vol.free)}` : kind === 'cloud' ? (r.group === 'rclone' ? [r.kind, r.email].filter(Boolean).join(' · ') || 'حساب سحابي مباشر' : 'متزامن') : 'ملفاتك' });
  }
  return list;
}
/* ---------- المفضلة: ملفات ومجلدات مثبّتة، تُحفظ داخل الأداة على الكمبيوتر ---------- */
let favList = [], readyOps = [];
async function loadReadyOps() { try { const r = (await api('/api/migrate')).rules; const sig = JSON.stringify(r); if (sig !== loadReadyOps.sig) { loadReadyOps.sig = sig; readyOps = r; renderSources(); try { renderAuto(); } catch (_) {} } } catch (_) {} }
const getFavs = () => favList;
const isFav = (id, path) => favList.some(f => !f.under && (f.id === id || f.src === id) && f.path === path);
async function saveFavs() { try { favList = (await api('/api/favorites', { favs: favList })).favs; } catch (e) { note('تعذّر حفظ المفضلة: ' + e.message); } renderSources(); updateFavBtns(); }
function toggleFavPaths(p, ents) {
  if (!p?.src || !ents.length) return; const id = p.src.id, all = ents.every(e => isFav(id, e.path));
  if (all) favList = favList.filter(f => !(f.id === id && !f.under && ents.some(e => e.path === f.path)));
  else ents.forEach(e => { if (!isFav(id, e.path)) favList.push({ id, path: e.path, name: e.name || e.path.split('/').filter(Boolean).pop() || p.src.label, is_dir: !!e.is_dir, added: Date.now() }); });
  saveFavs(); note(all ? `أُزيل ${ents.length} من المفضلة.` : `أُضيف ${ents.length} إلى المفضلة ⭐`);
}
function togglePin(src, e) {
  if (!src || !e) return;
  const exists = favList.some(f => f.under && (f.id === src.id || f.src === src.id) && f.path === e.path);
  if (exists) {
    favList = favList.filter(f => !(f.under && (f.id === src.id || f.src === src.id) && f.path === e.path));
    note('أُزيل التثبيت من الشريط الجانبي.');
  } else {
    favList.push({ id: src.id, src: src.id, path: e.path, name: e.name || e.path.split('/').filter(Boolean).pop() || src.label, is_dir: true, under: true, added: Date.now() });
    note('📌 ثُبّت المجلد تحت المصدر في الشريط الجانبي.');
  }
  saveFavs();
}
const toggleFav = p => p?.src && toggleFavPaths(p, [{ path: p.cur, name: p.cur.split('/').filter(Boolean).pop() || p.src.label, is_dir: true }]);
function updateFavBtns() { allPanes().forEach(p => { const b = p.q('.pfav'); if (b) { const on = p.src && isFav(p.src.id, p.cur); b.textContent = on ? '★' : '☆'; b.classList.toggle('on', !!on); b.title = on ? 'إزالة هذا المجلد من المفضلة' : 'إضافة هذا المجلد إلى المفضلة'; } }); }
async function openFav(f) {
  if (!P) return; if (f.is_dir) return P.go(f.id, f.path);
  const s = sources.find(x => x.id === f.id), parent = s ? parentOf(s, f.path) : null;
  P.reveal({ path: f.path, folder: parent ?? '', is_dir: false, name: f.name }, f.id);
}
async function loadFavs() {
  try { favList = (await api('/api/favorites')).favs; } catch (_) {}
  try { const old = JSON.parse(store.get('favs', '[]')); if (!favList.length && old.length) { favList = old.map(o => ({ id: o.id, path: o.path, name: o.label || o.path, is_dir: true })); await saveFavs(); } if (old.length) store.set('favs', '[]'); } catch (_) {}
  renderSources(); updateFavBtns();
}
function sourceUsage(s) {
  if (!['disk', 'network', 'cloud'].includes(s.kind) || !s.total || s.total <= 0) return null;
  let used = s.used, free = s.free;
  if (used == null && free != null) used = s.total - free;
  if (free == null && used != null) free = s.total - used;
  if (used == null) return null;
  const pct = Math.max(0, Math.min(100, Math.round(used / s.total * 100)));
  const extra = [s.fs ? s.fs.toUpperCase() : '', s.writable === false ? 'للقراءة فقط' : ''].filter(Boolean).join(' · ');
  return { pct, free: Math.max(0, free), total: s.total, extra, text: `المستخدم ${fsize(used)} من ${fsize(s.total)} (${pct}%) · حرّة ${fsize(Math.max(0, free))}` };
}
function renderSources() {
  const box = $('#sources'); box.replaceChildren();
  const side = box, coll = store.get('side', 'open') === 'min'; side.classList.toggle('collapsed', coll);
  const head = el('div', undefined, 'sidehead'), tg = el('button', coll ? '▸' : '◂'); tg.title = coll ? 'توسيع الشريط الجانبي' : 'طيّ الشريط الجانبي'; tg.onclick = () => { store.set('side', coll ? 'open' : 'min'); renderSources(); }; head.append(tg);
  box.append(head);
  if (!coll) { const hd = el('div', undefined, 'sidegrip'); hd.title = 'اسحب لتغيير العرض · نقر مزدوج لإعادته'; hd.ondblclick = () => setSideW(240); hd.onpointerdown = ev => { ev.preventDefault(); hd.setPointerCapture(ev.pointerId); const r = box.getBoundingClientRect(), rtl = getComputedStyle(box).direction === 'rtl'; hd.onpointermove = e2 => setSideW(rtl ? r.right - e2.clientX : e2.clientX - r.left); hd.onpointerup = () => { hd.onpointermove = null; }; }; box.append(hd); }
  let folded = []; try { folded = JSON.parse(store.get('foldg', '[]')); } catch (_) {}
  const cs = P?.src;
  const favs = getFavs().filter(f => !f.under);
  {
    const foldF = folded.includes('المفضلة'), fh = el('h4', (foldF ? '▸ ' : '▾ ') + '⭐ المفضلة'); fh.onclick = () => { store.set('foldg', JSON.stringify(foldF ? folded.filter(x => x !== 'المفضلة') : [...folded, 'المفضلة'])); renderSources(); }; box.append(fh);
    // اسحب أي مجلد أو ملف إلى هنا فيُثبَّت في الشريط ويبقى محفوظًا ولو فُصل الجهاز
    const fz = el('div', favs.length ? 'أفلت هنا للتثبيت' : 'اسحب مجلدًا إلى هنا لتثبيته', 'favdrop' + (favs.length ? '' : ' empty'));
    const pin = ev => { ev.preventDefault(); fz.classList.remove('dropt'); if (!dragInfo) return; const p = dragInfo.pane, ents = dragInfo.paths.map(x => p.entries.find(e => e.path === x) || { path: x, name: x.split('/').filter(Boolean).pop(), is_dir: true });
      toggleFavPaths(p, ents.filter(e => !isFav(dragInfo.srcId, e.path))); };
    fz.addEventListener('dragover', ev => { if (dragInfo) { ev.preventDefault(); ev.dataTransfer.dropEffect = 'link'; fz.classList.add('dropt'); } });
    fz.addEventListener('dragleave', () => fz.classList.remove('dropt')); fz.addEventListener('drop', pin);
    fh.addEventListener('dragover', ev => { if (dragInfo) { ev.preventDefault(); fz.classList.add('dropt'); } }); fh.addEventListener('drop', pin);
    box.append(fz);
    if (!foldF) favs.forEach(f => {
      const s = sources.find(x => x.id === f.id);
      const row = el('div', undefined, 'src fav' + (P?.src?.id === f.id && P.cur === f.path ? ' act' : '') + (s?.online ? '' : ' off')); row.title = `${f.name}\n${s ? s.label : f.id}${s?.online ? '' : ' (غير متصل)'}\n${f.path}`;
      const tx = el('div', undefined, 'tx'); tx.append(el('b', f.name), el('small', s ? s.label : f.id));
      const x = el('button', '✕', 'x'); x.title = 'إزالة من المفضلة'; x.onclick = ev => { ev.stopPropagation(); favList = favList.filter(y => !(y.id === f.id && y.path === f.path)); saveFavs(); };
      row.append(el('span', f.is_dir ? '📁' : '📄', 'ic'), tx, x); row.onclick = () => openFav(f);
      row.draggable = true; row.ondragstart = ev => { ev.dataTransfer.effectAllowed = 'copy'; ev.dataTransfer.setData('application/x-zajel', JSON.stringify({ items: [{ place: f.id, path: f.path, name: f.name, is_dir: !!f.is_dir }] })); };
      if (f.is_dir) dropTarget(row, () => s?.online ? { src: s, dir: f.path } : null); box.append(row);
    });
  }
  { const sy = el('a', '🔁 المزامنة التلقائية…', 'q conn'); sy.onclick = syncDialog; box.append(sy); }
  const groups = [['الأجهزة', s => s.type === 'adb' || s.type === 'ios' || s.type === 'kindle' || s.kindle], ['السحابة', s => s.kind === 'cloud'], ['الأقراص الخارجية', s => s.kind === 'disk' && !s.kindle], ['الشبكة', s => s.kind === 'network'], ['هذا الكمبيوتر', s => s.kind === 'home']];
  groups.forEach(([title, f]) => {
    const items = sources.filter(f); if (!items.length && title !== 'الشبكة') return;
    const fold = folded.includes(title), h4 = el('h4', (fold ? '▸ ' : '▾ ') + title); h4.onclick = () => { store.set('foldg', JSON.stringify(fold ? folded.filter(x => x !== title) : [...folded, title])); renderSources(); }; box.append(h4);
    if (fold) return;
    if (title === 'السحابة') { const c = el('a', '＋ إضافة حساب سحابي…', 'q conn'); c.onclick = addCloudAccount; box.append(c); }
    if (title === 'الشبكة') { const c = el('a', '＋ اتصال بخادم…', 'q conn'); c.onclick = networkConnect; box.append(c); }
    items.forEach(s => {
      const row = el('div', undefined, 'src' + (s.type === 'adb' || s.type === 'ios' ? ' dev' : '') + (cs?.id === s.id ? ' act' : '') + (s.online ? '' : ' off')); row.dataset.sid = s.id; row.title = `${s.label}${s.acct ? '\nالاسم داخل الأداة: ' + s.acct : ''}${s.email ? '\nالحساب: ' + s.email : ''}\n${s.sub || ''}`;
      const isDev = s.type === 'adb' || s.type === 'ios' || s.type === 'kindle', hasSub = isDev && (s.quick.length || s.id === 'phone' || favList.some(f => f.under && (f.id === s.id || f.src === s.id))), open = hasSub && devOpen().includes(s.id);
      const tx = el('div', undefined, 'tx'); tx.append(el('b', s.label), el('small', s.sub || ''));
      row.append(el('span', s.icon, 'ic'), tx);
      const usage = sourceUsage(s); if (usage) row.title += `\n${usage.text}`;
      if (hasSub) { const cv = el('span', open ? '▾' : '▸', 'devcaret'); cv.title = open ? 'طيّ الأقسام' : 'إظهار الأقسام'; cv.onclick = ev => { ev.stopPropagation(); toggleDev(s.id); }; row.append(cv); }
      if (s.type === 'adb' && !s.acct && s.kind !== 'disk') { const mb = el('button', '⋯', 'mb'); mb.title = 'خيارات هذا الجهاز'; mb.onclick = ev => { ev.stopPropagation(); ev.preventDefault(); const r = mb.getBoundingClientRect(); cleanMenu({ clientX: r.left, clientY: r.bottom + 4 }, s); }; row.append(mb); }
      if (s.acct || s.kind === 'disk') {
        const mb = el('button', '⋯', 'mb'); mb.title = 'خيارات هذا المصدر';
        mb.onclick = ev => { ev.stopPropagation(); ev.preventDefault(); const r = mb.getBoundingClientRect(), pos = { clientX: r.left, clientY: r.bottom + 4 }; s.acct ? acctMenu(pos, s) : diskMenu(pos, s); };
        row.append(mb);
      }
      if (s.acct) row.oncontextmenu = ev => { ev.preventDefault(); ev.stopPropagation(); acctMenu(ev, s); };
      if (s.kind === 'disk' || s.kind === 'network') {
        const ej = el('button', '⏏', 'ej'); ej.title = 'إخراج بأمان'; ej.onclick = ev => { ev.stopPropagation(); ejectDisk(s); }; row.append(ej);
        row.oncontextmenu = ev => { ev.preventDefault(); diskMenu(ev, s); };
      }
      const n = selUnion(s.id).size; if (n) row.append(el('span', String(n), 'selbadge'));
      row.append(el('span', undefined, 'sdot' + (s.online ? ' on' : '')));
      row.onclick = () => { if (hasSub && !(open && cs?.id !== s.id)) toggleDev(s.id); P && P.openSource(s.id); }; row.ondblclick = ev => { ev.preventDefault(); P && P.go(s.id, s.home); }; // نقرتان = المجلد الرئيسي
      dropTarget(row, () => s.online ? { src: s, dir: s.home } : null);
      row.draggable = true; row.ondragstart = ev => { ev.dataTransfer.effectAllowed = 'copy'; ev.dataTransfer.setData('application/x-zajel', JSON.stringify({ items: [{ place: s.id, path: s.home || '', name: s.label, is_dir: true, source: true }] })); };
      box.append(row);
      if (usage) { const bar = el('div', undefined, 'ubar' + (usage.pct >= 90 ? ' crit' : usage.pct >= 75 ? ' warn' : '')); bar.title = usage.text;
        const fill = el('i'); fill.style.width = usage.pct + '%'; bar.append(fill);
        const meta = el('div', undefined, 'umeta'); meta.append(el('span', usage.pct + '% ممتلئ'), el('span', 'حرّة ' + fsize(usage.free)), el('span', 'من ' + fsize(usage.total)), ...(usage.extra ? [el('span', usage.extra)] : []));
        const wrap = el('div', undefined, 'usage'); wrap.append(bar, meta); wrap.onclick = () => row.click(); box.append(wrap); }
      if (isDev ? open : cs?.id === s.id) s.quick.forEach(q => { const a = el('a', q.l, 'q' + (P.cur === q.p ? ' act' : '')); a.onclick = () => P.go(s.id, q.p); dropTarget(a, () => ({ src: s, dir: q.p })); box.append(a); });
      const pins = favList.filter(f => f.under && (f.id === s.id || f.src === s.id));
      if (isDev ? open : true) {
        pins.forEach(pf => {
          const isAct = (P?.src?.id === s.id && P.cur === pf.path);
          const a = el('a', undefined, 'q pin-item' + (isAct ? ' act' : ''));
          a.title = `${pf.name}\n${pf.path}`;
          a.append(el('span', '📌', 'pin-ic'), el('span', pf.name));
          a.onclick = () => { if (P) P.go(s.id, pf.path); };
          a.oncontextmenu = ev => {
            ev.preventDefault(); ev.stopPropagation(); closeCtx();
            const cm = el('div', undefined, 'ctx');
            const d = el('div', '📌 إزالة التثبيت');
            d.onclick = () => {
              closeCtx();
              favList = favList.filter(y => !(y.under && (y.id === s.id || y.src === s.id) && y.path === pf.path));
              saveFavs();
              note('أُزيل التثبيت من الشريط الجانبي.');
            };
            cm.append(d);
            document.body.append(cm);
            cm.style.left = Math.min(ev.clientX, innerWidth - 210) + 'px';
            cm.style.top = Math.min(ev.clientY, innerHeight - 80) + 'px';
          };
          dropTarget(a, () => s.online ? ({ src: s, dir: pf.path }) : null);
          box.append(a);
        });
      }
      if (open && s.id === 'phone' && s.online) { const ap = el('a', '📦 التطبيقات', 'q'); ap.onclick = () => document.querySelector('[data-v="apps"]')?.click(); box.append(ap); }
    });
    if (title === 'الأجهزة' && cs && (cs.id === 'phone' || cs.type === 'ios') && cs.online) {
      box.append(el('h4', 'عمليات جاهزة'));
      if (cs.id === 'phone') {
        const a1 = el('a', '🗂️ كل صور الهاتف', 'q'), a2 = el('a', '🎧 كل التسجيلات', 'q');
        a1.onclick = addAllImages; a2.onclick = () => { cats.add('التسجيلات الصوتية'); updateSummary(); note('أُضيف مجلد التسجيلات الصوتية كاملًا.'); }; box.append(a1, a2);
      }
      (readyOps || []).filter(r => cs.type === 'ios' ? r.dev === 'ios' && (!r.udid || 'ios:' + r.udid === cs.id) : r.dev !== 'ios').forEach(r => {
        const a = el('a', '▶ ' + r.name + (r.enabled ? ' ⟳' : ''), 'q'); a.title = `${r.src} ← ${r.dst_label || r.dst}${r.enabled ? '\nتلقائي عند الوصل' : ''}`;
        a.onclick = async () => { try { await api('/api/migrate/run', { id: r.id }); note('بدأت: ' + r.name); loadOps(); } catch (e) { note(e.message); } }; box.append(a);
      });
      const a3 = el('a', '＋ عملية جاهزة / ترحيل تلقائي…', 'q'); a3.onclick = () => migrateDialog(cs.id); box.append(a3);
    }
  });
  try { window.PBspace?.(); } catch (_) {}
}
const CLOUD_KINDS = [['drive', 'Google Drive', '🟢'], ['onedrive', 'OneDrive', '🔵'], ['dropbox', 'Dropbox', '🟦'], ['box', 'Box', '📦'], ['pcloud', 'pCloud', '☁️'], ['iclouddrive', 'iCloud Drive (حساب آبل آخر)', '🍎']];
function addCloudAccount() {
  openModal(m => {
    let kind = 'drive'; const used = () => cloudRoots.filter(r => r.group === 'rclone').map(r => r.id.slice(3));
    const nameFor = k => { let n = k, i = 2; while (used().includes(n)) n = k + i++; return n; };
    m.append(el('h3', '☁️ إضافة حساب سحابي'), el('p', 'اختر الخدمة، ثم يفتح المتصفح صفحتها الرسمية لتضغط «سماح». الأداة لا ترى كلمة مرورك. كرّر العملية لإضافة أكثر من حساب من الخدمة نفسها. iCloud الخاص بهذا الماك يظهر تلقائيًا؛ ولإضافة حساب آبل آخر اختر iCloud: تُفتح نافذة الطرفية لتكتب فيها كلمة مرورك ورمز التحقق بنفسك (الأداة لا تراهما).', 'muted'));
    const grid = el('div'); grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:10px 0';
    const inp = el('input'); inp.type = 'text'; inp.style.direction = 'ltr'; inp.value = nameFor(kind);
    const tiles = CLOUD_KINDS.map(([k, label, ic]) => {
      const t = el('button', ic + ' ' + label, 'btn'); t.style.padding = '14px 8px';
      t.onclick = () => { kind = k; inp.value = nameFor(k); tiles.forEach(x => x.classList.remove('pri')); t.classList.add('pri'); };
      if (k === kind) t.classList.add('pri'); grid.append(t); return t;
    });
    const ok = el('button', 'ربط الحساب', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    cancel.onclick = closeModal;
    ok.onclick = async () => {
      const name = inp.value.trim(); try { await api('/api/cloud/add', { kind, name }); } catch (e) { note('تعذّرت الإضافة: ' + e.message); inp.style.borderColor = 'var(--err)'; return; }
      closeModal(); note(kind === 'iclouddrive' ? 'فُتحت نافذة الطرفية: أجب عن أسئلتها (معرّف آبل، كلمة المرور، رمز التحقق).' : 'فُتح المتصفح لتفويض الحساب… بعد أن تضغط «سماح» يظهر هنا تلقائيًا.');
      for (let i = 0; i < 100; i++) { await new Promise(r => setTimeout(r, 3000)); try { cloudRoots = (await api('/api/cloud/roots')).roots; } catch (_) {} if (cloudRoots.some(r => r.id === 'rc:' + name)) { sourceChanged(); renderSources(); note('✓ أُضيف الحساب: ' + name); return; } }
      note('لم يكتمل التفويض خلال ثلاث دقائق؛ أعد المحاولة.');
    };
    m.append(grid, el('small', 'اسم قصير للحساب (لاتيني):', 'muted'), inp); acts.append(cancel, ok); m.append(acts);
  });
}
const sideW = () => +store.get('sw', 240);
function setSideW(w) { w = Math.max(150, Math.min(420, Math.round(w))); store.set('sw', String(w)); document.documentElement.style.setProperty('--sw', w + 'px'); }
document.documentElement.style.setProperty('--sw', sideW() + 'px');
setTimeout(() => refreshRoots(), 7000);
async function refreshRoots() { try { cloudRoots = (await api('/api/cloud/roots')).roots; } catch (_) {} sourceChanged(); renderSources(); }
async function ejectDisk(s) {
  const name = s.id.slice(4); note('جارٍ إخراج «' + name + '» بأمان…');
  allPanes().forEach(p => { if (p.src?.id === s.id) p.openSource('home'); });
  try { const r = await api('/api/eject', { name }); note('⏏ ' + r.message); } catch (e) { note(e.message); }
  refreshRoots();
}
function cleanSource(s) {
  initCleanRoots();
  const val = s.type === 'adb' ? 'dev:' + s.id : [...croot.options].some(o => o.value === s.id) ? s.id : (cloudRoots.find(r => r.label === s.label || r.id === 'rc:' + s.acct) || {}).id;
  if (!val || ![...croot.options].some(o => o.value === val)) { note('تعذّر تحديد هذا المصدر للتنظيف.'); return; }
  setTarget(val, val.startsWith('dev:') ? '/sdcard' : ''); document.querySelector('[data-v="clean"]').click(); runScan('analyze');
}
function cleanMenu(ev, s) {
  closeCtx(); const m = el('div', undefined, 'ctx'), d = el('div', '🧹 تنظيف هذا القسم'); d.onclick = () => { closeCtx(); cleanSource(s); }; m.append(d);
  document.body.append(m); m.style.left = Math.min(ev.clientX, innerWidth - 220) + 'px'; m.style.top = Math.min(ev.clientY, innerHeight - 80) + 'px';
}
function diskMenu(ev, s) {
  closeCtx(); const m = el('div', undefined, 'ctx'), name = s.id.slice(4);
  const add = (t, f, cls) => { const d = el('div', t, cls); d.onclick = () => { closeCtx(); f(); }; m.append(d); };
  add('🧹 تنظيف هذا القسم', () => cleanSource(s)); m.append(el('hr'));
  add('⏏ إخراج بأمان', () => ejectDisk(s));
  if (s.kind === 'disk') { add('✏️ إعادة تسمية القرص…', () => renameDisk(s)); m.append(el('hr')); add('🧹 فرمتة القرص…', () => eraseDisk(s), 'dg'); }
  document.body.append(m); m.style.left = Math.min(ev.clientX, innerWidth - 220) + 'px'; m.style.top = Math.min(ev.clientY, innerHeight - 160) + 'px';
}
function acctMenu(ev, s) {
  closeCtx(); const m = el('div', undefined, 'ctx');
  const add = (t, f, cls) => { const d = el('div', t, cls); d.onclick = () => { closeCtx(); f(); }; m.append(d); };
  add('🧹 تنظيف هذا القسم', () => cleanSource(s)); m.append(el('hr'));
  add('ⓘ خصائص الحساب', () => acctInfo(s)); add('✏️ إعادة تسمية…', () => acctRename(s)); add('🔄 إعادة تسجيل الدخول', async () => { try { await api('/api/cloud/account', { action: 'reconnect', name: s.acct }); note('فُتح المتصفح لإعادة التفويض.'); } catch (e) { note(e.message); } });
  m.append(el('hr')); add('🗑 إزالة الحساب من الأداة…', () => acctRemove(s), 'dg');
  document.body.append(m); m.style.left = Math.min(ev.clientX, innerWidth - 230) + 'px'; m.style.top = Math.min(ev.clientY, innerHeight - 190) + 'px';
}
async function acctInfo(s) {
  openModal(m => m.append(el('h3', s.label), el('p', 'جارٍ جلب المعلومات…', 'muted')));
  let d = {}; try { d = await api('/api/cloud/account', { action: 'info', name: s.acct }); } catch (e) { note(e.message); }
  openModal(m => {
    m.append(el('h3', s.label)); const kv = (k, v) => { const r = el('div', undefined, 'kv'); r.append(el('span', k), el('span', v)); m.append(r); };
    kv('الاسم داخل الأداة', s.acct); kv('البريد', d.email || 'غير معروف'); if (d.owner) kv('صاحب الحساب', d.owner);
    if (d.used != null) kv('المستخدم', fsize(d.used)); if (d.total) kv('السعة', fsize(d.total)); if (d.total && d.used != null) kv('المتاح', fsize(d.total - d.used));
    const ok = el('button', 'تم', 'btn pri'), acts = el('div', undefined, 'acts'); ok.onclick = closeModal; acts.append(ok); m.append(acts);
  });
}
function acctRename(s) {
  openModal(m => {
    m.append(el('h3', 'إعادة تسمية الحساب'), el('p', 'الاسم يظهر في القائمة فقط؛ لا يغيّر شيئًا في حسابك السحابي. حروف لاتينية وأرقام وشرطة.', 'muted'));
    const inp = el('input'); inp.type = 'text'; inp.value = s.acct; inp.style.direction = 'ltr';
    const ok = el('button', 'تسمية', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts'); cancel.onclick = closeModal;
    ok.onclick = async () => { try { await api('/api/cloud/account', { action: 'rename', name: s.acct, new: inp.value.trim() }); closeModal(); note('تمت إعادة التسمية.'); allPanes().forEach(p => { if (p.src?.id === s.id) p.openSource('home'); }); refreshRoots(); } catch (e) { note(e.message); inp.style.borderColor = 'var(--err)'; } };
    acts.append(cancel, ok); m.append(inp, acts); setTimeout(() => inp.select(), 50);
  });
}
function acctRemove(s) {
  openModal(m => {
    m.append(el('h3', 'إزالة «' + s.label + '»'), el('p', 'تُزال بطاقة الدخول من هذه الأداة فقط. ملفاتك في السحابة تبقى كما هي، وتستطيع إعادة إضافة الحساب لاحقًا.', 'muted'));
    const ok = el('button', 'إزالة', 'btn danger'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts'); cancel.onclick = closeModal;
    ok.onclick = async () => { try { await api('/api/cloud/account', { action: 'delete', name: s.acct }); closeModal(); allPanes().forEach(p => { if (p.src?.id === s.id) p.openSource('home'); }); note('أُزيل الحساب.'); refreshRoots(); } catch (e) { note(e.message); } };
    acts.append(cancel, ok); m.append(acts);
  });
}
function renameDisk(s) {
  const name = s.id.slice(4);
  openModal(m => {
    m.append(el('h3', 'إعادة تسمية القرص'), el('p', `الاسم الحالي: ${name}`, 'muted'));
    const inp = el('input'); inp.type = 'text'; inp.value = name; const ok = el('button', 'تسمية', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    cancel.onclick = closeModal; ok.onclick = async () => { try { const r = await api('/api/disk-rename', { name, new: inp.value.trim() }); closeModal(); note(r.message); } catch (e) { note(e.message); } refreshRoots(); };
    acts.append(cancel, ok); m.append(inp, acts); setTimeout(() => inp.select(), 50);
  });
}
function eraseDisk(s) {
  const name = s.id.slice(4); let fs = 'ExFAT';
  openModal(m => {
    m.append(el('h3', '🧹 فرمتة «' + name + '»'));
    const w = el('div', undefined, 'warnbox'); w.append(el('b', '⚠️ سيُمسح كل ما على هذا القرص نهائيًا ولا يمكن استرجاعه.'), el('div', 'تأكد من نسخ ملفاتك أولًا. كل الأقسام الأخرى على القرص نفسه لا تتأثر.')); m.append(w);
    const grid = el('div'); grid.style.cssText = 'display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin:10px 0';
    const kinds = [['ExFAT', 'ExFAT — يعمل على ماك وويندوز (للقرص الكبير)'], ['FAT32', 'FAT32 — للفلاشة الصغيرة، كل الأجهزة'], ['Mac', 'Mac OS Extended — لماك فقط'], ['APFS', 'APFS — لماك الحديث (SSD)']];
    const tl = kinds.map(([k, t]) => { const b = el('button', t, 'btn'); b.style.cssText = 'padding:10px;font-size:12px;text-align:start'; b.onclick = () => { fs = k; tl.forEach(x => x.classList.remove('pri')); b.classList.add('pri'); }; if (k === fs) b.classList.add('pri'); grid.append(b); return b; });
    const nn = el('input'); nn.type = 'text'; nn.value = name; nn.placeholder = 'الاسم الجديد';
    const cf = el('input'); cf.type = 'text'; cf.placeholder = `للتأكيد اكتب اسم القرص الحالي: ${name}`;
    const ok = el('button', 'فرمتة', 'btn danger'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts'); ok.disabled = true;
    cf.oninput = () => { ok.disabled = cf.value !== name; };
    cancel.onclick = closeModal; ok.onclick = async () => { ok.disabled = true; ok.textContent = 'جارٍ الفرمتة…'; try { const r = await api('/api/disk-erase', { name, fs, new: nn.value.trim(), confirm: cf.value }); closeModal(); note(r.message); } catch (e) { note(e.message); closeModal(); } refreshRoots(); };
    acts.append(cancel, ok); m.append(grid, nn, cf, acts);
  });
}
function sourceChanged() {
  sources = buildSources();
  const sig = JSON.stringify(sources.map(s => [s.id, s.label, s.online, s.sub, s.serial]));
  if (sig === srcSig) return; srcSig = sig;
  allPanes().forEach(p => {
    if (!p.src) return; const n = sources.find(s => s.id === p.src.id); if (!n) return;
    const was = p.src.online; p.src = n;
    if (n.online !== was) n.online ? p.go(n.id, p.cur || n.home, false) : p.showState();
  });
  renderSources(); initCleanRoots();
}

/* ---------- قراءة المجلدات (موحّدة) ---------- */
function archParent(p) { const [a, inner] = p.split('::'), i = (inner || '').replace(/\/$/, ''); if (!i) return a.split('/').slice(0, -1).join('/'); return a + '::' + i.split('/').slice(0, -1).join('/'); }
const parentOf = (s, p) => (s.type === 'ios' || s.type === 'kindle') ? (p === '/' || !p ? null : (p.slice(0, p.lastIndexOf('/')) || '/')) : s.type === 'adb' ? (p === '/sdcard' || !p ? null : p.slice(0, p.lastIndexOf('/')) || '/sdcard') : (p?.includes('::') ? archParent(p) : (p ? p.split('/').slice(0, -1).join('/') : null));
async function listDir(s, path) {
  if (s.type === 'kindle') { const d = await api(`/api/kindle/browse?path=${encodeURIComponent(path || '/')}`); return { entries: d.entries, path: d.path, warning: '' }; }
  if (s.type === 'ios') { const d = await api(`/api/ios/browse?udid=${encodeURIComponent(s.udid)}&path=${encodeURIComponent(path || '/')}`); return { entries: d.entries, path: d.path, warning: '' }; }
  if (s.type === 'adb') {
    const d = await api(`/api/browse?path=${encodeURIComponent(path)}&serial=${encodeURIComponent(s.serial || '')}`);
    return { entries: d.entries, path: d.path, warning: d.warning };
  }
  const d = await api(`/api/cloud/browse?root=${encodeURIComponent(s.root)}&path=${encodeURIComponent(path)}`);
  return { entries: d.entries, path: d.path, warning: '' };
}
const btn = (t, f, cls = 'btn') => { const b = el('button', t, cls); b.onclick = f; return b; };
const srcRef = s => s.type === 'kindle' ? { type: 'kindle' } : s.type === 'adb' ? { type: 'adb', serial: s.serial } : s.type === 'ios' ? { type: 'ios', udid: s.udid } : { type: 'local', root: s.root };
let iosDevices = [], kindleDev = null;
async function loadKindle() { try { const k = (await api('/api/kindle/status')).kindle; const sig = JSON.stringify(k); if (sig !== loadKindle.sig) { loadKindle.sig = sig; kindleDev = k; sourceChanged(); renderSources(); } } catch (_) {} }
setInterval(loadKindle, 5000); setTimeout(loadKindle, 1000);
async function loadIos() { try { const d = (await api('/api/ios/devices')).devices; const sig = JSON.stringify(d.map(x => [x.udid, x.locked, x.asleep, x.name, x.conn, x.free])); if (sig !== loadIos.sig) { loadIos.sig = sig; iosDevices = d; sourceChanged(); renderSources(); } } catch (_) {} }
setInterval(loadIos, 6000); setTimeout(loadIos, 800); setInterval(loadReadyOps, 8000); setTimeout(loadReadyOps, 900);
const chainOf = (s, p) => {
  if (s.type === 'local' && p.includes('::')) {
    const [a, inner] = p.split('::'), out = chainOf(s, a.split('/').slice(0, -1).join('/')); out.push(a + '::'); let acc = '';
    inner.split('/').filter(Boolean).forEach(x => { acc += (acc ? '/' : '') + x; out.push(a + '::' + acc); }); return out;
  } const out = s.type === 'adb' ? ['/sdcard'] : ['']; let acc = out[0]; const rel = s.type === 'adb' ? p.replace(/^\/sdcard\/?/, '') : p; rel.split('/').filter(Boolean).forEach(x => { acc += (acc && acc !== '' ? '/' : '') + x; out.push(acc); }); return out; };

/* ---------- القوائم المنسدلة العامة (بديل الأشرطة) ---------- */
document.querySelectorAll('.mbtn').forEach(b => b.onclick = e => { e.stopPropagation(); const pop = b.nextElementSibling; const was = pop.hidden; document.querySelectorAll('.menupop').forEach(p => p.hidden = true); pop.hidden = !was; });
document.addEventListener('click', e => { if (!e.target.closest('.menupop')) document.querySelectorAll('.menupop').forEach(p => p.hidden = true); });

/* ---------- المصغّرات ---------- */
const THUMBABLE = /\.(jpe?g|png|webp|gif|bmp|heic|heif|tiff?|avif|pdf|docx?|xlsx?|pptx?|mp4|mov|m4v|3gp|mkv|txt|rtf|csv|md)$/i;
const thumbObserver = new IntersectionObserver(items => items.forEach(it => {
  if (!it.isIntersecting) return;
  const box = it.target; thumbObserver.unobserve(box);
  const img = new Image(); img.onload = () => { box.textContent = ''; box.append(img); }; img.src = box.dataset.src;
}), { rootMargin: '200px' });
function thumbUrl(p, e) {
  const s = p.src; if (!s || !THUMBABLE.test(e.name) || e.is_dir || e.size == null || e.size > 40 * 1024 * 1024) return null;
  if (s.type === 'adb') return s.serial ? `/api/thumb?serial=${encodeURIComponent(s.serial)}&path=${encodeURIComponent(e.path)}&v=${e.mod}` : null;
  if (s.type === 'kindle') return null;
  if (s.type === 'ios') return `/api/ithumb?udid=${encodeURIComponent(s.udid)}&path=${encodeURIComponent(e.path)}&v=${e.mod}`;
  return `/api/lthumb?root=${encodeURIComponent(s.root)}&path=${encodeURIComponent(e.path)}&v=${e.mod}`;
}
function thumb(p, e, size) {
  const box = el('span', undefined, 'th' + (e.is_dir ? ' dir' : '')); box.style.width = size + 'px'; box.style.height = size + 'px';
  if (e.is_dir) { box.textContent = '📁'; return box; }
  const ext = (e.name.split('.').pop() || '').slice(0, 4).toUpperCase();
  box.textContent = EXT.img.test(e.name) ? '🖼️' : EXT.vid.test(e.name) ? '🎬' : EXT.aud.test(e.name) ? '🎵' : EXT.arc.test(e.name) ? '📦' : ext;
  const u = thumbUrl(p, e); if (u) { box.dataset.src = u; thumbObserver.observe(box); }
  return box;
}

/* ---------- الأقسام ووجهة الحفظ ---------- */
// قسم «نقل وإنقاذ المساحات»: يُنشأ هنا (التبويب + الحاوية) ويرسم محتواه sections.js
(() => {
  if ($('#v-rescue')) return;
  const tabs = document.querySelector('.tab[data-v="servers"]'); if (!tabs) return;
  const t = el('span', '🛟 نقل وإنقاذ المساحات', 'tab'); t.dataset.v = 'rescue'; tabs.after(t);
  const v = el('div', undefined, 'view'); v.id = 'v-rescue';
  const pg = el('div', undefined, 'page wide'); pg.id = 'rs-page'; v.append(pg);
  $('#v-servers').after(v);
})();
document.querySelectorAll('.tab').forEach(t => t.onclick = () => {
  document.querySelectorAll('.tab').forEach(x => x.classList.remove('on')); t.classList.add('on');
  document.body.dataset.sec = t.dataset.v; $('#secBtn').textContent = t.textContent + ' ▾'; $('#secMenu .menupop').hidden = true;
  document.querySelectorAll('.view').forEach(v => v.classList.remove('on')); $('#v-' + t.dataset.v).classList.add('on');
  if (t.dataset.v === 'apps' && !apps) loadApps();
  if (t.dataset.v === 'servers') window.loadServersView?.();
  if (t.dataset.v === 'phone') window.loadPhoneView?.();
  if (t.dataset.v === 'rescue') window.loadRescueView?.();
});
async function initDest() {
  const { items } = await api('/api/destinations');
  const saved = (dest.value && dest.value !== '__other') ? dest.value : store.get('dest', '');
  dest.replaceChildren();
  items.forEach(i => { const o = el('option', i.label); o.value = i.path; dest.append(o); });
  const other = el('option', 'مجلد آخر…'); other.value = '__other'; dest.append(other);
  if (saved && items.some(i => i.path === saved)) dest.value = saved;
  dest.dataset.prev = dest.value;
}
dest.onchange = async () => {
  if (dest.value !== '__other') { store.set('dest', dest.value); dest.dataset.prev = dest.value; return; }
  picking = true; refreshStart();
  try {
    const r = await api('/api/choose-folder', {});
    if (r.path) { const o = el('option', r.path); o.value = r.path.replace(/\/$/, ''); dest.insertBefore(o, dest.lastChild); dest.value = o.value; store.set('dest', dest.value); }
    else dest.value = dest.dataset.prev;
  } catch (e) { note(e.message); dest.value = dest.dataset.prev; }
  finally { picking = false; dest.dataset.prev = dest.value; refreshStart(); }
};

/* ================= اللوحة (Pane): متصفح مستقل بحالته وواجهته ================= */
const cols = [['name', 'الاسم'], ['kind', 'النوع'], ['size', 'الحجم'], ['mod', 'تاريخ التعديل'], ['added', 'تاريخ الإضافة'], ['chg', 'تغيّر الحالة']];
function check(on, handler) { const c = el('span', on ? '✓' : '', 'ck' + (on ? ' on' : '')); c.onclick = e => { e.stopPropagation(); handler(); }; return c; }
async function copyToClipboard(text) {
  try { if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(text); return; } } catch (_) {}
  const ta = document.createElement('textarea'); ta.value = text; ta.style.position = 'fixed'; ta.style.top = '-9999px'; ta.style.opacity = '0';
  document.body.append(ta); ta.focus(); ta.select(); try { document.execCommand('copy'); } catch (_) {} ta.remove();
}
async function copyPathFor(p, e) {
  if (!p?.src || !e) return;
  let fullPath = '';
  if (p.src.type === 'local' && !p.src.root?.startsWith('rc:')) {
    try {
      const r = await api(`/api/realpath?src=${encodeURIComponent(p.src.root)}&path=${encodeURIComponent(e.path)}`);
      if (r.ok && r.path) fullPath = r.path;
    } catch (_) {}
  }
  if (!fullPath) fullPath = `${p.src.label}:${e.path}`;
  await copyToClipboard(fullPath);
  note('نُسخ المسار');
  document.querySelector('.pathtoast')?.remove();
  const t = el('div', undefined, 'pathtoast'); t.append(el('b', '📋 نُسخ المسار'), el('div', fullPath)); document.body.append(t);
  setTimeout(() => t.classList.add('out'), 2700); setTimeout(() => t.remove(), 3000);
}
function makeDots(pane, e, isCol) {
  const b = el('button', '⋯', 'rmenu'); b.title = 'خيارات';
  b.onclick = ev => {
    ev.stopPropagation(); ev.preventDefault();
    if (pane !== P) setActive(pane);
    if (!pane.S().has(e.path)) { pane.S().clear(); pane.S().add(e.path); }
    pane.cursor = e;
    if (isCol) { pane.renderCols(); updateSummary(); }
    else { pane.rerender(); }
    const r = b.getBoundingClientRect();
    ctxMenu({ clientX: Math.round(r.left), clientY: Math.round(r.bottom + 4) }, e);
  };
  return b;
}

class Pane {
  constructor(opt = {}) {
    this.src = null; this.cur = ''; this.parentPath = null; this.entries = []; this.cursor = null; this.anchor = null;
    this.hist = []; this.histIdx = -1; this.colData = []; this.storage = null;
    this.viewMode = opt.view || store.get('view', 'list'); this.skey = store.get('skey', 'name'); this.desc = store.get('desc', '0') === '1'; this.filt = 'all'; this.query = '';
    this.srch_sort = store.get('srch_sort', 'mod'); this.srch_desc = store.get('srch_desc', '1') === '1';
    this.selBySrc = new Map(); this.stateOn = false; this.search = null; this.sexts = new Set(); this.searchTimer = null; this.prevView = null;
    this.root = $('#paneTpl').content.firstElementChild.cloneNode(true); this.root._pane = this;
    this.bind(); this.buildSearchPop(); this.applyView(); this.syncSort();
  }
  q(s) { return this.root.querySelector(s); }
  S(id) { id = id || this.src?.id; if (!this.selBySrc.has(id)) this.selBySrc.set(id, new Set()); return this.selBySrc.get(id); }
  toggle(path) { const s = this.S(); s.has(path) ? s.delete(path) : s.add(path); }
  bind() {
    this.root.addEventListener('mousedown', () => setActive(this), true);
    this.q('.pback').onclick = () => { if (this.histIdx > 0) { this.histIdx--; const h = this.hist[this.histIdx]; this.go(h.id, h.path, false); } };
    this.q('.pfwd').onclick = () => { if (this.histIdx < this.hist.length - 1) { this.histIdx++; const h = this.hist[this.histIdx]; this.go(h.id, h.path, false); } };
    this.q('.pup').onclick = () => this.parentPath != null && this.go(this.src.id, this.parentPath);
    this.q('.pnew').onclick = () => { setActive(this); newFolder(); };
    this.q('.pfav').onclick = () => { setActive(this); toggleFav(this); };
    this.q('.pq').oninput = e => { this.query = e.target.value; this.rerender(); };
    ['list', 'grid', 'cols'].forEach(k => this.q('.pv' + k).onclick = () => this.setView(k));
    this.q('.pvsync').onclick = e => { e.stopPropagation(); quickSync(this.src, this.cur); };
    this.q('.pszall').onclick = e => { e.stopPropagation(); window.recalcFolderSizes?.(this); note('جارٍ حساب أحجام المجلدات الظاهرة…'); };
    this.q('.pvopts').onclick = e => { e.stopPropagation(); const pop = this.q('.popts'); pop.hidden = !pop.hidden; this.q('.pvopts').classList.toggle('on', !pop.hidden); };
    this.q('.psort').onchange = e => { this.skey = e.target.value; this.syncSort(); this.rerender(); };
    this.q('.pdir').onclick = () => { this.desc = !this.desc; this.syncSort(); this.rerender(); };
    this.q('.ptype').onchange = e => { this.filt = e.target.value; this.rerender(); };
    this.q('.pdate').onchange = e => { this.dfilt = e.target.value; this.q('.pvopts').classList.toggle('on', this.dfilt !== 'all'); this.rerender(); };
    this.q('.phidden').onchange = () => this.rerender();
    this.q('.pq').onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); this.startSearch(); } };
    this.q('.pvext').onclick = e => { e.stopPropagation(); const pop = this.q('.psearch'); pop.hidden = !pop.hidden; this.q('.pvext').classList.toggle('on', !pop.hidden); };
    const body = this.q('.pbody');
    dropTarget(body, () => this.src?.online ? { src: this.src, dir: this.cur } : null, true);
  }
  syncSort() { this.q('.psort').value = this.skey; this.q('.pdir').textContent = this.desc ? '↓' : '↑'; store.set('skey', this.skey); store.set('desc', this.desc ? '1' : '0'); }
  hiddenOk(e) { return this.q('.phidden').checked || !e.name.startsWith('.'); }
  dateOk(e, k) {
    const f = this.dfilt || 'all'; if (f === 'all') return true;
    const key = ['mod', 'chg', 'added', 'born'].includes(k) ? k : 'added', t = e[key] ?? e.mod ?? 0, days = { today: 1, week: 7, month: 30, year: 365 }[f];
    if (f === 'today') { const d0 = new Date(); d0.setHours(0, 0, 0, 0); return t >= d0.getTime(); }
    return t >= Date.now() - days * 86400000;
  }
  typeOk(e) { return this.filt === 'all' || (this.filt === 'dir' ? e.is_dir : kindOf(e) === this.filt); }
  visible() {
    const rf = (this.search && this.rfilter || '').toLowerCase();
    const k = this.search ? (this.srch_sort || 'mod') : this.skey;
    const d = this.search ? (this.srch_desc ?? true) : this.desc;
    return sortEntries(this.entries.filter(e => this.hiddenOk(e) && e.name.toLowerCase().includes(this.query.toLowerCase()) && (!rf || (e.name + ' ' + (e.folder || '')).toLowerCase().includes(rf)) && this.typeOk(e) && this.dateOk(e, k)), k, d);
  }
  currentList() { return this.viewMode === 'cols' ? (this.colData.at(-1)?.entries || []) : this.visible(); }
  openSource(id) { const s = sources.find(x => x.id === id); if (s) this.go(id, store.get('path:' + id, s.home)); }

  async go(id, path, push = true) {
    const s = sources.find(x => x.id === id) || this.src; if (!s) return;
    if (this.search) this.cancelSearch();
    this.src = s;
    if (!s.online) { this.cur = path; this.entries = []; this.showState(); onPaneChanged(this); return; }
    if (this === P) note('جارٍ القراءة…');
    try {
      if (this.viewMode === 'cols') await this.loadChain(path); else {
        const d = await listDir(s, path); this.entries = d.entries; this.cur = d.path; if (this === P) note(d.warning || '');
      }
      this.parentPath = parentOf(s, this.cur); this.cursor = null; this.anchor = null;
      if (push) { this.hist = this.hist.slice(0, this.histIdx + 1); this.hist.push({ id, path: this.cur }); this.histIdx = this.hist.length - 1; }
      store.set('path:' + id, this.cur);
      this.hideState(); this.rerender(); onPaneChanged(this);
      if (s.type === 'adb' && s.serial) api('/api/storage?serial=' + encodeURIComponent(s.serial)).then(i => { storageInfo[id] = i; if (this === P) updateSbar(); }).catch(() => {});
    } catch (e) { if (!this._fallback && path !== s.home && /ليس مجلدًا|غير موجود|No such|not found/i.test(e.message)) { this._fallback = true; try { return await this.go(id, s.home, push); } finally { this._fallback = false; } } this.entries = []; this.showState(e.message); if (this === P) note(e.message); onPaneChanged(this); }
  }
  showState(msg) {
    const c = this.q('.pstate'); c.replaceChildren(); c.classList.add('on'); this.stateOn = true;
    ['.plist', '.pcols', '.pgrid'].forEach(k => this.q(k).style.display = 'none');
    const s = this.src;
    if (msg) { c.append(el('div', '⚠️', 'big'), el('h3', 'تعذّرت القراءة'), el('p', msg), btn('إعادة المحاولة', () => this.go(s.id, this.cur || s.home, false))); }
    else if (s.id === 'phone') { c.append(el('div', '📱', 'big'), el('h3', 'الهاتف غير متصل')); const ol = el('ol'); ['وصّل الهاتف بكابل USB.', 'افتح شاشة الهاتف ووافق على «السماح بتصحيح USB».', 'تأكد أن «تصحيح USB» مفعّل في خيارات المطوّر.'].forEach(t => ol.append(el('li', t))); c.append(ol, btn('إعادة الفحص', refresh)); }
    else if (s.id === 'watch') c.append(el('div', '⌚', 'big'), el('h3', 'الساعة غير متصلة'), el('p', 'فعّل «تصحيح ADB عبر Wi-Fi» في الساعة وأضئ شاشتها، وسيُعاد الوصل تلقائيًا.'), btn('إعدادات الساعة', () => document.querySelector('[data-v="watch"]').click()));
    else if (s.type === 'kindle') c.append(el('div', '📖', 'big'), el('h3', 'افتح قفل شاشة الكيندل'), el('p', 'الكيندل موصول، لكنه لا يفتح ملفاته والشاشة مقفلة. أيقظه وافتح القفل، فيظهر هنا تلقائيًا.'));
    else if (s.type === 'ios') c.append(el('div', '📱', 'big'), el('h3', 'افتح قفل الجهاز'), el('p', 'ثم اضغط «وثوق» إن سُئلت.'), btn('إعادة المحاولة', () => { loadIos.sig = ''; loadIos(); this.go(s.id, s.home, false); }));
    else c.append(el('div', '💾', 'big'), el('h3', 'المصدر غير متاح'));
    this.renderCrumbs();
  }
  hideState() { this.q('.pstate').classList.remove('on'); this.stateOn = false; ['.plist', '.pcols', '.pgrid'].forEach(k => this.q(k).style.display = ''); this.applyView(); }
  refreshNow() { if (this.search) return; if (this.src?.online) return this.go(this.src.id, this.cur, false); }

  /* ---------- البحث الذكي ---------- */
  buildSearchPop() {
    const pop = this.q('.psearch'); pop.replaceChildren();
    pop.append(el('h4', '🔍 بحث ذكي'), el('p', 'اكتب اسمًا أو اختر نوعًا، ثم «ابحث».', 'muted'));
    const groups = el('div', undefined, 'sgroups');
    EXT_GROUPS.forEach(([name, list]) => {
      const c = el('span', name, 'chip'); c.title = list.map(x => '.' + x).join('  ');
      c.onclick = () => { const all = list.every(x => this.sexts.has(x)); list.forEach(x => all ? this.sexts.delete(x) : this.sexts.add(x)); c.classList.toggle('on', !all); };
      groups.append(c);
    });
    const custom = el('input', undefined, 'search pcustom'); custom.placeholder = 'لاحقات أخرى: epub, log';
    this.swords = new Set(); const wbox = el('div', undefined, 'sgroups swords'); wbox.append(el('small', 'داخل الصور:', 'muted'));
    ['لقطات الشاشة', 'أشخاص', 'حيوانات', 'طعام', 'مستندات', 'طبيعة', 'سيارات', 'مبانٍ'].forEach(w => { const c = el('span', w, 'chip'); c.onclick = () => { this.swords.has(w) ? this.swords.delete(w) : this.swords.add(w); c.classList.toggle('on', this.swords.has(w)); }; wbox.append(c); });
    const wfree = el('input', undefined, 'search pwords'); wfree.placeholder = 'كلمات أخرى في الصور: قطط، بحر، كتب'; wbox.append(wfree);
    const sc = el('div', undefined, 'sscope'), mk = (v, t, on) => { const l = el('label'), r = document.createElement('input'); r.type = 'radio'; r.name = 'sc' + Math.random().toString(36).slice(2, 6); r.value = v; r.checked = on; l.append(r, document.createTextNode(' ' + t)); return [l, r]; };
    const [l1, r1] = mk('here', 'هذا المجلد وما تحته', true), [l2, r2] = mk('all', 'المصدر كله', false); r2.name = r1.name; sc.append(l1, l2);
    const btns = el('div', undefined, 'sbtns');
    btns.append(btn('مسح الاختيار', () => { this.sexts.clear(); this.swords.clear(); wfree.value = ''; wbox.querySelectorAll('.chip').forEach(c => c.classList.remove('on')); custom.value = ''; groups.querySelectorAll('.chip').forEach(c => c.classList.remove('on')); }), btn('🔍 ابحث', () => this.startSearch(), 'btn pri'));
    pop.append(groups, custom, wbox, sc, btns);
  }
  async startSearch() {
    const s = this.src; if (!s?.online) return;
    const q = this.q('.pq').value.trim(), custom = (this.q('.pcustom').value || '').split(/[,\s]+/).map(x => x.replace(/^\./, '').toLowerCase()).filter(Boolean);
    const exts = [...new Set([...this.sexts, ...custom])];
    const content = [...this.swords, ...(this.q('.pwords')?.value || '').split(/[،,]/).map(x => x.trim()).filter(Boolean)];
    if (!q && !exts.length && !content.length) { note('اكتب اسمًا أو اختر لاحقة.'); this.q('.psearch').hidden = false; return; }
    this.cancelSearch(); this.q('.psearch').hidden = true; this.q('.pvext').classList.remove('on');
    const scope = this.q('.psearch input[type=radio]:checked')?.value || 'here';
    if (scope === 'multi') { const sids = [...this.q('.psearch .msrc').querySelectorAll('.chip.on')].map(c => c.dataset.sid); if (!sids.length) { note('اختر مصدرًا واحدًا على الأقل.'); return; } multiSearch(q, exts, sids, content); return; }
    let r; try { r = await api('/api/search/start', { src: srcRef(s), path: this.cur, q, exts, scope, content }); } catch (e) { note(e.message); return; }
    this.prevView = this.viewMode; if (this.viewMode === 'cols') { this.viewMode = 'list'; this.applyView(); }
    this.search = { id: r.id, q, exts, scope, state: 'running', count: 0, before: { id: s.id, path: this.cur } };
    this.srch_sort = store.get('srch_sort', 'mod'); this.srch_desc = store.get('srch_desc', '1') === '1';
    this.entries = []; this.cursor = null; this.hideState(); this.rerender();
    this.searchTimer = setInterval(() => this.pollSearch(), 800);
  }
  async pollSearch() {
    const sr = this.search; if (!sr) return;
    try {
      const r = await api('/api/search/job?id=' + sr.id); if (this.search !== sr) return;
      sr.state = r.state; sr.count = r.count; sr.truncated = r.truncated; this.entries = r.entries;
      if (r.state !== 'running') clearInterval(this.searchTimer); if (r.state === 'error') note(r.error);
      this.rerender();
      if (r.to_scan && r.state === 'running' && this === P) $('#sinfo').textContent = `فحص الصور: ${r.scanned || 0} من ${r.to_scan} · وُجد ${r.count}`;
    } catch (e) { clearInterval(this.searchTimer); }
  }
  cancelSearch() { clearInterval(this.searchTimer); if (this.search?.state === 'running') api('/api/search/cancel', { id: this.search.id }).catch(() => {}); this.search = null; }
  exitSearch() {
    const b = this.search?.before, pv = this.prevView; this.cancelSearch();
    if (pv === 'cols' && this.viewMode === 'list') { this.viewMode = 'cols'; this.applyView(); }
    if (b) this.go(b.id, b.path, false);
  }
  async reveal(e, srcId) {
    this.cancelSearch(); const sid = srcId || this.src.id; if (e.is_dir) return this.go(sid, e.path);
    await this.go(sid, e.folder); const hit = this.entries.find(x => x.path === e.path);
    if (hit) { this.S().clear(); this.S().add(hit.path); this.cursor = hit; this.rerender(); this.root.querySelector(`[data-path="${CSS.escape(hit.path)}"]`)?.scrollIntoView({ block: 'center' }); }
  }

  rerender() {
    if (this.stateOn) return;
    this.viewMode === 'cols' ? this.renderCols() : this.viewMode === 'grid' ? this.renderGrid() : this.renderFiles();
    this.renderCrumbs(); updateSummary(); if (this === P) updateSbar();
  }
  renderCrumbs() {
    const cr = this.q('.pcrumbs'); cr.replaceChildren(); const s = this.src; if (!s) return;
    if (this.search) {
      const sr = this.search, box = el('div', undefined, 'srch');
      box.append(el('b', `🔍 نتائج البحث (${this.entries.length}${sr.truncated ? '+' : ''})`), el('span', [sr.q && `«${sr.q}»`, sr.exts.length && sr.exts.map(x => '.' + x).join(' ')].filter(Boolean).join('  ') + (sr.scope === 'all' ? '  · المصدر كله' : ''), 'muted'));
      if (sr.state === 'running') box.append(el('span', undefined, 'spin'));
      const fl = el('input', undefined, 'search rfilter'); fl.placeholder = 'تصفية النتائج…'; fl.value = this.rfilter || ''; fl.oninput = () => { this.rfilter = fl.value; this.renderFiles?.(); this.rerender(); setTimeout(() => { const n = this.q('.rfilter'); if (n && document.activeElement !== n) { n.focus(); n.setSelectionRange(n.value.length, n.value.length); } }, 0); };
      const ssel = el('select', undefined, 'srch-sort');
      [['mod', 'تاريخ التعديل'], ['name', 'الاسم'], ['size', 'الحجم']].forEach(([k, l]) => {
        const o = el('option', l); o.value = k; if (k === (this.srch_sort || 'mod')) o.selected = true; ssel.append(o);
      });
      ssel.onchange = () => { this.srch_sort = ssel.value; store.set('srch_sort', this.srch_sort); this.rerender(); };
      const sdir = btn((this.srch_desc ?? true) ? '↓' : '↑', () => { this.srch_desc = !(this.srch_desc ?? true); store.set('srch_desc', this.srch_desc ? '1' : '0'); this.rerender(); }, 'btn srch-dir');
      sdir.title = 'عكس اتجاه الترتيب';
      const dp = btn('المكررات', () => findDupes(this), 'btn'); dp.title = 'المكررات بالمحتوى بين هذه النتائج'; if (sr.state === 'running') dp.disabled = true;
      box.append(fl, ssel, sdir, dp, btn('✕ إغلاق البحث', () => { this.rfilter = ''; this.exitSearch(); })); cr.append(box); return;
    }
    const r = el('span', s.icon + ' ' + s.label, 'csrc'); r.title = 'تغيير المصدر'; r.onclick = ev => { ev.stopPropagation(); srcMenu(ev, this); }; cr.append(r);
    dropTarget(r, () => s.online ? { src: s, dir: s.home } : null);
    const add = (label, path, arch) => { cr.append(el('i', '‹')); const c = el('span', (arch ? '📦 ' : '') + label); c.onclick = () => this.go(s.id, path); dropTarget(c, () => ({ src: s, dir: path })); cr.append(c); };
    if (s.type === 'local' && this.cur.includes('::')) {
      const [a, inner] = this.cur.split('::'), segs = a.split('/').filter(Boolean); let acc = '';
      segs.forEach((p, i) => { acc += (acc ? '/' : '') + p; add(p, i === segs.length - 1 ? acc + '::' : acc, i === segs.length - 1); });
      let ia = ''; (inner || '').split('/').filter(Boolean).forEach(p => { ia += (ia ? '/' : '') + p; add(p, a + '::' + ia, false); });
      return;
    }
    const rel = s.type === 'adb' ? this.cur.replace(/^\/sdcard\/?/, '') : this.cur; let acc = s.type === 'adb' ? '/sdcard' : '';
    rel.split('/').filter(Boolean).forEach(p => { acc += (acc ? '/' : '') + p; add(p, acc, false); });
    // الأثر: يتذكّر أعمق مسار زرته في هذا الفرع، فيبقى ظاهرًا باهتًا بعد الصعود للأب لتعود إليه بنقرة
    this.trails = this.trails || {}; const tr = this.trails[s.id];
    const under = (a, b) => b === '' || a === b || a.startsWith(b.replace(/\/$/, '') + '/');
    if (!tr || !under(tr, this.cur)) this.trails[s.id] = this.cur;
    const trail = this.trails[s.id];
    if (trail !== this.cur && under(trail, this.cur)) {
      let a2 = this.cur; trail.slice(this.cur.length).split('/').filter(Boolean).forEach(p => { a2 += (a2 && !a2.endsWith('/') ? '/' : '') + p; const pth = a2;
        cr.append(el('i', '‹', 'ahead')); const c = el('span', p, 'ahead'); c.title = 'رجوع إلى ' + p; c.onclick = () => this.go(s.id, pth); dropTarget(c, () => ({ src: s, dir: pth })); cr.append(c); });
    }
    // خريطة المسار: نقرة على المجلد الحالي تعرض كل المستويات
    const cur = [...cr.querySelectorAll('span:not(.ahead)')].pop();
    if (cur) { cur.classList.add('here'); cur.title = 'خريطة المسار'; cur.onclick = ev => { ev.stopPropagation(); pathMap(ev, this); }; }
  }
  paintSel() {
    const s = this.S();
    this.root.querySelectorAll('[data-path]').forEach(n => { const on = s.has(n.dataset.path); n.classList.toggle('sel', on); const ck = n.querySelector('.ck'); if (ck) { ck.classList.toggle('on', on); ck.textContent = on ? '✓' : ''; } });
  }
  renderFiles() {
    const th = this.q('.pthead'); th.replaceChildren(el('th'));
    const colsNow = this.search ? [['name', 'الاسم'], ['folder', 'المجلد'], ['size', 'الحجم'], ['mod', 'تاريخ التعديل']] : cols;
    colsNow.forEach(([k, l]) => {
      const curK = this.search ? (this.srch_sort || 'mod') : this.skey;
      const curD = this.search ? (this.srch_desc ?? true) : this.desc;
      const h = el('th', l + (curK === k ? (curD ? ' ↓' : ' ↑') : ''), curK === k ? 's' : '');
      h.onclick = () => {
        if (this.search) {
          this.srch_sort === k ? this.srch_desc = !this.srch_desc : (this.srch_sort = k, this.srch_desc = (k === 'mod' || k === 'size'));
          store.set('srch_sort', this.srch_sort); store.set('srch_desc', this.srch_desc ? '1' : '0');
        } else {
          this.skey === k ? this.desc = !this.desc : (this.skey = k, this.desc = false); this.syncSort();
        }
        this.rerender();
      };
      th.append(h);
    });
    const list = this.visible(), body = this.q('.prows'); body.replaceChildren();
    if (!list.length) { const tr = el('tr'), td = el('td', this.query ? 'لا توجد نتائج' : 'هذا المجلد فارغ', 'empty'); td.colSpan = 7; tr.append(td); body.append(tr); }
    list.forEach(e => {
      const tr = el('tr', undefined, 'r' + (this.S().has(e.path) ? ' sel' : ''));
      const t0 = el('td'); t0.append(check(this.S().has(e.path), () => { this.toggle(e.path); this.rerender(); }));
      const t1 = el('td'), nm = el('div', undefined, 'nm'); nm.append(thumb(this, e, 24), el('b', e.name), makeDots(this, e)); t1.append(nm);
      if (this.search) { const fc = el('td', e.folder || '/', 'num'); fc.title = e.folder || '/'; fc.style.maxWidth = '260px'; fc.style.overflow = 'hidden'; fc.style.textOverflow = 'ellipsis'; tr.append(t0, t1, fc, el('td', e.is_dir ? '—' : fsize(e.size), 'num'), el('td', fdate(e.mod), 'num')); }
      else tr.append(t0, t1, el('td', typeLabel(e), 'num'), el('td', e.is_dir ? '—' : fsize(e.size), 'num'), el('td', fdate(e.mod), 'num'), el('td', fdate(e.added ?? e.mod), 'num'), el('td', fdate(e.chg), 'num'));
      this.wire(tr, e, list, nm); body.append(tr);
    });
  }
  renderGrid() {
    const box = this.q('.pgrid'); box.replaceChildren(); const list = this.visible();
    if (!list.length) box.append(el('div', this.query ? 'لا توجد نتائج' : 'هذا المجلد فارغ', 'empty'));
    list.forEach(e => {
      const c = el('div', undefined, 'gc' + (this.S().has(e.path) ? ' sel' : '')), th = thumb(this, e, 104); th.style.width = '100%';
      c.append(th, check(this.S().has(e.path), () => { this.toggle(e.path); this.rerender(); }), el('b', e.name), el('small', this.search ? (e.folder || '/') : (e.is_dir ? 'مجلد' : fsize(e.size))), makeDots(this, e));
      this.wire(c, e, list, c); box.append(c);
    });
  }
  wire(node, e, list, dragNode) {
    node.dataset.path = e.path; if (this.cursor && this.cursor.path === e.path) node.classList.add('cur');
    node.onclick = ev => { if (this.modClick(ev, e, list)) return; if (this.S().size) { this.toggle(e.path); this.anchor = e.path; this.cursor = e; this.rerender(); return; } this.cursor = e; showDetails(this, e); this.markCursor(); };
    node.ondblclick = () => { if (this.search) this.reveal(e); else if (e.is_dir) this.go(this.src.id, e.path); else if (e.is_archive) this.go(this.src.id, e.path + '::'); else openPreviewFor(this, e); }; // أي ملف: يفتح في العارض (صورة، نص، PDF، صوت، فيديو، غلاف كتاب…)
    node.oncontextmenu = ev => { ev.preventDefault(); if (!this.S().has(e.path)) { this.S().clear(); this.S().add(e.path); } this.cursor = e; this.rerender(); ctxMenu(ev, e); };
    this.makeDraggable(dragNode, e);
    if (e.is_dir) dropTarget(node, () => this.src?.online ? { src: this.src, dir: e.path } : null, true);
  }
  makeDraggable(node, e) {
    node.draggable = true; const rowEl = node.closest('tr'); if (rowEl && rowEl !== node) { rowEl.draggable = true; rowEl.ondragstart = ev => { if (ev.target === rowEl) node.ondragstart(ev); }; rowEl.ondragend = () => node.ondragend(); }
    node.ondragstart = ev => {
      if (!this.S().has(e.path)) { this.S().clear(); this.S().add(e.path); this.paintSel(); }
      dragInfo = { pane: this, srcId: this.src.id, ref: srcRef(this.src), cur: this.cur, paths: [...this.S()] };
      ev.dataTransfer.effectAllowed = 'copyMove'; ev.dataTransfer.setData('text/plain', dragInfo.paths.join('\n'));
      try { ev.dataTransfer.setData('application/x-zajel', JSON.stringify({ items: dragInfo.paths.map(pp => { const en = this.entries?.find(x => x.path === pp); return { place: this.src.id, path: pp, name: pp.split('/').filter(Boolean).pop() || this.src.label, is_dir: en ? !!en.is_dir : null }; }) })); } catch (_) {}
      if (dragInfo.paths.length > 1) { const g = el('div', `${dragInfo.paths.length} عناصر`, 'dragghost'); document.body.append(g); ev.dataTransfer.setDragImage(g, 20, 14); setTimeout(() => g.remove(), 0); }
      document.body.classList.add('dnd');
    };
    node.ondragend = () => { dragInfo = null; document.body.classList.remove('dnd'); document.querySelectorAll('.dropt').forEach(n => n.classList.remove('dropt')); };
  }
  markCursor() { this.root.querySelectorAll('.cur').forEach(n => n.classList.remove('cur')); if (this.cursor) this.root.querySelector(`[data-path="${CSS.escape(this.cursor.path)}"]`)?.classList.add('cur'); }
  modClick(ev, e, list) {
    const s = this.S();
    if (ev.shiftKey && this.anchor) {
      const a = list.findIndex(x => x.path === this.anchor), b = list.findIndex(x => x.path === e.path);
      if (a >= 0 && b >= 0) { const [lo, hi] = a < b ? [a, b] : [b, a]; if (!(ev.metaKey || ev.ctrlKey)) s.clear(); list.slice(lo, hi + 1).forEach(x => s.add(x.path)); this.cursor = e; this.rerender(); return true; }
    }
    if (ev.metaKey || ev.ctrlKey) { this.toggle(e.path); this.anchor = e.path; this.cursor = e; this.rerender(); return true; }
    this.anchor = e.path; return false;
  }
  /* أعمدة */
  async loadChain(path) {
    const chain = chainOf(this.src, path), res = await Promise.all(chain.map(p => listDir(this.src, p)));
    this.colData = res.map((d, i) => ({ path: d.path, entries: d.entries, open: chain[i + 1] || null }));
    this.cur = res.at(-1).path; this.entries = res.at(-1).entries; if (this === P) note(res.map(d => d.warning).filter(Boolean).join(' '));
  }
  async openInCol(i, e) {
    const target = e.is_archive ? e.path + '::' : e.path, asDir = e.is_dir || e.is_archive;
    this.colData = this.colData.slice(0, i + 1); this.colData[i].open = asDir ? target : null; this.cursor = e;
    if (asDir) { try { const d = await listDir(this.src, target); this.colData.push({ path: d.path, entries: d.entries, open: null }); this.cur = d.path; this.entries = d.entries; this.parentPath = parentOf(this.src, this.cur); store.set('path:' + this.src.id, this.cur); } catch (err) { note(err.message); } }
    showDetails(this, e); this.renderCols(); this.renderCrumbs(); onPaneChanged(this);
  }
  renderCols() {
    const box = this.q('.pcols'); box.replaceChildren();
    this.colData.forEach((c, i) => {
      const col = el('div', undefined, 'col' + (i < this.colData.length - 2 ? ' compact' : ''));
      col.title = c.path ? c.path.split('/').filter(Boolean).pop() || '' : '';
      const list = sortEntries(c.entries.filter(e => this.hiddenOk(e) && e.name.toLowerCase().includes(i === this.colData.length - 1 ? this.query.toLowerCase() : '') && (this.filt === 'all' || e.is_dir || this.typeOk(e))), this.skey, this.desc);
      list.forEach(e => {
        const row = el('div', undefined, 'ci' + (c.open === e.path || c.open === e.path + '::' || this.cursor === e ? ' act' : '') + (this.S().has(e.path) ? ' sel' : ''));
        row.append(check(this.S().has(e.path), () => { this.toggle(e.path); this.renderCols(); updateSummary(); }), thumb(this, e, 22), el('b', e.name), (e.is_dir || e.is_archive) ? el('span', '◂', 'ar') : el('span', fsize(e.size), 'num'), makeDots(this, e, true));
        row.dataset.path = e.path; row.ondblclick = () => { if (!e.is_dir) openPreviewFor(this, e); };
        row.onclick = ev => { if (this.modClick(ev, e, list)) return; if (this.S().size) { this.toggle(e.path); this.anchor = e.path; this.cursor = e; this.renderCols(); updateSummary(); if (this === P) updateSbar(); return; } this.openInCol(i, e); };
        row.oncontextmenu = ev => { ev.preventDefault(); if (!this.S().has(e.path)) { this.S().clear(); this.S().add(e.path); } this.renderCols(); ctxMenu(ev, e); };
        this.makeDraggable(row, e);
        if (e.is_dir) dropTarget(row, () => ({ src: this.src, dir: e.path }), true);
        col.append(row);
      });
      if (!list.length) col.append(el('div', 'لا توجد عناصر', 'empty'));
      box.append(col);
    });
    requestAnimationFrame(() => box.lastElementChild?.scrollIntoView({ inline: 'nearest', block: 'nearest', behavior: 'smooth' }));
  }
  applyView() {
    ['list', 'grid', 'cols'].forEach(k => this.q('.pv' + k).classList.toggle('on', this.viewMode === k));
    this.q('.plist').classList.toggle('off', this.viewMode !== 'list'); this.q('.pcols').classList.toggle('on', this.viewMode === 'cols'); this.q('.pgrid').classList.toggle('on', this.viewMode === 'grid');
  }
  async setView(m) {
    this.viewMode = m; store.set('view', m); this.applyView();
    if (m === 'cols' && this.src?.online) { try { await this.loadChain(this.cur); } catch (e) { note(e.message); } }
    this.rerender(); saveLayout();
  }
}
document.addEventListener('click', e => { document.querySelectorAll('.psearch').forEach(p => { if (!p.hidden && !p.contains(e.target) && !e.target.closest('.pvext')) { p.hidden = true; p.closest('.pane')?.querySelector('.pvext')?.classList.remove('on'); } }); document.querySelectorAll('.popts').forEach(p => { if (!p.hidden && !p.contains(e.target) && !e.target.closest('.pvopts')) { p.hidden = true; p.closest('.pane')?.querySelector('.pvopts')?.classList.remove('on'); } }); });
let storageInfo = {};

/* ---------- السحب والإفلات بين اللوحات والمصادر ---------- */
function dropAction(target, ev) {
  const info = dragInfo; if (!info || !target) return;
  if (target.src.type === 'ios') { note('الآيفون/الآيباد للقراءة فقط: انسخ منه لا إليه.'); return; }
  const sameSrc = info.srcId === target.src.id, move = sameSrc !== !!ev.altKey;    // نفس المصدر: نقل، وغيره: نسخ (Alt يعكس)
  if (sameSrc && info.cur === target.dir) return;                                  // نفس المجلد: لا شيء
  if (sameSrc && info.paths.includes(target.dir)) return;                          // إفلات مجلد على نفسه
  startOp({ kind: move ? 'move' : 'copy', src: info.ref, paths: info.paths, dst: srcRef(target.src), dst_dir: target.dir, policy: 'keep' });
}
function dropTarget(node, getTarget, stop) {
  node.addEventListener('dragover', ev => {
    if (!dragInfo) return; const t = getTarget(); if (!t) return;
    ev.preventDefault(); if (stop) ev.stopPropagation();
    const sameSrc = dragInfo.srcId === t.src.id, move = sameSrc !== !!ev.altKey; ev.dataTransfer.dropEffect = move ? 'move' : 'copy';
    document.querySelectorAll('.dropt').forEach(n => n !== node && n.classList.remove('dropt')); node.classList.add('dropt');
  });
  node.addEventListener('dragleave', ev => { if (!node.contains(ev.relatedTarget)) node.classList.remove('dropt'); });
  node.addEventListener('drop', ev => { ev.preventDefault(); if (stop) ev.stopPropagation(); node.classList.remove('dropt'); dropAction(getTarget(), ev); });
}

/* ---------- التبويبات ---------- */
let wid = 0;
function saveLayout() {
  try { store.set('layout', JSON.stringify({ tabs: workspaces.map(w => ({ active: w.activeIdx || 0, panes: w.panes.map(p => ({ src: p.src?.id, path: p.cur, view: p.viewMode })) })), active: workspaces.indexOf(ws) })); } catch (_) {}
}
function tabTitle(w) { const p = w.panes[w.activeIdx || 0] || w.panes[0]; const name = p.cur ? p.cur.split('/').filter(Boolean).pop() : ''; return (p.src ? p.src.icon + ' ' : '') + (name || p.src?.label || 'جديد') + (w.panes.length === 2 ? '  ⫿' : ''); }
function pathMap(ev, pane) {
  closeCtx(); const s = pane.src, m = el('div', undefined, 'ctx pathmap'), rootP = s.type === 'adb' ? '/sdcard' : '';
  const trail = pane.trails?.[s.id] || pane.cur, rel = s.type === 'adb' ? trail.replace(/^\/sdcard\/?/, '') : trail;
  const levels = [[s.label, rootP]]; let acc = rootP; rel.split('/').filter(Boolean).forEach(p => { acc += (acc && !acc.endsWith('/') ? '/' : '') + p; levels.push([p, acc]); });
  levels.forEach(([name, path], i) => {
    const d = el('div', undefined, path === pane.cur ? 'on' : ''); d.style.paddingInlineStart = (10 + i * 14) + 'px';
    d.append(el('span', i === 0 ? s.icon : (path === pane.cur ? '📂' : '📁')), document.createTextNode(' ' + name)); d.onclick = () => { closeCtx(); pane.go(s.id, path); }; m.append(d);
  });
  document.body.append(m); const r = ev.target.getBoundingClientRect(); m.style.top = (r.bottom + 6) + 'px'; m.style.left = Math.max(8, Math.min(r.left, innerWidth - m.offsetWidth - 8)) + 'px';
}
async function findDupes(pane) {
  const files = pane.visible().filter(e => !e.is_dir && e.size > 0);
  if (files.length < 2) { note('لا ملفات كافية للمقارنة.'); return; }
  openModal(m => m.append(el('h3', 'المكررات'), el('p', `جارٍ مقارنة ${files.length} ملفًا…`, 'muted')));
  let r; try { r = await api('/api/dupes', { src: srcRef(pane.src), items: files.map(e => ({ path: e.path, size: e.size, mod: e.mod, name: e.name })) }); } catch (e) { closeModal(); note(e.message); return; }
  if (!r.groups.length) { openModal(m => { m.append(el('h3', 'لا مكررات'), el('p', 'كل النتائج مختلفة المحتوى.', 'muted')); const a = el('div', undefined, 'acts'); a.append(btn('تم', closeModal, 'btn pri')); m.append(a); }); return; }
  const pick = new Set(); r.groups.forEach(g => g.slice(1).forEach(x => pick.add(x.path)));
  openModal(m => {
    m.classList.add('wide'); const sum = el('p', '', 'muted'); const upd = () => { sum.textContent = `${r.groups.length} مجموعة · محدد ${pick.size} · يوفّر ${fsize(r.groups.flat().filter(x => pick.has(x.path)).reduce((a, x) => a + x.size, 0))}`; };
    m.append(el('h3', 'المكررات في النتائج'), sum);
    const list = el('div', undefined, 'dupelist');
    r.groups.forEach(g => { const gb = el('div', undefined, 'dg'); gb.append(el('div', `${fsize(g[0].size)} × ${g.length}`, 'dgh'));
      g.forEach((x, i) => { const row = el('label', undefined, 'dr'), ck = document.createElement('input'); ck.type = 'checkbox'; ck.checked = pick.has(x.path);
        ck.onchange = () => { ck.checked ? pick.add(x.path) : pick.delete(x.path); upd(); };
        row.append(ck, el('b', x.name || x.path.split('/').pop()), el('small', x.path.split('/').slice(0, -1).join('/') || '/'), el('span', i === 0 ? 'الأقدم' : fdate(x.mod), 'muted')); gb.append(row); });
      list.append(gb); });
    m.append(list); upd();
    const acts = el('div', undefined, 'acts');
    const sel = btn('تحديدها في القائمة', () => { const S = pane.S(); S.clear(); pick.forEach(p => S.add(p)); closeModal(); pane.rerender(); note(`حُدّد ${pick.size} ملفًا؛ انقلها أو احذفها من الأزرار.`); }, 'btn');
    const del = btn('حذف المحدد', () => { if (!pick.size) return; const paths = [...pick]; const go = () => { closeModal(); startOp({ kind: 'delete', src: srcRef(pane.src), paths, confirm: true }); paths.forEach(p => { const i = pane.entries.findIndex(e => e.path === p); if (i >= 0) pane.entries.splice(i, 1); }); pane.rerender(); };
      if (pane.src.type === 'adb') openModal(m2 => { m2.append(el('h3', `حذف ${paths.length} ملفًا نهائيًا من الجهاز`)); typedConfirm(m2, '', go, 'حذف نهائي'); }); else go(); }, 'btn danger');
    acts.append(btn('إغلاق', closeModal, 'btn'), sel, del); m.append(acts);
  });
}
/* منتقي المجلدات: يعرض مجلدات أي مصدر (الهاتف، الكمبيوتر، الأقراص، السحابة) للتنقل والاختيار */
/* ---------- منتقي المجلدات: أعمدة مثل Finder + بحث في المعروض + بحث عميق بالاسم ---------- */
async function folderPicker(box, sid, path, onPick) {
  const s = sources.find(x => x.id === sid); box.replaceChildren(el('div', 'جارٍ القراءة…', 'muted fpwait'));
  if (!s?.online) { box.replaceChildren(el('div', 'المصدر غير متصل.', 'muted fpwait')); return; }
  const root = s.type === 'adb' ? '/sdcard' : s.type === 'ios' || s.type === 'kindle' ? '/' : '';
  const cache = new Map(), join = (a, n) => a === '' ? n : a.endsWith('/') ? a + n : a + '/' + n;
  const dirsOf = async p => { if (!cache.has(p)) { const d = await listDir(s, p); cache.set(p, d.entries.filter(e => e.is_dir && !e.name.startsWith('.')).sort((x, y) => (x.label || x.name).localeCompare(y.label || y.name, 'ar'))); } return cache.get(p); };
  // سلسلة الأعمدة من الجذر حتى المسار المطلوب
  const chainOf = p => { const out = [root]; let acc = root; const rest = (root && p.startsWith(root) ? p.slice(root.length) : p).split('/').filter(Boolean); rest.forEach(x => { acc = join(acc, x); out.push(acc); }); return out; };
  let sel = path || root, q = '';
  const top = el('div', undefined, 'fptop'), search = el('input', undefined, 'search fpq'); search.placeholder = 'ابحث عن مجلد… (Enter = في كل المكان)';
  const cols = el('div', undefined, 'fpcols'), foot = el('div', undefined, 'fpfoot'), results = el('div', undefined, 'fpres'); results.hidden = true;
  const mk = el('button', '📁＋ مجلد جديد', 'btn fpnew'); mk.title = 'إنشاء مجلد جديد داخل المجلد المحدد';
  mk.onclick = async ev => { ev.preventDefault(); const name = (prompt('اسم المجلد الجديد داخل: ' + label(sel)) || '').trim(); if (!name) return;
    try { const d = await runOpWait({ kind: 'mkdir', src: srcRef(s), parent: sel, name }); const made = (String(d.detail || '').replace(/^أُنشئ:\s*/, '') || name); cache.delete(sel); pick(join(sel, made)); render(); note('أُنشئ المجلد: ' + made); } catch (x) { note('تعذّر إنشاء المجلد: ' + x.message); } };
  top.append(search, mk); box.replaceChildren(top, results, cols, foot);
  const label = p => p === root ? s.label : s.label + ' / ' + (root && p.startsWith(root) ? p.slice(root.length) : p).replace(/^\/+/, '').replace(/^@apps\/?/, 'تطبيقات/');
  const pick = p => { sel = p; foot.textContent = '✓ ' + label(p); onPick(p, s); };
  let gen = 0;
  async function render(scrollEnd = true) {
    const my = ++gen, chain = chainOf(sel); cols.replaceChildren();
    for (let i = 0; i < chain.length; i++) {
      const col = el('div', undefined, 'fpcol'); cols.append(col); col.append(el('div', 'جارٍ…', 'muted fpwait'));
      let list; try { list = await dirsOf(chain[i]); } catch (e) { col.replaceChildren(el('div', e.message, 'err fpwait')); break; }
      if (my !== gen) return; // رسمٌ أحدث بدأ
      col.replaceChildren(); const f = q.toLowerCase(), shown = f ? list.filter(e => (e.label || e.name).toLowerCase().includes(f)) : list;
      if (!shown.length) col.append(el('div', f ? 'لا تطابق' : 'لا مجلدات', 'muted fpwait'));
      shown.forEach(e => { const r = el('div', undefined, 'fprow' + (chain[i + 1] === e.path ? ' on' : '')); r.append(el('span', '📁'), el('span', e.label || e.name, 'fpn'), el('i', '‹')); r.title = e.label || e.name;
        r.onclick = () => { pick(e.path); render(); }; col.append(r); });
    }
    if (scrollEnd) cols.scrollLeft = getComputedStyle(cols).direction === 'rtl' ? -cols.scrollWidth : cols.scrollWidth;
  }
  search.oninput = () => { q = search.value.trim(); results.hidden = true; render(false); };
  search.onkeydown = async ev => {
    if (ev.key !== 'Enter') return; ev.preventDefault(); const term = search.value.trim(); if (!term) return;
    results.hidden = false; results.replaceChildren(el('div', 'جارٍ البحث في كل ' + s.label + '…', 'muted fpwait'));
    try {
      let job = await api('/api/search/start', { src: srcRef(s), path: root, q: term, exts: [], scope: 'all' });
      for (let k = 0; k < 120 && job.state === 'running'; k++) { await new Promise(r => setTimeout(r, 700)); job = await api('/api/search/job?id=' + job.id); }
      const found = (job.entries || []).filter(e => e.is_dir).slice(0, 80); results.replaceChildren();
      if (!found.length) results.append(el('div', 'لم أجد مجلدًا بهذا الاسم.', 'muted fpwait'));
      found.forEach(e => { const r = el('div', undefined, 'fprow'); r.append(el('span', '📁'), el('span', e.name, 'fpn'), el('small', label(e.folder || root).replace(s.label, '').replace(/^ \/ /, '') || s.label)); r.onclick = () => { results.hidden = true; search.value = ''; q = ''; pick(e.path); render(); }; results.append(r); });
    } catch (e) { results.replaceChildren(el('div', e.message, 'err fpwait')); }
  };
  pick(sel); render();
}
// اختيار أنواع الملفات: قائمة منسدلة بفئات، لكل فئة صناديق لاحقاتها؛ لا اختيار = كل الأنواع
const TYPE_CATS = [['🖼 صور', 'jpg jpeg png heic heif webp gif bmp tiff dng raw'], ['🎬 فيديو', 'mp4 mov m4v mkv avi 3gp webm'], ['🎵 صوتيات', 'mp3 m4a aac wav ogg opus flac amr 3ga'],
  ['📄 مستندات', 'pdf doc docx txt rtf odt pages md xls xlsx csv ppt pptx'], ['📚 كتب', 'epub azw azw3 mobi fb2 djvu'], ['🗜 أرشيف', 'zip rar 7z tar gz'], ['📦 تطبيقات', 'apk apks xapk']];
function typePicker() {
  // صف واحد: كل نوع = صندوق + كلمة + سهم؛ السهم يفتح قائمة صيغه بصناديقها
  const wrap = el('div', undefined, 'tpick'), on = new Set(), other = el('input'); other.type = 'text'; other.placeholder = 'صيغ أخرى'; other.className = 'tpother'; other.style.direction = 'ltr';
  const closeAll = () => wrap.querySelectorAll('.tppop').forEach(p => p.hidden = true);
  TYPE_CATS.forEach(([t, list]) => { const exts = list.split(' '), cat = el('div', undefined, 'tpcat'), cb = document.createElement('input'); cb.type = 'checkbox';
    const pop = el('div', undefined, 'tppop'); pop.hidden = true; const boxes = [];
    const sync = () => { const n = boxes.filter(b => b.checked).length; cb.checked = n > 0; cb.indeterminate = n > 0 && n < boxes.length; cat.classList.toggle('on', n > 0); };
    exts.forEach(x => { const l = el('label'), c = document.createElement('input'); c.type = 'checkbox'; c.onchange = () => { c.checked ? on.add(x) : on.delete(x); sync(); }; boxes.push(c); l.append(c, el('span', x)); pop.append(l); });
    cb.onchange = () => { boxes.forEach((c, k) => { c.checked = cb.checked; cb.checked ? on.add(exts[k]) : on.delete(exts[k]); }); sync(); };
    const nm = el('span', t.replace(/^\S+\s/, ''), 'tpname'); nm.onclick = () => { cb.checked = !cb.checked; cb.onchange(); };
    const arr = el('button', '▾', 'tparr'); arr.title = 'الصيغ'; arr.onclick = ev => { ev.preventDefault(); ev.stopPropagation(); const was = pop.hidden; closeAll(); pop.hidden = !was; };
    pop.onclick = ev => ev.stopPropagation(); cat.append(cb, nm, arr, pop); wrap.append(cat); });
  wrap.append(other); document.addEventListener('click', closeAll);
  wrap.exts = () => [...on, ...other.value.split(',').map(x => x.trim().replace(/^\./, '').toLowerCase()).filter(Boolean)]; return wrap;
}
async function migrateDialog(devId) {
  if (typeof devId !== 'string') devId = (cs?.type === 'ios' ? cs.id : 'phone');
  let st; try { st = await api('/api/migrate'); } catch (e) { note(e.message); return; }
  let rules = st.rules;
  const save = async () => { try { rules = (await api('/api/migrate', { rules })).rules; loadReadyOps.sig = ''; loadReadyOps(); } catch (e) { note(e.message); } };
  const draw = () => openModal(m => {
    m.classList.add('wide', 'migmodal'); m.append(el('h3', '🔄 العمليات الجاهزة والترحيل التلقائي'));
    const list = el('div', undefined, 'miglist');
    if (!rules.length) list.append(el('div', 'لا قواعد بعد.', 'muted'));
    rules.forEach((r, i) => {
      const row = el('div', undefined, 'migrow' + (r.enabled ? '' : ' off'));
      const tg = document.createElement('input'); tg.type = 'checkbox'; tg.checked = r.enabled; tg.title = 'تلقائي عند وصل الجهاز'; tg.onchange = async () => { r.enabled = tg.checked; await save(); draw(); };
      const tx = el('div', undefined, 'mtx'); tx.append(el('b', r.name), el('small', `${r.dev === 'ios' ? (srcOf('ios:' + r.udid)?.label || 'iPhone/iPad') + ': ' : ''}${r.src.replace('/sdcard/', '').replace('/@apps/', 'تطبيق: ')}  ←  ${r.dst_label || (r.dst || '').replace(/^\/Users\/[^/]+/, '~')}${r.content?.length ? '  · صور: ' + r.content.join('، ') : ''}`));
      const badge = el('span', r.mode === 'move' ? 'نقل' : 'نسخ', 'mbadge ' + r.mode), cnt = el('span', `${st.counts?.[r.id] || 0} مُرحّل`, 'muted');
      const run = btn('تشغيل الآن', async () => { await api('/api/migrate/run', { id: r.id }); note('بدأ الترحيل: ' + r.name); loadOps(); closeModal(); }, 'btn');
      const del = btn('✕', async () => { rules.splice(i, 1); await save(); draw(); }, 'btn'); del.title = 'حذف القاعدة';
      row.append(tg, tx, badge, cnt, run, del); list.append(row);
    });
    m.append(list);
    // قاعدة جديدة
    const f = el('div', undefined, 'migform'); f.append(el('h4', 'عملية جديدة'));
    const devs = sources.filter(x => x.id === 'phone' || x.type === 'ios'), devSel = document.createElement('select');
    devs.forEach(x => { const o = el('option', x.label + (x.online ? '' : ' (غير متصل)')); o.value = x.id; devSel.append(o); }); devSel.value = devs.some(x => x.id === devId) ? devId : 'phone';
    const dev = () => srcOf(devSel.value), isIos = () => dev()?.type === 'ios', droot = () => isIos() ? '/' : '/sdcard';
    const srcSel = document.createElement('select'), srcIn = el('input'); srcIn.type = 'hidden'; const pick = el('div', undefined, 'fpick'); pick.hidden = true;
    const fillSrc = () => { srcSel.replaceChildren(); (isIos() ? dev().quick.map(q => [q.l, q.p]) : QUICK_PHONE).forEach(([l, p]) => { const o = el('option', l); o.value = p; srcSel.append(o); }); const oc = el('option', 'مجلد آخر…'); oc.value = ''; srcSel.append(oc); srcSel.value = isIos() ? '/DCIM' : '/sdcard/Recordings'; pick.hidden = true; srcIn.value = ''; };
    fillSrc(); devSel.onchange = () => { fillSrc(); seg.hidden = isIos(); if (isIos()) mode = 'copy'; };
    srcSel.onchange = () => { pick.hidden = !!srcSel.value; if (!srcSel.value) folderPicker(pick, devSel.value, droot(), p => { srcIn.value = p; }); };
    const nm = el('input'); nm.type = 'text'; nm.placeholder = 'اسم العملية (اختياري)';
    const words = new Set(), cw = el('div', undefined, 'cwords'), cin = el('input'); cin.type = 'text'; cin.placeholder = 'أو اكتب كلمات: قطط، بحر…';
    ['لقطات الشاشة', 'أشخاص', 'حيوانات', 'طعام', 'مستندات', 'طبيعة', 'سيارات', 'مبانٍ'].forEach(w => { const b = btn(w, () => { words.has(w) ? words.delete(w) : words.add(w); b.classList.toggle('pri', words.has(w)); }, 'btn chip'); cw.append(b); }); cw.append(cin);
    const allWords = () => [...words, ...cin.value.split(/[،,]/).map(x => x.trim()).filter(Boolean)];
    const auto = document.createElement('input'); auto.type = 'checkbox'; auto.checked = true; const autoL = el('label', undefined, 'chk'); autoL.append(auto, el('span', 'تلقائي كلما وُصل الجهاز'));
    let dst = null; const dstSel = document.createElement('select'), dpick = el('div', undefined, 'fpick');
    const o0 = el('option', 'اختر الوجهة…'); o0.value = ''; dstSel.append(o0);
    sources.filter(s => s.type !== 'adb' && s.online).forEach(s => { const o = el('option', (s.kind === 'cloud' ? '☁ ' : s.kind === 'disk' ? '💾 ' : s.kind === 'network' ? '🌐 ' : '🖥 ') + s.label + (s.email ? ' — ' + s.email : '')); o.value = s.id; dstSel.append(o); });
    dpick.hidden = true;
    dstSel.onchange = () => { dst = null; dpick.hidden = !dstSel.value; if (dstSel.value) folderPicker(dpick, dstSel.value, '', (p, s) => { dst = { root: s.root, path: p, label: s.label + (p ? ' / ' + p : '') }; }); };
    const dstB = el('div'); dstB.append(dstSel, dpick);
    let mode = 'move'; const seg = el('div', undefined, 'seg2'); const mk = (v, t) => { const b = btn(t, () => { mode = v; seg.querySelectorAll('button').forEach(x => x.classList.toggle('pri', x === b)); }, 'btn' + (v === mode ? ' pri' : '')); seg.append(b); };
    mk('move', 'نقل (يُحذف من الهاتف بعد التحقق)'); mk('copy', 'نسخ (يبقى في الهاتف)');
    const ex = typePicker();
    const grid = el('div', undefined, 'mgrid'); const lab = (t, n) => { const l = el('label'); l.append(el('span', t), n); grid.append(l); };
    const srcWrap = el('div'); srcWrap.append(srcSel, srcIn, pick); lab('الاسم', nm); lab('الجهاز', devSel); lab('من', srcWrap); lab('إلى', dstB); lab('الطريقة', seg); { const l = el('div', undefined, 'mlab'); l.append(el('span', 'الأنواع'), ex); grid.append(l); } /* ليس <label>: وإلا قلبت كل نقرة صندوقَ «صور» الأول */ lab('محتوى الصور', cw); lab('التشغيل', autoL); seg.hidden = isIos(); if (isIos()) mode = 'copy';
    f.append(grid);
    const add = btn('إضافة', async () => {
      const src = srcSel.value || srcIn.value.trim(); if (!src || src === droot()) { note('ادخل مجلدًا داخل الجهاز ثم أضف القاعدة.'); return; } if (!isIos() && !src.startsWith('/sdcard/')) { note('اختر مجلدًا في الهاتف.'); return; } if (!dst) { note('اختر مجلد الوجهة.'); return; }
      rules.push({ name: nm.value.trim() || (srcSel.value ? srcSel.selectedOptions[0].textContent : src.split('/').pop()), src, dev: isIos() ? 'ios' : 'adb', udid: isIos() ? dev().udid : '', dst_root: dst.root, dst_path: dst.path, dst_label: dst.label, mode: isIos() ? 'copy' : mode, exts: ex.exts(), content: allWords(), enabled: auto.checked });
      await save(); st = await api('/api/migrate'); draw(); note(auto.checked ? 'أُضيفت؛ تعمل كلما وُصل الجهاز.' : 'أُضيفت إلى العمليات الجاهزة.');
    }, 'btn pri');
    f.append(add); m.append(f);
    const acts = el('div', undefined, 'acts'); acts.append(btn('تم', closeModal, 'btn')); m.append(acts);
  });
  draw();
}
/* ---------- المزامنة التلقائية: مجلد واحد في عدة أماكن ---------- */
/* ---------- مزامنة مجلد بخطوتين: المجلد ← الوجهة (أو عدة وجهات) ← ابدأ ---------- */
function syncLocOf(sx, path) {
  const p = String(path || '');
  if (sx.type === 'ios') return { kind: 'ios', root: sx.udid, path: p.replace(/^\/+/, ''), label: sx.label + ' / ' + p.replace(/^\/?@apps\/?/, 'تطبيق: ') + (/^\/?@apps/.test(p) ? '' : ' (قراءة فقط)') };
  if (sx.id === 'phone') return { kind: 'adb', root: '', path: p.replace(/^\/+/, ''), label: 'الهاتف / ' + p.replace('/sdcard/', '') };
  return { kind: 'local', root: sx.root, path: p.replace(/^\/+/, ''), label: sx.label + (p ? ' / ' + p : '') };
}
const syncOk = x => x.online && (x.type === 'ios' || x.id === 'phone' || (x.type === 'local' && x.root));
async function quickSync(srcS, path) {
  if (!srcS || !syncOk(srcS)) { note('هذا المكان لا يدعم المزامنة (الساعة وكيندل خارج المزامنة).'); return; }
  if (!path || path === '/' || path === '/sdcard' || path === '/@apps') { note('اختر مجلدًا داخل المكان لا جذره.'); return; }
  const name = String(path).replace(/\/+$/, '').split('/').pop().replace(/^@apps$/, srcS.label) || srcS.label;
  let existing = []; try { existing = (await api('/api/sync')).groups; } catch (e) { note(e.message); return; }
  const srcLoc = syncLocOf(srcS, path), dests = [], made = [];
  openModal(m => {
    m.classList.add('wide'); m.append(el('h3', '🔁 مزامنة مجلد'));
    const sline = el('div', undefined, 'syncloc'); sline.append(el('span', '📁 ' + srcLoc.label)); m.append(el('small', 'المجلد المراد مزامنته', 'muted'), sline);
    const dbox = el('div', undefined, 'synclocs'); m.append(el('small', 'الوجهات (إلى أين تُزامَن)', 'muted'), dbox);
    const err = el('div', undefined, 'err'); err.style.margin = '6px 0';
    const drawD = () => { dbox.replaceChildren(); dests.forEach((l, k) => { const r = el('div', undefined, 'syncloc'); r.append(el('span', '⇄ ' + l.label)); r.append(btn('✕', () => { dests.splice(k, 1); drawD(); }, 'btn')); dbox.append(r); }); if (!dests.length) dbox.append(el('small', 'اختر مكانًا ثم مجلدًا فيه، ثم «إضافة هذه الوجهة».', 'muted')); };
    const sel = document.createElement('select'); const o0 = el('option', '＋ اختر الوجهة: قرص / سحابة / جهاز…'); o0.value = ''; sel.append(o0);
    sources.filter(syncOk).forEach(x => { const o = el('option', (x.type === 'ios' ? (x.cls === 'iPad' ? '📟 ' : '📱 ') : x.id === 'phone' ? '📱 ' : x.kind === 'cloud' ? '☁ ' : x.kind === 'disk' ? '💾 ' : x.kind === 'network' ? '🌐 ' : '🖥 ') + x.label + (x.email ? ' — ' + x.email : '')); o.value = x.id; sel.append(o); });
    const pick = el('div', undefined, 'fpick'); pick.hidden = true;
    const inner = document.createElement('input'); inner.type = 'checkbox'; inner.checked = true;
    const innerL = el('label', undefined, 'chk'); innerL.append(inner, el('span', `أنشئ داخل المجلد المختار مجلدًا باسم «${name}» (موصى به)`)); innerL.hidden = true;
    let cand = null, candSrc = null;
    const addD = btn('إضافة هذه الوجهة', () => {
      err.textContent = ''; if (cand == null) { err.textContent = 'اختر مجلدًا في الوجهة أولًا.'; return; }
      let p = String(cand).replace(/\/+$/, ''), prefix = '';
      if (candSrc.type === 'ios') { if (!/^\/?@apps\/.+/.test(p)) { err.textContent = 'في الآيفون/الآيباد اختر مجلدًا داخل «ملفات التطبيقات».'; return; } }
      if (inner.checked) p = (p && p !== '/' ? p + '/' : candSrc.id === 'phone' && !p ? '/sdcard/' : '') + name;
      else if (!p || p === '/' || p === '/sdcard') { err.textContent = 'اختر مجلدًا لا الجذر، أو فعّل إنشاء مجلد داخله.'; return; }
      const l = syncLocOf(candSrc, p);
      if (candSrc.id === 'phone' && !('/' + l.path).startsWith('/sdcard/')) l.path = 'sdcard/' + l.path.replace(/^sdcard\/?/, '');
      const clash = [srcLoc, ...dests].find(x => x.kind === l.kind && x.root === l.root && (x.path === l.path || l.path.startsWith(x.path + '/') || x.path.startsWith(l.path + '/')));
      if (clash) { err.textContent = 'هذا المكان مكرر أو متداخل مع: ' + clash.label; return; }
      dests.push(l); cand = null; sel.value = ''; pick.hidden = innerL.hidden = addD.hidden = true; drawD();
    }, 'btn'); addD.hidden = true;
    sel.onchange = () => { cand = null; err.textContent = ''; pick.hidden = innerL.hidden = addD.hidden = !sel.value; if (!sel.value) return; const sid = sel.value, sx = sources.find(x => x.id === sid);
      folderPicker(pick, sid, sid === 'phone' ? '/sdcard' : sx.type === 'ios' ? '/@apps' : '', (p, sx2) => { candSrc = sx2 || sx; cand = p; }); };
    m.append(sel, pick, innerL, addD, dbox.nextSibling ? '' : '', err);
    drawD();
    const opt = el('div', undefined, 'migform');
    const dir = document.createElement('select'); [['two', '⇄ في الاتجاهين: الأحدث يغلب (الموصى به)'], ['one', '→ اتجاه واحد: نسخة احتياطية، الأصل لا يتغير']].forEach(([v, t]) => { const o = el('option', t); o.value = v; dir.append(o); });
    const del = document.createElement('input'); del.type = 'checkbox'; const delL = el('label', undefined, 'chk'); delL.append(del, el('span', 'انقل الحذف أيضًا (إلى السلة دائمًا)'));
    const hid = document.createElement('input'); hid.type = 'checkbox'; const hidL = el('label', undefined, 'chk'); hidL.append(hid, el('span', 'ضمّن الملفات المخفية (إعدادات Obsidian وإضافاتها). تُفعَّل تلقائيًا لخزائن Obsidian'));
    const ev = document.createElement('select'); [[5, 'كل 5 دقائق'], [15, 'كل 15 دقيقة'], [30, 'كل 30 دقيقة'], [60, 'كل ساعة'], [360, 'كل 6 ساعات']].forEach(([v, t]) => { const o = el('option', t); o.value = v; ev.append(o); }); ev.value = 30;
    opt.append(el('small', 'تبدأ فورًا، ثم تلقائيًا عند أي تغيير وعند وصل الجهاز/القرص، وبمدة احتياطية:', 'muted'), dir, delL, hidL, ev); m.append(opt);
    const createdBox = el('div', undefined, 'okmsg'); m.append(createdBox);
    const go = btn('ابدأ المزامنة', async () => {
      err.textContent = ''; if (!dests.length) { err.textContent = 'أضف وجهة واحدة على الأقل.'; return; }
      go.disabled = true;
      try {
        const g = { name: name + ' ⇄ ' + dests.map(d => d.label.split(' / ')[0]).join('، '), locations: [srcLoc, ...dests], every: +ev.value, enabled: true, deletes: del.checked, mode: dir.value, hidden: hid.checked ? true : undefined };
        existing = (await api('/api/sync', { groups: [...existing, g] })).groups; const gid = existing[existing.length - 1].id;
        await api('/api/sync/run', { id: gid }); loadAuto.sig = ''; loadAuto(); loadOps();
        made.push(g.name); createdBox.replaceChildren(...made.map(n => el('div', '✔ بدأت: ' + n)));
        dests.length = 0; drawD();
      } catch (e) { err.textContent = e.message; }
      go.disabled = false;
    }, 'btn pri');
    const acts = el('div', undefined, 'acts'); acts.append(btn('إغلاق', closeModal, 'btn'), go); m.append(acts);
  });
}
/* ---------- قسم «المزامنات»: الفئة والحالة وآخر مرة وتحليل بياني ---------- */
const SY_STATE = { ok: ['✔ سليمة', 'ok'], running: ['⏳ تعمل الآن', 'running'], waiting: ['⏸ بانتظار مكان', 'waiting'], error: ['⚠ فيها أخطاء', 'error'], never: ['لم تبدأ بعد', 'never'], paused: ['⏹ موقوفة', 'never'] };
const SY_KIND = { cloud: '☁', disk: '💾', phone: '📱', computer: '🖥' };
let syTimer = null, syBusy = false;
const syAgo = t => { if (!t) return 'لم تُزامَن بعد'; const m = Math.round((Date.now() / 1000 - t) / 60); return m < 1 ? 'الآن' : m < 60 ? `قبل ${m} دقيقة` : m < 1440 ? `قبل ${Math.round(m / 60)} ساعة` : `قبل ${Math.round(m / 1440)} يومًا`; };
function syBars(rows, fmt) { const mx = Math.max(1, ...rows.map(r => r.v)), box = el('div'); rows.forEach(r => { const b = el('div', undefined, 'sy-bar'), tr = el('div', undefined, 'tr'), i = document.createElement('i'); i.style.width = (r.v / mx * 100).toFixed(1) + '%'; if (r.color) i.style.background = r.color; tr.append(i); const nm = el('span', r.name, 'nm'); nm.title = r.name; b.append(nm, tr, el('span', fmt(r.v), 'v')); box.append(b); }); return box; }
async function loadSyncView(refresh = false) {
  if (syBusy) return; syBusy = true;
  let d; try { d = await api('/api/sync/overview' + (refresh ? '?refresh=1' : '')); } catch (e) { $('#sy-body').replaceChildren(el('div', e.message, 'empty err')); syBusy = false; return; }
  syBusy = false; const body = $('#sy-body'), gs = d.groups; body.replaceChildren(); $('#sy-upd').textContent = 'آخر تحديث للصفحة: ' + new Date().toLocaleTimeString('en-GB');
  if (!gs.length) { const e0 = el('div', undefined, 'empty'); e0.append(el('div', 'لا مجلدات متزامنة بعد.'), el('small', 'كليك يمين على أي مجلد ← «مزامنة هذا المجلد…»، أو اضغط «＋ مزامنة جديدة».', 'muted')); body.append(e0); return; }
  const total = k => gs.filter(g => g.state === k).length, bytes = gs.reduce((a, g) => a + g.bytes, 0), files = gs.reduce((a, g) => a + g.files, 0), lastT = Math.max(...gs.map(g => g.last));
  if (gs.some(g => g.state === 'running')) { pollOps(true); setTimeout(() => { if ($('#v-sync').classList.contains('on')) loadSyncView(); }, 3500); }
  const sum = el('div', undefined, 'sy-sum');
  [[gs.length, 'مجلدات متزامنة'], [total('ok') + total('running'), 'سليمة أو تعمل'], [total('waiting') + total('error'), 'بانتظار أو فيها أخطاء'], [files.toLocaleString('en-US'), 'ملف'], [fsize(bytes), 'الحجم الكلي'], [syAgo(lastT), 'آخر مزامنة']].forEach(([v, l]) => { const t = el('div', undefined, 'sy-tile'); t.append(el('b', String(v)), el('span', l)); sum.append(t); });
  body.append(sum);
  // الرسوم: توزيع الفئات، حجم كل مجلد، نشاط الأيام
  const catAgg = {}; gs.forEach(g => g.cats.forEach(([n, c, b]) => { const x = catAgg[n] = catAgg[n] || { name: n, size: 0, n: 0 }; x.size += b; x.n += c; }));
  const rows = Object.values(catAgg).sort((a, b) => b.size - a.size), charts = el('div', undefined, 'sy-charts');
  const b1 = el('div', undefined, 'sy-box'); b1.append(el('h4', 'توزيع الفئات بحسب الحجم')); if (rows.length && bytes) { const cb = chartBlock('', rows, bytes); cb.querySelector('h4')?.remove(); b1.append(cb); } else b1.append(el('small', 'جارٍ تحليل المجلدات… اضغط «تحديث التحليل» بعد قليل.', 'muted')); charts.append(b1);
  const b2 = el('div', undefined, 'sy-box'); b2.append(el('h4', 'حجم كل مجلد متزامن'), syBars([...gs].sort((a, b) => b.bytes - a.bytes).slice(0, 10).map((g, i) => ({ name: g.name, v: g.bytes, color: PALETTE[i % PALETTE.length] })), fsize)); charts.append(b2);
  const days = []; for (let i = 13; i >= 0; i--) { const dd = new Date(); dd.setHours(0, 0, 0, 0); dd.setDate(dd.getDate() - i); days.push({ t0: dd.getTime() / 1000, ok: 0, bad: 0, copied: 0 }); }
  d.history.forEach(h => { const x = days.find(y => h.t >= y.t0 && h.t < y.t0 + 86400); if (x) { h.ok ? x.ok++ : x.bad++; x.copied += h.copied; } });
  const b3 = el('div', undefined, 'sy-box'); b3.append(el('h4', 'نشاط آخر 14 يومًا (عدد مرات المزامنة)'));
  const dv = el('div', undefined, 'sy-days'), mx = Math.max(1, ...days.map(x => x.ok + x.bad));
  days.forEach(x => { const c = el('div', undefined, 'sy-day'), col = el('div', undefined, 'col'); const mk = (n, cls) => { if (!n) return; const i = document.createElement('i'); i.className = cls; i.style.height = (n / mx * 90) + 'px'; col.append(i); }; mk(x.bad, 'bad'); mk(x.ok, 'ok'); c.title = `${x.ok} ناجحة، ${x.bad} فيها أخطاء، نُسخ ${x.copied} ملفًا`; c.append(col, el('span', new Date(x.t0 * 1000).getDate() + '')); dv.append(c); });
  b3.append(dv, el('small', 'أخضر = ناجحة، أحمر = فيها أخطاء. مرّر على العمود لرؤية عدد الملفات المنسوخة.', 'muted')); charts.append(b3);
  const stc = {}; gs.forEach(g => { const n = g.category; stc[n] = (stc[n] || 0) + 1; });
  const b4 = el('div', undefined, 'sy-box'); b4.append(el('h4', 'عدد المجلدات في كل فئة'), syBars(Object.entries(stc).sort((a, b) => b[1] - a[1]).map(([name, v], i) => ({ name, v, color: PALETTE[i % PALETTE.length] })), v => v + '')); charts.append(b4);
  body.append(charts);
  // البطاقات
  const catColor = n => PALETTE[Math.max(0, rows.findIndex(r => r.name === n)) % PALETTE.length];
  gs.forEach(g => {
    const [stTxt, stCls] = SY_STATE[g.state] || SY_STATE.never, card = el('div', undefined, 'sy-card' + (g.enabled ? '' : ' off'));
    const head = el('div', undefined, 'sy-head'); head.append(el('b', g.name), el('span', stTxt + (g.state === 'waiting' ? ': ' + g.waiting.join('، ') : ''), 'sy-badge ' + stCls), el('span', '🗂 ' + g.category, 'sy-badge cat')); card.append(head);
    const pl = el('div', undefined, 'sy-places'); g.locs.forEach((l, i) => { if (i) pl.append(el('span', g.mode === 'one' ? '→' : '⇄')); pl.append(el('span', `${SY_KIND[l.kind] || ''} ${l.label}${l.online ? '' : ' (غير متصل)'}`, 'sy-pl' + (l.online ? '' : ' offl'))); }); card.append(pl);
    if (g.bytes) { const st = el('div', undefined, 'sy-stack'); g.cats.forEach(([n, c, b]) => { const i = document.createElement('i'); i.style.width = (b / g.bytes * 100) + '%'; i.style.background = catColor(n); i.title = `${n}: ${c} ملف · ${fsize(b)}`; st.append(i); }); card.append(st, el('small', g.cats.slice(0, 4).map(([n, c]) => `${n} ${c}`).join(' · '), 'muted')); }
    const meta = el('div', undefined, 'sy-meta'); meta.append(el('span', '🕒 آخر مزامنة: ' + (g.last ? fdate(g.last * 1000) + ' (' + syAgo(g.last) + ')' : 'لم تبدأ')), el('span', `${g.files.toLocaleString('en-US')} ملف · ${fsize(g.bytes)}`), el('span', (g.mode === 'one' ? '→ اتجاه واحد' : '⇄ اتجاهان') + ' · كل ' + g.every + ' دقيقة'), g.trigger ? el('span', 'المحفّز: ' + g.trigger) : '');
    card.append(meta);
    if (g.state === 'running' && g.op) { const pg = el('div', undefined, 'sy-prog'); pg.dataset.op = g.op; const bar = el('div', undefined, 'bar'); bar.append(document.createElement('i')); pg.append(bar, el('small', 'يحضّر القائمة…', 't')); card.append(pg); }
    if (g.result) card.append(el('small', g.result, 'muted'));
    const acts = el('div', undefined, 'sy-acts');
    acts.append(btn('✎ تعديل', () => syncDialog(g.id), 'btn'),
      btn('مزامنة الآن', async () => { await api('/api/sync/run', { id: g.id }); note('بدأت المزامنة: ' + g.name); setTimeout(() => loadSyncView(), 800); }, 'btn'),
      btn(g.enabled ? 'إيقاف مؤقت' : 'تشغيل', async () => { const all = (await api('/api/sync')).groups; const x = all.find(y => y.id === g.id); if (x) { x.enabled = !x.enabled; await api('/api/sync', { groups: all }); } loadSyncView(); }, 'btn'),
      btn('حذف المزامنة', async () => { if (!confirm('حذف المزامنة «' + g.name + '»؟ لا يُحذف أي ملف.')) return; const all = (await api('/api/sync')).groups.filter(y => y.id !== g.id); await api('/api/sync', { groups: all }); loadSyncView(); }, 'btn'));
    card.append(acts); body.append(card);
  });
}
document.querySelector('[data-v="sync"]')?.addEventListener('click', () => { loadSyncView(); clearInterval(syTimer); syTimer = setInterval(() => { if ($('#v-sync').classList.contains('on')) loadSyncView(); else clearInterval(syTimer); }, 6000); });
$('#sy-refresh').onclick = () => loadSyncView(true);
$('#sy-manage').onclick = syncDialog;
$('#sy-new').onclick = () => { document.querySelector('[data-v="files"]').click(); note('اختر المجلد بكليك يمين ← «مزامنة هذا المجلد…».'); };
/* ---------- قسم «المراقبة»: مساحة الأجهزة والسحابة + اقتراح النقل إلى سحابة التجميع ---------- */
let moBusy = false, moTimer = null; const moSug = {};
async function moSpace(s) {
  try {
    if (s.type === 'adb' && s.online && s.serial) { const r = await api('/api/storage?serial=' + encodeURIComponent(s.serial)); return r.total ? { total: r.total, used: r.used ?? r.total - r.free } : null; }
    if (s.type === 'ios') return s.total ? { total: s.total, used: s.total - s.free } : null;
    if (s.id === 'home') { const r = await api('/api/space?root=home'); return r.total ? r : null; }
    if (s.root?.startsWith?.('vol:')) { const v = (phone?.volumes || []).find(x => 'vol:' + x.name === s.root); return v?.total ? { total: v.total, used: v.total - v.free } : null; }
    const r = cloudRoots.find(x => x.id === s.root); return r?.total ? { total: r.total, used: r.used } : null;
  } catch (_) { return null; }
}
const moGroup = s => s.type === 'ios' || s.type === 'adb' ? 'الأجهزة' : s.id === 'home' ? 'الأجهزة' : s.root?.startsWith?.('vol:') ? 'الأقراص' : s.kind === 'cloud' ? 'السحابة' : null;
async function loadMonitor(force = false) {
  if (moBusy) return; moBusy = true;
  try {
    const list = sources.filter(s => s.online && moGroup(s) && !s.kindle && s.id !== 'watch'), rows = [];
    for (const s of list) { const sp = await moSpace(s); if (sp) rows.push({ s, ...sp, free: sp.total - sp.used, pct: sp.used / sp.total * 100 }); }
    const clouds = rows.filter(r => moGroup(r.s) === 'السحابة'), sel = $('#mo-cloud'), saved = store.get('moCloud', '');
    const best = [...clouds].sort((a, b) => b.free - a.free)[0]?.s.id, cur = clouds.find(r => r.s.id === saved)?.s.id || best || '';
    sel.replaceChildren(...clouds.map(r => { const o = el('option', `${r.s.label}${r.s.email ? ' — ' + r.s.email : ''} (حرة ${fsize(r.free)})`); o.value = r.s.id; return o; })); sel.value = cur;
    sel.onchange = () => { store.set('moCloud', sel.value); Object.keys(moSug).forEach(k => delete moSug[k]); loadMonitor(true); };
    const thr = +store.get('moThr', '85'); $('#mo-thr').value = thr; $('#mo-thr').onchange = () => { store.set('moThr', $('#mo-thr').value); loadMonitor(); };
    const body = $('#mo-body'); body.replaceChildren(); $('#mo-upd').textContent = 'آخر قراءة: ' + new Date().toLocaleTimeString('en-GB');
    const target = clouds.find(r => r.s.id === cur);
    const hot = rows.filter(r => r.pct >= thr && moGroup(r.s) !== 'السحابة');
    if (hot.length) { const w = el('div', `⚠ ${hot.length} ${hot.length === 1 ? 'جهاز يقترب' : 'أجهزة تقترب'} من الامتلاء: ${hot.map(r => r.s.label).join('، ')}`, 'warnbox'); body.append(w); }
    ['الأجهزة', 'الأقراص', 'السحابة'].forEach(g => {
      const part = rows.filter(r => moGroup(r.s) === g); if (!part.length) return; body.append(el('h4', g));
      part.forEach(r => {
        const lvl = r.pct >= 90 ? 'hot' : r.pct >= thr ? 'warm' : '', row = el('div', undefined, 'mo-row ' + lvl), head = el('div', undefined, 'mo-head');
        head.append(el('span', r.s.icon || ''), el('b', r.s.label + (r.s.email ? ' — ' + r.s.email : '')), el('span', r.pct.toFixed(0) + '%', 'sy-badge ' + (lvl === 'hot' ? 'error' : lvl === 'warm' ? 'waiting' : 'ok')), el('span', `مستخدم ${fsize(r.used)} من ${fsize(r.total)} · حرة ${fsize(r.free)}`, 'muted'));
        const bar = el('div', undefined, 'mo-bar ' + lvl), i = document.createElement('i'); i.style.width = Math.min(100, r.pct).toFixed(1) + '%'; bar.append(i); row.append(head, bar);
        if (lvl && g !== 'السحابة') { const box = el('div', undefined, 'mo-sug'); row.append(box); moSuggest(r, target, box, force); }
        if (lvl && g === 'السحابة') row.append(el('small', 'هذه السحابة تقترب من الامتلاء: اختر سحابة تجميع أخرى من القائمة أعلاه.', 'muted'));
        body.append(row);
      });
    });
    if (!rows.length) body.append(el('div', 'لا توجد أجهزة أو سحابات متصلة بمعلومات مساحة.', 'empty'));
    if (!clouds.length) body.append(el('div', 'أضف حسابًا سحابيًا (من الشريط الجانبي) ليُقترح النقل إليه.', 'warnbox'));
  } finally { moBusy = false; }
}
async function moSuggest(r, target, box, force) {
  const s = r.s, key = s.id + '|' + (target?.s.id || '');
  if (s.type === 'ios') { box.append(el('small', 'الآيفون/الآيباد للقراءة: انسخ صوره إلى السحابة من «ترحيل تلقائي» ثم احذفها يدويًا من الجهاز.', 'muted')); return; }
  if (!target) { box.append(el('small', 'لا توجد سحابة تجميع.', 'muted')); return; }
  if (!moSug[key] || force) {
    box.append(el('small', 'جارٍ حساب أكبر المجلدات…', 'muted'));
    moSug[key] = (async () => {
      const base = s.type === 'adb' ? '/sdcard' : '', d = await listDir(s, base), dirs = d.entries.filter(e => e.is_dir && !e.name.startsWith('.') && !['Library', 'Applications', 'System', 'Android'].includes(e.name));
      const q = s.type === 'adb' ? `serial=${encodeURIComponent(s.serial || '')}` : `root=${encodeURIComponent(s.root)}`, out = [];
      await Promise.all(dirs.slice(0, 40).map(async e => { for (let k = 0; k < 60; k++) { try { const z = await api(`/api/dirsize?${q}&path=${encodeURIComponent(e.path)}`); if (z.done) { if (z.size) out.push({ name: e.name, path: e.path, size: z.size }); return; } } catch (_) { return; } await new Promise(r2 => setTimeout(r2, 2000)); } }));
      return out.sort((a, b) => b.size - a.size).slice(0, 5);
    })();
  }
  let items; try { items = await moSug[key]; } catch (e) { box.replaceChildren(el('small', e.message, 'err')); return; }
  box.replaceChildren(el('div', `اقتراح: انقل أكبر المجلدات إلى «${target.s.label}» (حرة ${fsize(target.free)}) لتحرير مساحة:`, 'muted'));
  if (!items.length) box.append(el('small', 'لم أجد مجلدات كبيرة على المستوى الأول.', 'muted'));
  items.forEach(it => {
    const row = el('div', undefined, 'it'), ok = it.size < target.free * 0.95; row.append(el('span', '📁'), el('b', it.name), el('span', fsize(it.size) + ' · يحرّر ' + (it.size / r.total * 100).toFixed(1) + '% من الجهاز', 'muted'));
    const b = btn(ok ? 'انقل إلى السحابة…' : 'لا تتسع السحابة', () => moMove(s, target.s, it), 'btn'); b.disabled = !ok; row.append(b); box.append(row);
  });
}
function moMove(s, cloud, it) {
  openModal(m => {
    m.append(el('h3', 'نقل إلى سحابة التجميع'), el('p', `سيُنقل «${it.name}» (${fsize(it.size)}) من «${s.label}» إلى «${cloud.label}» داخل مجلد «زاجل/${s.label}». لا يُحذف الأصل من الجهاز إلا بعد التحقق من اكتمال النسخ.`));
    const go = btn('انقل', async () => { try { await api('/api/ops/start', { kind: 'move', src: srcRef(s), paths: [it.path], dst: srcRef(cloud), dst_dir: 'زاجل/' + s.label, policy: 'rename' }); closeModal(); note('بدأ النقل: ' + it.name); loadOps(); } catch (e) { note(e.message); } }, 'btn pri');
    const acts = el('div', undefined, 'acts'); acts.append(btn('إلغاء', closeModal, 'btn'), go); m.append(acts);
  });
}
document.querySelector('[data-v="monitor"]')?.addEventListener('click', () => { loadMonitor(); clearInterval(moTimer); moTimer = setInterval(() => { if ($('#v-monitor').classList.contains('on')) loadMonitor(); else clearInterval(moTimer); }, 60000); });
$('#mo-refresh').onclick = () => loadMonitor(true);
async function syncDialog(editId) {
  let st; try { st = await api('/api/sync'); } catch (e) { note(e.message); return; }
  let groups = st.groups;
  const save = async () => { try { groups = (await api('/api/sync', { groups })).groups; loadAuto.sig = ''; loadAuto(); return true; } catch (e) { note(e.message); return false; } };
  const EVERY = [[5, 'كل 5 دقائق'], [15, 'كل 15 دقيقة'], [30, 'كل 30 دقيقة'], [60, 'كل ساعة'], [360, 'كل 6 ساعات'], [1440, 'كل يوم'], [10080, 'كل أسبوع']];
  const everyTxt = n => (EVERY.find(x => x[0] === n) || [0, `كل ${n} دقيقة`])[1];
  let editing = editId ? groups.findIndex(g => g.id === editId) : -1; // رقم المزامنة التي تُعدَّل في النموذج، أو -1 لمزامنة جديدة
  const draw = () => openModal(m => {
    m.classList.add('wide'); m.append(el('h3', '🔁 المزامنة التلقائية'));
    const list = el('div', undefined, 'miglist');
    if (!groups.length) list.append(el('div', 'لا مزامنات بعد.', 'muted'));
    groups.forEach((g, i) => {
      const row = el('div', undefined, 'migrow' + (g.enabled ? '' : ' off'));
      const tg = document.createElement('input'); tg.type = 'checkbox'; tg.checked = g.enabled; tg.title = 'تشغيل تلقائي'; tg.onchange = async () => { g.enabled = tg.checked; await save(); draw(); };
      const tx = el('div', undefined, 'mtx'); tx.append(el('b', g.name), el('small', g.locations.map(l => l.label || l.path).join('  ⇄  ')), el('small', `${g.mode === 'one' ? '→ اتجاه واحد · ' : '⇄ '}${everyTxt(g.every)}${g.last ? ' · آخر مرة ' + fdate(g.last * 1000) : ''}${g.result ? ' · ' + g.result : ''}`), (() => { const x = (st.state || {})[g.id] || {}; return el('small', x.running ? '⏳ تعمل الآن…' : x.waiting?.length ? '⏸ بانتظار: ' + x.waiting.join('، ') : '✔ جاهزة' + (x.trigger ? ' · آخر محفّز: ' + x.trigger : ''), 'muted'); })());
      const run = btn('مزامنة الآن', async () => { await api('/api/sync/run', { id: g.id }); note('بدأت المزامنة: ' + g.name); loadOps(); closeModal(); }, 'btn');
      const del = btn('✕', async () => { groups.splice(i, 1); await save(); draw(); }, 'btn'); del.title = 'حذف المزامنة (لا يحذف أي ملف)';
      const mins = el('input'); mins.type = 'number'; mins.min = 1; mins.max = 10080; mins.value = g.every; mins.title = 'كل كم دقيقة'; mins.style.width = '70px';
      mins.onchange = async () => { g.every = Math.max(1, Math.min(10080, Math.round(+mins.value || g.every))); await save(); draw(); };
      const dl = document.createElement('input'); dl.type = 'checkbox'; dl.checked = !!g.deletes; dl.title = 'نقل الحذف (إلى السلة)'; dl.onchange = async () => { g.deletes = dl.checked; await save(); draw(); };
      const ed = btn('✎ تعديل', () => { editing = i; draw(); setTimeout(() => $('#modal .migform')?.scrollIntoView({ behavior: 'smooth' }), 50); }, 'btn' + (editing === i ? ' pri' : '')); ed.title = 'تعديل الاسم والأماكن (إضافة جهاز أو حذفه)';
      row.append(tg, tx, mins, el('span', 'د', 'muted'), dl, el('span', '🗑', 'muted'), ed, run, del); list.append(row);
    });
    m.append(list);
    const eg = groups[editing];
    const f = el('div', undefined, 'migform' + (eg ? ' editing' : '')); f.append(el('h4', eg ? '✎ تعديل: ' + eg.name : 'مزامنة جديدة'));
    const nm = el('input'); nm.type = 'text'; nm.placeholder = 'الاسم، مثل: الرسالة';
    const ev0 = document.createElement('select'); EVERY.forEach(([v, t]) => { const o = el('option', t); o.value = v; ev0.append(o); }); const oc = el('option', 'مدة أخرى…'); oc.value = ''; ev0.append(oc); ev0.value = 30;
    const evn = el('input'); evn.type = 'number'; evn.min = 1; evn.max = 10080; evn.value = 30; evn.hidden = true; evn.style.width = '90px'; const evl = el('span', 'دقيقة', 'muted'); evl.hidden = true;
    ev0.onchange = () => { evn.hidden = evl.hidden = !!ev0.value; if (!ev0.value) evn.focus(); };
    const ev = el('div', undefined, 'evrow'); ev.append(ev0, evn, evl); Object.defineProperty(ev, 'value', { get: () => ev0.value || String(Math.max(1, Math.min(10080, Math.round(+evn.value || 30)))) });
    const locs = eg ? eg.locations.map(l => ({ ...l })) : [], locBox = el('div', undefined, 'synclocs');
    if (eg) { nm.value = eg.name; if (EVERY.some(x => x[0] === eg.every)) ev0.value = eg.every; else { ev0.value = ''; evn.value = eg.every; evn.hidden = evl.hidden = false; } }
    const drawLocs = () => { locBox.replaceChildren(); locs.forEach((l, k) => { const r = el('div', undefined, 'syncloc'); r.append(el('span', l.label)); const x = btn('✕', () => { locs.splice(k, 1); drawLocs(); }, 'btn'); r.append(x); locBox.append(r); }); if (!locs.length) locBox.append(el('small', 'أضف مكانين على الأقل.', 'muted')); };
    const pickSel = document.createElement('select'), ppick = el('div', undefined, 'fpick'); ppick.hidden = true;
    const o0 = el('option', '＋ أضف مكانًا…'); o0.value = ''; pickSel.append(o0);
    sources.filter(x => x.online && (x.type === 'local' || x.id === 'phone' || x.type === 'ios')).forEach(x => { const o = el('option', (x.type === 'ios' ? (x.cls === 'iPad' ? '📟 ' : '📱 ') : x.id === 'phone' ? '📱 ' : x.kind === 'cloud' ? '☁ ' : x.kind === 'disk' ? '💾 ' : x.kind === 'network' ? '🌐 ' : '🖥 ') + x.label + (x.email ? ' — ' + x.email : '')); o.value = x.id; pickSel.append(o); });
    let cand = null; const addLoc = btn('إضافة هذا المجلد', () => { if (!cand) { note('اختر مجلدًا.'); return; } if (!cand.path) { note('اختر مجلدًا داخل المكان، لا جذره.'); return; } locs.push(cand); cand = null; pickSel.value = ''; ppick.hidden = true; addLoc.hidden = true; drawLocs(); }, 'btn'); addLoc.hidden = true;
    pickSel.onchange = () => { cand = null; ppick.hidden = addLoc.hidden = !pickSel.value; if (!pickSel.value) return; const sid = pickSel.value;
      folderPicker(ppick, sid, sid === 'phone' ? '/sdcard' : srcOf(sid)?.type === 'ios' ? '/@apps' : '', (p, sx) => { sx = sx || srcOf(sid); cand = sx.type === 'ios' ? { kind: 'ios', root: sx.udid, path: String(p).replace(/^\/+/, ''), label: sx.label + ' / ' + String(p).replace(/^\/?@apps\/?/, 'تطبيق: ') + (String(p).startsWith('/@apps') || String(p).startsWith('@apps') ? '' : ' (قراءة فقط)') } : sid === 'phone' ? { kind: 'adb', root: '', path: p.replace(/^\/+/, ''), label: 'الهاتف / ' + p.replace('/sdcard/', '') } : { kind: 'local', root: sx.root, path: p, label: sx.label + (p ? ' / ' + p : '') }; }); };
    const grid = el('div', undefined, 'mgrid'); const lab = (t, n) => { const l = el('label'); l.append(el('span', t), n); grid.append(l); };
    const lw = el('div'); lw.append(locBox, pickSel, ppick, addLoc); drawLocs();
    const del = document.createElement('input'); del.type = 'checkbox'; const delL = el('label', undefined, 'chk'); delL.append(del, el('span', 'نقل الحذف: ما تحذفه في مكان يُنقل إلى السلة في الباقي'));
    lab('الاسم', nm); lab('الأماكن', lw); lab('المدة', ev); lab('الحذف', delL); f.append(grid, el('small', 'الأحدث يغلب. الحذف لا ينتقل إلا إذا فعّلته، وإلى السلة دائمًا، وبشرط اتصال كل الأماكن. في الآيفون/الآيباد: ملفات التطبيقات بالاتجاهين، والصور منه فقط.', 'muted'));
    const add = btn('إضافة المزامنة', async () => { if (cand && cand.path && !locs.some(l => l.kind === cand.kind && l.root === cand.root && l.path === cand.path)) { locs.push(cand); cand = null; } // مجلد اختير ولم يُضغط «إضافة هذا المجلد»
      if (locs.length < 2) { note('أضف مكانين على الأقل.'); return; }
      if (eg) { const keep = groups[editing]; groups[editing] = { ...keep, name: nm.value.trim() || keep.name, locations: locs, every: +ev.value, deletes: del.checked };
        if (await save()) { editing = -1; draw(); note('حُفظ التعديل؛ الأماكن الجديدة تُملأ في المزامنة القادمة.'); } else groups[editing] = keep; return; }
      groups.push({ name: nm.value.trim() || locs[0].label.split(' / ').pop(), locations: locs, every: +ev.value, enabled: true, deletes: del.checked }); if (await save()) { draw(); note('أُضيفت؛ تبدأ خلال دقيقة ثم ' + everyTxt(+ev.value) + '.'); } }, 'btn pri');
    if (eg) { add.textContent = '💾 حفظ التعديل'; del.checked = !!eg.deletes; f.append(add, btn('إلغاء التعديل', () => { editing = -1; draw(); }, 'btn')); } else f.append(add);
    m.append(f);
    const acts = el('div', undefined, 'acts'); acts.append(btn('تم', closeModal, 'btn')); m.append(acts);
  });
  draw();
}
/* ---------- المعرض الموحّد: نتائج بحث واحد في عدة مصادر ---------- */
async function multiSearch(q, exts, sids, content = []) {
  const list = (sids.length ? sources.filter(s => sids.includes(s.id)) : sources).filter(s => s.online);
  if (!list.length) { note('اختر مصدرًا متصلًا واحدًا على الأقل.'); return; }
  let job; try { job = await api('/api/search/multi', { q, exts, content, sources: list.map(s => ({ sid: s.id, src: srcRef(s) })) }); } catch (e) { note(e.message); return; }
  const g = openGallery(q, exts, list);
  for (;;) { await new Promise(r => setTimeout(r, 900)); let j; try { j = await api('/api/search/job?id=' + job.id); } catch (_) { break; } g.update(j); if (j.state !== 'running') break; if (!g.alive()) { api('/api/search/cancel', { id: job.id }).catch(() => {}); break; } }
}
function openGallery(q, exts, list) {
  const gsel = new Set(); let selbar = null;
  let data = { entries: [], state: 'running' }, only = '', byFolder = false, gview = store.get('gview', 'grid');
  const ov = el('div', undefined, 'gallery'), head = el('div', undefined, 'ghead'), body = el('div', undefined, 'gbody');
  const title = el('b', ''), chips = el('div', undefined, 'gchips'), close = el('button', '✕', 'btn nav'); close.title = 'إغلاق (Esc)';
  const fold = btn('حسب المجلد', () => { byFolder = !byFolder; fold.classList.toggle('pri', byFolder); draw(); }, 'btn');
  let gsort = store.get('gsort', ''), gdesc = store.get('gdesc', '1') === '1';
  const gs = document.createElement('select'); gs.className = 'gsort'; gs.title = 'ترتيب النتائج';
  [['', 'ترتيب: الصلة'], ['mod', 'تاريخ التعديل'], ['born', 'تاريخ الإنشاء'], ['size', 'الحجم'], ['name', 'الاسم'], ['type', 'النوع']].forEach(([k, l]) => { const o = el('option', l); o.value = k; if (k === gsort) o.selected = true; gs.append(o); });
  const gd = btn(gdesc ? '↓' : '↑', () => { gdesc = !gdesc; gd.textContent = gdesc ? '↓' : '↑'; store.set('gdesc', gdesc ? '1' : '0'); draw(); }, 'btn'); gd.title = 'عكس الترتيب';
  gs.onchange = () => { gsort = gs.value; store.set('gsort', gsort); draw(); };
  const gv = btn(gview === 'list' ? '▦ شبكة' : '☰ صفوف', () => { gview = gview === 'list' ? 'grid' : 'list'; store.set('gview', gview); gv.textContent = gview === 'list' ? '▦ شبكة' : '☰ صفوف'; draw(); }, 'btn'); gv.title = 'العرض: صفوف بالتفاصيل أو شبكة مصغّرات';
  head.append(title, chips, gs, gd, gv, fold, close); ov.append(head, body); document.body.append(ov);
  const kill = () => { ov.remove(); document.removeEventListener('keydown', esc, true); };
  const esc = ev => { if (ev.key === 'Escape' && $('#lb').hidden) { ev.stopPropagation(); kill(); } }; document.addEventListener('keydown', esc, true); close.onclick = kill;
  const srcOf = sid => sources.find(s => s.id === sid);
  const ent = e => Object.assign({}, e, { _src: srcOf(e.sid) });
  function card(e, all) {
    const s = srcOf(e.sid); if (!s) return null; const fake = { src: s };
    const c = el('div', undefined, 'gcard'), th = el('div', undefined, 'gth'), u = thumbUrl(fake, e);
    if (u) { const im = new Image(); im.loading = 'lazy'; im.src = u; im.onerror = () => { th.textContent = EXT.vid.test(e.name) ? '🎬' : '📄'; }; th.append(im); } else th.textContent = /\.pdf$/i.test(e.name) ? '📄' : EXT.aud.test(e.name) ? '🎵' : EXT.vid.test(e.name) ? '🎬' : '📄';
    const b = el('b', e.name), sm = el('small', `${s.label}${e.folder ? ' · ' + e.folder.split('/').slice(-2).join('/') : ''}`); c.title = `${e.name}\n${s.label}\n${e.path}`;
    const key = e.sid + '|' + e.path, local = s.type === 'local' && !String(s.root || '').startsWith('rc:');
    const ck = el('span', gsel.has(key) ? '✓' : '', 'gck' + (gsel.has(key) ? ' on' : '')); ck.title = 'تحديد';
    ck.onclick = ev => { ev.stopPropagation(); gsel.has(key) ? gsel.delete(key) : gsel.add(key); draw(); };
    const open = async ev => { ev?.stopPropagation();
      if (local) { try { await api('/api/open', { root: s.root, path: e.path }); kill(); closeLightbox(); } catch (x) { note(x.message); } return; }
      const items = all.map(x => { const sx = srcOf(x.sid), fx = { src: sx }; return { title: x.name, entry: ent(x), url: x.is_dir ? null : (EXT.img.test(x.name) ? previewUrl(fx, x) : thumbUrl(fx, x)), fallback: thumbUrl(fx, x), meta: `${sx?.label || ''} · ${fsize(x.size)} · ${fdate(x.mod)}`, icon: '📄' }; });
      openLightbox(items, all.indexOf(e), { src: s, markCursor() {}, root: document.createElement('div') }); };
    th.onclick = open; b.onclick = open; th.style.cursor = b.style.cursor = 'pointer'; th.title = b.title = local ? 'فتح الملف' : 'معاينة';
    const dots = el('button', '⋯', 'gact'); dots.title = 'خيارات';
    dots.onclick = ev => { ev.stopPropagation(); gMenu(dots, [
      ['📂 فتح المجلد المتضمِّن داخل زاجل', () => { kill(); closeLightbox(); if (P) P.reveal({ path: e.path, folder: e.folder || (s.type === 'adb' ? '/sdcard' : ''), name: e.name, is_dir: false }, e.sid); }],
      ...(local ? [['🔍 إظهار في Finder', () => api('/api/open', { root: s.root, path: e.path, reveal: true }).catch(x => note(x.message))]] : []),
      ['📋 نسخ المسار', () => copyPathFor({ src: s }, e)],
      [isFav(s.id, e.path) ? '⭐ إزالة من المفضلة' : '☆ إضافة إلى المفضلة', () => toggleFavPaths({ src: s }, [e])]]); };
    const acts = el('div', undefined, 'gacts'); acts.append(dots);
    c.append(th, b, sm, ck, acts); c._e = e; c._acts = acts; c._ck = ck; c._open = open; c.classList.toggle('sel', gsel.has(key));
    c.onclick = () => { gsel.has(key) ? gsel.delete(key) : gsel.add(key); draw(); };
    return c;
  }
  function drawSel(ents) {
    selbar?.remove(); selbar = el('div', undefined, 'gselbar'); ov.append(selbar);
    const picked = data.entries.filter(e => gsel.has(e.sid + '|' + e.path));
    const all = btn(picked.length && picked.length === ents.length ? 'إلغاء تحديد الكل' : `تحديد الكل (${ents.length})`, () => { if (picked.length === ents.length) gsel.clear(); else ents.forEach(e => gsel.add(e.sid + '|' + e.path)); draw(); }, 'btn');
    selbar.append(all); if (!picked.length) return;
    const bySrc = {}; picked.forEach(e => (bySrc[e.sid] = bySrc[e.sid] || []).push(e));
    const run = (kind, dst, dir) => { Object.entries(bySrc).forEach(([sid, arr]) => startOp({ kind, src: srcRef(srcOf(sid)), paths: arr.map(x => x.path), dst: srcRef(dst), dst_dir: dir, policy: 'rename' })); note((kind === 'copy' ? 'بدأ نسخ ' : 'بدأ نقل ') + picked.length + ' ملف'); gsel.clear(); draw(); };
    selbar.append(el('b', `${picked.length} محدد`),
      btn('📥 نسخ إلى مجلد…', () => gDest('نسخ ' + picked.length + ' ملف إلى…', (d, dir) => run('copy', d, dir)), 'btn'),
      btn('➡️ نقل إلى مجلد…', () => gDest('نقل ' + picked.length + ' ملف إلى…', (d, dir) => run('move', d, dir)), 'btn'),
      ...(picked.length === 1 ? [btn('✎ إعادة تسمية', () => { const e = picked[0], s = srcOf(e.sid), nn = prompt('الاسم الجديد:', e.name); if (!nn || nn === e.name) return;
        startOp({ kind: 'rename', src: srcRef(s), paths: [e.path], name: nn }); e.name = nn; e.path = e.path.replace(/[^/]*$/, nn); gsel.clear(); gsel.add(e.sid + '|' + e.path); draw(); }, 'btn')] : []),
      btn('🗑 حذف…', () => { const phone = picked.filter(e => srcOf(e.sid)?.type === 'adb' || srcOf(e.sid)?.type === 'ios');
        if (phone.length) { note('حذف ملفات الهاتف/الآيفون من هنا غير متاح؛ افتح مجلدها واحذفها منه.'); return; }
        if (!confirm(`نقل ${picked.length} ملف إلى سلة المهملات؟ (يمكن استرجاعها منها)`)) return;
        Object.entries(bySrc).forEach(([sid, arr]) => startOp({ kind: 'delete', src: srcRef(srcOf(sid)), paths: arr.map(x => x.path), confirm: true }));
        data.entries = data.entries.filter(e => !gsel.has(e.sid + '|' + e.path)); gsel.clear(); draw(); }, 'btn danger'),
      btn('إلغاء التحديد', () => { gsel.clear(); draw(); }, 'btn'));
  }
  function gDest(titleTxt, cb) {
    openModal(m => {
      m.append(el('h3', titleTxt)); const sel = document.createElement('select'); sel.className = 'search'; sel.style.width = '100%'; sel.style.margin = '8px 0';
      sources.filter(s => s.online && s.type !== 'ios').forEach(s => { const o = el('option', s.label); o.value = s.id; sel.append(o); });
      const pk = el('div', undefined, 'fpick'); pk.style.maxHeight = '300px'; let dst = null, dir = '';
      const up = sid => { const s = sources.find(x => x.id === sid); dst = s; dir = s.type === 'adb' ? '/sdcard' : (s.home || ''); folderPicker(pk, sid, dir, (d, sx) => { dir = d; dst = sx || s; }); };
      sel.onchange = () => up(sel.value); m.append(sel, pk); up(sel.value);
      const ok = el('button', 'هنا', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts'); cancel.onclick = closeModal;
      ok.onclick = () => { closeModal(); cb(dst, dir); }; acts.append(cancel, ok); m.append(acts);
    });
  }
  function gMenu(anchor, items) {
    document.querySelector('.gmenu')?.remove(); const mnu = el('div', undefined, 'gmenu'); const r = anchor.getBoundingClientRect();
    items.forEach(([t, f]) => { const it = el('div', t, 'gmi'); it.onclick = ev => { ev.stopPropagation(); mnu.remove(); f(); }; mnu.append(it); });
    document.body.append(mnu); mnu.style.top = Math.min(r.bottom + 4, innerHeight - mnu.offsetHeight - 8) + 'px'; mnu.style.left = Math.max(8, Math.min(r.left, innerWidth - mnu.offsetWidth - 8)) + 'px';
    setTimeout(() => document.addEventListener('click', () => mnu.remove(), { once: true }), 0);
  }
  function draw() {
    const ents = data.entries.filter(e => !e.is_dir && (!only || e.sid === only));
    if (gsort) { const ext = n => (n.split('.').pop() || '').toLowerCase(), k = { mod: e => e.mod || 0, born: e => e.born || 0, place: e => (srcOf(e.sid)?.label || '') + '/' + (e.folder || ''), size: e => e.size || 0, name: e => e.name.toLowerCase(), type: e => ext(e.name) + ' ' + e.name.toLowerCase() }[gsort];
      ents.sort((a, b) => { const x = k(a), y = k(b), r = typeof x === 'number' ? x - y : String(x).localeCompare(String(y), 'ar'); return gdesc ? -r : r; }); }
    gd.hidden = !gsort;
    title.textContent = `${data.state === 'running' ? '⏳ ' : ''}${ents.length} نتيجة${q ? ` «${q}»` : ''}${exts.length ? ' · ' + exts.map(x => '.' + x).join(' ') : ''}`;
    chips.replaceChildren(); const mk = (sid, label, n) => { const c = el('span', `${label} (${n})`, 'chip' + (only === sid ? ' on' : '')); c.onclick = () => { only = only === sid ? '' : sid; draw(); }; chips.append(c); };
    mk('', 'الكل', data.entries.filter(e => !e.is_dir).length); list.forEach(s => { const n = data.entries.filter(e => e.sid === s.id && !e.is_dir).length; if (n || data.state === 'running') mk(s.id, s.label, n); });
    Object.entries(data.sources || {}).forEach(([sid, st]) => { const lab = srcOf(sid)?.label || sid, tx = st.state === 'error' ? 'تعذّر — ' + (st.error || '') : st.state === 'timeout' ? 'تأخر (نتائج جزئية)' : st.state === 'slow' ? 'بطيء ' + st.seconds + ' ث' : st.state === 'running' && data.seconds > 10 ? 'ما زال يبحث…' : ''; if (tx) { const c = el('span', `⚠ ${lab}: ${tx}`, 'chip'); c.style.opacity = '.8'; chips.append(c); } });
    body.replaceChildren();
    if (!ents.length) { body.append(el('div', data.state === 'running' ? 'جارٍ البحث…' : 'لا نتائج.', 'gempty')); return; }
    const shown = ents.slice(0, 1500);
    if (byFolder) {
      const groups = {}; shown.forEach(e => { const k = e.sid + '|' + (e.folder || ''); (groups[k] = groups[k] || []).push(e); });
      Object.entries(groups).sort((a, b) => b[1].length - a[1].length).forEach(([k, arr]) => { const [sid, folder] = k.split('|'), s = srcOf(sid);
        const h = el('div', undefined, 'gfold'); h.append(el('b', '📁 ' + (folder.split('/').pop() || s?.label || '')), el('small', `${s?.label || ''} · ${folder || '/'} · ${arr.length}`));
        h.onclick = () => { kill(); P && P.go(sid, folder || (s?.type === 'adb' ? '/sdcard' : '')); }; body.append(h);
        const grid = el('div', undefined, 'ggrid'); arr.forEach(e => { const c = card(e, shown); c && grid.append(c); }); body.append(grid); });
    } else { const grid = el('div', undefined, 'ggrid'); shown.forEach(e => { const c = card(e, shown); c && grid.append(c); }); body.append(grid); }
    if (gview === 'list') body.querySelectorAll('.ggrid').forEach(g => {
      const t = el('table', undefined, 'glist'), hr = el('tr');
      [['', ''], ['', ''], ['name', 'الاسم'], ['size', 'الحجم'], ['place', 'المكان'], ['born', 'تاريخ الإنشاء'], ['mod', 'تاريخ التعديل']].forEach(([k, x]) => { const h = el('th', x + (k && gsort === k ? (gdesc ? ' ↓' : ' ↑') : '')); if (k) { h.className = 'gsortable'; h.title = 'اضغط للترتيب، ومرة أخرى لعكسه';
        h.onclick = () => { if (gsort === k) gdesc = !gdesc; else { gsort = k; gdesc = k !== 'name' && k !== 'place'; } store.set('gsort', gsort); store.set('gdesc', gdesc ? '1' : '0'); if ([...gs.options].some(o => o.value === k)) gs.value = k; gd.textContent = gdesc ? '↓' : '↑'; draw(); }; } hr.append(h); }); t.append(hr);
      [...g.children].forEach(c => { const e = c._e; if (!e) return; const s = srcOf(e.sid), r = el('tr'), tdTh = el('td'), th = c.querySelector('.gth'); if (th) tdTh.append(th);
        const loc = el('td', `${s?.label || ''}${e.folder ? ' / ' + e.folder : ''}`, 'gloc'); loc.title = loc.textContent;
        const tdN = el('td', undefined, 'gname'), nmw = el('div', undefined, 'gnmw'); const nsp = el('span', e.name, 'gopen'); nsp.onclick = c._open; nsp.title = c.title; nmw.append(nsp); if (c._acts) nmw.append(c._acts); tdN.append(nmw); const tdC = el('td'); tdC.append(c._ck); if (c.classList.contains('sel')) r.classList.add('sel');
        r.append(tdC, tdTh, tdN, el('td', fsize(e.size), 'num'), loc, el('td', e.born ? fdate(e.born) : '—', 'num'), el('td', e.mod ? fdate(e.mod) : '—', 'num'));
        r.onclick = c.onclick; t.append(r); });
      // عرض الأعمدة: مقبض على حافة كل عنوان يُسحب، ويُحفظ
      const W = (() => { try { return JSON.parse(store.get('gcolw2', '[]')) || []; } catch (_) { return []; } })(), DEF = [34, 52, 320, 90, 260, 150, 150];
      const cg = el('colgroup'); DEF.forEach((d, k) => { const col = el('col'); col.style.width = (W[k] || d) + 'px'; cg.append(col); }); t.prepend(cg); t.style.tableLayout = 'fixed'; t.style.width = 'max-content';
      [...hr.children].forEach((h, k) => { if (!k) return; const gr = el('span', undefined, 'gcolgrip'); gr.title = 'اسحب لتغيير عرض العمود'; gr.onclick = ev => ev.stopPropagation();
        gr.onmousedown = ev => { ev.preventDefault(); ev.stopPropagation(); const col = cg.children[k], x0 = ev.clientX, w0 = col.getBoundingClientRect().width, rtl = getComputedStyle(t).direction === 'rtl';
          const mv = e2 => { col.style.width = Math.max(50, w0 + (rtl ? x0 - e2.clientX : e2.clientX - x0)) + 'px'; };
          const up = () => { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); const ws = [...cg.children].map(c2 => Math.round(c2.getBoundingClientRect().width)); store.set('gcolw2', JSON.stringify(ws)); };
          document.addEventListener('mousemove', mv); document.addEventListener('mouseup', up); };
        h.style.position = 'relative'; h.append(gr); });
      g.replaceWith(t); });
    if (ents.length > shown.length) body.append(el('div', `… و${ents.length - shown.length} أخرى — ضيّق البحث.`, 'gempty'));
    drawSel(ents);
  }
  draw();
  return { update(j) { data = j; draw(); }, alive: () => ov.isConnected };
}
function renderTabs() {
  const box = $('#wtabs'); box.replaceChildren();
  workspaces.forEach(w => {
    const t = el('div', undefined, 'wtab' + (w === ws ? ' on' : '')); t.append(el('b', tabTitle(w)));
    if (workspaces.length > 1) { const x = el('button', '✕', 'x'); x.title = 'إغلاق التبويب (⌘W)'; x.onclick = e => { e.stopPropagation(); closeTab(w); }; t.append(x); }
    t.onclick = ev => { if (w === ws && P?.src) pathMap(ev, P); else activateWs(w); }; if (w === ws) t.title = 'خريطة المسار'; t.onauxclick = e => { if (e.button === 1) closeTab(w); };
    box.append(t);
  });
  $('#vsplit').classList.toggle('on', ws?.panes.length === 2);
}
function setActive(p) {
  if (P === p) return;
  P = p; const w = workspaces.find(x => x.panes.includes(p)); if (w) { ws = w; w.activeIdx = w.panes.indexOf(p); }
  allPanes().forEach(x => x.root.classList.toggle('active', x === p));
  renderSources(); updateSbar(); renderTabs(); p.cursor ? showDetails(p, p.cursor) : showSourceCard();
}
/* ---------- مجموعة أيقونات خطية موحّدة (كلاسيكية) ---------- */
const ICONS = {
  arrowR: '<path d="M5 12h14M13 6l6 6-6 6"/>', arrowL: '<path d="M19 12H5M11 6l-6 6 6 6"/>',
  copy: '<rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V6a2 2 0 0 1 2-2h9"/>',
  move: '<path d="M12 3v18M3 12h18M8 7l4-4 4 4M8 17l4 4 4-4M7 8l-4 4 4 4M17 8l4 4-4 4"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
  selectAll: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M8 12l3 3 5-6"/>', clear: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M9 9l6 6M15 9l-6 6"/>'
};
const icon = (names, size = 20) => `<svg class="ico" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${[].concat(names).map(n => ICONS[n]).join('')}</svg>`;
/* شريط الأوامر بين اللوحتين: تحديد الكل، مسح، نسخ ونقل بالأسهم، حذف. */
const xferEl = (() => {
  const box = el('div', undefined, 'xfer');
  const mk = (cls, ic, cap, title, f) => { const b = el('button', undefined, 'xbtn ' + cls); b.innerHTML = ic + `<span>${cap}</span>`; b.title = title; b.onclick = f; return b; };
  const pair = (kind, capt) => { const g = el('div', undefined, 'xpair'); g.append(
    mk('x' + kind, icon([kind === 'copy' ? 'copy' : 'move', 'arrowR'], 17), capt, `${capt}: من اللوحة اليسرى إلى اليمنى`, () => xferTo('right', kind)),
    mk('x' + kind, icon([kind === 'copy' ? 'copy' : 'move', 'arrowL'], 17), capt, `${capt}: من اللوحة اليمنى إلى اليسرى`, () => xferTo('left', kind))); return g; };
  box.append(mk('xsel', icon('selectAll'), 'الكل', 'تحديد الكل في اللوحة النشطة', () => $('#selall').click()), mk('xclr', icon('clear'), 'مسح', 'مسح التحديد في اللوحة النشطة', () => $('#clr').click()),
    el('hr'), pair('copy', 'نسخ'), pair('move', 'نقل'), el('hr'), mk('xdel', icon('trash'), 'حذف', 'حذف المحدد في اللوحة النشطة (Delete)', () => $('#delfiles').click()));
  return box;
})();
function syncXfer() { const n = P?.S().size || 0; xferEl.querySelectorAll('.xdel,.xclr').forEach(b => b.disabled = !n); }
function xferTo(side, kind) {
  if (ws.panes.length !== 2) return;
  const [a, b] = ws.panes, rightPane = a.root.getBoundingClientRect().left > b.root.getBoundingClientRect().left ? a : b, leftPane = rightPane === a ? b : a;
  const from = side === 'right' ? leftPane : rightPane, to = side === 'right' ? rightPane : leftPane;
  const sel = from.S(), paths = sel.size ? [...sel] : (from.cursor ? [from.cursor.path] : []);
  if (!paths.length) { note('حدد عنصرًا أو أكثر في اللوحة المصدر أولًا.'); return; }
  if (!from.src?.online || !to.src?.online) { note('أحد المصدرين غير متصل.'); return; }
  if (from.src.id === to.src.id && from.cur === to.cur) { note('اللوحتان على المجلد نفسه.'); return; }
  startOp({ kind, src: srcRef(from.src), paths, dst: srcRef(to.src), dst_dir: to.cur, policy: 'keep' });
  sel.clear(); from.rerender(); note(`${kind === 'copy' ? 'يُنسخ' : 'يُنقل'} ${paths.length} عنصر إلى ${to.src.label}…`);
}
function renderPanesArea() {
  const box = $('#panes'), dual = ws.panes.length === 2;
  box.replaceChildren(...(dual ? [ws.panes[0].root, xferEl, ws.panes[1].root] : ws.panes.map(p => p.root)));
  box.classList.toggle('dual', dual); $('#sbar').classList.toggle('dualbar', dual); syncXfer();
}
function activateWs(w) { ws = w; renderPanesArea(); P = null; setActive(w.panes[w.activeIdx || 0] || w.panes[0]); saveLayout(); }
function newTab(from) {
  const p = new Pane({ view: from?.viewMode }), w = { id: ++wid, panes: [p], activeIdx: 0 }; workspaces.push(w); activateWs(w);
  const s = from?.src || sources.find(x => x.online); if (s) p.go(s.id, from?.cur ?? store.get('path:' + s.id, s.home));
  return w;
}
function closeTab(w) {
  if (workspaces.length === 1) return;
  const i = workspaces.indexOf(w); workspaces.splice(i, 1);
  if (w === ws) activateWs(workspaces[Math.max(0, i - 1)]); else { renderTabs(); saveLayout(); }
}
function toggleSplit() {
  if (ws.panes.length === 1) {
    const p2 = new Pane({ view: P.viewMode }); ws.panes.push(p2); renderPanesArea();
    if (P.src) p2.go(P.src.id, P.cur); setActive(p2);
  } else {
    const keep = P; ws.panes = [keep]; ws.activeIdx = 0; renderPanesArea(); renderTabs(); allPanes().forEach(x => x.root.classList.toggle('active', x === P));
  }
  saveLayout(); renderTabs();
}
function onPaneChanged(p) { saveLayout(); renderTabs(); updateFavBtns(); if (p === P) { renderSources(); updateSbar(); if (!p.cursor) showSourceCard(); } else renderSources(); }
$('#newtab').onclick = () => newTab(P);
$('#vsplit').onclick = toggleSplit;
$('#vdet').onclick = () => { $('#det').classList.toggle('off'); $('#vdet').classList.toggle('on', !$('#det').classList.contains('off')); store.set('det', $('#det').classList.contains('off') ? 'off' : 'on'); };
function srcMenu(ev, pane) {
  closeCtx(); const m = el('div', undefined, 'ctx');
  sources.forEach(s => { const d = el('div', `${s.icon} ${s.label}${s.online ? '' : '  (غير متصل)'}`); d.onclick = () => { closeCtx(); pane.openSource(s.id); }; m.append(d); });
  document.body.append(m); m.style.left = Math.min(ev.clientX, innerWidth - 240) + 'px'; m.style.top = Math.min(ev.clientY + 8, innerHeight - m.offsetHeight - 10) + 'px';
}
$('#selall').onclick = () => { P.currentList().forEach(e => P.S().add(e.path)); P.rerender(); };
$('#clr').onclick = () => { P.S().clear(); if (P.src?.id === 'phone') cats.clear(); P.rerender(); renderSources(); };

/* ---------- شريط الحالة ولوحة المعلومات ---------- */
function updateSbar() {
  const p = P; if (!p?.src) return;
  const list = p.currentList(), sel = p.S(), chosen = p.entries.filter(e => sel.has(e.path)), sz = chosen.reduce((a, e) => a + (e.size || 0), 0);
  $('#sinfo').textContent = `${list.length} عنصر` + (sel.size ? ` · ${sel.size} محدد${sz ? ' (' + fsize(sz) + ')' : ''}` : '');
  const st = storageInfo[p.src.id], vol = (phone?.volumes || []).find(v => 'vol:' + v.name === p.src.id);
  $('#sstore').textContent = st?.free ? `حرة ${fsize(st.free)} من ${fsize(st.total)}` : vol ? `حرة ${fsize(vol.free)}` : '';
  $('#delfiles').hidden = !sel.size; $('#bookren').hidden = !chosen.some(e => BOOK_RE.test(e.name)); syncXfer();
}
function showSourceCard() {
  const p = P; if (!p?.src || p.cursor) return; const d = $('#detBody'); d.replaceChildren(); const s = p.src;
  const c = el('div', undefined, 'srccard mini'), h = el('div', undefined, 'sch');
  const dot = el('span', undefined, 'scdot' + (s.online ? ' on' : '')); dot.title = s.online ? 'متصل' : 'غير متصل';
  h.append(el('b', `${s.icon} ${s.label}`), dot); c.append(h);
  const files = (p.entries || []).filter(e => !e.is_dir), dirs = (p.entries || []).length - files.length;
  const row = el('div', undefined, 'scrow'), chip = (t, tip) => { const x = el('span', t); if (tip) x.title = tip; row.append(x); };
  chip('📁 ' + (p.cur ? p.cur.split('/').filter(Boolean).pop() : 'الجذر'), p.cur || '');
  chip(`${dirs} مجلد`); chip(`${files.length} ملف`); chip(fsize(files.reduce((a, e) => a + (e.size || 0), 0)), 'حجم الملفات في هذا المجلد');
  c.append(row);
  const vol = (phone?.volumes || []).find(v => 'vol:' + v.name === s.id), st = storageInfo?.[s.id], rr = (cloudRoots || []).find(r => r.id === s.id);
  const tot = vol?.total || st?.total || rr?.total || s.total, free = vol ? vol.free : st ? st.free : rr?.total ? rr.total - rr.used : s.free;
  if (tot) c.append(el('small', `متاح ${fsize(free)} من ${fsize(tot)}`, 'scsub'));
  if (s.email) c.append(el('small', s.email, 'scsub'));
  d.append(c);
}
async function showDetails(p, e) {
  const s = p.src, d = $('#detBody'); d.replaceChildren(el('h3', e.name), el('p', 'جارٍ قراءة المعلومات…', 'muted'));
  try {
    const i = s.type === 'adb' ? await api(`/api/info?path=${encodeURIComponent(e.path)}&serial=${encodeURIComponent(s.serial || '')}`) : await api(`/api/lfs/info?root=${encodeURIComponent(s.root)}&path=${encodeURIComponent(e.path)}`);
    if (p.cursor !== e || P !== p) return;
    d.replaceChildren(el('h3', e.name));
    const u = thumbUrl(p, e); if (u) { const big = el('div', undefined, 'bigth'); const im = new Image(); im.src = u; im.onload = () => big.append(im); d.append(big); }
    const kv = (k, v) => { const r = el('div', undefined, 'kv'); r.append(el('span', k), el('span', v)); d.append(r); };
    kv('النوع', i.type === 'dir' ? 'مجلد' : 'ملف'); kv('الحجم', i.size == null ? '—' : `${fsize(i.size)} (${i.size.toLocaleString('en')} B)`);
    kv('آخر تعديل', fdate(i.mod)); kv('تغيّر الحالة', fdate(i.chg)); kv('آخر وصول', fdate(i.acc));
    kv('تاريخ الإنشاء', s.type === 'adb' ? 'غير محفوظ في الهاتف' : fdate(i.birth)); kv('الصلاحيات', i.perm); kv('المالك', i.owner); kv('المسار', i.path);
    Object.entries(i.extra || {}).forEach(([k, v]) => kv(k, v));
  } catch (err) {
    // مصادر لا تعطي معلومات تفصيلية (مثل حسابات السحابة): نعرض ما نعرفه من القائمة
    if (p.cursor !== e) return; d.replaceChildren(el('h3', e.name));
    const kv = (k, v) => { const r = el('div', undefined, 'kv'); r.append(el('span', k), el('span', v)); d.append(r); };
    kv('النوع', e.is_dir ? 'مجلد' : (e.name.split('.').pop() || '').toUpperCase() + ' ملف'); if (!e.is_dir) kv('الحجم', fsize(e.size)); kv('آخر تعديل', fdate(e.mod)); kv('المسار', e.path); kv('المصدر', s.label);
  }
  if (e.is_dir && p.cursor === e) dirSizeRows(p, e, d);
}
async function dirSizeRows(p, e, d) {
  const box = el('div', undefined, 'dsz'); box.append(el('div', 'جارٍ حساب حجم المجلد…', 'muted')); d.append(box);
  const s = p.src, q = s.type === 'adb' ? `serial=${encodeURIComponent(s.serial || '')}` : `root=${encodeURIComponent(s.root)}`;
  try {
    const r = await api(`/api/dirsize?${q}&path=${encodeURIComponent(e.path)}`); if (p.cursor !== e) return; box.replaceChildren();
    const kv = (k, v) => { const x = el('div', undefined, 'kv'); x.append(el('span', k), el('span', v)); box.append(x); };
    kv('الحجم الكلي', fsize(r.size) + (r.partial ? '+' : '')); kv('الملفات', r.files.toLocaleString('en')); if (r.dirs) kv('المجلدات الفرعية', r.dirs.toLocaleString('en'));
    const row = p.root.querySelector(`[data-path="${CSS.escape(e.path)}"] .num`); e.size = r.size; dirSizes[s.id + '|' + e.path] = r.size;
  } catch (err) { box.replaceChildren(el('div', err.message, 'err')); }
}
const dirSizes = {};

/* ---------- التحديد بالسحب والاختصارات والقائمة ---------- */
function setupMarquee() {
  /* المستطيل بإحداثيات «محتوى» القائمة (لا الشاشة)، فلا يضيع التحديد عند انزلاق القائمة تلقائيًا. */
  let start = null, box = null, base = null, container = null, pane = null, timer = null, last = null;
  const toContent = (cx, cy) => { const r = container.getBoundingClientRect(); return { x: cx - r.left + container.scrollLeft, y: cy - r.top + container.scrollTop }; };
  const update = () => {
    const r = container.getBoundingClientRect(), now = toContent(last.clientX, last.clientY), s = pane.S();
    const x1 = Math.min(start.x, now.x), x2 = Math.max(start.x, now.x), y1 = Math.min(start.y, now.y), y2 = Math.max(start.y, now.y);
    Object.assign(box.style, { left: Math.max(r.left, x1 - container.scrollLeft + r.left) + 'px', top: Math.max(r.top, y1 - container.scrollTop + r.top) + 'px',
      width: Math.max(0, Math.min(r.right, x2 - container.scrollLeft + r.left) - Math.max(r.left, x1 - container.scrollLeft + r.left)) + 'px',
      height: Math.max(0, Math.min(r.bottom, y2 - container.scrollTop + r.top) - Math.max(r.top, y1 - container.scrollTop + r.top)) + 'px' });
    s.clear(); base.forEach(p => s.add(p));
    container.querySelectorAll('[data-path]').forEach(n => {
      const b = n.getBoundingClientRect(), top = b.top - r.top + container.scrollTop, left = b.left - r.left + container.scrollLeft;
      if (!(left + b.width < x1 || left > x2 || top + b.height < y1 || top > y2)) s.add(n.dataset.path);
    });
    pane.paintSel();
  };
  document.addEventListener('mousedown', ev => {
    if (ev.button !== 0 || ev.target.closest('input,select,button,.ck,.det,#ov,th,.chip,.ctx,[draggable="true"],.phead')) return;
    { const r = ev.target.closest('[data-path]'), pn = r?.closest('.pane')?._pane; if (r && pn && pn.S().has(r.dataset.path)) return; } // صف محدد: سحب لا تحديد بالمستطيل
    const c = ev.target.closest('.plist,.pgrid,.col'); if (!c || !c.querySelector('[data-path]')) return;
    container = c; pane = c.closest('.pane')._pane; start = toContent(ev.clientX, ev.clientY); base = (ev.shiftKey || ev.metaKey || ev.ctrlKey) ? new Set(pane.S()) : new Set(); box = null; last = ev;
  });
  document.addEventListener('mousemove', ev => {
    if (!start) return; last = ev;
    if (!box) {
      const st = { x: start.x - container.scrollLeft + container.getBoundingClientRect().left, y: start.y - container.scrollTop + container.getBoundingClientRect().top };
      if (Math.hypot(ev.clientX - st.x, ev.clientY - st.y) < 6) return;
      box = el('div', undefined, 'marq'); document.body.append(box); document.body.classList.add('dragging'); dragFlag = true;
      timer = setInterval(() => { const r = container.getBoundingClientRect(); if (last.clientY > r.bottom - 30) container.scrollTop += 18; else if (last.clientY < r.top + 30) container.scrollTop -= 18; if (box) update(); }, 40);
    }
    update();
  });
  document.addEventListener('mouseup', () => {
    if (!start) return; clearInterval(timer);
    if (box) { box.remove(); document.body.classList.remove('dragging'); updateSummary(); updateSbar(); setTimeout(() => dragFlag = false, 0); }
    start = null; box = null;
  });
  document.addEventListener('click', ev => { if (dragFlag) { ev.stopPropagation(); ev.preventDefault(); } }, true);
}
setupMarquee();
document.addEventListener('keydown', ev => {
  if (!$('#lb').hidden) { if (ev.key === 'Escape' || ev.key === ' ') { ev.preventDefault(); closeLightbox(); } else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowDown') { ev.preventDefault(); lbStep(1); } else if (ev.key === 'ArrowRight' || ev.key === 'ArrowUp') { ev.preventDefault(); lbStep(-1); } return; }
  if ($('#ov').classList.contains('on')) { if (ev.key === 'Escape') closeModal(); return; }
  closeCtx();
  if (!$('#v-files').classList.contains('on') || !P?.src) return;
  const p = P, mod = ev.metaKey || ev.ctrlKey;
  if (mod && ev.key.toLowerCase() === 't') { ev.preventDefault(); newTab(P); return; }
  if (mod && ev.key.toLowerCase() === 'w') { ev.preventDefault(); closeTab(ws); return; }
  if (mod && ev.key.toLowerCase() === 'f') { ev.preventDefault(); topSearch.open(); return; }
  if (ev.key === 'Tab' && ws.panes.length === 2 && !ev.target.closest?.('input,select,textarea')) { ev.preventDefault(); setActive(ws.panes[1 - ws.panes.indexOf(p)]); return; }
  if (ev.target.closest?.('input,select,textarea')) { if (ev.key === 'Escape') ev.target.blur(); return; }
  const list = p.currentList(), s = p.S();
  const idx = p.cursor ? list.findIndex(x => x.path === p.cursor.path) : -1;
  const move = d => {
    const n = Math.max(0, Math.min(list.length - 1, (idx < 0 ? (d > 0 ? -1 : list.length) : idx) + d)); const e = list[n]; if (!e) return;
    if (ev.shiftKey) { if (!p.anchor) p.anchor = p.cursor?.path || e.path; const a = list.findIndex(x => x.path === p.anchor), lo = Math.min(a, n), hi = Math.max(a, n); s.clear(); list.slice(lo, hi + 1).forEach(x => s.add(x.path)); }
    p.cursor = e; showDetails(p, e); p.rerender();
    p.root.querySelector(`[data-path="${CSS.escape(e.path)}"]`)?.scrollIntoView({ block: 'nearest' });
  };
  if (ev.altKey && ev.key === 'ArrowRight') { ev.preventDefault(); p.q('.pback').click(); }
  else if (ev.altKey && ev.key === 'ArrowLeft') { ev.preventDefault(); p.q('.pfwd').click(); }
  else if (mod && ev.key.toLowerCase() === 'a') { ev.preventDefault(); list.forEach(e => s.add(e.path)); p.rerender(); }
  else if (ev.key === 'Escape') { if (p.search) p.exitSearch(); else { s.clear(); if (p.src.id === 'phone') cats.clear(); p.rerender(); } }
  else if (ev.key === 'ArrowDown' || (p.viewMode === 'grid' && ev.key === 'ArrowLeft')) { ev.preventDefault(); move(1); }
  else if (ev.key === 'ArrowUp' || (p.viewMode === 'grid' && ev.key === 'ArrowRight')) { ev.preventDefault(); move(-1); }
  else if (ev.key === ' ' && ev.shiftKey && p.cursor) { ev.preventDefault(); p.toggle(p.cursor.path); p.anchor = p.cursor.path; p.rerender(); }
  else if (ev.key === ' ') { ev.preventDefault(); openQuickLook(p); }
  else if (ev.key === 'Enter' && p.cursor && !p.cursor.is_dir && kindOf(p.cursor) === 'img') { ev.preventDefault(); openPreviewFor(p, p.cursor); }
  else if (ev.key === 'Enter' && p.cursor?.is_archive) { ev.preventDefault(); p.go(p.src.id, p.cursor.path + '::'); }
  else if (ev.key === 'Enter' && p.cursor?.is_dir) { ev.preventDefault(); p.viewMode === 'cols' ? p.openInCol(p.colData.length - 1, p.cursor) : p.go(p.src.id, p.cursor.path); }
  else if ((ev.key === 'Backspace' || (mod && ev.key === 'ArrowUp')) && p.parentPath != null) { ev.preventDefault(); p.go(p.src.id, p.parentPath); }
  else if (ev.key === 'Delete' && s.size) { ev.preventDefault(); $('#delfiles').click(); }
  else if (ev.key === 'F2') { ev.preventDefault(); renameSel(); }
  else if (mod && ev.shiftKey && ev.key.toLowerCase() === 'n') { ev.preventDefault(); newFolder(); }
  else if (mod && ev.key.toLowerCase() === 'c') { ev.preventDefault(); copySel('copy'); }
  else if (mod && ev.key.toLowerCase() === 'x') { ev.preventDefault(); copySel('cut'); }
  else if (mod && ev.key.toLowerCase() === 'v') { ev.preventDefault(); pasteHere(); }
});
function closeCtx() { document.querySelector('.ctx')?.remove(); }
document.addEventListener('click', closeCtx);
function ctxMenu(ev, e) {
  closeCtx(); const p = P, m = el('div', undefined, 'ctx'), s = p.S();
  const add = (t, f, cls) => { const d = el('div', t, cls); d.onclick = () => { closeCtx(); f(); }; m.append(d); };
  if (e) {
    if (e.is_dir) add('📂 فتح', () => p.go(p.src.id, e.path));
    if (e.is_dir && !e.is_archive) add('🔁 مزامنة هذا المجلد…', () => quickSync(p.src, e.path));
    if (e.is_archive) add('📦 فتح الأرشيف كمجلد', () => p.go(p.src.id, e.path + '::'));
    if (e.is_dir) {
      const isPinned = favList.some(f => f.under && (f.id === p.src.id || f.src === p.src.id) && f.path === e.path);
      add(isPinned ? '📌 إزالة التثبيت من الشريط الجانبي' : '📌 تثبيت تحت المصدر في الشريط الجانبي', () => togglePin(p.src, e));
    }
    if (p.search && !e.is_dir) add('📂 فتح المجلد المتضمِّن داخل زاجل', () => p.reveal(e));
    if (!e.is_dir && p.src.type === 'local' && !String(p.src.root || '').startsWith('rc:')) { add('↗ فتح بالتطبيق', () => api('/api/open', { root: p.src.root, path: e.path }).catch(x => note(x.message))); add('🔍 إظهار في Finder', () => api('/api/open', { root: p.src.root, path: e.path, reveal: true }).catch(x => note(x.message))); }
    add('📋 نسخ المسار', () => copyPathFor(p, e));
    add(s.has(e.path) ? '☐ إلغاء تحديده' : '☑ تحديد', () => { p.toggle(e.path); p.rerender(); });
    add('ⓘ المعلومات', () => { p.cursor = e; showDetails(p, e); if ($('#det').classList.contains('off')) $('#vdet').click(); });
    m.append(el('hr'));
    add('✏️ إعادة تسمية  (F2)', renameSel);
    add('📦 نقل إلى…', moveSel);
    if (selectedPaths().some(x => BOOK_RE.test(x)) || BOOK_RE.test(e?.name || '')) add('📚 إعادة تسمية الكتب…', renameBooks);
    add(`📦 تجميع المحدد (${Math.max(1, s.size)}) في مجلد جديد`, groupSel);
    add('✂️ قص', () => copySel('cut')); add('📋 نسخ', () => copySel('copy'));
  }
  if (e) { const ents = (s.has(e.path) && s.size > 1 ? p.entries.filter(x => s.has(x.path)) : [e]).map(x => ({ path: x.path, name: x.name, is_dir: x.is_dir })), isF = ents.every(x => isFav(p.src.id, x.path)); add(isF ? '☆ إزالة من المفضلة' : `⭐ إضافة إلى المفضلة${ents.length > 1 ? ' (' + ents.length + ')' : ''}`, () => toggleFavPaths(p, ents)); }
  add('📁 مجلد جديد  (⇧⌘N)', newFolder);
  if (clip) add(`📥 لصق ${clip.paths.length} عنصر هنا`, pasteHere);
  if (e) {
    add('☑ تحديد الكل', () => $('#selall').click());
    m.append(el('hr'));
    add(`⬇️ نسخ احتياطي للمحدد (${s.size}) إلى الوجهة`, () => { if (!$('#start').disabled) $('#start').click(); else note('اختر وجهة وتأكد من التحديد.'); });
    m.append(el('hr')); add('🗑️ حذف…  (Delete)', () => $('#delfiles').click(), 'dg');
  }
  document.body.append(m);
  m.style.left = Math.min(ev.clientX, innerWidth - 230) + 'px'; m.style.top = Math.max(4, Math.min(ev.clientY, innerHeight - m.offsetHeight - 10)) + 'px';
}
async function addAllImages() {
  note('جارٍ البحث عن كل الصور… قد يستغرق دقيقة');
  try { const r = await api('/api/images'); const s = allPanes().find(p => p.src?.id === 'phone')?.S('phone') || P.S('phone'); r.paths.forEach(x => s.add(x)); note(`أُضيفت ${r.count} صورة. ${r.warning || ''}`); P.rerender(); }
  catch (e) { note(e.message); }
}

/* ---------- التطبيقات ---------- */
let apps = null, appMeta = {}, metaTimer = null, appDev = 'phone';
const appSerial = () => appDev === 'watch' ? (phone?.watch?.addr || '') : (phone?.serial || '');
const appQ = () => { const x = appSerial(); return x ? '?serial=' + encodeURIComponent(x) : ''; };
async function loadApps() {
  try { if (appDev === 'watch' && !appSerial()) throw new Error('الساعة غير متصلة.'); apps = (await api('/api/apps' + appQ())).packages; await pollMeta(); renderApps(); clearInterval(metaTimer); metaTimer = setInterval(pollMeta, 4000); }
  catch (e) { $('#applist').replaceChildren(el('div', e.message, 'empty err')); }
}
async function pollMeta() {
  try { const r = await api('/api/appmeta'); appMeta = r.meta; appOverrides = r.overrides || {}; const pl = r.play, gs = r.genres;
    $('#aicons').textContent = pl && pl.running ? `جارٍ الجلب… ${pl.done}/${pl.total}` : '🌐 جلب الأيقونات الناقصة';
    $('#agenres').textContent = gs && gs.running ? `جارٍ… ${gs.done}/${gs.total}` : '🌐 تحسين التصنيف';
    if ($('#v-apps').classList.contains('on') && apps) renderApps(); } catch (e) {}
}
const appName = p => appMeta[p]?.label || '';

/* ---------- تصنيف التطبيقات (للتنسيق داخل الأداة فقط) ---------- */
const CATS = ['الإنتاجية', 'الكتابة والملاحظات', 'التواصل', 'الإسلاميات', 'التعليم', 'الوسائط', 'الذكاء الاصطناعي', 'المطورون', 'الأدوات والنظام', 'الإنترنت', 'المال والتسوق', 'السفر والخرائط', 'الصحة وأسلوب الحياة', 'أخبار وكتب', 'الألعاب', 'أخرى'];
const GENRE_MAP = { PRODUCTIVITY: 'الإنتاجية', BUSINESS: 'الإنتاجية', EVENTS: 'الإنتاجية', TOOLS: 'الأدوات والنظام', PERSONALIZATION: 'الأدوات والنظام', WEATHER: 'الأدوات والنظام', COMMUNICATION: 'التواصل', SOCIAL: 'التواصل', DATING: 'التواصل', EDUCATION: 'التعليم', BOOKS_AND_REFERENCE: 'أخبار وكتب', NEWS_AND_MAGAZINES: 'أخبار وكتب', MUSIC_AND_AUDIO: 'الوسائط', VIDEO_PLAYERS: 'الوسائط', PHOTOGRAPHY: 'الوسائط', ENTERTAINMENT: 'الوسائط', ART_AND_DESIGN: 'الوسائط', COMICS: 'الوسائط', FINANCE: 'المال والتسوق', SHOPPING: 'المال والتسوق', TRAVEL_AND_LOCAL: 'السفر والخرائط', MAPS_AND_NAVIGATION: 'السفر والخرائط', AUTO_AND_VEHICLES: 'السفر والخرائط', HEALTH_AND_FITNESS: 'الصحة وأسلوب الحياة', LIFESTYLE: 'الصحة وأسلوب الحياة', FOOD_AND_DRINK: 'الصحة وأسلوب الحياة', MEDICAL: 'الصحة وأسلوب الحياة', HOUSE_AND_HOME: 'الصحة وأسلوب الحياة', PARENTING: 'الصحة وأسلوب الحياة', BEAUTY: 'الصحة وأسلوب الحياة', LIBRARIES_AND_DEMO: 'المطورون' };
const HEUR = [['الذكاء الاصطناعي', /chatgpt|openai|gemini|claude|perplexity|copilot|genspark|mistral|deepseek|grok|\.ai\b|\bai[.\s_-]|chatbot|aichat/], ['الإسلاميات', /quran|islam|muslim|prayer|salah|salat|hadith|\bdua\b|athan|adhan|qibla|shamela|ramadan|tafsir|mushaf|turath|sunnah|qur|قرآن|إسلام|صلاة|أذكار|حديث|قبلة|مصحف/], ['المطورون', /github|termux|androidstudio|developer|\badb\b|terminal|ssh|devtools|code\b|\bide\b|debug/], ['الكتابة والملاحظات', /notes?\b|notion|obsidian|evernote|writer|markor|simplenote|journal|diary|keep\b|docs\b|document|memo|ملاحظ|كتابة/], ['التواصل', /whatsapp|telegram|signal|messenger|instagram|facebook|twitter|tiktok|snapchat|discord|viber|kakao|messages|\bsms\b|dialer|contacts|\bmms\b|\bchat\b|threads|\bx\.android/], ['التعليم', /duolingo|language|learn|dictionary|translate|school|edu|course|lms|mediu|coursera|quizlet|study|classroom|دراسة|تعليم/], ['الوسائط', /music|player|video|camera|gallery|photos?|spotify|youtube|netflix|podcast|audio|recorder|radio|vlc|editor|capcut|screenshot|مسجل|صوت/], ['المال والتسوق', /bank|\bpay|wallet|shop|amazon|mercado|cart|store|finance|invest|crypto|binance|paypal|ebay|temu|aliexpress/], ['السفر والخرائط', /maps?\b|uber|taxi|travel|booking|airbnb|flight|waze|transit|navigation|cabify|rappi/], ['الإنترنت', /browser|chrome|firefox|brave|edge|opera|duckduckgo|vpn|wifi|\bweb\b/], ['الألعاب', /game|games|puzzle|supercell|\bplay[a-z]*\.games|arcade|chess|ludo/], ['الإنتاجية', /calendar|tasks?\b|todo|office|word|excel|powerpoint|sheets|slides|drive|onedrive|dropbox|pdf|scanner|mail|gmail|outlook|trello|slack|teams|zoom|meet|reminder|planner|clock|alarm|agenda/], ['الأدوات والنظام', /com\.samsung\.|com\.android\.|com\.sec\.|settings|battery|clean|file|manager|calculator|weather|torch|flashlight|wallpaper|launcher|keyboard|widget|qr|barcode|\bgoogle\.android\./]];
function appCat(p) {
  if (appOverrides[p]) return appOverrides[p];
  const g = appMeta[p]?.genre; if (g && g !== '-') { if (g.startsWith('GAME')) return 'الألعاب'; if (GENRE_MAP[g]) return GENRE_MAP[g]; }
  const t = (p + ' ' + appName(p)).toLowerCase(); for (const [c, re] of HEUR) if (re.test(t)) return c;
  return 'أخرى';
}
/* ---------- الاستخدام والكاش ---------- */
let appUsage = null, appOverrides = {}, aGroup = store.get('agroup', '0') === '1', aView = store.get('aview', 'list'); const aColl = new Set();
function arCount(n, one, two, few, many) { return n === 1 ? one : n === 2 ? two : n <= 10 ? `${n} ${few}` : `${n} ${many}`; }
function ago(ms) {
  if (!ms) return 'لم يُستخدم'; const s = Math.max(0, (Date.now() - ms) / 1000);
  if (s < 90) return 'الآن';
  if (s < 3600) return 'قبل ' + arCount(Math.round(s / 60), 'دقيقة', 'دقيقتين', 'دقائق', 'دقيقة');
  if (s < 86400) return 'قبل ' + arCount(Math.round(s / 3600), 'ساعة', 'ساعتين', 'ساعات', 'ساعة');
  if (s < 2592000) return 'قبل ' + arCount(Math.round(s / 86400), 'يوم', 'يومين', 'أيام', 'يومًا');
  if (s < 31536000) return 'قبل ' + arCount(Math.round(s / 2592000), 'شهر', 'شهرين', 'أشهر', 'شهرًا');
  return `قبل ${(s / 31536000).toFixed(1)} سنة`;
}
async function loadUsage() {
  $('#ausage').textContent = 'جارٍ القراءة…';
  try { appUsage = (await api('/api/appusage' + appQ())).usage; note(`قُرئ استخدام ${Object.keys(appUsage).length} تطبيقًا.`); }
  catch (e) { note(e.message); done('تعذّرت قراءة الاستخدام', [e.message]); }
  $('#ausage').textContent = '📊 قراءة الاستخدام والكاش'; renderApps();
}
const useOf = p => appUsage?.[p];
const sortKeys = { last: p => -(useOf(p)?.last || 0), lastold: p => (useOf(p)?.last || 0), cache: p => -(useOf(p)?.cache || 0), app: p => -(useOf(p)?.app || 0), data: p => -(useOf(p)?.data || 0), launches: p => -(useOf(p)?.launches || 0) };
function appMetaLine(p) {
  const u = useOf(p); const box = el('span', undefined, 'ause'); if (!u) return box;
  box.append(el('b', ago(u.last))); box.append(document.createElement('br'));
  box.append(document.createTextNode(`كاش ${u.cache != null ? fsize(u.cache) : '—'} · فتح ${u.launches || u.resumes || 0}`)); return box;
}
function catMenu(ev, p) {
  ev.preventDefault(); ev.stopPropagation(); closeCtx(); const m = el('div', undefined, 'ctx');
  const add = (t, f, cls) => { const d = el('div', t, cls); d.onclick = () => { closeCtx(); f(); }; m.append(d); };
  add('📤 سحب APK', () => pullApkFor([p]));
  add('🗑️ حذف (إلغاء التثبيت)', () => uninstallApps([p]), 'dg');
  m.append(el('hr'));
  const ch = el('div', `نقل «${appName(p) || p}» إلى مجموعة:`, 'muted'); ch.style.cursor = 'default'; m.append(ch);
  CATS.forEach(c => { const d = el('div', (appCat(p) === c ? '● ' : '') + c); d.onclick = async () => { closeCtx(); const r = await api('/api/appgroups', { pkg: p, cat: c }); appOverrides = r.overrides; renderApps(); }; m.append(d); });
  if (appOverrides[p]) { m.append(el('hr')); const d = el('div', '↺ إعادة التصنيف التلقائي'); d.onclick = async () => { closeCtx(); const r = await api('/api/appgroups', { pkg: p, cat: null }); appOverrides = r.overrides; renderApps(); }; m.append(d); }
  document.body.append(m); m.style.left = Math.min(ev.clientX, innerWidth - 230) + 'px'; m.style.top = Math.max(4, Math.min(ev.clientY, innerHeight - 420)) + 'px';
}
function appRow(p) {
  const r = el('div', undefined, 'row app'), m = appMeta[p], ai = el('span', (appName(p) || p)[0]?.toUpperCase() || '?', 'ai');
  if (m?.icon) { const img = new Image(); img.src = '/api/appicon?pkg=' + encodeURIComponent(p); img.onload = () => { ai.textContent = ''; ai.append(img); }; }
  const nm = el('div', undefined, 'an'); nm.append(el('b', appName(p) || p), el('small', p));
  const tag = el('span', appCat(p), 'acat'); tag.title = 'انقر لتغيير المجموعة'; tag.onclick = ev => catMenu(ev, p);
  r.append(check(asel.has(p), () => r.click()), ai, nm, el('span', undefined, 'sp'), appMetaLine(p), tag);
  r.onclick = ev => appClick(ev, p); r.oncontextmenu = ev => catMenu(ev, p);
  return r;
}
function appCard(p) {
  const c = el('div', undefined, 'acard' + (asel.has(p) ? ' sel' : '')), m = appMeta[p], ai = el('span', (appName(p) || p)[0]?.toUpperCase() || '?', 'ai');
  if (m?.icon) { const img = new Image(); img.src = '/api/appicon?pkg=' + encodeURIComponent(p); img.onload = () => { ai.textContent = ''; ai.append(img); }; }
  const u = useOf(p); c.append(check(asel.has(p), () => c.click()), ai, el('b', appName(p) || p), el('small', u ? ago(u.last) : appCat(p)));
  c.title = `${appName(p) || p}\n${p}\n${appCat(p)}${u ? `\nآخر استخدام: ${ago(u.last)}\nالكاش: ${u.cache != null ? fsize(u.cache) : '—'}` : ''}`;
  c.onclick = ev => appClick(ev, p); c.oncontextmenu = ev => catMenu(ev, p);
  return c;
}
/* تحديد التطبيقات: نقرة = تبديل، Shift+نقرة = كل ما بين آخر نقرة وهذه، ⌘+نقرة = تبديل دون فقد الباقي */
let appAnchor = null, appShown = [];
function appClick(ev, p) {
  if (ev.shiftKey && appAnchor && appShown.includes(appAnchor)) {
    const a = appShown.indexOf(appAnchor), b = appShown.indexOf(p), on = !asel.has(p) || asel.has(appAnchor);
    appShown.slice(Math.min(a, b), Math.max(a, b) + 1).forEach(x => on ? asel.add(x) : asel.delete(x));
  } else { asel.has(p) ? asel.delete(p) : asel.add(p); appAnchor = p; }
  renderApps(); updateSummary();
}
document.addEventListener('keydown', ev => {
  if (!$('#v-apps')?.classList.contains('on') || ev.target.closest?.('input,select,textarea')) return;
  if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === 'a') { ev.preventDefault(); appShown.forEach(x => asel.add(x)); renderApps(); updateSummary(); }
  else if (ev.key === 'Escape') { asel.clear(); renderApps(); updateSummary(); }
});
function renderApps() {
  const f = $('#aq').value.toLowerCase(), box = $('#applist'); box.replaceChildren();
  const sk = $('#asort').value; let shown = appShown = apps.filter(p => p.toLowerCase().includes(f) || appName(p).toLowerCase().includes(f) || appCat(p).includes(f));
  shown.sort((a, b) => sk === 'name' || !sortKeys[sk] ? (appName(a) || a).localeCompare(appName(b) || b, 'ar') : (sortKeys[sk](a) - sortKeys[sk](b)) || (appName(a) || a).localeCompare(appName(b) || b, 'ar'));
  const named = Object.keys(appMeta).length;
  $('#acount').textContent = `${shown.length} من ${apps.length}` + (named < apps.length ? ` · تحميل الأسماء ${named}/${apps.length}` : '');
  $('#agroup').classList.toggle('pri', aGroup); $('#aview').textContent = aView === 'grid' ? '☰ قائمة' : '▦ أيقونات';
  const build = list => { if (aView === 'grid') { const g = el('div', undefined, 'appgrid'); list.forEach(p => g.append(appCard(p))); return g; } const g = el('div'); list.forEach(p => g.append(appRow(p))); return g; };
  if (!aGroup) { box.append(build(shown.slice(0, 600))); if (shown.length > 600) box.append(el('div', 'تُعرض أول ٦٠٠ نتيجة؛ ضيّق البحث.', 'empty')); return; }
  const by = new Map(); CATS.forEach(c => by.set(c, [])); shown.forEach(p => { const c = appCat(p); (by.get(c) || by.get('أخرى')).push(p); });
  by.forEach((list, c) => {
    if (!list.length) return; const open = !aColl.has(c);
    const hd = el('div', undefined, 'agrp'), cache = appUsage ? list.reduce((a, p) => a + (useOf(p)?.cache || 0), 0) : 0;
    hd.append(el('span', (open ? '▾ ' : '▸ ') + c), el('span', `${list.length} تطبيق`, 'muted'), el('span', undefined, 'sp'), el('span', appUsage ? `كاش ${fsize(cache)}` : '', 'muted'));
    const sel = btn('تحديد المجموعة', () => { list.forEach(p => asel.add(p)); renderApps(); updateSummary(); }); sel.onclick = ev => { ev.stopPropagation(); list.forEach(p => asel.add(p)); renderApps(); updateSummary(); }; hd.append(sel);
    hd.onclick = () => { open ? aColl.add(c) : aColl.delete(c); renderApps(); };
    box.append(hd); if (open) box.append(build(list));
  });
}
$('#asort').onchange = () => { if (sortKeys[$('#asort').value] && !appUsage) loadUsage(); else renderApps(); };
$('#agroup').onclick = () => { aGroup = !aGroup; store.set('agroup', aGroup ? '1' : '0'); renderApps(); };
$('#aview').onclick = () => { aView = aView === 'grid' ? 'list' : 'grid'; store.set('aview', aView); renderApps(); };
$('#ausage').onclick = loadUsage;
$('#adev').onclick = () => { appDev = appDev === 'phone' ? 'watch' : 'phone'; $('#adev').textContent = appDev === 'watch' ? '⌚ الساعة' : '📱 الهاتف'; apps = null; asel.clear(); loadApps(); };
$('#aapk').onclick = () => openModal(m => {
  const dev = appDev === 'watch' ? 'الساعة' : 'الهاتف';
  m.append(el('h3', 'تثبيت ملف APK على ' + dev));
  const zone = el('div', undefined, 'apkdrop'); zone.append(el('div', '📥', 'apkdropi'), el('b', 'اسحب ملف APK وأفلته هنا'));
  const pick = el('button', '📂 اختر ملفًا…', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
  cancel.onclick = closeModal; acts.append(cancel, pick); m.append(zone, acts);
  const finish = (r, name) => { done(r.ok ? 'تم تثبيت ' + name : 'فشل التثبيت', r.ok ? [] : [r.detail || r.error]); apps = null; loadApps(); };
  const busy = name => $('#modal').replaceChildren(el('h3', 'جارٍ التثبيت على ' + dev + '…'), el('p', name, 'muted'));
  pick.onclick = async () => {
    let r; try { r = await api('/api/choose-file', {}); } catch (e) { note(e.message); return; }
    if (!r.path) return; const name = r.path.split('/').pop();
    if (!/\.apks?$/i.test(name)) { note('اختر ملف apk أو apks.'); return; }
    busy(name); try { finish(await post('/api/install-apk', { path: r.path, serial: appSerial() || undefined }), name); } catch (e) { done('فشل التثبيت', [e.message]); }
  };
  zone.ondragover = ev => { ev.preventDefault(); ev.stopPropagation(); zone.classList.add('over'); };
  zone.ondragleave = () => zone.classList.remove('over');
  zone.ondrop = async ev => {
    ev.preventDefault(); ev.stopPropagation(); zone.classList.remove('over');
    const fs = [...(ev.dataTransfer.files || [])].filter(x => /\.apks?$/i.test(x.name));
    if (!fs.length) { note('أفلت ملف apk أو apks.'); return; }
    const label = fs.length > 1 ? `${fs.length} ملفات (تطبيق مقسّم)` : fs[0].name; busy(label);
    try {
      const batch = Math.random().toString(36).slice(2, 12); let r;
      for (let i = 0; i < fs.length; i++) {
        const q = `/api/install-apk-upload?name=${encodeURIComponent(fs[i].name)}&batch=${batch}&last=${i === fs.length - 1 ? 1 : 0}` + (appSerial() ? `&serial=${encodeURIComponent(appSerial())}` : '');
        const res = await fetch(q, { method: 'POST', headers: { 'Content-Type': 'application/octet-stream' }, body: fs[i] });
        r = await res.json(); if (!res.ok && r.error) throw new Error(r.error);
      }
      finish(r, label);
    } catch (e) { done('فشل التثبيت', [e.message]); }
  };
});
$('#agenres').onclick = async () => { try { await api('/api/appgenres/fetch', {}); pollMeta(); } catch (e) { note(e.message); } };
$('#aicons').onclick = async () => { try { await api('/api/appicons/fetch', {}); pollMeta(); } catch (e) { note(e.message); } };
$('#aq').oninput = renderApps;
$('#aall').onclick = () => { const f = $('#aq').value.toLowerCase(); apps.filter(p => p.toLowerCase().includes(f) || appName(p).toLowerCase().includes(f)).forEach(p => asel.add(p)); renderApps(); updateSummary(); };
$('#aclr').onclick = () => { asel.clear(); renderApps(); updateSummary(); };

/* ---------- نافذة التأكيد والحذف والتثبيت ---------- */
function openModal(build) { const m = $('#modal'); m.replaceChildren(); build(m); $('#ov').classList.add('on'); }
function closeModal() { $('#ov').classList.remove('on'); }
$('#ov').onclick = e => { if (e.target === $('#ov')) closeModal(); };
function listBox(lines) { const b = el('div', undefined, 'list'); lines.slice(0, 200).forEach(t => b.append(el('div', t))); if (lines.length > 200) b.append(el('div', `… و${lines.length - 200} أخرى`)); return b; }
/* تأكيد مزدوج: «موافق» ثم رسالة ثانية «موافق» (بدل كتابة كلمة). */
function typedConfirm(m, _word, onOk, label) {
  const ok = el('button', 'موافق', 'btn danger'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
  cancel.onclick = closeModal;
  ok.onclick = () => {
    const box = el('div', undefined, 'warnbox final');
    box.append(el('b', '⚠️ تأكيد أخير'), el('div', `هل أنت متأكد؟ سيتم تنفيذ «${label}» ولا يمكن التراجع عنه.`));
    const ok2 = el('button', 'موافق', 'btn danger'), back = el('button', 'رجوع', 'btn'), acts2 = el('div', undefined, 'acts');
    back.onclick = closeModal; ok2.onclick = onOk;
    acts2.append(back, ok2); acts.replaceWith(box, acts2);
    ok2.focus();
  };
  acts.append(cancel, ok); m.append(acts); return ok;
}
const done = (title, bad) => openModal(m2 => { m2.append(el('h3', title)); if (bad?.length) m2.append(listBox(bad)); const b = el('button', 'حسنًا', 'btn pri'); b.onclick = closeModal; const a = el('div', undefined, 'acts'); a.append(b); m2.append(a); });
async function post(path, body) { return api(path, { ...body, confirm: true, ...(phone?.serial ? { serial: phone.serial } : {}) }); }

/* ---------- عمليات الملفات (مجلد جديد، تسمية، نقل، نسخ، تجميع، حذف) ---------- */
let clip = null, opsTimer = null, opsList = [], pendingRefresh = false;
window.opsListRaw = () => opsList;
async function startOp(body) { pendingRefresh = true; try { const r = await api('/api/ops/start', body); loadOps(); return r; } catch (e) { pendingRefresh = false; note(e.message); done('تعذّر تنفيذ العملية', [e.message]); } }
function pollOps(fast) { clearTimeout(opsTimer); opsTimer = setTimeout(loadOps, fast ? 500 : 4000); }
/* عمليات الواجهة نفسها (التحليل…) تظهر مع عمليات الخادم */
const LOPS = new Map(); let lopSeq = 0;
function lop(title) { const id = 'l' + (++lopSeq), o = { id, title, state: 'running', detail: '', started: Date.now() / 1000, local: true }; LOPS.set(id, o); renderOps(); autoShowOps(id);
  return { set(d) { o.detail = d; renderOps(); }, end(st = 'done') { o.state = st; renderOps(); setTimeout(() => { LOPS.delete(id); renderOps(); }, 20000); } }; }
const opsSeen = new Set();
function autoShowOps(id) { if (opsSeen.has(id)) return; opsSeen.add(id); if ($('#det').classList.contains('off') && document.body.dataset.sec !== 'clean') $('#vdet').click(); $('#opsPanel').classList.remove('flash'); void $('#opsPanel').offsetWidth; $('#opsPanel').classList.add('flash'); }
async function loadOps() {
  try { opsList = (await api('/api/ops/list')).ops; opsNotify(opsList); if (!loadOps.primed) { opsList.forEach(o => opsSeen.add(o.id)); loadOps.primed = true; } opsList.filter(o => o.state === 'running').forEach(o => autoShowOps(o.id)); renderOps(); } catch (_) {}
  const running = opsList.some(o => o.state === 'running'); pollOps(running);
  if (!running && pendingRefresh) { pendingRefresh = false; allPanes().forEach(p => p.refreshNow()); }
}
const opsPrev = new Map(); let opsBatch = [], opsBatchTimer = null;
/* إشعارات الانتهاء تُجمَّع: عمليات كثيرة متتابعة (أتمتة ونسخ ومزامنة) تظهر رسالة واحدة بعددها بدل رسالة لكل عملية */
function opsFlush() {
  opsBatchTimer = null; const L = opsBatch; opsBatch = []; if (!L.length || !window.uiToast) return;
  if (L.length === 1) { const o = L[0], nerr = o.errors?.length || 0, sz = o.bytes_total ? ' (' + fsize(o.bytes_total) + ')' : '';
    if (o.state === 'cancelled') window.uiToast('أُوقفت العملية: ' + o.title);
    else if (o.state === 'error' || nerr) window.uiToast('تعذّر في «' + o.title + '»: ' + (o.errors?.[0] || o.detail || 'فشلت العملية').slice(0, 140) + (nerr > 1 ? ` (+${nerr - 1} أخطاء)` : ''));
    else window.uiToast('تمت «' + o.title + '» بنجاح' + sz + (o.detail ? ' — ' + o.detail : o.total ? ` — ${o.done} عنصرًا` : '')); }
  else { const bad = L.filter(o => o.state === 'error' || o.errors?.length).length, items = L.reduce((n, o) => n + (o.done || 0), 0), bytes = L.reduce((n, o) => n + (o.bytes_total || 0), 0);
    window.uiToast(bad ? `انتهت ${L.length} عمليات: ${L.length - bad} ناجحة و${bad} فيها أخطاء (افتح لوحة العمليات)` : `تمت ${L.length} عمليات بنجاح — ${items} عنصرًا` + (bytes ? ' (' + fsize(bytes) + ')' : '')); }
  if (document.body.dataset.sec === 'sync' || $('#v-sync')?.classList.contains('on')) setTimeout(() => loadSyncView(), 400);
}
function opsNotify(list) {
  const first = !opsPrev.size && !loadOps.primed;
  list.forEach(o => {
    const was = opsPrev.get(o.id); opsPrev.set(o.id, o.state);
    if (first || was !== 'running' || o.state === 'running') return;
    opsBatch.push(o); clearTimeout(opsBatchTimer); opsBatchTimer = setTimeout(opsFlush, 2500);
  });
}
function syPaintProg() {
  document.querySelectorAll('.sy-prog[data-op]').forEach(box => {
    const o = (window.opsListRaw() || []).find(x => x.id === box.dataset.op); if (!o) return;
    const hasB = o.bytes_total > 0, pct = hasB ? o.bytes_done / o.bytes_total * 100 : (o.total ? o.done / o.total * 100 : 3);
    box.querySelector('i').style.width = Math.max(2, Math.min(100, pct)).toFixed(1) + '%';
    box.querySelector('.t').textContent = (o.total ? `${o.done} من ${o.total} ملف` : 'يحضّر القائمة…') + (hasB ? ' · ' + fsize(o.bytes_done) + ' من ' + fsize(o.bytes_total) : '') + (o.speed ? ' · ' + fsize(o.speed) + '/ث' : '') + (o.current ? ' · ' + o.current.split('/').pop() : '');
  });
}
function renderOps() {
  const box = $('#opsPanel'); box.replaceChildren();
  const opsList = [...LOPS.values(), ...window.opsListRaw()];
  const h = el('h4'); h.append(el('span', 'العمليات'), el('span', opsList.filter(o => o.state === 'running').length ? 'جارية…' : '', 'muted')); box.append(h);
  if (!opsList.length) box.append(el('p', 'لا عمليات بعد. كل نسخ أو نقل أو حذف يظهر هنا.', 'muted'));
  opsList.slice(0, 14).forEach(o => {
    const r = el('div', undefined, 'op ' + o.state), t = el('div', undefined, 'ot');
    t.append(el('span', o.title), el('span', { running: '⏳', done: '✓', error: '✗', cancelled: '⏹' }[o.state] || ''));
    if (o.local) { r.onclick = () => opDetails(o); r.append(t); if (o.state === 'running') { const bar = el('div', undefined, 'bar indet'), i = el('i'); i.style.width = '35%'; bar.append(i); r.append(bar); } if (o.detail) r.append(el('small', o.detail)); box.append(r); return; }
    if (o.state === 'running') {
      const pz = el('button', o.paused ? '▶' : '⏸', 'x pz'); pz.title = o.paused ? 'استئناف' : 'إيقاف مؤقت'; pz.setAttribute('aria-label', pz.title);
      pz.onclick = async () => { await api('/api/ops/pause', { id: o.id, paused: !o.paused }); loadOps(); };
      const x = el('button', '⏹', 'x'); x.title = 'إلغاء'; x.onclick = () => api('/api/ops/cancel', { id: o.id }); t.append(pz, x);
      if (o.paused) r.classList.add('paused');
    }
    r.append(t);
    const hasB = o.bytes_total > 0, pct = hasB ? o.bytes_done / o.bytes_total * 100 : (o.total ? o.done / o.total * 100 : 5);
    if (o.state === 'running') {
      const bar = el('div', undefined, 'bar'), i = el('i'); i.style.width = Math.max(2, pct) + '%'; bar.append(i);
      const eta = o.eta != null ? (o.eta >= 3600 ? Math.floor(o.eta / 3600) + ':' : '') + String(Math.floor(o.eta % 3600 / 60)).padStart(o.eta >= 3600 ? 2 : 1, '0') + ':' + String(o.eta % 60).padStart(2, '0') : '';
      const meta = el('div', undefined, 'opmeta');
      meta.append(el('span', hasB ? `${fsize(o.bytes_done)} من ${fsize(o.bytes_total)}` : `${o.done} من ${o.total}`), el('span', o.speed && !o.paused ? fsize(o.speed) + '/ث' : ''), el('span', o.paused ? 'متوقف مؤقتًا' : eta ? 'باقٍ ' + eta : ''));
      r.append(bar, meta, el('small', o.current ? o.current.split('/').pop() : ''));
    }
    else {
      r.append(el('small', (o.errors?.[0] ? o.errors[0] : o.detail || `${o.done}/${o.total}`) + (hasB && o.state === 'done' ? '  ·  ' + fsize(o.bytes_total) : '') + (o.time ? '  ·  ' + o.time.slice(11, 16) : '')));
      if (o.retry) { const rb = el('button', 'إعادة محاولة الفاشل (' + o.retry.paths.length + ')', 'btn retry'); rb.onclick = () => startOp(o.retry); r.append(rb); }
    }
    if (o.errors?.length) r.title = o.errors.join('\n');
    r.onclick = ev => { if (ev.target.closest('button')) return; opDetails(o); };
    box.append(r);
  });
  syPaintProg();
}
function promptModal(title, label, value, okLabel, onOk) {
  openModal(m => {
    m.append(el('h3', title), el('p', label, 'muted'));
    const inp = el('input'); inp.type = 'text'; inp.value = value;
    const ok = el('button', okLabel, 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    const go = () => { const v = inp.value.trim(); if (v) { closeModal(); onOk(v); } };
    ok.onclick = go; cancel.onclick = closeModal; inp.onkeydown = e => { if (e.key === 'Enter') go(); };
    acts.append(cancel, ok); m.append(inp, acts); setTimeout(() => { inp.focus(); inp.select(); }, 60);
  });
}
const selectedPaths = () => { const s = P.S(); return [...s].length ? [...s] : (P.cursor ? [P.cursor.path] : []); };
const nameOf = p => p.split('/').pop();
function newFolder() { if (!P?.src?.online) return; const ref = srcRef(P.src), parent = P.cur; promptModal('مجلد جديد', 'اسم المجلد في المكان الحالي:', 'مجلد جديد', 'أنشئ', name => startOp({ kind: 'mkdir', src: ref, parent, name })); }
function renameSel() {
  const p = selectedPaths(), ref = srcRef(P.src); if (p.length !== 1) { note('اختر عنصرًا واحدًا لإعادة تسميته.'); return; }
  promptModal('إعادة تسمية', 'الاسم الجديد:', nameOf(p[0]), 'غيّر', name => startOp({ kind: 'rename', src: ref, paths: p, name }));
}
/* ---------- نتائج المساعد: نسخ ومعاينة وفتح في المكان (تُستعمل من نافذة المساعد) ---------- */
const entrySrc = sid => sources.find(x => x.id === sid) || (String(sid).startsWith('phone:') ? sources.find(x => x.id === 'phone') : null);
function copyEntries(items) {
  const groups = new Map();
  items.forEach(it => { const s = entrySrc(it.sid); if (s && s.type !== 'kindle') { if (!groups.has(s.id)) groups.set(s.id, { s, paths: [] }); groups.get(s.id).paths.push(it.path); } });
  if (!groups.size) { note('لا يمكن نسخ هذه العناصر: مصدرها غير متصل.'); return; }
  const total = [...groups.values()].reduce((a, g) => a + g.paths.length, 0);
  openModal(m => {
    m.append(el('h3', `نسخ ${total > 1 ? total + ' عناصر' : 'العنصر'} إلى…`), el('p', 'تبقى الأصول في أماكنها كما هي؛ يُنسخ إلى الوجهة فقط.', 'muted'));
    const selSrc = document.createElement('select'); selSrc.className = 'search'; selSrc.style.width = '100%'; selSrc.style.margin = '8px 0';
    sources.filter(s => s.online && s.type !== 'ios' && s.type !== 'kindle').forEach(s => { const o = el('option', s.label); o.value = s.id; if (s.id === (P?.src?.id || 'home')) o.selected = true; selSrc.append(o); });
    const pickBox = el('div', undefined, 'fpick'); pickBox.style.maxHeight = '280px';
    let targetDir = '', targetSrc = null;
    const updatePicker = sid => { const s = sources.find(x => x.id === sid); targetSrc = s; targetDir = s.type === 'adb' ? '/sdcard' : (s.home || ''); folderPicker(pickBox, sid, targetDir, (dir, sx) => { targetDir = dir; targetSrc = sx || s; }); };
    selSrc.onchange = () => updatePicker(selSrc.value);
    m.append(el('div', 'المكان المستهدف (ويمكنك إنشاء مجلد جديد من «＋ مجلد جديد»):', 'muted'), selSrc, pickBox);
    updatePicker(selSrc.value);
    const ok = el('button', 'انسخ إلى هنا', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    cancel.onclick = closeModal;
    ok.onclick = () => { closeModal(); groups.forEach(g => startOp({ kind: 'copy', src: srcRef(g.s), paths: g.paths, dst: srcRef(targetSrc), dst_dir: targetDir, policy: 'keep' })); note('بدأ نسخ ' + total + ' — يظهر تقدّمه في شريط العمليات.'); };
    acts.append(cancel, ok); m.append(acts);
  });
}
function previewEntries(items, i) {
  const list = items.map(it => { const s = entrySrc(it.sid); if (!s) return null; const p = { src: s }, e = { path: it.path, name: it.name, mod: it.mod || 0, size: it.size, is_dir: !!it.is_dir };
    return { title: it.name, url: it.is_dir ? null : previewUrl(p, e), fallback: thumbUrl(p, e), meta: `${it.is_dir ? 'مجلد' : fsize(it.size)}  ·  ${s.label}`, icon: it.is_dir ? '📁' : EXT.arc.test(it.name) ? '📦' : EXT.aud.test(it.name) ? '🎵' : '📄' }; });
  const k = list.filter(Boolean); if (!k.length) { note('تعذّرت المعاينة: المصدر غير متصل.'); return; }
  openLightbox(k, Math.max(0, Math.min(i, k.length - 1)), null);
}
function entryThumb(sid, it) { const s = entrySrc(sid); return s ? thumbUrl({ src: s }, { path: it.path, name: it.name, mod: it.mod || 0, size: it.size, is_dir: !!it.is_dir }) : null; }
function revealEntry(it) {
  const s = entrySrc(it.sid); if (!s || !P) { note('المصدر غير متصل.'); return; }
  const parent = parentOf(s, it.path);
  P.reveal({ path: it.path, folder: parent ?? '', is_dir: !!it.is_dir, name: it.name }, s.id);
}
function moveSel() {
  const p = P, paths = selectedPaths(); if (!paths.length || !p?.src) return;
  openModal(m => {
    m.append(el('h3', `نقل ${paths.length > 1 ? paths.length + ' عناصر' : 'العنصر'} إلى…`));
    const selSrc = document.createElement('select'); selSrc.className = 'search'; selSrc.style.width = '100%'; selSrc.style.margin = '8px 0';
    sources.filter(s => s.online && s.type !== 'ios').forEach(s => {
      const o = el('option', s.label); o.value = s.id; if (s.id === p.src.id) o.selected = true; selSrc.append(o);
    });
    const pickBox = el('div', undefined, 'fpick'); pickBox.style.maxHeight = '280px';
    let targetDir = p.cur, targetSrc = p.src;
    const updatePicker = sid => {
      const s = sources.find(x => x.id === sid); targetSrc = s;
      const startPath = (sid === p.src.id) ? p.cur : (s.type === 'adb' ? '/sdcard' : (s.home || ''));
      targetDir = startPath;
      folderPicker(pickBox, sid, startPath, (dir, sx) => { targetDir = dir; targetSrc = sx || s; });
    };
    selSrc.onchange = () => updatePicker(selSrc.value);
    m.append(el('div', 'المكان المستهدف:', 'muted'), selSrc, pickBox);
    updatePicker(selSrc.value);
    const ok = el('button', 'انقل إلى هنا', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    cancel.onclick = closeModal;
    ok.onclick = () => {
      closeModal();
      if (p.src.id === targetSrc.id && p.cur === targetDir) { note('المجلد المستهدف هو نفسه المجلد الحالي.'); return; }
      startOp({ kind: 'move', src: srcRef(p.src), paths, dst: srcRef(targetSrc), dst_dir: targetDir, policy: 'keep' });
      p.S().clear(); p.rerender();
    };
    acts.append(cancel, ok); m.append(acts);
  });
}
function groupSel() {
  const p = P, own = selectedPaths(); if (!own.length) return;
  const other = ws.panes.length === 2 ? ws.panes.find(x => x !== p) : null, otherSel = other ? [...other.S()] : [];
  const names = own.map(x => nameOf(x).replace(/\.[^.]*$/, '')); let pre = names[0] || '';
  names.forEach(n => { while (pre && !n.startsWith(pre)) pre = pre.slice(0, -1); }); pre = pre.replace(/[\s_\-.(]+$/, '');
  const multiDirs = new Set(own.map(x => x.replace(/\/[^/]*$/, ''))).size > 1;
  openModal(m => {
    m.append(el('h3', '📦 تجميع في مجلد جديد'));
    m.append(el('p', `العناصر المحددة: ${own.length} من «${p.src.label}»${otherSel.length ? ` (+ ${otherSel.length} من «${other.src.label}»)` : ''}${multiDirs ? ' — من مجلدات مختلفة، لا مشكلة.' : '.'}`, 'muted'));
    const inp = el('input'); inp.type = 'text'; inp.value = pre.length >= 3 ? pre : 'مجلد جديد'; m.append(el('label', 'اسم المجلد الجديد:'), inp);
    const grp = (title, name, opts) => { const box = el('div', undefined, 'radiogrp'); box.append(el('b', title)); opts.forEach(([v, t, on, dis]) => { const l = el('label'), r = document.createElement('input'); r.type = 'radio'; r.name = name; r.value = v; r.checked = !!on; r.disabled = !!dis; l.append(r, document.createTextNode(' ' + t)); box.append(l); }); return box; };
    m.append(grp('ماذا نفعل بالعناصر؟', 'gmode', [['move', 'نقلها إلى المجلد الجديد (تُحذف من مكانها الأصلي)', true], ['copy', 'نسخها فقط (تبقى في مكانها الأصلي)', false]]));
    const locs = [['here', `هنا: المجلد الحالي على «${p.src.label}» (جهاز المصدر)`, true]];
    if (other) locs.push(['other', `في مجلد اللوحة الأخرى على «${other.src.label}» (الجهاز الوجهة)`, false, !other.src.online]);
    m.append(grp('أين يُنشأ المجلد الجديد؟', 'gloc', locs));
    let withOther = null;
    if (otherSel.length) { const l = el('label'), c = document.createElement('input'); c.type = 'checkbox'; c.checked = true; withOther = c; l.append(c, document.createTextNode(` ضمّ المحدد في اللوحة الأخرى أيضًا (${otherSel.length})`)); m.append(l); }
    const ok = el('button', 'جمّع', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    cancel.onclick = closeModal;
    ok.onclick = () => {
      const name = inp.value.trim(); if (!name) return;
      const mode = m.querySelector('input[name=gmode]:checked').value, loc = m.querySelector('input[name=gloc]:checked').value;
      const target = loc === 'other' && other ? other : p;
      const items = own.map(x => ({ src: srcRef(p.src), path: x }));
      if (withOther?.checked) otherSel.forEach(x => items.push({ src: srcRef(other.src), path: x }));
      closeModal(); startOp({ kind: 'gather', name, mode, dst: srcRef(target.src), parent: target.cur, items });
      p.S().clear(); p.rerender(); if (withOther?.checked) { other.S().clear(); other.rerender(); }
    };
    acts.append(cancel, ok); m.append(acts); setTimeout(() => { inp.focus(); inp.select(); }, 60);
  });
}
function copySel(mode) { const p = selectedPaths(); if (!p.length) return; clip = { src: srcRef(P.src), paths: p, mode }; note(`${mode === 'cut' ? 'قُصّ' : 'نُسخ'} ${p.length} عنصر. انتقل إلى المكان المطلوب ثم الصق (⌘V).`); }
function pasteHere() {
  if (!clip || !P?.src?.online) return;
  const c = clip; if (c.mode === 'cut') clip = null;
  startOp({ kind: c.mode === 'cut' ? 'move' : 'copy', src: c.src, paths: c.paths, dst: srcRef(P.src), dst_dir: P.cur, policy: 'keep' });
}
$('#delfiles').onclick = async () => {
  const src = P.src, S = () => P.S();
  const paths = [...S()]; if (!paths.length) { note('حدد ملفات أو مجلدات أولًا.'); return; }
  if (src.type === 'adb') {
    note('جارٍ التحقق من وجود نسخ محفوظة…');
    let chk; try { chk = (await api('/api/phone-delete-check', { paths, serial: src.serial })).items; } catch (e) { note(e.message); return; }
    const files = chk.reduce((a, c) => a + c.files, 0), bad = chk.reduce((a, c) => a + c.unverified, 0);
    openModal(m => {
      m.append(el('h3', `حذف من ${src.label}`), el('div', `سيُحذف ${chk.length} عنصر (${files} ملف) نهائيًا. لا توجد سلة مهملات.`, 'warnbox'));
      m.append(el('div', bad ? `⚠️ ${bad} ملف ليس له نسخة مطابقة محفوظة على الكمبيوتر.` : '✓ لكل الملفات نسخة مطابقة (بالبصمة) على الكمبيوتر.', bad ? 'warnbox' : 'muted'));
      m.append(listBox(chk.map(c => `${c.unverified ? '⚠️' : '✓'} ${c.path}`)));
      let allow = false;
      if (bad) { const l = el('label'), c = document.createElement('input'); c.type = 'checkbox'; c.onchange = () => allow = c.checked; l.append(c, document.createTextNode(' أسمح بحذف ما ليس له نسخة محفوظة (لا رجعة فيه)')); l.className = 'err'; m.append(l); }
      typedConfirm(m, 'حذف', async () => { closeModal(); S().clear(); await startOp({ kind: 'delete', src: srcRef(src), paths: chk.map(c => c.path), confirm: true, allow_unverified: allow }); }, 'احذف نهائيًا');
    });
    note(''); return;
  }
  openModal(m => {
    m.append(el('h3', 'نقل إلى سلة المهملات'), el('div', `سيُنقل ${paths.length} عنصر إلى سلة المهملات (يمكنك استرجاعه منها).` + (src.kind === 'cloud' ? ' تنبيه: هذا مجلد سحابة متزامن، فسيُحذف من السحابة أيضًا بعد المزامنة.' : ''), 'warnbox'), listBox(paths));
    const ok = el('button', 'انقل إلى السلة', 'btn danger'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    cancel.onclick = closeModal; ok.onclick = async () => { closeModal(); S().clear(); await startOp({ kind: 'delete', src: srcRef(src), paths, confirm: true }); };
    acts.append(cancel, ok); m.append(acts);
  });
};
// زر أيمن على مساحة فارغة من المتصفح
document.addEventListener('contextmenu', ev => { if (ev.target.closest('.plist,.pgrid,.col') && !ev.target.closest('[data-path]')) { ev.preventDefault(); ctxMenu(ev, null); } });

async function uninstallApps(list) {
  if (!list.length) { note('حدد تطبيقات أولًا.'); return; }
  let prot = []; try { prot = (await api('/api/backups/apps')).protected; } catch (_) {}
  const blocked = list.filter(p => prot.includes(p)), todo = list.filter(p => !prot.includes(p));
  openModal(m => {
    m.append(el('h3', 'إلغاء تثبيت من ' + (appDev === 'watch' ? 'الساعة' : 'الهاتف')));
    if (blocked.length) m.append(el('div', `🔒 محمية ولن تُحذف: ${blocked.map(p => appName(p) || p).join('، ')}`, 'warnbox'));
    if (!todo.length) { const b = el('button', 'حسنًا', 'btn'); b.onclick = closeModal; m.append(b); return; }
    m.append(el('div', 'يُحذف التطبيق من ' + (appDev === 'watch' ? 'الساعة' : 'الهاتف') + '، ومعه بياناته (رسائله وإعداداته) إلا إن اخترت إبقاءها. هذا لا يعتمد على وجود نسخة محفوظة منه.', 'warnbox'), listBox(todo.map(p => `${appName(p) || p}  (${p})`)));
    let keep = false; const l = el('label'), c = document.createElement('input'); c.type = 'checkbox'; c.onchange = () => keep = c.checked;
    l.append(c, document.createTextNode(' أبقِ بيانات التطبيق (يستعيدها التثبيت من جديد)')); m.append(l);
    typedConfirm(m, 'حذف', async () => {
      let ok = 0, fail = [];
      for (let i = 0; i < todo.length; i++) {
        $('#modal').replaceChildren(el('h3', `جارٍ الإلغاء… ${i + 1}/${todo.length}`), el('p', todo[i], 'muted'));
        try { const r = await post('/api/uninstall', { package: todo[i], keep_data: keep, serial: appSerial() || undefined }); r.ok ? ok++ : fail.push(`${todo[i]}: ${r.detail}`); } catch (e) { fail.push(`${todo[i]}: ${e.message}`); }
      }
      todo.forEach(p => asel.delete(p)); updateSummary(); done(`أُلغي تثبيت ${ok} من ${todo.length}`, fail); apps = null; loadApps();
    }, 'ألغِ التثبيت');
  });
}
async function pullApkFor(packages) {
  if (!packages.length) { note('حدد تطبيقات أولًا.'); return; }
  openModal(m => {
    m.append(el('h3', `سحب APK (${packages.length} تطبيق)`), el('p', 'سيتم سحب ملفات التثبيت إلى مجلد التنزيلات (Downloads/زاجل APK).', 'muted'), listBox(packages.map(p => `${appName(p) || p}  (${p})`)));
    const ok = el('button', 'ابدأ السحب', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    cancel.onclick = closeModal;
    ok.onclick = async () => {
      let good = 0, fail = [];
      for (let i = 0; i < packages.length; i++) {
        const p = packages[i];
        $('#modal').replaceChildren(el('h3', `جارٍ سحب APK… ${i + 1}/${packages.length}`), el('p', `${appName(p) || p} (${p})`, 'muted'));
        try {
          const r = await post('/api/pull-apk', { packages: [p], names: { [p]: appName(p) || p }, serial: appSerial() || undefined });
          if (r.ok && r.results?.[0]?.ok) good++;
          else fail.push(`${appName(p) || p}: ${r.results?.[0]?.detail || r.error || 'فشل السحب'}`);
        } catch (e) {
          fail.push(`${appName(p) || p}: ${e.message}`);
        }
      }
      done(`تم سحب ${good} من ${packages.length} تطبيق إلى مجلد التنزيلات.`, fail);
    };
    acts.append(cancel, ok); m.append(acts);
  });
}
$('#apull').onclick = () => pullApkFor([...asel]);
$('#auninst').onclick = () => uninstallApps([...asel]);
$('#ainst').onclick = async () => {
  let items; try { items = (await api('/api/backups/apps')).items; } catch (e) { note(e.message); return; }
  openModal(m => {
    m.append(el('h3', 'تثبيت من نسخة محفوظة'));
    if (!items.length) { m.append(el('p', 'لا توجد نسخ تطبيقات محفوظة في مجلدات النسخ.', 'muted')); const b = el('button', 'حسنًا', 'btn'); b.onclick = closeModal; m.append(b); return; }
    m.append(el('p', 'اختر التطبيقات التي تريد تثبيتها على الهاتف. إن كان التطبيق مثبّتًا بالفعل يُحدَّث بنسخته المحفوظة.', 'muted'));
    const chosen = new Set(), box = el('div', undefined, 'list'); box.style.maxHeight = '300px';
    items.forEach(it => { const row = el('div'), c = document.createElement('input'); c.type = 'checkbox'; c.onchange = () => c.checked ? chosen.add(it.folder) : chosen.delete(it.folder); row.append(c, document.createTextNode(` ${appName(it.package) || it.package} — ${it.package} (${it.files} ملف، ${it.backup.replace('Samsung_', '')})`)); box.append(row); });
    m.append(box);
    const ok = el('button', 'ثبّت المحدد', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'); cancel.onclick = closeModal;
    ok.onclick = async () => {
      const todo = [...chosen]; if (!todo.length) return; let good = 0, fail = [];
      for (let i = 0; i < todo.length; i++) {
        $('#modal').replaceChildren(el('h3', `جارٍ التثبيت… ${i + 1}/${todo.length}`), el('p', todo[i].split('/').pop(), 'muted'));
        try { const r = await post('/api/install', { folder: todo[i], serial: appSerial() || undefined }); r.ok ? good++ : fail.push(`${r.package}: ${r.detail}`); } catch (e) { fail.push(`${todo[i].split('/').pop()}: ${e.message}`); }
      }
      done(`ثُبّت ${good} من ${todo.length}`, fail); apps = null; loadApps();
    };
    const acts = el('div', undefined, 'acts'); acts.append(cancel, ok); m.append(acts);
  });
};

/* ---------- الساعة (إعدادات الاتصال) ---------- */
$('#wconn').onclick = async () => {
  $('#wres').textContent = 'جارٍ الاتصال…'; $('#wres').classList.remove('err');
  try {
    watch = await api('/api/watch/connect', { addr: $('#waddr').value.trim() });
    $('#wres').textContent = `متصلة: ${watch.model || 'ساعة'} (${watch.addr}) — ${watch.packages.length} تطبيق مثبّت. حُفظت، وسيعاد وصلها تلقائيًا.`;
    $('#wopts').style.display = 'block';
  } catch (e) { watch = null; $('#wres').textContent = e.message; $('#wres').classList.add('err'); $('#wopts').style.display = 'none'; }
  updateSummary();
};
$('#wapps').onchange = $('#wfs').onchange = updateSummary;

/* ---------- الملخص والنسخ ---------- */
const wantWatch = () => watch && ($('#wapps').checked || $('#wfs').checked);
function selectionTotals() {
  const parts = []; let any = false, local = false;
  for (const s of sources) { const n = selUnion(s.id).size + (s.id === 'phone' ? cats.size : 0); if (n) { parts.push(`${n} من ${s.label}`); any = true; if (s.type === 'local') local = true; } }
  if (asel.size) { parts.push(`${asel.size} تطبيق`); any = true; }
  if (wantWatch()) { parts.push('الساعة'); any = true; }
  return { parts, any, local };
}
function updateSummary() {
  const t = selectionTotals();
  $('#summary').textContent = t.parts.length ? 'المحدد: ' + t.parts.join(' · ') : 'لم تحدد شيئًا بعد.';
  $('#toPhoneWrap').hidden = !t.local;
  refreshStart();
}
function refreshStart() {
  const t = selectionTotals(), needPhone = selUnion('phone').size || cats.size || asel.size || ($('#toPhone').checked && t.local);
  $('#start').disabled = !(phone && !phone.busy && !picking && t.any && (phone.connected || !needPhone));
}
$('#toPhone').onchange = refreshStart;
$('#start').onclick = async () => {
  $('#start').disabled = true;
  const cloud = [];
  for (const s of sources) if (s.type === 'local') selUnion(s.id).forEach(p => cloud.push({ root: s.root, path: p, to_phone: $('#toPhone').checked }));
  try {
    await api('/api/backup', {
      categories: [...cats], paths: [...selUnion('phone')], apps: [...asel], cloud, watch_paths: [...selUnion('watch')], destination: dest.value, csv: $('#csv').checked, incremental: $('#incr').checked,
      ...(wantWatch() ? { watch: { use: true }, watchapps: $('#wapps').checked, watchfs: $('#wfs').checked } : {})
    });
    lastResult = ''; await refresh();
  } catch (e) { $('#status').textContent = e.message; $('#status').classList.add('err'); await refresh(); }
};
async function refresh() {
  if (polling) return; polling = true;
  try {
    phone = await api('/api/status');
    $('#dot').classList.toggle('ok', !!phone.connected);
    $('#devname').textContent = phone.connected ? phone.model : 'الهاتف غير متصل'; $('#devname').title = phone.connected ? `${phone.model} · ${phone.serial}` : phone.message;
    const b = phone.backup;
    $('#pb').classList.toggle('on', !!phone.busy);
    if (phone.busy) {
      $('#status').classList.remove('err'); $('#status').textContent = 'جارٍ النسخ…';
      $('#log').textContent = `أُنجز: ${b.completed?.length || 0} من ${b.total || '؟'} · جديد: ${b.copied || 0} · موجود سابقًا (تُخطّي): ${b.skipped || 0} · أخطاء: ${b.errors?.length || 0} · الآن: ${b.current || ''}`;
    } else if (b?.target && JSON.stringify(b) !== lastResult) {
      lastResult = JSON.stringify(b);
      $('#status').classList.toggle('err', !!b.errors?.length);
      $('#status').textContent = b.errors?.length ? 'انتهت العملية مع أخطاء؛ راجع التقرير.' : 'اكتمل النسخ ✓';
      $('#log').textContent = `أُنجز: ${b.completed?.length || 0} · جديد: ${b.copied || 0} · موجود سابقًا (تُخطّي): ${b.skipped || 0} · أخطاء: ${b.errors?.length || 0}${b.report ? ' · التقرير: ' + b.report : ''}`;
    }
    const vsig = JSON.stringify((phone.volumes || []).map(v => v.name));
    if (vsig !== lastVols) { const first = lastVols === null; lastVols = vsig; try { cloudRoots = (await api('/api/cloud/roots')).roots; initCleanRoots(); } catch (_) {} if (!first) initDest(); }
    if (phone.watch) {
      $('#wstate').textContent = phone.watch.ip ? (phone.watch.connected ? `الساعة المحفوظة ${phone.watch.ip}: متصلة الآن ✓` : `الساعة المحفوظة ${phone.watch.ip}: غير متصلة، أحاول إعادة الوصل تلقائيًا…`) : 'لم تُحفظ ساعة بعد.';
      if (phone.watch.ip && !$('#waddr').value) $('#waddr').value = phone.watch.ip;
      if (phone.watch.connected && !watch) $('#wconn').click();
    }
    sourceChanged(); refreshStart();
  } catch (e) { $('#devname').textContent = 'تعذر الاتصال بالخدمة المحلية.'; $('#start').disabled = true; }
  finally { polling = false; }
}

/* ---------- المعاينة بالحجم الكامل ---------- */
let lb = { items: [], i: 0, pane: null };
function previewUrl(p, e) {
  const s = p.src;
  if (s.type === 'adb') return s.serial ? `/api/preview?serial=${encodeURIComponent(s.serial)}&path=${encodeURIComponent(e.path)}&v=${e.mod}` : null;
  if (s.type === 'kindle') return null;
  if (s.type === 'ios') return `/api/ipreview?udid=${encodeURIComponent(s.udid)}&path=${encodeURIComponent(e.path)}&v=${e.mod}`;
  return `/api/lpreview?root=${encodeURIComponent(s.root)}&path=${encodeURIComponent(e.path)}&v=${e.mod}`;
}
function openPreviewFor(p, e) {
  if (kindOf(e) !== 'img') { p.cursor = e; openQuickLook(p); return; } // النصوص وPDF والصوت والفيديو: العارض نفسه
  const list = p.currentList().filter(x => !x.is_dir && kindOf(x) === 'img');
  const items = list.map(x => ({ title: x.name, url: previewUrl(p, x), fallback: thumbUrl(p, x) }));
  const i = Math.max(0, list.findIndex(x => x.path === e.path)); openLightbox(items, i);
}
function openQuickLook(p) {
  const list = p.currentList(), e = p.cursor || list.find(x => p.S().has(x.path)); if (!e) { note('حدد عنصرًا ثم اضغط المسافة للمعاينة.'); return; }
  const items = list.map(x => ({ title: x.name, entry: x, url: x.is_dir ? null : previewUrl(p, x), fallback: thumbUrl(p, x),
    meta: `${x.is_dir ? 'مجلد' : fsize(x.size)}  ·  ${fdate(x.mod)}`, icon: x.is_dir ? '📁' : EXT.arc.test(x.name) ? '📦' : EXT.aud.test(x.name) ? '🎵' : '📄' }));
  openLightbox(items, Math.max(0, list.findIndex(x => x.path === e.path)), p);
}
function openLightbox(items, i, pane) { lb = { items, i, pane }; $('#lb').hidden = false; showLb(); }
function closeLightbox() { $('#lb').hidden = true; $('#lbpic').removeAttribute('src'); }
function lbStep(d) {
  const n = lb.i + d; if (n < 0 || n >= lb.items.length) return; lb.i = n; showLb();
  const it = lb.items[n]; if (lb.pane && it.entry) { lb.pane.cursor = it.entry; lb.pane.markCursor(); lb.pane.root.querySelector(`[data-path="${CSS.escape(it.entry.path)}"]`)?.scrollIntoView({ block: 'nearest' }); }
}
function showLb() {
  const it = lb.items[lb.i], img = $('#lbpic'); if (!it) return;
  $('#lbcap').textContent = `${it.title}${it.meta ? '  ·  ' + it.meta : ''}  ·  ${lb.i + 1} / ${lb.items.length}`;
  $('#lbimg').classList.remove('zoom'); img.style.visibility = 'hidden'; $('#lbspin').style.display = ''; $('#lbspin').textContent = 'جارٍ التحميل…';
  const noPreview = () => { $('#lbspin').style.display = ''; $('#lbspin').innerHTML = ''; const c = el('div', undefined, 'qlcard'); c.append(el('div', it.icon || '📄', 'qlico'), el('b', it.title), el('div', it.meta || '', 'muted'), el('div', it.isDir || it.icon === '📁' ? '' : 'لا توجد معاينة لهذا النوع (أو الملف كبير جدًا).', 'muted')); $('#lbspin').append(c); };
  if (!it.url) { img.removeAttribute('src'); noPreview(); return; }
  let triedFallback = false;
  img.onload = () => { $('#lbspin').style.display = 'none'; img.style.visibility = 'visible'; };
  img.onerror = () => { if (!triedFallback && it.fallback) { triedFallback = true; img.src = it.fallback; } else noPreview(); };
  img.src = it.url;
  [lb.i + 1, lb.i - 1].forEach(k => { const n = lb.items[k]; if (n?.url) { const q = new Image(); q.src = n.url; } });
}
$('#lbclose').onclick = closeLightbox; $('#lbprev').onclick = () => lbStep(-1); $('#lbnext').onclick = () => lbStep(1);
$('#lb').onclick = e => { if (e.target === $('#lb') || e.target === $('#lbimg')) closeLightbox(); };
$('#lbpic').onclick = e => { e.stopPropagation(); $('#lbimg').classList.toggle('zoom'); };

/* ---------- مركز التحليل والتنظيف ---------- */
const TOOLS = [['analyze', '📊', 'تحليل المساحة', 'أين تذهب مساحة هذا المجلد؟ أحجام المجلدات والأنواع وأكبر الملفات.'],
  ['duplicates', '🗂️', 'ملفات مكررة', 'ملفات متطابقة تمامًا في المحتوى (تُقارن بالبصمة)، ولو اختلفت أسماؤها.'],
  ['similar', '🖼️', 'ملفات متشابهة', 'صور متقاربة بصريًا (حجم أصغر أو ضغط مختلف أو تعديل خفيف)، وملفات بأسماء متشابهة مثل «(1)» و«نسخة».'],
  ['caches', '🧹', 'الكاش والنظام', 'فحص كامل للجهاز: سرعة الاستيقاظ والذاكرة والبرامج المستهلكة، وما في «بيانات النظام» (نسخ السحابة، أرشيف iCloud، النماذج المحلية، بقايا الوكلاء)، والكاش والسجلات وسلة المهملات. في الجوال: واتساب وبيانات التطبيقات والسجلات والنسخ المكررة.'],
  ['large', '📦', 'الملفات الكبيرة', 'أكبر ملفات المجلد، مع تمييز ما لم يُعدَّل منذ أكثر من سنة.'],
  ['empty', '📁', 'مجلدات فارغة', 'مجلدات لا تحتوي أي ملف.'],
  ['folders', '📂', 'مجلدات متشابهة', 'مجلدان تتطابق نسبة كبيرة من محتواهما (بالحجم والاسم)، فتختار أيهما تحذف.']];
let cleanJob = null, cleanKind = '', cleanData = null, cleanTimer = null;
const cleanSel = new Set(), cleanSizes = new Map(), cleanPerm = new Set(), cleanGroupOf = new Map();
const SHORT = { analyze: 'المساحة', duplicates: 'المكرر', similar: 'المتشابه', caches: 'الكاش', large: 'الكبير', empty: 'الفارغ', folders: 'المجلدات' };
TOOLS.forEach(([k, ic, t, d]) => { const c = el('button', undefined, 'tbtn'); c.title = `${t}: ${d}`; c.append(el('span', ic, 'ti'), el('span', SHORT[k])); c.onclick = () => runScan(k); $('#ctools').append(c); });
// ===== التنظيف الكامل: فحص شامل + خطة بمشاركة الذكاء الاصطناعي + تنفيذ بعد الموافقة =====
{
  const b = el('button', undefined, 'tbtn pri'); b.title = 'يفحص كل ما تختاره (الكمبيوتر، الأقراص، السحابات) ويعرض خطة تحسين تراجعها ثم يبدأ بعد موافقتك';
  b.append(el('span', '🧹', 'ti'), el('span', 'تنظيف كامل')); b.onclick = openFullClean; $('#ctools').prepend(b);
}
function openFullClean() {
  const RISK = { safe: ['آمن', '#16a34a'], rebuild: ['يُعاد بناؤه', '#2563eb'], review: ['للمراجعة', '#d97706'], info: ['للعلم', '#64748b'], keep: ['لا تلمسه', '#dc2626'] };
  let fid = '', timer = null;
  const stop = () => { if (timer) clearInterval(timer); timer = null; };
  openModal(m => {
    m.style.maxWidth = 'min(860px,94vw)'; m.style.width = '860px';
    const body = el('div'); body.style.cssText = 'max-height:70vh;overflow:auto;display:flex;flex-direction:column;gap:8px';
    const foot = el('div'); foot.style.cssText = 'display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap';
    m.append(el('h3', '🧹 التنظيف الكامل'), body, foot);
    const close = el('button', 'إغلاق', 'btn'); close.onclick = () => { stop(); if (fid) api('/api/clean/full/cancel', { id: fid }).catch(() => {}); closeModal(); };
    const pick = () => {
      body.replaceChildren(el('p', 'اختر ما تريد تنظيفه. سيُحلَّل كل واحد (المساحة، الكاش، المكرر، الكبير، الفارغ) ثم تُعرض عليك خطة كاملة؛ لا يُنقل ولا يُحذف شيء قبل موافقتك، والتنفيذ ينقل إلى السلة.', 'muted'));
      const rank = { computer: 0, disk: 1, network: 2, cloud: 3, rclone: 3 };
      const roots = [...cloudRoots].sort((a, c) => (rank[a.group] ?? 9) - (rank[c.group] ?? 9));
      const boxes = [];
      roots.forEach(r => {
        const supported = r.group === 'computer' || r.group === 'disk' || r.group === 'rclone';
        const row = el('label'); row.style.cssText = 'display:flex;gap:8px;align-items:center;padding:6px 8px;border:1px solid var(--line);border-radius:8px;' + (supported ? 'cursor:pointer' : 'opacity:.5');
        const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = supported && r.id === 'home'; cb.disabled = !supported;
        const label = r.group === 'computer' ? '🖥️ هذا الكمبيوتر' : r.label;
        const info = r.total ? ` · ${fsize(r.total)}` : '';
        row.append(cb, el('b', label), el('small', (supported ? '' : 'غير مدعوم هنا ') + info, 'muted')); boxes.push([cb, r, label]); body.append(row);
      });
      sources.filter(s => s.type === 'adb' && s.online).forEach(s => {
        const row = el('label'); row.style.cssText = 'display:flex;gap:8px;align-items:center;padding:6px 8px;border:1px solid var(--line);border-radius:8px;cursor:pointer';
        const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = false;
        row.append(cb, el('b', `📱 ${s.label}`)); boxes.push([cb, { id: 'dev:' + s.serial }, `📱 ${s.label}`]); body.append(row);
      });
      body.append(el('small', 'يُحذف من الهاتف نهائيًا ما توافق عليه فقط', 'muted'));
      foot.replaceChildren(close);
      const go = el('button', 'ابدأ التحليل', 'btn pri'); go.onclick = async () => {
        const targets = boxes.filter(([c]) => c.checked).map(([, r, label]) => ({ root: r.id, label }));
        if (!targets.length) { note('اختر هدفًا واحدًا على الأقل.'); return; }
        try { fid = (await api('/api/clean/full/start', { targets })).id; } catch (e) { note(e.message); return; }
        watch();
      };
      foot.prepend(go);
    };
    const watch = () => {
      const cancel = el('button', 'إلغاء', 'btn'); cancel.onclick = () => api('/api/clean/full/cancel', { id: fid }).catch(() => {});
      foot.replaceChildren(cancel);
      let fails = 0;
      const tick = async () => {
        let r; try { r = await api('/api/clean/full/job?id=' + fid); fails = 0; } catch (e) {
          if (++fails < 8) return;     // انقطاع عابر (إعادة تشغيل الخادم أو انشغاله): نعيد المحاولة قبل أن نستسلم
          stop(); body.replaceChildren(el('div', '⚠️ انقطع الاتصال بزاجل (' + e.message + '). إن أُعيد تشغيل التطبيق فأعد التنظيف الكامل.', 'warnbox')); foot.replaceChildren(close); return; }
        if (r.state === 'ready') { stop(); return plan(r); }
        if (r.state === 'done') { stop(); return finish(r); }
        if (r.state === 'error' || r.state === 'cancelled') { stop(); body.replaceChildren(el('div', r.state === 'error' ? '⚠️ ' + r.error : 'أُلغي التنظيف الكامل.', 'warnbox')); foot.replaceChildren(close); return; }
        const list = el('div'); list.style.cssText = 'display:flex;flex-direction:column;gap:3px;font-size:13px';
        (r.steps || []).forEach(s => list.append(el('div', (s.state === 'done' ? '✓ ' : s.state === 'error' ? '✗ ' : '⏳ ') + s.label + (s.detail ? ' — ' + s.detail : ''))));
        body.replaceChildren(el('b', (r.state === 'planning' ? '🤖 ' : '🔎 ') + r.progress + ' · ' + r.seconds + ' ث'), list);
      };
      stop(); tick(); timer = setInterval(tick, 900);
    };
    const plan = r => {
      const P = r.plan, sel = new Set(P.items.filter(i => i.default_on).map(i => i.id));
      const total = () => P.items.filter(i => sel.has(i.id)).reduce((a, i) => a + i.size, 0);
      const btn = el('button', '', 'btn pri'), sum = () => { btn.textContent = `ابدأ التنفيذ (${sel.size} بند · نحو ${fsize(total())})`; btn.disabled = !sel.size; };
      body.replaceChildren();
      if (r.ai) { const ai = el('div'); ai.style.cssText = 'white-space:pre-wrap;line-height:1.7;border:1px solid var(--acc);border-radius:10px;padding:10px 12px;background:var(--accp)'; ai.append(el('b', '🤖 رؤية الذكاء الاصطناعي\n'), document.createTextNode(r.ai)); body.append(ai); }
      else body.append(el('div', 'تعذّر الحصول على رأي الذكاء الاصطناعي الآن؛ هذه الخطة من التحليل الآلي وحده.', 'muted'));
      if (r.health) body.append(healthBox(r.health));
      Object.entries(r.phone_health || {}).forEach(([label, h]) => { const box = healthBox(h); box.querySelector('h4').textContent = `🩺 صحة الجهاز — ${label}`; body.append(box); });
      (P.overview || []).forEach(o => body.append(el('div', `📊 ${o.target}: ${fsize(o.total)} في ${o.files.toLocaleString()} ملف — الأكبر: ${o.top.map(t => t.name + ' ' + fsize(t.size)).join('، ')}`, 'muted')));
      if (!P.items.length) body.append(el('div', '✨ لا شيء يستحق التنظيف في ما اخترته.'));
      P.items.forEach(it => {
        const row = el('div'); row.style.cssText = 'border:1px solid var(--line);border-radius:9px;padding:7px 10px;display:flex;flex-direction:column;gap:3px';
        const top = el('label'); top.style.cssText = 'display:flex;gap:8px;align-items:center;cursor:pointer';
        const cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = sel.has(it.id); cb.onchange = () => { cb.checked ? sel.add(it.id) : sel.delete(it.id); sum(); };
        const [rt, rc] = RISK[it.risk] || ['', 'inherit']; const pill = el('small', rt); pill.style.cssText = `color:${rc};border:1px solid ${rc};border-radius:99px;padding:0 7px`;
        top.append(cb, el('b', `${it.target} — ${it.title}`), pill, el('span', `${it.count.toLocaleString()} عنصر${it.size ? ' · ' + fsize(it.size) : ''}`, 'muted'));
        if (it.device) top.append(el('small', 'نهائي من الهاتف', 'rk keep'));
        const det = el('details'); det.append(el('summary', it.desc)); const ul = el('div'); ul.style.cssText = 'font-size:11.5px;direction:ltr;text-align:left;color:var(--mut);overflow-wrap:anywhere'; (it.sample || []).forEach(x => ul.append(el('div', x))); if (it.count > (it.sample || []).length) ul.append(el('div', `… و${(it.count - it.sample.length).toLocaleString()} غيرها`));
        if ((it.notes || []).length) { const notes = el('div'); notes.style.cssText = 'direction:rtl;text-align:right;color:var(--mut);font-size:12px'; it.notes.forEach(n => notes.append(el('div', 'ℹ️ ' + n))); ul.append(notes); }
        (it.unique || []).forEach(u => {
          const n = Number(u.count || 0), line = el('div', `فريد هنا: ${n} ملف (${fsize(u.size || 0)})`); line.style.cssText = 'direction:rtl;text-align:right;color:var(--mut);font-size:12px'; ul.append(line);
          if (n > 0) { const move = btn('⇢ انقل الفريد إلى المستندات', async () => {
            if (!confirm(`سيُنقل ${n} ملف (${fsize(u.size || 0)}) إلى المستندات مع الحفاظ على المجلدات. متابعة؟`)) return;
            try { const result = await api('/api/clean/move_unique', { job: it.job, archive: u.path, confirm: true }); note(`نُقل ${result.moved} ملف (${fsize(result.size)}) إلى ${result.dest}${result.skipped ? ` · تُرك ${result.skipped}` : ''}.`); }
            catch (e) { note(e.message); }
          }); ul.append(move); }
        });
        det.append(ul);
        row.append(top, det); body.append(row);
      });
      if ((P.advice || []).length) {
        const section = el('div', undefined, 'box'); section.append(el('h4', '📌 يحتاج خطوة منك (لا يُحذف شيء هنا)'));
        P.advice.forEach(a => {
          const card = el('div', undefined, 'hcard'); card.style.padding = '8px'; const h = el('b', `${a.target} — ${a.title}  `), [label, color] = RISK[a.risk] || [a.risk || '', '#64748b'];
          const pill = el('small', label, 'rk'); pill.style.color = color; pill.style.borderColor = color; h.append(pill, document.createTextNode('  ' + fsize(a.size || 0))); card.append(h, el('p', a.desc || '', 'muted'));
          if ((a.action?.steps || []).length) { const ol = el('ol', undefined, 'hadv'); a.action.steps.forEach(s => ol.append(el('li', s))); card.append(ol); }
          if (a.action?.command) card.append(cmdLine(a.action.label, a.action.command));
          (a.items || []).forEach(i => card.append(el('div', `${i.name} · ${fsize(i.size || 0)}${i.note ? ' · ' + i.note : ''}`, 'muted'))); section.append(card);
        });
        body.append(section);
      }
      sum(); btn.onclick = async () => {
        if (!confirm(`سيُنقل ${sel.size} بند إلى السلة (نحو ${fsize(total())}). متابعة؟`)) return;
        try { await api('/api/clean/full/apply', { id: fid, items: [...sel], confirm: true }); } catch (e) { note(e.message); return; }
        watchApply();
      };
      foot.replaceChildren(btn, close);
    };
    const watchApply = () => {
      foot.replaceChildren(el('small', 'لا تغلق النافذة حتى ينتهي التنفيذ.', 'muted'));
      stop(); timer = setInterval(async () => {
        try { const r = await api('/api/clean/full/job?id=' + fid); body.replaceChildren(el('b', '⏳ ' + r.progress)); if (r.state === 'done') { stop(); finish(r); } else if (r.state === 'error') { stop(); body.replaceChildren(el('div', '⚠️ ' + r.error, 'warnbox')); foot.replaceChildren(close); } } catch (e) { stop(); body.replaceChildren(el('div', '⚠️ ' + e.message, 'warnbox')); foot.replaceChildren(close); }
      }, 900);
    };
    const finish = r => {
      const R = r.report || { ok: 0, failed: 0, freed: 0, items: [] };
      body.replaceChildren(el('b', `✅ اكتمل: نُقل ${R.ok.toLocaleString()} عنصر إلى السلة (نحو ${fsize(R.freed)})${R.failed ? ` · تعذّر ${R.failed}` : ''}`));
      R.items.forEach(i => body.append(el('div', `${i.target || ''} — ${i.title}: ${i.error ? '⚠️ ' + i.error : `${i.ok} نجح${i.failed ? '، ' + i.failed + ' تعذّر' : ''}`}`, 'muted')));
      body.append(el('div', 'يمكنك استرجاع أي شيء من سلة المهملات قبل إفراغها.', 'muted')); foot.replaceChildren(close);
    };
    pick();
  });
}
function initCleanRoots() {
  const sel0 = croot.value; croot.replaceChildren();
  sources.filter(s => s.type === 'adb').forEach(s => { const o = el('option', `${s.icon} ${s.label}${s.online ? '' : ' (غير متصل)'}`); o.value = 'dev:' + s.id; croot.append(o); });
  [...cloudRoots].sort((a, b) => ({ computer: 0, disk: 1, network: 2, cloud: 3, rclone: 3 }[a.group] - { computer: 0, disk: 1, network: 2, cloud: 3, rclone: 3 }[b.group])).forEach(r => { const o = el('option', r.label); o.value = r.id; croot.append(o); });
  if (sel0 && [...croot.options].some(o => o.value === sel0)) croot.value = sel0; else if (!sel0) croot.value = 'home';
  updateTargetLabel();
}
function updateTargetLabel() {
  const dv = croot.value.startsWith('dev:') ? sources.find(s => s.id === croot.value.slice(4)) : null;
  const r = cloudRoots.find(x => x.id === croot.value), name = dv ? `${dv.icon} ${dv.label}` : r ? (r.group === 'disk' ? r.label : r.group === 'computer' ? '🖥️ هذا الكمبيوتر' : r.label) : croot.value;
  const p = $('#cpath').value.trim(); $('#ctarget').textContent = p ? `${name}  ›  ${p.split('/').filter(Boolean).join('  ›  ')}` : name; $('#ctarget').title = `${name}/${p}`;
}
function setTarget(root, path) { if (![...croot.options].some(o => o.value === root)) initCleanRoots(); croot.value = root; $('#cpath').value = path || ''; updateTargetLabel(); }
const DEV_QUICK = { '': '/sdcard', Downloads: '/sdcard/Download', Documents: '/sdcard/Documents', Desktop: '/sdcard/DCIM' };
document.querySelectorAll('[data-q]').forEach(b => b.onclick = () => croot.value.startsWith('dev:') ? setTarget(croot.value, DEV_QUICK[b.dataset.q]) : setTarget('home', b.dataset.q));
document.querySelectorAll('[data-dev]').forEach(b => b.onclick = () => setTarget('dev:' + b.dataset.dev, '/sdcard'));
const isDev = () => croot.value.startsWith('dev:');
const normPath = () => isDev() ? ($('#cpath').value.trim() || '/sdcard').replace(/\/+$/, '') : $('#cpath').value.trim().replace(/^\/+|\/+$/g, '');
let cleanIsAdb = false;
$('#cpick').onclick = async () => {
  try {
    const r = await api('/api/choose-folder', {}); if (!r.path) return;
    const t = await api('/api/clean/resolve?path=' + encodeURIComponent(r.path.replace(/\/$/, '')));
    setTarget(t.root, t.path);
  } catch (e) { cleanError(e.message.includes('خارج') ? 'اختر مجلدًا داخل مجلدك الشخصي أو على قرص خارجي.' : e.message); }
};
$('#vclean').onclick = () => {
  if (!P?.src) return;
  // مجلد محدد (أو المؤشر على مجلد) ← يُحلَّل وحده؛ وإلا المجلد الحالي
  const sel = [...P.S()], one = sel.length === 1 ? P.entries.find(e => e.path === sel[0]) : (!sel.length && P.cursor?.is_dir ? P.cursor : null);
  const target = one?.is_dir ? one.path : P.cur;
  setTarget(P.src.type === 'adb' ? 'dev:' + P.src.id : P.src.root, target); document.querySelector('[data-v="clean"]').click(); runScan('analyze');
  if (one?.is_dir) note('يُحلَّل المجلد المحدد وحده: ' + one.name);
};
function cleanError(msg) { $('#cres').replaceChildren(el('div', '⚠️ ' + msg, 'warnbox')); }
async function runScan(kind) {
  if (cleanTimer) return;
  updateTargetLabel(); cleanKind = kind; cleanData = null; cleanSel.clear(); cleanSizes.clear(); cleanPerm.clear(); cleanGroupOf.clear(); $('#cres').replaceChildren(); $('#cfoot').hidden = true;
  cleanIsAdb = isDev(); const dv = cleanIsAdb ? sources.find(s => s.id === croot.value.slice(4)) : null;
  if (cleanIsAdb && !dv?.online) { cleanError('الجهاز غير متصل الآن.'); return; }
  const body = { kind, options: { min_size: +$('#cmin').value, max_dist: +$('#csens').value, names: true, threshold: ({ 3: 0.9, 6: 0.8, 10: 0.6 })[+$('#csens').value] || 0.8 }, ...(cleanIsAdb ? { src: srcRef(dv), path: normPath() } : { root: croot.value, path: normPath() }) };
  $('#cprog').hidden = false; $('#cptxt').textContent = 'يبدأ…'; const lo = lop('تحليل: ' + (croot.selectedOptions?.[0]?.textContent || ''));
  try { cleanJob = (await api('/api/clean/start', body)).id; } catch (e) { $('#cprog').hidden = true; cleanError(e.message); lo.end('error'); return; }
  runScan.lo = lo;
  cleanTimer = setInterval(async () => {
    try {
      const r = await api('/api/clean/job?id=' + cleanJob); $('#cptxt').textContent = `${r.progress} · ${r.seconds} ث`; runScan.lo?.set(`${r.progress} · ${r.seconds} ث`);
      if (r.state === 'running') return; runScan.lo?.end(r.state === 'done' ? 'done' : r.state === 'error' ? 'error' : 'cancelled');
      clearInterval(cleanTimer); cleanTimer = null; $('#cprog').hidden = true;
      if (r.state === 'done') { cleanData = r.result; renderClean(); } else if (r.state === 'error') cleanError(r.error); else $('#cres').textContent = 'أُلغي الفحص.';
    } catch (e) { clearInterval(cleanTimer); cleanTimer = null; $('#cprog').hidden = true; cleanError(e.message); }
  }, 800);
}
$('#ccancel').onclick = async () => { if (cleanJob) await api('/api/clean/cancel', { id: cleanJob }).catch(() => {}); };
function ccheck(path, size) {
  cleanSizes.set(path, size || 0);
  const c = check(cleanSel.has(path), () => {
    const g = cleanGroupOf.get(path);
    if (!cleanSel.has(path) && g && g.every(p => p === path || cleanSel.has(p))) { cleanError('أبقِ ملفًا واحدًا على الأقل في كل مجموعة.'); return; }
    cleanSel.has(path) ? cleanSel.delete(path) : cleanSel.add(path); renderClean(true);
  });
  return c;
}
function crow(path, name, sub, size, extra) {
  const r = el('div', undefined, 'crow'), g = el('div', undefined, 'grow'); g.append(el('b', name), el('small', sub || path));
  r.append(ccheck(path, size)); if (extra) r.append(extra); r.append(g, el('span', fsize(size), 'sz'));
  r.dataset.cpath = path; r.onmouseenter = () => cleanHoverSet(r); r.title = 'مسافة: معاينة';
  if (path.startsWith('/')) { const f = el('button', '🔍', 'cfind'); f.title = 'إظهار في Finder (تبقى النتائج كما هي)'; f.onclick = ev => { ev.stopPropagation(); api('/api/clean/reveal', { job: cleanJob, path }).catch(x => note(x.message)); }; r.append(f); }
  return r;
}
// معاينة نتيجة التنظيف بزر المسافة قبل الحذف (مثل Quick Look)، والتنقل بين النتائج بالأسهم داخل العارض
let cleanHover = null;
function cleanHoverSet(r) { cleanHover?.classList.remove('hov'); cleanHover = r; r.classList.add('hov'); }
function cleanPreview(r) {
  const rows = [...$('#cres').querySelectorAll('.crow[data-cpath]')], i = Math.max(0, rows.indexOf(r));
  const items = rows.map(x => { const p = x.dataset.cpath, nm = p.split('/').pop(); const local = p.startsWith('/');
    return { title: nm, url: local ? `/api/clean/thumb?job=${cleanJob}&path=${encodeURIComponent(p)}&v=1&s=2000` : null, fallback: local ? `/api/clean/thumb?job=${cleanJob}&path=${encodeURIComponent(p)}&v=1` : null, meta: p, icon: '📄' }; });
  openLightbox(items, i);
}
window.addEventListener('keydown', ev => {
  if (ev.key !== ' ' || document.body.dataset.sec !== 'clean' || ev.target.closest?.('input,textarea,select,[contenteditable]')) return;
  ev.preventDefault(); ev.stopImmediatePropagation();
  if (!$('#lb').hidden) closeLightbox(); else if (cleanHover?.isConnected) cleanPreview(cleanHover);
}, true);
$('#ccloud').onclick = ev => { ev.stopPropagation(); document.querySelector('.gmenu')?.remove();
  const list = [...cloudRoots].filter(r => r.group === 'cloud' || r.group === 'rclone'), mnu = el('div', undefined, 'gmenu'), rc = $('#ccloud').getBoundingClientRect();
  if (!list.length) mnu.append(el('div', 'لا حسابات سحابية متصلة.', 'gmi'));
  list.forEach(r => { const it = el('div', (r.group === 'rclone' ? '☁ ' : '🗂 ') + r.label, 'gmi'); it.title = r.group === 'rclone' ? 'حساب مباشر: تحليل، كبيرة، مكررة (ببصمة الخدمة)، فارغة — بلا تنزيل' : 'مجلد متزامن على الكمبيوتر'; it.onclick = () => { mnu.remove(); setTarget(r.id, ''); runScan('analyze'); }; mnu.append(it); });
  document.body.append(mnu); mnu.style.top = (rc.bottom + 4) + 'px'; mnu.style.left = Math.max(8, Math.min(rc.left, innerWidth - mnu.offsetWidth - 8)) + 'px';
  setTimeout(() => document.addEventListener('click', () => mnu.remove(), { once: true }), 0); };
function cthumb(path, mtime, group) {
  const box = el('span', undefined, 'th'); box.style.width = '44px'; box.style.height = '44px'; box.textContent = '🖼️';
  const u = `/api/clean/thumb?job=${cleanJob}&path=${encodeURIComponent(path)}&v=${mtime}`;
  const img = new Image(); img.onload = () => { box.textContent = ''; box.append(img); }; img.src = u;
  box.style.cursor = 'zoom-in';
  box.ondblclick = () => { const items = group.files.map(f => ({ title: f.path.split('/').pop(), url: `/api/clean/thumb?job=${cleanJob}&path=${encodeURIComponent(f.path)}&v=${f.mtime}&s=2000`, fallback: `/api/clean/thumb?job=${cleanJob}&path=${encodeURIComponent(f.path)}&v=${f.mtime}` })); openLightbox(items, group.files.findIndex(f => f.path === path)); };
  box.title = 'انقر مرتين للمعاينة'; return box;
}
// ---------- الفحص الشامل: بطاقات الصحة وفئات المعرفة ----------
const RISK_AR = { safe: 'آمن', rebuild: 'يُعاد بناؤه', review: 'راجعه', info: 'للعلم', keep: 'لا تلمسه' };
function copyBtn(txt) { const b = btn('📋 نسخ', () => { navigator.clipboard?.writeText(txt).then(() => note('نُسخ الأمر. الصقه في الطرفية.')).catch(() => note(txt)); }); b.style.marginInlineStart = '8px'; return b; }
function cmdLine(label, cmd) { const r = el('div', undefined, 'hcmd'); if (label) r.append(el('small', label, 'muted')); const c = el('code', cmd); c.dir = 'ltr'; r.append(c, copyBtn(cmd)); return r; }
function healthBox(h) {
  const wrap = el('div', undefined, 'box hbox'); wrap.append(el('h4', '🩺 صحة الجهاز'));
  (h.cards || []).forEach(c => {
    const card = el('details', undefined, 'hcard ' + (c.status || 'ok')); if (c.status && c.status !== 'ok') card.open = true;
    const sm = el('summary'); sm.append(el('span', { ok: '✓', warn: '⚠️', bad: '⛔' }[c.status] || '•', 'hst'), el('b', c.title), el('span', '  ' + (c.summary || ''), 'muted')); card.append(sm);
    (c.details || []).forEach(t => card.append(el('div', t, 'hdet')));
    if ((c.advice || []).length) { const ul = el('ol', undefined, 'hadv'); c.advice.forEach(a => ul.append(el('li', a))); card.append(ul); }
    (c.commands || []).forEach(k => card.append(cmdLine(k.label, k.cmd)));
    wrap.append(card);
  });
  const apps = h.apps || [];
  if (apps.length) {
    const t = el('details', undefined, 'hcard ok'), sm = el('summary'); sm.append(el('span', '📦', 'hst'), el('b', 'أكبر التطبيقات في الجوال'), el('span', '  التطبيق + بياناته', 'muted')); t.append(sm);
    apps.forEach(a => { const r = el('div', undefined, 'crow'), g = el('div', undefined, 'grow'); g.append(el('b', a.label || a.pkg), el('small', (a.note ? a.note + ' · ' : '') + `التطبيق ${fsize(a.app)} · البيانات ${fsize(a.data)} · الكاش ${fsize(a.cache)}`)); r.append(g, el('span', fsize((a.app || 0) + (a.data || 0)), 'sz')); t.append(r); });
    wrap.append(t);
  }
  return wrap;
}
function cleanCatBox(c) {
  const sel = c.selectable !== false, card = el('div', undefined, 'box' + (sel ? '' : ' cinfo')), h4 = el('h4');
  h4.append(c.title + '  ', el('span', RISK_AR[c.risk] || c.risk, 'rk ' + c.risk), '  ' + fsize(c.size));
  if (sel) { const all = btn('تحديد الكل', () => { c.items.forEach(i => cleanSel.add(i.path)); renderClean(true); }); all.style.marginInlineStart = '10px'; h4.append(all); }
  card.append(h4, el('p', c.desc, 'muted'));
  const a = c.action;
  if (a && (a.steps || []).length) { const ol = el('ol', undefined, 'hadv'); a.steps.forEach(t => ol.append(el('li', t))); if (a.label) card.append(el('b', a.label)); card.append(ol); }
  if (a && a.kind === 'command' && a.command) card.append(cmdLine(a.label, a.command));
  c.items.forEach(i => {
    let sub = (i.note ? i.note + '  ·  ' : '') + i.path, extra;
    if (i.unique) {
      sub = (i.unique.complete === false ? '⚠️ المقارنة ناقصة — لا تحذفه الآن  ·  ' : i.unique.count ? '' : '✓ كل ملفاته موجودة في مكان آخر، فهو مكرر بالكامل  ·  ') + `فريد هنا: ${i.unique.count} ملف (${fsize(i.unique.size)}) غير موجود في iCloud أو OneDrive أو المستندات  ·  ` + sub;
      if (i.unique.count) extra = btn('⇢ انقل الفريد إلى المستندات', ev => { ev.stopPropagation(); moveUnique(i.path, i.unique); });
    }
    if (sel) { if (c.permanent_ok) cleanPerm.add(i.path); card.append(crow(i.path, i.name, sub, i.size, extra)); }
    else { const r = el('div', undefined, 'crow'), g = el('div', undefined, 'grow'); g.append(el('b', i.name), el('small', sub)); r.append(g); if (extra) r.append(extra); r.append(el('span', fsize(i.size), 'sz'));
      if (i.path.startsWith('/')) { const f = el('button', '🔍', 'cfind'); f.title = 'إظهار في Finder'; f.onclick = () => api('/api/clean/reveal', { job: cleanJob, path: i.path }).catch(x => note(x.message)); r.append(f); }
      card.append(r); }
  });
  return card;
}
async function moveUnique(path, u) {
  if (!confirm(`سيُنقل ${u.count} ملف (${fsize(u.size)}) موجود في هذا الأرشيف وحده إلى:\nالمستندات / من أرشيف iCloud\nبنفس ترتيب المجلدات، دون الكتابة فوق أي ملف. متابعة؟`)) return;
  try { const r = await api('/api/clean/move_unique', { job: cleanJob, archive: path, confirm: true }); note(`نُقل ${r.moved} ملف (${fsize(r.size)}) إلى ${r.dest}${r.skipped ? ` · تُرك ${r.skipped}` : ''}. صار الأرشيف مكررًا ويمكن نقله إلى السلة.`); runScan('caches'); }
  catch (e) { cleanError(e.message); }
}
function renderClean(keepScroll) {
  const d = cleanData, box = $('#cres'), y = window.scrollY; if (!d) return; box.replaceChildren();
  if (cleanKind === 'analyze') {
    const head = el('div', undefined, 'sumh'), mk = (t, v) => { const x = el('div'); x.append(el('b', v), el('span', t, 'muted')); head.append(x); };
    mk('الحجم الكلي', fsize(d.total)); mk('عدد الملفات', d.files.toLocaleString('en')); if (d.skipped) mk('مجلدات لم تُقرأ', String(d.skipped)); box.append(head);
    const p = normPath();
    if (p && !(cleanIsAdb && p === '/sdcard')) { const up = btn('↑ المجلد الأعلى', () => { $('#cpath').value = p.split('/').slice(0, -1).join('/') || (cleanIsAdb ? '/sdcard' : ''); runScan('analyze'); }); up.style.marginBottom = '8px'; box.append(up); }
    const max = Math.max(1, ...d.children.map(c => c.size)), b1 = el('div', undefined, 'box'); b1.append(el('h4', 'المجلدات والملفات بحسب الحجم (انقر مجلدًا للتعمق)'));
    d.children.forEach(c => {
      const r = el('div', undefined, 'crow' + (c.is_dir ? ' link' : '')), g = el('div', undefined, 'grow'), bar = el('div', undefined, 'bar'), i = el('i'); i.style.width = (c.size / max * 100) + '%'; bar.append(i);
      g.append(el('b', (c.is_dir ? '📁 ' : '📄 ') + c.name), bar); r.append(g, el('span', c.is_dir ? `${fsize(c.size)} · ${c.files.toLocaleString('en')} ملف` : fsize(c.size), 'sz')); r.querySelector('.sz').style.width = '150px';
      if (c.is_dir) r.onclick = () => { $('#cpath').value = (p ? p + '/' : '') + c.name; runScan('analyze'); };
      b1.append(r);
    });
    const b2 = el('div', undefined, 'box'); b2.append(el('h4', 'بحسب النوع'));
    const tmax = Math.max(1, ...d.types.map(t => t.size));
    d.types.forEach(t => { const r = el('div', undefined, 'crow'), g = el('div', undefined, 'grow'), bar = el('div', undefined, 'bar'), i = el('i'); i.style.width = (t.size / tmax * 100) + '%'; bar.append(i); g.append(el('b', `${t.name} (${t.count.toLocaleString('en')})`), bar); r.append(g, el('span', fsize(t.size), 'sz')); b2.append(r); });
    const b3 = el('div', undefined, 'box'); b3.append(el('h4', 'أكبر الملفات'));
    d.biggest.forEach(f => b3.append(crow(f.path, f.path.split('/').pop(), f.path, f.size)));
    box.append(b1, b2, b3);
  } else if (cleanKind === 'duplicates' || cleanKind === 'similar') {
    const head = el('div', undefined, 'sumh'), mk = (t, v) => { const x = el('div'); x.append(el('b', v), el('span', t, 'muted')); head.append(x); };
    mk('مجموعات', String(d.groups.length)); mk('مساحة يمكن توفيرها', fsize(d.wasted)); if (d.images) mk('صور حُلّلت', d.images.toLocaleString('en')); box.append(head);
    if (d.note) box.append(el('div', 'ℹ️ ' + d.note, 'warnbox'));
    if (!d.groups.length) box.append(el('div', '✓ لم أجد شيئًا.', 'warnbox'));
    else { const auto = btn('تحديد المكرر تلقائيًا (أُبقي الأفضل في كل مجموعة)', () => { d.groups.forEach(g => g.files.slice(1).forEach(f => cleanSel.add(f.path))); renderClean(true); }, 'btn pri'); auto.style.marginBottom = '8px'; box.append(auto, el('p', (cleanKind === 'similar' ? 'راجع الصور بنفسك (انقر مرتين على المصغّرة لمعاينتها). مجموعات «أسماء متشابهة» قد تكون ملفات مختلفة فعلًا. ' : '') + 'الملف الأول في كل مجموعة هو الذي يُبقى بحسب «القواعد» (⚙ أعلى الصفحة): الأحدث/الأقدم، المجلدات المفضّلة والمرفوضة، الاسم النظيف.', 'muted')); }
    d.groups.forEach(g => {
      g.files.forEach(f => cleanGroupOf.set(f.path, g.files.map(x => x.path)));
      const card = el('div', undefined, 'grp'), gh = el('div', undefined, 'gh');
      gh.append(el('b', g.type === 'name' ? `أسماء متشابهة: ${g.key}` : g.type === 'image' ? 'صور متشابهة' : 'ملفات متطابقة'), el('span', `${g.files.length} ملفات · توفير ${fsize(g.wasted)}`, 'muted')); card.append(gh);
      g.files.forEach((f, i) => { const extra = (g.type === 'image' || /\.(jpe?g|png|webp|gif|heic|bmp|tiff?)$/i.test(f.path)) ? cthumb(f.path, f.mtime, g) : null;
        const sub = `${f.path}  ·  ${fdate(f.mtime)}` + (f.w ? `  ·  ${f.w}×${f.h}` : '') + (i === 0 ? `  ·  (يُبقى — ${g.keep_reason || 'الأول'})` : '');
        card.append(crow(f.path, f.path.split('/').pop(), sub, f.size ?? g.size, extra)); });
      box.append(card);
    });
  } else if (cleanKind === 'folders') {
    const head = el('div', undefined, 'sumh'), x = el('div'); x.append(el('b', String(d.pairs.length)), el('span', 'أزواج متشابهة', 'muted')); head.append(x); box.append(head);
    if (!d.pairs.length) box.append(el('div', '✓ لم أجد مجلدات متشابهة بهذه الحساسية.', 'warnbox'));
    else { const auto = btn('تحديد المجلد الأقل ملفات فريدة في كل زوج', () => { d.pairs.forEach(p => cleanSel.add(p.only_a < p.only_b ? p.a : p.b)); renderClean(true); }, 'btn pri'); auto.style.marginBottom = '8px'; box.append(auto, el('p', 'كل زوج يتطابق جزء كبير من محتواه (بالحجم والاسم). احذف أحد المجلدين فقط، وراجع «الملفات الفريدة» قبل الحذف لئلا تخسر ما ليس في الآخر.', 'muted')); }
    d.pairs.forEach(pr => {
      cleanGroupOf.set(pr.a, [pr.a, pr.b]); cleanGroupOf.set(pr.b, [pr.a, pr.b]);
      const card = el('div', undefined, 'grp'), gh = el('div', undefined, 'gh'); gh.append(el('b', `تطابق ${Math.round(pr.ratio * 100)}%`), el('span', `${pr.shared} ملف مشترك · ${fsize(pr.shared_bytes)}`, 'muted')); card.append(gh);
      [['a', pr.a, pr.only_a, pr.size_a], ['b', pr.b, pr.only_b, pr.size_b]].forEach(([, pth, only, sz]) => card.append(crow(pth, pth.split('/').pop(), `${pth}  ·  ملفات فريدة فيه: ${only}`, sz)));
      box.append(card);
    });
  } else if (cleanKind === 'caches') {
    const head = el('div', undefined, 'sumh'), x = el('div'); x.append(el('b', fsize(d.total)), el('span', 'يمكن تحريره بالتحديد', 'muted')); head.append(x);
    const info = (d.categories || []).filter(c => c.selectable === false && c.risk !== 'keep').reduce((a, c) => a + (c.size || 0), 0);
    if (info) { const y2 = el('div'); y2.append(el('b', fsize(info)), el('span', 'يحتاج خطوة منك (انظر الشرح)', 'muted')); head.append(y2); }
    box.append(head);
    if (d.health) box.append(healthBox(d.health));
    d.categories.forEach(c => box.append(cleanCatBox(c)));
    if (!d.categories.length) box.append(el('div', '✓ لا ملفات كاش تُذكر.', 'warnbox'));
  } else if (cleanKind === 'large') {
    const head = el('div', undefined, 'sumh'), x = el('div'); x.append(el('b', fsize(d.total)), el('span', `أكبر ${d.files.length} ملف`, 'muted')); head.append(x); box.append(head);
    const b = el('div', undefined, 'box'); d.files.forEach(f => b.append(crow(f.path, f.path.split('/').pop(), `${f.path}  ·  ${fdate(f.mtime)}${f.old ? '  ·  لم يُعدَّل منذ أكثر من سنة' : ''}`, f.size))); box.append(b);
  } else if (cleanKind === 'empty') {
    const b = el('div', undefined, 'box'); b.append(el('h4', `${d.dirs.length} مجلد فارغ`));
    d.dirs.forEach(p => b.append(crow(p, p.split('/').pop(), p, 0))); if (!d.dirs.length) b.append(el('p', '✓ لا مجلدات فارغة.', 'muted')); box.append(b);
  }
  updateCleanFoot(); if (keepScroll) window.scrollTo(0, y);
}
function updateCleanFoot() {
  const n = cleanSel.size, sz = [...cleanSel].reduce((a, p) => a + (cleanSizes.get(p) || 0), 0);
  $('#cfoot').hidden = !n; $('#csum').textContent = `${n} محدد · ${fsize(sz)}`;
  $('#cperm').hidden = cleanIsAdb || !(n && [...cleanSel].every(p => cleanPerm.has(p)));
  $('#ctrash').textContent = cleanIsAdb ? 'حذف نهائي من الجهاز' : 'نقل المحدد إلى السلة'; $('#ctrash').classList.toggle('danger', cleanIsAdb); $('#ctrash').classList.toggle('pri', !cleanIsAdb);
  $('#cres').querySelectorAll('.ck').forEach(() => {});
}
$('#ccl').onclick = () => { cleanSel.clear(); renderClean(true); };
$('#crules').onclick = async () => {
  let data; try { data = await api('/api/clean/rules'); } catch (e) { cleanError(e.message); return; }
  const rules = data.rules, choices = data.choices; let keep = [...rules.keep];
  openModal(m => {
    m.classList.add('wide'); m.append(el('h3', '⚙ قواعد الاحتفاظ بالنسخة المفضّلة'), el('p', 'عند وجود نسخ متعددة (مكرر أو متشابه) تُبقي الأداة نسخة واحدة بحسب هذه القواعد بالترتيب، وتحدّد الباقي للحذف. لا يُحذف شيء تلقائيًا؛ تراجع وتؤكد دائمًا.', 'muted'));
    const list = el('div', undefined, 'rulelist'), draw = () => {
      list.replaceChildren(el('b', '١) احتفظ بالنسخة… (بحسب هذا الترتيب)'));
      keep.forEach((k, i) => { const r = el('div', undefined, 'ruleitem'); r.append(el('span', `${i + 1}. ${choices[k]}`), el('span', undefined, 'sp'), btn('↑', () => { if (i) { [keep[i - 1], keep[i]] = [keep[i], keep[i - 1]]; draw(); } }), btn('↓', () => { if (i < keep.length - 1) { [keep[i + 1], keep[i]] = [keep[i], keep[i + 1]]; draw(); } }), btn('✕', () => { keep.splice(i, 1); draw(); })); list.append(r); });
      const sel = el('select'); sel.append(Object.assign(el('option', '＋ إضافة معيار…'), { value: '' })); Object.entries(choices).filter(([k]) => !keep.includes(k)).forEach(([k, v]) => sel.append(Object.assign(el('option', v), { value: k })));
      sel.onchange = () => { if (sel.value) { keep.push(sel.value); draw(); } }; list.append(sel);
    }; draw(); m.append(list);
    const ta = (title, hint, val) => { const w = el('div', undefined, 'rulebox'), t = el('textarea'); t.value = val.join('\n'); t.rows = 3; t.placeholder = hint; w.append(el('b', title), t); m.append(w); return t; };
    const pref = ta('٢) مجلدات مفضّلة — تُفضَّل النسخة الموجودة فيها (اسم مجلد أو جزء من المسار، سطر لكل واحد)', 'مثال: Documents\nالأرشيف', rules.prefer_dirs);
    const avoid = ta('٣) مجلدات مرفوضة — يُتجنَّب الإبقاء على نسخة فيها', 'مثال: Downloads\ntrash', rules.avoid_dirs);
    const l = el('label'), cb = document.createElement('input'); cb.type = 'checkbox'; cb.checked = rules.prefer_clean_names; l.append(cb, document.createTextNode(' ٤) فضّل الأسماء النظيفة (بلا «(1)» أو «copy» أو «نسخة»)')); m.append(l);
    const ok = el('button', 'حفظ', 'btn pri'), again = el('button', 'حفظ وإعادة الفحص', 'btn'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    const save = async rescan => { const lines = t => t.value.split('\n').map(x => x.trim()).filter(Boolean); await api('/api/clean/rules', { keep, prefer_dirs: lines(pref), avoid_dirs: lines(avoid), prefer_clean_names: cb.checked }); closeModal(); note('حُفظت القواعد. تُطبَّق على الفحوص القادمة.'); if (rescan && cleanKind) runScan(cleanKind); };
    cancel.onclick = closeModal; ok.onclick = () => save(false); again.onclick = () => save(true); acts.append(cancel, again, ok); m.append(acts);
  });
};
function pruneResult(removed) {
  const d = cleanData; if (!d) return; const gone = new Set(removed);
  if (d.groups) { d.groups.forEach(g => g.files = g.files.filter(f => !gone.has(f.path))); d.groups = d.groups.filter(g => g.files.length > 1); d.wasted = d.groups.reduce((a, g) => a + g.wasted, 0); }
  if (d.categories) { d.categories.forEach(c => { c.items = c.items.filter(i => !gone.has(i.path)); c.size = c.items.reduce((a, i) => a + i.size, 0); }); d.categories = d.categories.filter(c => c.items.length); d.total = d.categories.reduce((a, c) => a + c.size, 0); }
  if (d.files && cleanKind === 'large') d.files = d.files.filter(f => !gone.has(f.path));
  if (d.biggest) d.biggest = d.biggest.filter(f => !gone.has(f.path));
  if (d.dirs) d.dirs = d.dirs.filter(p => !gone.has(p));
  if (d.pairs) d.pairs = d.pairs.filter(p => !gone.has(p.a) && !gone.has(p.b));
  removed.forEach(p => cleanSel.delete(p));
}
function confirmRemove(permanent) {
  if (cleanIsAdb) permanent = true;
  const paths = [...cleanSel]; if (!paths.length) return; const sz = paths.reduce((a, p) => a + (cleanSizes.get(p) || 0), 0);
  const run = async () => {
    closeModal();
    try {
      const r = (await api('/api/clean/remove', { job: cleanJob, paths, permanent, confirm: true })).report;
      const ok = r.filter(x => x.ok).map(x => x.path), bad = r.filter(x => !x.ok);
      pruneResult(ok); renderClean(true);
      done(`${permanent ? 'حُذف نهائيًا' : 'نُقل إلى السلة'}: ${ok.length} من ${r.length}`, bad.map(x => `${x.path}: ${x.detail}`));
    } catch (e) { cleanError(e.message); }
  };
  openModal(m => {
    m.append(el('h3', permanent ? 'حذف نهائي' : 'نقل إلى سلة المهملات'), el('div', permanent ? `سيُحذف ${paths.length} عنصر (${fsize(sz)}) ${cleanIsAdb ? 'من الجهاز ' : ''}نهائيًا ولا يمكن استرجاعه${cleanIsAdb ? ' (لا توجد سلة مهملات على الجهاز)' : ''}.` : `سيُنقل ${paths.length} عنصر (${fsize(sz)}) إلى سلة المهملات. يمكنك استرجاعه منها.`, 'warnbox'), listBox(paths));
    if (permanent) typedConfirm(m, 'حذف', run, 'احذف نهائيًا');
    else { const ok = el('button', 'انقل إلى السلة', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'); ok.onclick = run; cancel.onclick = closeModal; const a = el('div', undefined, 'acts'); a.append(cancel, ok); m.append(a); }
  });
}
$('#ctrash').onclick = () => confirmRemove(false); $('#cperm').onclick = () => confirmRemove(true);

/* ---------- الشبكة الداخلية: الاتصال بجهاز آخر (macOS يطلب كلمة المرور بنفسه) ---------- */
async function networkConnect() {
  let hosts = []; openModal(m => { m.append(el('h3', '🌐 الاتصال بجهاز على الشبكة'), el('p', 'جارٍ البحث عن أجهزة…', 'muted')); });
  try { hosts = (await api('/api/network/discover')).hosts; } catch (_) {}
  openModal(m => {
    m.append(el('h3', '🌐 الاتصال بجهاز على الشبكة'), el('p', 'اكتب عنوان المشاركة، فيفتح macOS نافذة الاتصال ويطلب كلمة المرور بنفسه (الأداة لا ترى كلمة المرور). بعد الاتصال يظهر الجهاز تحت «الشبكة».', 'muted'));
    const inp = el('input'); inp.type = 'text'; inp.placeholder = 'smb://اسم-الجهاز.local/المشاركة'; inp.value = store.get('lastNet', ''); inp.style.direction = 'ltr';
    if (hosts.length) { m.append(el('h4', 'أجهزة اكتُشفت على شبكتك:')); hosts.forEach(h => { const r = el('div', undefined, 'hostrow'); r.append(el('span', '🖥️'), el('b', h.name), el('span', undefined, 'sp'), btn('استخدم', () => { inp.value = 'smb://' + (h.host || h.name.replace(/\s+/g, '-') + '.local'); inp.focus(); })); m.append(r); }); }
    else m.append(el('p', 'لم يُكتشف أي جهاز تلقائيًا؛ اكتب العنوان يدويًا.', 'muted'));
    const ok = el('button', 'اتصال', 'btn pri'), cancel = el('button', 'إلغاء', 'btn'), acts = el('div', undefined, 'acts');
    ok.onclick = async () => { try { const r = await api('/api/network/connect', { url: inp.value.trim() }); store.set('lastNet', inp.value.trim()); closeModal(); note(r.message); } catch (e) { note(e.message); inp.style.borderColor = 'var(--err)'; } };
    cancel.onclick = closeModal; acts.append(cancel, ok); m.append(inp, acts);
  });
}
/* ---------- تثبيت كتطبيق (PWA) ---------- */
let deferredInstall = null;
window.addEventListener('beforeinstallprompt', e => { e.preventDefault(); deferredInstall = e; });
if (!matchMedia('(display-mode: standalone)').matches) $('#installbtn').hidden = false;
$('#installbtn').onclick = () => {
  if (deferredInstall) { deferredInstall.prompt(); deferredInstall = null; return; }
  openModal(m => {
    m.append(el('h3', '⬇ تثبيت كتطبيق بنافذة مستقلة'));
    [['Chrome', 'القائمة ⋮ ثم «Cast, save and share» ثم «Install page as app…» (أو أيقونة التثبيت في شريط العنوان).'], ['Safari', 'القائمة «File» ثم «Add to Dock…».'], ['المُشغّل الجاهز', 'أيقونة «نسخ الهاتف» الزرقاء في الـDock تفتح الأداة مباشرة في نافذة مستقلة (وضع التطبيق) وتشغّل الخدمة عند الحاجة.']]
      .forEach(([t, d]) => { const r = el('div', undefined, 'hostrow'); r.append(el('b', t), el('span', d, 'muted')); m.append(r); });
    const b = el('button', 'حسنًا', 'btn pri'), a = el('div', undefined, 'acts'); b.onclick = closeModal; a.append(b); m.append(a);
  });
};
if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});

/* ---------- التحليل البياني (دائرة وجدول لأين تذهب المساحة) ---------- */
const PALETTE = ['#2f6bff', '#16a06a', '#e0a100', '#d6455d', '#8a5cf6', '#00a3b4', '#f2711c', '#6b7587', '#b5cc18', '#c77dff'];
function donut(items, total, size = 170) {
  const NS = 'http://www.w3.org/2000/svg', svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', '0 0 100 100'); svg.setAttribute('width', size); svg.setAttribute('height', size);
  const r = 38, C = 2 * Math.PI * r; let off = 0;
  items.forEach((it, i) => {
    const frac = total ? it.size / total : 0, c = document.createElementNS(NS, 'circle');
    Object.entries({ cx: 50, cy: 50, r, fill: 'none', stroke: it.color || PALETTE[i % PALETTE.length], 'stroke-width': 16, 'stroke-dasharray': `${Math.max(0, frac * C - 0.4)} ${C}`, 'stroke-dashoffset': -off, transform: 'rotate(-90 50 50)' }).forEach(([k, v]) => c.setAttribute(k, v));
    const t = document.createElementNS(NS, 'title'); t.textContent = `${it.name}: ${fsize(it.size)} (${(frac * 100).toFixed(1)}%)`; c.append(t); svg.append(c); off += frac * C;
  });
  const tx = document.createElementNS(NS, 'text'); tx.setAttribute('x', 50); tx.setAttribute('y', 54); tx.setAttribute('text-anchor', 'middle'); tx.setAttribute('font-size', 10); tx.setAttribute('fill', 'currentColor'); tx.textContent = fsize(total); svg.append(tx);
  return svg;
}
function chartBlock(title, rows, total, onPick) {
  const top = rows.slice(0, 9), rest = rows.slice(9), other = rest.reduce((a, x) => a + x.size, 0);
  const items = other > 0 ? [...top, { name: 'أخرى (' + rest.length + ')', size: other, color: '#aab2c0' }] : top;
  const wrap = el('div', undefined, 'chartblk'); wrap.append(el('h4', title));
  const row = el('div', undefined, 'chartrow'), tbl = el('div', undefined, 'charttbl');
  row.append(donut(items, total), tbl);
  items.forEach((it, i) => {
    const r = el('div', undefined, 'cr' + (onPick && it.pick ? ' link' : '')), dot = el('i', undefined, 'cd'); dot.style.background = it.color || PALETTE[i % PALETTE.length];
    r.append(dot, el('b', it.name), el('span', (total ? (it.size / total * 100).toFixed(1) : 0) + '%', 'muted'), el('span', fsize(it.size), 'sz'));
    if (onPick && it.pick) r.onclick = () => onPick(it); tbl.append(r);
  });
  wrap.append(row); return wrap;
}
async function chartAnalysis() { const lo = lop('تحليل بياني: ' + (P?.cur?.split('/').filter(Boolean).pop() || P?.src?.label || '')); try { await chartAnalysis0(); lo.end(); } catch (e) { lo.end('error'); throw e; } }
async function chartAnalysis0() {
  const p = P; if (!p?.src?.online) { note('افتح مجلدًا أولًا.'); return; }
  let cancelled = false, jobId = null;
  const close = () => { cancelled = true; if (jobId) api('/api/clean/cancel', { id: jobId }).catch(() => {}); closeModal(); };
  openModal(m => { m.classList.add('wide'); m.append(el('h3', `📊 تحليل بياني: ${p.src.label} › ${p.cur.split('/').filter(Boolean).pop() || ''}`), el('p', 'جارٍ التحليل… قد يستغرق المجلد الكبير وقتًا.', 'muted'), btn('إلغاء', close)); });
  try {
    let children, types = null, total, files = null;
    if (p.src.type === 'local') {
      jobId = (await api('/api/clean/start', { kind: 'analyze', root: p.src.root, path: p.cur, options: {} })).id;
      for (;;) { await new Promise(r => setTimeout(r, 700)); if (cancelled) return; const j = await api('/api/clean/job?id=' + jobId); if (j.state === 'running') continue; if (j.state !== 'done') throw new Error(j.error || 'أُلغي'); ({ children, types, total, files } = j.result); break; }
    } else { ({ children, total } = await api(`/api/adb/usage?path=${encodeURIComponent(p.cur)}&serial=${encodeURIComponent(p.src.serial || '')}`)); }
    if (cancelled) return;
    const join = n => p.src.type === 'adb' ? (p.cur === '/' ? '' : p.cur) + '/' + n : (p.cur ? p.cur + '/' : '') + n;
    const isDir = n => p.src.type === 'local' ? true : !!p.entries.find(e => e.name === n)?.is_dir;
    const rows = children.map(c => ({ name: (c.is_dir ?? isDir(c.name) ? '📁 ' : '📄 ') + c.name, size: c.size, pick: (c.is_dir ?? isDir(c.name)) ? join(c.name) : null }));
    openModal(m => {
      m.classList.add('wide'); m.append(el('h3', `📊 ${p.src.label} › ${p.cur || '/'}`), el('p', `الحجم الكلي ${fsize(total)}${files != null ? ' · ' + files.toLocaleString('en') + ' ملف' : ''}. انقر مجلدًا في الجدول لفتحه.`, 'muted'));
      m.append(chartBlock('بحسب المجلدات والملفات', rows, total, it => { closeModal(); p.go(p.src.id, it.pick); }));
      if (types?.length) m.append(chartBlock('بحسب نوع الملفات', types.map(t => ({ name: `${t.name} (${t.count.toLocaleString('en')})`, size: t.size })), total));
      const b = btn('إغلاق', closeModal, 'btn pri'), a = el('div', undefined, 'acts'); a.append(b); m.append(a);
    });
  } catch (e) { if (!cancelled) { closeModal(); done('تعذّر التحليل', [e.message]); } }
}
$('#chartbtn').onclick = chartAnalysis;

let lastVols = null;
function restoreLayout() {
  let L = null; try { L = JSON.parse(store.get('layout', 'null')); } catch (_) {}
  const first = sources.find(x => x.online) || sources[0];
  const mk = cfg => { const w = { id: ++wid, panes: [], activeIdx: cfg.active || 0 }; (cfg.panes?.length ? cfg.panes : [{}]).slice(0, 2).forEach(pc => w.panes.push(new Pane({ view: pc.view }))); workspaces.push(w); };
  if (L?.tabs?.length) L.tabs.forEach(mk); else mk({});
  ws = workspaces[Math.min(Math.max(0, L?.active || 0), workspaces.length - 1)];
  renderPanesArea(); P = null; setActive(ws.panes[ws.activeIdx] || ws.panes[0]);
  workspaces.forEach((w, wi) => w.panes.forEach((p, pi) => {
    const pc = L?.tabs?.[wi]?.panes?.[pi], s = sources.find(x => x.id === pc?.src && x.online) || sources.find(x => x.id === store.get('lastSrc', '') && x.online) || first;
    if (s) p.go(s.id, pc?.src === s.id && pc.path != null ? pc.path : store.get('path:' + s.id, s.home));
  }));
  renderTabs();
}
(() => { [['#selall', 'selectAll', 'تحديد الكل'], ['#clr', 'clear', 'مسح'], ['#delfiles', 'trash', 'حذف']].forEach(([id, ic, t]) => { $(id).innerHTML = icon(ic, 15) + ' ' + t; $(id).classList.add('ibtn'); }); })();
(async () => {
  if (store.get('det', 'on') === 'off') $('#det').classList.add('off'); else $('#vdet').classList.add('on');
  await initDest().catch(() => {}); await refresh(); setInterval(refresh, 3000); loadOps();
  restoreLayout(); loadFavs();
})();

/* ---------- البحث في الشريط العلوي: أيقونة تتوسع على حساب الأيقونات وتنطوي عند الانتهاء أو النقر خارجها؛ يعمل على اللوحة الفعّالة ---------- */
const topSearch = (() => {
  const box = $('#tsearch'), q = $('#tsq'), top = box?.closest('.top');
  const sync = () => box.classList.toggle('has', !!P?.query);
  const open = () => { box.classList.add('open'); top.classList.add('searching'); q.value = P?.query || ''; setTimeout(() => { q.focus(); q.select(); }, 30); };
  const close = () => { box.classList.remove('open'); top.classList.remove('searching'); sync(); };
  const push = v => { if (!P) return; const i = P.q('.pq'); i.value = v; P.query = v; P.rerender(); };
  $('#tsbtn').onclick = e => { e.stopPropagation(); box.classList.contains('open') ? (q.value ? q.focus() : close()) : open(); };
  q.oninput = () => push(q.value);
  q.onkeydown = e => { if (e.key === 'Enter') { e.preventDefault(); push(q.value); P?.startSearch(); close(); } else if (e.key === 'Escape') { e.preventDefault(); q.value = ''; push(''); close(); } };
  $('#tsopt').onclick = e => { e.stopPropagation(); P?.q('.pvext')?.click(); };
  document.addEventListener('mousedown', e => { if (box.classList.contains('open') && !box.contains(e.target) && !e.target.closest('.psearch')) close(); }, true);
  return { open, close, sync };
})();

/* ---------- لوحة المعلومات والعمليات: تغيير عرضها بالسحب مثل الشريط الجانبي ---------- */
(() => {
  const det = $('#det'); if (!det) return;
  const setW = w => { w = Math.max(180, Math.min(640, Math.round(w))); store.set('dw', String(w)); document.documentElement.style.setProperty('--dw', w + 'px'); };
  setW(+store.get('dw', 240));
  const g = el('div', undefined, 'detgrip'); g.title = 'اسحب لتغيير العرض · نقر مزدوج لإعادته'; g.ondblclick = () => setW(240);
  g.onpointerdown = ev => { ev.preventDefault(); g.setPointerCapture(ev.pointerId); const r = det.getBoundingClientRect(), rtl = getComputedStyle(det).direction === 'rtl';
    g.onpointermove = e2 => setW(rtl ? e2.clientX - r.left : r.right - e2.clientX); g.onpointerup = () => { g.onpointermove = null; }; };
  det.append(g);
})();

/* ---------- تفاصيل عملية: ما تمّ فيها وما فشل ---------- */
async function opDetails(o) {
  let d = o;
  if (!o.local) { try { d = await api('/api/ops/get?id=' + encodeURIComponent(o.id)); } catch (e) { note(e.message); return; } }
  const ST = { running: 'جارية', done: 'تمّت', error: 'فشلت', cancelled: 'أُلغيت' };
  openModal(m => {
    m.classList.add('wide'); m.append(el('h3', d.title));
    const kv = (k, v) => { if (v == null || v === '') return; const r = el('div', undefined, 'kv'); r.append(el('span', k), el('b', String(v))); m.append(r); };
    kv('الحالة', ST[d.state] || d.state);
    kv('البداية', d.started ? fdate(d.started * 1000) : d.history || d.time || '');
    kv('المدة', d.seconds != null ? (d.seconds >= 60 ? Math.floor(d.seconds / 60) + ' د ' : '') + Math.round(d.seconds % 60) + ' ث' : '');
    if (d.total) kv('المنجز', `${d.done} من ${d.total}`);
    if (d.bytes_total) kv('الحجم', fsize(d.bytes_total));
    kv('الخلاصة', d.detail);
    const log = d.log || [];
    m.append(el('h4', `الملفات المنجزة (${log.length})`));
    const lb = el('div', undefined, 'oplog'); if (!log.length) lb.append(el('div', d.state === 'running' ? 'لم يكتمل ملف بعد.' : 'لا سجلّ لأسماء الملفات في هذه العملية.', 'muted'));
    log.slice(-1000).reverse().forEach(x => lb.append(el('div', String(x).replace(/^\/Users\/[^/]+/, '~')))); m.append(lb);
    if (d.errors?.length) { m.append(el('h4', `الأخطاء (${d.errors.length})`)); const eb = el('div', undefined, 'oplog err'); d.errors.forEach(x => eb.append(el('div', x))); m.append(eb); }
    const acts = el('div', undefined, 'acts'); acts.append(btn('إغلاق', closeModal, 'btn')); m.append(acts);
  });
}
/* ---------- قسم «الأتمتة» المطوي: المزامنات وقواعد الترحيل والعمليات الجاهزة المسجّلة ---------- */
let autoSync = [], autoSyncState = {};
async function loadAuto() {
  try { const r = await api('/api/sync'); const sig = JSON.stringify([r.groups, Object.entries(r.state || {}).map(([k, v]) => [k, v.running])]); if (sig !== loadAuto.sig) { loadAuto.sig = sig; autoSync = r.groups; autoSyncState = r.state || {}; renderAuto(); } } catch (_) {}
}
function renderAuto() {
  const box = $('#autoBox'); if (!box) return; box.replaceChildren();
  const open = store.get('autoopen', '0') === '1', items = [...autoSync.map(g => ({ t: 'sync', g })), ...(readyOps || []).map(r => ({ t: 'mig', r }))];
  const active = items.filter(x => (x.g || x.r).enabled).length;
  const h = el('h4'); h.append(el('span', (open ? '▾ ' : '▸ ') + 'الأتمتة'), el('span', items.length ? `${active} مفعّلة من ${items.length}` : '', 'muted'));
  h.onclick = () => { store.set('autoopen', open ? '0' : '1'); renderAuto(); }; box.append(h);
  if (!open) return;
  if (!items.length) { box.append(el('p', 'لا أتمتة مسجّلة.', 'muted')); }
  const EV = n => n >= 1440 && n % 1440 === 0 ? `كل ${n / 1440} يوم` : n >= 60 && n % 60 === 0 ? `كل ${n / 60} ساعة` : `كل ${n} دقيقة`;
  items.forEach(x => {
    const it = x.g || x.r, running = x.t === 'sync' ? !!autoSyncState[it.id]?.running : false;
    const row = el('div', undefined, 'au' + (it.enabled ? ' on' : '') + (running ? ' run' : '')), tx = el('div', undefined, 'tx');
    let sub;
    if (x.t === 'sync') sub = `🔁 مزامنة · ${EV(it.every)}${it.last ? ' · آخر مرة ' + fdate(it.last * 1000) : ''}${it.result ? ' · ' + it.result : ''}`;
    else { const dev = it.dev === 'ios' ? (srcOf('ios:' + it.udid)?.label || 'iPhone/iPad') : 'الهاتف'; sub = `${it.enabled ? '👁 يراقب ' : '▶ يدوي · '}${dev}: ${it.src.replace('/sdcard/', '').replace('/@apps/', 'تطبيق: ')} ← ${it.dst_label || it.dst || ''}`; }
    tx.append(el('b', it.name), el('small', sub)); tx.title = sub;
    const go = btn(running ? '…' : '▶', async ev => { ev.stopPropagation(); try { await api(x.t === 'sync' ? '/api/sync/run' : '/api/migrate/run', { id: it.id }); note('بدأت: ' + it.name); loadOps(); setTimeout(loadAuto, 1500); } catch (e) { note(e.message); } }, 'btn'); go.title = 'تشغيل الآن';
    row.append(el('span', undefined, 'ad'), tx, go);
    row.onclick = () => x.t === 'sync' ? syncDialog() : migrateDialog(it.dev === 'ios' ? 'ios:' + it.udid : 'phone');
    box.append(row);
  });
  const add = el('div', undefined, 'au'); add.append(el('span', '＋', 'muted'), el('small', 'مزامنة جديدة')); add.onclick = syncDialog;
  const add2 = el('div', undefined, 'au'); add2.append(el('span', '＋', 'muted'), el('small', 'عملية جاهزة / مراقبة مجلد')); add2.onclick = () => migrateDialog();
  box.append(add, add2);
}
setInterval(loadAuto, 6000); setTimeout(loadAuto, 1200);

/* ---------- إعادة تسمية الكتب: من عنوان الكتاب ومؤلفه داخله (Calibre)، وإلا تنظيف اسمه ---------- */
const BOOK_RE = /\.(epub|azw3?|azw4|mobi|prc|kfx|pdf|djvu|fb2|lit|cbz|cbr|docx?|rtf)$/i;
$('#bookren').onclick = () => renameBooks();
async function renameBooks() {
  const p = P; if (!p?.src?.online) return;
  let paths = selectedPaths().filter(x => BOOK_RE.test(x));
  if (!paths.length) paths = p.currentList().filter(e => !e.is_dir && BOOK_RE.test(e.name)).map(e => e.path);
  if (!paths.length) { note('لا كتب في التحديد.'); return; }
  const src = p.src, ref = srcRef(src);
  let job; try { job = await api('/api/books/names', { src: ref, paths }); } catch (e) { note(e.message); return; }
  const lo = lop(`قراءة بيانات ${paths.length} كتاب`);
  openModal(m => { m.classList.add('wide'); m.append(el('h3', '📚 إعادة تسمية الكتب'), el('p', `جارٍ قراءة العنوان والمؤلف من داخل ${paths.length} كتاب…`, 'muted bkprog')); });
  for (;;) { await new Promise(r => setTimeout(r, 700)); try { job = await api('/api/books/job?id=' + job.id); } catch (_) { break; } const pg = document.querySelector('.bkprog'); if (pg) pg.textContent = `قُرئ ${job.done} من ${job.total}…`; lo.set(`${job.done} من ${job.total}`); if (job.state !== 'running') break; }
  lo.end(job.state === 'done' ? 'done' : 'error');
  const items = (job.items || []).map(it => ({ ...it, on: !it.skip && !it.error && it.suggested && it.suggested !== it.name, nv: it.suggested || it.name }));
  openModal(m => {
    m.classList.add('wide'); m.append(el('h3', '📚 إعادة تسمية الكتب'));
    const changed = items.filter(x => x.on).length;
    m.append(el('p', `${changed} اسمًا مقترحًا من ${items.length}. راجع الأسماء وعدّل ما تشاء.`, 'muted'));
    const box = el('div', undefined, 'bkren');
    items.forEach(it => {
      const r = el('div', undefined, 'br' + (it.skip || it.error ? ' skip' : ''));
      const ck = document.createElement('input'); ck.type = 'checkbox'; ck.checked = it.on; ck.disabled = !!(it.skip || it.error); ck.onchange = () => { it.on = ck.checked; };
      const inp = document.createElement('input'); inp.type = 'text'; inp.value = it.nv; inp.disabled = !!(it.skip || it.error); inp.oninput = () => { it.nv = inp.value; it.on = ck.checked = inp.value.trim() !== it.name; };
      const old = el('small', 'الحالي: ' + it.name);
      if (it.skip || it.error) old.append(el('span', it.skip || it.error, 'tag')); else if (it.source) old.append(el('span', it.source === 'meta' ? 'من داخل الكتاب' : 'تنظيف الاسم', 'tag'));
      r.append(ck, inp, el('span'), old); box.append(r);
    });
    m.append(box);
    const acts = el('div', undefined, 'acts');
    acts.append(btn('إلغاء', closeModal, 'btn'), btn('طبّق', async () => {
      const todo = items.filter(x => x.on && x.nv.trim() && x.nv.trim() !== x.name); if (!todo.length) { closeModal(); return; }
      closeModal(); const lo2 = lop(`إعادة تسمية ${todo.length} كتاب`); let ok = 0; const errs = [];
      const names = new Set(p.entries.map(e => e.name));
      for (const it of todo) {
        const nv = it.nv.trim().replace(/[\/\\:]/g, ' ');
        try {
          await runOpWait({ kind: 'rename', src: ref, paths: [it.path], name: nv }); ok++;
          // كيندل: مجلد «‎.sdr» بجوار الكتاب يحفظ موضع القراءة والتظليلات؛ يُسمّى معه حتى لا يضيع
          const stem = it.name.replace(/\.[^.]+$/, ''), sdr = stem + '.sdr';
          if (names.has(sdr)) { const dir = it.path.slice(0, it.path.length - it.name.length); await runOpWait({ kind: 'rename', src: ref, paths: [dir + sdr], name: nv.replace(/\.[^.]+$/, '') + '.sdr' }).catch(() => {}); }
        } catch (e) { errs.push(`${it.name}: ${e.message}`); }
        lo2.set(`${ok} من ${todo.length}`);
      }
      lo2.end(errs.length && !ok ? 'error' : 'done'); p.refreshNow?.();
      note(`أُعيدت تسمية ${ok} كتاب` + (errs.length ? ` · فشل ${errs.length}: ${errs[0]}` : ''));
    }, 'btn pri'));
    m.append(acts);
  });
}
async function runOpWait(body) {
  const r = await api('/api/ops/start', body);
  for (;;) { await new Promise(res => setTimeout(res, 300)); const d = await api('/api/ops/get?id=' + r.id); if (d.state !== 'running') { if (d.state !== 'done' || d.errors?.length) throw new Error(d.errors?.[0] || 'تعذّر'); return d; } }
}

// قائمة «أدوات» في شاشة التطبيقات
$('#atoolsbtn').onclick = ev => { ev.stopPropagation(); const p = $('.atoolspop'); p.hidden = !p.hidden; };
document.addEventListener('click', ev => { const p = $('.atoolspop'); if (p && !p.hidden && !ev.target.closest('.atoolspop')) p.hidden = true; });
$('.atoolspop').addEventListener('click', ev => { if (ev.target.closest('button')) setTimeout(() => { $('.atoolspop').hidden = true; }, 0); });

/* ---------- سجلّ النتائج: قائمة منسدلة لاستعادة بحث أو تنظيف سابق بدل البدء من جديد ---------- */
(function () {
  const tab = document.querySelector('.tab[data-v="files"]'); if (!tab) return;
  const sel = document.createElement('select'); sel.id = 'histsel'; sel.title = 'النتائج السابقة للبحث والتنظيف';
  sel.style.cssText = 'margin-inline-start:auto;max-width:210px;font-size:12px;opacity:.75;padding:3px 6px;border-radius:7px;border:1px solid var(--line,#ccc);background:transparent;color:inherit';
  tab.parentElement.appendChild(sel);
  const ago = t => { const m = Math.max(0, Math.round((Date.now() / 1000 - t) / 60)); return m < 60 ? `قبل ${m} د` : m < 1440 ? `قبل ${Math.round(m / 60)} س` : `قبل ${Math.round(m / 1440)} يوم`; };
  async function fill() {
    let s, c; try { [s, c] = await Promise.all([api('/api/history/list?kind=search'), api('/api/history/list?kind=clean')]); } catch (_) { return; }
    sel.replaceChildren(new Option('🕘 النتائج السابقة…', ''));
    for (const [lab, d] of [['البحث', s], ['التنظيف', c]]) {
      if (!d.items.length) continue;
      const g = document.createElement('optgroup'); g.label = lab;
      d.items.forEach(i => g.appendChild(new Option(`${i.title} · ${ago(i.time)}`, i.id)));
      sel.appendChild(g);
    }
  }
  async function open(id) {
    let r; try { r = await api('/api/history/get?id=' + encodeURIComponent(id)); } catch (e) { note(e.message); return; }
    if (r.kind === 'clean') {
      document.querySelector('[data-v="clean"]').click();
      cleanJob = r.job.id; cleanKind = r.job.kind; cleanData = r.job.result; cleanSel.clear(); cleanSizes.clear(); cleanPerm.clear(); cleanGroupOf.clear();
      $('#cprog').hidden = true; $('#cfoot').hidden = false; renderClean(); note('نتيجة محفوظة: ' + r.title + ' — يمكنك المتابعة منها.'); return;
    }
    const job = { id: 'saved', state: 'done', entries: r.entries || [], count: (r.entries || []).length, truncated: !!r.truncated, sources: r.sources, error: '', seconds: 0 };
    if (r.scope === 'multi') {
      const ids = new Set((r.entries || []).map(e => e.sid)); const list = sources.filter(s => ids.has(s.id) || (r.srcs || []).length === 0);
      const g = openGallery(r.q, r.exts || [], list.length ? list : sources.filter(s => s.online)); g.update(job); return;
    }
    document.querySelector('[data-v="files"]').click();
    const p = P; if (!p) return; p.cancelSearch();
    p.prevView = p.viewMode; if (p.viewMode === 'cols') { p.viewMode = 'list'; p.applyView(); }
    p.search = { id: 'saved', q: r.q, exts: r.exts || [], scope: r.scope, state: 'done', count: job.count, truncated: job.truncated, before: { id: p.src?.id, path: p.cur } };
    p.srch_sort = store.get('srch_sort', 'mod'); p.srch_desc = store.get('srch_desc', '1') === '1'; p.entries = job.entries; p.cursor = null; p.hideState(); p.rerender();
    note('نتيجة بحث محفوظة: ' + r.title);
  }
  sel.onchange = () => { const v = sel.value; sel.value = ''; if (v) open(v); };
  sel.onfocus = sel.onmousedown = fill;
  fill(); setInterval(fill, 60000);
})();
