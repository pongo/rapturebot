import enum
import typing
from datetime import datetime, timedelta
from threading import Lock
from time import sleep

import sqlalchemy
import telegram
from sqlalchemy import Column, Integer, Text, BigInteger, DateTime

from src.config import CONFIG, get_config_chats
from src.models.chat_user import ChatUser
from src.models.user import User
from src.utils.cache import cache, TWO_YEARS, FEW_DAYS, pure_cache
from src.utils.db import Base, add_to_db, session_scope, retry
from src.utils.logger_helpers import get_logger
from src.utils.telegram_helpers import telegram_retry

logger = get_logger(__name__)


class LeaveCollectorDB(Base):
    __tablename__ = 'leave_logs'

    class LeaveType(enum.Enum):
        added = 1
        invite = 2
        kicked = 3
        left = 4

    id = Column('id', Integer, primary_key=True)
    uid = Column('uid', Integer)
    cid = Column('cid', BigInteger)  # chat id
    date = Column('date', DateTime)
    leave_type = Column('leave_type', sqlalchemy.Enum(LeaveType))
    from_uid = Column('from_uid', Integer)  # кто кикнул/добавил
    reason = Column('reason', Text)

    @staticmethod
    @retry(logger=logger)
    def add(uid, cid, date, from_uid, leave_type):
        try:
            add_to_db(LeaveCollectorDB(uid=uid, cid=cid, date=date, from_uid=from_uid,
                                       leave_type=leave_type))
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't add leave_collect {uid}:{cid} to DB")

    @staticmethod
    @retry(logger=logger)
    def get_leaves(cid, days_ago) -> typing.List[int]:
        try:
            with session_scope() as db:
                q = db.query(LeaveCollectorDB).from_statement(sqlalchemy.text(
                    f"""
                        SELECT 
                          t1.* 
                        FROM leave_logs t1
                          JOIN (SELECT 
                                  uid, MAX(date) date 
                                FROM leave_logs 
                                WHERE date >= {days_ago} 
                                AND cid = {cid} 
                                GROUP BY uid) t2
                          ON t1.uid = t2.uid 
                          AND t1.date = t2.date 
                          AND t1.leave_type in ('kicked', 'left')
                          AND t1.cid = {cid};
                    """)).all()
            return [x.uid for x in q]
        except Exception as e:
            logger.error(e)
            return []

    @staticmethod
    @retry(logger=logger)
    def get_joins(cid, days_ago) -> typing.List[int]:
        try:
            with session_scope() as db:
                q = db.query(LeaveCollectorDB).from_statement(sqlalchemy.text(
                    f"""
                        SELECT
                            t1.* 
                        FROM leave_logs t1
                          JOIN (SELECT 
                                    uid, MAX(date) date 
                                FROM leave_logs 
                                WHERE date >= {days_ago} 
                                AND cid = {cid} 
                                GROUP BY uid) t2
                          ON t1.uid = t2.uid 
                          AND t1.date = t2.date 
                          AND t1.leave_type in ('added', 'invite') 
                          AND t1.cid = {cid};
                    """)).all()
            return [x.uid for x in q]
        except Exception as e:
            logger.error(e)
            return []


