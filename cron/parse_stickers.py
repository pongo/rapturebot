# coding=UTF-8
"""
Скрипт загружает случайные стикерпаки (с инета и других мест).
Запускать нужно каждый день в 10 вечера:

    0 22 * * * python3 /home/--path--/parse_stickers.py

"""

import pickle
from datetime import datetime, timedelta
import re

import redis
import requests
import random

YEAR = 31556926  # год
FEW_DAYS = 4 * 24 * 60 * 60  # 4 дня

re_base_addstickers = r"/addstickers/(\S+?)[<>[\]/,.\\'\"]"
urls = [
    ('https://tlgrm.ru/stickers/rss', r"tlgrm\.ru/stickers/(.+?)/install"),

    ('http://feed.exileed.com/vk/feed/tstickers', re_base_addstickers),
    ('http://feed.exileed.com/vk/feed/tgstickers', re_base_addstickers),

    ('https://tgram.ru/stickers/', r"href='https://tgram\.ru/stickers/(?:(?!['\"]))(\S+?)['\"]"),
    ('https://tgram.ru/wiki/stickers/PersonActionsPagedSorted.php?action=list&jtStartIndex=0&jtPageSize=50&jtSorting=pp%20DESC', r'"id":"(\S+?)"'),

    ('https://combot.org/telegram/stickers', re_base_addstickers),
    ('https://combot.org/telegram/stickers?page=2', re_base_addstickers),
    ('https://combot.org/telegram/stickers?page=3', re_base_addstickers),
    ('https://combot.org/telegram/stickers/top/weekly', re_base_addstickers),
]

_redis = redis.StrictRedis(host="localhost", port=6379, db=0)


class Cache:
    @staticmethod
    def get(key, default=None):
        cached = _redis.get(key)
        if cached:
            return pickle.loads(cached)
        return default

    @staticmethod
    def set(key, val, time=None):
        return _redis.set(key, pickle.dumps(val), ex=time)

    @staticmethod
    def delete(key):
        return _redis.delete(key)

    @staticmethod
    def delete_by_pattern(pattern: str):
        """
        Удаляет ключи из кэша по паттерну. Пример паттерна: 'user:*'

        See: https://stackoverflow.com/a/27561399/136559
        """
        _redis.eval("for i, name in ipairs(redis.call('KEYS', ARGV[1])) do redis.call('DEL', name); end", 0, pattern)


def request(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64; rv:55.0) Gecko/20100101 Firefox/55.0'}
    try:
        response = requests.get(url, headers=headers)
        return response.text
    except Exception:
        return ''

def get_urls_stickers(urls):
    result = set()
    for url, re_template in urls:
        content = request(url)
        stickers = re.findall(re_template, content, re.IGNORECASE)
        result.update(stickers)
    return result

def get_cached(cache, key):
    return set(cache.get(key, []))

def get_current_monday_str(additional_days=0):
    date = datetime.today()
    monday = date - timedelta(days=date.weekday() + additional_days)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y%m%d")

def get_monday_stickers(cache):
    result = get_cached(cache, f'pipinder:monday_stickersets:{get_current_monday_str()}')
    prev_monday = get_cached(cache, f'pipinder:monday_stickersets:{get_current_monday_str(additional_days=7)}')
    result.update(prev_monday)
    return result

def get_random_list(stickers, limit=100):
    stickers = filter(None.__ne__, stickers)  # исключаем None из списка
    stickers = sorted(stickers)
    random.shuffle(stickers)
    return stickers[:limit]


if __name__ == "__main__":
    cache = Cache()

    used_stickersets = get_cached(cache, 'pipinder:used_stickersets')

    stickers = set()
    stickers.update(get_cached(cache, 'pipinder:big_store'))
    stickers.update(get_monday_stickers(cache))
    stickers.update(get_urls_stickers(urls))

    stickers.difference_update(used_stickersets)  # удаляем использованные
    stickers.update(get_cached(cache, 'pipinder:fav_stickersets_names'))  # но сашины любимые все равно могут попасться
    print(len(stickers))

    tomorrow = (datetime.today() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y%m%d")
    cache.set(f'pipinder:stickersets:{tomorrow}', get_random_list(stickers), time=FEW_DAYS)
    cache.set(f'pipinder:big_store', get_random_list(stickers, 2000), time=YEAR)
