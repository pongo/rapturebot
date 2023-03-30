import enum
import random
import re
import textwrap
import typing
from datetime import datetime
from functools import wraps

import telegram
from pytils.numeral import get_plural
from telegram.ext import run_async

from src.config import CONFIG
from src.dayof.helper import set_today_special
from src.models.chat_user import ChatUser
from src.models.user import User
from src.utils.cache import cache, USER_CACHE_EXPIRE
from src.utils.callback_helpers import get_callback_data
from src.utils.logger_helpers import get_logger
from src.utils.text_helpers import lstrip_every_line

logger = get_logger(__name__)
CACHE_PREFIX = 'fsb_day'


def extend_initial_data(data: dict) -> dict:
    initial = {"name": 'dayof', "module": "fsb_day"}
    result = {**initial, **data}
    return result


class FSBDayGuard:
    @classmethod
    def handlers_guard(cls, f):
        @wraps(f)
        def decorator(_cls, bot: telegram.Bot, update: telegram.Update):
            message = update.edited_message if update.edited_message else update.message
            uid = message.from_user.id
            if not FSBDayModel.is_day_active():
                return
            if not ChatUser.get(uid, CONFIG['anon_chat_id']):
                return
            if cls.is_dinner_time():
                cls.__send_dinner(bot, uid)
                return
            return f(_cls, bot, update)

        return decorator

    @classmethod
    def callback_handler_guard(cls, f):
        @wraps(f)
        def decorator(_cls, bot: telegram.Bot, update: telegram.Update, query, data):
            uid = query.from_user.id
            # if not FSBDayModel.is_day_active():
            #    return
            # if not ChatUser.get(uid, CONFIG['anon_chat_id']):
            #    return
            if FSBDayModel.is_day_active() and cls.is_dinner_time():
                cls.__send_dinner(bot, uid)
                return
            return f(_cls, bot, update, query, data)

        return decorator

    @staticmethod
    def is_dinner_time() -> bool:
        """
        Сейчас время обеда?
        """
        return datetime.now().hour == 13

    @staticmethod
    @run_async
    def __send_dinner(bot: telegram.Bot, uid) -> None:
        user = User.get(uid)
        who = 'Женщина' if user.female else 'Мужчина'
        bot.send_message(uid, f'{who}, вы что не видите, у нас обед до 14!')
        FSBDayAnekdot.send_anekdot(bot, uid)


class FSBDayTextType(enum.IntEnum):
    unknown, donos, raskayanie = range(3)


