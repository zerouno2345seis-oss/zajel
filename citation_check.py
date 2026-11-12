"""فهرسة الإحالات والتحقق المحافظ من النصوص المنقولة.

يستطيع المستدعي تمرير جالب بديل أو قارئ محلي اختياري. غياب النص أو المصدر
لا يعني أن الإحالة خاطئة؛ لا نحكم عليها إلا عند توفر نص المصدر والاقتباس.
"""
import difflib
import html
import ipaddress
import re
import socket
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

_ARABIC_DIGITS = str.maketrans('0123456789', '٠١٢٣٤٥٦٧٨٩')
_URL = re.compile(r'https?://[^\s<>\]»"\)]+', re.I)
_QUOTE = re.compile(r'«([^»]+)»|"([^"\n]+)"')
_DEF = re.compile(r'^\s*(?:[-*]\s*)?\[\^?(\d+|[٠-٩]+)\]\s*[:.\-]?\s*(.+)$')


def normalize(text):
    text = unicodedata.normalize('NFKC', html.unescape(text or ''))
    text = ''.join(ch for ch in text if not unicodedata.combining(ch) and ch != 'ـ')
    text = text.translate(str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ئ': 'ي', 'ة': 'ه'}))
    return ' '.join(re.sub(r'[^\w]+', ' ', text.casefold()).split())


def _first_quote(text):
    match = _QUOTE.search(text)
    return (match.group(1) or match.group(2)).strip() if match else ''


def _number(text, labels):
    match = re.search(r'(?:' + labels + r')\s*[:：]?\s*([\d٠-٩]+)', text)
    return match.group(1) if match else ''


_LABELS = r'(?:المؤلف|الكتاب|الجزء والصفحة|الجزء|الصفحة|الرابط|النص المنقول حرفي[اًا]|النص المنقول|النص)'


def _labeled(source, label):
    """قيمة حقل مسمّى في تعريف متعدد الأسطر («المؤلف: …» ثم «الكتاب: …»)، أو ''."""
    m = re.search(label + r'\s*[:：]\s*(.+?)(?=\s+' + _LABELS + r'\s*[:：]|$)', source)
    return m.group(1).strip(' .،؛') if m else ''


def _heading(line):
    """هل السطر عنوان قسم المصادر؟ يقبل الإبراز بنجوم أو شرطات سفلية أو علامات # («**المصادر**»، «## **المصادر:**»)."""
    clean = re.sub(r'^[\s#*_\-]+', '', line)
    clean = re.sub(r'[\s#*_:：]+$', '', clean)
    return bool(re.fullmatch(r'(?:المصادر|المراجع|الحواشي|الهوامش)(?:\s+.*)?', clean))


def extract_citations(text, answer_code='ج'):
    """Return references in their source order; identifiers are stable per answer.
    التعريف قد يمتد على أسطر تالية (المؤلف/الكتاب/النص المنقول…) حتى التعريف التالي أو عنوان أو وسم أو آخر النص."""
    text = html.unescape(text or '')
    in_sources = False
    refs, seen = [], set()
    lines = text.splitlines()
    pos = 0
    for idx, line in enumerate(lines):
        line_start = pos
        pos += len(line) + 1
        if _heading(line):
            in_sources = True
            continue
        m = _DEF.match(line)
        if not m or (not in_sources and not re.match(r'^\s*\[\^\d+\]\s*:', line)):
            continue
        number, source = m.groups()
        number = number.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789'))
        if number in seen:
            continue
        seen.add(number)
        extra = []
        for nxt in lines[idx + 1:idx + 41]:
            if _DEF.match(nxt) or re.match(r'^\s*(?:#|<\w)', nxt) or _heading(nxt):
                break
            joined = source + ' ' + ' '.join(extra)
            if not nxt.strip() and joined.count('«') <= joined.count('»'):
                break                        # سطر فارغ يُنهي التعريف إلا إن كان اقتباس «…» مفتوحًا
            extra.append(nxt.strip())
        while extra and not extra[-1]:
            extra.pop()
        source = ' '.join((' '.join([source] + extra)).split())
        url_match = _URL.search(source)
        quote = _first_quote(source)
        if not quote:
            marker = re.search(r'\[\^?' + re.escape(number) + r'\]', text[:line_start])
            if marker:
                preceding = text[max(0, marker.start() - 1000):marker.start()]
                quotes = list(_QUOTE.finditer(preceding))
                if quotes and not preceding[quotes[-1].end():].strip(' .،,:؛\n'):
                    quote = (quotes[-1].group(1) or quotes[-1].group(2)).strip()
        parts = [p.strip() for p in re.split(r'[,،]', source) if p.strip()]
        author, book = _labeled(source, 'المؤلف'), _labeled(source, 'الكتاب')
        refs.append({'id': answer_code + str(len(refs) + 1).translate(_ARABIC_DIGITS),
                     'number': number, 'source': source, 'author': author or (parts[0] if len(parts) > 1 else ''),
                     'book': book or (parts[1] if len(parts) > 1 else parts[0] if parts else ''),
                     'part': _number(source, r'الجزء|جزء|ج'), 'page': _number(source, r'الصفحة|صفحة|ص'),
                     'url': url_match.group().rstrip('.,،؛') if url_match else '', 'quote': quote})
    return refs


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('script', 'style', 'noscript'):
            self.hidden += 1
        elif not self.hidden:
            self.parts.append(' ')

    def handle_endtag(self, tag):
        if tag.lower() in ('script', 'style', 'noscript') and self.hidden:
            self.hidden -= 1
        elif not self.hidden:
            self.parts.append(' ')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _validate_url(url):
    parsed = urlsplit(url)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('رابط غير صالح')
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80), type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ValueError('الرابط لا يشير إلى موقع عام')
    except socket.gaierror as exc:
        raise ValueError('تعذر الوصول إلى الموقع') from exc


