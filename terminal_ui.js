(() => {
  'use strict';
  if (window.ZajelTerminalUI) return;
  let root = null, listTimer = null, screenTimer = null, resizeObserver = null, broadcastPanel = null, broadcastBackdrop = null;
  let round = null, roundTimer = null, roundBusy = false, webLast = '', webSame = 0, webPosted = '';
  let activeSlot = 0, agents = [], slots = [], layout = 1, notify = false, guard = true, hist = 3000, listBusy = false, builtLayout = 0, sendChain = Promise.resolve();
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  let termFont = (() => { try { const n = Number(localStorage.getItem('zajel_term_font')); return Number.isFinite(n) && n >= 9 && n <= 18 ? n : 12.5; } catch (_) { return 12.5; } })();
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
  // السؤال يُعرف من العلامة التي يضعها الوكيل أوله (❯ عند Claude وHermes، › عند Codex، > عند Antigravity)، والإجابة من علامتها (⏺ ● •)
  const Q_RE=/^\s{0,3}(?:[│|]\s*)?[❯›>]\s/, A_RE=/^\s{0,3}[⏺●•]\s/, EDGE_RE=/^\s*[─━╭╰┌└]/;
  function ansiHtml(input) {
    const T=window.ZajelTermTheme, pal=T?T.palette():palette;
    const fg=c=>T?T.fixFg(c):c, bg=c=>T?T.fixBg(c):c;
    const c256=n=>n<16?pal[n]:color256(n);
    let style={}, out='', mode='', qOpen=false;
    const wrap = chunk => { if(!chunk)return ''; let css=[]; const f=style.fg&&fg(style.fg), b=style.bg&&bg(style.bg); if(f)css.push('color:'+f); if(b)css.push('background-color:'+b); if(style.bold)css.push('font-weight:bold'); if(style.dim)css.push('opacity:.65'); if(style.italic)css.push('font-style:italic'); if(style.underline)css.push('text-decoration:underline'); if(style.inverse)css.push('filter:invert(1)'); return `<span${css.length?' style="'+css.join(';')+'"':''}>${esc(chunk)}</span>`; };
    const line = text => { let o='', last=0, m; const re=/\x1b\[([0-9;]*)m/g;
      while((m=re.exec(text))){o+=wrap(text.slice(last,m.index));last=re.lastIndex;const a=(m[1]||'0').split(';').map(x=>Number(x||0));for(let i=0;i<a.length;i++){const n=a[i];if(n===0)style={};else if(n===1)style.bold=true;else if(n===2)style.dim=true;else if(n===3)style.italic=true;else if(n===4)style.underline=true;else if(n===7)style.inverse=true;else if(n===22){style.bold=false;style.dim=false;}else if(n===23)style.italic=false;else if(n===24)style.underline=false;else if(n===27)style.inverse=false;else if(n===39)delete style.fg;else if(n===49)delete style.bg;else if(n>=30&&n<=37)style.fg=pal[n-30];else if(n>=90&&n<=97)style.fg=pal[n-90+8];else if(n>=40&&n<=47)style.bg=pal[n-40];else if(n>=100&&n<=107)style.bg=pal[n-100+8];else if((n===38||n===48)&&a[i+1]===5){style[n===38?'fg':'bg']=c256(a[i+2]||0);i+=2;}else if((n===38||n===48)&&a[i+1]===2){style[n===38?'fg':'bg']=cssColor(a[i+2]||0,a[i+3]||0,a[i+4]||0);i+=4;}}}
      return o+wrap(text.slice(last)); };
    const rows=String(input||'').split('\n');
    const plainRows=rows.map(row=>row.replace(/\x1b\[[0-9;]*m/g,'')), lastText=(()=>{for(let k=plainRows.length-1;k>=0;k--)if(plainRows[k].trim())return k;return 0;})(),start=Math.max(0,lastText-25), numbered=new Map(), cursorLines=[];
    for(let i=start;i<rows.length;i++){
      const m=plainRows[i].match(/^\s*(?:[❯›>●]\s*)?(\d{1,2})[.)]\s+\S/);
      if(m)numbered.set(i,Number(m[1]));
      if(/^\s*(?:[│┃|]\s*)?[❯›>]\s+\S/.test(plainRows[i]))cursorLines.push(i);
    }
    let unnumbered=new Set(), curLine=-1, curMode='';
    const colOf=(p,isCur)=>{const m=isCur?p.match(/^\s*(?:[│┃|]\s*)?[❯›>]\s+/):p.match(/^\s*(?:[│┃|]\s*)?/);return m?m[0].length:p.search(/\S/);};
    const buildBlock=(ci,accept)=>{const col=colOf(plainRows[ci],true),ok=i=>{const p=plainRows[i];return p&&p.trim()&&!EDGE_RE.test(p)&&colOf(p,false)===col&&(!accept||accept(i));};const b=[ci];for(let i=ci+1;i<rows.length&&ok(i)&&b.length<30;i++)b.push(i);for(let i=ci-1;i>=0&&ok(i)&&b.length<30;i--)b.unshift(i);return b;};
    {const cands=cursorLines.map(ci=>({ci,block:buildBlock(ci)})).filter(x=>x.block.length>1);   // مع مربع الاختيار يوجد ❯ آخر في سطر الإدخال؛ نأخذ صاحب أكبر كتلة
      cands.sort((p,q)=>q.block.length-p.block.length);
      const top=cands[0];
      if(top&&(cands.length===1||top.block.length>=3&&top.block.length>cands[1].block.length)){unnumbered=new Set(top.block);curLine=top.ci;curMode=top.block.length>=3?'mark':'weak';}}
    if(curLine<0){
      // القوائم المنبثقة (مثل / في Hermes) لا تضع علامة ❯: كل الصفوف بخلفية واحدة والصف المختار معكوس الألوان أو بخلفية مختلفة.
      // نقرأ حالة أول حرف مرئي في كل سطر: خلفية؟ عكس ألوان؟
      const st=row=>{let bgv='',inv=false,last=0,m;const re=/\x1b\[([0-9;]*)m/g;const seen=t=>/[^\s│┃|]/.test(t);
        while((m=re.exec(row))){if(seen(row.slice(last,m.index)))return {bg:bgv,inv};last=re.lastIndex;const a=(m[1]||'0').split(';').map(x=>Number(x||0));for(let i=0;i<a.length;i++){const n=a[i];if(n===0){bgv='';inv=false;}else if(n===7)inv=true;else if(n===27)inv=false;else if(n===49)bgv='';else if((n>=40&&n<=47)||(n>=100&&n<=107))bgv=String(n);else if(n===48){const k=a[i+1]===5?2:a[i+1]===2?4:0;bgv=a.slice(i,i+1+k).join(',');i+=k;}else if(n===38)i+=a[i+1]===5?2:a[i+1]===2?4:0;}}
        return seen(row.slice(last))?{bg:bgv,inv}:null;};
      let run=[];const runs=[];
      for(let i=start;i<rows.length-1;i++){const x=plainRows[i].trim()?st(rows[i]):null;if(x&&(x.bg||x.inv))run.push({i,...x});else{if(run.length)runs.push(run);run=[];}}
      if(run.length)runs.push(run);
      runs.sort((p,q)=>q.length-p.length);
      const r=runs[0];
      if(r&&r.length>=3&&r.length<=30){
        const inv=r.filter(x=>x.inv);let cur=-1;
        if(inv.length===1)cur=inv[0].i;
        else if(!inv.length){const cnt=new Map();r.forEach(x=>cnt.set(x.bg,(cnt.get(x.bg)||0)+1));const maj=[...cnt.entries()].sort((p,q)=>q[1]-p[1])[0];const odd=r.filter(x=>x.bg!==maj[0]);if(odd.length===1&&maj[1]>=2)cur=odd[0].i;}
        // بلا صف مختار لا نعدّها قائمة إلا إن كانت صفوفها أوامر أو إشارات (/ أو @)؛ فمربع الإدخال بخلفية أيضًا ولا نخطف تمريره
        const cmdRows=r.every(x=>/^\s*[\/@]\S/.test(plainRows[x.i]));
        if(cur>=0||cmdRows){unnumbered=new Set(r.map(x=>x.i));curLine=cur;curMode='hl';}
      }
    }
    rows.forEach((row,i)=>{
      const plain=row.replace(/\x1b\[[0-9;]*m/g,''), nl=i<rows.length-1?'\n':'';
      if(Q_RE.test(plain))mode='q';
      else if(A_RE.test(plain))mode='a';
      else if(EDGE_RE.test(plain))mode='';
      else if(mode==='q'&&!/^\s{2}\S/.test(plain))mode='';   // سطر السؤال التالي يبدأ بفراغين؛ غير ذلك نهاية السؤال
      if(qOpen&&mode!=='q'){out+='</span>';qOpen=false;}
      if(mode==='q'&&!qOpen){out+='<span class="tt-q">';qOpen=true;}
      const h=line(row);
      const option=numbered.has(i)?' data-opt-number="'+numbered.get(i)+'"':(unnumbered.has(i)?' data-opt-list="1" data-opt-menu="'+curMode+'"'+(i===curLine?' data-opt-cur="1"':''):'');
      out+='<span data-line="'+i+'"'+option+(option?' role="button" tabindex="-1"':'')+'>'+(mode==='a'?'<span class="tt-a">'+h+'</span>':h)+'</span>'+nl;
    });
    return out+(qOpen?'</span>':'');
  }
  let themeHooked=false;
  function applyTheme(){const T=window.ZajelTermTheme;if(!T||!root)return;T.apply(root);if(themeHooked)return;themeHooked=true;T.onChange(()=>{if(root)T.apply(root);slots.forEach(x=>{x.hash='';});refreshScreens(true);});}
  const agentColors = { claude: '#c96442', codex: '#3a4a5c', hermes: '#6b4bb8', agy: '#2f6fd6', opencode: '#2a8a72', pi: '#ec4899', grok: '#111827', perplexity: '#20808d', shell: '#374151', shell2: '#374151' };
  // رمز يدلّ على كل وكيل في الشريط (المطويّ خاصة)؛ الوكيل الذي يضيفه المستخدم يأخذ أول حرف من اسمه
  const agentGlyphs = { shell: '▸_', shell2: '▸2', claude: '✻', codex: '⬡', hermes: '☤', agy: '✦', opencode: '{}', pi: 'π', grok: '◐', perplexity: '⁂' };
  const glyphOf = (id, name) => agentGlyphs[id] || String(name || id || '?').trim().charAt(0).toUpperCase();
  const colorOf = id => {
    if (agentColors[id]) return agentColors[id];
    let h = 0;
    for (let i = 0; i < id.length; i++) h = ((h << 5) - h + id.charCodeAt(i)) | 0;
    const p = ['#c96442', '#3a4a5c', '#6b4bb8', '#2f6fd6', '#2a8a72', '#ec4899', '#0f8f9a', '#d97706'];
    return p[Math.abs(h) % p.length];
  };
  function stateColor(s){return s==='working'?'#22c55e':s==='waiting'?'#eab308':s==='shell'?'#ef4444':'#94a3b8';}
  let fastUntil=0,lastFull=0,screenBusy=false;
  function kick(){fastUntil=Date.now()+2500;}
  function send(slot, payload){kick();sendChain=sendChain.then(()=>req('send',{id:slot.id,...payload})).then(()=>{setMsg(slot,'');for(const d of [0,70,180,400])setTimeout(()=>{if(!screenBusy)refreshScreens(false,slot);},d);}).catch(e=>setMsg(slot,'تعذّر الإرسال: '+(e&&e.message||'خطأ'),true));}

  let barState = (() => { try { return localStorage.getItem('zajel_term_bar_state') || 'expanded'; } catch (_) { return 'expanded'; } })();
  let barPos = (() => { try { return localStorage.getItem('zajel_term_bar_pos') || 'side'; } catch (_) { return 'side'; } })();
  let shortcuts = [];
  let shortcutsBusy = false;
  let confirmRestart = null;
  let confirmRemove = null;
  let addingAgent = false;
  let savingCwd = null;
  let runningShortcutNotice = null;

  function showToast(text) {
    if (!root) return;
    let t = root.querySelector('.as-term-toast');
    if (!t) {
      t = document.createElement('div');
      t.className = 'as-term-toast';
      t.setAttribute('role', 'status');
      t.setAttribute('aria-live', 'polite');
      t.style.cssText = 'position:absolute;bottom:16px;left:50%;transform:translateX(-50%);background:var(--term-ink,#fff);color:var(--rail,#111);padding:6px 14px;border-radius:8px;font-size:12px;z-index:99999;box-shadow:0 4px 16px rgba(0,0,0,0.4);transition:opacity .2s;pointer-events:none;opacity:0;';
      root.appendChild(t);
    }
    t.textContent = text;
    t.style.opacity = '1';
    clearTimeout(t.timer);
    t.timer = setTimeout(() => { if (t) t.style.opacity = '0'; }, Math.max(2200, String(text).length * 70));
  }

  async function refreshShortcuts() {
    if (shortcutsBusy) return;
    shortcutsBusy = true;
    try {
      const res = await fetch('/api/term/custom');
      if (res.ok) {
        const d = await res.json();
        shortcuts = Array.isArray(d.shortcuts) ? d.shortcuts : [];
      }
    } catch (_) {
    } finally {
      shortcutsBusy = false;
    }
  }

  function updateActiveCardHighlight() {
    if (!root) return;
    const curSlot = slots[Math.min(activeSlot, Math.max(0, slots.length - 1))];
    const activeId = curSlot?.id || '';
    root.querySelectorAll('.rail .agent[data-agent-id]').forEach(c => {
      c.classList.toggle('sel', c.dataset.agentId === activeId);
    });
  }

  function selectAgentForActiveSlot(id) {
    const sl = slots[Math.min(activeSlot, Math.max(0, slots.length - 1))];
    if (!sl) return;
    sl.id = id;
    sl.hash = '';
    updateSlotIdentity(sl);
    if (sl.select) sl.select.value = id;
    refreshScreens(true);
    updateActiveCardHighlight();
  }

  // لا يُعاد رسم الشريط وأنت تكتب في نموذج داخله أو تمرّ عليه بالفأرة (كانت القيم تُمسح كل ثانيتين)
  function railBusy() {
    const rail = root && root.querySelector('.rail');
    if (!rail) return false;
    if (addingAgent || savingCwd || confirmRestart || confirmRemove || runningShortcutNotice) return true;
    const ae = document.activeElement;
    return !!(ae && rail.contains(ae) && /^(INPUT|SELECT|TEXTAREA)$/.test(ae.tagName)) || rail.matches(':hover');
  }

  // اسم الوكيل يظهر فور مرور المؤشر عليه في الشريط المطوي. التلميح يُرسم فوق كل شيء
  // (position:fixed)، لأن قائمة الشريط تقصّ ما يخرج عن حدودها.
  function bindRailTips(rail) {
    if (rail._tips) return;
    rail._tips = true;
    let f = null;
    const hide = () => { if (f) { f.remove(); f = null; } };
    rail.addEventListener('mouseover', e => {
      const card = e.target.closest('.agent');
      const app = root && root.querySelector('.as-terminal');
      const tip = card && card.querySelector('.tip');
      if (!card || !tip || !app || app.dataset.state !== 'collapsed') { hide(); return; }
      if (f && f._card === card) return;
      hide();
      f = document.createElement('div'); f._card = card; f.className = 'rail-flytip'; f.setAttribute('role', 'tooltip');
      f.textContent = tip.textContent;
      (document.getElementById('zajel-term-window') || document.body).appendChild(f);   // في البرنامج المستقل كل ما خارج النافذة مخفي
      const r = card.getBoundingClientRect();
      if (app.dataset.pos === 'top') { f.style.left = Math.max(4, r.left + r.width / 2 - f.offsetWidth / 2) + 'px'; f.style.top = (r.bottom + 6) + 'px'; }
      else { f.style.left = Math.max(4, r.left - f.offsetWidth - 8) + 'px'; f.style.top = (r.top + r.height / 2 - f.offsetHeight / 2) + 'px'; }
    });
    rail.addEventListener('mouseleave', hide);
    rail.addEventListener('click', hide);
  }

  // تلميح سريع لأزرار نافذة الطرفيات: تلميح النظام (title) يتأخر نحو ثانية، فنُظهر الاسم بعد لحظة قصيرة
  (() => {
    if (window.__zajelFastTips) return;
    window.__zajelFastTips = true;
    let tip = null, timer = 0, cur = null;
    const hide = () => { clearTimeout(timer); cur = null; if (tip) { tip.remove(); tip = null; } };
    document.addEventListener('mouseover', e => {
      const el = e.target.closest && e.target.closest('#zajel-term-window [title], #zajel-term-window [data-tip], .as-terminal-ui [title], .as-terminal-ui [data-tip]');
      if (!el || el.closest('.rail .agent')) { if (!el) hide(); return; }
      if (el.title) { el.dataset.tip = el.title; el.removeAttribute('title'); }      // يمنع تلميح النظام البطيء
      if (tip && tip._el === el) return;
      hide(); cur = el;
      timer = setTimeout(() => {
        if (!el.isConnected || !el.dataset.tip) return;
        tip = document.createElement('div'); tip._el = el; tip.className = 'rail-flytip'; tip.setAttribute('role', 'tooltip');
        tip.textContent = el.dataset.tip;
        (document.getElementById('zajel-term-window') || document.body).appendChild(tip);
        const r = el.getBoundingClientRect();
        tip.style.left = Math.max(4, Math.min(innerWidth - tip.offsetWidth - 4, r.left + r.width / 2 - tip.offsetWidth / 2)) + 'px';
        tip.style.top = (r.bottom + 6 + tip.offsetHeight > innerHeight ? r.top - tip.offsetHeight - 6 : r.bottom + 6) + 'px';
      }, 120);
    });
    document.addEventListener('mouseout', e => { const el = tip ? tip._el : cur; if (el && e.relatedTarget && el.contains(e.relatedTarget)) return; if (el && !el.contains(e.target)) return; hide(); });
    document.addEventListener('mousedown', hide, true);
  })();

  function renderRail() {
    if (!root) return;
    const rail = root.querySelector('.rail');
    if (!rail) return;
    const app = root.querySelector('.as-terminal');
    if (app) {
      app.dataset.state = barState;
      app.dataset.pos = barPos;
    }
    bindRailTips(rail);
    document.querySelectorAll('.rail-flytip').forEach(x => x.remove());
    const keepScroll = rail.querySelector('.rail-list')?.scrollTop || 0;
    rail.replaceChildren();

    const head = document.createElement('div');
    head.className = 'rail-head';

    const lbl = document.createElement('span');
    lbl.className = 'lbl';
    lbl.textContent = 'الوكلاء · ' + agents.length;
    head.appendChild(lbl);

    const headActs = document.createElement('div');
    headActs.className = 'rail-head-acts';

    const posBtn = document.createElement('button');
    posBtn.type = 'button';
    posBtn.className = 'rail-btn-pos';
    const posTitle = barPos === 'side' ? 'انقل الشريط إلى الأعلى' : 'انقل الشريط إلى الجانب';
    posBtn.title = posTitle;
    posBtn.setAttribute('aria-label', posTitle);
    posBtn.textContent = barPos === 'side' ? 'علوي' : 'جانبي';
    posBtn.onclick = () => {
      barPos = barPos === 'side' ? 'top' : 'side';
      try { localStorage.setItem('zajel_term_bar_pos', barPos); } catch (_) {}
      if (app) app.dataset.pos = barPos;
      renderRail();
    };
    headActs.appendChild(posBtn);

    const toggleBtn = document.createElement('button');
    toggleBtn.type = 'button';
    toggleBtn.className = 'rail-toggle';
    const exp = barState === 'expanded';
    toggleBtn.textContent = exp ? '⇥' : '⇤';
    const togTitle = exp ? 'اطوِ الشريط' : 'وسّع الشريط';
    toggleBtn.title = togTitle;
    toggleBtn.setAttribute('aria-label', togTitle);
    toggleBtn.onclick = () => {
      barState = barState === 'expanded' ? 'collapsed' : 'expanded';
      try { localStorage.setItem('zajel_term_bar_state', barState); } catch (_) {}
      if (app) app.dataset.state = barState;
      renderRail();
    };
    headActs.appendChild(toggleBtn);

    head.appendChild(headActs);
    rail.appendChild(head);

    const list = document.createElement('div');
    list.className = 'rail-list';
    rail.appendChild(list);
    queueMicrotask(() => { list.scrollTop = keepScroll; });   // إعادة الرسم الدورية لا تُرجع القائمة إلى أولها

    const curSlot = slots[Math.min(activeSlot, Math.max(0, slots.length - 1))];
    const activeAgentId = curSlot?.id || agents[0]?.id || 'shell';

    agents.forEach(a => {
      const isSel = curSlot && curSlot.id === a.id;
      const card = document.createElement('div');
      card.className = 'agent' + (isSel ? ' sel' : '');
      card.dataset.agentId = a.id;
      card.tabIndex = 0;
      card.setAttribute('role', 'button');
      const stDot = a.state === 'working' ? 'working' : (a.state === 'waiting' ? 'waiting' : ((a.health && a.health.status && a.health.status !== 'ok') || a.state === 'broken' || a.state === 'error' ? 'broken' : 'stopped'));
      const stLabel = a.label || a.state || '';
      card.setAttribute('aria-label', a.name + ' · ' + stLabel);

      const av = document.createElement('div');
      av.className = 'av';
      av.style.background = colorOf(a.id);
      const ch = glyphOf(a.id, a.name);
      const dot = document.createElement('span');
      dot.className = 'dot ' + stDot;
      av.append(document.createTextNode(ch), dot);

      const meta = document.createElement('div');
      meta.className = 'meta';
      const strong = document.createElement('strong');
      strong.textContent = a.name;
      if (a.custom) {
        const badge = document.createElement('span');
        badge.className = 'new-badge';
        badge.textContent = 'مخصّص';
        strong.appendChild(badge);
      }
      const small = document.createElement('small');
      let subTxt = a.installed === false ? 'غير مثبّت' : stLabel;
      if (a.health && a.health.checking) subTxt += ' · يفحص…';
      else if (a.health && a.health.label && a.health.status !== 'ok') subTxt += ' · ' + a.health.label;
      small.textContent = subTxt;
      meta.append(strong, small);

      const tip = document.createElement('span');
      tip.className = 'tip';
      tip.textContent = a.name + ' · ' + subTxt;

      card.append(av, meta, tip);

      if (confirmRestart === a.id) {
        const row = document.createElement('div');
        row.className = 'inline-confirm';
        row.setAttribute('role', 'alert');
        const msg = document.createElement('span');
        msg.className = 'confirm-msg';
        msg.textContent = 'هل تعيد تشغيل ' + a.name + '؟';
        const btns = document.createElement('div');
        btns.className = 'confirm-btns';
        const bYes = document.createElement('button');
        bYes.type = 'button';
        bYes.className = 'btn pri';
        bYes.textContent = 'نعم، أعد';
        bYes.setAttribute('aria-label', 'تأكيد إعادة تشغيل ' + a.name);
        bYes.onclick = async (ev) => {
          ev.stopPropagation();
          confirmRestart = null;
          try {
            await req('restart', { id: a.id });
            showAgent(a.id);
            setTimeout(refreshList, 250);
          } catch (e) {
            showToast(e.message || 'تعذّرت إعادة التشغيل');
          }
          renderRail();
        };
        const bNo = document.createElement('button');
        bNo.type = 'button';
        bNo.className = 'btn';
        bNo.textContent = 'إلغاء';
        bNo.setAttribute('aria-label', 'إلغاء');
        bNo.onclick = (ev) => {
          ev.stopPropagation();
          confirmRestart = null;
          renderRail();
        };
        btns.append(bYes, bNo);
        row.append(msg, btns);
        card.appendChild(row);
      } else if (confirmRemove === a.id) {
        const row = document.createElement('div');
        row.className = 'inline-confirm';
        row.setAttribute('role', 'alert');
        const msg = document.createElement('span');
        msg.className = 'confirm-msg';
        msg.textContent = 'هل تحذف ' + a.name + '؟';
        const btns = document.createElement('div');
        btns.className = 'confirm-btns';
        const bYes = document.createElement('button');
        bYes.type = 'button';
        bYes.className = 'btn danger';
        bYes.textContent = 'نعم، احذف';
        bYes.setAttribute('aria-label', 'تأكيد حذف ' + a.name);
        bYes.onclick = async (ev) => {
          ev.stopPropagation();
          confirmRemove = null;
          try {
            await req('agent_remove', { id: a.id });
            await refreshList();
          } catch (e) {
            showToast(e.message || 'تعذّر حذف الوكيل');
          }
          renderRail();
        };
        const bNo = document.createElement('button');
        bNo.type = 'button';
        bNo.className = 'btn';
        bNo.textContent = 'إلغاء';
        bNo.setAttribute('aria-label', 'إلغاء');
        bNo.onclick = (ev) => {
          ev.stopPropagation();
          confirmRemove = null;
          renderRail();
        };
        btns.append(bYes, bNo);
        row.append(msg, btns);
        card.appendChild(row);
      } else {
        const acts = document.createElement('div');
        acts.className = 'acts';

        const bStart = document.createElement('button');
        bStart.type = 'button';
        bStart.className = 'btn';
        bStart.textContent = '▶';
        bStart.disabled = a.installed === false;
        bStart.title = a.installed === false ? 'غير مثبّت' : 'تشغيل';
        bStart.setAttribute('aria-label', 'تشغيل ' + a.name);
        bStart.onclick = async (ev) => {
          ev.stopPropagation();
          try {
            await req('start', { id: a.id });
            showAgent(a.id);
            setTimeout(refreshList, 250);
          } catch (e) {
            showToast(e.message || 'تعذّر التشغيل');
          }
        };
        acts.appendChild(bStart);

        const bRestart = document.createElement('button');
        bRestart.type = 'button';
        bRestart.className = 'btn';
        bRestart.textContent = '↻';
        bRestart.title = 'إعادة تشغيل';
        bRestart.setAttribute('aria-label', 'إعادة تشغيل ' + a.name);
        bRestart.onclick = (ev) => {
          ev.stopPropagation();
          confirmRestart = a.id;
          confirmRemove = null;
          renderRail();
        };
        acts.appendChild(bRestart);

        const bCheck = document.createElement('button');
        bCheck.type = 'button';
        bCheck.className = 'btn';
        bCheck.textContent = '✓';
        bCheck.title = 'فحص الجاهزية';
        bCheck.setAttribute('aria-label', 'فحص جاهزية ' + a.name);
        bCheck.onclick = async (ev) => {
          ev.stopPropagation();
          try {
            await req('health', { id: a.id, check: true, force: true });
            refreshList();
          } catch (e) {
            showToast(e.message || 'تعذّر الفحص');
          }
        };
        acts.appendChild(bCheck);

        if (a.custom) {
          const bRem = document.createElement('button');
          bRem.type = 'button';
          bRem.className = 'btn btn-remove';
          bRem.textContent = '✕';
          bRem.title = 'حذف الوكيل';
          bRem.setAttribute('aria-label', 'حذف ' + a.name);
          bRem.onclick = (ev) => {
            ev.stopPropagation();
            confirmRemove = a.id;
            confirmRestart = null;
            renderRail();
          };
          acts.appendChild(bRem);
        }
        card.appendChild(acts);
      }

      card.onclick = (ev) => {
        if (ev.target.closest('button') || ev.target.closest('.inline-confirm')) return;
        showAgent(a.id);
      };
      card.onkeydown = (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          if (!ev.target.closest('button') && !ev.target.closest('input')) {
            ev.preventDefault();
            showAgent(a.id);
          }
        }
      };
      list.appendChild(card);
    });

    if (addingAgent) {
      const form = document.createElement('form');
      form.className = 'agent-form-inline';
      const fTitle = document.createElement('div');
      fTitle.style.fontWeight = '600';
      fTitle.textContent = 'إضافة وكيل جديد';

      const lName = document.createElement('label');
      lName.textContent = 'الاسم:';
      const inpName = document.createElement('input');
      inpName.type = 'text';
      inpName.required = true;
      inpName.placeholder = 'مثال: Grok';
      inpName.setAttribute('aria-label', 'اسم الوكيل');
      lName.appendChild(inpName);

      const lCmd = document.createElement('label');
      lCmd.textContent = 'الأمر في الطرفية:';
      const inpCmd = document.createElement('input');
      inpCmd.type = 'text';
      inpCmd.required = true;
      inpCmd.dir = 'ltr';
      inpCmd.placeholder = 'مثال: grok';
      inpCmd.setAttribute('aria-label', 'الأمر في الطرفية');
      lCmd.appendChild(inpCmd);

      const lAsk = document.createElement('label');
      lAsk.textContent = 'أمر الاستدعاء المباشر (اختياري):';
      const inpAsk = document.createElement('input');
      inpAsk.type = 'text';
      inpAsk.dir = 'ltr';
      inpAsk.placeholder = 'مثال: grok -p';
      inpAsk.setAttribute('aria-label', 'أمر الاستدعاء المباشر');
      lAsk.appendChild(inpAsk);

      const fErr = document.createElement('div');
      fErr.style.color = 'var(--bad)';
      fErr.style.fontSize = '11px';
      fErr.hidden = true;

      const fActs = document.createElement('div');
      fActs.className = 'form-acts';
      const bSub = document.createElement('button');
      bSub.type = 'submit';
      bSub.className = 'btn pri';
      bSub.textContent = 'إضافة';
      bSub.setAttribute('aria-label', 'حفظ الوكيل الجديد');
      const bCan = document.createElement('button');
      bCan.type = 'button';
      bCan.className = 'btn';
      bCan.textContent = 'إلغاء';
      bCan.setAttribute('aria-label', 'إلغاء إضافة الوكيل');
      bCan.onclick = () => { addingAgent = false; renderRail(); };
      fActs.append(bSub, bCan);

      form.onsubmit = async (ev) => {
        ev.preventDefault();
        fErr.hidden = true;
        const name = inpName.value.trim();
        const cmd = inpCmd.value.trim();
        const ask = inpAsk.value.trim();
        if (!name || !cmd) return;
        try {
          const res = await req('agent_add', { name, cmd, ask: ask || undefined });
          if (res && res.error) {
            fErr.textContent = res.error;
            fErr.hidden = false;
          } else {
            addingAgent = false;
            await refreshList();
          }
        } catch (e) {
          fErr.textContent = e.message || 'تعذّرت الإضافة';
          fErr.hidden = false;
        }
      };

      form.append(fTitle, lName, lCmd, lAsk, fErr, fActs);
      list.appendChild(form);
    } else {
      const addCard = document.createElement('div');
      addCard.className = 'agent add';
      addCard.tabIndex = 0;
      addCard.setAttribute('role', 'button');
      addCard.setAttribute('aria-label', 'أضف وكيلًا');
      const av = document.createElement('div');
      av.className = 'av';
      av.textContent = '＋';
      const meta = document.createElement('div');
      meta.className = 'meta';
      const strong = document.createElement('strong');
      strong.textContent = 'أضف وكيلًا';
      const small = document.createElement('small');
      small.textContent = 'اسم + الأمر في الطرفية';
      meta.append(strong, small);
      const tip = document.createElement('span');
      tip.className = 'tip';
      tip.textContent = 'أضف وكيلًا جديدًا';
      addCard.append(av, meta, tip);
      addCard.onclick = () => {
        if (barState === 'collapsed') {
          barState = 'expanded';
          try { localStorage.setItem('zajel_term_bar_state', 'expanded'); } catch (_) {}
        }
        addingAgent = true;
        savingCwd = null;
        renderRail();
      };
      addCard.onkeydown = (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          addCard.click();
        }
      };
      list.appendChild(addCard);
    }

    const sep = document.createElement('div');
    sep.className = 'sep';
    list.appendChild(sep);

    const secHead = document.createElement('div');
    secHead.className = 'rail-sec-head';
    const secLbl = document.createElement('span');
    secLbl.className = 'lbl';
    secLbl.textContent = 'الاختصارات';
    secHead.appendChild(secLbl);
    list.appendChild(secHead);

    shortcuts.forEach(s => {
      const scCard = document.createElement('div');
      scCard.className = 'agent shortcut-card';
      scCard.tabIndex = 0;
      scCard.setAttribute('role', 'button');
      scCard.setAttribute('aria-label', s.name + ' · ' + s.path);

      const av = document.createElement('div');
      av.className = 'av';
      if (s.kind === 'agent') {
        av.style.background = colorOf(s.agent || '');
        const ch = glyphOf(s.agent, (agents.find(x => x.id === s.agent) || {}).name);
        const badge = document.createElement('span');
        badge.className = 'sc-badge';
        badge.textContent = '📁';
        av.append(document.createTextNode(ch), badge);
      } else {
        av.style.background = '#4b5563';
        av.textContent = '📁';
      }

      const meta = document.createElement('div');
      meta.className = 'meta';
      const strong = document.createElement('strong');
      strong.textContent = s.name;
      const small = document.createElement('small');
      small.textContent = s.path;
      meta.append(strong, small);

      const tip = document.createElement('span');
      tip.className = 'tip';
      tip.textContent = s.name + (s.kind === 'agent' ? ' (' + s.agent + ')' : '') + ' · ' + s.path;

      const bRem = document.createElement('button');
      bRem.type = 'button';
      bRem.className = 'btn btn-remove';
      bRem.textContent = '✕';
      bRem.title = 'حذف الاختصار';
      bRem.setAttribute('aria-label', 'حذف الاختصار ' + s.name);
      bRem.onclick = async (ev) => {
        ev.stopPropagation();
        try {
          await req('shortcut_remove', { id: s.id });
          await refreshShortcuts();
          renderRail();
        } catch (e) {
          showToast(e.message || 'تعذّر حذف الاختصار');
        }
      };

      scCard.append(av, meta, tip, bRem);

      if (runningShortcutNotice && runningShortcutNotice.scId === s.id) {
        const notice = document.createElement('div');
        notice.className = 'shortcut-inline-notice';
        notice.setAttribute('role', 'alert');
        const nTxt = document.createElement('div');
        nTxt.textContent = 'الوكيل يعمل الآن؛ هل تود فتحه في طرفية، أم إعادة تشغيله هنا؟';
        const nActs = document.createElement('div');
        nActs.className = 'acts';
        const bShell = document.createElement('button');
        bShell.type = 'button';
        bShell.className = 'btn';
        bShell.textContent = 'افتح في طرفية';
        bShell.setAttribute('aria-label', 'افتح في طرفية');
        bShell.onclick = async (ev) => {
          ev.stopPropagation();
          runningShortcutNotice = null;
          showAgent('shell');
          await req('open_path', { id: 'shell', path: s.path }).catch(() => {});
          refreshScreens(true);
          renderRail();
        };
        const bRestartHere = document.createElement('button');
        bRestartHere.type = 'button';
        bRestartHere.className = 'btn pri';
        bRestartHere.textContent = 'أعد تشغيل الوكيل هنا';
        bRestartHere.setAttribute('aria-label', 'أعد تشغيل الوكيل هنا');
        bRestartHere.onclick = async (ev) => {
          ev.stopPropagation();
          const tgt = runningShortcutNotice.agentId;
          runningShortcutNotice = null;
          await req('restart', { id: tgt, cwd: s.path }).catch(() => {});
          refreshList();
          refreshScreens(true);
          renderRail();
        };
        const bCancelNotice = document.createElement('button');
        bCancelNotice.type = 'button';
        bCancelNotice.className = 'btn';
        bCancelNotice.textContent = 'إلغاء';
        bCancelNotice.setAttribute('aria-label', 'إلغاء');
        bCancelNotice.onclick = (ev) => {
          ev.stopPropagation();
          runningShortcutNotice = null;
          renderRail();
        };
        nActs.append(bShell, bRestartHere, bCancelNotice);
        notice.append(nTxt, nActs);
        scCard.appendChild(notice);
      }

      scCard.onclick = async (ev) => {
        if (ev.target.closest('button') || ev.target.closest('.shortcut-inline-notice')) return;
        runningShortcutNotice = null;
        const targetAgentId = s.kind === 'agent' ? (s.agent || activeAgentId) : activeAgentId;
        if (s.kind === 'agent') {
          showAgent(targetAgentId);
        }
        try {
          const res = await req('open_path', { id: targetAgentId, path: s.path });
          if (res && res.running) {
            runningShortcutNotice = { scId: s.id, agentId: targetAgentId, path: s.path };
            renderRail();
          } else {
            refreshScreens(true);
          }
        } catch (e) {
          showToast(e.message || 'تعذّر فتح المسار');
        }
      };
      scCard.onkeydown = (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          if (!ev.target.closest('button')) {
            ev.preventDefault();
            scCard.click();
          }
        }
      };
      list.appendChild(scCard);
    });

    if (savingCwd) {
      const form = document.createElement('form');
      form.className = 'agent-form-inline';
      const fTitle = document.createElement('div');
      fTitle.style.fontWeight = '600';
      fTitle.textContent = 'حفظ المسار الحالي';

      const defaultName = (savingCwd.path ? savingCwd.path.split('/').filter(Boolean).pop() : '') || 'مجلد';
      const lName = document.createElement('label');
      lName.textContent = 'الاسم:';
      const inpName = document.createElement('input');
      inpName.type = 'text';
      inpName.required = true;
      inpName.value = defaultName;
      inpName.setAttribute('aria-label', 'اسم الاختصار');
      lName.appendChild(inpName);

      const lPath = document.createElement('label');
      lPath.textContent = 'المسار:';
      const inpPath = document.createElement('input');
      inpPath.type = 'text';
      inpPath.required = true;
      inpPath.dir = 'ltr';
      inpPath.value = savingCwd.path || '';
      inpPath.setAttribute('aria-label', 'مسار المجلد');
      lPath.appendChild(inpPath);

      const kGrp = document.createElement('div');
      kGrp.style.display = 'flex';
      kGrp.style.flexDirection = 'column';
      kGrp.style.gap = '4px';
      kGrp.style.margin = '4px 0';

      const rPathLbl = document.createElement('label');
      rPathLbl.style.flexDirection = 'row';
      rPathLbl.style.alignItems = 'center';
      rPathLbl.style.gap = '6px';
      const rPath = document.createElement('input');
      rPath.type = 'radio';
      rPath.name = 'kind';
      rPath.value = 'path';
      rPath.checked = true;
      rPathLbl.append(rPath, document.createTextNode('مسار'));

      const rAgentLbl = document.createElement('label');
      rAgentLbl.style.flexDirection = 'row';
      rAgentLbl.style.alignItems = 'center';
      rAgentLbl.style.gap = '6px';
      const rAgent = document.createElement('input');
      rAgent.type = 'radio';
      rAgent.name = 'kind';
      rAgent.value = 'agent';
      rAgentLbl.append(rAgent, document.createTextNode('الوكيل الحالي (' + activeAgentId + ') في هذا المسار'));

      kGrp.append(rPathLbl, rAgentLbl);

      const fErr = document.createElement('div');
      fErr.style.color = 'var(--bad)';
      fErr.style.fontSize = '11px';
      fErr.hidden = true;

      const fActs = document.createElement('div');
      fActs.className = 'form-acts';
      const bSub = document.createElement('button');
      bSub.type = 'submit';
      bSub.className = 'btn pri';
      bSub.textContent = 'حفظ الاختصار';
      bSub.setAttribute('aria-label', 'حفظ الاختصار');
      const bCan = document.createElement('button');
      bCan.type = 'button';
      bCan.className = 'btn';
      bCan.textContent = 'إلغاء';
      bCan.setAttribute('aria-label', 'إلغاء');
      bCan.onclick = () => { savingCwd = null; renderRail(); };
      fActs.append(bSub, bCan);

      form.onsubmit = async (ev) => {
        ev.preventDefault();
        fErr.hidden = true;
        const name = inpName.value.trim();
        const path = inpPath.value.trim();
        const kind = rAgent.checked ? 'agent' : 'path';
        if (!name || !path) return;
        try {
          const res = await req('shortcut_add', {
            kind,
            name,
            path,
            agent: kind === 'agent' ? activeAgentId : undefined
          });
          if (res && res.error) {
            fErr.textContent = res.error;
            fErr.hidden = false;
          } else {
            savingCwd = null;
            await refreshShortcuts();
            renderRail();
          }
        } catch (e) {
          fErr.textContent = e.message || 'تعذّر حفظ الاختصار';
          fErr.hidden = false;
        }
      };

      form.append(fTitle, lName, lPath, kGrp, fErr, fActs);
      list.appendChild(form);
    } else {
      const saveCard = document.createElement('div');
      saveCard.className = 'agent add save-cwd-btn';
      saveCard.tabIndex = 0;
      saveCard.setAttribute('role', 'button');
      saveCard.setAttribute('aria-label', 'احفظ المسار الحالي');
      const av = document.createElement('div');
      av.className = 'av';
      av.textContent = '⭐';
      const meta = document.createElement('div');
      meta.className = 'meta';
      const strong = document.createElement('strong');
      strong.textContent = 'احفظ المسار الحالي';
      const small = document.createElement('small');
      small.textContent = 'اختصار للمسار أو الوكيل';
      meta.append(strong, small);
      const tip = document.createElement('span');
      tip.className = 'tip';
      tip.textContent = 'احفظ المسار الحالي';
      saveCard.append(av, meta, tip);
      saveCard.onclick = async () => {
        if (barState === 'collapsed') {
          barState = 'expanded';
          try { localStorage.setItem('zajel_term_bar_state', 'expanded'); } catch (_) {}
        }
        addingAgent = false;
        let p = '';
        try {
          const d = await fetch('/api/term/cwd?id=' + encodeURIComponent(activeAgentId)).then(r => r.json());
          if (d && d.ok && d.path) p = d.path;
        } catch (_) {}
        savingCwd = { path: p };
        renderRail();
      };
      saveCard.onkeydown = (ev) => {
        if (ev.key === 'Enter' || ev.key === ' ') {
          ev.preventDefault();
          saveCard.click();
        }
      };
      list.appendChild(saveCard);
    }
  }

  // Carbon modifier bits: cmdKey=256, shiftKey=512, optionKey=2048, controlKey=4096. Label order: ⌃⌥⇧⌘.
  const CODE_TO_KVK = {
    KeyA: 0, KeyS: 1, KeyD: 2, KeyF: 3, KeyH: 4, KeyG: 5, KeyZ: 6, KeyX: 7,
    KeyC: 8, KeyV: 9, KeyB: 11, KeyQ: 12, KeyW: 13, KeyE: 14, KeyR: 15, KeyY: 16,
    KeyT: 17, Digit1: 18, Digit2: 19, Digit3: 20, Digit4: 21, Digit6: 22, Digit5: 23,
    Equal: 24, Digit9: 25, Digit7: 26, Minus: 27, Digit8: 28, Digit0: 29, BracketRight: 30,
    KeyO: 31, KeyU: 32, BracketLeft: 33, KeyI: 34, KeyP: 35, Enter: 36, KeyL: 37,
    KeyJ: 38, Quote: 39, KeyK: 40, Semicolon: 41, Backslash: 42, Comma: 43, Slash: 44,
    KeyN: 45, KeyM: 46, Period: 47, Tab: 48, Space: 49, Backquote: 50,
    F1: 122, F2: 120, F3: 99, F4: 118, F5: 96, F6: 97, F7: 98, F8: 100, F9: 101, F10: 109, F11: 103, F12: 111
  };
  const KVK_TO_LABEL = {};
  for (const [code, kvk] of Object.entries(CODE_TO_KVK)) {
    if (code.startsWith('Key')) KVK_TO_LABEL[kvk] = code.slice(3).toUpperCase();
    else if (code.startsWith('Digit')) KVK_TO_LABEL[kvk] = code.slice(5);
    else if (code === 'Space') KVK_TO_LABEL[kvk] = 'Space';
    else if (code === 'Enter') KVK_TO_LABEL[kvk] = 'Enter';
    else if (code === 'Tab') KVK_TO_LABEL[kvk] = 'Tab';
    else if (code === 'Equal') KVK_TO_LABEL[kvk] = '=';
    else if (code === 'Minus') KVK_TO_LABEL[kvk] = '-';
    else if (code === 'BracketLeft') KVK_TO_LABEL[kvk] = '[';
    else if (code === 'BracketRight') KVK_TO_LABEL[kvk] = ']';
    else if (code === 'Semicolon') KVK_TO_LABEL[kvk] = ';';
    else if (code === 'Quote') KVK_TO_LABEL[kvk] = "'";
    else if (code === 'Backslash') KVK_TO_LABEL[kvk] = '\\';
    else if (code === 'Comma') KVK_TO_LABEL[kvk] = ',';
    else if (code === 'Period') KVK_TO_LABEL[kvk] = '.';
    else if (code === 'Slash') KVK_TO_LABEL[kvk] = '/';
    else if (code === 'Backquote') KVK_TO_LABEL[kvk] = '`';
    else if (/^F\d+$/.test(code)) KVK_TO_LABEL[kvk] = code;
  }
  function formatHotkeyLabel(hk) {
    if (!hk || hk.key === -1 || hk.key == null) return 'بلا اختصار';
    const mods = Number(hk.mods) || 0;
    let s = '';
    if (mods & 4096) s += '⌃';
    if (mods & 2048) s += '⌥';
    if (mods & 512) s += '⇧';
    if (mods & 256) s += '⌘';
    const kLabel = KVK_TO_LABEL[hk.key] != null ? KVK_TO_LABEL[hk.key] : String(hk.key);
    return (s ? s + ' ' : '') + kLabel;
  }

  let hotkeyBtnRef = null;
  let hotkeyPanel = null;
  function updateHotkeyUI() {
    if (!hotkeyBtnRef) return;
    const isTerminalApp = window.ZajelNative?.app === 'terminal';
    hotkeyBtnRef.style.display = isTerminalApp ? 'inline-flex' : 'none';
    if (isTerminalApp) {
      hotkeyBtnRef.textContent = '⌨';   // زر صغير؛ الاختصار الحالي في التلميح
      hotkeyBtnRef.title = hotkeyBtnRef.ariaLabel = 'مفتاح الاستدعاء: ' + formatHotkeyLabel(window.ZajelNative?.hotkey) + ' — اضغط لتغييره';
      hotkeyBtnRef.title = 'تغيير اختصار استدعاء الطرفية';
      hotkeyBtnRef.setAttribute('aria-label', 'تغيير اختصار استدعاء الطرفية');
    }
  }
  window.addEventListener('zajel-native', updateHotkeyUI);

  function closeHotkeyPanel() {
    if (!hotkeyPanel) return;
    hotkeyPanel.remove();
    hotkeyPanel = null;
  }

  function openHotkeyPanel() {
    closeHotkeyPanel();
    const winEl = root?.closest('#zajel-term-window') || document.getElementById('zajel-term-window') || root || document.body;

    const backdrop = document.createElement('div');
    backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:100006;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(2px);padding:14px;box-sizing:border-box;';
    backdrop.onclick = (e) => { if (e.target === backdrop) { closeHotkeyPanel(); cleanup(); } };

    const panel = document.createElement('div');
    panel.dir = 'rtl';
    panel.style.cssText = 'background:var(--panel,#182230);color:var(--ink,#fff);border:1px solid var(--line,#24344a);border-radius:12px;padding:18px 20px;box-shadow:0 16px 48px rgba(0,0,0,0.6);display:flex;flex-direction:column;gap:12px;width:min(400px, 92vw);box-sizing:border-box;text-align:center;font-size:13px;';

    const title = document.createElement('div');
    title.style.cssText = 'font-size:14px;font-weight:700;line-height:1.4;';
    title.textContent = 'اضغط الاختصار الجديد الآن (مع ⌘ أو ⌥ أو ⌃)';

    const curView = document.createElement('div');
    curView.style.cssText = 'font-size:12.5px;color:var(--term-dim,#7f93a8);padding:6px;background:var(--bg,#101318);border-radius:6px;border:1px dashed var(--line,#24344a);';
    curView.textContent = 'الاختصار الحالي: ' + formatHotkeyLabel(window.ZajelNative?.hotkey);

    const btns = document.createElement('div');
    btns.style.cssText = 'display:flex;gap:8px;justify-content:center;margin-top:4px;';

    const bNone = document.createElement('button');
    bNone.type = 'button';
    bNone.className = 'btn';
    bNone.textContent = 'بلا اختصار';
    bNone.onclick = () => {
      const hk = { key: -1, mods: 0 };
      try { window.webkit?.messageHandlers?.zajel?.postMessage({ hotkey: hk }); } catch (_) {}
      if (window.ZajelNative) window.ZajelNative.hotkey = hk;
      closeHotkeyPanel();
      cleanup();
      updateHotkeyUI();
      showToast('تم إلغاء اختصار الاستدعاء');
    };

    const bCancel = document.createElement('button');
    bCancel.type = 'button';
    bCancel.className = 'btn';
    bCancel.textContent = 'إلغاء';
    bCancel.onclick = () => {
      closeHotkeyPanel();
      cleanup();
    };

    btns.append(bNone, bCancel);
    panel.append(title, curView, btns);
    backdrop.appendChild(panel);
    winEl.appendChild(backdrop);
    hotkeyPanel = backdrop;

    const onKeyDown = (e) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        closeHotkeyPanel();
        cleanup();
        return;
      }
      if (!e.metaKey && !e.altKey && !e.ctrlKey) return;
      if (['Meta', 'Alt', 'Control', 'Shift'].includes(e.key)) return;
      const kvk = CODE_TO_KVK[e.code];
      if (kvk === undefined) return;

      e.preventDefault();
      e.stopPropagation();

      let mods = 0;
      if (e.ctrlKey) mods |= 4096;
      if (e.altKey) mods |= 2048;
      if (e.shiftKey) mods |= 512;
      if (e.metaKey) mods |= 256;

      const newHk = { key: kvk, mods };
      try {
        window.webkit?.messageHandlers?.zajel?.postMessage({ hotkey: newHk });
      } catch (_) {}
      if (window.ZajelNative) window.ZajelNative.hotkey = newHk;

      closeHotkeyPanel();
      cleanup();
      updateHotkeyUI();
      showToast('تم تعيين الاختصار: ' + formatHotkeyLabel(newHk));
    };

    const cleanup = () => {
      document.removeEventListener('keydown', onKeyDown, true);
    };
    document.addEventListener('keydown', onKeyDown, true);
  }

  const workingSince = {};
  const prevAgentState = {};
  const finishedAgents = new Set();

  function updateSlotIdentity(slot) {
    if (!slot || !slot.card) return;
    const col = colorOf(slot.id || '');
    const agent = agents.find(a => a.id === slot.id);
    const name = agent?.name || (slot.id==='verdict'?'⚖️ الحكم':slot.id==='deep'?'🔬 بحث متعمق':slot.id==='perplexity'?'Perplexity':slot.id) || '';

    slot.card.style.borderColor = col;
    slot.card.style.borderWidth = '2px';
    slot.card.style.borderStyle = 'solid';
    if (slot.topStrip) slot.topStrip.style.background = col;

    if (slot.avatarEl) {
      slot.avatarEl.style.background = col;
      slot.avatarEl.textContent = glyphOf(slot.id || '', name);
    }
    if (slot.nameEl) {
      slot.nameEl.textContent = name;
    }
    if (slot.progBar) {
      slot.progBar.style.background = col;
    }
    updateSlotBadges();
  }

  function updateSlotBadges() {
    slots.forEach(slot=>{if(!slot.badgeEl)return;const ag=round?.agents?.[slot.id], live=agents.find(a=>a.id===slot.id);let state=ag?.state||(slot.id==='verdict'?round?.judge_state:slot.id==='deep'?round?.deep_state:'')||({working:'writing',waiting:'needs_input',stopped:'idle'}[live?.state]||'idle');
      const labels={idle:'متوقف',waiting:'ينتظر',waiting_answers:'ينتظر',writing:'يكتب',running:'يكتب',needs_input:'ينتظر ردّك',done:'انتهى',timeout:'تأخر',error:'تأخر'};
      slot.badgeEl.dataset.state=state;slot.badgeEl.title=labels[state]||'ينتظر';slot.badgeEl.setAttribute('aria-label',slot.badgeEl.title);
      if(slot.selectBtn){slot.selectBtn.hidden=!ag;slot.selectBtn.textContent=ag?.selected?'☑️':'☐';slot.selectBtn.setAttribute('aria-pressed',String(!!ag?.selected));}
    });
  }

  function closeBroadcastPanel() {
    if (!broadcastBackdrop) return;
    broadcastBackdrop.remove();
    broadcastBackdrop = null;
    broadcastPanel = null;
    document.removeEventListener('keydown', onBroadcastKey, true);
  }

  function onBroadcastKey(ev) {
    if (ev.key === 'Escape') {
      ev.preventDefault();
      closeBroadcastPanel();
    }
  }

  function openBroadcastPanel(btn) {
    if(broadcastBackdrop){closeBroadcastPanel();return;}
    const backdrop=document.createElement('div');backdrop.className='as-broadcast-backdrop';backdrop.style.cssText='position:fixed;inset:0;background:#000a;z-index:100005;display:flex;align-items:center;justify-content:center;padding:14px';backdrop.onclick=e=>{if(e.target===backdrop)closeBroadcastPanel();};
    const modal=document.createElement('div');modal.dir='rtl';modal.className='as-broadcast-modal';modal.style.cssText='background:var(--panel);color:var(--ink);padding:20px;border-radius:14px;width:min(680px,92vw);max-height:90vh;overflow:auto;display:flex;flex-direction:column;gap:12px';
    const head=document.createElement('div');head.textContent='أرسل إلى عدة وكلاء';const close=document.createElement('button');close.className='btn';close.textContent='✕';close.onclick=closeBroadcastPanel;head.appendChild(close);
    const ta=document.createElement('textarea');ta.rows=6;ta.dir='auto';ta.placeholder='اكتب سؤالك هنا مرة واحدة…';ta.style.cssText='width:100%;box-sizing:border-box;font:inherit;min-height:110px;flex:none;resize:vertical';
    const grid=document.createElement('div');grid.style.cssText='display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:5px;font-size:12.5px';
    const valid=agents.filter(a=>a.cmd), selected=new Set();try{JSON.parse(localStorage.getItem('zajel_broadcast_ids')||'[]').forEach(id=>{if(valid.some(a=>a.id===id))selected.add(id);});}catch(_){}if(!selected.size&&valid[0])selected.add(valid[0].id);
    let judge='',judgeChanged=false;const rows=[];const warning=document.createElement('small');warning.style.color='#eab308';
    function update(){rows.forEach(r=>{r.answer.checked=selected.has(r.id);if(r.judge)r.judge.checked=judge===r.id;});warning.textContent=judge&&selected.has(judge)?'المحكِّم سيجيب أيضًا؛ تُخفى الأسماء عنه':'';sendBtn.disabled=!ta.value.trim()||!selected.size;}
    const deepSel=new Set();const deep=document.createElement('input');deep.type='checkbox';
    [...valid,{id:'perplexity',name:'Perplexity'}].forEach(a=>{const row=document.createElement('div');row.style.cssText='border:1px solid var(--line);border-radius:7px;padding:4px 7px;display:flex;flex-wrap:wrap;gap:2px 8px;align-items:center;line-height:1.3';const name=document.createElement('strong');name.textContent=glyphOf(a.id,a.name)+' '+a.name;name.style.cssText='width:100%;font-size:12.5px';const al=document.createElement('label'),answer=document.createElement('input');answer.type='checkbox';al.append(answer,document.createTextNode(' يجيب'));answer.onchange=()=>{answer.checked?selected.add(a.id):selected.delete(a.id);try{localStorage.setItem('zajel_broadcast_ids',JSON.stringify([...selected]));}catch(_){}update();};const dpl=document.createElement('label'),dp=document.createElement('input');dp.type='checkbox';dp.checked=deepSel.has(a.id);dpl.title='بحث متعمق لهذا الوكيل وحده';dpl.append(dp,document.createTextNode(' 🔬'));dp.onchange=()=>{dp.checked?deepSel.add(a.id):deepSel.delete(a.id);if(dp.checked&&!answer.checked){answer.checked=true;answer.onchange();}deep.checked=rows.length>0&&rows.every(x=>!x.answer.checked||deepSel.has(x.id));};row.append(name,al,dpl);let jc=null;if(a.id!=='perplexity'){const jl=document.createElement('label');jc=document.createElement('input');jc.type='radio';jc.name='round-judge';jl.append(jc,document.createTextNode(' ⚖️ يحكّم'));jc.onchange=async()=>{judgeChanged=true;judge=a.id;selected.delete(a.id);update();try{await req('judge_default',{judge});}catch(e){showToast(e.message||'تعذّر حفظ المحكِّم');}};row.appendChild(jl);}grid.appendChild(row);rows.push({id:a.id,answer,judge:jc,dp});});
    const opts=document.createElement('div');const auto=document.createElement('input');auto.type='checkbox';deep.onchange=()=>rows.forEach(x=>{if(!x.answer.checked)return;x.dp.checked=deep.checked;deep.checked?deepSel.add(x.id):deepSel.delete(x.id);});const al=document.createElement('label'),dl=document.createElement('label');al.append(auto,document.createTextNode(' ⚖️ تحكيم تلقائي'));dl.append(deep,document.createTextNode(' 🔬 بحث متعمق للجميع'));opts.append(al,document.createTextNode('　'),dl);
    const err=document.createElement('small');err.style.color='#ef4444';const sendBtn=document.createElement('button');sendBtn.className='btn pri';sendBtn.textContent='أرسل';ta.oninput=update;
    sendBtn.onclick=async()=>{const question=ta.value.trim(),answerers=[...selected];if(!question||!answerers.length)return;sendBtn.disabled=true;try{const deepAgents=answerers.filter(id=>deepSel.has(id));const r=await req('round/start',{question,answerers,judge,auto_judge:auto.checked,deep_agents:deepAgents});if(r.error)throw new Error(r.error);round=r;webLast=webPosted='';webSame=0;slots=answerers.map(id=>({id,hash:'',view:'answer',manual:false}));layout=slots.length;activeSlot=0;builtLayout=layout;if(answerers.includes('perplexity'))openPerplexity(question,true,deepAgents.includes('perplexity'));closeBroadcastPanel();build();refreshScreens(true);pollRound();}catch(e){err.textContent=e.message||'تعذّر الإرسال';update();}};
    modal.append(head,ta,grid,warning,opts,err,sendBtn);backdrop.appendChild(modal);(root?.closest('#zajel-term-window')||root||document.body).appendChild(backdrop);broadcastBackdrop=backdrop;broadcastPanel=modal;document.addEventListener('keydown',onBroadcastKey,true);update();req('judge_default').then(r=>{if(!broadcastBackdrop||judgeChanged)return;judge=r.judge||valid.find(a=>a.id==='claude')?.id||valid[0]?.id||'';selected.delete(judge);update();}).catch(()=>{});setTimeout(()=>ta.focus(),20);
  }

  function build(){ if(!root)return; root.replaceChildren(); root.dir='rtl'; root.className='as-terminal-ui'; applyTheme();
    const unavailable=document.createElement('div'); unavailable.className='as-memory-hint'; unavailable.hidden=true; root.appendChild(unavailable);
    const app=document.createElement('div'); app.className='as-terminal'; app.dataset.state=barState; app.dataset.pos=barPos; root.appendChild(app);
    const controls=document.createElement('div'); controls.className='as-terminal-controls'; app.appendChild(controls);
    const main=document.createElement('div'); main.className='as-terminal-main'; app.appendChild(main);
    const rail=document.createElement('aside'); rail.className='rail'; rail.setAttribute('aria-label','شريط الوكلاء'); main.appendChild(rail);
    const area=document.createElement('div');area.className='as-screen-area';main.appendChild(area);const chips=document.createElement('div');chips.className='as-hidden-chips';area.appendChild(chips);const viewport=document.createElement('div'); viewport.className='as-terminal-grid screens'; viewport.setAttribute('aria-label','الشاشات'); area.appendChild(viewport);
    const cols = layout <= 2 ? layout : (layout <= 4 ? 2 : 3);
    viewport.style.gridTemplateColumns = 'repeat(' + cols + ', minmax(0, 1fr))';
    viewport.style.gridAutoRows = 'minmax(0, 1fr)';
    const renderControls=()=>{
      controls.replaceChildren();
      const fontBtn=(label,title,delta)=>{const b=document.createElement('button');b.type='button';b.className='btn as-term-font';b.textContent=label;b.title=title;b.setAttribute('aria-label',title);b.onclick=()=>{termFont=Math.max(9,Math.min(18,termFont+delta));root.style.setProperty('--tt-size',termFont+'px');try{localStorage.setItem('zajel_term_font',String(termFont));}catch(_){}slots.forEach(s=>{s.lastSize='';resizeSlot(s);});};controls.appendChild(b);};
      fontBtn('A−','تصغير خط الطرفيات',-1);
      fontBtn('A+','تكبير خط الطرفيات',1);
      const bcBtn=document.createElement('button');
      bcBtn.type='button';
      bcBtn.className='btn as-broadcast-btn';
      bcBtn.textContent='📣 لعدة وكلاء';
      bcBtn.title='إرسال نفس الرسالة إلى عدة وكلاء في وقت واحد';
      bcBtn.setAttribute('aria-label','أرسل لعدة وكلاء');
      bcBtn.onclick=()=>openBroadcastPanel(bcBtn);
      controls.appendChild(bcBtn);

      const allTerm=document.createElement('button');allTerm.className='btn';allTerm.textContent='⌨️ الكل طرفيات';allTerm.onclick=()=>slots.forEach(s=>setSlotView(s,'terminal',true));controls.appendChild(allTerm);
      if(round){const judgeBtn=document.createElement('button');judgeBtn.className='btn';judgeBtn.dataset.roundJudge='1';judgeBtn.textContent='⚖️ حكّم';judgeBtn.disabled=Object.values(round.agents||{}).filter(a=>a.state==='done').length<2;judgeBtn.onclick=()=>roundAction('judge');controls.appendChild(judgeBtn);const deepBtn=document.createElement('button');deepBtn.className='btn';deepBtn.textContent='🔬 عمّق';deepBtn.onclick=()=>roundAction('deepen');controls.appendChild(deepBtn);}
      const exportAllBtn=document.createElement('button');
      exportAllBtn.type='button';
      exportAllBtn.className='btn';
      exportAllBtn.textContent='📄 كل الأجوبة';
      exportAllBtn.title='اجمع أجوبة الوكلاء المعروضين في مستند Word واحد';
      exportAllBtn.setAttribute('aria-label','اجمع أجوبة الوكلاء المعروضين في مستند Word واحد');
      exportAllBtn.onclick=async()=>{
        if(round){await roundAction('export');return;}
        const ids=slots.map(s=>s.id).filter(Boolean);
        if(!ids.length){ showToast('لا يوجد وكلاء معروضون لتصدير أجوبتهم'); return; }
        exportAllBtn.disabled=true;
        try{
          // جواب نافذة Perplexity إن كانت مفتوحة (يقرؤه البرنامج من الصفحة)
          const h=window.webkit&&window.webkit.messageHandlers&&window.webkit.messageHandlers.zajel;
          const web=h?await getWebAnswer():null;
          const r=await req('export_all',{ids,extra:web&&web.answer?[web]:[]});
          if(r&&r.error)throw new Error(r.error);
          showToast('حُفظ في التنزيلات: '+(r.title||'المستند')+(r.missing&&r.missing.length?' · لم يكتمل: '+r.missing.join('، '):''));
        }catch(e){
          showToast(e.message||'تعذّر صنع المستند');
        }finally{
          exportAllBtn.disabled=false;
        }
      };
      controls.appendChild(exportAllBtn);const pxBtn=document.createElement('button');pxBtn.type='button';pxBtn.className='btn';pxBtn.textContent='🔎 Perplexity';pxBtn.title='افتح Perplexity داخل زاجل';pxBtn.onclick=()=>openPerplexity('');controls.appendChild(pxBtn);

      const hotkeyBtn=document.createElement('button');
      hotkeyBtn.type='button';
      hotkeyBtn.className='btn as-hotkey-btn';
      hotkeyBtnRef=hotkeyBtn;
      updateHotkeyUI();
      hotkeyBtn.onclick=()=>openHotkeyPanel();
      controls.appendChild(hotkeyBtn);

      [1,2,3,4,5].forEach(n=>{
        const b=document.createElement('button');
        b.type='button';
        b.className='btn'+(layout===n?' pri':'');
        b.textContent=String(n);
        b.title='عدد النوافذ';
        b.setAttribute('aria-label','تخطيط '+n+' نوافذ');
        b.onclick=()=>{layout=n;build();refreshList();};
        controls.appendChild(b);
      });

      const pal=document.createElement('button');
      pal.type='button';
      pal.className='btn';
      pal.textContent='🎨 الألوان';
      pal.title='ألوان الطرفية وإطار السؤال';
      pal.setAttribute('aria-label','ألوان الطرفية');
      pal.onclick=()=>window.ZajelTermTheme&&window.ZajelTermTheme.openPanel(pal);
      controls.appendChild(pal);

      const down=document.createElement('button');
      down.type='button';
      down.className='btn';
      down.textContent='⤓';
      down.title='انتقل إلى أسفل الشاشات';
      down.setAttribute('aria-label','انتقل إلى الأسفل');
      down.onclick=()=>viewport.querySelectorAll('pre').forEach(x=>x.scrollTop=x.scrollHeight);
      controls.appendChild(down);

      const longer=document.createElement('button');
      longer.type='button';
      longer.className='btn';
      longer.textContent=hist>3000?'سجلّ عادي':'سجلّ أطول';
      longer.setAttribute('aria-label',hist>3000?'سجلّ عادي':'سجلّ أطول');
      longer.onclick=()=>{hist=hist>3000?3000:7000;longer.textContent=hist>3000?'سجلّ عادي':'سجلّ أطول';refreshScreens(true);};
      controls.appendChild(longer);

      const dirb=document.createElement('button');
      dirb.type='button';
      dirb.className='btn';
      const dirTxt=()=>root.dataset.dir==='ltr'?'الاتجاه: يسار ثابت':'الاتجاه: تلقائي';
      root.dataset.dir=(()=>{try{return localStorage.getItem('zajel_term_dir')||'auto';}catch(_){return 'auto';}})();
      dirb.textContent=dirTxt();
      dirb.setAttribute('aria-label',dirTxt());
      dirb.onclick=()=>{root.dataset.dir=root.dataset.dir==='ltr'?'auto':'ltr';try{localStorage.setItem('zajel_term_dir',root.dataset.dir);}catch(_){}dirb.textContent=dirTxt();dirb.setAttribute('aria-label',dirTxt());};
      controls.appendChild(dirb);

      const lab=document.createElement('label');
      lab.className='as-terminal-notify';
      const cb=document.createElement('input');
      cb.type='checkbox';
      cb.checked=notify;
      cb.setAttribute('aria-label','إشعار تيليجرام');
      cb.onchange=()=>{notify=cb.checked;req('notify',{on:notify}).catch(()=>{});};
      lab.title='إشعار تيليجرام عند انتظار الوكيل أو انتهائه';
      lab.append(cb,document.createTextNode('إشعار تيليجرام'));
      controls.appendChild(lab);

      const gl=document.createElement('label');
      gl.className='as-terminal-notify';
      gl.title='يراقب الوكلاء ويعيد تشغيل من يخرج منهم';
      const gc=document.createElement('input');
      gc.type='checkbox';
      gc.checked=guard;
      gc.setAttribute('aria-label','جهاز التحكم');
      gc.onchange=()=>{guard=gc.checked;req('guard',{on:guard}).catch(()=>{});};
      gl.append(gc,document.createTextNode('إنعاش تلقائي'));
      controls.appendChild(gl);
    };
    renderControls();

    while(slots.length<layout)slots.push({id:agents[slots.length]?.id||'',hash:'',pre:null,select:null,card:null});
    slots=slots.slice(0,layout);

    slots.forEach((slot,index)=>{
      const card=document.createElement('section');
      card.className='as-terminal-window';
      slot.card=card;

      const topStrip=document.createElement('div');
      topStrip.className='as-slot-top-strip';
      topStrip.style.cssText='height:3px;flex:none;background:'+colorOf(slot.id||'');
      slot.topStrip=topStrip;
      card.appendChild(topStrip);

      const head=document.createElement('div');
      head.className='as-terminal-window-head';

      const curAgent=agents.find(a=>a.id===slot.id);
      const curName=curAgent?.name||(slot.id==='verdict'?'⚖️ الحكم':slot.id==='deep'?'🔬 بحث متعمق':slot.id==='perplexity'?'Perplexity':slot.id)||'';

      const av=document.createElement('div');
      av.className='as-slot-av';
      av.style.cssText='width:22px;height:22px;border-radius:4px;display:grid;place-items:center;font-size:11px;font-weight:700;color:#fff;flex:none;background:'+colorOf(slot.id||'');
      av.textContent=glyphOf(slot.id||'',curName);
      slot.avatarEl=av;

      const nameEl=document.createElement('strong');
      nameEl.className='as-slot-name';
      nameEl.style.cssText='font-size:12.5px;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:110px;';
      nameEl.textContent=curName;
      slot.nameEl=nameEl;

      const badgeEl=document.createElement('span');badgeEl.className='as-slot-dot';slot.badgeEl=badgeEl;head.append(av,nameEl,badgeEl);
      const selectBtn=document.createElement('button');selectBtn.className='btn as-head-icon';selectBtn.title='إدراج الجواب في التقرير';selectBtn.setAttribute('aria-label',selectBtn.title);selectBtn.onclick=()=>{const ag=round?.agents?.[slot.id];if(ag)roundAction('select',{agent_id:slot.id,selected:!ag.selected});};slot.selectBtn=selectBtn;head.appendChild(selectBtn);
      const rb=document.createElement('button');rb.className='btn as-head-icon';rb.textContent='📖';rb.title='عرض الجواب';rb.onclick=()=>{if(!round?.agents?.[slot.id]&&!['verdict','deep'].includes(slot.id)){openReader(slot);return;}setSlotView(slot,slot.view==='answer'?'terminal':'answer',true);};slot.viewBtn=rb;head.appendChild(rb);
      const fsb=document.createElement('button');
      fsb.type='button';
      fsb.className='btn as-terminal-fs';
      fsb.textContent='⤢';
      fsb.title='ملء الشاشة / تصغير';
      fsb.setAttribute('aria-label','ملء الشاشة');
      fsb.onclick=()=>{
        const on=card.classList.toggle('is-full');
        fsb.textContent=on?'🗗':'⤢';
        fsb.title=on?'تصغير':'ملء الشاشة';
        setTimeout(()=>{
          resizeSlot(slot);
          slot.input&&slot.input.focus({preventScroll:true});
        },60);
      };
      head.appendChild(fsb);

      const wb=document.createElement('button');
      wb.type='button';
      wb.className='btn as-terminal-fs';
      wb.textContent='📄';
      wb.title='احفظ آخر سؤال وجوابه في مستند Word';
      wb.onclick=async()=>{
        wb.disabled=true;
        try{
          const r=round&&['verdict','deep'].includes(slot.id)?await req('round/export',{round_id:round.round_id}):slot.id==='perplexity'?(window.webkit?.messageHandlers?.zajel?.postMessage({webWord:1}),{title:'جواب Perplexity'}):await req('export_answer',{id:slot.id});
          if(r&&r.error)throw new Error(r.error);
          showToast('حُفظ في التنزيلات: '+r.title);
        }catch(e){
          showToast(e.message||'تعذّر صنع المستند');
        }finally{
          wb.disabled=false;
        }
      };
      head.appendChild(wb);

      const more=document.createElement('details');more.className='as-card-more';const summary=document.createElement('summary');summary.title='المزيد';summary.textContent='⋯';const deepen=document.createElement('button');deepen.className='btn';deepen.textContent='🔬 عمّق';deepen.onclick=()=>{more.open=false;roundAction('deepen',{agent_id:slot.id});};more.append(summary,deepen);more.hidden=!round?.agents?.[slot.id]||slot.id==='perplexity';head.appendChild(more);const reask=document.createElement('button');reask.type='button';reask.className='btn as-reask';reask.textContent='↻';reask.title='أعد السؤال نفسه على هذا الوكيل';reask.setAttribute('aria-label',reask.title);reask.onclick=()=>{slot.manual=false;roundAction('reask',{agent_id:slot.id});};reask.hidden=more.hidden;head.appendChild(reask);
      const hide=document.createElement('button');hide.className='btn as-head-icon';hide.textContent='—';hide.title='إخفاء البطاقة';hide.onclick=()=>{slot.hidden=true;card.classList.remove('is-full');tileSlots();};head.appendChild(hide);
      const msg=document.createElement('small');slot.msg=msg;msg.hidden=true;card.appendChild(msg);

      card.appendChild(head);

      const progWrap=document.createElement('div');
      progWrap.className='as-slot-prog-wrap';
      progWrap.style.cssText='height:2.5px;position:relative;overflow:hidden;background:rgba(255,255,255,0.06);display:none;';
      const progBar=document.createElement('div');
      progBar.className='as-slot-prog-bar';
      progBar.style.cssText='position:absolute;top:0;bottom:0;width:40%;background:'+colorOf(slot.id||'')+';';
      progWrap.appendChild(progBar);
      slot.progWrap=progWrap;
      slot.progBar=progBar;
      card.appendChild(progWrap);

      const pre=document.createElement('pre');
      pre.dir='ltr';
      pre.tabIndex=0;
      pre.className='as-terminal-screen';
      pre.setAttribute('aria-label','شاشة الطرفية · اضغط للكتابة');
      slot.pre=pre;
      // عجلة الفأرة فوق قائمة منبثقة (أو تطبيق بشاشة كاملة) تُحرّك الاختيار بأسهم لأعلى/لأسفل بدل تمرير السجل
      let wheelAcc=0;
      pre.addEventListener('wheel',e=>{
        if(e.ctrlKey||e.metaKey)return;
        const menu=pre.querySelector('[data-opt-menu]'),mode=menu?menu.dataset.optMenu:'',alt=!!(slot.cur&&slot.cur.alt);
        if(!alt&&mode!=='hl'&&mode!=='mark')return;
        e.preventDefault();
        wheelAcc+=e.deltaMode===1?e.deltaY*40:e.deltaY;
        const n=Math.trunc(wheelAcc/40);if(!n)return;
        wheelAcc-=n*40;
        send(slot,{keys:Array(Math.min(8,Math.abs(n))).fill(n>0?'Down':'Up')});
      },{passive:false});
      pre.addEventListener('click',e=>{
        const target=e.target.closest('[data-opt-number],[data-opt-list]');
        if(!target||window.getSelection()?.toString())return;
        const optionLines=[...pre.querySelectorAll('[data-opt-list]')], cursor=optionLines.findIndex(x=>x.hasAttribute('data-opt-cur'));
        let action;
        if(target.hasAttribute('data-opt-number')) action=req('send',{id:slot.id,text:String(target.dataset.optNumber)});
        else {const index=optionLines.indexOf(target);if(index<0||(cursor<0&&optionLines[0]?.dataset.optMenu!=='hl'))return;const delta=index-cursor,keys=Array(Math.abs(delta)).fill(delta>0?'Down':'Up');keys.push('Enter');action=req('send',{id:slot.id,keys});}
        e.preventDefault();e.stopPropagation();kick();Promise.resolve(action).then(()=>setTimeout(()=>refreshScreens(true),150)).catch(err=>showToast('تعذّر الإرسال: '+(err.message||'خطأ')));
      });

      const scrollDownBtn=document.createElement('button');
      scrollDownBtn.type='button';
      scrollDownBtn.className='btn as-slot-scroll-down';
      scrollDownBtn.textContent='↓ إلى الأسفل';
      scrollDownBtn.title='انتقل إلى أسفل الشاشة';
      scrollDownBtn.setAttribute('aria-label','انتقل إلى الأسفل');
      scrollDownBtn.style.cssText='position:absolute;bottom:14px;left:14px;z-index:10;display:none;background:var(--panel,#182230);color:var(--ink,#fff);border:1px solid var(--line,#24344a);border-radius:20px;padding:4px 12px;font-size:11.5px;font-weight:600;box-shadow:0 4px 14px rgba(0,0,0,0.45);cursor:pointer;';
      scrollDownBtn.onclick=(e)=>{
        e.stopPropagation();
        pre.scrollTop=pre.scrollHeight;
        scrollDownBtn.style.display='none';
      };
      card.appendChild(scrollDownBtn);
      slot.scrollDownBtn=scrollDownBtn;

      const updateScrollBtn=()=>{
        const isUp=pre.scrollHeight-pre.scrollTop-pre.clientHeight>=30;
        scrollDownBtn.style.display=isUp?'inline-flex':'none';
      };
      pre.addEventListener('scroll',updateScrollBtn);
      slot.updateScrollBtn=updateScrollBtn;

      const ta=document.createElement('textarea');
      ta.setAttribute('aria-label','إدخال الطرفية');
      ta.setAttribute('autocapitalize','off');
      ta.setAttribute('autocomplete','off');
      ta.setAttribute('autocorrect','off');
      ta.spellcheck=false;
      ta.style.cssText='position:absolute;opacity:0;width:2px;height:2px;left:0;top:0;border:0;padding:0;resize:none;font-size:16px';
      slot.input=ta;

      pre.addEventListener('focus',()=>{
        activeSlot=index;
        root&&root.querySelectorAll('.as-terminal-window').forEach((w,k)=>w.classList.toggle('is-active',k===index));
        updateActiveCardHighlight();
      });

      card.style.position='relative';
      card.append(pre,ta);
      viewport.appendChild(card);
      wireKeys(slot);

      updateSlotIdentity(slot);
      answerView(slot);setSlotView(slot,slot.view||((round?.agents?.[slot.id]||['verdict','deep'].includes(slot.id))?'answer':'terminal'),false);
    });

    const agentStyle=document.createElement('style');
    agentStyle.textContent='.as-reader h2,.as-reader h3,.as-reader h4{color:var(--acc);margin:16px 0 6px}.as-reader p{margin:6px 0}.as-reader ul,.as-reader ol{margin:6px 0;padding-inline-start:22px}.as-reader figure.as-mermaid{margin:10px 0;text-align:center}.as-reader pre{background:var(--side);padding:10px;border-radius:8px;overflow-x:auto;font:12.5px/1.5 ui-monospace,Menlo,monospace;text-align:left}.as-reader code{font-family:ui-monospace,Menlo,monospace;background:var(--side);padding:0 4px;border-radius:4px}.as-terminal-main{direction:rtl!important}/* المساعد يضع dir=auto على العناصر بلا اتجاه؛ في الشريط يقلب البطاقات ذات الأسماء اللاتينية */.rail .agent,.rail .agent .meta,.rail .agent .acts{direction:rtl!important;unicode-bidi:isolate!important}.rail .agent .meta small{unicode-bidi:plaintext!important;text-align:right}.as-terminal-ui{display:flex;flex-direction:column;gap:8px;min-height:0;flex:1;height:100%;--rail:var(--side,#152131);--rail-line:var(--line,#24344a);--term-ink:var(--ink,#d6e2ee);--term-dim:var(--mut,#7f93a8);--accent:var(--acc,#0f8f9a);--accent-ink:#ffffff;--ok:var(--ok,#22a55a);--wait:var(--warn,#d99a06);--off:#8796a6;--bad:var(--err,#d64545)}.as-terminal{display:flex;flex-direction:column;gap:6px;flex:1;min-height:0}.as-terminal-controls{display:flex;gap:6px;align-items:center;flex-wrap:wrap;flex:none;direction:rtl}.as-terminal-main{display:flex;flex:1;min-height:0;min-width:0;overflow:hidden}.as-terminal[data-pos="top"] .as-terminal-main{flex-direction:column}.rail{background:var(--rail);border-inline-end:1px solid var(--rail-line);display:flex;flex-direction:column;gap:6px;padding:10px 8px;transition:width .22s ease;width:224px;flex:none;min-height:0}.as-terminal[data-state="collapsed"] .rail{width:64px;align-items:center}.as-terminal[data-state="collapsed"] .btn-remove,.as-terminal[data-state="collapsed"] .rail .agent:hover .tip{display:none!important}.rail .av{direction:ltr;unicode-bidi:isolate}.rail-flytip{position:fixed;z-index:100000;pointer-events:none;background:var(--panel,#182230);color:var(--ink,#fff);border:1px solid var(--line,#24344a);border-radius:8px;padding:5px 10px;font-size:12.5px;white-space:nowrap;box-shadow:0 6px 20px -8px rgba(0,0,0,.5);direction:rtl}.as-terminal[data-state="collapsed"] .rail-list{scrollbar-width:none;align-items:center}.as-terminal[data-state="collapsed"] .rail-list::-webkit-scrollbar{display:none}.as-terminal[data-state="collapsed"] .agent{justify-items:center;width:44px}.as-terminal[data-state="collapsed"] .av{width:36px;height:36px;font-size:16px}.as-terminal[data-pos="top"] .rail{width:auto;flex-direction:row;align-items:center;border-inline-end:0;border-bottom:1px solid var(--rail-line);padding:8px 10px;overflow-x:auto}.as-terminal[data-pos="top"][data-state="collapsed"] .rail{padding-block:6px}.rail-head{display:flex;align-items:center;justify-content:space-between;gap:6px;color:var(--term-dim);font-size:12px;padding:0 2px 4px;flex:none;width:100%}.as-terminal[data-state="collapsed"] .rail-head .lbl{display:none}.as-terminal[data-pos="top"] .rail-head{padding:0;flex:none;width:auto}.rail-head-acts{display:flex;gap:4px;align-items:center}.rail-toggle,.rail-btn-pos{border:1px solid var(--rail-line);background:transparent;color:var(--term-ink);border-radius:7px;width:28px;height:26px;cursor:pointer;font-size:12px;line-height:1;display:inline-flex;align-items:center;justify-content:center}.rail-btn-pos{width:auto;padding:2px 6px;font-size:11px}.as-terminal[data-state="collapsed"] .rail-btn-pos{display:none}.rail-list{display:flex;flex-direction:column;gap:6px;overflow-y:auto;min-height:0;flex:1;padding:2px 0;width:100%}.as-terminal[data-pos="top"] .rail-list{flex-direction:row;overflow-x:auto;overflow-y:hidden;align-items:center;width:auto}.rail-sec-head{display:flex;align-items:center;font-size:11px;font-weight:600;color:var(--term-dim);padding:4px 2px 2px;flex:none}.as-terminal[data-state="collapsed"] .rail-sec-head{display:none}.as-terminal[data-pos="top"] .rail-sec-head{display:none}.agent{position:relative;display:grid;grid-template-columns:auto 1fr;align-items:center;gap:4px 9px;padding:8px 9px;border-radius:10px;background:rgba(127,127,127,0.08);border:1px solid transparent;color:var(--term-ink);cursor:pointer;text-align:start;font:inherit;flex:none}.agent:hover{background:rgba(127,127,127,0.15)}.agent.sel{border-color:var(--accent);background:rgba(15,143,154,0.15)}.agent:focus-visible,.rail-toggle:focus-visible,.rail-btn-pos:focus-visible,.btn:focus-visible{outline:2px solid var(--accent);outline-offset:2px}.av{width:30px;height:30px;border-radius:8px;display:grid;place-items:center;font-family:ui-monospace,Menlo,monospace;font-weight:600;font-size:13px;color:#fff;position:relative;flex:none}.dot{position:absolute;bottom:-3px;inset-inline-end:-3px;width:11px;height:11px;border-radius:50%;border:2px solid var(--rail)}.dot.working{background:var(--ok)}.dot.waiting{background:var(--wait);animation:pulse 1.4s ease-in-out infinite}.dot.stopped{background:var(--off)}.dot.broken{background:var(--bad)}@keyframes pulse{50%{box-shadow:0 0 0 5px rgba(240,180,41,0.35)}}@media(prefers-reduced-motion:reduce){.dot.waiting{animation:none}.rail{transition:none}}.sc-badge{position:absolute;bottom:-4px;inset-inline-end:-4px;font-size:10px;line-height:1}.meta{min-width:0;overflow:hidden}.meta strong{display:block;font-size:13px;font-weight:600;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.meta small{display:block;font-size:11px;color:var(--term-dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.acts{grid-column:1/-1;display:flex;gap:4px;margin-top:4px}.acts .btn{flex:1;font:inherit;font-size:11px;padding:3px 0;border-radius:6px;border:1px solid var(--rail-line);background:transparent;color:var(--term-ink);cursor:pointer;text-align:center}.acts .btn:hover{border-color:var(--accent)}.acts .btn.btn-remove{flex:none;width:22px;padding:0;color:var(--term-dim)}.acts .btn.btn-remove:hover{color:var(--bad);border-color:var(--bad)}.new-badge{font-size:10px;background:var(--accent);color:var(--accent-ink);border-radius:5px;padding:0 5px;margin-inline-start:4px;vertical-align:1px}.inline-confirm{grid-column:1/-1;display:flex;flex-direction:column;gap:4px;padding:5px;background:rgba(0,0,0,0.15);border:1px dashed var(--rail-line);border-radius:7px;margin-top:4px}.confirm-msg{font-size:11px;color:var(--term-ink)}.confirm-btns{display:flex;gap:4px}.confirm-btns .btn{flex:1;padding:2px 6px;font-size:11px}.confirm-btns .btn.danger{color:var(--bad);border-color:var(--bad)}.as-terminal[data-state="collapsed"] .agent{grid-template-columns:auto;padding:5px;background:transparent}.as-terminal[data-state="collapsed"] .meta,.as-terminal[data-state="collapsed"] .acts,.as-terminal[data-state="collapsed"] .inline-confirm{display:none!important}.as-terminal[data-pos="top"] .agent{flex:none;width:176px}.as-terminal[data-pos="top"][data-state="collapsed"] .agent{width:auto}.as-terminal[data-pos="top"] .acts{display:none}.as-terminal[data-pos="top"][data-state="expanded"] .acts{display:flex}.tip{display:none}.as-terminal[data-state="collapsed"] .agent:hover .tip,.as-terminal[data-state="collapsed"] .agent:focus-visible .tip{display:block;position:absolute;z-index:1000;inset-inline-end:calc(100% + 8px);top:50%;transform:translateY(-50%);background:var(--panel,#182230);color:var(--ink,#fff);border:1px solid var(--line,#24344a);border-radius:8px;padding:5px 9px;font-size:12px;white-space:nowrap;box-shadow:0 6px 20px -8px rgba(0,0,0,0.5);pointer-events:none}.as-terminal[data-pos="top"][data-state="collapsed"] .agent:hover .tip{inset-inline-end:auto;top:calc(100% + 6px);transform:none;right:0}.add .av{background:transparent!important;border:1.5px dashed var(--term-dim);color:var(--term-dim)}.sep{height:1px;background:var(--rail-line);margin:4px 0;flex:none;align-self:stretch}.as-terminal[data-pos="top"] .sep{width:1px;height:28px;margin:0 4px}.agent-form-inline{display:flex;flex-direction:column;gap:6px;padding:8px;border-radius:8px;border:1px solid var(--rail-line);background:rgba(0,0,0,0.2);margin:4px 0;font-size:11.5px}.as-terminal[data-pos="top"] .agent-form-inline{position:absolute;top:100%;right:0;z-index:20;width:250px;background:var(--side,#152131);box-shadow:0 8px 24px rgba(0,0,0,0.4)}.agent-form-inline label{display:flex;flex-direction:column;gap:2px;color:var(--term-dim)}.agent-form-inline input[type="text"]{border:1px solid var(--rail-line);background:rgba(0,0,0,0.25);color:var(--term-ink);border-radius:6px;padding:4px 7px;font:inherit}.agent-form-inline .form-acts{display:flex;gap:5px;margin-top:4px}.agent-form-inline .form-acts .btn{flex:1;padding:4px;font-size:11px}.shortcut-inline-notice{grid-column:1/-1;display:flex;flex-direction:column;gap:4px;padding:6px;background:rgba(217,154,6,0.15);border:1px solid var(--wait);border-radius:7px;margin-top:4px;font-size:11px}.shortcut-inline-notice .acts{display:flex;gap:4px;flex-wrap:wrap}.as-terminal-grid{flex:1;min-height:0;min-width:0;display:grid;gap:8px}.as-terminal-ui[data-layout="1"] .as-terminal-grid{grid-template-columns:1fr;grid-auto-rows:minmax(0,1fr)}.as-terminal-ui[data-layout="2"] .as-terminal-grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:minmax(0,1fr)}.as-terminal-ui[data-layout="3"] .as-terminal-grid,.as-terminal-ui[data-layout="4"] .as-terminal-grid{grid-template-columns:repeat(2,minmax(0,1fr));grid-auto-rows:minmax(0,1fr)}.as-terminal-ui[data-layout="5"] .as-terminal-grid,.as-terminal-ui[data-layout="6"] .as-terminal-grid,.as-terminal-ui[data-layout="7"] .as-terminal-grid,.as-terminal-ui[data-layout="8"] .as-terminal-grid,.as-terminal-ui[data-layout="9"] .as-terminal-grid{grid-template-columns:repeat(3,minmax(0,1fr));grid-auto-rows:minmax(0,1fr)}.as-terminal-window{min-width:0;min-height:0;display:flex;flex-direction:column;border:2px solid var(--line);border-radius:9px;overflow:hidden;position:relative;transition:border-color .2s, box-shadow .2s;}.as-terminal-window.is-active{box-shadow:0 0 0 1px var(--acc)}.as-terminal-window-head{padding:5px 8px;background:var(--side);flex:none;display:flex;flex-wrap:wrap;gap:6px;align-items:center;min-height:36px;direction:rtl;}.as-terminal-window-head select{max-width:100%;flex:1;min-width:90px}.as-terminal-fs{padding:2px 9px;font-size:14px;line-height:1.2}.as-terminal-window.is-full{position:fixed!important;inset:0!important;width:auto!important;height:auto!important;max-height:100dvh!important;z-index:99999!important;border-radius:0!important;background:var(--bg)!important;display:flex!important;flex-direction:column!important;}.as-terminal-window.is-full .as-terminal-screen{font-size:var(--tt-size,12.5px);flex:1 1 0!important;min-height:0!important;height:auto!important;overflow-y:auto!important;}.as-terminal-screen{margin:0;padding:8px 10px;overflow-y:auto;overflow-x:hidden;scrollbar-gutter:stable;white-space:pre;direction:ltr;unicode-bidi:plaintext;text-align:start;background:var(--tt-bg,#101318);color:var(--tt-fg,#e5e7eb);font:var(--tt-size,12.5px)/1.25 ui-monospace,SFMono-Regular,Menlo,"SF Arabic","Geeza Pro",Consolas,monospace;flex:1;min-height:0;outline:none;tab-size:8}.as-terminal-ui[data-dir="ltr"] .as-terminal-screen{unicode-bidi:normal;text-align:left}.as-terminal-screen span[style*=background]{padding-block:.16em}.as-terminal-msg{display:block;font-size:11px;min-height:14px;padding:2px 4px;color:var(--mut)}.as-terminal-screen .tt-a{color:var(--tt-a)}.as-terminal-screen .tt-q{display:block;margin:5px 0;padding:3px 8px;border:1.5px solid var(--tt-qborder);border-radius:7px;background:var(--tt-qbg);color:var(--tt-q)}.as-terminal-screen .tt-q span{color:inherit!important;background:transparent!important}.as-terminal-screen [data-opt-number],.as-terminal-screen [data-opt-list]{cursor:pointer}.as-terminal-screen [data-opt-number]:hover,.as-terminal-screen [data-opt-list]:hover{ text-decoration:underline;background:var(--panel,rgba(127,127,127,.18));}.as-terminal-screen:focus{box-shadow:inset 0 0 0 1px var(--acc)}@keyframes slot-prog-anim{0%{left:-40%;}100%{left:100%;}}.as-slot-prog-bar{animation:slot-prog-anim 1.4s ease-in-out infinite;}@keyframes slot-flash-anim{0%,100%{box-shadow:none;}50%{box-shadow:0 0 0 4px #22c55e, 0 0 18px rgba(34,197,94,0.6);}}.as-terminal-window.is-flashing{animation:slot-flash-anim 1.2s ease-in-out;}@media(prefers-reduced-motion:reduce){.as-slot-prog-bar{animation:none!important}.as-terminal-window.is-flashing{animation:none!important}}@media(max-width:860px){.as-terminal-ui[data-layout="2"] .as-terminal-grid,.as-terminal-ui[data-layout="3"] .as-terminal-grid,.as-terminal-ui[data-layout="4"] .as-terminal-grid,.as-terminal-ui[data-layout="5"] .as-terminal-grid,.as-terminal-ui[data-layout="6"] .as-terminal-grid,.as-terminal-ui[data-layout="7"] .as-terminal-grid,.as-terminal-ui[data-layout="8"] .as-terminal-grid,.as-terminal-ui[data-layout="9"] .as-terminal-grid{grid-template-columns:1fr!important;grid-template-rows:none!important;grid-auto-rows:minmax(220px,1fr)!important;overflow-y:auto!important}}/* شريط الوكلاء المضغوط: سطر لكل وكيل، والأزرار أيقونات تظهر عند المرور أو للمختار */.rail .agent{grid-template-columns:auto 1fr auto;padding:5px 7px;gap:0 8px;border-radius:8px;background:transparent}.rail .agent:hover{background:rgba(127,127,127,0.10)}.rail .agent.sel{background:rgba(15,143,154,0.12)}.rail .av{width:26px;height:26px;font-size:12px;border-radius:7px}.rail .dot{width:9px;height:9px}.rail .meta strong{font-size:12.5px}.rail .meta small{font-size:10.5px}.rail .acts{grid-column:auto;margin:0;gap:2px;opacity:0;transition:opacity .15s}.rail .agent:hover .acts,.rail .agent:focus-within .acts{opacity:1}.rail .agent:not(:hover):not(:focus-within) .acts{width:0;overflow:hidden}.rail .acts .btn{flex:none;width:22px;height:22px;padding:0;font-size:11px;line-height:20px;border-radius:6px;border-color:transparent;color:var(--term-dim)}.rail .acts .btn:hover{color:var(--term-ink);border-color:var(--rail-line);background:rgba(127,127,127,0.12)}.rail-list{gap:2px}.as-terminal-controls{gap:4px!important;row-gap:4px!important}.as-terminal-controls .btn{padding:3px 8px!important;font-size:12px!important;min-height:26px;line-height:1.2;border-radius:7px}.as-terminal-controls label{font-size:12px}.as-terminal-controls .ii svg{width:14px;height:14px}.as-reask{padding:1px 7px!important;font-size:12px!important;min-height:0!important;line-height:1.3}';
    agentStyle.textContent+=' .as-screen-area{display:flex;flex-direction:column;flex:1;min-width:0;min-height:0}.as-hidden-chips{display:flex;gap:5px;flex-wrap:wrap}.as-hidden-chips:empty{display:none}.as-terminal-window[hidden]{display:none!important}.as-terminal-window-head{flex-wrap:nowrap;gap:4px;min-width:0}.as-slot-name{flex:1;min-width:0}.as-head-icon,.as-terminal-fs{padding:2px 4px;font-size:13px;flex:none}.as-slot-dot{width:8px;height:8px;border-radius:50%;background:#94a3b8;flex:none}.as-slot-dot[data-state=writing],.as-slot-dot[data-state=running]{background:#3b82f6;animation:as-blue-pulse 1.4s infinite}.as-slot-dot[data-state=needs_input]{background:#eab308}.as-slot-dot[data-state=done]{background:#22c55e}@keyframes as-blue-pulse{50%{box-shadow:0 0 0 4px #3b82f655}}.as-card-more{position:relative;flex:none}.as-card-more summary{cursor:pointer;list-style:none}.as-card-more button{position:absolute;top:100%;left:0;z-index:25;white-space:nowrap}.as-round-answer{flex:1;min-height:0;overflow:auto;padding:12px 16px;background:var(--panel);font:calc(var(--tt-size,12.5px) + 2.5px)/1.75 "SF Arabic","Geeza Pro",system-ui,sans-serif}.as-terminal-window .as-slot-scroll-down{display:none!important}@media(prefers-reduced-motion:reduce){.as-slot-dot{animation:none!important}}';
    root.appendChild(agentStyle);tileSlots();
    root.dataset.layout=String(layout);
    renderRail();
    resizeObserver?.disconnect();
    resizeObserver=new ResizeObserver(entries=>{
      for(const e of entries){
        const s=slots.find(x=>x.pre===e.target);
        if(s)resizeSlot(s);
      }
    });
    slots.forEach(s=>{if(s.pre)resizeObserver.observe(s.pre);});
  }
  function renderAgents(){if(!root)return;const cards=root.querySelector('.as-terminal-agents');if(!cards)return;cards.replaceChildren();agents.forEach(a=>{const c=document.createElement('div');c.className='as-terminal-agent';const h=document.createElement('div');h.className='as-terminal-agent-head';const dot=document.createElement('span');dot.className='as-terminal-dot';dot.style.background=stateColor(a.state);h.append(dot,document.createTextNode(a.name));const label=document.createElement('div');label.className='as-terminal-label';label.textContent=(a.label||a.state||'')+(a.health&&(a.health.checking?' · يفحص…':a.health.label&&a.health.status!=='ok'?' · '+a.health.label:''));if(a.health&&a.health.status&&a.health.status!=='ok'){label.title='الإصدار '+(a.health.version||'؟')+(a.health.latest?' · الأحدث '+a.health.latest:'');}const actions=document.createElement('div');actions.className='as-terminal-actions';(a.state==='stopped'?[['تشغيل','start']]:[['إعادة تشغيل','restart'],['إيقاف','stop']]).forEach(([t,op])=>{const b=document.createElement('button');b.className='btn';b.textContent=t;b.disabled=op==='start'&&a.installed===false;b.title=a.installed===false?'غير مثبّت':t;b.onclick=async(ev)=>{ev.stopPropagation();try{await req(op,{id:a.id});if(op!=='stop')showAgent(a.id);setTimeout(refreshList,250);}catch(_){}};actions.appendChild(b);});if(a.installed===false){const not=document.createElement('small');not.textContent='غير مثبّت';not.className='as-card-err';actions.appendChild(not);}c.classList.toggle('is-shown',slots.some(x=>x.id===a.id));c.onclick=()=>showAgent(a.id);c.append(h,label,actions);cards.appendChild(c);});root.querySelectorAll('.as-terminal-window').forEach((w,i)=>{const s=w.querySelector('select');if(!s)return;const old=slots[i]?.id;s.replaceChildren();agents.forEach(a=>{const o=document.createElement('option');o.value=a.id;o.textContent=a.name+' · '+a.label;s.appendChild(o);});if(old&&agents.some(a=>a.id===old))s.value=old;});}
  const KEYMAP={Enter:'Enter',Backspace:'BSpace',Tab:'Tab',ArrowUp:'Up',ArrowDown:'Down',ArrowLeft:'Left',ArrowRight:'Right',Home:'Home',End:'End',PageUp:'PgUp',PageDown:'PgDn',Delete:'DC',Escape:'Escape'};
  function setMsg(slot,text,bad){if(!slot.msg)return;slot.msg.textContent=text||'';slot.msg.hidden=!text;slot.msg.style.color=bad?'#ef4444':'';}
  function wireKeys(slot){
    const pre=slot.pre,ta=slot.input;let queue=[],timer=null,composing=false;
    const flush=()=>{timer=null;if(!queue.length)return;const batch=queue;queue=[];let text='',keys=[];const emit=()=>{if(text||keys.length)send(slot,{...(text?{text}:{}),...(keys.length?{keys}:{})});text='';keys=[];};for(const p of batch){if(p.text!=null){if(keys.length)emit();text+=p.text;}else keys.push(p.key);}emit();};
    const push=p=>{queue.push(p);if(!timer)timer=setTimeout(flush,8);};
    const focusIt=()=>{ta.focus({preventScroll:true});};
    // تحديد جزء من السطر الحالي ثم الكتابة فوقه: نحرّك المؤشر إلى نهاية التحديد ونمسح ما حُدِّد ثم يصل الحرف الجديد
    const selInfo=()=>{const s=getSelection();if(!s||!s.rangeCount||s.isCollapsed)return null;const r=s.getRangeAt(0);if(!pre.contains(r.startContainer)||!pre.contains(r.endContainer))return null;const off=(n,o)=>{const x=document.createRange();x.selectNodeContents(pre);x.setEnd(n,o);return x.toString().length;};const a=off(r.startContainer,r.startOffset),b=off(r.endContainer,r.endOffset);return a<b?{a,b}:null;};
    slot.holdSel=()=>!!selInfo();
    const replaceSel=()=>{
      const info=selInfo(),cur=slot.cur;if(!info||!cur)return false;
      const lines=pre.textContent.split('\n');if(lines[lines.length-1]==='')lines.pop();
      const find=p=>{let pos=0;for(let i=0;i<lines.length;i++){if(p<=pos+lines[i].length)return [i,p-pos];pos+=lines[i].length+1;}return [-1,0];};
      const [la,sc]=find(info.a),[lb,eb]=find(info.b);
      if(la<0||la!==lb||la!==lines.length-cur.rows+cur.cy)return false;
      const line=lines[la],trimmed=line.replace(/\s+$/,'').length,ec=Math.min(eb,trimmed);
      const pm=line.match(/^\s*(?:[│|]\s*)?(?:[❯>$%#›»➜]\s+)/),pl=pm?pm[0].length:0;   // النقر الثلاثي يحدد السطر كله: لا نمس المحث
      const sc2=Math.max(sc,pl);
      if(sc2>=ec)return false;
      const at=line.length>cur.cols?trimmed:Math.min(cur.cx,line.length),d=ec-at,keys=[];
      for(let i=0;i<Math.abs(d);i++)keys.push(d>0?'Right':'Left');
      for(let i=0;i<ec-sc2;i++)keys.push('BSpace');
      clearTimeout(timer);flush();
      if(keys.length)send(slot,{keys});
      try{getSelection().removeAllRanges();}catch(_){}
      slot.hash='';
      return true;
    };
    // التركيز على مربع الإدخال أثناء السحب كان يلغي التحديد؛ لذا نؤجله إلى رفع الزر، ولا نفعله إن وُجد تحديد
    let down=false;
    pre.addEventListener('mousedown',()=>{down=true;const up=()=>{document.removeEventListener('mouseup',up,true);down=false;setTimeout(()=>{if(!selInfo())focusIt();},0);};document.addEventListener('mouseup',up,true);});
    pre.addEventListener('focus',()=>{if(!down)focusIt();});
    pre.addEventListener('keydown',e=>{
      if(e.metaKey||e.ctrlKey||e.altKey||!selInfo())return;
      if(e.key==='Backspace'||e.key==='Delete'){if(replaceSel())e.preventDefault();return;}
      if(e.key.length===1||e.keyCode===229){replaceSel();focusIt();}
    });
    pre.addEventListener('paste',e=>{const t=e.clipboardData&&e.clipboardData.getData('text/plain');if(!t)return;e.preventDefault();replaceSel();send(slot,{text:t,paste:true});});
    ta.addEventListener('focus',()=>{activeSlot=slots.indexOf(slot);setMsg(slot,'اكتب الآن…');});
    ta.addEventListener('blur',()=>setMsg(slot,''));
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
  // عدد الأعمدة يُقاس بخط الشاشة نفسه (كان يُقاس بخط أصغر فيُعطى الوكيل عرضًا أكبر من الظاهر: كلام يخرج عن الشاشة وخطوط مكسورة)،
  // ولا يُرسل المقاس إلا إذا تغيّر فعلًا (كان كل ظهور لشريط التمرير يغيّر العرض فيعيد الوكيل الرسم فترتجف الشاشة)
  function resizeSlot(slot){if(!slot.id||!slot.pre||slot.hidden||slot.view==='answer'||['perplexity','verdict','deep'].includes(slot.id))return;const cs=getComputedStyle(slot.pre);const probe=document.createElement('span');probe.textContent='MMMMMMMMMM';probe.style.cssText='position:absolute;visibility:hidden;white-space:pre;font:'+cs.font;slot.pre.appendChild(probe);const cw=(probe.getBoundingClientRect().width/10)||7.6,ch=parseFloat(cs.lineHeight)||17.5;probe.remove();const padX=(parseFloat(cs.paddingLeft)||0)+(parseFloat(cs.paddingRight)||0),padY=(parseFloat(cs.paddingTop)||0)+(parseFloat(cs.paddingBottom)||0);const cols=Math.max(20,Math.floor((slot.pre.clientWidth-padX-2)/cw)),rows=Math.max(5,Math.floor((slot.pre.clientHeight-padY)/ch));const key=slot.id+':'+cols+'x'+rows;if(slot.lastSize===key)return;clearTimeout(slot.resizeTimer);slot.resizeTimer=setTimeout(()=>{slot.lastSize=key;req('resize',{id:slot.id,cols,rows}).catch(()=>{slot.lastSize='';});},250);}
  function showAgent(id){req('health',{id,check:true}).catch(()=>{});const found=slots.findIndex(s=>s.id===id);if(found>=0)activeSlot=found;else {selectAgentForActiveSlot(id);const changed=slots[activeSlot];if(changed)changed.answerKey='';}const sl=slots[activeSlot];if(sl){sl.hidden=false;updateSlotIdentity(sl);setSlotView(sl,'terminal',true);tileSlots();}refreshScreens(true);}
  function showAgents(ids){if(!root)return false;ids=(ids||[]).filter(Boolean).slice(0,5);if(!ids.length)return false;layout=ids.length;slots=ids.map(id=>({id,hash:'',pre:null,select:null,card:null}));activeSlot=0;build();builtLayout=layout;refreshList();refreshScreens(true);return true;}
  function syncSelects(){slots.forEach((slot,i)=>{if(!slot.id&&agents.length){slot.id=(agents[i]||agents[0]).id;updateSlotIdentity(slot);refreshScreens(true,slot);}if(!slot.select)return;if(!slot.id&&agents[i])slot.id=agents[i].id||agents[0]?.id||'';if(!slot.id&&agents[0])slot.id=agents[0].id;const sel=slot.select;sel.replaceChildren();agents.forEach(a=>{const o=document.createElement('option');o.value=a.id;o.textContent=a.name+' · '+(a.label||a.state||'');sel.appendChild(o);});if(slot.id)sel.value=slot.id;});}
  async function refreshList(){if(!root||listBusy)return;listBusy=true;try{const [data,customData]=await Promise.all([req('list'),fetch('/api/term/custom').then(r=>r.json()).catch(()=>({shortcuts:[]}))]);agents=Array.isArray(data.agents)?data.agents:[];shortcuts=Array.isArray(customData.shortcuts)?customData.shortcuts:[];notify=!!data.notify;guard=data.guard!==false;const hint=root.querySelector('.as-memory-hint'),app=root.querySelector('.as-terminal');if(data.available===false){if(hint){hint.hidden=false;hint.textContent=data.hint||'الطرفية غير متاحة';}if(app)app.hidden=true;}else{if(hint)hint.hidden=true;if(app)app.hidden=false;if(builtLayout!==layout){build();builtLayout=layout;}else if(!railBusy())renderRail();syncSelects();updateSlotBadges();slots.forEach(updateSlotIdentity);}}catch(e){const hint=root.querySelector('.as-memory-hint');if(hint){hint.hidden=false;hint.textContent='تعذر تحميل قائمة الطرفيات: '+e.message;}}finally{listBusy=false;}}
  async function refreshScreens(force,only){if(!root||root.hidden)return;root.style.setProperty('--tt-size',termFont+'px');for(const slot of (only?[only]:slots)){if(!slot.id||!slot.pre||['perplexity','verdict','deep'].includes(slot.id))continue;try{if(!force&&slot.holdSel&&slot.holdSel())continue;const d=await req('screen?id='+encodeURIComponent(slot.id)+'&since='+encodeURIComponent(force?'':slot.hash)+'&hist='+hist);if(d.hash)slot.hash=d.hash;if(!d.unchanged&&typeof d.text==='string'){slot.cur=d.cursor?{cx:d.cursor[0],cy:d.cursor[1],rows:d.rows,cols:d.cols,alt:!!d.alt}:null;const pre=slot.pre,stick=pre.scrollHeight-pre.scrollTop-pre.clientHeight<40||!pre.dataset.init;pre.innerHTML=ansiHtml(d.text);pre.dataset.init='1';if(stick)pre.scrollTop=pre.scrollHeight;}if(d.alive===false)slot.pre.dataset.dead='true';}catch(_){}}}


  function activate(el){if(!el)return;if(root&&root.parentNode===el&&listTimer)return;const host=document.createElement('div');el.replaceChildren(host);root=host;hist=1500;builtLayout=0;build();builtLayout=layout;refreshList();clearInterval(listTimer);listTimer=setInterval(refreshList,2000);clearInterval(screenTimer);screenTimer=setInterval(screenTick,100);refreshScreens(true);clearInterval(roundTimer);roundTimer=setInterval(pollRound,2000);if(round)pollRound();else req('round/last').then(r=>{if(root&&r.round){round=r.round;slots=Object.keys(round.agents||{}).map(id=>({id,hash:'',view:'answer',manual:false}));if(slots.length){layout=slots.length;builtLayout=layout;activeSlot=0;build();}pollRound();}}).catch(()=>{});}
  // بعد أي إدخال يُحدَّث الشاشة النشطة كل ~100ms لثانيتين ونصف، وفي الراحة كل نصف ثانية؛ ولا تتراكم الطلبات
  async function screenTick(){if(screenBusy||!root)return;const now=Date.now(),fast=now<fastUntil;if(!fast&&now-lastFull<500)return;lastFull=now;screenBusy=true;try{await refreshScreens(false,fast?slots[activeSlot]:null);}finally{screenBusy=false;}}
  function deactivate(){clearInterval(listTimer);clearInterval(screenTimer);clearInterval(roundTimer);listTimer=screenTimer=roundTimer=null;resizeObserver?.disconnect();resizeObserver=null;closeBroadcastPanel();root=null;}

  // نافذة الطرفية المستقلة: أزرار التحكم في أقصى اليسار مثل نوافذ macOS
  let win = null;
  function toggleWindow(tabOrOpts, maybeOpts){
    const opts = (tabOrOpts && typeof tabOrOpts === 'object') ? tabOrOpts : (maybeOpts || {});
    const isApp = opts.app === true;
    if (win && win.el.isConnected) {
      if (isApp) {
        win.show();
        return;
      }
      if (win.el.hidden) {
        win.el.hidden = false;
        win.show();
      } else {
        closeWindow();
      }
      return;
    }
    const GEO = 'zajel_term_win_geo';
    const el = document.createElement('div'); el.id = 'zajel-term-window'; el.dir = 'ltr';
    if (isApp) el.classList.add('is-app');
    let geo = null, maximized = false, prev = null;
    if (!isApp) {
      try { geo = JSON.parse(localStorage.getItem(GEO) || 'null'); } catch (_) {}
      // أول فتح: نصف عرض زاجل ونصف ارتفاعه في الوسط؛ بعده آخر حجم ومكان، مصغَّرًا ليدخل في النافذة الحالية
      if (!geo || !(geo.w > 0 && geo.h > 0)) { const w = Math.round(innerWidth * 0.5), h = Math.round(innerHeight * 0.5); geo = { x: (innerWidth - w) / 2, y: (innerHeight - h) / 2, w, h }; }
      geo.w = Math.max(420, Math.min(geo.w, innerWidth - 16)); geo.h = Math.max(280, Math.min(geo.h, innerHeight - 16));
      geo.x = Math.max(0, Math.min(geo.x, innerWidth - geo.w)); geo.y = Math.max(0, Math.min(geo.y, innerHeight - geo.h));
      el.style.cssText = `position:fixed;left:${geo.x}px;top:${geo.y}px;width:${geo.w}px;height:${geo.h}px;min-width:420px;min-height:280px;z-index:10002;display:flex;flex-direction:column;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:12px;box-shadow:0 12px 48px #0006;overflow:hidden;resize:both`;
    } else {
      el.style.cssText = 'position:fixed;inset:0;width:auto;height:auto;max-height:100dvh;margin:0;border:0;border-radius:0;box-shadow:none;overflow:hidden;resize:none;z-index:10002;display:flex;flex-direction:column;background:var(--bg);color:var(--ink)';
    }

    const style = document.createElement('style');
    style.textContent = '#zajel-term-window .tw-head{display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--side);border-bottom:1px solid var(--line);cursor:move;user-select:none;touch-action:none}#zajel-term-window.is-app .tw-head{cursor:default}#zajel-term-window .tw-lights{display:flex;gap:8px}#zajel-term-window .tw-light{width:13px;height:13px;border-radius:50%;border:0;padding:0;cursor:pointer;font-size:9px;line-height:13px;color:transparent}#zajel-term-window .tw-lights:hover .tw-light{color:#0009}#zajel-term-window .tw-title{flex:1;text-align:center;font-weight:600;font-size:13px}#zajel-term-window .tw-body{flex:1;min-height:0;display:flex;flex-direction:column;padding:10px;direction:rtl;overflow:hidden}#zajel-term-window.is-app .tw-body{padding:6px}';
    const head = document.createElement('div'); head.className = 'tw-head';

    if (!isApp) {
      const lights = document.createElement('div'); lights.className = 'tw-lights';
      const mk = (c, t, sym) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'tw-light'; b.style.background = c; b.title = t; b.setAttribute('aria-label', t); b.textContent = sym; return b; };
      const bClose = mk('#ff5f57', 'إغلاق', '×'), bMin = mk('#febc2e', 'تصغير', '–'), bMax = mk('#28c840', 'تكبير', '+');
      lights.append(bClose, bMin, bMax);
      head.append(lights);
      bClose.onclick = closeWindow;
      let minimized = false;
      bMin.onclick = () => { minimized = !minimized; body.hidden = minimized; if (minimized) { prev = el.style.height; el.style.height = 'auto'; el.style.minHeight = '0'; el.style.resize = 'none'; } else { el.style.height = prev || geo.h + 'px'; el.style.minHeight = '280px'; el.style.resize = 'both'; } };
      bMax.onclick = () => { maximized = !maximized; if (maximized) { save(); prev = [el.style.left, el.style.top, el.style.width, el.style.height]; Object.assign(el.style, { left: '8px', top: '8px', width: (innerWidth - 16) + 'px', height: (innerHeight - 16) + 'px' }); } else if (prev) { [el.style.left, el.style.top, el.style.width, el.style.height] = prev; } save(); };
      head.ondblclick = ev => { if (!ev.target.closest('button')) bMax.onclick(); };
      head.onpointerdown = ev => {
        if (ev.target.closest('button') || maximized) return; ev.preventDefault();
        const sx = ev.clientX, sy = ev.clientY, ox = el.offsetLeft, oy = el.offsetTop; head.setPointerCapture(ev.pointerId);
        head.onpointermove = e2 => { el.style.left = Math.max(0, Math.min(innerWidth - 80, ox + e2.clientX - sx)) + 'px'; el.style.top = Math.max(0, Math.min(innerHeight - 40, oy + e2.clientY - sy)) + 'px'; };
        const end = e3 => { try { head.releasePointerCapture(e3.pointerId); } catch (_) {} head.onpointermove = head.onpointerup = head.onpointercancel = null; save(); };
        head.onpointerup = end; head.onpointercancel = end;
      };
      new ResizeObserver(() => { if (!maximized && !minimized) save(); }).observe(el);
    }

    const title = document.createElement('div'); title.className = 'tw-title'; title.textContent = 'طرفية زاجل';
    head.append(title);
    const body = document.createElement('div'); body.className = 'tw-body';
    el.append(style, head, body);
    document.body.appendChild(el);
    const save = () => {
      if (isApp) return;
      // وهي مكبّرة يُحفظ حجمها قبل التكبير مع علامة التكبير، فتفتح مكبّرة ويعيدها زر التصغير إلى حجمها
      const g = maximized && prev ? { x: parseFloat(prev[0]), y: parseFloat(prev[1]), w: parseFloat(prev[2]), h: parseFloat(prev[3]) } : { x: el.offsetLeft, y: el.offsetTop, w: el.offsetWidth, h: el.offsetHeight };
      g.max = maximized;
      try { localStorage.setItem(GEO, JSON.stringify(g)); } catch (_) {}
    };
    win = { el, show() {
      deactivate(); body.replaceChildren();
      const host = document.createElement('div'); host.style.cssText = 'flex:1;min-height:0;display:flex;flex-direction:column'; body.appendChild(host);
      activate(host);
    } };
    win.show();
    if (!isApp && geo.max) head.querySelector('.tw-lights button:last-child')?.onclick();
  }
  function closeWindow(){ if (!win) return; deactivate(); win.el.remove(); win = null; }

  window.ZajelTerminalUI = { showAgents, activate, deactivate, toggleWindow, closeWindow };

  // الطرفية العادية: cd إلى المجلد (أو مجلد الملف)؛ الوكيل: المسار وحده (cd ستُقرأ جزءًا من رسالتك). لا يُضغط Enter.
  function dropPaths(items, x, y) {
    if (!root || !Array.isArray(items) || !items.length) return false;
    const slot = slots.find(sl => { const r = sl.card && sl.card.getBoundingClientRect(); return r && x >= r.left && x <= r.right && y >= r.top && y <= r.bottom; });
    if (!slot || !slot.id) return false;
    const q = p => "'" + String(p).replace(/'/g, "'\\''") + "'";
    const a = agents.find(z => z.id === slot.id);
    let text;
    if (a && !a.cmd) {
      const it = items[0];
      text = 'cd ' + q(it.dir ? it.path : it.path.replace(/\/[^/]*$/, '') || '/');
    } else {
      text = items.map(it => q(it.path)).join(' ');
    }
    if (a && !a.cmd && a.state === 'stopped') {      // طرفية متوقفة: تُفتح مباشرة في ذلك المجلد
      const it = items[0];
      req('start', { id: slot.id, cwd: it.dir ? it.path : it.path.replace(/\/[^/]*$/, '') }).then(() => { showToast('فُتحت الطرفية في المجلد'); refreshList(); refreshScreens(true); }).catch(e => showToast(e.message || 'تعذّر الفتح'));
    } else {
      req('send', { id: slot.id, text }).then(() => showToast('أُدرج المسار؛ اضغط Enter حين تريد')).catch(e => showToast(e.message || 'تعذّر الإدراج'));
    }
    activeSlot = slots.indexOf(slot); slot.pre && slot.pre.focus({ preventScroll: true });
    return true;
  }

  // نافذة قراءة فوق الشاشة: السؤال ثم الجواب منسّقًا، تتمرر من أوله إلى آخره
  const mermaidUrls = new Map();
  const mermaidDiagram = /^(?:graph|flowchart|sequenceDiagram|classDiagram|stateDiagram|erDiagram|gantt|pie|mindmap|timeline|journey|quadrantChart|xychart-beta|sankey-beta|gitGraph|block-beta)\b/i;
  function mdHtml(t){const e=x=>esc(x).replace(/\*\*([^*]+)\*\*/g,'<b>$1</b>').replace(/`([^`]+)`/g,'<code>$1</code>');const out=[];let list=null,code=null,lang='';for(const raw of String(t||'').split('\n')){const l=raw.trimEnd();if(code!==null){if(/^\s*```/.test(l)){if(lang.toLowerCase()==='mermaid'||mermaidDiagram.test(code.trimStart()))out.push('<figure class="as-mermaid" data-code="'+esc(code)+'"><div>جارٍ رسم المخطط…</div></figure>');else out.push('<pre dir="ltr">'+esc(code)+'</pre>');code=null;lang='';}else code+=(code?'\n':'')+raw;continue;}const fence=l.match(/^\s*```\s*([^\s`]*)/);if(fence){code='';lang=fence[1]||'';continue;}const m=l.match(/^\s*(#{1,6})\s+(.*)/),li=l.match(/^\s*(?:[-•*·]|\d+[.)])\s+(.*)/);if(!li&&list){out.push('</'+list+'>');list=null;}if(m)out.push('<h'+Math.min(4,m[1].length+1)+'>'+e(m[2])+'</h'+Math.min(4,m[1].length+1)+'>');else if(li){const tag=/^\s*\d/.test(l)?'ol':'ul';if(list!==tag){if(list)out.push('</'+list+'>');out.push('<'+tag+'>');list=tag;}out.push('<li>'+e(li[1])+'</li>');}else if(l.trim())out.push('<p dir="auto">'+e(l)+'</p>');}if(list)out.push('</'+list+'>');if(code!==null){if(lang.toLowerCase()==='mermaid'||mermaidDiagram.test(code.trimStart()))out.push('<figure class="as-mermaid" data-code="'+esc(code)+'"><div>جارٍ رسم المخطط…</div></figure>');else out.push('<pre dir="ltr">'+esc(code)+'</pre>');}return out.join('');}
  function hydrateMermaid(containerEl){if(!containerEl)return;containerEl.querySelectorAll('figure.as-mermaid:not([data-done])').forEach(async figure=>{figure.dataset.done='1';const code=figure.dataset.code||'';try{let url=mermaidUrls.get(code);if(!url){const res=await fetch('/api/term/mermaid_png',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code})});if(!res.ok)throw new Error('render failed');url=URL.createObjectURL(await res.blob());mermaidUrls.set(code,url);}const img=document.createElement('img');img.alt='مخطط';img.style.cssText='max-width:100%;background:#fff;border-radius:8px';img.src=url;figure.replaceChildren(img);}catch(_){const pre=document.createElement('pre');pre.dir='ltr';pre.textContent=code;const message=document.createElement('div');message.textContent='تعذّر رسم المخطط';figure.replaceChildren(pre,message);}});}
  async function openReader(slot){if(!slot||!slot.card||!slot.id)return;slot.card.querySelector('.as-reader')?.remove();const box=document.createElement('div');box.className='as-reader';box.dir='rtl';box.style.cssText='position:absolute;inset:34px 0 0 0;z-index:20;background:var(--panel);color:var(--ink);overflow-y:auto;padding:14px 18px 40px;font:calc(var(--tt-size,12.5px) + 2.5px)/1.75 "SF Arabic","Geeza Pro",system-ui,sans-serif;border-top:2px solid '+colorOf(slot.id);const close=document.createElement('button');close.type='button';close.className='btn';close.textContent='✕ إغلاق';close.style.cssText='position:sticky;top:0;float:left;z-index:1';close.onclick=()=>box.remove();box.appendChild(close);const body=document.createElement('div');body.textContent='يقرأ الجواب…';box.appendChild(body);slot.card.appendChild(box);box.addEventListener('keydown',e=>{if(e.key==='Escape')box.remove();});try{const r=await fetch('/api/term/last_answer?id='+encodeURIComponent(slot.id)).then(x=>x.json());if(r.error)throw new Error(r.error);if(!r.answer){body.textContent=r.question?'لم يكتمل جواب آخر سؤال بعد.':'لم أجد سؤالًا عند هذا الوكيل بعد.';return;}body.innerHTML='<div style="background:var(--side);border-inline-start:3px solid '+colorOf(slot.id)+';padding:8px 12px;border-radius:8px;margin:6px 0 14px"><b>السؤال</b><p dir="auto" style="margin:4px 0 0">'+esc(r.question)+'</p></div><div class="as-reader-md">'+mdHtml(r.answer)+'</div>';hydrateMermaid(body);}catch(e){body.textContent=e.message||'تعذّرت القراءة';}}

    // جواب نافذة Perplexity: يقرؤه البرنامج من الصفحة ويعيده عبر __zajelWeb (طابور لأكثر من طالب)
  window.__zajelWebQ = window.__zajelWebQ || [];
  window.__zajelWeb = j => { window.__zajelWebQ.splice(0).forEach(f => f(j)); };
  function getWebAnswer() {
    const h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.zajel;
    if (!h) return Promise.resolve(null);
    return new Promise(res => { const t = setTimeout(() => res(null), 2500); window.__zajelWebQ.push(j => { clearTimeout(t); res(j); }); h.postMessage({ getWeb: 1 }); });
  }

  function tileSlots(){if(!root)return;const grid=root.querySelector('.as-terminal-grid'),chips=root.querySelector('.as-hidden-chips');if(!grid||!chips)return;chips.replaceChildren();slots.forEach(s=>{if(!s.card)return;s.card.hidden=!!s.hidden;if(s.hidden){const b=document.createElement('button');b.className='btn';b.textContent=glyphOf(s.id,s.nameEl?.textContent)+' '+(s.nameEl?.textContent||s.id);b.title='إظهار البطاقة';b.onclick=()=>{s.hidden=false;tileSlots();};chips.appendChild(b);}});const n=slots.filter(s=>!s.hidden).length,cols=n<=2?n:n<=4?2:3;grid.style.gridTemplateColumns='repeat('+Math.max(1,cols)+', minmax(0,1fr))';slots.forEach(s=>{s.lastSize='';if(!s.hidden)resizeSlot(s);});}
  function setSlotView(slot,view,manual){if(!slot?.card)return;if(manual)slot.manual=true;if(['perplexity','verdict','deep'].includes(slot.id))view='answer';slot.view=view;slot.pre.style.display=view==='answer'?'none':'';if(slot.answerEl)slot.answerEl.hidden=view!=='answer';if(slot.viewBtn){slot.viewBtn.textContent=view==='answer'?'⌨️':'📖';slot.viewBtn.title=view==='answer'?'عرض الطرفية':'عرض الجواب';}if(view==='terminal'){slot.card.querySelector('.as-reader:not(.as-round-answer)')?.remove();slot.lastSize='';resizeSlot(slot);}else renderAnswer(slot);}
  function answerView(slot){slot.answerKey='';const el=document.createElement('div');el.className='as-reader as-round-answer';el.dir='rtl';slot.answerEl=el;slot.card.appendChild(el);renderAnswer(slot);}
  function renderAnswer(slot){if(!slot.answerEl||!round)return;const ag=round.agents?.[slot.id],text=slot.id==='verdict'?round.verdict:slot.id==='deep'?round.deep_answer:ag?.answer||'';const key=round.question+'\n'+text;if(slot.answerKey===key)return;const el=slot.answerEl,atEnd=el.scrollHeight-el.scrollTop-el.clientHeight<40||!slot.answerKey;el.innerHTML='<div style="background:var(--side);border-inline-start:3px solid '+colorOf(slot.id)+';padding:6px 10px;border-radius:8px"><b>السؤال</b><p dir="auto">'+esc(round.question)+'</p></div>'+(text?mdHtml(text):'<p>ينتظر الجواب…</p>');slot.answerKey=key;hydrateMermaid(el);if(atEnd)el.scrollTop=el.scrollHeight;}
  async function roundAction(action,extra={}){if(!round)return;try{const r=await req('round/'+action,{round_id:round.round_id,...extra});if(r.error)throw new Error(r.error);if(action==='export')showToast('حُفظ المستند: '+(r.title||'كل الأجوبة')+(r.missing?.length?' · لم يكتمل: '+r.missing.join('، '):''));else {round=r;await pollRound();}}catch(e){showToast(e.message||'تعذّر تنفيذ الطلب');}}
  async function pollRound(){if(!root||!round||roundBusy)return;roundBusy=true;const rid=round.round_id;try{const r=await req('round/status?id='+encodeURIComponent(rid));if(!root||round?.round_id!==rid)return;if(r.error)throw new Error(r.error);const old=round;round=r;let added=false;for(const [id,field,state,name] of [['verdict','verdict','judge_state','⚖️ الحكم'],['deep','deep_answer','deep_state','🔬 بحث متعمق']]){if((r[field]||!['idle','waiting_answers'].includes(r[state]))&&!slots.some(s=>s.id===id)){slots.push({id,view:'answer',manual:false,hash:''});layout=slots.length;added=true;}}if(added){builtLayout=layout;build();}slots.forEach(s=>{const a=r.agents?.[s.id];if(a&&!s.manual&&s.id!=='perplexity'){const prev=old.agents?.[s.id]?.answer||'',live=agents.find(x=>x.id===s.id);if(a.state==='needs_input'||(!a.answer&&Date.now()/1000-r.created>=20))setSlotView(s,'terminal',false);else if(a.state==='writing'&&a.answer&&a.answer!==prev)setSlotView(s,'answer',false);}renderAnswer(s);});updateSlotBadges();const jb=root.querySelector('[data-round-judge]');if(jb)jb.disabled=Object.values(r.agents||{}).filter(a=>a.state==='done').length<2;
      if(r.agents?.perplexity){const j=await getWebAnswer();if(!root||round?.round_id!==rid)return;const ans=j?.answer||'';if(ans&&ans===webLast)webSame++;else{webLast=ans;webSame=0;}if(ans&&webSame>=3&&ans!==webPosted&&(!j.question||j.question.trim()===r.question.trim())){await req('round/web_answer',{round_id:rid,question:r.question,answer:ans});webPosted=ans;}}
    }catch(e){console.warn('round status',e);}finally{roundBusy=false;}}

  // داخل البرنامج: نافذة Perplexity تابعة لزاجل (تتذكر الدخول)؛ في المتصفح العادي: تبويب جديد
  function openPerplexity(text, background, deep) {
    // deep: وضع البحث المتعمق (Research) عبر mode=research — معامل غير موثّق رسميًّا، يعمل في واجهة الموقع الحالية
    const url = 'https://www.perplexity.ai/' + (text ? (deep ? '?q=' + encodeURIComponent(text) + '&mode=research' : 'search?q=' + encodeURIComponent(text)) : '');
    const h = window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.zajel;
    if (h) h.postMessage(text ? { web: url, background: !!background } : { webShow: 1 }); else window.open(url, '_blank');   // الزر بلا سؤال يُظهر النافذة بجوابها كما هو
  }

  window.ZajelTermApp = {
    perplexity: openPerplexity,
    dropPaths,
    async open(id) {
      const isApp = new URLSearchParams(location.search).get('mode') === 'terminal';
      if (!win || !win.el.isConnected) {
        toggleWindow({ app: isApp });
      }
      showAgent(id);
      const a = agents.find(x => x.id === id);
      if (!a || a.state === 'stopped') {
        try { await req('start', { id }); } catch (_) {}
      }
      refreshScreens(true);
      refreshList();
    },
    async startAll() {
      try {
        const d = await req('list');
        const list = Array.isArray(d.agents) ? d.agents : agents;
        const toStart = list.filter(a => a.cmd && a.installed !== false && a.state === 'stopped');
        await Promise.all(toStart.map(a => req('start', { id: a.id }).catch(() => {})));
        await refreshList();
      } catch (_) {}
    },
    async checkAll() {
      try {
        const d = await req('list');
        const list = Array.isArray(d.agents) ? d.agents : agents;
        await Promise.all(list.map(a => req('health', { id: a.id, check: true, force: true }).catch(() => {})));
        await refreshList();
      } catch (_) {}
    },
    broadcast() {
      const isApp = new URLSearchParams(location.search).get('mode') === 'terminal';
      if (!win || !win.el.isConnected) {
        toggleWindow({ app: isApp });
      } else if (win.el.hidden) {
        win.el.hidden = false;
        win.show();
      }
      setTimeout(() => {
        const btn = root?.querySelector('.as-broadcast-btn');
        if (btn) {
          if (!broadcastPanel) openBroadcastPanel(btn);
          else broadcastPanel.querySelector('textarea')?.focus();
        }
      }, 60);
    },
    async refresh() {
      await refreshList();
      await refreshScreens(true);
    }
  };
})();
