# coding=UTF-8
import collections
import functools
import hashlib
import re
import textwrap
from datetime import datetime
from functools import wraps
from random import randint
from typing import Optional, List, Tuple

import telegram
from pytils.numeral import get_plural

from src.config import CONFIG
from src.modules.dayof.helper import set_today_special
from src.modules.models.chat_user import ChatUser
from src.modules.models.user import User
from src.utils.cache import cache, USER_CACHE_EXPIRE, pure_cache
from src.utils.callback_helpers import get_callback_data
from src.utils.logger_helpers import get_logger
from src.utils.misc import get_int
from src.utils.misc import retry
from src.utils.text_helpers import lstrip_every_line

logger = get_logger(__name__)
CACHE_PREFIX = 'valentine_day'
MODULE_NAME = 'valentine_day'
HEARTS = ['♥️', '❤️', '💛', '💚', '💙', '💜', '🖤', '💔']

SENT_TITLE = '<b>Отправлено</b>'


def extend_initial_data(data: dict) -> dict:
    initial = {"name": 'dayof', "module": MODULE_NAME}
    result = {**initial, **data}
    return result


class DateChecker:
    @staticmethod
    def is_day_active() -> bool:
        """
        Сегодня 14-е фев?
        """
        # TODO: убрать
        if CONFIG.get('feb14_debug_begin', False):
            return True
        return datetime.today().strftime(
            "%m-%d") == '02-14'  # месяц-день. Первое января будет: 01-01

    @staticmethod
    def is_today_ending() -> bool:
        """
        Сегодня 15-е фев?
        """
        # TODO: убрать
        if CONFIG.get('feb14_debug_end', False):
            return True
        return datetime.today().strftime("%m-%d") == '02-15'


class Guard:
    @classmethod
    def handlers_guard(cls, f):
        @wraps(f)
        def decorator(_cls, bot: telegram.Bot, update: telegram.Update):
            message = update.edited_message if update.edited_message else update.message
            uid = message.from_user.id
            if not DateChecker.is_day_active():
                return
            if not ChatUser.get(uid, CONFIG['anon_chat_id']):
                return
            return f(_cls, bot, update)

        return decorator

    @classmethod
    def callback_handler_guard(cls, f):
        @wraps(f)
        def decorator(_cls, bot: telegram.Bot, update: telegram.Update, query, data):
            if not DateChecker.is_day_active():
                bot.answer_callback_query(query.id, 'Все уже закончилось', show_alert=True)
                return
            return f(_cls, bot, update, query, data)

        return decorator


class TelegramWrapper:
    chat_id = CONFIG['anon_chat_id']

    @classmethod
    @retry(logger=logger)
    def send_message(cls,
                     bot: telegram.Bot,
                     text: str,
                     chat_id: int = chat_id,
                     buttons=None,
                     reply_to_message_id=None) -> Optional[int]:
        if chat_id == 0:
            return
        reply_markup = cls.get_reply_markup(buttons)
        try:
            message = bot.send_message(
                chat_id,
                text,
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id,
                parse_mode=telegram.ParseMode.HTML,
                disable_web_page_preview=True,
                timeout=20)
            cache.set(f'{CACHE_PREFIX}:messages:{chat_id}:{message.message_id}:text',
                      message.text_html, time=USER_CACHE_EXPIRE)
            cache.set(f'{CACHE_PREFIX}:messages:{chat_id}:{message.message_id}:buttons', buttons,
                      time=USER_CACHE_EXPIRE)
            return message.message_id
        except Exception as e:
            logger.error(f"[{MODULE_NAME}] Can't send message to {chat_id}. Exception: {e}")
            if str(e) == 'Timed out':
                raise Exception(e)
            return None

    @classmethod
    def edit_message(cls,
                     bot: telegram.Bot,
                     message_id: int,
                     text: str,
                     chat_id: int = chat_id,
                     buttons=None) -> None:
        if chat_id == 0:
            return
        reply_markup = cls.get_reply_markup(buttons)
        try:
            bot.edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=reply_markup,
                parse_mode=telegram.ParseMode.HTML,
                disable_web_page_preview=True)
            cache.set(f'{CACHE_PREFIX}:messages:{chat_id}:{message_id}:text', text,
                      time=USER_CACHE_EXPIRE)
            cache.set(f'{CACHE_PREFIX}:messages:{chat_id}:{message_id}:buttons', buttons,
                      time=USER_CACHE_EXPIRE)
        except Exception as e:
            logger.error(f"[{MODULE_NAME}] Can't edit message from {chat_id}. Exception: {e}")

    @classmethod
    def edit_buttons(cls, bot: telegram.Bot, message_id: int, buttons,
                     chat_id: int = chat_id) -> None:
        if chat_id == 0:
            return
        reply_markup = cls.get_reply_markup(buttons)
        try:
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=reply_markup)
            cache.set(f'{CACHE_PREFIX}:messages:{chat_id}:{message_id}:buttons', buttons,
                      time=USER_CACHE_EXPIRE)
        except Exception as e:
            logger.error(f"[{MODULE_NAME}] Can't edit buttons in {chat_id}. Exception: {e}")

    @staticmethod
    def get_reply_markup(buttons) -> Optional[telegram.InlineKeyboardMarkup]:
        """
        Инлайн-кнопки под сообщением
        """
        if not buttons:
            return None
        keyboard = []
        for line in buttons:
            keyboard.append([
                telegram.InlineKeyboardButton(
                    button_title,
                    callback_data=(get_callback_data(button_data)))
                for button_title, button_data in line
            ])
        return telegram.InlineKeyboardMarkup(keyboard)

    @classmethod
    def answer_callback_query_with_bot_link(cls, bot: telegram.Bot, query_id, query_data) -> None:
        bot.answer_callback_query(query_id, url=f"t.me/{bot.username}?start={query_data}")


