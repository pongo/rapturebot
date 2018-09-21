# -*- coding: utf-8 -*-
import json
import logging
import os
import random
import re
import typing
from datetime import datetime, timedelta
from time import sleep

import apiai
import pytils
import requests
import telegram
from telegram import ParseMode, ChatAction, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import run_async

import emoji_fixed as emoji
import src.config as config
from src.config import CHATRULES, CMDS, VALID_CMDS, CONFIG
from src.handlers_m.khaleesi import check_base_khaleesi
from src.handlers_m.mat_notify import mat_notify
from src.handlers_m.topmat import send_topmat
from src.modules.bayanometer import Bayanometer
from src.modules.dayof.day_manager import DayOfManager
from src.modules.dayof.helper import is_today_special
from src.modules.khaleesi import Khaleesi
from src.modules.matshowtime import MatshowtimeHandlers
from src.modules.models.chat_user import ChatUser
from src.modules.models.leave_collector import LeaveCollector
from src.modules.models.pidor_weekly import PidorWeekly
from src.modules.models.reply_top import ReplyTop, ReplyLove
from src.modules.models.user import User
from src.modules.models.user_stat import UserStat
from src.modules.models.week_word import WeekWord
from src.modules.reduplicator import reduplicate
from src.modules.spoiler import SpoilerHandlers
from src.utils.cache import cache, TWO_DAYS, TWO_YEARS, USER_CACHE_EXPIRE, MONTH, DAY
from src.utils.handlers_helpers import is_cmd_delayed
from src.utils.misc import get_int
from src.utils.misc import weighted_choice
from src.utils.telegram_helpers import get_chat_admins, get_photo_url

logger = logging.getLogger(__name__)


class CommandConfig:
    def __init__(self, chat_id: int, command_name: str):
        self.config = None
        try:
            self.config = CONFIG['chats'][str(chat_id)]['commands_config'][command_name]
        except Exception:
            return

    def get(self, key):
        if not self.config:
            return None
        return self.config.get(key, None)


