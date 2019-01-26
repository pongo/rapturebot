import random
import textwrap
from typing import List, Tuple, Union, Optional, Set

import telegram
from telegram.ext import run_async

from src.modules.models.chat_user import ChatUser
from src.modules.models.user import User
from src.plugins.valentine_day.model import VUnknownUser, VChatsUser, VChat, command_val, \
    CardDraftSelectHeart, Button, CACHE_PREFIX, MODULE_NAME, \
    DraftHeartButton, CardDraftSelectChat, DraftChatButton, \
    RevnButton, MigButton, AboutButton, Card, all_hearts
from src.utils.cache import cache, TWO_DAYS
from src.utils.callback_helpers import get_callback_data
from src.utils.mwt import MWT

callbacks = {}
HTML = telegram.ParseMode.HTML


@run_async
def callback_handler(bot: telegram.Bot, update: telegram.Update,
                     query: telegram.CallbackQuery, data) -> None:
    if data['value'] not in callbacks:
        return
    if 'module' not in data or data['module'] != MODULE_NAME:
        return
    callbacks[data['value']](bot, update, query, data)


@run_async
def val(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Обработчик команды /val в личке бота
    """
    message: telegram.Message = update.message
    user_id = message.from_user.id
    from_user = get_vuser(user_id)
    entities = message.parse_entities().items()
    mentions = get_mentions(entities)
    text_html = remove_first_command(replace_text_mentions(message.text, entities))

    answer = command_val(text_html, mentions, from_user, get_random_hearts(user_id))

    if isinstance(answer, str):
        bot.send_message(user_id, answer, parse_mode=HTML)
        return

    if isinstance(answer, CardDraftSelectHeart):
        cache.set(f'{CACHE_PREFIX}:draft:card:{user_id}', answer, time=TWO_DAYS)
        bot.send_message(user_id, answer.get_message_text(),
                         reply_markup=get_reply_markup(answer.get_message_buttons()),
                         parse_mode=HTML)


def draft_heart_button_click_handler(bot: telegram.Bot, _: telegram.Update,
                                     query: telegram.CallbackQuery, data) -> None:
    """
    Обработчик кнопки выбора сердечка
    """
    user_id = query.from_user.id

    draft: Optional[CardDraftSelectHeart] = cache.get(f'{CACHE_PREFIX}:draft:card:{user_id}')
    if draft is None or not isinstance(draft, CardDraftSelectHeart):
        query.answer(text='Черновик не найден')
        query.message.delete()
        return

    heart: str = data['heart']
    chat_names = {chat.chat_id: get_chat_title(bot, chat.chat_id)
                  for chat in draft.from_user.chats}
    answer = draft.select_heart(heart, chat_names)

    cache.set(f'{CACHE_PREFIX}:draft:card:{user_id}', answer, time=TWO_DAYS)
    query.edit_message_text(text=answer.get_message_text(), parse_mode=HTML)
    query.edit_message_reply_markup(reply_markup=get_reply_markup(answer.get_message_buttons()))
    query.answer()


def draft_chat_button_click_handler(bot: telegram.Bot, _: telegram.Update,
                                    query: telegram.CallbackQuery, data) -> None:
    """
    Обработчик кнопки выбора чата
    """
    user_id = query.from_user.id

    draft: Optional[CardDraftSelectChat] = cache.get(f'{CACHE_PREFIX}:draft:card:{user_id}')
    if draft is None or not isinstance(draft, CardDraftSelectChat):
        query.answer(text='Черновик не найден')
        query.message.delete()
        return

    key_delayed = f'{CACHE_PREFIX}:delayed:{user_id}'
    if cache.get(key_delayed):
        query.answer(text='Отправляй раз в минуту. Жди 👆')
        return
    cache.set(key_delayed, True, time=60)

    chat_id: int = data['chat_id']
    card = draft.select_chat(chat_id)

    msg = bot.send_message(chat_id, card.get_message_text(),
                           reply_markup=get_reply_markup(card.get_message_buttons()),
                           parse_mode=HTML,
                           disable_web_page_preview=True)
    card.message_id = msg.message_id
    cache.set(f'{CACHE_PREFIX}:card:{chat_id}:{card.message_id}', card, time=TWO_DAYS)
    clear_random_hearts(user_id)
    query.message.delete()
    bot.send_message(user_id, 'Открытка отправлена!')
    query.answer()


class Store:
    def __init__(self, query: telegram.CallbackQuery):
        self.query = query
        self.message: telegram.Message = query.message
        self.user_id: int = query.from_user.id
        self.chat_id = self.message.chat_id
        self.message_id: int = self.message.message_id
        self.card: Optional[Card] = None

    def load(self) -> bool:
        """
        Загружает карточку из редиса и возвращает True, если она существует
        """
        self.card = cache.get(self._card_key())
        if self.card is None:
            self.query.answer('Закончилась Луна-красотка')
            return False
        return True

    def save(self) -> None:
        cache.set(self._card_key(), self.card, time=TWO_DAYS)

    def is_already_clicked(self, button_name: str) -> bool:
        return cache.get(self._already_clicked_key(button_name), False)

    def mark_as_already_clicked(self, button_name: str) -> None:
        cache.set(self._already_clicked_key(button_name), True, time=TWO_DAYS)

    def update_buttons(self) -> None:
        try:
            reply_markup = get_reply_markup(self.card.get_message_buttons())
            self.query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception:
            pass

    def _already_clicked_key(self, button_name: str) -> str:
        return f'{self._card_key()}:{button_name}:{self.user_id}'

    def _card_key(self) -> str:
        return f'{CACHE_PREFIX}:card:{self.chat_id}:{self.message_id}'


def revn_button_click_handler(_: telegram.Bot, __: telegram.Update,
                              query: telegram.CallbackQuery, ___) -> None:
    """
    Обработчик кнопки ревности
    """
    store = Store(query)
    if not store.load():
        return

    button_name = 'revn_clicked'
    result = store.card.revn(store.user_id, store.is_already_clicked(button_name))

    if result.success:
        store.mark_as_already_clicked(button_name)
        store.save()
        store.update_buttons()
    query.answer(result.text)


def mig_button_click_handler(bot: telegram.Bot, _: telegram.Update,
                             query: telegram.CallbackQuery, __) -> None:
    """
    Обработчик кнопки подмигивания
    """
    store = Store(query)
    if not store.load():
        return

    button_name = 'mig_clicked'
    to_user = User.get(store.user_id)
    result = store.card.mig(store.user_id, store.is_already_clicked(button_name), 
                            to_user.get_username_or_link())

    query.answer(result.text)
    if result.success:
        store.mark_as_already_clicked(button_name)
        try:
            bot.send_message(store.card.from_user.user_id, result.notify_text, parse_mode=HTML)
        except Exception:
            pass


def about_button_click_handler(bot: telegram.Bot, _: telegram.Update,
                               query: telegram.CallbackQuery, __) -> None:
    text = textwrap.dedent(
        """
        Сегодня 14 февраля. Все отправляют валентинки! 

        Тоже хотите? Напишите /help боту в личку.
        """).strip()
    bot.answer_callback_query(query.id, text, show_alert=True)


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


def remove_first_command(text: str) -> str:
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


def get_man_name(user_id: int) -> str:
    random.seed(user_id)
    name = random.choice(('Орзик', 'Девочка', 'Мальчик', 'Человек'))
    random.seed()
    return name


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


callbacks[DraftHeartButton.CALLBACK_NAME] = draft_heart_button_click_handler
callbacks[DraftChatButton.CALLBACK_NAME] = draft_chat_button_click_handler
callbacks[RevnButton.CALLBACK_NAME] = revn_button_click_handler
callbacks[MigButton.CALLBACK_NAME] = mig_button_click_handler
callbacks[AboutButton.CALLBACK_NAME] = about_button_click_handler
