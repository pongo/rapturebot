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
CACHE_PREFIX = 'instagram'
MODULE_NAME = CACHE_PREFIX
callback_upload_video = 'instagram_upload_video'
re_instagram_url = re.compile(r"instagram\.com\S*?\/(?:p|tv|reel)\/([\w-]+)\/?")
re_instagram_story = re.compile(r"instagram.com/stories/(?:\S+)/(\d+)/?")
instagram_user = CONFIG.get('instagram_user')
SEND_VIDEO_SIZE_LIMIT = 50 * 1048576  # 50mb https://core.telegram.org/bots/api#sendvideo

# if os.path.isfile('instaloader.session') and instagram_user is not None:
if False:
    L = instaloader.Instaloader(
        proxy=CONFIG.get('instagram_proxy', None)
        # user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0"
    )
    L.load_session_from_file(instagram_user, 'instaloader.session')


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


def get_first_instagram_post_id_from_message(message: telegram.Message):
    posts = [
        parse_instagram_post_id(n)
        for n in message.parse_entities([MessageEntity.URL]).values()
    ]
    for post in posts:
        if post is not None:
            return post[0], post[1]
    return None


def get_first_instagram_story_id_from_message(message: telegram.Message):
    stories = [
        parse_instagram_story_id(n)
        for n in message.parse_entities([MessageEntity.URL]).values()
    ]
    for story in stories:
        if story is not None:
            return story[0], story[1]
    return None


def parse_instagram_post_id(text: str):
    m = re_instagram_url.search(text)
    try:
        return (m.group(1), text) if m else None
    except Exception as _:
        return None


def parse_instagram_story_id(text: str):
    m = re_instagram_story.search(text)
    try:
        return (m.group(1), text) if m else None
    except Exception as _:
        return None


def process_message_for_instagram(message: telegram.Message) -> bool:
    if not instaloader_session_exists or instagram_user is None:
        return False

    post = get_first_instagram_post_id_from_message(message)
    if post is not None:
        post_id, url = post
        call(message, post_id, url)
        return True

    story = get_first_instagram_story_id_from_message(message)
    if story is not None:
        story_id, url = story
        call(message, story_id, url, story=True)
        return True

    return False


def call(message: telegram.Message, post_id: str, url: str, story=False):
    try:
        message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)
        images, videos = fetch_post(post_id, url, story)
        # is_private = message.chat.id >= 0

        if len(images) == 0 and len(videos) == 0:
            message.reply_text('Unable to download the post ☹️ Try later')
            return

        # если у нас картинка и видео, то нужно отправить несколько сообщений,
        # поэтому здесь нигде нет return'ов
        send_images(post_id, message, images)
        send_videos(message, videos)
        logger.info(f"Processed instagram {post_id}")
    except Exception as e:
        logger.error("Failed to download instagram %s: %s" % (post_id, repr(e)))
        logger.error(e)


def send_images(post_id: str, message: telegram.Message, images: List[str]) -> None:
    if len(images) == 1:
        # телеграм сейчас сам показывает превью поста, поэтому нет смысла для чатов отправлять.
        # но мы всегда отправляем если запрос из лички или если есть видео
        # if is_private or len(videos) > 0:
        message.reply_photo(images[0], filename=f"{post_id}.jpg")

    # несколько изображений отправляем группой
    if len(images) > 1:
        message.reply_media_group([
            InputMediaPhoto(url)  # , filename=f"{post_id}-{i + 1}.jpg")
            for i, url in enumerate(images)
        ])


def send_videos(message: telegram.Message, videos: List[str]) -> None:
    if len(videos) == 0:
        return

    if len(videos) == 1:
        send_video(message, videos[0])

    if len(videos) > 1:
        for video_url in videos:
            send_video(message, video_url)
            sleep(1)


class InstagramActive:
    @staticmethod
    def create_and_return_active_id(video_url: str) -> str:
        key = str(uuid.uuid4())
        hour = 60 * 60
        cache.set(f"instagram:active:{key}", video_url, time=hour)
        return key

    @staticmethod
    def get_active_video_url(key: str) -> Optional[str]:
        return cache.get(f"instagram:active:{key}", None)