class FSBDayTelegram:
    chat_id = CONFIG['anon_chat_id']

    class TelegramExecute:
        def execute(self, bot):
            pass

        @staticmethod
        def get_reply_markup(buttons):
            """
            Инлайн-кнопки под сообщением
            """
            keyboard = []
            for line in buttons:
                keyboard.append([
                    telegram.InlineKeyboardButton(
                        button_title,
                        callback_data=(get_callback_data(button_data)))
                    for button_title, button_data in line
                ])
            return telegram.InlineKeyboardMarkup(keyboard)

        @staticmethod
        def get_full_reply_markup(buttons):
            """
            Кнопки, располагающиеся внизу самого телеграмма
            """
            keyboard = []
            for line in buttons:
                keyboard.append(line)
            return telegram.ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    class AnswerCallbackQuery(TelegramExecute):
        def __init__(self, query_id, text: str, show_alert=False) -> None:
            self.query_id = query_id
            self.text = text
            self.show_alert = show_alert

        def execute(self, bot):
            bot.answer_callback_query(self.query_id, text=self.text, show_alert=self.show_alert)

    class AnswerCallbackQueryWithBotLink(TelegramExecute):
        def __init__(self, query_id, query_data):
            self.query_id = query_id
            self.query_data = query_data

        def execute(self, bot):
            bot.answer_callback_query(self.query_id,
                                      url=f"t.me/{bot.username}?start={self.query_data}")

    class EditChatButtons(TelegramExecute):
        def __init__(self, message_id, buttons):
            self.message_id = message_id
            self.buttons = buttons

        def execute(self, bot):
            reply_markup = self.get_reply_markup(self.buttons)
            bot.edit_message_reply_markup(FSBDayTelegram.chat_id, self.message_id,
                                          reply_markup=reply_markup)
            cache.set(f'{CACHE_PREFIX}__message_buttons_{self.message_id}', self.buttons,
                      time=USER_CACHE_EXPIRE)

    class ShowName(TelegramExecute):
        def __init__(self, message_id, uid: int) -> None:
            self.message_id = message_id
            self.uid = uid

        def execute(self, bot: telegram.Bot):
            user = User.get(self.uid)
            old_text = cache.get(f'{CACHE_PREFIX}__message_text_{self.message_id}')
            if old_text:
                new_text = re.sub(r"^Подписано\s+[█ ]+$", f'Подписано {user.fullname}', old_text, 0,
                                  re.IGNORECASE | re.MULTILINE)
                buttons = cache.get(f'{CACHE_PREFIX}__message_buttons_{self.message_id}')
                reply_markup = self.get_reply_markup(buttons)
                female = 'а' if user.female else ''
                bot.send_message(FSBDayTelegram.chat_id,
                                 f'Какой ужас. Это был{female} {user.get_username_or_link()}',
                                 reply_to_message_id=self.message_id,
                                 parse_mode=telegram.ParseMode.HTML)
                return bot.edit_message_text(new_text, FSBDayTelegram.chat_id, self.message_id,
                                             parse_mode=telegram.ParseMode.HTML,
                                             reply_markup=reply_markup)
            bot.send_message(FSBDayTelegram.chat_id,
                             f'Не могу исправить само сообщение. Но оно подписано {user.get_username_or_link()}',
                             reply_to_message_id=self.message_id,
                             parse_mode=telegram.ParseMode.HTML)

    class SendToUserWithFullButtons(TelegramExecute):
        def __init__(self, uid, text, buttons):
            self.uid = uid
            self.text = text
            self.buttons = buttons

        def execute(self, bot):
            reply_markup = self.get_full_reply_markup(self.buttons)
            try:
                bot.send_message(self.uid, self.text, parse_mode=telegram.ParseMode.HTML,
                                 reply_markup=reply_markup)
            except:
                user = User.get(self.uid)
                logger.warning(f"[fsb_day] can't send message to {user.get_username_or_link()}")

    class SendToChat(TelegramExecute):
        def __init__(self, text, reply_to_message_id=None):
            self.text = text
            self.reply_to_message_id = reply_to_message_id

        def execute(self, bot):
            bot.send_message(FSBDayTelegram.chat_id, self.text, parse_mode=telegram.ParseMode.HTML,
                             reply_to_message_id=self.reply_to_message_id,
                             disable_web_page_preview=True)

    class SendToChatWithButtons(TelegramExecute):
        def __init__(self, text, buttons, reply_to_message_id=None):
            self.text = text
            self.buttons = buttons
            self.reply_to_message_id = reply_to_message_id

        def execute(self, bot: telegram.Bot):
            reply_markup = self.get_reply_markup(self.buttons)
            message: telegram.Message = bot.send_message(FSBDayTelegram.chat_id, self.text,
                                                         parse_mode=telegram.ParseMode.HTML,
                                                         reply_markup=reply_markup,
                                                         reply_to_message_id=self.reply_to_message_id,
                                                         disable_web_page_preview=True, timeout=60)
            cache.set(f'{CACHE_PREFIX}__message_text_{message.message_id}', message.text_html,
                      time=USER_CACHE_EXPIRE)
            cache.set(f'{CACHE_PREFIX}__message_buttons_{message.message_id}', self.buttons,
                      time=USER_CACHE_EXPIRE)

    class SendToUser(TelegramExecute):
        def __init__(self, uid, text, reply_to_message_id=None):
            self.uid = uid
            self.text = text
            self.reply_to_message_id = reply_to_message_id

        def execute(self, bot):
            try:
                bot.send_message(self.uid, self.text, parse_mode=telegram.ParseMode.HTML,
                                 reply_to_message_id=self.reply_to_message_id)
            except:
                user = User.get(self.uid)
                logger.warning(f"[fsb_day] can't send message to {user.get_username_or_link()}")


