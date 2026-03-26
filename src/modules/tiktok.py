import re
import os
import shutil

import requests
import telegram
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

        videos = fetch_api(url)
        if not videos:
            logger.error(f"Tiktok api returns None for {url}")
            send_vxtiktok(message, url)
            return

        too_big = False
        for video_url in videos:
            r = send_video(message, video_url)
            if r["ok"]:
                logger.info(f"Processed tiktok {url}")
                return
            if r["too_big"]:
                logger.info(f"[inside] too_big tiktok {url}")
            if not too_big and r["too_big"]:
                too_big = True

        if too_big:
            logger.info(f"Processed too_big tiktok {url}")
            message.reply_html(f"""Телеграм не дает отправить видео больше 50 мб. Качайте сами:\n\n<a href="{videos[0]}">Video</a>""")
        else:
            logger.info(f"Processed VX tiktok {url}")
            send_vxtiktok(message, url)
    except Exception as e:
        logger.error("Failed to download tiktok %s: %s" % (url, repr(e)))
        logger.error(e)


def send_vxtiktok(message: telegram.Message, url: str):
    message.reply_text(url.replace("tiktok.com", "vxtiktok.com"))


def send_video(message: telegram.Message, video_url: str):
    try:
        with CustomNamedTemporaryFile(suffix='.mp4') as f:
            with requests.get(video_url, stream=True, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:101.0) Gecko/20100101 Firefox/101.0'}) as r:
                if not r.ok:
                    logger.info(f"Failed to download video ({r.status_code}) {video_url}")
                    return {"ok": False, "cant_download": True, "too_big": False}

                file_size = int(r.headers.get('Content-length', 0))
                if file_size >= SEND_VIDEO_SIZE_LIMIT:
                    return {"ok": False, "cant_download": False, "too_big": True}

                r.raw.decode_content = True
                shutil.copyfileobj(r.raw, f)

            with open(f.name, "rb") as infile:
                infile.seek(0, os.SEEK_END)
                file_size = infile.tell()
                if file_size >= SEND_VIDEO_SIZE_LIMIT:
                    return {"ok": False, "cant_download": False, "too_big": True}

            message.reply_video(video=open(f.name, "rb"))
            return {"ok": True}
    except Exception as e:
        logger.error("Failed to download tiktok: %s" % (repr(e)))
        logger.error(e)
        return {"ok": False, "cant_download": True, "too_big": False}


def fetch_api(url: str):
    r = requests.post(f'http://localhost:3001/api/v1/tiktok-video', json={"video": url})
    res = r.json()
    if not res['ok']:
        logger.error(res)
        return None

    return res["value"]["videos"]