class CmdHelp:
    @classmethod
    def send(cls, bot: telegram.Bot, uid: int) -> None:
        TelegramWrapper.send_message(bot, cls.__get_text(), chat_id=uid)

    @staticmethod
    def __get_text() -> str:
        return textwrap.dedent(
            f"""
            <em>It might not be the right time.</em>
            <em>I might not be the right one.</em>
            <em>But there's something about us I want to say.</em>
            <em>Cause there's something between us anyway.</em>
            
            Эх, любовь-любовь, какое чувство! Ох уж эта химия, это притяжение двух сердец. Мне-то, боту 🤖, холодной бездушной машине, никогда этого не понять. Но я постараюсь помочь моему пользователю выразить свою любовь. Ну, или легкую симпатию, если вы не выносите нежностей.
            
            <b>Отправка валентинки</b>
            
            Самый простой вариант — напишите текст валентинки прямо сюда, не забыв указать @username получателя. Я покажу вам как она будет выглядеть, и вы сможете отправить ее. После этого валентинка появится в чате, при этом ваше имя не будет указано.
            
            На валентинке будут специальные кнопки:
            
            • <b>поревновать</b> — вам придет сообщение, что такой-то ревнует. На кнопке указано количество ревнивцев. 
            • <b>подмигнуть</b> — я сообщу, если адресат вам подмигнул. Сама кнопка не изменится.
            
            В любом случае, ваше имя останется в тайне. Кстати, валентинок вы можете отправить любое количество. Почему бы и нет?
            
            <b>Анонимный сайт</b>
            
            Мой автор уверяет, что все отправители останутся в тайне. Но для самых матерых параноидальных анонимов заведен специальный сайт для отправки валентинок:
            
            https://rapture14.surge.sh
            
            Если отправлять через него, то даже я, 🤖, не буду знать кто вы. Это так печально 😥. Единственный минус: уведомления о подмигиваниях тоже придется проверять через сайт, ведь я не буду знать вашего юзернейма.
            
            <b>Готовы?</b>
            
            Сегодня не время тянуть! Напишите валентинку.
            """).strip()


class DayBegin:
    callback_name = 'day_begin_btn'

    @classmethod
    def send(cls, bot: telegram.Bot):
        team = cls.__get_team(CONFIG['anon_chat_id'])
        text = textwrap.dedent(
            f"""
            <b>14 февраля</b>

            Сегодня в чате отмечается День всех влюбленных! В этот прекрасный день сам бог рептилий велит вашему сердцу признаваться в любви ♥. 
            
            Или напишите приятное тем, кто вам <em>платонически</em> симпатичен. Даже если вы мужик 👨🏻 и хотите написать другому мужику 👨🏾. В этом нет ничего <em>такого</em> 🌋.

            А еще можете отправить <b>чорную</b> валентинку всякому мудачью, АХАХАХА 😈

            В празднике примет участие наш замечательный коллектив: {team}.

            Как отправить валентинку? Напишите <code>/help</code> боту в личку.
            """).strip()

        data = extend_initial_data({'value': cls.callback_name})
        buttons = [
            [('Отправить валентинку (нажмите там Start)', data)]
        ]
        TelegramWrapper.send_message(bot, text, buttons=buttons)

    # noinspection PyUnusedLocal
    @classmethod
    @Guard.callback_handler_guard
    def btn_click(cls, bot: telegram.Bot, update: telegram.Message, query: telegram.CallbackQuery,
                  data):
        TelegramWrapper.answer_callback_query_with_bot_link(bot, query.id, query.data)
        CmdHelp.send(bot, query.from_user.id)

    @classmethod
    def __get_team(cls, chat_id: int) -> str:
        """
        Возвращает строку с "коллективом" чата.

        Пример: "30 👨, 10 👩, 2 👘, 1 🍍, 2 🦆, 1 🐽, 3 🏳️‍🌈, 3 🐈, 4 🐕, 5 🐀"
        """

        # Итоговая строка должна состоять из двух частей:
        # 1. количество мужчин/женщин (берется из настоящих данных)
        # 2. жестко зафиксированная "специальная часть"

        # нам нужно подсчитать количество людей, задействованных в спец части
        # и вычесть это количество из общего списка
        special = '2 👘, 1 🍍, 2 🦆, 1 🐽, 3 🏳️‍🌈, 3 🐈, 2 🐕, 5 🐀'
        special_count = 2 + 1 + 2 + 1 + 3 + 3 + 2 + 5
        chat_users = ChatUser.get_all(chat_id)
        uids = [chat_user.uid for chat_user in chat_users][:-special_count or None]  # вычитаем

        # теперь нужно подсчитать сколько мужчин и женщин осталось
        users = (User.get(uid) for uid in uids)
        genders = ('👩' if user.female else '👨' for user in users if user)
        # noinspection PyArgumentList
        gender_counter = collections.Counter(genders)
        gender_text = ', '.join(
            (f'{count} {gender}' for gender, count in gender_counter.most_common()))

        # собираем итоговую строку
        return f'{gender_text}, {special}'.strip(',').strip()


