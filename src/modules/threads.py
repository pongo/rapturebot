import os
import re
import shutil
import uuid
from time import sleep
from typing import List, Optional, Tuple

import ffmpeg
import requests
import telegram
from telegram import MessageEntity, InputMediaPhoto, ChatAction, ParseMode

from packages.instaloader_proxy import Post
from src.config import CONFIG, instaloader_session_exists
from src.utils.cache import cache
from src.utils.callback_helpers import get_callback_data, remove_inline_keyboard
from src.utils.logger_helpers import get_logger
from src.utils.misc import CustomNamedTemporaryFile

logger = get_logger(__name__)
re_threads_url = re.compile(r"^https://(www)\.threads\.net/t/.+$")
CACHE_PREFIX = 'threads'
MODULE_NAME = CACHE_PREFIX
callback_upload_video = 'threads_upload_video'

SEND_VIDEO_SIZE_LIMIT = 50 * 1048576  # 50mb https://core.telegram.org/bots/api#sendvideo

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
    #return
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


def send_images(message: telegram.Message, images: List[str], text: str) -> bool:
    if len(images) == 0:
        return False

    if len(images) == 1:
        message.reply_photo(images[0], filename=f"photo.jpg", caption=text)
        return True

    if len(images) > 1:
        message.reply_text(text)
        sleep(1)
        message.reply_media_group([
            InputMediaPhoto(url)  # , filename=f"{post_id}-{i + 1}.jpg")
            for i, url in enumerate(images)
        ])
        return False


def send_videos(message: telegram.Message, videos: List[str], text: str, caption_sent: bool) -> None:
    if len(videos) == 0:
        return

    if caption_sent:
        text = ''

    if len(videos) == 1:
        send_video(message, videos[0], text)

    if len(videos) > 1:
        first = True
        for video_url in videos:
            send_video(message, video_url, text if first else '')
            sleep(1)
            first = False


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


class ThreadsActive:
    @staticmethod
    def create_and_return_active_id(video_url: str) -> str:
        key = str(uuid.uuid4())
        hour = 60 * 60
        cache.set(f"threads:active:{key}", video_url, time=hour)
        return key

    @staticmethod
    def get_active_video_url(key: str) -> Optional[str]:
        return cache.get(f"threads:active:{key}", None)


def send_video(message: telegram.Message, video_url: str, text: str) -> None:
    message_id = message.message_id
    reply_markup = get_reply_markup([
        [('Отправить как видео', (extend_initial_data({
            'value': callback_upload_video, 'message_id': message_id,
            'active_id': ThreadsActive.create_and_return_active_id(video_url)
        })))],
    ])
    message.reply_html(f"""{text}\n\n<a href="{video_url}">Video</a>""".strip(), reply_markup=reply_markup)


def extend_initial_data(data: dict) -> dict:
    initial = {"name": CACHE_PREFIX, "module": MODULE_NAME}
    result = {**initial, **data}
    return result


def get_reply_markup(buttons) -> Optional[telegram.InlineKeyboardMarkup]:
    """
    Инлайн-кнопки под сообщением
    """
    if not buttons:
        return None
    keyboard = []
    for line in buttons:
        keyboard.append([
            telegram.InlineKeyboardButton(
                button_title,
                callback_data=(get_callback_data(button_data)))
            for button_title, button_data in line
        ])
    return telegram.InlineKeyboardMarkup(keyboard)


def threads_callback_handler(bot: telegram.Bot, _: telegram.Update,
                               query: telegram.CallbackQuery, data) -> None:
    if 'module' not in data or data['module'] != MODULE_NAME:
        return
    if data['value'] == callback_upload_video:
        chat_id = query.message.chat_id
        remove_inline_keyboard(bot, chat_id, query.message.message_id)
        video_url = ThreadsActive.get_active_video_url(data['active_id'])

        if video_url is None:
            bot.answer_callback_query(query.id, 'Загрузить видео можно только в течение часа',
                                      show_alert=True)
            return

        message_id = data['message_id']
        try:
            send_video_upload(bot, chat_id, message_id, video_url)
        except Exception as e:
            logger.error(f"Failed to upload to query threads. message_id {message_id}: {repr(e)}")
            logger.error(e)
        bot.answer_callback_query(query.id)
        return


def get_video_wh(video_path: str) -> Tuple[Optional[int], Optional[int]]:
    try:
        probe = ffmpeg.probe(video_path)
    except ffmpeg.Error as e:
        logger.error(e)
        return None, None

    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    if video_stream is None:
        logger.error('No video stream found')
        return None, None

    return (int(video_stream['width'])), (int(video_stream['height']))


def send_video_upload(bot: telegram.Bot, chat_id, message_id, video_url: str) -> None:
    bot.send_chat_action(chat_id, action=ChatAction.UPLOAD_VIDEO)
    with CustomNamedTemporaryFile(suffix='.mp4') as f:
        with requests.get(video_url, stream=True, headers={
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0"
        }) as r:
            if not r.ok:
                logger.info(f"Failed to download video ({r.status_code}) {video_url}")
                bot.send_message(chat_id,
                                 f"""Не смог скачать видео. Качайте сами:\n\n<a href="{video_url}">Video</a>""",
                                 parse_mode=ParseMode.HTML, reply_to_message_id=message_id)
                return
            file_size = int(r.headers.get('Content-length', 0))
            # if file_size == 0:
            # message.reply_html(f"<a href='{video_url}'>Video</a>")
            # return
            if file_size >= SEND_VIDEO_SIZE_LIMIT:
                bot.send_message(
                    f"""Телеграм не дает отправить видео больше 50 мб. Качайте сами:\n\n<a href="{video_url}">Video</a>""",
                    parse_mode=ParseMode.HTML, reply_to_message_id=message_id)
                return
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)

        with open(f.name, "rb") as infile:
            infile.seek(0, os.SEEK_END)
            filesize = infile.tell()
            # logger.info(filesize)
            if filesize >= SEND_VIDEO_SIZE_LIMIT:
                bot.send_message(
                    f"""Телеграм не дает отправить видео больше 50 мб. Качайте сами:\n\n<a href="{video_url}">Video</a>""",
                    parse_mode=ParseMode.HTML, reply_to_message_id=message_id)
                return

        width, height = get_video_wh(f.name)
        bot.send_video(chat_id, video=open(f.name, "rb"), reply_to_message_id=message_id, width=width, height=height)
