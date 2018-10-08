# coding=UTF-8
from typing import Optional, List, Union, Set

import redis

try:
    import cPickle as pickle  # type:ignore
except ImportError:
    import pickle  # type:ignore

from src.config import CONFIG

if 'cache' in CONFIG:
    _redis = redis.StrictRedis(host=CONFIG['cache']['redis']['host'], port=CONFIG['cache']['redis']['port'], db=CONFIG['cache']['redis']['db'])
    _pure_redis = redis.StrictRedis(host=CONFIG['cache']['redis']['host'], port=CONFIG['cache']['redis']['port'], db=CONFIG['cache']['redis']['db'], charset='utf-8', decode_responses=True)
else:
    # print("Can't connect to Redis")
    _redis = None
    _pure_redis = None

USER_CACHE_EXPIRE = 15 * 24 * 60 * 60  # 15 дней
MONTH = 30 * 24 * 60 * 60  # 30 дней
DAY = 1 * 24 * 60 * 60  # день
TWO_DAYS = 2 * 24 * 60 * 60  # 2 дня
FEW_DAYS = 4 * 24 * 60 * 60  # 4 дня
SIX_MONTHS = 6 * MONTH
YEAR = 31556926  # год
TWO_YEARS = 2 * YEAR

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


class PureCache:
    """
    Аналог Cache для хранения простых объектов. Добавляет префикс "__pure__:".

    Из-за технических особенностей, все объекты будут сохранены как строки. Т.е. булево True станет строкой "True".
    """
    prefix = '__pure__'

    @staticmethod
    def get(key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Всегда возвращает или None, или str. Даже если хранится число.
        """
        cached = _pure_redis.get(f'__pure__:{key}')
        if cached:
            return cached
        return default

    @staticmethod
    def set(key: str, val, time=None) -> None:
        _pure_redis.set(f'__pure__:{key}', val, ex=time)

    @staticmethod
    def incr(key: str, amount: int = 1) -> None:
        _pure_redis.incr(f'__pure__:{key}', amount)
        _pure_redis.expire(f'__pure__:{key}', USER_CACHE_EXPIRE)

    @classmethod
    def get_int(cls, key: str, default: Optional[int] = None) -> Optional[int]:
        cached = cls.get(key)
        if cached:
            try:
                return int(cached)
            except Exception:
                pass
        return default

    @classmethod
    def append_list(cls, key: str, value: Union[str, list, tuple, Set], time=None) -> None:
        if isinstance(value, (list, tuple, set)):
            _pure_redis.rpush(f'{cls.prefix}:{key}', *value)
        else:
            _pure_redis.rpush(f'{cls.prefix}:{key}', value)
        if time:
            _pure_redis.expire(f'{cls.prefix}:{key}', time)

    @classmethod
    def add_to_list(cls, key: str, value, time=None) -> None:
        cls.append_list(key, value, time)

    @classmethod
    def add_to_set(cls, key: str, value: Union[str, list, tuple, Set], time=None) -> None:
        if isinstance(value, (list, tuple, set)):
            _pure_redis.sadd(f'{cls.prefix}:{key}', *value)
        else:
            _pure_redis.sadd(f'{cls.prefix}:{key}', value)
        if time:
            _pure_redis.expire(f'{cls.prefix}:{key}', time)

    @classmethod
    def get_set(cls, key: str) -> Set[str]:
        return set(_pure_redis.smembers(f'{cls.prefix}:{key}'))

    @classmethod
    def get_list(cls, key: str) -> List[str]:
        return _pure_redis.lrange(f'{cls.prefix}:{key}', 0, -1)


cache = Cache()
pure_cache = PureCache()
