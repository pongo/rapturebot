import json
import os
from datetime import datetime
from threading import Lock
from typing import List, Tuple, Optional

import pytils
from telegram.ext import run_async

from src.config import CONFIG
from src.modules.models.chat_user import ChatUser
from src.modules.models.user import UserDB, User
from src.utils.cache import cache, USER_CACHE_EXPIRE, bot_id
from src.utils.logger_helpers import get_logger
from src.utils.misc import sort_dict, get_int
from src.utils.time_helpers import get_current_monday, get_date_monday, get_yesterday

logger = get_logger(__name__)


class ReplyTopDBHelper:
    """
    Хелпер для работы с данными
    """
    def __init__(self, name: str, delay=USER_CACHE_EXPIRE) -> None:
        self.name = name
        self.delay = delay
        self.lock = Lock()

    def __get_cache_key(self, date: datetime, cid: int) -> str:
        return f'{self.name}:{date.strftime("%Y%m%d")}:{cid}'

    def get_db(self, date: datetime, cid: int) -> dict:
        cached = cache.get(self.__get_cache_key(date, cid))
        if cached:
            return cached

        template = {
            'to': {},
            'from': {},
            'pair': {},
            'outbound': {},
            'inbound': {},
        }
        return template

    def set_db(self, newdb: dict, date: datetime, cid: int) -> None:
        cache.set(self.__get_cache_key(date, cid), newdb, time=self.delay)

    def add(self, from_uid: int, to_uid: int, cid: int, date: datetime) -> None:
        """
        Добавляет статистику по страсти
        """
        logger.debug(f'[{self.name}] lock {cid}:{from_uid}-->{to_uid}')
        with self.lock:
            db = self.get_db(date, cid)
            self.__count_replays(db, from_uid, to_uid)
            self.__count_pairs(db, from_uid, to_uid)
            self.__count_outbound(db, from_uid, to_uid)
            self.__count_inbound(db, from_uid, to_uid)
            self.set_db(db, date, cid)

    @staticmethod
    def __count_inbound(db, from_uid, to_uid):
        """
        Входящая страсть
        """
        if 'inbound' not in db:
            db['inbound'] = {}
        if to_uid not in db['inbound']:
            db['inbound'][to_uid] = {}
        if from_uid in db['inbound'][to_uid]:
            db['inbound'][to_uid][from_uid] += 1
        else:
            db['inbound'][to_uid][from_uid] = 1

    @staticmethod
    def __count_outbound(db, from_uid, to_uid):
        """
        Исходящая страсть
        """
        if 'outbound' not in db:
            db['outbound'] = {}
        if from_uid not in db['outbound']:
            db['outbound'][from_uid] = {}
        if to_uid in db['outbound'][from_uid]:
            db['outbound'][from_uid][to_uid] += 1
        else:
            db['outbound'][from_uid][to_uid] = 1

    @staticmethod
    def __count_pairs(db, from_uid, to_uid):
        """
        Парная страсть
        """
        # сортируем id, чтобы ключ всегда был одинаковый
        # вариант когда юзер реплает самому себе тоже допустим
        pair_key = ','.join(sorted([str(from_uid), str(to_uid)]))
        if pair_key in db['pair']:
            db['pair'][pair_key] += 1
        else:
            db['pair'][pair_key] = 1

    @staticmethod
    def __count_replays(db, from_uid, to_uid):
        """
        Подсчет реплаев
        """
        # сколько реплаев отправлено этому юзеру
        if to_uid in db['to']:
            db['to'][to_uid] += 1
        else:
            db['to'][to_uid] = 1
        # сколько реплаев отправил этот юзер
        if from_uid in db['from']:
            db['from'][from_uid] += 1
        else:
            db['from'][from_uid] = 1


