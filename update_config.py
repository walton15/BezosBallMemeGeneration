import json
import sys
from datetime import date, datetime
from zoneinfo import ZoneInfo


def main():
    if len(sys.argv) < 2:
        print("Usage: update_config.py <enable|disable> [start_date] [end_date]")
        print("       update_config.py special <date> <aggressor_line> <theme>")
        print("       update_config.py clear <date>")
        sys.exit(1)

    action = sys.argv[1]

    with open("config.json") as f:
        config = json.load(f)

    if action == "enable":
        today = date.today().isoformat()
        before = len(config.get("disabled_ranges", []))
        config["disabled_ranges"] = [
            r for r in config.get("disabled_ranges", [])
            if r["end"] < today
        ]
        removed = before - len(config["disabled_ranges"])
        print(f"Removed {removed} active/future disabled range(s). Sending is now enabled.")

    elif action == "disable":
        if len(sys.argv) < 4:
            print("Usage: update_config.py disable <start_date> <end_date>")
            sys.exit(1)
        start_date, end_date = sys.argv[2], sys.argv[3]
        config.setdefault("disabled_ranges", []).append({"start": start_date, "end": end_date})
        print(f"Disabled sending from {start_date} to {end_date}.")

    elif action in ("special", "clear"):
        if len(sys.argv) < 3:
            print(f"Usage: update_config.py {action} <date> ...")
            sys.exit(1)
        try:
            day = date.fromisoformat(sys.argv[2].strip())
        except ValueError:
            print(f"Bad date {sys.argv[2]!r}; expected YYYY-MM-DD.")
            sys.exit(1)
        special_days = config.setdefault("special_days", {})
        if action == "clear":
            removed = special_days.pop(day.isoformat(), None)
            print(f"{'Removed' if removed else 'No'} special day for {day}.")
        else:
            # A past date would never be read by generate_meme.py, so refuse
            # it rather than silently saving a dead entry.
            today_et = datetime.now(ZoneInfo("America/New_York")).date()
            if day < today_et:
                print(f"{day} is in the past (today is {today_et}); not saved.")
                sys.exit(1)
            line = sys.argv[3].strip() if len(sys.argv) > 3 else ""
            theme = sys.argv[4].strip() if len(sys.argv) > 4 else ""
            if not line and not theme:
                print("Give an aggressor line, a theme, or both.")
                sys.exit(1)
            entry = {}
            if line:
                entry["aggressor_line"] = line.upper()
            if theme:
                entry["theme"] = theme
            special_days[day.isoformat()] = entry
            print(f"Special day {day}: {entry}")

    else:
        print(f"Unknown action: {action}. Use 'enable', 'disable', 'special' or 'clear'.")
        sys.exit(1)

    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)


if __name__ == "__main__":
    main()
