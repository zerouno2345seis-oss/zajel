// ينقل واجهة زاجل إلى المجلد الذي يطلب المساعد فتحه (أداة open_in_zajel). مستقل عن نافذة المساعد ليعمل ولو كانت مغلقة.
(() => {
  let last = -1, busy = false;
  const parentOf = p => { const i = p.replace(/\/+$/, '').lastIndexOf('/'); return i <= 0 ? (p.startsWith('/') ? '/' : '') : p.slice(0, i); };
  async function tick() {
    if (busy || document.hidden || typeof P === 'undefined' || !P) return;
    busy = true;
    try {
      const r = await fetch('/api/assistant/nav?after=' + last, { cache: 'no-store' });
      const d = await r.json();
      if (last < 0) { last = d.seq; return; }
      for (const it of d.items || []) {
        last = Math.max(last, it.seq);
        if (it.is_file) P.reveal({ path: it.path, folder: parentOf(it.path), is_dir: false, name: it.path.split('/').pop() }, it.place);
        else await P.go(it.place, it.path);
        try { window.focus(); } catch (_) {}
      }
    } catch (_) { /* الخادم مشغول أو لا مساعد بعد: نعيد المحاولة */ }
    finally { busy = false; }
  }
  setInterval(tick, 1500);
  tick();

  // إشعارات الأتمتة تظهر منبثقة في الواجهة فور وصولها (أول استعلام يكتفي بتسجيل الموجود)
  let seenN = null;
  async function noticeTick() {
    if (document.hidden || !window.uiToast) return;
    try {
      const d = await (await fetch('/api/assistant/automations', { cache: 'no-store' })).json();
      const ids = new Set((d.notices || []).map(n => n.id));
      if (seenN) (d.notices || []).filter(n => !seenN.has(n.id) && !n.read).reverse().forEach(n => window.uiToast((n.level === 'error' ? 'تعذّر في أتمتة «' : 'أتمتة «') + n.rule + '»: ' + n.text));
      seenN = ids;
    } catch (_) { /* لا شيء */ }
  }
  setInterval(noticeTick, 15000);
  noticeTick();
})();
