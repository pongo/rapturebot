# coding=UTF-8

import telegram

from src.modules.music import music, musicdel, musicadd
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard


@chat_guard
@collect_stats
@command_guard
def music_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    music(bot, update)


@chat_guard
@collect_stats
@command_guard
def musicadd_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    musicadd(bot, update)


@chat_guard
@collect_stats
@command_guard
def musicdel_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    musicdel(bot, update)
