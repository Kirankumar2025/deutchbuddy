from datetime import datetime, timedelta
from typing import Tuple

# Simple SM-2-ish spaced repetition
def sm2_next(ease: float, interval: int, reps: int, quality: int) -> Tuple[float, int, int]:
    # quality: 0..3 (Again, Hard, Good, Easy)
    q_map = {0:1, 1:3, 2:4, 3:5}
    q = q_map.get(quality, 4)

    if q < 3:
        reps = 0
        interval = 1
    else:
        if reps == 0:
            interval = 1
        elif reps == 1:
            interval = 3
        else:
            interval = int(round(interval * ease))
        reps += 1

    ease = ease + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    if ease < 1.3:
        ease = 1.3
    return ease, interval, reps

def next_due_date(days:int):
    return (datetime.utcnow() + timedelta(days=days)).isoformat() + "Z"
