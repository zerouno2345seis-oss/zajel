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


def extract_citations(text, answer_code='ج'):
    """Return references in their source order; identifiers are stable per answer."""
    text = html.unescape(text or '')
    in_sources = False
    refs, seen = [], set()
    lines = text.splitlines()
    for line in lines:
        clean = re.sub(r'^[\s#*\-]+', '', line).strip(' :：')
        if re.fullmatch(r'(?:المصادر|المراجع|الحواشي|الهوامش)(?:\s+.*)?', clean):
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
        url_match = _URL.search(source)
        quote = _first_quote(source)
        if not quote:
            marker = re.search(r'\[\^?' + re.escape(number) + r'\]', text[:text.find(line)])
            if marker:
                preceding = text[max(0, marker.start() - 1000):marker.start()]
                quotes = list(_QUOTE.finditer(preceding))
                if quotes and not preceding[quotes[-1].end():].strip(' .،,:؛\n'):
                    quote = (quotes[-1].group(1) or quotes[-1].group(2)).strip()
        parts = [p.strip() for p in re.split(r'[,،]', source) if p.strip()]
        refs.append({'id': answer_code + str(len(refs) + 1).translate(_ARABIC_DIGITS),
                     'number': number, 'source': source, 'author': parts[0] if len(parts) > 1 else '',
                     'book': parts[1] if len(parts) > 1 else parts[0] if parts else '',
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


def _check_one(ref, fetcher, local_reader):
    item = dict(ref)
    quote = item.get('quote', '')
    item.update(status='❓ تعذّر التحقق', reason='')
    if len(normalize(quote).replace(' ', '')) < 20:
        item['reason'] = 'لا يوجد اقتباس كافٍ للمطابقة'
        return item
    try:
        source = local_reader(item) if local_reader else None
        if not source and item.get('url'):
            source = fetcher(item['url'])
        if not source or not normalize(source):
            item['reason'] = 'لم يتوفر نص المصدر'
        elif _matches(quote, source):
            item.update(status='✅ موثّق', reason='وُجد النص في المصدر بعد التطبيع')
        else:
            # غياب الاقتباس من الصفحة لا يثبت أنه غير موجود في الكتاب (صفحة جزئية أو موضع آخر): خلل لا «غير موجود»
            item.update(status='⚠️ فيه خلل', reason='لم يُعثر على الاقتباس في الصفحة المحال إليها (قد يكون الموضع أو الصفحة مختلفة)')
    except Exception:
        item['reason'] = 'تعذر جلب نص المصدر أو قراءته'
    return item


def check_citations(refs, fetcher=None, local_reader=None, workers=6):
    """Return new reference dictionaries with status and reason, in input order; readers are injectable. Fetches run in parallel."""
    fetcher = fetcher or fetch_source
    refs = list(refs)
    if len(refs) <= 1:
        return [_check_one(r, fetcher, local_reader) for r in refs]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=min(workers, len(refs))) as ex:
        return list(ex.map(lambda r: _check_one(r, fetcher, local_reader), refs))
