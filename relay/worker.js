// وسيط «زاجل في تيليجرام» على Cloudflare Workers (مجاني).
// - يخدم صفحة التطبيق المصغّر (public/) ويستقبل طلباتها.
// - يتحقق من توقيع تيليجرام ومن أن المستخدم هو المقترن (ALLOWED_USER_ID) قبل أي شيء.
// - لا يفتح منفذًا للماك: الماك هو الذي يسأل الوسيط عمّا ينتظره (long-poll) ثم يرد.
// - الأسرار: BOT_TOKEN وMAC_KEY وALLOWED_USER_ID أسرار في Cloudflare (wrangler secret put)، لا في أي ملف.
import { verifyInitData } from './verify.js';

const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } });
const MAX_BODY = 64 * 1024;

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const hub = env.HUB.get(env.HUB.idFromName('main'));

    if (url.pathname === '/api' && req.method === 'POST') {
      const raw = await req.text();
      if (raw.length > MAX_BODY) return json({ error: 'الطلب كبير' }, 413);
      const v = await verifyInitData(req.headers.get('x-init-data'), env.BOT_TOKEN, Math.floor(Date.now() / 1000));
      if (!v.ok) return json({ error: v.error }, 401);
      if (String(v.user.id) !== String(env.ALLOWED_USER_ID)) return json({ error: 'هذا الحساب غير مقترن بزاجل' }, 403);   // يُرفض كل من عدا المقترن
      let b;
      try { b = JSON.parse(raw); } catch { return json({ error: 'طلب غير صالح' }, 400); }
      const device = String(b.device || '').slice(0, 60);
      // الصفحة لا تعرف اسم الجهاز في أول طلب: تُرسل device.list بلا جهاز فيوجَّه إلى أي جهاز موصول
      if (typeof b.op !== 'string' || (!device && b.op !== 'device.list')) return json({ error: 'طلب ناقص' }, 400);
      const job = { id: crypto.randomUUID(), device, user: v.user.id, op: b.op, args: b.args || {}, confirm: b.confirm || null };
      return hub.fetch('https://hub/enqueue', { method: 'POST', body: JSON.stringify(job) });
    }

    if (url.pathname === '/mac/poll' || url.pathname === '/mac/reply') {
      if (!env.MAC_KEY || req.headers.get('x-mac-key') !== env.MAC_KEY) return json({ error: 'غير مصرح' }, 401);
      return hub.fetch('https://hub' + url.pathname + url.search, { method: req.method, body: req.method === 'POST' ? await req.text() : undefined });
    }

    if (url.pathname === '/health') return json({ ok: true });
    return env.ASSETS.fetch(req);          // الصفحة نفسها
  },
};

// مركز واحد يحمل طابورًا لكل جهاز وينتظر الرد
export class Hub {
  constructor() { this.q = {}; this.pollers = {}; this.waiters = {}; this.seen = {}; }

  async fetch(req) {
    const u = new URL(req.url);
    if (u.pathname === '/enqueue') {
      const job = await req.json();
      if (!job.device) {                                   // أحدث جهاز اتصل خلال دقيقة
        const now = Date.now();
        job.device = Object.keys(this.seen).filter((d) => now - this.seen[d] < 60000).sort((a, b) => this.seen[b] - this.seen[a])[0] || '';
        if (!job.device) return json({ error: 'لا يوجد جهاز موصول الآن. افتح زاجل على الماك.' }, 503);
      }
      return new Promise((resolve) => {
        const t = setTimeout(() => { delete this.waiters[job.id]; resolve(json({ error: 'الجهاز لا يردّ (قد يكون نائمًا أو مغلقًا)' }, 504)); }, 28000);
        this.waiters[job.id] = (reply) => { clearTimeout(t); resolve(json(reply)); };
        (this.q[job.device] ||= []).push(job);
        const p = this.pollers[job.device];
        if (p) { delete this.pollers[job.device]; p(this.q[job.device].splice(0)); }
      });
    }
    if (u.pathname === '/mac/poll') {
      const device = u.searchParams.get('device') || '';
      this.seen[device] = Date.now();
      const wait = Math.min(25, Number(u.searchParams.get('wait') || 20)) * 1000;
      if (this.q[device]?.length) return json({ jobs: this.q[device].splice(0) });
      return new Promise((resolve) => {
        const t = setTimeout(() => { if (this.pollers[device] === done) delete this.pollers[device]; resolve(json({ jobs: [] })); }, wait);
        const done = (jobs) => { clearTimeout(t); resolve(json({ jobs })); };
        this.pollers[device] = done;
      });
    }
    if (u.pathname === '/mac/reply') {
      const { id, reply } = await req.json();
      const w = this.waiters[id];
      if (w) { delete this.waiters[id]; w(reply || {}); }
      return json({ ok: !!w });
    }
    return json({ error: 'غير موجود' }, 404);
  }
}
