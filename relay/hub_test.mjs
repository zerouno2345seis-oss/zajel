import { Hub } from './worker.js';
const h = new Hub();
const post = (path, body) => h.fetch(new Request('https://hub' + path, { method: 'POST', body: JSON.stringify(body) }));
// بلا أي جهاز: 503
let r = await post('/enqueue', { id: '1', device: '', op: 'device.list' });
console.log('no-device', r.status);
// جهاز يستعلم ثم طلب بلا جهاز يصله
const poll = h.fetch(new Request('https://hub/mac/poll?device=Mac-A&wait=5'));
await new Promise((x) => setTimeout(x, 50));
const enq = post('/enqueue', { id: '2', device: '', op: 'device.list' });
const jobs = await (await poll).json();
console.log('routed-to', jobs.jobs[0]?.device, jobs.jobs[0]?.op);
await post('/mac/reply', { id: '2', reply: { devices: [] } });
console.log('reply', JSON.stringify(await (await enq).json()));
process.exit(0);
