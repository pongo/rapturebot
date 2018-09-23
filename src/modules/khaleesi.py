# coding=UTF-8
import functools
import itertools
import random
import re


class PostCorrection:
    @classmethod
    def get_post_correction(cls, words):
        result = []
        re_chto = re.compile('^сьто')
        exists_words = set()
        for word in words:
            if word in exists_words:
                if re_chto.search(word):
                    result.append(re_chto.sub(random.choice(['чьто', 'сто', 'шьто', 'што']), word, 1))
                    continue
                result.append(cls.__random_replace(word))
                continue
            if len(word) < 2:
                result.append(word)
                continue
            if 'ийи' in word:
                result.append(word.replace('ийи', 'ии'))
                continue
            result.append(cls.__random_replace(word) if random.randint(1, 100) < 20 else word)
            exists_words.add(word)

        return result

    @staticmethod
    def __random_replace(word):
        replaces = [
            ("ожк", "озьг"),
            ("кол", "га"),
            ("ко", "га"),
            ("колгот", "гагот"),
            ("шо", "ша"),
            ("дка", "ка"),
            ("он", "онь"),
            ("б", "п"),
            ("хи", "ни"),
            ("шк", "к"),
            ("тро", "го"),
            ("тка", "пка"),
            ("кров", "кав"),
            ("ра", "я"),
            ("дюк", "дю"),
            ("ойд", "анд"),
            ("дка", "та"),
            ("ро", "мо"),
            ("ны", "ни"),
            ("ре", "е"),
            ("ле", "не"),
            ("ки", "ке"),
            ("ш", "ф"),
            ("шка", "вха"),
            ("гри", "ги"),
            ("ч", "щ"),
            ("ре", "ле"),
            ("го", "хо"),
            ("ль", "й"),
            ("иг", "ег"),
            ("ра", "ва"),
            ("к", "г"),
            ("зо", "йо"),
            ("зо", "ё"),
            ("рё", "йо"),
            ("ск", "фк"),
            ("ры", "вы"),
            ("шо", "фо"),
            ("ло", "ле"),
            ("сы", "фи"),
            ("еня", "ея"),
            ("пель", "пюль"),
            ("а", "я"),
            ("у", "ю"),
            ("о", "ё"),
            ("ща", "ся"),
            ("ы", "и"),
            ("ри", "ви"),
            ("ло", "во"),
            ("е", "и"),
            ("и", "е"),
            ("а", "о"),
            ("о", "а"),
        ]
        random.shuffle(replaces)
        for repl_search, replace in replaces:
            if repl_search in word:
                return word.replace(repl_search, replace, 1)
        return word

class KhaleesiUtils:
    re_grouping_space_regex = re.compile('([^\w_-]|[+])', re.U)
    re_last_sentense = re.compile(r".*[.;?!]+\s*(.+(?:[.;?!]|$))", re.IGNORECASE)
    re_cyrillic = re.compile("[\u0400-\u0500]+")

    @staticmethod
    def get_words(line):
        return [t for t in KhaleesiUtils.re_grouping_space_regex.split(line) if t]

    @staticmethod
    def previous_and_next(some_iterable):
        prevs, items, nexts = itertools.tee(some_iterable, 3)
        prevs = itertools.chain([''], prevs)
        nexts = itertools.chain(itertools.islice(nexts, 1, None), [''])
        return zip(prevs, items, nexts)

    @staticmethod
    def has_cyrillic(str):
        return True if KhaleesiUtils.re_cyrillic.search(str) else False

    @staticmethod
    @functools.lru_cache(maxsize=100, typed=False)
    def lower_char(char):
        return char.lower()

    @staticmethod
    @functools.lru_cache(maxsize=100, typed=False)
    def replace_with_case(current_char, replace):
        return replace.upper() if current_char.isupper() else replace

    @staticmethod
    def get_last_sentense(line):
        """
        Возвращет последнее предложение в последней строке.
        """
        last_line = (line.strip().splitlines()[-1]).strip()
        rstripped = last_line.rstrip('.;?! ')  # для работы с многоточием, потом мы его вернем

        # ищем последнее предложение
        match = KhaleesiUtils.re_last_sentense.search(rstripped)
        if not match:
            return last_line

        diff = '' if rstripped == last_line else last_line.replace(rstripped, '')
        return match.group(1) + diff

