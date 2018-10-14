# coding=UTF-8
from datetime import datetime

import telegram
from telegram.ext import run_async

from src.config import get_config_chats
from src.modules.dayof.day_manager import DayOfManager
from src.modules.models.leave_collector import LeaveCollector
from src.modules.models.reply_top import ReplyDumper
from src.modules.weather import send_alert_if_full_moon
from src.plugins.night_watch.night_watch_plugin import go_go_watchmen
from src.utils.cache import pure_cache, FEW_DAYS
from src.utils.handlers_helpers import is_command_enabled_for_chat
from src.utils.time_helpers import today_str


@run_async
def daily_midnight(bot: telegram.Bot, _):
    # особый режим сегодняшнего дня
    DayOfManager.midnight(bot)

    # для каждого чата
    for chat in get_config_chats():
        if 'daily_full_moon_check' in chat.enabled_commands:
            send_alert_if_full_moon(bot, chat.chat_id)

    for chat in get_config_chats():
        if is_command_enabled_for_chat(chat.chat_id, 'weeklystat'):
            ReplyDumper.dump(chat.chat_id)


@run_async
def daily_afternoon(bot: telegram.Bot, _):
    DayOfManager.afternoon(bot)


def every_hour(bot: telegram.Bot, _) -> None:
    go_go_watchmen(bot)
    LeaveCollector.check_left_users(bot)


def health_log(bot: telegram.Bot, _) -> None:
    now = datetime.now()
    try:
        me = bot.get_me()
        answer = f' @{me.username}'
    except Exception as e:
        answer = f' error: {e}'

    messages_metric = pure_cache.get(f"metrics:messages:{today_str()}", '0')
    value = f"{now.strftime('%H:%M')} - {messages_metric} - {answer}"
    pure_cache.append_list(f"health_log:{now.strftime('%Y%m%d')}", value, time=FEW_DAYS)
