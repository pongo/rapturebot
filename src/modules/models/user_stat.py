# coding=UTF-8

import locale
import random
import typing
from datetime import timedelta
from threading import Lock
from urllib.parse import urlparse

import pytils
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, func

import emoji_fixed as emoji
from src.config import CONFIG
from src.modules.antimat import Antimat
from src.modules.models.chat_user import ChatUser, ChatUserDB
from src.modules.models.user import UserDB, User
from src.utils.cache import USER_CACHE_EXPIRE
from src.utils.cache import cache
from src.utils.db import Base, add_to_db, retry, session_scope
from src.utils.logger import logger
from src.utils.misc import sort_dict
from src.utils.time_helpers import get_current_monday, get_date_monday


class UserStatDB(Base):
    __tablename__ = 'user_stats'

    id = Column('id', Integer, primary_key=True)
    stats_monday = Column('stats_monday', DateTime)
    uid = Column('uid', Integer)  # telegram user id
    cid = Column('cid', BigInteger)  # chat id
    last_activity = Column('last_activity', DateTime)
    all_messages_count = Column('all_messages_count', Integer, default=0)
    sent_replies_count = Column('sent_replies_count', Integer, default=0)
    received_replies_count = Column('received_replies_count', Integer, default=0)
    forwards_count = Column('forwards_count', Integer, default=0)
    text_messages_count = Column('text_messages_count', Integer, default=0)
    text_messages_with_obscene_count = Column('text_messages_with_obscene_count', Integer, default=0)
    audios_count = Column('audios_count', Integer, default=0)
    documents_count = Column('documents_count', Integer, default=0)
    gifs_count = Column('gifs_count', Integer, default=0)
    photos_count = Column('photos_count', Integer, default=0)
    stickers_count = Column('stickers_count', Integer, default=0)
    videos_count = Column('videos_count', Integer, default=0)
    video_notes_count = Column('video_notes_count', Integer, default=0)
    video_notes_duration = Column('video_notes_duration', Integer, default=0)
    voices_count = Column('voices_count', Integer, default=0)
    voices_duration = Column('voices_duration', Integer, default=0)
    games_count = Column('games_count', Integer, default=0)
    sent_mentions_count = Column('sent_mentions_count', Integer, default=0)
    received_mentions_count = Column('received_mentions_count', Integer, default=0)
    hashtags_count = Column('hashtags_count', Integer, default=0)
    bot_commands_count = Column('bot_commands_count', Integer, default=0)
    urls_count = Column('urls_count', Integer, default=0)
    emails_count = Column('emails_count', Integer, default=0)
    words_count = Column('words_count', Integer, default=0)
    obscene_words_count = Column('obscene_words_count', Integer, default=0)
    chars_count = Column('chars_count', Integer, default=0)
    chars_wo_space_count = Column('chars_wo_space_count', Integer, default=0)
    emoji_count = Column('emoji_count', Integer, default=0)
    score = Column('score', Integer, default=0)
    top_domain = Column('top_domain', String(255))

    @staticmethod
    def copy(obj):
        return UserStatDB(
            id=obj.id,
            stats_monday=obj.stats_monday,
            uid=obj.uid,
            cid=obj.cid,
            last_activity=obj.last_activity,
            all_messages_count=obj.all_messages_count,
            sent_replies_count=obj.sent_replies_count,
            received_replies_count=obj.received_replies_count,
            forwards_count=obj.forwards_count,
            text_messages_count=obj.text_messages_count,
            text_messages_with_obscene_count=obj.text_messages_with_obscene_count,
            audios_count=obj.audios_count,
            documents_count=obj.documents_count,
            gifs_count=obj.gifs_count,
            photos_count=obj.photos_count,
            stickers_count=obj.stickers_count,
            videos_count=obj.videos_count,
            video_notes_count=obj.video_notes_count,
            video_notes_duration=obj.video_notes_duration,
            voices_count=obj.voices_count,
            voices_duration=obj.voices_duration,
            games_count=obj.games_count,
            sent_mentions_count=obj.sent_mentions_count,
            received_mentions_count=obj.received_mentions_count,
            hashtags_count=obj.hashtags_count,
            bot_commands_count=obj.bot_commands_count,
            urls_count=obj.urls_count,
            emails_count=obj.emails_count,
            words_count=obj.words_count,
            obscene_words_count=obj.obscene_words_count,
            chars_count=obj.chars_count,
            chars_wo_space_count=obj.chars_wo_space_count,
            emoji_count=obj.emoji_count,
            score=obj.score,
            top_domain=obj.top_domain
        )

    @staticmethod
    @retry(logger=logger)
    def add(added_stat: 'UserStat') -> None:
        try:
            add_to_db(UserStatDB.copy(added_stat))
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't add userstat {added_stat.uid} to DB")

    @staticmethod
    @retry(logger=logger)
    def update_db(added_stat: 'UserStat', update) -> None:
        try:
            with session_scope() as db:
                user_stat = db.query(UserStatDB).filter(UserStatDB.stats_monday == added_stat.stats_monday,
                                                        UserStatDB.cid == added_stat.cid,
                                                        UserStatDB.uid == added_stat.uid)
                if user_stat.update(update) > 0:
                    return

            logger.error(f'[userstat.update] user {added_stat.uid}:{added_stat.cid} not found in DB')

            # update возвращает 0 если объекта нет в бд
            # тогда мы добавляем его в бд и еще раз пробуем обновить
            # статистику добавляем даже по тем, кого нет в таблицах User|ChatUser
            add_to_db(UserStatDB.copy(added_stat))
            with session_scope() as db:
                user_stat = db.query(UserStatDB).filter(UserStatDB.stats_monday == added_stat.stats_monday,
                                                        UserStatDB.cid == added_stat.cid,
                                                        UserStatDB.uid == added_stat.uid)
                user_stat.update(update)
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't update userstat {added_stat.uid}:{added_stat.cid} to DB")


