import os
import sys
import unittest
from unittest.mock import MagicMock

from src.modules.antimat.antimat import Antimat, get_default_filter, ObsceneRegexp, extended_filter_enabled

sys.modules['telegram'] = MagicMock()
sys.modules['telegram.ext'] = MagicMock()
sys.modules['src.commands'] = MagicMock()
sys.modules['src.config'] = MagicMock()
sys.modules['src.config.CONFIG'] = MagicMock()
sys.modules['src.modules.khaleesi'] = MagicMock()
sys.modules['src.utils.handlers_helpers'] = MagicMock()
sys.modules['src.utils.cache'] = MagicMock()
sys.modules['src.utils.logger'] = MagicMock()


stop_after_first_fail = True


class StopAfterFailTestCase(unittest.TestCase):
    """
    https://stackoverflow.com/a/690286/136559
    """
    def run(self, result=None):
        if stop_after_first_fail and result.failures or result.errors:
            print('aborted')
        else:
            super(StopAfterFailTestCase, self).run(result)


class ObsceneRegexpTest(StopAfterFailTestCase):
    """
    Тест из https://github.com/asyncee/python-obscene-words-filter
    """

    @classmethod
    def setUpClass(cls):
        cls.pattern_pizd = r'\b[\w]*([пn]+(?:[^\w\s\\/])*[еёe|иi]+(?:[^\w\s\\/])*[зz]+(?:[^\w\s\\/])*[дd]+)[\w]*\b'
        cls.pattern_hlebalo = r'\b([х][л][е][б][а][л][оа])\b'
        cls.pattern_skipidar = r'\b([с][к][и][п][и][д][а][р])\b'

    def test_variants_of_letter(self):
        alpha = {
            'ф': 'фF ts',
            'г': 'гg',
        }
        self.assertEqual('фF|ts', ObsceneRegexp.variants_of_letter(alpha, 'ф'))
        self.assertEqual('гg', ObsceneRegexp.variants_of_letter(alpha, 'г'))

    def test_build_bad_phrase_from_tuple(self):
        cases = {
            ('п', 'еи', 'з', 'д'): self.pattern_pizd,
        }
        for k, v in cases.items():
            self.assertEqual(v, ObsceneRegexp.build_bad_phrase(*k))

    def test_build_bad_phrase_from_string(self):
        cases = {
            'п еи з д': self.pattern_pizd,
        }
        for k, v in cases.items():
            self.assertEqual(v, ObsceneRegexp.build_bad_phrase(k))

    def test_build_good_phrase_from_tuple(self):
        cases = {
            ('х', 'л', 'е', 'б', 'а', 'л', 'оа'): self.pattern_hlebalo,
            ('с', 'к', 'и', 'п', 'и', 'д', 'а', 'р'): self.pattern_skipidar,
        }
        for k, v in cases.items():
            self.assertEqual(v, ObsceneRegexp.build_good_phrase(*k))

    def test_build_good_phrase_from_string(self):
        cases = {
            'х л е б а л оа': self.pattern_hlebalo,
            'с к и п и д а р': self.pattern_skipidar,
        }
        for k, v in cases.items():
            self.assertEqual(v, ObsceneRegexp.build_good_phrase(k))