class DayEnd:
    callback_like = 'day_end_like_click'
    callback_dislike = 'day_end_dislike_click'

    class Poll:
        def __init__(self, chat_id: int):
            self.key_prefix = f'{CACHE_PREFIX}:end_poll:{chat_id}'

        def get_count(self) -> Tuple[int, int]:
            likes = len(cache.get(f'{self.key_prefix}:like', []))
            dislikes = len(cache.get(f'{self.key_prefix}:dislike', []))
            return likes, dislikes

        def like(self, uid: int) -> bool:
            can_vote = self.__incr('all', uid)
            if can_vote:
                return self.__incr('like', uid)
            return False

        def dislike(self, uid: int) -> bool:
            can_vote = self.__incr('all', uid)
            if can_vote:
                return self.__incr('dislike', uid)
            return False

        def __incr(self, type: str, uid: int) -> bool:
            key = f'{self.key_prefix}:{type}'
            uids: List[int] = cache.get(key, [])
            if uid in uids:
                return False
            uids.append(uid)
            cache.set(key, uids, time=USER_CACHE_EXPIRE)
            return True

    @classmethod
    def send(cls, bot: telegram.Bot) -> None:
        stats = Stats.get_stats()
        text = lstrip_every_line(textwrap.dedent(
            f"""
            <b>День закончился, но не любовь.</b> А теперь сухая статистика:
            
            {stats}
            """)).strip()
        TelegramWrapper.send_message(bot, text, buttons=cls.__get_buttons())

    @classmethod
    def __get_buttons(cls, likes: int = 0, dislikes: int = 0):
        text1 = 'Отличный день' if likes == 0 else f'{likes} — Отличный день'
        text2 = 'Ненавижу 14-ое' if dislikes == 0 else f'{dislikes} — Ненавижу 14-ое'
        data1 = extend_initial_data({'value': cls.callback_like})
        data2 = extend_initial_data({'value': cls.callback_dislike})
        buttons = [
            [(text1, data1), (text2, data2)]
        ]
        return buttons

    @classmethod
    def on_poll_click(cls, bot: telegram.Bot, _: telegram.Update, query: telegram.CallbackQuery,
                      data):
        uid = query.from_user.id
        message_id = query.message.message_id
        chat_id = query.message.chat_id
        poll = cls.Poll(chat_id)
        if data['value'] == cls.callback_like:
            voted = poll.like(uid)
            text = '❤️'
        elif data['value'] == cls.callback_dislike:
            voted = poll.dislike(uid)
            text = '💔'
        else:
            bot.answer_callback_query(query.id, 'Вы сюда как попали???')
            return
        if not voted:
            bot.answer_callback_query(query.id, 'Только один раз')
            return
        bot.answer_callback_query(query.id, text)
        likes, dislikes = poll.get_count()
        buttons = cls.__get_buttons(likes, dislikes)
        TelegramWrapper.edit_buttons(bot, message_id, buttons, chat_id)


class AntiPlagiat:
    """
    Проверяет, чтобы все валентинки были уникальными в пределах одного чата.

    Для проверки уникальности мы храним хеш, полученный при помощи SHA512.
    """

    @classmethod
    def is_plagiat(cls, chat_id: int, text: str) -> bool:
        text_hash = cls.__get_hash(text)
        cached = cache.get(cls.__get_key(chat_id, text_hash))
        if cached:
            return True
        return False

    @classmethod
    def add_text(cls, chat_id: int, text: str) -> None:
        text_hash = cls.__get_hash(text)
        cache.set(cls.__get_key(chat_id, text_hash), True, time=USER_CACHE_EXPIRE)

    @classmethod
    def __get_hash(cls, text: str) -> str:
        return hashlib.sha512(cls.__prepare_text(text)).hexdigest()

    @classmethod
    def __prepare_text(cls, orig: str) -> bytes:
        return re.sub(r"(@\w+)", '', orig, 0, re.IGNORECASE).strip().encode('utf-8')

    @staticmethod
    def __get_key(chat_id: int, text_hash: str) -> str:
        return f'{CACHE_PREFIX}:texts_by_chat:{chat_id}:{text_hash}'


