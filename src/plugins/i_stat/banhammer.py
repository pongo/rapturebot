from enum import Enum, auto

from src.plugins.i_stat.db import RedisChatStatistician
from src.utils.cache import cache, SIX_MONTHS


class BanStatus(Enum):
    BANNED = auto()
    UNBANNDED = auto()


def get_key(chat_id: int, user_id: int) -> str:
    return f'i_stat:ban:{chat_id}:{user_id}'


def is_banned(chat_id: int, user_id: int) -> bool:
    return cache.get(get_key(chat_id, user_id), False)


def banhammer(chat_id: int, user_id: int) -> BanStatus:
    banned = is_banned(chat_id, user_id)
    if banned:
        unban(chat_id, user_id)
        return BanStatus.UNBANNDED

    ban(chat_id, user_id)
    return BanStatus.BANNED


def ban(chat_id: int, user_id: int, reset: bool = True, time=SIX_MONTHS) -> None:
    cache.set(get_key(chat_id, user_id), True, time=time)
    if reset:
        rs = RedisChatStatistician(chat_id)
        rs.load()
        rs.chat_statistician.reset(user_id)
        rs.save()


def unban(chat_id: int, user_id: int) -> None:
    cache.delete(get_key(chat_id, user_id))
