# coding=UTF-8

import logging
import typing
from threading import Lock

import telegram
from sqlalchemy import Column, Integer, Text, Boolean

from src.modules.models.chat_user import ChatUser
from src.utils.cache import cache, USER_CACHE_EXPIRE
from src.utils.db import Base, add_to_db, retry, session_scope

logger = logging.getLogger(__name__)


class UserDB(Base):
    __tablename__ = 'users'

    id = Column('id', Integer, primary_key=True)
    uid = Column('uid', Integer)
    username = Column('username', Text)  # без @
    fullname = Column('fullname', Text)
    public = Column('public', Boolean, default=False)
    female = Column('female', Boolean, default=False)

    @staticmethod
    def copy(obj: 'User') -> 'UserDB':
        # noinspection PyProtectedMember
        return UserDB(
            id=obj._id,
            uid=obj.uid,
            username=obj.username,
            fullname=obj.fullname,
            public=obj.public,
            female=obj.female,
        )

    @classmethod
    @retry(logger=logger)
    def add(cls, new_user: 'User'):
        try:
            add_to_db(cls.copy(new_user))
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't add user {new_user.uid} to DB")

    @classmethod
    @retry(logger=logger)
    def get(cls, uid: int) -> typing.Optional['User']:
        try:
            with session_scope() as db:
                q = db.query(UserDB) \
                    .filter(UserDB.uid == uid) \
                    .limit(1) \
                    .all()
            if q:
                return User.copy(q[0])
            return None
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't get user {uid} from DB")

    @classmethod
    @retry(logger=logger)
    def get_by_username(cls, username: str) -> typing.Optional['User']:
        username = username.lstrip('@')
        try:
            with session_scope() as db:
                q = db.query(UserDB) \
                    .filter(UserDB.username == username) \
                    .limit(1) \
                    .all()
            if q:
                return User.copy(q[0])
            return None
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't get username {username} from DB")

    @classmethod
    def get_uid_by_username(cls, username: str) -> typing.Optional[int]:
        try:
            user = cls.get_by_username(username)
            if user:
                return user.uid
            return None
        except Exception:
            raise

    @staticmethod
    @retry(logger=logger)
    def update(uid, update, new_user):
        try:
            with session_scope() as db:
                user = db.query(UserDB).filter(UserDB.uid == uid)
                # если запись обновилась
                if user.update(update) > 0:
                    return

            logger.error(f'[user.update] User {uid} not found in DB')
            # нет смысла кого попало добавлять в таблицу User

            # # если не обновилась - значит такой записи нет в базе
            # # тогда добавляем ее и пробуем обновить еще раз
            # add_to_db(UserDB.copy(new_user))
            # with session_scope() as db:
            #     user = db.query(UserDB).filter(UserDB.uid == uid)
            #     user.update(update)
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't update user {uid} to DB")


class User:
    """
    Список всех юзеров, даже ливнувших.
    """
    add_lock = Lock()
    get_lock = Lock()

    def __init__(self, id=None, uid=None, username=None, fullname=None, public=False, female=False):
        self._id = id  # делаем его protected, чтобы не путать с uid
        self.uid = uid
        self.username = username
        self.fullname = fullname
        self.public = public
        self.female = female

    def __repr__(self) -> str:
        return f"<User('{self.uid}', '{self.fullname}')>"

    @classmethod
    def copy(cls, user: UserDB) -> 'User':
        return User(
            id=user.id,
            uid=user.uid,
            username=user.username,
            fullname=user.fullname,
            public=user.public,
            female=user.female
        )

    @classmethod
    def add_user(cls, user: telegram.User) -> None:
        if user.is_bot:
            return
        username = user.username
        fullname = ' '.join([user.first_name or '', user.last_name or '']).strip()
        with cls.add_lock:
            cls.__add(user.id, username, fullname)

    @classmethod
    def get(cls, uid) -> typing.Optional['User']:
        if not uid:
            return None
        if isinstance(uid, ChatUser):
            uid = uid.uid
        if isinstance(uid, str):
            try:
                uid = int(uid)
            except Exception as e:
                logger.error(e)
                return None

        cached = cache.get(cls.__get_cache_key(uid))
        if cached:
            # if isinstance(cached, Base):
            #     logger.info(f'[user] Base class. uid {uid}')
            #     return cls.copy(cached)
            return cached

        with cls.get_lock:
            try:
                user = UserDB.get(uid)
                if user:
                    cache.set(cls.__get_cache_key(uid), user, time=USER_CACHE_EXPIRE)
                    return user
            except Exception as e:
                logger.error(e)
        return None

    def get_username_or_link(self) -> str:
        if self.username is not None:
            return '@{}'.format(self.username)
        return '<a href="tg://user?id={}">{}</a>'.format(self.uid, self.fullname)

    @classmethod
    def clear_cache(cls):
        cache.delete_by_pattern(cls.__get_cache_key('*'))

    @staticmethod
    def get_id_by_name(username: str) -> typing.Optional[int]:
        username = username.lstrip('@')
        try:
            return UserDB.get_uid_by_username(username)
        except Exception as e:
            logger.error(e)
        return None

    @classmethod
    def __add(cls, uid, username, fullname) -> None:
        old_user = cls.get(uid)
        old_user_female = False if old_user is None else old_user.female
        new_user = User(uid=uid, username=username, fullname=fullname, female=old_user_female)
        try:
            if old_user is not None:
                update = {}
                if old_user.username != username:
                    update['username'] = username
                if old_user.fullname != fullname:
                    update['fullname'] = fullname
                if update:
                    UserDB.update(uid, update, new_user)
            else:
                UserDB.add(new_user)
        except Exception as e:
            logger.error(e)
            return
        cache.set(cls.__get_cache_key(uid), new_user, time=USER_CACHE_EXPIRE)

    @staticmethod
    def __get_cache_key(uid) -> str:
        return f'user:{uid}'