class FSBDayModel:
    state_begin = 'state_begin'
    state_end = 'state_end'

    @staticmethod
    def is_day_active() -> bool:
        """
        Сегодня этот день?
        """
        if 'dayof_debug' in CONFIG:
            return True
        md = datetime.today().strftime("%m-%d")
        return md == '12-20'  # месяц-день. Первое января будет: 01-01

    @classmethod
    def midnight(cls) -> typing.Optional[typing.Tuple[str, typing.List[typing.Tuple[str, dict]]]]:
        # срабатывает 20 дек
        if cls.is_day_active():
            return cls.__day_begin()

        # срабатывает 21 дек
        if datetime.today().strftime("%m-%d") == '12-21':
            return cls.__day_end()

        return None

    @classmethod
    def callback_handler(cls, uid, message_id, query_id, query_data, data):
        if 'module' not in data or data['module'] != 'fsb_day':
            return None

        if data['value'] == 'like' or data['value'] == 'dislike':
            return cls.__callback_like_dislike(uid, message_id, query_id, data)

        if not cls.is_day_active():
            return [FSBDayTelegram.AnswerCallbackQuery(query_id, 'Все уже закончилось',
                                                       show_alert=True)]

        if data['value'] == 'begin':
            text, buttons = cls.__get_help(uid)
            return [
                FSBDayTelegram.AnswerCallbackQueryWithBotLink(query_id, query_data),
                FSBDayTelegram.SendToUserWithFullButtons(uid, text, buttons),
            ]

        if data['value'] == 'wtf':
            text = textwrap.dedent(
                """
                Сегодня в России отмечается День ФСБ. В честь праздника в личке бота открыта анонимная линия доверия. Для получения инструкций напишите /help боту в личку.

                Облегчите совесть, снимите груз с души!
                """).strip()
            return [FSBDayTelegram.AnswerCallbackQuery(query_id, text, show_alert=True)]

        if data['value'] == 'stuk' or data['value'] == 'donate':
            return cls.__callback_stuk_donate(uid, message_id, query_id, data)

    @classmethod
    def private_help_handler(cls, uid: int) -> typing.Union[
        None, typing.List[FSBDayTelegram.TelegramExecute]]:
        text, buttons = cls.__get_help(uid)
        return [FSBDayTelegram.SendToUserWithFullButtons(uid, text, buttons)]

    @classmethod
    def private_handler(cls, uid: int, text: str) -> typing.Union[
        None, typing.List[FSBDayTelegram.TelegramExecute]]:
        if re.search(r"www|http|\.(jpe?g|gif|png|webp|mp4|webm)", text,
                     re.IGNORECASE | re.MULTILINE):
            return [FSBDayTelegram.SendToUser(uid, 'Орзик, хватит играться.')]

        case = FSBDayCase(text, uid)
        if case.text_type == FSBDayTextType.unknown:
            return [FSBDayTelegram.SendToUser(uid,
                                              'Не могу понять, вы доносите или раскаиваетесь? Начните сообщение с нужных слов (/help).\n\nВы можете как отправить сообщение заново, так и отредактировать старое.')]

        if case.plagiat:
            return [FSBDayTelegram.SendToUser(uid, 'Мы уже получили такое обращение.')]

        text_for_chat = case.get_chat_text()
        buttons = cls.__generate_stuk_donate_buttons(uid)
        FSBDayStats.add_case(case.text_type, uid)
        case_opened = textwrap.dedent(
            f"""
            Ваше заявление принято. Открыто дело под номером {case.num}.

            Для подачи нового заявления просто напишите мне сообщение. Или получите инструкции через /help.
            """
        ).strip()
        return [
            FSBDayTelegram.SendToChatWithButtons(text_for_chat, buttons),
            FSBDayTelegram.SendToUser(uid, case_opened)
        ]

    @classmethod
    def __day_begin(cls) -> typing.Tuple[str, list]:
        text = textwrap.dedent(
            """
            👮🚓👮🚓👮🚓👮🚓

            Сегодня в России отмечается День ФСБ. В честь праздника ровно на одни сутки в личке бота открыта анонимная линия доверия. Прием доносов и чистосердечных раскаяний проходит без перерывов. Перерыв на обед с 13 до 14 часов.

            Для получения инструкций напишите команду <code>/help</code> боту в личку.

            Облегчите совесть, снимите груз с души!
            """).strip()

        data = extend_initial_data({"value": "begin"})
        buttons = [
            [('Перейти на линию (нажмите там Start)', data)]
        ]
        return text, buttons

    @classmethod
    def __day_end(cls) -> typing.Tuple[str, list]:
        stats = FSBDayStats.get_stats()
        text = lstrip_every_line(textwrap.dedent(
            f"""
            День ФСБшника закончился. Личка доверия прекратила прием обращений. Самое время подвести итоги:

            {stats}
            """)).strip()
        text = re.sub(r"^ +", "", text, 0, re.IGNORECASE | re.MULTILINE)

        data1 = extend_initial_data({'value': 'like'})
        data2 = extend_initial_data({'value': 'dislike'})
        buttons = [
            [('Мне понравилось', data1), ('Мне не понравилось', data2)]
        ]
        return text, buttons

    @classmethod
    def __callback_like_dislike(cls, uid, message_id, query_id, data) -> typing.List[
        FSBDayTelegram.TelegramExecute]:
        clicks_count = FSBDayStats.inc_click_count(data['value'], message_id, uid)
        if clicks_count is None:
            return [FSBDayTelegram.AnswerCallbackQuery(query_id, 'Только один раз')]

        like_count, dislike_count, _ = clicks_count
        query_answer_text = '❤️' if data['value'] == 'like' else '💔'
        buttons = cls.__generate_likedislike_buttons(like_count, dislike_count)
        return [
            FSBDayTelegram.AnswerCallbackQuery(query_id, query_answer_text),
            FSBDayTelegram.EditChatButtons(message_id, buttons),
        ]

    @classmethod
    def __generate_likedislike_buttons(cls, like_count: int = 0, dislike_count: int = 0):
        data1 = extend_initial_data({'value': 'like'})
        data2 = extend_initial_data({'value': 'dislike'})
        first_button_title = 'Мне понравилось' if like_count == 0 else f'Мне понравилось — {like_count}'
        second_button_title = 'Мне не понравилось' if dislike_count == 0 else f'Мне не понравилось — {dislike_count}'
        buttons = [
            [(first_button_title, data1), (second_button_title, data2)]
        ]
        return buttons

    @classmethod
    def __generate_stuk_donate_buttons(cls, case_uid: int, stuk_count: int = 0,
                                       donate_count: int = 0):
        data1 = extend_initial_data({'value': 'stuk', 'case_uid': case_uid})
        data2 = extend_initial_data({'value': 'donate', 'case_uid': case_uid})
        data3 = extend_initial_data({"value": "wtf"})
        first_button_title = 'Настучать' if stuk_count == 0 else f'Настучать — {stuk_count}'
        second_button_title = 'Поддержать рублем' if donate_count == 0 else f'{donate_count} — Поддержать рублем'
        buttons = [
            [(first_button_title, data1), (second_button_title, data2)],
            [('Что это?', data3)]
        ]
        return buttons

    @classmethod
    def __get_help(cls, uid):
        user = User.get(uid)
        name = user.fullname if user.fullname else user.get_username_or_link()
        text = textwrap.dedent(
            f"""
            Здравствуйте, {name}, вас приветствует анонимная линия доверия!

            <b>Помните</b>

            • Все заявления анонимны. Ваше имя нигде не будет указано. И вы свое имя не указывайте.
            • Отправляйте любое количество сообщений без ограничений.

            <b>Инструкция</b>

            Отправьте сообщение мне в личку — оно и будет вашим заявлением. Донос или раскаяние вы пишете будет зависеть от того, как вы начнете свое сообщение.

            <b>Донос</b>

            Пишите доносы как на участников чата, так и на любых других людей, предметы, явления. Пожалуйтесь на жизнь, цены, рецензии к фильмам. Если доносите на участника чата, то указывайте его @username, чтобы негодяй получил уведомление.

            Начните донос с любой из фраз:

            • Настоящим сообщаю, что
            • Довожу до вашего сведения, что
            • Обращаюсь по поводу
            • Спешу сообщить, что
            • Я случайно услышал(а)/увидел(а)

            Затем сообщите когда, что и с кем произошло. Не забудьте окунуть в моральную грязь виновника. Вы — лучше него.

            <b>Признания, раскаяния, явка с повинной</b>

            Если хотите раскаяться, то начните сообщение со слов:

            • Признаю себя виновным/виновной
            • Заявляю/сообщаю, что я/мною/мне/меня/мной/мы
            • Хочу чистосердечно заявить/раскаяться
            """).strip()
        # buttons = [["/help"]]
        buttons = []
        return text, buttons

    @staticmethod
    def __should_show_name(message_id) -> bool:
        stuk_count, donate_count = FSBDayStats.get_clicks_count(message_id)
        should = stuk_count - donate_count >= 7
        if not should:
            return False
        key = f'{CACHE_PREFIX}__name_shown__{message_id}'
        shown = cache.get(key)
        if shown:
            return False
        cache.set(key, True, time=USER_CACHE_EXPIRE)
        return True

    @classmethod
    def __callback_stuk_donate(cls, uid, message_id, query_id, data) -> typing.Union[
        None, typing.List[FSBDayTelegram.TelegramExecute]]:
        result: typing.List[FSBDayTelegram.TelegramExecute] = []

        # если юзер кликает на кнопки своего же дела
        if uid == data['case_uid']:
            if data['value'] == 'stuk':
                FSBDayStats.inc_samodonos()
                result.append(FSBDayTelegram.AnswerCallbackQuery(query_id, 'Самодонос, кек'))
            result.append(FSBDayTelegram.AnswerCallbackQuery(query_id, 'Самопожертвование, кек'))
            if cls.__should_show_name(message_id):
                result.append(FSBDayTelegram.ShowName(message_id, data['case_uid']))
            return result

        # кликнуть можно только на одну из кнопок дела
        clicks_count = FSBDayStats.inc_click_count(data['value'], message_id, uid)
        if clicks_count is None:
            result.append(FSBDayTelegram.AnswerCallbackQuery(query_id, 'Только один раз'))
            if cls.__should_show_name(message_id):
                result.append(FSBDayTelegram.ShowName(message_id, data['case_uid']))
            return result

        titles = {
            'stuk': '👮 Спасибо за бдительность! Воронок уже в пути',
            'donate': 'Thank you for your support',
        }
        result.append(FSBDayTelegram.AnswerCallbackQuery(query_id, titles[data['value']]))

        stuk_count, donate_count, comment = clicks_count
        buttons = cls.__generate_stuk_donate_buttons(data['case_uid'], stuk_count, donate_count)
        result.append(FSBDayTelegram.EditChatButtons(message_id, buttons))

        if cls.__should_show_name(message_id):
            result.append(FSBDayTelegram.ShowName(message_id, data['case_uid']))

        # если сперва нажал одну кнопку, а потом другую
        if comment != '':
            user = User.get(uid)
            if comment == 'stuk, donate':
                msg = f'{user.get_username_or_link()} сразу же стуканула. Но позже одумалась и пожертвовала свои кровные. Давайте похлопаем ее великодушию! 👏' if user.female else f'{user.get_username_or_link()} сразу же стуканул. Но позже одумался и пожертвовал свои кровные. Давайте похлопаем его великодушию! 👏'
            else:
                msg = f'{user.get_username_or_link()} сперва подала копейку, а потом настучала. Вот жеж крыса! 🐀' if user.female else f'{user.get_username_or_link()} сперва подал копейку, а потом настучал. Вот жеж крыса! 🐀'
            result.append(FSBDayTelegram.SendToChat(msg, reply_to_message_id=message_id))

        # если часто стучит
        result.append(cls.__super_stukach_alert(uid))
        return result

    @classmethod
    def __super_stukach_alert(cls, uid: int) -> typing.Union[None, FSBDayTelegram.TelegramExecute]:
        recent_stucks = cache.get(f'{CACHE_PREFIX}__{uid}_recent_stucks')
        key_super_stukach_alert = f'{CACHE_PREFIX}__super_stukach_alert'
        if recent_stucks and recent_stucks >= 3 and not cache.get(key_super_stukach_alert):
            user = User.get(uid)
            cache.set(key_super_stukach_alert, True, time=30 * 60)
            return FSBDayTelegram.SendToChat(
                f'{user.get_username_or_link()} стучите помедленнее. Я не успеваю записывать.')
        return None


