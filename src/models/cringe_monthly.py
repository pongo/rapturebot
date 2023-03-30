import random
import re
from datetime import datetime, timedelta
from threading import Lock
from typing import List, Tuple, Optional

import telegram
from telegram.ext import run_async

from src.models.user import UserDB, User
from src.utils.cache import cache, MONTH, DAY, bot_id
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.logger_helpers import get_logger
from src.utils.telegram_helpers import send_long

logger = get_logger(__name__)
CRINGE_EXPIRE = MONTH + (DAY * 4)  # 34 days


class CringeMonthly:
    lock = Lock()
    re_words = re.compile(
        r"\b(обана|тарелочн\S+|набутылил\S*|тян\S*|баз.|базирован\S*|нн|моноколес\S*|топ\S*|10/10|10|сис.|сис.чк\S+|boobs|кун\S*|правач?к\S*|левач?к\S*|двач\S*|гигачад\S*|пяточк\S+|ножк\S+|русн\S+|википеди\S+|араб\S*|тренд\S*|[ао]ниме\S*|титечк\S+|жирух\S*|бабк\S+|лампов\S+|няш\S+|фемини\S+|радфем\S*|фемк\S+|трамп\S*|твит\S*|тиндер\S*|неадекватн\S+|пиксел\S*|айфон\S*|андроид\S*|кац\S*|газел\S*|светов\S*|либерах\S*|либертариан\S+|анкап\S*|донат\S*)\b",
        re.IGNORECASE)
    re_multi_words = re.compile(
        r"(хороши. русски.|генерал.? свр)",
        re.IGNORECASE)

    @classmethod
    def topcringe(cls, cid, date, sort_by_percent=False) -> List[Tuple[int, Tuple[int, int]]]:
        db = cls.__get_db(date, cid)
        cringe = {}
        for uid, user_stat in db.items():
            if user_stat['value'] == 0 or user_stat['all_messages_count'] == 0:
                continue
            if sort_by_percent and user_stat['all_messages_count'] < 30:
                continue
            cringe[uid] = (user_stat['value'], user_stat['value'] / user_stat['all_messages_count'])
        sort_index = 1 if sort_by_percent else 0
        return sorted(cringe.items(), key=lambda x: x[1][sort_index], reverse=True)

    @classmethod
    def get_toppest_cringe(cls, cid, date) -> Optional[int]:
        db = cls.__get_db(date, cid)
        # подсчитаем всех по отношению кринж-слов к общему количеству слов этого участника
        cringe_by_count = {}
        for uid, user_stat in db.items():
            # учитываем только тек, кто написал от 30 сообщений
            if user_stat['all_messages_count'] < 30:
                continue
            cringe_by_count[uid] = user_stat['value'] / user_stat['all_messages_count']

        if len(cringe_by_count) > 0:
            uid, _ = cls.__sort_dict(cringe_by_count)[0]
        elif len(db) == 0:
            return None
        else:
            uid = random.choice(list(db.keys()))
        return uid

    @classmethod
    @run_async
    def parse_message(cls, message: telegram.Message) -> None:
        msg = message.text
        if msg is None:
            return
        uid = message.from_user.id
        cid = message.chat_id
        today = datetime.today()

        if not cls.__has_cringe(msg):
            cls.__add(uid, cid, today, cringe=False)
            return
        cls.__add(uid, cid, today)

        if message.reply_to_message is not None:
            to_uid = message.reply_to_message.from_user.id
            cls.__add(to_uid, cid, today, replay=True)

        for entity, entity_text in message.parse_entities().items():
            if entity.type == 'mention':
                username = entity_text.lstrip('@').strip()
                try:
                    mentioned_user_uid = UserDB.get_uid_by_username(username)
                    if mentioned_user_uid:
                        cls.__add(mentioned_user_uid, cid, today, replay=True)
                except Exception:
                    pass
                continue
            if entity.type == 'text_mention':
                cls.__add(entity.user.id, cid, today, replay=True)
                continue

    @classmethod
    def __has_cringe(cls, msg: str) -> bool:
        msg_lower = msg.lower().replace('ё', 'е')
        if cls.re_words.search(msg_lower):
            return True
        if cls.re_multi_words.search(msg_lower):
            return True
        return False

    @classmethod
    def __add(cls, uid, cid, date, cringe=True, replay=False):
        logger.debug(f'[cringe] lock {cid}:{uid}')
        with cls.lock:
            db = cls.__get_db(date, cid)

            value = 0
            if cringe:
                value = 1
                if replay:
                    value = 0.4

            all_messages_count = 1
            if replay:
                all_messages_count = 0

            if uid in db:
                db[uid]['all_messages_count'] += all_messages_count
                db[uid]['value'] += value
            else:
                db[uid] = {
                    'all_messages_count': all_messages_count,
                    'value': value
                }

            cls.__set_db(db, date, cid)

    @staticmethod
    def __sort_dict(d):
        return sorted(d.items(), key=lambda x: x[1], reverse=True)

    @staticmethod
    def __get_cache_key(date, cid):
        return f'cringemonthly:{date.strftime("%Y%m")}:{cid}'

    @classmethod
    def __get_db(cls, date, cid):
        cached = cache.get(cls.__get_cache_key(date, cid))
        if cached:
            return cached
        return {}

    @classmethod
    def __set_db(cls, newdb, date, cid):
        cache.set(cls.__get_cache_key(date, cid), newdb, time=CRINGE_EXPIRE)


@run_async
@chat_guard
@collect_stats
@command_guard
def topcringe(bot: telegram.Bot, update: telegram.Update):
    chat_id = update.message.chat_id
    msg = __get_top_cringe_lines(chat_id)
    send_long(bot, chat_id, f"<b>Кринж месяца</b>\n\n{msg}")
    # send_monthly_cringe_for_chat(bot, chat_id)


def __get_top_cringe_lines(chat_id, date=None, show_percent=False) -> str:
    def __get_user_fullname(uid):
        if uid == bot_id():
            return 'Бот 🤖'
        user = User.get(uid)
        fullname = uid if not user else user.fullname
        return fullname

    date = datetime.today() if date is None else date
    msg = ""
    stats = CringeMonthly.topcringe(chat_id, date, sort_by_percent=show_percent)
    for i, (uid, (cringe_value, pr)) in enumerate(stats, start=1):
        cringe_formatted = f'{cringe_value:.1f}'
        fullname = __get_user_fullname(uid)
        if show_percent:
            msg += f"{i}. <b>{fullname}</b> ({cringe_formatted}, {round(pr * 100)}%)\n"
        else:
            msg += f"{i}. <b>{fullname}</b> ({cringe_formatted})\n"
    return msg


def send_monthly_cringe_for_chat(bot, chat_id):
    last_day_of_prev_month = datetime.today().replace(day=1) - timedelta(days=1)
    # last_day_of_prev_month = datetime.today()
    uid = CringeMonthly.get_toppest_cringe(chat_id, last_day_of_prev_month)
    logger.info(f"cringe {chat_id}:{uid}")
    if not uid:
        return
    user = User.get(uid)
    if not user:
        logger.error(f'None user {uid}')
        return

    body = __get_top_cringe_lines(chat_id, date=last_day_of_prev_month, show_percent=True)
    try:
        header = f"<b>Кринж месяца:</b> {user.fullname} <a href='tg://user?id={user.uid}'>⚡️</a>\n\n"
        send_long(bot, chat_id, f"{header}{body}")
    except Exception:
        header = f'<b>Кринж месяца:</b> {user.get_username_or_link()} ⚡️\n\n'
        send_long(bot, chat_id, f"{header}{body}")