class UserStat:
    add_lock = Lock()
    get_lock = Lock()

    def __init__(self,
                 id=None,
                 stats_monday=None,
                 uid=None,
                 cid=None,
                 last_activity=None,
                 all_messages_count=0,
                 sent_replies_count=0,
                 received_replies_count=0,
                 forwards_count=0,
                 text_messages_count=0,
                 text_messages_with_obscene_count=0,
                 audios_count=0,
                 documents_count=0,
                 gifs_count=0,
                 photos_count=0,
                 stickers_count=0,
                 videos_count=0,
                 video_notes_count=0,
                 video_notes_duration=0,
                 voices_count=0,
                 voices_duration=0,
                 games_count=0,
                 sent_mentions_count=0,
                 received_mentions_count=0,
                 hashtags_count=0,
                 bot_commands_count=0,
                 urls_count=0,
                 emails_count=0,
                 words_count=0,
                 obscene_words_count=0,
                 chars_count=0,
                 chars_wo_space_count=0,
                 emoji_count=0,
                 score=0,
                 top_domain=None):
        self.id = id
        self.stats_monday = stats_monday
        self.uid = uid
        self.cid = cid
        self.last_activity = last_activity
        self.all_messages_count = all_messages_count
        self.sent_replies_count = sent_replies_count
        self.received_replies_count = received_replies_count
        self.forwards_count = forwards_count
        self.text_messages_count = text_messages_count
        self.text_messages_with_obscene_count = text_messages_with_obscene_count
        self.audios_count = audios_count
        self.documents_count = documents_count
        self.gifs_count = gifs_count
        self.photos_count = photos_count
        self.stickers_count = stickers_count
        self.videos_count = videos_count
        self.video_notes_count = video_notes_count
        self.video_notes_duration = video_notes_duration
        self.voices_count = voices_count
        self.voices_duration = voices_duration
        self.games_count = games_count
        self.sent_mentions_count = sent_mentions_count
        self.received_mentions_count = received_mentions_count
        self.hashtags_count = hashtags_count
        self.bot_commands_count = bot_commands_count
        self.urls_count = urls_count
        self.emails_count = emails_count
        self.words_count = words_count
        self.obscene_words_count = obscene_words_count
        self.chars_count = chars_count
        self.chars_wo_space_count = chars_wo_space_count
        self.emoji_count = emoji_count
        self.score = score
        self.top_domain = top_domain

    def __repr__(self):
        return "<UserStat('{}', '{}', '{}', '{}')>".format(self.stats_monday, self.cid, self.uid,
                                                           self.all_messages_count)

    @classmethod
    def copy(cls, userstat):
        return UserStat(
            id=userstat.id,
            stats_monday=userstat.stats_monday,
            uid=userstat.uid,
            cid=userstat.cid,
            last_activity=userstat.last_activity,
            all_messages_count=userstat.all_messages_count,
            sent_replies_count=userstat.sent_replies_count,
            received_replies_count=userstat.received_replies_count,
            forwards_count=userstat.forwards_count,
            text_messages_count=userstat.text_messages_count,
            text_messages_with_obscene_count=userstat.text_messages_with_obscene_count,
            audios_count=userstat.audios_count,
            documents_count=userstat.documents_count,
            gifs_count=userstat.gifs_count,
            photos_count=userstat.photos_count,
            stickers_count=userstat.stickers_count,
            videos_count=userstat.videos_count,
            video_notes_count=userstat.video_notes_count,
            video_notes_duration=userstat.video_notes_duration,
            voices_count=userstat.voices_count,
            voices_duration=userstat.voices_duration,
            games_count=userstat.games_count,
            sent_mentions_count=userstat.sent_mentions_count,
            received_mentions_count=userstat.received_mentions_count,
            hashtags_count=userstat.hashtags_count,
            bot_commands_count=userstat.bot_commands_count,
            urls_count=userstat.urls_count,
            emails_count=userstat.emails_count,
            words_count=userstat.words_count,
            obscene_words_count=userstat.obscene_words_count,
            chars_count=userstat.chars_count,
            chars_wo_space_count=userstat.chars_wo_space_count,
            emoji_count=userstat.emoji_count,
            score=userstat.score,
            top_domain=userstat.top_domain,
        )

    @classmethod
    def add(cls, added_stat: 'UserStat') -> None:
        if added_stat.uid == cache.get('bot_id'):
            return
        monday = get_current_monday()
        added_stat.stats_monday = monday
        uid = added_stat.uid
        cid = added_stat.cid
        with cls.add_lock:
            old_stat = cls.get(monday, uid, cid)
            key = cls.__get_cache_key(monday, uid, cid)
            try:
                if old_stat is not None:
                    updated_stat = cls.__update(old_stat, added_stat)
                    cache.set(key, updated_stat, time=USER_CACHE_EXPIRE)
                    return
                UserStatDB.add(added_stat)
                cache.set(key, added_stat, time=USER_CACHE_EXPIRE)
            except Exception as e:
                logger.error(e)

    @classmethod
    def get(cls, monday, uid, cid) -> typing.Optional['UserStat']:
        cached = cache.get(cls.__get_cache_key(monday, uid, cid))
        if cached:
            if isinstance(cached, Base):
                logger.info(f'Base class. uid {uid}. cid {cid}')
                return cls.copy(cached)
            return cached
        with cls.get_lock:
            try:
                with session_scope() as db:
                    q = db.query(UserStatDB) \
                        .filter(UserStatDB.stats_monday == monday,
                                UserStatDB.cid == cid,
                                UserStatDB.uid == uid) \
                        .limit(1) \
                        .all()
                    if q:
                        userstat = cls.copy(q[0])
                        cache.set(cls.__get_cache_key(monday, uid, cid), userstat)
                        return userstat
            except Exception as e:
                logger.error(e)
        return None

    @classmethod
    def me_format(cls, date, uid, cid):
        monday = get_date_monday(date)
        stat = cls.get(monday, uid, cid)
        if stat is None:
            return ''

        user = User.get(uid)

        # сообщения
        count_keys = {
            'all_messages_count': 'всего, всего, всего',
            'text_messages_count': 'сообщение, сообщения, сообщений',
            'text_messages_with_obscene_count': 'сообщение с матом, сообщения с матом, сообщений с матом',
            'forwards_count': 'форвард, форварда, форвардов',
            # 'audios_count': 'аудио, аудио, аудио',
            # 'documents_count': 'файл, файла, файлов',
            'gifs_count': 'гифка, гифки, гифок',
            'photos_count': 'фотка, фотки, фоток',
            'stickers_count': 'стикер, стикера, стикеров',
            'videos_count': 'видео, видео, видео',
            'video_notes_count': 'кругляш, кругляша, кругляшей',
            'voices_count': 'войс, войса, войсов',
            'games_count': 'игра, игры, игр',
            'hashtags_count': 'хештег, хештега, хештегов',
            # 'bot_commands_count': 'команда боту, команды боту, команд боту',
            'urls_count': 'ссылка, ссылки, ссылок',
            'emails_count': 'электронная почта, электронные почты, электронных почт',
            'emoji_count': 'эмодзи, эмодзи, эмодзи',
        }
        counts = []
        for key, plural_variants in count_keys.items():
            count = getattr(stat, key, None)
            if count is None or count == 0 or count == '':
                continue
            msg = pytils.numeral.get_plural(count, plural_variants)
            # if key == 'text_messages_count':
            #     msg = '{msg} ({words}, {chars})'.format(
            #         msg=msg,
            #         words=pytils.numeral.get_plural(getattr(stat, 'words_count', 0), 'слово, слова, слов'),
            #         chars=pytils.numeral.get_plural(getattr(stat, 'chars_wo_space_count', 0),
            #                                         'символ без пробелов, символа без пробелов, символов без пробелов'))
            if key == 'text_messages_with_obscene_count':
                text_messages_count = getattr(stat, 'text_messages_count', 0)
                msg_percent = round(count / text_messages_count * 100)
                obscene_words_count = getattr(stat, 'obscene_words_count', 0)
                words_count = getattr(stat, 'words_count', 0)
                words_percent = obscene_words_count / words_count * 100
                obscene_words_count_str = pytils.numeral.get_plural(obscene_words_count, 'матерное слово, матерных слова, матерных слов')
                msg = f'{msg}, {msg_percent}% ({obscene_words_count_str}, {words_percent:.2f}%)'
            if key == 'voices_count' or key == 'video_notes_count':
                msg = '{msg} (длительностью {duration})'.format(
                    msg=msg,
                    duration=cls.__format_duration(getattr(stat, key.replace('_count', '_duration'), 0)))
            counts.append(msg)
        counts_result = ''
        if len(counts) > 0:
            counts_sorted = sorted(counts, reverse=True, key=lambda s: int(s.split(' ')[0]))
            counts_result = '{}'.format(',\n'.join(counts_sorted)) + '.'

        # реплаи
        replies_keys_order = ['sent_replies_count', 'received_replies_count', 'sent_mentions_count',
                              'received_mentions_count']
        replies_keys = {
            'sent_replies_count': 'реплай отправлен, реплая отправлено, реплаев отправлено',
            'received_replies_count': 'реплай получен, реплая получено, реплаев получено',
            'sent_mentions_count': (
                'раз тегала сама, раза тегала сама, раз тегала сама',
                'раз тегал сам, раза тегал сам, раз тегал сам'
            ),
            'received_mentions_count': (
                'раз тегали ее, раза тегали ее, раз тегали ее',
                'раз тегали его, раза тегали его, раз тегали его'
            ),
        }
        replies = []
        for key in replies_keys_order:
            plural_variants = replies_keys[key]
            if isinstance(plural_variants, tuple):
                plural_variants = plural_variants[0] if user.female else plural_variants[1]
            count = getattr(stat, key, None)
            if count is None or count == 0 or count == '':
                continue
            msg = pytils.numeral.get_plural(count, plural_variants)
            replies.append(msg)
        replies_result = ''
        if len(replies) > 0:
            replies_result = ',\n'.join(replies) + '.'

        # домены
        top_domain = ''
        if stat.top_domain is not None and stat.top_domain != '':
            top_domain = '{count} упомянут домен {domain}'.format(
                count=pytils.numeral.get_plural(
                    UserDomains.get_user_domain_count(monday, uid, cid, stat.top_domain),
                    'раз, раза, раз',
                    absence='Чаще всего'
                ),
                domain=stat.top_domain)

        # результат
        results = [x for x in [counts_result, replies_result, top_domain] if x != '']
        return "\n\n".join(results)

    @classmethod
    def me_format_position(cls, username, group_msg_count, position, user_id):
        user = User.get(user_id)
        if not user:
            return f'Нет такого: {username}'
        uname = '{}'.format(user.get_username_or_link())
        pos = ''
        if position != -1:
            pos = '{}. '.format(position)
        msg = '{2}{0} — {1}'.format(uname, group_msg_count, pos)
        return msg

    @classmethod
    def number_format(cls, num, places=0):
        return locale.format("%.*f", (places, num), True)

    @classmethod
    def stat_format(cls,
                    chat_title,
                    msg_count,
                    users_count,
                    users_count_caption,
                    top_chart,
                    top_chart_caption,
                    count_percent=None):
        msg = '<b>{0}</b>\n' \
              '{1}: {2}\n' \
              'Сообщений: {3}\n'.format(chat_title, users_count_caption, users_count, msg_count)
        if count_percent:
            msg += 'От общего количества: {}%\n'.format(count_percent)
        msg += '\n'
        if top_chart is not '':
            msg += '{0}:\n{1}\n'.format(top_chart_caption, top_chart)
        return msg

    @classmethod
    def get_chat_stats(cls, cid, date=None):
        last_monday = get_current_monday() if date is None else get_date_monday(date)
        try:
            with session_scope() as db:
                # noinspection PyUnresolvedReferences
                q = db.query(UserStatDB, UserDB) \
                    .filter(UserStatDB.stats_monday == last_monday) \
                    .filter(UserStatDB.uid == UserDB.uid) \
                    .filter(UserStatDB.cid == cid) \
                    .filter(UserStatDB.all_messages_count > 0) \
                    .order_by(UserStatDB.all_messages_count.desc()) \
                    .all()
            return [(UserStat.copy(userstat), User.copy(user)) for userstat, user in q]
        except Exception:
            return []

    @classmethod
    def get_chat(cls, cid, date=None, fullstat=False, salo=False, tag_salo=False, mat=False):
        if cid > 0:
            return {'users_count': 0, 'top_chart': '', 'msg_count': 0, 'percent': 0}
        msg_count_percent = 100
        top_chart = ''
        uids = []
        last_monday = get_current_monday() if date is None else get_date_monday(date)
        all_msg_count = cls.__get_all_msg_count(last_monday, cid)

        q = []
        try:
            with session_scope() as db:
                # noinspection PyUnresolvedReferences
                q = db.query(UserStatDB, UserDB) \
                    .filter(UserStatDB.stats_monday == last_monday) \
                    .filter(UserStatDB.uid == UserDB.uid) \
                    .filter(UserStatDB.cid == cid) \
                    .filter(UserStatDB.all_messages_count > 0) \
                    .order_by(UserStatDB.all_messages_count.desc()) \
                    .all()
                q = [(UserStat.copy(userstat), User.copy(user)) for userstat, user in q]
        except Exception as e:
            logger.error(e)
        if len(q) == 0:
            return {'users_count': 0, 'top_chart': '', 'msg_count': 0, 'percent': 0, 'uids': []}

        user_position = 0
        asc_msg_count = 0
        if salo:
            q = q[::-1]

        magic_percent = 100
        q_all_length = len(q)  # if type(q) is list else len(q.all())
        if not salo and q_all_length > 25:
            magic_percent = 146

        for user_stat, user in q:
            count = user_stat.all_messages_count
            user_position += 1
            asc_msg_count += count
            raw_percent = count * magic_percent / all_msg_count
            percent = cls.number_format(raw_percent, 2)
            user_mat = '' if not mat else cls.__get_user_mat(user_stat)
            top_chart += f"<b>{user_position}. {user.fullname}</b> — <b>{count}</b> ({percent}%){user_mat}\n"
            uids.append(user.uid)
            if not fullstat and user_position >= CONFIG['top_users_num']:
                break
            if salo and count > 15:
                break

        if not salo:
            users_count = q_all_length
        else:
            users_count = user_position
            all_users: typing.List[ChatUser] = []
            try:
                all_users = ChatUserDB.get_all(cid)
            except Exception as e:
                logger.error(e)
            active_user_ids = [x.uid for _, x in q]
            silent_lines = []
            for chat_user in all_users:
                if chat_user.uid not in active_user_ids:
                    user = User.get(chat_user.uid)
                    if user is not None:
                        username_if_salo = ' @{}'.format(user.username) if tag_salo else ''
                        silent_lines.append("<b>{}</b>{}\n".format(user.fullname, username_if_salo))
            if len(silent_lines) > 0:
                top_chart += "\nСовсем молчуны:\n"
                top_chart += ''.join(silent_lines)
            else:
                top_chart += "\nСовсем молчунов нет 🙊\n"

        if not fullstat or salo:
            msg_count_percent = cls.number_format(asc_msg_count * 100 / all_msg_count, 2)
            all_msg_count = asc_msg_count

        return {
            'users_count': users_count,
            'top_chart': top_chart,
            'msg_count': all_msg_count,
            'percent': msg_count_percent,
            'uids': uids
        }

    @staticmethod
    def __get_user_mat(stat) -> str:
        obscene_count = getattr(stat, 'text_messages_with_obscene_count', 0)
        if obscene_count == 0:
            return ''
        text_messages_count = getattr(stat, 'text_messages_count', 0)
        msg_percent = round(obscene_count / text_messages_count * 100)
        obscene_words_count = getattr(stat, 'obscene_words_count', 0)
        words_count = getattr(stat, 'words_count', 0)
        words_percent = obscene_words_count / words_count * 100
        # msg = f'.\nС матом: {obscene_count} ({msg_percent}%). Матерных слов: {obscene_words_count} ({words_percent:.2f}%)'
        msg = f'. Мат: {obscene_count} ({msg_percent}%)'
        return msg

    @classmethod
    def get_user_position(cls, user_id, cid, date):
        position = -1
        msg_count = 0
        last_monday = get_current_monday() if date is None else get_date_monday(date)

        try:
            with session_scope() as db:
                # noinspection PyUnresolvedReferences
                q = db.query(UserStatDB, UserDB) \
                    .filter(UserStatDB.stats_monday == last_monday) \
                    .filter(UserStatDB.uid == UserDB.uid) \
                    .filter(UserStatDB.cid == cid) \
                    .filter(UserStatDB.all_messages_count > 0) \
                    .order_by(UserStatDB.all_messages_count.desc()) \
                    .all()
                q = [(UserStat.copy(userstat), User.copy(user)) for userstat, user in q]
            if q:
                position = 0
                for userstat, user in q:
                    position += 1
                    if userstat.uid == user_id:
                        msg_count = userstat.all_messages_count
                        break
        except Exception as e:
            logger.error(e)
        return {
            'position': position,
            'msg_count': msg_count
        }

    @classmethod
    def get_top_kroshka(cls, cid, date=None):
        """
        :rtype: User
        """
        last_monday = get_current_monday() if date is None else get_date_monday(date)
        try:
            with session_scope() as db:
                # noinspection PyUnresolvedReferences
                q = db.query(UserStatDB, UserDB) \
                    .filter(UserStatDB.stats_monday == last_monday) \
                    .filter(UserStatDB.uid == UserDB.uid) \
                    .filter(UserStatDB.cid == cid) \
                    .filter(UserStatDB.emoji_count > 0) \
                    .order_by(UserStatDB.emoji_count.desc()) \
                    .all()
                q = [(UserStat.copy(userstat), User.copy(user)) for userstat, user in q]
            if not q:
                return None
        except Exception as e:
            logger.error(e)
            return None

        # получаем соотношение количества эмодзи к сообщениям
        users_by_emoji = {}
        for user_stat, user in q:
            count = user_stat.all_messages_count
            # учитываем только тек, кто написал от 30 сообщений
            if count < 30 or user_stat.words_count < 500:
                continue
            users_by_emoji[user.uid] = user_stat.emoji_count / count

        if len(users_by_emoji) > 0:
            uid, _ = random.choice(sort_dict(users_by_emoji)[:10])
        else:
            _, user = random.choice(q)
            uid = user.uid
        user = User.get(uid)
        return user

    # @staticmethod
    # def __add_all_msg_count_cache(monday, cid):
    #     key = 'all_msg_{}_{}'.format(monday.strftime("%Y%m%d"), cid)
    #     cached = cache.incr(key)
    #     if cached is None:
    #         cache.set(key, str(1))

    @staticmethod
    def __get_all_msg_count(monday, cid):
        # key = 'all_msg_{}_{}'.format(monday.strftime("%Y%m%d"), cid)
        # cached = cache.get(key)
        # if cached is not None:
        #     return int(cached)

        try:
            with session_scope() as db:
                q = db.query(func.sum(UserStatDB.all_messages_count)) \
                    .filter(UserStatDB.stats_monday == monday) \
                    .filter(UserStatDB.cid == cid) \
                    .all()[0][0]
            if q is None:
                # cache.set(key, str(0), time=USER_CACHE_EXPIRE)
                return 0
        except Exception as e:
            logger.error(e)
            return 0
        count = int(q)
        # cache.set(key, str(count), time=USER_CACHE_EXPIRE)
        return count

    @staticmethod
    def __update(old_stat, added_stat):
        update = {}
        if added_stat.last_activity is not None:
            old_stat.last_activity = added_stat.last_activity
            update['last_activity'] = added_stat.last_activity
        if added_stat.score > 0:
            old_stat.score = added_stat.score
            update['score'] = added_stat.score
        if added_stat.top_domain is not None:
            old_stat.top_domain = added_stat.top_domain
            update['top_domain'] = added_stat.top_domain

        for key in old_stat.__dict__.keys():
            if key.startswith('_'):
                continue
            if not key.endswith('_count') and not key.endswith('_duration'):
                continue
            old_value = getattr(old_stat, key, 0)
            new_value = getattr(added_stat, key, 0)
            if new_value > 0:
                update[key] = old_value + new_value
                setattr(old_stat, key, update[key])

        try:
            UserStatDB.update_db(added_stat, update)
        except Exception as e:
            logger.error(e)
            raise
        return old_stat

    @staticmethod
    def parse_message_stat(uid, cid, message, entities):
        result = UserStat()
        result.uid = uid
        result.cid = cid
        result.last_activity = message.date
        result.all_messages_count = 1

        if message.reply_to_message is not None:
            result.sent_replies_count = 1
            reply_stat = UserStat(received_replies_count=1)
            reply_stat.uid = message.reply_to_message.from_user.id
            reply_stat.cid = cid
            UserStat.add(reply_stat)

        for entity, entity_text in entities.items():
            if entity.type == 'mention':
                result.sent_mentions_count = result.sent_mentions_count + 1
                username = entity_text.lstrip('@').strip()
                try:
                    mentioned_user = UserDB.get_by_username(username)
                    if mentioned_user:
                        mentioned_stat = UserStat(received_mentions_count=1)
                        mentioned_stat.uid = mentioned_user.uid
                        mentioned_stat.cid = cid
                        UserStat.add(mentioned_stat)
                except Exception as e:
                    logger.error(e)
                continue
            if entity.type == 'hashtag':
                result.hashtags_count = result.hashtags_count + 1
                continue
            if entity.type == 'bot_command':
                result.bot_commands_count = result.bot_commands_count + 1
                continue
            if entity.type == 'email':
                result.emails_count = result.emails_count + 1
                continue
            if entity.type == 'url':
                result.urls_count = result.urls_count + 1
                result.top_domain = UserDomains.update_user_top_domain(uid, cid, entity_text)
                continue

        # True - если это форвард чужого сообщения
        # нам тогда не нужно учитывать статистику текста
        foreign_forward = False
        if message.forward_date is not None:
            result.forwards_count = 1
            if message.forward_from is None or message.forward_from.id != uid:
                foreign_forward = True

        if message.text is not None and not foreign_forward:
            result.text_messages_count = 1
            obscene_words_count = Antimat.bad_words_count(message.text)
            if obscene_words_count > 0:
                result.text_messages_with_obscene_count = 1
            result.obscene_words_count = result.obscene_words_count + obscene_words_count
            result.words_count = result.words_count + len(message.text.split())
            result.chars_count = result.chars_count + len(message.text)
            result.chars_wo_space_count = result.chars_wo_space_count + result.chars_count - message.text.count(' ')
            result.emoji_count = len([e for e in message.text if e in emoji.UNICODE_EMOJI])

        if message.audio is not None:
            result.audios_count = 1

        if message.document is not None:
            if message.document.mime_type == 'video/mp4' or (
                    message.document.file_name is not None and message.document.file_name.endswith('.gif')):
                result.gifs_count = 1
            else:
                result.documents_count = 1

        if message.game is not None:
            result.games_count = 1

        if len(message.photo) > 0:
            result.photos_count = 1

        if message.sticker is not None:
            result.stickers_count = 1

        if message.video is not None:
            result.videos_count = 1

        if message.voice is not None and not foreign_forward:
            result.voices_count = 1
            result.voices_duration = message.voice.duration

        if message.video_note is not None and not foreign_forward:
            result.video_notes_count = 1
            result.video_notes_duration = message.video_note.duration

        if message.caption is not None and not foreign_forward:
            result.obscene_words_count = result.obscene_words_count + Antimat.bad_words_count(message.caption)
            result.words_count = result.words_count + len(message.caption.split())
            result.chars_count = result.chars_count + len(message.caption)
            result.chars_wo_space_count = result.chars_wo_space_count + result.chars_count - message.caption.count(' ')

        return result

    @staticmethod
    def __format_duration(seconds):
        t = timedelta(seconds=seconds)
        counts_key_order = ['days', 'hours', 'minutes', 'seconds']
        counts = {
            'days': int(t.days),
            'hours': int(t.seconds / (60 * 60)),
            'minutes': int((t.seconds % (60 * 60)) / 60),
            'seconds': int(t.seconds % 60),
        }
        plural_variants = {
            'days': 'день, дня, дней',
            'hours': 'час, часа, часов',
            'minutes': 'минута, минуты, минут',
            'seconds': 'секунда, секунды, секунд',
        }
        for key in counts_key_order:
            value = counts[key]
            if value > 0:
                return pytils.numeral.get_plural(value, plural_variants[key])

        return '0 секунд'

    @staticmethod
    def __get_cache_key(monday, uid, cid):
        return f'userstat:{monday.strftime("%Y%m%d")}:{cid}:{uid}'


