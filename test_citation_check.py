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

    def _refs(self, n, url=''):
        return [{'id': 'ج%d' % i, 'quote': 'نص منقول طويل رقم %d يكفي للفحص الآلي' % i, 'url': url} for i in range(n)]

    def test_verifier_statuses_and_unavailable(self):
        out = {}
        seen = []

        def verifier(q):
            seen.append(q)
            return out.get(q)
        refs = self._refs(4)
        out[refs[0]['quote']] = {'found': True, 'where': 'كتاب، ج١/ص٢', 'in_footnote': False}
        out[refs[1]['quote']] = {'found': True, 'where': 'كتاب، ج١/ص٣', 'in_footnote': True}
        out[refs[2]['quote']] = {'found': False, 'where': '', 'in_footnote': False}
        res = c.check_citations(refs, verifier=verifier)
        self.assertEqual([x['status'] for x in res], ['✅ موثّق', '⚠️ فيه خلل', '❌ غير موجود', '❓ تعذّر التحقق'])
        self.assertIn('كتاب، ج١/ص٢', res[0]['reason'])
        self.assertIn('الحاشية', res[1]['reason'])
        self.assertTrue(res[3].get('verify_down'))
        boom = c.check_citations(refs[:1], verifier=lambda q: (_ for _ in ()).throw(OSError('x')))
        self.assertEqual(boom[0]['status'], '❓ تعذّر التحقق')          # لا استثناء يخرج

    def test_verifier_skips_urls_short_quotes_and_caps_at_20(self):
        calls = []
        verifier = lambda q: calls.append(q) or {'found': True, 'where': 'x', 'in_footnote': False}
        with_url = self._refs(1, 'https://example.org')
        short = [{'id': 's', 'quote': 'قصير', 'url': ''}]
        res = c.check_citations(with_url + short, fetcher=lambda u: 'لا شيء', verifier=verifier)
        self.assertEqual(calls, [])
        self.assertEqual(res[0]['status'], '⚠️ فيه خلل')
        res = c.check_citations(self._refs(25), verifier=verifier)
        self.assertEqual(len(calls), 20)
        self.assertEqual(sum(x['status'] == '✅ موثّق' for x in res), 20)
        self.assertIn('حدّ', res[24]['reason'])
        self.assertEqual(res[24]['status'], '❓ تعذّر التحقق')

    def test_no_verifier_keeps_old_behavior(self):
        res = c.check_citations(self._refs(2))
        self.assertEqual([x['status'] for x in res], ['❓ تعذّر التحقق'] * 2)
        self.assertEqual(res[0]['reason'], 'لم يتوفر نص المصدر')

    def test_partial_and_differs_matches(self):
        refs = self._refs(3)
        out = {refs[0]['quote']: {'found': False, 'where': 'كتاب، ج١/ص٢', 'in_footnote': False, 'match': 'partial', 'ratio': 0.8, 'url': 'https://s/1'},
               refs[1]['quote']: {'found': True, 'where': 'كتاب، ج١/ص٣', 'in_footnote': False, 'match': 'differs', 'url': 'https://s/2'},
               refs[2]['quote']: {'found': False, 'where': '', 'in_footnote': False, 'match': 'not_found'}}
        res = c.check_citations(refs, verifier=out.get)
        self.assertEqual(res[0]['status'], '⚠️ فيه خلل')
        self.assertIn('مطابقة جزئية فقط: النص المنقول يختلف عن الأصل', res[0]['reason'])
        self.assertIn('كتاب، ج١/ص٢', res[0]['reason'])
        self.assertEqual(res[0]['verified_url'], 'https://s/1')
        self.assertEqual(res[1]['status'], '✅ موثّق')
        self.assertIn('(باختلاف يسير في الضبط أو الرسم)', res[1]['reason'])
        self.assertEqual(res[1]['verified_url'], 'https://s/2')
        self.assertEqual(res[2]['status'], '❌ غير موجود')
        self.assertNotIn('verified_url', res[2])

