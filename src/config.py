# coding=UTF-8

import json
import re

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

re_ducks_trigger = re.compile(CONFIG['ducks_trigger']['re_pattern'], re.IGNORECASE | re.MULTILINE) if 'ducks_trigger' in CONFIG else None
