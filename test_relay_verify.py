"""يتحقق أن وسيط الويب يقبل توقيع تيليجرام الصحيح ويرفض المزوَّر والقديم (يشغّل node مع نفس الشيفرة التي تُنشر)."""
import hashlib
import hmac
import json
import os
import shutil
import subprocess
import time
import unittest
import urllib.parse
from pathlib import Path

RELAY = Path(__file__).parent / "relay"
TOKEN = "1234:" + os.urandom(16).hex()          # يُولَّد وقت الاختبار؛ ليس مفتاحًا حقيقيًا
OTHER = "999:" + os.urandom(16).hex()


def sign(fields, token=TOKEN):
    lines = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret, lines.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode({**fields, "hash": h})


def verify(init, now, token=TOKEN):
    js = f"""import {{ verifyInitData }} from {json.dumps((RELAY / 'verify.js').as_uri())};
const r = await verifyInitData({json.dumps(init)}, {json.dumps(token)}, {now});
console.log(JSON.stringify(r));"""
    p = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, timeout=30)
    return json.loads(p.stdout.strip() or "{}") if p.returncode == 0 else {"crash": p.stderr[-300:]}


@unittest.skipUnless(shutil.which("node"), "node غير مثبت")
class Verify(unittest.TestCase):
    def fields(self, **k):
        return {"auth_date": str(int(time.time())), "query_id": "AAH", "user": json.dumps({"id": 777, "first_name": "س"}, ensure_ascii=False), **k}

    def test_valid(self):
        r = verify(sign(self.fields()), int(time.time()))
        self.assertTrue(r.get("ok"), r)
        self.assertEqual(r["user"]["id"], 777)

    def test_tampered_user_rejected(self):
        init = sign(self.fields())
        forged = init.replace("777", "888")
        self.assertFalse(verify(forged, int(time.time()))["ok"])

    def test_wrong_token_rejected(self):
        self.assertFalse(verify(sign(self.fields(), token=OTHER), int(time.time()))["ok"])

    def test_old_rejected(self):
        old = self.fields(auth_date=str(int(time.time()) - 7200))
        r = verify(sign(old), int(time.time()))
        self.assertFalse(r["ok"])
        self.assertIn("انتهت", r["error"])

    def test_missing_hash_or_empty(self):
        self.assertFalse(verify("auth_date=1&user=%7B%7D", int(time.time()))["ok"])
        self.assertFalse(verify("", int(time.time()))["ok"])

    def test_future_date_rejected(self):
        self.assertFalse(verify(sign(self.fields(auth_date=str(int(time.time()) + 4000))), int(time.time()))["ok"])


if __name__ == "__main__":
    unittest.main()