# class AntiPlagiat:
#     """
#     Проверяет, чтобы все валентинки были уникальными.
#     """
#     @classmethod
#     def is_plagiat(cls, chat_id: int, text: str) -> bool:
#         text = cls.__prepare_text(text)
#         texts = cls.__get_texts(chat_id)
#         if text in texts:
#             return True
#         return False
#
#     @classmethod
#     def add_text(cls, chat_id: int, text: str) -> None:
#         text = cls.__prepare_text(text)
#         texts = cls.__get_texts(chat_id)
#         texts.add(text)
#         cache.set(cls.__get_key(chat_id), texts, time=USER_CACHE_EXPIRE)
#
#     @classmethod
#     def __prepare_text(cls, orig: str) -> str:
#         return re.sub(r"(@\w+)", "", orig, 0, re.IGNORECASE)
#
#     @classmethod
#     def __get_texts(cls, chat_id: int) -> set:
#         texts = cache.get(cls.__get_key(chat_id))
#         texts = set() if not texts else set(texts)
#         return texts
#
#     @staticmethod
#     def __get_key(chat_id: int) -> str:
#         return f'{CACHE_PREFIX}:texts_by_chat:{chat_id}'


class OneStat:
    def __init__(self, name):
        self.key = f'{CACHE_PREFIX}:stats:{name}'

    def incr(self, amount: int = 1) -> None:
        pure_cache.incr(self.key, amount)

    def get(self) -> int:
        # return randint(0, 100)
        return pure_cache.get_int(self.key, 0)


class HeartsStat:
    def __init__(self):
        self.key_prefix = f'total:hearts'

    def incr(self, heart_index: int, amount: int = 1) -> None:
        OneStat(f'{self.key_prefix}:{heart_index}').incr(amount)

    def get(self, heart_index: int) -> int:
        return OneStat(f'{self.key_prefix}:{heart_index}').get()


class UidsStats:
    def __init__(self, name):
        self.key = f'{CACHE_PREFIX}:stats:uids:{name}'

    def add(self, uid: int) -> None:
        cached: set = cache.get(self.key, set())
        if uid in cached:
            return
        cached.add(uid)
        cache.set(self.key, cached, time=USER_CACHE_EXPIRE)

    def get(self) -> List[int]:
        # return [user.uid for user in ChatUser.get_all(-1001088799794)]
        return list(cache.get(self.key, []))


class Stats:
    total_cards = OneStat('total:cards')  # сколько валентинок отправлено
    total_migs = OneStat('total:migs')  # сколько подмигиваний отправлено
    total_revn = OneStat('total:revn')  # сколько ревности отправлено
    hearts_stats = HeartsStat()  # сколько валентинок с каждым видом сердечек отправлено
    senders = UidsStats('senders')
    migs_users = UidsStats('migs_users')
    revn_users = UidsStats('revn_users')

    @classmethod
    def get_stats(cls) -> str:
        total = cls.__get_total()
        gender = cls.__get_gender_stats()
        hearts = cls.__get_hearts_stats()
        text = lstrip_every_line(textwrap.dedent(
            f"""
            {total}

            {gender}
            
            {hearts}
            """)).strip()
        return text

    @classmethod
    def __get_total(cls) -> str:
        stats = [
            get_plural(cls.total_cards.get(),
                       'валентинка отправлена, валентинки отправлено, валентинок отправлено'),
            get_plural(cls.total_migs.get(),
                       'подмигивание произведено, подмигивания произведено, подмигиваний произведено'),
            get_plural(cls.total_revn.get(),
                       'ревность источена, ревности источено, ревностей источено'),
        ]
        text = ''.join((f'• {stat}\n' for stat in stats if stat)).strip()
        return text

    @classmethod
    def __get_gender_stats(cls) -> str:
        uids = cls.senders.get()
        users = (User.get(uid) for uid in uids)
        genders = ('👩' if user.female else '👨' for user in users if user)
        # noinspection PyArgumentList
        gender_counter = collections.Counter(genders)
        gender_stats = ', '.join(
            (f'{count} {gender}' for gender, count in gender_counter.most_common()))
        text = f'Валентинки отправляли: {gender_stats}.'
        return text

    @classmethod
    def __get_hearts_stats(cls) -> str:
        stats = ', '.join(
            f'{cls.hearts_stats.get(index)} {heart}' for index, heart in enumerate(HEARTS))
        return f'Валентинки по виду сердечка: {stats}.'


class ReactionNotification:
    callback_show_card = 'reaction_show_card'

    @classmethod
    def send(cls, bot: telegram.Bot, uid: int, text: str, card: 'Card') -> None:
        # msg = f"{text}\n<em>Валентинка отправлена в {card.time.strftime('%H:%M')} (по Москве)</em>"
        msg = text
        buttons = [
            [(f"Показать валентинку ({card.time.strftime('%H:%M')})",
              extend_initial_data({'value': cls.callback_show_card, 'card_id': card.card_id}))]
        ]
        TelegramWrapper.send_message(bot, msg, uid, buttons=buttons)

    @classmethod
    def on_show_card_click(cls, bot: telegram.Bot, _: telegram.Message,
                           query: telegram.CallbackQuery, data) -> None:
        """
        Показываем текст валентинки
        """
        card: Card = cache.get(f"{CACHE_PREFIX}:cards:{data['card_id']}")
        if not card:
            bot.answer_callback_query(query.id,
                                      f"Ошибка. Не могу найти открытку #{data['card_id']}",
                                      show_alert=True)
            return

        msg = textwrap.shorten(card.text, 190, placeholder='…')
        try:
            bot.answer_callback_query(query.id, msg, show_alert=True)
        except Exception:
            pass


