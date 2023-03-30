import os
import re
import shutil
from time import sleep
from typing import List

import requests
import telegram
from telegram import MessageEntity, InputMediaPhoto, ChatAction

from packages.instaloader_proxy import instaloader, Post
from src.config import CONFIG, instaloader_session_exists
from src.utils.logger_helpers import get_logger
from src.utils.misc import CustomNamedTemporaryFile

logger = get_logger(__name__)
re_instagram_url = re.compile(r"instagram\.com\S*?\/(?:p|tv|reel)\/([\w-]+)\/?")
instagram_user = CONFIG.get('instagram_user')
SEND_VIDEO_SIZE_LIMIT = 50 * 1048576  # 50mb https://core.telegram.org/bots/api#sendvideo

#if os.path.isfile('instaloader.session') and instagram_user is not None:
if False:
    L = instaloader.Instaloader(
        proxy=CONFIG.get('instagram_proxy', None)
        #user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/110.0"
    )
    L.load_session_from_file(instagram_user, 'instaloader.session')


def get_first_instagram_post_id_from_message(message: telegram.Message):
    posts = [
        parse_instagram_post_id(n)
        for n in message.parse_entities([MessageEntity.URL]).values()
    ]
    for post in posts:
        if post is not None:
            return post[0], post[1]
    return None


def process_message_for_instagram(message: telegram.Message) -> bool:
    if not instaloader_session_exists or instagram_user is None:
        return False
    post = get_first_instagram_post_id_from_message(message)
    if post is None:
        return False
    post_id, url = post
    call(message, post_id, url)
    return True


def call(message: telegram.Message, post_id: str, url: str):
    try:
        message.chat.send_action(action=ChatAction.UPLOAD_PHOTO)
        images, videos = fetch_post(post_id, url)
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

    message.chat.send_action(action=ChatAction.UPLOAD_VIDEO)

    if len(videos) == 1:
        send_video(message, videos[0])

    if len(videos) > 1:
        for video_url in videos:
            send_video(message, video_url)
            sleep(1)


def send_video(message: telegram.Message, video_url: str) -> None:
    with CustomNamedTemporaryFile(suffix='.mp4') as f:
        with requests.get(video_url, stream=True, headers={
            'User-Agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/109.0"
        }) as r:
            if not r.ok:
                logger.info(f"Failed to download video ({r.status_code}) {video_url}")
                message.reply_html(f"""<a href="{video_url}">Video</a>""")
                return
            file_size = int(r.headers.get('Content-length', 0))
            # if file_size == 0:
            # message.reply_html(f"<a href='{video_url}'>Video</a>")
            # return
            if file_size >= SEND_VIDEO_SIZE_LIMIT:
                message.reply_html(f"""Телеграм не дает отправить видео больше 50 мб. Качайте сами:\n\n<a href="{video_url}">Video</a>""")
                return
            r.raw.decode_content = True
            shutil.copyfileobj(r.raw, f)

        with open(f.name, "rb") as infile:
            infile.seek(0, os.SEEK_END)
            filesize = infile.tell()
            # logger.info(filesize)
            if filesize >= SEND_VIDEO_SIZE_LIMIT:
                message.reply_html(f"""Телеграм не дает отправить видео больше 50 мб. Качайте сами:\n\n<a href="{video_url}">Video</a>""")
                return

        message.reply_video(video=open(f.name, "rb"), disable_notification=True)


def parse_instagram_post_id(text: str):
    m = re_instagram_url.search(text)
    try:
        return (m.group(1), text) if m else None
    except Exception as _:
        return None


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


def fetch_via_our_vision_api(post_id: str, url: str):
    r = requests.post(f'http://localhost:3000/api/v1/instagram', json={"post_id": post_id, "url": url})
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
        #if ".jpg" in lower_link or ".jpeg" in lower_link:
        else:
            images.append(link)
    return images, videos


def fetch_post(post_id: str, url: str):
    # return [], ["https://scontent-fml2-1.cdninstagram.com/v/t66.30100-16/10000000_1227502374528111_4339098781378517958_n.mp4?efg=eyJ2ZW5jb2RlX3RhZyI6InZ0c192b2RfdXJsZ2VuLjEwODAuY2xpcHMuaGlnaCIsInFlX2dyb3VwcyI6IltcImlnX3dlYl9kZWxpdmVyeV92dHNfb3RmXCJdIn0&_nc_ht=scontent-fml2-1.cdninstagram.com&_nc_cat=103&_nc_ohc=C9aUgshl6EsAX9EEEDg&edm=ALQROFkBAAAA&vs=885627935950029_3328842131&_nc_vs=HBksFQAYJEdJQ1dtQUJ2cFA0cWFGd0VBTWFiWlNWYWt6YzhicFIxQUFBRhUAAsgBABUAGCRHSGhNVEJOWUQzYmI4d1VFQUIzVnh2Q1hqSVU0YnBSMUFBQUYVAgLIAQAoABgAGwAVAAAmmMu%2B0vbc%2BD8VAigCQzMsF0BROZmZmZmaGBJkYXNoX2hpZ2hfMTA4MHBfdjERAHX%2BBwA%3D&_nc_rid=be6d5b32eb&ccb=7-5&oh=00_AfCLxf_Ht52OfHPhg6zMZvZByzGwVs5WPX116Zk6K9MT1w&oe=6426F952&_nc_sid=30a2ef"]

    #result = fetch_via_instaloader(post_id)
    #if result is not None:
    #    return result

    result = fetch_via_our_vision_api(post_id, url)
    if result is not None:
        return result

    return [], []
