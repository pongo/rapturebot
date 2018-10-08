# coding=UTF-8

import telegram

from src.config import CONFIG
from src.modules.ment import ment, MentConfig
from src.modules.models.chat_user import ChatUser
from src.modules.models.user import User
from src.utils.cache import cache
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard


@chat_guard
@collect_stats
@command_guard
def ment_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    if 'ment' not in CONFIG:
        return
    if update.message.chat_id != CONFIG.get('anon_chat_id'):
        return
    ment(bot, update, cache, User, ChatUser, MentConfig(CONFIG['ment']))
