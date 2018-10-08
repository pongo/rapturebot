# coding=UTF-8
import random
from typing import List

import telegram

from src.config import CONFIG
from src.modules.antimat import Antimat
from src.modules.matshowtime import matshowtime
from src.utils.cache import pure_cache, FEW_DAYS, USER_CACHE_EXPIRE
from src.utils.time_helpers import get_current_monday_str


def mat_notify(bot: telegram.Bot, update: telegram.Update):
    message = update.message
    text = message.text if message.text else message.caption
    if text is None:
        return

    # получаем матерные слова из текста
    mat_words = list(word.lower() for word in Antimat.bad_words(text))
    if len(mat_words) == 0:
        return

    cid = message.chat_id
    uid = message.from_user.id

    matshowtime.send(bot, mat_words)

    # чужие форварды не учитываем
    if is_foreign_forward(uid, message):
        return

    # нужно сохранить их в редисе для статистики
    # мы сохраняем только слова, которые сами используем
    # поэтому этот вызов стоит после проверки на внешние форварды
    save_to_redis(cid, mat_words)

    # нам нужно уведомлять этого пользователя?
    if uid not in CONFIG.get('mat_notify_uids', []):
        return

    message_id = message.message_id
    send_mat_notify(bot, cid, mat_words, message_id)


def send_mat_notify(bot: telegram.Bot, cid: int, mat_words: List[str], message_id: int) -> None:
    phrases = [
        'И этими устами ты целуешь папочку?',
        'Как грубо!',
        'А потом в музей, да?',
        'Я не понимаю. Ничего не понимаю.',
        'Сажа, как же так!?',
        'Сапожница!',
    ]
    mat_words_str = ', '.join(word.upper() for word in mat_words)
    msg = f'{random.choice(phrases)} 🙈\n\n<b>{mat_words_str}</b>'
    bot.send_message(cid, msg, reply_to_message_id=message_id, parse_mode=telegram.ParseMode.HTML)


def is_foreign_forward(uid: int, message: telegram.Message) -> bool:
    """
    Это сообщение -- чужой форвард?
    """
    # это вообще форвард?
    if not message.forward_date:
        return False
    # вернет False если это форвард от uid
    return message.forward_from is None or message.forward_from.id != uid


def save_to_redis(cid: int, mat_words: List[str]) -> None:
    monday = get_current_monday_str()

    # сохраняем все уникальные матерные слова в редис, чтобы проверять ложные срабатывания
    pure_cache.add_to_set(f"mat:daily_uniq:{monday}", mat_words, time=FEW_DAYS)

    # сохраняем все слова для подсчета статистики по словам
    pure_cache.append_list(f'mat:words:{monday}:{cid}', mat_words, time=USER_CACHE_EXPIRE)
