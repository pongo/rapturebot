from datetime import datetime

import telegram

from src.config import get_config_chats
from src.dayof.fsb_day import FSBDay
from src.dayof.day_8.day_8 import midnight8
from src.dayof.valentine_day.valentine_day import ValentineDay as ValentineDay2
from src.utils.telegram_helpers import dsp


def new_year(bot: telegram.Bot):
    if datetime.today().strftime("%m-%d") != '01-01':
        return
    for chat in get_config_chats():
        dsp(_send_new_year, bot, chat.chat_id)


def _send_new_year(bot, chat_id):
    bot.send_message(chat_id, 'https://www.youtube.com/watch?v=Tsbbi0V6l7s')


class DayOfManager:
    @staticmethod
    def midnight(bot: telegram.Bot) -> None:
        # здесь перечислены все модули - просто вызывается метод midnight в каждом
        # а там уж модуль сам разберется, должен ли он реагировать
        FSBDay.midnight(bot)
        # ValentineDay.midnight(bot)
        ValentineDay2.midnight(bot)
        midnight8(bot)
        new_year(bot)

    @staticmethod
    def morning(bot: telegram.Bot) -> None:
        ValentineDay2.morning(bot)

    @staticmethod
    def afternoon(bot: telegram.Bot) -> None:
        # ValentineDay.afternoon(bot)
        pass

    @staticmethod
    def callback_handler(bot, update, query, data) -> None:
        FSBDay.callback_handler(bot, update, query, data)
        # ValentineDay.callback_handler(bot, update, query, data)
        ValentineDay2.callback_handler(bot, update, query, data)

    @staticmethod
    def private_handler(bot: telegram.Bot, update: telegram.Update):
        FSBDay.private_handler(bot, update)
        # ValentineDay.private_handler(bot, update)
        ValentineDay2.private_text_handler(bot, update)

    @staticmethod
    def private_help_handler(bot: telegram.Bot, update: telegram.Update):
        FSBDay.private_help_handler(bot, update)
        # ValentineDay.private_help_handler(bot, update)
        ValentineDay2.private_help_handler(bot, update)