class Card:
    callback_revn = 'card_revn_click'
    callback_mig = 'card_mig_click'
    callback_about = 'card_about_click'

    def __init__(self, bot: telegram.Bot, chat_id: int, from_uid: int, to_uid: int, text: str,
                 orig_text: str, preview_message_id: int, heart_index: int = 0):
        self.bot = bot
        self.chat_id = chat_id
        self.from_uid = from_uid
        self.to_uid = to_uid
        self.text = text
        self.chat_text = f'{text}\n\n#валентин'
        self.orig_text = orig_text
        self.heart_index = heart_index
        self.card_id = self.__generate_card_id()
        self.preview_message_id = preview_message_id
        self.message_id = None
        self.mig_uids = []
        self.revn_uids = []
        self.time = datetime.now()

    def send(self, bot: telegram.Bot) -> bool:
        buttons = self.get_buttons()
        self.time = datetime.now()
        self.message_id = TelegramWrapper.send_message(bot, self.chat_text, chat_id=self.chat_id,
                                                       buttons=buttons)
        if not self.message_id:
            return False

        AntiPlagiat.add_text(self.chat_id, self.orig_text)
        Stats.total_cards.incr()
        Stats.senders.add(self.from_uid)
        Stats.hearts_stats.incr(self.heart_index)

        cache.set(self.__get_key(self.card_id), self, time=USER_CACHE_EXPIRE)
        return True

    def get_buttons(self):
        return self.__get_buttons(self.card_id, len(self.revn_uids))

    @classmethod
    def __get_buttons(cls, card_id: int, revn_count: int = 0):
        card_about_data = extend_initial_data({'value': cls.callback_about, 'card_id': card_id})
        revn_text = 'Поревновать' if revn_count == 0 else f'Поревновать — {revn_count}'
        revn_data = extend_initial_data({'value': cls.callback_revn, 'card_id': card_id})
        mig_data = extend_initial_data({'value': cls.callback_mig, 'card_id': card_id})
        buttons = [
            [(revn_text, revn_data), ('Подмигнуть', mig_data)],
            [('Что это?', card_about_data)]
        ]
        return buttons

    @classmethod
    @Guard.callback_handler_guard
    def on_about_click(cls, bot: telegram.Bot, _: telegram.Message, query: telegram.CallbackQuery,
                       __):
        text = textwrap.dedent(
            """
            Сегодня 14 февраля. Все отправляют валентинки! 
            
            Тоже хотите? Напишите /help боту в личку.
            """).strip()
        bot.answer_callback_query(query.id, text, show_alert=True)

    @classmethod
    @Guard.callback_handler_guard
    def on_mig_click(cls, bot: telegram.Bot, _: telegram.Message, query: telegram.CallbackQuery,
                     data):
        uid = query.from_user.id
        card: Card = cache.get(cls.__get_key(data['card_id']))
        if not card:
            bot.answer_callback_query(query.id,
                                      f"Ошибка. Не могу найти открытку #{data['card_id']}",
                                      show_alert=True)
            return

        if uid != card.to_uid:
            bot.answerCallbackQuery(query.id, 'Только адресат валентинки может подмигнуть 💔')
            return

        if uid in card.mig_uids:
            if User.get(uid).female:
                text = 'Подруга, ты уже подмигивала 💆'
            else:
                text = 'Дружище, ты уже подмигивал 💆‍♂️'
            bot.answerCallbackQuery(query.id, text)
            return

        card.mig_uids.append(uid)
        cache.set(cls.__get_key(card.card_id), card, time=USER_CACHE_EXPIRE)
        bot.answerCallbackQuery(query.id, 'Подмигивание прошло успешно')
        Stats.total_migs.incr()
        Stats.migs_users.add(uid)
        user = User.get(uid)
        username = user.get_username_or_link()
        ReactionNotification.send(bot, card.from_uid, f"{username} подмигивает тебе ❤", card)
        cls.__set_card_preview_as_done(bot, card)

    @classmethod
    @Guard.callback_handler_guard
    def on_revn_click(cls, bot: telegram.Bot, _: telegram.Message, query: telegram.CallbackQuery,
                      data) -> None:
        uid = query.from_user.id
        card: Card = cache.get(cls.__get_key(data['card_id']))
        if not card:
            bot.answer_callback_query(query.id,
                                      f"Ошибка. Не могу найти открытку #{data['card_id']}",
                                      show_alert=True)
            return

        # уже ревновали?
        if uid in card.revn_uids:
            if User.get(uid).female:
                text = 'Подруга, да забудь ты про эту сучку 🍸'
            else:
                text = 'Дружище, да забей ты на эту сучку 🍺'
            bot.answerCallbackQuery(query.id, text)
            return

        card.revn_uids.append(uid)
        cache.set(cls.__get_key(card.card_id), card, time=USER_CACHE_EXPIRE)
        Stats.total_revn.incr()
        Stats.revn_users.add(uid)
        user = User.get(uid)
        if uid == card.to_uid:
            bot.answerCallbackQuery(query.id, 'Саша, ты? 👸')
        else:
            if user.female:
                text = 'Вот она сучка, да? Уж мы-то ей покажем 👗'
            else:
                text = 'Ха! Мы-то с тобой знаем, кто тут круче всех 👑'
            bot.answerCallbackQuery(query.id, text)

        username = user.get_username_or_link()
        to_username = '' if not User.get(card.to_uid) else User.get(
            card.to_uid).get_username_or_link()
        ReactionNotification.send(bot, card.to_uid, f"{username} ревнует к валентинке для тебя",
                                  card)
        ReactionNotification.send(bot, card.from_uid, f"{username} ревнует к {to_username}", card)
        cls.__update_buttons(bot, card)

    @classmethod
    def __update_buttons(cls, bot: telegram.Bot, card: 'Card') -> None:
        TelegramWrapper.edit_buttons(bot, card.message_id, card.get_buttons(), card.chat_id)

    @staticmethod
    def __get_key(card_id: int) -> str:
        return f'{CACHE_PREFIX}:cards:{card_id}'

    @classmethod
    def __generate_card_id(cls) -> int:
        digits = 8
        for count in range(0, 1000):
            range_start = 10 ** (digits - 1)
            range_end = (10 ** digits) - 1
            card_id = randint(range_start, range_end)
            # убедимся, что id уникален
            if not cache.get(cls.__get_key(card_id)):
                return card_id
        raise Exception("Can't generate card id")

    @classmethod
    def __set_card_preview_as_done(cls, bot: telegram.Bot, card: 'Card') -> None:
        msg = f'{SENT_TITLE} ✅ Нам подмигнули!\n\n{card.text}'
        TelegramWrapper.edit_message(bot, card.preview_message_id, msg, chat_id=card.from_uid)


