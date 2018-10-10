# coding=UTF-8
import logging
from datetime import datetime
from time import sleep

import telegram
from telegram.ext import Updater
from telegram.ext.messagequeue import DelayQueueError

import src.config as config
import src.utils.cache as cache_file
from src.bot_start.add_handlers import add_chat_handlers, add_private_handlers, add_other_handlers
from src.bot_start.add_jobs import add_jobs
from src.bot_start.google_cloud import auth_google_vision
from src.config import CONFIG
from src.utils.cache import cache, YEAR
from src.utils.repair import repair_bot
from src.web.server import start_server

logger = logging.getLogger(__name__)


def error(_, update, error):
    try:
        raise error
    except telegram.error.TimedOut:
        return
    except Exception:
        logger.warning(f'Update "{update}" caused error "{error}"')


class CriticalHandler(logging.Handler):
    """
    Этот обработчит логгирования следит за критичными ошибками и вызывает самовосстановление бота.
    """

    def emit(self, record: logging.LogRecord):
        if record.levelname != 'CRITICAL':
            return
        if record.msg == 'stopping due to exception in another thread':
            logger.critical(f'[CriticalHandler] {record.msg}')
            repair_bot(logger=logger)
            return


def set_default_logging_format():
    default_format = '[%(asctime)s][%(levelname)s][%(name)s] - %(message)s'
    logging.basicConfig(
        format=CONFIG.get('logging', {}).get('format', default_format),
        level=logging.getLevelName(CONFIG.get('logging', {}).get('level', 'INFO').upper()),
        filename=CONFIG.get('logging', {}).get('file', None)
    )


def prepare():
    """
    Подготовительный этап
    """
    set_default_logging_format()
    if 'google_vision_client_json_file' in CONFIG:
        config.google_vision_client = auth_google_vision(CONFIG['google_vision_client_json_file'])
    cache.set('pipinder:fav_stickersets_names',
              set(CONFIG.get("sasha_rebinder_stickersets_names", [])), time=YEAR)


def start_bot():
    """
    Инициализация бота
    """
    updater = Updater(token=CONFIG['bot_token'], workers=50, request_kwargs=get_request_data())
    bot = updater.bot
    dp = updater.dispatcher
    dp.logger.addHandler(CriticalHandler())  # в логгер библиотеки добавляем свой обработчик
    add_chat_handlers(dp)
    add_private_handlers(dp)
    add_other_handlers(dp)
    dp.add_error_handler(error)

    logger.info('Bot started')
    cache.set('bot_startup_time', datetime.now(), time=YEAR)

    if 'webhook_domain' in CONFIG:
        domain = CONFIG['webhook_domain']
        token = CONFIG['bot_token']
        port = 8443
        updater.start_webhook(listen='0.0.0.0',
                              port=port,
                              url_path=token,
                              key='private.key',
                              cert='cert.pem',
                              webhook_url=f'https://{domain}:{port}/{token}')
        sleep(1)
    else:
        updater.start_polling()

    add_jobs(updater)
    cache_file._bot_id = bot.id
    return updater


def get_request_data():
    read_timeout = 10.
    connect_timeout = 10.
    if 'telegram_proxy' not in CONFIG:
        return {'read_timeout': read_timeout, 'connect_timeout': connect_timeout}
    proxy_url = CONFIG['telegram_proxy']['proxy_url']
    if CONFIG['telegram_proxy'].get('username', '') == '':
        return {'read_timeout': read_timeout, 'connect_timeout': connect_timeout,
                'proxy_url': proxy_url}
    return {'read_timeout': read_timeout,
            'connect_timeout': connect_timeout,
            'proxy_url': proxy_url,
            'urllib3_proxy_kwargs': {
                'username': CONFIG['telegram_proxy']['username'],
                'password': CONFIG['telegram_proxy']['password'],
            }}


def start():
    prepare()
    try:
        updater = start_bot()
        start_server(updater.bot, '5010')
        updater.idle()
    except DelayQueueError as e:
        if str(e) == 'Could not process callback in stopped thread':
            logger.critical(f'[start] {str(e)}')
            repair_bot(logger=logger)
            return
        raise e
    except Exception as e:
        if isinstance(e, telegram.error.RetryAfter):
            logger.critical(f'[start] Flood limit, wait 5 sec')
            sleep(5)
            repair_bot(logger=logger)
            return
        raise e
