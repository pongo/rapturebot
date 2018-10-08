# coding=UTF-8

import json
import logging
import random
import re
from datetime import datetime

import apiai
import requests
import telegram
from telegram import ParseMode
from telegram.ext import run_async

from src.config import CONFIG
from src.handlers.other import send_huificator
from src.modules.dayof.day_manager import DayOfManager
from src.modules.dayof.helper import is_today_special
from src.modules.models.reply_top import LoveDumpTable
from src.modules.models.user import User
from src.utils.cache import cache
from src.utils.handlers_decorators import only_users_from_main_chat
from src.utils.misc import weighted_choice

logger = logging.getLogger(__name__)


def startup_time(bot: telegram.Bot, update: telegram.Update) -> None:
    uid = update.message.chat_id
    logger.info(f'id {uid} /startup_time')
    cached = cache.get('bot_startup_time')
    if cached:
        bot.send_message(uid, cached.strftime('%Y-%m-%d %H:%M'))
        return
    bot.send_message(uid, 'В кеше ничего нет (но должно быть)')


def users_clear_cache(bot: telegram.Bot, update: telegram.Update) -> None:
    """
    Если через бд изменили пол - нужно обновить в кеше эти сведения
    """
    uid = update.message.chat_id
    logger.info(f'id {uid} /users_clear_cache')
    User.clear_cache()
    bot.send_message(uid, '<b>User</b> кеш очищен', parse_mode=telegram.ParseMode.HTML)


@run_async
def huyamda(bot: telegram.Bot, update: telegram.Update) -> None:
    message = update.edited_message if update.edited_message else update.message
    send_huificator(bot, message)


def rand(bot: telegram.Bot, update):
    message = update.edited_message if update.edited_message else update.message
    words = re.sub(r'[^\d.,]+', ' ', message.text).split()
    num = 42
    if len(words) == 1:
        try:
            num = random.randint(1, int(words[0]))
        except Exception:
            pass
    elif len(words) >= 2:
        try:
            num = random.randint(int(words[0]), int(words[1]))
        except Exception:
            pass
    return bot.send_message(message.chat_id, str(num))


@run_async
def lovedump(_: telegram.Bot, update: telegram.Update) -> None:
    message = update.message
    try:
        __, cid_str, date_str = message.text.split(' ')
        cid = int(cid_str)
        date = datetime.strptime(date_str.strip(), '%Y%m%d')
        LoveDumpTable.dump(cid, date)
        message.reply_text('Готово!')
    except Exception:
        message.reply_text('Неверный формат')


@only_users_from_main_chat
def anon(bot: telegram.Bot, update: telegram.Update) -> None:
    if not CONFIG.get('anon', False):
        return
    text = update.message.text
    if not text:
        return
    uid = update.message.from_user.id
    cid = CONFIG['anon_chat_id']

    text = re.sub(r"\s*/\w+", '', text)
    text = text.strip()
    if len(text) == 0:
        return
    logger.info(f'[anon] from {uid}. text: {text}')
    bot.send_message(cid, text, disable_web_page_preview=True)


@run_async
def private(bot: telegram.Bot, update: telegram.Update):
    """
    Текст в личку бота.
    """
    DayOfManager.private_handler(bot, update)
    if is_today_special():
        return
    ai(bot, update)


@run_async
def help(bot: telegram.Bot, update: telegram.Update):
    DayOfManager.private_help_handler(bot, update)


@run_async
def ai(bot: telegram.Bot, update: telegram.Update):
    if 'dialogflow_api_token' not in CONFIG:
        return
    text = update.message.text
    if text is None:
        return
    chat_id = update.message.chat_id
    msg_id = update.message.message_id
    session_id = cache.get(f'ai:session_id:{chat_id}')
    if not session_id:
        session_id = msg_id
    cache.set(f'ai:session_id:{chat_id}', session_id, time=15 * 60)

    request = apiai.ApiAI(CONFIG['dialogflow_api_token']).text_request()
    request.lang = 'ru'  # На каком языке будет послан запрос
    request.session_id = str(session_id)  # ID Сессии диалога (нужно, чтобы потом учить бота)
    request.query = text

    response_json = json.loads(request.getresponse().read().decode('utf-8'))
    response = response_json['result']['fulfillment'][
        'speech']  # Разбираем JSON и вытаскиваем ответ
    response_text = response if response else 'Я вас не поняль'
    bot.send_message(chat_id, f'{response_text} 🤖')


