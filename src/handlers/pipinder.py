# coding=UTF-8
import random
from typing import Optional, List

import telegram

from src.utils.cache import cache, FEW_DAYS, YEAR
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.logger import logger
from src.utils.telegram_helpers import telegram_retry
from src.utils.time_helpers import today_str


@telegram_retry(tries=3, silence=True, logger=logger, title='pipinder:get_working_stickerset')
def get_working_stickerset(bot: telegram.Bot, chat_id: int, stickerset_name: str) -> Optional[telegram.StickerSet]:
    """
    Получаем от телеграма этот пак.
    """
    logger.debug(f'[pipinder:get_working_stickerset] trying get stickerset {stickerset_name}')
    bot.send_chat_action(chat_id, telegram.ChatAction.TYPING)
    return bot.get_sticker_set(stickerset_name)


def remove_stickersets_from_cache(stickersets: List[str]) -> None:
    """
    Удаляем указанные стикерпаки из списков в редисе.
    """

    def __remove(cache_list_name, stickersets, time) -> None:
        key = f'pipinder:{cache_list_name}'
        cached: list = cache.get(key, [])
        for stickerset_name in stickersets:
            if stickerset_name not in cached:
                continue
            try:
                cached.remove(stickerset_name)
            except Exception:
                pass
        cache.set(key, cached, time=time)

    __remove(f'stickersets:{today_str()}', stickersets, FEW_DAYS)
    __remove('big_store', stickersets, YEAR)


def find_working_stickerset(
        bot: telegram.Bot,
        chat_id: int,
        today_stickersets_names: List[str]) -> Optional[telegram.StickerSet]:
    """
    Находим первый рабочий пак, заодно удаляя нерабочие из редиса.
    """
    list_for_remove = []  # удаленные паки храним в отдельном списке
    for stickerset_name in today_stickersets_names:
        stickerset = get_working_stickerset(bot, chat_id, stickerset_name)
        if stickerset:
            break  # нашли рабочий
        list_for_remove.append(stickerset_name)  # нерабочий пак добавляем в список
    else:
        return None
    remove_stickersets_from_cache(list_for_remove)  # удаляем нерабочие
    return stickerset


def send_pipinder(bot: telegram.Bot, update: telegram.Update) -> None:
    message = update.message
    chat_id = message.chat_id

    # получаем список сегодняшних паков
    today_stickersets_names = cache.get(f'pipinder:stickersets:{today_str()}')
    if not today_stickersets_names:
        message.reply_text('Кажется что-то пошло не так. Здесь должен быть стикер, но его нет!')
        return

    # находим первый рабочий пак
    stickerset = find_working_stickerset(bot, chat_id, today_stickersets_names)
    if not stickerset:
        message.reply_text('Странно, все стикеры оказались нерабочими')
        return

    # добавляем выбранный пак в использованные
    # нам не нужно здесь проверять, был ли уже такой пак,
    # потому что это проверятся заранее, еще на этапе подготовки паков
    add_stickerset_to_used(stickerset)

    # отправляем случайный стикер из пака
    sticker = random.choice(stickerset.stickers)
    bot.send_sticker(chat_id, sticker)


def add_stickerset_to_used(stickerset):
    """
    Добавляем пак в список использованных.
    """
    used_stickersets = set(cache.get('pipinder:used_stickersets', []))
    used_stickersets.add(stickerset.name)
    cache.set('pipinder:used_stickersets', used_stickersets, time=YEAR)


@chat_guard
@collect_stats
@command_guard
def pipinder(bot: telegram.Bot, update: telegram.Update):
    send_pipinder(bot, update)