class FSBDay:
    @classmethod
    def midnight(cls, bot: telegram.Bot) -> None:
        """
        Показывает ночные приветственное и подводящее итоги сообщения.
        """
        result = FSBDayModel.midnight()
        if not result:
            return
        set_today_special()
        text, buttons = result
        cls.__execute_work(bot, [FSBDayTelegram.SendToChatWithButtons(text, buttons)])

    @classmethod
    @FSBDayGuard.callback_handler_guard
    def callback_handler(cls, bot: telegram.Bot, update: telegram.Message,
                         query: telegram.CallbackQuery, data) -> None:
        uid = query.from_user.id
        message_id = query.message.message_id
        query_id = query.id
        result = FSBDayModel.callback_handler(uid, message_id, query_id, query.data, data)
        cls.__execute_work(bot, result)

    @classmethod
    @FSBDayGuard.handlers_guard
    def private_handler(cls, bot: telegram.Bot, update: telegram.Update):
        message = update.edited_message if update.edited_message else update.message
        text = message.text
        if not text:
            return
        uid = message.from_user.id
        result = FSBDayModel.private_handler(uid, text)
        cls.__execute_work(bot, result)

    @classmethod
    @FSBDayGuard.handlers_guard
    def private_help_handler(cls, bot: telegram.Bot, update: telegram.Update):
        """
        Обрабатывает команду /help
        """
        uid = update.message.chat_id
        result = FSBDayModel.private_help_handler(uid)
        cls.__execute_work(bot, result)

    @staticmethod
    def __execute_work(
            bot: telegram.Bot,
            result: typing.Union[
                None, typing.List[typing.Union[None, FSBDayTelegram.TelegramExecute]]]
    ) -> None:
        if not result:
            return
        if isinstance(result, FSBDayTelegram.TelegramExecute):
            result.execute(bot)
            return
        for work in result:
            if work is None:
                continue
            work.execute(bot)


