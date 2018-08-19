# coding=UTF-8

import re
from functools import partial
from typing import Iterable


extended_filter_enabled = False  # если True, то проверяем не только мат, но и оскорбления, ругательства, etc


class ObsceneRegexp:
    """
    Основа из https://github.com/asyncee/python-obscene-words-filter
    """

    alphabet_ru = {
        'а': 'аa',
        'б': 'б6b',
        'в': 'вvb',
        'г': 'гr',
        'д': 'дd',
        'е': 'еёe',
        'ё': 'ёеe',
        'ж': 'ж',
        'з': 'зz',
        'и': 'иi',
        'й': 'й',
        'к': 'кk',
        'л': 'лl',
        'м': 'мm',
        'н': 'нh',
        'о': 'оo',
        'п': 'пn',
        'р': 'рp',
        'с': 'сc',
        'т': 'тt',
        'у': 'уy',
        'ф': 'фf',
        'х': 'хx',
        'ц': 'цc',
        'ч': 'ч',
        'ъ': 'ъ',
        'ы': 'ы',
        'ь': 'ь',
        'э': 'э',
        'ю': 'ю',
        'я': 'я',
    }
    ru_variants_of_letter: partial = None

    @classmethod
    def variants_of_letter(cls, alphabet, letter):
        letters = alphabet.get(letter, letter)
        return '|'.join(letters.split())

    @classmethod
    def build_bad_phrase(cls, *symbols, **kwargs):
        """
        Построить регулярную фразу из символов.

        Между символами могут располагаться пробелы или любые не−кириллические символы.
        Фраза возвращается в виде группы.
        """
        variants_func = kwargs.get('variants_func', cls.ru_variants_of_letter)
        separator = '(?:[^\w\s\\\\/])*'  # non-capturing group

        if len(symbols) == 1:
            symbols = symbols[0].split()

        symbol_regexp = []
        for symbol in symbols:
            if len(symbol) == 1:
                symbol = [symbol]
            parts = [variants_func(i) for i in symbol]
            symbol_regexp.append('[{}]+'.format('|'.join(parts)))
        return r'\b[\w]*({})[\w]*\b'.format(separator.join(symbol_regexp))

    @classmethod
    def regex_with_latin(cls, pattern: str):
        new_pattern = []
        for symbol in pattern:
            if symbol not in cls.alphabet_ru:
                new_pattern.append(symbol)
                continue
            parts = cls.alphabet_ru[symbol]
            if len(parts) == 1:
                new_pattern.append(f'{parts}+')
                continue
            new_pattern.append('(?:{})+'.format('|'.join(parts)))
        result = (''.join(new_pattern)).replace('+*', '*').replace('+?', '*')
        return result

    @classmethod
    def build_good_phrase(cls, *symbols):
        if len(symbols) == 1:
            symbols = symbols[0].split()

        out = []
        for symbol in symbols:
            out.append('[{}]'.format(symbol))
        return r'\b({})\b'.format(''.join(out))


ObsceneRegexp.ru_variants_of_letter = partial(ObsceneRegexp.variants_of_letter, ObsceneRegexp.alphabet_ru)


class ObsceneWordsFilter(object):
    """
    Основа из https://github.com/asyncee/python-obscene-words-filter
    """

    def __init__(self, bad_regexp, good_regexp):
        self.bad_regexp = bad_regexp
        self.good_regexp = good_regexp

    def find_bad_word_matches(self, text):
        return self.bad_regexp.finditer(text)

    def find_bad_word_matches_without_good_words(self, text):
        for match in self.find_bad_word_matches(text):
            if not self.is_word_good(match.group()):
                yield match

    def is_word_good(self, word):
        return bool(self.good_regexp.match(word))

    def is_word_bad(self, word):
        if self.is_word_good(word):
            return False

        return bool(self.bad_regexp.match(word))

    def mask_bad_words(self, text):
        for match in self.find_bad_word_matches_without_good_words(text):
            start, end = match.span()
            text = self.mask_text_range(text, start, end)
        return text

    @staticmethod
    def mask_text_range(text, start, stop, symbol='*'):
        return text[:start] + (symbol * (stop - start)) + text[stop:]