class ObsceneWordsFilterTest(StopAfterFailTestCase):
    """
    Тест из https://github.com/asyncee/python-obscene-words-filter
    """

    @classmethod
    def setUpClass(cls):
        cls.words_filter = get_default_filter()

    def test_is_word_good(self):
        cases = [
            'хлебало', 'хлебала', 'скипидар',
            'колебания', 'колебание', 'колебаний',
            'заколебал', 'заколебать', 'закалебал', 'зоколебать',
            'рубля', 'стебель', 'страховка', 'страховку', 'страховки',
            'оскорблять', 'оскорбляешь', 'оскорблял',
            'влюблять', 'влюбляешься',
            'подстрахуй', 'застрахуй', 'подстрахует', 'застрахует', 'застрахуешься',
            'мебельный',
            'употреблять', 'употребляешь', 'употреблял',
            'истреблять', 'истребляешь', 'истреблял',
            'страх', 'страха',
        ]
        for word in cases:
            self.assertTrue(self.words_filter.is_word_good(word), word)

    def test_is_word_bad(self):
        good = {
            'хлебало', 'хлебала', 'скипидар',
        }
        extended = {'пидор', 'пидар', 'пидер', 'пидр', 'говно', 'гавно', 'мудак', 'мудачьё', 'гондон',
                    'чмо', 'дерьмо', 'шлюха', 'залупа', 'золупа', 'манда', 'монда', 'сучара'}
        bad = [
            'пизда', 'пиздец', 'пизды', 'пезда',
            'хуй', 'хуйло', 'хуюшки',
            'охуевший', 'охуел', 'охуеть',
            'пидор', 'пидар', 'пидер', 'пидр',
            'ебаный', 'ебака', 'ебало', 'ёбаный', 'ебать',
            'уебан', 'уёбок', 'уебот',
            'ебло', 'ёбла', 'ёбли', 'ебли',
            'выеб', 'выёб', 'выебли', 'выебали',
            'бля', 'говно', 'гавно', 'мудак', 'мудачьё',
            'гондон', 'чмо', 'дерьмо', 'шлюха', 'залупа', 'золупа',
            'манда', 'монда', 'сучара', 'далбаёб', 'долбоёб', 'далбаёбы',
        ]
        if not extended_filter_enabled:
            bad = list(set(bad) - extended)
            good.update(extended)
            for word in extended:
                self.assertEqual(0, Antimat.bad_words_count(word), word)
        for word in bad:
            self.assertTrue(self.words_filter.is_word_bad(word), word)
        for word in good:
            self.assertFalse(self.words_filter.is_word_bad(word), word)

    def test_is_word_bad_case_insensitive(self):
        bad = ['пизда', 'ПИЗДА']
        for word in bad:
            self.assertTrue(self.words_filter.is_word_bad(word), word)

    def test_is_word_good_case_insensitive(self):
        cases = {
            'скипидар': True,
            'СКИПИДАР': True,
        }
        for k, v in cases.items():
            self.assertEqual(v, self.words_filter.is_word_good(k))

    def test_find_bad_word_matches(self):
        cases = {
            ' пиздец пизда опиздеть вот это да': ['пиздец', 'пизда', 'опиздеть'],
            'хуйло хуй хуёвый хуясе пирожок': ['хуйло', 'хуй', 'хуёвый', 'хуясе'],

            'собака ебаный и ёбаный ебало ебака ебатуй': ['ебаный', 'ёбаный', 'ебало', 'ебака', 'ебатуй'],
            'уебался уебать уебак уебок уёбок': ['уебался', 'уебать', 'уебак', 'уебок', 'уёбок'],
            'охуевший охуеть охуел ОХУЕТЬ Охуел охуеваю': ['охуевший', 'охуеть', 'охуел', 'ОХУЕТЬ', 'Охуел', 'охуеваю'],
        }
        if extended_filter_enabled:
            cases.update({
                'трамвай пидар пидараз пидор пидер пидераст локомотив': ['пидар', 'пидараз', 'пидор', 'пидер', 'пидераст'],
            })

        for k, v in cases.items():
            self.assertSequenceEqual(
                set(v),
                set([m.group() for m in self.words_filter.find_bad_word_matches(k)]))

    def test_find_bad_word_matches_without_good_words(self):
        cases = {
            'ебало хлебало': ['ебало'],
        }
        if extended_filter_enabled:
            cases.update({'пидар скипидар пидор': ['пидар', 'пидор']})
        for k, v in cases.items():
            self.assertSequenceEqual(
                set(v),
                set([m.group() for m in self.words_filter.find_bad_word_matches_without_good_words(k)]))

    @unittest.skip
    def test_mask_text_range(self):
        self.assertEqual('012**56789', self.words_filter.mask_text_range('0123456789', 3, 5))
        self.assertEqual('-----06789', self.words_filter.mask_text_range('0123456789', 1, 6, symbol='-'))

    @unittest.skip
    def test_mask_bad_words(self):
        cases = {
            'Охуеть, товарищи! Это пиздец! Хуй! Вчера ехал на газели — уебался в камаз! Хуй.': (
                '******, товарищи! Это ******! ***! Вчера ехал на газели — ******* в камаз! ***.'
            ),
            'Да охуеть блять, вы что, суки, заебали, охуели совсем в конец уже!': (
                'Да ****** *****, вы что, суки, *******, ****** совсем в конец уже!'
            ),
            u'Долбоёбам и любой тупой пизде вход закрыт, нахуй и не ебёт.': (
                u'********* и любой тупой ***** вход закрыт, ***** и не ****.'
            ),
        }

        for k, v in cases.items():
            self.assertEqual(v, self.words_filter.mask_bad_words(k))


