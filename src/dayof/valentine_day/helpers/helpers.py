import random
from typing import List, Tuple, Union, Optional, Set, Callable

import telegram

from src.config import get_config_chats
from src.models.chat_user import ChatUser
from src.models.user import User
from src.dayof.valentine_day.model import VUnknownUser, VChatsUser, VChat, Button, CACHE_PREFIX, \
    all_hearts
from src.utils.cache import cache, TWO_DAYS
from src.utils.callback_helpers import get_callback_data
from src.utils.logger_helpers import get_logger
from src.utils.mwt import MWT
from src.utils.telegram_helpers import dsp, telegram_retry

HTML = telegram.ParseMode.HTML
logger = get_logger(__name__)


def get_reply_markup(buttons: List[List[Button]]) -> Optional[telegram.InlineKeyboardMarkup]:
    """
    Инлайн-кнопки под сообщением
    """
    if not buttons:
        return None
    keyboard = []
    for line in buttons:
        keyboard.append([
            telegram.InlineKeyboardButton(
                button.title,
                callback_data=(get_callback_data(button.get_data())))
            for button in line
        ])
    return telegram.InlineKeyboardMarkup(keyboard)


def remove_first_word(text: str) -> str:
    return f'{text} '.split(' ', 1)[1].strip()


def replace_text_mentions(text: str, entities: List[Tuple[telegram.MessageEntity, str]]) -> str:
    new_text = text
    for entity, entity_text in reversed(list(entities)):
        if entity.type != 'text_mention':
            continue
        link = f'<a href="tg://user?id={entity.user.id}">{entity_text}</a>'
        new_text = new_text[:entity.offset] + link + new_text[entity.offset + entity.length:]
    return new_text


def get_mentions(entities: List[Tuple[telegram.MessageEntity, str]]) \
        -> Set[Union[VChatsUser, VUnknownUser]]:
    mentions = set()
    for entity, entity_text in entities:
        if entity.type == 'mention':
            user_id = User.get_id_by_name(entity_text)
        elif entity.type == 'text_mention':
            user_id = entity.user.id
        else:
            continue
        mentions.add(get_vuser(user_id))
    return mentions


def get_vuser(user_id: Optional[int]) -> Union[VUnknownUser, VChatsUser]:
    if user_id is None:
        return VUnknownUser()

    user = User.get(user_id)
    if user is None:
        return VUnknownUser(user_id)

    chats = {VChat(cid) for cid in get_user_chats(user_id)}
    return VChatsUser(user_id, chats, user.female)


@MWT(timeout=5 * 60)  # 5m
def get_user_chats(uid: int) -> List[int]:
    return ChatUser.get_user_chats(uid)


@MWT(timeout=5 * 60)  # 5m
def get_chat_title(bot: telegram.Bot, cid: int) -> str:
    chat = bot.get_chat(cid)
    return chat.title if chat.title else str(cid)


def get_random_hearts(user_id: int) -> List[str]:
    key = f'{CACHE_PREFIX}:draft:hearts:{user_id}'
    cached = cache.get(key)
    if cached:
        return cached
    hearts = random.choices(all_hearts, k=3)
    cache.set(key, hearts, time=TWO_DAYS)
    return hearts


def clear_random_hearts(user_id: int) -> None:
    cache.delete(f'{CACHE_PREFIX}:draft:hearts:{user_id}')


def get_username_or_link(user_id: int) -> str:
    user = User.get(user_id)
    if user:
        return user.get_username_or_link()
    return f'<a href="tg://user?id={user_id}">{user_id}</a>'


def send_to_all_chats(bot: telegram.Bot, key_name: str,
                      get_text: Callable[[int], str]) -> None:
    for chat in get_config_chats():
        chat_id = chat.chat_id
        chat_key = f'{CACHE_PREFIX}:{key_name}:{chat_id}'
        if cache.get(chat_key, False):
            continue
        dsp(send_html, bot, chat_id, get_text(chat_id))
        cache.set(chat_key, True, time=TWO_DAYS)


@telegram_retry(logger=logger, silence=False, default=None, title='send_replay')
def send_html(bot: telegram.Bot, chat_id: int, text: str) -> telegram.Message:
    return bot.send_message(chat_id, text, parse_mode=HTML)
