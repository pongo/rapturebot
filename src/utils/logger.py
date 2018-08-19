# coding=UTF-8

import logging

from src.config import CONFIG

logging.basicConfig(
    format=CONFIG.get('logging', {}).get('format', '[%(asctime)s][%(levelname)s] - %(message)s'),
    level=logging.getLevelName(CONFIG.get('logging', {}).get('level', 'INFO').upper()),
    filename=CONFIG.get('logging', {}).get('file', None)
)
logger = logging.getLogger(__name__)
