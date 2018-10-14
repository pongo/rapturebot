"""
Рядовой ночной стражи
"""
import random
from datetime import datetime
from threading import Timer

import pytils
import telegram

from src.config import CONFIG
from src.modules.khaleesi import Khaleesi
from src.utils.cache import cache

CACHE_KEY = 'night_watch'


def all_s_well(bot: telegram.Bot) -> None:
    """
    Отправляет в основной чат сообщение типа "12 часов и все спокойно"
    """
    if 'anon_chat_id' not in CONFIG:
        return
    text = f'{Khaleesi.khaleesi(get_hour(datetime.now()))} 🐉'
    bot.send_message(CONFIG['anon_chat_id'], text)


def get_hour(now: datetime) -> str:
    """
    Отсылка к Пратчетту.
    """
    hour = int(now.strftime("%I"))
    plural = pytils.numeral.sum_string(hour, pytils.numeral.MALE, 'час, часа, часов')
    return f'{plural} и все спокойно!'.upper()


def postpone_our_phrase(bot: telegram.Bot) -> None:
    """
    Через случайное время запускает функцию `all_s_well`
    """
    wait = how_long_we_should_wait()
    timer = Timer(wait, all_s_well, args=[bot])
    timer.start()


def go_go_watchmen(bot: telegram.Bot) -> None:
    """
    Стражник смотрит на часы: а пора ли уже идти в дозор?
    """
    # стражник выходит на работу в 22 часа
    if datetime.now().hour not in (22, 23,):
        return

    # на случай если метод вызван и в 22, и в 23
    # второй раз игнорируем
    if cache.get(f'{CACHE_KEY}:patrols', False):
        return
    cache.set(f'{CACHE_KEY}:patrols', True, time=10 * 60 * 60)

    # через случайные N часов запустить функцию all_s_well
    postpone_our_phrase(bot)


def how_long_we_should_wait() -> int:
    """
    Возвращает случайно от 1 до 6 часов в секундах
    """
    hour = 60 * 60
    wait = random.randint(1 * hour, 6 * hour)
    return wait