def __private(bot: telegram.Bot, update: telegram.Update):
    # logger.info('Anon message from {}'.format(update.message.from_user.name))
    message = update.edited_message if update.edited_message else update.message

    # key = 'anonlimit_{}'.format(message.from_user.id)
    # cached = cache.get(key)
    # if cached:
    #     bot.sendMessage(message.chat_id, 'Попробуй после {}'.format(cached.strftime("%H:%M")))
    #     return
    #
    # limit_seconds = 5 * 60
    # release_time = datetime.now() + timedelta(seconds=limit_seconds, minutes=1)
    # cache.set(key, release_time, time=limit_seconds)

    text = message.text
    if text:
        # пустые сообщения игнорируем
        prepared_text = text.strip()
        if len(prepared_text) == 0:
            return

        # в анонимках можно указывать никнейм.
        # --в конце сообщения отдельной строкой должно быть указано: `nickname (c)`--
        # в начале сообщения отдельной строкой должно быть указано: `Леха пишет:`

        # re_nicknamed = r"\n\s*(.+)\s* (?:\([cс]\)|©)\s*$"
        re_nicknamed = r"^\s*(.+)\s* пишет:\n"
        match = re.search(re_nicknamed, prepared_text, re.IGNORECASE)
        # если указан
        if match:
            name = match.group(1).strip()
            # нам нужно вырезать строку указания никнейма из текста
            prepared_text = re.sub(re_nicknamed, "", prepared_text, 0, re.IGNORECASE)
            prepared_text = prepared_text.strip()
            if len(prepared_text) == 0:
                return
        # если не указан, то генерируем случайный никнейм с заданными шансами
        else:
            name = weighted_choice([
                ('Аноним', 40),
                ('Анонимка', 40),
                ('Дикая антилопа', 20),
            ])

        # начинаем предложения с больших букв
        # для этого мы делаем запрос к апи
        response = requests.post(
            'https://languagetool.org/api/v2/check',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json'
            },
            data={
                'text': prepared_text,
                'language': 'ru-RU',
                'enabledRules': 'UPPERCASE_SENTENCE_START,Cap_Letters_Name',
                'enabledOnly': 'true'
            }
        )
        if response.status_code == 200:
            json_result = response.json()
            if 'matches' in json_result:
                for m in reversed(json_result['matches']):
                    replacement = m['replacements'][0]['value']
                    prepared_text = '{}{}{}'.format(
                        prepared_text[0:m['offset']],
                        replacement,
                        prepared_text[m['offset'] + len(replacement):],
                    )

        # типографируем текст
        response = requests.post("http://mdash.ru/api.v1.php", params={
            'text': prepared_text,
            'OptAlign.all': 'off',
            'Etc.unicode_convert': 'on',
            'Text.paragraphs': 'off',
            'Text.auto_links': 'off',
            'Text.email': 'off',
            'Text.breakline': 'off',
            'Punctmark.dot_on_end': 'on',
        })
        if response.status_code == 200:
            prepared_text = response.json()['result']

        # if re.search(r""".*([^-!$%^&*()_+|~=`{}\[\]:";'<>?,.\/]\s*)$""", prepared_text, re.IGNORECASE):
        #     prepared_text = '{}.'.format(prepared_text)

        msg = '<b>{}</b> пишет:\n\n{}'.format(name, prepared_text)
        bot.sendMessage(CONFIG['anon_chat_id'], msg, parse_mode=ParseMode.HTML)
        return

    if message.sticker:
        bot.sendSticker(CONFIG['anon_chat_id'], message.sticker)
        return

    if len(message.photo) > 0:
        caption = message.caption if message.caption else ''
        bot.sendPhoto(CONFIG['anon_chat_id'], message.photo[-1], caption)
        return

    if message.voice is not None:
        bot.sendVoice(CONFIG['anon_chat_id'], message.voice)
        return

    if message.document is not None:
        bot.sendDocument(CONFIG['anon_chat_id'], message.document)
