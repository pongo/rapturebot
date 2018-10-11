# coding=UTF-8
import random
import typing
from datetime import datetime, timedelta

import pytils
import telegram
from telegram import ParseMode, ChatAction
from telegram.ext import run_async

import emoji_fixed as emoji
import src.config as config
from src.config import CMDS
from src.handlers.topmat import send_topmat
from src.modules.models.igor_weekly import IgorWeekly
from src.modules.models.pidor_weekly import PidorWeekly
from src.modules.models.reply_top import ReplyTop, ReplyLove
from src.modules.models.user import User
from src.modules.models.user_stat import UserStat
from src.utils.cache import cache, MONTH, bot_id
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.handlers_helpers import is_command_enabled_for_chat, \
    get_command_name, check_admin
from src.utils.logger_helpers import get_logger
from src.utils.misc import get_int
from src.utils.telegram_helpers import dsp

logger = get_logger(__name__)


@run_async
@chat_guard
@collect_stats
@command_guard
def stats(bot, update):
    # Get stats for group
    msg_id = update.message.message_id
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не статистику', reply_to_message_id=msg_id)
        return
    bot.sendChatAction(chat_id, ChatAction.TYPING)
    command = get_command_name(update.message.text)
    send_stats(bot, chat_id, update.message.chat.title, command, update.message.date)


def send_stats(bot, chat_id, chat_title, command, date, tag_salo=False, mat=False):
    users_count_caption = ''
    top_chart_caption = ''
    percent_needed = False
    salo = False
    fullstat = True
    if command:
        if command == CMDS['admins']['all_stat']['name']:
            users_count_caption = 'Активных пидоров'
            top_chart_caption = 'Все пидоры'
        if command == CMDS['admins']['top_stat']['name']:
            users_count_caption = 'Активных пидоров'
            top_chart_caption = 'Топ пидоры'
            fullstat = False
            percent_needed = True
        if command == CMDS['admins']['silent_guys']['name']:
            users_count_caption = 'Стесняш'
            top_chart_caption = 'Топ молчуны'
            percent_needed = True
            salo = True
    info = UserStat.get_chat(chat_id, date=date, fullstat=fullstat, salo=salo, tag_salo=tag_salo,
                             mat=mat)
    percents = None
    if percent_needed:
        percents = info['percent']
    msg = UserStat.stat_format(chat_title,
                               info['msg_count'],
                               info['users_count'],
                               users_count_caption,
                               info['top_chart'],
                               top_chart_caption,
                               percents)
    bot.sendMessage(chat_id, msg, parse_mode=ParseMode.HTML)
    logger.info(f'Group {chat_id} requested stats')
    if salo:
        cache.set(f'weekgoal:{chat_id}:salo_uids', info['uids'][0:3], time=MONTH)
    elif fullstat:
        cache.set(f'weekgoal:{chat_id}:top_pidori_uids', info['uids'][0:3], time=MONTH)


def send_top_kroshka(bot, chat_id, monday):
    kroshka = UserStat.get_top_kroshka(chat_id, monday)
    if not kroshka:
        return
    cache.set(f'weekgoal:{chat_id}:kroshka_uid', kroshka.uid, time=MONTH)
    emoj = ''.join(random.sample(list(emoji.UNICODE_EMOJI), 5))
    she = 'Она' if kroshka.female else 'Он'
    msg = f'Замечательная крошка-картошка <a href="tg://user?id={kroshka.uid}">🥔</a> недели —\n\n<b>{kroshka.fullname}</b> ❤️❤️❤️\n\n{she} получает эти прекрасные эмодзи: {emoj}'
    try:
        bot.sendMessage(chat_id, msg, parse_mode=ParseMode.HTML)
    except Exception:
        msg = f'Замечательная крошка-картошка 🥔 недели —\n\n<b>{kroshka.fullname}</b> ❤️❤️❤️\n\n{she} получает эти прекрасные эмодзи: {emoj}'
        bot.sendMessage(chat_id, f'{msg}\n\n{kroshka.get_username_or_link()}',
                        parse_mode=ParseMode.HTML)


def send_alllove(bot, chat_id, prev_monday):
    alllove = ReplyLove.get_all_love(chat_id, date=prev_monday, header='Вся страсть за неделю')
    bot.send_message(chat_id, alllove, parse_mode=telegram.ParseMode.HTML)


def send_alllove_outbound(bot, chat_id, prev_monday):
    alllove = ReplyLove.get_all_love_outbound(chat_id, date=prev_monday,
                                              header='Вся исходящая страсть за неделю',
                                              no_love_show_only_count=True)
    bot.send_message(chat_id, alllove, parse_mode=telegram.ParseMode.HTML)


