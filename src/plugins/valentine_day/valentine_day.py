import telegram
from telegram.ext import run_async

from src.config import CONFIG, get_config_chats
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
from src.utils.logger_helpers import get_logger
from src.utils.telegram_helpers import telegram_retry, dsp

HTML = telegram.ParseMode.HTML
logger = get_logger(__name__)


@telegram_retry(logger=logger, silence=False, default=None, title='send_replay')
def send_html(bot: telegram.Bot, chat_id: int, text: str) -> telegram.Message:
    return bot.send_message(chat_id, text, parse_mode=HTML)


def send_end(bot: telegram.Bot) -> None:
    """
    Отправка во все чаты подводящих итог сообщений
    """
    with StatsRedis() as stats:
        # отправка админу статы по всем чатам
        admin_key = f'{CACHE_PREFIX}:end:admin'
        if not cache.get(admin_key, False):
            text = StatsHumanReporter(stats).get_text(None)
            dsp(send_html, bot, CONFIG.get('debug_uid', None), text)
            cache.set(admin_key, True, time=TWO_DAYS)

        # отправка в чаты
        for chat in get_config_chats():
            chat_id = chat.chat_id
            chat_key = f'{CACHE_PREFIX}:end:{chat_id}'
            if cache.get(chat_key, False):
                continue
            stats_text = StatsHumanReporter(stats).get_text(chat_id)
            text = f'Отгремело шампанское, отзвенели бубенцы. Замолили ли мы нашего двукратного дракона великого зеленокожесластного? Такс:\n\n{stats_text}'
            dsp(send_html, bot, chat_id, text)
            cache.set(chat_key, True, time=TWO_DAYS)


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
        Отправка ночных приветственных и подводящих итоги сообщений
        """
        if is_day_active():
            set_today_special()
            # DayBegin.send(bot)
            return 
        if is_today_ending():
            send_end(bot)

    @classmethod
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
    def private_text_handler(bot: telegram.Bot, update: telegram.Update) -> None:
        if not is_day_active():
            return
        private_text_handler(bot, update)
