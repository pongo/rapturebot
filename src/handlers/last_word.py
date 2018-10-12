# coding=UTF-8

import telegram
from telegram.ext import run_async

from src.utils.cache import cache, TWO_YEARS
from src.utils.logger_helpers import get_logger

logger = get_logger(__name__)


def get_last_word_cache_key(cid, uid) -> str:
    return f'last_word:{cid}:{uid}'


def callback_last_word(bot: telegram.Bot, _: telegram.Update, query, data):
    uid = query.from_user.id
    cid = query.message.chat_id
    msg_ids = [result[0] for result in
               (cache.get(get_last_word_cache_key(cid, _uid)) for _uid in data['leaves_uid']) if
               result is not None and isinstance(result, tuple)]
    if len(msg_ids) == 0:
        try:
            bot.sendMessage(uid, 'Увы, у меня не сохранились последние слова этих человеков 😢')
        except Exception:
            pass
        return

    try:
        bot.sendMessage(uid, 'Последние слова убывших:')
    except Exception:
        pass
    for msg_id in msg_ids:
        try:
            bot.forwardMessage(uid, cid, message_id=msg_id)
        except Exception:
            pass


@run_async
def last_word(_: telegram.Bot, update: telegram.Update):
    message = update.message
    left = message.left_chat_member is not None
    join = message.new_chat_members is not None and len(message.new_chat_members) > 0
    if left or join:
        return
    cache.set(get_last_word_cache_key(update.message.chat_id, update.message.from_user.id),
              (message.message_id, message.date), time=TWO_YEARS)
