import telegram
from telegram.ext import run_async

from src.plugins.valentine_day.date_checker import is_day_active
from src.plugins.valentine_day.handlers.card_handlers import revn_button_click_handler, \
    mig_button_click_handler, about_button_click_handler
from src.plugins.valentine_day.handlers.draft_handlers import draft_heart_button_click_handler, \
    draft_chat_button_click_handler, private_text_handler
from src.plugins.valentine_day.model import MODULE_NAME, \
    DraftHeartButton, DraftChatButton, \
    RevnButton, MigButton, AboutButton

HTML = telegram.ParseMode.HTML


class ValentineDay:
    callbacks = {
        DraftHeartButton.CALLBACK_NAME: draft_heart_button_click_handler,
        DraftChatButton.CALLBACK_NAME: draft_chat_button_click_handler,
        RevnButton.CALLBACK_NAME: revn_button_click_handler,
        MigButton.CALLBACK_NAME: mig_button_click_handler,
        AboutButton.CALLBACK_NAME: about_button_click_handler
    }

    @classmethod
    @run_async
    def callback_handler(cls, bot: telegram.Bot, update: telegram.Update,
                         query: telegram.CallbackQuery, data) -> None:
        if data['value'] not in cls.callbacks:
            return
        if 'module' not in data or data['module'] != MODULE_NAME:
            return
        if not is_day_active():
            bot.answer_callback_query(query.id, 'Все уже закончилось', show_alert=True)
            return
        cls.callbacks[data['value']](bot, update, query, data)

    @staticmethod
    @run_async
    def private_text_handler(bot: telegram.Bot, update: telegram.Update) -> None:
        if not is_day_active():
            return
        private_text_handler(bot, update)