class FSBDayAnekdot:
    @classmethod
    @run_async
    def send_anekdot(cls, bot, uid) -> None:
        if 'anecdotica_url' not in CONFIG:
            return
        FSBDayStats.inc_anekdots_count()
        if 'dayof_debug' in CONFIG:
            bot.send_message(uid, f'Рассказываю анекдот:\n\n[debug]')
            return
        import requests
        anekdot = requests.get(CONFIG['anecdotica_url']).text
        bot.send_message(uid, f'Рассказываю анекдот:\n\n{anekdot}',
                         parse_mode=telegram.ParseMode.HTML)


class FSBDayStats:
    key_anekdots_count = f'{CACHE_PREFIX}__anekdots_count'
    key_engage_users = f'{CACHE_PREFIX}__engage_users'
    key_engagement_count = f'{CACHE_PREFIX}__engagement_count'
    key_donos_count = f'{CACHE_PREFIX}__donos_count'
    key_samodonos_count = f'{CACHE_PREFIX}__samodonos_count'
    key_raskayanie_count = f'{CACHE_PREFIX}__raskayanie_count'
    key_stukachi = f'{CACHE_PREFIX}__stukachi'
    key_stuk_click_count = f'{CACHE_PREFIX}__stuk_click_count'
    key_donators = f'{CACHE_PREFIX}__donators'
    key_donate_click_count = f'{CACHE_PREFIX}__donate_click_count'
    key_sobrano_rub = f'{CACHE_PREFIX}__sobrano_rub'
    key_users_stats = f'{CACHE_PREFIX}__users_stats'

    @classmethod
    def get_stats(cls):
        stukachey = cls.__get_count(cls.key_stukachi,
                                    'ответственный гражданин настучал, ответственных гражданина настучали, ответственных гражданинов настучали')
        stuk_count = cls.__get_count(cls.key_stuk_click_count, 'раз, раза, раз')
        donators = cls.__get_count(cls.key_donators,
                                   'либерал сделал, либерала сделали, либералов сделали')
        donate_count = cls.__get_count(cls.key_donate_click_count,
                                       'пожертвование, пожертвования, пожертвований')
        sobrano = cls.__get_sobrano()
        stats = [
            cls.__get_engage_users_count(),
            cls.__get_count(cls.key_donos_count,
                            'донос был написанан, доноса было написано, доносов было написано'),
            cls.__get_count(cls.key_raskayanie_count,
                            'раскаяние было написано, раскаяния было написано, раскаяний было написано'),
            f'{stukachey} {stuk_count}',
            f'{donators} {donate_count} (собрано {sobrano} ₽)',
            cls.__get_count(cls.key_samodonos_count,
                            'попытка самодоноса, попытки самодоноса, попыток самодоноса'),
            cls.__get_count(cls.key_anekdots_count,
                            'анекдот отправлен, анекдота отправлено, анекдотов отправлено'),
        ]
        stats_text = ''.join((f'• {stat}\n' for stat in stats if stat)).strip()
        top_informer = cls.__get_top_informer()
        text = textwrap.dedent(
            f"""
            {stats_text}
            
            {top_informer}
            """
        ).strip()
        return text

    @staticmethod
    def __get_count(key: str, plural_forms: str) -> typing.Union[None, str]:
        count = cache.get(key)
        if not count:
            count = 0
        if isinstance(count, (set, list, dict)):
            count = len(count)
        return get_plural(count, plural_forms)

    @classmethod
    def __get_engage_users_count(cls):
        users = cache.get(cls.key_engage_users)
        if not users:
            return None
        return get_plural(len(users),
                          'человек принял участие, человека приняло участие, человек приняло участие')

    @classmethod
    def __get_top_informer(cls) -> str:
        users = cache.get(cls.key_users_stats)
        if not users:
            return ''
        users_sorted_by_donos: typing.List[typing.Tuple[int, dict]] = sorted(
            users.items(),
            key=lambda user: user[1]['case_types'][int(FSBDayTextType.donos)],
            reverse=True)

        if len(users_sorted_by_donos) == 0:
            return ''
        uid, stats = users_sorted_by_donos[0]
        user = User.get(uid)
        female = 'а' if user.female else ''
        return f'Больше всего доносов написал{female} {user.get_username_or_link()}'

    @classmethod
    def inc_anekdots_count(cls) -> None:
        cls.__inc(cls.key_anekdots_count)

    @staticmethod
    def __inc(key: str, value: int = 1, time=USER_CACHE_EXPIRE) -> None:
        count = cache.get(key)
        if not count:
            count = 0
        count += value
        cache.set(key, count, time=time)

    @classmethod
    def add_case(cls, text_type: FSBDayTextType, uid: int) -> None:
        cls.__inc(cls.key_engagement_count)
        cls.__add_user_case(uid, text_type)
        cls.__add_click_users_general(cls.key_engage_users, uid)
        if text_type == FSBDayTextType.donos:
            cls.__inc(cls.key_donos_count)
        else:
            cls.__inc(cls.key_raskayanie_count)

    @classmethod
    def __add_user_case(cls, uid, text_type):
        users = cache.get(cls.key_users_stats)
        if not users:
            users = {}
        if uid not in users:
            users[uid] = {
                'engagement_count': 0,
                'case_types': {
                    int(FSBDayTextType.donos): 0,
                    int(FSBDayTextType.raskayanie): 0,
                },
            }
        users[uid]['engagement_count'] += 1
        text_type_int = int(text_type)
        if text_type_int not in users[uid]['case_types']:
            users[uid]['case_types'][text_type_int] = 0
        users[uid]['case_types'][text_type_int] += 1
        cache.set(cls.key_users_stats, users, time=USER_CACHE_EXPIRE)

    @classmethod
    def inc_samodonos(cls) -> None:
        cls.__inc(cls.key_samodonos_count)

    @classmethod
    def get_clicks_count(cls, message_id) -> typing.Tuple[int, int]:
        key = f'{CACHE_PREFIX}__{message_id}_clicks'
        msg_clicks = cache.get(key)
        if not msg_clicks:
            msg_clicks = (0, 0)
        return msg_clicks

    @classmethod
    def inc_click_count(cls, click_type: str, message_id, uid: int) -> typing.Union[
        None, typing.Tuple[int, int, str]]:
        cls.__add_click_users_general(cls.key_engage_users, uid)
        if click_type == 'stuk' or click_type == 'donate':
            success = cls.__add_click_users_general(
                f'{CACHE_PREFIX}__{message_id}_{click_type}_click_users', uid)
            if not success:
                return None
        elif click_type == 'like' or click_type == 'dislike':
            success = cls.__add_click_users_general(
                f'{CACHE_PREFIX}__{message_id}_likedislike_click_users', uid)
            if not success:
                return None

        key = f'{CACHE_PREFIX}__{message_id}_clicks'
        msg_clicks = cache.get(key)
        if not msg_clicks:
            msg_clicks = (0, 0)
        stuk_count, donate_count = msg_clicks
        comment = ''

        if click_type == 'stuk':
            cls.__add_user_click(click_type, uid)
            stuk_count += 1
            cls.__inc(cls.key_stuk_click_count)
            cls.__inc(f'{CACHE_PREFIX}__{uid}_recent_stucks', time=30 * 60)
            if not cls.__add_click_users_general(f'{CACHE_PREFIX}__{message_id}_donate_click_users',
                                                 uid, simulate=True):
                comment = 'donate, stuk'
        elif click_type == 'donate':
            cls.__add_user_click(click_type, uid)
            donate_count += 1
            cls.__inc(cls.key_donate_click_count)
            cls.__inc(cls.key_sobrano_rub, random.randrange(50, 1000, 50))
            if not cls.__add_click_users_general(f'{CACHE_PREFIX}__{message_id}_stuk_click_users',
                                                 uid, simulate=True):
                comment = 'stuk, donate'
        elif click_type == 'like':
            stuk_count += 1
        elif click_type == 'dislike':
            donate_count += 1

        cache.set(key, (stuk_count, donate_count), time=USER_CACHE_EXPIRE)
        return stuk_count, donate_count, comment

    @classmethod
    def __add_user_click(cls, click_type: str, uid: int):
        key = cls.key_stukachi if click_type == 'stuk' else cls.key_donators
        cls.__add_click_users_general(key, uid)

    @staticmethod
    def __add_click_users_general(key, uid: int, simulate=False) -> bool:
        users = cache.get(key)
        if not users:
            users = set()
        else:
            users = set(users)
        if uid in users:
            return False
        users.add(uid)
        if not simulate:
            cache.set(key, users, time=USER_CACHE_EXPIRE)
        return True

    @classmethod
    def __get_sobrano(cls):
        rub = cache.get(cls.key_sobrano_rub)
        if not rub:
            rub = 0
        return '{:,}'.format(rub).replace(',', ' ')


