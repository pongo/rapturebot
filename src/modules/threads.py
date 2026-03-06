import re

import requests
import telegram
from telegram import MessageEntity, ChatAction

from src.utils.logger_helpers import get_logger
from src.utils.send_video_helpers import send_images, send_videos

logger = get_logger(__name__)
re_threads_url = re.compile(r"^https://www\.threads\.com/@[\w.-_]+/post/[\w\-_]+")
CACHE_PREFIX = 'threads'
MODULE_NAME = CACHE_PREFIX


def get_first_threads_url_from_message(message: telegram.Message):
    message_entities = [
        n
        for n in message.parse_entities([MessageEntity.URL]).values()
        if re_threads_url.match(n)
    ]
    return message_entities[0] if message_entities else None


def process_message_for_threads(message: telegram.Message) -> bool:
    url = get_first_threads_url_from_message(message)
    if url is None:
        return False
    call(message, url)
    return True


def call(message: telegram.Message, url: str):
    try:
        message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)
        r = fetch_post(url)
        if r is None:
            logger.error(f"Third threads api returns None for {url}")
            return

        images, videos = r
        send_images(message, images)
        send_videos(message, videos)
        logger.info(f"Processed threads {url}")
    except Exception as e:
        logger.error("Failed to download threads %s: %s" % (url, repr(e)))
        logger.error(e)


def fetch_post(url):
    r = requests.post(f'http://localhost:3000/api/v1/threads', json={"url": url})
    res = r.json()
    if not res['ok']:
        logger.error(res)
        return None

    videos = res["value"]["videos"]
    images = res["value"]["images"]
    if len(images) == 0 and len(videos) == 0:
        logger.error("Failed to download threads %s: empty result" % url)
        return None
    return images, videos
