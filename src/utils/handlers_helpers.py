# coding=UTF-8
from datetime import datetime, timedelta
from functools import wraps
from typing import Union, Optional

import telegram

from src.config import CMDS, VALID_CMDS, CONFIG
from src.modules.khaleesi import Khaleesi
from src.modules.models.chat_user import ChatUser
from src.modules.models.reply_top import ReplyTop
from src.modules.models.user import User
from src.modules.models.user_stat import UserStat
from src.utils.cache import cache, DAY
from src.utils.logger import logger
from src.utils.telegram_helpers import get_chat_admins


def is_command_enabled_for_chat(chat_id: Union[int, str], cmd_name: Optional[str]) -> bool:
    """
    Проверяет, включена ли команда в чате. Включая чаты с all_cmd=True.
    """
    if cmd_name is None:
        return True  # TODO: разобраться почему тут True
    chat_id_str = str(chat_id)
    if chat_id_str not in CONFIG['chats']:
        return False
    chat_options = CONFIG['chats'][chat_id_str]
    if cmd_name in chat_options.get('enabled_commands', []):
        return True
    if cmd_name in chat_options.get('disabled_commands', []):
        return False
    return chat_options.get('all_cmd', False)


class CommandConfig:
    def __init__(self, chat_id: int, command_name: str):
        self.config = None
        try:
            self.config = CONFIG['chats'][str(chat_id)]['commands_config'][command_name]
        except Exception:
            return

    def get(self, key):
        if not self.config:
            return None
        return self.config.get(key, None)


def get_current_monday_str():
    date = datetime.today()
    monday = date - timedelta(days=date.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y%m%d")


def is_valid_command(text):
    cmd = get_command_name(text)
    if cmd in VALID_CMDS:
        return cmd
    return None


def check_admin(bot, chat_id, user_id):
    """
    Проверяет, есть ли админские права.

    Идет два вида проверки:
    1. Проверяем айдишники в конфиге.
    2. Через апи проверяем есть ли админка у юзера.
    """
    if user_id in CONFIG['admins_ids']:
        return True

    admins = get_chat_admins(bot, chat_id)
    return any(user_id == admin.user.id for admin in admins)


def get_command_name(text):
    if text is None:
        return None
    lower = text.lower()
    if lower.startswith('/'):
        lower_cmd = lower[1:].split(' ')[0].split('@')[0]
        for cmd, values in CMDS['synonyms'].items():
            if lower_cmd in values:
                return cmd
        return lower_cmd
    else:
        if lower in CMDS['text_cmds']:
            return lower
    return None


def check_command_is_off(chat_id, cmd_name):
    """
    Проверяет, отключена ли эта команда в чате.
    """
    all_disabled = cache.get(f'all_cmd_disabled:{chat_id}')
    if all_disabled:
        return True

    disabled = cache.get(f'cmd_disabled:{chat_id}:{cmd_name}')
    if disabled:
        return disabled
    return False


def check_user_is_plohish(update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    cmd_name = get_command_name(update.message.text)
    disabled = cache.get(f'plohish_cmd:{chat_id}:{user_id}:{cmd_name}')
    if disabled:
        return True
    return False


def collect_stats(f):
    def decorator(bot: telegram.Bot, update: telegram.Update):
        if update.message.from_user.is_bot:
            return
        User.add_user(update.message.from_user)
        UserStat.add(UserStat.parse_message_stat(update.message.from_user.id,
                                                 update.message.chat_id,
                                                 update.message,
                                                 update.message.parse_entities()))
        ReplyTop.parse_message(update.message)
        return f(bot, update)

    return decorator


def command_guard(f):
    def decorator(bot, update):
        chat_id = update.message.chat_id
        cmd_name = get_command_name(update.message.text)
        if not is_command_enabled_for_chat(chat_id, cmd_name):
            return
        if check_user_is_plohish(update):
            return
        if check_command_is_off(chat_id, cmd_name):
            return
        return f(bot, update)

    return decorator


def send_chat_access_denied(bot, update) -> None:
    chat_id = update.message.chat_id
    key = f'chat_guard:{chat_id}'
    cached = cache.get(key)
    if cached:
        text = update.message.text
        if text is None:
            return
        khaleesed = Khaleesi.khaleesi(text, last_sentense=True)
        try:
            bot.send_message(chat_id, '{} 🐉'.format(khaleesed), reply_to_message_id=update.message.message_id)
        except Exception:
            pass
        return
    logger.info(f'Chat {chat_id} not in config. Name: {update.message.chat.title}')
    try:
        admins = ', '.join((f'[{admin.user.id}] @{admin.user.username}' for admin in
                            bot.get_chat_administrators(update.message.chat_id)))
        logger.info(f'Chat {chat_id} admins: {admins}')
    except Exception:
        pass
    cache.set(key, True, time=DAY)


def chat_guard(f):
    """
    Проверяет, разрешено боту работать в этом чате
    """

    def decorator(bot: telegram.Bot, update):
        chat_id_str = str(update.message.chat_id)
        if chat_id_str not in CONFIG["chats"]:
            send_chat_access_denied(bot, update)
            return
        if "disable_chat" in CONFIG["chats"][chat_id_str] and CONFIG["chats"][chat_id_str]["disable_chat"]:
            logger.info(f'Chat {chat_id_str} disabled in config. Name: {update.message.chat.title}')
            return
        return f(bot, update)

    return decorator


def is_cmd_delayed(chat_id: int, cmd: str) -> bool:
    delayed_key = f'delayed:{cmd}:{chat_id}'
    delayed = cache.get(delayed_key)
    if delayed:
        return True
    cache.set(delayed_key, True, 5 * 60)  # 5 минут
    return False

def only_users_from_main_chat(f):
    @wraps(f)
    def decorator(bot: telegram.Bot, update: telegram.Update):
        message = update.edited_message if update.edited_message else update.message
        uid = message.from_user.id
        if not ChatUser.get(uid, CONFIG['anon_chat_id']):
            return
        return f(bot, update)
    return decorator
