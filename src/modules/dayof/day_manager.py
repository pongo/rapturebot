# coding=UTF-8

from datetime import datetime

import telegram
from telegram.ext import run_async

from src.config import CONFIG
from src.modules.dayof.fsb_day import FSBDay
from src.modules.dayof.valentine_day import ValentineDay


def new_year(bot: telegram.Bot):
    if datetime.today().strftime("%m-%d") != '01-01':
        return
    for chat_id_str, chat_options in CONFIG["chats"].items():
        chat_id = int(chat_id_str)
        bot.send_message(chat_id, 'https://www.youtube.com/watch?v=Tsbbi0V6l7s')


class DayOfManager:
    @staticmethod
    def midnight(bot: telegram.Bot) -> None:
        # здесь перечислены все модули - просто вызывается метод midnight в каждом
        # а там уж модуль сам разберется, должен ли он реагировать
        FSBDay.midnight(bot)
        ValentineDay.midnight(bot)
        new_year(bot)

    @staticmethod
    def afternoon(bot: telegram.Bot) -> None:
        ValentineDay.afternoon(bot)

    @staticmethod
    def callback_handler(bot, update, query, data) -> None:
        FSBDay.callback_handler(bot, update, query, data)
        ValentineDay.callback_handler(bot, update, query, data)

    @staticmethod
    def private_handler(bot: telegram.Bot, update: telegram.Update):
        FSBDay.private_handler(bot, update)
        ValentineDay.private_handler(bot, update)

    @staticmethod
    def private_help_handler(bot: telegram.Bot, update: telegram.Update):
        FSBDay.private_help_handler(bot, update)
        ValentineDay.private_help_handler(bot, update)

