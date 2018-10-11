# coding=UTF-8

from telegram.ext import CommandHandler, MessageHandler, Filters, CallbackQueryHandler

from src.config import CMDS
from src.handlers import khaleesi, ask, pipinder, repinder, topmat
from src.handlers.callbacks import callback_handler
from src.handlers.ment_handler import ment_handler
from src.handlers.message import pidor, message
from src.handlers.music_handler import musicadd_handler, musicdel_handler, music_handler
from src.handlers.mylove import mylove, alllove, private_mylove
from src.handlers.mystat import mystat, whois, private_whois, private_mystat
from src.handlers.on_off import off_cmd, off_cmd_for_user, on_cmd, on_cmd_for_user
from src.handlers.orzik import orzik, lord
from src.handlers.other import rules, love, papa, pomogite, huificator, leave, expert, anketa, \
    putin, changelog, gdeleha
from src.handlers.weeklystat import stats
from src.handlers.welcome import welcome
from src.modules import private
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
    dp.add_handler(CommandHandler(CMDS['admins']['top_stat']['name'], stats, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['admins']['all_stat']['name'], stats, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['admins']['silent_guys']['name'], stats, filters=cmd_filter))
    dp.add_handler(
        CommandHandler(CMDS['admins']['disable_command']['name'], off_cmd, filters=cmd_filter))
    dp.add_handler(
        CommandHandler(CMDS['admins']['enable_command']['name'], on_cmd, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['admins']['disable_user']['name'], off_cmd_for_user,
                                  filters=cmd_filter))
    dp.add_handler(
        CommandHandler(CMDS['admins']['enable_user']['name'], on_cmd_for_user, filters=cmd_filter))
    dp.add_handler(CommandHandler('welcome', welcome, filters=cmd_filter))

    # common
    dp.add_handler(CommandHandler(CMDS['common']['self_stat']['name'], mystat, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['who_is']['name'], whois, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['rules']['name'], rules, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['gdeleha']['name'], gdeleha, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['saratov']['name'], pidor, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['zayac']['name'], love, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['london']['name'], papa, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['pomogite']['name'], pomogite, filters=cmd_filter))

    dp.add_handler(
        CommandHandler(CMDS['common']['hueplicator']['name'], huificator, filters=cmd_filter))
    dp.add_handler(CommandHandler('huyambda', huificator, filters=cmd_filter))
    dp.add_handler(CommandHandler('huyamba', huificator, filters=cmd_filter))

    dp.add_handler(
        CommandHandler(CMDS['common']['khaleesi']['name'], khaleesi.chat, filters=cmd_filter))
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
    dp.add_handler(CommandHandler(CMDS['common']['leave']['name'], leave, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['orzik']['name'], orzik, filters=cmd_filter))
    dp.add_handler(
        CommandHandler(CMDS['common']['pipinder']['name'], pipinder.pipinder, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['common']['ment']['name'], ment_handler, filters=cmd_filter))

    # hidden
    dp.add_handler(
        CommandHandler(CMDS['hidden']['repinder']['name'], repinder.repinder, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['hidden']['expert']['name'], expert, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['hidden']['anketa']['name'], anketa, filters=cmd_filter))
    dp.add_handler(CommandHandler(CMDS['hidden']['putin']['name'], putin, filters=cmd_filter))
    dp.add_handler(CommandHandler('changelog', changelog, filters=cmd_filter))
    dp.add_handler(CommandHandler('lord', lord, filters=cmd_filter))
    dp.add_handler(CommandHandler('ask', ask.chat, filters=cmd_filter))

    dp.add_handler(CommandHandler('mylove', mylove, filters=cmd_filter))
    dp.add_handler(CommandHandler('alove', alllove, filters=cmd_filter))
    dp.add_handler(CommandHandler('allove', alllove, filters=cmd_filter))
    dp.add_handler(CommandHandler('alllove', alllove, filters=cmd_filter))
    dp.add_handler(CommandHandler('allllove', alllove, filters=cmd_filter))
    dp.add_handler(CommandHandler('alllllove', alllove, filters=cmd_filter))

    dp.add_handler(
        CommandHandler(CMDS['common']['music']['name'], music_handler, filters=cmd_filter))
    dp.add_handler(CommandHandler('m', music_handler, filters=cmd_filter))
    dp.add_handler(
        CommandHandler(CMDS['hidden']['musicadd']['name'], musicadd_handler, filters=cmd_filter))
    dp.add_handler(
        CommandHandler(CMDS['hidden']['musicdel']['name'], musicdel_handler, filters=cmd_filter))

    # должно идти в конце
    dp.add_handler(MessageHandler(Filters.group & Filters.all, message))


def add_private_handlers(dp):
    """
    Регистрирует обработчики для лички
    """
    dp.add_handler(CommandHandler('help', private.help, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('startup_time', private.startup_time,
                                  filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('users_clear_cache', private.users_clear_cache,
                                  filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('user_clear_cache', private.users_clear_cache,
                                  filters=Filters.private & Filters.command))
    dp.add_handler(
        CommandHandler('khaleesi', khaleesi.private, filters=Filters.private & Filters.command,
                       allow_edited=True))
    dp.add_handler(
        CommandHandler('huyamda', private.huyamda, filters=Filters.private & Filters.command,
                       allow_edited=True))
    dp.add_handler(
        CommandHandler('mystat', private_mystat, filters=Filters.private & Filters.command))
    dp.add_handler(
        CommandHandler('whois', private_whois, filters=Filters.private & Filters.command))
    dp.add_handler(
        CommandHandler('mylove', private_mylove, filters=Filters.private & Filters.command))
    dp.add_handler(
        CommandHandler('random', private.rand, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('ask', ask.private, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('spoiler', SpoilerHandlers.private_handler,
                                  filters=Filters.private & Filters.command))
    dp.add_handler(
        CommandHandler('lovedump', private.lovedump, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('mats', MatshowtimeHandlers.cmd_mats,
                                  filters=Filters.private & Filters.command))
    dp.add_handler(
        CommandHandler('topmat', topmat.private_topmat, filters=Filters.private & Filters.command))
    dp.add_handler(CommandHandler('anon', private.anon, filters=Filters.private & Filters.command))

    # должно идти в конце
    private_filters = Filters.private & (
            Filters.text | Filters.sticker | Filters.photo | Filters.voice | Filters.document)
    dp.add_handler(MessageHandler(private_filters, private.private, edited_updates=True))


def add_other_handlers(dp):
    """
    Регистрирует прочие обработчики
    """
    dp.add_handler(CallbackQueryHandler(callback_handler))
