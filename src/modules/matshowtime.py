# coding=UTF-8
import logging
import time
from random import randint
from threading import Lock
from typing import List, Union, Optional, Tuple

import telegram
from telegram.utils.promise import Promise

from src.config import CONFIG
from src.modules.antimat import Antimat
from src.utils.cache import pure_cache, TWO_YEARS, cache, MONTH
from src.utils.callback_helpers import get_callback_data
from src.utils.telegram_helpers import telegram_retry, dsp

logger = logging.getLogger(__name__)
CACHE_PREFIX = 'matshowtime'


def extend_initial_data(data: dict) -> dict:
    initial = {"name": CACHE_PREFIX, "module": CACHE_PREFIX}
    result = {**initial, **data}
    return result


def make_button(title, code_name, id, count=0) -> tuple:
    text = title if count == 0 else f'{title} {count}'
    data = extend_initial_data({'value': code_name, 'id': id})
    return text, data


class TelegramWrapper:
    @staticmethod
    def __get_message_from_promise(promise: Union[Promise, telegram.Message]) -> telegram.Message:
        if isinstance(promise, Promise):
            return promise.result(timeout=20)
        return promise

    @classmethod
    @telegram_retry(logger=logger, title=f'[{CACHE_PREFIX}] send_message')
    def send_message(cls,
                     bot: telegram.Bot,
                     text: str,
                     chat_id: int,
                     buttons=None,
                     reply_to_message_id=None) -> Optional[int]:
        reply_markup = cls.get_reply_markup(buttons)
        try:
            message = cls.__get_message_from_promise(bot.send_message(
                chat_id,
                text,
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id,
                parse_mode=telegram.ParseMode.HTML,
                disable_web_page_preview=True))
            # cache.set(f'{CACHE_PREFIX}:messages:{chat_id}:{message.message_id}:text', message.text_html, time=USER_CACHE_EXPIRE)
            return message.message_id
        except Exception as e:
            logger.error(f"[{CACHE_PREFIX}] Can't send message to {chat_id}. Exception: {e}")
            if str(e) == 'Timed out':
                raise Exception(e)
            return None

    @classmethod
    def edit_message(cls,
                     bot: telegram.Bot,
                     message_id: int,
                     text: str,
                     chat_id: int,
                     buttons=None) -> None:
        reply_markup = cls.get_reply_markup(buttons)
        try:
            bot.edit_message_text(
                text,
                chat_id,
                message_id,
                reply_markup=reply_markup,
                parse_mode=telegram.ParseMode.HTML,
                disable_web_page_preview=True)
            # cache.set(f'{CACHE_PREFIX}:messages:{chat_id}:{message_id}:text', text, time=USER_CACHE_EXPIRE)
            # cache.set(f'{CACHE_PREFIX}:messages:{chat_id}:{message_id}:buttons', buttons, time=USER_CACHE_EXPIRE)
        except Exception as e:
            logger.error(f"[{CACHE_PREFIX}] Can't edit message from {chat_id}. Exception: {e}")

    @classmethod
    def edit_buttons(cls, bot: telegram.Bot, message_id: int, buttons, chat_id: int) -> None:
        reply_markup = cls.get_reply_markup(buttons)
        try:
            bot.edit_message_reply_markup(chat_id, message_id, reply_markup=reply_markup, timeout=5)
            # cache.set(f'{CACHE_PREFIX}:messages:{chat_id}:{message_id}:buttons', buttons, time=USER_CACHE_EXPIRE)
        except Exception as e:
            logger.error(f"[{CACHE_PREFIX}] Can't edit buttons in {chat_id}. Exception: {e}")

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


class Poll:
    def __init__(self, telegram_message_id: int):
        self.key_prefix = f'{CACHE_PREFIX}:polls:likes:{telegram_message_id}'

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
        cache.set(key, uids, time=MONTH)
        return True


