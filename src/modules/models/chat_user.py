# coding=UTF-8
import logging
import typing
from threading import Lock

from sqlalchemy import Column, Integer, BigInteger, Boolean, func

from src.config import CONFIG
from src.utils.cache import USER_CACHE_EXPIRE
from src.utils.cache import cache
from src.utils.db import Base, add_to_db, retry, session_scope

logger = logging.getLogger(__name__)


class ChatUserDB(Base):
    __tablename__ = 'chat_users'

    id = Column('id', Integer, primary_key=True)
    uid = Column('uid', Integer)
    cid = Column('cid', BigInteger)  # chat id
    left = Column('left', Boolean, default=False)  # ливнул?

    @staticmethod
    def copy(obj: 'ChatUser') -> 'ChatUserDB':
        return ChatUserDB(
            id=obj.id,
            uid=obj.uid,
            cid=obj.cid,
            left=obj.left
        )

    @classmethod
    @retry(logger=logger)
    def add(cls, value: 'ChatUser'):
        try:
            add_to_db(cls.copy(value))
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't add chatuser {value.uid}:{value.cid} to DB")

    @classmethod
    @retry(logger=logger)
    def get(cls, uid: int, cid: int) -> typing.Optional['ChatUser']:
        try:
            with session_scope() as db:
                q: typing.List[ChatUserDB] = db.query(ChatUserDB) \
                    .filter(ChatUserDB.uid == uid) \
                    .filter(ChatUserDB.cid == cid) \
                    .limit(1) \
                    .all()
            if q:
                chatuser = ChatUser.copy(q[0])
                return chatuser
            return None
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't get chatuser {uid}:{cid} from DB")

    @classmethod
    @retry(logger=logger)
    def get_random(cls, cid: int) -> typing.Optional['ChatUser']:
        try:
            with session_scope() as db:
                q: typing.List[ChatUserDB] = db.query(ChatUserDB) \
                    .filter(ChatUserDB.cid == cid) \
                    .filter(ChatUserDB.left == 0) \
                    .order_by(func.rand()) \
                    .limit(1) \
                    .all()
            if q:
                return ChatUser.copy(q[0])
            return None
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't get random chatuser {cid} from DB")

    @classmethod
    @retry(logger=logger)
    def get_all(cls, cid: int, left=False) -> typing.List['ChatUser']:
        try:
            with session_scope() as db:
                all_users = db.query(ChatUserDB) \
                    .filter(ChatUserDB.cid == cid) \
                    .filter(ChatUserDB.left == left) \
                    .all()
                return [ChatUser.copy(chatuser) for chatuser in all_users]
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't get all chatusers {cid}:{left} from DB")

    @classmethod
    @retry(logger=logger)
    def get_user_chats(cls, uid: int, cids: typing.Optional[typing.List[int]] = None) -> \
    typing.List[int]:
        config_cids = cids if cids else [int(c) for c in CONFIG.get('chats', [])]
        try:
            with session_scope() as db:
                # noinspection PyUnresolvedReferences
                user_in_chats = db.query(ChatUserDB) \
                    .filter(ChatUserDB.cid.in_(config_cids)) \
                    .filter(ChatUserDB.uid == uid) \
                    .filter(ChatUserDB.left == 0) \
                    .all()
                return [chatuser.cid for chatuser in user_in_chats]
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't get user chats {uid} from DB")

    @classmethod
    @retry(logger=logger)
    def update(cls, uid: int, cid: int, update, new_user: 'ChatUser'):
        try:
            with session_scope() as db:
                user = db.query(ChatUserDB).filter(ChatUserDB.uid == uid).filter(
                    ChatUserDB.cid == cid)
                # если запись обновилась
                if user.update(update) > 0:
                    return

            logger.error(f'[chatuser.update] user {uid}:{cid} not found in DB')
            # в chatuser можно попасть только через вход/лив/написание собственных сообщений

            # # если не обновилась - значит такой записи нет в базе
            # # тогда добавляем ее и пробуем обновить еще раз
            # add_to_db(cls.copy(new_user))
            # with session_scope() as db:
            #     user = db.query(ChatUserDB).filter(ChatUserDB.uid == uid).filter(ChatUserDB.cid == cid)
            #     user.update(update)
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't update chatuser {uid}:{cid} to DB")


class ChatUser:
    """
    Список всех юзеров в конкретном чате, даже ливнувших.
    """
    add_lock = Lock()
    get_lock = Lock()

    def __init__(self, id=None, uid=None, cid=None, left=False):
        self.id = id
        self.uid = uid
        self.cid = cid
        self.left = left

    def __repr__(self):
        return f"<ChatUser('{self.uid}', '{self.cid}', '{self.left}')>"

    @staticmethod
    def copy(chatuser: ChatUserDB) -> 'ChatUser':
        return ChatUser(
            id=chatuser.id,
            uid=chatuser.uid,
            cid=chatuser.cid,
            left=chatuser.left
        )

    @classmethod
    def add(cls, uid: int, cid: int, left: bool = False) -> None:
        if uid == cache.get('bot_id'):
            return
        with cls.add_lock:
            new_user = ChatUser(uid=uid, cid=cid, left=left)
            old_user = cls.get(uid, cid)
            try:
                if old_user is not None:
                    update = {}
                    if old_user.left != left:
                        update['left'] = left
                    if update:
                        ChatUserDB.update(uid, cid, update, new_user)
                else:
                    ChatUserDB.add(new_user)
                cache.set(cls.__get_key(uid, cid), new_user, time=USER_CACHE_EXPIRE)
            except Exception as e:
                logger.error(e)

    @classmethod
    def get(cls, uid, cid) -> typing.Optional['ChatUser']:
        cached = cache.get(cls.__get_key(uid, cid))
        if cached:
            if isinstance(cached, Base):
                logger.info(f'[chatuser] Base class. {uid}:{cid}')
                return cls.copy(cached)
            return cached
        try:
            with cls.get_lock:
                chatuser = ChatUserDB.get(uid, cid)
                if chatuser:
                    cache.set(cls.__get_key(uid, cid), chatuser, time=USER_CACHE_EXPIRE)
                    return chatuser
        except Exception as e:
            logger.error(e)
        return None

    @classmethod
    def get_all(cls, cid: int) -> typing.List['ChatUser']:
        """
        Возвращает список всех, кто сейчас в чате.
        """
        try:
            return ChatUserDB.get_all(cid)
        except Exception as e:
            logger.error(e)
            return []

    @classmethod
    def get_random(cls, cid: int) -> typing.Optional['ChatUser']:
        try:
            return ChatUserDB.get_random(cid)
        except Exception as e:
            logger.error(e)
        return None

    @classmethod
    def get_user_chats(cls, uid, cids=None) -> typing.List[int]:
        try:
            return ChatUserDB.get_user_chats(uid, cids)
        except Exception as e:
            logger.error(e)
            return []

    @staticmethod
    def __get_key(uid, cid):
        return f'chatuser:{cid}:{uid}'