class FSBDayTextChecker:
    @classmethod
    def detect_text_type(cls, text) -> FSBDayTextType:
        """
        Определяет тип заявления в тексте: донос, раскаяние или неизвестный тип.
        """
        if re.search(
                r"^\s*(настоящим сообщаю,? что|довожу до вашего сведения,? что|обращаюсь по поводу|спешу сообщить,? что|(?:я )?случайно (?:услышала?|увидела?))",
                text, re.IGNORECASE | re.MULTILINE):
            return FSBDayTextType.donos

        if re.search(
                r"^\s*(признаю себя виновн(?:ым|ой)|(?:заявляю|сообщаю),? что (?:я|мною|мне|меня|мной|мы)|хочу чистосердечно (?:заявить|раскаяться))",
                text, re.IGNORECASE | re.MULTILINE):
            return FSBDayTextType.raskayanie

        return FSBDayTextType.unknown


class FSBDayCaseNumber:
    titles = {
        1: 'Петр I',
        2: 'Гусь',
        3: 'Крендель',
        4: 'Хорошист',
        5: 'Отличник',
        6: 'Антон Павлович Чехов',
        7: 'Топор',
        8: 'Женский день',
        10: 'Червонец',
        11: 'Барабанные палочки',
        12: 'Дюжина',
        13: 'Чёртова дюжина',
        14: 'Олимпиада в Сочи',
        17: 'Где мои семнадцать лет',
        18: 'В первый раз',
        20: 'Лебединое озеро',
        21: 'Очко',
        22: 'Гуси-лебеди',
        23: 'Два притопа, три прихлопа',
        24: 'День в ночь — кек в кукарек',
        25: 'Опять двадцать пять',
        27: 'Гусь с топором',
        28: 'Сено мы косить не бросим',
        30: 'Ума нет',
        31: 'С Новым Годом!',
        32: 'Три притопа, два прихлопа',
        33: 'Кудрин',
        36: 'Ваше здоровье',
        38: 'Где мы все мечтаем побывать',
        40: 'Али-баба',
        41: 'Ем один',
        44: 'Стульчики',
        45: 'Баба ягодка опять',
        47: 'Баба ягодка совсем',
        48: 'Сено косим, половинку просим',
        50: 'Полста',
        55: 'Перчатки',
        66: 'Валенки',
        69: 'Туда-сюда',
        70: 'Топор в озере',
        77: 'Семен Семеныч',
        80: 'Бабушка',
        81: 'Бабушка с клюшкой',
        82: 'Бабушка надвое сказала',
        85: 'Перестройка',
        88: 'Крендельки',
        89: 'Дедушкин сосед',
        90: 'Дедушка',
    }

    def __init__(self):
        num, title = self.__get_next_num()
        self.num: int = num
        self.title: typing.Union[None, str] = title

    @classmethod
    def __get_next_num(cls) -> typing.Tuple[int, typing.Union[None, str]]:
        """
        Возвращает следующее число с заголовком (заголовки берутся из `cls.titles`).
        Если числа с заголовками закончились, то просто увеличивает число.
        """
        nums = sorted([num for num, _ in cls.titles.items()])
        cache_key = f'{CACHE_PREFIX}__used_case_numbers'
        used_nums = cache.get(cache_key)
        if not used_nums:
            used_nums = []
        for num in nums:
            if num in used_nums:
                continue
            title = cls.titles[num]
            break
        else:
            num = 1 if len(used_nums) == 0 else used_nums[-1] + 1
            title = None
        used_nums.append(num)
        cache.set(cache_key, used_nums, time=USER_CACHE_EXPIRE)
        return num, title


