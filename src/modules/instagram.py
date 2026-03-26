import re
from typing import Optional

import requests
import telegram
from telegram import MessageEntity, ChatAction

from src.utils.callback_helpers import get_callback_data
from src.utils.logger_helpers import get_logger
from src.utils.send_video_helpers import send_images, send_videos

logger = get_logger(__name__)
CACHE_PREFIX = 'instagram'
MODULE_NAME = CACHE_PREFIX
callback_upload_video = 'instagram_upload_video'
re_instagram_url = re.compile(r"instagram\.com\S*?\/(?:p|tv|reel)\/([\w-]+)\/?")
re_instagram_story = re.compile(r"instagram.com/stories/(?:\S+)/(\d+)/?")
SEND_VIDEO_SIZE_LIMIT = 50 * 1048576  # 50mb https://core.telegram.org/bots/api#sendvideo


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


def get_first_instagram_share_url(message: telegram.Message):
    for url in message.parse_entities([MessageEntity.URL]).values():
        if 'instagram.com/share/' in url:
            return url
    return None


def get_post_from_share(message: telegram.Message):
    share_url = get_first_instagram_share_url(message)
    if not share_url:
        return None

    # через редирект получаем настоящую ссылку
    r = requests.head(share_url, allow_redirects=True)
    return parse_instagram_post_id(r.url)


def process_message_for_instagram(message: telegram.Message) -> bool:
    post = get_post_from_share(message)  # instagram.com/share/ links
    if post is not None:
        post_id, url = post
        call(message, post_id, url)
        return True

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
        # is_private = message.chat.id >= 0
        r = fetch_post(post_id, url, story)
        if r is None:
            logger.error(f"Third instagram api returns None for {post_id}")
            message.reply_text(url.replace('instagram.com', 'eeinstagram.com'))
            return

        images, videos = r
        send_images(message, images)
        send_videos(message, videos)
        logger.info(f"Processed instagram {post_id}")
    except Exception as e:
        logger.error("Failed to download instagram %s: %s" % (post_id, repr(e)))
        logger.error(e)


def fetch_post(post_id: str, url: str, story=False):
    # return [], ["https://download.samplelib.com/mp4/sample-5s.mp4"]
    # return ["https://download.samplelib.com/jpeg/sample-clouds-400x300.jpg"], []
    # return [
    #            "https://download.samplelib.com/jpeg/sample-clouds-400x300.jpg",
    #            "https://download.samplelib.com/jpeg/sample-city-park-400x300.jpg",
    #            "https://download.samplelib.com/jpeg/sample-birch-400x300.jpg",
    #            "https://download.samplelib.com/jpeg/sample-red-400x300.jpg",
    #            "https://download.samplelib.com/jpeg/sample-green-400x300.jpg",
    #            "https://download.samplelib.com/jpeg/sample-blue-400x300.jpg",
    #            "https://download.samplelib.com/jpeg/sample-red-200x200.jpg",
    #            "https://download.samplelib.com/jpeg/sample-green-200x200.jpg",
    #            "https://download.samplelib.com/jpeg/sample-blue-200x200.jpg",
    #            "https://download.samplelib.com/jpeg/sample-red-100x75.jpg",
    #            "https://download.samplelib.com/jpeg/sample-green-100x75.jpg",
    #            # "https://download.samplelib.com/jpeg/sample-blue-100x75.jpg"
    #        ], []
    # return None

    if story:
        r = requests.post(f'http://localhost:3001/api/v1/instagram_story',
                          json={"id": post_id, "url": url})
    else:
        r = requests.post(f'http://localhost:3001/api/v2/instagram',
                          json={"post_id": post_id})
    res = r.json()
    if not res['ok']:
        logger.error(res)
        return None

    videos = res["value"]["videos"]
    images = res["value"]["images"]
    if len(images) == 0 and len(videos) == 0:
        logger.error("Failed to download instagram %s: empty result" % post_id)
        return None
    return images, videos
