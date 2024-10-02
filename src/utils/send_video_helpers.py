import os
import shutil
import uuid
from time import sleep
from typing import Optional, Tuple, List, Union

import ffmpeg
import requests
import telegram
from telegram import ChatAction, ParseMode, InputMediaPhoto

from src.utils.cache import cache
from src.utils.callback_helpers import get_callback_data, remove_inline_keyboard
from src.utils.logger_helpers import get_logger
from src.utils.misc import CustomNamedTemporaryFile, chunks

logger = get_logger(__name__)
CACHE_PREFIX = 'send_video'
MODULE_NAME = CACHE_PREFIX
CALLBACK_UPLOAD_VIDEO = 'send_video_upload'
SEND_VIDEO_SIZE_LIMIT = 50 * 1048576  # 50mb https://core.telegram.org/bots/api#sendvideo
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0"


class SendVideoButton:
    @staticmethod
    def create_and_return_button_id(video_url: str) -> str:
        key = str(uuid.uuid4())
        hour = 60 * 60
        cache.set(f"{CACHE_PREFIX}:active:{key}", video_url, time=hour)
        return key

    @staticmethod
    def get_video_url(key: str) -> Optional[str]:
        return cache.get(f"{CACHE_PREFIX}:active:{key}", None)


def extend_initial_data(data: dict) -> dict:
    initial = {"name": CACHE_PREFIX, "module": MODULE_NAME}
    result = {**initial, **data}
    return result


def send_video(message: telegram.Message, video_url: str, text: str) -> None:
    message_id = message.message_id
    reply_markup = get_reply_markup([
        [('Отправить как видео', (extend_initial_data({
            'value': CALLBACK_UPLOAD_VIDEO, 'message_id': message_id,
            'active_id': SendVideoButton.create_and_return_button_id(video_url)
        })))],
    ])
    message.reply_html(f"""<a href="{video_url}">Video</a>\n\n{text}""".strip(),
                       reply_markup=reply_markup)


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


def send_video_callback_handler(bot: telegram.Bot, _: telegram.Update,
                                query: telegram.CallbackQuery, data) -> None:
    if 'module' not in data or data['module'] != MODULE_NAME:
        return
    if data['value'] != CALLBACK_UPLOAD_VIDEO:
        return

    chat_id = query.message.chat_id
    remove_inline_keyboard(bot, chat_id, query.message.message_id)
    video_url = SendVideoButton.get_video_url(data['active_id'])

    if video_url is None:
        bot.answer_callback_query(query.id, 'Загрузить видео можно только в течение часа',
                                  show_alert=True)
        return

    bot.answer_callback_query(query.id)
    message_id = data['message_id']
    try:
        send_video_upload(bot, chat_id, message_id, video_url)
    except Exception as e:
        logger.error(f"[send_video] Failed to upload. message_id {message_id}: {repr(e)}")
        logger.error(e)


def get_video_wh(video_path: str) -> Tuple[Optional[int], Optional[int]]:
    try:
        probe = ffmpeg.probe(video_path)
    except ffmpeg.Error as e:
        logger.error(e)
        return None, None

    video = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
    if video is None:
        logger.error('No video stream found')
        return None, None

    return (int(video['width'])), (int(video['height']))


def send_video_upload(bot: telegram.Bot, chat_id, message_id, video_url: str) -> None:
    bot.send_chat_action(chat_id, action=ChatAction.UPLOAD_VIDEO)
    with CustomNamedTemporaryFile(suffix='.mp4') as f:
        with requests.get(video_url, stream=True, headers={'User-Agent': USER_AGENT}) as r:
            if not r.ok:
                logger.info(f"Failed to download video ({r.status_code}) {video_url}")
                send_cant_download(bot, chat_id, message_id, video_url)
                return

            file_size = int(r.headers.get('Content-length', 0))
            if file_size >= SEND_VIDEO_SIZE_LIMIT:
                send_too_big(bot, chat_id, message_id, video_url)
                return

            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)

        with open(f.name, "rb") as infile:
            infile.seek(0, os.SEEK_END)
            filesize = infile.tell()
            if filesize >= SEND_VIDEO_SIZE_LIMIT:
                send_too_big(bot, chat_id, message_id, video_url)
                return

        width, height = get_video_wh(f.name)
        bot.send_video(
            chat_id, reply_to_message_id=message_id,
            video=open(f.name, "rb"), width=width, height=height)


def send_cant_download(bot, chat_id, message_id, video_url):
    bot.send_message(
        chat_id,
        f"""Не смог скачать видео. Качайте сами:\n\n<a href="{video_url}">Video</a>""",
        parse_mode=ParseMode.HTML, reply_to_message_id=message_id)


def send_too_big(bot, chat_id, message_id, video_url):
    bot.send_message(
        chat_id,
        f"""Телеграм не дает отправить видео больше 50 мб. Качайте сами:\n\n<a href="{video_url}">Video</a>""",
        parse_mode=ParseMode.HTML, reply_to_message_id=message_id)


def send_images(message: telegram.Message, images: List[str], text: str = '') -> bool:
    if len(images) == 0:
        return False

    if len(images) == 1:
        message.reply_photo(images[0], filename=f"photo.jpg", caption=text)
        return True

    if len(images) > 1:
        if text:
            message.reply_text(text, disable_web_page_preview=True)
            sleep(1)
        # телеграм позволяет отправить только 10 изображений в группе
        send_images_by_chunks(message, images, 10)
        return True

def send_images_by_chunks(message: telegram.Message, images: List[str], chunk_size=10) -> None:
    first = True
    for chunk in chunks(images, chunk_size):
        if first:
            first = False
        else:
            sleep(1)
        message.reply_media_group([
            InputMediaPhoto(url)  # , filename=f"{post_id}-{i + 1}.jpg")
            for i, url in enumerate(chunk)
        ])

def send_videos(message: telegram.Message, videos: List[str], text: str = '',
                text_sent: bool = False, best_quality=False) -> None:
    if len(videos) == 0:
        return

    if text_sent:
        text = ''

    if len(videos) == 1:
        send_video(message, pick_one(videos[0], best_quality), text)

    if len(videos) > 1:
        first = True
        for video_url in videos:
            send_video(message, pick_one(video_url, best_quality), text if first else '')
            sleep(1)
            first = False


def pick_one(variants: Union[str, List[str]], best_quality: bool) -> str:
    if not isinstance(variants, (list, tuple)):
        return variants

    if best_quality or len(variants) == 1:
        return variants[0]

    return variants[1]  # типа среднее качество
