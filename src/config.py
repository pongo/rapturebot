# coding=UTF-8

import json

with open('config.json', 'r', encoding="utf-8") as file:
    CONFIG = json.loads(file.read())

with open('chat_rules', 'r', encoding="utf-8") as file:
    CHATRULES = file.read()

with open('commands', 'r', encoding="utf-8") as file:
    CMDS = json.loads(file.read())

VALID_CMDS = []
for key, cmd in CMDS['common'].items():
    VALID_CMDS.append(cmd['name'])
for key, cmd in CMDS['admins'].items():
    VALID_CMDS.append(cmd['name'])
for key, cmd in CMDS['hidden'].items():
    VALID_CMDS.append(cmd['name'])
for cmd in CMDS['text_cmds']:
    VALID_CMDS.append(cmd)

google_vision_client = None
