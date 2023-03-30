import html
import json
import re
import os
import shutil
from typing import Union

import requests
import telegram
from jsonpath_ng import parse
from telegram import MessageEntity, ChatAction

from src.utils.logger_helpers import get_logger
from src.utils.misc import CustomNamedTemporaryFile

logger = get_logger(__name__)
re_tiktok_url = re.compile(r"^https:\/\/(www|m|vm|vt)\.tiktok\.com\/.+$")

SEND_VIDEO_SIZE_LIMIT = 50 * 1048576  # 50mb https://core.telegram.org/bots/api#sendvideo


def get_first_tiktok_url_from_message(message: telegram.Message):
    message_entities = [
        n
        for n in message.parse_entities([MessageEntity.URL]).values()
        if re_tiktok_url.match(n)
    ]
    return message_entities[0] if message_entities else None


def process_message_for_tiktok(message: telegram.Message) -> bool:
    url = get_first_tiktok_url_from_message(message)
    if url is None:
        return False
    url = url.replace('vt.tiktok', 'vm.tiktok')
    call(message, url)
    return True


# yt-dlp тоже умеет тиктоки скачивать. через --max-filesize можно задать ограничение в 50 мб
def call(message: telegram.Message, url: str):
    try:
        message.chat.send_action(action=ChatAction.UPLOAD_VIDEO)
        res = requests.post(f'http://localhost:3000/api/v1/tiktok-video', json={"video": url})
        if not res.ok:
            logger.error("Failed to request from TikBot API: %s" % res.status_code)
            return

        item_infos = res.json()
        fetch_key = lambda key: parse("$..%s" % key).find(item_infos)[0].value

        video_url = fetch_key("videoUrl")
        #logger.info(video_url)
        if len(video_url) == 0:
            logger.error("Failed to find videoUrl in video meta: %s" % json.dumps(item_infos))
            message.reply_html(
                f"Could not download video \U0001f613, TikTok gave a bad video meta response \U0001f97a")
            return

        with CustomNamedTemporaryFile(suffix='.mp4') as f:
            tmp_url = video_url #.replace('https://v1.musicaldown.com/dl?url=', 'https://muscdn.xyz/dl?url=')
            with requests.get(tmp_url, stream=True, headers=item_infos.get("headers", { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0' })) as r:
                if not r.ok:
                    logger.info(f"Failed to download video {item_infos}")
                    message.reply_html(f"""Could not download video \U0001f613, TikTok gave a bad response \U0001f97a ({r.status_code}). <a href="{video_url}">Video</a>""")
                    return
                #logger.info(r.headers)
                file_size = int(r.headers.get('Content-length', 0))
                #if file_size == 0:
                    #message.reply_html(f"<a href='{video_url}'>Video</a>")
                    #return
                if file_size >= SEND_VIDEO_SIZE_LIMIT:
                    message.reply_html(f"Телеграм не дает отправить видео больше 50 мб. Качайте сами:\n\n{video_url}")
                    return
                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)
                
            with open(f.name, "rb") as infile:
                infile.seek(0, os.SEEK_END)
                filesize = infile.tell()
                #logger.info(filesize)
                if filesize >= SEND_VIDEO_SIZE_LIMIT:
                    message.reply_html(f"Телеграм не дает отправить видео больше 50 мб. Качайте сами:\n\n{video_url}")
                    return

            message.reply_video(
                video=open(f.name, "rb"),
                disable_notification=True,
                caption=build_caption(fetch_key),
                parse_mode=telegram.ParseMode.HTML,
            )
            logger.info(f"Processed tiktok {url}")
    except Exception as e:
        logger.error("Failed to download tiktok %s: %s" % (url, repr(e)))
        logger.error(e)


def build_caption(fetch_key):
    try:
        video_caption = fetch_key("text")
        if "#" in video_caption:
            video_caption = video_caption.split("#")[0]

        likes = space_thousand(int(fetch_key("diggCount") or 0))
        comments = space_thousand(int(fetch_key("commentCount") or 0))
        plays = space_thousand(int(fetch_key("playCount") or 0))

        video_caption = html.escape(video_caption.strip())
        for mention in fetch_key("mentions"):
            video_caption = video_caption.replace(mention, f"<a href='https://tiktok.com/{mention}'>{mention}</a>")

        return f"{video_caption}\n\n❤ {likes}\n💬 {comments}\n⏯ {plays}"
    except:
        return ''


def space_thousand(num: Union[int, float]):
    """
    https://stackoverflow.com/a/18891054/136559
    """
    return '{:,}'.format(num).replace(',', ' ')