def get_current_monday_str():
    date = datetime.today()
    monday = date - timedelta(days=date.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y%m%d")


def is_valid_command(text):
    cmd = get_command_name(text)
    if cmd in VALID_CMDS:
        return cmd
    return None


def check_admin(bot, chat_id, user_id):
    """
    Проверяет, есть ли админские права.
    
    Идет два вида проверки:
    1. Проверяем айдишники в конфиге.
    2. Через апи проверяем есть ли админка у юзера.
    """
    if user_id in CONFIG['admins_ids']:
        return True

    admins = get_chat_admins(bot, chat_id)
    return any(user_id == admin.user.id for admin in admins)


def get_command_name(text):
    if text is None:
        return None
    lower = text.lower()
    if lower.startswith('/'):
        lower_cmd = lower[1:].split(' ')[0].split('@')[0]
        for cmd, values in CMDS['synonyms'].items():
            if lower_cmd in values:
                return cmd
        return lower_cmd
    else:
        if lower in CMDS['text_cmds']:
            return lower
    return None


def check_command_is_off(chat_id, cmd_name):
    """
    Проверяет, отключена ли эта команда в чате.
    """
    all_disabled = cache.get(f'all_cmd_disabled:{chat_id}')
    if all_disabled:
        return True

    disabled = cache.get(f'cmd_disabled:{chat_id}:{cmd_name}')
    if disabled:
        return disabled
    return False


def off_all_cmds(bot, update):
    """
    Отключает все команды в указанном чате.
    """
    chat_id = update.message.chat_id
    cache.set(f'all_cmd_disabled:{chat_id}', True, time=CONFIG['off_delay'])
    bot.sendMessage(chat_id, 'Все команды выключены на 5 минут.\nСтатистика собирается в школу.')


def check_user_is_plohish(update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    cmd_name = get_command_name(update.message.text)
    disabled = cache.get(f'plohish_cmd:{chat_id}:{user_id}:{cmd_name}')
    if disabled:
        return True
    return False


def is_command_enabled_for_chat(chat_id, cmd_name: typing.Union[str, None]) -> bool:
    if cmd_name is None:
        return True
    chat_id_str = str(chat_id)
    if chat_id_str not in CONFIG["chats"]:
        return False
    if "enabled_commands" in CONFIG["chats"][chat_id_str] and cmd_name in CONFIG["chats"][chat_id_str]["enabled_commands"]:
        return True
    if "disabled_commands" in CONFIG["chats"][chat_id_str] and cmd_name in CONFIG["chats"][chat_id_str]["disabled_commands"]:
        return False
    if "all_cmd" in CONFIG["chats"][chat_id_str] and CONFIG["chats"][chat_id_str]["all_cmd"]:
        return True
    return False


def collect_stats(f):
    def decorator(bot: telegram.Bot, update: telegram.Update):
        if update.message.from_user.is_bot:
            return
        User.add_user(update.message.from_user)
        UserStat.add(UserStat.parse_message_stat(update.message.from_user.id,
                                                 update.message.chat_id,
                                                 update.message,
                                                 update.message.parse_entities()))
        ReplyTop.parse_message(update.message)
        return f(bot, update)
    return decorator


def command_guard(f):
    def decorator(bot, update):
        chat_id = update.message.chat_id
        cmd_name = get_command_name(update.message.text)
        if not is_command_enabled_for_chat(chat_id, cmd_name):
            return
        if check_user_is_plohish(update):
            return
        if check_command_is_off(chat_id, cmd_name):
            return
        return f(bot, update)
    return decorator


def send_chat_access_denied(bot, update) -> None:
    chat_id = update.message.chat_id

    # если чат есть в кеше, то значит мы уже писали в него приветствие
    # и теперь нам нужно заняться драконизацией
    key = f'chat_guard:{chat_id}'
    cached = cache.get(key)
    if cached:
        text = update.message.text
        if text is None:
            return
        # драконизируем 5% сообшений
        if random.randint(1, 100) > 5:
            return
        khaleesed = Khaleesi.khaleesi(text, last_sentense=True)
        try:
            bot.send_message(chat_id, '{} 🐉'.format(khaleesed), reply_to_message_id=update.message.message_id)
        except Exception:
            pass
        return

    # новый неопознанный чат. пишем приветствие. плюс в логи инфу о чате
    logger.info(f'Chat {chat_id} not in config. Name: {update.message.chat.title}')
    try:
        admins = ', '.join((f'[{admin.user.id}] @{admin.user.username}' for admin in
                            bot.get_chat_administrators(update.message.chat_id)))
        logger.info(f'Chat {chat_id} admins: {admins}')
        bot.send_message(chat_id, 'Привет ребята 👋!\n\nВашего чата нет в конфиге, поэтому я могу лишь время от времени драконизировать🐉 ваши сообщения.\n\nСвяжитесь с моим админом, чтобы он добавил ваш чат в конфиг — тогда все функции будут доступны, а драконизация отключится.')
    except Exception:
        pass
    cache.set(key, True, time=MONTH)


def chat_guard(f):
    """
    Проверяет, разрешено боту работать в этом чате
    """
    def decorator(bot: telegram.Bot, update):
        chat_id_str = str(update.message.chat_id)
        if chat_id_str not in CONFIG["chats"]:
            send_chat_access_denied(bot, update)
            return
        if "disable_chat" in CONFIG["chats"][chat_id_str] and CONFIG["chats"][chat_id_str]["disable_chat"]:
            logger.info(f'Chat {chat_id_str} disabled in config. Name: {update.message.chat.title}')
            return
        return f(bot, update)
    return decorator


@chat_guard
@collect_stats
@command_guard
def off_cmd(bot, update):
    chat_id = update.message.chat_id
    text = update.message.text.split(' ')
    user_id = update.message.from_user.id
    msg_id = update.message.message_id

    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не команды выключать.', reply_to_message_id=msg_id)
        return

    if len(text) < 2:
        if update.message.reply_to_message is not None:
            text = update.message.reply_to_message.text.split(' ')
            bot_command = text[0]
        else:
            bot.sendMessage(chat_id, 'Ты забыл указать, что выключать, пидор.', reply_to_message_id=msg_id)
            return
    else:
        bot_command = text[1]

    if bot_command == 'all' or bot_command == '/all':
        off_all_cmds(bot, update)
        return

    cmd_name = is_valid_command(bot_command)
    if not cmd_name:
        bot.sendMessage(chat_id, f'Нет такой команды: {bot_command}.', reply_to_message_id=msg_id)
        return

    if check_command_is_off(chat_id, bot_command):
        bot.sendMessage(chat_id, f'Команда {bot_command} уже выключена. Ты тоже уймись.', reply_to_message_id=msg_id)
        return

    _off_cmd(bot, bot_command, chat_id, cmd_name)


def _off_cmd(bot, bot_command, chat_id, cmd_name):
    cache.set(f'cmd_disabled:{chat_id}:{cmd_name}', True, time=CONFIG['off_delay'])
    if cmd_name == 'off':
        bot.sendMessage(chat_id, f'Команда {bot_command} выключена на 5 минут. Запретим запрещать!')
    else:
        bot.sendMessage(chat_id, f'Команда {bot_command} выключена на 5 минут. Уймитесь.')


@chat_guard
@collect_stats
@command_guard
def on_cmd(bot, update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    msg_id = update.message.message_id
    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не команды включать', reply_to_message_id=msg_id)
        return

    text = update.message.text.split()
    if len(text) < 2:
        if update.message.reply_to_message is not None:
            text = update.message.reply_to_message.text.split(' ')
            bot_command = text[0]
        else:
            bot.sendMessage(chat_id, 'Ты забыл указать, что включать, пидор', reply_to_message_id=msg_id)
            return
    else:
        bot_command = text[1]

    if bot_command == 'all' or bot_command == '/all':
        cache.delete(f'all_cmd_disabled:{chat_id}')
        bot.sendMessage(chat_id, 'Все команды снова работают.')
        return
    if not is_valid_command(bot_command):
        bot.sendMessage(chat_id, f'Нет такой команды: {bot_command}', reply_to_message_id=msg_id)
        return
    if not check_command_is_off(chat_id, bot_command):
        bot.sendMessage(chat_id, f'Команда {bot_command} уже включена. Все хорошо.', reply_to_message_id=msg_id)
        return

    cmd_name = get_command_name(bot_command)
    cache.delete(f'cmd_disabled:{chat_id}:{cmd_name}')
    bot.sendMessage(chat_id, f'Команда {bot_command} снова работает. На твой страх и риск.', reply_to_message_id=msg_id)


@chat_guard
@collect_stats
@command_guard
def off_cmd_for_user(bot, update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    msg_id = update.message.message_id
    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не плохишам команды выключать.', reply_to_message_id=msg_id)
        return

    # вычисляем название команды
    cmd_name = None
    words = update.message.text.split()
    reply_to_msg = update.message.reply_to_message
    if len(words) < 2:
        if not reply_to_msg:
            bot.sendMessage(chat_id, 'Ты забыл указать команду.', reply_to_message_id=msg_id)
            return
        for entity, entity_text in reply_to_msg.parse_entities().items():
            if entity.type == 'bot_command':
                cmd_name = entity_text
                break
    else:
        cmd_name = words[1]

    valid_cmd_name = is_valid_command(cmd_name)
    if not valid_cmd_name:
        bot.sendMessage(chat_id, f'Нет такой команды: {cmd_name}.', reply_to_message_id=msg_id)
        return

    # вычисляем кому отключать
    if reply_to_msg:
        plohish_id = reply_to_msg.from_user.id
        plohish_name = '@' + reply_to_msg.from_user.username
    else:
        # если не указали кому, то отключаем для всех
        if len(words) < 3:
            off_cmd(bot, update)
            return
        plohish_name = words[2]
        plohish_id = User.get_id_by_name(plohish_name)
        if not plohish_id:
            bot.sendMessage(chat_id, f'Нет такого плохиша: {words[2]}', reply_to_message_id=msg_id)
            return

    plohish_cmd_cache_key = f'plohish_cmd:{chat_id}:{plohish_id}:{valid_cmd_name}'
    disabled = cache.get(plohish_cmd_cache_key)
    if disabled:
        bot.sendMessage(chat_id, f'Команда /{valid_cmd_name} у плохиша {plohish_name} уже не работает')
        return

    cache.set(plohish_cmd_cache_key, True, time=MONTH)
    if reply_to_msg:
        data = {"name": '/off', "bot_command": cmd_name, "plohish_id": plohish_id, "valid_cmd_name": valid_cmd_name}
        keyboard = [[InlineKeyboardButton("Отключить у всех", callback_data=(get_callback_data(data)))]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        bot.sendMessage(chat_id, f'Команда /{valid_cmd_name} у плохиша {plohish_name} теперь не работает.', reply_to_message_id=msg_id, reply_markup=reply_markup)
        return
    bot.sendMessage(chat_id, f'Команда /{valid_cmd_name} у плохиша {plohish_name} теперь не работает')


@chat_guard
@collect_stats
@command_guard
def on_cmd_for_user(bot, update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    msg_id = update.message.message_id
    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не плохишам команды включать.', reply_to_message_id=msg_id)
        return

    text = update.message.text.split()
    if len(text) < 2:
        if update.message.reply_to_message is None:
            bot.sendMessage(chat_id, 'Ты забыл указать команду.', reply_to_message_id=msg_id)
            return
        text = update.message.reply_to_message.text.split(' ')
        bot_command = text[0]
    else:
        bot_command = text[1]

    cmd_name = is_valid_command(bot_command)
    if not cmd_name:
        bot.sendMessage(chat_id, f'Нет такой команды: {bot_command}.', reply_to_message_id=msg_id)
        return

    reply_to_msg = update.message.reply_to_message
    if reply_to_msg:
        plohish_id = reply_to_msg.from_user.id
        plohish_name = '@' + reply_to_msg.from_user.username
    else:
        if len(text) < 3:
            on_cmd(bot, update)
            return
        plohish_name = text[2]
        plohish_id = User.get_id_by_name(plohish_name)
        if not plohish_id:
            bot.sendMessage(chat_id, f'Нет такого плохиша: {text[2]}', reply_to_message_id=msg_id)

    if check_command_is_off(chat_id, bot_command):
        bot.sendMessage(chat_id, f'Команда {cmd_name} отключена у всех, без исключений')
        return

    plohish_cmd_cache_key = f'plohish_cmd:{chat_id}:{plohish_id}:{cmd_name}'
    disabled = cache.get(plohish_cmd_cache_key)
    if not disabled:
        bot.sendMessage(chat_id, f'Команда {cmd_name} у плохиша {plohish_name} и так работает')
        return

    cache.delete(plohish_cmd_cache_key)
    bot.sendMessage(chat_id, f'Команда {cmd_name} у плохиша {plohish_name} теперь работает')


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


def send_welcome(bot: telegram.Bot, chat_id: int, user_id: int, show_errors: bool = False, msg_id=None) -> None:
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


@chat_guard
@collect_stats
@command_guard
@run_async
def huificator(bot, update):
    send_huificator(bot, update.message, limit_chars=1000)


def send_huificator(bot: telegram.Bot, message: telegram.Message, limit_chars: int = 0) -> None:
    def get_new_msg(words: typing.List[str]) -> str:
        new_msg = ''
        for word in words:
            new_msg += reduplicate(word)
            new_msg += ' '
        return new_msg

    result = check_base_khaleesi(bot, message, 'Хуй', 'Хуишком хуинное хуёобщение', limit_chars)
    if not result:
        return
    chat_id, text, reply_to_message_id = result
    new_msg = get_new_msg(text.split())
    bot.send_message(chat_id, new_msg, reply_to_message_id=reply_to_message_id)


@chat_guard
@collect_stats
@command_guard
def expert(bot, update):
    expert_uid = CONFIG.get('expert_uid', None)
    if expert_uid is None:
        return
    chat_id = update.message.chat_id
    rand_num = random.randrange(1, 10)
    name = User.get(expert_uid).username
    last_msg_id, _ = cache.get(get_last_word_cache_key(chat_id, expert_uid))
    expert_phrases = [
        'иди сюда!',
        'Срочно нужен эксперт!',
        'ты тут нужен!',
        'твое мнение по этому вопросу?',
    ]
    # TODO: рефакторинг. сразу проверять last_msg_id и избавиться от проверки name (ссылку можно делать по uid)
    if rand_num < 5:
        if name:
            bot.sendMessage(chat_id, f'@{name}, {random.choice(expert_phrases)}')
    else:
        if last_msg_id:
            bot.sendMessage(chat_id, f'{random.choice(expert_phrases)}', reply_to_message_id=last_msg_id)


@chat_guard
@collect_stats
@command_guard
def gdeleha(bot, update):
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    msg_id = update.message.message_id
    send_gdeleha(bot, chat_id, msg_id, user_id)


def send_gdeleha(bot, chat_id, msg_id, user_id):
    if user_id in CONFIG.get('leha_ids', []) or user_id in CONFIG.get('leha_anya', []):
        bot.sendMessage(chat_id, "Леха — это ты!", reply_to_message_id=msg_id)
        return
    bot.sendSticker(chat_id, random.choice([
        'BQADAgADXgIAAolibATmbw713OR4OAI',
        'BQADAgADYwIAAolibATGN2HOX9g1wgI',
        'BQADAgADZQIAAolibAS0oUsHQK3DeQI',
        'BQADAgADdAIAAolibATvy9YzL3EJ_AI',
        'BQADAgADcwIAAolibATLRcR2Y1U5LQI',
        'BQADAgADdgIAAolibAQD0bDVAip6bwI',
        'BQADAgADeAIAAolibAT4u54Y18S13gI',
        'BQADAgADfQIAAolibAQzRBdOwpQL_gI',
        'BQADAgADfgIAAolibASJFncLc9lxdgI',
        'BQADAgADfwIAAolibATLieQe0J2MxwI',
        'BQADAgADgAIAAolibATcQ-VMJoDQ-QI',
        'BQADAgADggIAAolibAR_Wqvo57gCPwI',
        'BQADAgADhAIAAolibATcTIr_YdowgwI',
        'BQADAgADiAIAAolibARZHNSejUISQAI',
        'BQADAgADigIAAolibAS_n7DVTejNhAI',
        'BQADAgADnQIAAolibAQE8V7GaofXLgI',
    ]))


@chat_guard
@collect_stats
@command_guard
def pidor(bot, update):
    chat_id = update.message.chat_id
    msg_id = update.message.message_id
    net_ty_stickers = [
        'BQADAgAD7QEAAln0dAABu8kix5NFssAC',
        'BQADAgAD7wEAAln0dAABUEAYCW4yCjcC',
    ]
    sticker_id = random.choice(net_ty_stickers)  # "net ty" stickers
    reply_to_msg = update.message.reply_to_message
    if reply_to_msg:
        msg_id = reply_to_msg.message_id
        sticker_id = "BQADAgAD6wEAAln0dAABZu9RDDDpx3YC"  # "ty pidor" sticker
    bot.sendSticker(chat_id, sticker_id, reply_to_message_id=msg_id)


@chat_guard
@collect_stats
@command_guard
def papa(bot, update):
    phrases = [
        'Кек в кукарек',
        'Че кого сучары?',
        'Ночь в ночь',
        'Обед в обед',
        'Я на даче',
        'Крыса',
    ]
    chat_id = update.message.chat_id
    bot.sendMessage(chat_id, random.choice(phrases))


@chat_guard
@collect_stats
@command_guard
def changelog(bot: telegram.Bot, update):
    text = CONFIG.get('changelog', '')
    if len(text) == 0:
        return
    chat_id = update.message.chat_id
    bot.send_message(chat_id, text, parse_mode=telegram.ParseMode.HTML, disable_web_page_preview=True)


@chat_guard
@collect_stats
@command_guard
def love(bot, update):
    chat_id = update.message.chat_id
    stickers = [
        'BQADBQADoQADq2Y0AdG-PWaBAtQJAg',
        'BQADBQADmQADq2Y0AVCj5lMjk3x1Ag',
        'BQADBQADmwADq2Y0AdL-nlAYDZxoAg',
        'BQADBQADnwADq2Y0ARG1h2XKDTfUAg',
        'BQADBQADtwADq2Y0AULrTZbfPNGSAg',
        'BQADBQADwwADq2Y0AYNaGBjXfCaHAg',
        'BQADBQADIwEAAqtmNAEbknbN74qTvAI',
    ]
    bot.sendSticker(chat_id, random.choice(stickers))


def send_whois(bot: telegram.Bot, update: telegram.Update, send_to_cid: int, find_in_cid: int) -> None:
    requestor_id = update.message.from_user.id
    msg_id = update.message.message_id
    text = update.message.text.split()
    reply_to_msg = update.message.reply_to_message
    bot.sendChatAction(send_to_cid, ChatAction.TYPING)
    if reply_to_msg:
        user_id = reply_to_msg.from_user.id
        username = '@' + reply_to_msg.from_user.username
    else:
        if len(text) < 2:
            bot.sendMessage(send_to_cid, 'Укажи имя, пидор.', reply_to_message_id=msg_id)
            return
        username = text[1]
        user_id = User.get_id_by_name(username)
        if not user_id:
            for entity, entity_text in update.message.parse_entities().items():
                if entity.type == 'text_mention':
                    user_id = entity.user.id
            if not user_id:
                bot.sendMessage(send_to_cid, f'Нет такого: {username}', reply_to_message_id=msg_id)
                return
    info = UserStat.get_user_position(user_id, find_in_cid, update.message.date)
    msg = UserStat.me_format_position(username, info['msg_count'], info['position'], user_id)
    msg_userstat = UserStat.me_format(update.message.date, user_id, find_in_cid)
    if msg_userstat != '':
        msg_userstat = f"\n\n{msg_userstat}"
    bot.sendMessage(send_to_cid, f'{msg}{msg_userstat}', reply_to_message_id=msg_id, parse_mode=ParseMode.HTML)
    logger.info(f'User {requestor_id} requested stats for user {user_id}')


@chat_guard
@collect_stats
@command_guard
def whois(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id
    send_whois(bot, update, send_to_cid=chat_id, find_in_cid=chat_id)


@chat_guard
@collect_stats
@command_guard
def rules(bot, update):
    chat_id = update.message.chat_id
    bot.sendMessage(chat_id, CHATRULES, parse_mode=ParseMode.HTML)


@chat_guard
@collect_stats
@command_guard
@run_async
def anketa(bot, update):
    chat_id = update.message.chat_id
    with open('anketa.txt', 'r', encoding="utf-8") as file:
        content = file.read()
    if update.message.reply_to_message is not None:
        bot.sendMessage(chat_id, content, reply_to_message_id=update.message.reply_to_message.message_id)
    else:
        bot.sendMessage(chat_id, content)


@chat_guard
@collect_stats
@command_guard
def putin(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id
    if update.message.reply_to_message is None:
        bot.sendMessage(chat_id, 'Кхе-кхе')
        return
    if update.message.reply_to_message.text.strip().endswith('?'):
        bot.sendMessage(chat_id, 'Она утонула', reply_to_message_id=update.message.reply_to_message.message_id)
        return
    bot.sendMessage(chat_id, 'Кто вам это сказал?', reply_to_message_id=update.message.reply_to_message.message_id)


@chat_guard
@collect_stats
@command_guard
def pomogite(bot, update):
    def __get_commands(chat_id, section_name):
        return [
            f"/{cmd['name']} — {cmd['description']}\n"
            for key, cmd in CMDS[section_name].items()
            if is_command_enabled_for_chat(chat_id, cmd['name'])
        ]
    
    chat_id = update.message.chat_id
    msg = "Общие:\n"
    commands = __get_commands(chat_id, 'common')
    msg += ''.join(sorted(commands))
    user_id = update.message.from_user.id
    if check_admin(bot, chat_id, user_id):
        msg += "\nАдминские:\n"
        commands = __get_commands(chat_id, 'admins')
        msg += ''.join(sorted(commands))
    bot.sendMessage(chat_id, msg)


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
    info = UserStat.get_chat(chat_id, date=date, fullstat=fullstat, salo=salo, tag_salo=tag_salo, mat=mat)
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


def send_top_kroshka(bot, chat_id, monday):
    kroshka = UserStat.get_top_kroshka(chat_id, monday)
    if not kroshka:
        return
    emoj = ''.join(random.sample(list(emoji.UNICODE_EMOJI), 5))
    she = 'Она' if kroshka.female else 'Он'
    msg = f'Замечательная крошка-картошка <a href="tg://user?id={kroshka.uid}">🥔</a> недели —\n\n<b>{kroshka.fullname}</b> ❤️❤️❤️\n\n{she} получает эти прекрасные эмодзи: {emoj}'
    try:
        bot.sendMessage(chat_id, msg, parse_mode=ParseMode.HTML)
    except Exception:
        msg = f'Замечательная крошка-картошка 🥔 недели —\n\n<b>{kroshka.fullname}</b> ❤️❤️❤️\n\n{she} получает эти прекрасные эмодзи: {emoj}'
        bot.sendMessage(chat_id, f'{msg}\n\n{kroshka.get_username_or_link()}', parse_mode=ParseMode.HTML)


def send_alllove(bot, chat_id, prev_monday):
    bot.send_message(chat_id, ReplyLove.get_all_love(chat_id, date=prev_monday, header='Вся страсть за неделю'), parse_mode=telegram.ParseMode.HTML)
    sleep(1)
    bot.send_message(chat_id, ReplyLove.get_all_love_outbound(chat_id, date=prev_monday, header='Вся исходящая страсть за неделю', no_love_show_only_count=True), parse_mode=telegram.ParseMode.HTML)


def send_replytop(bot, chat_id, prev_monday):
    stats = ReplyTop.get_stats(chat_id, prev_monday)
    msg = "<b>Кто кого реплаит</b>\n\n"

    def __get_user_fullname(uid):
        bot_id = cache.get('bot_id')
        if bot_id and uid == bot_id:
            return 'Бот 🤖'
        user = User.get(uid)
        fullname = uid if not user else user.fullname
        return fullname

    def __get_stat_part(header, stat, delimeter, plurals):
        result = header
        for i, stat in enumerate(stat, start=1):
            uid, count = stat
            comment = " {} {}".format(delimeter, pytils.numeral.get_plural(count, plurals)) if i == 1 else ''
            fullname = __get_user_fullname(uid)
            result += "{}. <b>{}</b>{}\n".format(count, fullname, comment)
        return result

    msg += __get_stat_part("Им все пишут:\n", stats['to'], '←', 'реплай получен, реплая получено, реплаев получено')

    msg += "\n"

    msg += __get_stat_part("Они всем пишут:\n", stats['from'], '→', 'реплай отправлен, реплая отправлено, реплаев отправлено')

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
    pidorom = 'пидоршей' if user.female else 'пидором'
    header = f"И {pidorom} недели становится... <a href='tg://user?id={user.uid}'>👯‍♂</a> \n\n"
    body = "🎉     <b>{}</b>    🎉\n\n".format(user.fullname)
    random_emoji = [':couple_with_heart_man_man:', ':eggplant:', ':eggplant:', ':rocket:', ':volcano:']
    random.shuffle(random_emoji)
    body += "{} Ура!".format(emoji.emojize(''.join(random_emoji)))
    try:
        bot.sendMessage(chat_id, f'{header}{body}', parse_mode=ParseMode.HTML)
    except Exception:
        header = f"И {pidorom} недели становится... 👯‍♂ \n\n"
        bot.sendMessage(chat_id, f'{header}{body}\n\n{user.get_username_or_link()}', parse_mode=ParseMode.HTML)


@run_async
def send_weekword(bot, chat_id, prev_monday):
    word = WeekWord.get_top_word(prev_monday, chat_id)
    if not word:
        return
    current_dir = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.dirname(current_dir + '/tmp/weekword/'), exist_ok=True)
    with open(current_dir + '/tmp/weekword/{date}_{chat_id}.json'.format(date=prev_monday.strftime("%Y%m%d"), chat_id=chat_id), 'w', encoding='utf-8') as f:
        f.write(json.dumps(word, ensure_ascii=False, indent=2))


def weekly_stats(bot, job):
    today = datetime.today()
    # эта штука запускается в понедельник ночью, поэтому мы откладываем неделю назад
    prev_monday = (today - timedelta(days=today.weekday() + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    for chat_id in CONFIG["weekly_stats_chats_ids"]:
        send_stats(bot, chat_id, 'Стата за прошлую неделю', CMDS['admins']['all_stat']['name'], prev_monday)
        send_stats(bot, chat_id, 'Стата за прошлую неделю', CMDS['admins']['silent_guys']['name'], prev_monday, tag_salo=True)
        send_top_kroshka(bot, chat_id, prev_monday)
        send_pidorweekly(bot, chat_id, prev_monday)
        send_replytop(bot, chat_id, prev_monday)
        send_alllove(bot, chat_id, prev_monday)
        send_topmat(bot, chat_id, chat_id, prev_monday)
        # send_weekword(bot, chat_id, prev_monday)


def daily_evening(bot, job):
    today = datetime.today()
    monday = (today - timedelta(days=today.weekday() + 0)).replace(hour=0, minute=0, second=0, microsecond=0)
    for chat_id in CONFIG["weekly_stats_chats_ids"]:
        # send_weekword(bot, chat_id, monday)
        pass


@chat_guard
@collect_stats
@command_guard
def mystat(bot, update):
    chat_id = update.message.chat_id
    send_mystat(bot, update, chat_id, chat_id)


def send_mystat(bot: telegram.Bot, update: telegram.Update, send_to_cid: int, find_in_cid: int) -> None:
    msg_id = update.message.message_id
    user_id = update.message.from_user.id
    username = update.message.from_user.username

    bot.sendChatAction(send_to_cid, ChatAction.TYPING)
    info = UserStat.get_user_position(user_id, find_in_cid, update.message.date)
    msg = UserStat.me_format_position(username, info['msg_count'], info['position'], user_id)

    msg_userstat = UserStat.me_format(update.message.date, user_id, find_in_cid)
    if msg_userstat != '':
        msg_userstat = f"\n\n{msg_userstat}"

    bot.sendMessage(send_to_cid, f'{msg}{msg_userstat}', reply_to_message_id=msg_id, parse_mode=ParseMode.HTML)
    logger.info(f'User {user_id} requested stats')


@chat_guard
@collect_stats
@command_guard
@run_async
def mylove(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id
    send_mylove(bot, update, chat_id, chat_id)


def send_mylove(bot: telegram.Bot, update: telegram.Update, send_to_cid: int, find_in_cid: int) -> None:
    def format_love(type: str, b: User) -> typing.Optional[str]:
        if not b:
            return None
        b_pair, b_inbound, b_outbound = ReplyTop.get_user_top_strast(find_in_cid, b.uid)

        mutual_sign = ' ❤'
        if type == 'pair' and b_pair:
            mutual = mutual_sign if b_pair.uid == user_id else ''
            return f'Парная: {ReplyLove.get_fullname_or_username(b)}{mutual}'
        if type == 'inbound' and b_inbound:
            mutual = mutual_sign if b_inbound and b_inbound.uid == user_id else ''
            return f'Входящая: {ReplyLove.get_fullname_or_username(b)}{mutual}'
        if type == 'outbound' and b_outbound:
            mutual = mutual_sign if b_outbound and b_outbound.uid == user_id else ''
            return f'Исходящая: {ReplyLove.get_fullname_or_username(b)}{mutual}'
        return None

    bot.sendChatAction(send_to_cid, ChatAction.TYPING)

    reply_to_msg = update.message.reply_to_message
    if reply_to_msg:
        user_id = reply_to_msg.from_user.id
    else:
        splitted = update.message.text.split()
        if len(splitted) == 2:
            user_id = User.get_id_by_name(splitted[1])
        else:
            user_id = update.message.from_user.id
    user = User.get(user_id)
    if not user:
        bot.send_message(send_to_cid, 'А кто это? Таких не знаю.', reply_to_message_id=update.message.message_id)
        return

    pair, inbound, outbound = ReplyTop.get_user_top_strast(find_in_cid, user_id)

    love_list = [s for s in (format_love('pair', pair), format_love('inbound', inbound), format_love('outbound', outbound)) if s]
    if len(love_list) == 0:
        result = '🤷‍♀️🤷‍♂️ А нет никакой страсти'
    else:
        result = '\n'.join(love_list)

    if user_id in CONFIG.get('replylove__dragon_lovers', []):
        result = '🐉'

    bot.send_message(send_to_cid, f'Страсть {user.get_username_or_link()}:\n\n{result}', reply_to_message_id=update.message.message_id, parse_mode=ParseMode.HTML)


@chat_guard
@collect_stats
@command_guard
@run_async
def alllove(bot: telegram.Bot, update: telegram.Update) -> None:
    chat_id = update.message.chat_id
    user_id = update.message.from_user.id
    if not check_admin(bot, chat_id, user_id):
        bot.sendMessage(chat_id, 'Хуй тебе, а не страсти смотреть.', reply_to_message_id=update.message.message_id)
        return
    bot.sendChatAction(chat_id, ChatAction.TYPING)
    bot.send_message(chat_id, ReplyLove.get_all_love(chat_id), parse_mode=telegram.ParseMode.HTML)


@chat_guard
@collect_stats
@command_guard
def leave(bot, update):
    chat_id = update.message.chat_id
    bot.sendChatAction(chat_id, ChatAction.TYPING)

    leaves = LeaveCollector.get_leaves(chat_id, 3)
    joins = LeaveCollector.get_joins(chat_id, 3)

    reply_markup = None
    result = ""
    if len(leaves) > 0:
        leaves_text = "\n".join(leaves)
        result = "Убыло за 3 дня:\n\n{}".format(leaves_text)
        data = {"name": 'last_word', "leaves_uid": LeaveCollector.get_leaves(chat_id, 3, return_id=True)}
        keyboard = [[InlineKeyboardButton("Показать последние слова (нажмите там Start)", callback_data=(get_callback_data(data)))]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    if len(joins) > 0:
        joins_text = "\n".join(joins)
        if not result:  # здесь это аналогично `if len(leaves) == 0:`
            result = "Прибыло за 3 дня:\n\n{}"
        else:
            result += "\n\nПрибыло:\n\n{}"
        result = result.format(joins_text)

    if not result:
        result = "За 3 дня ничего не произошло"

    bot.sendMessage(chat_id, result, parse_mode='HTML', reply_markup=reply_markup)


def get_base_name(key: str) -> typing.Optional[str]:
    cache_key = f'{key}:{datetime.today().strftime("%Y%m%d")}'
    name = cache.get(cache_key)
    if name:
        return name

    from collections import OrderedDict
    from collections import deque
    month = 30 * 24 * 60 * 60  # 30 дней

    # особые дни
    if key == 'orzik' and datetime.today().strftime("%m-%d") == '04-12':
        name = 'Гагарин'
        cache.set(cache_key, name, time=month)
        return name

    # получаем непустые имена без пробелов
    stripped_names = [x for x in (x.strip() for x in CONFIG.get(key, 'Никто').split(',')) if x]

    # удаляем дубликаты, сохраняя порядок имен
    uniq_names = list(OrderedDict((x, True) for x in stripped_names).keys())

    # мы отдельно храним последние выбранные имена, чтобы они не повторялись
    recent_names = cache.get(f'{key}_recent')
    if recent_names is None:
        recent_names = []
    half_len = round(len(uniq_names) / 2)
    deq = deque(maxlen=half_len)
    deq.extend(recent_names)

    # типа бесконечный цикл, в течение которого мы пытаемся выбрать случайное имя, которое еще не постили
    for i in range(1, 1000):
        name = random.choice(uniq_names)
        if name not in recent_names:
            deq.append(name)
            cache.set(f'{key}_recent', list(deq), time=month)
            cache.set(cache_key, name, time=month)
            return name
    return None


@chat_guard
@collect_stats
@command_guard
def orzik(bot, update):
    """
    Говорит случайное имя Озрика.

    Имена добавляйте в конец списка, через запятую, с большой буквы. Дубликаты он сам удалит.
    """
    chat_id = update.message.chat_id
    name = get_base_name('orzik')
    if name:
        return bot.send_message(chat_id, f"Сегодня ты: {name}")
    # уведомляем о баге
    bot.sendMessage(chat_id, 'Это баг, такого не должно быть')


@chat_guard
@collect_stats
@command_guard
def lord(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Для аляски. Аналог /orzik
    """
    chat_id = update.message.chat_id
    name = get_base_name('lord')
    if name:
        bot.send_message(chat_id, f"Сегодня ты: {name}")
        return
    # уведомляем о баге
    bot.sendMessage(chat_id, 'Это баг, такого не должно быть')


def orzik_correction(bot, update):
    chat_id = update.message.chat_id
    today = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y%m%d")
    delayed_key = f'orzik_correction:{today}:{chat_id}'
    delayed = cache.get(delayed_key)
    if delayed:
        return
    name = get_base_name('orzik')
    if name is None:
        return bot.sendMessage(chat_id, 'Баг: у orzik_correction возникли проблемы')

    # помимо имен бот еще иногда дает орзику указания ("НЕ постишь селфи")
    # затруднительно автоматически преобразовывать это к "сегодня он не постит селфи", да и не нужно.
    # зато нужно отличать имена от таких указаний и игнорировать их
    # обычно имена состоят из одного слова
    # но даже если имя из двух слов, то обычно оба слова начинаются с больших букв - это и проверяем
    if len(name.split(' ')) > 1 and not name.istitle():
        # если это не имя, то сегодняшний день пропускаем
        cache.set(delayed_key, True, time=(2 * 24 * 60 * 60))
        return

    cache.set(delayed_key, True, time=(4 * 60 * 60))  # и теперь ждем 4 часа
    bot.sendMessage(chat_id, f'Сегодня он {name}', reply_to_message_id=update.message.message_id)


def send_kek(bot: telegram.Bot, chat_id):
    stickerset = cache.get('kekopack_stickerset')
    if not stickerset:
        stickerset = bot.get_sticker_set('Kekopack')
        cache.set('kekopack_stickerset', stickerset, time=50)
    sticker = random.choice(stickerset.stickers)
    bot.send_sticker(chat_id, sticker)


@chat_guard
@collect_stats
@command_guard
def message_reactions(bot: telegram.Bot, update: telegram.Update):
    if len(update.message.photo) > 0:
        photo_reactions(bot, update)

    if update.message.sticker:
        cache_key = f'pipinder:monday_stickersets:{get_current_monday_str()}'
        monday_stickersets = cache.get(cache_key)
        if not monday_stickersets:
            monday_stickersets = set()
        monday_stickersets.add(update.message.sticker.set_name)
        cache.set(cache_key, monday_stickersets, time=USER_CACHE_EXPIRE)

    msg = update.message.text
    if msg is None:
        return

    chat_id = update.message.chat_id
    msg_lower = msg.lower()
    msg_id = update.message.message_id
    if msg_lower == 'сы':
        bot.sendSticker(chat_id, random.choice([
            'BQADAgADpAADbUmmAAGH7b4k7tGlngI',
            'BQADAgADoAADbUmmAAF4FOlT87nh6wI',
        ]))
        return
    if msg_lower == 'без':
        bot.sendSticker(chat_id, random.choice([
            'BQADAgADXgADRd4ECHiiriOI0A51Ag',
            'BQADAgADWgADRd4ECHfSw52J6tn5Ag',
            'BQADAgADXAADRd4ECC4HwcwErfUcAg',
            'BQADAgADzQADRd4ECNFByeY4RuioAg',
        ]))
        return
    if msg_lower == 'кек':
        send_kek(bot, chat_id)
        return
    if is_command_enabled_for_chat(chat_id, CMDS['common']['orzik']['name']) \
            and not check_command_is_off(chat_id, CMDS['common']['orzik']['name']) \
            and 'орзик' in msg_lower:
        orzik_correction(bot, update)
    if is_command_enabled_for_chat(chat_id, "ebalo_zavali") \
            and (re.search(r"утр[оаеи]\S*[^!?.]* добр[оыеиа]\S+|добр[оыеиа]\S+[^!?.]* утр[оаие]\S*", msg_lower, re.IGNORECASE) or
                 re.search(r"[чш]т?[аое]\s+((у вас тут)|(тут у вас))", msg_lower, re.IGNORECASE)):
        bot.send_message(chat_id, 'Да завали ты уже ебало своё блять чмо ты сраное', reply_to_message_id=msg_id)
        return
    if is_command_enabled_for_chat(chat_id, CMDS['common']['gdeleha']['name']) \
            and re.search(r"(где л[её]ха|л[её]ха где)[!?.]*\s*$", msg_lower, re.IGNORECASE | re.MULTILINE):
        user_id = update.message.from_user.id
        send_gdeleha(bot, chat_id, msg_id, user_id)
        return

    user_id = update.message.from_user.id

    # hardfix warning
    if len(msg.split()) > 0 and msg.split()[0] == '/kick':
        if check_admin(bot, chat_id, user_id):
            bot.sendMessage(chat_id, 'Ты и сам можешь.', reply_to_message_id=msg_id)
        else:
            bot.sendMessage(chat_id, 'Анус себе покикай.', reply_to_message_id=msg_id)
        return

    # TODO: get rid of separate /pidor command
    pidor_string = msg_lower.split()
    if 'пидор' in pidor_string or '/pidor' in pidor_string:
        pidor(bot, update)

    ducks_trigger(bot, chat_id, msg_lower)

    # если картинка вставлена урлом, то чтобы узнать об этом мы парсим entities сообщения
    entities = update.message.parse_entities()
    for entity, entity_text in entities.items():
        if entity.type == 'url':
            if re.search(r"\.(jpg|jpeg|png)$", entity_text, re.IGNORECASE):
                photo_reactions(bot, update, img_url=entity_text)
                break


def ducks_trigger(bot: telegram.Bot, chat_id: int, msg_lower: str) -> None:
    """
    Проверка на утко-триггер.

    Бот проверяет каждое сообщение и решает, триггерится он на него или нет. И если да, то
    через несколько часов бот постит сообщение со случайными знаками.

    Отложеннная реакция нужна, чтобы люди не понимали на что триггерится бот.
    """
    if config.re_ducks_trigger is None:
        return
    if chat_id != CONFIG.get('anon_chat_id'):
        return

    # проверяем каждое сообщение на триггер
    # и решаем через сколько часов бот должен запостить сообщение
    if config.re_ducks_trigger.search(msg_lower):
        cache.set('ducks:delayed', True, time=(random.randint(45, 300) * 60))
        cache.set('ducks:go', True, time=MONTH)
        return

    # теперь каждый раз, когда кто-то пишет сообщение, не связанное с триггером,
    # бот проверяет, не настало ли время реагировать.
    #
    # если `ducks:delayed` is None — значит пора отправлять.
    # при этом `ducks:go` используется как ограничитель, чтобы бот постил только один раз.
    if cache.get('ducks:delayed') is None and cache.get('ducks:go') is True:
        cache.delete('ducks:go')
        ducks = cache.get('ducks:count', 0) + 1
        cache.set('ducks:count', ducks, time=(random.randint(1, 7) * 24 * 60 * 60))
        sign = random.choice(CONFIG.get('ducks_trigger').get('variants', ['🦆']))
        bot.send_message(chat_id, sign * ducks)


@run_async
def photo_reactions(bot: telegram.Bot, update: telegram.Update, img_url=None):
    """
    Вычисляем объекты на фотке.

    Используется google vision api:
    * https://cloud.google.com/vision/
    * https://cloud.google.com/vision/docs/reference/libraries
    * https://googlecloudplatform.github.io/google-cloud-python/latest/vision/index.html
    """
    if config.google_vision_client is None:
        return

    chat_id = update.message.chat_id
    if not is_command_enabled_for_chat(chat_id, 'photo_reactions'):
        return

    key_media_group = f'media_group_reacted:{update.message.media_group_id}'
    if update.message.media_group_id and cache.get(key_media_group):
        return

    # если урл картинки не задан, то сами берем самую большую фотку из сообщения
    # гугл апи, почему-то, перестал принимать ссылки телеги, нам приходится самим загружать ему фото
    if img_url is None:
        from google.cloud.vision import types
        file = bot.get_file(update.message.photo[-1].file_id)
        content = bytes(file.download_as_bytearray())
        image = types.Image(content=content)
    # но если передана ссылка, то и гуглу отдаем только ссылку
    # чтобы не заниматься самим вопросом загрузки каких-то непонятных ссылок
    # а если гугл не сможет ее открыть -- ну не судьба
    else:
        image = {'source': {'image_uri': img_url}}

    # noinspection PyPackageRequirements
    from google.cloud import vision
    # обращаемся к апи детектирования объектов на фото
    try:
        logger.debug(f"[google vision] parse img {img_url}")
        client = config.google_vision_client
        response = client.annotate_image({
            'image': image,
            'features': [{'type': vision.enums.Feature.Type.LABEL_DETECTION, 'max_results': 30}],
        })
    except Exception as ex:
        logger.error(ex)
        return

    # если на фото кот
    cat = any(re.search(r"\bcats?\b", label.description, re.IGNORECASE) for label in response.label_annotations)
    if cat:
        logger.debug(f"[google vision] cat found")
        if update.message.media_group_id:
            if cache.get(key_media_group):
                return
            cache.set(key_media_group, True, time=TWO_DAYS)
        msg_id = update.message.message_id
        bot.sendMessage(chat_id, CONFIG.get("cat_tag", "Это же кошак 🐈"), reply_to_message_id=msg_id)
        return
    logger.debug(f"[google vision] cat not found")


def leave_check(bot: telegram.Bot, update: telegram.Update):
    message = update.message
    chat_id = message.chat_id
    from_user: telegram.User = message.from_user
    from_uid = from_user.id

    if not from_user.is_bot:        
        User.add_user(from_user)
        ChatUser.add(from_uid, chat_id)

    # убыло
    left_user = message.left_chat_member
    if left_user is not None and not left_user.is_bot:
        User.add_user(left_user)
        ChatUser.add(left_user.id, chat_id, left=True)
        if from_uid == left_user.id:  # сам ливнул
            LeaveCollector.add_left(left_user.id, chat_id, message.date, from_uid)
        else:
            LeaveCollector.add_kick(left_user.id, chat_id, message.date, from_uid)

    # прибыло
    new_users = message.new_chat_members
    if new_users is not None and len(new_users) > 0:
        for new_user in new_users:
            if new_user.is_bot:
                continue
            User.add_user(new_user)
            ChatUser.add(new_user.id, chat_id)
            if from_uid == new_user.id:  # вошел по инвайт-ссылке
                LeaveCollector.add_invite(new_user.id, chat_id, message.date, from_uid)
            else:
                LeaveCollector.add_join(new_user.id, chat_id, message.date, from_uid)
            send_welcome(bot, chat_id, new_user.id)

    # если ктоливнулыч что-то пишет, то запускаем сверку списков
    if 'ktolivnul' in CONFIG and from_uid == CONFIG['ktolivnul']:
        LeaveCollector.update_ktolivnul(chat_id)


@run_async
def last_word(bot: telegram.Bot, update: telegram.Update):
    message = update.message
    if message.left_chat_member is not None or (message.new_chat_members is not None and len(message.new_chat_members) > 0):
        return
    cache.set(get_last_word_cache_key(update.message.chat_id, update.message.from_user.id), (message.message_id, message.date), time=TWO_YEARS)


def get_last_word_cache_key(cid, uid) -> str:
    return f'last_word:{cid}:{uid}'


@run_async
def random_khaleesi(bot, update):
    text = update.message.text
    if text is None:
        return
    chat_id = update.message.chat_id
    if not is_command_enabled_for_chat(chat_id, CMDS['common']['khaleesi']['name']):
        return
    if Khaleesi.is_its_time_for_khaleesi(chat_id) and Khaleesi.is_good_for_khaleesi(text):
        khaleesed = Khaleesi.khaleesi(text, last_sentense=True)
        Khaleesi.increase_khaleesi_time(chat_id)
        bot.sendMessage(chat_id, '{} 🐉'.format(khaleesed), reply_to_message_id=update.message.message_id)


@run_async
def ai(bot: telegram.Bot, update: telegram.Update):
    if 'dialogflow_api_token' not in CONFIG:
        return
    text = update.message.text
    if text is None:
        return
    chat_id = update.message.chat_id
    msg_id = update.message.message_id
    session_id = cache.get(f'ai:session_id:{chat_id}')
    if not session_id:
        session_id = msg_id
    cache.set(f'ai:session_id:{chat_id}', session_id, time=15 * 60)

    request = apiai.ApiAI(CONFIG['dialogflow_api_token']).text_request()
    request.lang = 'ru'  # На каком языке будет послан запрос
    request.session_id = str(session_id)  # ID Сессии диалога (нужно, чтобы потом учить бота)
    request.query = text

    response_json = json.loads(request.getresponse().read().decode('utf-8'))
    response = response_json['result']['fulfillment']['speech']  # Разбираем JSON и вытаскиваем ответ
    response_text = response if response else 'Я вас не поняль'
    response_msg = bot.send_message(chat_id, f'{response_text} 🤖')


@chat_guard
def message(bot, update):
    leave_check(bot, update)
    Bayanometer.check(bot, update)
    message_reactions(bot, update)
    PidorWeekly.parse_message(update.message)
    last_word(bot, update)
    # WeekWord.add(update.message.text, update.message.chat_id)
    random_khaleesi(bot, update)
    mat_notify(bot, update)
    tema_warning(bot, update)


def tema_warning(bot: telegram.Bot, update: telegram.Update):
    tema_uid = CONFIG.get('tema_uid', None)
    if tema_uid is None:
        return
    if tema_uid != update.message.from_user.id:
        return
    if update.message.text is None:
        return

    delayed = cache.get('tema_warning:delayed')
    if delayed:
        return
    cache.set('tema_warning:delayed', True, time=(2 * 60 * 60))  # 2 часа

    try:
        import requests
        anekdot = requests.get(CONFIG['anecdotica_url']).text
        msg = f'Тёма, ты такой юморист. Вот тебе анекдот:\n\n{anekdot}'
    except Exception:
        msg = random.choice(['Это Тема пишет', 'Тем, ну хватит', 'Тема, шутка зашла слишком далеко', 'Тёма, ты чего такой грустный?', 'Очень смешно, Артем', 'Тём, ну перестань'])

    bot.send_message(update.message.chat_id, msg, reply_to_message_id=update.message.message_id)


def private(bot: telegram.Bot, update: telegram.Update):
    DayOfManager.private_handler(bot, update)
    if is_today_special():
        return
    ai(bot, update)


def private_help(bot: telegram.Bot, update: telegram.Update):
    DayOfManager.private_help_handler(bot, update)


def __private(bot: telegram.Bot, update: telegram.Update):
    # logger.info('Anon message from {}'.format(update.message.from_user.name))
    message = update.edited_message if update.edited_message else update.message

    # key = 'anonlimit_{}'.format(message.from_user.id)
    # cached = cache.get(key)
    # if cached:
    #     bot.sendMessage(message.chat_id, 'Попробуй после {}'.format(cached.strftime("%H:%M")))
    #     return
    #
    # limit_seconds = 5 * 60
    # release_time = datetime.now() + timedelta(seconds=limit_seconds, minutes=1)
    # cache.set(key, release_time, time=limit_seconds)

    text = message.text
    if text:
        # пустые сообщения игнорируем
        prepared_text = text.strip()
        if len(prepared_text) == 0:
            return

        # в анонимках можно указывать никнейм.
        # --в конце сообщения отдельной строкой должно быть указано: `nickname (c)`--
        # в начале сообщения отдельной строкой должно быть указано: `Леха пишет:`

        # re_nicknamed = r"\n\s*(.+)\s* (?:\([cс]\)|©)\s*$"
        re_nicknamed = r"^\s*(.+)\s* пишет:\n"
        match = re.search(re_nicknamed, prepared_text, re.IGNORECASE)
        # если указан
        if match:
            name = match.group(1).strip()
            # нам нужно вырезать строку указания никнейма из текста
            prepared_text = re.sub(re_nicknamed, "", prepared_text, 0, re.IGNORECASE)
            prepared_text = prepared_text.strip()
            if len(prepared_text) == 0:
                return
        # если не указан, то генерируем случайный никнейм с заданными шансами
        else:
            name = weighted_choice([
                ('Аноним', 40),
                ('Анонимка', 40),
                ('Дикая антилопа', 20),
            ])

        WeekWord.add(prepared_text, CONFIG['anon_chat_id'])

        # начинаем предложения с больших букв
        # для этого мы делаем запрос к апи
        response = requests.post(
            'https://languagetool.org/api/v2/check',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            },
            data={
                'text': prepared_text,
                'language': 'ru-RU',
                'enabledRules': 'UPPERCASE_SENTENCE_START,Cap_Letters_Name',
                'enabledOnly': 'true'
            }
        )
        if response.status_code == 200:
            json_result = response.json()
            if 'matches' in json_result:
                for m in reversed(json_result['matches']):
                    replacement = m['replacements'][0]['value']
                    prepared_text = '{}{}{}'.format(
                        prepared_text[0:m['offset']],
                        replacement,
                        prepared_text[m['offset'] + len(replacement):],
                    )

        # типографируем текст
        response = requests.post("http://mdash.ru/api.v1.php", params={
            'text': prepared_text,
            'OptAlign.all': 'off',
            'Etc.unicode_convert': 'on',
            'Text.paragraphs': 'off',
            'Text.auto_links': 'off',
            'Text.email': 'off',
            'Text.breakline': 'off',
            'Punctmark.dot_on_end': 'on',
        })
        if response.status_code == 200:
            prepared_text = response.json()['result']

        # if re.search(r""".*([^-!$%^&*()_+|~=`{}\[\]:";'<>?,.\/]\s*)$""", prepared_text, re.IGNORECASE):
        #     prepared_text = '{}.'.format(prepared_text)

        msg = '<b>{}</b> пишет:\n\n{}'.format(name, prepared_text)
        bot.sendMessage(CONFIG['anon_chat_id'], msg, parse_mode=ParseMode.HTML)
        return

    if message.sticker:
        bot.sendSticker(CONFIG['anon_chat_id'], message.sticker)
        return

    if len(message.photo) > 0:
        caption = message.caption if message.caption else ''
        bot.sendPhoto(CONFIG['anon_chat_id'], message.photo[-1], caption)
        return

    if message.voice is not None:
        bot.sendVoice(CONFIG['anon_chat_id'], message.voice)
        return

    if message.document is not None:
        bot.sendDocument(CONFIG['anon_chat_id'], message.document)


def remove_inline_keyboard(bot, chat_id, message_id):
    reply_markup = InlineKeyboardMarkup([])
    bot.editMessageReplyMarkup(chat_id, message_id, reply_markup=reply_markup)


def get_callback_data(data):
    import uuid
    key = str(uuid.uuid4())
    cache.set(f'callback:{key}', data, USER_CACHE_EXPIRE)
    return key


def callback_off(bot, update, query, data):
    chat_id = query.message.chat_id
    user_id = query.from_user.id
    if not check_admin(bot, chat_id, user_id):
        return
    bot_command = data['bot_command']
    cmd_name = is_valid_command(bot_command)
    if cmd_name:
        remove_inline_keyboard(bot, chat_id, query.message.message_id)
        if check_command_is_off(chat_id, bot_command):
            bot.sendMessage(chat_id, f'Команда {bot_command} уже выключена. Ты тоже уймись.')
            return
        _off_cmd(bot, bot_command, chat_id, cmd_name)


def callback_last_word(bot, update, query, data):
    uid = query.from_user.id
    cid = query.message.chat_id
    msg_ids = [result[0] for result in (cache.get(get_last_word_cache_key(cid, _uid)) for _uid in data['leaves_uid']) if result is not None and isinstance(result, tuple)]
    if len(msg_ids) == 0:
        try:
            bot.sendMessage(uid, 'Увы, у меня не сохранились последние слова этих человеков 😢')
        except Exception:
            pass
        return

    try:
        bot.sendMessage(uid, 'Последние слова убывших:')
    except Exception:
        pass
    for msg_id in msg_ids:
        try:
            bot.forwardMessage(uid, cid, message_id=msg_id)
        except Exception:
            pass


def callback_handler(bot, update):
    query = update.callback_query
    data = cache.get(f'callback:{query.data}')
    if not data:
        return
    if data['name'] == '/off':
        bot.answerCallbackQuery(query.id)
        return callback_off(bot, update, query, data)
    if data['name'] == 'last_word':
        bot.answerCallbackQuery(query.id, url=f"t.me/{bot.username}?start={query.data}")
        return callback_last_word(bot, update, query, data)
    # if data['name'] == '/private_valya':
    #     return callback_private_valya(bot, update, query, data)
    if data['name'] == 'dayof':
        return DayOfManager.callback_handler(bot, update, query, data)
    if data['name'] == 'bayanometer_show_orig':
        return Bayanometer.callback_handler(bot, update, query, data)
    if data['name'] == 'spoiler':
        return SpoilerHandlers.callback_handler(bot, update, query, data)
    if data['name'] == 'matshowtime':
        return MatshowtimeHandlers.callback_handler(bot, update, query, data)


# def update_to_supergroup(bot, update):
#    old_id = update.message.migrate_from_chat_id
#    new_id = update.message.chat_id
#    user_id = update.message.from_user.id
# 
#    if old_id:
#        UserStat.update(user_id, old_id, {'cid': new_id})
#        Entity.update_all(old_id, {'cid': new_id})
#        Chat.update(old_id, {'cid': new_id})
# 
#        # Update all rows in chat_stats
#        for c in db.query(ChatStat)\
#                .filter(ChatStat.cid == old_id)\
#                .all():
#            c.cid = new_id
#        db.commit()
# 
#        bot.sendMessage(new_id, 'Group was updated to supergroup')
#        cache.delete('last_{}'.format(old_id))
#        logger.info('Group {} was updated to supergroup {}'.format(old_id, new_id))
# 
# 
# def set_privacy(bot, update):
#    chat_id = update.message.chat_id
#    chat_type = update.message.chat.type
#    user_id = update.message.from_user.id
#    msg_id = update.message.message_id
# 
#    user = User.get(user_id)
# 
#    if user:
#        privacy = user.public
# 
#        if privacy:
#            public = False
#            msg = 'Your statistics is *private*'
#        else:
#            public = True
#            msg = 'Your statistics is *public*\n\n' \
#                  '{0}/user/{1}'.format(CONFIG['site_url'], user_id)
# 
#        User.update(user_id, {'public': public})
#        cache.delete('user_{}'.format(user_id))
#    else:
#        msg = 'User not found'
# 
#    bot.sendMessage(chat_id, msg, parse_mode=ParseMode.MARKDOWN, reply_to_message_id=msg_id)
