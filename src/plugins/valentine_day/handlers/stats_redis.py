from threading import Lock
from typing import Optional

from src.utils.cache import cache, USER_CACHE_EXPIRE
from src.plugins.valentine_day.model import CACHE_PREFIX, Stats
from src.utils.logger_helpers import get_logger


logger = get_logger(__name__)


class StatsRedis:
    lock = Lock()

    def __init__(self):
        self.stats: Stats = Stats()

    def __enter__(self) -> Stats:
        self.stats = cache.get(self._key(), Stats())
        return self.stats

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            cache.set(self._key(), self.stats, time=USER_CACHE_EXPIRE)
            return
        logger.error(exc_val, exc_type, exc_tb)
        return True

    @staticmethod
    def _key():
        return f'{CACHE_PREFIX}:stats'
