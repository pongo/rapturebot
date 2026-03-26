import re
from typing import Optional, Tuple

import requests
import telegram
from telegram import MessageEntity, ChatAction

from src.config import CONFIG
from src.utils.logger_helpers import get_logger
from src.utils.send_video_helpers import send_images, send_videos
from src.utils.text_helpers import truncate

logger = get_logger(__name__)
re_twitter_url = re.compile(r"https?://(?:x|twitter).com/([0-9-a-zA-Z_]{1,20})/status/([0-9]*)")
twitter_third_api_key = CONFIG.get('twitter_third_api_key', None)


def get_first_twitter_id_from_message(message: telegram.Message) -> Tuple[Optional[str], Optional[str]]:
    twits = [
        parse_twitter_id(n)
        for n in message.parse_entities([MessageEntity.URL]).values()
    ]
    for twitter_username, twitter_id in twits:
        if twitter_id is not None:
            return twitter_username, twitter_id
    return None, None


def parse_twitter_id(text: str) -> Tuple[Optional[str], Optional[str]]:
    m = re_twitter_url.search(text)
    try:
        if m:
            return m.group(1), m.group(2)
        return None, None
    except Exception as _:
        return None, None


def process_message_for_twitter(message: telegram.Message) -> bool:
    """
    Отправляет видео из первой твиттер-ссылки, если она есть
    :return: False, если твиттер-ссылки нет
    """
    if twitter_third_api_key is None:
        return False
    twitter_username, twitter_id = get_first_twitter_id_from_message(message)
    if twitter_id is None:
        return False
    call(message, twitter_username, twitter_id)
    return True


def call(message: telegram.Message, twitter_username: str, twitter_id: str):
    try:
        message.chat.send_action(action=ChatAction.UPLOAD_VIDEO)
        is_private = message.chat.id >= 0

        r = fetch_post(twitter_id)
        if r is None:
            logger.error(f"Third twitter api returns None for {twitter_id}")
            message.reply_text(f"https://vxtwitter.com/{twitter_username}/status/{twitter_id}")
            return
        text, images, videos = r

        if len(images) == 0 and len(videos) == 0:
            message.reply_text(truncate(text, 4000))
        else:
            text_sent = send_images(message, images, text)
            send_videos(message, videos, text, text_sent, is_private)

        logger.info(f"Processed twitter {twitter_id}")
    except Exception as e:
        logger.error("Failed to download twitter %s: %s" % (twitter_id, repr(e)))
        logger.error(e)


def fetch_post(twitter_id):
    r = requests.post(f'http://localhost:3001/api/v1/twitter', json={"id": twitter_id})
    res = r.json()
    if not res['ok']:
        logger.error(res)
        return None

    text = res["value"]["text"]
    videos = res["value"]["videos"]
    images = res["value"]["images"]
    return text, images, videos
