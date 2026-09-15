# -*- coding: utf-8 -*-
"""Player level system.

Starts at level 0, caps at MAX_LEVEL. Each level costs roughly 1.5x the
previous one, rounded to a human-friendly integer (not a raw float) so the
numbers a player sees are always "nice": 5, 8, 10, 15, 25, 40, 60, 90, 140, 210.
"""

LEVEL_UP_COSTS = [5, 8, 10, 15, 25, 40, 60, 90, 140, 210]
MAX_LEVEL = len(LEVEL_UP_COSTS)

_CUMULATIVE = []
_acc = 0
for _cost in LEVEL_UP_COSTS:
    _acc += _cost
    _CUMULATIVE.append(_acc)


def compute_level(total_exp: int) -> tuple[int, int, int | None]:
    """Returns (level, exp_into_current_level, exp_needed_for_next_level).

    exp_needed_for_next_level is None once MAX_LEVEL is reached.
    """
    total_exp = max(0, int(total_exp))
    level = 0
    for i, threshold in enumerate(_CUMULATIVE, start=1):
        if total_exp >= threshold:
            level = i
        else:
            break

    prev_cum = _CUMULATIVE[level - 1] if level > 0 else 0
    exp_into = total_exp - prev_cum
    if level >= MAX_LEVEL:
        return level, exp_into, None
    return level, exp_into, LEVEL_UP_COSTS[level]
