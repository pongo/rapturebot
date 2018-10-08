# coding=UTF-8
import uuid

import telegram

from src.utils.cache import cache, USER_CACHE_EXPIRE


def get_callback_data(data) -> str:
    key = str(uuid.uuid4())
    cache.set(f'callback:{key}', data, time=USER_CACHE_EXPIRE)
    return key


def remove_inline_keyboard(bot: telegram.Bot, chat_id: int, message_id: int) -> None:
    reply_markup = telegram.InlineKeyboardMarkup([])
    bot.editMessageReplyMarkup(chat_id, message_id, reply_markup=reply_markup)