class CardPreview:
    callback_preview_heart_change = 'preview_heart_change'
    callback_preview_done = 'preview_done'

    @staticmethod
    def __get_key(from_uid):
        return f'{CACHE_PREFIX}:card_preview:{from_uid}'

    @classmethod
    def __get_text(cls, text: str, heart_index: int = 0, with_header=True,
                   title='<b>Предпросмотр</b>') -> str:
        try:
            heart = HEARTS[heart_index]
        except Exception:
            heart = HEARTS[0]

        header = '' if not with_header else 'Для изменения текста отправьте новое сообщение или измените старое. Можете выбрать цвет сердечка. Нажмите „Отправить“ когда все будет готово. Передумали и хотите начать заново — просто отправьте сообщение с новым текстом.'
        title = '' if not title else title
        return lstrip_every_line(textwrap.dedent(
            f"""
            {header}
            
            {title}
            
            {heart}  {text}  {heart}
            """)).strip()

    @classmethod
    def send_preview(cls, bot: telegram.Bot, chat_id: int, from_uid: int, to_uid: int, text: str):
        key = cls.__get_key(from_uid)
        cached = cache.get(key)
        heart_index = cls.__restore_last_heart_index(cached)
        if cached and not cached['done']:
            cls.__remove_header_and_title(bot, cached)
        msg = cls.__get_text(text, heart_index)
        message_id = TelegramWrapper.send_message(bot, msg, chat_id=from_uid,
                                                  buttons=cls.__get_buttons())
        if not message_id:
            return
        preview_data = {
            'chat_id': chat_id,
            'from_uid': from_uid,
            'to_uid': to_uid,
            'text': text,
            'preview_message_id': message_id,
            'heart_index': heart_index,
            'done': False,
        }
        cache.set(key, preview_data, time=USER_CACHE_EXPIRE)

    @staticmethod
    def __restore_last_heart_index(preview_data, default_index: int = 0) -> int:
        """
        Если мы еще не отправили валентинку, то возвращает последний используемый номер сердечка. А если уже отправили, то номер по-умолчанию
        """
        return default_index if not preview_data or preview_data['done'] else preview_data[
            'heart_index']

    @classmethod
    def __remove_header_and_title(cls, bot, preview_data):
        cls.__change_preview_title(bot, preview_data, '<em>Черновик</em>')

    @classmethod
    def __edit_preview(cls, bot: telegram.Bot, preview_data) -> None:
        msg = cls.__get_text(preview_data['text'], preview_data['heart_index'])
        TelegramWrapper.edit_message(bot, preview_data['preview_message_id'], msg,
                                     chat_id=preview_data['from_uid'], buttons=cls.__get_buttons())
        cache.set(cls.__get_key(preview_data['from_uid']), preview_data, time=USER_CACHE_EXPIRE)

    @classmethod
    @Guard.callback_handler_guard
    def preview_done_click(cls, bot: telegram.Bot, _: telegram.Message,
                           query: telegram.CallbackQuery, __):
        uid = query.from_user.id
        key = cls.__get_key(uid)

        key_delayed = f'{key}:delayed'
        if cache.get(key_delayed):
            bot.answer_callback_query(query.id, 'Ждите…')
            return
        cache.set(key_delayed, True, time=60)

        preview_data = cache.get(key)
        if not preview_data:
            bot.answer_callback_query(query.id,
                                      'Произошла ошибка. Отправьте текст валентинки повторно',
                                      show_alert=True)
            cache.delete(key_delayed)
            return

        # если валентинка уже отправлена, а пользователь жмет на кнопки прошлых предпросмотров
        if preview_data['done']:
            bot.answer_callback_query(query.id)
            cache.delete(key_delayed)
            return

        # пробуем отправить валентинку в чат
        text = cls.__get_text(preview_data['text'], preview_data['heart_index'], with_header=False,
                              title='')
        card = Card(bot, preview_data['chat_id'], preview_data['from_uid'], preview_data['to_uid'],
                    text,
                    preview_data['text'], preview_data['preview_message_id'],
                    heart_index=preview_data['heart_index'])
        if not CardCreator.send_card(bot, card):
            bot.answer_callback_query(query.id,
                                      'Произошла ошибка. Напишите текст валентинки повторно',
                                      show_alert=True)
            cache.delete(key_delayed)
            return

        # если отправилась, то нужно все подчистить
        bot.answer_callback_query(query.id, 'Успешно отправилось!')
        cls.__change_preview_title(bot, preview_data, SENT_TITLE)
        if not preview_data['done']:
            preview_data['done'] = True
            cache.set(cls.__get_key(preview_data['from_uid']), preview_data, time=USER_CACHE_EXPIRE)
        cache.delete(key_delayed)

    @classmethod
    def __change_preview_title(cls, bot, preview_data, title, with_header=False):
        text = cls.__get_text(preview_data['text'], preview_data['heart_index'],
                              with_header=with_header, title=title)
        TelegramWrapper.edit_message(bot, preview_data['preview_message_id'], text,
                                     chat_id=preview_data['from_uid'])

    @classmethod
    @Guard.callback_handler_guard
    def heart_click(cls, bot: telegram.Bot, _: telegram.Message, query: telegram.CallbackQuery,
                    data):
        uid = query.from_user.id
        preview_data = cache.get(cls.__get_key(uid))
        if not preview_data:
            bot.answer_callback_query(query.id,
                                      'Произошла ошибка. Отправьте текст валентинки повторно',
                                      show_alert=True)
            return
        bot.answer_callback_query(query.id)
        if preview_data['done']:
            return

        message_id = query.message.message_id
        if message_id != preview_data['preview_message_id']:
            return
        if preview_data['heart_index'] == data['heart']:
            return

        preview_data['heart_index'] = data['heart']
        cls.__edit_preview(bot, preview_data)

    @classmethod
    @functools.lru_cache(maxsize=1)
    def __get_buttons(cls):
        return [
            [(
                heart,
                extend_initial_data({'value': cls.callback_preview_heart_change, 'heart': index})
            ) for index, heart in enumerate(HEARTS)],
            [('Отправить в чат', extend_initial_data({'value': cls.callback_preview_done}))]
        ]


