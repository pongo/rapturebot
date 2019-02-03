from src.utils.cache import cache


def cheats_key(chat_id: int, user_id: int) -> str:
    return f'i_stat:cheats:{chat_id}:{user_id}'


def cheats_found(chat_id: int, user_id: int, sum_count: int) -> bool:
    key = cheats_key(chat_id, user_id)
    sums = cache.get(key, 0)
    sums += sum_count
    if sums > 20:
        return True

    cache.set(key, sums, time=10 * 60)  # 10m
    return False
