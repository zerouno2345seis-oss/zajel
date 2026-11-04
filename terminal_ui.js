(() => {
  'use strict';
  if (window.ZajelTerminalUI) return;
  let councilApi = null, root = null, listTimer = null, screenTimer = null, resizeObserver = null, councilRoot = null, councilTimer = null, councilRoundId = '', councilPanel = null, councilFolded = true;
  let activeSlot = 0, agents = [], slots = [], layout = 1, notify = false, hist = 1500, listBusy = false, builtLayout = 0, sendChain = Promise.resolve();
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const req = async (path, body) => {
    const url = '/api/term/' + path;
    try {
      if (typeof window.api === 'function') return await window.api(url, body);
      const response = await fetch(url, body ? { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) } : {});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      return await response.json();
    } catch (e) {
      if (/failed to fetch|networkerror|load failed/i.test(String(e && e.message))) throw new Error('انقطع الاتصال بزاجل؛ يعيد المحاولة عند عودته.');
      throw e;
    }
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
    const renderControls=()=>{controls.replaceChildren();[1,2,3,4,5].forEach(n=>{const b=document.createElement('button');b.className='btn'+(layout===n?' pri':'');b.textContent=String(n);b.title='عدد النوافذ';b.onclick=()=>{layout=n;build();refreshList();};controls.appendChild(b);});const down=document.createElement('button');down.className='btn';down.textContent='انتقل إلى الأسفل';down.onclick=()=>viewport.querySelectorAll('pre').forEach(x=>x.scrollTop=x.scrollHeight);controls.appendChild(down);const tg=document.createElement('button');tg.className='btn';tg.textContent='الوكلاء ▾';tg.onclick=()=>{cards.classList.toggle('open');tg.textContent=cards.classList.contains('open')?'الوكلاء ▴':'الوكلاء ▾';};controls.insertBefore(tg,controls.firstChild);const longer=document.createElement('button');longer.className='btn';longer.textContent=hist>1500?'سجلّ عادي':'سجلّ أطول';longer.onclick=()=>{hist=hist>1500?1500:5000;longer.textContent=hist>1500?'سجلّ عادي':'سجلّ أطول';refreshScreens(true);};controls.appendChild(longer);const dirb=document.createElement('button');dirb.className='btn';const dirTxt=()=>root.dataset.dir==='ltr'?'الاتجاه: يسار ثابت':'الاتجاه: تلقائي (عربي يمينًا)';root.dataset.dir=(()=>{try{return localStorage.getItem('zajel_term_dir')||'auto';}catch(_){return 'auto';}})();dirb.textContent=dirTxt();dirb.onclick=()=>{root.dataset.dir=root.dataset.dir==='ltr'?'auto':'ltr';try{localStorage.setItem('zajel_term_dir',root.dataset.dir);}catch(_){}dirb.textContent=dirTxt();};controls.appendChild(dirb);const lab=document.createElement('label');lab.className='as-terminal-notify';const cb=document.createElement('input');cb.type='checkbox';cb.checked=notify;cb.onchange=()=>{notify=cb.checked;req('notify',{on:notify}).catch(()=>{});};lab.append(cb,document.createTextNode('إشعار تيليجرام عند انتظار الوكيل/انتهائه'));controls.appendChild(lab);};
    renderControls();
    while(slots.length<layout)slots.push({id:agents[slots.length]?.id||'',hash:'',pre:null,select:null,card:null});slots=slots.slice(0,layout);
    slots.forEach((slot,index)=>{const card=document.createElement('section');card.className='as-terminal-window';slot.card=card;const head=document.createElement('div');head.className='as-terminal-window-head';const select=document.createElement('select');select.setAttribute('aria-label','اختر الوكيل');agents.forEach(a=>{const o=document.createElement('option');o.value=a.id;o.textContent=a.name+' · '+a.label;select.appendChild(o);});if(slot.id)select.value=slot.id;if(!slot.id&&agents[0])slot.id=agents[0].id;select.onchange=()=>{slot.id=select.value;slot.hash='';refreshScreens(true);};slot.select=select;head.appendChild(select);const fsb=document.createElement('button');fsb.type='button';fsb.className='btn as-terminal-fs';fsb.textContent='⛶';fsb.title='ملء الشاشة / تصغير';fsb.setAttribute('aria-label','ملء الشاشة');fsb.onclick=()=>{const on=card.classList.toggle('is-full');fsb.textContent=on?'🗗':'⛶';fsb.title=on?'تصغير':'ملء الشاشة';setTimeout(()=>{resizeSlot(slot);slot.pre.scrollTop=slot.pre.scrollHeight;slot.input&&slot.input.focus({preventScroll:true});},60);};head.appendChild(fsb);const pre=document.createElement('pre');pre.dir='ltr';pre.tabIndex=0;pre.className='as-terminal-screen';pre.setAttribute('aria-label','شاشة الطرفية · اضغط للكتابة');const ta=document.createElement('textarea');ta.setAttribute('aria-label','إدخال الطرفية');ta.setAttribute('autocapitalize','off');ta.setAttribute('autocomplete','off');ta.setAttribute('autocorrect','off');ta.spellcheck=false;ta.style.cssText='position:absolute;opacity:0;width:2px;height:2px;left:0;top:0;border:0;padding:0;resize:none;font-size:16px';slot.input=ta;const msg=document.createElement('small');msg.className='as-terminal-msg';slot.msg=msg;head.appendChild(msg);slot.pre=pre;pre.addEventListener('focus',()=>{activeSlot=index;root&&root.querySelectorAll('.as-terminal-window').forEach((w,k)=>w.classList.toggle('is-active',k===index));});card.style.position='relative';card.append(head,pre,ta);viewport.appendChild(card);wireKeys(slot);});
    const agentStyle=document.createElement('style');agentStyle.textContent='.as-council-terminal-panel{max-height:42vh;overflow:auto;min-height:0;border:1px solid var(--line);border-radius:9px;padding:7px}.as-terminal-ui{display:flex;flex-direction:column;gap:8px;min-height:0;flex:1;height:100%}.as-terminal{display:grid;grid-template-columns:232px minmax(0,1fr);grid-template-rows:auto minmax(0,1fr);gap:10px;flex:1;min-height:0}.as-terminal-agents{grid-row:1/3;grid-column:1;display:flex;flex-direction:column;gap:7px;overflow-y:auto;padding:2px;min-height:0}.as-terminal-controls{grid-column:2;grid-row:1;display:flex;gap:6px;align-items:center;flex-wrap:wrap}.as-terminal-grid{grid-column:2;grid-row:2;display:grid;gap:8px;min-height:0;min-width:0;grid-template-columns:1fr;grid-auto-rows:minmax(0,1fr)}.as-terminal-ui[data-layout="2"] .as-terminal-grid{grid-template-rows:repeat(2,minmax(0,1fr))}.as-terminal-ui[data-layout="4"] .as-terminal-grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-template-rows:repeat(2,minmax(0,1fr))}.as-terminal-toolbar{display:none}.as-terminal-agent{border:1px solid var(--line);border-radius:10px;padding:8px 9px;background:var(--bg);cursor:pointer}.as-terminal-agent.is-shown{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc) inset}.as-terminal-agent-head{display:flex;align-items:center;gap:6px;font-weight:600}.as-terminal-dot{width:9px;height:9px;border-radius:50%;display:inline-block;flex:none}.as-terminal-label{font-size:11px;color:var(--mut);margin:3px 0 6px}.as-terminal-actions{display:flex;gap:5px;flex-wrap:wrap;align-items:center}.as-terminal-actions .btn{padding:3px 9px;font-size:11.5px}.as-terminal-notify{display:flex;gap:5px;align-items:center;font-size:11.5px;margin-inline-start:auto}.as-terminal-window{min-width:0;min-height:0;display:flex;flex-direction:column;border:1px solid var(--line);border-radius:9px;overflow:hidden}.as-terminal-window.is-active{border-color:var(--acc)}.as-terminal-window-head{padding:4px;background:var(--side);flex:none;display:flex;flex-wrap:wrap;gap:4px;align-items:center}.as-terminal-window-head select{max-width:100%;flex:1;min-width:0}.as-terminal-fs{padding:2px 9px;font-size:14px;line-height:1.2}.as-terminal-window.is-full{position:fixed!important;inset:0;z-index:99999;border-radius:0;background:var(--bg)}.as-terminal-window.is-full .as-terminal-screen{font-size:14px}.as-terminal-screen{margin:0;padding:8px 10px;overflow:auto;white-space:pre;direction:ltr;unicode-bidi:plaintext;text-align:start;background:#101318;color:#e5e7eb;font:12.5px/1.4 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;flex:1;min-height:0;outline:none;tab-size:8}.as-terminal-ui[data-dir="ltr"] .as-terminal-screen{unicode-bidi:normal;text-align:left}.as-terminal-window:focus-within{border-color:var(--acc);box-shadow:0 0 0 1px var(--acc)}.as-terminal-msg{display:block;font-size:11px;min-height:14px;padding:2px 4px;color:var(--mut)}.as-terminal-screen:focus{box-shadow:inset 0 0 0 1px var(--acc)}@media(max-width:860px){.as-terminal{grid-template-columns:minmax(0,1fr);grid-template-rows:auto auto minmax(0,1fr)}.as-terminal-agents{grid-row:1;grid-column:1;flex-direction:row;overflow-x:auto;overflow-y:hidden}.as-terminal-agent{flex:0 0 150px}.as-terminal-controls{grid-column:1;grid-row:2}.as-terminal-grid{grid-column:1;grid-row:3}.as-terminal-ui[data-layout="4"] .as-terminal-grid,.as-terminal-ui[data-layout="2"] .as-terminal-grid{grid-template-columns:1fr;grid-template-rows:none;grid-auto-rows:minmax(180px,1fr);overflow-y:auto}}.as-terminal{grid-template-columns:minmax(0,1fr)!important;grid-template-rows:auto auto minmax(0,1fr)!important;gap:6px}.as-terminal-agents{grid-row:1!important;grid-column:1!important;flex-direction:row!important;flex-wrap:wrap;overflow:visible!important}.as-terminal-agent{padding:3px 9px!important;flex:none!important;border-radius:99px}.as-terminal-agent .as-terminal-label,.as-terminal-agent .as-terminal-actions{display:none}.as-terminal-agents.open .as-terminal-agent{flex:0 0 150px!important;border-radius:10px;padding:8px 9px!important}.as-terminal-agents.open .as-terminal-label{display:block}.as-terminal-agents.open .as-terminal-actions{display:flex}.as-terminal-controls{grid-column:1!important;grid-row:2!important}.as-terminal-grid{grid-column:1!important;grid-row:3!important}.as-terminal-ui[data-layout="2"] .as-terminal-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-template-rows:minmax(0,1fr)!important}.as-terminal-ui[data-layout="3"] .as-terminal-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important;grid-template-rows:minmax(0,1fr)!important}.as-terminal-ui[data-layout="4"] .as-terminal-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important;grid-template-rows:repeat(2,minmax(0,1fr))!important}.as-terminal-ui[data-layout="5"] .as-terminal-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important;grid-template-rows:repeat(2,minmax(0,1fr))!important}.as-terminal-screen{font-size:12px}@media(max-width:860px){.as-terminal-ui[data-layout="2"] .as-terminal-grid,.as-terminal-ui[data-layout="3"] .as-terminal-grid,.as-terminal-ui[data-layout="4"] .as-terminal-grid,.as-terminal-ui[data-layout="5"] .as-terminal-grid{grid-template-columns:1fr!important;grid-template-rows:none!important;grid-auto-rows:minmax(220px,1fr);overflow-y:auto}}';root.appendChild(agentStyle);root.dataset.layout=String(layout);
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
  const councilStateText = { restarting: 'يُعاد تشغيله', queued: 'في الانتظار', starting: 'يبدأ', asking: 'يجيب', reviewing: 'يراجع وينقد', done: 'انتهى', done_raw: 'انتهى بلا علامات', timeout: 'انتهت المهلة', error: 'خطأ', stopped: 'متوقف' };
  const councilStateColor = { restarting: '#a855f7', queued: '#a3a3a3', starting: '#eab308', asking: '#3b82f6', reviewing: '#8b5cf6', done: '#22c55e', done_raw: '#16a34a', timeout: '#f97316', error: '#ef4444', stopped: '#737373' };
  function councilButton(label, action, primary) { const b = document.createElement('button'); b.type = 'button'; b.className = 'btn' + (primary ? ' pri' : ''); b.textContent = label; b.onclick = action; return b; }
  const agentColors = { claude: '#d97757', codex: '#10a37f', agy: '#3b82f6', hermes: '#8b5cf6', opencode: '#64748b', pi: '#ec4899' };
  const colorOf = id => agentColors[id] || '#64748b';
  const agentSpeed = { claude: 1.0, codex: 1.2, hermes: 0.9, agy: 2.4, opencode: 1.0, pi: 1.0 };

  function formatClaimsTable(text) {
    if (!text) return null;
    const lines = text.split('\n').map(l => l.trim()).filter(l => l.startsWith('|'));
    if (lines.length < 2) return null;
    const parseRow = ln => ln.split('|').slice(1, -1).map(c => c.trim());
    const headerCells = parseRow(lines[0]);
    if (!headerCells.length) return null;
    const table = document.createElement('table');
    table.className = 'claims';
    const thead = document.createElement('thead');
    const trh = document.createElement('tr');
    headerCells.forEach((c, idx) => {
      const th = document.createElement('th');
      th.textContent = c;
      if (idx > 0 && idx < headerCells.length - 1) th.className = 'c';
      trh.appendChild(th);
    });
    thead.appendChild(trh);
    table.appendChild(thead);

    const tbody = document.createElement('tbody');
    const dataLines = lines.slice(1).filter(l => !/^[|\s-:]+$/.test(l));
    dataLines.forEach(ln => {
      const rowCells = parseRow(ln);
      const tr = document.createElement('tr');
      rowCells.forEach((c, idx) => {
        const td = document.createElement('td');
        if (idx > 0 && idx < rowCells.length - 1) {
          td.className = 'c';
          if (c.includes('✓')) td.innerHTML = '<span class="yes">✓</span>';
          else if (c.includes('✗')) td.innerHTML = '<span class="no">✗</span>';
          else if (c === '—' || c === '-' || !c) td.innerHTML = '<span class="na">—</span>';
          else td.textContent = c;
        } else if (idx === rowCells.length - 1) {
          if (c.includes('✓')) td.innerHTML = `<span class="yes">${esc(c)}</span>`;
          else if (c.includes('✗')) td.innerHTML = `<span class="no">${esc(c)}</span>`;
          else td.textContent = c;
        } else {
          td.textContent = c;
        }
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    return table;
  }

  function parseVerdict(text) {
    if (!text || typeof text !== 'string') return null;
    const re = /^##\s+(.+)$/gm;
    const sections = {};
    const matches = [];
    let m;
    while ((m = re.exec(text)) !== null) {
      matches.push({ title: m[1].trim(), index: m.index, headerLen: m[0].length });
    }
    if (!matches.length) return null;
    for (let i = 0; i < matches.length; i++) {
      const cur = matches[i];
      const start = cur.index + cur.headerLen;
      const end = (i + 1 < matches.length) ? matches[i + 1].index : text.length;
      sections[cur.title] = text.slice(start, end).trim();
    }
    const findSec = (...keys) => {
      for (const k of Object.keys(sections)) {
        for (const key of keys) {
          if (k.includes(key)) return sections[k];
        }
      }
      return '';
    };

    let confidence = '';
    let summary = '';
    const rawSum = findSec('الخلاصة');
    if (rawSum) {
      const lines = rawSum.split('\n').map(l => l.trim()).filter(Boolean);
      for (const l of lines) {
        const cm = l.match(/الثقة\s*:\s*([^\n]+)/);
        if (cm) {
          confidence = cm[1].replace(/[*_#]/g, '').trim();
        } else if (!summary) {
          summary = l.replace(/^[-*•]\s*/, '').trim();
        }
      }
      if (!summary && lines.length) summary = lines[0];
    }
    if (!confidence) {
      const cm = text.match(/الثقة\s*:\s*([^\n]+)/);
      if (cm) confidence = cm[1].replace(/[*_#]/g, '').trim();
    }

    const finalVerdict = findSec('الحكم النهائي') || text;
    const agreement = findSec('الاتفاق');
    const difference = findSec('الاختلاف', 'الخلاف');
    const claimsMap = findSec('خريطة الأقوال');
    const sources = findSec('المصادر');
    const ranking = findSec('الترتيب');

    return {
      confidence,
      summary,
      finalVerdict,
      panes: {
        agree: agreement,
        diff: difference,
        map: claimsMap,
        src: sources,
        rank: ranking
      }
    };
  }

  const mdBox = text => {
    const box = document.createElement('div'); box.className = 'cn-md'; box.dir = 'auto'; let ul = null;
    const fill = (el, t) => t.split(/(\*\*[^*]+\*\*)/).forEach(part => {
      if (/^\*\*[^*]+\*\*$/.test(part)) { const b = document.createElement('b'); b.textContent = part.slice(2, -2); el.appendChild(b); } else el.appendChild(document.createTextNode(part));
    });
    const lines = String(text || '').split('\n');
    let tblLines = [];
    const flushTable = () => {
      if (!tblLines.length) return;
      const tbl = formatClaimsTable(tblLines.join('\n'));
      if (tbl) box.appendChild(tbl);
      else tblLines.forEach(ln => { const p = document.createElement('p'); fill(p, ln); box.appendChild(p); });
      tblLines = [];
    };
    lines.forEach(ln => {
      if (ln.trim().startsWith('|')) {
        ul = null;
        tblLines.push(ln);
        return;
      }
      flushTable();
      const h = ln.match(/^(#{1,4})\s+(.*)/), b = ln.match(/^\s*(?:[-*•]|\d+[.)])\s+(.*)/);
      if (!b) ul = null;
      if (h) { const e = document.createElement('h4'); fill(e, h[2]); box.appendChild(e); }
      else if (b) { if (!ul) { ul = document.createElement('ul'); box.appendChild(ul); } const li = document.createElement('li'); fill(li, b[1]); ul.appendChild(li); }
      else if (ln.trim()) { const p = document.createElement('p'); fill(p, ln); box.appendChild(p); }
    });
    flushTable();
    return box;
  };

  const CN_CSS = `
.cn{
  /* ألوان زاجل نفسها (لا يُعرَّف متغير بنفسه: المتصفح يُسقط التعريف الدائري فتختفي الألوان) */
  --acc-soft:var(--accp,#e6eeff);
  --card:var(--panel,#ffffff);
  --txt:var(--ink,#1b1f27);
  --gold:#c08a00;
  --gold-soft:#fff5d6;
  --ok:#16a34a;
  --ok-soft:#e3f6e9;
  --bad:var(--err,#dc2626);
  --bad-soft:#fde8e8;
  --warn:#d97706;
  --warn-soft:var(--warnp,#fff1dc);
  --c-claude:#d97757;
  --c-codex:#10a37f;
  --c-hermes:#8b5cf6;
  --c-agy:#3b82f6;
  --c-opencode:#64748b;
  --c-pi:#ec4899;
  display:flex;flex-direction:column;gap:10px;min-width:0;width:100%;min-height:0;flex:1;height:100%;color:var(--txt);background:var(--bg);font-size:13.5px;direction:rtl;
}
@media (prefers-color-scheme:dark){
  .cn{--gold:#f0b429;--gold-soft:#3a2f12;--ok:#4ade80;--ok-soft:#143221;--bad-soft:#3b1717;--warn:#fbbf24;}
}
.cn *{box-sizing:border-box}
.cn-top{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.cn-top h3{margin:0;font-size:16px;font-weight:700}
.cn-top .sp{flex:1}
/* صفّان من خانات مربّعة متلاصقة بلا فراغات، بانحناء خفيف جدًا */
.mbar{display:flex;flex-direction:column;gap:6px}
.brow{display:flex;min-width:0}
.roster,.tiles{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);gap:0;width:100%;min-width:0}
.roster{grid-auto-columns:minmax(104px,1fr);overflow-x:auto;scrollbar-width:thin}
.roster .chip .nm{overflow:visible;text-overflow:clip}
.opt.locked .tile{opacity:.55!important}
.brow.cfg{display:grid;grid-template-columns:3fr 4fr;gap:6px}
.msel{display:none}
.chip,.tile{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;min-height:58px;padding:6px 4px;
  border:1px solid var(--line);margin-inline-start:-1px;border-radius:0;background:var(--card);color:var(--txt);cursor:pointer;user-select:none;
  font:inherit;font-size:12px;line-height:1.25;text-align:center;transition:background .15s,box-shadow .15s;min-width:0}
.roster>:first-child,.tiles>:first-child,.tiles>:first-child .tile{border-start-start-radius:4px;border-end-start-radius:4px;margin-inline-start:0}
.roster>:last-child,.tiles>:last-child,.tiles>:last-child .tile{border-start-end-radius:4px;border-end-end-radius:4px}
.chip:hover,.tile:hover{background:var(--side)}
.chip.on{background:color-mix(in srgb,var(--c,var(--acc)) 14%,var(--card));box-shadow:inset 0 -3px 0 var(--c,var(--acc));z-index:1}
.chip.judge{box-shadow:inset 0 -3px 0 var(--c,var(--acc)),inset 0 0 0 2px var(--gold);z-index:2}
.chip.off{opacity:.62}
.cn .chip,.cn .chip .nm{color:var(--txt)!important;text-shadow:none!important}
.cn .chip.on{background:color-mix(in srgb,var(--c,var(--acc)) 22%,var(--card))!important}
.cn .chip.on .nm{font-weight:700}
.cn .chip.off .nm{text-decoration:line-through;text-decoration-thickness:1px}
.cn .tile,.cn .tile .tl,.cn .tile .ic{color:var(--txt)!important}
.cn .tile.on,.cn .opt input:checked+.tile{background:color-mix(in srgb,var(--acc) 24%,var(--card))!important;box-shadow:inset 0 -3px 0 var(--acc)!important}
.cn .tile.on .tl,.cn .opt input:checked+.tile .tl{font-weight:700;color:var(--txt)!important}
.cn .tile .tm,.cn .tile.on .tm{color:var(--mut)!important}
.chip .av{width:24px;height:24px;border-radius:4px;display:grid;place-items:center;color:#fff;font-size:12px;font-weight:700;background:var(--c,#64748b)}
.chip .nm{max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-weight:600}
.chip .dot{position:absolute;top:6px;inset-inline-start:6px;width:7px;height:7px;border-radius:50%}
.dot.ready{background:var(--ok)}
.dot.slow{background:var(--warn)}
.dot.off{background:var(--bad)}
.chip .crown{position:absolute;top:2px;inset-inline-end:3px;border:0;background:none;cursor:pointer;opacity:.25;font-size:12px;padding:0;filter:grayscale(1)}
.chip.judge .crown,.chip .crown:hover{opacity:1;filter:none}
.tile .ic{font-size:16px;line-height:1}
.tile .tl{font-weight:600}
.tile .tm{font-size:10.5px;color:var(--mut)}
.tile.on,.opt input:checked+.tile{background:var(--acc-soft);color:var(--acc);box-shadow:inset 0 -3px 0 var(--acc);z-index:1}
.tile.on .tm{color:var(--acc)}
.opt{display:flex;min-width:0;cursor:pointer}
.opt .tile{flex:1}
.opt input{display:none}
.opt.locked .tile{opacity:.4;cursor:not-allowed}
.opts{animation:slide .3s}
@keyframes slide{from{opacity:0;transform:translateY(-6px)}to{opacity:1}}
@media(max-width:520px){.brow.cfg{grid-template-columns:1fr}}

/* مضغوط: خانات بسطر واحد، ومربع كتابة بإطار واضح يُكبَّر بالسحب */
.chip,.tile{flex-direction:row;min-height:28px;padding:2px 5px;gap:4px;font-size:11.5px}
.chip .nm,.tile .tl{font-weight:500}
.mbar{gap:4px}
.brow.cfg{gap:4px}
.chip .av{width:16px;height:16px;font-size:10px;border-radius:3px}
.tile .tm{display:none}
.tile .ic{font-size:12px}
.chip .dot{top:3px;inset-inline-start:3px}
.chip .crown{top:1px}
.composer{border:1.5px solid color-mix(in srgb,var(--mut) 55%,transparent)!important;background:var(--card)!important;border-radius:8px!important}
.composer textarea{resize:vertical!important;min-height:64px!important;max-height:none!important;border:1px solid var(--line)!important;border-radius:6px;background:var(--bg)!important}
.cn-top:not(:has(*)){display:none}
.composer{border:1.5px solid var(--line);border-radius:14px;background:var(--bg);padding:8px 10px;display:flex;flex-direction:column;gap:6px;transition:border-color .15s}
.composer:focus-within{border-color:var(--acc);box-shadow:0 0 0 2px color-mix(in srgb,var(--acc) 20%,transparent)}
.composer textarea{border:0;background:transparent;color:inherit;resize:none;min-height:36px;max-height:200px;padding:4px 6px;font:inherit;line-height:1.7;outline:none;direction:auto;width:100%}
.composer .row{display:flex;align-items:center;gap:6px;flex-wrap:wrap}
.composer .row .sp{flex:1}
.est{font-size:12px;color:var(--mut)}
.cn-atts{display:flex;flex-wrap:wrap;gap:6px}
.cn-att{display:flex;align-items:center;gap:5px;border:1px solid var(--line);border-radius:9px;padding:3px 4px 3px 8px;background:var(--side);font-size:12px}
.cn-att select{border:0;background:transparent;color:inherit;font-size:12px;max-width:110px}
.cn-att button{border:0;background:transparent;cursor:pointer;color:var(--mut)}
.cn-ibtn{border:0;background:transparent;cursor:pointer;border-radius:9px;padding:5px 8px;color:var(--mut);font-size:15px}
.cn-ibtn:hover{background:var(--acc-soft);color:var(--acc)}
.cn-send{border:0;border-radius:10px;padding:7px 18px;background:var(--acc);color:#fff;font-weight:700;cursor:pointer;font-size:13.5px}
.cn-send:disabled{opacity:.45;cursor:default}
.cn-send.stop{background:var(--bad)}
.cn-thread{display:flex;flex-direction:column;gap:14px;flex:1;min-height:0;overflow-y:auto;padding-bottom:12px}
.cn-round{display:flex;flex-direction:column;gap:10px;animation:cnin .25s ease}
@keyframes cnin{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}
.cn-q{align-self:flex-start;max-width:92%;background:var(--acc-soft);border-radius:14px 14px 4px 14px;padding:9px 13px;white-space:pre-wrap;overflow-wrap:anywhere}
.cn-qfiles{font-size:11.5px;color:var(--mut);margin-top:4px}
.stages{display:flex;gap:4px;align-items:center;flex-wrap:wrap;font-size:12px;margin:2px 0}
.stages span{padding:2px 9px;border-radius:99px;background:var(--side);color:var(--mut)}
.stages span.done{background:var(--ok-soft);color:var(--ok)}
.stages span.cur{background:var(--acc);color:#fff}
.stages-sep{background:none!important;padding:0!important;color:var(--mut)}
.verdict{border:2px solid var(--gold);background:var(--gold-soft);border-radius:14px;padding:12px 14px;color:var(--txt)}
.verdict .vh{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.verdict .vh b{font-size:15px}
.verdict .conf{font-size:12px;border-radius:99px;padding:1px 9px;background:var(--card);border:1px solid var(--gold);color:var(--gold);font-weight:600}
.verdict .vbody{margin-top:8px;font-size:14px;line-height:1.8}
.verdict .vsum{display:none;font-size:13px;color:var(--mut);margin-top:4px}
.verdict.collapsed .vbody,.verdict.collapsed .vtabs,.verdict.collapsed .vpane{display:none}
.verdict.collapsed .vsum{display:block}
.vtabs{display:flex;gap:4px;margin-top:10px;flex-wrap:wrap}
.vtabs button{border:1px solid var(--line);background:var(--card);color:var(--txt);border-radius:8px;padding:3px 10px;cursor:pointer;font:inherit;font-size:12.5px;transition:.15s}
.vtabs button:hover{border-color:var(--gold)}
.vtabs button.on{border-color:var(--gold);background:var(--gold);color:#fff;font-weight:700}
.vpane{margin-top:8px;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px;font-size:13.5px;line-height:1.75;overflow-x:auto}
table.claims{width:100%;border-collapse:collapse;font-size:13px}
table.claims th,table.claims td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:start;vertical-align:top}
table.claims td.c,table.claims th.c{text-align:center;width:52px}
.yes{color:var(--ok);font-weight:700}.no{color:var(--bad);font-weight:700}.na{color:var(--mut)}
.tbar{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--mut);margin:6px 0 2px}
.tbar .sp{flex:1}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px;align-items:start}
.acard{border:1px solid var(--line);border-radius:12px;background:var(--card);border-top:3px solid var(--c,var(--line));display:flex;flex-direction:column;min-height:150px;min-width:0;transition:box-shadow .15s}
.acard:hover{box-shadow:0 2px 8px rgba(0,0,0,.06)}
.acard.wide{grid-column:1/-1}
.acard .h{display:flex;align-items:center;gap:6px;padding:8px 10px;border-bottom:1px solid var(--line);font-size:13.5px}
.acard .h .letter{font-size:11px;color:var(--mut)}
.acard .h .bd{margin-inline-start:auto;font-size:11px;border-radius:99px;padding:1px 8px;color:#fff}
.acard .act{font-size:12px;color:var(--mut);padding:6px 10px;border-bottom:1px dashed var(--line);min-height:28px;display:flex;align-items:center;gap:5px;flex-wrap:wrap}
.acard .act .tool{display:inline-block;background:var(--side);border-radius:6px;padding:1px 6px;margin:1px 0;font-size:11.5px}
.acard .tx{padding:8px 10px;font-size:13px;max-height:220px;overflow-y:auto;white-space:pre-wrap;scrollbar-width:thin}
.acard.wide .tx{max-height:60vh}
.acard .peek{display:none;font-size:12px;color:var(--mut);padding:8px 10px}
.acard.collapsed{min-height:0}
.acard.collapsed .act,.acard.collapsed .tx{display:none}
.acard.collapsed .peek{display:block}
.acard .ft{display:flex;gap:6px;padding:6px 10px;border-top:1px solid var(--line);margin-top:auto;font-size:12px;color:var(--mut);align-items:center;flex-wrap:wrap}
.fold-h{cursor:pointer;user-select:none}
.chev2{display:inline-block;margin-inline-start:auto;color:var(--mut);transition:transform .2s;font-size:13px}
.collapsed .chev2{transform:rotate(90deg)}
.mbtn{border:1px solid var(--line);background:var(--card);color:var(--txt);border-radius:9px;padding:4px 11px;cursor:pointer;font:inherit;font-size:12.5px;transition:.15s}
.mbtn:hover{border-color:var(--acc);color:var(--acc)}
.mbtn.pri{background:var(--acc);border-color:var(--acc);color:#fff}
.mbtn.pri:hover{opacity:.9}
.mbtn.gold{background:var(--gold-soft);border-color:var(--gold);color:var(--gold)}
.mbtn.gold:hover{background:var(--gold);color:#fff}
.cn [hidden]{display:none!important}
.pill{display:inline-block;font-size:11px;border-radius:99px;padding:1px 7px;font-weight:600}
.p-warn{background:var(--warn-soft);color:var(--warn)}
.p-crit{background:var(--bad-soft);color:var(--bad)}
.p-ok{background:var(--ok-soft);color:var(--ok)}
.skel{height:12px;border-radius:6px;background:linear-gradient(90deg,var(--side),var(--line),var(--side));background-size:200% 100%;animation:sh 1.2s infinite;margin:6px 0}
@keyframes sh{to{background-position:-200% 0}}
.foot-actions{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:6px}
.cn-md{overflow-wrap:anywhere;line-height:1.8}
.cn-md h4{margin:10px 0 4px;color:var(--c,var(--acc));font-size:13.5px}
.cn-md p{margin:3px 0}
.cn-md ul{margin:3px 0;padding-inline-start:20px}
.cn-err{color:var(--bad);font-size:12.5px;padding:4px 0}
.cn-sub{color:var(--mut);font-size:12px}
.cn-time{font-size:11px;color:var(--mut)}
.cn-empty{border:1.5px dashed var(--line);border-radius:12px;padding:22px;text-align:center;color:var(--mut)}
.cn-live{margin:0;padding:8px;max-height:180px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;font:12px ui-monospace,monospace;background:var(--side);border-radius:8px;color:var(--mut);direction:auto}

/* ===== ضغط شامل: مساحة أكبر للأجوبة ===== */
.cn{gap:5px;font-size:12.5px}
.brow.team{display:flex;gap:4px;align-items:stretch}
.brow.team .roster{flex:1;grid-auto-columns:minmax(78px,1fr)}
.cn-cfgtoggle{flex:none;border:1px solid var(--line);background:var(--card);color:var(--txt);border-radius:4px;padding:0 8px;font:inherit;font-size:11px;cursor:pointer;white-space:nowrap}
.cn-cfgtoggle:hover{background:var(--side)}
.brow.cfg[hidden]{display:none}
.chip,.tile{min-height:22px;padding:1px 4px;font-size:11px}
.chip .av{width:14px;height:14px;font-size:9px}
.composer{padding:3px 6px!important;gap:3px!important;border-radius:7px!important}
.composer textarea{min-height:34px!important;padding:2px 5px!important;line-height:1.5!important;font-size:12.5px}
.composer .row{gap:4px}
.cn-send{padding:3px 12px!important;font-size:12px!important;border-radius:6px!important}
.cn-ibtn{padding:1px 6px;font-size:13px}
.est{font-size:11px}
.mbtn{padding:2px 8px;font-size:11.5px}
.cn-thread{gap:8px;padding-bottom:6px}
.cn-round{gap:6px}
.cn-q{padding:5px 10px}
.stages{margin:0;font-size:11px}
.stages span{padding:1px 7px}
.verdict{padding:6px 10px;border-width:1.5px;border-radius:9px}
.verdict .vbody{margin-top:4px;line-height:1.65;font-size:13px}
.tbar{margin:2px 0 0;font-size:12px}
.cards{grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:6px}
.acard{min-height:90px;border-radius:8px}
.acard .h{padding:4px 8px;font-size:12px}

`;

  function mountCouncil(container, opts) {
    if (!container) return;
    opts = opts || {};
    unmountCouncil(container);
    const host = container; host.replaceChildren(); host.className = (host.className + ' cn').trim(); host.dir = 'rtl'; councilRoot = host;
    const style = document.createElement('style'); style.textContent = CN_CSS; host.appendChild(style);
    const mk = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

    // ===== الرأس =====
    const top = mk('div', 'cn-top');
    const checkBtn = mk('button', 'mbtn', 'فحص الجاهزية');
    checkBtn.type = 'button';
    const histSel = mk('select', 'mbtn');
    histSel.title = 'مجالس سابقة';
    top.append(checkBtn, histSel);
    const tabBar = host.closest('#zajel-term-window')?.querySelector('.tw-tabs');
    if (tabBar) {
      tabBar.querySelectorAll('.cn-tabtools').forEach(x => x.remove());
      const tools = mk('span', 'cn-tabtools'); tools.style.cssText = 'margin-inline-start:auto;display:inline-flex;gap:6px';
      tools.append(checkBtn, histSel); tabBar.appendChild(tools);
    }
    if (opts.onExit) {
      const exitBtn = mk('button', 'mbtn', 'العودة للمحادثة');
      exitBtn.type = 'button';
      exitBtn.onclick = opts.onExit;
      top.appendChild(exitBtn);
    }
    host.appendChild(top);

    // ===== الصفّان (الفريق ثم العمق وخيارات الحكم) =====
    const mbar = mk('div', 'mbar');

    // الصف ١: الفريق
    const browTeam = mk('div', 'brow team');
    const roster = mk('div', 'roster');
    roster.title = 'اضغط على الوكيل ليشارك · 👑 لتجعله الحكم';
    browTeam.append(roster);
    const cfgToggle = mk('button', 'cn-cfgtoggle'); cfgToggle.type = 'button'; cfgToggle.title = 'إعدادات العمق والخيارات (توسيع/طي)';
    browTeam.append(cfgToggle);

    // الصف ٢: العمق وخيارات الحكم
    const browCfg = mk('div', 'brow cfg');
    const depthSel = mk('select', 'msel');   // لا يُعرض: الأزرار الثلاثة تضبطه
    depthSel.title = 'العمق يحدد طريقة التفكير والبحث والأدوات';
    [
      ['fast', '⚡ سريع · ١–٣ د'],
      ['bal', '⚖ متوازن · ٣–٨ د'],
      ['deep', '🔬 عميق · ١٠–٢٥ د']
    ].forEach(([v, t]) => {
      const o = mk('option', '', t); o.value = v; depthSel.appendChild(o);
    });

    // العمق: ثلاث خانات بدل القائمة المنسدلة
    const DEPTH_TILES = [['fast', '⚡', 'سريع', '١–٣ د', 'سريع: تفكير عادي، للأسئلة القصيرة'],
      ['bal', '⚖', 'متوازن', '٣–٨ د', 'متوازن: أقوى نموذج وتفكير عالٍ (الافتراضي)'],
      ['deep', '🔬', 'عميق', '١٠–٢٥ د', 'عميق: أقصى تفكير ونقد متبادل، للدراسات والرسائل']];
    const depthBtns = {};
    const depthGroup = mk('div', 'tiles depth');
    DEPTH_TILES.forEach(([v, ic, t, tm, tip]) => {
      const b = mk('button', 'tile'); b.type = 'button'; b.title = tip;
      b.append(mk('span', 'ic', ic), mk('span', 'tl', t), mk('span', 'tm', tm));
      b.onclick = () => applyDepth(v);
      depthBtns[v] = b; depthGroup.appendChild(b);
    });
    const syncDepthTiles = () => { Object.entries(depthBtns).forEach(([v, b]) => b.classList.toggle('on', v === depthSel.value)); if (typeof syncCfg === 'function') syncCfg(); };
    const optsSpan = mk('div', 'tiles opts');

    const makeOpt = (id, label, tip) => {
      const lbl = mk('label', 'opt');
      lbl.title = tip;
      lbl.dataset.tip = tip;
      const inp = mk('input'); inp.type = 'checkbox'; inp.id = id;
      const [ic, ...rest] = label.split(' ');
      const sp = mk('span', 'tile');
      sp.append(mk('span', 'ic', ic), mk('span', 'tl', rest.join(' ')));
      lbl.append(inp, sp);
      return { lbl, inp };
    };

    const optBlind = makeOpt('cnOptBlind', '🙈 مُعمّى', 'حكم مُعمّى: لا يعرف الحكم أسماء أصحاب الإجابات');
    const optReview = makeOpt('cnOptReview', '💬 نقد', 'جولة نقد متبادل: يراجع كل وكيل إجابات الآخرين قبل الحكم');
    const optVerify = makeOpt('cnOptVerify', '🔎 تحقق', 'تحقق: يراجع الحكم الإحالات في الشاملة');
    const optLive = makeOpt('cnOptLive', '📺 حي', 'وضع حي: تشاهد الوكيل وهو يكتب عبر الطرفية');

    optsSpan.append(optBlind.lbl, optReview.lbl, optVerify.lbl, optLive.lbl);
    browCfg.append(depthGroup, optsSpan);

    mbar.append(browTeam, browCfg);
    let cfgOpen = (() => { try { return localStorage.getItem('zajel_council_cfg_open') === 'true'; } catch (_) { return false; } })();
    const DEPTH_NAME = { fast: '⚡ سريع', bal: '⚖ متوازن', deep: '🔬 عميق' };
    const syncCfg = () => {
      browCfg.hidden = !cfgOpen;
      cfgToggle.textContent = (DEPTH_NAME[depthSel.value] || '') + (cfgOpen ? ' ▴' : ' ▾');
    };
    cfgToggle.onclick = () => { cfgOpen = !cfgOpen; try { localStorage.setItem('zajel_council_cfg_open', String(cfgOpen)); } catch (_) {} syncCfg(); };
    depthSel.addEventListener('change', syncCfg);
    host.appendChild(mbar);

    // ===== مربع الكتابة والمرفقات =====
    const composer = mk('div', 'composer');
    const attBar = mk('div', 'cn-atts'); attBar.hidden = true;
    const ta = mk('textarea');
    ta.rows = 1;
    ta.dir = 'auto';
    ta.placeholder = 'اسأل المجلس… أرفق ملفًا أو اكتب مساره على الكمبيوتر (Markdown أو Word أو PDF) · ⌘↩ للإرسال';

    const compRow = mk('div', 'row');
    const attachBtn = mk('button', 'cn-ibtn', '📎');
    attachBtn.type = 'button';
    attachBtn.title = 'إرفاق ملفات لوكيل أو للحكم';
    const fileIn = mk('input'); fileIn.type = 'file'; fileIn.multiple = true; fileIn.hidden = true;
    const estSpan = mk('span', 'est');
    const sp = mk('span', 'sp');
    const newBtn = mk('button', 'mbtn', 'سؤال جديد'); newBtn.type = 'button'; newBtn.hidden = true;
    const sendBtn = mk('button', 'cn-send', 'أرسل ⌘↩'); sendBtn.type = 'button';

    compRow.append(attachBtn, fileIn, estSpan, sp, newBtn, sendBtn);
    composer.append(attBar, ta, compRow);
    host.appendChild(composer);

    const thread = mk('div', 'cn-thread');
    const empty = mk('div', 'cn-empty', 'اختر الوكلاء بالضغط على أسمائهم، وعيّن الحكم بالتاج، ثم اطرح سؤالك.');
    thread.appendChild(empty);
    host.appendChild(thread);

    // ===== الحالة =====
    let available = [], selected = new Set(), main = '', checkStates = {}, atts = [];
    let activeId = '', lastDoneId = '', parentId = '', boxes = {};

    // قراءة التفضيلات المحفوظة
    try {
      const sv = JSON.parse(localStorage.getItem('zajel_council_sel') || '{}');
      selected = new Set(Array.isArray(sv.ids) ? sv.ids : []);
      main = typeof sv.main === 'string' ? sv.main : '';
    } catch (_) {}

    let depth = (() => { try { return localStorage.getItem('zajel_council_depth') || 'bal'; } catch (_) { return 'bal'; } })();
    if (!['fast', 'bal', 'deep'].includes(depth)) depth = 'bal';
    depthSel.value = depth; syncCfg();

    let blind = (() => { try { const v = localStorage.getItem('zajel_council_blind'); return v == null ? true : v === 'true'; } catch (_) { return true; } })();
    let review = (() => { try { return localStorage.getItem('zajel_council_review') === 'true'; } catch (_) { return false; } })();
    let verify = (() => { try { const v = localStorage.getItem('zajel_council_verify'); return v == null ? true : v === 'true'; } catch (_) { return true; } })();
    let liveMode = (() => { try { return localStorage.getItem('zajel_council_live') === 'true'; } catch (_) { return false; } })();

    optBlind.inp.checked = blind;
    optReview.inp.checked = review;
    optVerify.inp.checked = verify;
    optLive.inp.checked = liveMode;

    const persist = () => {
      try {
        localStorage.setItem('zajel_council_sel', JSON.stringify({ ids: [...selected], main }));
        localStorage.setItem('zajel_council_depth', depth);
        localStorage.setItem('zajel_council_blind', String(optBlind.inp.checked));
        localStorage.setItem('zajel_council_review', String(optReview.inp.checked));
        localStorage.setItem('zajel_council_verify', String(optVerify.inp.checked));
        localStorage.setItem('zajel_council_live', String(optLive.inp.checked));
      } catch (_) {}
    };

    const nameOf = id => available.find(a => a.id === id)?.name || id;
    const err = e => {
      const p = mk('div', 'cn-err', e?.message || 'تعذّر تنفيذ الطلب');
      composer.after(p);
      setTimeout(() => p.remove(), 6000);
    };

    const grow = () => {
      ta.style.height = 'auto';
      ta.style.height = Math.min(200, ta.scrollHeight) + 'px';
    };
    ta.addEventListener('input', grow);

    // تطبيق ضبط العمق على حبوب الخيارات
    const applyDepth = mode => {
      depth = mode;
      depthSel.value = depth;
      syncDepthTiles();
      if (mode === 'fast') {
        optBlind.inp.checked = true;
        optBlind.inp.disabled = false;
        optBlind.lbl.classList.remove('locked');
        optBlind.lbl.title = optBlind.lbl.dataset.tip;

        optReview.inp.checked = false;
        optReview.inp.disabled = true;
        optReview.lbl.classList.add('locked');
        optReview.lbl.title = 'غير متاح في الوضع السريع — ' + optReview.lbl.dataset.tip;

        optVerify.inp.checked = false;
        optVerify.inp.disabled = false;
        optVerify.lbl.classList.remove('locked');
        optVerify.lbl.title = optVerify.lbl.dataset.tip;
      } else if (mode === 'bal') {
        optBlind.inp.checked = true;
        optBlind.inp.disabled = false;
        optBlind.lbl.classList.remove('locked');
        optBlind.lbl.title = optBlind.lbl.dataset.tip;

        optReview.inp.checked = false;
        optReview.inp.disabled = false;
        optReview.lbl.classList.remove('locked');
        optReview.lbl.title = optReview.lbl.dataset.tip;

        optVerify.inp.checked = true;
        optVerify.inp.disabled = false;
        optVerify.lbl.classList.remove('locked');
        optVerify.lbl.title = optVerify.lbl.dataset.tip;
      } else if (mode === 'deep') {
        optBlind.inp.checked = true;
        optBlind.inp.disabled = false;
        optBlind.lbl.classList.remove('locked');
        optBlind.lbl.title = optBlind.lbl.dataset.tip;

        optReview.inp.checked = true;
        optReview.inp.disabled = false;
        optReview.lbl.classList.remove('locked');
        optReview.lbl.title = optReview.lbl.dataset.tip;

        optVerify.inp.checked = true;
        optVerify.inp.disabled = false;
        optVerify.lbl.classList.remove('locked');
        optVerify.lbl.title = optVerify.lbl.dataset.tip;
      }
      persist();
      updateEst();
    };

    depthSel.onchange = () => applyDepth(depthSel.value);
    [optBlind.inp, optReview.inp, optVerify.inp, optLive.inp].forEach(inp => {
      inp.onchange = () => { persist(); updateEst(); };
    });

    // سطر تقدير الوقت
    const updateEst = () => {
      const ids = [...selected].filter(id => available.some(a => a.id === id));
      if (!ids.length) {
        estSpan.textContent = 'اختر مفوَّضًا واحدًا على الأقل';
        return;
      }
      const base = { fast: 2, bal: 5, deep: 11 }[depth] + (optReview.inp.checked ? 4 : 0);
      const speeds = ids.map(id => {
        const cs = checkStates[id];
        if (cs && cs.secs && cs.secs > 5) return Math.min(3, cs.secs / 10);
        return agentSpeed[id] || 1.0;
      });
      const maxSp = Math.max(...speeds);
      const lo = Math.max(1, Math.round(base * maxSp));
      const hi = Math.max(lo + 1, Math.round(base * maxSp * 1.5));
      const sorted = ids.map(id => ({ id, name: nameOf(id), sp: agentSpeed[id] || 1.0 })).sort((a, b) => b.sp - a.sp);
      const slowest = sorted[0];
      const slowestText = slowest && slowest.sp > 1.5 ? ' · الأبطأ: ' + slowest.name : '';
      const judgeText = main ? ' · الحكم: ' + nameOf(main) : ' · بلا حكم';
      estSpan.textContent = `متوقّع: ${lo}–${hi} دقيقة · ${ids.length} مفوَّض${judgeText}${slowestText}`;
    };

    applyDepth(depth);   // بعد تعريف updateEst (كان يُستدعى قبله فيتوقف المجلس عند الفتح)

    // فحص الجاهزية GET council/check
    const runCheck = async force => {
      checkBtn.textContent = 'يفحص…';
      checkBtn.disabled = true;
      const ids = available.map(a => a.id);
      try {
        const query = (ids.length ? 'ids=' + encodeURIComponent(ids.join(',')) + '&' : '') + 'force=' + (force ? '1' : '0');
        const res = await req('council/check?' + query).catch(() => null);
        if (res && res.agents) {
          checkStates = res.agents;
        }
        let readyCount = 0, offCount = 0;
        available.forEach(a => {
          const st = (checkStates[a.id] || {}).state || 'ready';
          if (st === 'off') {
            offCount++;
            if (selected.has(a.id)) selected.delete(a.id);
            if (main === a.id) main = '';
          } else {
            readyCount++;
          }
        });
        persist();
        renderRoster();
        checkBtn.textContent = `✓ ${readyCount} جاهز${offCount ? ' · ' + offCount + ' معطّل' : ''}`;
        setTimeout(() => { checkBtn.textContent = 'فحص الجاهزية'; checkBtn.disabled = false; }, 3500);
      } catch (_) {
        checkBtn.textContent = 'فحص الجاهزية';
        checkBtn.disabled = false;
      }
    };
    checkBtn.onclick = () => runCheck(true);

    const flashChip = (c, note) => {
      c.animate([
        { transform: 'translateX(0)' },
        { transform: 'translateX(-5px)' },
        { transform: 'translateX(5px)' },
        { transform: 'translateX(-4px)' },
        { transform: 'translateX(4px)' },
        { transform: 'translateX(0)' }
      ], { duration: 280 });
      err(new Error(note || 'الوكيل غير جاهز، لا يمكن اختياره'));
    };

    // رسم الفريق في الرستر
    const renderRoster = () => {
      roster.replaceChildren();
      available.forEach(a => {
        const chk = checkStates[a.id] || { state: 'ready', note: 'جاهز' };
        const isOff = chk.state === 'off';
        const isSlow = chk.state === 'slow';
        const dotCls = isOff ? 'off' : (isSlow ? 'slow' : 'ready');

        const chip = mk('div', 'chip' + (selected.has(a.id) ? ' on' : '') + (main === a.id ? ' judge' : '') + (isOff ? ' off' : ''));
        chip.style.setProperty('--c', colorOf(a.id));
        chip.title = a.name + ': ' + (chk.note || (isOff ? 'معطّل' : isSlow ? 'بطيء' : 'جاهز'));

        const av = mk('span', 'av', a.name.trim().charAt(0).toUpperCase());
        const nm = mk('span', '', a.name);
        const dot = mk('span', 'dot ' + dotCls);
        const crown = mk('button', 'crown', '👑');
        crown.type = 'button';
        crown.title = main === a.id ? 'هو الحكم (اضغط للإلغاء)' : 'اجعله الحكم';

        crown.onclick = ev => {
          ev.stopPropagation();
          if (isOff) { flashChip(chip, chk.note); return; }
          main = (main === a.id) ? '' : a.id;
          if (main && !selected.has(main)) selected.add(main);
          persist();
          renderRoster();
          renderAtts();
        };

        chip.onclick = () => {
          if (isOff) { flashChip(chip, chk.note); return; }
          if (selected.has(a.id)) {
            selected.delete(a.id);
            if (main === a.id) main = '';
          } else {
            selected.add(a.id);
          }
          persist();
          renderRoster();
          renderAtts();
        };

        nm.className = 'nm';
        chip.append(dot, crown, av, nm);
        roster.appendChild(chip);
      });
      updateEst();
      sync();
    };

    // ===== المرفقات =====
    const targets = () => [
      ['*', 'للجميع'],
      ...(main ? [['main', 'للحكم فقط']] : []),
      ...[...selected].filter(id => available.some(a => a.id === id)).map(id => [id, 'لـ ' + nameOf(id)])
    ];

    function renderAtts() {
      attBar.replaceChildren();
      attBar.hidden = !atts.length;
      atts.forEach((a, i) => {
        const chip = mk('div', 'cn-att');
        chip.appendChild(mk('span', '', (a.status === 'up' ? '⏳ ' : a.status === 'err' ? '⚠ ' : '📄 ') + a.name));
        const sel = mk('select');
        targets().forEach(([v, t]) => {
          const o = mk('option', '', t); o.value = v; sel.appendChild(o);
        });
        if (!targets().some(([v]) => v === a.to)) a.to = '*';
        sel.value = a.to;
        sel.onchange = () => { a.to = sel.value; };
        const rm = mk('button', '', '✕');
        rm.type = 'button';
        rm.onclick = () => { atts.splice(i, 1); renderAtts(); };
        chip.append(sel, rm);
        attBar.appendChild(chip);
      });
    }

    const upload = async file => {
      const item = { name: file.name, status: 'up', path: '', to: '*' };
      atts.push(item);
      renderAtts();
      try {
        const r = await (await fetch('/api/assistant/upload?name=' + encodeURIComponent(file.name), { method: 'POST', body: file })).json();
        if (r && r.ok) {
          item.path = r.path;
          item.status = 'ok';
        } else {
          item.status = 'err';
          err(new Error(r?.error || 'فشل رفع الملف'));
        }
      } catch (e) {
        item.status = 'err';
        err(e);
      }
      renderAtts();
      sync();
    };

    attachBtn.onclick = () => fileIn.click();
    fileIn.onchange = () => { [...fileIn.files].forEach(upload); fileIn.value = ''; };
    ta.addEventListener('paste', ev => {
      const fs = [...(ev.clipboardData?.files || [])];
      if (fs.length) { ev.preventDefault(); fs.forEach(upload); }
    });
    host.addEventListener('dragover', ev => ev.preventDefault());
    host.addEventListener('drop', ev => {
      if (ev.dataTransfer?.files?.length) {
        ev.preventDefault();
        [...ev.dataTransfer.files].forEach(upload);
      }
    });

    // ===== عرض الجولة وتحديثها الجزئي =====
    const secs = t => {
      const n = Math.max(0, Math.round(t));
      return n < 60 ? n + ' ث' : Math.floor(n / 60) + ' د ' + (n % 60) + ' ث';
    };
    const finished = r => ['done', 'stopped', 'error'].includes(r.phase);

    function renderRound(r) {
      let box = boxes[r.id];
      if (!box) {
        empty.remove();
        box = boxes[r.id] = mk('section', 'cn-round');
        box.dataset.roundId = r.id;
        thread.appendChild(box);

        const qEl = mk('div', 'cn-q');
        box.appendChild(qEl);

        const stagesEl = mk('div', 'stages');
        box.appendChild(stagesEl);

        const verdictEl = mk('div');
        verdictEl.hidden = true;
        box.appendChild(verdictEl);

        const tbarEl = mk('div', 'tbar');
        tbarEl.innerHTML = '<span>إجابات الوكلاء</span><span class="sp"></span>';
        const foldAllBtn = mk('button', 'mbtn', 'طيّ الكل');
        foldAllBtn.type = 'button';
        foldAllBtn.onclick = () => {
          const isFold = foldAllBtn.textContent === 'طيّ الكل';
          box.querySelectorAll('.acard, .verdict').forEach(el => el.classList.toggle('collapsed', isFold));
          foldAllBtn.textContent = isFold ? 'توسيع الكل' : 'طيّ الكل';
        };
        tbarEl.appendChild(foldAllBtn);
        box.appendChild(tbarEl);

        const cardsEl = mk('div', 'cards');
        box.appendChild(cardsEl);

        const refiningNoteEl = mk('div', 'cn-sub');
        refiningNoteEl.style.margin = '4px 0';
        box.appendChild(refiningNoteEl);

        const footEl = mk('div', 'foot-actions');
        box.appendChild(footEl);

        box._ui = {
          qEl,
          stagesEl,
          verdictEl,
          tbarEl,
          cardsEl,
          refiningNoteEl,
          footEl,
          agentCards: {},
          lastEvalText: '',
          activeVerdictTab: 'agree',
          isVerdictCollapsed: false
        };

        setTimeout(() => box.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50);
      }

      const ui = box._ui;

      // 1. السؤال والمرفقات
      if (!ui.qEl.dataset.rendered) {
        ui.qEl.textContent = r.question || '';
        if ((r.attachments || []).length) {
          const qf = mk('div', 'cn-qfiles', '📎 ' + r.attachments.map(a => (a.name || a.path.split('/').pop()) + (a.scanned ? ' (⚠ مصوَّر بلا نص)' : a.text ? ' (✓ استُخرج نصه)' : '')).join('، '));
          ui.qEl.appendChild(qf);
        }
        ui.qEl.dataset.rendered = '1';
      }

      // 2. شريط المراحل
      const hasReview = !!r.review || r.phase === 'review';
      const hasJudge = !!r.main;
      const hasVerify = r.verify !== false;
      const stagesList = [
        'التحضير',
        'الإجابات',
        ...(hasReview ? ['النقد المتبادل'] : []),
        ...(hasJudge ? ['الحكم'] : []),
        ...(hasVerify ? ['التحقق'] : []),
        'الصادر'
      ];

      let curStage = 0;
      if (r.phase === 'asking') curStage = 1;
      else if (r.phase === 'review') curStage = stagesList.indexOf('النقد المتبادل');
      else if (r.phase === 'evaluating' || r.phase === 'refining') {
        const evIdx = stagesList.indexOf('الحكم');
        curStage = evIdx !== -1 ? evIdx : 1;
      } else if (finished(r)) {
        curStage = stagesList.length - 1;
      }

      const stagesHtml = stagesList.map((st, i) => {
        const isDone = i < curStage;
        const isCur = i === curStage;
        const cls = isDone ? 'done' : (isCur ? 'cur' : '');
        const mark = isDone ? '✓ ' : '';
        return `<span class="${cls}">${mark}${st}</span>`;
      }).join('<span class="stages-sep">‹</span>');

      if (ui.stagesEl.innerHTML !== stagesHtml) {
        ui.stagesEl.innerHTML = stagesHtml;
      }

      // 3. صندوق الحكم الذهبي
      const ev = r.eval || {};
      if (r.main) {
        ui.verdictEl.hidden = false;
        const isDoneEval = ['done', 'done_raw'].includes(ev.state) || (ev.answer && finished(r));
        if (!ev.answer && !isDoneEval) {
          if (['asking', 'starting', 'evaluating', 'refining'].includes(r.phase) || ['asking', 'starting'].includes(ev.state)) {
            const textThinking = r.blind ? ' (لا يعرف أسماء أصحاب الإجابات)' : '';
            const waitHtml = `<div class="verdict"><div class="vh"><span class="av" style="background:var(--gold)">⚖</span><b>الحكم يكتب${textThinking}…</b></div><div class="skel"></div><div class="skel" style="width:60%"></div></div>`;
            if (ui.verdictEl.dataset.state !== 'wait') {
              ui.verdictEl.innerHTML = waitHtml;
              ui.verdictEl.dataset.state = 'wait';
            }
          } else {
            ui.verdictEl.hidden = true;
          }
        } else if (ev.answer) {
          ui.verdictEl.dataset.state = 'ans';
          if (ui.lastEvalText !== ev.answer) {
            ui.lastEvalText = ev.answer;
            const judgeName = ev.name || nameOf(r.main);
            const parsed = parseVerdict(ev.answer);

            if (parsed) {
              const vcard = mk('div', 'verdict');
              if (ui.isVerdictCollapsed) vcard.classList.add('collapsed');

              const vh = mk('div', 'vh fold-h');
              vh.title = 'اضغط للطيّ أو التوسيع';
              vh.innerHTML = `<span class="av" style="background:var(--gold);color:#fff">⚖</span><b>الحكم النهائي — ${esc(judgeName)}</b>${parsed.confidence ? `<span class="conf">الثقة: ${esc(parsed.confidence)}</span>` : ''}<span class="chev2">▾</span>`;
              vh.onclick = () => {
                ui.isVerdictCollapsed = vcard.classList.toggle('collapsed');
              };
              vcard.appendChild(vh);

              if (parsed.summary) {
                const vsum = mk('div', 'vsum', parsed.summary);
                vcard.appendChild(vsum);
              }

              const vbody = mk('div', 'vbody');
              vbody.appendChild(mdBox(parsed.finalVerdict));
              vcard.appendChild(vbody);

              const tabDefs = [
                ['agree', 'الاتفاق', parsed.panes.agree],
                ['diff', 'الخلاف ومن الأصح', parsed.panes.diff],
                ['map', 'خريطة الأقوال', parsed.panes.map],
                ['src', 'المصادر', parsed.panes.src],
                ['rank', 'الترتيب', parsed.panes.rank]
              ].filter(t => Boolean(t[2]));

              if (tabDefs.length) {
                if (!tabDefs.some(t => t[0] === ui.activeVerdictTab)) {
                  ui.activeVerdictTab = tabDefs[0][0];
                }
                const vtabs = mk('div', 'vtabs');
                const vpane = mk('div', 'vpane');

                const renderPane = tabKey => {
                  const def = tabDefs.find(t => t[0] === tabKey);
                  if (!def) return;
                  vpane.replaceChildren();
                  if (tabKey === 'map') {
                    const tbl = formatClaimsTable(def[2]);
                    if (tbl) vpane.appendChild(tbl);
                    else vpane.appendChild(mdBox(def[2]));
                  } else {
                    vpane.appendChild(mdBox(def[2]));
                  }
                };

                tabDefs.forEach(([k, label]) => {
                  const btn = mk('button', k === ui.activeVerdictTab ? 'on' : '', label);
                  btn.type = 'button';
                  btn.dataset.k = k;
                  btn.onclick = () => {
                    ui.activeVerdictTab = k;
                    vtabs.querySelectorAll('button').forEach(b => b.classList.toggle('on', b.dataset.k === k));
                    renderPane(k);
                  };
                  vtabs.appendChild(btn);
                });

                renderPane(ui.activeVerdictTab);
                vcard.append(vtabs, vpane);
              }

              ui.verdictEl.replaceChildren(vcard);
            } else {
              const vcard = mk('div', 'verdict');
              if (ui.isVerdictCollapsed) vcard.classList.add('collapsed');
              const vh = mk('div', 'vh fold-h');
              vh.title = 'اضغط للطيّ أو التوسيع';
              vh.innerHTML = `<span class="av" style="background:var(--gold);color:#fff">⚖</span><b>الحكم — ${esc(judgeName)}</b><span class="chev2">▾</span>`;
              vh.onclick = () => {
                ui.isVerdictCollapsed = vcard.classList.toggle('collapsed');
              };
              vcard.appendChild(vh);
              const vbody = mk('div', 'vbody');
              vbody.appendChild(mdBox(ev.answer));
              vcard.appendChild(vbody);
              ui.verdictEl.replaceChildren(vcard);
            }
          }
        }
      } else {
        ui.verdictEl.hidden = true;
      }

      // 4. بطاقات الوكلاء
      const delegates = r.delegates || [];
      const letters = r.letters || {};
      delegates.forEach(id => {
        const d = (r.agents && r.agents[id]) || {};
        let card = ui.agentCards[id];
        if (!card) {
          card = mk('div', 'acard');
          card.dataset.agentId = id;
          card.style.setProperty('--c', colorOf(id));

          const h = mk('div', 'h fold-h');
          h.title = 'اضغط للطيّ أو التوسيع';
          const av = mk('span', 'av', (d.name || nameOf(id)).trim().charAt(0).toUpperCase());
          const nm = mk('b', '', d.name || nameOf(id));
          const letSpan = mk('span', 'letter');
          const bd = mk('span', 'bd');
          const partBadge = mk('span', 'pill p-warn', 'جزئية');
          partBadge.hidden = true;
          const chev = mk('span', 'chev2', '▾');
          h.append(av, nm, letSpan, bd, partBadge, chev);
          h.onclick = () => card.classList.toggle('collapsed');

          const peek = mk('div', 'peek');
          const act = mk('div', 'act');
          const tx = mk('div', 'tx');

          const ft = mk('div', 'ft');
          const tm = mk('span', 'tm');
          const toggleRevBtn = mk('button', 'mbtn', 'الأصلية');
          toggleRevBtn.type = 'button';
          toggleRevBtn.hidden = true;
          const cpBtn = mk('button', 'mbtn', 'نسخ');
          cpBtn.type = 'button';
          const wideBtn = mk('button', 'mbtn', 'توسيع');
          wideBtn.type = 'button';
          ft.append(tm, toggleRevBtn, cpBtn, wideBtn);

          card.append(h, peek, act, tx, ft);
          ui.cardsEl.appendChild(card);

          card._ui = {
            h, av, nm, letSpan, bd, partBadge, peek, act, tx, ft, tm, toggleRevBtn, cpBtn, wideBtn,
            showRevised: true,
            lastRenderedText: '',
            lastActivity: '',
            lastState: ''
          };

          wideBtn.onclick = () => {
            const isWide = card.classList.toggle('wide');
            wideBtn.textContent = isWide ? 'تصغير' : 'توسيع';
          };

          cpBtn.onclick = () => {
            const textToCopy = (card._ui.showRevised && d.revised) ? d.revised : (d.answer || d.live || '');
            if (textToCopy && navigator.clipboard?.writeText) {
              navigator.clipboard.writeText(textToCopy).then(() => {
                cpBtn.textContent = 'تم النسخ ✓';
                setTimeout(() => cpBtn.textContent = 'نسخ', 1500);
              }).catch(() => {});
            }
          };

          toggleRevBtn.onclick = () => {
            card._ui.showRevised = !card._ui.showRevised;
            toggleRevBtn.textContent = card._ui.showRevised ? 'الأصلية' : 'المنقّحة';
            card._ui.lastRenderedText = '';
            renderCardText();
          };

          ui.agentCards[id] = card;
        }

        const cui = card._ui;

        // تحديث الرأس
        const letter = letters[id] || '';
        cui.letSpan.textContent = letter ? `(الإجابة ${letter})` : '';
        if (cui.lastState !== d.state) {
          cui.lastState = d.state;
          cui.bd.textContent = councilStateText[d.state] || d.state || 'في الانتظار';
          cui.bd.style.background = councilStateColor[d.state] || '#737373';
        }
        cui.partBadge.hidden = !d.partial;

        // تحديث النشاط
        if (d.activity && cui.lastActivity !== d.activity) {
          cui.lastActivity = d.activity;
          cui.act.innerHTML = '🔧 <span class="tool">' + esc(d.activity) + '</span>';
        } else if (!d.activity && cui.lastActivity !== (d.state || '')) {
          cui.lastActivity = d.state || '';
          if (['done', 'done_raw'].includes(d.state)) {
            cui.act.innerHTML = '<span class="small muted">✓ اكتملت الإجابة</span>';
          } else if (d.error) {
            cui.act.innerHTML = '<span class="cn-err">⚠ ' + esc(d.error) + '</span>';
          } else if (['asking', 'starting', 'reviewing'].includes(d.state)) {
            cui.act.innerHTML = '<span class="small muted">⏳ يعمل الآن…</span>';
          } else {
            cui.act.textContent = '';
          }
        }

        // زر الأصلية / المنقّحة
        cui.toggleRevBtn.hidden = !(d.answer && d.revised);

        // وقت الاستغراق
        if (d.sent_at) {
          cui.tm.textContent = secs(((d.finished_at || Date.now() / 1000) - d.sent_at));
        } else {
          cui.tm.textContent = '';
        }

        // نص الإجابة (مع احترام التحديد النشط)
        function renderCardText() {
          const sel = window.getSelection();
          const hasActiveSelection = sel && !sel.isCollapsed && card.contains(sel.anchorNode);
          if (hasActiveSelection) return;

          const activeAns = (cui.showRevised && d.revised) ? d.revised : (d.answer || '');
          if (activeAns) {
            if (cui.lastRenderedText !== activeAns) {
              cui.lastRenderedText = activeAns;
              const st = cui.tx.scrollTop;
              cui.tx.replaceChildren(mdBox(activeAns));
              cui.tx.scrollTop = st;
              const firstLn = activeAns.split('\n').map(l => l.trim()).filter(l => l && !l.startsWith('#'))[0] || '';
              cui.peek.textContent = firstLn.slice(0, 80) + (firstLn.length > 80 ? '…' : '');
            }
          } else if (d.live) {
            if (cui.lastRenderedText !== d.live) {
              cui.lastRenderedText = d.live;
              cui.tx.replaceChildren();
              const pre = mk('pre', 'cn-live', d.live);
              cui.tx.appendChild(pre);
              pre.scrollTop = pre.scrollHeight;
              cui.peek.textContent = d.live.slice(0, 80) + '…';
            }
          } else if (['asking', 'starting', 'queued', 'reviewing'].includes(d.state)) {
            if (cui.lastRenderedText !== '__skel__') {
              cui.lastRenderedText = '__skel__';
              cui.tx.innerHTML = '<div class="skel"></div><div class="skel" style="width:70%"></div>';
            }
          }
        }
        renderCardText();
      });

      // 5. الملاحظات والتذييل
      if (r.phase === 'refining') {
        ui.refiningNoteEl.textContent = 'زاجل ينتظر ' + (r.pending || 'بعض') + ' وكيل ليحدّث الحكم بإجاباتهم…';
        ui.refiningNoteEl.hidden = false;
      } else {
        ui.refiningNoteEl.hidden = true;
      }

      // أزرار التصدير والتقييم
      ui.footEl.replaceChildren();
      const anyAns = Object.values(r.agents || {}).some(x => x.answer);
      if (r.main && anyAns && !['done', 'done_raw'].includes(ev.state) && !finished(r)) {
        const evalNowBtn = mk('button', 'mbtn', 'قيّم الآن بما وصل');
        evalNowBtn.type = 'button';
        evalNowBtn.onclick = async () => {
          try {
            await req('council/evaluate', { id: r.id });
            poll();
          } catch (e) {
            err(e);
          }
        };
        ui.footEl.appendChild(evalNowBtn);
      }

      if (finished(r) && anyAns) {
        ui.footEl.appendChild(mk('span', 'small muted', 'حفظ كامل الجلسة:'));
        [['Word', 'docx'], ['PDF', 'pdf'], ['Markdown', 'md']].forEach(([t, f]) => {
          const b = mk('button', 'mbtn', t);
          b.type = 'button';
          b.onclick = async () => {
            try {
              const x = await req('council/export', { id: r.id, fmt: f });
              b.textContent = '✓ ' + t;
              if (x.path) {
                ui.refiningNoteEl.textContent = 'حُفظ في: ' + x.path;
                ui.refiningNoteEl.hidden = false;
              }
            } catch (e) {
              err(e);
            }
          };
          ui.footEl.appendChild(b);
        });

        [['إلى تيليجرام', 'telegram'], ['إلى الموقع', 'web']].forEach(([t, target]) => {
          const b = mk('button', 'mbtn', t);
          b.type = 'button';
          b.title = target === 'web' ? 'يرسل النتيجة إلى الرابط الذي ضبطته بأمر cweb في تيليجرام' : 'يرسل الحكم إلى محادثتك في تيليجرام';
          b.onclick = async () => {
            try {
              await req('council/deliver', { id: r.id, target });
              b.textContent = '✓ ' + t;
            } catch (e) {
              err(e);
            }
          };
          ui.footEl.appendChild(b);
        });

        const followBtn = mk('button', 'mbtn gold', '↳ متابعة على هذا الحكم');
        followBtn.type = 'button';
        followBtn.onclick = () => {
          lastDoneId = r.id;
          parentId = r.id;
          sync();
          ta.focus();
          followBtn.textContent = '✓ سيُرفق الحكم السابق كاملًا';
        };
        ui.footEl.appendChild(followBtn);
      }
    }

    // ===== الاستعلام الدوري =====
    async function poll() {
      if (councilRoot !== host || !host.isConnected || !activeId) return;
      try {
        const d = await req('council/status?id=' + encodeURIComponent(activeId));
        if (!d.round) return;
        renderRound(d.round);
        if (finished(d.round) && !(d.round.pending > 0)) {
          clearInterval(councilTimer);
          councilTimer = null;
          lastDoneId = d.round.id;
          sync();
        }
      } catch (e) {
        err(e);
      }
    }

    function sync() {
      const busy = activeId && lastDoneId !== activeId;
      sendBtn.textContent = busy ? '■ إيقاف' : (lastDoneId ? 'متابعة ⌘↩' : 'أرسل ⌘↩');
      sendBtn.classList.toggle('stop', !!busy);
      sendBtn.disabled = !busy && (!ta.value.trim() || !selected.size || atts.some(a => a.status === 'up'));
      newBtn.hidden = !lastDoneId || busy;
    }
    ta.addEventListener('input', sync);
    ta.addEventListener('keydown', ev => {
      if (ev.key === 'Enter' && (ev.metaKey || ev.ctrlKey)) {
        ev.preventDefault();
        if (!sendBtn.disabled) sendBtn.click();
      }
    });

    newBtn.onclick = () => {
      lastDoneId = '';
      parentId = '';
      sync();
      ta.focus();
    };

    sendBtn.onclick = async () => {
      if (activeId && lastDoneId !== activeId) {
        try {
          await req('council/stop', { id: activeId });
          poll();
        } catch (e) {
          err(e);
        }
        return;
      }
      const ids = [...selected].filter(id => available.some(a => a.id === id));
      if (!ta.value.trim() || !ids.length) {
        err(new Error('اكتب سؤالًا واختر مفوَّضًا واحدًا على الأقل'));
        return;
      }
      const files = atts.filter(a => a.status === 'ok').map(a => ({ path: a.path, name: a.name, to: a.to }));
      const limit = depth === 'fast' ? 180 : (depth === 'bal' ? 300 : 0);
      const mode = optLive.inp.checked ? 'terminal' : 'direct';

      try {
        const payload = {
          ids,
          text: ta.value,
          main,
          evaluate: true,
          attachments: files,
          parent: lastDoneId || parentId || '',
          depth,
          blind: optBlind.inp.checked,
          review: optReview.inp.checked,
          verify: optVerify.inp.checked,
          mode,
          limit
        };
        const d = await req('council/send', payload);
        activeId = d.id;
        lastDoneId = '';
        ta.value = '';
        atts = [];
        renderAtts();
        grow();
        sync();

        try {
          window.ZajelTerminalUI?.showAgents?.(main && !ids.includes(main) ? [...ids, main] : ids);
        } catch (_) {}

        clearInterval(councilTimer);
        councilTimer = setInterval(poll, 1500);
        poll();
      } catch (e) {
        err(e);
      }
    };

    // ===== المجالس السابقة =====
    const loadHistory = async () => {
      try {
        const d = await req('council/history');
        histSel.replaceChildren();
        const o0 = mk('option', '', 'مجالس سابقة ▾');
        o0.value = '';
        histSel.appendChild(o0);
        (d.rounds || []).forEach(r => {
          const o = mk('option', '', (r.question || 'مجلس').slice(0, 50));
          o.value = r.id;
          histSel.appendChild(o);
        });
        histSel.hidden = !(d.rounds || []).length;
      } catch (_) {
        histSel.hidden = true;
      }
    };

    histSel.onchange = async () => {
      if (!histSel.value) return;
      activeId = histSel.value;
      lastDoneId = '';
      thread.replaceChildren();
      boxes = {};
      await poll();
      histSel.value = '';
      if (!councilTimer) councilTimer = setInterval(poll, 1500);
    };

    // تهيئة الوكلاء وفحص الجاهزية التلقائي
    req('list').then(d => {
      available = (d.agents || []).filter(a => a.cmd && a.installed === true);
      selected = new Set([...selected].filter(id => available.some(a => a.id === id)));
      if (main && !available.some(a => a.id === main)) main = '';
      renderRoster();
      renderAtts();
      loadHistory();
      sync();
      runCheck(false);
    }).catch(err);

    councilApi = { ask: t => { ta.value = t; sync(); return sendBtn.onclick(); } };
  }
  function unmountCouncil(container){if(councilRoot&&(!container||councilRoot===container||container.contains(councilRoot))){clearInterval(councilTimer);councilTimer=null;councilRoot=null;councilApi=null;councilRoundId='';}}
  function activate(el){if(!el)return;if(root&&root.parentNode===el&&listTimer)return;const host=document.createElement('div');el.replaceChildren(host);root=host;hist=1500;builtLayout=0;build();builtLayout=layout;refreshList();clearInterval(listTimer);listTimer=setInterval(refreshList,2000);clearInterval(screenTimer);screenTimer=setInterval(()=>refreshScreens(false),500);refreshScreens(true);}
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