def send_video(message: telegram.Message, video_url: str) -> None:
    message_id = message.message_id
    reply_markup = get_reply_markup([
        [('Отправить как видео', (extend_initial_data({
            'value': callback_upload_video, 'message_id': message_id,
            'active_id': InstagramActive.create_and_return_active_id(video_url)
        })))],
    ])
    message.reply_html(f"""<a href="{video_url}">Video</a>""", reply_markup=reply_markup)


def instagram_callback_handler(bot: telegram.Bot, _: telegram.Update,
                               query: telegram.CallbackQuery, data) -> None:
    if 'module' not in data or data['module'] != MODULE_NAME:
        return
    if data['value'] == callback_upload_video:
        chat_id = query.message.chat_id
        remove_inline_keyboard(bot, chat_id, query.message.message_id)
        video_url = InstagramActive.get_active_video_url(data['active_id'])

        if video_url is None:
            bot.answer_callback_query(query.id, 'Загрузить видео можно только в течение часа',
                                      show_alert=True)
            return

        message_id = data['message_id']
        try:
            send_video_upload(bot, chat_id, message_id, video_url)
        except Exception as e:
            logger.error(f"Failed to upload to query instagram. message_id {message_id}: {repr(e)}")
            logger.error(e)
        bot.answer_callback_query(query.id)
        return


def get_video_wh(video_path: str) -> Tuple[Optional[int], Optional[int]]:
    try:
        probe = ffmpeg.probe(video_path)
    except ffmpeg.Error as e:
        logger.error(e)
        return None, None

    video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'),
                        None)
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
                bot.send_message(
                    chat_id,
                    f"""Не смог скачать видео. Качайте сами:\n\n<a href="{video_url}">Video</a>""",
                    parse_mode=ParseMode.HTML, reply_to_message_id=message_id)
                return
            file_size = int(r.headers.get('Content-length', 0))
            # if file_size == 0:
            # message.reply_html(f"<a href='{video_url}'>Video</a>")
            # return
            if file_size >= SEND_VIDEO_SIZE_LIMIT:
                bot.send_message(
                    chat_id,
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
                    chat_id,
                    f"""Телеграм не дает отправить видео больше 50 мб. Качайте сами:\n\n<a href="{video_url}">Video</a>""",
                    parse_mode=ParseMode.HTML, reply_to_message_id=message_id)
                return

        width, height = get_video_wh(f.name)
        bot.send_video(chat_id, video=open(f.name, "rb"), reply_to_message_id=message_id,
                       width=width, height=height)


def fetch_via_instaloader(post_id: str):
    try:
        images = []
        videos = []
        post = Post.from_shortcode(L.context, post_id)

        for node in post.get_sidecar_nodes():
            if node.is_video:
                videos.append(node.video_url)
            else:
                images.append(node.display_url)

        if len(images) == 0 and len(videos) == 0:
            if post.is_video:
                videos.append(post.video_url)
            else:
                images.append(post.url)

        return images, videos
    except Exception as e:
        logger.error("Failed to download instagram %s: %s" % (post_id, repr(e)))
        logger.error(e)
        return None


def fetch_via_our_vision_api(post_id: str, url: str, story=False):
    if story:
        r = requests.post(f'http://localhost:3000/api/v1/instagram_story',
                          json={"id": post_id, "url": url})
    else:
        r = requests.post(f'http://localhost:3000/api/v1/instagram',
                          json={"post_id": post_id, "url": url})
    res = r.json()
    if not res['ok']:
        logger.error(res)
        return None

    images = []
    videos = []
    for link in res["links"]:
        lower_link = link.lower()
        if ".mp4" in lower_link:
            videos.append(link)
        # if ".jpg" in lower_link or ".jpeg" in lower_link:
        else:
            images.append(link)
    return images, videos


def fetch_post(post_id: str, url: str, story=False):
    # return [], ["https://download.samplelib.com/mp4/sample-5s.mp4"]

    # result = fetch_via_instaloader(post_id)
    # if result is not None:
    #    return result

    result = fetch_via_our_vision_api(post_id, url, story)
    if result is not None:
        return result

    return [], []