class ObsceneConf:
    bad_words = [
        ObsceneRegexp.build_bad_phrase('п еиё з д'),
        ObsceneRegexp.build_bad_phrase('п еиё з д её ж'),
        ObsceneRegexp.build_bad_phrase('х у йёеяию'),
        ObsceneRegexp.build_bad_phrase('х у йёеяию м'),
        ObsceneRegexp.build_bad_phrase('ао х у е втл'),
        ObsceneRegexp.build_bad_phrase('у её б оа нтк'),
        ObsceneRegexp.build_bad_phrase('в ы её б'),
        ObsceneRegexp.build_bad_phrase('в з ъь её б'),
        # ObsceneRegexp.build_bad_phrase('её б л аои'),
        # ObsceneRegexp.build_bad_phrase('её б оаыия'),
        ObsceneRegexp.build_bad_phrase('её б а нклт'),
        ObsceneRegexp.build_bad_phrase('е б л а н'),
        # ObsceneRegexp.build_bad_phrase('е б ё т'),
        # ObsceneRegexp.build_bad_phrase('е б и'),
        # ObsceneRegexp.build_bad_phrase('е б л иоы'),
        ObsceneRegexp.build_bad_phrase('е б с т и'),
        # ObsceneRegexp.build_bad_phrase('е б у'),
        ObsceneRegexp.build_bad_phrase('е б уеё т'),
        # ObsceneRegexp.build_bad_phrase('её б т'),
        # ObsceneRegexp.build_bad_phrase('е л д ауео'),
        ObsceneRegexp.build_bad_phrase('её б н у лт'),
        ObsceneRegexp.build_bad_phrase('её б а р ь'),
        ObsceneRegexp.build_bad_phrase('её б л я'),
        ObsceneRegexp.build_bad_phrase('з аъь её б'),
        ObsceneRegexp.build_bad_phrase('п ао её б о т'),
        ObsceneRegexp.build_bad_phrase('св ъь еёи б'),
        ObsceneRegexp.build_bad_phrase('б л я'),

        ObsceneRegexp.build_bad_phrase('д ао л б ао её б'),
        ObsceneRegexp.regex_with_latin(r'\b(?:худ[оа]|муд[оа]|кон[ое]|дура)еб[ы]?\b'),

        ObsceneRegexp.regex_with_latin(r'\bеб[уиа]?\b'),
        ObsceneRegexp.regex_with_latin(r'\bпроеб\w*\b'),
        ObsceneRegexp.regex_with_latin(r'\b\w\w+оеб\b'),
        ObsceneRegexp.regex_with_latin(r'\b\w\w+шееб\b'),
        ObsceneRegexp.regex_with_latin(r'\b(?:не)?у*еб\w+'),
        ObsceneRegexp.regex_with_latin(r'\w+ебить*ся\b'),
        ObsceneRegexp.regex_with_latin(r'\w+ебина\b'),
        ObsceneRegexp.regex_with_latin(r'\bелд[ауео]\b'),
        ObsceneRegexp.regex_with_latin(r'\bебтет\w+'),
        ObsceneRegexp.regex_with_latin(r'\bебл[аоеи]\w*'),
    ]
    if extended_filter_enabled:
        bad_words.extend([
            ObsceneRegexp.build_bad_phrase('п иеё д оеа р'),
            ObsceneRegexp.build_bad_phrase('п ие д р'),
            ObsceneRegexp.build_bad_phrase('г оа в н'),
            ObsceneRegexp.build_bad_phrase('м у д а кч'),
            ObsceneRegexp.build_bad_phrase('г ао н д о н'),
            # ObsceneRegexp.build_bad_phrase('ч м оы'),
            ObsceneRegexp.build_bad_phrase('д е р ь м'),
            ObsceneRegexp.build_bad_phrase('ш л ю х'),
            ObsceneRegexp.build_bad_phrase('з ао л у п'),
            ObsceneRegexp.build_bad_phrase('с у ч а р'),
            ObsceneRegexp.build_bad_phrase('м у д и л'),
            ObsceneRegexp.build_bad_phrase('д р оа ч и л'),
            ObsceneRegexp.build_bad_phrase('д р о ч к'),
            ObsceneRegexp.build_bad_phrase('ш а л а в'),
            ObsceneRegexp.regex_with_latin(r'\bчм[оы]\w*'),
            ObsceneRegexp.regex_with_latin(r'\bм[ао]нд[ауеои][^тр\W]'),
            ObsceneRegexp.regex_with_latin(r'\bм[ао]нд[ау]\b'),
            ObsceneRegexp.regex_with_latin(r'\bзбс\b'),
            ObsceneRegexp.regex_with_latin(r'\bхз\b'),
        ])
    bad_words_re = re.compile('|'.join(bad_words), re.IGNORECASE | re.UNICODE)

    good_words = [
        ObsceneRegexp.build_good_phrase('х л е б а л оа'),
        ObsceneRegexp.build_good_phrase('с к и п и д а р'),
        ObsceneRegexp.build_good_phrase('к о л е б а н и яей'),
        ObsceneRegexp.build_good_phrase('з ао к оа л е б а лт'),
        ObsceneRegexp.build_good_phrase('р у б л я'),
        ObsceneRegexp.build_good_phrase('с т е б е л ь'),
        ObsceneRegexp.build_good_phrase('с т р а х о в к ауи'),
        ObsceneRegexp.build_good_phrase('с е б яе'),
        ObsceneRegexp.build_good_phrase('e b a y'),
        ObsceneRegexp.build_good_phrase('e b o o kt'),
        ObsceneRegexp.build_good_phrase('в т и х у ю'),
        # regex_with_latin здесь везде будет лишним. где нужна ё - указать вручную
        r'([о][с][к][о][Р][б][л][я]([т][ь])*([л])*([её][ш][ь])*)',
        r'([в][л][ю][б][л][я](([т][ь])([с][я])*)*(([её][ш][ь])([с][я])*)*)',
        r'((([п][о][д])*([з][а])*([п][её][р][её])*)*[с][т][р][а][х][у]([й])*([с][я])*([её][ш][ь])*([ёе][т])*)',
        r'([м][её][б][её][л][ь]([н][ы][й])*)',
        r'(\w*кол[её]б)',
        r'([Уу][Пп][Оо][Тт][Рр][Ееё][Бб][Лл][Яя]([Тт][Ьь])*([Ееё][Шш][Ьь])*([Яя])*([Лл])*)',
        r'([Ии][Сс][Тт][Рр][Ееё][Бб][Лл][Яя]([Тт][Ьь])*([Ееё][Шш][Ьь])*([Яя])*([Лл])*)',
        r'([Сс][Тт][Рр][Аа][Хх]([Аа])*)',
        r'(\bмандарин\w*)',
        r'(\bмандел\w*)',
        r'(\bманда[лн]\w*)',
        r'(\w*мандий\w*)',
        r'(\w*(?:rebind|р[еёe]бинд)\w*)',
        r'(\bкоманд\w*)',
        r'(\b\w*рубл\w*)',
        r'(\b[еёe]билд\w*)',
        r'(\bв[еэ]б)',
        r'(\w*хребет\w*)',
        r'(\bбухую\w*)',
        r'(\bхуи[зс][уыа]?\b)',
        r'(\bхуи[зс]ит\b)',
        r'(\w*деб[еа]т\w*)',
        r'(\w*потр[еи]бл[яе])',
        r'(\w*тр[еи]бу[яе])',
        r'(\w*губл[яе])',
        r'(корабля)',
        r'(\w*ухую\b)',
        r'(\bмандат\w*)',
        r'(\w*скр[ёе]б\w*)',
        r'(\w*собля\w*)',
        r'(\w*слабля\w*)',
        r'(\w*перебан\w*)',
        r'(\w*плохую\w*)',
        r'(\w*ст[её]б\w*)',
        r'(\w*ск[ао]рбля\w*)',
        r'(\w*психу[еиюя]\w*)',
        r'(\w*разгреб\w*)',
        r'(\w*ребут\w*)',
        r'(\w*сабля\w*)',
        r'(\w*спидорак\w*)',
        r'(\w*спидран\w*)',
        r'(\w*[ст]ебе-т\w*)',
        r'(\w*трудовыеб\w*)',
        r'(\w*углубл[яе]\w*)',
        r'(\w*подобля\w*)',
        r'(\w*учеб[уаые]\w*)',
        r'(\w*хлеб\w*)',
        r'(\w*блях[ауие]\w*)',
        r'(\w*[еёe]бук\w*)',
        r'(\bнеб\w+)',
        r'(\bпедр[оуеа]\b)',
        r'(\bдубля\w*)',
        r'(\bчмок\w*)',
        r'(\w*ихую\b)',
        r'(\w*треб\w+)',
        r'(\w*оглобля\w*)',
        r'(\w*раздробля\w*)',
        r'(\w*щебет\w*)',
        r'(\w*гребал\w*)',
        r'(\bгребст\w+)',
        r'(\bикебан\w+)',
        r'(\bграбл\w+)',
        r'(\w+блями\w*)',
        r'(\bзагребал\w*)',
        r'(\w*греб[еёа]т\w*)',
        r'(\w*греб[еа]ние\b)',
        r'(\bк[ао]рд[еэо]балет\w*)',
        r'(\bперебал\w+)',
        r'(\bблямб\w*)',
        r'(\bблях(?:о[йю]|у)?)',
        r'(\bбляш(?:[эеиы]ч?ь?)?к\w*)',
        r'(\bабля(?:тив|ут|ц[ыи])\w*)',
        r'(\w*щербля\w*)',
        r'(\w*ебетон\w*)',
        r'(\w*озлобля\w*)',
        r'(\w*обляп\w*)',
        r'(\bгреб(?:л|нуть)\w*)',
        r'(\w*глубля\w*)',
        r'(\w*жереби\w*)',
        r'(\bзар[иы]бля\w*)',
        r'(\bпереби\w*)',
        r'(\bчебак\w*)',
        r'(\w*любля\w*)',
        r'(\w*скобля\w*)',
        r'(\w*штрих\w*)',
        r'(\w*теребит\w*)',
        r'(\w*дебаль\w*)',
        r'(\w*внебал\w*)',
        r'(\w*шебутн\w*)',
        r'(\w*брюх\w+)',
        r'(\w*хл[ёе]ба?н\w*)',
        r'(\w*жабл\w*)',
        r'(\w*витеблян\w*)',
        r'(\w*ансамбл\w*)',
        r'(\w*асс?амбл\w*)',
        r'(\w*археба\w+)',
        r'(\bбебут\w*)',
        r'(\w*ве[рт]ху\w*)',
        r'(\w*(?:вы|за|от|с)греб\w*)',
        # r'(\w*доверху\w*)',
        r'(\w*гренобл\w*)',
        r'(\w*деребин\w*)',
        r'(\w*нотабл\w*)',
        r'(\w*грабля\w*)',
        r'(\w*ознобл\w*)',
        r'(\w*скл[ая]бл\w*)',
        r'(\w*психу[йе]\w*)',
        r'(\w*сплоху\w*)',
    ]
    if not extended_filter_enabled:
        good_words.extend([
            r'(\bгр[ёе]бан\w*)',
        ])
    good_words_re = re.compile('|'.join(good_words), re.IGNORECASE | re.UNICODE)


def get_default_filter():
    return ObsceneWordsFilter(ObsceneConf.bad_words_re, ObsceneConf.good_words_re)


class Antimat:
    words_filter = get_default_filter()

    @classmethod
    def bad_words_count(cls, text: str) -> int:
        return sum(1 for _ in cls.bad_words(text))

    @classmethod
    def bad_words(cls, text: str) -> Iterable['str']:
        return (m.group(0) for m in cls.words_filter.find_bad_word_matches_without_good_words(text))
