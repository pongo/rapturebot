from datetime import datetime
from typing import Optional

from src.commands.i_stat.i_stat import ChatStatistician, ChatStat
from src.utils.cache import cache, USER_CACHE_EXPIRE
from src.utils.time_helpers import get_current_monday, get_date_monday


class RedisChatStatistician(object):
    def __init__(self, chat_id: int):
        self.chat_id = chat_id
        self.chat_statistician = ChatStatistician()

    def load(self):
        self.chat_statistician.db = cache.get(self.__get_cache_key(), ChatStat())

    def save(self):
        cache.set(self.__get_cache_key(), self.chat_statistician.db, time=USER_CACHE_EXPIRE)

    def __get_cache_key(self, date: Optional[datetime] = None) -> str:
        date = get_current_monday() if date is None else get_date_monday(date)
        return f'i_stat:{date.strftime("%Y%m%d")}:{self.chat_id}'