class ReplyTop:
    """
    Хранит недельную статистику кто кого реплаит
    """

    db_helper = ReplyTopDBHelper('replytop')

    @classmethod
    def add(cls, from_uid, to_uid, cid, date: Optional[datetime] = None):
        monday = get_current_monday() if date is None else get_date_monday(date)
        cls.db_helper.add(from_uid, to_uid, cid, monday)
        ReplyTopDaily.add(from_uid, to_uid, cid)

    @classmethod
    def get_stats(cls, cid, date=None):
        monday = get_current_monday() if date is None else get_date_monday(date)
        db = cls.db_helper.get_db(monday, cid)
        ignore = CONFIG.get('replylove__ignore', [])
        return {
            'to': sort_dict(cls.__remove_uids(db['to'], ignore))[:3],
            'from': sort_dict(cls.__remove_uids(db['from'], ignore))[:3],
            'pair': sort_dict(cls.__ignore_pairs(cid, cls.__remove_uids(db['pair'], ignore)))[:10]
        }

    @classmethod
    def get_stats_unlimited(cls, cid, date=None):
        """
        Как get_stats, но с полным показом страсти, без игнорирования
        """
        monday = get_current_monday() if date is None else get_date_monday(date)
        db = cls.db_helper.get_db(monday, cid)
        return {
            'to': sort_dict(db['to']),
            'from': sort_dict(db['from']),
            'pair': sort_dict(db['pair'])
        }

    @staticmethod
    def __ignore_pairs(chat_id, pairs):
        copy = pairs.copy()
        replylove__ignore_pairs = CONFIG.get('replylove__ignore_pairs', {}).get(str(chat_id), {})
        for uid_str, ignore_uids in replylove__ignore_pairs.items():
            str_uids = [str(uid) for uid in ignore_uids]
            for pair in pairs.keys():
                pair_uids = pair.split(',')
                if uid_str not in pair_uids:
                    continue
                pair_uids.remove(uid_str)
                b = pair_uids[0]
                if b in str_uids:
                    copy.pop(pair, None)
        return copy

    @staticmethod
    def __remove_uids(d: dict, uids: List[int]) -> dict:
        if len(d) == 0:
            return d
        if len(uids) == 0:
            return d
        copy = d.copy()  # иначе он будет удалять из оригинального словаря
        # разбираем парный список
        if isinstance(next(iter(d)), str):  # первый элемент словаря - это строка?
            str_uids = [str(uid) for uid in uids]
            for uid in str_uids:
                for pair in d.keys():
                    pair_uids = pair.split(',')
                    if uid in pair_uids:
                        copy.pop(pair, None)
            return copy
        # разбираем обычный список
        for uid in uids:
            if uid in d:
                copy.pop(uid, None)
        return copy

    @classmethod
    @run_async
    def parse_message(cls, message):
        from_uid = message.from_user.id
        cid = message.chat_id
        entities = message.parse_entities()

        if message.reply_to_message is not None:
            to_uid = message.reply_to_message.from_user.id
            cls.add(from_uid, to_uid, cid)

        for entity, entity_text in entities.items():
            if entity.type == 'mention':
                username = entity_text.lstrip('@').strip()
                try:
                    mentioned_user_uid = UserDB.get_uid_by_username(username)
                    if mentioned_user_uid:
                        cls.add(from_uid, mentioned_user_uid, cid)
                except Exception:
                    pass
                continue

    @classmethod
    def get_user_top_strast(cls, chat_id: int, user_id: int, date=None) -> Tuple[Optional[User], Optional[User], Optional[User]]:
        def get_top(type: str, uid: int) -> Optional[User]:
            if type not in db:
                return None
            if uid not in db[type]:
                return None
            replylove__ignore = CONFIG.get('replylove__ignore', [])
            if uid in replylove__ignore:
                return None
            replylove__dragon_lovers = CONFIG.get('replylove__dragon_lovers', [])
            if uid in replylove__dragon_lovers:
                return User(0, 0, 'drakon', '🐉')
            sorted: List[Tuple[int, int]] = sort_dict(db[type][uid])
            if len(sorted) == 0:
                return None
            replylove__ignore_pairs = CONFIG.get('replylove__ignore_pairs', {}).get(str(chat_id), {}).get(str(uid), [])
            for result_uid, count in sorted:
                if count < 5:
                    continue
                if uid == result_uid:
                    continue
                if result_uid in replylove__dragon_lovers:
                    continue
                if result_uid in replylove__ignore:
                    continue
                if result_uid in replylove__ignore_pairs:
                    continue
                return User.get(result_uid)
            return None

        def get_top_pair(uid: int) -> Optional[User]:
            replylove__dragon_lovers = CONFIG.get('replylove__dragon_lovers', [])
            if uid in replylove__dragon_lovers:
                return User(0, 0, 'drakon', '🐉')
            replylove__ignore = CONFIG.get('replylove__ignore', [])
            replylove__ignore_pairs = CONFIG.get('replylove__ignore_pairs', {}).get(str(chat_id), {}).get(str(uid), [])
            pairs: List[Tuple[str, int]] = sort_dict(db['pair'])
            for pair, count in pairs:
                a_uid, b_uid = [get_int(x) for x in pair.split(',')]
                strast = None
                if a_uid is None or b_uid is None:
                    continue
                if count < 5:
                    continue
                if uid == a_uid and a_uid == b_uid:
                    continue
                if any(x in replylove__dragon_lovers for x in (a_uid, b_uid)):
                    continue
                if any(x in replylove__ignore for x in (uid, a_uid, b_uid)):
                    continue
                if any(x in replylove__ignore_pairs for x in (a_uid, b_uid)):
                    continue
                if uid == a_uid:
                    strast = User.get(b_uid)
                if uid == b_uid:
                    strast = User.get(a_uid)
                if strast:
                    return strast
            return None

        monday = get_current_monday() if date is None else get_date_monday(date)
        db = cls.db_helper.get_db(monday, chat_id)

        pair = get_top_pair(user_id)
        inbound = get_top('inbound', user_id)
        outbound = get_top('outbound', user_id)
        return pair, inbound, outbound