class Khaleesi:
    re_has_bound = re.compile("[$^]")
    re_not_first = re.compile(r"^\(")
    global_replaces = None

    @staticmethod
    def get_replaces():
        # сначала подготавливаем правила
        #
        # @ означает текущую букву
        # ^ и $ - начало/конец слова (как в регулярных выражениях
        # С и Г - любая согласная/гласная буквы
        # до знака "=" у нас искомый паттерн, а после знака - на что мы будем заменять эту букву
        replaces = {
            # 'абвгдеёжзийклмнопрстуфхцчшщъыьэюя': '',
            'а': [
                '^дра = а',
                '^ @  = @',
                '[тбвкпмнг]@$  = я',
                '@ $  = @',
                '@ я  = @',
                'С @  = я',
                'Г @  = я',
            ],
            'в': [
                'з @ = ь@'
            ],
            'е': [
                '@ С * $ = @',
                '@ - = @',
                'С @ = и',
                'Г @ = и',
            ],
            'ж': [
                '@ = з',
            ],
            'л': [
                '^ @ = @',
                '@ $ = @',
                '@р$ = @',
                'лл  = @@',
                '@к  = @',
                '@п  = @',
                'С @ = @',
                'Г @ = ',
            ],
            'н': [
                'кон$ = нь',
            ],
            'о': [
                '[мпжзгтс]@[цкнгшщзхфвпджбтмсч] = ё',
            ],
            'р': [
                '^дра = _',
                '^ @ = л',
                'Г @ = й',
                'С @ = ь',
            ],
            'у': [
                '^ @ = @',
                '@   = ю',
            ],
            'ч': [
                '^что = сь',
            ],
            'щ': [
                '^тыщ$ = сь',
                '^ @ = @',
                '@   = с',
            ],
            'ь': [
                'л@  = й',
                '@ $ = @',
                '@Г$ = @',
                'С@  = @',
                '@   = й',
            ],
        }

        # теперь мы на основе этих правил делаем регулярные выражения
        re_replaces = {}
        for char, str_patterns in replaces.items():
            re_patterns = []
            for str_pattern in str_patterns:
                re_pattern = []
                search, replace = str_pattern.split('=')
                replace = replace.strip()
                replace = replace.replace('@', char)
                if replace == '_':
                    replace = ''
                for element in search.replace(' ', ''):
                    if element == '@':
                        re_pattern.append('({})'.format(char))
                    elif element == 'Г':
                        re_pattern.append('[vьъаеёиоуыэюя]')  # первая v - английская
                    elif element == 'С' or element == 'C':
                        re_pattern.append('[cьъйцкнгшщзхфвпрлджбтмсч]')  # первая c - английская
                    else:
                        re_pattern.append(element)
                re_pattern_str = ''.join(re_pattern)
                regex = re.compile(re_pattern_str, re.IGNORECASE)
                re_patterns.append((re_pattern_str, regex, replace))
            re_replaces[char] = re_patterns
        return re_replaces

    @staticmethod
    def prepare_word_for_search(current_char, index, word):
        """
        заменяем такие же буквы спецсимволом (чтобы не мешались при поиске)
        """
        vowels = 'аеёиоуыэюя'  # consonants = set('йцкнгшщзхфвпрлджбтмсч')  # signs = set('ъь')
        word_for_pattern = word.replace(current_char, 'v' if current_char in vowels else 'c')
        word_for_pattern = word_for_pattern[:index - 1] + current_char + word_for_pattern[index:]
        return word_for_pattern

    @classmethod
    def replace_word(cls, word):
        if cls.global_replaces is None:
            cls.global_replaces = cls.get_replaces()
        # если не содержит кириллицу
        if not KhaleesiUtils.has_cyrillic(word):
            return word

        result = []
        characters = KhaleesiUtils.previous_and_next(word)
        for index, tuple in enumerate(characters, start=1):
            prev_char, current_char, next_char = tuple
            lower_current = KhaleesiUtils.lower_char(current_char)

            if lower_current not in cls.global_replaces:
                result.append(current_char)
                continue

            result.append(cls.replace_char(current_char, index, lower_current, next_char, prev_char, word))
        return ''.join(result)

    @classmethod
    @functools.lru_cache(maxsize=500, typed=False)
    def replace_char(cls, current_char, index, lower_current, next_char, prev_char, word):
        if cls.global_replaces is None:
            cls.global_replaces = cls.get_replaces()
        replaced_char = current_char
        word_for_pattern = None
        for re_pattern, regex, replace in cls.global_replaces[lower_current]:
            # заменяем только если найдено соответствие. иначе пропускаем
            if cls.re_has_bound.search(re_pattern):
                if word_for_pattern is None:
                    word_for_pattern = cls.prepare_word_for_search(current_char, index, word)
                if not regex.search(word_for_pattern):
                    continue
            elif re.search(r"^\S+\(.+\)\S+$", re_pattern):
                if not regex.search(prev_char + current_char + next_char):
                    continue
            elif not cls.re_not_first.search(re_pattern):
                if not regex.search(prev_char + current_char):
                    continue
            else:
                if not regex.search(current_char + next_char):
                    continue

            # заменяем с учетом регистра
            replaced_char = KhaleesiUtils.replace_with_case(current_char, replace)
            break
        return replaced_char

    @classmethod
    def khaleesi(cls, orig_line, last_sentense=False, post_correction=True):
        line = orig_line.strip()
        if last_sentense:
            line = KhaleesiUtils.get_last_sentense(line).strip()
        result = []
        for word in KhaleesiUtils.get_words(line):
            if len(word) < 2:
                result.append(word)
                continue
            result.append(cls.replace_word(word))
        if post_correction:
            result = PostCorrection.get_post_correction(result)
        return ''.join(result)
