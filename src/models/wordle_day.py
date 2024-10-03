import re
from dataclasses import dataclass
from threading import Lock
from typing import Optional, List

import telegram
from sqlalchemy import Column, Integer, BigInteger, Boolean
from telegram.ext import run_async

from src.models.user import User
from src.utils.cache import bot_id
from src.utils.db import Base, add_to_db, session_scope, retry
from src.utils.handlers_decorators import chat_guard, collect_stats, command_guard
from src.utils.logger_helpers import get_logger
from src.utils.telegram_helpers import send_long

logger = get_logger(__name__)


@dataclass
class WordleDayRecord:
    user_id: int
    day: int
    attempts: Optional[int]
    won: bool


@dataclass
class WordleStatsRow:
    user_id: int
    max_consecutive_days: int
    avg_win_percentage: int
    avg_attempts_per_game: str


@dataclass
class WordleFullStatsRow:
    user_id: int
    total_games_played: int
    max_consecutive_days: int
    avg_win_percentage: int
    avg_attempts_per_game: str


class WordleDayDB(Base):
    __tablename__ = 'wordle_day'

    # CREATE TABLE `wordle_day` (
    # 	`day` INT(11) NOT NULL,
    # 	`uid` INT(11) NOT NULL,
    # 	`attempts` TINYINT(1) NULL DEFAULT NULL,
    # 	`won` TINYINT(1) NULL DEFAULT '0',
    # 	PRIMARY KEY (`day`, `uid`)
    # )

    day = Column(Integer, primary_key=True)
    uid = Column(BigInteger, primary_key=True)
    attempts = Column(Integer, default=None)
    won = Column(Boolean, default=False)

    @staticmethod
    @retry(logger=logger)
    def add(wordle: WordleDayRecord):
        try:
            if WordleDayDB.exists(wordle):
                logger.error(f'Wordle already exists: {wordle}')
                return
            add_to_db(WordleDayDB(
                day=wordle.day, uid=wordle.user_id, attempts=wordle.attempts, won=wordle.won
            ))
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't add wordle_day {wordle.user_id} to DB")

    @staticmethod
    @retry(logger=logger)
    def exists(wordle: WordleDayRecord) -> bool:
        try:
            with session_scope() as db:
                c = db.query(WordleDayDB) \
                    .filter(WordleDayDB.day == wordle.day) \
                    .filter(WordleDayDB.uid == wordle.user_id) \
                    .count()
                return c > 0
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't check wordle exists {wordle}")

    @staticmethod
    @retry(logger=logger)
    def get_stats() -> List[WordleStatsRow]:
        try:
            with session_scope() as db:
                q = db.execute(
                    f"""
WITH consecutive_days
  AS (SELECT UID,
             DAY,
             attempts,
             won,
             DAY - ROW_NUMBER() OVER (PARTITION BY UID ORDER BY DAY) AS grp
        FROM wordle_day),
     latest_sequence
  AS (SELECT c.uid,
             c.day,
             c.attempts,
             c.won
        FROM consecutive_days c
       INNER JOIN (SELECT UID, MAX(grp) AS max_grp FROM consecutive_days GROUP BY UID) m
          ON c.uid = m.uid
         AND c.grp = m.max_grp)
SELECT UID,
       COUNT(*) AS max_consecutive_days,
       ROUND(AVG(won) * 100) AS avg_win_percentage,
       ROUND(AVG(attempts), 2) AS avg_attempts_per_game
  FROM latest_sequence
 GROUP BY UID
HAVING max_consecutive_days > 1
 ORDER BY max_consecutive_days DESC
                    """).fetchall()
                return [
                    WordleStatsRow(x[0], x[1], int(x[2]), str(x[3]))
                    for x in q
                ]
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't get wordle stats")

    @staticmethod
    @retry(logger=logger)
    def get_full() -> List[WordleFullStatsRow]:
        try:
            with session_scope() as db:
                db.execute("""SET @curUid := 0, @curStreak := 0, @lastDay := 0;""")
                q = db.execute(
                    f"""
SELECT 
  a.uid,
  d.total_games_played,
  a.max_consecutive_days,
  b.avg_win_percentage,
  c.avg_attempts_per_game
FROM
(SELECT uid, MAX(consecutive_days) as max_consecutive_days
FROM (
  SELECT
    uid,
    day,
    CASE
      WHEN @curUid = uid AND day = @lastDay + 1 THEN @curStreak := @curStreak + 1
      WHEN @curUid = uid THEN @curStreak := 1
      ELSE @curStreak := 1
    END AS consecutive_days,
    @curUid := uid,
    @lastDay := day
  FROM wordle_day
  ORDER BY uid, day
) AS subquery
GROUP BY uid) a
JOIN
  (SELECT uid, ROUND(AVG(won) * 100) AS avg_win_percentage FROM wordle_day GROUP BY uid) b ON a.uid = b.uid
JOIN
  (SELECT uid, ROUND(AVG(attempts), 2) AS avg_attempts_per_game FROM wordle_day WHERE attempts IS NOT NULL GROUP BY uid) c ON a.uid = c.uid
JOIN 
  (SELECT uid, COUNT(*) AS total_games_played FROM wordle_day GROUP BY uid) d ON a.uid = d.uid
ORDER BY d.total_games_played DESC
                            """).fetchall()
                return [
                    WordleFullStatsRow(x[0], int(x[1]), int(x[2]), int(x[3]), str(x[4]))
                    for x in q
                ]
        except Exception as e:
            logger.error(e)
            raise Exception(f"Can't get wordle full stats")


