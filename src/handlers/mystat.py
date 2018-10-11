# coding=UTF-8

import telegram
from telegram import ParseMode, ChatAction
from telegram.ext import run_async

from src.config import CONFIG
from src.modules.models.user import User
from src.modules.models.user_stat import UserStat
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard, \
    only_users_from_main_chat
from src.utils.logger_helpers import get_logger

logger = get_logger(__name__)


def send_whois(bot: telegram.Bot, update: telegram.Update, send_to_cid: int,
               find_in_cid: int) -> None:
    requestor_id = update.message.from_user.id
    msg_id = update.message.message_id
    text = update.message.text.split()
    reply_to_msg = update.message.reply_to_message
    bot.sendChatAction(send_to_cid, ChatAction.TYPING)
    if reply_to_msg:
        user_id = reply_to_msg.from_user.id
        username = '@' + reply_to_msg.from_user.username
    else:
        if len(text) < 2:
            bot.sendMessage(send_to_cid, 'Укажи имя, пидор.', reply_to_message_id=msg_id)
            return
        username = text[1]
        user_id = User.get_id_by_name(username)
        if not user_id:
            for entity, entity_text in update.message.parse_entities().items():
                if entity.type == 'text_mention':
                    user_id = entity.user.id
            if not user_id:
                bot.sendMessage(send_to_cid, f'Нет такого: {username}', reply_to_message_id=msg_id)
                return
    info = UserStat.get_user_position(user_id, find_in_cid, update.message.date)
    msg = UserStat.me_format_position(username, info['msg_count'], info['position'], user_id)
    msg_userstat = UserStat.me_format(update.message.date, user_id, find_in_cid)
    if msg_userstat != '':
        msg_userstat = f"\n\n{msg_userstat}"
    bot.sendMessage(send_to_cid, f'{msg}{msg_userstat}', reply_to_message_id=msg_id,
                    parse_mode=ParseMode.HTML)
    logger.info(f'User {requestor_id} requested stats for user {user_id}')


@run_async
@chat_guard
@collect_stats
@command_guard
def whois(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id
    send_whois(bot, update, send_to_cid=chat_id, find_in_cid=chat_id)


@run_async
@chat_guard
@collect_stats
@command_guard
def mystat(bot, update):
    chat_id = update.message.chat_id
    send_mystat(bot, update, chat_id, chat_id)


def send_mystat(bot: telegram.Bot, update: telegram.Update, send_to_cid: int,
                find_in_cid: int) -> None:
    msg_id = update.message.message_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    bot.sendChatAction(send_to_cid, ChatAction.TYPING)
    info = UserStat.get_user_position(user_id, find_in_cid, update.message.date)
    msg = UserStat.me_format_position(username, info['msg_count'], info['position'], user_id)

    msg_userstat = UserStat.me_format(update.message.date, user_id, find_in_cid)
    if msg_userstat != '':
        msg_userstat = f"\n\n{msg_userstat}"

    bot.sendMessage(send_to_cid, f'{msg}{msg_userstat}', reply_to_message_id=msg_id,
                    parse_mode=ParseMode.HTML)
    logger.info(f'User {user_id} requested stats')


@only_users_from_main_chat
def private_mystat(bot: telegram.Bot, update: telegram.Update) -> None:
    uid = update.message.chat_id
    send_mystat(bot, update, send_to_cid=uid, find_in_cid=CONFIG.get('anon_chat_id'))


@only_users_from_main_chat
def private_whois(bot: telegram.Bot, update: telegram.Update) -> None:
    uid = update.message.chat_id
    send_whois(bot, update, send_to_cid=uid, find_in_cid=CONFIG.get('anon_chat_id'))
