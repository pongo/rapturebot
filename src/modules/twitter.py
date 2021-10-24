import re
from typing import Optional

import telegram
import tweepy
from telegram import MessageEntity, ChatAction

from src.config import CONFIG
from src.utils.logger_helpers import get_logger

logger = get_logger(__name__)

twitter_auth = CONFIG.get('twitter_auth', {})
consumer_key = twitter_auth.get('consumer_key')
consumer_secret = twitter_auth.get('consumer_secret')
access_token = twitter_auth.get('access_token')
access_token_secret = twitter_auth.get('access_token_secret')

if consumer_key:
    auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
    auth.set_access_token(access_token, access_token_secret)

    api = tweepy.API(auth)
    logger.info('Twitter logged in')

re_twitter_url = re.compile(r"https?:\/\/twitter.com\/[0-9-a-zA-Z_]{1,20}\/status\/([0-9]*)")


def get_first_twitter_id_from_message(message: telegram.Message):
    twitters = [
        parse_twitter_id(n)
        for n in message.parse_entities([MessageEntity.URL]).values()
    ]
    for twitter_id in twitters:
        if twitter_id is not None:
            return twitter_id
    return None

def process_message_for_twitter(message: telegram.Message, twitter_id=None):
    if twitter_id is None:
        twitter_id = get_first_twitter_id_from_message(message)
    if twitter_id is None:
        return

    try:
        message.chat.send_action(action=ChatAction.UPLOAD_VIDEO)
        video_urls = get_urls_of_video(twitter_id)
        if not video_urls:
            return

        message.reply_html(f"<a href='{video_urls[0]}'>Video</a>")
        logger.info(f"Processed twitter {twitter_id}")
    except Exception as e:
        logger.error("Failed to download twitter %s: %s" % (twitter_id, repr(e)))
        logger.error(e)

def get_urls_of_video(twitter_id):
    """
    Возвращает массив урлов разного качества на видео из твита.
    """
    status = api.get_status(twitter_id, tweet_mode='extended')
    if status.extended_entities and status.extended_entities['media'][0]['type'] == "video":
        return [
            file['url']
            for file in status.extended_entities['media'][0]['video_info']['variants']
            if file['content_type'] == "video/mp4"
        ]
    return []

def parse_twitter_id(text: str) -> Optional[str]:
    m = re_twitter_url.search(text)
    try:
        return m.group(1) if m else None
    except Exception as _:
        return None