class _SafeRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_source(url, timeout=4, max_bytes=1_000_000):
    """Fetch limited public HTML only; reject local addresses and unsafe redirects."""
    _validate_url(url)
    request = Request(url, headers={'User-Agent': 'ZajelCitationCheck/1.0'})
    with build_opener(_SafeRedirect()).open(request, timeout=timeout) as response:
        if response.headers.get_content_type() not in ('text/html', 'text/plain', 'application/xhtml+xml'):
            raise ValueError('نوع الصفحة غير مدعوم')
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError('حجم الصفحة أكبر من الحد المسموح')
        text = data.decode(response.headers.get_content_charset() or 'utf-8', errors='replace')
    parser = _TextParser()
    parser.feed(text)
    return ' '.join(parser.parts)


def _matches(quote, source):
    q, s = normalize(quote), normalize(source)
    if q in s:
        return True
    # Compare windows by words to allow minor OCR or spelling differences.
    words, target = s.split(), q.split()
    if len(target) < 4:
        return False
    # Compare only windows anchored by meaningful quotation words; bounded work
    # even when a fetched page contains hundreds of thousands of words.
    anchors = {word for word in target if len(word) >= 4}
    positions = {}
    for i, word in enumerate(words):
        if word in anchors and len(positions.setdefault(word, [])) < 50:
            positions[word].append(i)
    candidates = set()
    for offset, word in enumerate(target):
        for pos in positions.get(word, []):
            candidates.add(max(0, pos - offset))
    for start in list(sorted(candidates))[:1000]:
        for size in range(max(1, len(target) - 2), len(target) + 3):
            if difflib.SequenceMatcher(None, q, ' '.join(words[start:start + size]), autojunk=False).ratio() >= .94:
                return True
    return False


PARTIAL_MIN_RATIO = 0.5    # أدنى نسبة كلمات متطابقة تُعدّ «مطابقة جزئية» حقيقية؛ دونها يُعدّ النص غير موجود (قِيس: منقول بتبديل كلمتين ٠٫٥٣، مختلق كليًا ٠٫٤٠)
VERIFY_LIMIT = 20          # أقصى عدد نصوص تُفحص بالشاملة في الجولة الواحدة


