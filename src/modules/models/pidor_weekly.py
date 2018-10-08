# coding=UTF-8

import random
import re
from datetime import datetime, timedelta
from threading import Lock

from src.modules.models.user import UserDB
from src.modules.models.user_stat import UserStat
from src.utils.cache import cache, USER_CACHE_EXPIRE


class PidorWeekly:
    lock = Lock()
    re_words = re.compile(r"\b(ге[йяи]|геев|анал|аналы|аналь\S+|анус|очко|жоп[ау]|жопой|поп[ау]|попой|попк[ау]|попкой|говн[оа]|говном|пенис\S*|член\S*|пизд\S+|гомос\S+|гомик\S*|\S+сексуал\S*|климов\S*|педерас\S+|пидор\S*|пидар\S*|педик\S+|подвор\S+|iphone\S*|айфон\S*|samsung|самсунг\S*|смузи|барбер\S*|рокет\S*|хипстер\S*|лгбт\S*|бабочк\S+|м[ао]к[ао]син\S*|ахтунг\S*|толерант\S+|политкорр?ект\S+|стрижк\S+|бород\S+|аниме\S*|саратов\S*|фемк\S+|\S+изм\S*|dtf|дтф|в[еэ]йп\S*|гироскутер\S*|мизог\S+|козел|козл\S+|муда[кч]\S*|сволоч\S+|ресторан\S*|кача[лт]\S+|мыло|читер\S*|читы?|культур\S+|сра[тл]\S+|насра[тл]\S+|гад\S*|блогг?ер\S*)\b", re.IGNORECASE)
    re_inside = re.compile(r"п[еи]д[оа]р\S*", re.IGNORECASE)

    @classmethod
    def get_top_pidor(cls, cid, date=None):
        monday = cls.__get_current_monday() if date is None else cls.__get_date_monday(date)
        db = cls.__get_db(monday, cid)
        stats = UserStat.get_chat_stats(cid, date)

        # подсчитаем всех по отношению пидор-слов к общему количеству слов этого участника
        pidor_by_count = {}
        for user_stat, user in stats:
            count = user_stat.all_messages_count
            # учитываем только тек, кто написал от 30 сообщений
            if count < 30 or user_stat.words_count < 500:
                continue
            if user.uid not in db:
                continue
            pidor_by_count[user.uid] = db[user.uid] / count

        if len(pidor_by_count) > 0:
            uid, _ = cls.__sort_dict(pidor_by_count)[0]
        elif len(stats) == 0:
            return None
        else:
            _, user = random.choice(stats)
            uid = user.uid
        return uid

    @classmethod
    def parse_message(cls, message):
        msg = message.text
        if msg is None:
            return
        uid = message.from_user.id
        cid = message.chat_id
        entities = message.parse_entities()

        if not cls.__has_pidor(msg):
            return
        cls.__add(uid, cid)

        if message.reply_to_message is not None:
            to_uid = message.reply_to_message.from_user.id
            cls.__add(to_uid, cid, replay=True)

        for entity, entity_text in entities.items():
            if entity.type == 'mention':
                username = entity_text.lstrip('@').strip()
                try:
                    mentioned_user_uid = UserDB.get_uid_by_username(username)
                    if mentioned_user_uid:
                        cls.__add(mentioned_user_uid, cid, replay=True)
                except Exception:
                    pass
                continue
            if entity.type == 'text_mention':
                cls.__add(entity.user.id, cid, replay=True)
                continue

    @classmethod
    def __has_pidor(cls, msg):
        msg_lower = msg.lower().replace('ё', 'е')
        if cls.re_words.search(msg_lower):
            return True
        if cls.re_inside.search(msg_lower):
            return True
        return False

    @classmethod
    def __add(cls, uid, cid, date=None, replay=False):
        monday = cls.__get_current_monday() if date is None else cls.__get_date_monday(date)
        with cls.lock:
            db = cls.__get_db(monday, cid)
            value = 1
            if replay is True:
                value = 0.4

            if uid in db:
                db[uid] += value
            else:
                db[uid] = value

            cls.__set_db(db, monday, cid)

    @staticmethod
    def __sort_dict(d):
        return sorted(d.items(), key=lambda x: x[1], reverse=True)

    @staticmethod
    def __get_cache_key(monday, cid):
        return f'pidorweekly:{monday.strftime("%Y%m%d")}:{cid}'

    @staticmethod
    def __get_date_monday(date):
        monday = date - timedelta(days=date.weekday())
        return monday.replace(hour=0, minute=0, second=0, microsecond=0)

    @classmethod
    def __get_current_monday(cls):
        return cls.__get_date_monday(datetime.today())

    @classmethod
    def __get_db(cls, monday, cid):
        cached = cache.get(cls.__get_cache_key(monday, cid))
        if cached:
            return cached
        return {}

    @classmethod
    def __set_db(cls, newdb, monday, cid):
        cache.set(cls.__get_cache_key(monday, cid), newdb, time=USER_CACHE_EXPIRE)
