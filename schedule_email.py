"""Pick a random send time for tonight's meme email and record it.

Run by the daily generation workflow (which fires on a reliable fixed cron
before the send window). It chooses a random target time between 6:15pm and
9:00pm ET *today* and writes it to next_send.json. The Email Meme workflow
polls every 15 min and sends once the target time has passed.

All times are computed in America/New_York so DST is handled automatically.
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import random

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# 15 min to 3 hours after 6pm ET => 18:15 to 21:00, in minutes since midnight.
WINDOW_START = 18 * 60 + 15
WINDOW_END = 21 * 60
# Never schedule the send less than this many minutes from now (guards against
# a delayed generation run picking a target that's already in the past).
MIN_LEAD = 20


def main():
    now = datetime.now(ET)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

    now_minute_of_day = now.hour * 60 + now.minute
    earliest = max(WINDOW_START, now_minute_of_day + MIN_LEAD)
    if earliest > WINDOW_END:
        earliest = WINDOW_END
    minute_of_day = random.randint(earliest, WINDOW_END)

    target_et = midnight + timedelta(minutes=minute_of_day)
    target_utc = target_et.astimezone(UTC)

    record = {
        "date": now.date().isoformat(),
        "target_utc": target_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sent": False,
    }
    with open("next_send.json", "w") as f:
        json.dump(record, f)

    print(f"Next email send: {target_et:%Y-%m-%d %H:%M %Z} "
          f"({record['target_utc']})")


if __name__ == "__main__":
    main()
