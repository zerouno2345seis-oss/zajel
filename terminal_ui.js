(() => {
  'use strict';
  if (window.ZajelTerminalUI) return;
  let councilApi = null, root = null, listTimer = null, screenTimer = null, resizeObserver = null, councilRoot = null, councilTimer = null, councilRoundId = '', councilPanel = null, councilFolded = true;
  let activeSlot = 0, agents = [], slots = [], layout = 1, notify = false, hist = 0, listBusy = false, builtLayout = 0, sendChain = Promise.resolve();
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const req = async (path, body) => {
    const url = '/api/term/' + path;
    if (typeof window.api === 'function') return window.api(url, body);
    const response = await fetch(url, body ? { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) } : {});
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return response.json();
  };
  const cssColor = (r,g,b) => `rgb(${r},${g},${b})`;
  const palette = ['#000000','#aa0000','#00aa00','#aa5500','#0000aa','#aa00aa','#00aaaa','#aaaaaa','#555555','#ff5555','#55ff55','#ffff55','#5555ff','#ff55ff','#55ffff','#ffffff'];
  const color256 = n => { if(n<16)return palette[n]; if(n<232){n-=16;const v=[0,95,135,175,215,255];return cssColor(v[Math.floor(n/36)],v[Math.floor(n/6)%6],v[n%6]);} const v=8+(n-232)*10;return cssColor(v,v,v); };
  function ansiHtml(input) {
    const text=String(input||''); let out='', last=0, style={};
    const wrap = chunk => { if(!chunk)return ''; let css=[]; if(style.fg)css.push('color:'+style.fg); if(style.bg)css.push('background-color:'+style.bg); if(style.bold)css.push('font-weight:bold'); if(style.dim)css.push('opacity:.65'); if(style.italic)css.push('font-style:italic'); if(style.underline)css.push('text-decoration:underline'); if(style.inverse)css.push('filter:invert(1)'); return `<span${css.length?' style="'+css.join(';')+'"':''}>${esc(chunk)}</span>`; };
    const re=/\x1b\[([0-9;]*)m/g; let m;
    while((m=re.exec(text))){out+=wrap(text.slice(last,m.index));last=re.lastIndex;const a=(m[1]||'0').split(';').map(x=>Number(x||0));for(let i=0;i<a.length;i++){const n=a[i];if(n===0)style={};else if(n===1)style.bold=true;else if(n===2)style.dim=true;else if(n===3)style.italic=true;else if(n===4)style.underline=true;else if(n===7)style.inverse=true;else if(n===22){style.bold=false;style.dim=false;}else if(n===23)style.italic=false;else if(n===24)style.underline=false;else if(n===27)style.inverse=false;else if(n===39)delete style.fg;else if(n===49)delete style.bg;else if(n>=30&&n<=37)style.fg=palette[n-30];else if(n>=90&&n<=97)style.fg=palette[n-90+8];else if(n>=40&&n<=47)style.bg=palette[n-40];else if(n>=100&&n<=107)style.bg=palette[n-100+8];else if((n===38||n===48)&&a[i+1]===5){style[n===38?'fg':'bg']=color256(a[i+2]||0);i+=2;}else if((n===38||n===48)&&a[i+1]===2){style[n===38?'fg':'bg']=cssColor(a[i+2]||0,a[i+3]||0,a[i+4]||0);i+=4;}}}
    return out+wrap(text.slice(last));
  }
  function stateColor(s){return s==='working'?'#22c55e':s==='waiting'?'#eab308':s==='shell'?'#ef4444':'#94a3b8';}
  function send(slot, payload){sendChain=sendChain.then(()=>req('send',{id:slot.id,...payload})).then(()=>setMsg(slot,'')).catch(e=>setMsg(slot,'تعذّر الإرسال: '+(e&&e.message||'خطأ'),true));}
  function build(){ if(!root)return; root.replaceChildren(); root.dir='rtl'; root.className='as-terminal-ui';
    const unavailable=document.createElement('div'); unavailable.className='as-memory-hint'; unavailable.hidden=true; root.appendChild(unavailable);
    const councilToggle=document.createElement('button');councilToggle.type='button';councilToggle.className='btn';councilToggle.textContent='⚖ مجلس الوكلاء (شاشة كاملة)';councilToggle.onclick=()=>{if(win&&win.el.isConnected)win.show('council');};root.appendChild(councilToggle);
    const app=document.createElement('div'); app.className='as-terminal'; root.appendChild(app);
    const toolbar=document.createElement('div'); toolbar.className='as-terminal-toolbar'; app.appendChild(toolbar);
    const cards=document.createElement('div'); cards.className='as-terminal-agents'; app.appendChild(cards);
    const controls=document.createElement('div'); controls.className='as-terminal-controls'; app.appendChild(controls);
    const viewport=document.createElement('div'); viewport.className='as-terminal-grid'; app.appendChild(viewport);
    const renderControls=()=>{controls.replaceChildren();[1,2,3,4,5].forEach(n=>{const b=document.createElement('button');b.className='btn'+(layout===n?' pri':'');b.textContent=String(n);b.title='عدد النوافذ';b.onclick=()=>{layout=n;build();refreshList();};controls.appendChild(b);});const down=document.createElement('button');down.className='btn';down.textContent='انتقل إلى الأسفل';down.onclick=()=>viewport.querySelectorAll('pre').forEach(x=>x.scrollTop=x.scrollHeight);controls.appendChild(down);const tg=document.createElement('button');tg.className='btn';tg.textContent='الوكلاء ▾';tg.onclick=()=>{cards.classList.toggle('open');tg.textContent=cards.classList.contains('open')?'الوكلاء ▴':'الوكلاء ▾';};controls.insertBefore(tg,controls.firstChild);const longer=document.createElement('button');longer.className='btn';longer.textContent='سجلّ أطول';longer.onclick=()=>{hist=hist?0:2000;longer.textContent=hist?'عرض الشاشة فقط':'سجلّ أطول';refreshScreens(true);};controls.appendChild(longer);const dirb=document.createElement('button');dirb.className='btn';const dirTxt=()=>root.dataset.dir==='ltr'?'الاتجاه: يسار ثابت':'الاتجاه: تلقائي (عربي يمينًا)';root.dataset.dir=(()=>{try{return localStorage.getItem('zajel_term_dir')||'auto';}catch(_){return 'auto';}})();dirb.textContent=dirTxt();dirb.onclick=()=>{root.dataset.dir=root.dataset.dir==='ltr'?'auto':'ltr';try{localStorage.setItem('zajel_term_dir',root.dataset.dir);}catch(_){}dirb.textContent=dirTxt();};controls.appendChild(dirb);const lab=document.createElement('label');lab.className='as-terminal-notify';const cb=document.createElement('input');cb.type='checkbox';cb.checked=notify;cb.onchange=()=>{notify=cb.checked;req('notify',{on:notify}).catch(()=>{});};lab.append(cb,document.createTextNode('إشعار تيليجرام عند انتظار الوكيل/انتهائه'));controls.appendChild(lab);};
    renderControls();
    while(slots.length<layout)slots.push({id:agents[slots.length]?.id||'',hash:'',pre:null,select:null,card:null});slots=slots.slice(0,layout);
    slots.forEach((slot,index)=>{const card=document.createElement('section');card.className='as-terminal-window';slot.card=card;const head=document.createElement('div');head.className='as-terminal-window-head';const select=document.createElement('select');select.setAttribute('aria-label','اختر الوكيل');agents.forEach(a=>{const o=document.createElement('option');o.value=a.id;o.textContent=a.name+' · '+a.label;select.appendChild(o);});if(slot.id)select.value=slot.id;if(!slot.id&&agents[0])slot.id=agents[0].id;select.onchange=()=>{slot.id=select.value;slot.hash='';refreshScreens(true);};slot.select=select;head.appendChild(select);const pre=document.createElement('pre');pre.dir='ltr';pre.tabIndex=0;pre.className='as-terminal-screen';pre.setAttribute('aria-label','شاشة الطرفية · اضغط للكتابة');const ta=document.createElement('textarea');ta.setAttribute('aria-label','إدخال الطرفية');ta.setAttribute('autocapitalize','off');ta.setAttribute('autocomplete','off');ta.setAttribute('autocorrect','off');ta.spellcheck=false;ta.style.cssText='position:absolute;opacity:0;width:2px;height:2px;left:0;top:0;border:0;padding:0;resize:none;font-size:16px';slot.input=ta;const msg=document.createElement('small');msg.className='as-terminal-msg';slot.msg=msg;head.appendChild(msg);slot.pre=pre;pre.addEventListener('focus',()=>{activeSlot=index;root&&root.querySelectorAll('.as-terminal-window').forEach((w,k)=>w.classList.toggle('is-active',k===index));});card.style.position='relative';card.append(head,pre,ta);viewport.appendChild(card);wireKeys(slot);});
    const agentStyle=document.createElement('style');agentStyle.textContent='.as-council-terminal-panel{max-height:42vh;overflow:auto;min-height:0;border:1px solid var(--line);border-radius:9px;padding:7px}.as-terminal-ui{display:flex;flex-direction:column;gap:8px;min-height:0;flex:1;height:100%}.as-terminal{display:grid;grid-template-columns:232px minmax(0,1fr);grid-template-rows:auto minmax(0,1fr);gap:10px;flex:1;min-height:0}.as-terminal-agents{grid-row:1/3;grid-column:1;display:flex;flex-direction:column;gap:7px;overflow-y:auto;padding:2px;min-height:0}.as-terminal-controls{grid-column:2;grid-row:1;display:flex;gap:6px;align-items:center;flex-wrap:wrap}.as-terminal-grid{grid-column:2;grid-row:2;display:grid;gap:8px;min-height:0;min-width:0;grid-template-columns:1fr;grid-auto-rows:minmax(0,1fr)}.as-terminal-ui[data-layout="2"] .as-terminal-grid{grid-template-rows:repeat(2,minmax(0,1fr))}.as-terminal-ui[data-layout="4"] .as-terminal-grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:repeat(2,minmax(0,1fr))}.as-terminal-toolbar{display:none}.as-terminal-agent{border:1px solid var(--line);border-radius:10px;padding:8px 9px;background:var(--bg);cursor:pointer}.as-terminal-agent.is-shown{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc) inset}.as-terminal-agent-head{display:flex;align-items:center;gap:6px;font-weight:600}.as-terminal-dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}.as-terminal-label{font-size:11px;color:var(--mut);margin:3px 0 6px}.as-terminal-actions{display:flex;gap:5px;flex-wrap:wrap;align-items:center}.as-terminal-actions .btn{padding:3px 9px;font-size:11.5px}.as-terminal-notify{display:flex;gap:5px;align-items:center;font-size:11.5px;margin-inline-start:auto}.as-terminal-window{min-width:0;min-height:0;display:flex;flex-direction:column;border:1px solid var(--line);border-radius:9px;overflow:hidden}.as-terminal-window.is-active{border-color:var(--acc)}.as-terminal-window-head{padding:4px;background:var(--side);flex:none}.as-terminal-window-head select{max-width:100%;width:100%}.as-terminal-screen{margin:0;padding:8px 10px;overflow:auto;white-space:pre;direction:ltr;unicode-bidi:plaintext;text-align:start;background:#101318;color:#e5e7eb;font:12.5px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;flex:1;min-height:0;outline:none;tab-size:8}.as-terminal-ui[data-dir="ltr"] .as-terminal-screen{unicode-bidi:normal;text-align:left}.as-terminal-window:focus-within{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc)}.as-terminal-msg{display:block;font-size:11px;min-height:14px;padding:2px 4px;color:var(--mut)}.as-terminal-screen:focus{box-shadow:inset 0 0 0 1px var(--acc)}@media(max-width:860px){.as-terminal{grid-template-columns:minmax(0,1fr);grid-template-rows:auto auto minmax(0,1fr)}.as-terminal-agents{grid-row:1;grid-column:1;flex-direction:row;overflow-x:auto;overflow-y:hidden}.as-terminal-agent{flex:0 0 150px}.as-terminal-controls{grid-column:1;grid-row:2}.as-terminal-grid{grid-column:1;grid-row:3}.as-terminal-ui[data-layout="4"] .as-terminal-grid,.as-terminal-ui[data-layout="2"] .as-terminal-grid{grid-template-columns:1fr;grid-template-rows:none;grid-auto-rows:minmax(180px,1fr);overflow-y:auto}}.as-terminal{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:auto auto minmax(0,1fr)!important;gap:6px}.as-terminal-agents{grid-row:1!important;grid-column:1!important;flex-direction:row!important;flex-wrap:wrap;overflow:visible!important}.as-terminal-agent{padding:3px 9px!important;flex:none!important;border-radius:99px}.as-terminal-agent .as-terminal-label,.as-terminal-agent .as-terminal-actions{display:none}.as-terminal-agents.open .as-terminal-agent{flex:0 0 150px!important;border-radius:10px;padding:8px 9px!important}.as-terminal-agents.open .as-terminal-label{display:block}.as-terminal-agents.open .as-terminal-actions{display:flex}.as-terminal-controls{grid-column:1!important;grid-row:2!important}.as-terminal-grid{grid-column:1!important;grid-row:3!important}.as-terminal-ui[data-layout="2"] .as-terminal-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-template-rows:minmax(0,1fr)!important}.as-terminal-ui[data-layout="3"] .as-terminal-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important;grid-template-rows:minmax(0,1fr)!important}.as-terminal-ui[data-layout="4"] .as-terminal-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-template-rows:repeat(2,minmax(0,1fr))!important}.as-terminal-ui[data-layout="5"] .as-terminal-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important;grid-template-rows:repeat(2,minmax(0,1fr))!important}.as-terminal-screen{font-size:12px}@media(max-width:860px){.as-terminal-ui[data-layout="2"] .as-terminal-grid,.as-terminal-ui[data-layout="3"] .as-terminal-grid,.as-terminal-ui[data-layout="4"] .as-terminal-grid,.as-terminal-ui[data-layout="5"] .as-terminal-grid{grid-template-columns:1fr!important;grid-template-rows:none!important;grid-auto-rows:minmax(220px,1fr);overflow-y:auto}}';root.appendChild(agentStyle);root.dataset.layout=String(layout);
    renderAgents();
    resizeObserver?.disconnect();resizeObserver=new ResizeObserver(entries=>{for(const e of entries){const s=slots.find(x=>x.pre===e.target);if(s)resizeSlot(s);}});slots.forEach(s=>{if(s.pre)resizeObserver.observe(s.pre);});
  }
  function renderAgents(){if(!root)return;const cards=root.querySelector('.as-terminal-agents');if(!cards)return;cards.replaceChildren();agents.forEach(a=>{const c=document.createElement('div');c.className='as-terminal-agent';const h=document.createElement('div');h.className='as-terminal-agent-head';const dot=document.createElement('span');dot.className='as-terminal-dot';dot.style.background=stateColor(a.state);h.append(dot,document.createTextNode(a.name));const label=document.createElement('div');label.className='as-terminal-label';label.textContent=a.label||a.state||'';const actions=document.createElement('div');actions.className='as-terminal-actions';(a.state==='stopped'?[['تشغيل','start']]:[['إعادة تشغيل','restart'],['إيقاف','stop']]).forEach(([t,op])=>{const b=document.createElement('button');b.className='btn';b.textContent=t;b.disabled=op==='start'&&a.installed===false;b.title=a.installed===false?'غير مثبّت':t;b.onclick=async(ev)=>{ev.stopPropagation();try{await req(op,{id:a.id});if(op!=='stop')showAgent(a.id);setTimeout(refreshList,250);}catch(_){}};actions.appendChild(b);});if(a.installed===false){const not=document.createElement('small');not.textContent='غير مثبّت';not.className='as-card-err';actions.appendChild(not);}c.classList.toggle('is-shown',slots.some(x=>x.id===a.id));c.onclick=()=>showAgent(a.id);c.append(h,label,actions);cards.appendChild(c);});root.querySelectorAll('.as-terminal-window').forEach((w,i)=>{const s=w.querySelector('select');if(!s)return;const old=slots[i]?.id;s.replaceChildren();agents.forEach(a=>{const o=document.createElement('option');o.value=a.id;o.textContent=a.name+' · '+a.label;s.appendChild(o);});if(old&&agents.some(a=>a.id===old))s.value=old;});}
  const KEYMAP={Enter:'Enter',Backspace:'BSpace',Tab:'Tab',ArrowUp:'Up',ArrowDown:'Down',ArrowLeft:'Left',ArrowRight:'Right',Home:'Home',End:'End',PageUp:'PgUp',PageDown:'PgDn',Delete:'DC',Escape:'Escape'};
  function setMsg(slot,text,bad){if(!slot.msg)return;slot.msg.textContent=text||'';slot.msg.style.color=bad?'#ef4444':'';}
  function wireKeys(slot){
    const pre=slot.pre,ta=slot.input;let queue=[],timer=null,composing=false;
    const flush=()=>{timer=null;if(!queue.length)return;const batch=queue;queue=[];let text='';for(const p of batch){if(p.text!=null)text+=p.text;else{if(text){send(slot,{text});text='';}send(slot,{keys:[p.key]});}}if(text)send(slot,{text});};
    const push=p=>{queue.push(p);if(!timer)timer=setTimeout(flush,30);};
    const focusIt=()=>{ta.focus({preventScroll:true});};
    pre.addEventListener('mousedown',()=>setTimeout(()=>{if(!getSelection().toString())focusIt();},0));
    pre.addEventListener('focus',focusIt);
    ta.addEventListener('focus',()=>{activeSlot=slots.indexOf(slot);setMsg(slot,'اكتب الآن…');});
    ta.addEventListener('blur',()=>setMsg(slot,'اضغط داخل الشاشة ثم اكتب'));setMsg(slot,'اضغط داخل الشاشة ثم اكتب');
    ta.addEventListener('compositionstart',()=>{composing=true;});
    ta.addEventListener('compositionend',e=>{composing=false;if(e.data)push({text:e.data});ta.value='';});
    // أي نص يدخل (لوحة المفاتيح العربية، الإملاء الصوتي، الإدخال الخارجي) يصل من هنا
    ta.addEventListener('input',e=>{if(composing||e.isComposing)return;const v=ta.value;ta.value='';if(v)push({text:v.replace(/\r?\n/g,'\r')});});
    ta.addEventListener('keydown',e=>{
      if(e.isComposing||composing||e.keyCode===229)return;
      let key=KEYMAP[e.key];
      if(key){e.preventDefault();if(e.key==='Tab'&&e.shiftKey)key='BTab';push({key});return;}
      if(/^F(?:[1-9]|1[0-2])$/.test(e.key)){e.preventDefault();push({key:e.key});return;}
      if(e.ctrlKey&&!e.metaKey&&e.key.length===1){e.preventDefault();push({key:'C-'+e.key.toLowerCase()});return;}
      if(e.altKey&&!e.metaKey&&!e.ctrlKey&&/^[a-z]$/i.test(e.code.replace('Key',''))&&e.code.startsWith('Key')){e.preventDefault();push({key:'M-'+e.code.slice(3).toLowerCase()});return;}
      // بقية الحروف تُترك لحدث input
    });
    ta.addEventListener('paste',e=>{e.preventDefault();const t=e.clipboardData.getData('text/plain');if(t)send(slot,{text:t,paste:true});});
  }
  function resizeSlot(slot){if(!slot.id||!slot.pre)return;const probe=document.createElement('span');probe.textContent='M';probe.style.cssText='position:absolute;visibility:hidden;font:12px ui-monospace,monospace';slot.pre.appendChild(probe);const cw=probe.getBoundingClientRect().width||7.2,ch=parseFloat(getComputedStyle(slot.pre).lineHeight)||16;probe.remove();const cols=Math.max(20,Math.floor((slot.pre.clientWidth-18)/cw)),rows=Math.max(5,Math.floor((slot.pre.clientHeight-16)/ch));clearTimeout(slot.resizeTimer);slot.resizeTimer=setTimeout(()=>req('resize',{id:slot.id,cols,rows}).catch(()=>{}),180);}
  function showAgent(id){const sl=slots[Math.min(activeSlot,slots.length-1)];if(!sl||sl.id===id)return;sl.id=id;sl.hash='';if(sl.select)sl.select.value=id;refreshScreens(true);renderAgents();}
  function showAgents(ids){if(!root)return false;ids=(ids||[]).filter(Boolean).slice(0,5);if(!ids.length)return false;layout=ids.length;slots=ids.map(id=>({id,hash:'',pre:null,select:null,card:null}));councilFolded=true;activeSlot=0;build();builtLayout=layout;refreshList();refreshScreens(true);return true;}
  function syncSelects(){slots.forEach((slot,i)=>{if(!slot.select)return;if(!slot.id&&agents[i])slot.id=agents[i].id||agents[0]?.id||'';if(!slot.id&&agents[0])slot.id=agents[0].id;const sel=slot.select;sel.replaceChildren();agents.forEach(a=>{const o=document.createElement('option');o.value=a.id;o.textContent=a.name+' · '+a.label;sel.appendChild(o);});if(slot.id)sel.value=slot.id;});}
  async function refreshList(){if(!root||listBusy)return;listBusy=true;try{const data=await req('list');agents=Array.isArray(data.agents)?data.agents:[];notify=!!data.notify;const hint=root.querySelector('.as-memory-hint'),app=root.querySelector('.as-terminal');if(data.available===false){hint.hidden=false;hint.textContent=data.hint||'الطرفية غير متاحة';app.hidden=true;}else{hint.hidden=true;app.hidden=false;if(builtLayout!==layout){build();builtLayout=layout;}else renderAgents();syncSelects();}}catch(e){const hint=root.querySelector('.as-memory-hint');hint.hidden=false;hint.textContent='تعذر تحميل قائمة الطرفيات: '+e.message;}finally{listBusy=false;}}
  async function refreshScreens(force){if(!root||root.hidden)return;for(const slot of slots){if(!slot.id||!slot.pre)continue;try{const d=await req('screen?id='+encodeURIComponent(slot.id)+'&since='+encodeURIComponent(force?'':slot.hash)+'&hist='+hist);if(d.hash)slot.hash=d.hash;if(!d.unchanged&&typeof d.text==='string'){const pre=slot.pre,stick=pre.scrollHeight-pre.scrollTop-pre.clientHeight<40||!pre.dataset.init;pre.innerHTML=ansiHtml(d.text);pre.dataset.init='1';if(stick)pre.scrollTop=pre.scrollHeight;}if(d.alive===false)slot.pre.dataset.dead='true';}catch(_){}}}
  const councilStateText={queued:'في الانتظار',starting:'يبدأ',asking:'يجيب',done:'انتهى',done_raw:'انتهى بلا علامات',timeout:'انتهت المهلة',error:'خطأ',stopped:'متوقف'};
  const councilStateColor={queued:'#a3a3a3',starting:'#eab308',asking:'#3b82f6',done:'#22c55e',done_raw:'#16a34a',timeout:'#f97316',error:'#ef4444',stopped:'#737373'};
  function councilButton(label,action,primary){const b=document.createElement('button');b.type='button';b.className='btn'+(primary?' pri':'');b.textContent=label;b.onclick=action;return b;}
  const agentColors = { claude: '#d97757', codex: '#10a37f', agy: '#4285f4', hermes: '#a855f7', opencode: '#14b8a6', pi: '#ec4899' };
  const colorOf = id => agentColors[id] || '#64748b';
  const mdBox = text => {
    const box = document.createElement('div'); box.className = 'cn-md'; box.dir = 'auto'; let ul = null;
    const fill = (el, t) => t.split(/(\*\*[^*]+\*\*)/).forEach(part => {
      if (/^\*\*[^*]+\*\*$/.test(part)) { const b = document.createElement('b'); b.textContent = part.slice(2, -2); el.appendChild(b); } else el.appendChild(document.createTextNode(part));
    });
    String(text || '').split('\n').forEach(ln => {
      const h = ln.match(/^(#{1,4})\s+(.*)/), b = ln.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)/);
      if (!b) ul = null;
      if (h) { const e = document.createElement('h4'); fill(e, h[2]); box.appendChild(e); }
      else if (b) { if (!ul) { ul = document.createElement('ul'); box.appendChild(ul); } const li = document.createElement('li'); fill(li, b[1]); ul.appendChild(li); }
      else if (ln.trim()) { const p = document.createElement('p'); fill(p, ln); box.appendChild(p); }
    });
    return box;
  };
  const CN_CSS = `
.cn{--gold:#d4a017;display:flex;flex-direction:column;gap:10px;min-width:0;width:100%;min-height:0;flex:1;height:100%;color:var(--fg);font-size:13.5px}
.cn *{box-sizing:border-box}
.cn-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.cn-top h3{margin:0;font-size:15px;flex:1}
.cn-roster{display:flex;flex-wrap:wrap;gap:8px}
.cn-chip{display:flex;align-items:center;gap:7px;padding:5px 6px 5px 11px;border:1.5px solid var(--line);border-radius:99px;background:var(--bg);cursor:pointer;transition:all .15s;user-select:none}
.cn-chip:hover{border-color:var(--c)}
.cn-chip.on{border-color:var(--c);background:color-mix(in srgb,var(--c) 11%,var(--bg))}
.cn-chip.judge{box-shadow:0 0 0 2px var(--gold)}
.cn-av{width:24px;height:24px;border-radius:50%;background:var(--c);color:#fff;display:inline-flex;align-items:center;justify-content:center;font-weight:700;font-size:12px;flex:none}
.cn-crown{border:0;background:transparent;cursor:pointer;font-size:15px;opacity:.35;padding:0 3px;filter:grayscale(1)}
.cn-chip.judge .cn-crown,.cn-crown:hover{opacity:1;filter:none}
.cn-sub{color:var(--mut);font-size:12px}
.cn-composer{border:1.5px solid var(--line);border-radius:14px;background:var(--bg);padding:8px;display:flex;flex-direction:column;gap:6px;transition:border-color .15s}
.cn-composer:focus-within{border-color:var(--acc);box-shadow:0 0 0 2px color-mix(in srgb,var(--acc) 20%,transparent)}
.cn-composer textarea{border:0;background:transparent;color:inherit;resize:none;min-height:34px;max-height:200px;padding:5px 7px;font:inherit;line-height:1.7;outline:none;direction:auto;width:100%}
.cn-row{display:flex;align-items:center;gap:7px;flex-wrap:wrap}
.cn-row .sp{flex:1}
.cn-ibtn{border:0;background:transparent;cursor:pointer;border-radius:9px;padding:6px 9px;color:var(--mut);font-size:15px}
.cn-ibtn:hover{background:var(--accp);color:var(--acc)}
.cn-send{border:0;border-radius:10px;padding:8px 20px;background:var(--acc);color:#fff;font-weight:700;cursor:pointer}
.cn-send:disabled{opacity:.45;cursor:default}
.cn-send.stop{background:#ef4444}
.cn-atts{display:flex;flex-wrap:wrap;gap:6px}
.cn-att{display:flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:9px;padding:3px 4px 3px 8px;background:var(--side);font-size:12px}
.cn-att select{border:0;background:transparent;color:inherit;font-size:12px;max-width:110px}
.cn-att button{border:0;background:transparent;cursor:pointer;color:var(--mut)}
.cn-thread{display:flex;flex-direction:column;gap:18px;flex:1;min-height:0;overflow-y:auto;padding-bottom:8px}.cn-team{display:flex;flex-direction:column;gap:8px}.cn-team.fold{display:none}.cn-teambar{display:none;align-items:center;gap:8px;border:1px solid var(--line);border-radius:10px;padding:5px 10px;background:var(--bg);cursor:pointer;font-size:12.5px}.cn-teambar.show{display:flex}.cn-teambar:hover{border-color:var(--acc)}.cn-body{max-height:34vh;overflow-y:auto;padding-inline-end:4px;scrollbar-width:thin}.cn-card.wide .cn-body{max-height:62vh}
.cn-round{display:flex;flex-direction:column;gap:10px;animation:cnin .25s ease}
@keyframes cnin{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.cn-q{align-self:flex-start;max-width:92%;background:var(--accp);border-radius:14px 14px 4px 14px;padding:9px 13px;white-space:pre-wrap;overflow-wrap:anywhere}
.cn-qfiles{font-size:11.5px;color:var(--mut);margin-top:4px}
.cn-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,290px),1fr));gap:10px}
.cn-card{border:1px solid var(--line);border-top:4px solid var(--c);border-radius:12px;background:var(--bg);padding:10px 12px;min-width:0;display:flex;flex-direction:column;gap:7px}
.cn-card.judge{--c:var(--gold);background:color-mix(in srgb,var(--gold) 8%,var(--bg))}
.cn-ch{display:flex;align-items:center;gap:8px}
.cn-ch strong{flex:1}
.cn-badge{border-radius:99px;padding:2px 9px;font-size:11px;color:#fff;display:inline-flex;align-items:center;gap:5px}
.cn-badge.run::before{content:'';width:7px;height:7px;border-radius:50%;background:#fff;animation:cnp 1s infinite}
@keyframes cnp{50%{opacity:.25}}
.cn-live{margin:0;padding:8px;max-height:180px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:12px ui-monospace,monospace;background:var(--side);border-radius:8px;color:var(--mut);direction:auto}
.cn-md{overflow-wrap:anywhere;line-height:1.85}
.cn-md h4{margin:12px 0 4px;color:var(--c,var(--acc));font-size:13.5px}
.cn-md p{margin:3px 0}.cn-md ul{margin:3px 0;padding-inline-start:20px}
.cn-foot{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.cn-btn{border:1px solid var(--line);background:var(--bg);color:inherit;border-radius:9px;padding:5px 11px;cursor:pointer;font-size:12.5px}
.cn-btn:hover{border-color:var(--acc);color:var(--acc)}
.cn-err{color:#ef4444;font-size:12.5px}
.cn-prog{height:5px;border-radius:9px;background:var(--line);overflow:hidden}.cn-prog i{display:block;height:100%;background:linear-gradient(90deg,var(--acc),var(--gold));transition:width .5s}
.cn-prog-t{font-size:12px;color:var(--mut);display:flex;justify-content:space-between}
.cn-skel{height:54px;border-radius:8px;background:linear-gradient(100deg,var(--side) 30%,color-mix(in srgb,var(--side) 55%,var(--bg)) 50%,var(--side) 70%);background-size:200% 100%;animation:cnsk 1.3s linear infinite}
@keyframes cnsk{to{background-position:-200% 0}}
.cn-verdict{border-radius:10px;padding:11px 14px;background:color-mix(in srgb,var(--gold) 16%,var(--bg));border:1px solid color-mix(in srgb,var(--gold) 55%,var(--line));font-size:14.5px}
.cn-verdict .lab{font-size:11px;font-weight:700;color:var(--gold);letter-spacing:.3px;margin-bottom:3px}
.cn-more{border:0;background:transparent;color:var(--acc);cursor:pointer;font-size:12px;padding:2px 0;align-self:flex-start}
.cn-clamp{max-height:230px;overflow:hidden;-webkit-mask-image:linear-gradient(#000 78%,transparent);mask-image:linear-gradient(#000 78%,transparent)}
.cn-card.wide{grid-column:1/-1}
.cn-time{font-size:11px;color:var(--mut)}
.cn-presets{display:flex;gap:6px;flex-wrap:wrap;align-items:center}
.cn-pre{border:1px dashed var(--line);background:transparent;color:inherit;border-radius:99px;padding:3px 11px;font-size:12px;cursor:pointer}
.cn-pre:hover{border-color:var(--acc);color:var(--acc)}
.cn-details>summary{cursor:pointer;color:var(--acc);font-size:12.5px;margin:6px 0}
.cn-empty{border:1.5px dashed var(--line);border-radius:12px;padding:22px;text-align:center;color:var(--mut)}
`;
  function mountCouncil(container, opts) {
    if (!container) return;
    opts = opts || {};
    unmountCouncil(container);
    const host = container; host.replaceChildren(); host.className = (host.className + ' cn').trim(); host.dir = 'rtl'; councilRoot = host;
    const style = document.createElement('style'); style.textContent = CN_CSS; host.appendChild(style);
    const mk = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

    // ===== الرأس والفريق =====
    const top = mk('div', 'cn-top'); top.appendChild(mk('h3', '', '⚖ مجلس الوكلاء'));
    const histSel = mk('select', 'cn-btn'); histSel.title = 'مجالس سابقة'; top.appendChild(histSel);
    if (opts.onExit) { const x = mk('button', 'cn-btn', 'العودة للمحادثة'); x.type = 'button'; x.onclick = opts.onExit; top.appendChild(x); }
    const roster = mk('div', 'cn-roster'); const summary = mk('div', 'cn-sub');
    const presetBar = mk('div', 'cn-presets');
    const team = mk('div', 'cn-team'); team.append(roster, summary, presetBar);
    const teamBar = mk('div', 'cn-teambar'); teamBar.title = 'اضغط لإظهار الفريق'; teamBar.onclick = () => setFold(false);
    const setFold = f => { team.classList.toggle('fold', f); teamBar.classList.toggle('show', f); };
    host.append(top, teamBar, team);

    // ===== مربع الكتابة والمرفقات =====
    const composer = mk('div', 'cn-composer'); const attBar = mk('div', 'cn-atts'); attBar.hidden = true;
    const ta = mk('textarea'); ta.rows = 1; ta.dir = 'auto'; ta.placeholder = 'اسأل المجلس… (⌘↩ للإرسال)';
    const row = mk('div', 'cn-row'); const attachBtn = mk('button', 'cn-ibtn', '📎'); attachBtn.type = 'button'; attachBtn.title = 'إرفاق ملفات لوكيل أو للحكم';
    const fileIn = mk('input'); fileIn.type = 'file'; fileIn.multiple = true; fileIn.hidden = true;
    const limSel = mk('select', 'cn-btn'); limSel.title = 'بعد هذه المدة يحكم الرئيسي بما وصل ويكمل البطيء'; [[180, 'مهلة الحكم: ٣ د'], [300, 'مهلة الحكم: ٥ د'], [600, 'مهلة الحكم: ١٠ د'], [0, 'بلا مهلة']].forEach(([v, t]) => { const o = mk('option', '', t); o.value = v; limSel.appendChild(o); }); limSel.value = (() => { try { return localStorage.getItem('zajel_council_limit') || '300'; } catch (_) { return '300'; } })(); limSel.onchange = () => { try { localStorage.setItem('zajel_council_limit', limSel.value); } catch (_) {} };
    const ctx = mk('span', 'cn-sub'); const newBtn = mk('button', 'cn-btn', 'سؤال جديد'); newBtn.type = 'button'; newBtn.hidden = true;
    const sendBtn = mk('button', 'cn-send', 'أرسل'); sendBtn.type = 'button';
    row.append(attachBtn, fileIn, limSel, ctx, newBtn, mk('span', 'sp'), sendBtn);
    composer.append(attBar, ta, row); host.appendChild(composer);
    const thread = mk('div', 'cn-thread'); host.appendChild(thread);
    const empty = mk('div', 'cn-empty', 'اختر الوكلاء بالضغط على أسمائهم، وعيّن الحكم بالتاج، ثم اطرح سؤالك.'); thread.appendChild(empty);

    // ===== الحالة =====
    let available = [], selected = new Set(), main = '', atts = [], activeId = '', lastDoneId = '', parentId = '', boxes = {};
    try { const sv = JSON.parse(localStorage.getItem('zajel_council_sel') || '{}'); selected = new Set(Array.isArray(sv.ids) ? sv.ids : []); main = typeof sv.main === 'string' ? sv.main : ''; } catch (_) {}
    const persist = () => { try { localStorage.setItem('zajel_council_sel', JSON.stringify({ ids: [...selected], main })); } catch (_) {} };
    const loadPresets = () => { try { return JSON.parse(localStorage.getItem('zajel_council_presets') || '[]'); } catch (_) { return []; } };
    const savePresets = a => { try { localStorage.setItem('zajel_council_presets', JSON.stringify(a)); } catch (_) {} };
    const renderPresets = () => {
      presetBar.replaceChildren(); const list = loadPresets();
      list.forEach((p, i) => { const b = mk('button', 'cn-pre', '★ ' + p.name); b.type = 'button'; b.title = 'اضغط لتحميل الفريق (⇧+نقر للحذف)'; b.onclick = ev => { if (ev.shiftKey) { list.splice(i, 1); savePresets(list); renderPresets(); return; } selected = new Set(p.ids.filter(id => available.some(a => a.id === id))); main = available.some(a => a.id === p.main) ? p.main : ''; persist(); renderRoster(); renderAtts(); }; presetBar.appendChild(b); });
      const add = mk('button', 'cn-pre', '＋ احفظ هذا الفريق'); add.type = 'button'; add.onclick = () => { if (!selected.size) return; const name = prompt('اسم الفريق؟', 'فريقي'); if (!name) return; list.push({ name: name.slice(0, 24), ids: [...selected], main }); savePresets(list); renderPresets(); }; presetBar.appendChild(add);
    };
    const nameOf = id => available.find(a => a.id === id)?.name || id;
    const err = e => { const p = mk('div', 'cn-err', e?.message || 'تعذّر تنفيذ الطلب'); composer.after(p); setTimeout(() => p.remove(), 6000); };
    const grow = () => { ta.style.height = 'auto'; ta.style.height = Math.min(200, ta.scrollHeight) + 'px'; };
    ta.addEventListener('input', grow);

    let warmTimer = null;
    const warmUp = () => { clearTimeout(warmTimer); warmTimer = setTimeout(() => { const ids = [...new Set([...selected, ...(main ? [main] : [])])].filter(id => available.some(a => a.id === id)); if (ids.length && (!activeId || lastDoneId === activeId)) req('council/warm', { ids }).catch(() => {}); }, 1200); };
    const renderRoster = () => {
      roster.replaceChildren();
      available.forEach(a => {
        const chip = mk('div', 'cn-chip' + (selected.has(a.id) ? ' on' : '') + (main === a.id ? ' judge' : '')); chip.style.setProperty('--c', colorOf(a.id)); chip.title = 'اضغط لإضافته/إزالته من المفوَّضين';
        const av = mk('span', 'cn-av', a.name.trim().charAt(0).toUpperCase()); const nm = mk('span', '', a.name);
        const crown = mk('button', 'cn-crown', '👑'); crown.type = 'button'; crown.title = main === a.id ? 'هو الحكم (اضغط لإلغاء)' : 'اجعله الحكم';
        crown.onclick = ev => { ev.stopPropagation(); main = main === a.id ? '' : a.id; persist(); renderRoster(); renderAttTargets(); };
        chip.onclick = () => { selected.has(a.id) ? selected.delete(a.id) : selected.add(a.id); persist(); renderRoster(); renderAttTargets(); };
        chip.append(av, nm, crown); roster.appendChild(chip);
      });
      warmUp();
      const n = [...selected].filter(id => available.some(a => a.id === id)).length;
      teamBar.textContent = '▾ الفريق: ' + ([...selected].filter(id => available.some(a => a.id === id)).map(nameOf).join('، ') || 'لا أحد') + (main ? ' · الحكم: ' + nameOf(main) : '');
      summary.textContent = n ? `${n} مفوَّض يجيبون معًا` + (main ? ` · الحكم: ${nameOf(main)}` : ' · بلا حكم (إجابات فقط)') : 'لم تختر أي مفوَّض بعد';
    };

    // ===== المرفقات =====
    const targets = () => [['*', 'للجميع'], ...(main ? [['main', 'للحكم فقط']] : []), ...[...selected].filter(id => available.some(a => a.id === id)).map(id => [id, 'لـ ' + nameOf(id)])];
    function renderAttTargets() { renderAtts(); }
    function renderAtts() {
      attBar.replaceChildren(); attBar.hidden = !atts.length;
      atts.forEach((a, i) => {
        const chip = mk('div', 'cn-att'); chip.appendChild(mk('span', '', (a.status === 'up' ? '⏳ ' : a.status === 'err' ? '⚠ ' : '📄 ') + a.name));
        const sel = mk('select'); targets().forEach(([v, t]) => { const o = mk('option', '', t); o.value = v; sel.appendChild(o); });
        if (!targets().some(([v]) => v === a.to)) a.to = '*'; sel.value = a.to; sel.onchange = () => { a.to = sel.value; };
        const rm = mk('button', '', '✕'); rm.type = 'button'; rm.onclick = () => { atts.splice(i, 1); renderAtts(); };
        chip.append(sel, rm); attBar.appendChild(chip);
      });
    }
    const upload = async file => {
      const item = { name: file.name, status: 'up', path: '', to: '*' }; atts.push(item); renderAtts();
      try { const r = await (await fetch('/api/assistant/upload?name=' + encodeURIComponent(file.name), { method: 'POST', body: file })).json(); if (r && r.ok) { item.path = r.path; item.status = 'ok'; } else { item.status = 'err'; err(new Error(r?.error || 'فشل رفع الملف')); } }
      catch (e) { item.status = 'err'; err(e); }
      renderAtts(); sync();
    };
    attachBtn.onclick = () => fileIn.click();
    fileIn.onchange = () => { [...fileIn.files].forEach(upload); fileIn.value = ''; };
    ta.addEventListener('paste', ev => { const fs = [...(ev.clipboardData?.files || [])]; if (fs.length) { ev.preventDefault(); fs.forEach(upload); } });
    host.addEventListener('dragover', ev => ev.preventDefault());
    host.addEventListener('drop', ev => { if (ev.dataTransfer?.files?.length) { ev.preventDefault(); [...ev.dataTransfer.files].forEach(upload); } });

    // ===== عرض الجولة =====
    const badge = state => { const b = mk('span', 'cn-badge' + (['asking', 'starting'].includes(state) ? ' run' : ''), councilStateText[state] || 'في الانتظار'); b.style.background = councilStateColor[state] || '#737373'; return b; };
    const secs = t => { const n = Math.round(t); return n < 60 ? n + ' ث' : Math.floor(n / 60) + ' د ' + (n % 60) + ' ث'; };
    const card = (title, id, state, answer, live, judge, data) => {
      const c = mk('section', 'cn-card' + (judge ? ' judge' : '')); if (!judge) c.style.setProperty('--c', colorOf(id));
      const h = mk('div', 'cn-ch'); const av = mk('span', 'cn-av', judge ? '⚖' : String(title).trim().charAt(0).toUpperCase()); av.style.background = judge ? 'var(--gold)' : colorOf(id);
      h.append(av, mk('strong', '', title));
      if (data && data.sent_at) h.appendChild(mk('span', 'cn-time', secs(((data.finished_at || Date.now() / 1000) - data.sent_at))));
      h.appendChild(badge(state)); c.appendChild(h);
      if (answer) {
        let body;
        const m = judge ? answer.search(/^##\s*الحكم النهائي.*$/m) : -1;
        if (m !== -1) {
          const final = answer.slice(m).replace(/^##.*\n?/, '').trim(); const rest = answer.slice(0, m).trim();
          const v = mk('div', 'cn-verdict'); v.appendChild(mk('div', 'lab', 'الحكم النهائي')); const fb = mdBox(final); fb.classList.add('cn-body'); v.appendChild(fb); c.appendChild(v);
          if (rest) { const d = mk('details', 'cn-details'); d.appendChild(mk('summary', '', 'تفاصيل المقارنة: الاتفاق والاختلاف والترتيب')); const rb = mdBox(rest); rb.classList.add('cn-body'); d.appendChild(rb); c.appendChild(d); }
        } else {
          body = mdBox(answer); body.classList.add('cn-body'); c.appendChild(body);
        }
        const f = mk('div', 'cn-foot'); const cp = mk('button', 'cn-btn', 'نسخ'); cp.type = 'button'; cp.onclick = () => navigator.clipboard?.writeText(answer).then(() => { cp.textContent = 'تم النسخ ✓'; setTimeout(() => cp.textContent = 'نسخ', 1500); }).catch(() => {}); f.appendChild(cp);
        if (!judge) { const wd = mk('button', 'cn-btn', 'توسيع'); wd.type = 'button'; wd.onclick = () => { const on = c.classList.toggle('wide'); wd.textContent = on ? 'تصغير' : 'توسيع'; }; f.appendChild(wd); }
        c.appendChild(f);
      } else if (live) { const lv = mk('pre', 'cn-live cn-body', live); c.appendChild(lv); lv.scrollTop = lv.scrollHeight; }
      else if (['asking', 'starting', 'queued'].includes(state)) { c.appendChild(mk('div', 'cn-skel')); }
      return c;
    };
    const finished = r => ['done', 'stopped'].includes(r.phase);
    function renderRound(r) {
      let box = boxes[r.id];
      if (!box) { setFold(true); empty.remove(); box = boxes[r.id] = mk('section', 'cn-round'); thread.appendChild(box); setTimeout(() => box.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50); }
      box.replaceChildren();
      const q = mk('div', 'cn-q', r.question); if ((r.attachments || []).length) q.appendChild(mk('div', 'cn-qfiles', '📎 ' + r.attachments.map(a => a.name || a.path.split('/').pop()).join('، '))); box.appendChild(q);
      const st = r.agents || {}; const ev = r.eval || {};
      { const tot = (r.delegates || []).length, dn = (r.delegates || []).filter(id => ['done', 'done_raw', 'error', 'timeout', 'stopped'].includes((st[id] || {}).state)).length; const judged = !r.main || ['done', 'done_raw'].includes(ev.state); const all = tot + (r.main ? 1 : 0), cur = dn + (r.main && judged ? 1 : 0);
        if (!finished(r)) { const pg = mk('div'); const t = mk('div', 'cn-prog-t'); t.append(mk('span', '', dn < tot ? `${dn} من ${tot} أجابوا` : (r.main ? 'الحكم يكتب تقييمه…' : 'اكتملت الإجابات')), mk('span', '', Math.round(cur / all * 100) + '%')); const bar = mk('div', 'cn-prog'); const i = mk('i'); i.style.width = Math.round(cur / all * 100) + '%'; bar.appendChild(i); pg.append(t, bar); box.appendChild(pg); } }
      if (r.main) box.appendChild(card('حكم ' + (ev.name || nameOf(r.main)), r.main, ev.state, ev.answer || ev.error, ev.live, true, ev));
      const grid = mk('div', 'cn-grid'); (r.delegates || []).forEach(id => { const d = st[id] || {}; grid.appendChild(card(d.name || nameOf(id), id, d.state, d.answer || d.error, d.live, false, d)); }); box.appendChild(grid);
      const foot = mk('div', 'cn-foot');
      const anyAns = Object.values(st).some(x => x.answer);
      if (r.cut && r.pending > 0) { foot.appendChild(mk('span', 'cn-sub', 'حكم الرئيسي بما وصل؛ ما زال ' + r.pending + ' يكتب إجابته…')); }
      if (r.main && anyAns && ev.state !== 'done' && ev.state !== 'done_raw' && !finished(r)) { const b = mk('button', 'cn-btn', 'قيّم الآن بما وصل'); b.type = 'button'; b.onclick = async () => { try { await req('council/evaluate', { id: r.id }); poll(); } catch (e) { err(e); } }; foot.appendChild(b); }
      if (finished(r) && anyAns) { foot.appendChild(mk('span', 'cn-sub', 'حفظ كامل الجلسة:')); [['Word', 'docx'], ['PDF', 'pdf'], ['Markdown', 'md']].forEach(([t, f]) => { const b = mk('button', 'cn-btn', t); b.type = 'button'; b.onclick = async () => { try { const x = await req('council/export', { id: r.id, fmt: f }); b.textContent = '✓ ' + t; foot.querySelector('.cn-sub').textContent = 'حُفظ في: ' + x.path; } catch (e) { err(e); } }; foot.appendChild(b); }); }
      if (foot.childNodes.length) box.appendChild(foot);
    }
    // ===== الاستعلام الدوري =====
    async function poll() {
      if (councilRoot !== host || !host.isConnected || !activeId) return;
      try { const d = await req('council/status?id=' + encodeURIComponent(activeId)); if (!d.round) return; renderRound(d.round); if (finished(d.round) && !(d.round.pending > 0)) { clearInterval(councilTimer); councilTimer = null; lastDoneId = d.round.id; sync(); } }
      catch (e) { err(e); }
    }
    function sync() {
      const busy = activeId && lastDoneId !== activeId;
      sendBtn.textContent = busy ? 'إيقاف' : (lastDoneId ? 'متابعة' : 'أرسل'); sendBtn.classList.toggle('stop', !!busy);
      sendBtn.disabled = !busy && (!ta.value.trim() || !selected.size || atts.some(a => a.status === 'up'));
      newBtn.hidden = !lastDoneId || busy; ctx.textContent = lastDoneId && !busy ? 'متابعة على الجولة السابقة (الوكلاء يتذكرون الحديث)' : '';
    }
    ta.addEventListener('input', sync);
    ta.addEventListener('keydown', ev => { if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) { ev.preventDefault(); if (!sendBtn.disabled && sendBtn.textContent !== 'إيقاف') sendBtn.click(); } });
    newBtn.onclick = () => { lastDoneId = ''; parentId = ''; sync(); ta.focus(); };
    sendBtn.onclick = async () => {
      if (activeId && lastDoneId !== activeId) { try { await req('council/stop', { id: activeId }); poll(); } catch (e) { err(e); } return; }
      const ids = [...selected].filter(id => available.some(a => a.id === id));
      if (!ta.value.trim() || !ids.length) { err(new Error('اكتب سؤالًا واختر مفوَّضًا واحدًا على الأقل')); return; }
      const files = atts.filter(a => a.status === 'ok').map(a => ({ path: a.path, name: a.name, to: a.to }));
      try {
        const d = await req('council/send', { ids, text: ta.value, main, evaluate: true, attachments: files, parent: lastDoneId || '', limit: Number(limSel.value) });
        setFold(true); activeId = d.id; lastDoneId = ''; ta.value = ''; atts = []; renderAtts(); grow(); sync();
        try { window.ZajelTerminalUI?.showAgents?.(main && !ids.includes(main) ? [...ids, main] : ids); } catch (_) {}
        clearInterval(councilTimer); councilTimer = setInterval(poll, 1500); poll();
      } catch (e) { err(e); }
    };
    // ===== المجالس السابقة =====
    const loadHistory = async () => {
      try { const d = await req('council/history'); histSel.replaceChildren(); const o0 = mk('option', '', 'مجالس سابقة…'); o0.value = ''; histSel.appendChild(o0); (d.rounds || []).forEach(r => { const o = mk('option', '', (r.question || 'مجلس').slice(0, 60)); o.value = r.id; histSel.appendChild(o); }); histSel.hidden = !(d.rounds || []).length; } catch (_) { histSel.hidden = true; }
    };
    histSel.onchange = async () => { if (!histSel.value) return; activeId = histSel.value; lastDoneId = ''; thread.replaceChildren(); boxes = {}; await poll(); histSel.value = ''; if (!councilTimer) councilTimer = setInterval(poll, 1500); };
    req('list').then(d => { available = (d.agents || []).filter(a => a.cmd && a.installed === true); selected = new Set([...selected].filter(id => available.some(a => a.id === id))); if (main && !available.some(a => a.id === main)) main = ''; renderRoster(); renderPresets(); renderAtts(); loadHistory(); sync(); }).catch(err);
    councilApi = { ask: t => { ta.value = t; sync(); return sendBtn.onclick(); } };
  }
  function unmountCouncil(container){if(councilRoot&&(!container||councilRoot===container||container.contains(councilRoot))){clearInterval(councilTimer);councilTimer=null;councilRoot=null;councilApi=null;councilRoundId='';}}
  function activate(el){if(!el)return;if(root&&root.parentNode===el&&listTimer)return;const host=document.createElement('div');el.replaceChildren(host);root=host;hist=0;builtLayout=0;build();builtLayout=layout;refreshList();clearInterval(listTimer);listTimer=setInterval(refreshList,2000);clearInterval(screenTimer);screenTimer=setInterval(()=>refreshScreens(false),500);refreshScreens(true);}
  function deactivate(){clearInterval(listTimer);clearInterval(screenTimer);listTimer=screenTimer=null;resizeObserver?.disconnect();resizeObserver=null;unmountCouncil();root=null;}

  // نافذة الطرفية المستقلة: أزرار التحكم في أقصى اليسار مثل نوافذ macOS
  let win = null;
  function toggleWindow(tab){
    if (win && win.el.isConnected) { if (win.el.hidden) { win.el.hidden = false; win.show(win.tab); } else { closeWindow(); } return; }
    const GEO = 'zajel_term_win_geo';
    const el = document.createElement('div'); el.id = 'zajel-term-window'; el.dir = 'ltr';
    let geo = null; try { geo = JSON.parse(localStorage.getItem(GEO) || 'null'); } catch (_) {}
    const w = Math.min(1100, innerWidth - 40), h = Math.min(720, innerHeight - 60);
    geo = geo || { x: Math.max(10, (innerWidth - w) / 2), y: 30, w, h };
    el.style.cssText = `position:fixed;left:${geo.x}px;top:${geo.y}px;width:${geo.w}px;height:${geo.h}px;min-width:420px;min-height:280px;z-index:10002;display:flex;flex-direction:column;background:var(--bg);color:var(--fg);border:1px solid var(--line);border-radius:12px;box-shadow:0 12px 48px #0006;overflow:hidden;resize:both`;
    const style = document.createElement('style');
    style.textContent = '#zajel-term-window .tw-head{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--side);border-bottom:1px solid var(--line);cursor:move;user-select:none;touch-action:none}#zajel-term-window .tw-lights{display:flex;gap:8px}#zajel-term-window .tw-light{width:13px;height:13px;border-radius:50%;border:0;padding:0;cursor:pointer;font-size:9px;line-height:13px;color:transparent}#zajel-term-window .tw-lights:hover .tw-light{color:#0009}#zajel-term-window .tw-title{flex:1;text-align:center;font-weight:600;font-size:13px}#zajel-term-window .tw-tabs{display:flex;gap:4px;padding:6px 10px;border-bottom:1px solid var(--line);direction:rtl}#zajel-term-window .tw-tabs .btn.pri{font-weight:700}#zajel-term-window .tw-body{flex:1;min-height:0;display:flex;flex-direction:column;padding:10px;direction:rtl;overflow:hidden}';
    const head = document.createElement('div'); head.className = 'tw-head';
    const lights = document.createElement('div'); lights.className = 'tw-lights';
    const mk = (c, t, sym) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'tw-light'; b.style.background = c; b.title = t; b.setAttribute('aria-label', t); b.textContent = sym; return b; };
    const bClose = mk('#ff5f57', 'إغلاق', '×'), bMin = mk('#febc2e', 'تصغير', '–'), bMax = mk('#28c840', 'تكبير', '+');
    lights.append(bClose, bMin, bMax);
    const title = document.createElement('div'); title.className = 'tw-title'; title.textContent = 'الطرفية ومجلس الوكلاء';
    head.append(lights, title);
    const tabs = document.createElement('div'); tabs.className = 'tw-tabs';
    const body = document.createElement('div'); body.className = 'tw-body';
    const tabBtns = {};
    [['terminals', 'الطرفيات'], ['council', 'مجلس الوكلاء']].forEach(([k, t]) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn'; b.textContent = t; b.onclick = () => win.show(k); tabs.appendChild(b); tabBtns[k] = b; });
    el.append(style, head, tabs, body);
    document.body.appendChild(el);
    const save = () => { try { localStorage.setItem(GEO, JSON.stringify({ x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight })); } catch (_) {} };
    let minimized = false, maximized = false, prev = null;
    bClose.onclick = closeWindow;
    bMin.onclick = () => { minimized = !minimized; tabs.hidden = body.hidden = minimized; if (minimized) { prev = el.style.height; el.style.height = 'auto'; el.style.minHeight = '0'; el.style.resize = 'none'; } else { el.style.height = prev || geo.h + 'px'; el.style.minHeight = '280px'; el.style.resize = 'both'; } };
    bMax.onclick = () => { maximized = !maximized; if (maximized) { save(); prev = [el.style.left, el.style.top, el.style.width, el.style.height]; Object.assign(el.style, { left: '8px', top: '8px', width: (innerWidth - 16) + 'px', height: (innerHeight - 16) + 'px' }); } else if (prev) { [el.style.left, el.style.top, el.style.width, el.style.height] = prev; } };
    head.ondblclick = ev => { if (!ev.target.closest('button')) bMax.onclick(); };
    head.onpointerdown = ev => {
      if (ev.target.closest('button') || maximized) return; ev.preventDefault();
      const sx = ev.clientX, sy = ev.clientY, ox = el.offsetLeft, oy = el.offsetTop; head.setPointerCapture(ev.pointerId);
      head.onpointermove = e2 => { el.style.left = Math.max(0, Math.min(innerWidth - 80, ox + e2.clientX - sx)) + 'px'; el.style.top = Math.max(0, Math.min(innerHeight - 40, oy + e2.clientY - sy)) + 'px'; };
      const end = e3 => { try { head.releasePointerCapture(e3.pointerId); } catch (_) {} head.onpointermove = head.onpointerup = head.onpointercancel = null; save(); };
      head.onpointerup = end; head.onpointercancel = end;
    };
    new ResizeObserver(() => { if (!maximized && !minimized) save(); }).observe(el);
    win = { el, tab: 'terminals', show(k) {
      win.tab = k; Object.entries(tabBtns).forEach(([n, b]) => b.classList.toggle('pri', n === k));
      deactivate(); body.replaceChildren();
      const host = document.createElement('div'); host.style.cssText = 'flex:1;min-height:0;display:flex;flex-direction:column'; body.appendChild(host);
      if (k === 'council') mountCouncil(host); else activate(host);
    } };
    win.show(tab || 'terminals');
  }
  function closeWindow(){ if (!win) return; deactivate(); win.el.remove(); win = null; }
  window.ZajelTerminalUI={showAgents,activate,deactivate,mountCouncil,unmountCouncil,toggleWindow,closeWindow,councilAsk:t=>councilApi?councilApi.ask(t):Promise.reject(new Error('المجلس غير مفتوح'))};
})();
