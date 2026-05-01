import json
import sys
from datetime import date


def main():
    if len(sys.argv) < 2:
        print("Usage: update_config.py <enable|disable> [start_date] [end_date]")
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

    else:
        print(f"Unknown action: {action}. Use 'enable' or 'disable'.")
        sys.exit(1)

    with open("config.json", "w") as f:
        json.dump(config, f, indent=2)


if __name__ == "__main__":
    main()
