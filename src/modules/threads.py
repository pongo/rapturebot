import re

import requests
import telegram
from telegram import MessageEntity, ChatAction

from src.utils.logger_helpers import get_logger
from src.utils.send_video_helpers import send_images, send_videos

logger = get_logger(__name__)
re_threads_url = re.compile(r"^https://(www)\.threads\.net/t/.+$")
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
        message.chat.send_action(action=ChatAction.UPLOAD_VIDEO)
        r = fetch_post(url)
        if r is None:
            return None

        caption, likes, replies, images, videos = r
        text = build_text(caption, likes, replies)

        if len(images) == 0 and len(videos) == 0:
            message.reply_text(text)
        else:
            caption_sent = send_images(message, images, text)
            send_videos(message, videos, text, caption_sent)

        logger.info(f"Processed threads {url}")
    except Exception as e:
        logger.error(f"Failed to download threads {url}: {repr(e)}")
        logger.error(e)


def build_text(caption, likes, replies):
    return f"{caption}\n\n{likes} likes, {replies} replies"


def fetch_post(url):
    r = requests.post(f'http://localhost:3000/api/v1/threads', json={"url": url})
    res = r.json()
    if not res['ok']:
        logger.error(res)
        return None

    caption = res["value"]["caption"]
    likes = res["value"]["likes"]
    replies = res["value"]["replies"]
    videos = res["value"]["videos"]
    images = res["value"]["images"]
    return caption, likes, replies, images, videos
