import re
from time import sleep
from typing import Optional, Tuple

import requests
import telegram
# import tweepy
from telegram import MessageEntity, ChatAction, InputMediaPhoto

from src.config import CONFIG
from src.utils.logger_helpers import get_logger

logger = get_logger(__name__)
# twitter_auth = CONFIG.get('twitter_auth', {})
# consumer_key = twitter_auth.get('consumer_key')
# consumer_secret = twitter_auth.get('consumer_secret')
# access_token = twitter_auth.get('access_token')
# access_token_secret = twitter_auth.get('access_token_secret')
re_twitter_url = re.compile(r"https?:\/\/twitter.com\/([0-9-a-zA-Z_]{1,20})\/status\/([0-9]*)")
twitter_third_api_key = CONFIG.get('twitter_third_api_key', None)

# if consumer_key is not None:
#     auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
#     auth.set_access_token(access_token, access_token_secret)
#     api = tweepy.API(auth)
#     logger.info('Twitter logged in')


def get_first_twitter_id_from_message(message: telegram.Message) -> Tuple[Optional[str], Optional[str]]:
    twits = [
        parse_twitter_id(n)
        for n in message.parse_entities([MessageEntity.URL]).values()
    ]
    for twitter_username, twitter_id in twits:
        if twitter_id is not None:
            return twitter_username, twitter_id
    return None, None


def parse_twitter_id(text: str) -> Tuple[Optional[str], Optional[str]]:
    m = re_twitter_url.search(text)
    try:
        if m:
            return m.group(1), m.group(2)
        return None, None
    except Exception as _:
        return None, None


def twitter_cmd(_bot: telegram.Bot, update: telegram.Update) -> None:
    process_message_for_twitter(update.effective_message)


def process_message_for_twitter(message: telegram.Message) -> bool:
    """
    Отправляет видео из первой твиттер-ссылки, если она есть
    :return: False, если твиттер-ссылки нет
    """
    # if consumer_key is None:
    #     return False
    twitter_username, twitter_id = get_first_twitter_id_from_message(message)
    if twitter_id is None:
        return False
    call(message, twitter_username, twitter_id)
    return True


# https://rapidapi.com/Glavier/api/twitter135/
def get_status_via_third_api(twitter_id: str):
    if twitter_third_api_key is None:
        return

    # api_url = "https://twitter135.p.rapidapi.com/TweetDetail/"
    # # api_url = "https://88b2b16c-e4a8-4e68-8dbf-b888b267fc68.mock.pstmn.io/TweetDetail/"
    # response = requests.request("GET", api_url, headers={
    #     "X-RapidAPI-Key": twitter_third_api_key,
    #     "X-RapidAPI-Host": "twitter135.p.rapidapi.com"
    # }, params={"id": twitter_id})

    api_url = "https://twitter-api47.p.rapidapi.com/v1/tweet-details"
    response = requests.request("GET", api_url, headers={
        "X-RapidAPI-Key": twitter_third_api_key,
        "X-RapidAPI-Host": "twitter-api47.p.rapidapi.com"
    }, params={"tweetId": twitter_id})

    if response.status_code != 200:
        return None
    try:
        json = response.json()
        if 'entries' in json:
            entries = json['entries']
        elif 'threaded_conversation_with_injections_v2' in json:
            entries = json['threaded_conversation_with_injections_v2']['instructions'][0][
                'entries']
        else:
            entries = json['data']['threaded_conversation_with_injections']['instructions'][0]['entries']
        for entry in entries:
            if entry['entryId'] != f"tweet-{twitter_id}":
                continue
            result = entry['content']['itemContent']['tweet_results']['result']
            if 'legacy' in result:
                data = result['legacy']
            elif 'tweet' in result and 'legacy' in result['tweet']:
                data = result['tweet']['legacy']
            else:
                return None
            return AttrDict(data)
        return None
    except:
        return None


class StatusDict(dict):
    """
    dot.notation access to dictionary attributes
    https://stackoverflow.com/a/72761907/136559
    """
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__
    __delattr__ = dict.__delitem__


class AttrDict(dict):
    """
    https://stackoverflow.com/a/14620633/136559
    """
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


def call(message: telegram.Message, twitter_username: str, twitter_id: str):
    try:
        message.chat.send_action(action=ChatAction.UPLOAD_VIDEO)
        is_private = message.chat.id >= 0

        # if use_third_api:
        #     status = get_status_via_third_api(twitter_id)
        # else:
        #     status = api.get_status(twitter_id, tweet_mode='extended')
        status = get_status_via_third_api(twitter_id)
        if status is None:
            logger.error(f"Third twitter api returns None for {twitter_id}")
            message.reply_text(f"https://vxtwitter.com/{twitter_username}/status/{twitter_id}")
            return
        text = status.full_text if hasattr(status, 'full_text') else ''
        if not hasattr(status, 'extended_entities'):
            message.reply_text(text)
            return
        photos_urls = get_urls_of_photos(status)
        video_urls = get_urls_of_video(status, is_private)
        if video_urls:
            if len(video_urls) == 1:
                message.reply_html(f"<a href='{video_urls[0]}'>Video</a>\n\n{text}")
            if len(video_urls) > 1:
                for num, video in enumerate(video_urls, start=1):
                    end = f"\n\n{text}" if num == 1 else ''
                    message.reply_html(f"<a href='{video}'>Video {num}</a>{end}")
                    sleep(1)
        if photos_urls:
            if len(photos_urls) == 1:
                message.reply_photo(photos_urls[0], filename=f"{twitter_id}.jpg", caption=text)
            else:
                message.reply_media_group([
                    InputMediaPhoto(url)  # , filename=f"{post_id}-{i + 1}.jpg")
                    for i, url in enumerate(photos_urls)
                ])
                sleep(1)
                message.reply_text(text, disable_web_page_preview=True)
        logger.info(f"Processed twitter {twitter_id}")
    except Exception as e:
        logger.error("Failed to download twitter %s: %s" % (twitter_id, repr(e)))
        logger.error(e)


def get_urls_of_photos(status):
    if not hasattr(status, 'extended_entities'):
        return []
    return [
        media['media_url_https']
        for media in status.extended_entities['media']
        if media['type'] == 'photo'
    ]


def get_urls_of_video(status, best_quality=False):
    """
    Возвращает массив урлов разного качества на видео из твита.
    """
    if not hasattr(status, 'extended_entities'):
        return []
    video_urls = []
    for media in status.extended_entities['media']:
        if media['type'] == "photo":
            continue
        urls_bitrate = [
            (file['url'], file['bitrate'])
            for file in media['video_info']['variants']
            if file['content_type'] == "video/mp4"
        ]
        if not urls_bitrate:
            continue
        if best_quality:
            urls_bitrate.sort(key=lambda x: x[1], reverse=True)  # сначала самые большие видео
            video_urls.append(urls_bitrate[0][0])
        else:
            urls_bitrate.sort(key=lambda x: x[1], reverse=False)
            if len(urls_bitrate) > 1:
                video_urls.append(urls_bitrate[1][0])  # среднее качество
            else:
                video_urls.append(urls_bitrate[0][0])
    return video_urls