class ReplyTopDaily:
    """
    Хранит дневную статистику кто кого реплаит
    """

    db_helper = ReplyTopDBHelper('replytop_daily')

    @classmethod
    def add(cls, from_uid, to_uid, cid, date: Optional[datetime] = None):
        day = datetime.today() if date is None else date
        cls.db_helper.add(from_uid, to_uid, cid, day)


class ReplyLove:
    @staticmethod
    def get_fullname_or_username(user: User) -> str:
        if user.fullname and len(user.fullname.strip()) > 0:
            return user.fullname
        if user.username:
            return user.username.strip('@')
        return f'Аноним #{user.uid} без имени и юзернейма'

    @classmethod
    def __format_pair(cls, a: User, b: Optional[User] = None, b_pair: Optional[User] = None) -> str:
        if not b:
            return f'<b>{cls.get_fullname_or_username(a)}</b>'
        if a.uid in CONFIG.get('replylove__dragon_lovers', []):
            return f'<b>{cls.get_fullname_or_username(a)}</b> ⟷ 🐉'
        love = ' ❤' if b_pair and b_pair.uid == a.uid else ''
        return f'<b>{cls.get_fullname_or_username(a)}</b> ⟷ {cls.get_fullname_or_username(b)}{love}'

    @classmethod
    def get_all_love(cls, chat_id: int, date=None, header='Вся страсть') -> str:
        def get_no_love_str(no_love_: List) -> str:
            length = len(no_love_)
            if length == 0:
                return ''
            if length <= 10:
                return '\n\nБеcстрастные:\n' + '\n'.join((cls.__format_pair(a) for a in no_love_))
            return f'\n\nИ еще {pytils.numeral.get_plural(length, "беcстрастный, беcстрастных, беcстрастных")}'

        def get_narcissist(narcissist_: List[User]) -> str:
            if len(narcissist_) == 0:
                return ''
            return f'\n\nНарциссы:\n' + '\n'.join((cls.__format_pair(a) for a in narcissist_))

        all_chat_users = ChatUser.get_all(chat_id)
        all_users = (User.get(chatuser.uid) for chatuser in all_chat_users)
        all_users = sorted(all_users, key=lambda x: x.fullname)
        all_love = [(user, ReplyTop.get_user_top_strast(chat_id, user.uid, date)[0]) for user in all_users if user]

        in_love = [(a, b, ReplyTop.get_user_top_strast(chat_id, b.uid, date)[0]) for a, b in all_love if b]
        narcissist = [a for a, _ in all_love if a.uid in CONFIG.get('replylove__narcissist', [])]
        no_love = [a for a, b in all_love if not b and a.uid not in CONFIG.get('replylove__narcissist', [])]

        in_love_str = '\n'.join(cls.__format_pair(a, b, b_pair) for a, b, b_pair in in_love)
        no_love_str = get_no_love_str(no_love)
        narcissist_str = get_narcissist(narcissist)

        return f'{header}:\n\n{in_love_str}{narcissist_str}{no_love_str}'

    @classmethod
    def get_all_love_outbound(cls, chat_id: int, date=None, header='Вся исходящая страсть', no_love_show_only_count=False) -> str:
        all_chat_users = ChatUser.get_all(chat_id)
        all_users = (User.get(chatuser.uid) for chatuser in all_chat_users)
        all_users = sorted(all_users, key=lambda x: x.fullname)
        all_love = [(user, ReplyTop.get_user_top_strast(chat_id, user.uid, date)[2]) for user in all_users if user]

        in_love = [(a, b, ReplyTop.get_user_top_strast(chat_id, b.uid, date)[2]) for a, b in all_love if b]
        no_love = [a for a, b in all_love if not b]

        in_love_str = '\n'.join(cls.__format_pair(a, b, b_pair) for a, b, b_pair in in_love)
        if no_love_show_only_count is False:
            no_love_str = '' if len(no_love) == 0 else '\n\nБеcстрастные:\n' + '\n'.join((cls.__format_pair(a) for a in no_love))
        else:
            no_love_str = '' if len(no_love) == 0 else f'\n\nИ еще {pytils.numeral.get_plural(len(no_love), "беcстрастный, беcстрастных, беcстрастных")}'

        return f'{header}:\n\n{in_love_str}{no_love_str}'


