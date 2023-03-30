import random
from typing import Union, Optional

from src.config import CMDS, VALID_CMDS, CONFIG
from src.commands.khaleesi.khaleesi import Khaleesi
from src.utils.cache import cache, MONTH
from src.utils.logger_helpers import get_logger
from src.utils.telegram_helpers import get_chat_admins

logger = get_logger(__name__)


def is_command_enabled_for_chat(chat_id: Union[int, str], cmd_name: Optional[str],
                                default: Optional[bool] = None) -> bool:
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
    if default:
        return default
    return chat_options.get('all_cmd', False)


class CommandConfig:
    def __init__(self, chat_id: int, command_name: str) -> None:
        self.config = None
        try:
            self.config = CONFIG['chats'][str(chat_id)]['commands_config'][command_name]
        except Exception:
            return

    def get(self, key):
        if not self.config:
            return None
        return self.config.get(key, None)


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

    admins = get_chat_admins(bot, chat_id) or []
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
        return True
    return False


def send_chat_access_denied(bot, update) -> None:
    chat_id = update.message.chat_id

    # если чат есть в кеше, то значит мы уже писали в него приветствие
    # и теперь нам нужно заняться драконизацией
    key = f'chat_guard:{chat_id}'
    cached = cache.get(key)
    if cached:
        text = update.message.text
        if text is None:
            return
        # драконизируем 5% сообшений
        if random.randint(1, 100) > 5:
            return
        khaleesed = Khaleesi.khaleesi(text, last_sentense=True)
        try:
            bot.send_message(chat_id, '{} 🐉'.format(khaleesed),
                             reply_to_message_id=update.message.message_id)
        except Exception:
            pass
        return

    # новый неопознанный чат. пишем приветствие. плюс в логи инфу о чате
    logger.info(f'Chat {chat_id} not in config. Name: {update.message.chat.title}')
    try:
        admins = ', '.join((f'[{admin.user.id}] @{admin.user.username}' for admin in
                            bot.get_chat_administrators(update.message.chat_id)))
        logger.info(f'Chat {chat_id} admins: {admins}')
        bot.send_message(chat_id,
                         'Привет ребята 👋!\n\nВашего чата нет в конфиге, поэтому я могу лишь время от времени драконизировать🐉 ваши сообщения.\n\nСвяжитесь с моим админом, чтобы он добавил ваш чат в конфиг — тогда все функции будут доступны, а драконизация отключится.')
    except Exception:
        pass
    cache.set(key, True, time=MONTH)


def is_cmd_delayed(chat_id: int, cmd: str) -> bool:
    delayed_key = f'delayed:{cmd}:{chat_id}'
    delayed = cache.get(delayed_key)
    if delayed:
        return True
    cache.set(delayed_key, True, 5 * 60)  # 5 минут
    return False


def check_user_is_plohish(update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    cmd_name = get_command_name(update.message.text)
    disabled = cache.get(f'plohish_cmd:{chat_id}:{user_id}:{cmd_name}')
    if disabled:
        return True
    return False