class PhpCensureTest(StopAfterFailTestCase):
    """
    Кое-что из https://github.com/rin-nas/php-censure
    """

    def test_pretext(self):
        words = ['уебать', 'охуеть', 'ахуеть', 'вспизднуть', 'коноебиться', 'мудаёб',
                 'остопиздело', 'худоебина', 'впиздячить', 'схуярить', 'съебаться', 'въебать', 'ёбля']
        for word in words:
            self.assertEqual(1, Antimat.bad_words_count(word), word)

    def test_bad_words_x(self):
        words = ['хуй', 'хуя', 'хую', 'хуем', 'хуёвый', 'охуительный']
        for word in words:
            self.assertEqual(1, Antimat.bad_words_count(word), word)

    def test_bad_words_p(self):
        words = {'пизда', 'пезда', 'пезды', 'пизде', 'пиздёж', 'пизду', 'пиздюлина', 'пиздобол',
                 'опиздинеть', 'пиздых', 'подпёздывать'}
        extended = {'пидор', 'педор', 'пидар'}
        if extended_filter_enabled:
            words.update(extended)
        else:
            for word in extended:
                self.assertEqual(0, Antimat.bad_words_count(word), word)
        for word in words:
            self.assertEqual(1, Antimat.bad_words_count(word), word)

    def test_bad_words_e(self):
        words = ['ебу', 'еби', 'ебут', 'ебать', 'ебись', 'ебёт', 'поеботина', 'выебываться', 'ёбарь', 'ебло',
                 'ебла', 'ебливая', 'еблись', 'еблысь', 'ёбля', 'ёбнул', 'ёбнутый', 'взъёбка', 'ебсти',
                 'долбоёб', 'дураёб', 'изъёб', 'заёб', 'заебай', 'разъебай', 'мудоёбы', 'ёб']
        for word in words:
            self.assertEqual(1, Antimat.bad_words_count(word), word)

    def test_bad_words_b(self):
        words = ['бля', 'блять', 'бляди']
        for word in words:
            self.assertEqual(1, Antimat.bad_words_count(word), word)

    def test_bad_words_m(self):
        words = set()
        extended = {'мудак', 'мудачок'}
        if extended_filter_enabled:
            words.update(extended)
        else:
            for word in extended:
                self.assertEqual(0, Antimat.bad_words_count(word), word)
        for word in words:
            self.assertEqual(1, Antimat.bad_words_count(word), word)

    def test_manda(self):
        bad = 'манда'.split(' ')
        good = 'город Мандалай, округ Мандаль, индейский народ Мандан, фамилия Мандель, мандарин, мандаринка'.split(', ')
        is_good = 0 if extended_filter_enabled else 0
        is_bad = 1 if extended_filter_enabled else 0
        for word in good:
            self.assertEqual(is_good, Antimat.bad_words_count(word), word)
        for word in bad:
            self.assertEqual(is_bad, Antimat.bad_words_count(word), word)