class ReplyDumper:
    """
    Сохраняет на диск дампы страстей
    """

    @classmethod
    def dump(cls, cid) -> None:
        current_dir = os.getcwd()
        tmp_dir = f'{current_dir}/tmp/reply_top/{cid}'
        os.makedirs(os.path.dirname(f'{tmp_dir}/'), exist_ok=True)

        yesterday = get_yesterday()
        yesterday_str = yesterday.strftime('%Y%m%d')
        monday = get_date_monday(yesterday)
        monday_str = monday.strftime('%Y%m%d')

        # недельная страсть будет каждый день нарастать
        cls.__dump(f'{tmp_dir}/{monday_str}_week_{yesterday_str}.json', ReplyTop.db_helper.get_db(monday, cid))

        # ежедневная страсть каждый день с нуля начинает
        cls.__dump(f'{tmp_dir}/{monday_str}_day_{yesterday_str}.json', ReplyTopDaily.db_helper.get_db(yesterday, cid))

    @staticmethod
    def __dump(filepath: str, value) -> None:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(json.dumps(value, ensure_ascii=False, indent=2))

class LoveDumpTable:
    """
    Сохраняет страсть для табличного формата
    """

    @classmethod
    def dump(cls, cid: int, date: datetime) -> None:
        stats = ReplyTop.get_stats_unlimited(cid, date)
        cls.__dump_simple('im_vse_pishut', 'Получено реплаев', stats['to'])
        cls.__dump_simple('oni_vsem_pishut', 'Отправлено реплаев', stats['from'])
        cls.__dump_love('top_strasti', stats['pair'])

    @classmethod
    def __dump_simple(cls, filename, header_first_colon, stats) -> None:
        header = f'{header_first_colon}\tИмя'
        rows = []
        for uid, count in stats:
            fullname = cls.__get_user_fullname(uid)
            rows.append(f'{count}\t{fullname}')
        body = '\n'.join(rows)
        cls.__save(filename, f'{header}\n{body}\n')

    @staticmethod
    def __save(filename: str, value: str) -> None:
        current_dir = os.getcwd()
        tmp_dir = f'{current_dir}/tmp/reply_top/lovedump'
        os.makedirs(os.path.dirname(f'{tmp_dir}/'), exist_ok=True)
        with open(f'{tmp_dir}/{filename}.txt', 'w', encoding='utf-8') as f:
            f.write(value)

    @classmethod
    def __dump_love(cls, filename, stats) -> None:
        from collections import OrderedDict
        header = 'Реплаев в этой паре\tИмя 1\tИмя 2'
        rows = []
        for pair_key, count in stats:
            uid1, uid2 = [get_int(uid) for uid in pair_key.split(',')]
            name1, name2 = [cls.__get_user_fullname(uid1), cls.__get_user_fullname(uid2)]
            # добавляем оба варианта, чтобы была полная картина
            rows.append(f'{count}\t{name1}\t{name2}')
            rows.append(f'{count}\t{name2}\t{name1}')
        rows_uniq = list(OrderedDict.fromkeys(rows))  # удаляем дубли, сохраняя порядок строк
        body = '\n'.join(rows_uniq)
        cls.__save(filename, f'{header}\n{body}\n')

    @staticmethod
    def __get_user_fullname(uid: int) -> str:
        if uid == bot_id():
            return 'Бот 🤖'
        user = User.get(uid)
        fullname = uid if not user else user.fullname
        return fullname
