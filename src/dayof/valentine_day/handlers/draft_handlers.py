from typing import Optional

import telegram

from src.dayof.valentine_day.handlers.stats_redis import StatsRedis
from src.dayof.valentine_day.helpers.helpers import get_reply_markup, clear_random_hearts, \
    get_vuser, \
    get_mentions, replace_text_mentions, get_random_hearts, get_chat_title
from src.dayof.valentine_day.model import command_val, \
    CardDraftSelectHeart, CACHE_PREFIX, CardDraftSelectChat
from src.utils.cache import cache, TWO_DAYS

HTML = telegram.ParseMode.HTML


def private_text_handler(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Обработчик текста в личке бота
    """
    message: telegram.Message = update.message
    user_id = message.from_user.id
    from_user = get_vuser(user_id)
    entities = message.parse_entities().items()
    mentions = get_mentions(entities)
    text_html = replace_text_mentions(message.text, entities)

    answer = command_val(text_html, mentions, from_user, get_random_hearts(user_id))

    if isinstance(answer, str):
        bot.send_message(user_id, answer, parse_mode=HTML)
        return

    if isinstance(answer, CardDraftSelectHeart):
        answer.original_draft_message_id = message.message_id
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
    answer.original_draft_message_id = draft.original_draft_message_id

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

    card_in_chat_msg = bot.send_message(
        chat_id, card.get_message_text(),
        reply_markup=get_reply_markup(card.get_message_buttons()),
        parse_mode=HTML, disable_web_page_preview=True)
    card.message_id = card_in_chat_msg.message_id

    with StatsRedis.lock:
        with StatsRedis() as stats:
            stats.add_card(card)

    query.message.delete()

    status_message: telegram.Message = bot.send_message(
        user_id, 'Валентинка отправлена!', reply_to_message_id=draft.original_draft_message_id
    )
    card.original_draft_message_id = draft.original_draft_message_id
    card.status_message_id = status_message.message_id
    cache.set(f'{CACHE_PREFIX}:card:{chat_id}:{card.message_id}', card, time=TWO_DAYS)

    clear_random_hearts(user_id)
    query.answer()