class WordleDay:
    lock = Lock()

    @classmethod
    @run_async
    def check_message(cls, message: telegram.Message) -> None:
        wordle = parse_wordle_message(message)
        if wordle is None:
            return

        with cls.lock:
            try:
                print(wordle)
                WordleDayDB.add(wordle)
            except Exception as e:
                logger.error(e)

    @classmethod
    def wordle_stats(cls) -> List[WordleStatsRow]:
        with cls.lock:
            try:
                return WordleDayDB.get_stats()
            except Exception as e:
                logger.error(e)
                return []

    @classmethod
    def wordle_full(cls) -> List[WordleFullStatsRow]:
        with cls.lock:
            try:
                return WordleDayDB.get_full()
            except Exception as e:
                logger.error(e)
                return []


# не опечатка
re_wordle = re.compile(r"ордли дня #(\d+) (\w)/6", re.IGNORECASE)

def parse_wordle_message(message: telegram.Message) -> Optional[WordleDayRecord]:
    text = get_wordle_message(message)
    if text is None:
        return None

    result = re_wordle.findall(text)
    if not result:
        return None

    try:
        day = int(result[0][0])
        if day < 0:
            return None
    except ValueError:
        return None

    try:
        attempts = int(result[0][1])
        if attempts < 1 or attempts > 6:
            return None
    except ValueError:
        attempts = None

    user_id = message.from_user.id
    won = attempts is not None
    return WordleDayRecord(user_id, day, attempts, won)

def get_wordle_message(message: telegram.Message) -> Optional[str]:
    text = message.text if message.text else message.caption
    if text is None:
        return None
    # не опечатка
    if 'ордли дня' in text or '#вордли' in text:
        return text
    return None


def get_user_fullname(uid) -> str:
    if uid == bot_id():
        return 'Бот 🤖'
    user = User.get(uid)
    fullname = uid if not user else user.fullname
    return fullname


@run_async
@chat_guard
@collect_stats
@command_guard
def wordle_stats(bot: telegram.Bot, update: telegram.Update):
    stats = WordleDay.wordle_stats()
    if not stats:
        return

    result = []
    for i, r in enumerate(stats, start=1):
        fullname = get_user_fullname(r.user_id)
        head = f"{i}. <b>{fullname}</b>"
        if i == 1:
            result.append(f"{head} <code>({r.max_consecutive_days} дней, {r.avg_win_percentage}% побед, {r.avg_attempts_per_game} попыток в среднем)</code>")
        else:
            result.append(f"{head} <code>({r.max_consecutive_days}, {r.avg_win_percentage}%, {r.avg_attempts_per_game})</code>")

    header = "<b>Топ по непрерывной игре в Вордли</b>"
    body = "\n".join(result)

    send_long(bot, update.message.chat_id, f"{header}\n\n{body}")


@run_async
@chat_guard
@collect_stats
@command_guard
def wordle_full(bot: telegram.Bot, update: telegram.Update):
    stats = WordleDay.wordle_full()
    if not stats:
        return

    result = []
    for i, r in enumerate(stats, start=1):
        fullname = get_user_fullname(r.user_id)
        head = f"<b>{fullname}</b>"
        if i == 1:
            result.append(f"{head} <code>({r.total_games_played} игр, максимум {r.max_consecutive_days} дней подряд, {r.avg_win_percentage}% побед, {r.avg_attempts_per_game} попыток в среднем)</code>")
        else:
            result.append(f"{head} <code>({r.total_games_played}, {r.max_consecutive_days}, {r.avg_win_percentage}%, {r.avg_attempts_per_game})</code>")

    header = "<b>Всего сыграно в Вордли</b>"
    body = "\n".join(result)

    send_long(bot, update.message.chat_id, f"{header}\n\n{body}")