# أجوبة حقيقية من التجربة الحية (جولة r_20261112_125638_e953)، نُسخت حرفيًا
CODEX_REAL = 'نعم، تسقط نفقة الزوجة مدة نشوزها عند عامة الفقهاء. [1]  \nوالمقصود بالنشوز هنا امتناعها عن حق زوجها الواجب عليها بغير حق. [1]  \nوتعود نفقتها إذا زال النشوز وعادت إلى زوجها، في المذهب الحنفي. [2]  \nوذكر ابن عبد البر استثناء الحامل، وأن النفقة تعود للناشز مستقبلًا إذا عادت. [3]  \nوخالف ابن حزم، فقال بعدم سقوط نفقتها بالنشوز. [4]\n\n**المصادر**\n\n[1] عبد الله بن أحمد بن قدامة، *المغني والشرح الكبير*، ج ٩، ص ٢٩٥، [الجامع، مكتبة المسجد النبوي](https://aljam3.com/ar/35265/67449/295): «معنى النشوز معصتها لزوجها فيما له عليها مما أوجبه له النكاح»، وذكر سقوط النفقة «في قول عامة أهل العلم». النص مستخرج آليًا؛ لم أتمكن من مقابلة صورة الصفحة.\n\n[2] علي بن أبي بكر المرغيناني، *الهداية شرح بداية المبتدي*، ج ٣، ص ٣٧٨، [الجامع، مكتبة المسجد النبوي](https://aljam3.com/ar/34151/64474/378): «وإن نشزت فلا نفقة لها حتى تعود إلى منزله». النص مستخرج آليًا؛ لم أتمكن من مقابلة صورة الصفحة.\n\n[3] يوسف بن عبد الله بن عبد البر، *الكافي في فقه أهل المدينة*، ج ٢، ص ٥٥٩، الشاملة: «ومن نشزت عنه امرأته بعد دخوله بها سقطت عنه نفقتها إلا أن تكون حاملا»، و«إذا عادت الناشز إلى زوجها وجبت في المستقبل نفقتها».\n\n[4] علي بن أحمد بن حزم، *المحلى بالآثار*، ج ٩، ص ١١٤، الشاملة: «وَلَمْ يُسْقِطْ \ufdff نَفَقَتَهَا وَلَا كِسْوَتَهَا».\n\n<oai-mem-citation>\n<citation_entries>\nMEMORY.md:760-765|note=[منهج فتح صفحات الجامع والتحقق من النص]\n</citation_entries>\n<rollout_ids>\n01a13672-f8de-78a0-871f-8c6630cef7a8\n</rollout_ids>\n</oai-mem-citation>'
ANTIGRAVITY_REAL = '  نعم، تسقط نفقة الزوجة بنشوزها باتفاق عامة أهل العلم والمذاهب الفقهية الأربعة [1] [2].\n  وعلة ذلك أن النفقة إنما تجب في مقابلة الاحتباس والتمكين التام، فإذا فوّتت المرأة التمكين سقط حقها في النفقة [1].\n  ويتحقق النشوز المسقط بامتناعها من فراش زوجها، أو خروجها من مسكن الزوجية بلا إذن، أو امتناعها من السفر معه بلا مسوغ [1].\n  ولم يشذ عن قول الجمهور إلا ما رُوي عن الحَكَم بن عُتيبة، مع ثبوت بقاء نفقة الأولاد على أبيهم دون سقوطها بنشوز أمهم [1] [2].\n  ويُعدّ سقوط النفقة مانعاً عارضاً يزول بزوال علته؛ فمتى عادت الزوجة إلى الطاعة ومكّنت زوجها استحقّت نفقتها فوراً [1].\n  ### المصادر\n  [1] المكتبة الشاملة:\nالمؤلف: موفق الدين عبد الله بن أحمد بن محمد بن قدامة المقدسي.\nالكتاب: المغني (طبعة مكتبة القاهرة).\nالجزء والصفحة: ج 8، ص 236.\nالنص المنقول حرفياً: «فَمَتَى امْتَنَعَتْ مِنْ فِرَاشِهِ، أَوْ خَرَجَتْ مِنْ مَنْزِلِهِ بِغَيْرِ إذْنِهِ، أَوْ امْتَنَعَتْ مِنْ الِانْتِقَالِ مَعَهُ إلَى مَسْكَنِ مِثْلِهَا، أَوْ مِنْ السَّفَرِ مَعَهُ، فَلَا\n  نَفَقَةَ لَهَا وَلَا سُكْنَى، فِي قَوْلِ عَامَّةِ أَهْلِ الْعِلْمِ؛ مِنْهُمْ الشَّعْبِيُّ، وَحَمَّادٌ، وَمَالِكٌ، وَالْأَوْزَاعِيُّ، وَالشَّافِعِيُّ، وَأَصْحَابُ الرَّأْيِ، وَأَبُو ثَوْرٍ وَقَالَ الْحَكَمُ: لَهَا النَّفَقَةُ\n  وَقَالَ ابْنُ الْمُنْذِرِ: لَا أَعْلَمُ أَحَدًا خَالَفَ هَؤُلَاءِ إلَّا الْحَكَمَ... وَلَنَا، أَنَّ النَّفَقَةَ إنَّمَا تَجِبُ فِي مُقَابَلَةِ تَمْكِينِهَا، بِدَلِيلِ أَنَّهَا لَا تَجِبُ قَبْلَ تَسْلِيمِهَا إلَيْهِ...\n  فَأَمَّا إذَا كَانَ لَهُ مِنْهَا وَلَدٌ، فَعَلَيْهِ نَفَقَةُ وَلَدِهِ؛ لِأَنَّهَا وَاجِبَةٌ لَهُ، فَلَا يَسْقُطُ حَقُّهُ بِمَعْصِيَتِهَا».\n  [2] الجامع — مكتبة المسجد النبوي (library_id: 1):\nالمؤلف: أبو بكر محمد بن إبراهيم بن المنذر النيسابوري.\nالكتاب: الأوسط من السنن والإجماع والاختلاف (طبعة دار الفلاح).\nالجزء والصفحة: ج 9، ص 62.\nالرابط: https://aljam3.com/ar/33976/64039/62\nالنص المنقول حرفياً: «ذكر إسقاط نفقة الناشز: أجمع عامة أهل العلم على إسقاط نفقة الناشز المانعة نفسها من الزوج. كذلك قال الشعبي وحماد\n  بن أبي سليمان، ومالك، والثوري، والأوزاعي، والشافعي وأبو ثور. وقال أصحاب الرأي: لا نفقة لها إن كان أعطاها مهرها... وسئل الحكم عن امرأة\n  خرجت من بيت زوجها عاصية هل لها نفقة؟ قال: نعم».\n  *(تنبيه: أود الإفادة بأن أدوات البحث والقراءة لكلا المصدرين: «المكتبة الشاملة» و«الجامع» متوفرة وتعمل بالكامل، وقد تم فتح الصفحات\n  المعنية وقراءتها ونقل النصوص منها حرفياً).'


