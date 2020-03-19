import re
from functools import wraps
from random import randint
from typing import List, Tuple, Optional

import telegram
from telegram.ext import run_async

from src.config import CONFIG
from src.models.chat_user import ChatUser
from src.models.user import User
from src.utils.cache import cache
from src.utils.callback_helpers import get_callback_data
from src.utils.logger_helpers import get_logger
from src.utils.mwt import MWT
from src.utils.telegram_helpers import telegram_retry

logger = get_logger(__name__)
CACHE_PREFIX = 'spoiler'
MODULE_NAME = CACHE_PREFIX


def extend_initial_data(data: dict) -> dict:
    initial = {"name": CACHE_PREFIX, "module": MODULE_NAME}
    result = {**initial, **data}
    return result


class ChatHelper:
    @classmethod
    @MWT(timeout=5 * 60)  # 5m
    def get_user_chats(cls, uid: int) -> List[int]:
        return ChatUser.get_user_chats(uid, cids=[CONFIG['anon_chat_id']])

    @classmethod
    @MWT(timeout=5 * 60)  # 5m
    def get_chat_title(cls, bot: telegram.Bot, cid: int) -> str:
        chat = bot.get_chat(cid)
        return chat.title if chat.title else str(cid)


class Guard:
    @classmethod
    def deco_handler_guard(cls, f):
        @wraps(f)
        def decorator(_cls, bot: telegram.Bot, update: telegram.Update):
            message = update.edited_message if update.edited_message else update.message
            uid = message.from_user.id
            if len(ChatHelper.get_user_chats(uid)) == 0:
                return
            return f(_cls, bot, update)

        return decorator


class TelegramWrapper:
    chat_id = CONFIG['anon_chat_id']

    @classmethod
    @telegram_retry(logger=logger, silence=True, default=None, title='spoiler_send_message')
    def send_message(cls,
                     bot: telegram.Bot,
                     text: str,
                     chat_id: int = chat_id,
                     buttons=None,
                     reply_to_message_id=None,
                     disable_web_page_preview=True) -> Optional[int]:
        if chat_id == 0:
            return None
        reply_markup = cls.get_reply_markup(buttons)
        message = bot.send_message(
            chat_id,
            text,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
            parse_mode=telegram.ParseMode.HTML,
            disable_web_page_preview=disable_web_page_preview,
            timeout=20)
        return message.message_id

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