class CardValidator:
    class ValidationResult:
        def __init__(self, error: bool, error_msg=None, to_uid=None):
            self.error = error
            self.error_msg = error_msg
            self.to_uid = to_uid

    @classmethod
    def check_valid(cls, text: str, uid: Optional[int]) -> ValidationResult:
        # нужно вычислить адресата
        to_username = cls.extract_username(text)
        if not to_username:
            return cls.ValidationResult(True, 'Через @username укажи кому отправлять валентинку')

        to_user = cls.find_user(to_username, CONFIG['anon_chat_id'])
        if not to_user:
            return cls.ValidationResult(True, f'В чате нет такого: {to_username}')

        # TODO: раскомментировать
        user = User.get(uid)
        if user and uid == to_user.uid:
            female = 'а' if user.female else ''
            return cls.ValidationResult(True, f'Сам{female} себе? Печально 😢')

        # проверочки
        if AntiPlagiat.is_plagiat(CONFIG['anon_chat_id'], text):
            return cls.ValidationResult(True, 'Ой! А такая валентиночка уже есть. Как неудобно…')

        # и если все хорошо
        return cls.ValidationResult(False, None, to_user.uid)

    @staticmethod
    def extract_username(text: str) -> Optional[str]:
        match = re.search(r"(@\w+)", text, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def find_user(username: Optional[str], chat_id: int) -> Optional[User]:
        if not username:
            return None
        uid = User.get_id_by_name(username)
        if not uid:
            return None
        chat_user = ChatUser.get(uid, chat_id)
        if not chat_user:
            return None
        if chat_user.left:
            return None
        return User.get(uid)


class CardCreator:
    @classmethod
    def text_handler(cls, bot: telegram.Bot, update: telegram.Update) -> None:
        # принимаем как новые сообщения, так и измененные
        message = update.edited_message if update.edited_message else update.message
        text = message.text
        if not text:
            return
        text = text.strip()
        uid = message.from_user.id
        chat_id = CONFIG['anon_chat_id']

        validation = CardValidator.check_valid(text, uid)
        if validation.error:
            TelegramWrapper.send_message(bot, validation.error_msg, uid)
            return
        CardPreview.send_preview(bot, chat_id, uid, validation.to_uid, text)

    @classmethod
    def send_card(cls, bot: telegram.Bot, card: Card) -> bool:
        if not card.send(bot):
            return False
        return True


class Web:
    class ValidationResult:
        def __init__(self, fake: bool, error: bool, error_msg=None, to_uid=None):
            self.fake = fake
            self.error = error
            self.error_msg = error_msg
            self.to_uid = to_uid

    @classmethod
    def create(cls, bot: telegram.Bot, text: str, heart_index: int):
        if not DateChecker.is_day_active():
            return {
                'error': True,
                'error_msg': 'Сегодня не 14-е',
            }

        text = text.strip()
        uid = 0
        chat_id = CONFIG['anon_chat_id']

        validation = CardValidator.check_valid(text, None)
        if validation.error:
            return {
                'error': True,
                'error_msg': validation.error_msg,
            }

        # пробуем отправить в чат
        card_text = cls.__get_text(text, heart_index)
        card = Card(bot, chat_id, 0, validation.to_uid, card_text, text, 0, heart_index=heart_index)
        if not CardCreator.send_card(bot, card):
            return {
                'error': True,
                'error_msg': 'При отправке в чат произошла ошибка. Попробуйте еще раз',
            }

        # Успешно отправилась
        return {
            'error': False,
            'card_id': card.card_id
        }

    @classmethod
    def get_card(cls, card_id: int):
        card: Card = cache.get(f"{CACHE_PREFIX}:cards:{card_id}")
        if not card:
            return None
        user = User.get(card.to_uid)
        return {
            "chat_id": card.chat_id,
            "to_user": user.get_username_or_link() if user else str(card.to_uid),
            "text": card.orig_text,
            "heart_index": card.heart_index,
            "card_id": card.card_id,
            "migs": cls.__update_notifications(card.card_id, 'migs', card.mig_uids),
            "revns": cls.__update_notifications(card.card_id, 'revns', card.revn_uids),
            "time": card.time,
        }

    @classmethod
    def get_cards(cls, ids):
        result = []
        for id_str in ids:
            card_id = get_int(id_str)
            if not card_id:
                continue
            card = cls.get_card(card_id)
            if not card:
                continue
            result.append(card)
        return result

    @classmethod
    def __update_notifications(cls, card_id: int, type: str, uids: List[int]):
        key = f"{CACHE_PREFIX}:viewed:{card_id}:{type}"
        viewed = cache.get(key, [])
        updated = []
        result = []
        for uid in uids:
            updated.append(uid)
            user = User.get(uid)
            username = user.get_username_or_link() if User else str(uid)
            result.append({
                "user": username,
                "viewed": uid in viewed,
            })
        cache.set(key, updated, time=USER_CACHE_EXPIRE)
        return result

    @classmethod
    def __get_text(cls, text: str, heart_index: int) -> str:
        try:
            heart = HEARTS[heart_index]
        except Exception:
            heart = HEARTS[0]
        return f"{heart}  {text}  {heart}".strip()


class ValentineDay:
    callbacks = {
        DayBegin.callback_name: DayBegin.btn_click,
        CardPreview.callback_preview_done: CardPreview.preview_done_click,
        CardPreview.callback_preview_heart_change: CardPreview.heart_click,
        Card.callback_revn: Card.on_revn_click,
        Card.callback_mig: Card.on_mig_click,
        Card.callback_about: Card.on_about_click,
        ReactionNotification.callback_show_card: ReactionNotification.on_show_card_click,
        DayEnd.callback_like: DayEnd.on_poll_click,
        DayEnd.callback_dislike: DayEnd.on_poll_click,
    }

    @classmethod
    def midnight(cls, bot: telegram.Bot) -> None:
        """
        Показывает ночные приветственное и подводящее итоги сообщения.
        """
        if DateChecker.is_day_active():
            set_today_special()
            DayBegin.send(bot)
        if DateChecker.is_today_ending():
            DayEnd.send(bot)

    @classmethod
    def afternoon(cls, bot: telegram.Bot) -> None:
        """
        Дневное напоминание
        """
        if DateChecker.is_day_active():
            DayBegin.send(bot)

    @classmethod
    def callback_handler(cls, bot: telegram.Bot, update: telegram.Message,
                         query: telegram.CallbackQuery, data) -> None:
        if 'module' not in data or data['module'] != MODULE_NAME:
            return
        if data['value'] not in cls.callbacks:
            return
        cls.callbacks[data['value']](bot, update, query, data)

    @classmethod
    @Guard.handlers_guard
    def private_handler(cls, bot: telegram.Bot, update: telegram.Update):
        CardCreator.text_handler(bot, update)

    @classmethod
    @Guard.handlers_guard
    def private_help_handler(cls, bot: telegram.Bot, update: telegram.Update):
        """
        Обрабатывает команду /help
        """
        CmdHelp.send(bot, update.message.chat_id)
