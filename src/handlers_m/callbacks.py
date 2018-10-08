# coding=UTF-8
import logging

import telegram
from telegram.ext import run_async

from src.handlers_m.last_word import callback_last_word
from src.handlers_m.on_off import callback_off
from src.modules.bayanometer import Bayanometer
from src.modules.dayof.day_manager import DayOfManager
from src.modules.matshowtime import MatshowtimeHandlers
from src.modules.spoiler import SpoilerHandlers
from src.utils.cache import cache

logger = logging.getLogger(__name__)


@run_async
def callback_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    query = update.callback_query
    data = cache.get(f'callback:{query.data}')
    if not data:
        return
    if data['name'] == '/off':
        bot.answerCallbackQuery(query.id)
        callback_off(bot, update, query, data)
        return
    if data['name'] == 'last_word':
        bot.answerCallbackQuery(query.id, url=f"t.me/{bot.username}?start={query.data}")
        callback_last_word(bot, update, query, data)
        return
    if data['name'] == 'dayof':
        DayOfManager.callback_handler(bot, update, query, data)
        return
    if data['name'] == 'bayanometer_show_orig':
        Bayanometer.callback_handler(bot, update, query, data)
        return
    if data['name'] == 'spoiler':
        SpoilerHandlers.callback_handler(bot, update, query, data)
        return
    if data['name'] == 'matshowtime':
        MatshowtimeHandlers.callback_handler(bot, update, query, data)
        return
