import os
import functools
import json
from typing import List, NamedTuple

from src.utils.misc import get_int

try:
    with open('config.json', 'r', encoding="utf-8") as file:
        CONFIG = json.loads(file.read())
except Exception:
    # print("Can't load config.json")
    CONFIG = {}

try:
    with open('chat_rules', 'r', encoding="utf-8") as file:
        CHATRULES = file.read()
except Exception:
    # print("Can't load chat_rules")
    CHATRULES = ''

try:
    with open('commands', 'r', encoding="utf-8") as file:
        CMDS = json.loads(file.read())
except Exception:
    # print("Can't load commands")
    CMDS = {}

VALID_CMDS = []
for key, cmd in CMDS.get('common', {}).items():
    VALID_CMDS.append(cmd['name'])
for key, cmd in CMDS.get('admins', {}).items():
    VALID_CMDS.append(cmd['name'])
for key, cmd in CMDS.get('hidden', {}).items():
    VALID_CMDS.append(cmd['name'])
for cmd in CMDS.get('text_cmds', []):
    VALID_CMDS.append(cmd)

google_vision_client = None
instaloader_session_exists = os.path.isfile('instaloader.session')


class ChatInConfig(NamedTuple):
    chat_id: int
    chat_options: dict
    enabled_commands: List[str]
    disabled_commands: List[str]


@functools.lru_cache(maxsize=1)
def get_config_chats() -> List[ChatInConfig]:
    result = []
    for chat_id_str, chat_options in CONFIG.get('chats', {}).items():
        chat_id = get_int(chat_id_str)
        if chat_id is None:
            continue
        chat = ChatInConfig(chat_id,
                            chat_options,
                            chat_options.get('enabled_commands', []),
                            chat_options.get('disabled_commands', []))
        result.append(chat)
    return result
