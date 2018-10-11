import logging

from src.config import CONFIG

LOGGING_CONFIG = CONFIG.get('logging', {})
BASE_LEVEL = LOGGING_CONFIG.get('level', 'INFO').upper()
SRC_LEVEL = logging.getLevelName(LOGGING_CONFIG.get('src_level', 'INFO').upper())
HAS_SRC_LEVEL = 'src_level' in LOGGING_CONFIG


def get_logger(name: str) -> logging.Logger:
    """
    Возвращает логгер, устанавливая ему уровень, как в конфиге.

    Если в конфиге есть уровень с названием модуля, то ставит уровень как там.
    Иначе если в конфиге указан уровень 'src_level', то берет его.
    Иначе не ставит уровень.
    """
    logger = logging.getLogger(name)
    if name in LOGGING_CONFIG:
        logger.setLevel(logging.getLevelName(LOGGING_CONFIG.get(name, 'INFO').upper()))
    elif HAS_SRC_LEVEL:
        logger.setLevel(SRC_LEVEL)
    return logger
