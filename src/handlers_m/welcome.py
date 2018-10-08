# coding=UTF-8
import logging

import telegram

from src.modules.models.user import User
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.handlers_helpers import is_cmd_delayed, is_command_enabled_for_chat, \
    check_admin, CommandConfig

logger = logging.getLogger(__name__)


@chat_guard
@collect_stats
@command_guard
def welcome(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    msg_id = update.message.message_id
    cmd_name = 'welcome'
    if not check_admin(bot, chat_id, user_id):
        if is_cmd_delayed(chat_id, cmd_name):
            return
        bot.send_message(chat_id, 'Только админы могут вызвать', reply_to_message_id=msg_id)
        return

    send_welcome(bot, chat_id, user_id, show_errors=True, msg_id=msg_id)


def send_welcome(bot: telegram.Bot, chat_id: int, user_id: int, show_errors: bool = False,
                 msg_id=None) -> None:
    cmd_name = 'welcome'
    if not is_command_enabled_for_chat(chat_id, cmd_name):
        return

    cmd_config = CommandConfig(chat_id, cmd_name)
    text = cmd_config.get('text')
    if not text:
        if show_errors:
            bot.send_message(chat_id, 'Приветственный текст еще не указан. Свяжись с разрабом бота',
                             reply_to_message_id=msg_id)
        return

    user = User.get(user_id)
    username = user.get_username_or_link()
    msg = text.replace('{username}', username)
    bot.send_message(chat_id, msg, parse_mode=telegram.ParseMode.HTML)
