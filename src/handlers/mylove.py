import typing

import telegram
from telegram import ParseMode, ChatAction
from telegram.ext import run_async

from src.config import CONFIG
from src.modules.models.reply_top import ReplyTop, ReplyLove
from src.modules.models.user import User
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard, \
    only_users_from_main_chat
from src.utils.handlers_helpers import check_admin
from src.utils.logger_helpers import get_logger

logger = get_logger(__name__)


@run_async
@chat_guard
@collect_stats
@command_guard
def mylove(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id
    send_mylove(bot, update, chat_id, chat_id)


def send_mylove(bot: telegram.Bot, update: telegram.Update, send_to_cid: int,
                find_in_cid: int) -> None:
    def format_love(type: str, b: User, female: bool) -> typing.Optional[str]:
        if not b:
            return None
        b_pair, b_inbound, b_outbound = ReplyTop.get_user_top_strast(find_in_cid, b.uid)

        mutual_sign = ' ❤'
        if type == 'pair' and b_pair:
            mutual = mutual_sign if b_pair.uid == user_id else ''
            return f'Взаимный пук: {ReplyLove.get_fullname_or_username(b)}{mutual}'
        if type == 'inbound' and b_inbound:
            mutual = mutual_sign if b_inbound and b_inbound.uid == user_id else ''
            fem = 'ее' if female else 'его'
            return f'В {fem} норку пукает: {ReplyLove.get_fullname_or_username(b)}{mutual}'
        if type == 'outbound' and b_outbound:
            mutual = mutual_sign if b_outbound and b_outbound.uid == user_id else ''
            return f'Обратный пук: {ReplyLove.get_fullname_or_username(b)}{mutual}'
        return None

    bot.sendChatAction(send_to_cid, ChatAction.TYPING)

    reply_to_msg = update.message.reply_to_message
    if reply_to_msg:
        user_id = reply_to_msg.from_user.id
    else:
        splitted = update.message.text.split()
        if len(splitted) == 2:
            user_id = User.get_id_by_name(splitted[1])
        else:
            user_id = update.message.from_user.id
    user = User.get(user_id)
    if not user:
        bot.send_message(send_to_cid, 'А кто это? Таких не знаю.',
                         reply_to_message_id=update.message.message_id)
        return

    pair, inbound, outbound = ReplyTop.get_user_top_strast(find_in_cid, user_id)

    formats = (format_love('pair', pair, user.female), format_love('inbound', inbound, user.female),
               format_love('outbound', outbound, user.female))
    love_list = [s for s in formats if s]
    if len(love_list) == 0:
        result = '🤷‍♀️🤷‍♂️ Мышь ебаная'
    else:
        result = '\n'.join(love_list)

    if user_id in CONFIG.get('replylove__dragon_lovers', []):
        result = '🐉'

    bot.send_message(send_to_cid, f'Норка {user.get_username_or_link()}:\n\n{result}',
                     reply_to_message_id=update.message.message_id, parse_mode=ParseMode.HTML)


@run_async
@chat_guard
@collect_stats
@command_guard
def alllove(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не страсти смотреть.',
                        reply_to_message_id=update.message.message_id)
        return
    bot.sendChatAction(chat_id, ChatAction.TYPING)
    bot.send_message(chat_id, ReplyLove.get_all_love(chat_id), parse_mode=telegram.ParseMode.HTML)


@only_users_from_main_chat
def private_mylove(bot: telegram.Bot, update: telegram.Update) -> None:
    uid = update.message.chat_id
    send_mylove(bot, update, send_to_cid=uid, find_in_cid=CONFIG.get('anon_chat_id'))
