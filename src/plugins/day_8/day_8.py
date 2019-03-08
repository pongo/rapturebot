import random
from datetime import datetime
from typing import List, Set

import telegram
from telegram.ext import run_async

from src.modules.dayof.helper import set_today_special
from src.modules.models.chat_user import ChatUser
from src.modules.models.user import User
from src.plugins.day_8.model import random_gift_text
from src.plugins.valentine_day.helpers.helpers import send_to_all_chats
from src.utils.cache import cache, FEW_DAYS
from src.utils.handlers_decorators import command_guard, collect_stats, chat_guard


def can_use(chat_id: int, from_uid: int) -> bool:
    key = f'8:{chat_id}:{from_uid}'
    count = cache.get(key, 0)
    if count < 4:
        cache.set(key, count + 1, time=FEW_DAYS)
        return True
    return False


def my_random_choice(gifts: List[str]) -> str:
    key = f'8:used'
    used: Set[str] = cache.get(key, set())
    gifts_set = set(gifts)
    non_used = gifts_set - used
    if len(non_used) == 0:
        return random.choice(gifts)
    gift = random.choice(list(non_used))
    used.add(gift)
    cache.set(key, used, time=FEW_DAYS)
    return gift


@run_async
@chat_guard
@collect_stats
@command_guard
def command_8(bot: telegram.Bot, update: telegram.Update) -> None:
    message: telegram.Message = update.message
    chat_id = message.chat_id
    from_uid = message.from_user.id

    if not can_use(chat_id, from_uid):
        return

    if not is_day_active():
        return

    all_uids = [chat_user.uid for chat_user in ChatUser.get_all(chat_id)]
    all_users = [User.get(uid) for uid in all_uids]
    males = [user.uid for user in all_users if not user.female]
    females = [user.uid for user in all_users if user.female]

    gifts = get_gifts()
    gift = my_random_choice(gifts)
    result = random_gift_text(from_uid, males, females, gift, random.choice)

    from_user = User.get(result.from_uid)
    to_user = User.get(result.to_uid)
    text = result.text \
        .replace('{from}', from_user.get_username_or_link()) \
        .replace('{to}', to_user.get_username_or_link())
    # reply_markup=get_reply_markup(answer.get_message_buttons()),
    bot.send_message(chat_id, text, parse_mode=telegram.ParseMode.HTML)


def get_gifts() -> List[str]:
    with open(r'8.txt', encoding='utf-8') as file:
        lines = file.readlines()
    stripped = (line.strip() for line in lines)
    result = [line for line in stripped if line]
    random.shuffle(result)
    return result


def send_announcement(bot: telegram.Bot) -> None:
    text = """
Хуёздравляйте хуюбимых хуенщин с 8 хуярта. Хуишите /8 — хуюдет хуюрприз!

<i>Хуёманда хуяботает хуёлько два хуяза</i>
        """.strip()
    send_to_all_chats(bot, '8announcement', lambda _: text)


def midnight8(bot: telegram.Bot) -> None:
    if is_day_active():
        set_today_special()
        send_announcement(bot)
        return


def is_day_active() -> bool:
    return datetime.today().strftime(
        "%m-%d") == '03-08'  # месяц-день. Первое января будет: 01-01
