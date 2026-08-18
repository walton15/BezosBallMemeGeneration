"""Generate a year of postcard memes into weekly_mail_meme/.

Fills the weekly postcard queue with 52 images, one per mailing Monday. Weeks
whose mailing lands near a holiday get a holiday-themed meme, and their
filename carries the holiday slug so it is obvious in the folder listing:

    week_01.jpg
    week_10_halloween.jpg
    week_18_christmas.jpg

Ascending filename order still drives the rotation, because "week_10_" sorts
between "week_09" and "week_11".

Images are 1536x1024 (exactly 3:2, the 6x4 postcard aspect) so nothing is
cropped when PostGrid renders the front full-bleed.

The run is resumable: a week whose file already exists is skipped, so a job
that dies partway through can be re-dispatched without paying twice. Failures
are recorded and reported at the end rather than aborting the whole batch.

Usage:
    python generate_weekly_memes.py --list            # free: print the plan
    python generate_weekly_memes.py --limit 2         # generate the first 2
    python generate_weekly_memes.py                   # generate all 52
"""

import argparse
import base64
import glob
import os
import random
import sys
from datetime import date, timedelta

from holiday_theme import HOLIDAY_LABELS, holidays_in, label_for

# openai/PIL/generate_meme are imported lazily inside the functions that need
# them, so --list works anywhere without the image-generation dependencies.

OUT_DIR = "weekly_mail_meme"
WEEKS = 52
IMAGE_SIZE = "1536x1024"  # 3:2, matching a 6x4 postcard exactly
JPEG_QUALITY = 88

def build_schedule(start_monday):
    """[(week_no, mail_date, holiday_slug_or_None, holiday_date_or_None)]."""
    mondays = [start_monday + timedelta(weeks=i) for i in range(WEEKS)]
    by_monday = {}

    for year in {mondays[0].year, mondays[-1].year}:
        for slug, when, priority in holidays_in(year):
            monday = when - timedelta(days=when.weekday())
            # A card mailed Monday lands several days later, so a holiday on
            # Monday or Tuesday has to ship the week before to arrive in time.
            if when.weekday() in (0, 1):
                monday -= timedelta(weeks=1)
            if monday not in mondays:
                continue
            if monday not in by_monday or priority > by_monday[monday][2]:
                by_monday[monday] = (slug, when, priority)

    schedule = []
    for index, monday in enumerate(mondays, start=1):
        slug, when, _ = by_monday.get(monday, (None, None, None))
        schedule.append((index, monday, slug, when))
    return schedule


def next_monday(today):
    """The first mailing Monday strictly after today."""
    return today + timedelta(days=(0 - today.weekday()) % 7 or 7)


def filename_for(week_no, slug):
    return "week_{:02d}{}.jpg".format(week_no, "_" + slug if slug else "")


def existing_file(week_no):
    matches = glob.glob(os.path.join(OUT_DIR, "week_{:02d}*".format(week_no)))
    return matches[0] if matches else None


def generate_one(client, art_styles, scenes, slug):
    """Return (image, art_style, scene) for one week, or raise."""
    import io
    from PIL import Image
    from generate_meme import generate_scene_prompt, is_refusal

    art_style = random.choice(art_styles)
    scene = random.choice(scenes)
    holiday = label_for(slug) if slug else None

    prompt = generate_scene_prompt(client, art_style, scene, holiday=holiday)
    if is_refusal(prompt):
        # Retry once with a different style/scene draw before giving up.
        art_style, scene = random.choice(art_styles), random.choice(scenes)
        prompt = generate_scene_prompt(client, art_style, scene, holiday=holiday)
        if is_refusal(prompt):
            raise RuntimeError("prompt model refused twice")

    response = client.images.generate(
        model="gpt-image-2",
        prompt=prompt,
        size=IMAGE_SIZE,
        quality="medium",
        n=1,
    )
    raw = base64.b64decode(response.data[0].b64_json)
    return Image.open(io.BytesIO(raw)).convert("RGB"), art_style, scene


def main():
    parser = argparse.ArgumentParser(
        description="Generate a year of weekly postcard memes.")
    parser.add_argument("--list", action="store_true",
                        help="print the 52-week plan and exit (no API calls)")
    parser.add_argument("--limit", type=int,
                        help="generate at most this many images this run")
    parser.add_argument("--start-week", type=int, default=1,
                        help="first week number to consider (default 1)")
    parser.add_argument("--force", action="store_true",
                        help="regenerate weeks whose file already exists")
    parser.add_argument("--start-date",
                        help="first mailing Monday as YYYY-MM-DD "
                             "(default: the next Monday)")
    args = parser.parse_args()

    if args.start_date:
        start = date.fromisoformat(args.start_date)
        if start.weekday() != 0:
            sys.exit("ERROR: --start-date must be a Monday")
    else:
        start = next_monday(date.today())

    schedule = build_schedule(start)
    themed = sum(1 for _, _, slug, _ in schedule if slug)

    if args.list:
        print("Mailing weeks {} .. {}  ({} holiday-themed)\n".format(
            schedule[0][1], schedule[-1][1], themed))
        for week_no, monday, slug, when in schedule:
            note = ""
            if slug:
                note = "  <- {} ({:%a %b %d})".format(slug, when)
            print("  {:<28} mail {}{}".format(
                filename_for(week_no, slug), monday, note))
        return 0

    from openai import OpenAI
    from generate_meme import load_numbered_list

    os.makedirs(OUT_DIR, exist_ok=True)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    art_styles = load_numbered_list("art_styles.txt")
    scenes = load_numbered_list("scenes.txt")

    todo = [row for row in schedule if row[0] >= args.start_week]
    if not args.force:
        todo = [row for row in todo if not existing_file(row[0])]
    if args.limit:
        todo = todo[:args.limit]

    if not todo:
        print("Nothing to generate; every requested week already has an image.")
        return 0

    print("Generating {} image(s) ({} holiday-themed) into {}/\n".format(
        len(todo), sum(1 for r in todo if r[2]), OUT_DIR))

    failures = []
    for position, (week_no, monday, slug, when) in enumerate(todo, start=1):
        target = os.path.join(OUT_DIR, filename_for(week_no, slug))
        label = slug or "no holiday"
        print("[{}/{}] week {:02d} (mail {}, {}) -> {}".format(
            position, len(todo), week_no, monday, label,
            os.path.basename(target)))

        try:
            image, art_style, scene = generate_one(
                client, art_styles, scenes, slug)
        except Exception as exc:                      # noqa: BLE001
            print("    FAILED: {}: {}".format(type(exc).__name__, exc))
            failures.append((week_no, str(exc)))
            continue

        # An existing file for this week may have a different holiday suffix
        # (e.g. --force after a schedule change); drop it so only one remains.
        stale = existing_file(week_no)
        if stale and os.path.abspath(stale) != os.path.abspath(target):
            os.remove(stale)

        image.save(target, "JPEG", quality=JPEG_QUALITY)
        print("    style: {}".format(art_style[:70]))
        print("    saved {} ({:.0f} KB)".format(
            target, os.path.getsize(target) / 1024))

    done = len(glob.glob(os.path.join(OUT_DIR, "week_*")))
    print("\n{} of {} weeks now have an image.".format(done, WEEKS))
    if failures:
        print("{} failed:".format(len(failures)))
        for week_no, message in failures:
            print("  week {:02d}: {}".format(week_no, message))
        print("Re-run to retry only the missing weeks.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
