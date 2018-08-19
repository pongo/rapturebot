# coding=UTF-8
from src.utils.cache import cache


def is_today_special() -> bool:
    return cache.get('special_day', False)


def set_today_special(value=True) -> None:
    cache.set('special_day', value, time=25 * 60 * 60)
