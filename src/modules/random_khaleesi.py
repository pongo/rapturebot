# coding=UTF-8
import random
from datetime import datetime
from typing import Optional

from src.modules.khaleesi import KhaleesiUtils
from src.utils.cache import cache


class RandomKhaleesi:
    @classmethod
    def is_its_time_for_khaleesi(cls, chat_id: int) -> bool:
        # постить можно раз в N часов
        limited = cache.get(cls.__get_limited_cache_key(chat_id))
        if limited:
            return False

        # считаем сколько раз за сутки кхалиси постила рандомно
        count = cache.get(cls.__get_count_cache_key(chat_id))
        if count:
            # лимит: 3 раза в сутки
            if count >= 3:
                return False
            # если уже постила утром, то след. раз только днем/вечером
            today = datetime.today()
            if count == 1 and today.hour <= 12:
                return False

        # считаем шанс
        return random.randint(1, 100) <= 2

    @classmethod
    def increase_khaleesi_time(cls, chat_id: int) -> None:
        key = cls.__get_count_cache_key(chat_id)
        count = cache.get(key)
        if not count:
            count = 0
        cache.set(key, count + 1, time=(2 * 24 * 60 * 60))
        # и теперь ждем 4 часа
        cache.set(cls.__get_limited_cache_key(chat_id), True, time=(4 * 60 * 60))

    @classmethod
    def is_good_for_khaleesi(cls, orig_line: str) -> bool:
        """
        Подходит ли это сообщение для обработки Кхалиси?
        """
        if orig_line is None:
            return False

        line = orig_line.strip()
        if len(line) < 15:
            return False

        last_sentense_len = len(KhaleesiUtils.get_last_sentense(line).strip())
        if last_sentense_len < 15 or last_sentense_len > 200:
            return False

        return True

    @staticmethod
    def __get_base_cache_key(chat_id: int, tail: str, date: Optional[datetime]=None) -> str:
        _date = datetime.today() if date is None else date
        date_str = _date.strftime('%Y%m%d')
        return f'khaleesi:{date_str}:{chat_id}:{tail}'

    @classmethod
    def __get_limited_cache_key(cls, chat_id, date=None) -> str:
        return cls.__get_base_cache_key(chat_id, 'limited', date)

    @classmethod
    def __get_count_cache_key(cls, chat_id, date=None) -> str:
        return cls.__get_base_cache_key(chat_id, 'count', date)
