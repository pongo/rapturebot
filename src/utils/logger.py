# coding=UTF-8

import logging

from src.config import CONFIG

default_format = '[%(asctime)s][%(levelname)s][%(name)s] - %(message)s'
logging.basicConfig(
    format=CONFIG.get('logging', {}).get('format', default_format),
    level=logging.getLevelName(CONFIG.get('logging', {}).get('level', 'INFO').upper()),
    filename=CONFIG.get('logging', {}).get('file', None)
)
logger = logging.getLogger(__name__)
