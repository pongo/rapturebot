import telegram
from telegram.ext import run_async

from src.config import CONFIG
from src.modules.dayof.helper import set_today_special
from src.plugins.valentine_day.date_checker import is_day_active, is_today_ending
from src.plugins.valentine_day.handlers.card_handlers import revn_button_click_handler, \
    mig_button_click_handler, about_button_click_handler
from src.plugins.valentine_day.handlers.draft_handlers import draft_heart_button_click_handler, \
    draft_chat_button_click_handler, private_text_handler
from src.plugins.valentine_day.handlers.stats_redis import StatsRedis
from src.plugins.valentine_day.model import MODULE_NAME, \
    DraftHeartButton, DraftChatButton, \
    RevnButton, MigButton, AboutButton, CACHE_PREFIX, StatsHumanReporter
from src.utils.cache import cache, TWO_DAYS

HTML = telegram.ParseMode.HTML


def send_end(bot: telegram.Bot) -> None:
    if not cache.get(f'{CACHE_PREFIX}:end:admin', False):
        with StatsRedis() as stats:
            text = StatsHumanReporter(stats).get_text(None)
        bot.send_message(CONFIG.get('debug_uid', None), text, parse_mode=telegram.ParseMode.HTML)
        cache.set(f'{CACHE_PREFIX}:end:admin', True, time=TWO_DAYS)


class ValentineDay:
    callbacks = {
        DraftHeartButton.CALLBACK_NAME: draft_heart_button_click_handler,
        DraftChatButton.CALLBACK_NAME: draft_chat_button_click_handler,
        RevnButton.CALLBACK_NAME: revn_button_click_handler,
        MigButton.CALLBACK_NAME: mig_button_click_handler,
        AboutButton.CALLBACK_NAME: about_button_click_handler
    }

    @classmethod
    def midnight(cls, bot: telegram.Bot) -> None:
        """
        Показывает ночные приветственное и подводящее итоги сообщения
        """
        if is_day_active():
            set_today_special()
            # DayBegin.send(bot)
        if is_today_ending():
            send_end(bot)


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
