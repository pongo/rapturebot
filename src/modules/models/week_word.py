# coding=UTF-8
from threading import Lock

from src.utils.cache import cache, USER_CACHE_EXPIRE
from src.utils.misc import sort_dict
from src.utils.time_helpers import get_current_monday

try:
    import pymorphy2
    from pymorphy2.tokenizers import simple_word_tokenize

    morph = pymorphy2.MorphAnalyzer()
except ImportError:
    pymorphy2 = None
    simple_word_tokenize = None
    morph = None


class WeekWord:
    lock = Lock()

    @classmethod
    def add(cls, text, cid):
        if not pymorphy2:
            return
        if not text:
            return

        text = text.strip().lower()
        if len(text) == 0:
            return

        words = (word for word in simple_word_tokenize(text))
        all_tokens = (morph.parse(word)[0] for word in words)
        useful_tokens = cls.__skip_tokens(all_tokens)
        normal_forms = (token.normal_form for token in useful_tokens)

        monday = get_current_monday()
        with cls.lock:
            db = cls.__get_db(monday, cid)
            for word in normal_forms:
                if len(word) < 3:
                    continue
                if word in db:
                    db[word] += 1
                else:
                    db[word] = 1
            cls.__set_db(db, monday, cid)

    @classmethod
    def get_top_word(cls, monday, cid):
        if not pymorphy2:
            return None
        db = cls.__get_db(monday, cid)
        if not db:
            return None
        words = sort_dict(db)
        return words

    @staticmethod
    def __skip_tokens(tokens):
        def is_excluded(token):
            if token.word == 'да':
                return False
            exclude = [
                'PNCT',  # пунктуация
                'PREP',  # предлог
                'CONJ',  # союз
                'PRCL',  # частица
                'NPRO',  # местоимение-существительное
                'Name',  # имя
            ]
            for gram in exclude:
                if gram in token.tag:
                    return True
            return False

        for token in tokens:
            # if 'NOUN' not in token.tag:
            #     continue
            if is_excluded(token):
                continue
            yield token

    @staticmethod
    def __get_cache_key(monday, cid):
        return f'weekword:{monday.strftime("%Y%m%d")}:{cid}'

    @classmethod
    def __get_db(cls, monday, cid):
        cached = cache.get(cls.__get_cache_key(monday, cid))
        if cached:
            return cached
        return {}

    @classmethod
    def __set_db(cls, newdb, monday, cid):
        cache.set(cls.__get_cache_key(monday, cid), newdb, time=USER_CACHE_EXPIRE)
