import telegram

from src.config import CONFIG
from src.modules.dayof.helper import set_today_special
from src.plugins.valentine_day.date_checker import is_day_active, is_today_ending
from src.plugins.valentine_day.handlers.card_handlers import revn_button_click_handler, \
    mig_button_click_handler, about_button_click_handler
from src.plugins.valentine_day.handlers.draft_handlers import draft_heart_button_click_handler, \
    draft_chat_button_click_handler, private_text_handler
from src.plugins.valentine_day.handlers.stats_redis import StatsRedis
from src.plugins.valentine_day.helpers.helpers import send_to_all_chats, send_html
from src.plugins.valentine_day.model import MODULE_NAME, \
    DraftHeartButton, DraftChatButton, \
    RevnButton, MigButton, AboutButton, CACHE_PREFIX, StatsHumanReporter
from src.utils.cache import cache, TWO_DAYS
from src.utils.logger_helpers import get_logger
from src.utils.telegram_helpers import dsp

HTML = telegram.ParseMode.HTML
logger = get_logger(__name__)


def send_announcement(bot: telegram.Bot) -> None:
    text = """
Всех от сих до сих 
          поздравляю с днем так-сяк. 
                    Стрелы, щиты, каблуки.
Вы в клетке? Повторите запрос
-
--,d88b.d88b,
--88888888888
--`Y8888888Y'
-----`Y888Y'           Утром!
---------`Y'
        """.strip()
    send_to_all_chats(bot, 'announcement', lambda _: text)


def send_end(bot: telegram.Bot) -> None:
    """
    Отправка во все чаты подводящих итог сообщений
    """
    def _get_text(chat_id: int) -> str:
        stats_text = StatsHumanReporter(stats).get_text(chat_id)
        return f'Отгремело шампанское, отзвенели бубенцы. Замолили ли мы нашего двукратного дракона великого зеленокожесластного? Такс:\n\n{stats_text}'

    with StatsRedis() as stats:
        # отправка админу статы по всем чатам
        admin_key = f'{CACHE_PREFIX}:end:admin'
        if not cache.get(admin_key, False):
            text = StatsHumanReporter(stats).get_text(None)
            dsp(send_html, bot, CONFIG.get('debug_uid', None), text)
            cache.set(admin_key, True, time=TWO_DAYS)

        send_to_all_chats(bot, 'end', _get_text)


def send_help(bot: telegram.Bot, user_id: int) -> None:
    text = f"""
Добрая дорога, кожаный мешок! Я помогу тебе выразить так называемую любовь.

<b>Отправка валентинки</b>

Напиши текст валентинки прямо сюда, не забыв указать @username получателя. Потом выберешь чат для отправки. Твое имя нигде не будет указано.

На валентинке будет кнопка для подмигивания. Я сообщу тебе, если адресат ее нажал (твое имя останется в тайне).

<b>Анонимность</b>

В этот раз без анонимного сайта. Но мой автор уверяет, что и так все останется в тайне. Поверьте этому кожаному мешку! 🙏

<b>Поехали!</b>

Сегодня не время тянуть! Пиши валентинку ❤️
    """.strip()
    send_html(bot, user_id, text)


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
            send_announcement(bot)
            return 
        if is_today_ending():
            send_end(bot)

    @classmethod
    def callback_handler(cls, bot: telegram.Bot, update: telegram.Update,
                         query: telegram.CallbackQuery, data) -> None:
        """
        Обработчик коллбеков
        """
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
        """
        Обработчик простого текста, отправляемого в личку
        """
        if not is_day_active():
            return
        private_text_handler(bot, update)

    @staticmethod
    def private_help_handler(bot: telegram.Bot, update: telegram.Update) -> None:
        """
        Обработчик команды /help в личке
        """
        send_help(bot, update.message.chat_id)