class Spoiler:
    callback_show = 'spoiler_show_click'
    callback_reply = 'spoiler_reply_click'

    def __init__(self, uid: int, cid: int, header: str, body: str) -> None:
        self.uid = uid
        self.cid = cid
        self.header = header
        self.body = body
        self.spoiler_id = self.__generate_id()
        self.msg_id = None

    def send(self, bot: telegram.Bot) -> bool:
        buttons = self.get_buttons()
        small_spoiler = len(self.body) <= 200
        text = self.__get_header_text(self.uid, self.header, small_spoiler)
        self.msg_id = TelegramWrapper.send_message(bot, text, chat_id=self.cid, buttons=buttons)
        if not self.msg_id:
            return False

        cache.set(self.__get_key(self.spoiler_id), self)
        return True

    def get_buttons(self):
        return self.__get_buttons(self.spoiler_id)

    def show(self, bot: telegram.Bot, uid: int) -> bool:
        header = self.__get_header_text(self.uid, self.header)
        text = f'{header}\n\n{self.body}'
        msg_id = TelegramWrapper.send_message(bot, text, chat_id=uid,
                                              disable_web_page_preview=False)
        if not msg_id:
            return False
        return True

    # def prepare_reply(self, bot: telegram.Bot, uid: int) -> bool:
    #     raise NotImplementedError
    #     Видимо создать класс ReplyCreator
    #     Создать в кеше сообщ на 5 минут. Если отвечает пока оно живо - значит сразу реплаем
    #     Так же создать более долгое на час. Если отвечает при нем, то показывать кнопку уточнение
    #     Кроме того в самом сообщении "Пришлите ответ. Он отобразится как спойлер" нужно показывать кнопку отмены

    @classmethod
    def on_show_click(cls, bot: telegram.Bot, _: telegram.Update, query: telegram.CallbackQuery,
                      data) -> None:
        spoiler: Spoiler = cache.get(cls.__get_key(data['spoiler_id']))
        if not spoiler:
            bot.answer_callback_query(query.id,
                                      f"Ошибка. Не могу найти спойлер {data['spoiler_id']}",
                                      show_alert=True)
            return

        uid = query.from_user.id
        if len(spoiler.body) <= 200:
            bot.answer_callback_query(query.id, spoiler.body, show_alert=True)
            logger.info(f'[spoiler] {uid} show popup spoiler {spoiler.spoiler_id}')
            return

        bot.answerCallbackQuery(query.id, url=f"t.me/{bot.username}?start={query.data}")
        if not spoiler.show(bot, uid):
            cls.__cant_send(bot, query.message.chat_id, uid, spoiler.spoiler_id)
            return
        logger.info(f'[spoiler] {uid} show private spoiler {spoiler.spoiler_id}')

    @classmethod
    def __cant_send(cls, bot: telegram.Bot, chat_id: int, uid: int, spoiler_id: int) -> None:
        logger.info(f"[spoiler] {uid} can't show spoiler {spoiler_id}")
        user = User.get(uid)
        username = '' if not user else user.get_username_or_link()
        text = f'{username} Не могу отправить спойлер. Нажми Start в личке бота \
@{bot.username} и попробуй вновь'
        bot.send_message(chat_id, text, parse_mode=telegram.ParseMode.HTML)

    # @classmethod
    # def on_reply_click(cls, bot: telegram.Bot, _: telegram.Message, query: telegram.CallbackQuery, data) -> None:
    #     uid = query.from_user.id
    #     spoiler: Spoiler = cache.get(cls.__get_key(data['spoiler_id']))
    #     if not spoiler:
    #         bot.answer_callback_query(query.id, f"Ошибка. Не могу найти спойлер #{data['spoiler_id']}", show_alert=True)
    #         return
    #     if spoiler.prepare_reply(bot, uid):
    #         bot.answerCallbackQuery(query.id)
    #     else:
    #         bot.answerCallbackQuery(query.id, 'Не могу отправить. Нажмите Start в личке бота и попробуйте вновь', show_alert=True)

    @classmethod
    def __get_buttons(cls, spoiler_id: int):
        show_data = extend_initial_data({'value': cls.callback_show, 'spoiler_id': spoiler_id})
        # reply_data = extend_initial_data({'value': cls.callback_reply, 'spoiler_id': spoiler_id})
        buttons = [
            # [('Показать', show_data), ('Ответить', reply_data)],
            [('Показать', show_data)],
        ]
        return buttons

    @staticmethod
    def __get_key(spoiler_id: int) -> str:
        return f'{CACHE_PREFIX}:spoilers:{spoiler_id}'

    @classmethod
    def __generate_id(cls) -> int:
        digits = 8
        for count in range(0, 1000):
            range_start = 10 ** (digits - 1)
            range_end = (10 ** digits) - 1
            card_id = randint(range_start, range_end)
            # убедимся, что id уникален
            if not cache.get(cls.__get_key(card_id)):
                return card_id
        raise Exception("Can't generate id")

    @classmethod
    def __get_header_text(cls, uid: int, header: str, small_spoiler: bool = False) -> str:
        user = User.get(uid)
        name = 'анонима' if not user else user.fullname
        small = 'Короткий спойлер' if small_spoiler else 'Спойлер'
        return f'<b>{small} от {name}</b>\n\n{header}'


class SpoilerCreator:
    @classmethod
    def text_handler(cls, bot: telegram.Bot, update: telegram.Update) -> None:
        message = update.edited_message if update.edited_message else update.message
        text = message.text
        if not text:
            return
        uid = message.from_user.id
        cid = CONFIG['anon_chat_id']

        text = re.sub(r"\s*/spoiler\s*", "", text)
        text = text.strip()
        header, body = cls.__split_text(text)
        if header == '' or body == '':
            return

        spoiler = Spoiler(uid, cid, header, body)
        if not spoiler.send(bot):
            bot.send_message(uid, 'Не удалось отправить. Попробуйте еще раз')
            return

    @classmethod
    def __split_text(cls, text: str) -> Tuple[str, str]:
        """
        Делим текст на первую строку и остальные
        """
        lines = text.splitlines()
        if len(lines) == 0:
            return '', ''
        first, rest = lines[0], ('\n'.join(lines[1:])).strip()
        return first, rest


class SpoilerHandlers:
    callbacks = {
        Spoiler.callback_show: Spoiler.on_show_click,
        # Spoiler.callback_reply: Spoiler.on_reply_click,
    }

    @classmethod
    @Guard.deco_handler_guard
    @run_async
    def private_handler(cls, bot: telegram.Bot, update: telegram.Update) -> None:
        SpoilerCreator.text_handler(bot, update)

    @classmethod
    def callback_handler(cls, bot: telegram.Bot, update: telegram.Update,
                         query: telegram.CallbackQuery, data) -> None:
        if 'module' not in data or data['module'] != MODULE_NAME:
            return
        if data['value'] not in cls.callbacks:
            return
        cls.callbacks[data['value']](bot, update, query, data)