class UserDomains:
    lock = Lock()

    @staticmethod
    def __parse_domain(url):
        parsed_uri = urlparse(url if '://' in url else 'http://{}'.format(url))
        domain = '{uri.netloc}'.format(uri=parsed_uri)
        return domain[:254]  # чтобы влезло в строку в бд

    @classmethod
    def update_user_top_domain(cls, uid, cid, url):
        domain = cls.__parse_domain(url)

        # в мемкеше хранятся все домены пользователя за текущую неделю с количеством использований
        monday = get_current_monday()
        with cls.lock:
            cache_key = cls.__get_user_domain_cache_key(monday, uid, cid)
            user_domains = cache.get(cache_key)
            if user_domains is None:
                user_domains = {}
            user_domains.setdefault(domain, 0)
            user_domains[domain] = user_domains[domain] + 1
            cache.set(cache_key, user_domains, time=USER_CACHE_EXPIRE)

        # самый часто используемый домен
        top_domain = max(user_domains, key=user_domains.get)
        return top_domain

    @classmethod
    def get_user_domain_count(cls, monday, uid, cid, domain):
        user_domains = cache.get(cls.__get_user_domain_cache_key(monday, uid, cid))
        if user_domains is None:
            return 0
        if domain in user_domains:
            return user_domains[domain]
        return 0

    @staticmethod
    def __get_user_domain_cache_key(monday, uid, cid):
        return f'userdomains:{monday.strftime("%Y%m%d")}:{cid}:{uid}'