class LeaveCollector:
    """
    Здесь хранятся все входы и ливы из чата.
    """
    update_ktolivnul_lock = Lock()

    def __init__(self, id=None, uid=None, cid=None, date=None, leave_type=None, from_uid=None,
                 reason=None):
        self.id = id
        self.uid = uid
        self.cid = cid
        self.date = date
        self.leave_type = leave_type
        self.from_uid = from_uid
        self.reason = reason

    def __repr__(self):
        return f"<Leave('{self.uid}', '{self.leave_type}')>"

    def format(self, show_username=True):
        return self.__format_uid(self.uid, show_username=show_username)

    @staticmethod
    def __format_uid(uid, show_username=True):
        user = User.get(uid)
        if not user:
            return ''
        username = ''
        if show_username and user.username is not None:
            username = f' @{user.username}'
        return f"<b>{user.fullname}</b>{username}".strip()

    @classmethod
    def __add(cls, uid, cid, date, from_uid, leave_type):
        try:
            LeaveCollectorDB.add(uid=uid, cid=cid, date=date, from_uid=from_uid,
                                 leave_type=leave_type)
        except Exception as e:
            logger.error(e)

    @staticmethod
    def add_invite(uid, cid, date, from_uid):
        LeaveCollector.__add(uid, cid, date, from_uid, LeaveCollectorDB.LeaveType.invite)

    @staticmethod
    def add_join(uid, cid, date, from_uid):
        LeaveCollector.__add(uid, cid, date, from_uid, LeaveCollectorDB.LeaveType.added)

    @staticmethod
    def add_left(uid, cid, date, from_uid):
        LeaveCollector.__add(uid, cid, date, from_uid, LeaveCollectorDB.LeaveType.left)

    @staticmethod
    def add_kick(uid, cid, date, from_uid):
        LeaveCollector.__add(uid, cid, date, from_uid, LeaveCollectorDB.LeaveType.kicked)

    @classmethod
    def get_leaves(cls, cid, days=3, return_id=False):
        days_ago = (datetime.today() - timedelta(days=days)).replace(hour=0, minute=0, second=0,
                                                                     microsecond=0)
        uids: typing.Set[int] = set(LeaveCollectorDB.get_leaves(cid, days_ago.strftime('%Y%m%d')))

        # некоторые ливают, а потом возвращаются без сообщений о входе.
        # из-за отсутствия сообщения о входе, LeaveCollector думает, что они не в чате
        # (при этом сам бот в курсе, что они в чате).
        # можно было бы в `leave_check` определять невидимые входы и отмечать их,
        # но проще просто в этом методе получить тех, кто в чате, и исключить их из выдачи.
        chat_uids_db: typing.Set[int] = set([x.uid for x in ChatUser.get_all(cid)])
        true_leaves = uids - chat_uids_db

        if return_id:
            return list(true_leaves)
        return [cls.__format_uid(uid) for uid in true_leaves]

    @classmethod
    def get_joins(cls, cid, days=3):
        days_ago = (datetime.today() - timedelta(days=days)).replace(hour=0, minute=0, second=0,
                                                                     microsecond=0)
        uids = LeaveCollectorDB.get_joins(cid, days_ago.strftime('%Y%m%d'))
        return [cls.__format_uid(uid, show_username=False) for uid in uids]

    @staticmethod
    def check_left_users(bot: telegram.Bot) -> None:
        LeftUsersChecker.check(bot)

    @classmethod
    def update_ktolivnul(cls, chat_id: int) -> None:
        logger.debug(f'update_ktolivnul_lock {chat_id}')
        # лок, чтобы работа прошла за раз
        # иначе можно кого-то отметить дважды ливнувшим
        with cls.update_ktolivnul_lock:
            chat_uids_ktolivnul = set(
                [int(x) for x in pure_cache.get(f'ktolivnul:{chat_id}', '').split(',') if x != ''])
            if len(chat_uids_ktolivnul) == 0:
                return
            chat_uids_db = set([x.uid for x in ChatUser.get_all(chat_id)])
            leaved_uids = chat_uids_db - chat_uids_ktolivnul
            if len(leaved_uids) == 0:
                return
            ktolivnul_uid = CONFIG.get('ktolivnul', 0)
            now = datetime.now()
            for uid in leaved_uids:
                ChatUser.add(uid, chat_id, left=True)
                LeaveCollector.add_kick(uid, chat_id, now, ktolivnul_uid)
                logger.info(f'[update_ktolivnul] kick {chat_id}:{uid}')


class LeftUsersChecker:
    """
    В супергруппах от 50 человек телеграм не посылает боту сообщения о выходе из группы.
    Так же в апи нет функции "получить список участников чата".
    Вместо этого есть отдельный клиент-апи бот КтоЛивнулыч, который будет собирать список чатовцев.
    А мы будем периодически сверять свой список с его.
    """

    @classmethod
    def check(cls, bot: telegram.Bot) -> None:
        for chat in get_config_chats():
            # это нужно только для супергрупп, поэтому сперва проверяем, супергруппа ли это
            if not cls.__is_supergroup(bot, chat.chat_id):
                continue
            # проверяем, не кикнули ли нас из этой супергруппы
            if not cls.__is_we_still_in_chat(bot, chat.chat_id):
                continue
            # используем данные ктоливнулыча
            LeaveCollector.update_ktolivnul(chat.chat_id)

    @classmethod
    def __get_chat_title_first_word(cls, bot: telegram.Bot, chat_id: int,
                                    prefix_if_not_empty: str = '') -> str:
        cache_key = f'chat_title_first_word:{chat_id}'
        cached = cache.get(cache_key)
        if cached:
            return cached
        try:
            sleep(1)
            chat = cls.__get_chat(bot, chat_id)
            first_word = '' if not chat.title else prefix_if_not_empty + chat.title.split(' ')[0]
            cache.set(cache_key, first_word, time=FEW_DAYS)
            return first_word
        except Exception:
            return ''

    @staticmethod
    @telegram_retry(logger=logger, title='leave_check.get_chat')
    def __get_chat(bot: telegram.Bot, chat_id: int) -> typing.Optional[telegram.Chat]:
        return bot.get_chat(chat_id)

    @classmethod
    def __is_supergroup(cls, bot: telegram.Bot, chat_id: int) -> bool:
        cache_key = f'is_supergroup:{chat_id}'
        is_supergroup = cache.get(cache_key)
        if is_supergroup is not None:
            return is_supergroup
        try:
            sleep(1)
            chat = cls.__get_chat(bot, chat_id)
            is_supergroup = chat.type == chat.SUPERGROUP
            cache.set(cache_key, is_supergroup, time=TWO_YEARS)
            return is_supergroup
        except telegram.error.TelegramError as e:
            if e.message == 'Chat not found':
                logger.warning(
                    f'[check_left_users] Chat {chat_id} not found (probably bot don\' have access, but chat is listed in config.json)')
            else:
                logger.warning(f'[check_left_users] Chat {chat_id} error: {e}')
        except Exception as e:
            logger.warning(f'[leave_check.__is_supergroup] cid {chat_id}. Exception {e}')
        return False

    @classmethod
    def __is_we_still_in_chat(cls, bot: telegram.Bot, chat_id: int) -> bool:
        try:
            sleep(1)
            cls.__get_chat(bot, chat_id)
            return True
        except telegram.error.TelegramError as e:
            logger.warning(f'[check_left_users double check] Chat {chat_id} error: {e}')
        except Exception as e:
            logger.warning(f'[leave_check.__is_we_still_in_chat] cid {chat_id}. Exception {e}')
        return False