class FilesTest(StopAfterFailTestCase):
    messages_collection = r'..\tmp\antimat\messages_collection.txt'
    # словари русских слов
    # https://github.com/danakt/russian-words
    # http://speakrus.ru/dict/index.htm
    # http://blog.harrix.org/article/3334
    words = r'..\tmp\antimat\words\words.txt'

    @unittest.skipUnless(os.path.exists(messages_collection), 'file not found')
    @unittest.skip
    def test_split_words(self):
        import re
        words = set()
        with open(self.messages_collection, 'r', encoding='utf-8') as f:
            for line in f:
                words.update(word for word in re.split(r'[,.\s;:()!@#$%^&*"\'№?<>/|\\=+~`«»„“”—]+', line.lower()))
        with open(r'..\tmp\messages_collection_words.txt', 'w', encoding='utf-8') as f:
            f.writelines(f'{word}\n' for word in sorted(words))

    @unittest.skipUnless(os.path.exists(messages_collection), 'file not found')
    @unittest.skip
    def test_messages_collection(self):
        bad_words = set()
        with open(self.messages_collection, 'r', encoding='utf-8') as f:
            for line in f:
                bad_words.update(word.lower() for word in Antimat.bad_words(line))
        with open(r'..\tmp\antimat\messages_collection_bad.txt', 'w', encoding='utf-8') as f:
            f.writelines(f'{word}\n' for word in sorted(bad_words))

    @unittest.skipUnless(os.path.exists(words), 'file not found')
    @unittest.skip
    def test_words(self):
        bad_words = set()
        with open(self.words, 'r', encoding='utf-8') as f:
            for line in f:
                # self.assertEqual(0, Antimat.bad_words_count(line), line)
                bad_words.update(word.lower() for word in Antimat.bad_words(line))
        with open(r'..\tmp\antimat\words\words_bad.txt', 'w', encoding='utf-8') as f:
            f.writelines(f'{word}\n' for word in sorted(bad_words))

    # noinspection PyNestedDecorators
    @unittest.skip
    @staticmethod
    def test_wp():
        bad_words = set()
        with open(r'..\tmp\antimat\text_for_mat.txt', 'r', encoding='utf-8') as f:
            for line in f:
                bad_words.update(word.lower() for word in Antimat.bad_words(line))
        with open(r'..\tmp\antimat\text_for_mat_bad.txt', 'w', encoding='utf-8') as f:
            f.writelines(f'{word}\n' for word in sorted(bad_words))


