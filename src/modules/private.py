# coding=UTF-8
import random
import re
from datetime import datetime
from functools import wraps

import telegram
from telegram.ext import run_async

from src.config import CONFIG
from src.handlers import send_huificator, send_mystat, send_whois, send_mylove
from src.modules.models.chat_user import ChatUser
from src.modules.models.reply_top import LoveDumpTable
from src.modules.models.user import User
from src.utils.cache import cache
from src.utils.handlers_helpers import only_users_from_main_chat
from src.utils.logger import logger
from src.utils.time_helpers import get_current_monday





def startup_time(bot: telegram.Bot, update: telegram.Update) -> None:
    uid = update.message.chat_id
    logger.info(f'id {uid} /startup_time')
    cached = cache.get('bot_startup_time')
    if cached:
        bot.send_message(uid, cached.strftime('%Y-%m-%d %H:%M'))
        return
    bot.send_message(uid, 'В кеше ничего нет (но должно быть)')


def users_clear_cache(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Если через бд изменили пол - нужно обновить в кеше эти сведения
    """
    uid = update.message.chat_id
    logger.info(f'id {uid} /users_clear_cache')
    User.clear_cache()
    bot.send_message(uid, '<b>User</b> кеш очищен', parse_mode=telegram.ParseMode.HTML)


@run_async
def huyamda(bot: telegram.Bot, update: telegram.Update) -> None:
    message = update.edited_message if update.edited_message else update.message
    send_huificator(bot, message)


@only_users_from_main_chat
def mystat(bot: telegram.Bot, update: telegram.Update) -> None:
    uid = update.message.chat_id
    send_mystat(bot, update, send_to_cid=uid, find_in_cid=CONFIG.get('anon_chat_id'))


@only_users_from_main_chat
def whois(bot: telegram.Bot, update: telegram.Update) -> None:
    uid = update.message.chat_id
    send_whois(bot, update, send_to_cid=uid, find_in_cid=CONFIG.get('anon_chat_id'))


@only_users_from_main_chat
def mylove(bot: telegram.Bot, update: telegram.Update) -> None:
    uid = update.message.chat_id
    send_mylove(bot, update, send_to_cid=uid, find_in_cid=CONFIG.get('anon_chat_id'))


def rand(bot: telegram.Bot, update):
    message = update.edited_message if update.edited_message else update.message
    words = re.sub(r'[^\d.,]+', ' ', message.text).split()
    num = 42
    if len(words) == 1:
        try:
            num = random.randint(1, int(words[0]))
        except Exception:
            pass
    elif len(words) >= 2:
        try:
            num = random.randint(int(words[0]), int(words[1]))
        except Exception:
            pass
    return bot.send_message(message.chat_id, str(num))

@run_async
def lovedump(_: telegram.Bot, update: telegram.Update) -> None:
    message = update.message
    try:
        __, cid_str, date_str = message.text.split(' ')
        cid = int(cid_str)
        date = datetime.strptime(date_str.strip(), '%Y%m%d')
        LoveDumpTable.dump(cid, date)
        message.reply_text('Готово!')
    except Exception:
        message.reply_text('Неверный формат')

@only_users_from_main_chat
def anon(bot: telegram.Bot, update: telegram.Update) -> None:
    if not CONFIG.get('anon', False):
        return
    text = update.message.text
    if not text:
        return
    uid = update.message.from_user.id
    cid = CONFIG['anon_chat_id']

    text = re.sub(r"\s*/\w+", '', text)
    text = text.strip()
    if len(text) == 0:
        return
    logger.info(f'[anon] from {uid}. text: {text}')
    bot.send_message(cid, text, disable_web_page_preview=True)
