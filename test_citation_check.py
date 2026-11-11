import unittest

import citation_check as c


class CitationCheckTest(unittest.TestCase):
    def test_sources_and_footnotes_have_stable_ids(self):
        text = 'قال: «هذا نص عربي طويل صالح للاختبار» [1].\n\nالمصادر\n[1] أحمد، كتاب الفقه، ج ٢ ص ٣، https://example.org/a\n[^2]: محمد، كتاب الحديث، ص ٤ «نص آخر صالح للتحقق هنا»'
        refs = c.extract_citations(text, 'أ')
        self.assertEqual([x['id'] for x in refs], ['أ١', 'أ٢'])
        self.assertEqual(refs[0]['quote'], 'هذا نص عربي طويل صالح للاختبار')
        self.assertEqual(refs[0]['url'], 'https://example.org/a')
        self.assertEqual(refs[0]['part'], '٢')
        self.assertEqual(refs[0]['page'], '٣')

    def test_verification_only_claims_match_for_long_quote(self):
        refs = c.extract_citations('المصادر\n[1] كتاب «هذه عبارة طويلة مع التشكيل للمقارنة الآلية» https://example.org\n[2] كتاب «قصير» https://example.org', 'ج')
        verified = c.check_citations(refs, fetcher=lambda url: 'هذه عبارة طويلة مع التشكيل للمقارنة الالية')
        self.assertEqual([x['status'] for x in verified], ['✅ موثّق', '❓ تعذّر التحقق'])
        missing = c.check_citations(refs[:1], fetcher=lambda url: 'محتوى مختلف بالكامل ولا يوجد فيه شيء مشابه')
        self.assertEqual(missing[0]['status'], '⚠️ فيه خلل')
        error = c.check_citations(refs[:1], fetcher=lambda url: (_ for _ in ()).throw(OSError('offline')))
        self.assertEqual(error[0]['status'], '❓ تعذّر التحقق')

    def test_ref_without_quote_or_source_is_unknown(self):
        refs = c.extract_citations('المصادر\n[1] كتاب الفقه', 'ج')
        self.assertEqual(c.check_citations(refs, fetcher=lambda _: '')[0]['status'], '❓ تعذّر التحقق')

    def test_private_url_is_refused(self):
        with self.assertRaises(ValueError):
            c.fetch_source('http://127.0.0.1/secret')

    def test_numeric_marker_in_body_is_not_a_definition(self):
        self.assertEqual(c.extract_citations('هذا بيان [1] بلا قائمة مصادر.'), [])
