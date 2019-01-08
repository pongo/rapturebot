# coding=UTF-8
from functools import wraps

import telegram

from src.config import CONFIG
from src.modules.models.chat_user import ChatUser
from src.modules.models.reply_top import ReplyTop
from src.modules.models.user import User
from src.modules.models.user_stat import UserStat
from src.plugins.i_stat.add_message_handler import IStatAddMessage
from src.utils.handlers_helpers import check_command_is_off, get_command_name, \
    send_chat_access_denied, is_command_enabled_for_chat, check_user_is_plohish


def only_users_from_main_chat(func):
    """
    Только для пользователей из основного чата, указанного в конфиге 'anon_chat_id'
    """

    @wraps(func)
    def decorator(bot: telegram.Bot, update: telegram.Update):
        message = update.edited_message if update.edited_message else update.message
        uid = message.from_user.id
        if not ChatUser.get(uid, CONFIG['anon_chat_id']):
            return
        return func(bot, update)

    return decorator


def chat_guard(func):
    """
    Разрешено ли боту работать в этом чате?
    """

    @wraps(func)
    def decorator(bot: telegram.Bot, update):
        chat_id_str = str(update.message.chat_id)
        if chat_id_str not in CONFIG["chats"]:
            send_chat_access_denied(bot, update)
            return
        return func(bot, update)

    return decorator


def command_guard(func):
    """
    Можно ли использовать эту команду?
    """

    @wraps(func)
    def decorator(bot, update):
        chat_id = update.message.chat_id
        cmd_name = get_command_name(update.message.text)
        if not is_command_enabled_for_chat(chat_id, cmd_name):
            return
        if check_user_is_plohish(update):
            return
        if check_command_is_off(chat_id, cmd_name):
            return
        return func(bot, update)

    return decorator


def collect_stats(func):
    """
    Сбор статистики сообщений
    """

    @wraps(func)
    def decorator(bot: telegram.Bot, update: telegram.Update):
        if update.message.from_user.is_bot:
            return
        User.add_user(update.message.from_user)
        UserStat.add(UserStat.parse_message_stat(update.message.from_user.id,
                                                 update.message.chat_id,
                                                 update.message,
                                                 update.message.parse_entities()))
        ReplyTop.parse_message(update.message)
        IStatAddMessage.add_message(update.message)
        return func(bot, update)

    return decorator
