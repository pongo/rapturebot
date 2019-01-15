from typing import Optional

import telegram
from telegram import ParseMode
from telegram.ext import run_async

from src.modules.models.user import User
from src.plugins.i_stat.banhammer import banhammer, BanStatus
from src.plugins.i_stat.db import RedisChatStatistician
from src.utils.callback_helpers import get_callback_data
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.handlers_helpers import check_admin

CACHE_PREFIX = 'i_stat'
MODULE_NAME = CACHE_PREFIX
callback_show = 'istat_show_click'


@run_async
@chat_guard
@collect_stats
@command_guard
def send_personal_stat_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    message: telegram.Message = update.message

    reply_to_msg = message.reply_to_message
    if reply_to_msg:
        user_id = reply_to_msg.from_user.id
    else:
        splitted = message.text.split()
        if len(splitted) == 2:
            user_id = User.get_id_by_name(splitted[1])
        else:
            user_id = message.from_user.id

    send_personal_stat(bot, message.chat_id, user_id, reply_to_message_id=message.message_id)


@run_async
@chat_guard
@collect_stats
@command_guard
def send_all_stat_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    message: telegram.Message = update.message
    chat_id = message.chat_id
    rs = RedisChatStatistician(chat_id)
    rs.load()
    text = rs.chat_statistician.show_chat_stat()
    bot.send_message(chat_id, text, parse_mode=ParseMode.HTML)


@run_async
@chat_guard
@collect_stats
@command_guard
def ban_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    message: telegram.Message = update.message
    chat_id = message.chat_id
    # splitted = message.text.split(' ')
    user_id = message.from_user.id
    msg_id = message.message_id

    if not check_admin(bot, chat_id, user_id):
        bot.send_message(chat_id, 'Хуй тебе, а не бан.', reply_to_message_id=msg_id)
        return

    splitted = message.text.split()
    if len(splitted) == 2:
        user_id = User.get_id_by_name(splitted[1])
    else:
        bot.send_message(chat_id, 'Укажи юзернейм, сестра', reply_to_message_id=msg_id)
        return

    ban(bot, chat_id, user_id, msg_id=msg_id)


def ban(bot: telegram.Bot, chat_id: int, user_id: int, msg_id: int) -> None:
    user = User.get(user_id)
    if not user:
        bot.send_message(chat_id, 'А кто это? Таких не знаю.', reply_to_message_id=msg_id)
        return

    status = banhammer(chat_id, user_id)
    if status == BanStatus.BANNED:
        msg = f'{user.get_username_or_link()} забанен в стате /i. \n\nЧтобы разбанить, вызови /iban еще раз.'
    else:
        msg = f'{user.get_username_or_link()} разбанен'
    bot.send_message(chat_id, msg, reply_to_message_id=msg_id, parse_mode=ParseMode.HTML)


def callback_handler(bot: telegram.Bot, _: telegram.Update,
                     query: telegram.CallbackQuery, data) -> None:
    if 'module' not in data or data['module'] != MODULE_NAME:
        return
    if data['value'] == callback_show:
        send_personal_stat(bot, query.message.chat_id, query.from_user.id)
        bot.answer_callback_query(query.id)
        return


def send_personal_stat(bot: telegram.Bot, chat_id: int, user_id: int,
                       reply_to_message_id: Optional[int] = None) -> None:
    user = User.get(user_id)
    if not user:
        bot.send_message(chat_id, 'А кто это? Таких не знаю.',
                         reply_to_message_id=reply_to_message_id)
        return

    show_data = extend_initial_data({'value': callback_show, 'chat_id': chat_id})
    buttons = [
        [('Показать мою стату', show_data)],
    ]
    reply_markup = get_reply_markup(buttons)

    rs = RedisChatStatistician(chat_id)
    rs.load()
    text = rs.chat_statistician.show_personal_stat(user_id)

    bot.send_message(chat_id, text,
                     reply_to_message_id=reply_to_message_id,
                     reply_markup=reply_markup,
                     parse_mode=ParseMode.HTML)


def extend_initial_data(data: dict) -> dict:
    initial = {"name": CACHE_PREFIX, "module": MODULE_NAME}
    result = {**initial, **data}
    return result


def get_reply_markup(buttons) -> Optional[telegram.InlineKeyboardMarkup]:
    """
    Инлайн-кнопки под сообщением
    """
    if not buttons:
        return None
    keyboard = []
    for line in buttons:
        keyboard.append([
            telegram.InlineKeyboardButton(
                button_title,
                callback_data=(get_callback_data(button_data)))
            for button_title, button_data in line
        ])
    return telegram.InlineKeyboardMarkup(keyboard)
