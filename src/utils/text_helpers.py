import re


def lstrip_every_line(text: str) -> str:
    return re.sub(r"^ +", "", text, 0, re.IGNORECASE | re.MULTILINE)


def truncate(s: str, limit: int, placeholder='…') -> str:
    if len(s) <= limit:
        return s
    else:
        return s[:limit - len(placeholder)] + placeholder