def _verify_quote(item, verifier):
    """يفحص النص المنقول بلا رابط بمدقق الشاملة: {"found","where","in_footnote"} أو None إن تعذّر الخادم. لا يرفع استثناءً."""
    quote = item.get('quote', '')
    segments = [x.strip() for x in re.split(r'\.{3,}|…', quote) if len(normalize(x).replace(' ', '')) >= 20]
    cut = bool(segments) and bool(re.search(r'\.{3,}|…', quote))
    if cut:
        quote = max(segments, key=lambda x: len(normalize(x)))       # نص مقتطع بـ«...»: يُفحص أطول مقطع متصل منه
    try:
        res = verifier(quote)
    except Exception:
        res = None
    if not isinstance(res, dict):
        item.update(status='❓ تعذّر التحقق', reason='تعذّر التحقق: خادم المكتبة الشاملة غير متاح', verify_down=True)
        return item
    where = str(res.get('where') or '').strip()
    if res.get('url'):
        item['verified_url'] = res['url']
    ratio = res.get('ratio')
    if not res.get('found') and res.get('match') == 'partial' and isinstance(ratio, (int, float)) and ratio >= PARTIAL_MIN_RATIO:
        item.update(status='⚠️ فيه خلل', reason='مطابقة جزئية فقط: النص المنقول يختلف عن الأصل' + (': ' + where if where else ''))
    elif not res.get('found'):
        item.update(status='❌ غير موجود', reason='لم يوجد النص في كتب المكتبة الشاملة المنزَّلة (قد يكون الكتاب غير منزَّل أو النص بمعناه لا بلفظه)')
    elif res.get('in_footnote'):
        item.update(status='⚠️ فيه خلل', reason='النص موجود في الحاشية لا في المتن (كلام المحقق أو المعلّق لا المصنف)' + (': ' + where if where else ''))
    else:
        item.update(status='✅ موثّق', reason='النص موجود في المتن' + (': ' + where if where else '')
                    + (' (باختلاف يسير في الضبط أو الرسم)' if res.get('match') == 'differs' else ''))
    if cut:
        item['reason'] += ' (النص مقتطع بـ«...»: فُحص أطول مقطع متصل منه)'
    return item


def _matches_all(quote, source):
    """نص مقتطع بـ«...»: كل مقطع طويل منه (٢٠ حرفًا فأكثر) يجب أن يوجد في المصدر؛ ونص بلا اقتطاع يُطابَق كاملًا."""
    segments = [x for x in re.split(r'\.{3,}|…', quote) if len(normalize(x).replace(' ', '')) >= 20]
    if len(segments) > 1:
        return all(_matches(x, source) for x in segments)
    return _matches(segments[0] if segments else quote, source)


def _check_one(ref, fetcher, local_reader, verifier=None, over_limit=False):
    item = dict(ref)
    quote = item.get('quote', '')
    item.update(status='❓ تعذّر التحقق', reason='')
    if len(normalize(quote).replace(' ', '')) < 20:
        item['reason'] = 'لا يوجد اقتباس كافٍ للمطابقة'
        return item
    try:
        source = local_reader(item) if local_reader else None
        if not source and over_limit:
            item['reason'] = 'تجاوز حدّ التحقق الآلي بالشاملة (%d نصًّا في الجولة)' % VERIFY_LIMIT
            return item
        if not source and verifier and not item.get('url'):
            return _verify_quote(item, verifier)
        if not source and item.get('url'):
            source = fetcher(item['url'])
        if not source or not normalize(source):
            item['reason'] = 'لم يتوفر نص المصدر'
        elif _matches_all(quote, source):
            item.update(status='✅ موثّق', reason='وُجد النص في المصدر بعد التطبيع')
        else:
            # غياب الاقتباس من الصفحة لا يثبت أنه غير موجود في الكتاب (صفحة جزئية أو موضع آخر): خلل لا «غير موجود»
            item.update(status='⚠️ فيه خلل', reason='لم يُعثر على الاقتباس في الصفحة المحال إليها (قد يكون الموضع أو الصفحة مختلفة)')
    except Exception:
        item['reason'] = 'تعذر جلب نص المصدر أو قراءته'
    return item


def check_citations(refs, fetcher=None, local_reader=None, workers=6, verifier=None, verify_limit=VERIFY_LIMIT):
    """Return new reference dictionaries with status and reason, in input order; readers are injectable. Fetches run in parallel.
    verifier(quote): يفحص النص المنقول بلا رابط (مثل sources.shamela_verify)؛ يُفحص أول verify_limit نصًّا فقط."""
    fetcher = fetcher or fetch_source
    refs = list(refs)
    allowed, over = set(), set()
    if verifier:
        eligible = [i for i, r in enumerate(refs) if not r.get('url') and len(normalize(r.get('quote', '')).replace(' ', '')) >= 20]
        allowed, over = set(eligible[:verify_limit]), set(eligible[verify_limit:])
    jobs = [(r, verifier if i in allowed else None, i in over) for i, r in enumerate(refs)]
    if len(refs) <= 1:
        return [_check_one(r, fetcher, local_reader, v, o) for r, v, o in jobs]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(workers, len(refs))) as ex:
        return list(ex.map(lambda j: _check_one(j[0], fetcher, local_reader, j[1], j[2]), jobs))
