import random

import telegram
from telegram.ext import run_async

from src.utils.cache import pure_cache, TWO_DAYS
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.time_helpers import today_str


@run_async
@chat_guard
@collect_stats
@command_guard
def hakeem(bot: telegram.Bot, update: telegram.Update) -> None:
    message: telegram.Message = update.message
    user_id = message.from_user.id
    quote = get_hakeem_day(user_id)
    quote = f'Сегодня твой Хаким:\n\n{quote}'
    bot.send_message(message.chat_id, quote, reply_to_message_id=message.message_id, parse_mode=telegram.ParseMode.HTML)


def get_hakeem_day(user_id: int) -> str:
    today = today_str()
    key = f'hakeem:day:{today}:{user_id}'
    cached = pure_cache.get(key)
    if cached:
        return cached

    with open(r'quotes_h.txt', encoding='utf-8') as file:
        quotes = file.readlines()
    q = random.choice(quotes)
    q = q.replace('<br/>', '\n\n')

    pure_cache.set(key, q, time=TWO_DAYS)
    return q
