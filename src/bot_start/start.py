# coding=UTF-8
import logging
from datetime import datetime
from time import sleep

import telegram
from telegram.ext import Updater
from telegram.ext import messagequeue as mq
from telegram.ext.messagequeue import DelayQueueError
from telegram.utils.request import Request

import src.config as config
from src.bot_start.add_handlers import add_chat_handlers, add_private_handlers, add_other_handlers
from src.bot_start.add_jobs import add_jobs
from src.bot_start.google_cloud import auth_google_vision
from src.bot_start.mqbot import MQBot
from src.config import CONFIG
from src.utils.cache import cache, YEAR
from src.utils.logger import logger
from src.utils.repair import repair_bot
from src.web.server import start_server


def error(bot, update, error):
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


def prepare():
    """
    Подготовительный этап
    """
    if 'google_vision_client_json_file' in CONFIG:
        config.google_vision_client = auth_google_vision(CONFIG['google_vision_client_json_file'])
    cache.set('pipinder:fav_stickersets_names', set(CONFIG.get("sasha_rebinder_stickersets_names", [])), time=YEAR)


def start_bot():
    """
    Инициализация бота
    """
    q = mq.MessageQueue(all_burst_limit=29, all_time_limit_ms=1017)
    bot = MQBot(CONFIG['bot_token'], mqueue=q, request=get_request_data())
    updater = Updater(bot=bot, workers=16)
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
    cache.set('bot_id', bot.id)
    return updater


def get_request_data():
    con_pool_size = 20
    read_timeout = 10.
    connect_timeout = 10.
    if 'telegram_proxy' not in CONFIG:
        return Request(con_pool_size=con_pool_size, read_timeout=read_timeout, connect_timeout=connect_timeout)
    proxy_url = CONFIG['telegram_proxy']['proxy_url']
    if CONFIG['telegram_proxy'].get('username', '') == '':
        return Request(con_pool_size=con_pool_size, read_timeout=read_timeout, connect_timeout=connect_timeout, proxy_url=proxy_url)
    return Request(con_pool_size=con_pool_size,
                   read_timeout=read_timeout,
                   connect_timeout=connect_timeout,
                   proxy_url=proxy_url,
                   urllib3_proxy_kwargs={
                       'username': CONFIG['telegram_proxy']['username'],
                       'password': CONFIG['telegram_proxy']['password'],
                   })


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