class RealAnswersTest(unittest.TestCase):
    def test_bold_heading_codex(self):
        refs = c.extract_citations(CODEX_REAL, 'ج')
        self.assertEqual(len(refs), 4)
        self.assertEqual([x['url'] for x in refs], ['https://aljam3.com/ar/35265/67449/295', 'https://aljam3.com/ar/34151/64474/378', '', ''])
        self.assertEqual(refs[0]['quote'], 'معنى النشوز معصتها لزوجها فيما له عليها مما أوجبه له النكاح')
        self.assertEqual(refs[2]['quote'], 'ومن نشزت عنه امرأته بعد دخوله بها سقطت عنه نفقتها إلا أن تكون حاملا')
        self.assertIn('وَلَمْ يُسْقِطْ', refs[3]['quote'])
        self.assertEqual((refs[3]['part'], refs[3]['page']), ('٩', '١١٤'))
        self.assertNotIn('oai-mem-citation', refs[3]['source'])           # الوسم لا يدخل التعريف الأخير

    def test_multiline_definitions_antigravity(self):
        refs = c.extract_citations(ANTIGRAVITY_REAL, 'ج')
        self.assertEqual(len(refs), 2)
        self.assertTrue(refs[0]['quote'].startswith('فَمَتَى امْتَنَعَتْ مِنْ فِرَاشِهِ'))
        self.assertTrue(refs[0]['quote'].rstrip().endswith('فَلَا يَسْقُطُ حَقُّهُ بِمَعْصِيَتِهَا'))
        self.assertEqual(refs[0]['url'], '')
        self.assertEqual((refs[0]['part'], refs[0]['page']), ('8', '236'))
        self.assertIn('بن قدامة', refs[0]['author'])
        self.assertEqual(refs[0]['book'], 'المغني (طبعة مكتبة القاهرة)')
        self.assertTrue(refs[1]['quote'].startswith('ذكر إسقاط نفقة الناشز'))
        self.assertEqual(refs[1]['url'], 'https://aljam3.com/ar/33976/64039/62')
        self.assertEqual((refs[1]['part'], refs[1]['page']), ('9', '62'))
        self.assertNotIn('\n', refs[0]['source'])                         # سطر واحد يصلح للفهرس

    def test_emphasised_headings_variants(self):
        for head in ('**المصادر**', '__المصادر__', '## **المصادر:**', '### المصادر', '**المراجع:**'):
            refs = c.extract_citations('نص [1]\n\n' + head + '\n\n[1] كتاب «نص منقول طويل يكفي للمطابقة الآلية»', 'ج')
            self.assertEqual(len(refs), 1, head)
            self.assertEqual(refs[0]['quote'], 'نص منقول طويل يكفي للمطابقة الآلية')

    def test_definition_stops_at_next_definition_or_blank_line(self):
        refs = c.extract_citations('المصادر\n[1] مؤلف، كتاب\nالجزء والصفحة: ج 2، ص 3\nالنص المنقول: «عبارة منقولة طويلة للمطابقة الآلية هنا»\n[2] آخر، كتاب ثانٍ\n\nفقرة لا علاقة لها «ليست اقتباسًا»', 'ج')
        self.assertEqual(len(refs), 2)
        self.assertEqual((refs[0]['part'], refs[0]['page']), ('2', '3'))
        self.assertEqual(refs[0]['quote'], 'عبارة منقولة طويلة للمطابقة الآلية هنا')
        self.assertNotIn('ليست', refs[1]['source'])
        self.assertEqual(refs[1]['quote'], '')

    def test_partial_ratio_threshold_and_ellipsis(self):
        q = 'نص منقول طويل يكفي للفحص الآلي بالشاملة'
        ref = [{'id': 'ج1', 'quote': q, 'url': ''}]
        mk = lambda ratio, match='partial': (lambda quote: {'found': False, 'where': 'كتاب غريب، ص١', 'in_footnote': False, 'match': match, 'ratio': ratio})
        hi = c.check_citations(ref, verifier=mk(0.64))[0]
        self.assertEqual(hi['status'], '⚠️ فيه خلل')
        self.assertIn('كتاب غريب', hi['reason'])
        for ratio in (0.4, None):
            lo = c.check_citations(ref, verifier=mk(ratio))[0]
            self.assertEqual(lo['status'], '❌ غير موجود')
            self.assertNotIn('كتاب غريب', lo['reason'])               # لا يُطبع موضع لا علاقة له
        # نص مقتطع بـ«...»: يُفحص أطول مقطع
        seen = []
        long = 'مقطع أول قصير لكنه كافٍ للفحص ... مقطع ثانٍ أطول بكثير من الأول ويكفي للفحص الآلي ...'
        res = c.check_citations([{'id': 'ج2', 'quote': long, 'url': ''}], verifier=lambda quote: seen.append(quote) or {'found': True, 'where': 'x', 'in_footnote': False, 'match': 'verbatim', 'ratio': 1.0})[0]
        self.assertEqual(seen, ['مقطع ثانٍ أطول بكثير من الأول ويكفي للفحص الآلي'])
        self.assertIn('أطول مقطع', res['reason'])

    def test_ellipsis_quote_matches_each_segment_in_page(self):
        page = 'بداية الصفحة مقطع أول طويل يكفي للمطابقة الآلية هنا ثم كلام آخر محذوف مقطع ثانٍ طويل يكفي للمطابقة الآلية أيضًا نهاية'
        ref = [{'id': 'ج1', 'quote': 'مقطع أول طويل يكفي للمطابقة الآلية هنا ... مقطع ثانٍ طويل يكفي للمطابقة الآلية أيضًا', 'url': 'https://example.org'}]
        self.assertEqual(c.check_citations(ref, fetcher=lambda u: page)[0]['status'], '✅ موثّق')
        ref[0]['quote'] = 'مقطع أول طويل يكفي للمطابقة الآلية هنا ... مقطع مختلف تمامًا ولا وجود له في الصفحة إطلاقًا'
        self.assertEqual(c.check_citations(ref, fetcher=lambda u: page)[0]['status'], '⚠️ فيه خلل')
