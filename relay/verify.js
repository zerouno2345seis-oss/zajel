// التحقق من توقيع بيانات التطبيق المصغّر (initData) كما في توثيق تيليجرام:
// secret = HMAC_SHA256(key="WebAppData", msg=BOT_TOKEN)؛ hash = HMAC_SHA256(key=secret, msg=الحقول مرتبة وبينها \n بلا hash)
const enc = new TextEncoder();

async function hmac(keyBytes, msgBytes) {
  const key = await crypto.subtle.importKey('raw', keyBytes, { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  return new Uint8Array(await crypto.subtle.sign('HMAC', key, msgBytes));
}
const hex = (u8) => [...u8].map((b) => b.toString(16).padStart(2, '0')).join('');

function sameHex(a, b) { // مقارنة بزمن ثابت
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

// يعيد { ok, user, error }
export async function verifyInitData(initData, botToken, nowSec, maxAgeSec = 3600) {
  if (!initData || !botToken) return { ok: false, error: 'بيانات ناقصة' };
  const params = new URLSearchParams(initData);
  const hash = params.get('hash');
  if (!hash) return { ok: false, error: 'لا توقيع' };
  params.delete('hash');
  const lines = [...params.entries()].map(([k, v]) => `${k}=${v}`).sort();
  const secret = await hmac(enc.encode('WebAppData'), enc.encode(botToken));
  const calc = hex(await hmac(secret, enc.encode(lines.join('\n'))));
  if (!sameHex(calc, hash)) return { ok: false, error: 'توقيع غير صحيح' };
  const auth = Number(params.get('auth_date') || 0);
  if (!auth || nowSec - auth > maxAgeSec || auth - nowSec > 300) return { ok: false, error: 'انتهت صلاحية الفتح؛ أعد فتح التطبيق' };
  let user;
  try { user = JSON.parse(params.get('user') || '{}'); } catch { return { ok: false, error: 'مستخدم غير صالح' }; }
  if (!user.id) return { ok: false, error: 'لا مستخدم' };
  return { ok: true, user };
}
