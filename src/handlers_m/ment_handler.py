# coding=UTF-8
import random
from typing import Optional, List

import telegram

from src.config import CONFIG
from src.modules.ment import ment, MentConfig
from src.modules.models.chat_user import ChatUser
from src.modules.models.user import User
from src.utils.cache import cache, FEW_DAYS, YEAR
from src.utils.handlers_helpers import chat_guard, collect_stats, command_guard
from src.utils.logger import logger
from src.utils.telegram_helpers import telegram_retry
from src.utils.time_helpers import today_str


@chat_guard
@collect_stats
@command_guard
def ment_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    if 'ment' not in CONFIG:
        return
    if update.message.chat_id != CONFIG.get('anon_chat_id'):
        return
    ment(bot, update, cache, User, ChatUser, MentConfig(CONFIG['ment']))