class AntimatTest(StopAfterFailTestCase):
    def test_empty(self):
        self.assertEqual(0, Antimat.bad_words_count(''))

    def test_count(self):
        self.assertEqual(4, Antimat.bad_words_count('Да охуеть блять, вы заебали, охуели совсем в конец уже!'))

    def test_names(self):
        words = 'Орзэмэс, Варзамес, Уэзырмэс, Орзик, Арзамас, Органайзер, Оренбург, Орнамент, Аризона, Озарк, Арьегард, Осирис, Озимандий, Orgazmotron, Аркамбаз, Арканзас, Орзумандий, Юрий, Анубис, Озарий, Орангзеб, Орзабэль, Орметес, Оразгуль, Орзометр, Орион, Оракул, Орегон, Оркестр, Орнитолог, Ортопед, Оренбург, Орнитопод, Орнамент, Ортаногенез, Ортодокс, Обскур, Орбакайте, Оргазмолог, Ордабасы, Оргазмайзер, Орсимер, покупаешь печенье ОРЕО, Оториноларинголог, Омагат, Орзан Кадыров, Артмани, Виктор Цой, заказываешь суши, носишь бороду, вуапще красаучик 😘, играешь джаз, даришь девушкам цветы, НЕ постишь селфи, Борщ С Водочкой, так грациозна и мила. обворожительна. прекрасна. ты так желанна и опасна. тебе ведь нет еще 16 лет, Орифлеймс, покупаешь автомат, говоришь всем комплименты, пьешь прямо с утра, Озидяима, Мерзомес, Орзамент, Орзамемс, Бодифлекс, Оксисайз, Озарк, Гномерзас, Ойзэмэс, Ореземес, Адинослав, Адислав, Адыслав, Анастаслав, Анислав, Бедислав, Белослав, Бенислав, Береслав, Берислав, Бечислав, Благослав, Богослав, Богуслав, Бодеслав, Боеслав, Божеслав, Болеслав, Борислав, Бохаслав, Бранислав, Братислав, Брацислав, Бронеслав, Бронислав, Брячислав, Будислав, Буеслав, Буслав, Быслав, Вадислав, Вакслав, Вартислав, Васлав, Ваславий, Ватрослав, Вацлав, Векослав, Велеслав, Венеслав, Венкеслав, Венислав, Венцеслав, Верислав, Верослав, Верхослав, Веслав, Вестислав, Видислав, Видослав, Виленслав, Вилислав, Вирослав, Вислав, Витаслав, Витчеслав, Витязослав, Вишеслав, Владжислав, Владислав, Властислав, Внислав, Воислав,Волеслав, Воротислав, Вратислав, Вростислав, Всеслав, Вукослав, Вчеслав, Вышеслав, Вятчеслав, Годислав, Годослав, Гореслав, Горислав, Гостислав, Градислав, Гранислав, Гремислав, Губислав, Гудислав, Далеслав, Данислав, Данслав, Даньслав, Дарослав, Дедослав, Дезислав, Денислав, Десислав, Доброслав, Домослав, Домислав, Дорислав, Драгослав, Егослав, Егославий, Ездислав, Ерослав, Есислав, Зареслав, Зарислав, Заслав, Збыслав, Звенислав, Звонислав, Здеслав, Здислав, Златислав, Златослав, Зореслав, Изяслав, Истислав, Калислав, Кареслав, Карислав, Крайслав, Краснослав, Критислав, Ладислав, Ленислав, Ленслав, Летослав, Литослав, Лихослав, Лудислав, Леслав, Лехослав, Любослав, Майеслав, Мечеслав, Милослав, Мирослав, Мстислав, Мсцислав, Негослав, Огнеслав, Одеслав, Одислав, Переслав, Переяслав, Православ, Преслав, Путислав, Пшемыслав, Радаслав, Радислав, Радослав, Ратислав, Растислав, Раслав, Рослав, Ростислав, Росцислав, Росцислау, Рудослав, Руславий, Сбыслав, Светислав, Светослав, Свойслав, Святослав, Сдеслав, Слава, Славик, Славозар, Славозавр, Славомир, Собеслав, Собислав, Сталинослав, Станислав, Станислас, Старислав, Стрезислав, Судислав, Сулислав, Таислав, Твердислав, Твердослав, Творислав, Терпислав, Техослав, Тихослав, Толислав, Томилослав, Томислав, Требислав, Трудослав, Услав, Хвалислав, Хлебослав, Ходислав, Хотислав, Хранислав, Христослав, Цветислав, Цветослав, Цдислав, Цеславий, Цтислав, Чаеслав, Часлав, Чеслав, Честислав, Числав, Чистослав, Чтислав, Чурослав, Эрислав, Югославий, Юраслав, Юреслав, Юрислав, Юрослав, Янислав, Ярослав, Ячислав, Оргазмослав, Какятебеслав, Воландемортослав'.split(', ')
        for word in words:
            self.assertEqual(0, Antimat.bad_words_count(word), word)

    def test_oxxxymiron(self):
        words = set('говно залупа пенис хер давалка хуй блядина головка шлюха жопа член еблан петух мудила рукоблуд ссанина очко блядун вагина сука ебланище влагалище пердун дрочила пидор пизда туз малафья гомик мудила пилотка манда анус вагина путана педрила шалава хуила мошонка елда'.split(' '))
        bad = set('хуй блядина еблан блядун ебланище пизда хуила елда'.split(' '))
        extended = 'мудила пидор мудила манда педрила говно залупа шлюха мудила дрочила шалава'.split(' ')
        if extended_filter_enabled:
            # TODO: добавить в плохие: хер сука жопа
            bad.update(extended)
        else:
            for word in extended:
                self.assertEqual(0, Antimat.bad_words_count(word), word)
        good = words - bad
        for word in good:
            self.assertEqual(0, Antimat.bad_words_count(word), f'{word} (false positive)')
        for word in bad:
            self.assertEqual(1, Antimat.bad_words_count(word), f'{word} (should be bad)')

    def test_words(self):
        words = {
            'xyясe', 'хуясе', 'Xyй', 'Ёбтеть', 'что за хуйня', 'приебнутый', 'бл*ядь', 'ахуенна',
            'ееееееелда', 'проеб', 'ретроеб', 'пешееб', 'точкоёб', 'удкоеб', 'ахуел',
            'хуисосить', 'хуистика', 'хуисываться', 'хуизнь', 'хуизм', 'охуительный',
            'ееебааать', 'хуюсно', 'пиздосия', 'пиздюк', 'хуюх', 'блякукарек', 'хуютра', 'пиздец', 'ебать',
            'хуютречка', 'долбоёбов', 'выблядок', 'пиздосище', 'пиздострадает', 'хуютине',
            'дохуя', 'нахуй', 'хуютки', 'ебанулся', 'нихуя', 'блядь', 'бляд', 'бля', 'блячяяя',
            'пиздосно', 'хуюси', 'хуирка', 'похуить', 'хуйню', 'ебейший', 'ахуенна', 'хуюсь',
            'хуюф', 'заебись', 'хуюсство', 'блядорумынский', 'пиздосищеее', 'еблан', 'хуила',
            'хуюче', 'пизда', 'хуемордый', 'пиздос', 'пиздосики', 'хуютро', 'хуютром', 'хуюсечка',
            'хуюхер', 'хуюсев', 'блядина', 'пиздоссссс',
            'пиздострадалище', 'нахуя', 'нахуйь', 'спиздило', 'похуй', 'очкохуялище', 'пиздюкам',
            'охуенные', 'блядун', 'пиздородов', 'хуюта', 'хуюточки', 'пиздосиики', 'блять', 'хуя',
            'хуютречко', 'хуют', 'долбоебами', 'блядиность', 'ебланище', 'хуюсский', 'хуй',
        }
        extended = {'збс', 'хз', 'додрочил', 'дрочил', 'дрочка', 'дрочильня', 'задрочился', 'надрочил', 'подрочил',
                    'говнобложик', 'гребаный', 'говноблогира', 'говноводителей', 'мудак', 'говновиндоус', 'говнобанк',
                    'чмо', 'говноаеалитик', 'шлюху', 'говно', 'говнобаянам', 'манда', 'пидор', 'говноаватарка',
                    'говноаймакса', 'мудака', 'дерьмо', 'гондон', 'залупа', 'шлюха', 'гребаные', 'грёбанные'}
        if extended_filter_enabled:
            words.update(extended)
        else:
            for word in extended:
                self.assertEqual(0, Antimat.bad_words_count(word), f'{word} (false positive)')
        for word in words:
            self.assertEqual(1, Antimat.bad_words_count(word), word)

    def test_false_positive(self):
        words = [
            'себя', 'себе', 'не будет', 'sasha_rebinder', 'rebinder', 'ниже были', 'ребиндер',
            'ребята', 'ребзя', 'мебель', 'меблирование', 'ребятишки', 'чебурашка', 'команду',
            'команда', 'команды', 'веб', 'web', 'вэбдизайн', 'веб-страница', 'небось', 'тебя',
            '42рубля', 'ebay', 'ebook', 'eboot', 'snegopad', 'чебурнет', 'чебуратор', 'снегопад',
            'азимандий', 'аманда', 'аманды', 'безмандариновый', 'бесхребетный', 'бельмондо',
            'бомонд', 'бухую', 'взахлеб', 'взахлёб', 'военнокомандующими', 'волшебную', 'волшебная',
            'волшебник', 'волшебство', 'втихую', 'хуис', 'хуиз', 'выгребную', 'главнокомандующему',
            'главнокомандующий', 'даблкомандер', 'даблкоммандер', 'тоталкомандер', 'командер', 'командир',
            'дебатам', 'дебатах', 'дебатировала', 'дебатов', 'дебаты', 'дебетка', 'дебетовая', 'ебилдов',
            'ебилд', 'ещеб', 'ещёб', 'загреб', 'загребе', 'злоупотреблять', 'злоупотребление',
            'коммандер', 'коммандировки', 'коммандника', 'коммандос', 'комманды', 'корабля', 'красноухую',
            'красноухие', 'лечебную', 'лечебная', 'мандат', 'мандраж', 'наскребсти', 'наскребёт', 'насухую',
            'небоскреб', 'нормандии', 'обособляла', 'озимандий', 'ослабляет', 'перебанить', 'погреб',
            'плохую', 'подстебать', 'подстеб', 'подстебнула', 'покомандовать', 'пооскорблять', 'оскорблять',
            'поскрёб', 'послабляющее', 'постебать', 'потребляет', 'потребляете', 'потребляешь', 'потребляла',
            'потребляют', 'потребует', 'потребуется', 'потребление', 'потребство', 'пригублять',
            'протоархимандритом', 'психует', 'психую', 'психующий', 'разгребать', 'разгребала',
            'расслабляемся', 'расслабляет', 'расслабляющие', 'ребут', 'ребутнуть', 'ребус', 'роспотреб',
            'рублям', 'рублях', 'саблями', 'сабля', 'саламандр', 'саламандра', 'свадеб', 'свадебную',
            'сгрёб', 'скребет', 'скребутся', 'спидорак', 'спидораковое', 'спидранил', 'спидраннеры',
            'стеб', 'стебал', 'стебалась', 'стебали', 'стебались', 'стебался', 'стебанулся', 'стебать',
            'стебетесь', 'стебется', 'стебут', 'стёб', 'судебную', 'судебная', 'талеб', 'тебе-то', 'себя-то',
            'требует', 'требуется', 'трудовыебудни', 'углубляться', 'уподобляешься', 'уподобляться',
            'употребляешь', 'употреблять', 'усугубляет', 'усугубляй', 'неусугубляй', 'уху', 'учебу',
            'учебу/туризм', 'хаммонд', 'хлеб', 'хлебали', 'хлебнуть', 'хребет', 'чармондер', 'ширпотреб',
            'бляха', 'бляхамуха', 'бляха-муха', 'ебук', 'дебет', 'веллдан', 'небаталов', 'небосклон',
            'педро', 'дубляж', 'дубляжам', 'хуизит', 'хуисит', 'щебет', 'щебетали', 'погребальная',
            'чмокнул', 'чмокал', 'тихую', 'истребится', 'лихую', 'оглоблях', 'раздробляются', 'погребения',
            'гребсти', 'икебана', 'слышала/видела', 'граблями', 'загребали', 'гребет', 'гребная', 'бляшек',
            'осклябляясь', 'BASOULHQUNXYYNXCWREHVFHRO2A', 'хуу', 'XYYN',
        ]
        for word in words:
            self.assertEqual(0, Antimat.bad_words_count(word), word)

    # def test_word1(self):
    #     # self.assertEqual(0, Antimat.bad_words_count('DEUTCHESHEISEGNEZDOLIEREN'))
    #     self.assertEqual(0, Antimat.bad_words_count('NEZDO'))
