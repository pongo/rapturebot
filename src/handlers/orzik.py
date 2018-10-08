# coding=UTF-8
import random
from collections import OrderedDict
from collections import deque
from datetime import datetime

import telegram
from telegram.ext import run_async

from src.config import CONFIG
from src.utils.cache import cache
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard

MONTH = 30 * 24 * 60 * 60  # 30 дней


def is_space_day() -> bool:
    """
    Сегодня 12 апреля?
    """
    return datetime.today().strftime("%m-%d") == '04-12'


def generate_next_name(key: str) -> str:
    """
    Возвращает следующее неиспользованное имя
    """
    # особые дни
    if key == 'orzik' and is_space_day():
        return 'Гагарин'

    # получаем непустые имена без пробелов
    stripped_names = [x for x in (x.strip() for x in CONFIG.get(key, 'Никто').split(',')) if x]

    # удаляем дубликаты, сохраняя порядок имен
    uniq_names = list(OrderedDict((x, True) for x in stripped_names).keys())

    # мы отдельно храним последние выбранные имена, чтобы они не повторялись
    recent_names = cache.get(f'{key}_recent', [])

    # очередь deq используется, чтобы хранить половину от возможного числа имен
    half_len = round(len(uniq_names) / 2)
    deq: deque = deque(maxlen=half_len)
    deq.extend(recent_names)

    # типа бесконечный цикл, в течение которого выбирается случайное имя, которое еще не постили
    for _ in range(1, 1000):
        name = random.choice(uniq_names)
        if name not in recent_names:
            deq.append(name)
            cache.set(f'{key}_recent', list(deq), time=MONTH)
            return name
    return 'Никто'


def get_base_name(key: str) -> str:
    """
    Возвращает имя
    """
    cache_key = f'{key}:{datetime.today().strftime("%Y%m%d")}'
    name = cache.get(cache_key)
    if name:
        return name

    name = generate_next_name(key)
    cache.set(cache_key, name, time=MONTH)
    return name


@run_async
@chat_guard
@collect_stats
@command_guard
def orzik(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Говорит случайное имя Озрика.

    Имена добавляйте в конец списка, через запятую, с большой буквы. Дубликаты он сам удалит.
    """
    chat_id = update.message.chat_id
    name = get_base_name('orzik')
    bot.send_message(chat_id, f"Сегодня ты: {name}")


@run_async
@chat_guard
@collect_stats
@command_guard
def lord(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Для аляски. Аналог /orzik
    """
    chat_id = update.message.chat_id
    name = get_base_name('lord')
    bot.send_message(chat_id, f"Сегодня ты: {name}")


@run_async
def orzik_correction(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Реакция на упоминание орзика
    """
    chat_id = update.message.chat_id
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y%m%d")
    delayed_key = f'orzik_correction:{today}:{chat_id}'

    # уже постили. нужно ждать
    delayed = cache.get(delayed_key)
    if delayed:
        return
    name = get_base_name('orzik')

    # помимо имен бот еще иногда дает орзику указания ("НЕ постишь селфи")
    # затруднительно автоматически преобразовывать это к "сегодня он не постит селфи", да и не нужно
    # зато нужно отличать имена от таких указаний и игнорировать их
    # обычно имена состоят из одного слова
    # но даже если имя из двух слов, то обычно оба слова начинаются с больших букв - это и проверяем
    if len(name.split(' ')) > 1 and not name.istitle():
        # если это не имя, то сегодняшний день пропускаем
        cache.set(delayed_key, True, time=(2 * 24 * 60 * 60))
        return

    cache.set(delayed_key, True, time=(4 * 60 * 60))  # и теперь ждем 4 часа
    bot.send_message(chat_id, f'Сегодня он {name}', reply_to_message_id=update.message.message_id)