class ChannelMessage:
    lock = Lock()
    callback_like = 'matshowtime_like_click'
    callback_dislike = 'matshowtime_dislike_click'

    def __init__(self, words: List[str]):
        self.words = words
        self.text = None
        self.telegram_message_id = None
        self.id = self.__generate_id()
        self.likes = 0
        self.dislikes = 0

    def send(self, bot: telegram.Bot) -> None:
        self.text = self.__prepare_text()
        buttons = self.__get_buttons()
        self.telegram_message_id = TelegramWrapper.send_message(bot, self.text, matshowtime.channel_id, buttons)
        if not self.telegram_message_id:
            logger.error(f"[{CACHE_PREFIX}] Can't send message {self.id}")
            return
        self.__save()

    def __save(self):
        cache.set(self.__get_key(self.id), self, time=MONTH)

    @classmethod
    def get_msg(cls, id: int) -> Optional['ChannelMessage']:
        return cache.get(cls.__get_key(id))

    @classmethod
    def on_poll_click(cls, bot: telegram.Bot, _: telegram.Update, query: telegram.CallbackQuery, data) -> None:
        msg: ChannelMessage = cache.get(cls.__get_key(data['id']))
        if not msg:
            bot.answer_callback_query(query.id, 'Время голосования истекло')
            return

        uid = query.from_user.id
        telegram_message_id = query.message.message_id
        if msg.telegram_message_id != telegram_message_id:
            bot.answer_callback_query(query.id, 'Вы сюда как попали???')
            logger.warning(f'[{CACHE_PREFIX}] msg {telegram_message_id} access {uid}')
            return

        with cls.lock:
            poll = Poll(telegram_message_id)
            if data['value'] == cls.callback_like:
                voted = poll.like(uid)
                text = '👍'
            elif data['value'] == cls.callback_dislike:
                voted = poll.dislike(uid)
                text = '👎'
            else:
                bot.answer_callback_query(query.id, 'Вы сюда как попали???')
                logger.warning(f'[{CACHE_PREFIX}] msg {telegram_message_id} access {uid}')
                return

        if not voted:
            bot.answer_callback_query(query.id, 'Только один раз')
            return
        likes, dislikes = poll.get_count()
        msg.likes = likes
        msg.dislikes = dislikes
        dsp(cls.__update_buttons_and_answer, bot, msg, query, text)

    @classmethod
    def __update_buttons_and_answer(cls, bot, msg, query, text):
        start_time = time.time()
        msg.update_buttons(bot)
        try:
            bot.answer_callback_query(query.id, text)
        except Exception:
            pass
        elapsed_time = time.time() - start_time
        logger.info(f'update buttons finished in {int(elapsed_time * 1000)} ms')

    def __prepare_text(self) -> str:
        upper_words = ', '.join(self.words).upper()
        return f'<b>{upper_words}</b>'

    def __get_buttons(self):
        like = make_button('👍', self.callback_like, self.id, self.likes)
        dislike = make_button('👎', self.callback_dislike, self.id, self.dislikes)

        buttons = [
            [like, dislike],
        ]
        return buttons

    @staticmethod
    def __get_key(id: int) -> str:
        return f'{CACHE_PREFIX}:messages:{id}'

    def __generate_id(self) -> int:
        digits = 8
        for count in range(0, 1000):
            range_start = 10 ** (digits - 1)
            range_end = (10 ** digits) - 1
            id = randint(range_start, range_end)
            # убедимся, что id уникален
            if not cache.get(self.__get_key(id)):
                return id
        raise Exception(f"[{CACHE_PREFIX}] Can't generate id")

    def update_buttons(self, bot: telegram.Bot) -> None:
        self.__save()
        buttons = self.__get_buttons()
        TelegramWrapper.edit_buttons(bot, self.telegram_message_id, buttons, matshowtime.channel_id)


class Matshowtime:
    cache_key_words = f'{CACHE_PREFIX}:words'

    def __init__(self):
        self.channel_id = CONFIG.get('matshowtime', {}).get('channel_id', None)

    def send(self, bot: telegram.Bot, mat_words: List[str]) -> None:
        # если список слов пуст или в конфиге не указан канал
        if len(mat_words) == 0 or not self.channel_id:
            return
        # мы отправляем в канал только новые слова, которые еще не отправляли
        new_words = self.__only_new_words(mat_words)
        if len(new_words) == 0:
            return

        self.__save_words(new_words)
        self.__send_to_channel(bot, new_words)

    @staticmethod
    def __send_to_channel(bot: telegram.Bot, words: List[str]) -> None:
        msg = ChannelMessage(words)
        msg.send(bot)

    def __only_new_words(self, words: List[str]) -> List[str]:
        lower_words = [word.lower() for word in words]
        used_words = pure_cache.get_set(self.cache_key_words)
        not_used_words = set(lower_words) - used_words
        return list(not_used_words)

    def __save_words(self, new_words: List[str]) -> None:
        pure_cache.add_to_set(self.cache_key_words, new_words, time=TWO_YEARS)


class MatshowtimeHandlers:
    callbacks = {
        ChannelMessage.callback_like: ChannelMessage.on_poll_click,
        ChannelMessage.callback_dislike: ChannelMessage.on_poll_click,
    }

    @classmethod
    def cmd_mats(cls, bot: telegram.Bot, update: telegram.Update) -> None:
        uid = update.message.from_user.id
        # только админ бота может использовать команду
        if uid != CONFIG.get('debug_uid', None):
            return
        # получаем параметры команды (текст после "/mats ")
        text = update.message.text.partition(' ')[2].strip()
        if not text:
            return
        # получаем мат
        mat_words = list(word.lower() for word in Antimat.bad_words(text))
        if len(mat_words) == 0:
            return
        # отправляем мат
        matshowtime.send(bot, mat_words)

    @classmethod
    def callback_handler(cls, bot: telegram.Bot, update: telegram.Update, query: telegram.CallbackQuery, data) -> None:
        if 'module' not in data or data['module'] != CACHE_PREFIX:
            return
        if data['value'] not in cls.callbacks:
            return
        cls.callbacks[data['value']](bot, update, query, data)


matshowtime = Matshowtime()
