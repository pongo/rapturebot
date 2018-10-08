# coding=UTF-8
import logging
import random
import typing
from datetime import datetime

import telegram
from telegram.ext import run_async

from src.config import CONFIG
from src.utils.cache import cache
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard

logger = logging.getLogger(__name__)


def get_base_name(key: str) -> typing.Optional[str]:
    cache_key = f'{key}:{datetime.today().strftime("%Y%m%d")}'
    name = cache.get(cache_key)
    if name:
        return name

    from collections import OrderedDict
    from collections import deque
    month = 30 * 24 * 60 * 60  # 30 дней

    # особые дни
    if key == 'orzik' and datetime.today().strftime("%m-%d") == '04-12':
        name = 'Гагарин'
        cache.set(cache_key, name, time=month)
        return name

    # получаем непустые имена без пробелов
    stripped_names = [x for x in (x.strip() for x in CONFIG.get(key, 'Никто').split(',')) if x]

    # удаляем дубликаты, сохраняя порядок имен
    uniq_names = list(OrderedDict((x, True) for x in stripped_names).keys())

    # мы отдельно храним последние выбранные имена, чтобы они не повторялись
    recent_names = cache.get(f'{key}_recent')
    if recent_names is None:
        recent_names = []
    half_len = round(len(uniq_names) / 2)
    deq = deque(maxlen=half_len)
    deq.extend(recent_names)

    # типа бесконечный цикл, в течение которого мы пытаемся выбрать случайное имя, которое еще не постили
    for i in range(1, 1000):
        name = random.choice(uniq_names)
        if name not in recent_names:
            deq.append(name)
            cache.set(f'{key}_recent', list(deq), time=month)
            cache.set(cache_key, name, time=month)
            return name
    return None


@run_async
@chat_guard
@collect_stats
@command_guard
def orzik(bot, update):
    """
    Говорит случайное имя Озрика.

    Имена добавляйте в конец списка, через запятую, с большой буквы. Дубликаты он сам удалит.
    """
    chat_id = update.message.chat_id
    name = get_base_name('orzik')
    if name:
        return bot.send_message(chat_id, f"Сегодня ты: {name}")
    # уведомляем о баге
    bot.sendMessage(chat_id, 'Это баг, такого не должно быть')


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
    if name:
        bot.send_message(chat_id, f"Сегодня ты: {name}")
        return
    # уведомляем о баге
    bot.sendMessage(chat_id, 'Это баг, такого не должно быть')


@run_async
def orzik_correction(bot, update):
    chat_id = update.message.chat_id
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y%m%d")
    delayed_key = f'orzik_correction:{today}:{chat_id}'
    delayed = cache.get(delayed_key)
    if delayed:
        return
    name = get_base_name('orzik')
    if name is None:
        return bot.sendMessage(chat_id, 'Баг: у orzik_correction возникли проблемы')

    # помимо имен бот еще иногда дает орзику указания ("НЕ постишь селфи")
    # затруднительно автоматически преобразовывать это к "сегодня он не постит селфи", да и не нужно.
    # зато нужно отличать имена от таких указаний и игнорировать их
    # обычно имена состоят из одного слова
    # но даже если имя из двух слов, то обычно оба слова начинаются с больших букв - это и проверяем
    if len(name.split(' ')) > 1 and not name.istitle():
        # если это не имя, то сегодняшний день пропускаем
        cache.set(delayed_key, True, time=(2 * 24 * 60 * 60))
        return

    cache.set(delayed_key, True, time=(4 * 60 * 60))  # и теперь ждем 4 часа
    bot.sendMessage(chat_id, f'Сегодня он {name}', reply_to_message_id=update.message.message_id)
