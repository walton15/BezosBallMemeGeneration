"""Decide whether the Email Meme workflow should send on this tick.

Prints "true" only when ALL of the following hold:
  - sending is enabled today (send_today.json)
  - a target time was scheduled for today (next_send.json, matching ET date)
  - that target time has now passed
  - the meme hasn't already been sent today

Otherwise prints "false". The workflow captures stdout into a step output.
"""

import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def load(path):
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def should_send():
    now = datetime.now(timezone.utc)
    today_et = datetime.now(ET).date().isoformat()

    if not load("send_today.json").get("send", False):
        return False

    sched = load("next_send.json")
    if sched.get("date") != today_et:
        return False
    if sched.get("sent", False):
        return False

    target = sched.get("target_utc")
    if not target:
        return False
    target_dt = datetime.fromisoformat(target.replace("Z", "+00:00"))
    return now >= target_dt


if __name__ == "__main__":
    print("true" if should_send() else "false")