class FSBDayCase:
    def __init__(self, text: str, uid: int) -> None:
        self.uid = uid
        self.num = -1
        self.text = text
        self.text_type = FSBDayTextChecker.detect_text_type(text)
        if self.text_type == FSBDayTextType.unknown:
            return

        self.plagiat = self.__is_plagiat(text)
        if self.plagiat:
            return

    @staticmethod
    def __is_plagiat(text: str) -> bool:
        text = text.strip()
        key = f'{CACHE_PREFIX}__texts'
        texts = cache.get(key)
        texts = set() if not texts else set(texts)
        if text in texts:
            return True
        texts.add(text)
        cache.set(key, texts, time=USER_CACHE_EXPIRE)
        return False

    def get_chat_text(self):
        case_num = FSBDayCaseNumber()
        if case_num.title:
            header = f'<b>Дело № {case_num.num}.</b> <i>"{case_num.title}"</i>'
        else:
            header = f'<b>Дело № {case_num.num}</b>'
        random_user = User.get(ChatUser.get_random(CONFIG['anon_chat_id']))
        user = User.get(self.uid)
        masked_sign = self.__mask_signature(random_user if random.randint(0, 100) < 70 else user)
        signature = f'Подписано  {masked_sign}' if random_user else ''
        msg = lstrip_every_line(textwrap.dedent(
            f"""
            {header}

            {self.text}

            {signature}
            """)).strip()
        self.num = case_num.num
        return msg

    @staticmethod
    def __mask_signature(user: User):
        result = user.fullname  # if not user.username or random.randint(0, 100) < 50 else user.username
        result = re.sub(r"\S", "█", result, 0, re.IGNORECASE | re.MULTILINE)
        result = result.replace(' ', '  ')
        return result