def send_replytop(bot, chat_id, prev_monday):
    stats = ReplyTop.get_stats(chat_id, prev_monday)
    msg = "<b>Кто кого реплаит</b>\n\n"

    def __get_user_fullname(uid):
        if uid == bot_id():
            return 'Бот 🤖'
        user = User.get(uid)
        fullname = uid if not user else user.fullname
        return fullname

    def __get_stat_part(header, stat, delimeter, plurals):
        result = header
        for i, stat in enumerate(stat, start=1):
            uid, count = stat
            comment = " {} {}".format(delimeter,
                                      pytils.numeral.get_plural(count, plurals)) if i == 1 else ''
            fullname = __get_user_fullname(uid)
            result += "{}. <b>{}</b>{}\n".format(count, fullname, comment)
        return result

    msg += __get_stat_part("Им все пишут:\n", stats['to'], '←',
                           'реплай получен, реплая получено, реплаев получено')

    msg += "\n"

    msg += __get_stat_part("Они всем пишут:\n", stats['from'], '→',
                           'реплай отправлен, реплая отправлено, реплаев отправлено')

    msg += "\n"
    msg += "Топ страсти ❤:\n"
    for i, stat in enumerate(stats['pair'], start=1):
        pair_key, count = stat
        uid1, uid2 = [get_int(uid) for uid in pair_key.split(',')]
        names = [__get_user_fullname(uid1), __get_user_fullname(uid2)]
        random.shuffle(names)
        msg += f"{count}. <b>{names[0]}</b> ⟷ <b>{names[1]}</b>\n"

    bot.sendMessage(chat_id, msg, parse_mode=ParseMode.HTML)


def send_pidorweekly(bot, chat_id, prev_monday):
    uid = PidorWeekly.get_top_pidor(chat_id, prev_monday)
    if not uid:
        return
    user = User.get(uid)
    if not user:
        logger.error(f'None user {uid}')
        return
    cache.set(f'weekgoal:{chat_id}:pidorweekly_uid', user.uid, time=MONTH)
    pidorom = 'пидоршей' if user.female else 'пидором'
    header = f"И {pidorom} недели становится... <a href='tg://user?id={user.uid}'>👯‍♂</a> \n\n"
    body = "🎉     <b>{}</b>    🎉\n\n".format(user.fullname)
    random_emoji = [':couple_with_heart_man_man:', ':eggplant:', ':eggplant:', ':rocket:',
                    ':volcano:']
    random.shuffle(random_emoji)
    body += "{} Ура!".format(emoji.emojize(''.join(random_emoji)))
    try:
        bot.sendMessage(chat_id, f'{header}{body}', parse_mode=ParseMode.HTML)
    except Exception:
        header = f"И {pidorom} недели становится... 👯‍♂ \n\n"
        bot.sendMessage(chat_id, f'{header}{body}\n\n{user.get_username_or_link()}',
                        parse_mode=ParseMode.HTML)


def send_igorweekly(bot: telegram.Bot, chat_id: int, prev_monday: datetime):
    uid = IgorWeekly.get_top_igor(chat_id, prev_monday)
    if not uid:
        return
    user = User.get(uid)
    if not user:
        logger.error(f'None user {uid}')
        return
    cache.set(f'weekgoal:{chat_id}:igorweekly_uid', user.uid, time=MONTH)
    igorem = 'игорессой' if user.female else 'игорем'
    header = f"И {igorem} недели становится... <a href='tg://user?id={user.uid}'>👯‍♂</a> \n\n"
    body = "🎉     <b>{}</b>    🎉\n\nУра!".format(user.fullname)
    try:
        bot.sendMessage(chat_id, f'{header}{body}', parse_mode=ParseMode.HTML)
    except Exception:
        header = f"И {igorem} недели становится... 👯‍♂ \n\n"
        bot.sendMessage(chat_id, f'{header}{body}\n\n{user.get_username_or_link()}',
                        parse_mode=ParseMode.HTML)


@run_async
def weekly_stats(bot: telegram.Bot, _) -> None:
    today = datetime.today()
    # эта штука запускается в понедельник ночью, поэтому мы откладываем неделю назад
    prev_monday = (today - timedelta(days=today.weekday() + 7)).replace(hour=0, minute=0, second=0,
                                                                        microsecond=0)
    for chat in config.get_config_chats():
        if not is_command_enabled_for_chat(chat.chat_id, 'weeklystat'):
            continue
        send_weekly_for_chat(bot, chat.chat_id, chat.disabled_commands, chat.enabled_commands,
                             prev_monday)


def send_weekly_for_chat(bot: telegram.Bot, chat_id: int, disabled_commands: typing.List[str],
                         enabled_commands: typing.List[str], prev_monday: datetime) -> None:
    dsp(send_stats, bot, chat_id, 'Стата за прошлую неделю',
        CMDS['admins']['all_stat']['name'], prev_monday)
    dsp(send_stats, bot, chat_id, 'Стата за прошлую неделю',
        CMDS['admins']['silent_guys']['name'], prev_monday, tag_salo=True)
    if 'weeklystat:top_kroshka' not in disabled_commands:
        dsp(send_top_kroshka, bot, chat_id, prev_monday)
    if 'weeklystat:pidorweekly' not in disabled_commands:
        dsp(send_pidorweekly, bot, chat_id, prev_monday)
    if 'weeklystat:igorweekly' in enabled_commands:
        dsp(send_igorweekly, bot, chat_id, prev_monday)
    dsp(send_replytop, bot, chat_id, prev_monday)
    dsp(send_alllove, bot, chat_id, prev_monday)
    dsp(send_alllove_outbound, bot, chat_id, prev_monday)
    dsp(send_topmat, bot, chat_id, chat_id, prev_monday)
