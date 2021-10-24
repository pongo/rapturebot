import os
import re
from time import sleep
from typing import Optional

import telegram
from telegram import MessageEntity, InputMediaPhoto, ChatAction

from packages.instaloader_proxy import instaloader, Post
from src.config import CONFIG
from src.utils.logger_helpers import get_logger

logger = get_logger(__name__)
re_instagram_url = re.compile(r"instagram\.com\S*?\/(?:p|tv|reel)\/([\w-]+)\/?")

L = instaloader.Instaloader(proxy=CONFIG.get('instagram_proxy', None))
if os.path.isfile('instaloader.session'):
    L.load_session_from_file(CONFIG.get('instagram_user'), 'instaloader.session')


def get_first_instagram_post_id_from_message(message: telegram.Message):
    posts = [
        parse_instagram_post_id(n)
        for n in message.parse_entities([MessageEntity.URL]).values()
    ]
    for post_id in posts:
        if post_id is not None:
            return post_id
    return None


def process_message_for_instagram(message: telegram.Message, post_id=None):
    if post_id is None:
        post_id = get_first_instagram_post_id_from_message(message)
    if post_id is None:
        return

    try:
        message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)
        images, videos = fetch_post(post_id)
        is_private = message.chat.id >= 0

        if len(images) == 0 and len(videos) == 0:
            message.reply_text('Unable to download the post ☹️ Try later')
            return

        # если у нас картинка и видео, то нужно отправить несколько сообщений,
        # поэтому здесь нигде нет return'ов

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

        # для инстаграм поста с видео телега вставляет только картинку, без самого видео.
        # поэтому отправляем мы отправляем ссылку на видео -- тогда телега вставляет уже плеер с видео.
        #
        # отправляем ссылкой, потому что на vercel ограничение на загрузку файлов больше 5 mb.
        # (и я не осилил загрузку потоком)
        if len(videos) == 1:
            message.reply_html(f"<a href='{videos[0]}'>Video</a>")

        # несколько видео отправляем каждое в своем сообщении, чтобы телега вставляла плеер
        if len(videos) > 1:
            for num, video in enumerate(videos):
                message.reply_html(f"<a href='{video}'>Video {num + 1}</a>")
                sleep(1)
        logger.info(f"Processed instagram {post_id}")
    except Exception as e:
        logger.error("Failed to download instagram %s: %s" % (post_id, repr(e)))
        logger.error(e)


def parse_instagram_post_id(text: str) -> Optional[str]:
    m = re_instagram_url.search(text)
    try:
        return m.group(1) if m else None
    except Exception as e:
        return None

def fetch_post(post_id):
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
