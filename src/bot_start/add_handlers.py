# coding=UTF-8

from telegram.ext import CommandHandler, MessageHandler, Filters, CallbackQueryHandler

import src.handlers as handlers
import src.modules.private as private
from src.config import CMDS
from src.handlers_m import khaleesi, ask, pipinder, repinder, topmat
from src.modules.matshowtime import MatshowtimeHandlers
from src.modules.spoiler import SpoilerHandlers
from src.modules.time import time_handler
from src.modules.weather import weather

cmd_filter = Filters.group

def add_chat_handlers(dp):
    """
    Регистрирует обработчики для чатов
    """
    # admins
    dp.add_handler(CommandHandler(CMDS['admins']['top_stat']['name'], handlers.stats, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['admins']['all_stat']['name'], handlers.stats, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['admins']['silent_guys']['name'], handlers.stats, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['admins']['disable_command']['name'], handlers.off_cmd, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['admins']['enable_command']['name'], handlers.on_cmd, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['admins']['disable_user']['name'], handlers.off_cmd_for_user, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['admins']['enable_user']['name'], handlers.on_cmd_for_user, filters=cmd_filter))
    dp.add_handler(CommandHandler('welcome', handlers.welcome, filters=cmd_filter))

    # common
    dp.add_handler(CommandHandler(CMDS['common']['self_stat']['name'], handlers.mystat, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['who_is']['name'], handlers.whois, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['rules']['name'], handlers.rules, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['gdeleha']['name'], handlers.gdeleha, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['saratov']['name'], handlers.pidor, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['zayac']['name'], handlers.love, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['london']['name'], handlers.papa, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['pomogite']['name'], handlers.pomogite, filters=cmd_filter))

    dp.add_handler(CommandHandler(CMDS['common']['hueplicator']['name'], handlers.huificator, filters=cmd_filter))
    dp.add_handler(CommandHandler('huyambda', handlers.huificator, filters=cmd_filter))
    dp.add_handler(CommandHandler('huyamba', handlers.huificator, filters=cmd_filter))

    dp.add_handler(CommandHandler(CMDS['common']['khaleesi']['name'], khaleesi.chat, filters=cmd_filter))
    dp.add_handler(CommandHandler('khaliisy', khaleesi.chat, filters=cmd_filter))
    dp.add_handler(CommandHandler('khalisy', khaleesi.chat, filters=cmd_filter))
    dp.add_handler(CommandHandler('khalisi', khaleesi.chat, filters=cmd_filter))
    dp.add_handler(CommandHandler('khaliisi', khaleesi.chat, filters=cmd_filter))
    dp.add_handler(CommandHandler('khalesi', khaleesi.chat, filters=cmd_filter))
    dp.add_handler(CommandHandler('khaleesy', khaleesi.chat, filters=cmd_filter))
    dp.add_handler(CommandHandler('khalesy', khaleesi.chat, filters=cmd_filter))

    dp.add_handler(CommandHandler(CMDS['common']['weather']['name'], weather, filters=cmd_filter))
    dp.add_handler(CommandHandler('p', weather, filters=cmd_filter))
    dp.add_handler(CommandHandler('w', weather, filters=cmd_filter))
    dp.add_handler(CommandHandler('pogoda', weather, filters=cmd_filter))

    dp.add_handler(CommandHandler(CMDS['common']['time']['name'], time_handler, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['leave']['name'], handlers.leave, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['orzik']['name'], handlers.orzik, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['pipinder']['name'], pipinder.pipinder, filters=cmd_filter))

    # hidden
    dp.add_handler(CommandHandler(CMDS['hidden']['repinder']['name'], repinder.repinder, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['hidden']['expert']['name'], handlers.expert, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['hidden']['anketa']['name'], handlers.anketa, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['hidden']['putin']['name'], handlers.putin, filters=cmd_filter))
    dp.add_handler(CommandHandler('changelog', handlers.changelog, filters=cmd_filter))
    dp.add_handler(CommandHandler('lord', handlers.lord, filters=cmd_filter))
    dp.add_handler(CommandHandler('ask', ask.chat, filters=cmd_filter))

    dp.add_handler(CommandHandler('mylove', handlers.mylove, filters=cmd_filter))
    dp.add_handler(CommandHandler('alove', handlers.alllove, filters=cmd_filter))
    dp.add_handler(CommandHandler('allove', handlers.alllove, filters=cmd_filter))
    dp.add_handler(CommandHandler('alllove', handlers.alllove, filters=cmd_filter))
    dp.add_handler(CommandHandler('allllove', handlers.alllove, filters=cmd_filter))
    dp.add_handler(CommandHandler('alllllove', handlers.alllove, filters=cmd_filter))

    # должно идти в конце
    dp.add_handler(MessageHandler(Filters.group & Filters.all, handlers.message))


def add_private_handlers(dp):
    """
    Регистрирует обработчики для лички
    """
    dp.add_handler(CommandHandler('help', handlers.private_help, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('startup_time', private.startup_time, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('users_clear_cache', private.users_clear_cache, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('user_clear_cache', private.users_clear_cache, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('khaleesi', khaleesi.private, filters=Filters.private & Filters.command, allow_edited=True))
    dp.add_handler(CommandHandler('huyamda', private.huyamda, filters=Filters.private & Filters.command, allow_edited=True))
    dp.add_handler(CommandHandler('mystat', private.mystat, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('whois', private.whois, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('mylove', private.mylove, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('random', private.rand, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('ask', ask.private, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('spoiler', SpoilerHandlers.private_handler, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('lovedump', private.lovedump, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('mats', MatshowtimeHandlers.cmd_mats, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('topmat', topmat.private_topmat, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('anon', private.anon, filters=Filters.private & Filters.command))

    # должно идти в конце
    dp.add_handler(MessageHandler(
        Filters.private & (Filters.text | Filters.sticker | Filters.photo | Filters.voice | Filters.document),
        handlers.private,
        edited_updates=True))


def add_other_handlers(dp):
    """
    Регистрирует прочие обработчики
    """
    dp.add_handler(CallbackQueryHandler(handlers.callback_handler))
