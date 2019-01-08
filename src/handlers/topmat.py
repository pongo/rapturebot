# coding=UTF-8
import collections
import textwrap
from typing import List, Tuple

import telegram

from src.config import CONFIG
from src.modules.models.user import User
from src.modules.models.user_stat import UserStat
from src.utils.cache import pure_cache, cache, MONTH
from src.utils.handlers_decorators import only_users_from_main_chat
from src.utils.text_helpers import lstrip_every_line
from src.utils.time_helpers import get_current_monday, get_date_monday


def get_words_stats(words: List['str']) -> List[Tuple[str, int]]:
    counter = collections.Counter(words)
    return counter.most_common()


def get_generic_users_stats(stats: List[Tuple[UserStat, User]], all: str, mat: str) -> list:
    result = []
    for user_stat, user in stats:
        if getattr(user_stat, mat, 0) == 0:
            continue
        all_count = getattr(user_stat, all, 0)
        if all_count < 30:
            continue
        mat_count = getattr(user_stat, mat, 0)
        mat_percent = mat_count / all_count * 100
        result.append({
            'uid': user.uid,
            'all': all_count,
            'mat': mat_count,
            'mat_percent': mat_percent
        })
    return sorted(result, key=lambda x: x['mat_percent'], reverse=True)

def get_mat_users_msg_stats(stats: List[Tuple[UserStat, User]]) -> list:
    return get_generic_users_stats(stats, 'text_messages_count', 'text_messages_with_obscene_count')


def get_mat_users_words_stats(stats: List[Tuple[UserStat, User]]) -> list:
    return get_generic_users_stats(stats, 'words_count', 'obscene_words_count')


def get_header_stats(stats: List[Tuple[UserStat, User]]) -> dict:
    result = {
        'all_active_users': 0,
        'mat_users': 0,
        'mat_users_percent': 0.0,
        'all_msg': 0,
        'mat_msg': 0,
        'mat_msg_percent': 0.0,
        'all_words': 0,
        'mat_words': 0,
        'mat_words_percent': 0.0,
    }

    for user_stat, user in stats:
        if user_stat.text_messages_count == 0:
            continue

        result['all_active_users'] += 1
        result['all_msg'] += user_stat.text_messages_count
        result['all_words'] += user_stat.words_count

        if user_stat.text_messages_with_obscene_count == 0:
            continue

        result['mat_users'] += 1
        result['mat_msg'] += user_stat.text_messages_with_obscene_count
        result['mat_words'] += user_stat.obscene_words_count

    try:
        result['mat_users_percent'] = result['mat_users'] / result['all_active_users'] * 100
        result['mat_msg_percent'] = result['mat_msg'] / result['all_msg'] * 100
        result['mat_words_percent'] = result['mat_words'] / result['all_words'] * 100
    except Exception:
        pass
    return result


def get_words_from_cache(monday, cid):
    monday_str = monday.strftime('%Y%m%d')
    return pure_cache.get_list(f'mat:words:{monday_str}:{cid}')


def format_msg(title: str, stats: dict) -> str:
    def format_user_row(row) -> str:
        user = User.get(row['uid'])
        fullname = row['uid'] if not user else user.fullname
        return f"<b>{row['mat_percent']:.0f} %. {fullname}</b> — {row['mat']} из {row['all']}"

    header = lstrip_every_line(textwrap.dedent(
        f"""
        Матерщинников: {stats['header_stats']['mat_users']} из {stats['header_stats']['all_active_users']} ({stats['header_stats']['mat_users_percent']:.0f}%)
        Сообщений с матом: {stats['header_stats']['mat_msg']} из {stats['header_stats']['all_msg']} ({stats['header_stats']['mat_msg_percent']:.0f}%)
        Матерных слов: {stats['header_stats']['mat_words']} из {stats['header_stats']['all_words']} ({stats['header_stats']['mat_words_percent']:.0f}%)
        """)).strip()

    umsgs = '\n'.join(format_user_row(row) for row in stats['users_msg_stats'])
    uwords = '\n'.join(format_user_row(row) for row in stats['users_words_stats'][:10])
    words = '\n'.join(f'<b>{count}.</b> {word}' for word, count in stats['words_stats'][:10])

    msg = lstrip_every_line(textwrap.dedent(
        f"""
        <b>{title}</b>
        {header}
        
        Сапожники <i>(по проценту сообщений с матом)</i>:
        {umsgs}
        
        Топ-10 по проценту слов:
        {uwords}
        
        Топ-10 матерных слов:
        {words}
        """)).strip()
    return msg


def send_topmat(bot: telegram.Bot, send_to_cid: int, stats_from_cid: int, date=None) -> None:
    monday = get_current_monday() if date is None else get_date_monday(date)
    stats = UserStat.get_chat_stats(stats_from_cid, date)
    words = get_words_from_cache(monday, stats_from_cid)
    users_msg_stats = get_mat_users_msg_stats(stats)
    msg = format_msg('Стата по мату', {
        'header_stats': get_header_stats(stats),
        'users_msg_stats': users_msg_stats,
        'users_words_stats': get_mat_users_words_stats(stats),
        'words_stats': get_words_stats(words),
    })
    set_top_mater(stats_from_cid, users_msg_stats)
    bot.send_message(send_to_cid, msg, parse_mode=telegram.ParseMode.HTML)


def set_top_mater(stats_from_cid, users_msg_stats) -> None:
    try:
        top_mater = [row['uid'] for row in users_msg_stats[0:3]]
        cache.set(f'weekgoal:{stats_from_cid}:top_mater_uids', top_mater, time=MONTH)
    except Exception:
        pass


@only_users_from_main_chat
def private_topmat(bot: telegram.Bot, update: telegram.Update) -> None:
    send_topmat(bot, update.message.chat_id, CONFIG['anon_chat_id'])
